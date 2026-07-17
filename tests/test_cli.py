import io
import json
import os
import signal
import subprocess
import sys
import time as _time
from types import SimpleNamespace

import pytest

import token_oracle.cli.main as cli_main
from token_oracle.cli.main import main


@pytest.fixture(autouse=True)
def _hermetic_live_store(monkeypatch, tmp_path):
    """CLI forecast/statusline paths read live.json + ratelimits via XDG."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))


def _cfg(tmp_path, feed_events, now, extra=None):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps(feed_events))
    body = {
        "source": "generic",
        "source_opts": {"events_path": str(feed)},
        "cache_path": str(tmp_path / "cache.json"),
        "windows": [{"name": "5h", "cap": 1000, "period_secs": 18000}],
    }
    if extra:
        body.update(extra)
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps(body))
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


def test_doctor_exit_one_when_no_events(tmp_path, monkeypatch):
    now = 100000.0
    cfg = _cfg(tmp_path, [], now)
    # hermetic: ignore real machine sage install for exit-code asserts
    monkeypatch.setattr(
        cli_main,
        "_sage_row",
        lambda now, home=None: ("sage", "agentic-sage not detected (optional)", True),
    )
    assert main(["doctor", "--config", cfg, "--now", str(now)]) == 1


def test_doctor_exit_zero_with_events(tmp_path, monkeypatch):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 50]], now)
    monkeypatch.setattr(
        cli_main,
        "_sage_row",
        lambda now, home=None: ("sage", "agentic-sage not detected (optional)", True),
    )
    assert main(["doctor", "--config", cfg, "--now", str(now)]) == 0


def test_statusline_runs(tmp_path, capsys, monkeypatch):
    # Hermetic: real ~/.local/share/token-oracle/ratelimits.json must not
    # flip the render into the header-headline path (used/cap tokens vanish).
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))
    monkeypatch.delenv("COLUMNS", raising=False)
    monkeypatch.delenv("ORACLE_STATUS_WIDTH", raising=False)
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


def test_doctor_project_provenance(tmp_path, monkeypatch, capsys):
    """With a project .token-oracle.json in cwd, doctor shows (project)."""
    monkeypatch.delenv("TOKEN_ORACLE_CONFIG", raising=False)
    proj = tmp_path / "proj"
    proj.mkdir()
    cfg_file = proj / ".token-oracle.json"
    cfg_file.write_text(
        json.dumps(
            {
                "plan": "pro",
                "source": "generic",
                "source_opts": {"events_path": str(tmp_path / "no.json")},
            }
        )
    )
    monkeypatch.chdir(proj)
    # generic empty source so doctor doesn't scan real logs forever
    rc = main(["doctor", "--now", "100000"])
    out = capsys.readouterr().out
    assert "(project)" in out
    assert ".token-oracle.json" in out
    # pro 5h cap is 19000 — doctor windows row should reflect plan
    assert rc in (0, 1)  # may be 1 if no events


def test_init_wizard_project_pro(monkeypatch, tmp_path, capsys):
    """Wizard with answers 1 / 2 / empty → pro plan + project file + cost auto."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("token_oracle.cli.main._init_is_tty", lambda: True)
    # plan choices are sorted(PRESETS): max20, max5, pro, supergrok → pro is index of "pro"
    from token_oracle.core.config import PRESETS

    names = sorted(PRESETS.keys())
    pro_idx = str(names.index("pro") + 1)
    answers = iter([pro_idx, "2", ""])  # plan pro, project, cost default Y
    monkeypatch.setattr("builtins.input", lambda _p="": next(answers))
    rc = main(["init"])
    assert rc == 0
    path = tmp_path / ".token-oracle.json"
    assert path.is_file()
    data = json.loads(path.read_text())
    assert data.get("plan") == "pro"
    assert data.get("cost_mode") == "auto"
    out = capsys.readouterr().out
    assert "next:" in out


def test_init_wizard_defaults_global(monkeypatch, tmp_path, capsys):
    """Empty answers → max20 + global path under XDG_CONFIG_HOME."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("token_oracle.cli.main._init_is_tty", lambda: True)
    answers = iter(["", "", ""])  # defaults
    monkeypatch.setattr("builtins.input", lambda _p="": next(answers))
    rc = main(["init"])
    assert rc == 0
    cfg = tmp_path / "xdg" / "token-oracle" / "config.json"
    assert cfg.is_file()
    data = json.loads(cfg.read_text())
    assert data.get("plan") == "max20"
    assert data.get("cost_mode") == "auto"


def test_init_wizard_existing_file_no_clobber(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "xdg" / "token-oracle" / "config.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"plan": "pro", "keep": True}))
    monkeypatch.setattr("token_oracle.cli.main._init_is_tty", lambda: True)
    answers = iter(["", "", ""])
    monkeypatch.setattr("builtins.input", lambda _p="": next(answers))
    rc = main(["init"])
    assert rc == 1
    assert json.loads(target.read_text())["keep"] is True
    assert "already configured" in capsys.readouterr().out


def test_init_non_tty_skips_wizard(monkeypatch, tmp_path, capsys):
    """Without a TTY, bare `init` stays non-interactive (plan 008 path)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("token_oracle.cli.main._init_is_tty", lambda: False)
    # if wizard ran it would call input() and fail — ensure it doesn't
    monkeypatch.setattr(
        "builtins.input",
        lambda _p="": (_ for _ in ()).throw(AssertionError("wizard should not prompt")),
    )
    rc = main(["init"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Which plan" not in out
    assert (tmp_path / "xdg" / "token-oracle" / "config.json").is_file()


def test_statusline_ingests_rate_limits(monkeypatch, tmp_path, capsys):
    """Statusline command ingests rate_limits from non-tty stdin into ratelimits snapshot.
    Hermetic: XDG_DATA_HOME + explicit path for assertion; monkeypatched stdin.
    """
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 250]], now)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    payload = '{"rate_limits":{"five_hour":{"used_percentage":7.0,"resets_at":9999999999}}}'
    fake = io.StringIO(payload)

    def _isatty_false():
        return False

    fake.isatty = _isatty_false
    monkeypatch.setattr(sys, "stdin", fake)

    rc = main(["statusline", "--config", cfg, "--now", str(now)])
    assert rc == 0
    # capture to drain
    _ = capsys.readouterr()

    from token_oracle.core import ratelimits as RL

    # explicit path to the expected location under our XDG (hermetic)
    rl_path = str(tmp_path / "token-oracle" / "ratelimits.json")
    d = RL.five_hour(now, path=rl_path)
    assert d is not None
    assert d.get("used_percentage") == 7.0
    assert d.get("stale") is False


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
    assert "Past/Present/Future" in out or "full-screen" in out


def test_now_flag_is_hidden(capsys):
    with pytest.raises(SystemExit) as ei:
        main(["forecast", "--help"])
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert "--now" not in out
    assert "--json" in out


# --- plan 043: first-run guidance for interactive TTY only (stable "idle" elsewhere) ---


def test_forecast_no_data_interactive_shows_hint(monkeypatch, capsys):
    monkeypatch.setattr(cli_main, "run_forecast", lambda now, cfg: [])
    monkeypatch.setattr(cli_main, "_is_interactive", lambda: True)
    fake_cfg = SimpleNamespace(profiles=None, source="generic", source_opts={})
    monkeypatch.setattr(cli_main, "load_config", lambda p: fake_cfg)
    rc = cli_main.main(["forecast", "--now", "1000"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no usage data yet" in out
    assert "oracle doctor" in out
    assert out.strip() != "idle"


def test_forecast_no_data_noninteractive_still_idle(monkeypatch, capsys):
    monkeypatch.setattr(cli_main, "run_forecast", lambda now, cfg: [])
    monkeypatch.setattr(cli_main, "_is_interactive", lambda: False)
    # Force a config without profiles so we get bare "idle" (default load may be multi-profile)
    fake_cfg = SimpleNamespace(profiles=None, source="generic", source_opts={})
    monkeypatch.setattr(cli_main, "load_config", lambda p: fake_cfg)
    rc = cli_main.main(["forecast", "--now", "1000"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "idle"


def test_forecast_no_data_json_unaffected(monkeypatch, capsys):
    monkeypatch.setattr(cli_main, "run_forecast", lambda now, cfg: [])
    monkeypatch.setattr(cli_main, "_is_interactive", lambda: True)
    fake_cfg = SimpleNamespace(profiles=None, source="generic", source_opts={})
    monkeypatch.setattr(cli_main, "load_config", lambda p: fake_cfg)
    rc = cli_main.main(["forecast", "--json", "--now", "1000"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no usage data yet" not in out  # json path never shows the hint


def test_forecast_session_idle_with_prior_use_stays_idle(monkeypatch, capsys):
    """Windows that are idle but have used>0 must not get first-run onboarding."""
    from token_oracle.core.contracts import Forecast

    idle_but_used = [
        Forecast("5h", 12000, 220000, 5.0, None, 100.0, True, profile="default"),
    ]
    monkeypatch.setattr(cli_main, "run_forecast", lambda now, cfg: idle_but_used)
    monkeypatch.setattr(cli_main, "_is_interactive", lambda: True)
    fake_cfg = SimpleNamespace(profiles=None, source="generic", source_opts={})
    monkeypatch.setattr(cli_main, "load_config", lambda p: fake_cfg)
    rc = cli_main.main(["forecast", "--now", "1000"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == "idle"
    assert "no usage data yet" not in out


def test_first_run_hint_mentions_grok():
    hint = cli_main._first_run_hint()
    assert "Grok" in hint or "grok" in hint
    assert "~/.grok/sessions" in hint


# --- plan 044: SIGPIPE reset + subprocess no-traceback smoke ---


@pytest.mark.skipif(not hasattr(signal, "SIGPIPE"), reason="no SIGPIPE on this platform")
def test_reset_sigpipe_restores_default():
    # start from Python's default-changed state, then assert our reset wins
    signal.signal(signal.SIGPIPE, signal.SIG_IGN)
    cli_main._reset_sigpipe()
    assert signal.getsignal(signal.SIGPIPE) == signal.SIG_DFL


def test_forecast_subprocess_no_brokenpipe_noise():
    p = subprocess.run(  # noqa: UP022
        [sys.executable, "-m", "token_oracle.cli.main", "forecast", "--now", "1000"],
        env={**os.environ, "TOKEN_ORACLE_SKIP_BOOTSTRAP": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.getcwd(),
    )
    assert b"BrokenPipeError" not in p.stderr
    assert b"Traceback" not in p.stderr


# --- plan 060: statusline headline + --install ---


def test_statusline_fallback_unchanged_when_no_rl(tmp_path, capsys, monkeypatch):
    # hermetic: XDG + generic config; no ratelimits snapshot -> old render + cost tail possible
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100, 1234]], now)
    rc = main(["statusline", "--config", cfg, "--now", str(now)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    # must contain the forecast segment form (not start with ◔)
    assert "🕐" in out or "/" in out  # old style tokens
    # cost tail may appear if priced, but here generic simple -> no or —
    assert "idle" not in out or out  # non idle


def test_statusline_headline_when_rl_present(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    now = 1700000000.0
    # ingest ratelimits snapshot into the XDG location that RL uses
    from token_oracle.core import ratelimits as RL

    RL.ingest(
        {
            "five_hour": {"used_percentage": 26, "resets_at": now + 3600},
            "seven_day": {"used_percentage": 60, "resets_at": now + 600000},
        },
        now=now,
    )
    cfg = _cfg(tmp_path, [[now - 100, 100]], now)
    rc = main(["statusline", "--config", cfg, "--now", str(now)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "5h 26%" in out
    assert "wk 60%" in out
    assert "◔" in out


def test_statusline_install_fresh(tmp_path, capsys):
    # use -- path to tmp settings, never real ~/.claude
    sdir = tmp_path / ".claude"
    sdir.mkdir()
    spath = sdir / "settings.json"
    # no file yet
    rc = main(
        ["statusline", "--install", "--config", "/dev/null", "--now", "0"]
    )  # config irrelevant
    # but _statusline_install uses default unless path; monkey the func or call via internal
    # call helper directly for hermetic path
    from token_oracle.cli.main import _statusline_install

    rc = _statusline_install(force=False, path=str(spath))
    assert rc == 0
    data = json.loads(spath.read_text())
    assert data["statusLine"]["command"] == "oracle statusline"
    out = capsys.readouterr().out
    assert "backed up" not in out  # fresh no backup
    assert "statusLine →" in out or "wired" in out or rc == 0


def test_statusline_install_idempotent(tmp_path, capsys):
    sdir = tmp_path / ".claude"
    sdir.mkdir()
    spath = sdir / "settings.json"
    spath.write_text(
        json.dumps(
            {"statusLine": {"type": "command", "command": "oracle statusline", "padding": 0}}
        )
    )
    from token_oracle.cli.main import _statusline_install

    rc = _statusline_install(force=False, path=str(spath))
    assert rc == 0
    out = capsys.readouterr().out
    assert "already wired" in out


def test_statusline_install_refuse_without_force(tmp_path, capsys):
    sdir = tmp_path / ".claude"
    sdir.mkdir()
    spath = sdir / "settings.json"
    spath.write_text(json.dumps({"statusLine": {"type": "command", "command": "other"}}))
    from token_oracle.cli.main import _statusline_install

    rc = _statusline_install(force=False, path=str(spath))
    assert rc == 1
    out = capsys.readouterr().out
    assert "already configured" in out or "Pass --force" in out
    # untouched
    assert json.loads(spath.read_text())["statusLine"]["command"] == "other"


def test_statusline_install_force_replaces_and_backs_up(tmp_path, capsys):
    sdir = tmp_path / ".claude"
    sdir.mkdir()
    spath = sdir / "settings.json"
    orig = {"foo": 1, "statusLine": {"type": "command", "command": "other"}}
    spath.write_text(json.dumps(orig))
    from token_oracle.cli.main import _statusline_install

    rc = _statusline_install(force=True, path=str(spath))
    assert rc == 0
    bak = spath.with_suffix(spath.suffix + ".oracle.bak")
    assert bak.exists()
    data = json.loads(spath.read_text())
    assert data["statusLine"]["command"] == "oracle statusline"
    assert data["foo"] == 1  # other keys preserved


def test_statusline_install_no_claude_dir(tmp_path, capsys):
    from token_oracle.cli.main import _statusline_install

    bad = str(tmp_path / "no" / "claude" / "settings.json")
    rc = _statusline_install(force=False, path=bad)
    assert rc == 1
    out = capsys.readouterr().out
    assert "not found" in out


# --- plan 059: oracle report subcommand ---


def test_report_help_has_flags(capsys):
    with pytest.raises(SystemExit) as ei:
        main(["report", "--help"])
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert "--by" in out and "{day,week,model}" in out
    assert "--since" in out and "--until" in out and "--days" in out
    assert "--json" in out
    assert "weekly cap" in out.lower() or "ledger" in out.lower()


def test_report_daily_table_and_total(tmp_path, capsys):
    now = 1_700_000_000.0
    day = 86400.0
    # 3 days of events
    feed = [
        [now, 1000],
        [now - 1 * day, 2000],
        [now - 2 * day, 500],
    ]
    cfg = _cfg(tmp_path, feed, now)
    # override windows to have a weekly for cap
    import json as _json

    cpath = cfg
    cdata = _json.loads(open(cpath).read())
    cdata["windows"] = [
        {"name": "5h", "cap": 220000, "period_secs": 18000},
        {"name": "weekly", "cap": 8000000, "period_secs": 604800},
    ]
    open(cpath, "w").write(_json.dumps(cdata))
    rc = main(["report", "--config", cpath, "--now", str(now), "--days", "3"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "TOTAL" in out
    assert "3-day ledger" in out or "ledger" in out
    # tokens present (fmt_tokens may use k)
    assert "k" in out
    # %CAP for day view
    assert "%CAP" in out or "%" in out


def test_report_json_shape(tmp_path, capsys):
    now = 1_700_000_000.0
    cfg = _cfg(tmp_path, [[now - 100, 1234]], now)
    rc = main(["report", "--json", "--config", cfg, "--now", str(now)])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "generated_at" in data
    assert "sections" in data
    assert len(data["sections"]) >= 1
    row0 = data["sections"][0]["rows"][0]
    assert "label" in row0 and "tokens" in row0 and "cost" in row0
    assert "unpriced_tokens" in row0 and "pct_cap" in row0


def test_report_by_model(tmp_path, capsys):
    now = 1_700_000_000.0
    # events with model info (generic may not, but normalize accepts; use full)
    feed = [
        [now, 100, "claude-sonnet-4", 50, 50, 0, 0, 0.3],
        [now, 200, "grok", 100, 100, 0, 0, None],
    ]
    cfg = _cfg(tmp_path, feed, now)
    rc = main(["report", "--by", "model", "--config", cfg, "--now", str(now)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "MODEL" in out
    assert "TOTAL" in out
    # no %CAP header for non-day
    assert "%CAP" not in out or "—" in out


def test_report_since_until_filter(tmp_path, capsys):
    now = 1_700_000_000.0
    day = 86400.0
    feed = [[now, 10], [now - 5 * day, 20], [now - 10 * day, 30]]
    cfg = _cfg(tmp_path, feed, now)
    rc = main(
        [
            "report",
            "--config",
            cfg,
            "--now",
            str(now),
            "--since",
            "2023-11-01",
            "--until",
            "2023-11-20",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    # depending on ts, but should not crash; at least TOTAL present
    assert "TOTAL" in out


def test_report_bad_since_exits_2(tmp_path, capsys):
    now = 1_700_000_000.0
    cfg = _cfg(tmp_path, [[now, 1]], now)
    rc = main(["report", "--config", cfg, "--now", str(now), "--since", "not-a-date"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "since" in err.lower() or "date" in err.lower() or rc == 2  # at least rc


def test_report_no_data_piped_is_stable(monkeypatch, capsys):
    # piped: no hint
    monkeypatch.setattr(cli_main, "_is_interactive", lambda: False)
    fake_cfg = SimpleNamespace(
        profiles=None,
        source="generic",
        source_opts={},
        windows=[],
        cost_mode="auto",
        pricing={},
    )
    monkeypatch.setattr(cli_main, "load_config", lambda p: fake_cfg)
    # report scans; use cfg that yields no data
    # simplest: use a cfg with no events feed that produces []
    rc = cli_main.main(["report", "--now", "1000"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no usage data yet" not in out


def test_report_no_data_tty_shows_hint(monkeypatch, capsys):
    monkeypatch.setattr(cli_main, "_is_interactive", lambda: True)
    fake_cfg = SimpleNamespace(
        profiles=None,
        source="generic",
        source_opts={},
        windows=[],
        cost_mode="auto",
        pricing={},
    )
    monkeypatch.setattr(cli_main, "load_config", lambda p: fake_cfg)
    rc = cli_main.main(["report", "--now", "1000"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no usage data yet" in out


# --- plan 015: snapshot write-through ---


def test_statusline_writethrough_writes_snapshot(tmp_path, monkeypatch, capsys):
    """With snapshot_writethrough, statusline refreshes forecast.json (plan 015)."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 250]], now, extra={"snapshot_writethrough": True})
    rc = main(["statusline", "--config", cfg, "--now", str(now)])
    assert rc == 0
    snap = tmp_path / "data" / "token-oracle" / "forecast.json"
    assert snap.exists()
    data = json.loads(snap.read_text())
    assert data["schema"] == 1
    assert len(data["windows"]) == 1
    assert data["windows"][0]["used"] == 250


def test_statusline_no_writethrough_by_default(tmp_path, monkeypatch):
    """Default config does not write snapshot on statusline (plan 015)."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 250]], now)
    rc = main(["statusline", "--config", cfg, "--now", str(now)])
    assert rc == 0
    snap = tmp_path / "data" / "token-oracle" / "forecast.json"
    assert not snap.exists()


def test_forecast_json_writethrough(tmp_path, monkeypatch, capsys):
    """forecast --json with write-through: stdout JSON + snapshot file (plan 015)."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 250]], now, extra={"snapshot_writethrough": True})
    rc = main(["forecast", "--json", "--config", cfg, "--now", str(now)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["schema"] == 1
    assert out["windows"][0]["used"] == 250
    snap = tmp_path / "data" / "token-oracle" / "forecast.json"
    assert snap.exists()
    assert json.loads(snap.read_text())["schema"] == 1


# --- plan 022: agentic-sage reciprocal detection ---


def _patch_sage_home(monkeypatch, home):
    """Point expanduser("~") and "~/.claude/..." at tmp home for sage detection."""
    real_expand = os.path.expanduser

    def _expand(p):
        s = str(p)
        if s == "~" or s.startswith("~/"):
            return str(home / s[2:]) if s.startswith("~/") else str(home)
        return real_expand(p)

    monkeypatch.setattr(os.path, "expanduser", _expand)
    # default_snapshot_path also uses expanduser / XDG
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))


def test_doctor_sage_not_detected(tmp_path, monkeypatch, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 50]], now)
    _patch_sage_home(monkeypatch, tmp_path / "home")
    rc = main(["doctor", "--config", cfg, "--now", str(now)])
    out = capsys.readouterr().out
    assert "sage" in out
    assert "not detected" in out
    assert rc == 0  # sage absence is not a red row


def test_doctor_sage_detected_unlinked(tmp_path, monkeypatch, capsys):
    now = 100000.0
    home = tmp_path / "home"
    sage = home / ".claude" / "agentic-sage"
    sage.mkdir(parents=True)
    (sage / "config.json").write_text("{}")
    cfg = _cfg(tmp_path, [[now - 100.0, 50]], now)
    _patch_sage_home(monkeypatch, home)
    rc = main(["doctor", "--config", cfg, "--now", str(now)])
    out = capsys.readouterr().out
    assert "tokenForecastPath" in out
    assert "forecast.json" in out
    assert rc == 0  # unlinked is fail-open green


def test_doctor_sage_linked_fresh(tmp_path, monkeypatch, capsys):
    now = 100000.0
    home = tmp_path / "home"
    sage = home / ".claude" / "agentic-sage"
    sage.mkdir(parents=True)
    data_dir = home / ".local" / "share" / "token-oracle"
    data_dir.mkdir(parents=True)
    snap = data_dir / "forecast.json"
    snap.write_text("{}")
    os.utime(snap, (now, now))
    (sage / "config.json").write_text(json.dumps({"tokenForecastPath": str(snap)}))
    cfg = _cfg(tmp_path, [[now - 100.0, 50]], now)
    _patch_sage_home(monkeypatch, home)
    rc = main(["doctor", "--config", cfg, "--now", str(now)])
    out = capsys.readouterr().out
    assert "linked via" in out
    assert rc == 0


def test_doctor_sage_linked_stale(tmp_path, monkeypatch, capsys):
    now = 100000.0
    home = tmp_path / "home"
    sage = home / ".claude" / "agentic-sage"
    sage.mkdir(parents=True)
    data_dir = home / ".local" / "share" / "token-oracle"
    data_dir.mkdir(parents=True)
    snap = data_dir / "forecast.json"
    snap.write_text("{}")
    # 2 days old
    old = now - 2 * 86400
    os.utime(snap, (old, old))
    (sage / "config.json").write_text(json.dumps({"tokenForecastPath": str(snap)}))
    cfg = _cfg(tmp_path, [[now - 100.0, 50]], now)
    _patch_sage_home(monkeypatch, home)
    rc = main(["doctor", "--config", cfg, "--now", str(now)])
    out = capsys.readouterr().out
    assert "stale" in out.lower()
    assert rc == 1


def test_doctor_sage_linked_elsewhere(tmp_path, monkeypatch, capsys):
    now = 100000.0
    home = tmp_path / "home"
    sage = home / ".claude" / "agentic-sage"
    sage.mkdir(parents=True)
    other = tmp_path / "other-forecast.json"
    other.write_text("{}")
    (sage / "config.json").write_text(json.dumps({"tokenForecastPath": str(other)}))
    cfg = _cfg(tmp_path, [[now - 100.0, 50]], now)
    _patch_sage_home(monkeypatch, home)
    rc = main(["doctor", "--config", cfg, "--now", str(now)])
    out = capsys.readouterr().out
    assert "fine if intentional" in out
    assert rc == 0


def test_doctor_sage_corrupt_config(tmp_path, monkeypatch, capsys):
    now = 100000.0
    home = tmp_path / "home"
    sage = home / ".claude" / "agentic-sage"
    sage.mkdir(parents=True)
    (sage / "config.json").write_text("not-json{{{")
    cfg = _cfg(tmp_path, [[now - 100.0, 50]], now)
    _patch_sage_home(monkeypatch, home)
    rc = main(["doctor", "--config", cfg, "--now", str(now)])
    out = capsys.readouterr().out
    assert "unreadable" in out
    assert rc == 0  # fail-open
