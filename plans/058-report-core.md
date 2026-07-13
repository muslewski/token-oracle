# Plan 058 — Cost/usage report core (`core/report.py`) + cached-events seam

**Written against commit `bd54990`.** If `token_oracle/core/pricing.py`,
**Status:** DONE — merged to main via advisor/058-sticky-hooks (2026-07-14)
`token_oracle/core/events.py`, or `token_oracle/core/engine.py` differ
materially from the excerpts below, STOP and report — the design assumes this
shape.

## Why this matters

token-oracle can *forecast* but cannot yet *retrospect*: there is no "what did
I spend / burn" report. `core/pricing.py` (cost math) exists but has **zero
callers outside its own tests** — it was built (plan 017) and never wired to a
surface. This plan builds the pure aggregation core that plan 059 (`oracle
report`) and plan 060 (statusline `$today`) both render. It is the head-to-head
gap with ccusage (whose stars are mostly "how much did I spend").

This plan is **pure core + one engine seam only** — no CLI, no rendering. Keep
it that way; the command lives in plan 059.

## Scope

**In scope — create/edit ONLY these:**
- `token_oracle/core/report.py` (NEW)
- `token_oracle/core/engine.py` (ADD one function `cached_events`; touch nothing else)
- `tests/test_report.py` (NEW)

**Out of scope — do NOT touch:** `pricing.py`, `events.py`, `config.py`,
`cli/main.py`, `dashboard/`, `adapters/`, any other file. Do NOT add a
subcommand. Do NOT render anything. Do NOT change `forecast()` or
`_forecast_one()` in engine.py.

## Current-state excerpts (read, do not re-derive)

`core/events.py` — event is an 8-tuple; math reads only the first two fields:
```python
# [ts, tokens, model, input, output, cache_create, cache_read, cost_usd]
N_FIELDS = 8
def normalize(e):  # any 2..8-seq -> canonical 8-tuple; never raises on well-typed short input
    ts, tok = float(e[0]), int(e[1])
    model = e[2] if len(e) > 2 else None
    ints = [int(e[i]) if len(e) > i and e[i] is not None else 0 for i in (3, 4, 5, 6)]
    cost = float(e[7]) if len(e) > 7 and e[7] is not None else None
    return (ts, tok, model, *ints, cost)
def as_pairs(events):
    return [(float(e[0]), int(e[1])) for e in events]
```
**There is no project field.** `--by project` is intentionally out of scope
this round (see plan 059). Do not invent one.

`core/pricing.py` — the cost API you build on (do NOT modify it):
```python
def event_cost(event, mode="auto", overrides=None): ...   # -> float USD | None ("unpriced")
def cost_summary(events, mode="auto", overrides=None):     # -> {"usd":float,"unpriced_tokens":int,"by_model":{model:usd}}
    ...
_MODES = {"auto", "calculate", "display", "off"}
```
`event_cost` returns `None` when a cost cannot be produced (unknown model price,
or missing recorded cost in display/off mode). **Never treat `None` as `$0`** —
carry it as unpriced. `cost_summary` already does this correctly.

`core/config.py` — `Config` dataclass fields you will be handed (by plan 059,
not read here): `windows: list[Window]`, `cost_mode: str = "auto"`,
`pricing: dict` (the `overrides` arg for pricing), `profiles: dict`,
`cache_path: str`. `Window` (contracts.py) has `.name`, `.cap` (int),
`.period_secs` (int).

`core/engine.py` — cache shape you will read in `cached_events`. Single-source
config stores at top level; multi-profile under `"profiles"`:
```python
# single:  cache = {"files": {...}, "events": [[...],...], "profile": [...], "lastAggregate": ts}
# multi:   cache = {"profiles": {pname: {"files":..,"events":[[...]],"profile":..,"lastAggregate":..}}, "lastAggregate": ts}
```
`forecast()` populates it; `events` entries are lists (JSON round-trip of the
8-tuple, or legacy 2-lists). `load_cache(path)` already exists in
`engine.py`'s imports (`from .cache import AGGREGATE_INTERVAL, load_cache, save_cache`).

## What to build

### 1. `token_oracle/core/report.py` (pure, stdlib only, no I/O, never raises on well-typed input)

Module docstring: state it is pure aggregation over normalized event lists;
cost via `core.pricing`; no I/O; the caller supplies events + caps.

Use `from . import pricing` and `from . import events as events_mod` and
`import time` only if needed (prefer taking `now` as an arg — do NOT call
`time.time()` at import). Local time bucketing via the stdlib `time`
(`time.localtime`) is fine inside functions.

Define a small row container (a `@dataclass` `LedgerRow`) with fields:
`label: str`, `tokens: int`, `cost: float | None`, `unpriced_tokens: int`,
`pct_cap: float | None`. `cost is None` ⇒ fully unpriced (render as "—", never
"$0.00"); `pct_cap is None` ⇒ no weekly cap known.

Functions (exact signatures — plan 059 and 060 call these):

```python
def weekly_cap(windows) -> int | None:
    """The cap of the window that best represents the weekly limit: the window
    whose period_secs is nearest 7*24*3600; ties/none -> the largest cap among
    windows; empty -> None. Pure."""

def day_key(ts, now=None) -> str:
    """Local calendar day label 'YYYY-MM-DD' for a unix ts."""

def daily_ledger(events, cap, now, days=7, mode="auto", overrides=None) -> list[LedgerRow]:
    """One row per local calendar day for the last `days` days ending at `now`
    (most-recent last), plus a final TOTAL row (label='TOTAL').
      tokens        = sum event[1] that day
      cost          = sum event_cost(...) that day; None only if EVERY priced
                      attempt returned None AND tokens>0 (fully unpriced day);
                      0.0 for a genuinely empty day
      unpriced_tokens = tokens whose cost could not be resolved
      pct_cap       = 100*tokens/cap if cap else None   (that day's share of the weekly cap)
    Days with zero events still emit a row (tokens=0, cost=0.0) so the table is
    a continuous calendar. Never raises on well-typed input."""

def group_ledger(events, key, now, mode="auto", overrides=None) -> list[LedgerRow]:
    """Aggregate ALL given events by `key`:
      key='day'   -> one row per calendar day present (no zero-fill), TOTAL last
      key='week'  -> one row per ISO week (label 'YYYY-Www'), TOTAL last
      key='model' -> one row per model (label = model or '(unknown)'), sorted by
                     cost desc then tokens desc, TOTAL last
    pct_cap is left None for group_ledger (grouping axis is not per-day-vs-cap).
    Unknown key -> raise ValueError('unsupported group key: %r' % key) so the
    command can report it honestly."""

def cost_today(events, now, mode="auto", overrides=None) -> dict:
    """{'usd': float, 'unpriced_tokens': int} over events whose ts falls in the
    local calendar day containing `now`. Reuses pricing.cost_summary on the
    filtered slice. Cheap; called on the statusline hot path (plan 060)."""
```

Implementation notes:
- Bucket by **local** day (`time.localtime(ts)` → `%Y-%m-%d`), consistent
  between `day_key`, `daily_ledger`, `cost_today`.
- Compute cost with `pricing.event_cost(e, mode, overrides)` per event and sum
  the non-None; count `e[1]` into `unpriced_tokens` when it is None. (You may
  call `pricing.cost_summary` on a day's slice instead — same result; pick one
  and be consistent.)
- `mode == "off"` ⇒ every cost is None ⇒ each non-empty row has `cost=None`.
  That is correct and honest; do not special-case it to 0.
- No `time.time()` / `random` at module top level (breaks determinism/tests).

### 2. `token_oracle/core/engine.py` — add `cached_events` (append; edit nothing else)

```python
def cached_events(config=None):
    """Normalized event list from the on-disk cache WITHOUT re-scanning
    (a cheap read for the statusline hot path, which runs after forecast() has
    already refreshed the cache). Single-source: cache['events']. Multi-profile:
    concatenation of every profiles[*]['events']. Returns [] on any problem.
    Never raises."""
    try:
        cfg = config or load_config()
        cache = load_cache(cfg.cache_path)
        raw = []
        if isinstance(cache, dict) and isinstance(cache.get("profiles"), dict):
            for slc in cache["profiles"].values():
                if isinstance(slc, dict):
                    raw.extend(slc.get("events") or [])
        else:
            raw.extend((cache or {}).get("events") or [])
        return [events_mod.normalize(e) for e in raw if isinstance(e, (list, tuple)) and len(e) >= 2]
    except Exception:
        return []
```
Place it near `forecast()`. `events_mod`, `load_cache`, `load_config` are
already imported at the top of engine.py — verify, do not re-import.

## Verification (run from the worktree root; stdlib-only, no install needed)

Set `TOKEN_ORACLE_SKIP_BOOTSTRAP=1` and ensure imports resolve from the
worktree: `python -c "import token_oracle, os; print(os.path.dirname(token_oracle.__file__))"`
must print a path UNDER this worktree; if not, prefix commands with
`PYTHONPATH="$PWD"`.

1. **Purity smoke** (deterministic — no real clock):
   ```
   TOKEN_ORACLE_SKIP_BOOTSTRAP=1 python -c "
   from token_oracle.core import report as R
   now=1_700_000_000.0; day=86400
   ev=[(now-0*day,1000,'claude-opus-4',1000,0,0,0,None),
       (now-1*day,2000,'claude-sonnet-4',2000,0,0,0,None),
       (now-1*day, 500,'grok-4',500,0,0,0,None)]
   rows=R.daily_ledger(ev, cap=8_000_000, now=now, days=3)
   print([ (r.label, r.tokens, round(r.cost,4) if r.cost is not None else None, r.pct_cap and round(r.pct_cap,4)) for r in rows ])
   print('TOTAL row last:', rows[-1].label=='TOTAL', 'total tokens', rows[-1].tokens)
   print('today usd', round(R.cost_today(ev, now)['usd'],4), 'unpriced', R.cost_today(ev, now)['unpriced_tokens'])
   print('by model', [(r.label,r.tokens) for r in R.group_ledger(ev,'model',now)])
   print('weekly_cap', R.weekly_cap([]))
   "
   ```
   Expect: 3 daily rows + TOTAL last; total tokens 3500; grok-4 tokens land in
   `unpriced_tokens` (no snapshot price) while claude models are priced; the
   `model` group has an `(unknown)`-free list with `grok-4` present; `weekly_cap([])` is `None`.
2. **`off` mode** yields `cost is None` on non-empty rows:
   `... R.daily_ledger(ev, cap=8_000_000, now=now, days=1, mode="off") ...` → last row `cost is None`.
3. **`group_ledger` bad key**: `R.group_ledger(ev,'project',now)` raises `ValueError`.
4. **`cached_events` empty-safe**: with a bogus config cache path it returns `[]` (covered by the test file).
5. `python -m pytest -q tests/test_report.py` — your new tests pass.
6. Full suite unchanged elsewhere: `python -m pytest -q` all pass (no existing
   test should change; you added only new files + one engine function).
7. Gates: `ruff check token_oracle tests` ; `ruff format --check token_oracle tests` ;
   `python -m mypy token_oracle --ignore-missing-imports` → 0 errors (notes OK).
8. `git diff --name-only bd54990..HEAD` shows ONLY `token_oracle/core/report.py`,
   `token_oracle/core/engine.py`, `tests/test_report.py`.

## Test plan (`tests/test_report.py`, follow `tests/test_engine.py` style)

Pure fixtures, fixed `now` (never `time.time()`), no filesystem except one
`cached_events` case using `tmp_path`. Cover:
- daily zero-fill: a 7-day ledger over events spanning 3 days has 7 daily rows +
  TOTAL; empty days have tokens=0, cost=0.0, and TOTAL equals the sum.
- pct_cap math: a day with 800k tokens against cap 8_000_000 → pct_cap == 10.0.
- unpriced accounting: a grok/unknown-model event contributes to
  `unpriced_tokens`, never to `usd`; a day of only-unknown-model events has
  `cost is None`.
- `mode="off"` → non-empty row `cost is None`.
- `group_ledger('model')` ordering (cost desc) and TOTAL last; `'week'` labels;
  `'project'`/other → `ValueError`.
- `cost_today` sums only today's slice and reports unpriced correctly.
- `weekly_cap`: nearest-7d selection among windows, max-cap tiebreak, `[] -> None`.
  Build `Window(name, cap, period_secs)` from `token_oracle.core.contracts`.
- `cached_events`: write a cache dict (single and multi shapes) to a
  `tmp_path` file, point a minimal `Config`-like object's `cache_path` at it,
  assert the concatenated normalized events; a missing file → `[]`.

## Maintenance note

`--by project` will need each event tagged with its originating project
(Claude logs encode it in the path `~/.claude/projects/<project>/…`; the scan
drops it today). That is a separate future plan that threads a project id
through `sources/*.scan()` and widens the event record — do NOT attempt it here.
When it lands, `group_ledger` gains a `key='project'` branch.

## STOP conditions

- If `pricing.event_cost` / `cost_summary` signatures differ from the excerpt — STOP.
- If `engine.py` does not already import `events_mod` / `load_cache` /
  `load_config` at module top — STOP and report (do not add imports blindly).
- If any *existing* test changes result — STOP; this plan is additive.

## Contract

One commit per step (2: `feat(core): report aggregation core (report.py)`,
then `feat(core): cached_events read-only seam in engine`; tests can fold into
the first or be a third commit). PROGRESS.md ledger (untracked). Final line
exactly: `RESULT: ok|partial|failed — commits: <n> — <summary>`.
