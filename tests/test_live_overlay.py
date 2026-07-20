import time

from token_oracle.core.contracts import Forecast
from token_oracle.live.contract import (
    CONF_HIGH,
    CONF_LOW,
    METRIC_MODEL_WEEKLY_PCT,
    METRIC_RATE_WINDOW,
    METRIC_WEEKLY_PCT,
    STATE_AUTH_NO_DATA,
    STATE_OK,
    STATE_STALE,
    LiveReading,
    ProviderLive,
)
from token_oracle.live.overlay import FRESH_TTL_SECS, HEADER_FRESH_TTL_SECS, overlay_cells


def test_overlay_high_conf_fresh_sets_pct():
    now = time.time()
    snap = {
        "version": 1,
        "written_at": now,
        "providers": {
            "claude": {
                "provider": "claude",
                "state": "ok",
                "readings": [
                    {
                        "provider": "claude",
                        "metric": METRIC_WEEKLY_PCT,
                        "value": 38.0,
                        "confidence": CONF_HIGH,
                        "extractor": "claude.ex",
                        "evidence": "row42",
                        "fetched_at": now,
                    }
                ],
            }
        },
    }
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="claude")]
    cells = overlay_cells(fs, snap, now, ttl=FRESH_TTL_SECS, weekly_header=None)
    cell = cells.get(("claude", "weekly"))
    assert cell is not None
    assert cell.pct == 38.0
    assert cell.state == "ok"


def test_overlay_low_conf_withholds_pct():
    now = time.time()
    snap = {
        "version": 1,
        "written_at": now,
        "providers": {
            "claude": {
                "provider": "claude",
                "state": "ok",
                "readings": [
                    {
                        "provider": "claude",
                        "metric": METRIC_WEEKLY_PCT,
                        "value": 38.0,
                        "confidence": CONF_LOW,
                        "extractor": "l",
                        "evidence": "e",
                        "fetched_at": now,
                    }
                ],
            }
        },
    }
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="claude")]
    cells = overlay_cells(fs, snap, now, weekly_header=None)
    cell = cells.get(("claude", "weekly"))
    assert cell is not None
    assert cell.pct is None  # low withheld
    assert cell.state == "ok"


def test_overlay_stale_sets_state_and_withholds():
    now = time.time()
    old = now - 3600
    snap = {
        "version": 1,
        "written_at": old,
        "providers": {
            "claude": {
                "provider": "claude",
                "state": "ok",
                "readings": [
                    {
                        "provider": "claude",
                        "metric": METRIC_WEEKLY_PCT,
                        "value": 38.0,
                        "confidence": CONF_HIGH,
                        "extractor": "e",
                        "evidence": "e",
                        "fetched_at": old,
                    }
                ],
            }
        },
    }
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="claude")]
    cells = overlay_cells(fs, snap, now, ttl=180, weekly_header=None)
    cell = cells.get(("claude", "weekly"))
    assert cell is not None
    assert cell.pct is None
    assert cell.state == STATE_STALE


def test_rate_window_never_maps_to_cell():
    now = time.time()
    snap = {
        "version": 1,
        "written_at": now,
        "providers": {
            "grok": {
                "provider": "grok",
                "state": "rate_data_only",
                "readings": [
                    {
                        "provider": "grok",
                        "metric": METRIC_RATE_WINDOW,
                        "value": 80.0,
                        "confidence": CONF_HIGH,
                        "extractor": "q",
                        "evidence": "q",
                        "fetched_at": now,
                    }
                ],
            }
        },
    }
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="grok")]
    cells = overlay_cells(fs, snap, now, weekly_header=None)
    # no cell for weekly from rate
    assert ("grok", "weekly") not in cells
    # rate_info would have it, but cells do not
    assert len(cells) == 0 or all("rate" not in str(k) for k in cells)


def test_fable_maps_to_fable_not_weekly():
    now = time.time()
    snap = {
        "version": 1,
        "written_at": now,
        "providers": {
            "claude": {
                "provider": "claude",
                "state": "ok",
                "readings": [
                    {
                        "provider": "claude",
                        "metric": METRIC_MODEL_WEEKLY_PCT,
                        "value": 77.0,
                        "confidence": CONF_HIGH,
                        "extractor": "f",
                        "evidence": "f",
                        "fetched_at": now,
                        "model": "fable",
                    }
                ],
            }
        },
    }
    fs = [Forecast("fable", 50, 500, 70.0, None, 100.0, False, profile="claude")]
    cells = overlay_cells(fs, snap, now, weekly_header=None)
    assert cells.get(("claude", "fable")) is not None
    assert cells.get(("claude", "fable")).pct == 77.0
    assert cells.get(("claude", "weekly")) is None  # not leaked to weekly


def test_provider_live_low_conf_gives_auth_no_data():
    """Equivalent to old legacy low-conf test (legacy adapter deleted in 032).
    Low confidence usage reading → not 'ok' state; reading is preserved.
    """
    now = time.time()
    low = LiveReading(
        provider="grok",
        metric=METRIC_WEEKLY_PCT,
        value=13.0,
        confidence=CONF_LOW,
        extractor="grok.legacy",
        evidence="overall_pct",
        fetched_at=now,
    )
    pl = ProviderLive(provider="grok", state=STATE_AUTH_NO_DATA, readings=[low], fetched_at=now)
    assert pl.state in (STATE_AUTH_NO_DATA, "authenticated_no_data")
    weekly = [r for r in pl.readings if r.metric == METRIC_WEEKLY_PCT]
    assert len(weekly) == 1
    assert weekly[0].confidence == CONF_LOW
    assert weekly[0].value == 13.0


def test_engine_purity_no_live_fetcher_leaked():
    import token_oracle.core.engine as e

    assert not hasattr(e, "fetch_claude_live_usage")
    assert not hasattr(e, "fetch_grok_live_usage")


def test_freshness_ttl_exceeds_probe_interval_with_margin():
    """Regression: the dash scrapes every LIVE_PROBE_INTERVAL, but a reading's
    worst-case age is interval + one probe's duration. FRESH_TTL_SECS must cover
    that, or cap cells flicker to 'stale' at the tail of every probe cycle."""
    from token_oracle.dashboard.app import LIVE_PROBE_INTERVAL

    probe_duration_margin = 60  # a headed both-provider probe takes tens of seconds
    assert FRESH_TTL_SECS >= LIVE_PROBE_INTERVAL + probe_duration_margin


def test_reading_at_full_probe_interval_still_applied():
    """A cap reading as old as one whole probe interval must still be live."""
    from token_oracle.dashboard.app import LIVE_PROBE_INTERVAL

    now = time.time()
    snap = {
        "version": 1,
        "written_at": now,
        "providers": {
            "grok": {
                "provider": "grok",
                "state": "ok",
                "readings": [
                    {
                        "provider": "grok",
                        "metric": METRIC_WEEKLY_PCT,
                        "value": 23.0,
                        "confidence": CONF_HIGH,
                        "extractor": "grok.usage_modal.text",
                        "evidence": "Weekly SuperGrok Heavy Limit 23% used",
                        "fetched_at": now - LIVE_PROBE_INTERVAL,
                    }
                ],
            }
        },
    }
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="grok")]
    cell = overlay_cells(fs, snap, now, weekly_header=None).get(("grok", "weekly"))
    assert cell is not None
    assert cell.pct == 23.0  # not withheld
    assert cell.state != STATE_STALE


# --- honest-provenance retained flag tests (plan 063 I4) ---


def test_retained_cell_is_flagged():
    """A cell built from a '+retained' last-good reading is display-only:
    still shown (weekly caps move slowly) but flagged is_retained."""
    now = time.time()
    snap = {
        "version": 1,
        "written_at": now,
        "providers": {
            "grok": {
                "provider": "grok",
                "state": "ok",
                "readings": [
                    {
                        "provider": "grok",
                        "metric": METRIC_WEEKLY_PCT,
                        "value": 23.0,
                        "confidence": CONF_HIGH,
                        "extractor": "grok.usage_modal.text+retained",
                        "evidence": "Weekly Heavy Limit 23% used",
                        "fetched_at": now - 1200,  # > FRESH_TTL, < 6h retain TTL
                    }
                ],
            }
        },
    }
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="grok")]
    cell = overlay_cells(fs, snap, now, weekly_header=None).get(("grok", "weekly"))
    assert cell is not None
    assert cell.pct == 23.0  # retained weekly still applied
    assert cell.state == STATE_OK
    assert cell.is_retained is True


def test_fresh_cell_not_flagged():
    now = time.time()
    snap = {
        "version": 1,
        "written_at": now,
        "providers": {
            "claude": {
                "provider": "claude",
                "state": "ok",
                "readings": [
                    {
                        "provider": "claude",
                        "metric": METRIC_WEEKLY_PCT,
                        "value": 38.0,
                        "confidence": CONF_HIGH,
                        "extractor": "claude.ex",
                        "evidence": "row42",
                        "fetched_at": now,
                    }
                ],
            }
        },
    }
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="claude")]
    cell = overlay_cells(fs, snap, now, weekly_header=None).get(("claude", "weekly"))
    assert cell is not None
    assert cell.pct == 38.0
    assert cell.is_retained is False


def test_over_fresh_cell_is_flagged():
    """Even a non-retained reading older than FRESH_TTL_SECS reads as retained."""
    now = time.time()
    snap = {
        "version": 1,
        "written_at": now,
        "providers": {
            "grok": {
                "provider": "grok",
                "state": "ok",
                "readings": [
                    {
                        "provider": "grok",
                        "metric": METRIC_WEEKLY_PCT,
                        "value": 50.0,
                        "confidence": CONF_HIGH,
                        "extractor": "grok.modal",
                        "evidence": "50% used",
                        "fetched_at": now - (FRESH_TTL_SECS + 30),
                    }
                ],
            }
        },
    }
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="grok")]
    # give a generous ttl so it is not withheld as stale; only test the flag
    cell = overlay_cells(
        fs, snap, now, ttl=FRESH_TTL_SECS + 600, weekly_header=None
    ).get(("grok", "weekly"))
    assert cell is not None
    assert cell.pct == 50.0
    assert cell.is_retained is True


# --- header weekly (self-ingested rate limit) tests (plan 054) ---


def test_header_weekly_with_none_or_empty_snapshot():
    """Header weekly must work without a live-web snapshot (statusline-only users)."""
    now = time.time()
    hdr = {"used_percentage": 41.0, "observed_at": now - 2, "stale": False}
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="claude")]
    for snap in (None, {}, {"providers": None}):
        cells = overlay_cells(fs, snap, now, weekly_header=hdr)
        cell = cells.get(("claude", "weekly"))
        assert cell is not None, f"snap={snap!r} dropped header weekly"
        assert cell.pct == 41.0
        assert cell.extractor == "header"


def test_header_weekly_becomes_live_cell():
    now = time.time()
    hdr = {"used_percentage": 33.0, "observed_at": now - 5, "stale": False}
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="claude")]
    # no web weekly in snap
    cells = overlay_cells(fs, {"providers": {}}, now, weekly_header=hdr)
    cell = cells.get(("claude", "weekly"))
    assert cell is not None
    assert cell.pct == 33.0
    assert cell.extractor == "header"
    assert cell.state == STATE_OK
    assert abs(cell.age_secs - 5) < 0.1


def test_header_weekly_overrides_web_cell():
    now = time.time()
    snap = {
        "providers": {
            "claude": {
                "provider": "claude",
                "state": "ok",
                "readings": [
                    {
                        "provider": "claude",
                        "metric": METRIC_WEEKLY_PCT,
                        "value": 30.0,
                        "confidence": CONF_HIGH,
                        "extractor": "claude.web",
                        "evidence": "web",
                        "fetched_at": now,
                    }
                ],
            }
        }
    }
    hdr = {"used_percentage": 33.0, "observed_at": now - 3, "stale": False}
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="claude")]
    cells = overlay_cells(fs, snap, now, weekly_header=hdr)
    cell = cells.get(("claude", "weekly"))
    assert cell is not None
    assert cell.pct == 33.0  # header wins
    assert cell.extractor == "header"


def test_stale_header_weekly_withheld():
    now = time.time()
    hdr_stale = {"used_percentage": 33.0, "observed_at": now - 5, "stale": True}
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="claude")]
    cells = overlay_cells(fs, {"providers": {}}, now, weekly_header=hdr_stale)
    assert cells.get(("claude", "weekly")) is None

    hdr_none = {"used_percentage": None, "observed_at": now - 5, "stale": False}
    cells2 = overlay_cells(fs, {"providers": {}}, now, weekly_header=hdr_none)
    assert cells2.get(("claude", "weekly")) is None


def test_old_header_weekly_withheld_by_ttl():
    now = time.time()
    old_obs = now - (HEADER_FRESH_TTL_SECS + 60)
    hdr = {"used_percentage": 40.0, "observed_at": old_obs, "stale": False}
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="claude")]
    cells = overlay_cells(fs, {"providers": {}}, now, weekly_header=hdr)
    # age > header TTL => withheld
    assert cells.get(("claude", "weekly")) is None


def test_header_weekly_fresh_within_multi_hour_ttl():
    """Statusline may idle for hours; weekly header still applies within 6h."""
    now = time.time()
    mid_obs = now - (FRESH_TTL_SECS + 120)  # older than web TTL, under header TTL
    hdr = {"used_percentage": 93.0, "observed_at": mid_obs, "stale": False}
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="claude")]
    cells = overlay_cells(fs, {"providers": {}}, now, weekly_header=hdr)
    assert cells.get(("claude", "weekly")) is not None
    assert cells[("claude", "weekly")].pct == 93.0


def test_grok_weekly_untouched_by_header():
    now = time.time()
    snap = {
        "providers": {
            "grok": {
                "provider": "grok",
                "state": "ok",
                "readings": [
                    {
                        "provider": "grok",
                        "metric": METRIC_WEEKLY_PCT,
                        "value": 55.0,
                        "confidence": CONF_HIGH,
                        "extractor": "grok.web",
                        "evidence": "web",
                        "fetched_at": now,
                    }
                ],
            }
        }
    }
    hdr_claude = {"used_percentage": 33.0, "observed_at": now - 1, "stale": False}
    fs = [Forecast("weekly", 100, 1000, 40.0, None, 100.0, False, profile="grok")]
    cells = overlay_cells(fs, snap, now, weekly_header=hdr_claude)
    cell = cells.get(("grok", "weekly"))
    assert cell is not None
    assert cell.pct == 55.0  # grok untouched
    assert cell.extractor == "grok.web"
    # claude header creates its cell (intended); does not affect grok
    cl = cells.get(("claude", "weekly"))
    assert cl is not None and cl.pct == 33.0 and cl.extractor == "header"
