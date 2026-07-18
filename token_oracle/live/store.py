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

Also hosts merge_with_previous(): partial probes must not wipe unprobed
providers, and empty bot-challenge results should retain last-good readings
for a bounded window so the dash does not blank weekly/fable on every CF fail.
"""

import json
import os
import re
import tempfile
import time

from .contract import (
    CONF_HIGH,
    METRIC_FIVE_HOUR_PCT,
    METRIC_MODEL_WEEKLY_PCT,
    METRIC_WEEKLY_PCT,
    STATE_STALE,
    ProviderLive,
    provider_live_from_dict,
    provider_live_to_dict,
)

# How long last-good usage readings may be kept when a probe fails empty
# (Cloudflare challenge, auth_no_data, transient error). Weekly caps move slowly.
RETAIN_MAX_AGE_SECS = 6 * 3600.0

# After this many consecutive retained (probe-failing) cycles a provider is
# escalated from a silent last-good hold to a visible 'stale — probe failing'
# state, so the dash/doctor stop showing hours-old numbers as if live (plan 063 I4).
RETAIN_MAX_CYCLES = 6

_RETAIN_CYCLE_RE = re.compile(r"retain#(\d+)")


def _retain_count(pl: ProviderLive) -> int:
    """Consecutive retained-cycle count previously stamped into the note (0 if none)."""
    m = _RETAIN_CYCLE_RE.search(getattr(pl, "note", "") or "")
    return int(m.group(1)) if m else 0


_USAGE_METRICS = frozenset({METRIC_WEEKLY_PCT, METRIC_MODEL_WEEKLY_PCT, METRIC_FIVE_HOUR_PCT})


def default_live_path():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "token-oracle", "live.json")


def _has_usable_usage(pl: ProviderLive) -> bool:
    """True if provider carries at least one high-conf numeric usage reading."""
    for r in pl.readings or []:
        if getattr(r, "confidence", None) != CONF_HIGH:
            continue
        if getattr(r, "metric", None) not in _USAGE_METRICS:
            continue
        if isinstance(getattr(r, "value", None), (int, float)):
            return True
    return False


def _reading_age(pl: ProviderLive, now: float) -> float | None:
    """Age of the newest usable usage reading (seconds), or provider fetched_at."""
    newest = None
    for r in pl.readings or []:
        if getattr(r, "confidence", None) != CONF_HIGH:
            continue
        if getattr(r, "metric", None) not in _USAGE_METRICS:
            continue
        if not isinstance(getattr(r, "value", None), (int, float)):
            continue
        fa = getattr(r, "fetched_at", None)
        if fa is not None:
            newest = float(fa) if newest is None else max(newest, float(fa))
    if newest is None and pl.fetched_at is not None:
        newest = float(pl.fetched_at)
    if newest is None:
        return None
    return max(0.0, now - newest)


def _tag_retained(pl: ProviderLive, fail_note: str, cycle: int = 1) -> ProviderLive:
    """Copy last-good provider; mark extractors + note so UI can show provenance.

    cycle counts consecutive retained probes. Once it exceeds RETAIN_MAX_CYCLES
    the provider is escalated to STATE_STALE (visible 'probe failing') instead of
    silently keeping its state so hours-old numbers stop reading as live.
    """
    from .contract import LiveReading

    tagged = []
    for r in pl.readings or []:
        ex = r.extractor or ""
        if not ex.endswith("+retained"):
            ex = f"{ex}+retained" if ex else "retained"
        tagged.append(
            LiveReading(
                provider=r.provider,
                metric=r.metric,
                value=r.value,
                confidence=r.confidence,
                extractor=ex,
                evidence=r.evidence,
                fetched_at=r.fetched_at,
                model=r.model,
            )
        )
    # Drop any prior retain# marker so the counter does not accumulate stale bits.
    note = _RETAIN_CYCLE_RE.sub("", pl.note or "").replace("  ", " ").strip(" ;").strip()
    fail = (fail_note or "").strip()
    retain_bit = "retained last-good"
    if fail:
        retain_bit = f"{retain_bit} · probe: {fail[:120]}"
    if retain_bit not in note:
        note = f"{note}; {retain_bit}".strip("; ").strip() if note else retain_bit
    note = f"{note}; retain#{cycle}".strip("; ").strip()
    escalated = cycle > RETAIN_MAX_CYCLES
    if escalated and "probe failing" not in note:
        note = f"{note}; probe failing".strip("; ").strip()
    return ProviderLive(
        provider=pl.provider,
        # keep prior state (ok) so cells still apply — until the retain streak
        # exceeds the cap, then surface it as stale.
        state=STATE_STALE if escalated else pl.state,
        readings=tagged,
        fetched_at=pl.fetched_at,
        error=None,
        note=note[:300],
    )


def merge_with_previous(
    new_providers: dict[str, ProviderLive],
    previous_snap: dict | None,
    now: float | None = None,
    retain_max_age: float = RETAIN_MAX_AGE_SECS,
    probed: set[str] | None = None,
) -> dict[str, ProviderLive]:
    """Merge a probe result with the prior live.json.

    - Providers not in this probe run are kept from previous (partial probe).
    - Probed providers with no usable readings keep previous last-good when
      previous readings are younger than retain_max_age (bot challenge / empty).
    - Successful usable probes always win.
    """
    now = time.time() if now is None else float(now)
    out: dict[str, ProviderLive] = dict(new_providers or {})
    prev_raw = (previous_snap or {}).get("providers") or {}
    if not isinstance(prev_raw, dict):
        prev_raw = {}

    prev: dict[str, ProviderLive] = {}
    for name, pdata in prev_raw.items():
        if not isinstance(pdata, dict):
            continue
        try:
            prev[str(name).lower()] = provider_live_from_dict(pdata)
        except Exception:
            continue

    probed_set = {p.lower() for p in probed} if probed is not None else set(out.keys())

    # Keep unprobed providers from previous
    for name, pl in prev.items():
        if name not in probed_set and name not in out:
            out[name] = pl

    # Last-good retention for empty/failed probes
    for name in list(probed_set):
        cur = out.get(name)
        old = prev.get(name)
        if cur is None:
            if old is not None:
                out[name] = old
            continue
        if _has_usable_usage(cur):
            continue  # fresh success
        if old is None or not _has_usable_usage(old):
            continue
        age = _reading_age(old, now)
        if age is None or age > retain_max_age:
            continue
        fail_note = (cur.note or cur.error or cur.state or "").strip()
        cycle = _retain_count(old) + 1
        out[name] = _tag_retained(old, fail_note, cycle)

    return out


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
