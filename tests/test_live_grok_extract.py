"""Pure tests for grok_extract (no playwright, no network)."""

import json
import pathlib
import time

from token_oracle.live.contract import (
    CONF_HIGH,
    CONF_LOW,
    CONF_MEDIUM,
    METRIC_RATE_WINDOW,
    METRIC_RESET_AT,
    METRIC_WEEKLY_PCT,
    STATE_AUTH_NO_DATA,
    STATE_OK,
    STATE_RATE_DATA_ONLY,
)
from token_oracle.live.grok_extract import (
    build_provider_live,
    merge_readings,
    monotonic_guard,
    readings_from_labeled_text,
    readings_from_network_json,
    readings_from_progressbars,
    readings_from_reset_text,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "live"


def load_json(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_rate_limit_json_yields_only_rate_window():
    obj = load_json("grok_rate_limit.json")
    now = time.time()
    rs = readings_from_network_json("https://grok.com/api/foo", obj, now)
    assert len(rs) == 1
    r = rs[0]
    assert r.metric == METRIC_RATE_WINDOW
    assert r.value == 0.0  # 150/150 used
    assert r.confidence == CONF_HIGH
    assert "grok.network_json.rate" in r.extractor
    assert "remainingQueries=150" in r.evidence
    # never weekly from rate shape
    assert all(r2.metric != METRIC_WEEKLY_PCT for r2 in rs)


def test_bars_fixture_emits_one_weekly_high_and_scales_fraction():
    bars = load_json("grok_usage_bars.json")
    now = time.time()
    rs = readings_from_progressbars(bars, now)
    weeklies = [r for r in rs if r.metric == METRIC_WEEKLY_PCT]
    # Grok build + Weekly SuperGrok Heavy Limit; bare "Usage …" decoy rejected
    assert len(weeklies) == 2  # 10% + 0.1 -> 10%
    vals = sorted(r.value for r in weeklies)
    assert vals == [10.0, 10.0]
    assert all(r.confidence == CONF_HIGH for r in weeklies)
    # decoys: Sidebar + bare "Usage …" produce nothing
    assert len([r for r in rs if "Sidebar" in (r.evidence or "")]) == 0
    assert len([r for r in rs if "Usage sidebar" in (r.evidence or "")]) == 0


def test_progressbar_bare_usage_label_yields_nothing():
    """Bare 'usage' alone must not become CONF_HIGH weekly (F-A5-2)."""
    now = time.time()
    bars = [{"valuenow": "45", "valuemax": "100", "label": "Usage settings"}]
    rs = readings_from_progressbars(bars, now)
    assert rs == []


def test_sections_yields_nothing_for_unlabeled_chat_and_weekly_plus_reset_for_real():
    secs = load_json("grok_sections.json")
    now = time.time()
    # decoy alone
    decoy = [secs[0]]
    rs = readings_from_labeled_text(decoy, now)
    assert len(rs) == 0
    # real labeled + reset
    real = [secs[1]]
    rs = readings_from_labeled_text(real, now) + readings_from_reset_text(real, now)
    week = [r for r in rs if r.metric == METRIC_WEEKLY_PCT]
    assert len(week) == 1
    assert week[0].value == 10.0
    assert week[0].confidence == CONF_MEDIUM
    assert "grok.labeled_text" in week[0].extractor
    resets = [r for r in rs if r.metric == METRIC_RESET_AT]
    assert len(resets) == 1
    assert resets[0].confidence == CONF_MEDIUM


def test_merge_agree_upgrades_to_high_and_conflict_prefer_trust():
    now = time.time()
    from token_oracle.live.contract import LiveReading

    a = LiveReading(
        "grok",
        METRIC_WEEKLY_PCT,
        10.0,
        CONF_HIGH,
        "grok.progressbar",
        "Grok build 10%",
        now,
    )
    b = LiveReading(
        "grok",
        METRIC_WEEKLY_PCT,
        10.0,
        CONF_MEDIUM,
        "grok.labeled_text",
        "Grok build — 10% used",
        now,
    )
    merged = merge_readings([a, b])
    assert len(merged) == 1
    assert merged[0].confidence == CONF_HIGH

    # Equal-trust conflict → both LOW
    equal_a = LiveReading(
        "grok", METRIC_WEEKLY_PCT, 10.0, CONF_MEDIUM, "grok.labeled_text", "a", now
    )
    equal_b = LiveReading(
        "grok", METRIC_WEEKLY_PCT, 13.0, CONF_MEDIUM, "grok.labeled_text2", "b", now
    )
    conflicted = merge_readings([equal_a, equal_b])
    assert len(conflicted) == 2
    assert all(r.confidence == CONF_LOW for r in conflicted)
    assert any("conflicts with" in (r.evidence or "") for r in conflicted)


def test_merge_conflict_prefers_modal_over_progressbar():
    """A correct modal weekly must survive a decoy progressbar (quality-pass F-A5-1)."""
    now = time.time()
    from token_oracle.live.contract import LiveReading

    modal = LiveReading(
        "grok",
        METRIC_WEEKLY_PCT,
        23.0,
        CONF_HIGH,
        "grok.usage_modal.text",
        "Weekly SuperGrok Heavy Limit — 23% used",
        now,
    )
    decoy = LiveReading(
        "grok",
        METRIC_WEEKLY_PCT,
        80.0,
        CONF_HIGH,
        "grok.progressbar",
        "Usage sidebar 80%",
        now,
    )
    merged = merge_readings([modal, decoy])
    highs = [r for r in merged if r.confidence == CONF_HIGH]
    assert len(highs) == 1
    assert highs[0].value == 23.0
    assert "usage_modal" in highs[0].extractor
    lows = [r for r in merged if r.confidence == CONF_LOW]
    assert any(r.value == 80.0 for r in lows)


def test_merge_two_medium_agree_does_not_upgrade_to_high():
    """Two text scrapes agreeing is not structured evidence (F-A5-6)."""
    now = time.time()
    from token_oracle.live.contract import LiveReading

    a = LiveReading("grok", METRIC_WEEKLY_PCT, 10.0, CONF_MEDIUM, "grok.labeled_text", "a 10%", now)
    b = LiveReading(
        "grok", METRIC_WEEKLY_PCT, 10.5, CONF_MEDIUM, "grok.labeled_text_b", "b 10%", now
    )
    merged = merge_readings([a, b])
    assert len(merged) == 1
    assert merged[0].confidence == CONF_MEDIUM


def test_monotonic_guard_downgrades_unexplained_drop_but_keeps_with_past_reset():
    now = time.time()
    from token_oracle.live.contract import LiveReading

    new_r = LiveReading("grok", METRIC_WEEKLY_PCT, 4.0, CONF_HIGH, "grok.progressbar", "4%", now)
    # no reset (or future reset) in prev snapshot + unexplained drop -> low
    prev_no_reset = {
        "providers": {
            "grok": {
                "readings": [
                    {"metric": METRIC_WEEKLY_PCT, "value": 10.0, "confidence": "high"},
                ]
            }
        }
    }
    guarded = monotonic_guard([new_r], prev_no_reset, now)
    assert guarded[0].confidence == CONF_LOW
    assert "dropped from 10.0" in guarded[0].evidence

    # past reset observed in prev -> keep high despite numeric drop
    prev_past_reset = {
        "providers": {
            "grok": {
                "readings": [
                    {"metric": METRIC_WEEKLY_PCT, "value": 10.0},
                    {"metric": METRIC_RESET_AT, "value": now - 100},
                ]
            }
        }
    }
    guarded2 = monotonic_guard([new_r], prev_past_reset, now)
    assert guarded2[0].confidence == CONF_HIGH


def test_build_provider_live_states():
    now = time.time()
    from token_oracle.live.contract import LiveReading

    # no readings, auth -> auth_no_data
    pl = build_provider_live([], authenticated=True, note="x", now=now)
    assert pl.state == STATE_AUTH_NO_DATA
    assert pl.provider == "grok"

    # rate only -> rate_data_only
    rate = LiveReading("grok", METRIC_RATE_WINDOW, 5.0, CONF_HIGH, "x", "e", now)
    pl2 = build_provider_live([rate], True, "", now)
    assert pl2.state == STATE_RATE_DATA_ONLY

    # high weekly -> ok
    hi = LiveReading("grok", METRIC_WEEKLY_PCT, 12.0, CONF_HIGH, "x", "e", now)
    pl3 = build_provider_live([hi], False, "", now)
    assert pl3.state == STATE_OK


def test_unknown_json_yields_nothing():
    now = time.time()
    rs = readings_from_network_json("u", {"version": "1.2.3", "count": 41}, now)
    assert rs == []


# --- regression tests for plan 031 strict allowlist (D4) ---


def test_usage_with_unlisted_numeric_child_yields_nothing():
    """{"usage": {"cpuPercent": 13}} must emit [] (no any-numeric under parent)."""
    now = time.time()
    rs = readings_from_network_json("https://grok.com", {"usage": {"cpuPercent": 13}}, now)
    assert rs == []


def test_bare_used_alone_yields_nothing():
    """{"used": 45} alone -> [] (no bare scalars)."""
    now = time.time()
    rs = readings_from_network_json("u", {"used": 45}, now)
    assert rs == []


def test_bare_limit_alone_yields_nothing():
    """{"limit": 100} alone -> [] (no bare scalars)."""
    now = time.time()
    rs = readings_from_network_json("u", {"limit": 100}, now)
    assert rs == []


def test_used_limit_pair_at_top_yields_nothing_now():
    """Generic {used, limit} is NOT weekly evidence (grok has no such endpoint — plan 038).
    Removing this closes the fabrication hole (plan 040)."""
    now = time.time()
    rs = readings_from_network_json("https://example", {"used": 45, "limit": 100}, now)
    assert rs == []


def test_used_limit_pair_one_level_deep_yields_nothing_now():
    """Nested generic {used, limit} also yields nothing (pair path fully removed)."""
    now = time.time()
    rs = readings_from_network_json("u", {"someQuota": {"used": 45, "limit": 100}}, now)
    assert rs == []


def test_exact_key_one_level_deep_still_works():
    """{"stats": {"weeklyUsagePercent": 10}} -> one weekly 10.0 (exact one-deep allowed)."""
    now = time.time()
    rs = readings_from_network_json("u", {"stats": {"weeklyUsagePercent": 10}}, now)
    weeklies = [r for r in rs if r.metric == METRIC_WEEKLY_PCT]
    assert len(weeklies) == 1
    assert weeklies[0].value == 10.0
    assert weeklies[0].confidence == CONF_HIGH
