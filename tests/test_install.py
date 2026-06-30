import json

from install import write_default_config
from uninstall import remove_config


def test_writes_preset_config(tmp_path):
    p = str(tmp_path / "config.json")
    write_default_config(p, preset="max20")
    data = json.load(open(p))
    assert {w["name"] for w in data["windows"]} == {"5h", "weekly"}


def test_no_clobber_without_force(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"source":"custom"}')
    write_default_config(str(p), preset="max20")  # must NOT overwrite
    assert json.load(open(p))["source"] == "custom"
    write_default_config(str(p), preset="max20", force=True)  # force overwrites
    assert "windows" in json.load(open(p))


def test_remove_config(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{}")
    assert remove_config(str(p)) is True
    assert not p.exists()
    assert remove_config(str(p)) is False
