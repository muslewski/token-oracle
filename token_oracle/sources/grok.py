"""Grok Build source adapter (first-class support).

Parses ~/.grok/sessions/<encoded-cwd>/<session-id>/updates.jsonl for
"_meta": {"totalTokens": N, ...} entries (cumulative within session).
ALSO reads sibling signals.json for freshest "contextTokensUsed" + its mtime
for more real-time values (signals is the live session state snapshot).

Deltas between increasing cum reports are emitted. Signals can inject a
fresher latest cum (using file mtime as ts) for live feel.

Detects resets by seeing significant used drops in later processing.
"""

import glob
import json
import os

from ..core import events as events_mod
from .base import register


def iter_total_tokens_reports(jsonl_path):
    """Yield (ts_epoch, total_tokens) for entries carrying params._meta.totalTokens.
    Timestamps are already epoch seconds (int/float)."""
    try:
        with open(jsonl_path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                meta = (obj.get("params") or {}).get("_meta") or {}
                tot = meta.get("totalTokens")
                ts = obj.get("timestamp")
                if ts is not None and isinstance(tot, (int, float)) and tot >= 0:
                    yield (float(ts), int(tot))
    except OSError:
        return


def load_signals_context(signals_path):
    """Return (ts, total_tokens) using mtime of signals.json + contextTokensUsed.
    Returns None if unreadable. Provides fresher live value."""
    try:
        st = os.stat(signals_path)
        with open(signals_path, encoding="utf-8") as fh:
            obj = json.load(fh)
        tot = obj.get("contextTokensUsed")
        if isinstance(tot, (int, float)) and tot >= 0:
            return (float(st.st_mtime), int(tot))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return None


@register("grok")
class GrokSource:
    def __init__(self, opts):
        self.sessions_dir = os.path.expanduser(
            opts.get("sessions_dir") or "~/.grok/sessions"
        )

    def scan(self, files_state, now, window):
        cutoff = now - window
        files = dict(files_state)
        # collect updates.jsonl
        try:
            upd_paths = glob.glob(os.path.join(self.sessions_dir, "*", "*", "updates.jsonl"))
        except OSError:
            upd_paths = []
        # also signals for live
        try:
            sig_paths = glob.glob(os.path.join(self.sessions_dir, "*", "*", "signals.json"))
        except OSError:
            sig_paths = []

        seen = set()
        for p in upd_paths:
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
            # reparse: reports are (ts, cumulative_total)
            reports = [r for r in iter_total_tokens_reports(p) if r[0] >= cutoff]
            reports.sort(key=lambda r: r[0])
            evs = []
            last = 0
            for ts, cum in reports:
                if cum > last:
                    delta = cum - last
                    evs.append((ts, delta, "grok-build", delta, 0, 0, 0, None))
                    last = cum
            files[p] = {"mtime": st.st_mtime, "size": st.st_size, "events": evs, "last_total": last}

        # augment with live signals.json (use mtime + contextTokensUsed for freshest cum)
        # map session dir -> max_cum from its updates (for correct delta)
        session_max = {}
        for p, ent in list(files.items()):
            if "updates.jsonl" in p:
                sessdir = os.path.dirname(p)
                last = ent.get("last_total", 0)
                session_max[sessdir] = max(session_max.get(sessdir, 0), last)
                # also collect any prior events for that session
        for sp in sig_paths:
            seen.add(sp)
            try:
                st = os.stat(sp)
            except OSError:
                continue
            if st.st_mtime < cutoff:
                continue
            sig = load_signals_context(sp)
            if not sig:
                continue
            ts, cum = sig
            if ts < cutoff:
                continue
            sessdir = os.path.dirname(sp)
            base = session_max.get(sessdir, 0)
            # IMPORTANT: do NOT emit contextTokensUsed as quota burn deltas.
            # contextTokensUsed reflects *current conversation context window fill*
            # (e.g. 120k/512k), NOT cumulative quota consumption toward weekly SuperGrok/Grok-build limits.
            # Emitting it caused massive overcount (summing full context of every recent session).
            # Only updates.jsonl _meta.totalTokens deltas (or small live increments) are used for burn.
            # Signals still update last_total for potential live corrections and mtime freshness.
            evs = []
            # Only inject a *tiny* live top-up if we have prior base and the diff is plausible small increment
            # (defensive; avoids re-adding full context sizes as "used").
            if cum > base:
                delta = cum - base
                # Heuristic: only accept as burn increment if reasonably small (<= ~50k per live tick; real turns are smaller)
                if 0 < delta <= 50000:
                    evs.append((ts, delta, "grok-build", delta, 0, 0, 0, None))
            # Always store for last_total / future base
            files[sp] = {"mtime": st.st_mtime, "size": st.st_size, "events": evs, "last_total": cum, "from_signals": True}
            session_max[sessdir] = max(session_max.get(sessdir, 0), cum)

        for gone in [p for p in files if p not in seen and not p.endswith("signals.json")]:
            # keep signals entries? prune only non-seen updates
            if not any(gone.endswith(x) for x in ("signals.json",)):
                files.pop(gone, None)

        out = []
        for ent in files.values():
            out.extend(
                events_mod.normalize(e) for e in ent.get("events", []) if cutoff <= e[0] <= now
            )
        out.sort(key=lambda e: e[0])
        return files, out
