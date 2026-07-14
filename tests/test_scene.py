"""Pure tests for the fixed-region scene primitives (plan 034)."""

import os

from token_oracle.core.contracts import Forecast
from token_oracle.dashboard.app import (
    ACTIVITY_H,
    ALERT_H,
    FOOTER_H,
    HEADER_H,
    panel_height,
    render_frame,
    render_frame_str,
)
from token_oracle.dashboard.scene import Region, Scene, strip_ansi, truncate_display, visible_len
from token_oracle.live.contract import STATE_OK
from token_oracle.live.overlay import LiveCell


def test_scene_pads_short_fill():
    def short():
        return ["only one"]

    reg = Region("test", 3, short)
    sc = Scene([reg])
    out = sc.render(80)
    assert len(out) == 3
    assert out[0] == "only one"
    assert out[1] == ""
    assert out[2] == ""


def test_scene_truncates_tall_fill():
    def tall():
        return [f"line{i}" for i in range(5)]

    reg = Region("test", 3, tall)
    sc = Scene([reg])
    out = sc.render(80)
    assert len(out) == 3
    assert out == ["line0", "line1", "line2"]


def test_visible_len_and_strip_and_truncate():
    assert visible_len("\033[1m42%\033[0m") == 3
    assert strip_ansi("\033[38;5;141mfoo\033[0m") == "foo"
    # over-width keeps ANSI styling + appends reset (color-safe, cell-aware trunc)
    long = "\033[1m" + "X" * 100 + "\033[0m"
    reg = Region("w", 1, lambda: [long])
    sc = Scene([reg])
    out = sc.render(10)
    assert len(out) == 1
    assert strip_ansi(out[0]) == "X" * 10
    assert out[0].endswith("\033[0m")
    assert "\033[1m" in out[0]  # opener preserved, then reset appended


def test_height_invariance_same_config_shape():
    """Core regression guard: identical window count + same regions => same output line count
    regardless of idle/active/live/present data. This is the load-bearing invariant.
    """
    base_fs = [
        Forecast("5h", 0, 220000, 0.0, None, 18000.0, True),
        Forecast("weekly", 0, 8000000, 0.0, None, 600000.0, True),
    ]
    active_fs = [
        Forecast("5h", 12000, 220000, 42.0, None, 3600.0, False),
        Forecast("weekly", 5000000, 8000000, 62.0, None, 400000.0, False),
    ]
    cells_live = {
        ("claude", "5h"): LiveCell(pct=5.0, state=STATE_OK, age_secs=10.0, extractor="claude.row"),
        ("claude", "weekly"): LiveCell(
            pct=38.0, state=STATE_OK, age_secs=42.0, extractor="claude.row"
        ),
    }
    empty_log = []
    probe_log = ["probing claude.ai…", "row 42s", "done"]

    # shape from groups determines panel region height (config shape proxy)
    h_idle = len(render_frame_str(base_fs, now=100000.0, color=False).splitlines())
    h_active = len(render_frame_str(active_fs, now=100000.0, color=False).splitlines())
    h_live = len(
        render_frame_str(active_fs, now=100000.0, color=False, cells=cells_live).splitlines()
    )
    h_empty_probe = len(
        render_frame_str(active_fs, now=100000.0, color=False, probe_log=empty_log).splitlines()
    )
    h_with_probe = len(
        render_frame_str(active_fs, now=100000.0, color=False, probe_log=probe_log).splitlines()
    )

    # all must be identical for this shape (2 windows, 1 profile)
    assert h_idle == h_active == h_live == h_empty_probe == h_with_probe

    # also assert the declared region math matches (header+alert+panels+act+foot)
    expected = HEADER_H + ALERT_H + panel_height({"default": base_fs}) + ACTIVITY_H + FOOTER_H
    assert h_idle == expected


def test_height_ladder_never_overflows_terminal():
    """The dash must fit any terminal height — the whole point of the ladder."""
    fs = [
        Forecast("5h", 12000, 220000, 42.0, None, 3600.0, False, profile="claude"),
        Forecast("weekly", 5000000, 8000000, 62.0, None, 400000.0, False, profile="claude"),
        Forecast("weekly", 2000000, 100000000, 20.0, None, 400000.0, False, profile="grok"),
    ]
    for h in range(2, 45):
        size = os.terminal_size((80, h))
        frame = render_frame(fs, now=100000.0, color=False, size=size)
        assert len(frame) <= h, f"height {h}: rendered {len(frame)} lines (overflow)"
        # every line also fits the width
        assert all(visible_len(ln) <= 80 for ln in frame)


def test_height_ladder_tiny_is_header_only():
    fs = [Forecast("weekly", 5000000, 8000000, 62.0, None, 400000.0, False, profile="claude")]
    size = os.terminal_size((80, 3))
    frame = render_frame(fs, now=100000.0, color=False, size=size)
    assert len(frame) == HEADER_H  # title + summary chip only


def test_size_none_is_full_layout_unchanged():
    """size=None (tests / non-interactive) must keep the original FULL frame."""
    fs = [
        Forecast("5h", 12000, 220000, 42.0, None, 3600.0, False),
        Forecast("weekly", 5000000, 8000000, 62.0, None, 400000.0, False),
    ]
    full = len(render_frame(fs, now=100000.0, color=False))
    expected = HEADER_H + ALERT_H + panel_height({"default": fs}) + ACTIVITY_H + FOOTER_H
    assert full == expected


def test_truncate_display_keeps_color_and_fits():
    """truncate_display (new) returns short strings unchanged; over-width ones
    are cell-width <= target, keep SGR openers, and end with reset."""
    from token_oracle.cli.colors import display_width as dw

    short = "\033[1m42%\033[0m"
    assert truncate_display(short, 10) == short
    assert dw(truncate_display(short, 10)) == 3

    long = "\033[1;31m" + "Z" * 50 + "\033[0m"
    t = truncate_display(long, 8)
    assert dw(t) <= 8
    assert t.endswith("\033[0m")
    assert "\033[1;31m" in t  # style kept
    # round trip strip gets the visible prefix
    assert strip_ansi(t) == "Z" * 8


def test_painter_erases_below_when_frame_shrinks(monkeypatch):
    """Tab switch Past(tall) → Present(short) must not leave ghost lines.

    Root cause: paint() only did per-line \\033[K and assumed fixed height
    (plan 034). Tabs produce variable height (past 40+ vs present ~25 vs
    future ~20); without erase-below, leftover past rows bleed into present.
    """
    import io
    import sys

    from token_oracle.dashboard.scene import Painter

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    # avoid real terminal size / alt-screen side effects
    monkeypatch.setattr(
        "token_oracle.dashboard.scene.shutil.get_terminal_size",
        lambda fallback=(80, 24): type("S", (), {"columns": 80, "lines": 40})(),
    )

    p = Painter()
    p._entered = False  # paint still works without alt screen
    p._prev_size = (80, 40)

    p.paint(["PAST1", "PAST2", "PAST3", "PAST4", "PAST5"])
    first = buf.getvalue()
    buf.seek(0)
    buf.truncate(0)

    p.paint(["NOW1", "NOW2"])  # shorter frame — must clear leftover PAST3..5
    second = buf.getvalue()

    # Erase-in-display from cursor (CSI J / CSI 0 J) clears rows below the new frame
    assert "\033[J" in second or "\033[0J" in second, (
        f"shorter paint must erase below; got {second!r}"
    )
    # Height change → full clear so old+new rows never mash for one frame
    assert "\033[2J" in second, f"shorter paint must full-clear on height change; got {second!r}"
    # Still homes cursor and clears EOL on written lines
    assert "\033[H" in second
    assert "NOW1" in second and "NOW2" in second
    assert "PAST5" in first
