"""Persistent aggregation cache: source-owned file state + last-aggregate time
+ burn profile. Atomic writes. Never raises to the caller."""

import json
import os
import tempfile

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
        fd, tmp = tempfile.mkstemp(dir=d or ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(cache, fh)
            os.replace(tmp, path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError:
        pass
