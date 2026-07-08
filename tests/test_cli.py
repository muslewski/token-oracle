import json
import os

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
    # avoid the claude_code default source scanning the real ~/.claude/projects
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
