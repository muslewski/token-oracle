"""Stable JSON snapshot any external consumer (agentic-sage, a status bar) can
read. Schema is versioned; see ADAPTERS.md. Atomic write, never raises."""
import json
import os
from dataclasses import asdict

SCHEMA_VERSION = 1


def forecast_to_dict(f):
    return asdict(f)


def build_snapshot(forecasts, now):
    return {"schema": SCHEMA_VERSION, "generated_at": now,
            "windows": [forecast_to_dict(f) for f in forecasts]}


def default_snapshot_path():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "token-oracle", "forecast.json")


def write_snapshot(forecasts, now, path=None):
    path = os.path.expanduser(path or default_snapshot_path())
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(build_snapshot(forecasts, now), fh)
        os.replace(tmp, path)
    except OSError:
        pass
    return path
