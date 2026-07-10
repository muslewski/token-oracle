# Plan 016: Event detail v2 — carry model and token classes through the pipeline

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ada32e9..HEAD -- token_oracle/sources/ token_oracle/core/engine.py token_oracle/core/cache.py token_oracle/core/contracts.py tests/test_sources_claude.py tests/test_sources_generic.py tests/test_cache.py tests/test_engine.py ADAPTERS.md`
> If any in-scope file changed since `ada32e9`, compare the "Current state"
> excerpts against live code before proceeding; on a mismatch, STOP.
> Note: plans 013/014 (TODO in the index) also touch `token_oracle/sources/` —
> if either landed first, expect an entry-point loader in `sources/base.py`
> and possibly a new provider module; the event-shape changes below still
> apply, but re-verify every excerpt.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED (touches the cache format and every source; prediction math must not change)
- **Depends on**: none (005's characterization tests, already DONE, are the safety net)
- **Category**: direction (foundation for cost + history features)
- **Planned at**: commit `ada32e9`, 2026-07-02

## Why this matters

Sources today emit bare `(timestamp, tokens)` tuples — the model name and the
per-class token split (input / output / cache-create / cache-read) are read
from the Claude Code JSONL and immediately discarded. Every planned feature
that users of competing tools take for granted — USD cost (needs per-model,
per-class prices), a daily per-model history table, cache-lane views — is
impossible until events carry that detail. This plan widens the event record
end-to-end (source → cache → engine) while keeping the prediction math
byte-identical: the forecast pipeline keeps consuming `(ts, tokens)` pairs
derived from the wider record. Plans 017 (pricing) and 019 (past view/report)
build directly on this.

## Current state

- `token_oracle/sources/claude_code.py` — parses transcripts; `_limit_tokens`
  (lines 12–19) sums `input_tokens + output_tokens + cache_creation_input_tokens`
  and drops everything else. `iter_usage_events` (lines 22–45) yields
  `(ts, tok)`. `scan()` (lines 53–83) stores per-file `"events": [[ts, tok], ...]`
  and returns a sorted flat list of `(float, int)` tuples.
  The parsed JSON object has `obj["message"]["usage"]` (dict with the four
  token-class keys), `obj["message"]["model"]` (string like
  `"claude-sonnet-4-5"`), and sometimes a top-level `obj["costUSD"]` (float,
  present in older Claude Code versions only).
- `token_oracle/sources/generic.py` — reads a user JSON file of
  `[[ts, tokens], ...]` pairs (lines 16–29); documented stub adapter.
- `token_oracle/sources/base.py` — registry; docstring (lines 1–2) states the
  old contract: "A source turns provider data into neutral (timestamp, tokens)
  events".
- `token_oracle/core/engine.py` — the facade. Lines 17–26:

  ```python
  if now - cache.get("lastAggregate", 0) >= AGGREGATE_INTERVAL:
      files, events = source.scan(cache.get("files", {}), now, HIST_SECS)
      cache["files"] = files
      cache["events"] = [[float(ts), int(tok)] for ts, tok in events]
      cache["lastAggregate"] = now
      cache["profile"] = build_profile(events, now)
      save_cache(cache, cfg.cache_path)
  else:
      events = [(float(ts), int(tok)) for ts, tok in cache.get("events", [])]
  ```

  `build_profile` (core/profile.py:35) and `compute_window`
  (core/windows.py:45) iterate events as `for ts, tok in events` /
  `sum(tok for ts, tok in events ...)` — they require exactly-2 unpacking.
- `token_oracle/core/cache.py` — schema-less JSON dict
  `{files, lastAggregate, profile, events}`; `load_cache` (lines 11–21)
  accepts any dict with a `"files"` key.
- `token_oracle/core/contracts.py` — docstring line 1–2: "Sources emit bare
  (timestamp, tokens) tuples — see ADAPTERS.md."
- `ADAPTERS.md` — documents the Source interface and the neutral-pairs
  contract for third-party adapters.
- Conventions: stdlib only (`pyproject.toml` `dependencies = []`); every
  module opens with a terse invariant docstring; "never raises" at facades
  (engine.py:2); tests are function-style pytest with `tmp_path`/`monkeypatch`
  (exemplar: `tests/test_config.py`).

## The new event shape (decided — do not redesign)

An event is a JSON array (tuple in memory) of up to 8 elements:

```
[ts, tokens, model, input, output, cache_create, cache_read, cost_usd]
 0    1       2      3      4       5             6           7
```

- Elements 0–1 are exactly today's pair: epoch float, limit-weighted int
  (input + output + cache_creation). **The math never reads past index 1.**
- `model`: string or `null`. `input`/`output`/`cache_create`/`cache_read`:
  ints, 0 when absent. `cost_usd`: float or `null` (from the transcript's
  `costUSD` when present; consumed by plan 017's `auto` mode).
- Short events remain valid: a legacy 2-element `[ts, tok]` (old caches, the
  generic source, third-party adapters) is normalized by padding with
  `None, 0, 0, 0, 0, None`.

Add one tiny pure module to own this shape, `token_oracle/core/events.py`:

```python
"""Event record shape shared by sources, cache, and consumers. An event is
[ts, tokens, model, input, output, cache_create, cache_read, cost_usd];
legacy [ts, tokens] pairs stay valid. Prediction math only ever reads the
first two fields — see as_pairs. Stdlib only."""

N_FIELDS = 8

def normalize(e):
    """Any 2..8-element sequence -> canonical 8-tuple. Never raises on
    well-typed short input."""
    ts, tok = float(e[0]), int(e[1])
    model = e[2] if len(e) > 2 else None
    ints = [int(e[i]) if len(e) > i and e[i] is not None else 0 for i in (3, 4, 5, 6)]
    cost = float(e[7]) if len(e) > 7 and e[7] is not None else None
    return (ts, tok, model, *ints, cost)

def as_pairs(events):
    """The 2-field view the forecast math consumes."""
    return [(float(e[0]), int(e[1])) for e in events]
```

(Exact bodies may vary; the signatures, the field order, and the "math only
reads index 0–1" invariant are load-bearing.)

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass (101 at plan time; more after) |
| Lint | `ruff check token_oracle/` | exit 0 |
| Format | `ruff format --check token_oracle/` | exit 0 |
| Types | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |

## Scope

**In scope** (the only files you should modify/create):
- `token_oracle/core/events.py` (create)
- `token_oracle/sources/claude_code.py`
- `token_oracle/sources/generic.py`
- `token_oracle/sources/base.py` (docstring only)
- `token_oracle/core/engine.py`
- `token_oracle/core/contracts.py` (docstring only)
- `tests/test_events.py` (create), `tests/test_sources_claude.py`,
  `tests/test_sources_generic.py`, `tests/test_engine.py`, `tests/test_cache.py`
- `ADAPTERS.md` (contract section update)

**Out of scope** (do NOT touch):
- `token_oracle/core/profile.py`, `token_oracle/core/windows.py` — the math
  stays pair-based; if you feel the need to edit them, you are off-plan.
- `token_oracle/snapshot/writer.py` and the `Forecast` dataclass fields —
  the external snapshot contract does not change in this plan.
- `token_oracle/dashboard/`, `token_oracle/adapters/`, `token_oracle/cli/`.
- Any pricing/cost computation (that is plan 017).

## Git workflow

- Branch: `advisor/016-event-detail-contract-v2` (matches the repo's
  `advisor/NNN-slug` convention, e.g. `advisor/007-dash-portable-clear`).
- Conventional commits, e.g. `feat(sources): carry model + token classes in events`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add `core/events.py` with tests

Create the module shown above. Create `tests/test_events.py` covering:
`normalize` on a 2-element list (pads correctly), on a full 8-element list
(round-trips), on a 7-element list (cost defaults None), and `as_pairs` on a
mixed list of 2- and 8-element events.

**Verify**: `python -m pytest -q tests/test_events.py` → all pass.

### Step 2: Widen the claude_code source

In `token_oracle/sources/claude_code.py`:
- `iter_usage_events` additionally extracts
  `model = msg.get("model")` (where `msg = obj.get("message") or {}`),
  the four usage ints (`usage.get("cache_read_input_tokens", 0)` is the new
  fourth), and `cost = obj.get("costUSD")`. Yield the 8-tuple
  `(ts, tok, model, i, o, cc, cr, cost)` — keep `tok = _limit_tokens(usage)`
  unchanged (cache_read stays excluded from the limit-weighted sum; that is
  a documented accounting decision in `plans/README.md`).
- In `scan()`, store per-file events as 8-element lists and build the flat
  return list with `key=lambda e: e[0]` sorting (tuples with `None` model
  fields are not orderable — do NOT rely on default tuple sort).
- Old per-file cache state may hold 2-element events. `scan()` only reuses a
  file's entry when mtime+size match; entries carried over unparsed must be
  emitted through `normalize()` so the flat list is uniformly 8 fields.

Update `tests/test_sources_claude.py`: extend the JSONL fixture lines with
`"model"` inside `message` and a `cache_read_input_tokens` value; assert the
yielded event carries them and that element 1 still equals
input+output+cache_creation. Keep every existing assertion passing unchanged
(characterization tests from plan 005 live here — they pin the incremental
scan behavior).

**Verify**: `python -m pytest -q tests/test_sources_claude.py` → all pass.

### Step 3: Widen the generic source and the registry docstring

- `generic.py`: accept rows of length ≥2; emit `normalize(row)` for each.
  The docstring keeps `[[timestamp, tokens], ...]` as the minimal documented
  format and mentions optional extra fields.
- `base.py` docstring: "neutral (timestamp, tokens) events" → "neutral event
  records (see core/events.py); minimally (timestamp, tokens)".
- `contracts.py` docstring line 1–2: same correction, pointing at
  `core/events.py`.

**Verify**: `python -m pytest -q tests/test_sources_generic.py` → all pass.

### Step 4: Engine + cache round-trip

In `engine.py`, replace the two conversion sites:

```python
cache["events"] = [list(events_mod.normalize(e)) for e in events]
...
events = [events_mod.normalize(e) for e in cache.get("events", [])]
```

and feed the math its pair view: `pairs = events_mod.as_pairs(events)`;
pass `pairs` to `build_profile` and `compute_window`. Return value and
`Forecast` list are unchanged. An old cache file (2-element events) must load
and forecast without a rebuild — `normalize` handles it; do not add a cache
version key.

Extend `tests/test_engine.py`: one test that seeds a cache file containing
legacy `[[ts, tok], ...]` events (see existing cache-seeding tests in
`tests/test_cache.py` / `tests/test_engine.py` for the fixture pattern) and
asserts `forecast()` returns the same numbers as with 8-field events of equal
(ts, tok).

**Verify**: `python -m pytest -q` → all pass, including plan 005's
characterization tests untouched and green.

### Step 5: ADAPTERS.md contract update

Update the Source interface section: events are arrays of 2–8 fields, field
table as in "The new event shape" above, legacy pairs remain valid forever.
State explicitly that fields 0–1 are the only ones the forecast math reads.

**Verify**: `grep -n "cache_read" ADAPTERS.md` → at least one hit;
`python -m pytest -q` still green.

## Test plan

- New: `tests/test_events.py` (normalize/as_pairs, ~5 cases).
- Extended: claude_code fixture with model/cache_read/costUSD; generic with a
  mixed-width rows file; engine legacy-cache compatibility test.
- Pattern: function-style pytest, `tmp_path`, no classes — model after
  `tests/test_config.py`.
- Verification: `python -m pytest -q` → all pass; count strictly greater
  than 101.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `python -m pytest -q` exits 0 with >101 tests
- [ ] `ruff check token_oracle/ && ruff format --check token_oracle/ && mypy token_oracle/ --ignore-missing-imports` all exit 0
- [ ] `python - <<'EOF'` prints `True True`:
  ```python
  from token_oracle.core.events import normalize, as_pairs
  e = normalize([1.0, 5])
  print(len(e) == 8, as_pairs([e, (2.0, 3, "m", 1, 1, 1, 0, None)]) == [(1.0, 5), (2.0, 3)])
  EOF
  ```
- [ ] `grep -n "for ts, tok in events" token_oracle/core/engine.py` → no matches (engine uses normalize/as_pairs)
- [ ] `git status` shows no modified files outside the in-scope list
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- Excerpts in "Current state" don't match live code (drift).
- Any plan-005 characterization test fails after your change — the math
  contract broke; do not "fix" the characterization test.
- You find `profile.py` or `windows.py` must change to make tests pass.
- The Claude Code JSONL fixtures in tests lack a `model` field and you are
  tempted to invent a different event shape to cope — the shape is fixed;
  absent fields are `None`/0.

## Maintenance notes

- Cache files grow ~3–4× (8 fields vs 2 per event). At a heavy 1 000
  events/day × 63-day retention this is single-digit MB of JSON — acceptable;
  if it ever isn't, the fix is daily rollups for old events, not narrowing
  the record.
- Plans 013/014 (source entry points, second provider) must emit the same
  shape; ADAPTERS.md is the contract they read.
- Reviewer focus: `scan()` sort key (`e[0]`, not tuple sort), legacy-pad path,
  and that element 1 still excludes `cache_read_input_tokens`.
- Deferred: exposing per-model data in `forecast.json` (plan 017/019 decide
  what surfaces externally).
