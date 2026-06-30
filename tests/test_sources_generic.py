import json

from token_oracle.sources.base import available, get_source


def test_generic_registered():
    assert "generic" in available()


def test_generic_reads_events_file(tmp_path):
    p = tmp_path / "feed.json"
    p.write_text(json.dumps([[10.0, 5], [50.0, 7], [1.0, 99]]))
    src = get_source("generic", {"events_path": str(p)})
    files, events = src.scan({}, now=50.0, window=45.0)
    assert events == [(10.0, 5), (50.0, 7)]


def test_generic_missing_file_is_empty(tmp_path):
    src = get_source("generic", {"events_path": str(tmp_path / "nope.json")})
    files, events = src.scan({}, now=100.0, window=100.0)
    assert events == []
