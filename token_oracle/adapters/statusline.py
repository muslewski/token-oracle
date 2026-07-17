"""Thin reference adapter: render a Forecast list to one ANSI status line.
Proof the engine renders anywhere; a polished status bar is a separate project.

Works for any configured source (claude_code, grok, generic). Use via
`oracle statusline` (e.g. in $PROMPT or shell rc). Grok users: set source=grok
in config; tmux users pipe via `oracle tmux` in status-right."""

from ..cli import colors as c
from . import segments


def render(forecasts, color=None, budget=None):
    """One ANSI line. ``budget`` degrades full→compact→minimal (adaptive HUD)."""
    enabled = c.pipe_color() if color is None else color
    if budget is None:
        budget = segments.cell_budget()
    return segments.render_adaptive(
        forecasts, budget=budget, encoding="ansi", color=enabled
    )


def cost_segment(usd, enabled):
    """' · $X.XX' when usd is a positive float, else '' (never $0.00 noise)."""
    if not isinstance(usd, (int, float)) or usd <= 0:
        return ""
    return c.dim(f" · ${usd:,.2f} today", enabled)
