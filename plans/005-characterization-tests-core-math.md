# Plan 005: Characterization tests for the burn profile, window projection, and incremental scan

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat d2b4d32..HEAD -- token_oracle/core/profile.py token_oracle/core/windows.py token_oracle/sources/claude_code.py tests/test_profile.py tests/test_windows.py tests/test_sources_claude.py tests/test_engine.py`
> If any of the three **source** files changed since `d2b4d32`, STOP — these
> tests pin current behavior, and pinning drifted behavior needs advisor
> review. Changes to the test files from other plans are fine.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW (test-only — no production code changes)
- **Depends on**: none. Gates Plans 010 and 012 (they refactor what these tests pin).
- **Category**: tests
- **Planned at**: commit `d2b4d32`, 2026-07-01

## Why this matters

The product's differentiating logic — the 168-bucket empirical-Bayes burn profile, the prior/measured projection blend, the rolling-window re-anchor walk, and the mtime/size incremental scan — has almost no behavioral test coverage. `test_profile.py` has 3 shallow tests for an 82-line numerical module; the projection blend and the re-anchor walk have zero tests; the incremental scan's cache-hit path (the whole point of `files_state`) is untested; and `tests/test_windows.py:49-50` contains a conditional assert that silently asserts nothing when the projection is ≤ 100%. Two upcoming plans (cache-size optimization, real confidence scores) refactor exactly this code — without characterization tests they cannot be executed safely.

**This plan changes no production code.** Every test pins behavior as it exists today. If a test you write fails, you have mis-derived the expectation — fix the test, not the code (see STOP conditions for the one exception).

## Current state

Files under test (read them fully before writing tests):

- `token_oracle/core/profile.py` — 168-bucket (hour-of-week) tok/s profile. Constants: `N_BUCKETS = 168`, `HIST_SECS = 63*24*3600`, `DECAY_HALFLIFE_SECS = 14*24*3600`, `SHRINK_K = 3.0`. `build_profile(events, now)` does empirical-Bayes shrinkage through a backoff chain: per-bucket → (hour, weekday/weekend) → hour-of-day → flat rate. `profile_integral(profile, start, end)` integrates tok/s over wall-clock, splitting at hour boundaries.
- `token_oracle/core/windows.py` — `compute_window(events, now, window, profile=None)`. Key logic at `windows.py:52-66`:

```python
    used = sum(tok for ts, tok in events if start <= ts <= now)
    elapsed = max(1.0, now - start)
    f = min(1.0, max(0.0, elapsed / P))
    measured_term = (used / elapsed) * (reset - now)
    if profile is None:
        hist_cutoff = now - HIST_SECS
        prior_used = sum(tok for ts, tok in events if hist_cutoff <= ts < start)
        prior_span = max(1.0, start - hist_cutoff)
        prior_term = (prior_used / prior_span) * (reset - now)
    else:
        prior_term = profile_integral(profile, now, reset)
    projected = used + (1.0 - f) * prior_term + f * measured_term
```

  and the rolling re-anchor walk at `windows.py:34-42`:

```python
    if not events:
        return None
    start = events[0][0]
    for ts, _tok in events[1:]:
        if ts >= start + P:
            start = ts  # window expired -> re-anchor here
    reset = start + P
    if now > reset:
        return None
```

- `token_oracle/sources/claude_code.py` — `ClaudeCodeSource.scan(files_state, now, window)` at lines 53-83: glob `<projects_dir>/*/*.jsonl`; per file: drop state if `st.st_mtime < cutoff`; **skip re-parse** if `ent.get("mtime") == st.st_mtime and ent.get("size") == st.st_size`; else re-parse via `iter_usage_events`; prune state entries for files no longer globbed; emit sorted `(ts, tok)` events within `[cutoff, now]`.
- `token_oracle/core/timeutil.py:16-19` — `bucket_key(ts)` uses **local time** (`datetime.fromtimestamp(ts).astimezone()`); index = `weekday()*24 + hour`. This makes naive hardcoded bucket expectations timezone-dependent — see the TZ-proof technique below.

Existing tests and their style (flat functions, `tmp_path`, direct asserts):
- `tests/test_profile.py` — 3 tests (empty profile, zero integral, uniform load positive).
- `tests/test_windows.py` — 6 tests; the defective one at lines 43-50:

```python
def test_projection_sets_eta_when_burning_hot():
    now = 100000.0
    w = Window(name="5h", cap=300, period_secs=18000)
    # heavy burst near window start: projected should exceed cap -> eta set
    evs = [(now - 17000.0, 250), (now - 100.0, 40)]
    f = compute_window(evs, now, w)
    if f.projected_pct > 100:
        assert f.eta_to_cap_secs is not None
```

- `tests/test_sources_claude.py` — registration, `iter_usage_events` parsing, basic scan, future-event exclusion. The `_line(ts, inp, out, cc)` helper at lines 7-19 builds a transcript JSONL line; reuse it.
- `tests/test_engine.py` — generic-source cold/warm forecast tests; the `Config(...)` construction pattern at lines 12-17.

**TZ-proof technique** (required for profile tests): never hardcode a bucket index. Derive timestamps from `bucket_key` itself, e.g.:

```python
def _first_ts_where(pred, base=1_800_000_000.0):
    """First hour-aligned ts >= base whose local hour-of-week satisfies pred."""
    t = base - (base % 3600.0)
    for _ in range(24 * 14):
        if pred(bucket_key(t)):
            return t
        t += 3600.0
    raise AssertionError("no matching hour found")
```

Weekend = `bucket_key(t) // 24 >= 5`; weekday = `< 5`. Tests written this way pass in any timezone (CI runs UTC; developer machines vary).

Conventions: stdlib only; no new fixtures/conftest; ruff line-length 100; test files mirror module names.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Focused | `python -m pytest tests/test_profile.py tests/test_windows.py tests/test_sources_claude.py tests/test_engine.py -q` | all pass |
| All | `python -m pytest -q` | all pass |
| Lint | `ruff check token_oracle/ tests/` | exit 0 (note: CI lints only `token_oracle/`, but keep tests clean too) |

## Scope

**In scope** (the only files you should modify):
- `tests/test_profile.py`
- `tests/test_windows.py`
- `tests/test_sources_claude.py`
- `tests/test_engine.py`

**Out of scope** (do NOT touch):
- ANY file under `token_oracle/` — this is a characterization plan. Zero production changes.
- `tests/test_cache.py` — Plan 006 deletes part of it; adding cache tests here would collide.

## Git workflow

- Branch: `advisor/005-characterization-tests`.
- Conventional commit, e.g.: `test: characterize burn profile, projection blend, re-anchor walk, incremental scan`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Fix the conditional assert (test_windows.py)

Replace `test_projection_sets_eta_when_burning_hot` with a construction that *deterministically* projects over cap. With no prior events and a burst at window start, `f` is tiny and `prior_term` is 0, so `projected ≈ used + f · (used/elapsed) · (reset-now)`; easier: make `used` big relative to cap with high measured rate near the window START so the huge `measured_term` × small `f` still clears the cap. Worked example (verify by hand before writing):

- `now = 100000.0`, `P = 18000`, `cap = 300`, events `[(now - 100.0, 280)]`.
- Window starts at first event → `start = now - 100`, `elapsed = 100`, `f = 100/18000 ≈ 0.00556`.
- `measured_term = (280/100) * 17900 = 50120`; `prior_term = 0`.
- `projected = 280 + 0.00556 * 50120 ≈ 558.4` → `projected_pct ≈ 186%` → `eta_to_cap_secs` is not None and > 0.

Assert: `f.projected_pct > 100` (unconditionally), `f.eta_to_cap_secs is not None`, `f.eta_to_cap_secs > 0`.

**Verify**: `python -m pytest tests/test_windows.py -q` → all pass.

### Step 2: Pin the rolling re-anchor walk and window edges (test_windows.py)

Add:

1. `test_rolling_reanchors_across_blocks` — `P = 18000`; events `[(0.0, 100), (20000.0, 50), (39000.0, 25)]`, `now = 40000.0`. Walk: start 0 → re-anchor 20000 (≥ 18000) → re-anchor 39000 (≥ 38000). Assert `used == 25`, `reset_in_secs == 17000.0`, `idle is False`.
2. `test_rolling_expired_is_idle` — events `[(0.0, 100)]`, `now = 20000.0` (> reset 18000) → `idle is True`, `used == 0`, `reset_in_secs == float(P)`.
3. `test_anchored_future_anchor_characterized` — `anchor = now + 1000`, `P = 18000` → current behavior: `n = 0`, `start = anchor` (in the future), `used == 0`, `idle is False`, `reset_in_secs == 19000.0` (> P). This is arguably odd behavior — the test **pins** it and carries a comment: `# characterization: future anchor yields a not-yet-started, non-idle window`.
4. `test_prior_history_raises_early_projection` — same in-window usage, with vs. without prior history (no profile): window `P=18000`, `cap=100000`; scenario A events `[(now-60.0, 100)]`; scenario B same plus heavy history `[(now-50000.0, 50000), (now-40000.0, 50000)]` (before window start). Assert `B.projected_pct > A.projected_pct` and `A.used == B.used == 100`.
5. `test_profile_prior_used_exactly` — constant profile `prof = [0.01]*168` (tok/s), single event window: `projected == used + (1-f)*0.01*(reset-now) + f*measured_term` within `pytest.approx`. Compute the expectation in the test from the same formula inputs (`start = first event`, etc.) — this pins the blend arithmetic itself.

**Verify**: `python -m pytest tests/test_windows.py -q` → all pass (10 total in file).

### Step 3: Pin profile math (test_profile.py)

Add (import `bucket_key` from `token_oracle.core.timeutil`; use the `_first_ts_where` helper from "Current state"):

1. `test_recency_decay_downweights_old_usage` — two single-event histories, identical except age: event A at `now - 3600`, event B at `now - 35*24*3600` (well past one half-life), same tokens, same local hour-of-week bucket (find via `_first_ts_where(lambda b: b == bucket_key(now - 3600))` scanning backwards by 168-hour strides: `ts_b = ts_a - 168*3600*5`). Build two profiles; assert the bucket rate from the old-event profile is strictly lower.
2. `test_weekend_weekday_separation` — heavy usage only in weekend buckets (place ~30 events of 1000 tokens at weekend hours over 3 weeks via `_first_ts_where`); assert mean rate over weekend buckets > mean rate over weekday buckets in the built profile.
3. `test_shrinkage_bounds_sparse_bucket` — a single 100k-token event in one bucket: with `SHRINK_K = 3.0` pseudo-hours, the bucket's rate must be well below the raw `100000/E_bucket` implied rate but above the flat rate. Assert `flat_rate < prof[b] < raw_rate` where you compute `flat` and `raw` from the module's own formulas (this documents the shrinkage direction without hardcoding constants).
4. `test_profile_integral_partial_hours` — constant profile `[r]*168`: `profile_integral(prof, t0 + 1800, t0 + 5400) == pytest.approx(r * 3600)` for an hour-aligned `t0` (spans two buckets, mid-hour boundaries).
5. `test_profile_integral_empty_and_reversed` — `profile_integral([], a, b) == 0.0` and `profile_integral(prof, b, a) == 0.0` when `b > a` reversed (start >= end guard).

**Verify**: `python -m pytest tests/test_profile.py -q` → all pass (8 total). Then re-run with a different timezone to prove TZ-proofing: `TZ=Australia/Sydney python -m pytest tests/test_profile.py -q` → all pass.

### Step 4: Pin the incremental scan (test_sources_claude.py)

Reuse the `_line` helper. Add:

1. `test_scan_skips_unchanged_files_via_state` — write `a.jsonl` with an event of 100 tokens; `files, _ = scan({}, now, window)`. Then rewrite the file with the token count edited to a **same-length** different value (`"100"` → `"999"`, byte length identical) and restore the original mtime with `os.utime(p, (st.st_atime, st.st_mtime))` captured before the rewrite. Re-scan passing the previous `files` state → events still show `100` (cache hit proven: same mtime+size ⇒ no re-parse).
2. `test_scan_reparses_on_size_change` — append a second event line (size changes), re-scan with previous state → both events present.
3. `test_scan_prunes_deleted_files` — scan, `os.remove` the file, re-scan with previous state → returned `files` no longer contains the path; events empty.
4. `test_scan_drops_files_older_than_cutoff` — set the file's mtime before `now - window` via `os.utime` → entry absent from returned state and events empty.

**Verify**: `python -m pytest tests/test_sources_claude.py -q` → all pass (8 total).

### Step 5: Engine corrupt-cache resilience (test_engine.py)

Add `test_forecast_recovers_from_corrupt_cache` — using the existing `Config`+generic-feed pattern: pre-write `"{ not json"` to `cache_path`, run `forecast(now, cfg)` → returns one window with `used == 250` (falls back to default cache and rescans), and afterwards the cache file parses as JSON again.

**Verify**: `python -m pytest tests/test_engine.py -q` → all pass (4 total).

### Step 6: Full gates

**Verify**: `python -m pytest -q` → all pass (≈15 new tests; total ≈81). `git diff --stat token_oracle/` → empty (no production changes).

## Test plan

This plan *is* the test plan — see Steps 1–5. Structural patterns: `tests/test_sources_claude.py` for file-based tests, `tests/test_engine.py` for engine-level. No conftest, no fixtures beyond `tmp_path`/`monkeypatch`, no mocking libraries.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `python -m pytest -q` exits 0 with ≥ 14 more tests than before this plan.
- [ ] `TZ=America/New_York python -m pytest tests/test_profile.py -q` and `TZ=UTC python -m pytest tests/test_profile.py -q` both pass (TZ-proof).
- [ ] `grep -n "if f.projected_pct > 100" tests/test_windows.py` → 0 matches (conditional assert gone).
- [ ] `git diff --stat d2b4d32..HEAD -- token_oracle/` shows no changes from this branch (test-only).
- [ ] `ruff check tests/` exits 0.
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report back (do not improvise) if:

- Any production file in "Current state" differs from its excerpt (behavior may have changed; pinning it needs advisor review).
- A test you believe is correctly derived from the excerpted formulas fails — do NOT adjust production code; report the discrepancy with the numbers (this would mean the advisor's reading or the code's intent is wrong — a human decides which).
- The mtime-restore trick in Step 4.1 proves unreliable on your filesystem (mtime granularity) — report rather than switching to sleep-based timing.

## Maintenance notes

- These tests intentionally encode **current** behavior, including the odd future-anchor case (Step 2.3). If Plans 010/012 or any future change alters projection behavior deliberately, updating these tests is expected — their value is making that change *visible*, not forbidding it.
- Reviewer: check tests derive expectations from formulas/inputs, not magic floats copied from a single run (magic floats rot); `pytest.approx` everywhere floats are compared.
- Deferred: property-based testing (hypothesis) — would add a dependency; revisit only if the dev-deps policy changes.
