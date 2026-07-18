"""Tests for get_live_status per-provider reading-age freshness (plan 063 I4).

A fresh snapshot write must not make hours-old retained readings read as live;
freshness is derived from the newest usable reading's fetched_at, and a
retain-escalated 'stale' provider surfaces as 'probe failing'.
"""

import json
import os

from token_oracle.live.store import default_live_path
from token_oracle.live.web import get_live_status


def _write_snap(providers, written_at):
    p = default_live_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump({"version": 1, "written_at": written_at, "providers": providers}, fh)


def _reading(value, fetched_at):
    return {
        "provider": "grok",
        "metric": "weekly_pct",
        "value": value,
        "confidence": "high",
        "extractor": "grok.modal",
        "evidence": "e",
        "fetched_at": fetched_at,
    }


def test_get_live_status_uses_reading_age(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    now = 10_000.0
    old = now - 4000.0  # > 600s STALE_AFTER
    _write_snap(
        {
            "grok": {
                "provider": "grok",
                "state": "ok",
                "readings": [_reading(22.0, old)],  # hours old
            },
            "claude": {
                "provider": "claude",
                "state": "ok",
                "readings": [_reading(30.0, now)],  # fresh
            },
        },
        written_at=now,  # snapshot itself written 'now' (fresh)
    )
    st = get_live_status(now=now)
    # grok reading is old despite fresh written_at -> stale (the whole point)
    assert st["grok"] == "stale"
    assert st["grok_last_state"] == "ok"
    # claude reading is fresh -> ok
    assert st["claude"] == "ok"


def test_get_live_status_probe_failing_when_state_stale(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    now = 10_000.0
    _write_snap(
        {
            "grok": {
                "provider": "grok",
                "state": "stale",  # retain-cycle guard escalated this provider
                "readings": [_reading(22.0, now - 4000.0)],
            },
        },
        written_at=now,
    )
    st = get_live_status(now=now)
    assert st["grok"] == "stale"
    assert "probe failing" in st["message"].lower()


def test_get_live_status_fresh_reading_reports_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    now = 10_000.0
    _write_snap(
        {
            "grok": {"provider": "grok", "state": "ok", "readings": [_reading(22.0, now)]},
            "claude": {"provider": "claude", "state": "ok", "readings": [_reading(30.0, now)]},
        },
        written_at=now,
    )
    st = get_live_status(now=now)
    assert st["grok"] == "ok"
    assert st["claude"] == "ok"
    assert st["message"] == "live web active"
