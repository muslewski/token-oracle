import json
from oracle.core.config import Config
from oracle.core.contracts import Window
from oracle.core.engine import forecast

def test_forecast_over_generic_source(tmp_path):
    feed = tmp_path / "feed.json"
    now = 100000.0
    feed.write_text(json.dumps([[now - 600.0, 200], [now - 60.0, 50]]))
    cfg = Config(source="generic", source_opts={"events_path": str(feed)},
                 cache_path=str(tmp_path / "cache.json"),
                 windows=[Window("5h", 1000, 18000)])
    out = forecast(now, cfg)
    assert len(out) == 1
    assert out[0].window == "5h"
    assert out[0].used == 250
    assert json.load(open(str(tmp_path / "cache.json")))["lastAggregate"] == now

def test_forecast_empty_on_bad_source(tmp_path):
    cfg = Config(source="does-not-exist", source_opts={},
                 cache_path=str(tmp_path / "c.json"),
                 windows=[Window("5h", 1000, 18000)])
    assert forecast(100.0, cfg) == []
