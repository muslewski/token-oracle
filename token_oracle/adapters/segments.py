"""Shared forecast segment body for statusline + tmux.

One plain-text body, two encodings (ANSI / tmux). Adaptive HUD degrades
full → compact → minimal to fit a cell budget. Stdlib only.
"""

from __future__ import annotations

from ..cli import colors as c
from ..core.timeutil import fmt_dh_long, fmt_reset, fmt_tokens

# Styles ordered richest → leanest.
_STYLES = ("full", "compact", "minimal")


def dedupe_forecasts(forecasts):
    """Drop windows that would render as the same segment body.

    Multi-profile configs can emit lookalikes (e.g. weekly + fable sharing the
    same used/cap/pct/reset). Key on visual identity, not just window name, so
    each segment appears once. Prefer the first occurrence (stable order).
    """
    seen = set()
    out = []
    for f in forecasts or []:
        if getattr(f, "idle", False):
            continue
        # Visual identity of the full segment (profile letter + numbers).
        key = (
            getattr(f, "profile", "default"),
            int(getattr(f, "used", 0) or 0),
            int(getattr(f, "cap", 0) or 0),
            round(float(getattr(f, "projected_pct", 0.0) or 0.0)),
            round(float(getattr(f, "reset_in_secs", 0) or 0) / 60.0),  # minute bucket
            None
            if getattr(f, "eta_to_cap_secs", None) is None
            else round(float(f.eta_to_cap_secs) / 60.0),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def _prefix(f, *, spaced: bool) -> str:
    prof = getattr(f, "profile", "default")
    if prof == "default":
        return ""
    letter = str(prof)[0].upper()
    return f"{letter}: " if spaced else f"{letter}:"


def segment_body(f, style: str = "full") -> str:
    """Plain (no color) segment text for one Forecast.

    full:     ``C: 4h 12k/220k →42%``  (+ optional `` ⚠ cap …``)
    compact:  ``C:5h 42%``
    minimal:  ``C:42%`` or ``OVER`` when ≥100%
    """
    style = style if style in _STYLES else "full"
    pct = float(getattr(f, "projected_pct", 0.0) or 0.0)
    rpct = round(pct)
    name = getattr(f, "window", "?") or "?"
    # shorten weekly → wk for compact surfaces
    short = "wk" if name.lower() in ("weekly", "week", "7d") else name

    if style == "minimal":
        pre = _prefix(f, spaced=False)
        if pct >= 100:
            return f"{pre}OVER" if pre else "OVER"
        return f"{pre}{rpct}%"

    if style == "compact":
        pre = _prefix(f, spaced=False)
        return f"{pre}{short} {rpct}%"

    # full — include short window name so weekly vs 5h are distinguishable
    pre = _prefix(f, spaced=True)
    body = (
        f"{pre}{short} {fmt_reset(f.reset_in_secs)} "
        f"{fmt_tokens(f.used)}/{fmt_tokens(f.cap)} "
        f"{c.ARROW}{rpct}%"
    )
    eta = getattr(f, "eta_to_cap_secs", None)
    if eta is not None:
        body += f" {c.M_WARN} cap {fmt_dh_long(eta)}"
    return body


def _encode_ansi(body: str, pct: float, enabled: bool, *, clock: bool = True) -> str:
    head = f"{c.violet(c.M_CLOCK, enabled)} " if clock else ""
    return f"{head}{c.gauge(body, pct, enabled)}"


def _encode_tmux(body: str, pct: float) -> str:
    # tmux: no leading clock emoji (width-unstable in status bars)
    return f"{c.gauge_tmux(pct)}{body}#[default]"


def _join(parts, encoding: str) -> str:
    if encoding == "tmux":
        return " ".join(parts)
    return "  ".join(parts)


def _render_style(forecasts, style: str, encoding: str, color: bool) -> str:
    parts = []
    for f in forecasts:
        body = segment_body(f, style=style)
        pct = float(getattr(f, "projected_pct", 0.0) or 0.0)
        if encoding == "tmux":
            parts.append(_encode_tmux(body, pct))
        else:
            # full style keeps clock; compact/minimal drop it for density
            parts.append(_encode_ansi(body, pct, color, clock=(style == "full")))
    return _join(parts, encoding)


def _plain_width(s: str) -> int:
    return c.display_width(c.strip_ansi(s).replace("#[fg=red]", "")
                           .replace("#[fg=green]", "")
                           .replace("#[fg=colour154]", "")
                           .replace("#[fg=colour214]", "")
                           .replace("#[default]", ""))


def render_adaptive(forecasts, budget=None, encoding="ansi", color=None) -> str:
    """Render forecasts, degrading style until plain width ≤ budget.

    ``budget is None`` → full style (parse-stable default for tmux / statusline).
    Idle-only / empty → ``""``.
    """
    fs = dedupe_forecasts(forecasts)
    if not fs:
        return ""
    if color is None:
        color = c.pipe_color() if encoding != "tmux" else True
    # tmux always "colored" via #[fg=…] tags (not ANSI); color flag unused

    if budget is None:
        return _render_style(fs, "full", encoding, bool(color))

    budget = max(1, int(budget))
    last = ""
    for style in _STYLES:
        last = _render_style(fs, style, encoding, bool(color))
        if _plain_width(last) <= budget:
            return last
    # still over: hard-truncate minimal to budget
    plain = c.strip_ansi(last)
    # strip tmux tags for measure
    for tag in (
        "#[fg=red]",
        "#[fg=green]",
        "#[fg=colour154]",
        "#[fg=colour214]",
        "#[default]",
    ):
        plain = plain.replace(tag, "")
    if c.display_width(plain) <= budget:
        return last
    # emit a single minimal severity chip that fits
    top = max(fs, key=lambda f: float(getattr(f, "projected_pct", 0) or 0))
    chip = segment_body(top, style="minimal")
    while c.display_width(chip) > budget and len(chip) > 1:
        chip = chip[:-1]
    pct = float(getattr(top, "projected_pct", 0) or 0)
    if encoding == "tmux":
        return _encode_tmux(chip, pct)
    return c.gauge(chip, pct, bool(color))


def cell_budget() -> int | None:
    """Best-effort cell budget from $COLUMNS / $ORACLE_STATUS_WIDTH. None = unlimited."""
    import os

    for key in ("ORACLE_STATUS_WIDTH", "COLUMNS"):
        raw = os.environ.get(key)
        if raw and str(raw).isdigit():
            n = int(raw)
            if n > 0:
                return n
    return None
