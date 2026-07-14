"""Future-tab renderer: projection detail, prophecy lines, 24h sparkline.
Pure; no I/O. Data comes from Forecast + profile (core.profile_integral)."""

from __future__ import annotations

from ..cli import colors as c
from ..core.profile import profile_integral
from ..core.timeutil import fmt_dh_long, fmt_hms, fmt_reset, fmt_tokens

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
    peak = max(hours) if hours else 0.0
    if peak <= 0:
        return " " * 24, 0.0
    chars = []
    for h in hours:
        # map 0..peak -> 0..8
        level = int(round((h / peak) * 8))
        level = max(0, min(8, level))
        chars.append(_SPARK[level])
    return "".join(chars), total


def prophecy_line(f, enabled: bool) -> str:
    """Product-voice prophecy for one Forecast. Exact key phrases tested."""
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


def render_future(
    forecasts,
    profile,
    now: float,
    width: int,
    enabled: bool,
    cost_line: str | None = None,
) -> list[str]:
    """Future panel: per-window detail + shared 24h sparkline + optional cost pace."""
    from ..cli.colors import display_width

    out: list[str] = [c.dim("Future — projection detail", enabled), ""]
    fs = list(forecasts or [])
    if not fs:
        out.append(c.dim("  (no windows / no forecast yet)", enabled))
        return out

    # group by profile for multi-sub clarity
    groups: dict[str, list] = {}
    for f in fs:
        p = getattr(f, "profile", "default") or "default"
        groups.setdefault(p, []).append(f)

    for pi, (pname, pfs) in enumerate(sorted(groups.items())):
        if pi:
            out.append("")
        if len(groups) > 1:
            out.append(c.violet(f"  {pname}", enabled))
        for f in sorted(pfs, key=lambda x: getattr(x, "window", "") or ""):
            name = getattr(f, "window", "?") or "?"
            idle = bool(getattr(f, "idle", False))
            pct = float(getattr(f, "projected_pct", 0.0) or 0.0)
            reset_s = fmt_reset(getattr(f, "reset_in_secs", 0) or 0)
            if idle:
                glyph = "–"
                head = f"{glyph} {name:<6}  idle        resets {reset_s}"
            else:
                glyph = "●"
                bar = _bar(pct, enabled, width=12 if width >= 60 else 8)
                pct_s = c.gauge(f"{round(pct):3d}%", pct, enabled)
                head = f"{glyph} {name:<6}  {bar}  {pct_s}        resets {reset_s}"
            if display_width(head) > width:
                head = head[: max(0, width)]
            out.append(head)
            out.append(prophecy_line(f, enabled))

            eta = getattr(f, "eta_to_cap_secs", None)
            if eta is not None and not idle:
                warn = f"  {c.M_WARN} cap in {fmt_dh_long(eta)}"
                out.append(c.gauge(warn, pct, enabled) if enabled else warn)

    # shared next-24h sparkline
    out.append("")
    spark, expected = spark_next24(profile, now)
    if not spark:
        out.append(c.dim("  next 24h  (no burn history yet)", enabled))
    else:
        exp_s = fmt_tokens(int(round(expected))) if expected else "0"
        line = f"  next 24h  {spark}   expected {exp_s} tokens"
        if display_width(line) > width and width >= 20:
            # drop the 'expected' tail first
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
