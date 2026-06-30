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
