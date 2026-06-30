"""Thin reference adapter: render a Forecast list to one ANSI status line.
Proof the engine renders anywhere; a polished status bar is a separate project."""
from ..core.timeutil import fmt_tokens, fmt_hms, fmt_dh_long
from ..cli import colors as c


def _segment(f, enabled):
    pct = f.projected_pct
    body = (f"{fmt_hms(f.reset_in_secs)} "
            f"{fmt_tokens(f.used)}/{fmt_tokens(f.cap)} →{round(pct)}%")
    if f.eta_to_cap_secs is not None:
        body += f" {c.M_WARN} cap {fmt_dh_long(f.eta_to_cap_secs)}"
    return f"{c.violet('🕐', enabled)} {c.gauge(body, pct, enabled)}"


def render(forecasts, color=None):
    enabled = c.pipe_color() if color is None else color
    return "  ".join(_segment(f, enabled) for f in forecasts if not f.idle)
