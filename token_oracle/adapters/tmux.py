"""Thin reference adapter: render a Forecast list to a tmux status string.

Neutral across sources. Configure "source": "grok" (or claude_code) and use:
set -g status-right '#(oracle tmux)'
Grok tmux users get live token forecasts in bottom bar alongside sessions."""

from ..cli import colors as c
from ..core.timeutil import fmt_dh_long, fmt_reset, fmt_tokens


def _segment(f):
    pct = f.projected_pct
    prof = getattr(f, "profile", "default")
    pre = f"{prof[0].upper()}:" if prof != "default" else ""
    body = f"{pre}{fmt_reset(f.reset_in_secs)} {fmt_tokens(f.used)}/{fmt_tokens(f.cap)} ->{round(pct)}%"
    if f.eta_to_cap_secs is not None:
        body += f" cap {fmt_dh_long(f.eta_to_cap_secs)}"
    return f"{c.gauge_tmux(pct)}{body}#[default]"


def render(forecasts):
    return " ".join(_segment(f) for f in forecasts if not f.idle)
