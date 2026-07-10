import json
import os

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


def test_nonstring_cache_path_falls_back_with_issue(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"cache_path": 123}))
    c = CFG.load_config(str(p))
    assert c.cache_path == os.path.expanduser(CFG.default_cache_path())
    assert len(c.issues) == 1
    assert "cache_path" in c.issues[0]


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


def test_plan_pro_yields_19000_cap(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"plan": "pro"}))
    c = CFG.load_config(str(p))
    assert c.plan == "pro"
    five = next(w for w in c.windows if w.name == "5h")
    assert five.cap == 19000
    assert c.issues == []


def test_plan_max5_yields_88000_cap(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"plan": "max5"}))
    c = CFG.load_config(str(p))
    assert c.plan == "max5"
    five = next(w for w in c.windows if w.name == "5h")
    assert five.cap == 88000


def test_unknown_plan_falls_back_to_max20_with_issue(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"plan": "ultra-mega"}))
    c = CFG.load_config(str(p))
    assert c.plan == "max20"
    five = next(w for w in c.windows if w.name == "5h")
    assert five.cap == 220000
    assert len(c.issues) == 1
    assert "plan" in c.issues[0]


def test_file_windows_override_chosen_plan_windows(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(
        json.dumps(
            {
                "plan": "pro",
                "windows": [{"name": "custom", "cap": 42, "period_secs": 60}],
            }
        )
    )
    c = CFG.load_config(str(p))
    assert c.plan == "pro"
    assert [w.name for w in c.windows] == ["custom"]
    assert c.windows[0].cap == 42


def test_bad_cost_mode_falls_back_to_auto_with_issue(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"cost_mode": "bogus"}))
    c = CFG.load_config(str(p))
    assert c.cost_mode == "auto"
    assert len(c.issues) == 1
    assert "cost_mode" in c.issues[0]


def test_valid_cost_mode_is_kept(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"cost_mode": "display"}))
    c = CFG.load_config(str(p))
    assert c.cost_mode == "display"
    assert c.issues == []


def test_pricing_non_dict_falls_back_to_empty_with_issue(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"pricing": ["not", "a", "dict"]}))
    c = CFG.load_config(str(p))
    assert c.pricing == {}
    assert len(c.issues) == 1
    assert "pricing" in c.issues[0]


def test_pricing_dict_is_kept(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"pricing": {"my-model": {"input": 1.0, "output": 2.0}}}))
    c = CFG.load_config(str(p))
    assert c.pricing == {"my-model": {"input": 1.0, "output": 2.0}}
    assert c.issues == []


def test_default_plan_and_cost_mode_when_missing(tmp_path):
    c = CFG.load_config(str(tmp_path / "none.json"))
    assert c.plan == "max20"
    assert c.cost_mode == "auto"
    assert c.pricing == {}


def test_live_headed_parsed_true(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"plan": "max20", "live": {"headed": True}}))
    c = CFG.load_config(str(p))
    assert c.headed_enabled() is True
    assert c.live == {"headed": True}


def test_live_headed_default_false(tmp_path):
    c = CFG.load_config(str(tmp_path / "none.json"))
    assert c.headed_enabled() is False
    assert c.live == {}


def test_live_headed_invalid_ignored(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"live": {"headed": "yes"}}))
    c = CFG.load_config(str(p))
    assert c.headed_enabled() is False
    assert any("live.headed" in iss for iss in c.issues)
    # does not crash, falls back


def test_update_config_file_roundtrip(tmp_path):
    p = tmp_path / "c.json"
    # seed with a plan so we can assert preservation
    p.write_text(json.dumps({"plan": "pro"}))
    CFG.update_config_file(str(p), {"live": {"headed": True}})
    loaded = json.loads(p.read_text())
    assert loaded.get("live", {}).get("headed") is True
    assert loaded.get("plan") == "pro"
    # flip it
    CFG.update_config_file(str(p), {"live": {"headed": False}})
    loaded2 = json.loads(p.read_text())
    assert loaded2.get("live", {}).get("headed") is False
    assert loaded2.get("plan") == "pro"  # still present
