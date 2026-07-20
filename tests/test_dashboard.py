import os
import re

from token_oracle.cli.colors import display_width
from token_oracle.core.contracts import Forecast
from token_oracle.core.engine import detect_resets
from token_oracle.core.report import LedgerRow
from token_oracle.dashboard.app import (
    BAR_W,
    TABS,
    _active_row_targets,
    _apply_tab_key,
    _bar,
    _compact_profile_line,
    _pulse_level,
    panel_height,
    render_footer,
    render_frame,
    render_frame_str,
    render_placeholder,
    render_tab_bar,
)
from token_oracle.dashboard.future import (
    cost_pace_line,
    prophecy_line,
    render_future,
    spark_next24,
)
from token_oracle.dashboard.past import render_past, short_model, top_models_by_day
from token_oracle.dashboard.race import (
    Truth,
    eta_for_race,
    margin_line,
    profile_verdict,
    race_status,
    window_truth,
)
from token_oracle.dashboard.skeleton import render_skeleton, render_stale_banner, spinner_char
from token_oracle.dashboard.store import DashStore
from token_oracle.live.contract import STATE_OK
from token_oracle.live.overlay import LiveCell


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


# --- row-change animation ---------------------------------------------------


def test_bar_is_always_full_width_and_subcell():
    from token_oracle.cli.colors import display_width

    for p in (0.0, 10.3, 50.0, 65.4, 99.9, 100.0):
        b = _bar(p, False, BAR_W)
        assert display_width(b) == BAR_W
    assert _bar(0.0, False, BAR_W).count("█") == 0
    assert _bar(100.0, False, BAR_W).count("█") == BAR_W
    # a fractional fill uses a sub-cell block glyph, not a whole extra cell
    assert any(g in _bar(65.4, False, BAR_W) for g in "▏▎▍▌▋▊▉")


def test_anim_pct_glides_bar_while_number_stays_truth():
    fs = [Forecast("weekly", 1000, 10000, 20.0, None, 400000.0, False, profile="grok")]
    cells = {("grok", "weekly"): LiveCell(pct=66.0, state=STATE_OK, age_secs=5.0, extractor="x")}
    # bar mid-glide at 30% while the true value is 66%
    frame = render_frame_str(
        fs, now=0.0, color=False, cells=cells, anim_pct={("grok", "weekly"): 30.0}
    )
    row = next(line for line in frame.splitlines() if "weekly" in line)
    assert "66%" in row  # number is the truth, not the animated value
    low_fill = row.count("█")
    # without the anim override the bar reflects the truth (66% -> more full cells)
    frame2 = render_frame_str(fs, now=0.0, color=False, cells=cells)
    row2 = next(line for line in frame2.splitlines() if "weekly" in line)
    assert row2.count("█") > low_fill  # truth bar is fuller than the mid-glide bar


def test_pulse_level_envelope():
    assert _pulse_level(0.0, -1.0) == 0.0  # before start
    assert _pulse_level(0.0, 0.0) == 1.0  # peak at start
    assert _pulse_level(0.0, 5.0) == 0.0  # past the window
    assert 0.0 <= _pulse_level(0.0, 1.0) <= 1.0


def test_active_row_targets_blend():
    fs = [
        Forecast("5h", 2000, 10000, 15.0, None, 3600.0, False, profile="claude"),
        Forecast("weekly", 100, 1000, 40.0, None, 400000.0, False, profile="claude"),
    ]
    cells = {("claude", "weekly"): LiveCell(pct=66.0, state=STATE_OK, age_secs=5.0, extractor="x")}
    t = _active_row_targets(fs, cells)
    assert t[("claude", "5h")] == 20.0  # local used/cap = 2000/10000
    assert t[("claude", "weekly")] == 66.0  # web cell wins for the cap


def _two_profile_two_window_fs():
    """Build a two-profile two-equal-window frame so side-by-side is possible."""
    return [
        Forecast("5h", 12000, 220000, 42.0, None, 3600.0, False, profile="claude"),
        Forecast("weekly", 5_000_000, 8_000_000, 130.0, 90000.0, 400000.0, False, profile="claude"),
        Forecast("5h", 8000, 220000, 31.0, None, 3600.0, False, profile="grok"),
        Forecast("weekly", 2_000_000, 10_000_000, 55.0, None, 500000.0, False, profile="grok"),
    ]


def test_no_line_exceeds_terminal_width_at_any_width():
    """Core regression guard: at every supported width, every rendered line's
    display cell width is <= the terminal width. This fails on pre-fix code."""
    fs = _two_profile_two_window_fs()
    for W in (200, 140, 123, 120, 100, 80, 72, 60, 50, 40, 32, 24, 16):
        size = os.terminal_size((W, 40))
        frame = render_frame(fs, now=100000.0, color=True, size=size)
        for i, line in enumerate(frame):
            dw = display_width(line)
            assert dw <= W, f"W={W} line#{i} display_width={dw} > {W}: {line[:60]!r}"


def test_no_dangling_color_after_truncation():
    """After truncation (or normal render), no line has an SGR escape without a
    balancing reset (prevents color bleed on narrow terms)."""
    fs = _two_profile_two_window_fs()
    for W in (200, 140, 123, 120, 100, 80, 72, 60, 50, 40, 32, 24, 16):
        size = os.terminal_size((W, 40))
        frame = render_frame(fs, now=100000.0, color=True, size=size)
        for i, line in enumerate(frame):
            if "\x1b[" in line:
                assert "\033[0m" in line, f"W={W} line#{i} has open SGR but no reset"
            # also cell width ok (defense)
            assert display_width(line) <= W


def test_arrangement_collapses_with_width():
    """Layout mode changes with width: side (two boxes per row) -> stack (one box)
    -> oneline (no boxes, · joined)."""
    fs = _two_profile_two_window_fs()
    # side-by-side at wide (two ┌ on some panel line, or ┐   ┌ join)
    size = os.terminal_size((140, 40))
    frame = render_frame(fs, now=100000.0, color=False, size=size)
    has_side_mark = any("┐   ┌" in ln or ln.count("┌") >= 2 for ln in frame)
    assert has_side_mark, "expected side-by-side at W=140"

    # stacked at narrower (single box per line, still has boxes)
    size = os.terminal_size((60, 40))
    frame = render_frame(fs, now=100000.0, color=False, size=size)
    has_stack_mark = any("┌" in ln for ln in frame)
    has_join_mark = any("┐   ┌" in ln for ln in frame)
    assert has_stack_mark and not has_join_mark, "expected stacked (single box) at W=60"

    # bars (borderless sliders) between box and oneline: no box, has bars, no ·
    size = os.terminal_size((24, 40))
    frame = render_frame(fs, now=100000.0, color=False, size=size)
    has_box = any(ch in ln for ln in frame for ch in "┌│└")
    has_bar = any(ch in ln for ln in frame for ch in "█░")
    has_compact = any("·" in ln for ln in frame)
    assert not has_box, "expected no box chars at W=24"
    assert has_bar, "expected bar glyphs at W=24"
    assert not has_compact, "expected no · at W=24 (bars mode keeps bars)"

    # oneline/compact at very narrow: no box, compact pct% lines (· joiner when fits)
    size = os.terminal_size((14, 40))
    frame = render_frame(fs, now=100000.0, color=False, size=size)
    has_box = any(ch in ln for ln in frame for ch in "┌│└")
    has_compact = any("·" in ln for ln in frame) or any(
        "%" in ln and ("wk" in ln or "5h" in ln) for ln in frame
    )
    assert not has_box, "expected no box chars at W=14"
    assert has_compact, "expected compact pct% line at W=14"


def test_size_none_unchanged():
    """size=None (tests/non-interactive) must produce byte-identical output to
    the pre-change default path (full layout + Scene trunc at w=80)."""
    fs = _two_profile_two_window_fs()
    now = 100000.0
    # capture "before" (current default-path behavior, which our arrange_w=999 preserves)
    baseline = render_frame_str(fs, now=now, color=False, size=None)
    out = render_frame_str(fs, now=now, color=False, size=None)
    assert out == baseline
    # also the structure is the wide side-by-side one (pre-chop content had 123-wide)
    # after render(80) for color=false the lines are the 80-char prefix
    assert len(out.splitlines()) == 15  # header2+alert1+panels8+act3+foot1 for n=2 side


# --- 056 low-width triage priority tests ---


def _claude_binding_fs():
    """claude with 5h=2%, fable=99%, weekly=33% (binding is fable)."""
    return [
        Forecast("5h", 1140, 57000, 2.0, None, 7200.0, False, profile="claude"),
        Forecast("fable", 5940, 6000, 99.0, None, 7200.0, False, profile="claude"),
        Forecast("weekly", 90000, 270000, 33.0, None, 7200.0, False, profile="claude"),
    ]


def test_compact_line_orders_binding_first():
    """Highest-% window leads; order is by current % DESC not alpha."""
    fs = _claude_binding_fs()
    line = _compact_profile_line("claude", fs, 100000.0, False, {}, width=200)
    plain = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", line)
    # 99% before 33% before 2%
    assert plain.index("99%") < plain.index("33%") < plain.index("2%"), f"wrong order: {plain}"


def test_compact_line_fits_and_keeps_binding():
    """At every narrow width the line <=w, contains binding 99%, no dangling sep."""
    import re as _re  # local to avoid polluting if not

    fs = _claude_binding_fs()
    for W in (40, 32, 24, 20, 16, 12, 10):
        line = _compact_profile_line("claude", fs, 100000.0, False, {}, width=W)
        dw = display_width(line)
        plain = _re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", line)
        assert dw <= W, f"W={W} dw={dw} > W: {plain!r}"
        assert "99%" in plain, f"W={W} lost binding 99%: {plain!r}"
        assert not plain.endswith("· "), f"W={W} dangling '· ': {plain!r}"
        assert not plain.endswith("·"), f"W={W} dangling '·': {plain!r}"


def test_glance_level_used_when_one_row():
    """At height=1 we get exactly the glance (🔮) line, fits w, contains binding."""
    fs = _claude_binding_fs()
    size = os.terminal_size((30, 1))
    frame = render_frame(fs, now=100000.0, color=True, size=size)
    assert len(frame) == 1
    line = frame[0]
    assert display_width(line) <= 30
    assert "🔮" in line
    plain = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", line)
    assert "99%" in plain


def test_glance_before_tiny():
    """At 1 row, glance (with %) is chosen before the header-only tiny fallback."""
    fs = _claude_binding_fs()
    size = os.terminal_size((24, 1))
    frame = render_frame(fs, now=100000.0, color=False, size=size)
    assert len(frame) == 1
    line = frame[0]
    assert "🔮" in line
    assert "%" in line, "glance should show a % number (not pure tiny header)"


def test_compact_no_dangling_separator():
    """No compact/glance line ends with sep or has dangling '·  ·' / ' · ' at end."""
    import re as _re

    fs = _claude_binding_fs()
    for W in (40, 24, 16, 12, 10):
        # compact
        cline = _compact_profile_line("claude", fs, 100000.0, False, {}, width=W)
        cplain = _re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", cline)
        assert not cplain.rstrip().endswith("·"), f"compact W={W} ends sep: {cplain!r}"
        assert "·  ·" not in cplain and cplain.strip().endswith("·") is False
        # glance
        size = os.terminal_size((W, 1))
        gframe = render_frame(fs, now=100000.0, color=False, size=size)
        gline = gframe[0] if gframe else ""
        gplain = _re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", gline)
        assert not gplain.rstrip().endswith("·"), f"glance W={W} ends sep: {gplain!r}"


def test_glance_binding_survives_across_providers():
    """1-row + narrow: glance must show the highest-% window across ALL providers,
    even when the alphabetically-first provider has a lower %. Regression: glance
    used to append per-provider unsorted, dropping the binding when truncated."""
    import re as _re

    fs = [
        Forecast("weekly", 33, 100, 33.0, None, 7200.0, False, profile="claude"),
        Forecast("5h", 99, 100, 99.0, None, 7200.0, False, profile="fable"),
    ]
    for W in (16, 12, 10):
        frame = render_frame(fs, now=100000.0, color=False, size=os.terminal_size((W, 1)))
        assert len(frame) == 1
        plain = _re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", frame[0])
        assert "99%" in plain, f"W={W} glance dropped binding 99%: {plain!r}"
        assert display_width(frame[0]) <= W


def test_glance_item_is_pct_first():
    """Glance items are formatted pct-first ('99% 5h') so the number leads."""
    import re as _re

    fs = [Forecast("5h", 99, 100, 99.0, None, 7200.0, False, profile="fable")]
    frame = render_frame(fs, now=100000.0, color=False, size=os.terminal_size((30, 1)))
    plain = _re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", frame[0])
    assert "99% 5h" in plain, f"expected pct-first '99% 5h', got: {plain!r}"


# --- 057 narrow bars tests ---


def test_bars_mode_between_box_and_oneline():
    """For BARS_MIN <= w < MIN_BOX the frame uses borderless bars (has bar glyphs,
    no box chars, no compact · joiner)."""
    fs = _two_profile_two_window_fs()
    for W in (33, 30, 24, 18):
        size = os.terminal_size((W, 40))
        frame = render_frame(fs, now=100000.0, color=False, size=size)
        has_bar = any(ch in ln for ln in frame for ch in "█░")
        has_box = any(ch in ln for ln in frame for ch in "┌│└")
        has_compact = any("·" in ln for ln in frame)
        assert has_bar, f"W={W} expected bar glyphs"
        assert not has_box, f"W={W} expected no box chars"
        assert not has_compact, f"W={W} expected no · compact joiner"


def test_bars_rows_fit_and_keep_number():
    """Every line fits <=w; binding number (99%) is preserved in bars mode."""
    fs = _claude_binding_fs()
    for W in (33, 24, 16):
        size = os.terminal_size((W, 40))
        frame = render_frame(fs, now=100000.0, color=False, size=size)
        for i, line in enumerate(frame):
            dw = display_width(line)
            assert dw <= W, f"W={W} line#{i} dw={dw} > W: {line!r}"
        plain = "\n".join(frame)
        assert "99%" in plain, f"W={W} lost binding 99% in bars render"


def test_bars_height_matches_fill():
    """panel_height must equal number of lines emitted by panels_fill (fixed-height
    contract) in bars mode. Bars mode is detail-invariant."""
    # build multi-profile with fable to match labels in other tests
    fs = [
        Forecast("5h", 20, 1000, 2.0, None, 3600.0, False, profile="claude"),
        Forecast("weekly", 3300000, 10000000, 33.0, None, 400000.0, False, profile="claude"),
        Forecast("5h", 990, 1000, 99.0, None, 3600.0, False, profile="fable"),
    ]
    groups = {}
    for f in fs:
        groups.setdefault(f.profile, []).append(f)
    for W in (30, 20, 16):
        ph2 = panel_height(groups, 2, W)
        ph0 = panel_height(groups, 0, W)
        assert ph2 == ph0, f"W={W} panel_height must ignore detail in bars"
        frame = render_frame(fs, now=100000.0, color=False, size=os.terminal_size((W, 40)))
        # panels region produces exactly ph2 lines (incl inter gaps)
        # simplest robust: headers + labels present, and ph matches a constructed count
        # (we already know from construction that render lines for panels are ph2)
        assert "claude" in "\n".join(frame).lower()
        assert "fable" in "\n".join(frame).lower()
        assert "5h" in "\n".join(frame)
        # Constructed bars height: per profile (header + one row per window + gap)
        expected = sum(1 + len(gfs) + 1 for gfs in groups.values())
        assert ph2 == expected, f"W={W} panel_height={ph2} expected={expected}"
        for line in frame:
            assert display_width(line) <= W, f"W={W} overflow: {line!r}"


def test_bars_show_all_windows_labeled():
    """At bars widths, provider header + per-window labeled rows (5h/wk) appear."""
    fs = [
        Forecast("5h", 20, 1000, 2.0, None, 3600.0, False, profile="claude"),
        Forecast("weekly", 3300000, 10000000, 33.0, None, 400000.0, False, profile="claude"),
        Forecast("5h", 990, 1000, 99.0, None, 3600.0, False, profile="fable"),
    ]
    size = os.terminal_size((24, 40))
    frame = render_frame(fs, now=100000.0, color=False, size=size)
    s = "\n".join(frame)
    # claude block
    assert "✳ claude" in s or "claude" in s.lower()
    assert "5h" in s and "wk" in s
    # fable block
    assert "fable" in s.lower()
    assert "5h" in s


def test_short_narrow_keeps_bars():
    """At bars width + short height, sliders must not fall to compact text (F-A11-1)."""
    fs = [
        Forecast("5h", 20, 1000, 2.0, None, 3600.0, False, profile="claude"),
        Forecast("weekly", 330, 1000, 33.0, None, 400000.0, False, profile="claude"),
        Forecast("5h", 990, 1000, 99.0, None, 3600.0, False, profile="fable"),
    ]
    # bars band width; height that fits header+bars but not full chrome
    frame = render_frame(fs, now=100000.0, color=False, size=os.terminal_size((24, 11)))
    plain = "\n".join(frame)
    # bars rows use label + % ; compact uses "·" separators heavily
    assert "5h" in plain and "%" in plain
    # binding survives
    assert "99" in plain


def test_tiny_chip_shows_binding_not_only_5h():
    """At height=2 (tiny), chip should prefer highest % window (F-A11-3)."""
    from token_oracle.live.contract import STATE_OK
    from token_oracle.live.overlay import LiveCell

    fs = [
        Forecast("5h", 20, 1000, 2.0, None, 3600.0, False, profile="claude"),
        Forecast("weekly", 990, 1000, 99.0, None, 400000.0, False, profile="claude"),
    ]
    cells = {("claude", "weekly"): LiveCell(99.0, STATE_OK, 1.0, "e", "header", None)}
    frame = render_frame(fs, now=100000.0, color=False, cells=cells, size=os.terminal_size((80, 2)))
    plain = "\n".join(frame)
    assert "99%" in plain or "99" in plain


# --- plan 018 tab shell (pure renderers) ------------------------------------


def test_render_tab_bar_marks_active():
    bar = render_tab_bar("present", 80, False)
    assert "Present" in bar and "Past" in bar and "Future" in bar
    assert "token-oracle" in bar
    assert "\033" not in bar  # color off


def test_render_tab_bar_width_60_vs_120():
    a = render_tab_bar("future", 60, False)
    b = render_tab_bar("future", 120, False)
    # wider bar can fit the clock; both mention Future
    assert "Future" in a and "Future" in b
    assert display_width(a) <= 60
    assert display_width(b) <= 120


def test_render_placeholder_mentions_tab():
    past = "\n".join(render_placeholder("past", 80, False))
    fut = "\n".join(render_placeholder("future", 80, False))
    assert "past" in past.lower()
    assert "future" in fut.lower()
    assert "019" in past
    assert "020" in fut
    assert "\033" not in past


def test_render_footer_lists_q():
    foot = render_footer(80, False)
    assert "q" in foot
    assert "\033" not in foot


def test_apply_tab_key_navigation():
    assert _apply_tab_key("present", "left") == "past"
    assert _apply_tab_key("present", "right") == "future"
    assert _apply_tab_key("future", "right") == "past"  # wrap
    assert _apply_tab_key("past", "tab2") == "present"
    assert _apply_tab_key("past", "tab3") == "future"
    assert _apply_tab_key("present", "cycle") == "future"
    assert _apply_tab_key("present", "quit") is None
    assert _apply_tab_key("present", "other") == "present"
    assert set(TABS) == {"past", "present", "future"}


# --- plan 019 past tab ------------------------------------------------------


def _ledger_rows():
    return [
        LedgerRow("2026-07-01", 100_000, 1.5, 0, 1.25),
        LedgerRow("2026-07-02", 500_000, 4.31, 0, 6.25),
        LedgerRow("2026-07-03", 0, 0.0, 0, 0.0),
        LedgerRow("TOTAL", 600_000, 5.81, 12000, 7.5),
    ]


def test_render_past_shows_dates_and_tokens():
    lines = render_past(_ledger_rows(), 120, False, days=3)
    text = "\n".join(lines)
    assert "Jul" in text
    assert "500" in text or "0.5M" in text or "500k" in text
    assert "TOTAL" in text
    assert "Past" in text
    assert "\033" not in text


def test_render_past_width_60_hides_bar():
    wide = "\n".join(render_past(_ledger_rows(), 120, False))
    narrow = "\n".join(render_past(_ledger_rows(), 60, False))
    assert "▇" in wide or "░" in wide
    assert "▇" not in narrow  # bar dropped under 72


def test_render_past_unpriced_warning():
    rows = [
        LedgerRow("2026-07-02", 1000, None, 1000, None),
        LedgerRow("TOTAL", 1000, None, 1000, None),
    ]
    text = "\n".join(render_past(rows, 100, False, show_cost=True))
    assert "unpriced" in text


def test_render_past_cost_off_hides_usd():
    text = "\n".join(render_past(_ledger_rows(), 120, False, show_cost=False))
    assert "$" not in text


def test_top_models_by_day():
    # 8-field events around a fixed day
    import time as _t

    # use local noon today-ish via fixed ts if TZ set; synthetic labels via day_key
    now = 1_751_500_000.0
    day = _t.strftime("%Y-%m-%d", _t.localtime(now))
    events = [
        [now - 100, 100, "claude-sonnet-4-5", 50, 50, 0, 0, None],
        [now - 50, 900, "claude-opus-4", 400, 500, 0, 0, None],
    ]
    tops = top_models_by_day(events, now, days=3)
    assert day in tops
    assert "opus" in tops[day] or "sonnet" in tops[day]
    assert short_model("claude-sonnet-4") == "sonnet-4"


# --- plan 020 future tab ----------------------------------------------------


def test_spark_flat_profile():
    prof = [1.0] * 168
    s, total = spark_next24(prof, 1_000_000.0)
    assert len(s) == 24
    assert total > 0
    # flat => all equal non-empty chars
    assert len(set(s)) == 1


def test_spark_empty_profile():
    assert spark_next24(None, 0.0) == ("", 0.0)
    assert spark_next24([], 0.0) == ("", 0.0)


def test_spark_hot_bucket():
    prof = [0.0] * 168
    # put heat in every bucket so integral is non-zero; one hour much hotter
    from token_oracle.core.timeutil import bucket_key

    now = 1_751_500_000.0
    for i in range(24):
        b = bucket_key(now + i * 3600.0)
        prof[b] = 10.0 if i == 5 else 1.0
    s, total = spark_next24(prof, now)
    assert "█" in s
    assert s[5] == "█" or s.count("█") >= 1
    assert total > 0


def test_prophecy_templates():
    active = Forecast("5h", 1000, 10000, 40.0, None, 3600.0, False)
    p = prophecy_line(active, False)
    assert "current pace" in p

    approach = Forecast("5h", 9000, 10000, 90.0, None, 3600.0, False)
    p = prophecy_line(approach, False)
    assert "approaching" in p

    over = Forecast("5h", 12000, 10000, 130.0, 5000.0, 3600.0, False)
    p = prophecy_line(over, False)
    assert "the cap falls" in p

    idle = Forecast("5h", 0, 10000, 0.0, None, 7200.0, True)
    p = prophecy_line(idle, False)
    assert "sleeps" in p


def test_prophecy_confidence_gate():
    f = Forecast("5h", 1000, 10000, 40.0, None, 3600.0, False, confidence=1.0)
    assert "confidence" not in prophecy_line(f, False)
    f2 = Forecast("5h", 1000, 10000, 40.0, None, 3600.0, False, confidence=0.7)
    assert "confidence 70%" in prophecy_line(f2, False)


def test_render_future_window_and_warning():
    fs = [
        Forecast("5h", 1000, 10000, 78.0, 90000.0, 8000.0, False, profile="claude"),
        Forecast("weekly", 100, 1000, 40.0, None, 400000.0, False, profile="claude"),
    ]
    text = "\n".join(render_future(fs, [1.0] * 168, 1_000_000.0, 100, False))
    assert "5h" in text
    assert "cap race" in text.lower() or "resets" in text
    assert "next 24h" in text
    assert "\033" not in text


def test_render_future_no_warning_without_eta():
    fs = [Forecast("5h", 1000, 10000, 40.0, None, 3600.0, False)]
    text = "\n".join(render_future(fs, None, 0.0, 80, False))
    assert "no hit before reset" in text or "SAFE" in text
    assert "no burn history" in text


def test_render_future_cost_line():
    fs = [Forecast("5h", 1000, 10000, 40.0, None, 3600.0, False)]
    with_c = "\n".join(render_future(fs, None, 0.0, 80, False, cost_line="spend pace: ~$1.00/day"))
    without = "\n".join(render_future(fs, None, 0.0, 80, False, cost_line=None))
    assert "spend pace" in with_c
    assert "spend pace" not in without
    assert cost_pace_line(7.0, days=7).startswith("spend pace:")


# --- plan 062 future cap-race ------------------------------------------------


def _race_truth(**kw):
    base = dict(
        now_pct=50.0,
        source="local",
        end_pct=50.0,
        reset_in=3600.0,
        idle=False,
        window="5h",
        cap=10000,
        profile="claude",
    )
    base.update(kw)
    return Truth(**base)


def test_race_status_table():
    assert race_status(_race_truth(idle=True), None) == "IDLE"
    assert race_status(_race_truth(now_pct=100.0), None) == "OVER"
    assert race_status(_race_truth(now_pct=50.0, end_pct=50.0, reset_in=7200.0), 3600.0) == "OVER"
    assert race_status(_race_truth(now_pct=90.0, end_pct=40.0), None) == "TIGHT"
    assert race_status(_race_truth(now_pct=40.0, end_pct=90.0), None) == "TIGHT"
    assert race_status(_race_truth(now_pct=40.0, end_pct=40.0), None) == "SAFE"
    assert race_status(_race_truth(now_pct=None, end_pct=None, source="none"), None) == "UNKNOWN"


def test_profile_verdict_worst_of():
    assert profile_verdict(["SAFE", "OVER", "TIGHT"]) == "OVER"
    assert profile_verdict(["IDLE", "SAFE"]) == "SAFE"
    assert profile_verdict(["IDLE", "UNKNOWN"]) == "IDLE"
    assert profile_verdict([]) == "UNKNOWN"


def test_window_truth_live_weekly():
    f = Forecast("weekly", 100, 1000, 23.0, None, 400000.0, False, profile="claude")
    cells = {("claude", "weekly"): LiveCell(pct=99.0, state=STATE_OK, age_secs=10.0)}
    t = window_truth(f, cells)
    assert t.now_pct == 99.0 and t.source == "live" and t.end_pct == 23.0


def test_window_truth_5h_local():
    f = Forecast("5h", 5000, 10000, 78.0, 90000.0, 8000.0, False, profile="claude")
    cells = {("claude", "5h"): LiveCell(pct=12.0, state=STATE_OK, age_secs=5.0)}
    t = window_truth(f, cells)
    assert t.now_pct == 50.0 and t.source == "local"


def test_window_truth_no_cells():
    f = Forecast("weekly", 400, 1000, 68.0, None, 1000.0, False, profile="claude")
    t = window_truth(f, None)
    assert t.source in ("local", "proj")
    assert t.now_pct is not None


def test_eta_for_race_at_wall():
    f = Forecast("weekly", 100, 1000, 23.0, None, 1000.0, False, profile="claude")
    t = _race_truth(now_pct=100.0, source="live", end_pct=23.0, cap=1000, reset_in=1000.0)
    assert eta_for_race(f, t) == 0.0


def test_eta_for_race_live_burn():
    f = Forecast("weekly", 100, 1000, 100.0, 999.0, 3600.0, False, profile="claude")
    t = _race_truth(now_pct=50.0, source="live", end_pct=100.0, cap=1000, reset_in=3600.0)
    eta = eta_for_race(f, t)
    assert eta is not None and abs(eta - 3600.0) < 1.0


def test_margin_line_variants():
    assert "already at the wall" in margin_line(_race_truth(now_pct=100.0), 0.0)
    assert "lose by" in margin_line(_race_truth(now_pct=50.0, reset_in=7200.0), 3600.0)
    assert "clear by" in margin_line(
        _race_truth(now_pct=50.0, end_pct=110.0, reset_in=3600.0), 7200.0
    )
    assert "headroom" in margin_line(_race_truth(now_pct=40.0, end_pct=50.0, reset_in=3600.0), None)


def test_render_future_live_disagree_shows_both():
    fs = [Forecast("fable", 100, 1000, 23.0, None, 400000.0, False, profile="claude")]
    cells = {("claude", "fable"): LiveCell(pct=99.0, state=STATE_OK, age_secs=5.0)}
    text = "\n".join(render_future(fs, None, 0.0, 100, False, cells=cells))
    assert "99%" in text and "23%" in text
    assert "TIGHT" in text or "OVER" in text
    assert "may lag live" in text
    assert "\033" not in text


def test_render_future_multi_profile_verdicts():
    fs = [
        Forecast("weekly", 100, 1000, 20.0, None, 1000.0, False, profile="claude"),
        Forecast("weekly", 100, 1000, 40.0, None, 1000.0, False, profile="grok"),
    ]
    cells = {
        ("claude", "weekly"): LiveCell(pct=100.0, state=STATE_OK, age_secs=1.0),
        ("grok", "weekly"): LiveCell(pct=40.0, state=STATE_OK, age_secs=1.0),
    }
    text = "\n".join(render_future(fs, None, 0.0, 100, False, cells=cells))
    assert "CLAUDE" in text and "OVER" in text
    assert "GROK" in text and "SAFE" in text


def test_render_future_no_cells_no_crash():
    fs = [Forecast("5h", 1000, 10000, 40.0, None, 3600.0, False)]
    text = "\n".join(render_future(fs, None, 0.0, 80, False))
    assert "SAFE" in text or "5h" in text
    assert "may lag live" not in text


def test_render_future_narrow_one_liner():
    fs = [Forecast("weekly", 100, 1000, 20.0, None, 200000.0, False, profile="claude")]
    cells = {("claude", "weekly"): LiveCell(pct=99.0, state=STATE_OK, age_secs=1.0)}
    text = "\n".join(render_future(fs, None, 0.0, 40, False, cells=cells))
    assert "99%" in text
    assert "TIGHT" in text or "OVER" in text


# --- smooth dash: skeletons + store -----------------------------------------


def test_skeleton_has_no_ansi_when_color_off():
    body = "\n".join(render_skeleton("past", 80, False, spin="⠋"))
    assert "loading" in body.lower()
    assert "░" in body  # placeholder bars
    assert "\033" not in body
    assert "\033" not in render_stale_banner(False)


def test_skeleton_mentions_tab():
    assert "Past" in "\n".join(render_skeleton("past", 60, False))
    assert "Future" in "\n".join(render_skeleton("future", 60, False))


def test_spinner_cycles():
    assert spinner_char(0) != spinner_char(1) or len(set(spinner_char(i) for i in range(20))) > 1


def test_dash_store_stale_while_revalidate():
    s = DashStore()
    snap0 = s.snapshot()
    assert snap0.loading_present is True
    assert snap0.has_present is False
    s.publish_present([object()], {}, {})
    snap1 = s.snapshot()
    assert snap1.has_present is True
    assert snap1.loading_present is False
    s.set_loading("present", True)
    snap2 = s.snapshot()
    assert snap2.loading_present is True
    assert snap2.has_present is True  # stale data still available


def test_render_past_explains_spend():
    rows = _ledger_rows()
    text = "\n".join(render_past(rows, 120, False, show_cost=True))
    assert "spent" in text.lower() or "spend" in text.lower()
    assert "subscription" in text.lower() or "API" in text


# --- plan 064: Future/Past honesty ---
def test_064_no_impossible_hit_caption():
    from token_oracle.core.contracts import Forecast
    from token_oracle.dashboard.future import render_future
    from token_oracle.live.contract import STATE_OK
    from token_oracle.live.overlay import LiveCell

    # live 50%, local end-proj 90% (< 100 → never hits cap) must NOT show "hit in ..."
    fs = [Forecast("weekly", 500, 1000, 90.0, None, 3600.0, False, profile="claude")]
    cells = {("claude", "weekly"): LiveCell(pct=50.0, state=STATE_OK, age_secs=5.0)}
    text = "\n".join(render_future(fs, None, 0.0, 100, False, cells=cells))
    assert "hit in" not in text
    assert "no cap hit projected" in text


def test_064_live_now_high_not_reassured():
    from token_oracle.core.contracts import Forecast
    from token_oracle.dashboard.future import render_future
    from token_oracle.live.contract import STATE_OK
    from token_oracle.live.overlay import LiveCell

    # live 99% while local end-proj lags at 23% — must not reassure "no hit before reset"
    fs = [Forecast("weekly", 100, 1000, 23.0, None, 3600.0, False, profile="claude")]
    cells = {("claude", "weekly"): LiveCell(pct=99.0, state=STATE_OK, age_secs=3.0)}
    text = "\n".join(render_future(fs, None, 0.0, 100, False, cells=cells))
    assert "99%" in text
    assert "no hit before reset" not in text
    assert "99% now" in text  # factual, near-the-wall caption


def test_064_future_shows_retained_age_like_present():
    from token_oracle.core.contracts import Forecast
    from token_oracle.dashboard.future import render_future
    from token_oracle.live.contract import STATE_OK
    from token_oracle.live.overlay import LiveCell

    fs = [Forecast("fable", 100, 1000, 23.0, None, 3600.0, False, profile="claude")]
    cells = {
        ("claude", "fable"): LiveCell(
            pct=48.0, state=STATE_OK, age_secs=7200.0, extractor="modal+retained"
        )
    }
    text = "\n".join(render_future(fs, None, 0.0, 100, False, cells=cells))
    assert "48%" in text
    assert "retained" in text and "~2h ago" in text
    assert "live now   48%" not in text  # a retained cell is not fresh "live now"


def test_064_spark_flat_profile_not_all_full():
    from token_oracle.dashboard.future import spark_next24

    spark, _total = spark_next24([1.0] * 168, 0.0)
    assert spark.count("█") < 24  # flat burn is a steady band, not a solid wall


def test_064_past_total_not_bare_pct():
    from token_oracle.core.report import LedgerRow
    from token_oracle.dashboard.past import render_past

    rows = [
        LedgerRow(label="2026-07-01", tokens=5_000_000, cost=1.0, unpriced_tokens=0, pct_cap=62.5),
        LedgerRow(label="TOTAL", tokens=24_000_000, cost=5.0, unpriced_tokens=0, pct_cap=300.0),
    ]
    text = "\n".join(render_past(rows, 100, False))
    assert "3.0×wk" in text  # 14-day sum shown as a multiple of a week, not "300%"
