import pytest

from token_oracle.core.contracts import Window
from token_oracle.core.windows import compute_window, eta_to_cap


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
    # single event 100s before window "now": tiny f, but huge measured_term
    # (280/100 tok/s) means f * measured_term alone clears the cap.
    evs = [(now - 100.0, 280)]
    f = compute_window(evs, now, w)
    assert f.projected_pct > 100
    assert f.eta_to_cap_secs is not None
    assert f.eta_to_cap_secs > 0


def test_rolling_reanchors_across_blocks():
    P = 18000
    w = Window(name="5h", cap=100000, period_secs=P)
    # start 0 -> re-anchor at 20000 (>= 0+P) -> re-anchor at 39000 (>= 20000+P)
    evs = [(0.0, 100), (20000.0, 50), (39000.0, 25)]
    now = 40000.0
    f = compute_window(evs, now, w)
    assert f.used == 25
    assert f.reset_in_secs == 17000.0
    assert f.idle is False


def test_rolling_expired_is_idle():
    P = 18000
    w = Window(name="5h", cap=100000, period_secs=P)
    evs = [(0.0, 100)]
    now = 20000.0  # > reset (18000)
    f = compute_window(evs, now, w)
    assert f.idle is True
    assert f.used == 0
    assert f.reset_in_secs == float(P)


def test_anchored_future_anchor_characterized():
    # characterization: future anchor yields a not-yet-started, non-idle window
    P = 18000
    now = 1000.0
    anchor = now + 1000
    w = Window(name="wk", cap=100000, period_secs=P, anchor=anchor)
    f = compute_window([], now, w)
    assert f.used == 0
    assert f.idle is False
    assert f.reset_in_secs == 19000.0  # > P


def test_prior_history_raises_early_projection():
    P = 18000
    w = Window(name="5h", cap=100000, period_secs=P)
    now = 100000.0
    evs_a = [(now - 60.0, 100)]
    evs_b = evs_a + [(now - 50000.0, 50000), (now - 40000.0, 50000)]  # before window start
    f_a = compute_window(evs_a, now, w)
    f_b = compute_window(evs_b, now, w)
    assert f_a.used == f_b.used == 100
    assert f_b.projected_pct > f_a.projected_pct


def test_profile_prior_used_exactly():
    P = 18000
    w = Window(name="5h", cap=100000, period_secs=P)
    now = 100000.0
    prof = [0.01] * 168
    used = 40
    evs = [(now - 100.0, used)]
    f = compute_window(evs, now, w, profile=prof)

    start = now - 100.0
    reset = start + P
    elapsed = max(1.0, now - start)
    frac = min(1.0, max(0.0, elapsed / P))
    measured_term = (used / elapsed) * (reset - now)
    prior_term = 0.01 * (reset - now)
    expected_projected = used + (1.0 - frac) * prior_term + frac * measured_term
    expected_pct = expected_projected / 100000 * 100

    assert f.projected_pct == pytest.approx(expected_pct)


def test_recompute_with_used_rebases_projection():
    from token_oracle.core.contracts import Forecast
    from token_oracle.core.windows import recompute_with_used

    # local: used 20%, end-proj 50% → residual 30% of cap
    f = Forecast("weekly", used=200, cap=1000, projected_pct=50.0,
                 eta_to_cap_secs=None, reset_in_secs=3600.0, idle=False, profile="claude")
    # live says 90% now
    g = recompute_with_used(f, used=900)
    assert g.used == 900
    # residual 300 tokens → end 1200 → 120%
    assert abs(g.projected_pct - 120.0) < 0.01
    assert g.eta_to_cap_secs is not None and g.eta_to_cap_secs > 0
    # projected_pct is end-of-window, not current fill alias
    assert g.projected_pct != 90.0


def test_recompute_with_used_floors_at_live_fill():
    from token_oracle.core.contracts import Forecast
    from token_oracle.core.windows import recompute_with_used

    # local end-proj undercounts badly (logs lag)
    f = Forecast("weekly", used=100, cap=1000, projected_pct=20.0,
                 eta_to_cap_secs=None, reset_in_secs=7200.0, idle=False)
    g = recompute_with_used(f, used=990)  # live 99%
    assert g.used == 990
    # residual = max(0, 200-100)=100 → 990+100=1090 → 109%
    assert g.projected_pct >= 99.0
    assert abs(g.projected_pct - 109.0) < 0.01


def test_recompute_idle_unchanged():
    from token_oracle.core.contracts import Forecast
    from token_oracle.core.windows import recompute_with_used

    f = Forecast("5h", 0, 1000, 0.0, None, 18000.0, True)
    assert recompute_with_used(f, 500) is f
