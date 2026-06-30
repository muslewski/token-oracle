from token_oracle.core.profile import build_profile, profile_integral, N_BUCKETS


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
