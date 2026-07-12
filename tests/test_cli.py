import json
import os
import time as _time

import pytest

from token_oracle.cli.main import main


def _cfg(tmp_path, feed_events, now):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps(feed_events))
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


def test_forecast_json(tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 250]], now)
    rc = main(["forecast", "--json", "--config", cfg, "--now", str(now)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["windows"][0]["used"] == 250


def test_snapshot_writes_file(tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 10]], now)
    out_path = str(tmp_path / "snap.json")
    rc = main(["snapshot", "--config", cfg, "--out", out_path, "--now", str(now)])
    assert rc == 0
    assert json.load(open(out_path))["schema"] == 1


def test_snapshot_exit_one_on_write_failure(tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 10]], now)
    (tmp_path / "blocker").write_text("file, not a dir")
    out_path = str(tmp_path / "blocker" / "snap.json")
    rc = main(["snapshot", "--config", cfg, "--out", out_path, "--now", str(now)])
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "write failed" in captured.err


def test_doctor_exit_one_when_no_events(tmp_path):
    now = 100000.0
    cfg = _cfg(tmp_path, [], now)
    assert main(["doctor", "--config", cfg, "--now", str(now)]) == 1


def test_doctor_exit_zero_with_events(tmp_path):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 50]], now)
    assert main(["doctor", "--config", cfg, "--now", str(now)]) == 0


def test_statusline_runs(tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 250]], now)
    assert main(["statusline", "--config", cfg, "--now", str(now)]) == 0
    out = capsys.readouterr().out
    assert out.strip()  # renders a non-empty status line
    assert "/1k" in out or "0k" in out  # used/cap tokens segment present


def test_doctor_footer_and_badges(tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [], now)
    main(["doctor", "--config", cfg, "--now", str(now)])
    out = capsys.readouterr().out
    assert "oracle doctor" in out
    assert "ok ·" in out and "need attention" in out
    assert "✓" in out  # source + windows are valid here → at least one pass


def test_doctor_flags_bad_source(tmp_path):
    from token_oracle.cli.main import _doctor_lines
    from token_oracle.core.config import load_config

    cfg_path = _cfg(tmp_path, [], 100000.0)
    cfg = load_config(cfg_path)
    cfg.source = "nope-not-real"
    lines, bad = _doctor_lines(cfg, cfg_path, color=False, now=100000.0)
    out = "\n".join(lines)
    assert bad >= 1
    assert "✗" in out


def test_doctor_data_row_counts_events(tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 200.0, 10], [now - 100.0, 20]], now)
    main(["doctor", "--config", cfg, "--now", str(now)])
    out = capsys.readouterr().out
    assert "2 events" in out
    assert "last" in out


def test_doctor_reports_config_issues(tmp_path, capsys):
    now = 100000.0
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps([[now - 100.0, 50]]))
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(
        json.dumps(
            {
                "source": "generic",
                "source_opts": {"events_path": str(feed)},
                "cache_path": str(tmp_path / "cache.json"),
                "windows": [{"cap": 1000, "period_secs": 18000}],  # missing "name"
            }
        )
    )
    rc = main(["doctor", "--config", str(cfg_path), "--now", str(now)])
    out = capsys.readouterr().out
    assert "issue" in out
    assert "✗" in out
    assert rc == 1


def test_doctor_missing_config_is_ok(tmp_path):
    from token_oracle.cli.main import _doctor_lines
    from token_oracle.core.config import load_config

    missing_path = str(tmp_path / "does-not-exist.json")
    cfg = load_config(missing_path)
    # avoid the claude_code default source scanning the real ~/.claude/projects (use generic feed)
    cfg.source = "generic"
    cfg.source_opts = {"events_path": str(tmp_path / "no-events.json")}
    lines, _bad = _doctor_lines(cfg, missing_path, color=False, now=100000.0)
    out = "\n".join(lines)
    assert "missing — using built-in max20 preset" in out


def test_doctor_corrupt_cache_flagged(tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 50]], now)
    from token_oracle.core.config import load_config

    cache_path = load_config(cfg).cache_path
    with open(cache_path, "w", encoding="utf-8") as fh:
        fh.write("{ not json")

    rc = main(["doctor", "--config", cfg, "--now", str(now)])
    out = capsys.readouterr().out
    assert "corrupt" in out
    assert rc == 1


def test_init_writes_config(tmp_path, capsys):
    cfg_path = str(tmp_path / "c.json")
    assert main(["init", "--config", cfg_path]) == 0
    assert os.path.exists(cfg_path)
    data = json.load(open(cfg_path))
    assert {w["name"] for w in data["windows"]} == {"5h", "weekly"}
    out = capsys.readouterr().out
    assert cfg_path in out


def test_init_no_clobber(tmp_path, capsys):
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps({"source": "custom"}))

    rc = main(["init", "--config", str(cfg_path)])
    assert rc == 0
    assert json.loads(cfg_path.read_text()) == {"source": "custom"}
    out = capsys.readouterr().out
    assert "--force" in out

    rc = main(["init", "--config", str(cfg_path), "--force"])
    assert rc == 0
    assert "windows" in json.loads(cfg_path.read_text())


def test_clean_requires_yes(tmp_path, capsys, monkeypatch):
    # Isolate cache/snapshot resolution to tmp_path so nothing real is touched.
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    cfg_path = str(tmp_path / "c.json")
    main(["init", "--config", cfg_path])
    capsys.readouterr()

    rc = main(["clean", "--config", cfg_path])
    assert rc == 1
    assert os.path.exists(cfg_path)
    out = capsys.readouterr().out
    assert cfg_path in out


def test_clean_yes_removes(tmp_path, monkeypatch):
    # Isolate cache/snapshot resolution to tmp_path so real user data is never removed.
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    cfg_path = str(tmp_path / "c.json")
    main(["init", "--config", cfg_path])

    # Create dummy cache + snapshot under the isolated data dir so removal is exercised.
    data_dir = tmp_path / "token-oracle"
    os.makedirs(data_dir, exist_ok=True)
    cache_path = data_dir / "cache.json"
    snapshot_path = data_dir / "forecast.json"
    cache_path.write_text("{}")
    snapshot_path.write_text("{}")

    rc = main(["clean", "--config", cfg_path, "--yes"])
    assert rc == 0
    assert not os.path.exists(cfg_path)
    assert not cache_path.exists()
    assert not snapshot_path.exists()

    # All three already absent → still exits 0, no exception (silently skipped).
    rc = main(["clean", "--config", cfg_path, "--yes"])
    assert rc == 0


# --- plan 033 additions: live-probe subcommand + doctor snapshot path ---


def test_live_probe_json_output_and_ok_exit(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("TOKEN_ORACLE_SKIP_BOOTSTRAP", "1")

    def fake_ok(**k):
        return {
            "version": 1,
            "written_at": 123456.0,
            "providers": {
                "grok": {
                    "provider": "grok",
                    "state": "ok",
                    "readings": [{"metric": "weekly_pct", "value": 7.0, "extractor": "g.t"}],
                }
            },
        }

    import token_oracle.live.probe as pr

    monkeypatch.setattr(pr, "run_probe", fake_ok)

    rc = main(["live-probe", "--json"])
    out = capsys.readouterr().out.strip()
    data = json.loads(out)
    assert data["version"] == 1
    assert rc == 0  # has ok


@pytest.mark.parametrize(
    "fake_state,expected_rc",
    [
        ({"grok": {"state": "ok"}}, 0),
        ({"grok": {"state": "rate_data_only"}}, 0),
        ({"claude": {"state": "needs_login"}}, 3),
        ({"grok": {"state": "error"}}, 4),
    ],
)
def test_live_probe_exit_codes(tmp_path, monkeypatch, fake_state, expected_rc):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("TOKEN_ORACLE_SKIP_BOOTSTRAP", "1")

    def fake(**k):
        provs = {k: {"provider": k, **v} for k, v in fake_state.items()}
        return {"version": 1, "written_at": 1.0, "providers": provs}

    import token_oracle.live.probe as pr

    monkeypatch.setattr(pr, "run_probe", fake)

    rc = main(["live-probe", "--json"])
    assert rc == expected_rc


def test_doctor_reads_fresh_snapshot_and_no_playwright(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("TOKEN_ORACLE_SKIP_BOOTSTRAP", "1")

    # pre-populate a fresh live snapshot (so get_live_status is instant)
    live_dir = tmp_path / "token-oracle"
    live_dir.mkdir(parents=True, exist_ok=True)
    snap = {
        "version": 1,
        "written_at": _time.time(),
        "providers": {
            "grok": {
                "provider": "grok",
                "state": "ok",
                "readings": [{"metric": "weekly_pct", "value": 4.2, "extractor": "g.w"}],
            },
            "claude": {"provider": "claude", "state": "authenticated_no_data", "readings": []},
        },
    }
    (live_dir / "live.json").write_text(json.dumps(snap))

    # ensure no playwright path is taken
    import token_oracle.live.web as lwmod

    monkeypatch.setattr(lwmod, "PLAYWRIGHT_AVAILABLE", False)
    lwmod._BLESSED_PYTHON = None
    lwmod._BLESSED_CHECKED = True

    cfg = _cfg(tmp_path, [[_time.time() - 10.0, 5]], _time.time())
    # must not raise even with playwright patched off
    rc = main(["doctor", "--config", cfg, "--now", str(_time.time())])
    out = capsys.readouterr().out
    assert "grok" in out or "ok" in out or "live" in out  # contains state-ish output
    assert "browser" not in out.lower() and "launching" not in out.lower()
    # rc reflects the data/config rows (not live); just ensure it ran
    assert rc in (0, 1)


# --- plan 036: live on/off/status + config headed toggle ---


def test_live_status_off_by_default(tmp_path, capsys):
    # always use explicit --config tmp; never real user config
    cfg_path = str(tmp_path / "c.json")
    # no live key -> default OFF
    rc = main(["live", "status", "--config", cfg_path])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OFF" in out


def test_live_on_persists(tmp_path):
    cfg_path = str(tmp_path / "c.json")
    # write minimal to avoid side effects
    import json as _json

    (tmp_path / "c.json").write_text(_json.dumps({"plan": "max20"}))

    rc = main(["live", "on", "--config", cfg_path])
    assert rc == 0
    from token_oracle.core.config import load_config as _load

    assert _load(cfg_path).headed_enabled() is True

    rc = main(["live", "off", "--config", cfg_path])
    assert rc == 0
    assert _load(cfg_path).headed_enabled() is False


def test_live_probe_honors_config_headed(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKEN_ORACLE_SKIP_BOOTSTRAP", "1")
    monkeypatch.delenv("TOKEN_ORACLE_LIVE_HEADED", raising=False)

    cfg_path = str(tmp_path / "c.json")
    import json as _json

    # headed true
    (tmp_path / "c.json").write_text(_json.dumps({"live": {"headed": True}}))

    calls = []

    def fake_run_probe(**kwargs):
        calls.append(kwargs)
        return {"version": 1, "providers": {}}

    import token_oracle.live.probe as pr

    monkeypatch.setattr(pr, "run_probe", fake_run_probe)

    rc = main(["live-probe", "--json", "--config", cfg_path])
    assert rc in (0, 3, 4)  # depends on fake states, we care about call
    assert len(calls) == 1
    assert calls[0].get("headless") is False  # because headed=True in config, env unset

    # now flip to false
    (tmp_path / "c.json").write_text(_json.dumps({"live": {"headed": False}}))
    calls.clear()
    rc = main(["live-probe", "--json", "--config", cfg_path])
    assert len(calls) == 1
    assert calls[0].get("headless") is True


# --- plan 042: real help text (descriptions, examples, per-arg help) ---


def test_top_help_lists_all_subcommands_with_descriptions(capsys):
    with pytest.raises(SystemExit) as ei:
        main(["--help"])
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert "forecast" in out
    assert "time left before your cap" in out
    assert "examples:" in out


def test_subcommand_help_has_description(capsys):
    with pytest.raises(SystemExit) as ei:
        main(["dash", "--help"])
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert "full-screen live dashboard" in out


def test_now_flag_is_hidden(capsys):
    with pytest.raises(SystemExit) as ei:
        main(["forecast", "--help"])
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert "--now" not in out
    assert "--json" in out
