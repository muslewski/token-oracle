"""Config loading + shipped presets. The forecast target is fully config-driven;
Claude's max20 caps ship as one preset, not as core law."""
import json
import os
from dataclasses import dataclass, field

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
    windows: list = field(default_factory=list)


def _xdg(env, default_tail):
    base = os.environ.get(env) or os.path.expanduser(default_tail)
    return base


def default_config_path():
    return os.path.join(_xdg("XDG_CONFIG_HOME", "~/.config"),
                        "token-oracle", "config.json")


def default_cache_path():
    return os.path.join(_xdg("XDG_DATA_HOME", "~/.local/share"),
                        "token-oracle", "cache.json")


def _window_from_dict(d):
    anchor = d.get("anchor")
    if isinstance(anchor, str):
        anchor = parse_ts(anchor)
    return Window(name=d["name"], cap=int(d["cap"]),
                  period_secs=int(d["period_secs"]), anchor=anchor)


def load_config(path=None):
    path = path or default_config_path()
    raw = dict(PRESETS["max20"])
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            raw.update(data)
    except (OSError, ValueError):
        pass
    windows = [_window_from_dict(w) for w in raw.get("windows", [])]
    cache_path = os.path.expanduser(raw.get("cache_path") or default_cache_path())
    return Config(source=raw.get("source", "claude_code"),
                  source_opts=raw.get("source_opts", {}),
                  cache_path=cache_path, windows=windows)
