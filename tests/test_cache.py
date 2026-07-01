import os

from token_oracle.core import cache as C


def test_load_missing_returns_default(tmp_path):
    c = C.load_cache(str(tmp_path / "nope.json"))
    assert c == {"files": {}, "lastAggregate": 0, "profile": []}


def test_save_then_load_roundtrip(tmp_path):
    p = str(tmp_path / "sub" / "cache.json")  # parent dir created
    c = {"files": {"a": {"events": [[1.0, 5]]}}, "lastAggregate": 99, "profile": [0.1]}
    C.save_cache(c, p)
    assert os.path.isfile(p)
    assert C.load_cache(p) == c


def test_save_leaves_no_tmp_files(tmp_path):
    p = str(tmp_path / "cache.json")
    C.save_cache({"files": {}, "lastAggregate": 0, "profile": []}, p)
    assert os.listdir(tmp_path) == ["cache.json"]


def test_save_failure_is_silent_and_leaves_no_tmp(tmp_path):
    (tmp_path / "blocker").write_text("file, not a dir")
    p = str(tmp_path / "blocker" / "cache.json")
    C.save_cache({"files": {}, "lastAggregate": 0, "profile": []}, p)
    assert [e.name for e in tmp_path.iterdir()] == ["blocker"]


def test_load_corrupt_returns_default(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{ not json")
    assert C.load_cache(str(p))["files"] == {}


def test_collect_and_window():
    files = {"f": {"events": [[10.0, 1], [50.0, 2], [5.0, 9]]}}
    assert C.collect_events(files, cutoff=10.0) == [(10.0, 1), (50.0, 2)]
    cache = {"files": files}
    assert C.events_from_cache(cache, now=50.0, window=40.0) == [(10.0, 1), (50.0, 2)]
