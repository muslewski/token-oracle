"""Apply authoritative live/server fill into Forecasts (engine write-through).

Display still uses LiveCell overlay for provenance. This module improves the
*prediction*: used, projected_pct (end-of-window), and eta_to_cap_secs, using
high-confidence live/header fill without putting current % into projected_pct
as a current-fill alias (plan 030).

Never probes browsers. Only reads live.json + ratelimits snapshots. Never raises.
"""

from __future__ import annotations

from ..core.windows import recompute_with_used
from .contract import (
    CONF_HIGH,
    METRIC_FIVE_HOUR_PCT,
    METRIC_MODEL_WEEKLY_PCT,
    METRIC_WEEKLY_PCT,
)
from .overlay import FRESH_TTL_SECS, HEADER_FRESH_TTL_SECS, RETAIN_FRESH_TTL_SECS
from .store import load_snapshot


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


def _fresh(age: float | None, ttl: float) -> bool:
    if age is None:
        return True
    return age <= ttl


def _pct_from_snapshot(snapshot: dict | None, profile: str, wkey: str, now: float) -> float | None:
    """High-conf fresh usage % from live.json for (profile, wkey), or None."""
    if not isinstance(snapshot, dict):
        return None
    provs = snapshot.get("providers") or {}
    p_c = _canon(profile)
    # prefer exact provider key match, then any canon-matching key
    candidates = []
    for raw, pdata in provs.items():
        if not isinstance(pdata, dict):
            continue
        if _canon(str(raw)) == p_c:
            candidates.append(pdata)
    if not candidates:
        return None

    best = None
    for pdata in candidates:
        pfetched = pdata.get("fetched_at")
        for r in pdata.get("readings") or []:
            if not isinstance(r, dict):
                continue
            conf = r.get("confidence")
            if conf != CONF_HIGH:
                continue
            metric = r.get("metric")
            val = r.get("value")
            if not isinstance(val, (int, float)):
                continue
            match = False
            if wkey == "weekly" and metric == METRIC_WEEKLY_PCT:
                match = True
            elif wkey == "fable" and metric == METRIC_MODEL_WEEKLY_PCT and r.get("model") == "fable":
                match = True
            elif wkey == "5h" and metric == METRIC_FIVE_HOUR_PCT:
                match = True
            elif (
                wkey == "weekly"
                and metric == METRIC_MODEL_WEEKLY_PCT
                and r.get("model") == "grok_build"
                and p_c == "grok"
            ):
                # optional: grok build sub-cap not used as weekly override
                match = False
            if not match:
                continue
            ex = str(r.get("extractor") or "")
            rfetched = r.get("fetched_at", pfetched)
            age = None if rfetched is None else max(0.0, now - float(rfetched))
            ttl = RETAIN_FRESH_TTL_SECS if ex.endswith("+retained") else FRESH_TTL_SECS
            if not _fresh(age, ttl):
                continue
            best = float(val)
    return best


def _header_weekly_pct(now: float) -> float | None:
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
    if not _fresh(age, HEADER_FRESH_TTL_SECS):
        return None
    return float(up)


def _header_five_hour_pct(now: float) -> float | None:
    try:
        from ..core import ratelimits as RL

        fh = RL.five_hour(now)
    except Exception:
        return None
    if not isinstance(fh, dict) or fh.get("stale"):
        return None
    up = fh.get("used_percentage")
    if not isinstance(up, (int, float)):
        return None
    obs = fh.get("observed_at")
    age = None if obs is None else max(0.0, now - float(obs))
    # 5h moves faster — use shorter web TTL, not multi-hour header weekly TTL
    if not _fresh(age, FRESH_TTL_SECS):
        return None
    return float(up)


def fill_pct_for_window(profile: str, window: str, snapshot: dict | None, now: float) -> float | None:
    """Authoritative current fill % for one window, or None if unavailable.

    Priority:
      weekly (claude): header rate_limits wins over web (same as overlay)
      weekly (grok) / fable: web cell
      5h (claude): header five_hour only (web 5h lags; logs remain default)
    """
    wkey = _wkey(window)
    if wkey is None:
        return None
    p_c = _canon(profile)

    if wkey == "weekly" and p_c == "claude":
        hdr = _header_weekly_pct(now)
        if hdr is not None:
            return hdr
        return _pct_from_snapshot(snapshot, profile, "weekly", now)

    if wkey == "5h" and p_c == "claude":
        return _header_five_hour_pct(now)

    if wkey in ("weekly", "fable"):
        return _pct_from_snapshot(snapshot, profile, wkey, now)

    return None


def apply_live_fills(forecasts, now: float, snapshot: dict | None = None):
    """Return a new list of Forecasts with live/server fill applied.

    When snapshot is None, loads live.json (best-effort). No-op per window when
    no usable fill. Never raises.
    """
    try:
        fs = list(forecasts or [])
        if not fs:
            return fs
        if snapshot is None:
            snapshot = load_snapshot()
        out = []
        for f in fs:
            try:
                if getattr(f, "idle", False):
                    out.append(f)
                    continue
                cap = int(getattr(f, "cap", 0) or 0)
                if cap <= 0:
                    out.append(f)
                    continue
                pct = fill_pct_for_window(
                    getattr(f, "profile", "default") or "default",
                    getattr(f, "window", "") or "",
                    snapshot,
                    now,
                )
                if pct is None:
                    out.append(f)
                    continue
                live_used = int(round(float(pct) / 100.0 * cap))
                out.append(recompute_with_used(f, live_used))
            except Exception:
                out.append(f)
        return out
    except Exception:
        return list(forecasts or [])
