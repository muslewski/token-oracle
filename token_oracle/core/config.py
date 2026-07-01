"""Config loading + shipped presets. The forecast target is fully config-driven;
Claude's max20 caps ship as one preset, not as core law."""

import json
import os
from dataclasses import dataclass, field
from typing import Any

from .contracts import Window
from .timeutil import parse_ts

PRESETS = {
    "max20": {
        "source": "claude_code",
        "windows": [
            {"name": "5h", "cap": 220000, "period_secs": 18000},
            {"name": "weekly", "cap": 8000000, "period_secs": 604800, "anchor": None},
        ],
    },
}


@dataclass
class Config:
    source: str = "claude_code"
    source_opts: dict = field(default_factory=dict)
    cache_path: str = ""
    windows: list[Window] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


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
    raw: dict[str, Any] = dict(PRESETS["max20"])
    issues: list[str] = []
    expanded_path = os.path.expanduser(path)
    if os.path.exists(expanded_path):
        try:
            with open(expanded_path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                raw.update(data)
        except (OSError, ValueError):
            issues.append(
                f"config file {path} is unreadable or not valid JSON — using built-in max20 preset"
            )

    raw_windows = raw.get("windows", [])
    if not isinstance(raw_windows, list):
        issues.append('config "windows" must be a list — using built-in max20 preset windows')
        raw_windows = PRESETS["max20"]["windows"]

    windows: list[Window] = []
    for i, w in enumerate(raw_windows):
        try:
            windows.append(_window_from_dict(w))
        except (KeyError, TypeError, ValueError) as e:
            issues.append(f"windows[{i}]: {e} — entry skipped")

    cache_path = os.path.expanduser(raw.get("cache_path") or default_cache_path())
    return Config(
        source=raw.get("source", "claude_code"),
        source_opts=raw.get("source_opts", {}),
        cache_path=cache_path,
        windows=windows,
        issues=issues,
    )
