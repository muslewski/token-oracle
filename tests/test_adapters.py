import oracle.cli.colors as colors
from oracle.core.contracts import Forecast
from oracle.adapters import statusline, tmux

F_OK = Forecast("5h", 12000, 220000, 42.0, None, 3 * 3600 + 46 * 60, False)
F_HOT = Forecast("weekly", 5_000_000, 8_000_000, 130.0, 90000.0,
                 5 * 86400 + 18 * 3600, False)


def test_statusline_contains_numbers():
    s = statusline.render([F_OK], color=False)
    assert "12k/220k" in s and "42%" in s


def test_statusline_warns_on_eta():
    s = statusline.render([F_HOT], color=False)
    assert "cap" in s


def test_statusline_color_thresholds():
    assert colors.gauge_ansi_code(130) != colors.gauge_ansi_code(10)


def test_statusline_no_color_has_no_escapes():
    assert "\033" not in statusline.render([F_HOT], color=False)


def test_statusline_color_on_has_escapes():
    assert "\033" in statusline.render([F_OK], color=True)


def test_statusline_skips_idle():
    idle = Forecast("5h", 0, 220000, 0.0, None, 100.0, True)
    assert statusline.render([idle], color=False) == ""


def test_tmux_render_uses_tmux_color_syntax():
    s = tmux.render([F_OK])
    assert "#[fg=" in s and "12k/220k" in s
