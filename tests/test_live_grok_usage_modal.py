"""Tests for grok's ?_s=usage modal extraction (plan 038).

The weekly usage cap is plain text in the modal (no aria bars, no clean JSON
endpoint), so extraction is text-anchored on the fixed UI labels. Fixture is the
real captured modal text.
"""

from token_oracle.live.contract import (
    METRIC_MODEL_WEEKLY_PCT,
    METRIC_RESET_AT,
    METRIC_WEEKLY_PCT,
)
from token_oracle.live.extract_common import build_provider_live
from token_oracle.live.grok_extract import (
    parse_absolute_reset,
    readings_from_usage_modal,
)
from token_oracle.live.overlay import overlay_cells

# Real captured modal text.
FIXTURE = (
    "Usage Weekly SuperGrok Heavy Limit 23% used "
    "Resets July 17, 2026 at 7:46 AM Grok Build 22% API 1%"
)
NOW = 1783000000.0  # 2026-07-02, before the Jul 17 reset in the fixture


def _by_metric(readings, metric, model=None):
    return [r for r in readings if r.metric == metric and (model is None or r.model == model)]


def test_weekly_pct_extracted_high_conf():
    rs = readings_from_usage_modal(FIXTURE, NOW)
    weekly = _by_metric(rs, METRIC_WEEKLY_PCT)
    assert len(weekly) == 1
    r = weekly[0]
    assert r.value == 23.0
    assert r.confidence == "high"
    assert r.extractor == "grok.usage_modal.text"
    assert r.provider == "grok"


def test_reset_at_absolute_date():
    rs = readings_from_usage_modal(FIXTURE, NOW)
    reset = _by_metric(rs, METRIC_RESET_AT)
    assert len(reset) == 1
    assert isinstance(reset[0].value, float)
    assert NOW < reset[0].value < NOW + 40 * 86400


def test_parse_absolute_reset_direct():
    r = parse_absolute_reset("Resets July 17, 2026 at 7:46 AM", NOW)
    assert r is not None
    assert r.metric == METRIC_RESET_AT
    assert r.confidence == "high"
    assert parse_absolute_reset("no reset here", NOW) is None
    # A reset far in the past / outside the 40-day window is rejected.
    assert parse_absolute_reset("Resets January 1, 2020 at 1:00 AM", NOW) is None


def test_bare_percent_without_label_emits_nothing():
    # 45% with no "Weekly ... Limit" anchor must not become a weekly reading.
    rs = readings_from_usage_modal("Some panel showing 45% of something", NOW)
    assert _by_metric(rs, METRIC_WEEKLY_PCT) == []


def test_grok_build_and_api_breakdown():
    rs = readings_from_usage_modal(FIXTURE, NOW)
    gb = _by_metric(rs, METRIC_MODEL_WEEKLY_PCT, model="grok_build")
    api = _by_metric(rs, METRIC_MODEL_WEEKLY_PCT, model="api")
    assert len(gb) == 1 and gb[0].value == 22.0 and gb[0].confidence == "high"
    assert len(api) == 1 and api[0].value == 1.0


def test_api_not_emitted_without_grok_build():
    # API row only trusted when Grok Build is also present (they always co-render).
    rs = readings_from_usage_modal("Weekly SuperGrok Heavy Limit 23% used API 1%", NOW)
    assert _by_metric(rs, METRIC_MODEL_WEEKLY_PCT, model="api") == []


def test_provider_state_ok_from_modal():
    rs = readings_from_usage_modal(FIXTURE, NOW)
    pl = build_provider_live(rs, authenticated=True, note="", now=NOW, provider="grok")
    assert pl.state == "ok"


def test_overlay_maps_weekly_and_grok_build_cells():
    rs = readings_from_usage_modal(FIXTURE, NOW)
    snapshot = {
        "providers": {
            "grok": {
                "state": "ok",
                "fetched_at": NOW,
                "readings": [
                    {
                        "metric": r.metric,
                        "value": r.value,
                        "confidence": r.confidence,
                        "extractor": r.extractor,
                        "evidence": r.evidence,
                        "fetched_at": r.fetched_at,
                        "model": r.model,
                    }
                    for r in rs
                ],
            }
        }
    }
    cells = overlay_cells([], snapshot, now=NOW, weekly_header=None)
    assert cells[("grok", "weekly")].pct == 23.0
    assert cells[("grok", "grok_build")].pct == 22.0
