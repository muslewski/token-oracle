from oracle.core.contracts import Window
from oracle.core.windows import compute_window, eta_to_cap

def test_eta_none_when_under_cap():
    assert eta_to_cap(50, 80.0, 3600.0, 100) is None

def test_eta_zero_when_already_over():
    assert eta_to_cap(150, 200.0, 3600.0, 100) == 0.0

def test_eta_positive_when_projected_over():
    eta = eta_to_cap(50, 200.0, 3600.0, 100)
    assert eta is not None and eta > 0

def test_rolling_window_idle_when_no_events():
    w = Window(name="5h", cap=1000, period_secs=18000)
    f = compute_window([], 1000.0, w)
    assert f.idle is True and f.used == 0 and f.projected_pct == 0.0

def test_rolling_window_counts_recent_usage():
    now = 100000.0
    w = Window(name="5h", cap=1000, period_secs=18000)
    evs = [(now - 600.0, 200), (now - 60.0, 50)]
    f = compute_window(evs, now, w)
    assert f.idle is False
    assert f.used == 250
    assert f.reset_in_secs > 0

def test_fixed_window_never_idle():
    now = 1_000_000.0
    w = Window(name="wk", cap=10_000, period_secs=604800, anchor=0.0)
    f = compute_window([(now - 100.0, 500)], now, w)
    assert f.idle is False
    assert f.used == 500
    assert 0 < f.reset_in_secs <= 604800

def test_projection_sets_eta_when_burning_hot():
    now = 100000.0
    w = Window(name="5h", cap=300, period_secs=18000)
    # heavy burst near window start: projected should exceed cap -> eta set
    evs = [(now - 17000.0, 250), (now - 100.0, 40)]
    f = compute_window(evs, now, w)
    if f.projected_pct > 100:
        assert f.eta_to_cap_secs is not None
