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
M_CLOCK = "🕐"
M_HEAD = "◔"
M_PEND = "◌"

# One arrow glyph for every human-facing surface (statusline, tmux, forecast).
ARROW = "→"

# U+2581–2588 block ramp (+ leading space for zero). Shared by forecast burn,
# report %CAP column, and any CLI spark.
SPARK_CHARS = " ▁▂▃▄▅▆▇█"


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
        # Truncate to the cell budget while KEEPING ANSI SGR (so a dim/colored
        # line stays dim/colored), leaving 1 cell for the ellipsis; append a
        # reset so styling never bleeds past the box.
        budget = inner_w - 1
        out = []
        used = 0
        i = 0
        had_sgr = False
        while i < len(text):
            m = _ANSI_RE.match(text, i)
            if m:
                out.append(m.group(0))
                had_sgr = True
                i = m.end()
                continue
            ch = text[i]
            w = _char_cells(ch)
            if used + w > budget:
                break
            out.append(ch)
            used += w
            i += 1
        out.append("…")
        if had_sgr:
            out.append(RESET)
        text = "".join(out)
    pad = " " * (inner_w - display_width(text))
    return f"│{text}{pad}│"


def strip_ansi(s: str) -> str:
    """Remove ANSI SGR/erase sequences; plain text for width/golden asserts."""
    return _ANSI_RE.sub("", s or "")


def sparkline(values, width=None) -> str:
    """Map a sequence of numbers to U+2581–2588 (stdlib only, no color).

    Empty → ``""``. Constant series → mid-level bars. Optional ``width``
    resamples by averaging buckets so a long series fits a fixed cell budget.
    """
    if not values:
        return ""
    nums = [float(v) for v in values]
    if width is not None and width > 0 and len(nums) != width:
        # bucket-average resample
        out_n = int(width)
        bucket = len(nums) / out_n
        resampled = []
        for i in range(out_n):
            a = int(i * bucket)
            b = max(a + 1, int((i + 1) * bucket))
            chunk = nums[a:b] or [0.0]
            resampled.append(sum(chunk) / len(chunk))
        nums = resampled
    lo = min(nums)
    hi = max(nums)
    n_levels = len(SPARK_CHARS) - 1  # 8 block levels; index 0 = space/empty
    if hi <= lo:
        mid = SPARK_CHARS[max(1, n_levels // 2)]
        return mid * len(nums)
    chars = []
    for v in nums:
        # 0..n_levels inclusive; tiny values can land on space when near lo
        level = int(round((v - lo) / (hi - lo) * n_levels))
        level = max(0, min(n_levels, level))
        chars.append(SPARK_CHARS[level])
    return "".join(chars)


def gauge_bar(pct, width=12, enabled=True) -> str:
    """Filled █/░ bar colored by gauge tier. Clamps pct to 0..100 for fill."""
    p = max(0.0, min(100.0, float(pct)))
    filled = int(round(width * p / 100.0))
    filled = max(0, min(width, filled))
    bar = "█" * filled + "░" * (width - filled)
    return gauge(bar, float(pct), enabled)


def severity_label(bad: int, total: int) -> str:
    """Doctor banner word from failure count: ok / warn / crit."""
    if bad <= 0:
        return "ok"
    if bad >= max(2, total // 2):
        return "crit"
    return "warn"


def help_paint(text: str, role: str = "accent", enabled: bool | None = None) -> str:
    """Argparse / help chrome — same 256 palette as the product (no 16-color dialect)."""
    if enabled is None:
        enabled = color_enabled(sys.stdout)
    if not enabled:
        return text
    if role == "accent":
        return violet(text, True)
    if role == "cmd":
        return paint(text, _TIER_CODE["green"], True)
    if role == "opt":
        return paint(text, "75", True)  # soft blue-ish for options
    if role == "muted":
        return dim(text, True)
    return text
