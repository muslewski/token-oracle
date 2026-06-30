from oracle.core.contracts import Forecast
from oracle.adapters import statusline, tmux

F_OK = Forecast("5h", 12000, 220000, 42.0, None, 3 * 3600 + 46 * 60, False)
F_HOT = Forecast("weekly", 5_000_000, 8_000_000, 130.0, 90000.0,
                 5 * 86400 + 18 * 3600, False)

def test_statusline_contains_numbers():
    s = statusline.render([F_OK])
    assert "12k/220k" in s and "42%" in s

def test_statusline_warns_on_eta():
    s = statusline.render([F_HOT])
    assert "cap" in s   # eta -> cap warning appended

def test_statusline_color_thresholds():
    assert statusline.color_for(130) != statusline.color_for(10)

def test_tmux_render_uses_tmux_color_syntax():
    s = tmux.render([F_OK])
    assert "#[fg=" in s and "12k/220k" in s
