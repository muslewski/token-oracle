"""Engine write-through: live/header fill rebases Forecast used + end-proj."""

import time

from token_oracle.core.contracts import Forecast
from token_oracle.live.contract import CONF_HIGH, METRIC_MODEL_WEEKLY_PCT, METRIC_WEEKLY_PCT
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


def test_apply_live_fills_improves_end_projection(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
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
    fs = [
        Forecast("weekly", 200, 1000, 40.0, None, 100000.0, False, profile="claude"),
        Forecast("fable", 50, 1000, 20.0, None, 100000.0, False, profile="claude"),
        Forecast("5h", 100, 1000, 30.0, None, 3600.0, False, profile="claude"),
    ]
    out, _degraded = apply_live_fills(fs, now, snapshot=snap)
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
    out, _ = apply_live_fills(fs, time.time(), snapshot={})
    assert out[0].used == 200
    assert out[0].projected_pct == 40.0


# --- plan 063 T4: trusted single-authority write-through (I1, I3, I5) ---
from token_oracle.live.contract import CONF_MEDIUM  # noqa: E402


def _weekly_snap(now, value, extractor="web", fetched_at=None, confidence=CONF_HIGH):
    return {
        "providers": {
            "claude": {
                "provider": "claude",
                "state": "ok",
                "fetched_at": now,
                "readings": [
                    {
                        "provider": "claude",
                        "metric": METRIC_WEEKLY_PCT,
                        "value": value,
                        "confidence": confidence,
                        "extractor": extractor,
                        "evidence": "e",
                        "fetched_at": now if fetched_at is None else fetched_at,
                        "model": None,
                    }
                ],
            }
        }
    }


def test_i1_trusted_reading_anchors_used(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    now = time.time()
    f = Forecast("weekly", 100, 1000, 23.0, None, 3600.0, False, profile="claude")
    out, degraded = apply_live_fills([f], now, snapshot=_weekly_snap(now, 60.0))
    assert out[0].used == 600 and degraded is False  # 60% of cap, server anchors


def test_i3_retained_reading_not_applied(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    now = time.time()
    f = Forecast("weekly", 100, 1000, 23.0, None, 3600.0, False, profile="claude")
    snap = _weekly_snap(now, 90.0, extractor="web+retained")  # retained → display-only
    out, _ = apply_live_fills([f], now, snapshot=snap)
    assert out[0].used == 100  # unchanged; retained never touches math


def test_i3_stale_reading_not_applied(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    now = time.time()
    f = Forecast("weekly", 100, 1000, 23.0, None, 3600.0, False, profile="claude")
    snap = _weekly_snap(now, 90.0, fetched_at=now - 4000.0)  # > FRESH_TTL (600s)
    out, _ = apply_live_fills([f], now, snapshot=snap)
    assert out[0].used == 100  # stale → not applied to math


def test_i3_low_confidence_not_applied(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    now = time.time()
    f = Forecast("weekly", 100, 1000, 23.0, None, 3600.0, False, profile="claude")
    snap = _weekly_snap(now, 90.0, confidence=CONF_MEDIUM)
    out, _ = apply_live_fills([f], now, snapshot=snap)
    assert out[0].used == 100


def test_i5_idle_forecast_activated_by_trusted_usage(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    now = time.time()
    idle_f = Forecast("weekly", 0, 1000, 0.0, None, 3600.0, True, profile="claude")
    out, _ = apply_live_fills([idle_f], now, snapshot=_weekly_snap(now, 40.0))
    assert out[0].idle is False and out[0].used == 400


def test_newest_wins_on_duplicate_readings(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
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
                        "value": 99.0,
                        "confidence": CONF_HIGH,
                        "extractor": "web",
                        "evidence": "e",
                        "fetched_at": now - 100.0,
                        "model": None,
                    },
                    {
                        "provider": "claude",
                        "metric": METRIC_WEEKLY_PCT,
                        "value": 55.0,
                        "confidence": CONF_HIGH,
                        "extractor": "web",
                        "evidence": "e",
                        "fetched_at": now,
                        "model": None,
                    },
                ],
            }
        }
    }
    f = Forecast("weekly", 100, 1000, 23.0, None, 3600.0, False, profile="claude")
    out, _ = apply_live_fills([f], now, snapshot=snap)
    assert out[0].used == 550  # newest (55%) wins, not the older 99%


def test_degraded_flag_on_store_error(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    now = time.time()

    def _boom():
        raise RuntimeError("store dead")

    monkeypatch.setattr("token_oracle.live.fill.load_snapshot", _boom)
    f = Forecast("weekly", 100, 1000, 23.0, None, 3600.0, False, profile="claude")
    out, degraded = apply_live_fills([f], now)  # snapshot=None → load_snapshot → boom
    assert degraded is True and out == [f]  # never blanks, but signals


def test_i1_header_weekly_fresh_anchors(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    now = time.time()
    monkeypatch.setattr(
        "token_oracle.core.ratelimits.weekly",
        lambda n=None: {
            "used_percentage": 70.0,
            "resets_at": now + 1e5,
            "observed_at": now - 10.0,
            "stale": False,
        },
    )
    f = Forecast("weekly", 100, 1000, 23.0, None, 3600.0, False, profile="claude")
    out, _ = apply_live_fills([f], now, snapshot={})
    assert out[0].used == 700  # fresh header anchors the math


def test_i3_header_weekly_stale_not_applied(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    now = time.time()
    monkeypatch.setattr(
        "token_oracle.core.ratelimits.weekly",
        lambda n=None: {
            "used_percentage": 88.0,
            "resets_at": now + 1e5,
            "observed_at": now - 4000.0,
            "stale": False,
        },
    )
    f = Forecast("weekly", 100, 1000, 23.0, None, 3600.0, False, profile="claude")
    out, _ = apply_live_fills([f], now, snapshot={})  # header 4000s old > FRESH_TTL
    assert out[0].used == 100  # stale header stays display-only, not math
