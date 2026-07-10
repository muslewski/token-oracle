"""Persistent aggregation cache: source-owned file state + last-aggregate time
+ burn profile. Supports multi-profile via "profiles": {pname: {files, profile, events, ...}}.
Atomic writes. Never raises to the caller. Old single caches auto-migrated on load."""

import json
import os
import tempfile

AGGREGATE_INTERVAL = 30  # seconds between heavy re-scans


def load_cache(path):
    try:
        with open(path, encoding="utf-8") as fh:
            c = json.load(fh)
        if isinstance(c, dict):
            c.setdefault("lastAggregate", 0)
            # legacy single-profile migration
            if "files" in c and "profiles" not in c:
                c.setdefault("profile", [])
                c.setdefault("events", [])
            if "profiles" not in c:
                c["profiles"] = {}
            # ensure per-profile defaults
            for p in list(c.get("profiles", {}).keys()):
                pd = c["profiles"].setdefault(p, {})
                pd.setdefault("files", {})
                pd.setdefault("profile", [])
                pd.setdefault("events", [])
            return c
    except (OSError, ValueError):
        pass
    return {
        "lastAggregate": 0,
        "files": {},  # legacy
        "profile": [],
        "events": [],
        "profiles": {},
    }


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
