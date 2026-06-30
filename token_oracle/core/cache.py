"""Persistent aggregation cache: source-owned file state + last-aggregate time
+ burn profile. Atomic writes. Never raises to the caller."""

import json
import os

AGGREGATE_INTERVAL = 30  # seconds between heavy re-scans


def load_cache(path):
    try:
        with open(path, encoding="utf-8") as fh:
            c = json.load(fh)
        if isinstance(c, dict) and "files" in c:
            c.setdefault("lastAggregate", 0)
            c.setdefault("profile", [])
            return c
    except (OSError, ValueError):
        pass
    return {"files": {}, "lastAggregate": 0, "profile": []}


def save_cache(cache, path):
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cache, fh)
        os.replace(tmp, path)
    except OSError:
        pass


def collect_events(files_state, cutoff):
    out = []
    for ent in files_state.values():
        for ts, tok in ent.get("events", []):
            if ts >= cutoff:
                out.append((float(ts), int(tok)))
    out.sort()
    return out


def events_from_cache(cache, now, window):
    return collect_events(cache.get("files", {}), now - window)
