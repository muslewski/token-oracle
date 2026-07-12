import json
import os

from token_oracle.sources.base import available, get_source
from token_oracle.sources.claude_code import iter_usage_events


def _line(ts, inp, out, cc, cr=0, model="claude-sonnet-4-5", cost=None):
    msg = {
        "usage": {
            "input_tokens": inp,
            "output_tokens": out,
            "cache_creation_input_tokens": cc,
            "cache_read_input_tokens": cr,
        },
        "model": model,
    }
    obj = {"timestamp": ts, "message": msg}
    if cost is not None:
        obj["costUSD"] = cost
    return json.dumps(obj)


def test_claude_registered():
    assert "claude_code" in available()


def test_iter_usage_events(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(
        "\n".join(
            [
                _line(
                    "1970-01-01T01:00:00Z", 100, 50, 10, cr=5, cost=0.02
                ),  # 160 tokens (cache_read excluded from the limit sum)
                "garbage-not-json",
                json.dumps({"timestamp": "1970-01-01T02:00:00Z"}),  # no usage -> skip
            ]
        )
    )
    evs = list(iter_usage_events(str(p)))
    assert evs == [(3600.0, 160, "claude-sonnet-4-5", 100, 50, 10, 5, 0.02)]
    # element 1 (the limit-weighted sum) excludes cache_read_input_tokens
    assert evs[0][1] == 100 + 50 + 10


def test_source_scan_collects_within_window(tmp_path):
    proj = tmp_path / "projects" / "repo"
    proj.mkdir(parents=True)
    (proj / "a.jsonl").write_text(_line("1970-01-01T01:00:00Z", 100, 0, 0))
    src = get_source("claude_code", {"projects_dir": str(tmp_path / "projects")})
    files, events = src.scan({}, now=7200.0, window=7200.0)
    assert events == [(3600.0, 100, "claude-sonnet-4-5", 100, 0, 0, 0, None)]
    assert any("a.jsonl" in k for k in files)


def test_source_scan_excludes_future_events(tmp_path):
    proj = tmp_path / "projects" / "repo"
    proj.mkdir(parents=True)
    # far-future timestamp should be excluded; past timestamp should be included
    future_ts = "2099-01-01T00:00:00Z"
    past_ts = "1970-01-01T01:00:00Z"  # 3600.0
    (proj / "b.jsonl").write_text(
        "\n".join(
            [
                _line(future_ts, 999, 0, 0),
                _line(past_ts, 50, 0, 0),
            ]
        )
    )
    src = get_source("claude_code", {"projects_dir": str(tmp_path / "projects")})
    now = 7200.0
    _, events = src.scan({}, now=now, window=7200.0)
    tss = [e[0] for e in events]
    assert all(ts <= now for ts in tss), f"future event leaked: {tss}"
    assert (3600.0, 50, "claude-sonnet-4-5", 50, 0, 0, 0, None) in events


def test_scan_skips_unchanged_files_via_state(tmp_path):
    proj = tmp_path / "projects" / "repo"
    proj.mkdir(parents=True)
    p = proj / "a.jsonl"
    p.write_text(_line("1970-01-01T01:00:00Z", 100, 0, 0))  # 100 tokens
    src = get_source("claude_code", {"projects_dir": str(tmp_path / "projects")})
    now = 7200.0
    window = 7200.0
    files1, events1 = src.scan({}, now=now, window=window)
    assert events1 == [(3600.0, 100, "claude-sonnet-4-5", 100, 0, 0, 0, None)]

    st_before = os.stat(p)
    mtime_before, atime_before = st_before.st_mtime, st_before.st_atime

    # Rewrite with a same-length-but-different payload, then restore the
    # original mtime so (mtime, size) match the cached state exactly.
    new_line = _line("1970-01-01T01:00:00Z", 999, 0, 0)
    assert len(new_line) == len(_line("1970-01-01T01:00:00Z", 100, 0, 0))
    p.write_text(new_line)
    os.utime(p, (atime_before, mtime_before))
    st_after = os.stat(p)
    assert st_after.st_mtime == mtime_before
    assert st_after.st_size == st_before.st_size

    _, events2 = src.scan(files1, now=now, window=window)
    # Cache hit proven: same mtime+size => no re-parse => still the old value.
    assert events2 == [(3600.0, 100, "claude-sonnet-4-5", 100, 0, 0, 0, None)]


def test_scan_reparses_on_size_change(tmp_path):
    proj = tmp_path / "projects" / "repo"
    proj.mkdir(parents=True)
    p = proj / "a.jsonl"
    p.write_text(_line("1970-01-01T01:00:00Z", 100, 0, 0))
    src = get_source("claude_code", {"projects_dir": str(tmp_path / "projects")})
    now = 7200.0
    window = 7200.0
    files1, events1 = src.scan({}, now=now, window=window)
    assert events1 == [(3600.0, 100, "claude-sonnet-4-5", 100, 0, 0, 0, None)]

    with open(p, "a") as fh:
        fh.write("\n" + _line("1970-01-01T01:30:00Z", 50, 0, 0))

    _, events2 = src.scan(files1, now=now, window=window)
    assert (3600.0, 100, "claude-sonnet-4-5", 100, 0, 0, 0, None) in events2
    assert (5400.0, 50, "claude-sonnet-4-5", 50, 0, 0, 0, None) in events2
    assert len(events2) == 2


def test_scan_prunes_deleted_files(tmp_path):
    proj = tmp_path / "projects" / "repo"
    proj.mkdir(parents=True)
    p = proj / "a.jsonl"
    p.write_text(_line("1970-01-01T01:00:00Z", 100, 0, 0))
    src = get_source("claude_code", {"projects_dir": str(tmp_path / "projects")})
    now = 7200.0
    window = 7200.0
    files1, events1 = src.scan({}, now=now, window=window)
    assert events1 == [(3600.0, 100, "claude-sonnet-4-5", 100, 0, 0, 0, None)]

    os.remove(p)
    files2, events2 = src.scan(files1, now=now, window=window)
    assert events2 == []
    assert not any("a.jsonl" in k for k in files2)


def test_scan_drops_files_older_than_cutoff(tmp_path):
    proj = tmp_path / "projects" / "repo"
    proj.mkdir(parents=True)
    p = proj / "a.jsonl"
    p.write_text(_line("1970-01-01T01:00:00Z", 100, 0, 0))
    now = 7200.0
    window = 7200.0
    old_mtime = now - window - 1000  # older than cutoff (now - window)
    os.utime(p, (old_mtime, old_mtime))
    src = get_source("claude_code", {"projects_dir": str(tmp_path / "projects")})
    files, events = src.scan({}, now=now, window=window)
    assert events == []
    assert not any("a.jsonl" in k for k in files)


def test_iter_usage_events_skips_malformed_lines(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(
        "\n".join([
            "123",                                   # valid JSON, not an object
            '"just a string"',                       # valid JSON, not an object
            "[1, 2, 3]",                             # valid JSON, not an object
            "null",                                  # valid JSON null
            json.dumps({"message": "not-a-dict", "timestamp": "1970-01-01T01:00:00Z"}),
            json.dumps({"message": {"usage": 5}, "timestamp": "1970-01-01T01:00:00Z"}),  # usage not a dict
            _line("1970-01-01T01:00:00Z", 100, 50, 10),  # the one GOOD line -> 160 tokens
        ])
    )
    evs = list(iter_usage_events(str(p)))
    assert evs == [(3600.0, 160, "claude-sonnet-4-5", 100, 50, 10, 0, None)]


def test_scan_survives_malformed_line(tmp_path):
    proj = tmp_path / "projects" / "repo"
    proj.mkdir(parents=True)
    (proj / "a.jsonl").write_text("\n".join(["[1,2,3]", _line("1970-01-01T01:00:00Z", 100, 0, 0)]))
    src = get_source("claude_code", {"projects_dir": str(tmp_path / "projects")})
    files, events = src.scan({}, now=7200.0, window=7200.0)
    assert events == [(3600.0, 100, "claude-sonnet-4-5", 100, 0, 0, 0, None)]
