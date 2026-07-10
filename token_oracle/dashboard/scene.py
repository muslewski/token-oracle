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

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def strip_ansi(s: str) -> str:
    """Remove all ANSI escape sequences for safe length/width calculations and truncation."""
    return _ANSI_RE.sub("", s or "")


def visible_len(s: str) -> int:
    """Visible character length ignoring ANSI escapes."""
    return len(strip_ansi(s))


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
                if visible_len(ln) > width:
                    # drop styling for over-width lines (simplest correct truncation)
                    ln = strip_ansi(ln)[:width]
                out.append(ln)
        return out


class Painter:
    """Owns the terminal for stable in-place repaints using alt screen.

    enter(): switches to alternate screen buffer and hides cursor.
    exit(): restores primary screen and shows cursor. Must be called on
    every exit path (use as context manager; run() adds try/finally too).

    paint(lines): moves cursor home, erases to EOL per line. Issues a full
    clear (\033[2J) ONLY on detected terminal size change since last paint.
    No assumption on line count — caller guarantees fixed height.
    """

    def __init__(self) -> None:
        self._prev_size: tuple[int, int] | None = None
        self._entered = False

    def __enter__(self) -> "Painter":
        self.enter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.exit()
        # return None (falsy) so exceptions propagate; do not swallow
        return None

    def enter(self) -> None:
        sys.stdout.write("\033[?1049h\033[?25l")
        sys.stdout.flush()
        self._entered = True
        try:
            sz = shutil.get_terminal_size((80, 24))
            self._prev_size = (sz.columns, sz.lines)
        except Exception:
            self._prev_size = (80, 24)

    def exit(self) -> None:
        if not self._entered:
            return
        try:
            sys.stdout.write("\033[?1049l\033[?25h\033[0m\n")
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
        if self._prev_size is None or curr_size != self._prev_size:
            sys.stdout.write("\033[2J")
            self._prev_size = curr_size
        sys.stdout.write("\033[H")
        n = len(lines)
        for i, line in enumerate(lines):
            if i < n - 1:
                sys.stdout.write(line + "\033[K\n")
            else:
                sys.stdout.write(line + "\033[K")
        sys.stdout.flush()
