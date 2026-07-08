"""Config loading + shipped presets. The forecast target is fully config-driven;
Claude's max20 caps ship as one preset, not as core law."""

import json
import os
from dataclasses import dataclass, field
from typing import Any

from .contracts import Window
from .timeutil import parse_ts

PRESETS = {
    "pro": {
        "source": "claude_code",
        "windows": [
            {"name": "5h", "cap": 19000, "period_secs": 18000},
            {"name": "weekly", "cap": 700000, "period_secs": 604800, "anchor": None},
        ],
    },
    "max5": {
        "source": "claude_code",
        "windows": [
            {"name": "5h", "cap": 88000, "period_secs": 18000},
            {"name": "weekly", "cap": 3200000, "period_secs": 604800, "anchor": None},
        ],
    },
    "max20": {
        "source": "claude_code",
        "windows": [
            {"name": "5h", "cap": 220000, "period_secs": 18000},
            {"name": "weekly", "cap": 8000000, "period_secs": 604800, "anchor": None},
        ],
    },
}

_COST_MODES = ("auto", "calculate", "display", "off")


@dataclass
class Config:
    source: str = "claude_code"
    source_opts: dict = field(default_factory=dict)
    cache_path: str = ""
    windows: list[Window] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    plan: str = "max20"
    cost_mode: str = "auto"
    pricing: dict = field(default_factory=dict)


def _xdg(env, default_tail):
    base = os.environ.get(env) or os.path.expanduser(default_tail)
    return base


def default_config_path():
    return os.path.join(_xdg("XDG_CONFIG_HOME", "~/.config"), "token-oracle", "config.json")


def default_cache_path():
    return os.path.join(_xdg("XDG_DATA_HOME", "~/.local/share"), "token-oracle", "cache.json")


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
    return Window(name=name, cap=cap, period_secs=period, anchor=anchor)


def load_config(path: str | None = None) -> "Config":
    path = path or default_config_path()
    issues: list[str] = []
    expanded_path = os.path.expanduser(path)
    data: dict[str, Any] | None = None
    if os.path.exists(expanded_path):
        try:
            with open(expanded_path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            issues.append(
                f"config file {path} is unreadable or not valid JSON — using built-in max20 preset"
            )

    # raw = max20 defaults ∪ chosen plan preset ∪ explicit file keys (file
    # keys always win — same "last update wins" rule as before plan support).
    raw: dict[str, Any] = dict(PRESETS["max20"])
    plan = data.get("plan") if data else None
    if plan is not None:
        if isinstance(plan, str) and plan in PRESETS:
            raw.update(PRESETS[plan])
        else:
            issues.append(f'config "plan" {plan!r} is unknown — using built-in max20 preset')
            plan = "max20"
    else:
        plan = "max20"
    preset_windows = raw.get("windows", PRESETS["max20"]["windows"])
    if data:
        raw.update(data)

    raw_windows = raw.get("windows", [])
    if not isinstance(raw_windows, list):
        issues.append('config "windows" must be a list — using built-in max20 preset windows')
        raw_windows = preset_windows

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

    return Config(
        source=raw.get("source", "claude_code"),
        source_opts=raw.get("source_opts", {}),
        cache_path=cache_path,
        windows=windows,
        issues=issues,
        plan=plan,
        cost_mode=cost_mode,
        pricing=pricing,
    )


def write_default_config(path=None, preset="max20", force=False) -> str:
    path = os.path.expanduser(path or default_config_path())
    if os.path.exists(path) and not force:
        return path
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(PRESETS[preset], fh, indent=2)
    return path
