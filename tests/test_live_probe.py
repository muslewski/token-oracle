"""Tests for live-probe orchestration (plan 033).

All tests are playwright-free and network-free by construction; fetchers are
monkeypatched at the `token_oracle.live.probe` import site.
"""

import json
import os
import time

from token_oracle.live.contract import CONF_HIGH, LiveReading, ProviderLive
from token_oracle.live.probe import run_probe
from token_oracle.live.store import default_live_path, load_snapshot
from token_oracle.live.web import get_live_status


def _write_cfg(tmp_path, events, now):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps(events))
    cfg = tmp_path / "cfg.json"
    cfg.write_text(
        json.dumps(
            {
                "source": "generic",
                "source_opts": {"events_path": str(feed)},
                "cache_path": str(tmp_path / "cache.json"),
                "windows": [{"name": "5h", "cap": 1000, "period_secs": 18000}],
            }
        )
    )
    return str(cfg)


def test_run_probe_writes_snapshot_and_handles_one_error(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    def good_grok(**kwargs):
        return ProviderLive(
            provider="grok",
            state="ok",
            readings=[
                LiveReading(
                    provider="grok",
                    metric="weekly_pct",
                    value=11.0,
                    confidence=CONF_HIGH,
                    extractor="grok.test",
                    evidence="ev",
                    fetched_at=time.time(),
                )
            ],
            fetched_at=time.time(),
        )

    def bad_claude(**kwargs):
        raise RuntimeError("simulated probe failure")

    import token_oracle.live.probe as probe_mod

    monkeypatch.setattr(probe_mod, "fetch_grok_live_usage", good_grok)
    monkeypatch.setattr(probe_mod, "fetch_claude_live_usage", bad_claude)

    snap = run_probe(providers=("grok", "claude"), headless=True, progress=None)
    assert snap["version"] == 1
    data = load_snapshot()
    assert data is not None
    assert data["providers"]["grok"]["state"] == "ok"
    assert len(data["providers"]["grok"]["readings"]) == 1
    assert data["providers"]["claude"]["state"] == "error"
    assert "simulated" in (data["providers"]["claude"].get("error") or "")


def test_run_probe_calls_progress_and_writes_nothing_to_stdout(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    msgs = []

    def ok(**kwargs):
        return ProviderLive(provider="grok", state="ok", readings=[], fetched_at=time.time())

    def nl(**kwargs):
        return ProviderLive(
            provider="claude", state="needs_login", readings=[], fetched_at=time.time()
        )

    import token_oracle.live.probe as probe_mod

    monkeypatch.setattr(probe_mod, "fetch_grok_live_usage", ok)
    monkeypatch.setattr(probe_mod, "fetch_claude_live_usage", nl)

    run_probe(providers="all", progress=msgs.append)
    captured = capsys.readouterr()
    assert len(msgs) >= 1
    assert captured.out == ""


def test_get_live_status_no_snapshot_and_stale(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    # no snapshot at all
    st = get_live_status(now=10000.0)
    assert st["grok"] == "unavailable"
    assert st["claude"] == "unavailable"
    assert "live-probe" in st.get("message", "").lower()

    # stale snapshot
    old = 10000.0 - 3600
    p = default_live_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "version": 1,
                "written_at": old,
                "providers": {
                    "grok": {"provider": "grok", "state": "ok", "readings": []},
                    "claude": {
                        "provider": "claude",
                        "state": "authenticated_no_data",
                        "readings": [],
                    },
                },
            },
            fh,
        )

    st2 = get_live_status(now=10000.0)
    assert st2["grok"] == "stale"
    assert st2["claude"] == "stale"
    assert "old" in st2.get("message", "").lower() or "3600" in st2.get("message", "")


def test_run_probe_error_state_for_all(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    def boom(**k):
        raise ValueError("all fail")

    import token_oracle.live.probe as probe_mod

    monkeypatch.setattr(probe_mod, "fetch_grok_live_usage", boom)
    monkeypatch.setattr(probe_mod, "fetch_claude_live_usage", boom)

    run_probe(providers="all")
    data = load_snapshot()
    assert data["providers"]["grok"]["state"] == "error"
    assert data["providers"]["claude"]["state"] == "error"


def test_run_probe_headed_no_display_is_honest(tmp_path, monkeypatch):
    """RC-D regression: headed=True + no display/Xvfb must yield unavailable, never needs_login lie."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    import token_oracle.live.probe as probe_mod
    import token_oracle.live.web as web_mod

    # Force no display and no Xvfb
    monkeypatch.setattr(web_mod, "_has_graphical_display", lambda: False)
    monkeypatch.setattr(web_mod.shutil, "which", lambda name: None)

    def must_not_be_called(**kwargs):
        raise AssertionError("fetch must not be called when no display for headed mode")

    monkeypatch.setattr(probe_mod, "fetch_grok_live_usage", must_not_be_called)
    monkeypatch.setattr(probe_mod, "fetch_claude_live_usage", must_not_be_called)

    snap = run_probe(providers="all", headless=False)

    assert "grok" in snap["providers"]
    assert "claude" in snap["providers"]
    for name in ("grok", "claude"):
        p = snap["providers"][name]
        assert p["state"] == "unavailable", f"{name} should be unavailable not {p['state']}"
        assert "needs_login" not in p["state"]
        note = p.get("note", "")
        assert "Xvfb" in note or "display" in note.lower(), f"note should mention Xvfb: {note}"


def test_run_probe_headed_shares_display_across_providers(tmp_path, monkeypatch):
    """RC-A regression at orchestrator: one virtual display for whole run; 2nd provider sees live DISPLAY."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    import token_oracle.live.probe as probe_mod
    import token_oracle.live.web as web_mod

    monkeypatch.setattr(web_mod, "_has_graphical_display", lambda: False)
    monkeypatch.setattr(web_mod.shutil, "which", lambda name: "/usr/bin/Xvfb" if name == "Xvfb" else None)

    term_count = {"n": 0}

    class FakeProc:
        def poll(self):
            return None
        def terminate(self):
            term_count["n"] += 1

    def fake_popen(*a, **k):
        return FakeProc()

    monkeypatch.setattr(web_mod.subprocess, "Popen", fake_popen)

    grok_seen = []
    claude_seen = []

    def make_fetch(name, seen_list):
        def f(**kwargs):
            seen_list.append(os.environ.get("DISPLAY"))
            # Return a minimal live result
            from token_oracle.live.contract import ProviderLive
            return ProviderLive(
                provider=name,
                state="ok" if name == "grok" else "rate_data_only",
                readings=[],
                fetched_at=0.0,
            )
        return f

    monkeypatch.setattr(probe_mod, "fetch_grok_live_usage", make_fetch("grok", grok_seen))
    monkeypatch.setattr(probe_mod, "fetch_claude_live_usage", make_fetch("claude", claude_seen))

    snap = run_probe(providers="all", headless=False)

    # Both fetches saw the same live display (would have been dead :99 without restore fix)
    assert len(grok_seen) == 1 and grok_seen[0] == ":99"
    assert len(claude_seen) == 1 and claude_seen[0] == ":99"
    assert grok_seen[0] == claude_seen[0]
    # Exactly one terminate for the whole run (not per-provider)
    assert term_count["n"] == 1
    # Snapshot has the results
    assert snap["providers"]["grok"]["state"] in ("ok", "rate_data_only")
    assert snap["providers"]["claude"]["state"] in ("ok", "rate_data_only")
