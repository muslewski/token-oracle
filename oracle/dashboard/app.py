"""Minimal stdlib TUI over the Forecast list. render_frame is pure (tested);
run() is the refresh loop."""
import os
import time

from ..core.engine import forecast as run_forecast
from ..core.timeutil import fmt_tokens, fmt_hms, fmt_dh_long


def _bar(pct, width=24):
    filled = max(0, min(width, int(round(pct / 100.0 * width))))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def render_frame(forecasts, now):
    lines = ["token-oracle", "=" * 40]
    if not forecasts:
        lines.append("(no windows / no data)")
        return "\n".join(lines)
    for f in forecasts:
        if f.idle:
            lines.append(f"{f.window:>8}: idle  (resets in {fmt_hms(f.reset_in_secs)})")
            continue
        eta = (f" | cap in {fmt_dh_long(f.eta_to_cap_secs)}"
               if f.eta_to_cap_secs is not None else "")
        lines.append(
            f"{f.window:>8}: {fmt_tokens(f.used)}/{fmt_tokens(f.cap)} "
            f"->{round(f.projected_pct)}%  resets {fmt_hms(f.reset_in_secs)}{eta}")
        lines.append(f"          {_bar(f.projected_pct)}")
    return "\n".join(lines)


def run(cfg, now):
    try:
        while True:
            os.system("clear")
            print(render_frame(run_forecast(time.time(), cfg), time.time()))
            print("\n(ctrl-c to quit)")
            time.sleep(2)
    except KeyboardInterrupt:
        return 0
