from token_oracle.core.contracts import Forecast, Window


def test_window_modes():
    rolling = Window(name="5h", cap=1000, period_secs=18000)
    fixed = Window(name="wk", cap=9000, period_secs=604800, anchor=0.0)
    assert rolling.anchor is None
    assert fixed.anchor == 0.0


def test_forecast_confidence_default():
    f = Forecast("5h", 10, 100, 12.0, None, 300.0, False)
    assert f.confidence == 1.0
    assert f.profile == "default"


def test_forecast_profile_tag():
    f = Forecast("weekly", 100, 1000, 10.0, None, 100.0, False, profile="grok")
    assert f.profile == "grok"
