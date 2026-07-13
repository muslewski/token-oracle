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
    # internal: absent "live" in source normalizes to explicit false (defensive)
    assert c.live.get("headed") is False


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


# --- Plan 039 cap validation tests ---


def test_validate_caps_rejects_impossible_magnitudes():
    five, wk, issues = CFG._validate_external_caps(57000000, 270000000, 220000, 8000000)
    assert five is None and wk is None
    assert len(issues) == 2
    assert any("fiveHourCap" in i for i in issues)
    assert any("weeklyCap" in i for i in issues)


def test_validate_caps_accepts_in_band_plan_change():
    # a plausible cap bump (~1.1x / ~1.15x) is honored, no issues
    five, wk, issues = CFG._validate_external_caps(240000, 9200000, 220000, 8000000)
    assert five == 240000 and wk == 9200000
    assert issues == []


def test_validate_caps_rejects_5h_ge_weekly():
    # test cross-window invariant #3 directly with custom presets (both pass band but 5h >= weekly)
    five, wk, issues = CFG._validate_external_caps(900, 800, 500, 900)
    assert wk == 800
    assert five is None
    assert any("impossible" in i for i in issues)


def test_validate_caps_rejects_nonpositive_and_nonnumeric():
    assert CFG._validate_external_caps(0, -5, 220000, 8000000)[0] is None
    assert CFG._validate_external_caps("big", None, 220000, 8000000)[0] is None
    # None weekly supplied -> no issue for weekly
    five, wk, issues = CFG._validate_external_caps(None, None, 220000, 8000000)
    assert five is None and wk is None and issues == []


def test_preset_caps_reads_shipped_presets():
    assert CFG._preset_caps("max20") == (220000, 8000000)
    assert CFG._preset_caps("pro") == (19000, 700000)
    assert CFG._preset_caps("nonsense") == (220000, 8000000)  # max20 fallback


def test_load_config_rejects_bogus_external_caps(monkeypatch, tmp_path):
    monkeypatch.setattr(CFG, "_should_apply_real_claude_limits", lambda: True)
    monkeypatch.setattr(
        CFG,
        "load_claude_limits",
        lambda: {"fiveHourCap": 57000000, "weeklyCap": 270000000, "plan": "max20"},
    )
    c = CFG.load_config(str(tmp_path / "none.json"))  # -> max20 preset windows
    weekly = next(w for w in c.windows if w.name == "weekly")
    five = next(w for w in c.windows if w.name == "5h")
    assert weekly.cap == 8000000  # preset kept, NOT 270000000
    assert five.cap == 220000  # preset kept, NOT 57000000
    assert any("weeklyCap" in i and "rejected" in i for i in c.issues)
    assert any("fiveHourCap" in i and "rejected" in i for i in c.issues)


def test_load_config_honors_plausible_external_caps(monkeypatch, tmp_path):
    monkeypatch.setattr(CFG, "_should_apply_real_claude_limits", lambda: True)
    monkeypatch.setattr(
        CFG,
        "load_claude_limits",
        lambda: {"fiveHourCap": 240000, "weeklyCap": 9200000, "plan": "max20"},
    )
    c = CFG.load_config(str(tmp_path / "none.json"))
    weekly = next(w for w in c.windows if w.name == "weekly")
    assert weekly.cap == 9200000  # in-band external value honored
    assert not any("rejected" in i for i in c.issues)


def test_five_hour_data_prefers_own_snapshot(monkeypatch, tmp_path):
    """Own ratelimits snapshot is preferred and returns source=server.
    Must be hermetic: XDG_DATA_HOME + ingest with explicit or default under it.
    """
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.delenv("TOKEN_ORACLE_NO_REAL_LIMITS", raising=False)
    # clear any pytest marker effect on other paths (our ratelimits path is independent)
    now = 123456.0
    # ingest using the default_path (honors XDG we set)
    from token_oracle.core import ratelimits as RL

    RL.ingest(
        {"five_hour": {"used_percentage": 42.0, "resets_at": now + 7200}},
        now=now,
    )
    d = CFG.try_get_claude_five_hour_data(now)
    assert d is not None
    assert d["source"] == "server"
    assert d["projected_pct"] == 42.0
    assert "reset_in_secs" in d


def test_non_object_json_config_records_issue(tmp_path, monkeypatch):
    """JSON array/string configs must not silently fall through to max20."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("[]\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    from token_oracle.core.config import load_config

    c = load_config(str(cfg_path))
    assert any("not a JSON object" in i for i in c.issues)
