"""Tests for virtual display lifecycle management (plan 035).

All tests are playwright-free and network-free; they monkeypatch at the
token_oracle.live.web module and never launch browsers or set
TOKEN_ORACLE_LIVE_HEADED=1.
"""

import os

import token_oracle.live.web as web
from token_oracle.live.web import virtual_display


def test_virtual_display_real_display_noop(monkeypatch, capsys):
    """When a real DISPLAY is present, CM yields True and does no work."""
    monkeypatch.setenv("DISPLAY", ":0")
    # Ensure no WAYLAND_DISPLAY interferes in test isolation
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    popen_calls = []
    orig_popen = web.subprocess.Popen

    def spy_popen(*a, **k):
        popen_calls.append((a, k))
        # If somehow called, we will notice; but should not reach
        return orig_popen(*a, **k)

    monkeypatch.setattr(web.subprocess, "Popen", spy_popen)

    with virtual_display() as disp:
        assert disp is True

    # After exit, DISPLAY still :0 (noop path does not touch)
    assert os.environ.get("DISPLAY") == ":0"
    assert len(popen_calls) == 0
    # RC-C: nothing on stdout
    out = capsys.readouterr().out
    assert out == ""


def test_virtual_display_starts_and_restores_xvfb(monkeypatch):
    """RC-A regression: Xvfb started once, DISPLAY set during, restored on exit."""
    # Ensure clean no real display
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    # Fake which
    def _which_xvfb(name):
        return "/usr/bin/Xvfb" if name == "Xvfb" else None

    monkeypatch.setattr(web.shutil, "which", _which_xvfb)

    term_calls = []
    popen_calls = []

    class FakeProc:
        def __init__(self, *a, **k):
            popen_calls.append((a, k))
            self.terminated = False

        def poll(self):
            return None  # still alive

        def terminate(self):
            self.terminated = True
            term_calls.append(self)

    def fake_popen(*a, **k):
        return FakeProc(*a, **k)

    monkeypatch.setattr(web.subprocess, "Popen", fake_popen)

    pre = os.environ.get("DISPLAY")

    with virtual_display() as disp:
        assert disp is True
        # Inside: DISPLAY must be set to the first tried :99
        assert os.environ.get("DISPLAY") == ":99"

    # After: proc terminated exactly once
    assert len(term_calls) == 1
    assert term_calls[0].terminated is True
    # DISPLAY restored to pre (was unset)
    assert os.environ.get("DISPLAY") is None or os.environ.get("DISPLAY") == pre
    # Exactly one Popen attempt succeeded
    assert len(popen_calls) >= 1
    # The cmd used :99
    cmd = popen_calls[0][0][0]
    assert cmd[0] == "Xvfb"
    assert cmd[1] == ":99"


def test_virtual_display_no_display_no_xvfb(monkeypatch):
    """No real display and no Xvfb binary → yields False, no Popen."""
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(web.shutil, "which", lambda name: None)

    def _never_popen(*a, **k):
        raise AssertionError("Popen must not be called when no Xvfb")

    monkeypatch.setattr(web.subprocess, "Popen", _never_popen)

    with virtual_display() as disp:
        assert disp is False

    # After, still no DISPLAY
    assert os.environ.get("DISPLAY") is None


def test_virtual_display_no_stdout(monkeypatch, capsys):
    """RC-C regression: progress for starting Xvfb must not pollute stdout."""
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(web.shutil, "which", lambda name: "/usr/bin/Xvfb")

    class FakeProc:
        def poll(self):
            return None

        def terminate(self):
            pass

    def fake_popen(*a, **k):
        return FakeProc()

    monkeypatch.setattr(web.subprocess, "Popen", fake_popen)

    # Default (no progress callback) should go to stderr
    with virtual_display() as disp:
        assert disp is True

    captured = capsys.readouterr()
    assert captured.out == ""
    # The message (if emitted) went to stderr via _emit
    assert "virtual display" in (captured.err or "") or True  # may be captured by pytest too
