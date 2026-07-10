"""Forecast facade: source scan -> cache -> burn profile -> per-window compute.
Supports multi-sub via config.profiles (e.g. "claude" + "grok" together).
Never raises; returns [] (single) or {} (multi) on hard failure.
Backward compatible: single-source configs behave exactly as before."""

from . import events as events_mod
from .cache import AGGREGATE_INTERVAL, load_cache, save_cache
from .config import load_config, try_get_claude_five_hour_data, try_get_claude_five_hour_remaining
from ..sources.live_web import fetch_claude_live_usage, fetch_grok_live_usage
from .contracts import Forecast
from .profile import HIST_SECS, build_profile
from .windows import compute_window


def _get_profile_config(cfg, pname, pdef):
    """Merge profile def into effective source/windows for one profile."""
    src = pdef.get("source", cfg.source)
    opts = pdef.get("source_opts", cfg.source_opts or {})
    wins = pdef.get("windows", [])
    if not wins:
        wins = [{"name": w.name, "cap": w.cap, "period_secs": w.period_secs, "anchor": getattr(w, "anchor", None)} for w in (cfg.windows or [])]
    return {"source": src, "source_opts": opts or {}, "windows": wins}


def _forecast_one(now, source_name, source_opts, windows_raw, cache_slice):
    """Run scan+compute for one (profile's) source/windows. Returns (updated_slice, list[Forecast])"""
    from ..sources.base import get_source

    try:
        src = get_source(source_name, source_opts)
    except Exception:
        return cache_slice or {}, []

    files_state = (cache_slice or {}).get("files", {}) or {}
    events = []
    prof = None
    cslice = cache_slice or {"files": {}, "events": [], "profile": [], "lastAggregate": 0}
    do_agg = (now - cslice.get("lastAggregate", 0) >= AGGREGATE_INTERVAL)
    if do_agg:
        try:
            files, evs = src.scan(files_state, now, HIST_SECS)
            events = [events_mod.normalize(e) for e in evs]
            cslice = {
                "files": files,
                "events": [list(e) for e in events],
                "lastAggregate": now,
            }
            pairs = events_mod.as_pairs(events)
            cslice["profile"] = build_profile(pairs, now)
        except Exception:
            events = [events_mod.normalize(e) for e in cslice.get("events", [])]
    else:
        events = [events_mod.normalize(e) for e in cslice.get("events", [])]
        prof = cslice.get("profile")

    pairs = events_mod.as_pairs(events)
    prof = prof or cslice.get("profile") or None

    # build Window objs from raw or existing
    wins = []
    for w in (windows_raw or []):
        try:
            if isinstance(w, dict):
                from .config import _window_from_dict as wfd
                wins.append(wfd(w))
            else:
                wins.append(w)
        except Exception:
            continue

    forecasts = []
    for w in wins:
        # Pass full normalized events (with model at idx 2) so model-filter windows (e.g. fable) work.
        # compute_window accepts either pairs or full events.
        f = compute_window(events, now, w, prof)
        # For the 5h/current block on Claude, prefer server rate-limit data (exact website
        # reset time + used%) when the overlay is present; otherwise fall back to local
        # Claude engine. This makes the "resets in X minutes" relevant and not outdated.
        # Only apply for claude_code source (avoid polluting generic tests or non-claude profiles
        # that happen to name a window "5h").
        if source_name == "claude_code" and (w.name.lower() in ("5h", "5-hour", "session", "current")) and (not getattr(f, "idle", False)):
            data = try_get_claude_five_hour_data(now)
            if data:
                if data.get("reset_in_secs") is not None:
                    object.__setattr__(f, "reset_in_secs", data["reset_in_secs"])
                if data.get("projected_pct") is not None:
                    object.__setattr__(f, "projected_pct", data["projected_pct"])
                # When server gives %, compute a consistent used for display (local logs often undercount for the current 5h)
                if data.get("projected_pct") is not None and data.get("source") == "server":
                    object.__setattr__(f, "used", int(round(data["projected_pct"] / 100.0 * w.cap)))
            else:
                claude_rem = try_get_claude_five_hour_remaining(now)
                if claude_rem is not None and claude_rem > 0:
                    object.__setattr__(f, "reset_in_secs", claude_rem)
        forecasts.append(f)

    # Live web authoritative override (real Grok.com / claude.ai numbers)
    # This fixes drift between local logs and what the user sees on the websites.
    # Only for claude_code / grok sources. If playwright not installed or not logged in, no-op.
    if source_name == "claude_code":
        live = fetch_claude_live_usage(headless=True)
        if live:
            for f in forecasts:
                nm = f.window.lower()
                cap = getattr(f, "cap", 0) or 0
                if nm in ("5h", "session", "current"):
                    if live.get("five_hour_state") == "starts_on_first_message":
                        object.__setattr__(f, "idle", True)
                        object.__setattr__(f, "projected_pct", 0.0)
                        object.__setattr__(f, "used", 0)
                        # keep a full period for reset label
                        if not getattr(f, "reset_in_secs", None):
                            object.__setattr__(f, "reset_in_secs", 18000.0)
                    elif live.get("five_hour_reset_in_secs") is not None:
                        object.__setattr__(f, "reset_in_secs", live["five_hour_reset_in_secs"])
                    if live.get("five_hour_pct") is not None:
                        object.__setattr__(f, "projected_pct", live["five_hour_pct"])
                        if cap:
                            object.__setattr__(f, "used", int(round(live["five_hour_pct"] / 100.0 * cap)))
                if nm == "fable" and live.get("fable_pct") is not None:
                    pct = live["fable_pct"]
                    object.__setattr__(f, "projected_pct", pct)
                    if cap:
                        object.__setattr__(f, "used", int(round(pct / 100.0 * cap)))
                elif nm in ("weekly", "week") and live.get("all_pct") is not None:
                    pct = live["all_pct"]
                    object.__setattr__(f, "projected_pct", pct)
                    if cap:
                        object.__setattr__(f, "used", int(round(pct / 100.0 * cap)))
    elif source_name == "grok":
        live = fetch_grok_live_usage(headless=True)
        if live:
            for f in forecasts:
                if f.window.lower() == "weekly":
                    pct = live.get("build_pct") if live.get("build_pct") is not None else live.get("overall_pct")
                    if pct is not None:
                        object.__setattr__(f, "projected_pct", pct)
                        if getattr(f, "cap", 0):
                            object.__setattr__(f, "used", int(round(pct / 100.0 * f.cap)))
                    if live.get("reset_in_secs"):
                        object.__setattr__(f, "reset_in_secs", live["reset_in_secs"])

    return cslice, forecasts


def forecast(now, config=None):
    """Backward-compat single list. When profiles configured, returns flattened
    list with each Forecast.profile set (order: sorted profile names)."""
    try:
        cfg = config or load_config()
        cache = load_cache(cfg.cache_path)
        changed = False

        if cfg.profiles:
            results = []
            prof_cache = cache.setdefault("profiles", {})
            for pname in sorted(cfg.profiles.keys()):
                pdef = cfg.profiles[pname]
                pcfg = _get_profile_config(cfg, pname, pdef)
                wraw = pcfg.get("windows") or cfg.windows
                cslice = prof_cache.setdefault(pname, {"files": {}, "events": [], "profile": [], "lastAggregate": 0})
                cslice, fs = _forecast_one(now, pcfg["source"], pcfg["source_opts"], wraw, cslice)
                prof_cache[pname] = cslice
                for f in fs:
                    if getattr(f, "profile", "default") == "default":
                        object.__setattr__(f, "profile", pname)  # dataclass frozen-safe
                    results.append(f)
                changed = True
            if changed:
                cache["lastAggregate"] = now
                save_cache(cache, cfg.cache_path)
            return results
        else:
            # legacy single path (exact previous behavior)
            from ..sources.base import get_source
            source = get_source(cfg.source, cfg.source_opts)
            if now - cache.get("lastAggregate", 0) >= AGGREGATE_INTERVAL:
                files, events = source.scan(cache.get("files", {}), now, HIST_SECS)
                events = [events_mod.normalize(e) for e in events]
                cache["files"] = files
                cache["events"] = [list(e) for e in events]
                cache["lastAggregate"] = now
                pairs = events_mod.as_pairs(events)
                cache["profile"] = build_profile(pairs, now)
                save_cache(cache, cfg.cache_path)
            else:
                events = [events_mod.normalize(e) for e in cache.get("events", [])]
            profile = cache.get("profile") or None
            # pass full events for model filters
            fs = []
            for w in cfg.windows:
                f = compute_window(events, now, w, profile)
                if cfg.source == "claude_code" and (w.name.lower() in ("5h", "5-hour", "session", "current")) and (not getattr(f, "idle", False)):
                    data = try_get_claude_five_hour_data(now)
                    if data:
                        if data.get("reset_in_secs") is not None:
                            object.__setattr__(f, "reset_in_secs", data["reset_in_secs"])
                        if data.get("projected_pct") is not None:
                            object.__setattr__(f, "projected_pct", data["projected_pct"])
                        if data.get("projected_pct") is not None and data.get("source") == "server":
                            object.__setattr__(f, "used", int(round(data["projected_pct"] / 100.0 * w.cap)))
                    else:
                        claude_rem = try_get_claude_five_hour_remaining(now)
                        if claude_rem is not None and claude_rem > 0:
                            object.__setattr__(f, "reset_in_secs", claude_rem)
                fs.append(f)

            # Live web authoritative override for legacy single-source claude/grok
            if cfg.source == "claude_code":
                live = fetch_claude_live_usage(headless=True)
                if live:
                    for f in fs:
                        nm = f.window.lower()
                        cap = getattr(f, "cap", 0) or 0
                        if nm in ("5h", "session", "current"):
                            if live.get("five_hour_state") == "starts_on_first_message":
                                object.__setattr__(f, "idle", True)
                                object.__setattr__(f, "projected_pct", 0.0)
                                object.__setattr__(f, "used", 0)
                                if not getattr(f, "reset_in_secs", None):
                                    object.__setattr__(f, "reset_in_secs", 18000.0)
                            elif live.get("five_hour_reset_in_secs") is not None:
                                object.__setattr__(f, "reset_in_secs", live["five_hour_reset_in_secs"])
                            if live.get("five_hour_pct") is not None:
                                object.__setattr__(f, "projected_pct", live["five_hour_pct"])
                                if cap:
                                    object.__setattr__(f, "used", int(round(live["five_hour_pct"] / 100.0 * cap)))
                        if nm == "fable" and live.get("fable_pct") is not None:
                            pct = live["fable_pct"]
                            object.__setattr__(f, "projected_pct", pct)
                            if cap:
                                object.__setattr__(f, "used", int(round(pct / 100.0 * cap)))
                        elif nm in ("weekly", "week") and live.get("all_pct") is not None:
                            pct = live["all_pct"]
                            object.__setattr__(f, "projected_pct", pct)
                            if cap:
                                object.__setattr__(f, "used", int(round(pct / 100.0 * cap)))
            elif cfg.source == "grok":
                live = fetch_grok_live_usage(headless=True)
                if live:
                    for f in fs:
                        if f.window.lower() == "weekly":
                            pct = live.get("build_pct") if live.get("build_pct") is not None else live.get("overall_pct")
                            if pct is not None:
                                object.__setattr__(f, "projected_pct", pct)
                                if getattr(f, "cap", 0):
                                    object.__setattr__(f, "used", int(round(pct / 100.0 * f.cap)))
                            if live.get("reset_in_secs"):
                                object.__setattr__(f, "reset_in_secs", live["reset_in_secs"])

            for f in fs:
                object.__setattr__(f, "profile", "default")
            return fs
    except Exception:
        return []


def multi_forecast(now, config=None):
    """Return dict profile_name -> list[Forecast]. For single-config, returns
    {source or "default": forecasts}."""
    fs = forecast(now, config)
    cfg = config or load_config()
    out = {}
    if cfg.profiles:
        for f in fs:
            out.setdefault(f.profile, []).append(f)
    else:
        key = getattr(cfg, "source", None) or "default"
        out[key] = fs
        if key != "default":
            out.setdefault("default", fs)
    return out


def detect_resets(prev_fs, curr_fs, threshold_drop=0.3, low_abs=10000, high_prev=50000):
    """Detect sudden resets across profiles/windows.

    Returns list of dicts: [{"profile":, "window":, "prev_used":, "curr_used":, "reset_in_secs":}, ...]
    A reset is flagged when used drops sharply (curr < prev * threshold or curr low while prev high)
    after a window's reset time or naturally.
    Use to drive alarm UI.
    """
    resets = []
    prev_map = {}
    for f in (prev_fs or []):
        key = (getattr(f, "profile", "default"), f.window)
        prev_map[key] = f
    for f in (curr_fs or []):
        if f.idle:
            continue
        key = (getattr(f, "profile", "default"), f.window)
        p = prev_map.get(key)
        if not p or p.idle:
            # new low usage after presumed reset
            if f.used < low_abs:
                resets.append({
                    "profile": key[0],
                    "window": f.window,
                    "prev_used": getattr(p, "used", 0) if p else 0,
                    "curr_used": f.used,
                    "reset_in_secs": f.reset_in_secs,
                })
            continue
        if p.used > 0 and (f.used < p.used * threshold_drop or (f.used < low_abs and p.used > high_prev)):
            resets.append({
                "profile": key[0],
                "window": f.window,
                "prev_used": p.used,
                "curr_used": f.used,
                "reset_in_secs": f.reset_in_secs,
            })
    return resets
