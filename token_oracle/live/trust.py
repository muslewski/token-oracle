"""Pure trust gate for present-time readings that may touch forecast MATH (plan 063, I3).

Retained / stale / low-confidence readings stay display-only; only a fresh,
high-confidence, non-retained OK reading is allowed to re-anchor the forecast.
"""

from __future__ import annotations

from .contract import CONF_HIGH, STATE_OK
from .overlay import FRESH_TTL_SECS


def is_trusted_for_math(*, state, confidence, age_secs, extractor) -> bool:
    if state != STATE_OK:
        return False
    if confidence != CONF_HIGH:
        return False
    if age_secs is None or age_secs > FRESH_TTL_SECS:
        return False
    if isinstance(extractor, str) and extractor.endswith("+retained"):
        return False
    return True


def newest_first(readings):
    def _key(r):
        ts = r.get("fetched_at") if isinstance(r, dict) else None
        return ts if isinstance(ts, (int, float)) else float("-inf")

    return sorted(readings or [], key=_key, reverse=True)
