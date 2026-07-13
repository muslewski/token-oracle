"""Self-ingested Claude rate-limit header (server truth for 5h / weekly).

Claude Code hands its statusline command a `rate_limits` block on stdin each
render. ingest() folds the freshest reading per window into a small JSON
snapshot; five_hour()/weekly() read it back. Monotonic within a window; a
forward jump in resets_at means a reset. Stdlib only. Never raises to callers.
"""

import json
import os
import tempfile
import time

WINDOWS = {"five_hour": 5 * 3600, "seven_day": 7 * 24 * 3600}


def default_path() -> str:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "token-oracle", "ratelimits.json")


def _coerce(reading):
    """A rate_limits sub-dict -> {used_percentage, resets_at} floats, or None."""
    if not isinstance(reading, dict):
        return None
    try:
        pct = float(reading["used_percentage"])
        resets_at = float(reading["resets_at"])
    except (KeyError, TypeError, ValueError):
        return None
    if resets_at <= 0:
        return None
    return {"used_percentage": pct, "resets_at": resets_at}


def _load(path) -> dict:
    """Never raises; {} on missing/corrupt/unreadable."""
    path = os.path.expanduser(path or default_path())
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
        return {}
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _save(path, snap) -> None:
    """Atomic mkstemp + os.replace in target dir; never raises to caller."""
    path = os.path.expanduser(path or default_path())
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d or ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(snap, fh)
            os.replace(tmp, path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError:
        pass  # swallow; statusline hot path must not raise


def _is_new_window(old, new, secs):
    return new["resets_at"] - old["resets_at"] > secs / 2.0


def _is_older_window(old, new, secs):
    return new["resets_at"] - old["resets_at"] < -secs / 2.0


def ingest(rate_limits, now=None, path=None) -> dict:
    """Fold a Claude `rate_limits` payload into the snapshot, keeping the
    freshest reading per window. Returns the snapshot dict. Never raises.
    """
    try:
        if now is None:
            now = time.time()
        p = path or default_path()
        snap = _load(p)
        if not isinstance(snap, dict):
            snap = {}
        if not isinstance(rate_limits, dict):
            return snap
        changed = False
        for win, secs in WINDOWS.items():
            inc = _coerce(rate_limits.get(win))
            if inc is None:
                continue
            inc = dict(inc)  # copy
            inc["observed_at"] = now
            old = snap.get(win)
            if not isinstance(old, dict) or "resets_at" not in old:
                snap[win] = inc
                changed = True
            elif _is_new_window(old, inc, secs):
                snap[win] = inc
                changed = True
            elif _is_older_window(old, inc, secs):
                continue  # stale older reading
            elif inc["used_percentage"] >= old.get("used_percentage", -1):
                snap[win] = inc
                changed = True
        if changed:
            _save(p, snap)
        return snap
    except Exception:
        # never raise to caller
        return _load(path or default_path())


def _window_view(win, now=None, path=None):
    """{used_percentage, resets_at, secs_to_reset, observed_at, stale} | None"""
    try:
        if now is None:
            now = time.time()
        p = path or default_path()
        snap = _load(p)
        r = snap.get(win) if isinstance(snap, dict) else None
        if not isinstance(r, dict) or "resets_at" not in r:
            return None
        secs = WINDOWS[win]
        reset = float(r["resets_at"])
        used = r.get("used_percentage")
        stale = False
        while reset <= now:  # roll forward unseen resets
            reset += secs
            stale = True
        if stale:
            used = None
        return {
            "used_percentage": used,
            "resets_at": reset,
            "secs_to_reset": reset - now,
            "observed_at": r.get("observed_at"),
            "stale": stale,
        }
    except Exception:
        return None


def five_hour(now=None, path=None):
    return _window_view("five_hour", now, path)


def weekly(now=None, path=None):
    return _window_view("seven_day", now, path)
