"""Apply authoritative live/server fill into Forecasts (engine write-through).

Display still uses the LiveCell overlay for provenance. This module improves the
*prediction*: used, projected_pct (end-of-window) and eta_to_cap_secs, re-anchored
on a TRUSTED present reading — fresh, high-confidence, non-retained (plan 063 I3;
retained/stale readings stay display-only). The current % is never written into
projected_pct as an alias (plan 030).

fill owns weekly / fable / grok windows. The Claude 5h window is owned by the
engine's inline server path (config.try_get_claude_five_hour_data, the richer
own-header→server→local chain) so there is no double-rebase (plan 063 T4).

Never probes browsers. Only reads live.json + ratelimits snapshots. Never raises;
returns a `degraded` flag when it swallows an error so the no-op is not silent.
"""

from __future__ import annotations

from dataclasses import replace

from ..core.capcal import calibrate
from ..core.windows import recompute_with_used
from .contract import (
    METRIC_FIVE_HOUR_PCT,
    METRIC_MODEL_WEEKLY_PCT,
    METRIC_WEEKLY_PCT,
    STATE_OK,
)
from .overlay import FRESH_TTL_SECS
from .store import load_snapshot
from .trust import is_trusted_for_math, newest_first

# A trusted present reading of at least this % marks a log-idle window active (I5).
ACTIVE_FLOOR = 1.0


def _canon(profile: str) -> str:
    p = (profile or "").lower()
    return "grok" if "grok" in p else "claude"


def _wkey(window: str) -> str | None:
    w = (window or "").lower()
    if w in ("weekly", "week"):
        return "weekly"
    if w == "fable":
        return "fable"
    if w in ("5h", "5-hour", "session", "current"):
        return "5h"
    return None


def _pct_from_snapshot(snapshot: dict | None, profile: str, wkey: str, now: float) -> float | None:
    """Newest TRUSTED (fresh, high-conf, non-retained) usage % for (profile, wkey).

    Returns the value of the most recently fetched trusted reading, or None.
    Retained / stale / low-confidence readings are display-only (I3) and skipped.
    """
    if not isinstance(snapshot, dict):
        return None
    provs = snapshot.get("providers") or {}
    p_c = _canon(profile)

    trusted: list[dict] = []
    for raw, pdata in provs.items():
        if not isinstance(pdata, dict):
            continue
        if _canon(str(raw)) != p_c:
            continue
        pfetched = pdata.get("fetched_at")
        for r in pdata.get("readings") or []:
            if not isinstance(r, dict):
                continue
            val = r.get("value")
            if not isinstance(val, (int, float)):
                continue
            metric = r.get("metric")
            match = False
            if wkey == "weekly" and metric == METRIC_WEEKLY_PCT:
                match = True
            elif (
                wkey == "fable" and metric == METRIC_MODEL_WEEKLY_PCT and r.get("model") == "fable"
            ):
                match = True
            elif wkey == "5h" and metric == METRIC_FIVE_HOUR_PCT:
                match = True
            if not match:
                continue
            ex = str(r.get("extractor") or "")
            rfetched = r.get("fetched_at", pfetched)
            age = None if rfetched is None else max(0.0, now - float(rfetched))
            if not is_trusted_for_math(
                state=STATE_OK, confidence=r.get("confidence"), age_secs=age, extractor=ex
            ):
                continue
            trusted.append({"value": float(val), "fetched_at": rfetched})

    if not trusted:
        return None
    return float(newest_first(trusted)[0]["value"])


def _header_weekly_pct(now: float) -> float | None:
    """Claude weekly % from the self-ingested rate-limit header (fresh only)."""
    try:
        from ..core import ratelimits as RL

        hdr = RL.weekly(now)
    except Exception:
        return None
    if not isinstance(hdr, dict) or hdr.get("stale"):
        return None
    up = hdr.get("used_percentage")
    if not isinstance(up, (int, float)):
        return None
    obs = hdr.get("observed_at")
    age = None if obs is None else max(0.0, now - float(obs))
    # I3: only a FRESH header (< FRESH_TTL) may re-anchor the forecast MATH. An
    # older-but-not-reset header stays display-only (overlay shows it with age).
    if age is None or age > FRESH_TTL_SECS:
        return None
    return float(up)


def fill_pct_for_window(
    profile: str, window: str, snapshot: dict | None, now: float
) -> float | None:
    """Authoritative current fill % for one window, or None if unavailable.

    Priority:
      weekly (claude): header rate_limits wins over web (same as overlay)
      weekly (grok) / fable: web cell
      5h: None here — the engine's inline server path owns Claude 5h (no double-rebase).
    """
    wkey = _wkey(window)
    if wkey is None or wkey == "5h":
        return None
    p_c = _canon(profile)

    if wkey == "weekly" and p_c == "claude":
        hdr = _header_weekly_pct(now)
        if hdr is not None:
            return hdr
        return _pct_from_snapshot(snapshot, profile, "weekly", now)

    if wkey in ("weekly", "fable"):
        return _pct_from_snapshot(snapshot, profile, wkey, now)

    return None


def apply_live_fills(forecasts, now: float, snapshot: dict | None = None):
    """Return (forecasts, degraded).

    Re-anchor each non-5h Forecast on a trusted present reading: adopt a grown
    effective cap (capcal, grow-only), rebase used, and recompute a bounded
    end-projection + observed-rate ETA. A trusted reading of real usage revives a
    log-idle window (I5). ``degraded`` is True iff an error was swallowed so the
    dash can flag that live truth is not being applied. Never raises; never blanks.
    """
    try:
        fs = list(forecasts or [])
        if not fs:
            return fs, False
        if snapshot is None:
            snapshot = load_snapshot()
        out = []
        for f in fs:
            try:
                cap = int(getattr(f, "cap", 0) or 0)
                window = getattr(f, "window", "") or ""
                profile = getattr(f, "profile", "default") or "default"
                if cap <= 0 or _wkey(window) == "5h":
                    out.append(f)
                    continue
                pct = fill_pct_for_window(profile, window, snapshot, now)
                if pct is None:
                    out.append(f)
                    continue
                # Self-calibrate the effective cap from the corroborated ratio
                # (grow-only). Adopt it so % and statusline k/cap track the real
                # (possibly moved) tier instead of a stale preset.
                cap_eff, _note = calibrate(
                    profile, window, int(getattr(f, "used", 0) or 0), pct, cap, now
                )
                cap_eff = int(cap_eff or cap)
                if cap_eff != cap:
                    f = replace(f, cap=cap_eff)
                used = int(round(float(pct) / 100.0 * cap_eff))
                out.append(recompute_with_used(f, used, active=(pct >= ACTIVE_FLOOR)))
            except Exception:
                out.append(f)
        return out, False
    except Exception:
        return list(forecasts or []), True
