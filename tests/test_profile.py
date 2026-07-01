import pytest

from token_oracle.core.profile import (
    N_BUCKETS,
    _accumulate,
    build_profile,
    profile_integral,
)
from token_oracle.core.timeutil import bucket_key


def _first_ts_where(pred, base=1_800_000_000.0):
    """First hour-aligned ts >= base whose local hour-of-week satisfies pred."""
    t = base - (base % 3600.0)
    for _ in range(24 * 14):
        if pred(bucket_key(t)):
            return t
        t += 3600.0
    raise AssertionError("no matching hour found")


def test_empty_events_zero_profile():
    prof = build_profile([], 1_000_000.0)
    assert len(prof) == N_BUCKETS
    assert all(r == 0.0 for r in prof)


def test_profile_integral_zero_when_flat_zero():
    assert profile_integral([0.0] * N_BUCKETS, 0.0, 3600.0) == 0.0


def test_uniform_load_gives_positive_rate_and_integral():
    now = 30 * 86400.0
    # ~one event/hour of 100 tokens across the trailing 21 days
    evs = [(now - h * 3600.0, 100) for h in range(1, 21 * 24)]
    prof = build_profile(evs, now)
    assert any(r > 0 for r in prof)
    # integral over a 5h horizon must be positive and finite
    val = profile_integral(prof, now, now + 5 * 3600.0)
    assert val > 0 and val < 5 * 3600.0 * max(prof) + 1


def test_recency_decay_downweights_old_usage():
    now = 1_800_000_000.0
    ts_a = now - 3600.0
    b_a = bucket_key(ts_a)
    # 5 weeks (168h * 5) back keeps the same local hour-of-week bucket and is
    # well past the 14-day recency half-life, while staying inside HIST_SECS.
    ts_b = ts_a - 168 * 3600.0 * 5
    b_b = bucket_key(ts_b)
    assert b_a == b_b
    tokens = 1000
    prof_a = build_profile([(ts_a, tokens)], now)
    prof_b = build_profile([(ts_b, tokens)], now)
    assert prof_b[b_b] < prof_a[b_a]


def test_weekend_weekday_separation():
    now = 1_800_000_000.0
    events = []
    base = now - 21 * 86400.0
    for _ in range(30):
        t = _first_ts_where(lambda b: b // 24 >= 5, base=base)
        events.append((t, 1000))
        base = t + 3600.0
    assert len(events) == 30
    assert all(ts <= now for ts, _ in events)
    prof = build_profile(events, now)
    weekend_rates = [prof[b] for b in range(N_BUCKETS) if b // 24 >= 5]
    weekday_rates = [prof[b] for b in range(N_BUCKETS) if b // 24 < 5]
    mean_weekend = sum(weekend_rates) / len(weekend_rates)
    mean_weekday = sum(weekday_rates) / len(weekday_rates)
    assert mean_weekend > mean_weekday


def test_shrinkage_bounds_sparse_bucket():
    now = 1_800_000_000.0
    ts = now - 3600.0
    b = bucket_key(ts)
    tokens = 100_000
    prof = build_profile([(ts, tokens)], now)
    S, E = _accumulate([(ts, tokens)], now)
    tot_s, tot_e = sum(S), sum(E)
    flat_rate = (tot_s / tot_e) if tot_e > 0 else 0.0
    raw_rate = (S[b] / E[b]) if E[b] > 0 else flat_rate
    assert flat_rate < prof[b] < raw_rate


def test_profile_integral_partial_hours():
    r = 0.02
    prof = [r] * 168
    t0 = 1_800_000_000.0
    t0 -= t0 % 3600.0  # hour-aligned
    val = profile_integral(prof, t0 + 1800, t0 + 5400)  # spans two buckets
    assert val == pytest.approx(r * 3600)


def test_profile_integral_empty_and_reversed():
    prof = [0.02] * 168
    assert profile_integral([], 0.0, 100.0) == 0.0
    assert profile_integral(prof, 100.0, 0.0) == 0.0  # start >= end guard
