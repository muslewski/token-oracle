import time

from token_oracle.live.contract import (
    CONF_HIGH,
    CONF_LOW,
    METRIC_FIVE_HOUR_PCT,
    METRIC_WEEKLY_PCT,
    LiveReading,
    ProviderLive,
    live_reading_from_dict,
    live_reading_to_dict,
    provider_live_from_dict,
    provider_live_to_dict,
)
from token_oracle.live.store import load_snapshot, save_snapshot


def test_live_reading_roundtrip_dict():
    r = LiveReading(
        provider="claude",
        metric=METRIC_FIVE_HOUR_PCT,
        value=42.5,
        confidence=CONF_HIGH,
        extractor="claude.test",
        evidence="foo bar baz",
        fetched_at=1234567890.0,
        model=None,
    )
    d = live_reading_to_dict(r)
    r2 = live_reading_from_dict(d)
    assert r2.provider == "claude"
    assert r2.value == 42.5
    assert r2.confidence == CONF_HIGH


def test_provider_live_roundtrip_dict():
    r1 = LiveReading("grok", METRIC_WEEKLY_PCT, 13.0, CONF_LOW, "grok.legacy", "overall_pct", 100.0)
    r2 = LiveReading("grok", "rate_window", 75.0, CONF_HIGH, "grok.legacy", "queries", 100.0)
    pl = ProviderLive("grok", "ok", [r1, r2], fetched_at=100.0, note="final_url=...")
    d = provider_live_to_dict(pl)
    pl2 = provider_live_from_dict(d)
    assert pl2.provider == "grok"
    assert pl2.state == "ok"
    assert len(pl2.readings) == 2
    assert pl2.readings[0].metric == METRIC_WEEKLY_PCT
    assert pl2.readings[1].confidence == CONF_HIGH


def test_save_load_snapshot_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    now = time.time()
    r = LiveReading("claude", METRIC_WEEKLY_PCT, 55.0, CONF_LOW, "t", "ev", now)
    pl = ProviderLive("claude", "authenticated_no_data", [r], fetched_at=now)
    p = save_snapshot({"claude": pl})
    assert p is not None
    data = load_snapshot()
    assert data is not None
    assert data["version"] == 1
    assert "claude" in data["providers"]
    assert data["providers"]["claude"]["state"] == "authenticated_no_data"


def test_load_snapshot_corrupt_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    p = str(tmp_path / "token-oracle" / "live.json")
    import os

    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write("{not valid json[")
    assert load_snapshot() is None
