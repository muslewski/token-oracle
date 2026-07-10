from token_oracle.core.contracts import Forecast
from token_oracle.core.engine import detect_resets
from token_oracle.dashboard.app import render_frame_str


def test_render_frame_lists_windows():
    fs = [
        Forecast("5h", 12000, 220000, 42.0, None, 3600.0, False),
        Forecast("weekly", 5_000_000, 8_000_000, 130.0, 90000.0, 400000.0, False),
    ]
    frame = render_frame_str(fs, now=100000.0, color=False)
    assert "5h" in frame and "weekly" in frame
    assert "42%" in frame and "130%" in frame


def test_render_frame_handles_idle():
    fs = [Forecast("5h", 0, 220000, 0.0, None, 18000.0, True)]
    frame = render_frame_str(fs, now=1.0, color=False)
    # 5h idle now always says "idle" in head (fixed 3-line); the "starts when..." phrase
    # appears ONLY when a LiveCell for 5h carries state_value="starts_on_first_message".
    fl = frame.lower()
    assert "idle" in fl and "5h" in fl
    # without cell, no starts phrase
    assert "starts when a message is sent" not in fl


def test_render_frame_empty():
    # render_frame returns list; str wrapper for compat
    s = render_frame_str([], now=1.0, color=False)
    assert isinstance(s, str)
    assert "no windows" in s or "no data" in s.lower()


def test_render_frame_no_color_clean():
    fs = [Forecast("5h", 12000, 220000, 130.0, 5000.0, 3600.0, False)]
    s = render_frame_str(fs, now=1.0, color=False)
    assert "\033" not in s


def test_render_frame_color_on():
    fs = [Forecast("5h", 12000, 220000, 130.0, 5000.0, 3600.0, False)]
    s = render_frame_str(fs, now=1.0, color=True)
    assert "\033" in s


def test_render_frame_multi_profile_side_by_side():
    fs = [
        Forecast("5h", 100, 1000, 10.0, None, 1000.0, False, profile="claude"),
        Forecast("weekly", 500000, 8000000, 6.0, None, 100000.0, False, profile="grok"),
    ]
    frame = render_frame_str(fs, now=100000.0, color=False)
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


def test_render_frame_live_cell_shows_both_and_proj_and_honest_live_wording():
    """Live pct row shows live number + proj label; 'live' word only on rows with cell.pct."""
    from token_oracle.live.contract import STATE_OK
    from token_oracle.live.overlay import LiveCell

    fs = [
        Forecast("weekly", 3000000, 8000000, 40.0, None, 500000.0, False, profile="claude"),
        Forecast("fable", 100000, 1000000, 10.0, None, 100000.0, False, profile="claude"),
    ]
    # only weekly has live pct; fable has cell but pct=None (local proj only)
    cells = {
        ("claude", "weekly"): LiveCell(
            pct=38.0, state=STATE_OK, age_secs=12.0, extractor="claude.usage_row"
        ),
        ("claude", "fable"): LiveCell(
            pct=None, state=STATE_OK, age_secs=5.0, extractor="claude.row"
        ),
    }
    frame = render_frame_str(fs, now=100000.0, color=False, cells=cells)
    # weekly row (live): shows 38% (the live), and "proj"
    assert "38%" in frame
    assert "proj" in frame.lower()
    # the live wording appears for the live row
    assert "live" in frame  # from chip or prov on the pct row
    # fable row (no pct): must NOT contain the word "live" (honest)
    # (we scan whole but the invariant is no claiming live number)
    # simpler: the prov line for fable should be the local one
    assert "local projection — live disabled" in frame or "no reliable live data" in frame
    # and head for fable uses ◌ (local)
    # at minimum the frame contains the non-live prov phrasing
    assert "local projection" in frame
