"""Documented stub source for non-Claude providers. Feed it a JSON file of
neutral [[timestamp, tokens], ...] pairs. Copy this file to build your own
adapter; see ADAPTERS.md."""

import json
import os

from .base import register


@register("generic")
class GenericSource:
    def __init__(self, opts):
        self.events_path = os.path.expanduser(opts.get("events_path") or "")

    def scan(self, files_state, now, window):
        cutoff = now - window
        out = []
        try:
            with open(self.events_path, encoding="utf-8") as fh:
                data = json.load(fh)
            for ts, tok in data:
                ts = float(ts)
                if cutoff <= ts <= now:
                    out.append((ts, int(tok)))
        except (OSError, ValueError, TypeError):
            pass
        out.sort()
        return files_state, out
