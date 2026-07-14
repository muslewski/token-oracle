"""Config loading + shipped presets. The forecast target is fully config-driven;
max20 (and other) caps ship as presets (Claude/Grok/etc), not as core law.
Source is pluggable: claude_code (default), grok, generic, or third-party."""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

from .contracts import Window
from .timeutil import parse_ts


def _should_apply_real_claude_limits() -> bool:
    """Use real caps/anchor from ~/.claude/usage-limits.json except in tests
    (to keep preset expectations stable) or when opted out."""
    if os.environ.get("TOKEN_ORACLE_NO_REAL_LIMITS"):
        return False
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return True


def try_get_claude_five_hour_remaining(now: float | None = None) -> float | None:
    """Best-effort to get the 5h reset remaining seconds.

    Priority:
    1. Server truth from token_forecast.ratelimits (or ~/token-forecast/src) if present.
       This gives the exact number the cloud website shows (secs_to_reset).
    2. Fall back to Claude Code's local ~/.claude/usage_limits.py compute_block.
       Matches what local claude status/tmux show.

    Returns None if nothing available. This is what makes the 5h "real" when the
    rate-limit overlay is installed in the user's environment.
    """
    if now is None:
        import time as _t

        now = _t.time()

    # Own ingested header (works for any user who wires `oracle statusline`).
    # Use last known server value if we have a reasonably recent ingest, even if
    # the internal view marks the window "stale" (e.g. at exact roll boundary).
    # This keeps the tmux/status bar numbers stable on the server truth instead
    # of flipping to local event sums.
    try:
        from . import ratelimits as _own_rl

        d = _own_rl.five_hour(now)
        if d and isinstance(d, dict):
            obs = d.get("observed_at")
            if obs is not None and (now - float(obs) < 600):  # last 10 min
                rem = d.get("secs_to_reset")
                if rem is not None:
                    return float(rem)
    except Exception:
        pass

    # 1. Try server truth (what the website uses)
    try:
        import sys

        try:
            import token_forecast.ratelimits as RL
        except Exception:
            p = os.path.expanduser("~/token-forecast/src")
            if p not in sys.path:
                sys.path.insert(0, p)
            import token_forecast.ratelimits as RL

        if hasattr(RL, "five_hour"):
            data = RL.five_hour(now)
            if data and isinstance(data, dict):
                rem = data.get("secs_to_reset")
                if rem is not None and not data.get("stale", False):
                    return float(rem)
    except Exception:
        pass  # no server truth available, fall through

    # 2. Local Claude engine (best local approximation)
    try:
        import importlib.util

        path = os.path.expanduser("~/.claude/usage_limits.py")
        if not os.path.exists(path):
            return None
        spec = importlib.util.spec_from_file_location("_claude_ul", path)
        if spec is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        if spec.loader is None:
            return None
        spec.loader.exec_module(mod)
        cfg = mod.load_limits()
        cap = cfg.get("fiveHourCap")
        if not cap:
            return None
        c = mod.load_cache()
        agg_int = getattr(mod, "AGGREGATE_INTERVAL", 30)
        if now - c.get("lastAggregate", 0) >= agg_int:
            c, evs = mod.scan_events(c, now)
            c["lastAggregate"] = now
            if hasattr(mod, "build_profile"):
                c["profile"] = mod.build_profile(evs, now)
            try:
                mod.save_cache(c)
            except Exception:
                pass
        else:
            evs = mod.events_from_cache(c, now)
        prof = c.get("profile")
        blk = mod.compute_block(evs, now, cap, profile=prof)
        if blk and not blk.get("idle", False):
            rem = blk.get("remaining")
            if rem is not None:
                return float(rem)
    except Exception:
        return None
    return None


def try_get_claude_five_hour_data(now: float | None = None):
    """Best-effort for current 5h. Prefers exact server data (website) when
    token_forecast.ratelimits is available. Falls back to local.
    """
    if now is None:
        import time as _t

        now = _t.time()

    # Own ingested header (works for any user who wires `oracle statusline`).
    # Use last known server value if we have a reasonably recent ingest (see
    # comment in try_get_claude_five_hour_remaining). This makes the 5h "used"
    # and % shown in `oracle tmux` / forecast stable on the server bucket fill
    # instead of oscillating with local event sums or re-anchoring.
    try:
        from . import ratelimits as _own_rl

        d = _own_rl.five_hour(now)
        if d and isinstance(d, dict):
            obs = d.get("observed_at")
            if obs is not None and (now - float(obs) < 600):
                rem = d.get("secs_to_reset")
                sp = d.get("used_percentage")
                if rem is not None:
                    return {
                        "reset_in_secs": float(rem),
                        "projected_pct": float(sp) if sp is not None else None,
                        "source": "server",
                    }
    except Exception:
        pass

    # Server (exact)
    try:
        import sys

        try:
            import token_forecast.ratelimits as RL
        except Exception:
            p = os.path.expanduser("~/token-forecast/src")
            if p not in sys.path:
                sys.path.insert(0, p)
            import token_forecast.ratelimits as RL
        if hasattr(RL, "five_hour"):
            d = RL.five_hour(now)
            if d and isinstance(d, dict) and not d.get("stale", False):
                rem = d.get("secs_to_reset")
                sp = d.get("used_percentage")
                if rem is not None:
                    return {
                        "reset_in_secs": float(rem),
                        "projected_pct": float(sp) if sp is not None else None,
                        "source": "server",
                    }
    except Exception:
        pass

    # Local
    try:
        import importlib.util

        path = os.path.expanduser("~/.claude/usage_limits.py")
        if not os.path.exists(path):
            return None
        spec = importlib.util.spec_from_file_location("_claude_ul", path)
        if spec is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        if spec.loader is None:
            return None
        spec.loader.exec_module(mod)
        cfg = mod.load_limits()
        cap = cfg.get("fiveHourCap") or 0
        c = mod.load_cache()
        agg = getattr(mod, "AGGREGATE_INTERVAL", 30)
        if now - c.get("lastAggregate", 0) >= agg:
            c, evs = mod.scan_events(c, now)
            c["lastAggregate"] = now
            if hasattr(mod, "build_profile"):
                c["profile"] = mod.build_profile(evs, now)
            try:
                mod.save_cache(c)
            except Exception:
                pass
        else:
            evs = mod.events_from_cache(c, now)
        blk = mod.compute_block(evs, now, cap, profile=c.get("profile"))
        if blk and not blk.get("idle", False):
            return {
                "reset_in_secs": float(blk.get("remaining", 0)),
                "projected_pct": blk.get("projected_pct"),
                "source": "local",
            }
    except Exception:
        pass
    return None


PRESETS = {
    "pro": {
        # change to "grok" (or "generic") in your config.json for other harnesses
        "source": "claude_code",
        "windows": [
            {"name": "5h", "cap": 19000, "period_secs": 18000},
            {"name": "weekly", "cap": 700000, "period_secs": 604800, "anchor": None},
        ],
    },
    "max5": {
        # change to "grok" (or "generic") in your config.json for other harnesses
        "source": "claude_code",
        "windows": [
            {"name": "5h", "cap": 88000, "period_secs": 18000},
            {"name": "weekly", "cap": 3200000, "period_secs": 604800, "anchor": None},
        ],
    },
    "max20": {
        # change to "grok" (or "generic") in your config.json for other harnesses
        "source": "claude_code",
        "windows": [
            {"name": "5h", "cap": 220000, "period_secs": 18000},
            {"name": "weekly", "cap": 8000000, "period_secs": 604800, "anchor": None},
        ],
    },
    # Example single for SuperGrok Heavy (tune caps to your plan; use in profiles for multi)
    # The real weekly allowance for SuperGrok/Grok-build is server-side and high;
    # local signals give context fill (not quota burn). Set cap so % matches your UI (e.g. 1%).
    "supergrok": {
        "source": "grok",
        "source_opts": {"sessions_dir": "~/.grok/sessions"},
        "windows": [
            {"name": "weekly", "cap": 100000000, "period_secs": 604800, "anchor": None},
        ],
    },
}

_COST_MODES = ("auto", "calculate", "display", "off")


@dataclass
class Config:
    source: str = "claude_code"  # "grok" for Grok Build sessions; see sources/ for adding more
    source_opts: dict = field(default_factory=dict)
    cache_path: str = ""
    windows: list[Window] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    plan: str = "max20"
    cost_mode: str = "auto"
    pricing: dict = field(default_factory=dict)
    profiles: dict = field(
        default_factory=dict
    )  # multi-sub: {"claude": {"source":.., "windows":..}, "grok": ...}
    live: dict = field(default_factory=dict)  # {"headed": bool} — real (headed) live probing
    snapshot_writethrough: bool = False  # when true, forecast/statusline/tmux also refresh snapshot

    def headed_enabled(self) -> bool:
        return bool(self.live.get("headed"))


def _xdg(env, default_tail):
    base = os.environ.get(env) or os.path.expanduser(default_tail)
    return base


def default_config_path():
    return os.path.join(_xdg("XDG_CONFIG_HOME", "~/.config"), "token-oracle", "config.json")


PROJECT_CONFIG_NAME = ".token-oracle.json"


def find_config_path(cwd=None):
    """Resolution order (first hit wins):

    1. ``$TOKEN_ORACLE_CONFIG`` (env)
    2. ``.token-oracle.json`` in cwd or any ancestor (stop after the user's
       home directory or filesystem root; hard cap 40 levels)
    3. ``default_config_path()`` (global XDG — returned even if absent)
    """
    env = os.environ.get("TOKEN_ORACLE_CONFIG")
    if env:
        return os.path.expanduser(env)

    start = os.path.abspath(cwd or os.getcwd())
    home = os.path.abspath(os.path.expanduser("~"))
    cur = start
    for _ in range(40):
        candidate = os.path.join(cur, PROJECT_CONFIG_NAME)
        if os.path.isfile(candidate):
            return candidate
        # stop after checking home; do not walk above it
        if os.path.normpath(cur) == os.path.normpath(home):
            break
        parent = os.path.dirname(cur)
        if parent == cur:  # filesystem root
            break
        cur = parent
    return default_config_path()


def config_provenance(path=None, cwd=None) -> str:
    """Which resolution rule produced the active config path.

    Returns one of: ``--config``, ``env``, ``project``, ``global``.
    When ``path`` is an explicit ``--config`` argument, always ``--config``.
    """
    if path is not None:
        return "--config"
    if os.environ.get("TOKEN_ORACLE_CONFIG"):
        return "env"
    resolved = find_config_path(cwd=cwd)
    if os.path.basename(resolved) == PROJECT_CONFIG_NAME:
        return "project"
    return "global"


def default_cache_path():
    return os.path.join(_xdg("XDG_DATA_HOME", "~/.local/share"), "token-oracle", "cache.json")


def load_claude_limits():
    """Read real plan caps + weekly anchor from Claude Code's usage-limits.json if present.
    Source of truth for cloud weekly reset timing and caps (5h + weekly).
    Returns keys: fiveHourCap, weeklyCap, weeklyResetAnchor, plan (as present)."""
    p = os.path.expanduser("~/.claude/usage-limits.json")
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            keys = ("fiveHourCap", "weeklyCap", "weeklyResetAnchor", "plan")
            return {k: data[k] for k in keys if k in data}
    except Exception:
        pass
    return {}


def _window_from_dict(d) -> Window:
    """Build one Window from a config dict. Raises ValueError on any invalid field."""
    if not isinstance(d, dict):
        raise ValueError("window entry must be an object")
    try:
        name = str(d["name"])
        cap = int(d["cap"])
        period = int(d["period_secs"])
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"missing or invalid field: {e}") from e
    if cap <= 0 or period <= 0:
        raise ValueError("cap and period_secs must be > 0")
    anchor = d.get("anchor")
    if isinstance(anchor, str):
        parsed = parse_ts(anchor)
        if parsed is None:
            raise ValueError(f"anchor {anchor!r} is not a parseable ISO 8601 timestamp")
        anchor = parsed
    elif anchor is not None and not isinstance(anchor, (int, float)):
        raise ValueError("anchor must be null, a number, or an ISO 8601 string")
    model = d.get("model")
    if model is not None:
        model = str(model)
    return Window(name=name, cap=cap, period_secs=period, anchor=anchor, model=model)


# Bands for accepting an external cap relative to the shipped preset cap.
_CAP_BAND_LOW = 0.2
_CAP_BAND_HIGH = 5.0


def _preset_caps(plan: str) -> tuple[int | None, int | None]:
    """(five_hour_cap, weekly_cap) from the shipped preset for `plan` (max20 fallback)."""
    pdef = PRESETS.get(plan) or PRESETS.get("max20") or {}
    if not isinstance(pdef, dict):
        pdef = {}
    five = wk = None
    for w in pdef.get("windows", []):
        if not isinstance(w, dict):
            continue
        nm = str(w.get("name", "")).lower()
        cap = w.get("cap")
        if not isinstance(cap, (int, float)):
            continue
        if nm in ("5h", "5-hour", "session", "current"):
            five = int(cap)
        elif nm in ("weekly", "week", "fable"):
            wk = int(cap)
    return five, wk


def _validate_external_caps(raw_five, raw_wk, preset_five, preset_wk):
    """Reject semantically-impossible external caps. Returns
    (five_or_None, wk_or_None, issues). None means 'rejected — use the preset'."""
    issues: list[str] = []

    def _check(ext, preset, label):
        if ext is None:
            return None  # nothing supplied -> preset (no issue)
        if not isinstance(ext, (int, float)) or isinstance(ext, bool):
            issues.append(f"external {label} {ext!r} rejected (not a number) — keeping preset")
            return None
        try:
            extf = float(ext)
        except (TypeError, ValueError):
            issues.append(f"external {label} {ext!r} rejected (not a number) — keeping preset")
            return None
        if not (extf > 0) or extf != extf or extf in (float("inf"), float("-inf")):
            issues.append(
                f"external {label} {ext} rejected (non-positive/non-finite) — keeping preset"
            )
            return None
        if preset and preset > 0:
            ratio = extf / preset
            if ratio < _CAP_BAND_LOW or ratio > _CAP_BAND_HIGH:
                issues.append(
                    f"external {label} {int(extf)} rejected "
                    f"({ratio:.0f}x the preset {int(preset)}, implausible) — keeping preset"
                )
                return None
        return int(extf)

    five = _check(raw_five, preset_five, "fiveHourCap")
    wk = _check(raw_wk, preset_wk, "weeklyCap")

    # Cross-window invariant: a 5h cap cannot be >= the weekly cap.
    eff_five = five if five is not None else preset_five
    eff_wk = wk if wk is not None else preset_wk
    if eff_five is not None and eff_wk is not None and eff_five >= eff_wk:
        # Only complain if the *external* 5h value is the culprit (don't fault a clean preset).
        if five is not None:
            issues.append(
                f"external fiveHourCap {int(five)} rejected "
                f"(>= weekly cap {int(eff_wk)}, impossible) — keeping preset"
            )
        five = None

    return five, wk, issues


def load_config(path: str | None = None) -> "Config":
    # Explicit --config wins; else discovery (env / project / global XDG).
    path = os.path.expanduser(path) if path is not None else find_config_path()
    issues: list[str] = []
    expanded_path = os.path.expanduser(path)
    data: dict[str, Any] | None = None
    if os.path.exists(expanded_path):
        try:
            with open(expanded_path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                data = loaded
            else:
                issues.append(
                    f"config file {path} is not a JSON object "
                    f"(got {type(loaded).__name__}) — using built-in max20 preset"
                )
        except (OSError, ValueError):
            issues.append(
                f"config file {path} is unreadable or not valid JSON — using built-in max20 preset"
            )

    # raw = max20 defaults ∪ chosen plan preset ∪ explicit file keys (file
    # keys always win — same "last update wins" rule as before plan support).
    base = PRESETS.get("max20") if isinstance(PRESETS, dict) else None
    raw: dict[str, Any] = dict(base) if isinstance(base, dict) else {}
    plan = data.get("plan") if isinstance(data, dict) else None
    if plan is not None:
        pdef = PRESETS.get(plan) if isinstance(PRESETS, dict) else None
        if isinstance(plan, str) and isinstance(pdef, dict):
            raw.update(pdef)
        else:
            issues.append(f'config "plan" {plan!r} is unknown — using built-in max20 preset')
            plan = "max20"
    else:
        plan = "max20"
    pwin = PRESETS.get("max20") if isinstance(PRESETS, dict) else None
    preset_windows = raw.get("windows", pwin.get("windows") if isinstance(pwin, dict) else [])
    if isinstance(data, dict):
        raw.update(data)

    raw_windows = raw.get("windows", [])
    if not isinstance(raw_windows, list):
        issues.append('config "windows" must be a list — using built-in max20 preset windows')
        raw_windows = preset_windows

    # Apply real caps + weeklyResetAnchor (cloud truth) from ~/.claude/usage-limits.json.
    # - fiveHourCap -> any 5h / session-ish window cap
    # - weeklyCap -> weekly + fable (model-specific weekly shares the period)
    # - weeklyResetAnchor -> set on weekly/fable windows (fixed grid, exact server reset)
    # Only for claude-sourced profiles/top-level; user config values for other fields preserved.
    is_claudeish = (
        raw.get("source") in (None, "claude_code")
        or "claude" in str(raw.get("source", "")).lower()
        or any("claude" in str(k).lower() for k in (raw.get("profiles") or {}))
    )
    five_cap = None
    wk_cap = None
    wk_anchor = None
    if is_claudeish and _should_apply_real_claude_limits():
        claude_limits = load_claude_limits()
        _pf, _pw = _preset_caps(plan)
        five_cap, wk_cap, _cap_issues = _validate_external_caps(
            claude_limits.get("fiveHourCap"), claude_limits.get("weeklyCap"), _pf, _pw
        )
        issues.extend(_cap_issues)
        wk_anchor_str = claude_limits.get("weeklyResetAnchor")
        wk_anchor = parse_ts(wk_anchor_str) if wk_anchor_str else None
        fixed = []
        for w in raw_windows:
            if isinstance(w, dict):
                ww = dict(w)
                nm = str(ww.get("name", "")).lower()
                if five_cap and (
                    "5h" in nm or "5-hour" in nm or nm in ("5h", "session", "current")
                ):
                    ww["cap"] = int(five_cap)
                if wk_cap and nm in ("weekly", "week", "fable"):
                    ww["cap"] = int(wk_cap)
                # Prefer server anchor for weekly (unless user overrode with explicit anchor)
                if (
                    wk_anchor is not None
                    and nm in ("weekly", "week", "fable")
                    and ww.get("anchor") in (None, "null")
                ):
                    ww["anchor"] = wk_anchor
                fixed.append(ww)
            else:
                fixed.append(w)
        raw_windows = fixed

    windows: list[Window] = []
    for i, w in enumerate(raw_windows):
        try:
            windows.append(_window_from_dict(w))
        except (KeyError, TypeError, ValueError) as e:
            issues.append(f"windows[{i}]: {e} — entry skipped")

    raw_cache_path = raw.get("cache_path")
    if raw_cache_path and not isinstance(raw_cache_path, str):
        issues.append('config "cache_path" must be a string — using default cache path')
        raw_cache_path = None
    cache_path = os.path.expanduser(raw_cache_path or default_cache_path())

    cost_mode = raw.get("cost_mode", "auto")
    if cost_mode not in _COST_MODES:
        issues.append(f'config "cost_mode" {cost_mode!r} is invalid — using "auto"')
        cost_mode = "auto"

    pricing = raw.get("pricing", {})
    if not isinstance(pricing, dict):
        issues.append('config "pricing" must be an object — ignoring')
        pricing = {}

    profiles = raw.get("profiles", {})
    if not isinstance(profiles, dict):
        issues.append('config "profiles" must be an object — ignoring multi profiles')
        profiles = {}

    # Apply real caps + anchors also to per-profile windows (for "claude", "grok+claude" setups).
    # Re-fetch limits (cheap) to avoid stale var issues.
    five_cap = None
    wk_cap = None
    wk_anchor = None
    if _should_apply_real_claude_limits():
        claude_limits = load_claude_limits()
        _pf, _pw = _preset_caps(plan)
        five_cap, wk_cap, _ = _validate_external_caps(
            claude_limits.get("fiveHourCap"), claude_limits.get("weeklyCap"), _pf, _pw
        )
        wk_anchor_str = claude_limits.get("weeklyResetAnchor")
        wk_anchor = parse_ts(wk_anchor_str) if wk_anchor_str else None
        for pname, pdef in list(profiles.items()):
            if not isinstance(pdef, dict):
                continue
            src = pdef.get("source", raw.get("source", ""))
            if "claude" in str(pname).lower() or str(src) == "claude_code":
                pw = pdef.get("windows") or []
                fixed = []
                for w in pw:
                    if isinstance(w, dict):
                        ww = dict(w)
                        nm = str(ww.get("name", "")).lower()
                        if five_cap and (
                            "5h" in nm or "5-hour" in nm or nm in ("5h", "session", "current")
                        ):
                            ww["cap"] = int(five_cap)
                        if wk_cap and nm in ("weekly", "week", "fable"):
                            ww["cap"] = int(wk_cap)
                        if (
                            wk_anchor is not None
                            and nm in ("weekly", "week", "fable")
                            and ww.get("anchor") in (None, "null")
                        ):
                            ww["anchor"] = wk_anchor
                        fixed.append(ww)
                    else:
                        fixed.append(w)
                if fixed:
                    pdef["windows"] = fixed

    # Normalize profiles entries (shallow copy so callers can augment)
    norm_profiles = {}
    for pname, pdef in profiles.items():
        if isinstance(pdef, dict):
            norm_profiles[str(pname)] = dict(pdef)
        else:
            issues.append(f"profiles[{pname!r}] ignored (not an object)")

    live = raw.get("live", {})
    if not isinstance(live, dict):
        issues.append('config "live" must be an object — ignoring')
        live = {}
    else:
        h = live.get("headed", False)
        if not isinstance(h, bool):
            issues.append('config "live.headed" must be true/false — ignoring')
            live = {}
        else:
            live = {"headed": h}

    return Config(
        source=raw.get("source", "claude_code"),
        source_opts=raw.get("source_opts", {}),
        cache_path=cache_path,
        windows=windows,
        issues=issues,
        plan=plan,
        cost_mode=cost_mode,
        pricing=pricing,
        profiles=norm_profiles,
        live=live,
        snapshot_writethrough=bool(raw.get("snapshot_writethrough", False)),
    )


def write_default_config(path=None, preset="max20", force=False, cost_mode=None) -> str:
    """Write a starter config. When the file already exists and force is false,
    return the path without modifying it (caller prints the clobber message).

    Body is the chosen preset plus a ``plan`` key; optional ``cost_mode`` is
    written when provided (wizard / explicit callers).
    """
    path = os.path.expanduser(path or default_config_path())
    if os.path.exists(path) and not force:
        return path
    if preset not in PRESETS:
        preset = "max20"
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    raw_preset = PRESETS.get(preset) or PRESETS.get("max20") or {}
    body: dict = dict(raw_preset) if isinstance(raw_preset, dict) else {}
    body["plan"] = preset
    if cost_mode is not None:
        body["cost_mode"] = cost_mode
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(body, fh, indent=2)
        fh.write("\n")
    return path


def update_config_file(path: str | None, updates: dict) -> str:
    """Deep-ish merge `updates` into the JSON config at `path` (or the default
    path), preserving all other keys, and write atomically. Returns the path."""
    import tempfile

    path = os.path.expanduser(path or default_config_path())
    data = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            data = {}
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(data.get(k), dict):
            merged = dict(data[k])
            merged.update(v)
            data[k] = merged
        else:
            data[k] = v
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d or ".", prefix=".config-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return path
