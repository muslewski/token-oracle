"""First source adapter: Claude Code transcripts (~/.claude/projects/*/*.jsonl).
Ported from usage_limits.iter_usage_events + scan_events."""

import glob
import json
import os

from ..core.timeutil import parse_ts
from .base import register


def _limit_tokens(usage):
    if not usage:
        return 0
    return (
        usage.get("input_tokens", 0)
        + usage.get("output_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
    )


def iter_usage_events(jsonl_path):
    """Yield (ts_epoch, tokens) for assistant messages carrying usage."""
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
            usage = (obj.get("message") or {}).get("usage")
            if not usage:
                continue
            ts = parse_ts(obj.get("timestamp"))
            if ts is None:
                continue
            tok = _limit_tokens(usage)
            if tok > 0:
                yield (ts, tok)


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
            if ent and ent.get("mtime") == st.st_mtime and ent.get("size") == st.st_size:
                continue
            evs = [[ts, tok] for ts, tok in iter_usage_events(p) if ts >= cutoff]
            files[p] = {"mtime": st.st_mtime, "size": st.st_size, "events": evs}
        for gone in [p for p in files if p not in seen]:
            files.pop(gone, None)
        out = []
        for ent in files.values():
            out.extend(
                (float(ts), int(tok)) for ts, tok in ent.get("events", []) if cutoff <= ts <= now
            )
        out.sort()
        return files, out
