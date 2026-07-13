import token_oracle.cli.colors as c


def test_gauge_tier_boundaries():
    assert c.gauge_tier(84) == "green"
    assert c.gauge_tier(85) == "lime"
    assert c.gauge_tier(99) == "lime"
    assert c.gauge_tier(100) == "orange"
    assert c.gauge_tier(119) == "orange"
    assert c.gauge_tier(120) == "red"


def test_paint_off_is_plain():
    assert c.paint("x", c.VIOLET, False) == "x"


def test_paint_on_wraps():
    s = c.paint("x", c.VIOLET, True)
    assert s.startswith("\033[38;5;141m") and s.endswith(c.RESET)


def test_no_color_env_disables(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert c.color_enabled() is False
    assert c.pipe_color() is False


def test_force_color_enables(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert c.color_enabled() is True


def test_pipe_color_ignores_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert c.pipe_color() is True


def test_gauge_codes_differ_by_severity():
    assert c.gauge_ansi_code(130) != c.gauge_ansi_code(10)
    assert c.gauge_tmux(130) != c.gauge_tmux(10)


def test_ok_badge_uses_markers():
    assert c.M_OK in c.ok_badge(True, False)
    assert c.M_BAD in c.ok_badge(False, False)


def test_box_line_truncation_preserves_color():
    # long dim text in narrow box must keep the dim SGR, include …, end with reset, exact width
    result = c.box_line(c.dim("x" * 80, True), 30, True)
    assert "38;5;240" in result
    assert "…" in result
    assert "\033[0m" in result
    assert c.display_width(result) == 30


def test_box_line_truncation_fits_exact_width():
    # for several widths, truncated colored text must yield a box of exact display width
    long_colored = c.dim("y" * 100, True) + c.violet("z" * 50, True)
    for w in (20, 30, 36, 50):
        result = c.box_line(long_colored, w, True)
        assert c.display_width(result) == w, f"width {w} failed: got {c.display_width(result)}"


def test_box_line_short_text_unchanged():
    # short (non-trunc) path must be byte-identical in structure, no …, exact width
    short = c.dim("short meta", True)
    w = 40
    result = c.box_line(short, w, True)
    assert "…" not in result
    assert result.startswith("│")
    assert result.endswith("│")
    assert c.display_width(result) == w
