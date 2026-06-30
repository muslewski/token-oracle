from oracle.core.contracts import UsageEvent, Window, Forecast, to_pairs

def test_usageevent_defaults():
    e = UsageEvent(timestamp=100.0, tokens=5)
    assert e.model is None and e.session_id is None and e.kind is None

def test_window_modes():
    rolling = Window(name="5h", cap=1000, period_secs=18000)
    fixed = Window(name="wk", cap=9000, period_secs=604800, anchor=0.0)
    assert rolling.anchor is None
    assert fixed.anchor == 0.0

def test_forecast_confidence_default():
    f = Forecast("5h", 10, 100, 12.0, None, 300.0, False)
    assert f.confidence == 1.0

def test_to_pairs_sorts():
    evs = [UsageEvent(3.0, 1), UsageEvent(1.0, 2), UsageEvent(2.0, 3)]
    assert to_pairs(evs) == [(1.0, 2), (2.0, 3), (3.0, 1)]
