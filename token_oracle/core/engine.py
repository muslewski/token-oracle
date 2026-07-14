"""Forecast facade: source scan -> cache -> burn profile -> per-window compute.
Supports multi-sub via config.profiles (e.g. "claude" + "grok" together).
Never raises; returns [] (single) or {} (multi) on hard failure.
Backward compatible: single-source configs behave exactly as before."""

from . import events as events_mod
from .cache import AGGREGATE_INTERVAL, load_cache, save_cache
from .config import load_config, try_get_claude_five_hour_data, try_get_claude_five_hour_remaining
from .profile import HIST_SECS, build_profile
from .windows import compute_window


def _get_profile_config(cfg, pname, pdef):
    """Merge profile def into effective source/windows for one profile."""
    src = pdef.get("source", cfg.source)
    opts = pdef.get("source_opts", cfg.source_opts or {})
    wins = pdef.get("windows", [])
    if not wins:
        wins = [
            {
                "name": w.name,
                "cap": w.cap,
                "period_secs": w.period_secs,
                "anchor": getattr(w, "anchor", None),
            }
            for w in (cfg.windows or [])
        ]
    return {"source": src, "source_opts": opts or {}, "windows": wins}


def _forecast_one(now, source_name, source_opts, windows_raw, cache_slice):
    """Run scan+compute for one (profile's) source/windows.

    Returns (updated_slice, list[Forecast])
    """
    from ..sources.base import get_source

    try:
        src = get_source(source_name, source_opts)
    except Exception:
        return cache_slice or {}, []

    files_state = (cache_slice or {}).get("files", {}) or {}
    events = []
    prof = None
    cslice = cache_slice or {"files": {}, "events": [], "profile": [], "lastAggregate": 0}
    do_agg = now - cslice.get("lastAggregate", 0) >= AGGREGATE_INTERVAL
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
    for w in windows_raw or []:
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
        # Pass full normalized events (model at idx 2) so model-filter windows work.
        # compute_window accepts either pairs or full events.
        f = compute_window(events, now, w, prof)
        # For the 5h/current block on Claude, prefer server rate-limit data for the
        # *reset clock* and *used* fill when present. Do NOT write current-usage %
        # into Forecast.projected_pct — that field is end-of-window projection
        # (plan 030 semantics). Local projection stays; used is corrected from
        # server fill so statusline k/cap stays honest. Display of live current %
        # on the dash goes through LiveCell overlay, not this field.
        # Only apply for claude_code source (avoid polluting generic tests or non-claude profiles
        # that happen to name a window "5h").
        if (
            source_name == "claude_code"
            and (w.name.lower() in ("5h", "5-hour", "session", "current"))
            and (not getattr(f, "idle", False))
        ):
            data = try_get_claude_five_hour_data(now)
            if data:
                if data.get("reset_in_secs") is not None:
                    object.__setattr__(f, "reset_in_secs", data["reset_in_secs"])
                # Server current fill → used only (never projected_pct).
                if data.get("projected_pct") is not None and data.get("source") == "server":
                    object.__setattr__(f, "used", int(round(data["projected_pct"] / 100.0 * w.cap)))
            else:
                claude_rem = try_get_claude_five_hour_remaining(now)
                if claude_rem is not None and claude_rem > 0:
                    object.__setattr__(f, "reset_in_secs", claude_rem)
        forecasts.append(f)

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
                cslice = prof_cache.setdefault(
                    pname, {"files": {}, "events": [], "profile": [], "lastAggregate": 0}
                )
                prev_agg = cslice.get("lastAggregate", 0)
                cslice, fs = _forecast_one(now, pcfg["source"], pcfg["source_opts"], wraw, cslice)
                prof_cache[pname] = cslice
                for f in fs:
                    if getattr(f, "profile", "default") == "default":
                        object.__setattr__(f, "profile", pname)  # dataclass frozen-safe
                    results.append(f)
                # Only persist when a profile actually re-aggregated. Unconditional
                # save_cache of a multi-MB cache was ~5s per call and made dash lag
                # even after UI/data decoupling (single-source path already gates).
                if cslice.get("lastAggregate", 0) != prev_agg:
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
                try:
                    files, events = source.scan(cache.get("files", {}), now, HIST_SECS)
                    events = [events_mod.normalize(e) for e in events]
                    cache["files"] = files
                    cache["events"] = [list(e) for e in events]
                    cache["lastAggregate"] = now
                    pairs = events_mod.as_pairs(events)
                    cache["profile"] = build_profile(pairs, now)
                    save_cache(cache, cfg.cache_path)
                except Exception:
                    events = [events_mod.normalize(e) for e in cache.get("events", [])]
            else:
                events = [events_mod.normalize(e) for e in cache.get("events", [])]
            profile = cache.get("profile") or None
            # pass full events for model filters
            fs = []
            for w in cfg.windows:
                f = compute_window(events, now, w, profile)
                if (
                    cfg.source == "claude_code"
                    and (w.name.lower() in ("5h", "5-hour", "session", "current"))
                    and (not getattr(f, "idle", False))
                ):
                    data = try_get_claude_five_hour_data(now)
                    if data:
                        if data.get("reset_in_secs") is not None:
                            object.__setattr__(f, "reset_in_secs", data["reset_in_secs"])
                        # Server current fill → used only (never projected_pct).
                        if data.get("projected_pct") is not None and data.get("source") == "server":
                            object.__setattr__(
                                f, "used", int(round(data["projected_pct"] / 100.0 * w.cap))
                            )
                    else:
                        claude_rem = try_get_claude_five_hour_remaining(now)
                        if claude_rem is not None and claude_rem > 0:
                            object.__setattr__(f, "reset_in_secs", claude_rem)
                fs.append(f)

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

    Returns list of dicts like:
      [{"profile":, "window":, "prev_used":, "curr_used":, "reset_in_secs":}, ...]
    A reset is flagged when used drops sharply after reset time or naturally.
    Use to drive alarm UI.
    """
    resets = []
    prev_map = {}
    for f in prev_fs or []:
        key = (getattr(f, "profile", "default"), f.window)
        prev_map[key] = f
    for f in curr_fs or []:
        if f.idle:
            continue
        key = (getattr(f, "profile", "default"), f.window)
        p = prev_map.get(key)
        if not p or p.idle:
            # new low usage after presumed reset
            if f.used < low_abs:
                resets.append(
                    {
                        "profile": key[0],
                        "window": f.window,
                        "prev_used": getattr(p, "used", 0) if p else 0,
                        "curr_used": f.used,
                        "reset_in_secs": f.reset_in_secs,
                    }
                )
            continue
        if p.used > 0 and (
            f.used < p.used * threshold_drop or (f.used < low_abs and p.used > high_prev)
        ):
            resets.append(
                {
                    "profile": key[0],
                    "window": f.window,
                    "prev_used": p.used,
                    "curr_used": f.used,
                    "reset_in_secs": f.reset_in_secs,
                }
            )
    return resets


def cached_events(config=None):
    """Normalized event list from the on-disk cache WITHOUT re-scanning
    (a cheap read for the statusline hot path, which runs after forecast() has
    already refreshed the cache). Single-source: cache['events']. Multi-profile:
    concatenation of every profiles[*]['events']. Returns [] on any problem.
    Never raises."""
    try:
        cfg = config or load_config()
        cache = load_cache(cfg.cache_path)
        raw = []
        if isinstance(cache, dict):
            # legacy single-source lives at top-level "events"; multi under profiles
            # load_cache always injects "profiles":{} so we collect top + profiles
            raw.extend((cache or {}).get("events") or [])
            if isinstance(cache.get("profiles"), dict):
                for slc in cache["profiles"].values():
                    if isinstance(slc, dict):
                        raw.extend(slc.get("events") or [])
        return [
            events_mod.normalize(e) for e in raw if isinstance(e, (list, tuple)) and len(e) >= 2
        ]
    except Exception:
        return []
