"""Tests for live snapshot retain-cycle escalation (plan 063 I4).

Pure, no I/O: exercise merge_with_previous with empty probes fed back as the
previous snapshot to simulate consecutive probe-failing cycles.
"""

from token_oracle.live.contract import (
    CONF_HIGH,
    METRIC_WEEKLY_PCT,
    STATE_AUTH_NO_DATA,
    STATE_OK,
    STATE_STALE,
    LiveReading,
    ProviderLive,
    provider_live_to_dict,
)
from token_oracle.live.store import (
    RETAIN_MAX_CYCLES,
    merge_with_previous,
)


def _good(now):
    return ProviderLive(
        provider="grok",
        state=STATE_OK,
        readings=[
            LiveReading(
                provider="grok",
                metric=METRIC_WEEKLY_PCT,
                value=20.0,
                confidence=CONF_HIGH,
                extractor="grok.modal",
                evidence="20% used",
                fetched_at=now,
            )
        ],
        fetched_at=now,
    )


def _empty(now):
    return ProviderLive(
        provider="grok",
        state=STATE_AUTH_NO_DATA,
        readings=[],
        fetched_at=now,
    )


def _as_snap(providers, now):
    return {
        "version": 1,
        "written_at": now,
        "providers": {k: provider_live_to_dict(v) for k, v in providers.items()},
    }


def test_retain_cycle_escalates_to_stale():
    now = 10_000.0
    prev = _as_snap({"grok": _good(now)}, now)
    # Keep readings artificially non-expired so only the cycle counter escalates.
    last = None
    for _ in range(RETAIN_MAX_CYCLES + 1):
        merged = merge_with_previous(
            {"grok": _empty(now)}, prev, now=now, retain_max_age=1e12
        )
        last = merged
        prev = _as_snap(merged, now)
    assert last["grok"].state == STATE_STALE
    assert "probe failing" in (last["grok"].note or "")


def test_retain_streak_stays_ok_within_cap():
    now = 10_000.0
    prev = _as_snap({"grok": _good(now)}, now)
    merged = None
    for _ in range(RETAIN_MAX_CYCLES):  # exactly at the cap, not over
        merged = merge_with_previous(
            {"grok": _empty(now)}, prev, now=now, retain_max_age=1e12
        )
        prev = _as_snap(merged, now)
    # last-good still applied, not yet escalated
    assert merged["grok"].state == STATE_OK
    assert merged["grok"].readings[0].value == 20.0


def test_retain_cycle_resets_on_real_reading():
    now = 10_000.0
    prev = _as_snap({"grok": _good(now)}, now)
    # a couple of failing cycles
    for _ in range(3):
        merged = merge_with_previous(
            {"grok": _empty(now)}, prev, now=now, retain_max_age=1e12
        )
        prev = _as_snap(merged, now)
    # a real probe arrives -> wins, no retain marker
    merged = merge_with_previous({"grok": _good(now)}, prev, now=now)
    assert merged["grok"].state == STATE_OK
    assert "retain#" not in (merged["grok"].note or "")
