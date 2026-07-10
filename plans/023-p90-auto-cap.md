# Plan 023: P90 auto-detected personal caps (`"cap": "auto"`)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ada32e9..HEAD -- token_oracle/core/config.py token_oracle/core/contracts.py token_oracle/core/windows.py token_oracle/core/engine.py tests/test_windows.py tests/test_config.py SETUP.md`
> Plans 016/017 will normally have landed first (events.py exists, PRESETS
> grew) — expected drift. `windows.py` `compute_window`/`_bounds` and
> `contracts.py` must match the excerpts below; on mismatch, STOP.

## Status

- **Priority**: P3
- **Effort**: M
- **Risk**: MED (touches the projection path; wrong caps produce wrong warnings)
- **Depends on**: none hard (works on (ts, tokens) pairs). Soft: 012 — an
  auto cap should eventually lower `confidence`; see Maintenance.
- **Category**: direction
- **Planned at**: commit `ada32e9`, 2026-07-02

## Why this matters

Anthropic doesn't publish exact subscription caps; every preset number
(19k/88k/220k) is community folklore that rots. Claude-Code-Usage-Monitor's
(8.3k★) flagship feature — its default `custom` plan — sidesteps this by
inferring the user's real ceiling from their own history: the 90th
percentile of observed per-window usage. Heavy users repeatedly bump the
true limit, so their observed maxima cluster just under it; P90 of those
maxima approximates the cap without Anthropic's cooperation. This plan adds
`"cap": "auto"`: per-window caps learned from the user's own 9 weeks of
events, with a preset fallback while history is thin.

## Current state

- `Window` (core/contracts.py:8-21): `name: str, cap: int,
  period_secs: int, anchor: float | None = None`.
- `_window_from_dict` (core/config.py:45-65): `cap = int(d["cap"])`;
  `if cap <= 0 or period <= 0: raise ValueError(...)` — `"auto"` currently
  fails `int()` and the entry is skipped with an issue.
- `compute_window(events, now, window, profile=None)`
  (core/windows.py:45-70): reads `cap = window.cap` once (line 46), divides
  by it for `projected_pct` (`(projected / cap * 100) if cap else 0.0`,
  line 67) and passes it into `eta_to_cap` and the `Forecast`.
- `_bounds(events, now, window)` (core/windows.py:25-42): rolling windows
  re-anchor at the first event after each expiry — the walk in lines 36-38:

  ```python
  start = events[0][0]
  for ts, _tok in events[1:]:
      if ts >= start + P:
          start = ts  # window expired -> re-anchor here
  ```

- Events available to the engine span `HIST_SECS` = 9 weeks
  (core/profile.py:8); engine.py:27 calls
  `compute_window(events, now, w, profile)` per configured window (post-016:
  with `as_pairs(events)`).
- Characterization tests for the re-anchor walk and blend live in
  `tests/test_windows.py` / `tests/test_engine.py` (plan 005) — they pin
  current behavior for integer caps and must not change.
- Convention: accumulate-not-raise config validation into `Config.issues`;
  "never raises" core.

## Design (decided — do not redesign)

**Config**: `"cap": "auto"` allowed in a window dict.
`_window_from_dict` maps it to `cap=0` plus a new field
`cap_auto: bool = False` on `Window` (`cap=0` is currently rejected, so no
existing config means anything different — no ambiguity). A numeric
`cap` may coexist in the same dict (`{"cap": "auto", "cap_fallback": 50000}`
is NOT the design — the fallback is the preset's cap for the same window
name when the active config came from a preset, else the auto estimate with
low-sample honesty; see below).

**New pure function in `core/windows.py`**:

```python
def observed_window_totals(events, now, window):
    """Per-completed-period token totals over the full event history.
    anchor set  -> totals per fixed grid slot [anchor+nP, anchor+(n+1)P).
    anchor None -> walk the same re-anchor rule as _bounds over ALL events
                   (a window starts at the first event after the previous
                   window's expiry) and total each closed window.
    The current (open) window is excluded. Returns list[int]."""

def p90_cap(totals, min_samples=5):
    """0.9-quantile (nearest-rank: sorted(totals)[ceil(0.9*n)-1]) of totals.
    None when len(totals) < min_samples."""
```

The rolling-mode walk MUST reuse `_bounds`' re-anchor semantics — implement
it by generalizing the existing three-line walk, not by inventing a new
windowing rule (that walk is characterization-pinned).

**Engine resolution** (engine.py, inside the per-window loop): when
`w.cap_auto`, compute `cap = p90_cap(observed_window_totals(pairs, now, w))`;
if `None` (thin history), fall back to `PRESETS["max20"]`'s cap for a window
with the same `period_secs` (220000 for 18000 s, 8000000 for 604800 s), else
`max(totals)` if even that lookup misses — and pass a `Window` copy with the
resolved integer cap to `compute_window` (use `dataclasses.replace(w, cap=resolved)`).
`compute_window` itself stays cap-agnostic — zero changes to it.

Resolved-cap visibility: the `Forecast` already carries `cap` — consumers
(dash, statusline, snapshot) show the learned number automatically. Doctor:
the `windows` row detail (main.py:83) gains `(auto)` after auto window
names.

**SETUP.md**: document `"cap": "auto"`, the P90 rule, the ≥5-samples
requirement, the fallback, and the honest caveat: *an inferred cap is only
as good as how often you've hit the real one; light users get
overestimates* (which fail safe: projections read lower).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass |
| Lint | `ruff check token_oracle/ && ruff format --check token_oracle/` | exit 0 |
| Types | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |

## Scope

**In scope**:
- `token_oracle/core/contracts.py` (`Window.cap_auto` field)
- `token_oracle/core/config.py` (`_window_from_dict` "auto" branch)
- `token_oracle/core/windows.py` (two new pure functions ONLY — no edits to
  `compute_window`/`eta_to_cap`/`_bounds` bodies beyond extracting the walk
  into a shared helper if needed, keeping `_bounds` behavior identical)
- `token_oracle/core/engine.py` (cap resolution)
- `token_oracle/cli/main.py` (doctor `(auto)` suffix)
- `tests/test_windows.py`, `tests/test_config.py`, `tests/test_engine.py`,
  `tests/test_cli.py` (extend)
- `SETUP.md`

**Out of scope**:
- `compute_window` math, profile, blend — untouched.
- Confidence values (plan 012 owns that; see Maintenance).
- Dashboard changes (the resolved cap flows through `Forecast.cap`).
- Presets' numeric values.

## Git workflow

- Branch: `advisor/023-p90-auto-cap`
- Conventional commits, e.g. `feat(core): P90 auto-detected window caps`
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: `observed_window_totals` + `p90_cap` + tests

Pure functions per Design. Tests in `tests/test_windows.py` (synthetic
events, fixed `now`): fixed-grid totals bucket correctly and exclude the
open window; rolling totals reproduce the `_bounds` re-anchor boundaries
(construct events with an idle gap > P and assert two separate totals);
`p90_cap` nearest-rank on a known list (e.g. 10 totals → index 8);
`< min_samples` → None. If you extract `_bounds`' walk into a helper, the
plan-005 characterization tests must pass unmodified.

**Verify**: `python -m pytest -q tests/test_windows.py` → all pass.

### Step 2: config + contracts

`Window.cap_auto` (default False — dataclass field order: append after
`anchor` to keep positional construction sites valid; grep
`Forecast(\|Window(` call sites to confirm none break) and the
`_window_from_dict` branch: `d["cap"] == "auto"` → `cap=0, cap_auto=True`;
all other non-int values still raise per today. Tests in
`tests/test_config.py`: `"auto"` accepted; `"Auto"`/`"unlimited"` rejected
with issue; numeric caps unaffected.

**Verify**: `python -m pytest -q tests/test_config.py` → all pass.

### Step 3: engine resolution + doctor suffix

Per Design. Tests: `tests/test_engine.py` — an auto window with ≥5 closed
periods of synthetic history forecasts against the P90 value (assert
`Forecast.cap == expected_p90`); with 2 periods it falls back to 220000 for
`period_secs=18000`. `tests/test_cli.py` — doctor shows `(auto)`.

**Verify**: `python -m pytest -q` → all pass.

### Step 4: SETUP.md

Window-object table row for `"auto"` + the caveat paragraph per Design.

**Verify**: `grep -n '"auto"' SETUP.md` → hit; suite green.

## Test plan

- `tests/test_windows.py`: +5 (Step 1); `tests/test_config.py`: +3 (Step 2);
  `tests/test_engine.py`: +2, `tests/test_cli.py`: +1 (Step 3).
- Verification: `python -m pytest -q` → all pass, plan-005 characterization
  tests unmodified (check `git diff --stat` shows only additions in test files).

## Done criteria

- [ ] `python -m pytest -q` exits 0
- [ ] `ruff check`, `ruff format --check`, `mypy` exit 0
- [ ] `git diff ada32e9..HEAD -- tests/ | grep "^-" | grep -v "^---"` shows no
  deleted test lines (characterization intact; additions only)
- [ ] A config with `{"windows": [{"name": "5h", "cap": "auto", "period_secs": 18000}]}`
  loads with zero issues and forecasts (manual or test)
- [ ] `git status` clean outside in-scope list; `plans/README.md` row updated

## STOP conditions

- The re-anchor walk cannot be shared with `_bounds` without changing
  `_bounds`' observable behavior (characterization tests fail) — report;
  duplicating the three-line walk with a comment is the acceptable fallback,
  silently changing `_bounds` is not.
- Auto-cap resolution makes `forecast()` measurably slow on 9 weeks of
  events (it shouldn't — one linear pass per auto window) — report numbers.
- You want to persist the learned cap into the cache — don't; recomputing
  per aggregate keeps it consistent with the event set. Report if profiling
  disagrees.

## Maintenance notes

- Plan 012 (real confidence): an auto cap with few samples deserves reduced
  `confidence` — when 012 lands, feed `len(totals)` into its design; noted
  in 012's inputs by this sentence.
- The P90-of-observed-totals estimator biases LOW for light users (they never
  approach the cap) — fail-safe direction, but the SETUP caveat is the
  contract; don't let future marketing copy oversell it.
- Reviewer focus: open-window exclusion (an in-progress window total would
  drag P90 down), nearest-rank quantile off-by-one, fallback lookup when
  `period_secs` matches no preset window.
