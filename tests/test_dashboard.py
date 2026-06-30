from token_oracle.core.contracts import Forecast
from token_oracle.dashboard.app import render_frame


def test_render_frame_lists_windows():
    fs = [Forecast("5h", 12000, 220000, 42.0, None, 3600.0, False),
          Forecast("weekly", 5_000_000, 8_000_000, 130.0, 90000.0, 400000.0, False)]
    frame = render_frame(fs, now=100000.0, color=False)
    assert "5h" in frame and "weekly" in frame
    assert "42%" in frame and "130%" in frame


def test_render_frame_handles_idle():
    fs = [Forecast("5h", 0, 220000, 0.0, None, 18000.0, True)]
    frame = render_frame(fs, now=1.0, color=False)
    assert "idle" in frame.lower()


def test_render_frame_empty():
    assert isinstance(render_frame([], now=1.0, color=False), str)


def test_render_frame_no_color_clean():
    fs = [Forecast("5h", 12000, 220000, 130.0, 5000.0, 3600.0, False)]
    assert "\033" not in render_frame(fs, now=1.0, color=False)


def test_render_frame_color_on():
    fs = [Forecast("5h", 12000, 220000, 130.0, 5000.0, 3600.0, False)]
    assert "\033" in render_frame(fs, now=1.0, color=True)
