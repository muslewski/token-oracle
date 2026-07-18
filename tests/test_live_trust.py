from token_oracle.live.trust import is_trusted_for_math, newest_first
from token_oracle.live.contract import CONF_HIGH, CONF_MEDIUM, STATE_OK, STATE_AUTH_NO_DATA


def _kw(**o):
    base = dict(state=STATE_OK, confidence=CONF_HIGH, age_secs=10.0, extractor="modal")
    base.update(o)
    return base


def test_trusted_fresh_high_ok():
    assert is_trusted_for_math(**_kw()) is True


def test_untrusted_stale():
    assert is_trusted_for_math(**_kw(age_secs=601.0)) is False


def test_untrusted_retained():
    assert is_trusted_for_math(**_kw(extractor="modal+retained")) is False


def test_untrusted_low_conf():
    assert is_trusted_for_math(**_kw(confidence=CONF_MEDIUM)) is False


def test_untrusted_bad_state():
    assert is_trusted_for_math(**_kw(state=STATE_AUTH_NO_DATA)) is False


def test_untrusted_missing_age():
    assert is_trusted_for_math(**_kw(age_secs=None)) is False


def test_newest_first_orders_by_fetched_at():
    rs = [{"v": 1, "fetched_at": 100.0}, {"v": 2, "fetched_at": 300.0}, {"v": 3, "fetched_at": 200.0}]
    assert [r["v"] for r in newest_first(rs)] == [2, 3, 1]


def test_newest_first_missing_ts_sinks():
    rs = [{"v": 1}, {"v": 2, "fetched_at": 50.0}]
    assert [r["v"] for r in newest_first(rs)] == [2, 1]
