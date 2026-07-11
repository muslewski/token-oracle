from token_oracle.core import pricing as P


def test_resolve_exact_id_with_date_suffix():
    prices = P.resolve("claude-sonnet-4-5-20250929")
    assert prices is not None
    assert prices["input"] == 3.0
    assert prices["output"] == 15.0


def test_resolve_unknown_model_is_none():
    assert P.resolve("mystery-model") is None
    assert P.resolve(None) is None
    assert P.resolve("") is None


def test_resolve_longest_prefix_wins():
    overrides = {
        "claude": {"input": 1.0, "output": 1.0, "cache_write": 1.0, "cache_read": 1.0},
        "claude-opus-4": {"input": 99.0, "output": 99.0, "cache_write": 99.0, "cache_read": 99.0},
    }
    prices = P.resolve("claude-opus-4-20250101", overrides=overrides)
    assert prices["input"] == 99.0


def test_resolve_overrides_win_over_snapshot():
    overrides = {
        "claude-opus-4": {"input": 1.0, "output": 2.0, "cache_write": 0.0, "cache_read": 0.0}
    }
    prices = P.resolve("claude-opus-4-20250101", overrides=overrides)
    assert prices["input"] == 1.0
    assert prices["output"] == 2.0


def test_event_cost_auto_uses_recorded_cost_usd():
    event = (0.0, 10, "claude-opus-4-20250101", 5, 5, 0, 0, 1.23)
    assert P.event_cost(event, "auto") == 1.23


def test_event_cost_auto_falls_back_to_calculate_when_cost_usd_missing():
    event = (0.0, 10, "claude-sonnet-4-5-20250929", 1_000_000, 0, 0, 0, None)
    assert P.event_cost(event, "auto") == 3.0


def test_event_cost_calculate_ignores_recorded_cost_usd():
    event = (0.0, 10, "claude-sonnet-4-5-20250929", 1_000_000, 0, 0, 0, 999.0)
    assert P.event_cost(event, "calculate") == 3.0


def test_event_cost_calculate_unresolvable_model_is_none():
    event = (0.0, 10, "mystery-model", 5, 5, 0, 0, None)
    assert P.event_cost(event, "calculate") is None


def test_event_cost_display_uses_only_recorded_cost_usd():
    event = (0.0, 10, "claude-opus-4-20250101", 1_000_000, 0, 0, 0, 2.5)
    assert P.event_cost(event, "display") == 2.5


def test_event_cost_display_with_missing_cost_usd_is_none():
    event = (0.0, 10, "claude-opus-4-20250101", 1_000_000, 0, 0, 0, None)
    assert P.event_cost(event, "display") is None


def test_event_cost_off_is_always_none():
    event = (0.0, 10, "claude-opus-4-20250101", 1_000_000, 0, 0, 0, 2.5)
    assert P.event_cost(event, "off") is None


def test_event_cost_computes_all_token_classes():
    # input 1, output 1, cache_create 1, cache_read 1 (all 1 token each) at
    # claude-sonnet-4 prices: input=3, output=15, cache_write=3.75, cache_read=0.3
    event = (0.0, 4, "claude-sonnet-4-5-20250929", 1, 1, 1, 1, None)
    expected = (3.0 + 15.0 + 3.75 + 0.3) / 1_000_000
    assert P.event_cost(event, "calculate") == expected


def test_cost_summary_sums_and_groups_by_model():
    events = [
        (0.0, 10, "claude-opus-4-20250101", 5, 5, 0, 0, 1.0),
        (1.0, 10, "claude-opus-4-20250101", 5, 5, 0, 0, 2.0),
        (2.0, 10, "claude-sonnet-4-5-20250929", 5, 5, 0, 0, 0.5),
    ]
    summary = P.cost_summary(events, "auto")
    assert summary["usd"] == 3.5
    assert summary["by_model"] == {
        "claude-opus-4-20250101": 3.0,
        "claude-sonnet-4-5-20250929": 0.5,
    }
    assert summary["unpriced_tokens"] == 0


def test_cost_summary_counts_unpriced_tokens_for_unknown_model():
    events = [
        (0.0, 10, "claude-opus-4-20250101", 5, 5, 0, 0, 1.0),
        (1.0, 42, "mystery-model", 5, 5, 0, 0, None),
    ]
    summary = P.cost_summary(events, "auto")
    assert summary["usd"] == 1.0
    assert summary["unpriced_tokens"] == 42
    assert summary["by_model"] == {"claude-opus-4-20250101": 1.0}
