"""Pattern-aware burn profile: 168-bucket (hour-of-week) tok/s rate with
recency decay and empirical-Bayes shrinkage. Stdlib only. ML seam: replace
build_profile with a learned model exposing the same signature."""

from .timeutil import bucket_key

N_BUCKETS = 168  # 7 weekdays x 24 hours
HIST_SECS = 63 * 24 * 3600  # trailing retention (9 weeks)
DECAY_HALFLIFE_SECS = 14 * 24 * 3600  # recency half-life
SHRINK_K = 3.0  # empirical-Bayes pseudo-count


def _decay(age_secs):
    return 0.5 ** (max(0.0, age_secs) / DECAY_HALFLIFE_SECS)


def _accumulate(events, now):
    """Decay-weighted token sums (S) and exposure seconds (E) per hour-of-week.
    Exposure is wall-clock (idle baked in): every hour-slot in the retained
    window contributes 3600s x its decay weight, regardless of activity."""
    S = [0.0] * N_BUCKETS
    E = [0.0] * N_BUCKETS
    cutoff = now - HIST_SECS
    for ts, tok in events:
        if ts < cutoff or ts > now:
            continue
        S[bucket_key(ts)] += _decay(now - ts) * tok
    t = cutoff
    while t < now:
        E[bucket_key(t)] += _decay(now - t) * 3600.0
        t += 3600.0
    return S, E


def build_profile(events, now):
    """168-bucket tok/s profile with empirical-Bayes backoff shrinkage:
    (hour,weekday) -> (hour,daytype) -> (hour) -> flat. flat is the root."""
    S, E = _accumulate(events, now)

    def shrink(s, e, parent):
        n = e / 3600.0
        raw = (s / e) if e > 0 else parent
        return (n * raw + SHRINK_K * parent) / (n + SHRINK_K)

    tot_s, tot_e = sum(S), sum(E)
    flat = (tot_s / tot_e) if tot_e > 0 else 0.0

    hour_s = [0.0] * 24
    hour_e = [0.0] * 24
    for b in range(N_BUCKETS):
        hour_s[b % 24] += S[b]
        hour_e[b % 24] += E[b]
    hour_rate = [shrink(hour_s[h], hour_e[h], flat) for h in range(24)]

    dt_s, dt_e = {}, {}
    for b in range(N_BUCKETS):
        h, wd = b % 24, b // 24
        dt = 1 if wd >= 5 else 0
        dt_s[(h, dt)] = dt_s.get((h, dt), 0.0) + S[b]
        dt_e[(h, dt)] = dt_e.get((h, dt), 0.0) + E[b]
    dt_rate = {k: shrink(dt_s[k], dt_e[k], hour_rate[k[0]]) for k in dt_s}

    profile = [0.0] * N_BUCKETS
    for b in range(N_BUCKETS):
        h, wd = b % 24, b // 24
        dt = 1 if wd >= 5 else 0
        profile[b] = shrink(S[b], E[b], dt_rate.get((h, dt), hour_rate[h]))
    return profile


def profile_integral(profile, start, end):
    """Expected tokens over [start, end) given a 168-bucket tok/s profile."""
    if not profile or start >= end:
        return 0.0
    total = 0.0
    t = start
    while t < end:
        nxt = min(end, t - (t % 3600.0) + 3600.0)
        total += profile[bucket_key(t)] * (nxt - t)
        t = nxt
    return total
