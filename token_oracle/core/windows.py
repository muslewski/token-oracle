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
    start = events[0][0]
    for ts, _tok in events[1:]:
        if ts >= start + P:
            start = ts  # window expired -> re-anchor here
    reset = start + P
    if now > reset:
        return None
    return start, reset


def compute_window(events, now, window, profile=None):
    cap = window.cap
    P = window.period_secs
    bounds = _bounds(events, now, window)
    if bounds is None:
        return Forecast(window.name, 0, cap, 0.0, None, float(P), True)
    start, reset = bounds
    used = sum(tok for ts, tok in events if start <= ts <= now)
    elapsed = max(1.0, now - start)
    # History-aware burn: naive (used/elapsed)*period explodes at window start.
    # Blend a learned prior with this window's measured rate by window-fraction.
    # Early window trusts the prior (no reset spike); late window trusts measured.
    f = min(1.0, max(0.0, elapsed / P))
    measured_term = (used / elapsed) * (reset - now)
    if profile is None:
        hist_cutoff = now - HIST_SECS
        prior_used = sum(tok for ts, tok in events if hist_cutoff <= ts < start)
        prior_span = max(1.0, start - hist_cutoff)
        prior_term = (prior_used / prior_span) * (reset - now)
    else:
        prior_term = profile_integral(profile, now, reset)
    projected = used + (1.0 - f) * prior_term + f * measured_term
    projected_pct = (projected / cap * 100) if cap else 0.0
    reset_in = reset - now
    eta = eta_to_cap(used, projected_pct, reset_in, cap)
    return Forecast(window.name, int(used), cap, projected_pct, eta, float(reset_in), False)
