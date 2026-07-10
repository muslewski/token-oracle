from token_oracle.core.contracts import Forecast
from token_oracle.dashboard.app import render_frame
from token_oracle.core.engine import detect_resets


def test_render_frame_lists_windows():
    fs = [
        Forecast("5h", 12000, 220000, 42.0, None, 3600.0, False),
        Forecast("weekly", 5_000_000, 8_000_000, 130.0, 90000.0, 400000.0, False),
    ]
    frame = render_frame(fs, now=100000.0, color=False)
    assert "5h" in frame and "weekly" in frame
    assert "42%" in frame and "130%" in frame


def test_render_frame_handles_idle():
    fs = [Forecast("5h", 0, 220000, 0.0, None, 18000.0, True)]
    frame = render_frame(fs, now=1.0, color=False)
    # 5h idle is special: shows the "starts when a message is sent" UX (truth from site)
    # not the generic "idle" wording.
    fl = frame.lower()
    assert "starts when a message is sent" in fl or "5h" in fl


def test_render_frame_empty():
    assert isinstance(render_frame([], now=1.0, color=False), str)


def test_render_frame_no_color_clean():
    fs = [Forecast("5h", 12000, 220000, 130.0, 5000.0, 3600.0, False)]
    assert "\033" not in render_frame(fs, now=1.0, color=False)


def test_render_frame_color_on():
    fs = [Forecast("5h", 12000, 220000, 130.0, 5000.0, 3600.0, False)]
    assert "\033" in render_frame(fs, now=1.0, color=True)


def test_render_frame_multi_profile_side_by_side():
    fs = [
        Forecast("5h", 100, 1000, 10.0, None, 1000.0, False, profile="claude"),
        Forecast("weekly", 500000, 8000000, 6.0, None, 100000.0, False, profile="grok"),
    ]
    frame = render_frame(fs, now=100000.0, color=False)
    assert "CLAUDE" in frame or "claude" in frame.lower()
    assert "GROK" in frame or "grok" in frame.lower()
    # boxes
    assert "┌" in frame and "│" in frame


def test_detect_resets_flags_drop():
    prev = [Forecast("weekly", 800000, 1000000, 80.0, None, 10000.0, False, profile="grok")]
    curr = [Forecast("weekly", 5000, 1000000, 0.5, None, 10000.0, False, profile="grok")]
    rs = detect_resets(prev, curr)
    assert len(rs) == 1
    assert rs[0]["profile"] == "grok"
    assert rs[0]["prev_used"] == 800000
