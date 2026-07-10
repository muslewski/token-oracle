# Plan 010: Investigate (and only then fix) warm-path cache cost — 63 days of events stored twice

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. This is an **investigate-first** plan: Step 2
> contains an explicit go/no-go gate; a NO-GO verdict is a successful outcome.
> When done, update the status row for this plan in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d2b4d32..HEAD -- token_oracle/core/engine.py token_oracle/core/cache.py token_oracle/sources/claude_code.py`
> Plans 004 and 006 landed (they rewrote `save_cache` and removed two dead
> functions from `cache.py` — expected, already reflected below). `engine.py`
> and `claude_code.py` are unchanged since `d2b4d32`, verified at `ada32e9`
> (2026-07-02). On changes after `ada32e9` that touch the excerpts, treat it
> as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: M (S if the verdict is NO-GO)
- **Risk**: MED — touches rolling-window anchor semantics if the fix proceeds
- **Depends on**: plans/005-characterization-tests-core-math.md — DONE (merged at `8890015`); dependency satisfied
- **Category**: perf
- **Planned at**: commit `d2b4d32`, 2026-07-01; excerpts verified current at `ada32e9`, 2026-07-02

## Why this matters

Every `oracle statusline` / `oracle tmux` invocation (status bars run these constantly) loads the entire cache JSON. The cache stores the full 63-day event history **twice**: once per-file under `files[*].events` (needed at aggregate time to rebuild the burn profile without re-parsing transcripts) and once flattened under `events` (used by the warm path's `compute_window`). The warm path only needs events spanning the longest configured window (7 days for the `weekly` preset) plus a safety margin — not 63 days. For a heavy user this is potentially a multi-MB `json.load` per status-bar render. But the real-world cost is **unmeasured** — hence: measure first, fix only past a threshold, and record a NO-GO honestly if the numbers don't justify the risk.

## Current state

- `token_oracle/core/engine.py` — full warm/cold logic (unchanged since `d2b4d32`, verified at `ada32e9`):

```python
def forecast(now, config=None):
    try:
        cfg = config or load_config()
        from ..sources.base import get_source

        source = get_source(cfg.source, cfg.source_opts)
        cache = load_cache(cfg.cache_path)
        if now - cache.get("lastAggregate", 0) >= AGGREGATE_INTERVAL:
            files, events = source.scan(cache.get("files", {}), now, HIST_SECS)
            cache["files"] = files
            cache["events"] = [[float(ts), int(tok)] for ts, tok in events]
            cache["lastAggregate"] = now
            cache["profile"] = build_profile(events, now)
            save_cache(cache, cfg.cache_path)
        else:
            events = [(float(ts), int(tok)) for ts, tok in cache.get("events", [])]
        profile = cache.get("profile") or None
        return [compute_window(events, now, w, profile) for w in cfg.windows]
    except Exception:
        return []
```

- `token_oracle/sources/claude_code.py:74` — per-file state keeps every parsed event within the 63-day horizon: `files[p] = {"mtime": st.st_mtime, "size": st.st_size, "events": evs}`. This duplication with `cache["events"]` is what doubles the file.
- `token_oracle/core/profile.py:8` — `HIST_SECS = 63 * 24 * 3600`. `build_profile(events, now)` consumes the *full-horizon* events at aggregate time.
- `token_oracle/core/windows.py:34-42` — the rolling `_bounds` walk starts at `events[0][0]` and re-anchors at each gap ≥ period. **The correctness subtlety**: with continuous usage (no gap ≥ P anywhere in the retained span), truncating old events changes `events[0]` and can shift the computed block anchor. With any real ≥-P gap inside the retained span (P = 5 h; humans sleep), the walk converges to the same current anchor regardless of how much older history is present. This is why the fix keeps a margin of 2× the longest period rather than exactly one period.
- `token_oracle/core/windows.py:59-63` — when `profile is None`, `compute_window` falls back to computing the prior from raw event history. After any first aggregate, `cache["profile"]` is a 168-float list (truthy), so the warm path uses the profile, not raw history. Legacy caches (written before a code upgrade) could lack it for ≤ 30 s until the next aggregate — acceptable.
- Plan 005's tests pin: re-anchor walk, blend arithmetic, incremental scan, warm replay (`tests/test_engine.py::test_forecast_warm_cache_replays_generic`).

Conventions: stdlib only; `engine.py`'s "Never raises; returns [] on hard failure" docstring contract must survive; ruff line-length 100.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass |
| Focused | `python -m pytest tests/test_engine.py tests/test_windows.py -q` | all pass |
| Lint/type | `ruff check token_oracle/ && ruff format --check token_oracle/ && mypy token_oracle/ --ignore-missing-imports` | exit 0 |

## Scope

**In scope** (only if the Step 2 gate says GO):
- `token_oracle/core/engine.py`
- `tests/test_engine.py` (one new test)

**Out of scope** (do NOT touch):
- `token_oracle/sources/claude_code.py` — `files[*].events` retention is REQUIRED for profile rebuilds without transcript re-parse; do not trim it.
- `token_oracle/core/profile.py`, `windows.py` — no math changes.
- Cache schema migrations/versioning — the trimmed `events` list is shape-compatible; old caches load fine.
- Alternative storage formats (sqlite, msgpack, …) — stdlib-JSON is a design decision.

## Git workflow

- Branch: `advisor/010-cache-warm-path`.
- Conventional commit if GO, e.g.: `perf(engine): trim warm-path event cache to active window span`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Measure the warm path at realistic scale

Run this benchmark (writes only under a temp dir; adjust nothing in the repo):

```bash
python - <<'EOF'
import json, os, tempfile, time
from token_oracle.core.config import Config
from token_oracle.core.contracts import Window
from token_oracle.core.engine import forecast

tmp = tempfile.mkdtemp()
now = 1_800_000_000.0
# Heavy-user shape: one event every 2 minutes for 63 days ≈ 45k events
evs = [[now - i * 120.0, 500] for i in range(45_000)]
cache = {
    "files": {"f.jsonl": {"mtime": 1.0, "size": 1, "events": evs}},  # duplicate copy, as production writes it
    "events": evs,
    "lastAggregate": now,
    "profile": [0.01] * 168,
}
cp = os.path.join(tmp, "cache.json")
json.dump(cache, open(cp, "w"))
cfg = Config(
    source="generic",
    source_opts={"events_path": os.path.join(tmp, "absent.json")},
    cache_path=cp,
    windows=[Window("5h", 220000, 18000), Window("weekly", 8000000, 604800)],
)
sz = os.path.getsize(cp) / 1e6
t0 = time.perf_counter()
for _ in range(10):
    out = forecast(now + 1.0, cfg)  # within AGGREGATE_INTERVAL -> pure warm path
dt = (time.perf_counter() - t0) / 10 * 1000
assert out and not out[0].idle
print(f"cache file: {sz:.2f} MB   warm forecast: {dt:.1f} ms/call")
EOF
```

Record both numbers in your report. Also run a second shape — 4× density (`i * 30.0`, 180k events) — and record it.

**Verify**: the script prints both lines without traceback.

### Step 2: GO / NO-GO gate

- **NO-GO** if the 45k-event warm call is **< 50 ms**: the optimization does not pay for its anchor-semantics risk at realistic scale. Mark this plan `REJECTED (measured: <numbers>)` in `plans/README.md`, include both measurements, and stop — this is a successful outcome, not a failure.
- **GO** if ≥ 50 ms: proceed to Step 3.

### Step 3 (GO only): Trim the flattened warm-path copy

In `engine.py`, after computing `events` in the aggregate branch, store a trimmed flat copy — keep everything needed by `compute_window` plus the anchor-walk margin:

```python
            keep_from = now - 2 * max(w.period_secs for w in cfg.windows) if cfg.windows else now - HIST_SECS
            cache["events"] = [[float(ts), int(tok)] for ts, tok in events if ts >= keep_from]
```

`build_profile(events, now)` MUST keep receiving the untrimmed `events` — order the lines so trimming happens only for the stored copy, and `compute_window` on the cold path still receives full `events` (unchanged variable). Only the warm path reads the trimmed list.

**Verify**: `python -m pytest tests/test_engine.py tests/test_windows.py -q` → all pass, **especially** Plan 005's `test_rolling_reanchors_across_blocks` and `test_forecast_warm_cache_replays_generic`.

### Step 4 (GO only): Regression test + re-measure

Add `test_warm_cache_events_trimmed_to_window_span` to `tests/test_engine.py`: cold-forecast a generic feed containing one event 30 days old and one recent event with a `weekly` (604800 s) window; assert the cache file's `events` list contains only the recent event (30 d > 2×7 d), while `files` state is untouched by engine trimming (generic passes state through — assert via the feed still being re-readable, or simply that `used` on a follow-up warm call matches the recent event). Then re-run the Step 1 benchmark and record before/after ms and MB.

**Verify**: `python -m pytest -q` → all pass; benchmark shows a material reduction (report exact numbers).

### Step 5 (GO only): Full gates

**Verify**: `ruff check token_oracle/ && ruff format --check token_oracle/ && mypy token_oracle/ --ignore-missing-imports` → exit 0.

## Test plan

- NO-GO path: no code, no tests — measurements recorded in `plans/README.md`.
- GO path: the one new engine test (Step 4) + Plan 005's characterization suite as the safety net. Structural pattern: `tests/test_engine.py::test_forecast_warm_cache_replays_generic`.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] Both benchmark measurements recorded in the report AND in the `plans/README.md` status row (either verdict).
- [ ] NO-GO: status = `REJECTED (measured: N ms @ 45k events)`; zero code changes (`git status --short` clean).
- [ ] GO: `python -m pytest -q` exits 0; new trim test present; before/after numbers recorded; lint/type gates pass; only `engine.py` + `test_engine.py` modified.
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report back (do not improvise) if:

- Plan 005 is not DONE in `plans/README.md` — its tests are the precondition for touching this code.
- Any Plan 005 characterization test fails after Step 3 — the trim broke anchor or blend semantics; report the failing test and the margin math rather than widening the margin ad hoc.
- The benchmark itself behaves unexpectedly (idle forecasts, exceptions) — the harness assumptions drifted.
- You want to also trim `files[*].events` — explicitly out of scope (breaks profile rebuild).

## Maintenance notes

- The 2×-longest-period margin is a heuristic resting on "a ≥ 5 h usage gap exists within any 14-day span". A pathological always-on machine account could still see a shifted rolling anchor after trimming; if such a user materializes, the follow-up is persisting the current anchor in the cache instead of re-deriving it — a bigger change, deliberately not done here.
- If window configs with very long periods (e.g. monthly) become common, `2 * max(period)` approaches `HIST_SECS` anyway and the optimization self-neutralizes — correct behavior, no action needed.
- Reviewer (GO path): confirm `build_profile` still receives untrimmed events, and the cold-path `compute_window` call uses the in-memory full list, not the trimmed stored copy.
