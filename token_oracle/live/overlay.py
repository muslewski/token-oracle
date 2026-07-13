"""Overlay live cells onto forecasts for display.

LiveCell carries a high-confidence fresh live pct (or None) + provenance.
overlay_cells never fabricates a number; it withholds unless CONF_HIGH + fresh.
"""

from dataclasses import dataclass

from ..core import ratelimits as _ratelimits
from .contract import (
    CONF_HIGH,
    METRIC_FIVE_HOUR_PCT,
    METRIC_FIVE_HOUR_STATE,
    METRIC_MODEL_WEEKLY_PCT,
    METRIC_RATE_WINDOW,
    METRIC_WEEKLY_PCT,
    STATE_OK,
    STATE_STALE,
    STATE_UNAVAILABLE,
)

_AUTO = object()  # sentinel: default => auto-read the header snapshot


def _read_claude_weekly_header(now):
    """Return core.ratelimits.weekly(now) or None. Never raises."""
    try:
        return _ratelimits.weekly(now)
    except Exception:
        return None


# Freshness window for applying a web reading. MUST exceed the dashboard's
# LIVE_PROBE_INTERVAL plus one probe's duration, or cap cells go "stale" for the
# tail of every probe cycle (worst-case reading age ≈ interval + probe time).
# Web readings are all slow-moving caps now (the fast 5h number comes from local
# logs), so a longer window is still truthful. See app.LIVE_PROBE_INTERVAL.
FRESH_TTL_SECS = 600.0


@dataclass(frozen=True)
class LiveCell:
    """Resolved live overlay for one (profile, window) slot.

    pct is set ONLY for high-confidence fresh readings.
    state reflects provider state or STATE_STALE.
    state_value carries e.g. "starts_on_first_message" for special 5h handling.
    """

    pct: float | None  # applied live percentage, or None
    state: str  # provider STATE_* (STATE_STALE if outdated)
    age_secs: float | None
    evidence: str = ""
    extractor: str = ""
    state_value: str | None = None


def _canon(p: str) -> str:
    p = (p or "").lower()
    if "grok" in p:
        return "grok"
    return "claude"


def _wkey(name: str) -> str | None:
    w = (name or "").lower()
    if w in ("weekly", "week"):
        return "weekly"
    if w == "fable":
        return "fable"
    if w in ("5h", "5-hour", "session", "current"):
        return "5h"
    return None


def overlay_cells(
    forecasts, snapshot: dict | None, now: float, ttl: float = FRESH_TTL_SECS, weekly_header=_AUTO
) -> dict[tuple[str, str], LiveCell]:
    """Build mapping (profile_canon, wkey) -> LiveCell for the given forecasts.

    Only high-conf fresh usage readings produce a non-None pct.
    Rate readings are never mapped into cells.
    """
    cells: dict[tuple[str, str], LiveCell] = {}
    # Web readings need a dict snapshot; header weekly must still apply when the
    # live-web snapshot is missing (None) or empty ({}) — statusline-only users
    # never have a browser snapshot but still ingest rate_limits headers.
    snap = snapshot if isinstance(snapshot, dict) else {}
    provs = snap.get("providers") or {}
    for p_raw, pdata in provs.items():
        if not isinstance(pdata, dict):
            continue
        p_c = _canon(p_raw)
        pfetched = pdata.get("fetched_at")
        pstate = pdata.get("state") or STATE_UNAVAILABLE

        for r in pdata.get("readings") or []:
            if not isinstance(r, dict):
                continue
            metric = r.get("metric")
            conf = r.get("confidence")
            val = r.get("value")
            ev = str(r.get("evidence", ""))[:160]
            ex = str(r.get("extractor", ""))
            rfetched = r.get("fetched_at", pfetched)
            rage = None if rfetched is None else max(0.0, now - float(rfetched))
            rstale = rage is not None and rage > ttl

            cstate = STATE_STALE if rstale else pstate
            apply = (conf == CONF_HIGH) and (not rstale)
            pct = float(val) if (apply and isinstance(val, (int, float))) else None

            state_val = None
            if metric == METRIC_FIVE_HOUR_STATE:
                state_val = str(val) if val is not None else None

            cell = LiveCell(
                pct=pct,
                state=cstate,
                age_secs=rage,
                evidence=ev,
                extractor=ex,
                state_value=state_val,
            )

            if metric == METRIC_WEEKLY_PCT:
                cells[(p_c, "weekly")] = cell
            elif metric == METRIC_MODEL_WEEKLY_PCT and r.get("model") in ("fable", "grok_build"):
                # fable -> claude Fable row; grok_build -> grok sub-cell (snapshot only,
                # no dash row today). api breakdown stays info-only (never a cell).
                cells[(p_c, str(r.get("model")))] = cell
            elif metric == METRIC_FIVE_HOUR_PCT:
                cells[(p_c, "5h")] = cell
            elif metric == METRIC_FIVE_HOUR_STATE:
                # overwrite or merge for 5h cell (state_value + possibly pct)
                existing = cells.get((p_c, "5h"))
                if existing:
                    # prefer a pct if present from five_hour_pct reading
                    merged_pct = existing.pct if existing.pct is not None else pct
                    cells[(p_c, "5h")] = LiveCell(
                        pct=merged_pct,
                        state=existing.state if existing.state != STATE_STALE else cstate,
                        age_secs=existing.age_secs if existing.age_secs is not None else rage,
                        evidence=existing.evidence or ev,
                        extractor=existing.extractor or ex,
                        state_value=state_val,
                    )
                else:
                    cells[(p_c, "5h")] = cell
            # METRIC_RATE_WINDOW and RESET_AT intentionally never become a cell here

    # Header weekly override for claude (from self-ingested rate_limits via 053).
    # Wins over any web scrape cell when fresh + non-stale. No-op otherwise (additive).
    # Runs even when snap is empty so weekly live works without browser probing.
    hdr = _read_claude_weekly_header(now) if weekly_header is _AUTO else weekly_header
    if isinstance(hdr, dict):
        up = hdr.get("used_percentage")
        obs = hdr.get("observed_at")
        age = None if obs is None else max(0.0, now - float(obs))
        fresh = (age is None) or (age <= ttl)
        if up is not None and not hdr.get("stale", False) and fresh:
            cells[("claude", "weekly")] = LiveCell(
                pct=float(up),
                state=STATE_OK,
                age_secs=age,
                evidence="claude rate-limit header (seven_day)",
                extractor="header",
                state_value=None,
            )

    return cells


def rate_info(snapshot: dict | None) -> dict:
    """Expose rate-window info (queries) if present. Never used for usage % caps."""
    if not snapshot or not isinstance(snapshot, dict):
        return {}
    out = {}
    for pname, pdata in (snapshot.get("providers") or {}).items():
        for r in pdata.get("readings") or []:
            if r.get("metric") == METRIC_RATE_WINDOW:
                out[pname] = {
                    "used_pct": r.get("value"),
                    "fetched_at": pdata.get("fetched_at"),
                    "evidence": r.get("evidence", ""),
                }
    return out
