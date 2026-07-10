"""Overlay live cells onto forecasts for display.

LiveCell carries a high-confidence fresh live pct (or None) + provenance.
overlay_cells never fabricates a number; it withholds unless CONF_HIGH + fresh.
"""

from dataclasses import dataclass

from .contract import (
    CONF_HIGH,
    METRIC_FIVE_HOUR_PCT,
    METRIC_FIVE_HOUR_STATE,
    METRIC_MODEL_WEEKLY_PCT,
    METRIC_RATE_WINDOW,
    METRIC_WEEKLY_PCT,
    STATE_STALE,
    STATE_UNAVAILABLE,
)

FRESH_TTL_SECS = 180.0


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
    forecasts, snapshot: dict | None, now: float, ttl: float = FRESH_TTL_SECS
) -> dict[tuple[str, str], LiveCell]:
    """Build mapping (profile_canon, wkey) -> LiveCell for the given forecasts.

    Only high-conf fresh usage readings produce a non-None pct.
    Rate readings are never mapped into cells.
    """
    cells: dict[tuple[str, str], LiveCell] = {}
    if not snapshot or not isinstance(snapshot, dict):
        return cells

    provs = snapshot.get("providers") or {}
    for p_raw, pdata in provs.items():
        p_c = _canon(p_raw)
        pfetched = pdata.get("fetched_at")
        pstate = pdata.get("state") or STATE_UNAVAILABLE

        for r in pdata.get("readings") or []:
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
            elif metric == METRIC_MODEL_WEEKLY_PCT and r.get("model") == "fable":
                cells[(p_c, "fable")] = cell
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
