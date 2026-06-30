import json

from token_oracle.core.config import Config
from token_oracle.core.contracts import Window
from token_oracle.core.engine import forecast


def test_forecast_over_generic_source(tmp_path):
    feed = tmp_path / "feed.json"
    now = 100000.0
    feed.write_text(json.dumps([[now - 600.0, 200], [now - 60.0, 50]]))
    cfg = Config(
        source="generic",
        source_opts={"events_path": str(feed)},
        cache_path=str(tmp_path / "cache.json"),
        windows=[Window("5h", 1000, 18000)],
    )
    out = forecast(now, cfg)
    assert len(out) == 1
    assert out[0].window == "5h"
    assert out[0].used == 250
    assert json.load(open(str(tmp_path / "cache.json")))["lastAggregate"] == now


def test_forecast_empty_on_bad_source(tmp_path):
    cfg = Config(
        source="does-not-exist",
        source_opts={},
        cache_path=str(tmp_path / "c.json"),
        windows=[Window("5h", 1000, 18000)],
    )
    assert forecast(100.0, cfg) == []


def test_forecast_warm_cache_replays_generic(tmp_path):
    feed = tmp_path / "feed.json"
    now = 100000.0
    feed.write_text(json.dumps([[now - 600.0, 200], [now - 60.0, 50]]))
    cfg = Config(
        source="generic",
        source_opts={"events_path": str(feed)},
        cache_path=str(tmp_path / "cache.json"),
        windows=[Window("5h", 1000, 18000)],
    )
    out1 = forecast(now, cfg)  # cold scan
    assert out1[0].used == 250
    out2 = forecast(now + 5.0, cfg)  # warm (within 30s) must replay, not idle
    assert out2[0].used == 250
    assert out2[0].idle is False
