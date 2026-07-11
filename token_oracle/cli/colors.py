"""Color/ANSI foundation: one palette, one set of gauge thresholds, terminal-aware
gating. Render functions stay plain; color is applied here at the output site so
color-off output is identical minus escape codes. Stdlib only. Consumer-ring util —
oracle.core never imports this."""

import os
import re
import sys
import unicodedata

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mK]")
# Zero-width code points that occupy no terminal cell (ZWSP, ZWNJ, ZWJ, BOM).
_ZERO_WIDTH = frozenset("\u200b\u200c\u200d\ufeff")

RESET = "\033[0m"

# 256-color foreground codes
VIOLET = "141"
DIMC = "240"
_TIER_CODE = {"green": "42", "lime": "154", "orange": "214", "red": "196"}
_TIER_TMUX = {"green": "green", "lime": "colour154", "orange": "colour214", "red": "red"}

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
    return f"#[fg={_TIER_TMUX[gauge_tier(pct)]}]"


def ok_badge(good, enabled):
    return (
        paint(M_OK, _TIER_CODE["green"], enabled)
        if good
        else paint(M_BAD, _TIER_CODE["red"], enabled)
    )


# Dashboard extras. Panel icons are width-1 glyphs (✳/✦) so box borders align on
# every terminal — emoji render as 1 or 2 cells unpredictably across terminals.
M_CLAUDE = "✳"
M_GROK = "✦"
M_RESET = "🔄"
M_HEAVY = "💪"


def pulse(text, enabled, period=1.5, now=None):
    """Simple blink/pulse for alarm: toggles dim/bright based on time."""
    if not enabled:
        return text
    import time

    t = now if now is not None else time.time()
    on = int(t / (period / 2)) % 2 == 0
    if on:
        return f"\033[1m{text}{RESET}"  # bold flash
    return dim(text, enabled)


def _char_cells(ch: str) -> int:
    """Terminal cell width of a single character: 0 for combining/zero-width,
    2 for East-Asian Wide/Fullwidth (incl. most emoji, e.g. 🧠 ⚡), else 1.
    Ambiguous (box-drawing, ●, ×, …) counts as 1, matching modern terminals."""
    if ch in _ZERO_WIDTH or unicodedata.combining(ch):
        return 0
    if "\ufe00" <= ch <= "\ufe0f":  # variation selectors
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def display_width(s: str) -> int:
    """Number of terminal cells s occupies, ignoring ANSI SGR escapes. Unlike a
    raw char count this accounts for wide glyphs (emoji/CJK = 2 cells) so box
    borders stay aligned regardless of the content."""
    return sum(_char_cells(c) for c in _ANSI_RE.sub("", s or ""))


def visible_len(s: str) -> int:
    """Deprecated alias — use display_width. Kept for callers; now width-aware."""
    return display_width(s)


def box_top(title, width=40, enabled=True):
    t = f" {title} " if title else ""
    bar = "─" * max(0, width - 2 - display_width(t))
    return f"┌{t}{bar}┐"


def box_bot(width=40, enabled=True):
    return f"└{'─' * (width - 2)}┘"


def box_line(text, width=40, enabled=True):
    # pad or truncate using *display* width so wide glyphs / colored bars align
    inner_w = width - 2
    if display_width(text) > inner_w:
        # trim character-by-character until it fits the cell budget (leaving 1 for …)
        cut = ""
        used = 0
        for ch in _ANSI_RE.sub("", text):
            w = _char_cells(ch)
            if used + w > inner_w - 1:
                break
            cut += ch
            used += w
        text = cut + "…"
    pad = " " * (inner_w - display_width(text))
    return f"│{text}{pad}│"
