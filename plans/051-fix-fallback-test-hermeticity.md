# Plan 051 — fix non-hermetic fallback test (5h overlay leaks real usage)

**Status:** TODO
**Priority:** P1 (a merged test gives false confidence + fails locally on the
operator's machine; CI is unaffected)
**Effort:** S (2-line test change)
**Risk:** very low (test-only; no production code changes)
**Written against commit:** `1115804`
**Files in scope:** `tests/test_engine.py` (one test only)
**Do NOT touch:** any production code — the engine behavior is CORRECT; only the
test's assertion is non-hermetic.

---

## Root cause (fully diagnosed by the advisor — do not re-investigate, just fix)

`tests/test_engine.py::test_single_path_scan_failure_falls_back_to_cached_events`
(added by plan 041) asserts that when the single-source `scan()` crashes, the
engine falls back to **cached events** and the 5h window's `used >= 5000` (the
cache seeds one 5000-token event).

The fallback CODE is correct — verified: the crash is caught, the forecast is
non-blank. **But the assertion is non-hermetic.** After the fallback builds the
forecast, the engine applies its intentional Claude **5h server overlay**
(`engine.try_get_claude_five_hour_data` / `try_get_claude_five_hour_remaining`,
imported at `engine.py:8`), which reads the real machine's
`~/.claude/usage-limits.json` / live 5h state and **overrides** the 5h `used`
with the real current value.

- In **CI** (no `~/.claude/usage-limits.json`): the overlay returns `None`, so
  `used` stays at the cached 5000 → test passes. This is why CI is green.
- On the **operator's machine**: the overlay injects the real current 5h usage.
  While that real usage was 77k the test passed by luck (77k ≥ 5000); once the
  5h window aged down to ~2.2k the assertion `2200 >= 5000` fails.

Evidence (advisor repro):
- `scan called: True` — the crash path IS exercised (fallback engaged), forecast
  has 1 entry (non-blank).
- `five.used == 2200` (real 5h) instead of 5000 (cache).
- With the two overlay functions mocked to `None`: `five.used == 5000` ✓.
- With a clean `HOME` (no `~/.claude`): the test passes as-is (CI-equivalent).

The overlay itself is a **documented, intentional** behavior (see the plans
README "considered and rejected": *"`try_get_claude_five_hour_data` server
overlay … left in place this round"*). So the fix is NOT to change the overlay —
it is to isolate the test from it.

## The fix — isolate the overlay in this one test

In `test_single_path_scan_failure_falls_back_to_cached_events`, before calling
`ENG.forecast(...)`, neutralize the 5h server overlay so the assertion measures
the fallback's use of cached events (its actual contract), not real machine
state. Add two `monkeypatch.setattr` lines alongside the existing
`load_cache`/`save_cache` monkeypatches (around line 194–195):

```python
    monkeypatch.setattr(ENG, "load_cache", lambda *a, **k: cache)
    monkeypatch.setattr(ENG, "save_cache", lambda *a, **k: None)
    # Isolate the intentional Claude 5h server overlay: it reads the real
    # ~/.claude/usage-limits.json / live 5h and would override the cached
    # `used` with real machine state, making this assertion non-hermetic
    # (green in CI, flaky on a dev machine with real usage < 5000).
    monkeypatch.setattr(ENG, "try_get_claude_five_hour_data", lambda *a, **k: None)
    monkeypatch.setattr(ENG, "try_get_claude_five_hour_remaining", lambda *a, **k: None)
```

Both names are module attributes of `token_oracle.core.engine` (imported at
`engine.py:8`: `from .config import ... try_get_claude_five_hour_data,
try_get_claude_five_hour_remaining`), so `monkeypatch.setattr(ENG, "...")` binds
the reference the engine actually calls.

Do NOT change the assertion, the cache fixture, or any other test.

## How to verify

1. The test passes on THIS machine (which has `~/.claude/usage-limits.json` with
   real 5h usage < 5000) — the point of the fix:
   `python -m pytest -q tests/test_engine.py::test_single_path_scan_failure_falls_back_to_cached_events`
   → 1 passed.
2. It also passes with a clean HOME (still CI-safe):
   `HOME=$(mktemp -d) python -m pytest -q tests/test_engine.py::test_single_path_scan_failure_falls_back_to_cached_events`
   → 1 passed.
3. Full suite green: `python -m pytest -q` → all pass (248).
4. Gates: `ruff check token_oracle tests`, `ruff format --check token_oracle tests`,
   `python -m mypy token_oracle --ignore-missing-imports` — unchanged (this is a
   test-only edit).
5. `git diff --stat` shows only `tests/test_engine.py`, and the diff is only the
   two added `monkeypatch.setattr` lines (+ the comment).

Confirm you are testing the worktree code, not an installed copy
(`python -c "import token_oracle, os; print(os.path.dirname(token_oracle.__file__))"`);
prefix with `PYTHONPATH="$PWD"` if needed. Do NOT `pip install -e`.

## Escape hatches

- If mocking those two names does NOT make `five.used == 5000` (i.e. the value is
  still real), STOP — a different overlay is in play; report the actual value and
  the code path rather than piling on more mocks.
- Do NOT "fix" this by weakening the assertion to `>= 0` or `assert fs` only —
  that would stop testing that the cached 5000-token event actually flows through
  the fallback. Keep `>= 5000`; make it deterministic by isolating the overlay.

## Maintenance note

Any test that calls `ENG.forecast` and asserts a specific `used`/percentage for a
Claude window must isolate `try_get_claude_five_hour_data` /
`try_get_claude_five_hour_remaining` (and, for weekly caps, the
`~/.claude/usage-limits.json` cap validator) — otherwise it silently measures the
dev machine's real usage. This is the second time real machine state has leaked
into a "pure" engine test; consider a shared `isolate_live_overlays` fixture if a
third appears.
