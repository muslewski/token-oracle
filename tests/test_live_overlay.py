import time

from token_oracle.live.contract import (
    LiveReading,
    ProviderLive,
    CONF_HIGH,
    CONF_LOW,
    CONF_MEDIUM,
    METRIC_WEEKLY_PCT,
    METRIC_MODEL_WEEKLY_PCT,
    METRIC_FIVE_HOUR_PCT,
    METRIC_FIVE_HOUR_STATE,
    METRIC_RATE_WINDOW,
    STATE_AUTH_NO_DATA,
    STATE_STALE,
)
from token_oracle.live.legacy import provider_live_from_legacy
from token_oracle.live.overlay import LiveCell, overlay_cells, FRESH_TTL_SECS
from token_oracle.core.contracts import Forecast


def test_overlay_high_conf_fresh_sets_pct():
    now = time.time()
    r = LiveReading("claude", METRIC_WEEKLY_PCT, 38.0, CONF_HIGH, "claude.ex", "row42", now)
    pl = ProviderLive("claude", "ok", [r], fetched_at=now)
    snap = {"version": 1, "written_at": now, "providers": {"claude": {"provider": "claude", "state": "ok", "readings": [ {"provider":"claude","metric":METRIC_WEEKLY_PCT,"value":38.0,"confidence":CONF_HIGH,"extractor":"claude.ex","evidence":"row42","fetched_at":now} ] } } }
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="claude")]
    cells = overlay_cells(fs, snap, now, ttl=FRESH_TTL_SECS)
    cell = cells.get(("claude", "weekly"))
    assert cell is not None
    assert cell.pct == 38.0
    assert cell.state == "ok"


def test_overlay_low_conf_withholds_pct():
    now = time.time()
    snap = {"version": 1, "written_at": now, "providers": {"claude": {"provider": "claude", "state": "ok", "readings": [ {"provider":"claude","metric":METRIC_WEEKLY_PCT,"value":38.0,"confidence":CONF_LOW,"extractor":"l","evidence":"e","fetched_at":now} ] } } }
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="claude")]
    cells = overlay_cells(fs, snap, now)
    cell = cells.get(("claude", "weekly"))
    assert cell is not None
    assert cell.pct is None  # low withheld
    assert cell.state == "ok"


def test_overlay_stale_sets_state_and_withholds():
    now = time.time()
    old = now - 3600
    snap = {"version": 1, "written_at": old, "providers": {"claude": {"provider": "claude", "state": "ok", "readings": [ {"provider":"claude","metric":METRIC_WEEKLY_PCT,"value":38.0,"confidence":CONF_HIGH,"extractor":"e","evidence":"e","fetched_at":old} ] } } }
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="claude")]
    cells = overlay_cells(fs, snap, now, ttl=180)
    cell = cells.get(("claude", "weekly"))
    assert cell is not None
    assert cell.pct is None
    assert cell.state == STATE_STALE


def test_rate_window_never_maps_to_cell():
    now = time.time()
    snap = {"version": 1, "written_at": now, "providers": {"grok": {"provider": "grok", "state": "rate_data_only", "readings": [ {"provider":"grok","metric":METRIC_RATE_WINDOW,"value":80.0,"confidence":CONF_HIGH,"extractor":"q","evidence":"q","fetched_at":now} ] } } }
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="grok")]
    cells = overlay_cells(fs, snap, now)
    # no cell for weekly from rate
    assert ("grok", "weekly") not in cells
    # rate_info would have it, but cells do not
    assert len(cells) == 0 or all("rate" not in str(k) for k in cells)


def test_fable_maps_to_fable_not_weekly():
    now = time.time()
    snap = {"version": 1, "written_at": now, "providers": {"claude": {"provider": "claude", "state": "ok", "readings": [ {"provider":"claude","metric":METRIC_MODEL_WEEKLY_PCT,"value":77.0,"confidence":CONF_HIGH,"extractor":"f","evidence":"f","fetched_at":now,"model":"fable"} ] } } }
    fs = [Forecast("fable", 50, 500, 70.0, None, 100.0, False, profile="claude")]
    cells = overlay_cells(fs, snap, now)
    assert cells.get(("claude", "fable")) is not None
    assert cells.get(("claude", "fable")).pct == 77.0
    assert cells.get(("claude", "weekly")) is None  # not leaked to weekly


def test_provider_live_from_legacy_grok_overall_low_and_auth_state():
    now = time.time()
    pl = provider_live_from_legacy("grok", {"authenticated": True, "overall_pct": 13.0}, now)
    assert pl.state in (STATE_AUTH_NO_DATA, "authenticated_no_data") or pl.state == "ok"  # ok only if high
    # the reading must exist and be low
    weekly = [r for r in pl.readings if r.metric == METRIC_WEEKLY_PCT]
    assert len(weekly) == 1
    assert weekly[0].confidence == CONF_LOW
    assert weekly[0].value == 13.0


def test_engine_purity_no_live_fetcher_leaked():
    import token_oracle.core.engine as e
    assert not hasattr(e, "fetch_claude_live_usage")
    assert not hasattr(e, "fetch_grok_live_usage")
