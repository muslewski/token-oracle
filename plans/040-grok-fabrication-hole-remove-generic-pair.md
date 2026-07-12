# Plan 040 — Close the grok "used+limit" fabrication hole (generic-shape → CONF_HIGH weekly %)

**Status:** TODO
**Written against commit:** `646a2ac`
**Priority:** P0 (truthfulness gate — blocks any launch)
**Effort:** S
**Depends on:** 031 (evidence-bound grok extractor — DONE), 038 (grok usage modal — DONE).
No file conflict with 039/041; may run in parallel.

---

## Why this matters (the bug)

The grok live extractor turns **any** JSON object the page loads that contains a numeric
`used` and a numeric `limit` in the same dict into a **`CONF_HIGH` weekly-usage %** reading.
`{"used": 45, "limit": 100}` → "grok weekly usage 45% (high confidence)".

`used`/`limit` is a **ubiquitous generic shape** — pagination, storage quotas, a rate
limit, a feature counter, a Stripe object, anything. There is no anchor tying it to weekly
usage. So this path manufactures a high-confidence usage number from unrelated data. That
directly violates the project's core promise ("we only show numbers we can prove") — the
one thing a viral launch would screenshot.

## Root cause (verified by direct read at `646a2ac`)

`token_oracle/live/grok_extract.py`, `readings_from_network_json`:

- `_try_emit_used_limit_pair(d, prefix)` (line 93) emits `METRIC_WEEKLY_PCT`, `CONF_HIGH`
  for any dict with numeric `used`+`limit` and `limit > 0`, `0 <= pct <= 100`. **No URL
  anchor, no key-name anchor** — the shape alone triggers it.
- It is called on the **top-level** object (line 127) and on **every one-level-deep** dict
  value (line 136).

This was added deliberately by **plan 031**, which *speculated* grok might expose a JSON
endpoint carrying `{used, limit}` for weekly quota. **Plan 038 later proved that speculation
false**: grok exposes **no clean JSON endpoint** for weekly usage — the number lives only in
the `?_s=usage` modal DOM text (038 checked `/rest/products` = Stripe catalog,
`/rest/subscriptions` = tier, `/rest/rate-limits` = 2h window, `/rest/tasks` = Tasks quota;
none carry weekly usage). This is documented in `grok_extract.py:40,290` and
`plans/README.md:127-129`. So the `used+limit` path can now only ever **false-positive**.

The regression test **`tests/test_live_grok_extract.py:208`
`test_used_limit_pair_at_top_emits_one_weekly_45_high`** asserts this fabrication as
intended behavior — firing on `url="https://example"`. That test encodes the hole and must
be rewritten to assert the fix.

**Distinction — what is NOT the hole:** the `exact_pct_keys` allowlist
(`usagePercent`, `weeklyUsagePercent`, `buildUsagePercent`, line 65) is **key-name-anchored**
— a JSON key literally named `weeklyUsagePercent` is legitimate evidence of intent (a false
positive would require grok to ship that exact key meaning something else — implausible).
Keep it. Only the **generic `used+limit` pair** is the fabrication hole.

## The fix (design — implement exactly this)

Remove the generic `used+limit` pair extractor and its two call sites. Keep everything else
in `readings_from_network_json` (the rate-window extractor and the `exact_pct_keys`
allowlist) untouched. Rewrite the tests that assert the removed behavior.

### Step 1 — Delete `_try_emit_used_limit_pair` and its two invocations

In `token_oracle/live/grok_extract.py`, `readings_from_network_json`:

1. Delete the entire `_try_emit_used_limit_pair` nested function (lines 93-119).
2. Delete its top-level call (line 127: `_try_emit_used_limit_pair(obj)`).
3. In the one-level-deep loop (lines 130-136), delete the
   `_try_emit_used_limit_pair(subv, p)` call (line 136). **Keep** the `exact_pct_keys`
   loop inside it (lines 133-135).
4. Update the docstring/comment block at lines 59-64 to reflect that only exact percent
   keys are honored from network JSON, and that the `used+limit` pair was removed because
   grok exposes no such endpoint (038). Keep the plan-031 note about NOT loosening to
   any-numeric/substring hints.

After the edit, `readings_from_network_json` still emits:
- `METRIC_RATE_WINDOW` from `remainingQueries`/`totalQueries` (unchanged), and
- `METRIC_WEEKLY_PCT` from an **exact** `usagePercent`/`weeklyUsagePercent`/`buildUsagePercent`
  key at top level or one level deep (unchanged).

It no longer emits anything from a bare `{used, limit}` pair.

### Step 2 — Rewrite the tests that assert the hole

In `tests/test_live_grok_extract.py`:

- **Replace** `test_used_limit_pair_at_top_emits_one_weekly_45_high` (lines 208-219) with a
  test asserting the pair now yields nothing:
  ```python
  def test_used_limit_pair_at_top_yields_nothing_now():
      """Generic {used, limit} is NOT weekly evidence (grok has no such endpoint — plan 038).
      Removing this closes the fabrication hole (plan 040)."""
      now = time.time()
      rs = readings_from_network_json("https://example", {"used": 45, "limit": 100}, now)
      assert rs == []
  ```
- **Add** a nested-pair regression (the one-deep call site is also removed):
  ```python
  def test_used_limit_pair_one_level_deep_yields_nothing_now():
      now = time.time()
      rs = readings_from_network_json("u", {"someQuota": {"used": 45, "limit": 100}}, now)
      assert rs == []
  ```
- **Keep unchanged** (they still pass, and prove the fix didn't over-reach):
  `test_bare_used_alone_yields_nothing`, `test_bare_limit_alone_yields_nothing`,
  `test_exact_key_one_level_deep_still_works` (exact keys retained),
  `test_rate_limit_json_yields_only_rate_window`, `test_unknown_json_yields_nothing`,
  `test_usage_with_unlisted_numeric_child_yields_nothing`.

## Files in scope

- `token_oracle/live/grok_extract.py` — delete `_try_emit_used_limit_pair` + its 2 calls;
  update the nearby comment. **No other behavior change.**
- `tests/test_live_grok_extract.py` — rewrite one test, add one, keep the rest.

## Files explicitly OUT of scope (do NOT touch)

- `token_oracle/live/web.py` — the fetch orchestration; `readings_from_network_json` stays
  a fallback there, just with the pair path removed. Do not rewire it.
- `readings_from_usage_modal` / `parse_absolute_reset` (the plan-038 primary path) — leave
  entirely alone; they are correct and are the real weekly source.
- `readings_from_progressbars`, `readings_from_labeled_text`, `readings_from_reset_text` —
  unchanged.
- The `exact_pct_keys` allowlist and `_emit_pct` — **keep them**. Removing them is
  over-reach; they are key-anchored, not the generic hole.
- `token_oracle/live/claude_extract.py`, `contract.py`, `overlay.py`, `store.py`.

## Test plan

Covered in Step 2. The net test delta is: one test rewritten (was: pair emits 45% HIGH →
now: pair emits nothing), one test added (nested pair emits nothing). No other test changes.

Run the focused file plus the full suite:
```
python -m pytest -q tests/test_live_grok_extract.py
python -m pytest -q
```

## Verification gates (run all; all must pass)

```
pip install -e ".[dev]"   # NOTE: clobbers the user's `oracle` entrypoint; advisor re-symlinks after merge — not your concern
python -m pytest -q
ruff check token_oracle tests
ruff format --check token_oracle tests
mypy token_oracle --ignore-missing-imports
```

Expected: all green; the two changed/added grok tests pass; every other test unchanged.

## Done criteria (machine-checkable)

- `rg "_try_emit_used_limit_pair" token_oracle` returns **nothing** (function and calls gone).
- `python -c "import time; from token_oracle.live.grok_extract import readings_from_network_json as f; print(f('https://example', {'used':45,'limit':100}, time.time()))"`
  prints `[]`.
- `python -c "import time; from token_oracle.live.grok_extract import readings_from_network_json as f; print([(r.metric,r.value) for r in f('u', {'stats':{'weeklyUsagePercent':10}}, time.time())])"`
  prints `[('weekly_pct', 10.0)]` (exact-key path still works).
- `python -m pytest -q` passes.
- `ruff check` / `ruff format --check` / `mypy` clean.

## Escape hatches — STOP and report instead of improvising if:

- Removing `_try_emit_used_limit_pair` breaks a test **outside** `test_live_grok_extract.py`
  — that would imply `web.py` or the overlay depends on pair-emitted readings; report the
  coupling instead of broadening the edit.
- You find grok DOES have a real JSON usage endpoint documented in the codebase/fixtures
  that carries `{used, limit}` for weekly (it does not, per 038 — but if a fixture proves
  otherwise, STOP: the fix would then be URL-anchoring, not deletion).

## Maintenance note

- If grok ever ships a genuine JSON weekly-usage endpoint, re-add extraction **anchored to
  that specific endpoint URL AND a specific key** (e.g. `url` contains the known path *and*
  the value sits under a named `weeklyUsage`/`weekly` key) — never from a bare `{used,
  limit}` shape. The generic shape is indistinguishable from noise and is why this hole
  existed.
- The truthful weekly source for grok is `readings_from_usage_modal` (plan 038, text-
  anchored on "Weekly … Limit … N% used"). That is the path to extend, not this one.
