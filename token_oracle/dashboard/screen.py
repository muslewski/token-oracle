"""Alternate-screen guard: enter alt buffer + hide cursor on start, ALWAYS
restore on exit (normal return, exception, ctrl-c). Pure-ANSI, stdlib.

Painter (scene.py) reuses these sequences so restore semantics stay in one place.
"""

from __future__ import annotations

import sys

ENTER = "\033[?1049h\033[?25l"  # alt screen + hide cursor
LEAVE = "\033[?1049l\033[?25h"  # restore primary + show cursor


class AltScreen:
    """Context manager for the alternate screen buffer.

    When stdout is not a tty, enter/exit are no-ops so piped `oracle dash | head`
    stays usable and CI-safe.
    """

    def __init__(self, stream=None):
        self._stream = stream if stream is not None else sys.stdout
        self._active = False

    def __enter__(self) -> AltScreen:
        self.enter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.exit()
        return None

    def _is_tty(self) -> bool:
        try:
            return bool(getattr(self._stream, "isatty", lambda: False)())
        except Exception:
            return False

    def enter(self) -> None:
        if not self._is_tty():
            return
        try:
            self._stream.write(ENTER)
            self._stream.flush()
            self._active = True
        except Exception:
            self._active = False

    def exit(self) -> None:
        if not self._active:
            return
        try:
            self._stream.write(LEAVE + "\033[0m")
            # trailing newline so the next shell prompt is clean
            self._stream.write("\n")
            self._stream.flush()
        except Exception:
            pass
        finally:
            self._active = False
