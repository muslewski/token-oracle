from token_oracle.core.events import N_FIELDS, as_pairs, normalize


def test_normalize_pads_2_element_list():
    e = normalize([1.0, 5])
    assert len(e) == N_FIELDS
    assert e == (1.0, 5, None, 0, 0, 0, 0, None)


def test_normalize_round_trips_8_element_list():
    e = normalize([2.0, 3, "claude-sonnet-4-5", 1, 1, 1, 0, 0.05])
    assert e == (2.0, 3, "claude-sonnet-4-5", 1, 1, 1, 0, 0.05)


def test_normalize_7_element_defaults_cost_to_none():
    e = normalize([3.0, 4, "m", 1, 2, 0, 1])
    assert len(e) == N_FIELDS
    assert e == (3.0, 4, "m", 1, 2, 0, 1, None)


def test_normalize_never_raises_on_well_typed_short_input():
    e = normalize((10.0, 20))
    assert e == (10.0, 20, None, 0, 0, 0, 0, None)


def test_as_pairs_on_mixed_2_and_8_element_events():
    e1 = normalize([1.0, 5])
    e2 = (2.0, 3, "m", 1, 1, 1, 0, None)
    assert as_pairs([e1, e2]) == [(1.0, 5), (2.0, 3)]
