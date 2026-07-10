"""Forecast one Window from neutral (ts, tokens) events. Generalizes the
5h-block (rolling, anchor=None) and weekly (fixed grid, anchor set) windows
into a single history-aware projection. Never raises."""

from .contracts import Forecast
from .profile import HIST_SECS, profile_integral


def eta_to_cap(used, projected_pct, time_left, cap):
    """Seconds until usage reaches cap at the projection-implied burn. None when
    not heading over (<=100%) or indeterminate; 0.0 when already at/over cap."""
    if projected_pct <= 100 or cap <= 0:
        return None
    if used >= cap:
        return 0.0
    if time_left <= 0:
        return None
    projected_tokens = projected_pct / 100.0 * cap
    rate = (projected_tokens - used) / time_left
    if rate <= 0:
        return None
    return (cap - used) / rate


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
    model_f = (getattr(window, "model", None) or None)
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
    projected_pct = (projected / cap * 100) if cap else 0.0
    reset_in = reset - now
    eta = eta_to_cap(used, projected_pct, reset_in, cap)
    return Forecast(window.name, int(used), cap, projected_pct, eta, float(reset_in), False)
