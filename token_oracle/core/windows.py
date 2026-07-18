"""Forecast one Window from neutral (ts, tokens) events. Generalizes the
5h-block (rolling, anchor=None) and weekly (fixed grid, anchor set) windows
into a single history-aware projection. Never raises."""

from dataclasses import replace

from .contracts import Forecast
from .profile import HIST_SECS, profile_integral

# Slack on the observed burn when bounding an end-of-window projection: only a
# history-driven blend that exceeds this multiple of the measured burn is
# clamped (plan 063, I2). >1 so a normal prior≈measured blend is never touched.
PROJ_BOUND_SLACK = 2.0


def observed_rate(events, start, now, rate_window_secs=3600.0):
    """Tokens/sec burned over the recent trailing window [max(start, now-W), now].

    A *measured* rate (not a projection-implied one), used to bound the
    projection + ETA by real recent burn. None when no burn is observed.
    """
    lo = max(float(start), float(now) - float(rate_window_secs))
    total = 0
    for e in events or []:
        try:
            ts = float(e[0])
            tok = int(e[1] or 0)
        except (TypeError, ValueError, IndexError):
            continue
        if lo <= ts <= now:
            total += tok
    span = now - lo
    if span <= 0 or total <= 0:
        return None
    return total / span


def bounded_projection(used_now, obs_rate, time_left, cap, slack=1.5):
    """End-of-window projected tokens from linear observed burn, floored at now.

    When ``obs_rate`` is unknown/zero the projection is flat at ``used_now`` —
    never invents future burn.
    """
    extra = 0.0 if not obs_rate or obs_rate <= 0 else obs_rate * max(0.0, time_left) * slack
    return max(int(used_now), int(round(used_now + extra)))


def eta_to_cap(used, cap, obs_rate, projected_pct=None):
    """Seconds until usage reaches cap at the OBSERVED trailing burn (I2).

    0.0 when already at/over cap; None when not heading over (projected<=100),
    when there is no observed burn, or when cap is unknown."""
    if cap <= 0:
        return None
    if projected_pct is not None and projected_pct <= 100:
        return None
    if used >= cap:
        return 0.0
    if not obs_rate or obs_rate <= 0:
        return None
    return (cap - used) / obs_rate


def recompute_with_used(f: Forecast, used: int, *, obs_rate=None, active=None) -> Forecast:
    """Re-base an existing Forecast on an authoritative *current* fill (live /
    server header), keeping the projection physically bounded (plan 063, I2).

    Keeps the local model's residual burn (``old_projected - old_used``) grafted
    onto the new ``used``, but clamps the total by the observed trailing burn so
    a locally over-projected cycle can't push a several-hundred-% end-projection
    onto a modest server fill. ``projected_pct`` stays an end-of-window
    projection, never a current-fill alias (plan 030). Idle forecasts pass
    through unless ``active`` (I5: a trusted present reading overrides the
    log-derived idle veto).
    """
    if f is None:
        return f
    if getattr(f, "idle", False) and not active:
        return f
    cap = int(getattr(f, "cap", 0) or 0)
    if cap <= 0:
        return f
    used_now = max(0, min(int(round(used)), cap))
    old_used = int(getattr(f, "used", 0) or 0)
    old_proj_tok = float(getattr(f, "projected_pct", 0.0) or 0.0) / 100.0 * cap
    residual = max(0.0, old_proj_tok - old_used)
    projected_tok = used_now + residual
    rate = obs_rate if obs_rate is not None else getattr(f, "obs_rate", None)
    reset_in = float(getattr(f, "reset_in_secs", 0.0) or 0.0)
    if rate is not None:
        # bound the grafted residual by real recent burn (kills r5 explosion)
        projected_tok = min(projected_tok, bounded_projection(used_now, rate, reset_in, cap))
    projected_tok = max(projected_tok, float(used_now))
    projected_pct = projected_tok / cap * 100.0
    eta = eta_to_cap(used_now, cap, rate, projected_pct)
    return replace(
        f,
        used=used_now,
        projected_pct=projected_pct,
        eta_to_cap_secs=eta,
        idle=False,
        obs_rate=rate,
    )


def _bounds(events, now, window):
    """Return (start, reset) of the current window, or None if rolling and
    idle/expired."""
    P = window.period_secs
    if window.anchor is not None:
        n = max(0, int((now - window.anchor) // P))
        start = window.anchor + n * P
        return start, start + P
    if not events:
        return None
    # For short rolling windows like the 5h "current" block, focus the re-anchor walk
    # on the most recent activity cluster (events that could be in the current 5h or
    # immediately preceding one). This makes the displayed reset time more relevant
    # to the user's *current session* instead of being anchored to an old burst from
    # hours earlier in the long history retention.
    start_events = events
    if P <= 6 * 3600:  # 5h-style current windows
        recent_cutoff = now - (P * 1.2)
        recent = [e for e in events if e[0] >= recent_cutoff]
        if recent:
            start_events = recent
    start = start_events[0][0]
    for ts, _tok in start_events[1:]:
        if ts >= start + P:
            start = ts  # window expired -> re-anchor here
    reset = start + P
    if now > reset:
        return None
    return start, reset


def compute_window(events, now, window, profile=None):
    """events may be list of normalized 8-tuples (with model at [2]) or bare (ts,tok) pairs.
    If window.model is set, only events whose model (case-insens) contains it contribute."""
    cap = window.cap
    P = window.period_secs
    model_f = getattr(window, "model", None) or None
    model_f = model_f.lower() if model_f else None

    def matches_model(e):
        if not model_f:
            return True
        # support both pair and full event
        m = e[2] if len(e) > 2 else None
        return bool(m and model_f in str(m).lower())

    # normalize view for bounds: bounds logic only cares about timestamps of matching events
    filtered_for_bounds = [e for e in (events or []) if matches_model(e)]
    pairs_all = [(float(e[0]), int(e[1])) for e in filtered_for_bounds]  # for bounds + sums
    bounds = _bounds(pairs_all, now, window)
    if bounds is None:
        return Forecast(window.name, 0, cap, 0.0, None, float(P), True)
    start, reset = bounds
    used = sum(tok for ts, tok in pairs_all if start <= ts <= now)
    elapsed = max(1.0, now - start)
    # History-aware burn: naive (used/elapsed)*period explodes at window start.
    # Blend a learned prior with this window's measured rate by window-fraction.
    # Early window trusts the prior (no reset spike); late window trusts measured.
    f = min(1.0, max(0.0, elapsed / P))
    measured_term = (used / elapsed) * (reset - now)
    if profile is None:
        hist_cutoff = now - HIST_SECS
        prior_used = sum(tok for ts, tok in pairs_all if hist_cutoff <= ts < start)
        prior_span = max(1.0, start - hist_cutoff)
        prior_term = (prior_used / prior_span) * (reset - now)
    else:
        prior_term = profile_integral(profile, now, reset)
    projected = used + (1.0 - f) * prior_term + f * measured_term
    # Bound the history-driven blend by the observed burn so an atypical early
    # burst (heavy prior_term at f≈0) can't project many-hundred-% (plan 063,
    # I2). Only a blend beyond PROJ_BOUND_SLACK× the measured burn is clamped;
    # a normal prior≈measured blend is untouched.
    observed_bound = used + PROJ_BOUND_SLACK * measured_term
    projected = max(float(used), min(projected, observed_bound))
    projected_pct = (projected / cap * 100) if cap else 0.0
    reset_in = reset - now
    # ETA from the OBSERVED trailing burn, not the (now-bounded) projection rate.
    obs_rate = observed_rate(pairs_all, start, now)
    eta = eta_to_cap(used, cap, obs_rate, projected_pct)
    return Forecast(
        window.name, int(used), cap, projected_pct, eta, float(reset_in), False, obs_rate=obs_rate
    )
