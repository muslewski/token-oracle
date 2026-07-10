# Plan 006: Remove the dead speculative API (UsageEvent, to_pairs, collect_events, events_from_cache)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 8890015..HEAD -- token_oracle/core/contracts.py token_oracle/core/cache.py tests/test_contracts.py tests/test_cache.py`
> If any in-scope file changed since this plan was reconciled, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none (Plans 004 and 005 have both landed on main — no remaining coordination)
- **Category**: tech-debt
- **Planned at**: commit `d2b4d32`, 2026-07-01; reconciled at `8890015`, 2026-07-02 (Plan 004's `save_cache` rewrite + 2 new atomic-write tests in `tests/test_cache.py` landed; line refs and test counts refreshed)

## Why this matters

Four public symbols have zero production callers: `UsageEvent` and `to_pairs` in `contracts.py`, and `collect_events` / `events_from_cache` in `cache.py`. Verified by grep at `d2b4d32`: the only references outside their definitions are their own tests. Worse, the architecture story they tell is false — `contracts.py`'s docstring says "Neutral data contracts **shared by sources**…", but sources yield bare `(timestamp, tokens)` tuples (see `sources/claude_code.py:45`, `sources/generic.py:25`) and ADAPTERS.md documents the tuple contract. A third-party adapter author reading `contracts.py` would reasonably build around `UsageEvent` and be wrong. The tests green-wash the dead code, inflating apparent coverage. At Alpha (0.1.x, pre-stability promises), deletion is the right call; resurrecting a typed event later is one small commit if ever needed.

## Current state

- `token_oracle/core/contracts.py` — full file is 45 lines. The dead parts:

```python
# contracts.py:6-12
@dataclass
class UsageEvent:
    timestamp: float  # epoch seconds
    tokens: int  # billable tokens for this event
    model: str | None = None
    session_id: str | None = None
    kind: str | None = None
```

```python
# contracts.py:43-45
def to_pairs(events: list["UsageEvent"]) -> list[tuple[float, int]]:
    """Sorted (timestamp, tokens) pairs the math operates on."""
    return sorted((float(e.timestamp), int(e.tokens)) for e in events)
```

  The live parts to KEEP: `Window` (contracts.py:15-28) and `Forecast` (contracts.py:31-40) — imported by config, windows, engine consumers, snapshot tests. Module docstring line 1: `"""Neutral data contracts shared by sources, core math, and consumers."""`.

- `token_oracle/core/cache.py:44-55` — the dead functions:

```python
def collect_events(files_state, cutoff):
    out = []
    for ent in files_state.values():
        for ts, tok in ent.get("events", []):
            if ts >= cutoff:
                out.append((float(ts), int(tok)))
    out.sort()
    return out


def events_from_cache(cache, now, window):
    return collect_events(cache.get("files", {}), now - window)
```

  KEEP: `AGGREGATE_INTERVAL`, `load_cache`, `save_cache`.

- `tests/test_contracts.py` — 4 tests; two die with the code: `test_usageevent_defaults` (lines 4-6) and `test_to_pairs_sorts` (lines 21-23). KEEP `test_window_modes` and `test_forecast_confidence_default`. The import line (test_contracts.py:1) currently reads `from token_oracle.core.contracts import Forecast, UsageEvent, Window, to_pairs` — trim to `Forecast, Window`.
- `tests/test_cache.py:38-42` — `test_collect_and_window` dies with the code. KEEP the other five tests (missing/roundtrip/corrupt + the two atomic-write tests `test_save_leaves_no_tmp_files` and `test_save_failure_is_silent_and_leaves_no_tmp` added by Plan 004).
- Grep proof of deadness to re-run yourself (Step 1).
- `CHANGELOG.md` mentions "neutral UsageEvent/Window/Forecast contracts" — historical release notes, do NOT edit.
- ADAPTERS.md documents the tuple-based `scan()` contract and mentions only the `Forecast` dataclass — no doc change needed.

Conventions: stdlib only; conventional commits; ruff `F401` will catch any import left dangling.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass |
| Lint | `ruff check token_oracle/ && ruff format --check token_oracle/` | exit 0 |
| Types | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |

## Scope

**In scope** (the only files you should modify):
- `token_oracle/core/contracts.py`
- `token_oracle/core/cache.py`
- `tests/test_contracts.py`
- `tests/test_cache.py`

**Out of scope** (do NOT touch):
- `Window`, `Forecast`, `load_cache`, `save_cache`, `AGGREGATE_INTERVAL` — live code.
- `CHANGELOG.md` — generated history.
- ADAPTERS.md / any docs — already consistent with the tuple contract.
- Any "while I'm here" refactor of the kept code.

## Git workflow

- Branch: `advisor/006-remove-dead-api`.
- Conventional commit, e.g.: `chore(core): remove dead UsageEvent/to_pairs and cache event collectors`.
- Note: `chore:` does not trigger a release-please version bump — appropriate here (no user-visible behavior change; these symbols were never documented as public API).
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Re-verify deadness

Run: `grep -rn "UsageEvent\|to_pairs\|collect_events\|events_from_cache" token_oracle/ tests/ install.py uninstall.py README.md ADAPTERS.md SETUP.md AGENTS.md`

**Verify**: matches appear ONLY in `contracts.py` (definitions), `cache.py` (definitions + internal call at line 55), `tests/test_contracts.py`, `tests/test_cache.py`. Any other match → STOP condition.

### Step 2: Delete from `contracts.py`

Remove the `UsageEvent` dataclass and `to_pairs`. Update the module docstring to reflect reality, e.g.: `"""Neutral data contracts shared by core math and consumers. Sources emit bare (timestamp, tokens) tuples — see ADAPTERS.md."""`. Keep the `dataclass` import (still used by `Window`/`Forecast`).

**Verify**: `python -c "from token_oracle.core.contracts import Window, Forecast"` → exit 0; `python -c "from token_oracle.core.contracts import UsageEvent" 2>&1 | grep -c ImportError` → 1.

### Step 3: Delete from `cache.py`

Remove `collect_events` and `events_from_cache`. The module docstring ("Persistent aggregation cache: source-owned file state + last-aggregate time + burn profile…") mentions no event collection — no docstring change needed.

**Verify**: `python -c "from token_oracle.core.cache import load_cache, save_cache, AGGREGATE_INTERVAL"` → exit 0.

### Step 4: Trim the tests

- `tests/test_contracts.py`: delete `test_usageevent_defaults` and `test_to_pairs_sorts`; fix the import to `from token_oracle.core.contracts import Forecast, Window`.
- `tests/test_cache.py`: delete `test_collect_and_window` (lines 38-42). The `import os` at the top stays (used by the roundtrip test).

**Verify**: `python -m pytest tests/test_contracts.py tests/test_cache.py -q` → all pass (2 + 5 tests).

### Step 5: Full gates

**Verify**: `python -m pytest -q` all pass; `ruff check token_oracle/ && ruff format --check token_oracle/` exit 0; `mypy token_oracle/ --ignore-missing-imports` exit 0.

## Test plan

Deletion-only — no new tests. The gate is the full suite staying green minus exactly 3 removed tests, plus the grep in Done criteria proving no dangling references.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -rn "UsageEvent\|to_pairs\|collect_events\|events_from_cache" token_oracle/ tests/` → 0 matches.
- [ ] `python -m pytest -q` exits 0 (3 fewer tests than before this plan).
- [ ] `ruff check token_oracle/`, `ruff format --check token_oracle/`, `mypy token_oracle/ --ignore-missing-imports` all exit 0.
- [ ] `git status --short` → only the four in-scope files (plus `plans/README.md`).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report back (do not improvise) if:

- Step 1's grep finds a reference outside the four known files — something started using these symbols after `d2b4d32`; deletion may no longer be safe.
- Plan 012 (real confidence) or 013 (entry-point sources) has landed and introduced a use of `UsageEvent` — reconcile with the index before deleting.
- Removing the symbols breaks an import you didn't expect (would indicate a wildcard import somewhere — none exist at `d2b4d32`).

## Maintenance notes

- If a typed event object is ever genuinely needed (e.g. per-model cap accounting), reintroduce it *at the source boundary with real callers* in the same commit — don't resurrect speculatively.
- Reviewer: confirm the commit is pure deletion + docstring/import fixes; any other diff hunk is scope creep.
- Plan 004's `save_cache` rewrite has already landed on main (`c0a91bf`); no rebase coordination remains.
