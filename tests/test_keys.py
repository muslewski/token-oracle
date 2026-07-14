"""Pure decode() tests for dashboard key input (plan 018)."""

from token_oracle.dashboard.keys import (
    CYCLE,
    LEFT,
    OTHER,
    QUIT,
    RIGHT,
    TAB1,
    TAB2,
    TAB3,
    decode,
    reader,
)


def test_decode_arrow_left_right():
    assert decode(b"\x1b[D") == [LEFT]
    assert decode(b"\x1b[C") == [RIGHT]


def test_decode_application_mode_arrows():
    assert decode(b"\x1bOD") == [LEFT]
    assert decode(b"\x1bOC") == [RIGHT]


def test_decode_vim_hl():
    assert decode(b"h") == [LEFT]
    assert decode(b"l") == [RIGHT]
    assert decode(b"H") == [LEFT]
    assert decode(b"L") == [RIGHT]


def test_decode_quit():
    assert decode(b"q") == [QUIT]
    assert decode(b"Q") == [QUIT]
    assert decode(b"\x03") == [QUIT]


def test_decode_digits_and_tab():
    assert decode(b"1") == [TAB1]
    assert decode(b"2") == [TAB2]
    assert decode(b"3") == [TAB3]
    assert decode(b"\t") == [CYCLE]


def test_decode_chunk_multiple_keys():
    # right, right, space (other), quit
    assert decode(b"\x1b[C\x1b[C q") == [RIGHT, RIGHT, OTHER, QUIT]


def test_decode_lone_esc_no_crash():
    assert decode(b"\x1b") == [OTHER]
    assert decode(b"") == []
    assert decode(b"\x1b[") == [OTHER, OTHER]  # incomplete CSI: esc + '['


def test_decode_windows_arrows():
    assert decode(b"\xe0K") == [LEFT]
    assert decode(b"\xe0M") == [RIGHT]


def test_reader_none_when_not_tty(monkeypatch):
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert reader() is None
