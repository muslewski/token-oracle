"""Stable JSON snapshot any external consumer (agentic-sage, a status bar) can
read. Schema is versioned; see ADAPTERS.md. Atomic write; returns the path, or
None when the write failed."""

import json
import os
import tempfile
from dataclasses import asdict

SCHEMA_VERSION = 1


def forecast_to_dict(f):
    return asdict(f)


def build_snapshot(forecasts, now):
    # flat list always (with .profile inside each); also grouped when multi
    windows = [forecast_to_dict(f) for f in forecasts]
    snap = {
        "schema": SCHEMA_VERSION,
        "generated_at": now,
        "windows": windows,
    }
    # convenience grouped view for multi consumers (e.g. sage)
    groups = {}
    for w in windows:
        p = w.get("profile", "default")
        groups.setdefault(p, []).append(w)
    if len(groups) > 1:
        snap["profiles"] = groups
    return snap


def default_snapshot_path():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "token-oracle", "forecast.json")


def write_snapshot(forecasts, now, path=None):
    path = os.path.expanduser(path or default_snapshot_path())
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d or ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(build_snapshot(forecasts, now), fh)
            os.replace(tmp, path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError:
        return None
    return path
