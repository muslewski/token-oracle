import json

from token_oracle.core import config as CFG
from token_oracle.core.contracts import Window


def test_default_is_max20_when_missing(tmp_path):
    c = CFG.load_config(str(tmp_path / "none.json"))
    names = {w.name for w in c.windows}
    assert names == {"5h", "weekly"}
    five = next(w for w in c.windows if w.name == "5h")
    assert five.cap == 220000 and five.period_secs == 18000


def test_paths_honor_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "dat"))
    assert CFG.default_config_path().endswith("/cfg/token-oracle/config.json")
    assert CFG.default_cache_path().endswith("/dat/token-oracle/cache.json")


def test_loads_custom_windows_and_anchor(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(
        json.dumps(
            {
                "source": "claude_code",
                "windows": [
                    {
                        "name": "daily",
                        "cap": 5000,
                        "period_secs": 86400,
                        "anchor": "2026-01-01T00:00:00Z",
                    }
                ],
            }
        )
    )
    c = CFG.load_config(str(p))
    assert c.source == "claude_code"
    w = c.windows[0]
    assert isinstance(w, Window) and w.name == "daily" and w.cap == 5000
    assert w.anchor == 1767225600.0  # 2026-01-01T00:00:00Z


def test_corrupt_falls_back(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("{ broken")
    c = CFG.load_config(str(p))
    assert {w.name for w in c.windows} == {"5h", "weekly"}


def test_window_missing_name_is_skipped_with_issue(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"windows": [{"cap": 100, "period_secs": 60}]}))
    c = CFG.load_config(str(p))
    assert c.windows == []
    assert len(c.issues) == 1
    assert "windows[0]" in c.issues[0]


def test_window_bad_cap_is_skipped(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"windows": [{"name": "x", "cap": "abc", "period_secs": 60}]}))
    c = CFG.load_config(str(p))
    assert c.windows == []
    assert len(c.issues) == 1
    assert "windows[0]" in c.issues[0]


def test_window_nonpositive_period_is_skipped(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"windows": [{"name": "x", "cap": 1, "period_secs": 0}]}))
    c = CFG.load_config(str(p))
    assert c.windows == []
    assert len(c.issues) == 1
    assert "windows[0]" in c.issues[0]


def test_bad_anchor_string_is_skipped_not_degraded(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(
        json.dumps(
            {"windows": [{"name": "x", "cap": 1, "period_secs": 60, "anchor": "not-a-date"}]}
        )
    )
    c = CFG.load_config(str(p))
    assert c.windows == []
    assert len(c.issues) == 1
    assert "anchor" in c.issues[0]


def test_windows_not_a_list_falls_back_with_issue(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"windows": "5h"}))
    c = CFG.load_config(str(p))
    assert {w.name for w in c.windows} == {"5h", "weekly"}
    assert len(c.issues) == 1


def test_corrupt_json_records_issue(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("{ broken")
    c = CFG.load_config(str(p))
    assert len(c.issues) == 1
    assert {w.name for w in c.windows} == {"5h", "weekly"}


def test_valid_config_has_no_issues(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(
        json.dumps(
            {
                "source": "claude_code",
                "windows": [
                    {
                        "name": "daily",
                        "cap": 5000,
                        "period_secs": 86400,
                        "anchor": "2026-01-01T00:00:00Z",
                    }
                ],
            }
        )
    )
    c = CFG.load_config(str(p))
    assert c.issues == []

    missing = CFG.load_config(str(tmp_path / "none.json"))
    assert missing.issues == []


def test_mixed_valid_and_invalid_window_entries(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(
        json.dumps(
            {
                "windows": [
                    {"name": "ok", "cap": 100, "period_secs": 60},
                    {"cap": 100, "period_secs": 60},
                ]
            }
        )
    )
    c = CFG.load_config(str(p))
    assert [w.name for w in c.windows] == ["ok"]
    assert len(c.issues) == 1
    assert "windows[1]" in c.issues[0]
