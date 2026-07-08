"""Documented stub source for non-Claude providers. Feed it a JSON file of
neutral [[timestamp, tokens], ...] pairs (rows may optionally carry more
fields — see core/events.py). Copy this file to build your own adapter; see
ADAPTERS.md."""

import json
import os

from ..core import events as events_mod
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
            for row in data:
                if cutoff <= float(row[0]) <= now:
                    out.append(events_mod.normalize(row))
        except (OSError, ValueError, TypeError):
            pass
        out.sort(key=lambda e: e[0])
        return files_state, out
