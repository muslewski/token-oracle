"""Thin reference adapter: render a Forecast list to a tmux status string.

Neutral across sources. Configure "source": "grok" (or claude_code) and use:
set -g status-right '#(oracle tmux)'
Grok tmux users get live token forecasts in bottom bar alongside sessions."""

from . import segments


def render(forecasts, budget=None):
    """tmux-formatted status. Shares segment body with statusline (encoding only differs)."""
    if budget is None:
        budget = segments.cell_budget()
    return segments.render_adaptive(
        forecasts, budget=budget, encoding="tmux", color=True
    )
