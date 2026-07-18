"""Future-tab renderer: live-aware cap race (plan 062) + 24h sparkline.
Pure; no I/O. Data comes from Forecast + optional live cells + profile integral."""

from __future__ import annotations

from ..cli import colors as c
from ..core.profile import profile_integral
from ..core.timeutil import fmt_dh_long, fmt_hms, fmt_reset, fmt_tokens
from .race import (
    eta_for_race,
    margin_line,
    profile_verdict,
    race_status,
    status_gauge_pct,
    window_truth,
)

_SPARK = " ▁▂▃▄▅▆▇█"  # 9 levels (index 0 = empty/zero)


def spark_next24(profile, now: float) -> tuple[str, float]:
    """Next-24h expected-burn sparkline + total expected tokens.

    For each of the next 24 hours compute profile_integral over that hour,
    scale to the 8-level block ramp. Returns ``("", 0.0)`` when profile is
    empty/falsy so the caller can show a dim placeholder.
    """
    if not profile:
        return "", 0.0
    hours: list[float] = []
    for i in range(24):
        t0 = now + i * 3600.0
        hours.append(float(profile_integral(profile, t0, t0 + 3600.0)))
    total = sum(hours)
    mean = total / len(hours) if hours else 0.0
    if mean <= 0:
        return " " * 24, 0.0
    # Normalize to 2× the mean, not the peak: a flat profile then renders as a
    # steady mid-height band instead of a solid wall of full blocks; a genuine
    # spike still stands tall against the flat hours (plan 064).
    ref = 2.0 * mean
    chars = []
    for h in hours:
        level = int(round((h / ref) * 8))
        level = max(0, min(8, level))
        chars.append(_SPARK[level])
    return "".join(chars), total


def prophecy_line(f, enabled: bool) -> str:
    """Legacy product-voice prophecy for one Forecast (unit-tested; not Future hero)."""
    name = getattr(f, "window", "?") or "?"
    idle = bool(getattr(f, "idle", False))
    if idle:
        reset = fmt_hms(getattr(f, "reset_in_secs", 0) or 0)
        text = f"the {name} window sleeps · resets in {reset}"
        return c.dim(f"  prophecy: {text}", enabled)

    pct = float(getattr(f, "projected_pct", 0.0) or 0.0)
    eta = getattr(f, "eta_to_cap_secs", None)
    conf = float(getattr(f, "confidence", 1.0) or 1.0)

    if pct >= 100 and eta is not None:
        text = f"the cap falls in {fmt_dh_long(eta)} at this pace"
    elif pct >= 80:
        text = f"approaching the cap — {round(pct)}% projected by reset"
    else:
        text = f"at the current pace you reach {round(pct)}% of cap before reset"

    if conf < 1.0:
        text += f" · confidence {int(conf * 100)}%"

    return c.dim(f"  prophecy: {text}", enabled)


def _bar(pct: float, enabled: bool, width: int = 12) -> str:
    pct = max(0.0, min(100.0, float(pct)))
    filled = int(round(width * pct / 100.0))
    filled = max(0, min(width, filled))
    bar = "█" * filled + "░" * (width - filled)
    return c.gauge(bar, pct, enabled)


def _status_word(status: str, enabled: bool) -> str:
    if status in ("IDLE", "UNKNOWN"):
        return c.dim(status, enabled)
    return c.gauge(status, status_gauge_pct(status), enabled)


def _race_caption(truth, eta, enabled: bool) -> str:
    if truth.idle and truth.source != "live":
        return c.dim("    cap race   (idle)", enabled)
    now = truth.now_pct
    if now is not None and now >= 100.0:
        return c.gauge("    cap race   already at the wall", 100.0, enabled)
    if eta is None:
        # No projected cap hit. Don't reassure ("no hit before reset") when the
        # live now is already near the wall — say so factually (plan 064).
        if now is not None and now >= 85.0:
            return c.gauge(
                f"    cap race   {round(now)}% now · no cap hit projected", 90.0, enabled
            )
        return c.dim("    cap race   no cap hit projected", enabled)
    # eta_for_race only returns a value for a real hit before reset.
    line = f"    cap race   hit in {fmt_dh_long(eta)} if pace holds"
    return c.gauge(line, 100.0, enabled) if enabled else line


def _fmt_age(age: float) -> str:
    a = int(age)
    if a < 90:
        return f"{a}s ago"
    if a < 5400:
        return f"~{round(a / 60)}m ago"
    return f"~{round(a / 3600)}h ago"


def _render_window_full(f, truth, eta, status, width: int, enabled: bool) -> list[str]:
    """width >= 48: multi-line race detail for one window."""
    out: list[str] = []
    name = truth.window
    out.append(f"  {name}")

    show_bar = width >= 72
    now = truth.now_pct
    if now is not None:
        pct_s = c.gauge(f"{round(now)}%", now, enabled)
        prov = ""
        if truth.source == "live":
            # A retained / stale cell is NOT "live now"; label + age it exactly
            # like Present so the same cell reads the same on both tabs (I4).
            if truth.is_retained:
                label = "    was live  "
                prov = c.dim(" · retained", enabled)
            else:
                label = "    live now  "
            if truth.age_secs is not None and truth.age_secs > 0:
                prov += c.dim(f" · {_fmt_age(truth.age_secs)}", enabled)
        else:
            label = "    now        "
        if show_bar:
            bar = _bar(now, enabled, width=12)
            out.append(f"{label} {pct_s}   {bar}{prov}")
        else:
            out.append(f"{label} {pct_s}{prov}")

    reset_s = fmt_dh_long(truth.reset_in) if truth.reset_in >= 3600 else fmt_reset(truth.reset_in)
    out.append(c.dim(f"    resets in  {reset_s}", enabled))
    out.append(_race_caption(truth, eta, enabled))
    out.append(c.dim(f"    margin     {margin_line(truth, eta)}", enabled))

    end = truth.end_pct
    if end is not None:
        show_end = True
        lag_note = ""
        if truth.source == "live" and now is not None and abs(end - now) >= 1.0:
            lag_note = "  (local logs · may lag live)"
        elif truth.source == "live":
            lag_note = "  (local logs)"
        elif now is not None and abs(end - now) < 1.0:
            show_end = False  # redundant with now
        if show_end:
            end_s = f"{round(end)}%"
            out.append(c.dim(f"    end proj   {end_s}{lag_note}", enabled))
    return out


def _render_window_narrow(truth, status, enabled: bool) -> str:
    """width < 48: one line per window."""
    name = (truth.window or "?")[:8]
    now = truth.now_pct
    now_s = f"{round(now)}%" if now is not None else "—"
    reset_s = fmt_reset(truth.reset_in)
    live = "live " if truth.source == "live" else ""
    st = _status_word(status, enabled)
    return f"  {name} {st} {live}{now_s} · reset {reset_s}"


def render_future(
    forecasts,
    profile,
    now: float,
    width: int,
    enabled: bool,
    cost_line: str | None = None,
    cells=None,
) -> list[str]:
    """Future panel: per-profile race verdict + window detail + 24h spark + cost."""
    from ..cli.colors import display_width

    cells = cells or {}
    fs = list(forecasts or [])

    # Pre-scan for any live source (title)
    any_live = False
    if fs:
        for f in fs:
            if window_truth(f, cells).source == "live":
                any_live = True
                break
    title = "Future — cap race (live when available)" if any_live else "Future — cap race"
    out: list[str] = [c.dim(title, enabled), ""]

    if not fs:
        out.append(c.dim("  (no windows / no forecast yet)", enabled))
        return out

    groups: dict[str, list] = {}
    for f in fs:
        p = getattr(f, "profile", "default") or "default"
        groups.setdefault(p, []).append(f)

    narrow = width < 48
    for pi, (pname, pfs) in enumerate(sorted(groups.items())):
        if pi:
            out.append("")

        # per-window truth + status
        rows = []
        statuses = []
        for f in sorted(pfs, key=lambda x: getattr(x, "window", "") or ""):
            truth = window_truth(f, cells)
            eta = eta_for_race(f, truth)
            status = race_status(truth, eta)
            rows.append((f, truth, eta, status))
            statuses.append(status)

        verdict = profile_verdict(statuses)
        label = (pname or "default").upper()
        if label == "DEFAULT":
            label = "DEFAULT"
        head = f"  {label}  ·  {_status_word(verdict, enabled)}"
        out.append(head)

        for f, truth, eta, status in rows:
            if narrow:
                line = _render_window_narrow(truth, status, enabled)
                if display_width(line) > width > 0:
                    # crude cell-blind trim is ok at this floor
                    line = line[: max(0, width)]
                out.append(line)
            else:
                out.extend(_render_window_full(f, truth, eta, status, width, enabled))

    # shared next-24h sparkline (secondary)
    out.append("")
    spark, expected = spark_next24(profile, now)
    if not spark:
        out.append(c.dim("  next 24h  (no burn history yet)", enabled))
    else:
        exp_s = fmt_tokens(int(round(expected))) if expected else "0"
        line = f"  next 24h  {spark}   expected {exp_s} tokens"
        if display_width(line) > width and width >= 20:
            line = f"  next 24h  {spark}"
        out.append(c.dim(line, enabled) if not enabled else line)

    if cost_line:
        out.append("")
        out.append(c.dim(f"  {cost_line}", enabled))
    return out


def cost_pace_line(usd_7d: float | None, days: int = 7) -> str | None:
    """Measured spend pace string, or None when cost unavailable."""
    if usd_7d is None:
        return None
    per_day = float(usd_7d) / max(1, days)
    per_week = per_day * 7.0
    return f"spend pace: ~${per_day:,.2f}/day over the last {days} days → ~${per_week:,.2f}/week"
