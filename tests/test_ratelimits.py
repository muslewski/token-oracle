"""Hermetic unit tests for core/ratelimits.py.

Each test uses an explicit `path=` (or XDG_DATA_HOME + default_path) pointing
at a temp file under tmp_path. NEVER touches the real machine snapshot.
"""

from token_oracle.core import ratelimits as RL


def _tmp_path(tmp_path, name="rl.json"):
    return str(tmp_path / name)


def test_ingest_and_read_roundtrip(tmp_path):
    p = _tmp_path(tmp_path)
    now = 1000.0
    RL.ingest(
        {
            "five_hour": {"used_percentage": 2.0, "resets_at": now + 3600},
            "seven_day": {"used_percentage": 33.0, "resets_at": now + 86400},
        },
        now=now,
        path=p,
    )
    fh = RL.five_hour(now, p)
    wk = RL.weekly(now, p)
    assert fh is not None and fh["used_percentage"] == 2.0 and fh["stale"] is False
    assert wk is not None and wk["used_percentage"] == 33.0 and wk["stale"] is False
    assert abs(fh["secs_to_reset"] - 3600) < 0.1


def test_monotonic_same_window_keeps_max(tmp_path):
    p = _tmp_path(tmp_path)
    now = 2000.0
    resets = now + 3600
    RL.ingest({"five_hour": {"used_percentage": 2.0, "resets_at": resets}}, now=now, path=p)
    RL.ingest({"five_hour": {"used_percentage": 1.0, "resets_at": resets}}, now=now + 10, path=p)
    fh = RL.five_hour(now, p)
    assert fh["used_percentage"] == 2.0  # kept the max


def test_new_window_replaces_on_forward_reset_jump(tmp_path):
    p = _tmp_path(tmp_path)
    now1 = 3000.0
    r1 = now1 + 3600
    RL.ingest({"five_hour": {"used_percentage": 10.0, "resets_at": r1}}, now=now1, path=p)
    # forward jump > half window => reset
    now2 = now1 + 10
    r2 = r1 + 5 * 3600 + 10
    RL.ingest({"five_hour": {"used_percentage": 3.0, "resets_at": r2}}, now=now2, path=p)
    fh = RL.five_hour(now2, p)
    assert fh["used_percentage"] == 3.0
    assert fh["resets_at"] == r2


def test_stale_when_reset_in_past(tmp_path):
    p = _tmp_path(tmp_path)
    now_ingest = 4000.0
    resets_past = now_ingest - 100
    RL.ingest(
        {"five_hour": {"used_percentage": 50.0, "resets_at": resets_past}},
        now=now_ingest,
        path=p,
    )
    # read at a later now
    now_read = now_ingest + 10
    fh = RL.five_hour(now_read, p)
    assert fh is not None
    assert fh["stale"] is True
    assert fh["used_percentage"] is None
    # rolled forward
    assert fh["resets_at"] > now_read


def test_never_raises_on_garbage(tmp_path):
    p = _tmp_path(tmp_path)
    # bad inputs must not raise
    assert RL.ingest("not a dict", now=1000.0, path=p) == {} or isinstance(
        RL.ingest("not a dict", now=1000.0, path=p), dict
    )
    assert RL.ingest({"five_hour": {}}, now=1000.0, path=p) is not None
    # missing file read
    missing = str(tmp_path / "nope" / "rl.json")
    assert RL.five_hour(1000.0, missing) is None
    # bad data in file
    badp = _tmp_path(tmp_path, "bad.json")
    with open(badp, "w") as f:
        f.write("{not json")
    assert RL.weekly(1000.0, badp) is None


def test_public_api_accepts_explicit_path_and_default(tmp_path, monkeypatch):
    # ensure path= works and does not leak to real default
    p = _tmp_path(tmp_path)
    now = 5000.0
    RL.ingest({"five_hour": {"used_percentage": 99.0, "resets_at": now + 100}}, now=now, path=p)
    assert RL.five_hour(now, path=p)["used_percentage"] == 99.0
    # default_path under different XDG must not see it
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "other"))
    assert RL.five_hour(now) is None or RL.five_hour(now).get("used_percentage") != 99.0
