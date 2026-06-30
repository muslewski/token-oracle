"""Stdlib TUI over the Forecast list. render_frame is pure (tested); run() is the
refresh loop."""
import os
import time

from ..core.engine import forecast as run_forecast
from ..core.timeutil import fmt_tokens, fmt_hms, fmt_dh_long
from ..cli import colors as c

BAR_W = 12


def _bar(pct, enabled, width=BAR_W):
    filled = max(0, min(width, int(round(pct / 100.0 * width))))
    return c.gauge("█" * filled + "░" * (width - filled), pct, enabled)


def render_frame(forecasts, now, color=None):
    enabled = c.color_enabled() if color is None else color
    lines = [c.violet(f"{c.M_ORACLE} token-oracle", enabled),
             c.dim("─" * 24, enabled)]
    if not forecasts:
        lines.append(c.dim("(no windows / no data)", enabled))
        return "\n".join(lines)
    for f in forecasts:
        if f.idle:
            lines.append(c.dim(
                f"  {c.M_BULLET} {f.window:<6} idle · resets {fmt_hms(f.reset_in_secs)}",
                enabled))
            continue
        pct = f.projected_pct
        lines.append(
            f"  {c.M_BULLET} {f.window:<6} {_bar(pct, enabled)}  "
            f"{c.gauge(f'{round(pct)}%', pct, enabled)}")
        meta = c.dim(
            f"         {fmt_tokens(f.used)}/{fmt_tokens(f.cap)} "
            f"· resets {fmt_hms(f.reset_in_secs)}", enabled)
        if f.eta_to_cap_secs is not None:
            meta += "  " + c.gauge(
                f"{c.M_WARN} cap in {fmt_dh_long(f.eta_to_cap_secs)}", pct, enabled)
        lines.append(meta)
    return "\n".join(lines)


def run(cfg, now):
    try:
        while True:
            os.system("clear")
            t = time.time()
            print(render_frame(run_forecast(t, cfg), t))
            print(c.dim("\n(ctrl-c to quit)", c.color_enabled()))
            time.sleep(2)
    except KeyboardInterrupt:
        return 0
