import json
import os

from token_oracle.sources.base import available, get_source


def _update_line(ts, total_tokens, update_type="AgentThoughtChunk"):
    """Build a minimal session/update line carrying _meta.totalTokens (cumulative)."""
    obj = {
        "timestamp": ts,
        "method": "session/update",
        "params": {
            "sessionId": "test-sess",
            "update": {"sessionUpdate": update_type},
            "_meta": {"totalTokens": total_tokens, "updateType": update_type},
        },
    }
    return json.dumps(obj)


def test_grok_registered():
    assert "grok" in available()


def test_grok_reads_deltas_from_totals(tmp_path):
    sess = tmp_path / "proj" / "sess-uuid"
    sess.mkdir(parents=True)
    p = sess / "updates.jsonl"
    # cumulative totals; deltas: 100 then +50 =150 total
    p.write_text(
        "\n".join(
            [
                _update_line(1000.0, 100),
                _update_line(1010.0, 150),
                "garbage",
                json.dumps({"timestamp": 1020.0}),  # no meta
            ]
        )
    )
    src = get_source("grok", {"sessions_dir": str(tmp_path)})
    files, events = src.scan({}, now=2000.0, window=2000.0)
    # deltas only
    assert [(e[0], e[1]) for e in events] == [(1000.0, 100), (1010.0, 50)]
    assert any("updates.jsonl" in k for k in files)


def test_grok_missing_dir_is_empty(tmp_path):
    src = get_source("grok", {"sessions_dir": str(tmp_path / "nope")})
    files, events = src.scan({}, now=100.0, window=100.0)
    assert events == []


def test_grok_uses_mtime_size_cache_skip(tmp_path):
    sess = tmp_path / "p" / "s"
    sess.mkdir(parents=True)
    p = sess / "updates.jsonl"
    p.write_text(_update_line(1000.0, 123))
    src = get_source("grok", {"sessions_dir": str(tmp_path)})
    now = 2000.0
    window = 2000.0
    f1, e1 = src.scan({}, now=now, window=window)
    assert [(e[0], e[1]) for e in e1] == [(1000.0, 123)]

    st = os.stat(p)
    m0, a0 = st.st_mtime, st.st_atime
    # same mtime+size, rewrite content (would change deltas if reparsed)
    p.write_text(_update_line(1000.0, 999))
    os.utime(p, (a0, m0))
    f2, e2 = src.scan(f1, now=now, window=window)
    # cached -> old delta value
    assert [(e[0], e[1]) for e in e2] == [(1000.0, 123)]


def test_grok_prunes_gone_and_old(tmp_path):
    sess = tmp_path / "p" / "s"
    sess.mkdir(parents=True)
    p = sess / "updates.jsonl"
    p.write_text(_update_line(1000.0, 10))
    src = get_source("grok", {"sessions_dir": str(tmp_path)})
    now = 2000.0
    window = 2000.0
    f1, e1 = src.scan({}, now=now, window=window)
    assert len(e1) == 1

    os.remove(p)
    f2, e2 = src.scan(f1, now=now, window=window)
    assert e2 == []
    assert not any("updates.jsonl" in k for k in f2)


def _signals_obj(tokens):
    return json.dumps(
        {"contextTokensUsed": tokens, "contextWindowTokens": 512000, "modelsUsed": ["grok-build"]}
    )


def test_grok_reads_live_from_signals(tmp_path):
    sess = tmp_path / "proj" / "sess-uuid"
    sess.mkdir(parents=True)
    upd = sess / "updates.jsonl"
    upd.write_text(_update_line(1000.0, 100))
    sig = sess / "signals.json"
    # fresher mtime + higher tokens -> should add delta
    sig.write_text(_signals_obj(250))
    # touch mtime to future
    now = 3000.0
    os.utime(sig, (now, now))
    src = get_source("grok", {"sessions_dir": str(tmp_path)})
    files, events = src.scan({}, now=now, window=2000.0)
    # from updates 100, then signals adds +150
    totals = [e[1] for e in events]
    assert 100 in totals
    assert any(d == 150 for d in totals)
