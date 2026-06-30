"""Color/ANSI foundation: one palette, one set of gauge thresholds, terminal-aware
gating. Render functions stay plain; color is applied here at the output site so
color-off output is identical minus escape codes. Stdlib only. Consumer-ring util —
oracle.core never imports this."""
import os
import sys

RESET = "\033[0m"

# 256-color foreground codes
VIOLET = "141"
DIMC = "240"
_TIER_CODE = {"green": "42", "lime": "154", "orange": "214", "red": "196"}
_TIER_TMUX = {"green": "green", "lime": "colour154",
              "orange": "colour214", "red": "red"}

# semantic markers
M_ORACLE = "🔮"
M_WARN = "⚠"
M_BULLET = "●"
M_OK = "✓"
M_BAD = "✗"


def _no_color():
    return os.environ.get("NO_COLOR") is not None


def color_enabled(stream=None):
    """Interactive surfaces (dashboard, doctor): NO_COLOR off AND (FORCE_COLOR or tty)."""
    if _no_color():
        return False
    fc = os.environ.get("FORCE_COLOR")
    if fc not in (None, "", "0"):
        return True
    stream = stream if stream is not None else sys.stdout
    return bool(getattr(stream, "isatty", lambda: False)())


def pipe_color():
    """Adapter media (statusline, tmux): codes are read from a pipe, never a TTY —
    gate on NO_COLOR only."""
    return not _no_color()


def paint(text, code, enabled):
    return f"\033[38;5;{code}m{text}{RESET}" if enabled else text


def violet(text, enabled):
    return paint(text, VIOLET, enabled)


def dim(text, enabled):
    return paint(text, DIMC, enabled)


def gauge_tier(pct):
    """Severity tier for a projected pct. The one source of truth for thresholds."""
    if pct >= 120:
        return "red"
    if pct >= 100:
        return "orange"
    if pct >= 85:
        return "lime"
    return "green"


def gauge_ansi_code(pct):
    return _TIER_CODE[gauge_tier(pct)]


def gauge(text, pct, enabled):
    return paint(text, gauge_ansi_code(pct), enabled)


def gauge_tmux(pct):
    return "#[fg=%s]" % _TIER_TMUX[gauge_tier(pct)]


def ok_badge(good, enabled):
    return (paint(M_OK, _TIER_CODE["green"], enabled) if good
            else paint(M_BAD, _TIER_CODE["red"], enabled))
