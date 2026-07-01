import json

from token_oracle.core.contracts import Forecast
from token_oracle.snapshot.writer import (
    SCHEMA_VERSION,
    build_snapshot,
    forecast_to_dict,
    write_snapshot,
)


def test_schema_shape_is_stable():
    f = Forecast("5h", 100, 1000, 42.0, 1234.5, 3600.0, False, 0.9)
    d = forecast_to_dict(f)
    assert set(d) == {
        "window",
        "used",
        "cap",
        "projected_pct",
        "eta_to_cap_secs",
        "reset_in_secs",
        "idle",
        "confidence",
    }


def test_build_snapshot_envelope():
    snap = build_snapshot([Forecast("5h", 1, 2, 3.0, None, 4.0, False)], now=10.0)
    assert snap["schema"] == SCHEMA_VERSION
    assert snap["generated_at"] == 10.0
    assert len(snap["windows"]) == 1


def test_write_snapshot_roundtrip(tmp_path):
    p = str(tmp_path / "d" / "forecast.json")
    result = write_snapshot([Forecast("wk", 5, 9, 55.0, None, 600.0, False)], 7.0, p)
    assert result == p
    snap = json.load(open(p))
    assert snap["windows"][0]["window"] == "wk"


def test_write_snapshot_returns_none_on_failure(tmp_path):
    (tmp_path / "blocker").write_text("file, not a dir")
    p = str(tmp_path / "blocker" / "forecast.json")
    result = write_snapshot([Forecast("wk", 5, 9, 55.0, None, 600.0, False)], 7.0, p)
    assert result is None
    assert [e.name for e in tmp_path.iterdir()] == ["blocker"]
