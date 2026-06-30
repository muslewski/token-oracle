from token_oracle.core import timeutil as T


def test_parse_ts_z_suffix():
    assert T.parse_ts("1970-01-01T00:00:00Z") == 0.0
    assert T.parse_ts(None) is None
    assert T.parse_ts("not-a-date") is None


def test_bucket_key_range():
    assert 0 <= T.bucket_key(0.0) <= 167


def test_fmt_tokens():
    assert T.fmt_tokens(1_500_000) == "1.5M"
    assert T.fmt_tokens(12_000) == "12k"


def test_fmt_hms_and_dh():
    assert T.fmt_hms(3 * 3600 + 46 * 60) == "3:46"
    assert T.fmt_dh(5 * 86400 + 18 * 3600) == "5d18h"


def test_fmt_dur():
    assert T.fmt_dur(59) == "59s"
    assert T.fmt_dur(80) == "1m20s"
    assert T.fmt_dur(12 * 60) == "12m"
    assert T.fmt_dur(3900) == "1h05m"


def test_fmt_dh_long():
    assert T.fmt_dh_long(5 * 86400 + 18 * 3600) == "5 days 18 hours"
    assert T.fmt_dh_long(3600) == "1 hour"
