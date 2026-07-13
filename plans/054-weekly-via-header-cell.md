# Plan 054: Surface the weekly number from the rate-limit header as a live cell (truthful merge)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on. If
> anything in "STOP conditions" occurs, stop and report — do not improvise. When
> done, update the status row for this plan in `plans/README.md` (a reviewer
> maintains the index — still flip your row).
>
> **Drift check (run first)**:
> `git diff --stat 5de6aac..HEAD -- token_oracle/live/overlay.py tests/test_live_overlay.py tests/test_live_grok_usage_modal.py`
> AND confirm plan 053 has already landed in this worktree:
> `test -f token_oracle/core/ratelimits.py && python -c "from token_oracle.core import ratelimits as r; print(hasattr(r,'weekly'))"` → prints `True`.
> If `core/ratelimits.py` is absent, STOP — this plan depends on plan 053.

## Status

- **Priority**: P2
- **Effort**: S–M
- **Risk**: MED (touches the live truthfulness merge — strictly additive; absent/stale header = today's exact behavior)
- **Depends on**: `plans/053-self-ingest-ratelimits-5h.md` (needs `core.ratelimits.weekly()`)
- **Category**: direction / correctness
- **Planned at**: commit `5de6aac`, 2026-07-13

## Why this matters

Plan 053 makes token-oracle capture Claude's rate-limit header, which carries
BOTH the 5h and the **seven_day (weekly)** window. Plan 053 wired only the 5h
number. This plan surfaces the weekly number too — the exact weekly % the website
shows — as a first-class LIVE cell, so a wired user sees a real, server-truthful
weekly figure **without the browser scrape**. Today the only authoritative weekly
source is the slow, fragile Chromium scrape (`live-probe`); the header is fresher
(~per turn vs. minutes), needs no browser, and cannot be wrong the way DOM
scraping can. The header therefore WINS over the web cell for Claude's weekly.

Strictly additive: when no header snapshot exists or it's stale, behavior is
byte-identical to today (web cell or local projection). This preserves the
Phase-0 truthfulness guarantees — a number is shown only when it is high-quality
and fresh.

## Current state

- `token_oracle/live/overlay.py` — `overlay_cells(forecasts, snapshot, now,
  ttl=FRESH_TTL_SECS)` (lines 63-134) builds `{(profile_canon, wkey): LiveCell}`
  from the WEB live snapshot's `providers[].readings[]`. The weekly web cell is
  set at lines 108-109:
  ```python
  if metric == METRIC_WEEKLY_PCT:
      cells[(p_c, "weekly")] = cell
  ```
  `LiveCell` (lines 28-43) fields: `pct, state, age_secs, evidence, extractor,
  state_value`. A cell renders as a live weekly row iff `pct is not None`.
- `token_oracle/dashboard/app.py` — the dash is the ONLY production caller of
  `overlay_cells` (line 659: `cells = overlay_cells(curr, snap, now)`). The weekly
  row prefers `cell.pct` when present (lines 287-292) and renders its provenance
  from the cell's `extractor` (lines 333-339):
  ```python
  age = int(cell.age_secs) ...
  ex = cell.extractor or ""
  domain = "claude.ai" if p_canon == "claude" else "grok.com"
  base = f"live {domain}"
  if ex: base += f" · {ex}"
  prov = f"{base} · {age}s ago" if age else base
  ```
  So a Claude weekly cell with `extractor="header"` renders as
  `live claude.ai · header · Ns ago` — honest, and **needs no app.py change**.
- `token_oracle/core/ratelimits.py` (created by plan 053) — `weekly(now, path=None)`
  returns `{used_percentage, resets_at, secs_to_reset, observed_at, stale}` or
  None. `used_percentage` is None when the window has rolled (stale).
- `token_oracle/live/contract.py` — `STATE_OK = "ok"` (line 9) is the state for a
  fresh high-confidence usage reading. Use it for the header cell.
- Existing `overlay_cells` callers (verified): production = `app.py:659` only.
  Tests = `tests/test_live_overlay.py` (call sites at lines 42, 73, 105, 136,
  168, 240) and `tests/test_live_grok_usage_modal.py:109`.

Conventions to match:
- overlay never fabricates: only fresh (`age <= ttl`), non-stale, non-None values
  become a `pct`. Apply the SAME discipline to the header cell.
- overlay (`live/`) may import `core.*`. `core.ratelimits` is stdlib-only, so
  `from ..core import ratelimits` creates no cycle.
- Hermeticity (per plan 051's lesson): tests must never read the real machine
  `~/.local/share/token-oracle/ratelimits.json`. The function will AUTO-read the
  header by default (so the dash needs no change), so existing tests must pass an
  explicit `weekly_header=None` to stay deterministic — this plan updates them.

## Commands you will need

| Purpose   | Command                                                   | Expected  |
|-----------|-----------------------------------------------------------|-----------|
| Tests (focus) | `python -m pytest -q tests/test_live_overlay.py tests/test_live_grok_usage_modal.py` | pass |
| Tests (all)   | `python -m pytest -q`                                 | all pass  |
| Lint      | `ruff check token_oracle tests`                           | exit 0    |
| Format    | `ruff format --check token_oracle tests`                  | exit 0    |
| Types     | `python -m mypy token_oracle --ignore-missing-imports`    | 0 errors  |

If needed, prefix with `PYTHONPATH="$PWD"`. Do NOT run `pip install -e`.

## Scope

**In scope**:
- `token_oracle/live/overlay.py` (add header-weekly merge)
- `tests/test_live_overlay.py` (add header tests + make existing calls hermetic)
- `tests/test_live_grok_usage_modal.py` (make the one call hermetic)

**Out of scope** (do NOT touch):
- `token_oracle/dashboard/app.py` — the existing `extractor`-based provenance
  renders the header cell correctly; NO change needed and another plan (052) owns
  this file. If you think you need to edit app.py, STOP — you don't.
- `token_oracle/core/ratelimits.py` — created/owned by plan 053; consume its
  `weekly()`, don't modify it.
- `token_oracle/core/engine.py` / `config.py` — the weekly number flows via the
  cell, not the engine; no change.
- The 5h cell / 5h path — done in plan 053.

## Git workflow

- Same worktree/branch as plan 053 (`advisor/053-self-ingest-ratelimits`), one
  new commit on top. Conventional commit, e.g.
  `feat(live): surface weekly from rate-limit header as a live cell`.
- Do NOT push or open a PR.

## Steps

### Step 1: Add an auto-reading header-weekly merge to `overlay_cells`

1. At the top of `overlay.py`, import the header source and add a sentinel + a
   safe reader:
   ```python
   from ..core import ratelimits as _ratelimits

   _AUTO = object()  # sentinel: default => auto-read the header snapshot

   def _read_claude_weekly_header(now):
       """Return core.ratelimits.weekly(now) or None. Never raises."""
       try:
           return _ratelimits.weekly(now)
       except Exception:
           return None
   ```
2. Change the signature:
   `def overlay_cells(forecasts, snapshot, now, ttl=FRESH_TTL_SECS, weekly_header=_AUTO):`
3. At the END of `overlay_cells`, just before `return cells`, inject the header
   cell so it OVERRIDES any web weekly cell for Claude:
   ```python
   hdr = _read_claude_weekly_header(now) if weekly_header is _AUTO else weekly_header
   if isinstance(hdr, dict):
       up = hdr.get("used_percentage")
       obs = hdr.get("observed_at")
       age = None if obs is None else max(0.0, now - float(obs))
       fresh = (age is None) or (age <= ttl)
       if up is not None and not hdr.get("stale", False) and fresh:
           cells[("claude", "weekly")] = LiveCell(
               pct=float(up),
               state=STATE_OK,
               age_secs=age,
               evidence="claude rate-limit header (seven_day)",
               extractor="header",
               state_value=None,
           )
   ```
   Add `STATE_OK` to the existing `from .contract import (...)` block.

Rationale: the header is server-authoritative and fresher than the web scrape, so
for `(claude, weekly)` it wins. Grok weekly is untouched (Grok has no such
header). When `weekly_header=None` (tests) or the header is absent/stale/rolled,
the block is a no-op → today's behavior exactly.

**Verify**: `python -m pytest -q tests/test_live_overlay.py` — see Step 2 first
(existing tests need the hermetic arg to stay green on a machine that has a real
header snapshot).

### Step 2: Make existing overlay tests hermetic

The default auto-read would let a real machine snapshot leak into assertions
(the plan-051 non-hermeticity trap). In `tests/test_live_overlay.py`, add
`weekly_header=None` to every `overlay_cells(...)` call (lines ~42, 73, 105, 136,
168, 240). In `tests/test_live_grok_usage_modal.py:109`, likewise add
`weekly_header=None`. This pins those tests to the web-only path they were
written for; their assertions stay unchanged.

**Verify**: `python -m pytest -q tests/test_live_overlay.py tests/test_live_grok_usage_modal.py`
→ all pass (unchanged assertions, now hermetic).

### Step 3: New tests for the header-weekly cell

Add to `tests/test_live_overlay.py` (model after its existing tests — they build
`Forecast`s and a web `snapshot` dict and assert on `cells[(p, wkey)]`):

- `test_header_weekly_becomes_live_cell`: pass `weekly_header={"used_percentage":
  33.0, "observed_at": now-5, "stale": False}` with an empty/absent web weekly →
  `cells[("claude","weekly")].pct == 33.0`, `.extractor == "header"`,
  `.state == "ok"`, `.age_secs ≈ 5`.
- `test_header_weekly_overrides_web_cell`: provide BOTH a web weekly reading
  (e.g. 30%) AND `weekly_header={"used_percentage": 33.0, ...fresh...}` → the
  resulting `(claude,"weekly")` cell has `pct == 33.0` and `extractor == "header"`
  (header wins).
- `test_stale_header_weekly_withheld`: `weekly_header={"used_percentage": 33.0,
  "observed_at": now-5, "stale": True}` → no header override; the web cell (or
  absence) stands. Also test `used_percentage=None` → withheld.
- `test_old_header_weekly_withheld_by_ttl`: `observed_at = now - (FRESH_TTL_SECS +
  60)` → `age > ttl` → withheld.
- `test_grok_weekly_untouched_by_header`: a grok weekly web cell + a claude header
  → the `(grok,"weekly")` cell is unchanged.

**Verify**: `python -m pytest -q tests/test_live_overlay.py` → all pass incl. the
5 new tests. Then full suite `python -m pytest -q`.

## Test plan

- New tests (all in `tests/test_live_overlay.py`): the 5 above — happy path,
  header-beats-web, stale withheld, none withheld, ttl withheld, grok untouched.
- Hermeticity edits: `weekly_header=None` added to all pre-existing
  `overlay_cells` calls in `test_live_overlay.py` and
  `test_live_grok_usage_modal.py`.
- Structural pattern: the existing tests in `tests/test_live_overlay.py`.
- Verification: `python -m pytest -q` → all pass.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `python -m pytest -q` exits 0; the 5 new tests exist and pass.
- [ ] `git grep -n "overlay_cells(" tests/` shows every call passing an explicit
      `weekly_header=` (no bare auto-read in tests).
- [ ] `ruff check token_oracle tests` = 0; `ruff format --check token_oracle tests` = 0; `python -m mypy token_oracle --ignore-missing-imports` = 0 errors.
- [ ] `git diff --name-only 5de6aac..HEAD` includes NO change to
      `token_oracle/dashboard/app.py` (this plan must not touch it).
- [ ] `git diff --name-only` for THIS plan's commit lists only the three in-scope files.
- [ ] `plans/README.md` status row for 054 updated.

## STOP conditions

Stop and report back if:

- `core/ratelimits.py` (plan 053) is not present in the worktree.
- The "Current state" excerpts don't match live code (drift).
- You find yourself needing to edit `app.py` to make the weekly header render —
  it should render via the existing `extractor` provenance branch; if it does
  not, report what you see rather than editing app.py.
- Any existing overlay test changes its assertion result after adding
  `weekly_header=None` (that would mean a real snapshot was already leaking —
  report it; it's a pre-existing hermeticity bug to surface, not silence).

## Maintenance notes

- Provenance of a header weekly reads `live claude.ai · header · Ns ago`. If the
  wording needs to distinguish "rate-limit header" from "browser scrape" more
  loudly, that is an app.py provenance-string change to make deliberately later,
  not here.
- If Grok ever exposes an equivalent header, add a `(grok,"weekly")` branch the
  same way; today Grok has no such header, so its weekly stays scrape-sourced.
- The header wins over the web cell unconditionally when fresh. If a future case
  needs the web cell to win (e.g. header known-wrong), gate the override on a
  freshness/age comparison between the two — but the header is strictly more
  authoritative for Claude today, so unconditional override is correct.
- Reviewer: confirm the merge is a no-op when `weekly_header` is None/stale/rolled
  (additive guarantee), and that no test reads the real machine snapshot.
