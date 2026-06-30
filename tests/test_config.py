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
    p.write_text(json.dumps({
        "source": "claude_code",
        "windows": [
            {"name": "daily", "cap": 5000, "period_secs": 86400,
             "anchor": "2026-01-01T00:00:00Z"}
        ],
    }))
    c = CFG.load_config(str(p))
    assert c.source == "claude_code"
    w = c.windows[0]
    assert isinstance(w, Window) and w.name == "daily" and w.cap == 5000
    assert w.anchor == 1767225600.0   # 2026-01-01T00:00:00Z

def test_corrupt_falls_back(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("{ broken")
    c = CFG.load_config(str(p))
    assert {w.name for w in c.windows} == {"5h", "weekly"}
