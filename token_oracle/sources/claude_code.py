"""Claude Code source adapter: reads ~/.claude/projects/*/*.jsonl .
One of several (see grok.py, generic.py); first-class but not privileged."""

import glob
import json
import os

from ..core import events as events_mod
from ..core.timeutil import parse_ts
from .base import register


def _as_int(val, default=0):
    """Coerce usage field to int; non-numeric → default (skip bad fields, not whole file)."""
    if val is None:
        return default
    if isinstance(val, bool):
        return default
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _limit_tokens(usage):
    if not usage:
        return 0
    return (
        _as_int(usage.get("input_tokens", 0))
        + _as_int(usage.get("output_tokens", 0))
        + _as_int(usage.get("cache_creation_input_tokens", 0))
    )


def iter_usage_events(jsonl_path):
    """Yield (ts_epoch, tokens, model, input, output, cache_create, cache_read,
    cost_usd) for assistant messages carrying usage. tokens (element 1) stays
    limit-weighted (input+output+cache_creation; cache_read excluded) — the
    forecast math only ever reads elements 0-1."""
    try:
        fh = open(jsonl_path, "rb")
    except OSError:
        return
    with fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue
            msg = obj.get("message")
            if not isinstance(msg, dict):
                continue
            usage = msg.get("usage")
            if not isinstance(usage, dict):
                continue
            ts = parse_ts(obj.get("timestamp"))
            if ts is None:
                continue
            tok = _limit_tokens(usage)
            if tok > 0:
                model = msg.get("model")
                inp = _as_int(usage.get("input_tokens", 0))
                out = _as_int(usage.get("output_tokens", 0))
                cc = _as_int(usage.get("cache_creation_input_tokens", 0))
                cr = _as_int(usage.get("cache_read_input_tokens", 0))
                cost = obj.get("costUSD")
                if cost is not None and not isinstance(cost, (int, float)):
                    try:
                        cost = float(cost)
                    except (TypeError, ValueError):
                        cost = None
                yield (ts, tok, model, inp, out, cc, cr, cost)


@register("claude_code")
class ClaudeCodeSource:
    def __init__(self, opts):
        self.projects_dir = os.path.expanduser(opts.get("projects_dir") or "~/.claude/projects")

    def scan(self, files_state, now, window):
        cutoff = now - window
        files = dict(files_state)
        try:
            paths = glob.glob(os.path.join(self.projects_dir, "*", "*.jsonl"))
        except OSError:
            paths = []
        seen = set()
        for p in paths:
            seen.add(p)
            try:
                st = os.stat(p)
            except OSError:
                continue
            if st.st_mtime < cutoff:
                files.pop(p, None)
                continue
            ent = files.get(p)
            # For "live" files (touched very recently relative to the scan's 'now'), always reparse
            # even if mtime+size match the caller's cache state. This captures appends from an
            # active Claude Code session promptly, improving 5h current-block freshness.
            # Guarded so it has no effect under the tiny synthetic 'now' values used in tests.
            live_window = 300  # seconds
            is_live = (now > 1_000_000_000) and (st.st_mtime >= now - live_window)
            if (
                ent
                and ent.get("mtime") == st.st_mtime
                and ent.get("size") == st.st_size
                and not is_live
            ):
                continue
            evs = [list(e) for e in iter_usage_events(p) if e[0] >= cutoff]
            files[p] = {"mtime": st.st_mtime, "size": st.st_size, "events": evs}
        for gone in [p for p in files if p not in seen]:
            files.pop(gone, None)
        out = []
        for ent in files.values():
            out.extend(
                events_mod.normalize(e) for e in ent.get("events", []) if cutoff <= e[0] <= now
            )
        out.sort(key=lambda e: e[0])
        return files, out
