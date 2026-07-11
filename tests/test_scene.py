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
from token_oracle.dashboard.scene import Region, Scene, strip_ansi, visible_len
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
    # over-width drops styling and cuts plainly
    long = "\033[1m" + "X" * 100 + "\033[0m"
    reg = Region("w", 1, lambda: [long])
    sc = Scene([reg])
    out = sc.render(10)
    assert len(out) == 1
    assert len(out[0]) == 10  # plain cut, no escapes left
    assert "\033" not in out[0]


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
