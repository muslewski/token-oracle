"""Pure tests for claude_extract (no playwright, no network)."""

import json
import pathlib
import time

from token_oracle.live.claude_extract import (
    classify_row,
    distinctness_check,
    five_hour_state_from_rows,
    readings_from_network_json,
    readings_from_rows,
)
from token_oracle.live.contract import (
    CONF_HIGH,
    CONF_LOW,
    CONF_MEDIUM,
    METRIC_FIVE_HOUR_PCT,
    METRIC_FIVE_HOUR_STATE,
    METRIC_MODEL_WEEKLY_PCT,
    METRIC_WEEKLY_PCT,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "live"


def load_json(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_classify_all_models_and_fable_and_session():
    assert classify_row("All models") == (METRIC_WEEKLY_PCT, None)
    assert classify_row("Fable") == (METRIC_MODEL_WEEKLY_PCT, "fable")
    assert classify_row("Current session") == (METRIC_FIVE_HOUR_PCT, None)
    assert classify_row("5h limit") == (METRIC_FIVE_HOUR_PCT, None)
    # nav decoy ignored
    assert classify_row("New chat") is None
    # descriptive text may classify at low level (pct+row collection prevents emission)


def test_rows_yields_weekly_and_model_weekly_distinct_high():
    rows = load_json("claude_rows.json")
    now = time.time()
    rs = readings_from_rows(rows, now)
    week = [r for r in rs if r.metric == METRIC_WEEKLY_PCT]
    model = [r for r in rs if r.metric == METRIC_MODEL_WEEKLY_PCT]
    assert len(week) == 1
    assert week[0].value == 38.0
    assert week[0].confidence == CONF_HIGH
    assert week[0].extractor == "claude.usage_row.aria"
    assert len(model) == 1
    assert model[0].value == 24.0
    assert model[0].model == "fable"
    assert model[0].confidence == CONF_HIGH
    # different rows → both kept (THE Fable-vs-All regression)
    assert week[0].evidence != model[0].evidence


def test_decoy_nav_row_yields_nothing():
    decoy = [
        {
            "valuenow": None,
            "valuemax": None,
            "label": "New chat",
            "text": "Fable — our most capable model",
        }
    ]
    now = time.time()
    rs = readings_from_rows(decoy, now)
    assert rs == []


def test_distinctness_drops_model_when_same_row_evidence():
    now = time.time()
    from token_oracle.live.contract import LiveReading

    w = LiveReading(
        "claude", METRIC_WEEKLY_PCT, 38.0, CONF_HIGH, "claude.usage_row.aria", "All models | 38%", now
    )
    m = LiveReading(
        "claude",
        METRIC_MODEL_WEEKLY_PCT,
        38.0,
        CONF_HIGH,
        "claude.usage_row.aria",
        "All models | 38%",
        now,
        model="fable",
    )
    kept = distinctness_check([w, m])
    assert len(kept) == 1
    assert kept[0].metric == METRIC_WEEKLY_PCT


def test_distinctness_keeps_both_when_equal_values_but_different_rows():
    now = time.time()
    from token_oracle.live.contract import LiveReading

    w = LiveReading("claude", METRIC_WEEKLY_PCT, 38.0, CONF_HIGH, "a", "All models 38%", now)
    m = LiveReading(
        "claude", METRIC_MODEL_WEEKLY_PCT, 38.0, CONF_HIGH, "b", "Fable 38%", now, model="fable"
    )
    kept = distinctness_check([w, m])
    assert len(kept) == 2


def test_five_hour_state_only_from_classified_row_and_regression_whole_page():
    now = time.time()
    sess = [
        {
            "valuenow": None,
            "valuemax": None,
            "label": "Current session",
            "text": "Current session Starts when you send a message",
        }
    ]
    st = five_hour_state_from_rows(sess, now)
    assert st is not None
    assert st.metric == METRIC_FIVE_HOUR_STATE
    assert st.value == "starts_on_first_message"
    assert st.confidence == CONF_HIGH
    assert "claude.session_state" in st.extractor

    # chat-text row containing phrase but not classified as 5h row → no state
    chat = [
        {
            "valuenow": None,
            "valuemax": None,
            "label": "Some chat",
            "text": "when you send a message here",
        }
    ]
    st2 = five_hour_state_from_rows(chat, now)
    assert st2 is None


def test_text_pct_medium_and_no_pct_yields_nothing():
    now = time.time()
    row_with_text_pct = [
        {"valuenow": None, "valuemax": None, "label": "All models", "text": "All models 38% used"}
    ]
    rs = readings_from_rows(row_with_text_pct, now)
    assert len(rs) == 1
    assert rs[0].confidence == CONF_MEDIUM
    assert rs[0].extractor == "claude.usage_row.text"

    row_no_pct = [{"valuenow": None, "valuemax": None, "label": "All models", "text": "All models"}]
    rs2 = readings_from_rows(row_no_pct, now)
    assert rs2 == []


def test_aria_fraction_scales_to_pct():
    now = time.time()
    frac = [{"valuenow": "0.38", "valuemax": None, "label": "All models", "text": ""}]
    rs = readings_from_rows(frac, now)
    assert len(rs) == 1
    assert rs[0].value == 38.0
    assert rs[0].confidence == CONF_HIGH


def test_monotonic_guard_applies_independently_to_model_weekly():
    now = time.time()
    from token_oracle.live.claude_extract import monotonic_guard  # reexported via common
    from token_oracle.live.contract import LiveReading

    new_model = LiveReading(
        "claude", METRIC_MODEL_WEEKLY_PCT, 4.0, CONF_HIGH, "claude.row", "f4%", now, model="fable"
    )
    prev = {
        "providers": {
            "claude": {
                "readings": [
                    {"metric": METRIC_MODEL_WEEKLY_PCT, "value": 10.0, "model": "fable"},
                ]
            }
        }
    }
    guarded = monotonic_guard([new_model], prev, now, provider="claude")
    assert guarded[0].confidence == CONF_LOW
    assert "dropped from 10.0" in guarded[0].evidence

    # weekly drop independent (different key)
    new_week = LiveReading("claude", METRIC_WEEKLY_PCT, 4.0, CONF_HIGH, "c", "all 4%", now)
    prev_week = {
        "providers": {"claude": {"readings": [{"metric": METRIC_WEEKLY_PCT, "value": 10.0}]}}
    }
    g2 = monotonic_guard([new_week], prev_week, now, provider="claude")
    assert g2[0].confidence == CONF_LOW


def test_network_json_is_conservative_noop():
    now = time.time()
    # even plausible keys yield nothing until real fixture + allowlist
    rs = readings_from_network_json(
        "https://claude.ai/api/usage", {"usage": {"limit": 100, "used": 41}}, now
    )
    assert rs == []
    rs2 = readings_from_network_json("u", {"weekly": {"percent": 22}}, now)
    assert rs2 == []
