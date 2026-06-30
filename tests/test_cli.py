import json
from oracle.cli.main import main

def _cfg(tmp_path, feed_events, now):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps(feed_events))
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({
        "source": "generic", "source_opts": {"events_path": str(feed)},
        "cache_path": str(tmp_path / "cache.json"),
        "windows": [{"name": "5h", "cap": 1000, "period_secs": 18000}],
    }))
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

def test_doctor_exit_zero(tmp_path):
    now = 100000.0
    cfg = _cfg(tmp_path, [], now)
    assert main(["doctor", "--config", cfg, "--now", str(now)]) == 0

def test_statusline_runs(tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 250]], now)
    assert main(["statusline", "--config", cfg, "--now", str(now)]) == 0
    out = capsys.readouterr().out
    assert out.strip()                 # renders a non-empty status line
    assert "/1k" in out or "0k" in out  # used/cap tokens segment present

def test_doctor_footer_and_badges(tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [], now)
    main(["doctor", "--config", cfg, "--now", str(now)])
    out = capsys.readouterr().out
    assert "oracle doctor" in out
    assert "ok ·" in out and "need attention" in out
    assert "✓" in out  # source + windows are valid here → at least one pass


def test_doctor_flags_bad_source(tmp_path, capsys):
    from oracle.cli.main import _doctor_lines
    from oracle.core.config import load_config
    cfg_path = _cfg(tmp_path, [], 100000.0)
    cfg = load_config(cfg_path)
    cfg.source = "nope-not-real"
    out = "\n".join(_doctor_lines(cfg, cfg_path, color=False))
    assert "✗" in out and "1 need attention" in out
