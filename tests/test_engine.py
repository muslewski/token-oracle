import json

from token_oracle.core.config import Config
from token_oracle.core.contracts import Forecast, Window
from token_oracle.core.engine import detect_resets, forecast, multi_forecast


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


def test_forecast_legacy_cache_events_match_full_events(tmp_path):
    """A cache file with old 2-element [ts, tok] events must load and forecast
    to the same numbers as an equivalent cache with full 8-field events —
    normalize() bridges the gap without a cache rebuild."""
    now = 100000.0
    windows = [Window("5h", 1000, 18000)]

    legacy_cache = tmp_path / "legacy.json"
    legacy_cache.write_text(
        json.dumps(
            {
                "files": {},
                "lastAggregate": now - 1.0,  # within AGGREGATE_INTERVAL -> warm path
                "profile": [],
                "events": [[now - 600.0, 200], [now - 60.0, 50]],
            }
        )
    )
    cfg_legacy = Config(
        source="generic",
        source_opts={"events_path": str(tmp_path / "unused.json")},
        cache_path=str(legacy_cache),
        windows=windows,
    )
    out_legacy = forecast(now, cfg_legacy)

    full_cache = tmp_path / "full.json"
    full_cache.write_text(
        json.dumps(
            {
                "files": {},
                "lastAggregate": now - 1.0,
                "profile": [],
                "events": [
                    [now - 600.0, 200, "claude-sonnet-4-5", 100, 100, 0, 0, None],
                    [now - 60.0, 50, "claude-sonnet-4-5", 50, 0, 0, 0, None],
                ],
            }
        )
    )
    cfg_full = Config(
        source="generic",
        source_opts={"events_path": str(tmp_path / "unused.json")},
        cache_path=str(full_cache),
        windows=windows,
    )
    out_full = forecast(now, cfg_full)

    assert out_legacy == out_full
    assert out_legacy[0].used == 250


def test_forecast_recovers_from_corrupt_cache(tmp_path):
    feed = tmp_path / "feed.json"
    now = 100000.0
    feed.write_text(json.dumps([[now - 600.0, 200], [now - 60.0, 50]]))
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("{ not json")
    cfg = Config(
        source="generic",
        source_opts={"events_path": str(feed)},
        cache_path=str(cache_path),
        windows=[Window("5h", 1000, 18000)],
    )
    out = forecast(now, cfg)
    assert len(out) == 1
    assert out[0].used == 250
    # cache falls back to default and gets rewritten with valid JSON


def test_forecast_multi_profiles(tmp_path):
    feed1 = tmp_path / "c.json"
    feed2 = tmp_path / "g.json"
    now = 100000.0
    feed1.write_text(json.dumps([[now - 100, 100]]))
    feed2.write_text(json.dumps([[now - 50, 200]]))
    cfg = Config(
        source="generic",
        cache_path=str(tmp_path / "c.json"),
        windows=[Window("wk", 1000, 604800)],
        profiles={
            "claude": {
                "source": "generic",
                "source_opts": {"events_path": str(feed1)},
                "windows": [{"name": "5h", "cap": 1000, "period_secs": 18000}],
            },
            "grok": {
                "source": "generic",
                "source_opts": {"events_path": str(feed2)},
                "windows": [{"name": "weekly", "cap": 10000, "period_secs": 604800}],
            },
        },
    )
    out = forecast(now, cfg)
    assert len(out) == 2
    profiles = {f.profile for f in out}
    assert profiles == {"claude", "grok"}
    ws = {f.window: f.used for f in out}
    assert ws.get("5h") == 100
    assert ws.get("weekly") == 200


def test_multi_forecast_skips_save_when_aggregate_fresh(monkeypatch, tmp_path):
    """Warm multi-profile path must not rewrite the cache every call.

    Root cause (dash lag): multi-profile forecast always set changed=True and
    save_cache()'d the whole cache (12MB+ / ~5s on real machines) even when
    AGGREGATE_INTERVAL had not elapsed. Single-source path already gates save
    on do_agg; multi must match.
    """
    from token_oracle.core import engine as ENG

    now = 100_000.0
    feed1 = tmp_path / "c.json"
    feed2 = tmp_path / "g.json"
    feed1.write_text(json.dumps([[now - 100, 100]]))
    feed2.write_text(json.dumps([[now - 50, 200]]))
    cache_path = tmp_path / "cache.json"
    # Pre-warm: both profiles already aggregated at `now` (within interval).
    warm = {
        "lastAggregate": now,
        "files": {},
        "events": [],
        "profile": [],
        "profiles": {
            "claude": {
                "files": {},
                "events": [[now - 100, 100, "", 0, 0, 0, 0, None]],
                "profile": [],
                "lastAggregate": now,
            },
            "grok": {
                "files": {},
                "events": [[now - 50, 200, "", 0, 0, 0, 0, None]],
                "profile": [],
                "lastAggregate": now,
            },
        },
    }
    cache_path.write_text(json.dumps(warm))
    cfg = Config(
        source="generic",
        cache_path=str(cache_path),
        windows=[Window("wk", 1000, 604800)],
        profiles={
            "claude": {
                "source": "generic",
                "source_opts": {"events_path": str(feed1)},
                "windows": [{"name": "5h", "cap": 1000, "period_secs": 18000}],
            },
            "grok": {
                "source": "generic",
                "source_opts": {"events_path": str(feed2)},
                "windows": [{"name": "weekly", "cap": 10000, "period_secs": 604800}],
            },
        },
    )
    saves = {"n": 0}
    real_save = ENG.save_cache

    def counting_save(cache, path):
        saves["n"] += 1
        return real_save(cache, path)

    monkeypatch.setattr(ENG, "save_cache", counting_save)
    out = forecast(now + 1.0, cfg)  # still within AGGREGATE_INTERVAL of lastAggregate
    assert len(out) == 2
    assert saves["n"] == 0, f"warm multi forecast must not save_cache; got {saves['n']}"


def test_multi_forecast_and_detect(tmp_path):
    feed = tmp_path / "f.json"
    now = 100000.0
    feed.write_text(json.dumps([[now - 10, 10]]))
    cfg = Config(
        source="generic",
        source_opts={"events_path": str(feed)},
        cache_path=str(tmp_path / "c"),
        windows=[Window("w", 100, 100)],
    )
    mf = multi_forecast(now, cfg)
    assert "generic" in mf or "default" in mf
    rs = detect_resets(
        [Forecast("w", 90, 100, 90, None, 10, False)],
        [Forecast("w", 5, 100, 5, None, 10, False, profile="grok")],
    )
    assert len(rs) >= 1


def test_single_path_scan_failure_falls_back_to_cached_events(monkeypatch, tmp_path):
    """A scan crash in the legacy single-source path must fall back to cached
    events (non-blank forecast) instead of the outer except returning []."""
    from token_oracle.core import engine as ENG

    now = 10_000_000.0

    class BoomSource:
        def scan(self, *a, **k):
            raise RuntimeError("malformed log blew up scan")

    monkeypatch.setattr("token_oracle.sources.base.get_source", lambda *a, **k: BoomSource())

    # warm cache with one good event well within the window, and a stale lastAggregate
    # so the aggregate branch (which calls scan) is taken.
    cache = {
        "files": {},
        "events": [[now - 100, 5000, "claude-sonnet-4-5", 5000, 0, 0, 0, None]],
        "profile": [],
        "lastAggregate": 0,
    }
    monkeypatch.setattr(ENG, "load_cache", lambda *a, **k: cache)
    monkeypatch.setattr(ENG, "save_cache", lambda *a, **k: None)
    # Isolate the intentional Claude 5h server overlay: it reads the real
    # ~/.claude/usage-limits.json / live 5h and would override the cached
    # `used` with real machine state, making this assertion non-hermetic
    # (green in CI, flaky on a dev machine with real usage < 5000).
    monkeypatch.setattr(ENG, "try_get_claude_five_hour_data", lambda *a, **k: None)
    monkeypatch.setattr(ENG, "try_get_claude_five_hour_remaining", lambda *a, **k: None)

    cfg = Config(
        source="claude_code",
        windows=[Window(name="5h", cap=220000, period_secs=18000)],
        cache_path=str(tmp_path / "cache.json"),
    )
    fs = ENG.forecast(now, cfg)
    assert fs, "forecast blanked on scan failure instead of using cached events"
    # the cached 5000-token event is reflected in the 5h window's used
    five = next(f for f in fs if f.window == "5h")
    assert five.used >= 5000


def test_server_5h_does_not_overwrite_projected_pct(monkeypatch, tmp_path):
    """Server current % updates used/reset only — never projected_pct (plan 030)."""
    import token_oracle.core.engine as ENG

    local_proj = 42.0

    # Force compute_window to a known projection, then apply server overlay.
    def fake_compute(events, now, w, prof):
        from token_oracle.core.contracts import Forecast

        return Forecast(w.name, 1000, w.cap, local_proj, None, 999.0, False)

    monkeypatch.setattr(ENG, "compute_window", fake_compute)
    monkeypatch.setattr(
        ENG,
        "try_get_claude_five_hour_data",
        lambda *a, **k: {
            "reset_in_secs": 3600.0,
            "projected_pct": 77.0,  # current fill from server
            "source": "server",
        },
    )
    monkeypatch.setattr(ENG, "try_get_claude_five_hour_remaining", lambda *a, **k: None)

    # Minimal path: call _forecast_one with claude_code + 5h window
    class FakeSrc:
        def scan(self, files, now, hist):
            return {}, []

    monkeypatch.setattr("token_oracle.sources.base.get_source", lambda name, opts: FakeSrc())
    # lastAggregate = now so we skip scan aggregate and still run overlay
    now = 1_700_000_000.0
    cslice = {
        "files": {},
        "events": [[now - 100, 1000, "claude-sonnet-4-5", 1000, 0, 0, 0, None]],
        "profile": [],
        "lastAggregate": now,
    }
    wins = [{"name": "5h", "cap": 220000, "period_secs": 18000}]
    _, fs = ENG._forecast_one(now, "claude_code", {}, wins, cslice)
    assert len(fs) == 1
    f = fs[0]
    assert f.projected_pct == local_proj  # NOT 77
    assert f.reset_in_secs == 3600.0
    assert f.used == int(round(77.0 / 100.0 * 220000))
