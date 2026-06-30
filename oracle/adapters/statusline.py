"""Thin reference adapter: render a Forecast list to one ANSI status line.
Proof the engine renders anywhere; a polished status bar is a separate project."""
from ..core.timeutil import fmt_tokens, fmt_hms, fmt_dh_long

GREEN, LIME, ORANGE, RED, RESET = (
    "\033[38;5;42m", "\033[38;5;154m", "\033[38;5;214m", "\033[38;5;196m",
    "\033[0m",
)


def color_for(pct):
    if pct >= 120:
        return RED
    if pct >= 100:
        return ORANGE
    if pct >= 85:
        return LIME
    return GREEN


def _segment(f):
    pct = f.projected_pct
    body = (f"{fmt_hms(f.reset_in_secs)} "
            f"{fmt_tokens(f.used)}/{fmt_tokens(f.cap)} →{round(pct)}%")
    if f.eta_to_cap_secs is not None:
        body += f" ⚠ cap {fmt_dh_long(f.eta_to_cap_secs)}"
    return f"{color_for(pct)}🕐 {body}{RESET}"


def render(forecasts):
    return "  ".join(_segment(f) for f in forecasts if not f.idle)
