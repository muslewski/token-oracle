"""Atomic persistence for live readings snapshot.

Snapshot format:
{
  "version": 1,
  "written_at": <epoch float>,
  "providers": {
    "grok": <ProviderLive-as-dict>,
    "claude": <ProviderLive-as-dict>
  }
}

Never raises on I/O; returns None on failure/missing/corrupt.
Follows the mkstemp + os.replace pattern from snapshot/writer.py exactly.
"""

import json
import os
import tempfile
import time

from .contract import ProviderLive, provider_live_to_dict


def default_live_path():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "token-oracle", "live.json")


def save_snapshot(providers: dict[str, ProviderLive], path=None) -> str | None:
    """Write atomic snapshot. Returns the path on success, None on any failure.

    Mirrors snapshot/writer.py: mkstemp in target dir, fdopen write, os.replace,
    best-effort unlink on error, outer OSError -> None.
    """
    path = os.path.expanduser(path or default_live_path())
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d or ".", suffix=".tmp")
        try:
            snap = {
                "version": 1,
                "written_at": time.time(),
                "providers": {
                    k: provider_live_to_dict(v)
                    for k, v in (providers or {}).items()
                    if v is not None
                },
            }
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
        return None
    return path


def load_snapshot(path=None) -> dict | None:
    """Return parsed snapshot dict or None on missing / corrupt / unreadable.

    Never raises.
    """
    path = os.path.expanduser(path or default_live_path())
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
        return None
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
