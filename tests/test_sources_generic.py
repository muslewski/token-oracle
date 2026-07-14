import json

import pytest

from token_oracle.sources.base import available, get_source


def test_generic_registered():
    assert "generic" in available()


def test_generic_reads_events_file(tmp_path):
    p = tmp_path / "feed.json"
    p.write_text(json.dumps([[10.0, 5], [50.0, 7], [1.0, 99]]))
    src = get_source("generic", {"events_path": str(p)})
    files, events = src.scan({}, now=50.0, window=45.0)
    assert [(e[0], e[1]) for e in events] == [(10.0, 5), (50.0, 7)]


def test_generic_missing_file_is_empty(tmp_path):
    src = get_source("generic", {"events_path": str(tmp_path / "nope.json")})
    files, events = src.scan({}, now=100.0, window=100.0)
    assert events == []


def test_generic_reads_mixed_width_rows(tmp_path):
    p = tmp_path / "feed.json"
    p.write_text(
        json.dumps(
            [
                [10.0, 5],
                [20.0, 7, "claude-sonnet-4-5", 3, 4, 0, 0, 0.01],
            ]
        )
    )
    src = get_source("generic", {"events_path": str(p)})
    files, events = src.scan({}, now=100.0, window=100.0)
    assert events == [
        (10.0, 5, None, 0, 0, 0, 0, None),
        (20.0, 7, "claude-sonnet-4-5", 3, 4, 0, 0, 0.01),
    ]


# --- plan 013: entry-point source discovery ---


class _FakeEp:
    name = "fake_src"

    @staticmethod
    def load():
        from token_oracle.sources.base import register

        @register("fake_src")
        class FakeSrc:
            def __init__(self, opts):
                self.opts = opts

            def scan(self, files_state, now, window):
                return files_state, []

        return FakeSrc


def test_entry_point_source_loads_on_demand(monkeypatch):
    from token_oracle.sources import base as B

    monkeypatch.setattr(
        "importlib.metadata.entry_points",
        lambda **kw: [_FakeEp] if kw.get("group") == B._EP_GROUP else [],
    )
    # ensure not pre-registered
    B._REGISTRY.pop("fake_src", None)
    try:
        src = get_source("fake_src", {"x": 1})
        assert src.opts == {"x": 1}
        assert "fake_src" in available()
    finally:
        B._REGISTRY.pop("fake_src", None)


def test_available_lists_entry_points_without_loading(monkeypatch):
    from token_oracle.sources import base as B

    class BoomEp:
        name = "listed_only"

        @staticmethod
        def load():
            raise AssertionError("must not load")

    monkeypatch.setattr(
        "importlib.metadata.entry_points",
        lambda **kw: [BoomEp] if kw.get("group") == B._EP_GROUP else [],
    )
    names = available()
    assert "listed_only" in names
    assert "generic" in names


def test_broken_entry_point_falls_through_to_keyerror(monkeypatch):
    from token_oracle.sources import base as B

    class BrokenEp:
        name = "broken"

        @staticmethod
        def load():
            raise ImportError("nope")

    monkeypatch.setattr(
        "importlib.metadata.entry_points",
        lambda **kw: [BrokenEp] if kw.get("group") == B._EP_GROUP else [],
    )
    B._REGISTRY.pop("broken", None)
    try:
        with pytest.raises(KeyError) as ei:
            get_source("broken")
        assert "broken" in str(ei.value)
    finally:
        B._REGISTRY.pop("broken", None)


def test_unknown_source_still_keyerror():
    with pytest.raises(KeyError) as ei:
        get_source("nope-not-real")
    assert "nope-not-real" in str(ei.value)
