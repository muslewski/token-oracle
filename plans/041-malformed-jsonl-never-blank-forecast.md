# Plan 041 — A malformed log line must never blank the forecast

**Status:** TODO
**Written against commit:** `646a2ac`
**Priority:** P0 (truthfulness gate — blocks any launch)
**Effort:** S–M
**Depends on:** 005 (characterization tests — DONE), 016 (8-field event record — DONE).
No file conflict with 039/040; may run in parallel.

---

## Why this matters (the bug)

The forecast is built by scanning the user's Claude Code / Grok JSONL logs. A **single
malformed line** — a line that is valid JSON but is not an object (`123`, `"hi"`, `[1,2]`,
`null`), or an object whose `message`/`usage` is the wrong type — **crashes the whole scan**,
and the engine's top-level `except Exception: return []` then makes `forecast()` return an
empty list. The dashboard shows **nothing / 0%** until that line ages out of the scan
window (up to `HIST_SECS` later). Real Claude Code logs occasionally contain such lines
(summary records, tool-only turns, partial writes during an active session). For a tool
whose entire value is "always show me my real usage," silently going blank on one bad line
is a truthfulness failure.

The engine's blanket `except: return []` is **intentional** ("never raises" contract —
`plans/README.md` records it as a deliberate design, not a finding). So the fix is **not**
to touch that outer guard. The fix is to (a) make the source iterators **skip** bad lines
instead of raising, and (b) make the engine's single-source path **fall back to cached
events** on a scan failure — exactly as the multi-profile path already does.

## Root cause (verified by direct read at `646a2ac`)

**Layer 1 — the source iterator crashes on a non-dict line.**
`token_oracle/sources/claude_code.py`, `iter_usage_events` (line 41):
```python
msg = obj.get("message") or {}      # AttributeError if obj is 123 / "x" / [..] / None
usage = msg.get("usage")            # AttributeError if message is a truthy non-dict (e.g. a string)
```
`json.loads` on `123`/`"x"`/`[1,2]`/`null` succeeds (they are valid JSON), so the
`except ValueError` at line 39 does **not** catch them. The generator then raises
`AttributeError` mid-iteration.

`token_oracle/sources/grok.py`, `iter_total_tokens_reports` (line 35) has the **identical**
flaw:
```python
meta = (obj.get("params") or {}).get("_meta") or {}   # AttributeError if obj is a non-dict JSON value
```

**Layer 2 — the crash propagates and blanks everything.**
`token_oracle/core/engine.py` **legacy single-source path** (lines 148-156) calls
`source.scan(...)` with **no try/except**:
```python
source = get_source(cfg.source, cfg.source_opts)
if now - cache.get("lastAggregate", 0) >= AGGREGATE_INTERVAL:
    files, events = source.scan(cache.get("files", {}), now, HIST_SECS)   # raises -> bubbles to outer except -> return []
    ...
```
The **multi-profile path** (`_forecast_one`, lines 48-60) already wraps the same scan in
`try/except` and falls back to `cslice.get("events", [])` on failure. The single path is
missing that guard — an inconsistency, and the reason a single-source config (the default,
and the operator's) blanks while a profiles config would not.

## The fix (design — implement exactly this)

Three edits, each independently valuable; do them in order and commit each.

### Step 1 — Harden `iter_usage_events` (claude_code.py) to skip malformed lines

In `token_oracle/sources/claude_code.py`, `iter_usage_events`, after `obj = json.loads(raw)`
succeeds, replace the message/usage extraction (lines 41-43) with type-guarded versions:

```python
            try:
                obj = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue
            msg = obj.get("message")
            if not isinstance(msg, dict):
                continue
            usage = msg.get("usage")
            if not isinstance(usage, dict):
                continue
            ts = parse_ts(obj.get("timestamp"))
            if ts is None:
                continue
            ...
```

Everything below (`tok = _limit_tokens(usage)` etc.) is unchanged — `usage` is now
guaranteed to be a dict, so `_limit_tokens`'s `.get(...)` calls are safe. This makes the
generator **skip** any malformed line and keep yielding good ones.

### Step 2 — Harden `iter_total_tokens_reports` (grok.py) the same way

In `token_oracle/sources/grok.py`, `iter_total_tokens_reports`, after `obj = json.loads(raw)`
(line 32-34), add a dict guard and make the nested access type-safe:

```python
                try:
                    obj = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                if not isinstance(obj, dict):
                    continue
                params = obj.get("params")
                meta = params.get("_meta") if isinstance(params, dict) else None
                meta = meta if isinstance(meta, dict) else {}
                tot = meta.get("totalTokens")
                ts = obj.get("timestamp")
                if ts is not None and isinstance(tot, (int, float)) and tot >= 0:
                    yield (float(ts), int(tot))
```

Behavior is identical for well-formed lines; malformed/non-dict lines are skipped instead
of crashing.

### Step 3 — Give the engine single-source path the same scan fallback as the multi path

In `token_oracle/core/engine.py`, the legacy single path (lines 148-158), wrap the
scan+aggregate block in `try/except` mirroring `_forecast_one` (lines 48-60). On failure,
fall back to the cached events — **do not** let it reach the outer `return []`:

```python
            source = get_source(cfg.source, cfg.source_opts)
            if now - cache.get("lastAggregate", 0) >= AGGREGATE_INTERVAL:
                try:
                    files, events = source.scan(cache.get("files", {}), now, HIST_SECS)
                    events = [events_mod.normalize(e) for e in events]
                    cache["files"] = files
                    cache["events"] = [list(e) for e in events]
                    cache["lastAggregate"] = now
                    pairs = events_mod.as_pairs(events)
                    cache["profile"] = build_profile(pairs, now)
                    save_cache(cache, cfg.cache_path)
                except Exception:
                    events = [events_mod.normalize(e) for e in cache.get("events", [])]
            else:
                events = [events_mod.normalize(e) for e in cache.get("events", [])]
```

**Do NOT touch** the outer `try/except Exception: return []` at the end of `forecast()` — it
is the intentional "never raises" backstop. This inner guard simply means a scan failure
degrades to last-good cached events (an honest, if slightly stale, forecast) instead of a
blank one.

## Files in scope

- `token_oracle/sources/claude_code.py` — `iter_usage_events` type guards (Step 1).
- `token_oracle/sources/grok.py` — `iter_total_tokens_reports` type guards (Step 2).
- `token_oracle/core/engine.py` — single-path scan `try/except` fallback (Step 3).
- `tests/test_sources_claude.py`, `tests/test_sources_grok.py`, `tests/test_engine.py` — tests below.

## Files explicitly OUT of scope (do NOT touch)

- The engine's outer `except Exception: return []` (intentional — see `plans/README.md`
  "considered and rejected").
- `token_oracle/sources/generic.py` — its `scan` already wraps parsing in `try/except`
  (`OSError, ValueError, TypeError`), so a bad row can't blank the forecast (it truncates
  the tail — a separate, minor, out-of-scope nit; note it in maintenance only).
- `_forecast_one` (the multi path) — it already has the guard; leave it.
- `windows.py`, `config.py`, `profile.py`, anything under `live/`.

## Test plan

**A. `tests/test_sources_claude.py` — malformed lines are skipped, good events survive.**
Reuse the existing `_line(...)` helper.

```python
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
```

**B. `tests/test_sources_grok.py` — same resilience for the grok iterator.**
Follow that file's existing fixture style; a minimal direct test:

```python
import json
from token_oracle.sources.grok import iter_total_tokens_reports

def test_grok_iter_skips_malformed_lines(tmp_path):
    p = tmp_path / "updates.jsonl"
    p.write_text("\n".join([
        "42",                                        # non-dict JSON
        '["a","b"]',                                 # non-dict JSON
        json.dumps({"params": "not-a-dict", "timestamp": 1000.0}),
        json.dumps({"params": {"_meta": {"totalTokens": 500}}, "timestamp": 1000.0}),  # good
    ]))
    reports = list(iter_total_tokens_reports(str(p)))
    assert reports == [(1000.0, 500)]
```

**C. `tests/test_engine.py` — a scan failure degrades to cached events, not a blank forecast.**
Prove Step 3 by monkeypatching a source whose `scan` raises, with a warm cache present.
Check the existing `test_engine.py` imports/patterns and follow them; the essence:

```python
def test_single_path_scan_failure_falls_back_to_cached_events(monkeypatch, tmp_path):
    from token_oracle.core import engine as ENG
    from token_oracle.core.config import Config
    from token_oracle.core.contracts import Window

    now = 10_000_000.0

    class BoomSource:
        def scan(self, *a, **k):
            raise RuntimeError("malformed log blew up scan")

    monkeypatch.setattr("token_oracle.sources.base.get_source", lambda *a, **k: BoomSource())

    # warm cache with one good event well within the window, and a stale lastAggregate
    # so the aggregate branch (which calls scan) is taken.
    cache = {
        "files": {},
        "events": [[now - 100, 5000, "claude-sonnet-4-5", 5000, 0, 0, 0, None]],
        "profile": [],
        "lastAggregate": 0,
    }
    monkeypatch.setattr(ENG, "load_cache", lambda *a, **k: cache)
    monkeypatch.setattr(ENG, "save_cache", lambda *a, **k: None)

    cfg = Config(
        source="claude_code",
        windows=[Window(name="5h", cap=220000, period_secs=18000)],
        cache_path=str(tmp_path / "cache.json"),
    )
    fs = ENG.forecast(now, cfg)
    assert fs, "forecast blanked on scan failure instead of using cached events"
    # the cached 5000-token event is reflected in the 5h window's used
    five = next(f for f in fs if f.window == "5h")
    assert five.used >= 5000
```

> Executor: adapt names to what `test_engine.py` already uses (it may import `forecast`
> directly and construct `Config`/`Window` differently). The assertion that matters:
> **with a raising `scan` and a warm cache, `forecast()` returns non-empty forecasts built
> from the cached events.** Before Step 3 this returns `[]`.

## Verification gates (run all; all must pass)

```
pip install -e ".[dev]"   # NOTE: clobbers the user's `oracle` entrypoint; advisor re-symlinks after merge — not your concern
python -m pytest -q
ruff check token_oracle tests
ruff format --check token_oracle tests
mypy token_oracle --ignore-missing-imports
```

Expected: all green; existing scan/iter tests (`test_iter_usage_events`,
`test_source_scan_*`, grok scan tests) still pass unchanged + the new resilience tests pass.

## Done criteria (machine-checkable)

- `python -c "import json,tempfile,os; from token_oracle.sources.claude_code import iter_usage_events as f; p=tempfile.mktemp(); open(p,'w').write('123\n[1,2]\n\"x\"\nnull\n'); print(list(f(p)))"`
  prints `[]` (no crash, all bad lines skipped).
- The single-path engine fallback test in `test_engine.py` passes (forecast non-empty under a raising scan).
- `rg -n "isinstance\(obj, dict\)" token_oracle/sources/claude_code.py token_oracle/sources/grok.py` shows the new guards in both files.
- `python -m pytest -q` passes; `ruff` / `ruff format --check` / `mypy` clean.
- One commit per step.

## Escape hatches — STOP and report instead of improvising if:

- `test_engine.py` constructs forecasts through a path you can't monkeypatch cleanly (e.g.
  it always goes through `load_config`) — report how it's structured; a smaller unit test on
  the single-path branch is acceptable, but the behavior (non-blank on scan failure) MUST be
  asserted somewhere.
- Adding the guards changes the output of an existing test (they should not — well-formed
  lines are unaffected). If `test_iter_usage_events` or a scan test changes value, STOP:
  you've altered good-line behavior, which is wrong.
- You discover another caller relies on `iter_usage_events`/`iter_total_tokens_reports`
  raising on bad input (nothing should) — report it.

## Maintenance note

- `generic.py`'s single `try/except` around its whole row loop means one bad row silently
  truncates the remaining rows (doesn't blank, but drops the tail). It's the documented
  "copy/adapt" reference adapter, so left as-is; if it ever becomes a real data path, give
  it per-row `try/continue` like the two first-class sources now have.
- The pattern to keep across all source iterators: **validate shape immediately after
  `json.loads`, `continue` on anything unexpected, never assume a line is a dict.** New
  source adapters (ADAPTERS.md) should follow it.
