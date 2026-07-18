"""Engine write-through: live/header fill rebases Forecast used + end-proj."""
import time

from token_oracle.core.contracts import Forecast
from token_oracle.live.contract import CONF_HIGH, METRIC_WEEKLY_PCT, METRIC_MODEL_WEEKLY_PCT
from token_oracle.live.fill import apply_live_fills, fill_pct_for_window


def test_fill_pct_from_snapshot_weekly():
    now = time.time()
    snap = {
        "providers": {
            "claude": {
                "provider": "claude",
                "state": "ok",
                "fetched_at": now,
                "readings": [
                    {
                        "provider": "claude",
                        "metric": METRIC_WEEKLY_PCT,
                        "value": 93.0,
                        "confidence": CONF_HIGH,
                        "extractor": "claude.test",
                        "evidence": "e",
                        "fetched_at": now,
                        "model": None,
                    }
                ],
            }
        }
    }
    # no header → web
    assert fill_pct_for_window("claude", "weekly", snap, now) == 93.0
    assert fill_pct_for_window("claude", "fable", snap, now) is None


def test_apply_live_fills_improves_end_projection(monkeypatch):
    now = time.time()
    snap = {
        "providers": {
            "claude": {
                "provider": "claude",
                "state": "ok",
                "fetched_at": now,
                "readings": [
                    {
                        "provider": "claude",
                        "metric": METRIC_WEEKLY_PCT,
                        "value": 90.0,
                        "confidence": CONF_HIGH,
                        "extractor": "web",
                        "evidence": "e",
                        "fetched_at": now,
                        "model": None,
                    },
                    {
                        "provider": "claude",
                        "metric": METRIC_MODEL_WEEKLY_PCT,
                        "value": 99.0,
                        "confidence": CONF_HIGH,
                        "extractor": "web",
                        "evidence": "e",
                        "fetched_at": now,
                        "model": "fable",
                    },
                ],
            }
        }
    }
    # hermetic: no real header ratelimits
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/token-oracle-fill-test-empty")
    fs = [
        Forecast("weekly", 200, 1000, 40.0, None, 100000.0, False, profile="claude"),
        Forecast("fable", 50, 1000, 20.0, None, 100000.0, False, profile="claude"),
        Forecast("5h", 100, 1000, 30.0, None, 3600.0, False, profile="claude"),
    ]
    out = apply_live_fills(fs, now, snapshot=snap)
    wk = next(f for f in out if f.window == "weekly")
    fb = next(f for f in out if f.window == "fable")
    h5 = next(f for f in out if f.window == "5h")
    assert wk.used == 900  # 90% of 1000
    # residual 200 → end 110%
    assert abs(wk.projected_pct - 110.0) < 0.1
    assert fb.used == 990
    assert fb.projected_pct >= 99.0
    # 5h unchanged without header
    assert h5.used == 100


def test_apply_live_fills_no_snapshot_noop(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    fs = [Forecast("weekly", 200, 1000, 40.0, None, 1000.0, False, profile="claude")]
    out = apply_live_fills(fs, time.time(), snapshot={})
    assert out[0].used == 200
    assert out[0].projected_pct == 40.0
