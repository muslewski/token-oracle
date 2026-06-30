import json, os
from oracle.sources.base import get_source, available
from oracle.sources.claude_code import iter_usage_events

def _line(ts, inp, out, cc):
    return json.dumps({"timestamp": ts, "message": {"usage": {
        "input_tokens": inp, "output_tokens": out,
        "cache_creation_input_tokens": cc}}})

def test_claude_registered():
    assert "claude_code" in available()

def test_iter_usage_events(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text("\n".join([
        _line("1970-01-01T01:00:00Z", 100, 50, 10),  # 160 tokens
        "garbage-not-json",
        json.dumps({"timestamp": "1970-01-01T02:00:00Z"}),  # no usage -> skip
    ]))
    evs = list(iter_usage_events(str(p)))
    assert evs == [(3600.0, 160)]

def test_source_scan_collects_within_window(tmp_path):
    proj = tmp_path / "projects" / "repo"
    proj.mkdir(parents=True)
    (proj / "a.jsonl").write_text(_line("1970-01-01T01:00:00Z", 100, 0, 0))
    src = get_source("claude_code", {"projects_dir": str(tmp_path / "projects")})
    files, events = src.scan({}, now=7200.0, window=7200.0)
    assert events == [(3600.0, 100)]
    assert any("a.jsonl" in k for k in files)

def test_source_scan_excludes_future_events(tmp_path):
    proj = tmp_path / "projects" / "repo"
    proj.mkdir(parents=True)
    # far-future timestamp should be excluded; past timestamp should be included
    future_ts = "2099-01-01T00:00:00Z"
    past_ts = "1970-01-01T01:00:00Z"  # 3600.0
    (proj / "b.jsonl").write_text("\n".join([
        _line(future_ts, 999, 0, 0),
        _line(past_ts, 50, 0, 0),
    ]))
    src = get_source("claude_code", {"projects_dir": str(tmp_path / "projects")})
    now = 7200.0
    _, events = src.scan({}, now=now, window=7200.0)
    tss = [ts for ts, _ in events]
    assert all(ts <= now for ts in tss), f"future event leaked: {tss}"
    assert (3600.0, 50) in events
