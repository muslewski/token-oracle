"""Pure cap-race helpers for the Future tab (plan 062). No I/O.

Window truth matches Present blend (dashboard/app.py row blend):
  5h/session — local used/cap (web 5h lags; Present ignores it for the number).
  weekly/fable — live cell when pct is not None; else local used/cap or end-proj.
Live is authoritative for **now** when present; end-proj alone can lag the site.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.timeutil import fmt_dh_long

STATUS_RANK = {"OVER": 0, "TIGHT": 1, "SAFE": 2, "IDLE": 3, "UNKNOWN": 4}


@dataclass(frozen=True)
class Truth:
    now_pct: float | None
    source: str  # live | local | proj | none
    end_pct: float | None
    reset_in: float
    idle: bool
    window: str
    cap: int
    profile: str


def profile_canon(name: str) -> str:
    return "grok" if "grok" in (name or "").lower() else "claude"


def _window_kind(window: str) -> str:
    ww = (window or "").lower()
    if "5h" in ww or "session" in ww or "current" in ww:
        return "5h"
    if ww in ("weekly", "week"):
        return "weekly"
    if ww == "fable":
        return "fable"
    return "other"


def window_truth(f, cells=None) -> Truth:
    """Resolve now_pct / source for one Forecast using the Present blend keys."""
    cells = cells or {}
    pname = getattr(f, "profile", "default") or "default"
    p_canon = profile_canon(pname)
    ww = getattr(f, "window", "?") or "?"
    kind = _window_kind(ww)
    idle = bool(getattr(f, "idle", False))
    end_pct = float(getattr(f, "projected_pct", 0.0) or 0.0)
    reset_in = float(getattr(f, "reset_in_secs", 0) or 0)
    cap = int(getattr(f, "cap", 0) or 0)
    used = int(getattr(f, "used", 0) or 0)

    now_pct: float | None = None
    source = "none"

    if kind == "5h":
        if cap > 0:
            now_pct = 100.0 * used / cap
            source = "local"
        elif not idle:
            now_pct = end_pct
            source = "proj"
    elif kind in ("weekly", "fable"):
        cell = cells.get((p_canon, kind))
        if cell is not None and getattr(cell, "pct", None) is not None:
            now_pct = float(cell.pct)
            source = "live"
        elif cap > 0 and not idle:
            now_pct = 100.0 * used / cap
            source = "local"
        elif not idle:
            now_pct = end_pct
            source = "proj"
    else:
        if cap > 0 and not idle:
            now_pct = 100.0 * used / cap
            source = "local"
        elif not idle:
            now_pct = end_pct
            source = "proj"

    return Truth(
        now_pct=now_pct,
        source=source,
        end_pct=end_pct,
        reset_in=reset_in,
        idle=idle,
        window=ww,
        cap=cap,
        profile=pname,
    )


def eta_for_race(f, truth: Truth) -> float | None:
    """Live-aware seconds-to-cap for the race clock."""
    now_pct = truth.now_pct
    if now_pct is not None and now_pct >= 100.0:
        return 0.0
    engine_eta = getattr(f, "eta_to_cap_secs", None)
    if truth.source == "live" and now_pct is not None and truth.cap > 0:
        live_used = (now_pct / 100.0) * truth.cap
        end_pct = truth.end_pct if truth.end_pct is not None else now_pct
        reset_in = truth.reset_in
        if end_pct > now_pct and reset_in > 0:
            remaining_tokens = (end_pct / 100.0) * truth.cap - live_used
            rate = remaining_tokens / reset_in
            if rate > 0:
                return (truth.cap - live_used) / rate
            return None
        return float(engine_eta) if engine_eta is not None else None
    return float(engine_eta) if engine_eta is not None else None


def race_status(truth: Truth, eta: float | None) -> str:
    """First match: IDLE → OVER → TIGHT → SAFE → UNKNOWN.

    Idle logs with a live fill still race on live (not short-circuited to IDLE).
    """
    if truth.idle and truth.source != "live":
        return "IDLE"
    now = truth.now_pct
    end = truth.end_pct
    if now is None and end is None:
        return "UNKNOWN"
    if (now is not None and now >= 100.0) or (
        eta is not None and eta < truth.reset_in
    ):
        return "OVER"
    if (now is not None and now >= 85.0) or (end is not None and end >= 85.0):
        return "TIGHT"
    if now is not None or end is not None:
        return "SAFE"
    return "UNKNOWN"


def profile_verdict(statuses) -> str:
    best = "UNKNOWN"
    best_rank = STATUS_RANK["UNKNOWN"]
    for s in statuses or []:
        r = STATUS_RANK.get(s, STATUS_RANK["UNKNOWN"])
        if r < best_rank:
            best, best_rank = s, r
    return best


def margin_line(truth: Truth, eta: float | None) -> str:
    now = truth.now_pct
    if now is not None and now >= 100.0:
        return "already at the wall"
    reset_in = truth.reset_in
    if eta is not None:
        if eta < reset_in:
            return f"lose by {fmt_dh_long(reset_in - eta)}"
        if eta > reset_in:
            return f"clear by {fmt_dh_long(eta - reset_in)}"
    end = truth.end_pct if truth.end_pct is not None else 0.0
    n = now if now is not None else end
    headroom = max(0.0, 100.0 - max(float(n or 0.0), float(end or 0.0)))
    return f"headroom ~{round(headroom)}% of cap"


def status_gauge_pct(status: str) -> float:
    """Map status word onto existing gauge thresholds for color."""
    if status == "OVER":
        return 100.0
    if status == "TIGHT":
        return 90.0
    if status == "SAFE":
        return 50.0
    return 0.0
