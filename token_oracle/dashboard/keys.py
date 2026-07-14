"""Non-blocking key input for the dash. decode() is pure (tested); the
readers own platform specifics. Stdlib only: termios/tty/select on POSIX,
msvcrt on Windows."""

from __future__ import annotations

import select
import sys
import time

LEFT, RIGHT, QUIT, OTHER = "left", "right", "quit", "other"
TAB1, TAB2, TAB3, CYCLE = "tab1", "tab2", "tab3", "cycle"

# Semantic keys the dash loop understands.
_SEMANTIC = frozenset({LEFT, RIGHT, QUIT, OTHER, TAB1, TAB2, TAB3, CYCLE})


def decode(data: bytes) -> list[str]:
    """Raw stdin bytes -> semantic keys.

    Understands arrow escapes (``b"\\x1b[D"`` LEFT / ``b"\\x1b[C"`` RIGHT),
    vim keys (h/l), digits 1-3 (tab1/tab2/tab3), tab (cycle), q/Q and
    ctrl-c (``b"\\x03"``) -> QUIT. Unknown -> OTHER. A lone ESC does not
    crash; incomplete escape sequences are treated as OTHER.
    """
    if not data:
        return []
    out: list[str] = []
    i = 0
    n = len(data)
    while i < n:
        b = data[i : i + 1]
        # CSI arrow sequences: ESC [ C/D  or ESC O C/D (application mode)
        if b == b"\x1b":
            if i + 2 < n and data[i + 1 : i + 2] in (b"[", b"O"):
                code = data[i + 2 : i + 3]
                if code == b"D":
                    out.append(LEFT)
                elif code == b"C":
                    out.append(RIGHT)
                else:
                    out.append(OTHER)
                i += 3
                continue
            # lone / incomplete ESC
            out.append(OTHER)
            i += 1
            continue
        if b in (b"\x03", b"q", b"Q"):
            out.append(QUIT)
            i += 1
            continue
        if b in (b"h", b"H"):
            out.append(LEFT)
            i += 1
            continue
        if b in (b"l", b"L"):
            out.append(RIGHT)
            i += 1
            continue
        if b == b"1":
            out.append(TAB1)
            i += 1
            continue
        if b == b"2":
            out.append(TAB2)
            i += 1
            continue
        if b == b"3":
            out.append(TAB3)
            i += 1
            continue
        if b == b"\t":
            out.append(CYCLE)
            i += 1
            continue
        # Windows console arrows arrive as 0xe0 + code when read as bytes
        if b == b"\xe0" and i + 1 < n:
            code = data[i + 1 : i + 2]
            if code == b"K":
                out.append(LEFT)
            elif code == b"M":
                out.append(RIGHT)
            else:
                out.append(OTHER)
            i += 2
            continue
        out.append(OTHER)
        i += 1
    return out


class PosixReader:
    """Context manager: tty.setcbreak on __enter__, restore termios attrs on
    __exit__. poll(timeout) uses select.select on sys.stdin; returns decode()d keys.
    """

    def __init__(self, stream=None):
        self._stream = stream if stream is not None else sys.stdin
        self._fd = None
        self._old = None
        self._entered = False

    def __enter__(self) -> PosixReader:
        import termios
        import tty

        self._fd = self._stream.fileno()
        self._old = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        self._entered = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._entered and self._old is not None and self._fd is not None:
            import termios

            try:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)
            except Exception:
                pass
        self._entered = False
        return None

    def poll(self, timeout: float = 0.25) -> list[str]:
        """Wait up to `timeout` seconds for input; return decoded keys (maybe empty)."""
        if not self._entered:
            return []
        try:
            r, _, _ = select.select([self._stream], [], [], max(0.0, float(timeout)))
        except (ValueError, OSError):
            return []
        if not r:
            return []
        try:
            data = os_read_stdin(self._stream)
        except Exception:
            return []
        return decode(data)


def os_read_stdin(stream) -> bytes:
    """Read available bytes from a tty stream without blocking past readiness."""
    import os as _os

    fd = stream.fileno()
    # After select says ready, read a modest chunk (escape seqs are short).
    try:
        return _os.read(fd, 64)
    except BlockingIOError:
        return b""


class WindowsReader:
    """msvcrt.kbhit()/getwch(); arrow keys arrive as '\\xe0' + code ('K' left,
    'M' right). Same poll(timeout) interface (timeout via time.sleep slice).
    """

    def __init__(self):
        self._entered = False

    def __enter__(self) -> WindowsReader:
        self._entered = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._entered = False
        return None

    def poll(self, timeout: float = 0.25) -> list[str]:
        if not self._entered:
            return []
        try:
            import msvcrt  # type: ignore[import-untyped]
        except ImportError:
            return []
        deadline = time.monotonic() + max(0.0, float(timeout))
        buf = bytearray()
        while True:
            while msvcrt.kbhit():  # type: ignore[attr-defined]
                ch = msvcrt.getwch()  # type: ignore[attr-defined]
                if ch in ("\x00", "\xe0"):
                    # special / arrow prefix; next getwch is the code
                    code = msvcrt.getwch()  # type: ignore[attr-defined]
                    if code == "K":
                        buf.extend(b"\xe0K")
                    elif code == "M":
                        buf.extend(b"\xe0M")
                    else:
                        buf.append(0x00)
                else:
                    buf.extend(ch.encode("utf-8", errors="replace"))
            if buf:
                return decode(bytes(buf))
            if time.monotonic() >= deadline:
                return []
            time.sleep(0.02)


def reader():
    """Return the platform reader; None when stdin is not a tty (dash then
    runs without key input — present-only / non-interactive path).
    """
    try:
        if not sys.stdin.isatty():
            return None
    except Exception:
        return None
    if sys.platform == "win32":
        return WindowsReader()
    try:
        import termios  # noqa: F401
        import tty  # noqa: F401
    except ImportError:
        return None
    return PosixReader()
