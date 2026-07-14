"""Fixed-region terminal scene. A Scene is an ordered list of Regions, each
with a constant height. render() returns exactly sum(heights) lines every
frame — layout stability is a type-level property here, not a hope. The
painter repaints in place (cursor home + erase-to-EOL per line); the only
full clear happens on terminal resize."""

import re
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass

from ..cli.colors import display_width

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def strip_ansi(s: str) -> str:
    """Remove all ANSI escape sequences for safe length/width calculations and truncation."""
    return _ANSI_RE.sub("", s or "")


def visible_len(s: str) -> int:
    """Visible character length ignoring ANSI escapes."""
    return len(strip_ansi(s))


_RESET = "\033[0m"


def truncate_display(s: str, width: int) -> str:
    """Truncate to at most `width` terminal cells, keeping ANSI SGR styling
    and appending a reset so color never bleeds past the cut. Cell-aware
    (emoji/CJK = 2 cells), so the result never exceeds `width` on screen."""
    if display_width(s) <= width:
        return s
    out = []
    cells = 0
    i = 0
    had_sgr = False
    while i < len(s):
        if s[i] == "\x1b":
            m = _ANSI_RE.match(s, i)
            if m:
                out.append(m.group(0))
                had_sgr = True
                i = m.end()
                continue
        ch = s[i]
        w = display_width(ch)
        if cells + w > width:
            break
        out.append(ch)
        cells += w
        i += 1
    res = "".join(out)
    if had_sgr:
        res += _RESET
    return res


@dataclass
class Region:
    """A fixed-height region whose fill() produces content lines.

    fill must return at most 'height' lines; Scene.render will pad with blank
    lines or truncate if the fill overproduces. Height is constant for a
    given Scene (depends only on config shape at construction).
    """

    name: str
    height: int
    fill: Callable[[], list[str]]


class Scene:
    """Composes Regions into a fixed total-height frame.

    render(width) always returns exactly sum(r.height for r in regions) lines,
    each truncated to width (with styling dropped on overlong lines).
    """

    def __init__(self, regions: list[Region]):
        self.regions = list(regions)

    def render(self, width: int) -> list[str]:
        out: list[str] = []
        for reg in self.regions:
            lines = list(reg.fill() or [])
            if len(lines) > reg.height:
                lines = lines[: reg.height]
            while len(lines) < reg.height:
                lines.append("")
            for ln in lines:
                if display_width(ln) > width:
                    ln = truncate_display(ln, width)
                out.append(ln)
        return out


class Painter:
    """Owns the terminal for stable in-place repaints using alt screen.

    enter(): switches to alternate screen buffer and hides cursor (via
    dashboard.screen sequences). exit(): restores primary screen and shows
    cursor. Must be called on every exit path (use as context manager).

    paint(lines): moves cursor home, erases to EOL per line. Issues a full
    clear (\\033[2J) ONLY on detected terminal size change since last paint.

    Variable-height frames are allowed (Past/Present/Future tabs differ).
    After writing the new frame, paint emits \\033[J (erase from cursor to end
    of screen) so a shorter frame cannot leave ghost lines from the previous
    taller tab. Plan 034's fixed-height Scene still pads regions; the tab
    shell is allowed to change total line count between paints.
    """

    def __init__(self) -> None:
        self._prev_size: tuple[int, int] | None = None
        self._prev_line_count: int = 0
        self._entered = False

    def __enter__(self) -> "Painter":
        self.enter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.exit()
        # return None (falsy) so exceptions propagate; do not swallow
        return None

    def enter(self) -> None:
        from .screen import ENTER

        # Only enter alt screen on a real TTY (piped dash stays non-interactive)
        is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
        if is_tty:
            sys.stdout.write(ENTER)
            sys.stdout.flush()
            self._entered = True
        else:
            self._entered = False
        try:
            sz = shutil.get_terminal_size((80, 24))
            self._prev_size = (sz.columns, sz.lines)
        except Exception:
            self._prev_size = (80, 24)

    def exit(self) -> None:
        if not self._entered:
            return
        from .screen import LEAVE

        try:
            sys.stdout.write(LEAVE + "\033[0m\n")
            sys.stdout.flush()
        finally:
            self._entered = False

    def paint(self, lines: list[str]) -> None:
        if not lines:
            return
        try:
            sz = shutil.get_terminal_size((80, 24))
            curr_size = (sz.columns, sz.lines)
        except Exception:
            curr_size = (80, 24)
        n = len(lines)
        size_changed = self._prev_size is None or curr_size != self._prev_size
        # Height change (tab switch Past↔Present, skeleton→ready) used to leave
        # ghost rows: plan 034 assumed fixed height. Full clear on height change
        # avoids a one-frame mash-up of old+new rows; erase-below is the safety net.
        height_changed = self._prev_line_count > 0 and n != self._prev_line_count
        if size_changed or height_changed:
            sys.stdout.write("\033[2J")
            if size_changed:
                self._prev_size = curr_size
        sys.stdout.write("\033[H")
        for i, line in enumerate(lines):
            if i < n - 1:
                sys.stdout.write(line + "\033[K\n")
            else:
                sys.stdout.write(line + "\033[K")
        # CSI J = erase from cursor to end of screen (rows under the new frame).
        sys.stdout.write("\033[J")
        self._prev_line_count = n
        sys.stdout.flush()
