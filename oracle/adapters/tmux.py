"""Thin reference adapter: render a Forecast list to a tmux status string."""
from ..core.timeutil import fmt_tokens, fmt_hms, fmt_dh_long


def color_for(pct):
    if pct >= 120:
        return "#[fg=red]"
    if pct >= 100:
        return "#[fg=colour214]"
    if pct >= 85:
        return "#[fg=colour154]"
    return "#[fg=green]"


def _segment(f):
    pct = f.projected_pct
    body = (f"{fmt_hms(f.reset_in_secs)} "
            f"{fmt_tokens(f.used)}/{fmt_tokens(f.cap)} ->{round(pct)}%")
    if f.eta_to_cap_secs is not None:
        body += f" cap {fmt_dh_long(f.eta_to_cap_secs)}"
    return f"{color_for(pct)}{body}#[default]"


def render(forecasts):
    return " ".join(_segment(f) for f in forecasts if not f.idle)
