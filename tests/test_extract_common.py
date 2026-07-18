"""Tests for the symmetric upward-misparse guard in monotonic_guard (plan 063 I4).

A lone extractor spiking weekly usage by a large amount with no corroboration is
held (downgraded to CONF_LOW so overlay/math will not adopt it); a jump backed by
a second reading near the same value is adopted.
"""

import time

from token_oracle.live.contract import (
    CONF_HIGH,
    CONF_LOW,
    METRIC_RESET_AT,
    METRIC_WEEKLY_PCT,
    LiveReading,
)
from token_oracle.live.extract_common import monotonic_guard

_PREV_30 = {
    "providers": {
        "grok": {
            "readings": [
                {"metric": METRIC_WEEKLY_PCT, "value": 30.0, "confidence": "high"},
            ]
        }
    }
}


def test_monotonic_upward_guard_holds_uncorroborated_jump():
    now = time.time()
    spike = LiveReading(
        "grok", METRIC_WEEKLY_PCT, 95.0, CONF_HIGH, "grok.usage_modal.text", "95% used", now
    )
    guarded = monotonic_guard([spike], _PREV_30, now)
    assert len(guarded) == 1
    assert guarded[0].confidence == CONF_LOW  # not adopted
    assert "unexplained jump" in guarded[0].evidence.lower()
    assert guarded[0].value == 95.0  # value retained for next-cycle self-heal


def test_monotonic_upward_guard_adopts_corroborated_jump():
    now = time.time()
    r1 = LiveReading(
        "grok", METRIC_WEEKLY_PCT, 95.0, CONF_HIGH, "grok.usage_modal.text", "95%", now
    )
    r2 = LiveReading(
        "grok", METRIC_WEEKLY_PCT, 94.0, CONF_HIGH, "grok.network_json", "94%", now
    )
    guarded = monotonic_guard([r1, r2], _PREV_30, now)
    assert all(g.confidence == CONF_HIGH for g in guarded)


def test_monotonic_small_rise_untouched():
    now = time.time()
    r = LiveReading("grok", METRIC_WEEKLY_PCT, 45.0, CONF_HIGH, "grok.modal", "45%", now)
    guarded = monotonic_guard([r], _PREV_30, now)
    assert guarded[0].confidence == CONF_HIGH  # +15 < 40pt threshold


def test_monotonic_upward_guard_allows_jump_after_reset():
    now = time.time()
    spike = LiveReading("grok", METRIC_WEEKLY_PCT, 95.0, CONF_HIGH, "grok.modal", "95%", now)
    prev_past_reset = {
        "providers": {
            "grok": {
                "readings": [
                    {"metric": METRIC_WEEKLY_PCT, "value": 30.0},
                    {"metric": METRIC_RESET_AT, "value": now - 100},
                ]
            }
        }
    }
    guarded = monotonic_guard([spike], prev_past_reset, now)
    assert guarded[0].confidence == CONF_HIGH  # reset explains a large move
