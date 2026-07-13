"""Thin reference adapter: render a Forecast list to one ANSI status line.
Proof the engine renders anywhere; a polished status bar is a separate project.

Works for any configured source (claude_code, grok, generic). Use via
`oracle statusline` (e.g. in $PROMPT or shell rc). Grok users: set source=grok
in config; tmux users pipe via `oracle tmux` in status-right."""

from ..cli import colors as c
from ..core.timeutil import fmt_dh_long, fmt_reset, fmt_tokens


def _segment(f, enabled):
    pct = f.projected_pct
    prof = getattr(f, "profile", "default")
    pre = f"{prof[0].upper()}: " if prof != "default" else ""
    body = (
        f"{pre}{fmt_reset(f.reset_in_secs)} {fmt_tokens(f.used)}/{fmt_tokens(f.cap)} →{round(pct)}%"
    )
    if f.eta_to_cap_secs is not None:
        body += f" {c.M_WARN} cap {fmt_dh_long(f.eta_to_cap_secs)}"
    return f"{c.violet('🕐', enabled)} {c.gauge(body, pct, enabled)}"


def render(forecasts, color=None):
    enabled = c.pipe_color() if color is None else color
    return "  ".join(_segment(f, enabled) for f in forecasts if not f.idle)


def cost_segment(usd, enabled):
    """' · $X.XX' when usd is a positive float, else '' (never $0.00 noise)."""
    if not isinstance(usd, (int, float)) or usd <= 0:
        return ""
    return c.dim(f" · ${usd:,.2f} today", enabled)
