# Plan 030: Truthful live-data contract — quarantine browser scraping out of the core engine

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: this plan was written against commit `2660dd1`
> **plus uncommitted working-tree changes** (the operator must commit those
> before you start — see STOP conditions). Verify these files exist:
> `token_oracle/sources/live_web.py`, `token_oracle/sources/grok.py`.
> If either is missing, the live-web WIP was not committed to your base —
> STOP immediately.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: none (first plan of the live-truthfulness round)
- **Category**: bug / tech-debt
- **Planned at**: commit `2660dd1` + uncommitted live-web WIP, 2026-07-10

## Why this matters

The live web scraper (Playwright browser automation reading grok.com and
claude.ai usage pages) is currently wired **directly into the pure forecast
engine**. `token_oracle/core/engine.py` imports the scraper at module level and
calls it inside `forecast()` — which means `oracle statusline`, `oracle tmux`,
`oracle snapshot`, and the test suite can all silently launch a Chromium
browser (or a 60-second blessed-venv subprocess). Each process has its own
25-second in-memory cache, so consecutive invocations disagree; when a scrape
fails, the code silently falls back to the local *projection*, so the displayed
number flips between "current % from the website" and "projected end-of-window
%" — two different quantities — with no visual distinction. This is the direct
cause of the operator-reported symptoms: values jumping 0% → 14% → wrong,
Claude weekly showing 41 when the site shows 38, and the dashboard claiming
"live" while showing local numbers.

This plan introduces a typed, provenance-carrying contract for live readings
(`LiveReading` / `ProviderLive` / a persisted `live.json` snapshot), removes
all browser calls from the engine, and makes the dashboard consume live data
only through an explicit overlay that **never applies a number that isn't
high-confidence and fresh**. After this plan, the tool would rather say
"no reliable live data" than show a fabricated percentage. Follow-up plans
(031, 032) rewrite the extractors so high-confidence readings actually exist;
plan 033 moves probing out-of-process; plan 034 rebuilds the dashboard UI.

## Current state

Relevant files:

- `token_oracle/core/engine.py` — forecast facade. Line 9 imports the scraper;
  lines ~97–142 (`_forecast_one`) and ~208–249 (legacy single-source path)
  overwrite `Forecast` fields in place with scraped values.
- `token_oracle/sources/live_web.py` (985 lines) — Playwright scraper:
  `fetch_grok_live_usage`, `fetch_claude_live_usage`, `get_live_status`,
  `launch_login_session`, `get_browser_profile_dir`, `_delegate_to_blessed`,
  module-level `_LIVE_CACHE` with `_LIVE_TTL = 25`.
- `token_oracle/sources/__init__.py` — imports and re-exports live_web, so any
  `import token_oracle.sources` triggers live_web's **import-time** blessed-venv
  subprocess check (live_web.py:41–50, 5s timeout).
- `token_oracle/dashboard/app.py` — `_render_profile_block` (lines 64–79 and
  130–151) makes its **own** `lw.fetch_*` calls per frame to infer whether a
  number "is live" — independently of what the engine actually applied.
- `token_oracle/cli/main.py` — doctor (lines 135–196) and `_live_setup`
  (356–450) import live_web.
- `token_oracle/core/contracts.py` — `Forecast` dataclass; has no field that
  records where a percentage came from.
- `token_oracle/snapshot/writer.py` — exemplar for atomic JSON writes
  (mkstemp + os.replace pattern); follow it for the new live store.

Key excerpts (confirm you are looking at the same code):

`token_oracle/core/engine.py:9`:
```python
from ..sources.live_web import fetch_claude_live_usage, fetch_grok_live_usage
```

`token_oracle/core/engine.py:100-129` (inside `_forecast_one`; a second,
near-identical block exists in `forecast()` at ~208–249):
```python
    if source_name == "claude_code":
        live = fetch_claude_live_usage(headless=True)
        if live:
            for f in forecasts:
                nm = f.window.lower()
                cap = getattr(f, "cap", 0) or 0
                ...
                if nm == "fable" and live.get("fable_pct") is not None:
                    pct = live["fable_pct"]
                    object.__setattr__(f, "projected_pct", pct)
                    if cap:
                        object.__setattr__(f, "used", int(round(pct / 100.0 * cap)))
```

`token_oracle/sources/__init__.py` (whole file):
```python
from . import (
    claude_code,  # noqa: F401  (register on import)
    generic,  # noqa: F401
    grok,  # noqa: F401  (register on import)
    live_web,  # noqa: F401
)

from .live_web import (
    fetch_grok_live_usage,
    fetch_claude_live_usage,
    get_browser_profile_dir,
    launch_login_session,
)  # type: ignore
```

`token_oracle/sources/live_web.py:39-50` (import-time subprocess probe —
must become lazy):
```python
_BLESSED_VENV_PY = os.path.expanduser("~/.local/share/token-oracle/venv/bin/python")
_BLESSED_PYTHON = None
if not PLAYWRIGHT_AVAILABLE and os.path.isfile(_BLESSED_VENV_PY):
    try:
        out = subprocess.check_output(
            [_BLESSED_VENV_PY, "-c", "import playwright; print('ok')"],
            ...
```

Repo conventions: stdlib-only runtime deps (`dependencies = []` in
pyproject.toml; playwright lives behind the `[live]` extra). Dataclasses for
contracts (see `core/contracts.py`). "Never raises" style in core modules
(module docstrings in `engine.py`, `windows.py`). Tests are plain pytest
functions, no classes (see `tests/test_engine.py`). Ruff line length 100.

Semantics you must preserve (this is the heart of the plan):
`Forecast.projected_pct` is a **projection to end-of-window**
(`token_oracle/core/windows.py:92-93`), while a scraped site percentage is
**current usage now**. They are different quantities and must never share a
field silently. Live values therefore live in `LiveCell` objects beside the
forecast, never inside it.

## Commands you will need

| Purpose   | Command                                      | Expected on success |
|-----------|----------------------------------------------|---------------------|
| Install   | `pip install -e ".[dev]"`                    | exit 0              |
| Tests     | `python -m pytest -q`                        | all pass            |
| Lint      | `ruff check token_oracle/`                   | exit 0              |
| Format    | `ruff format --check token_oracle/`          | exit 0              |
| Types     | `mypy token_oracle/ --ignore-missing-imports`| exit 0              |

Set `TOKEN_ORACLE_SKIP_BOOTSTRAP=1` in your shell for all manual `oracle`
invocations so the CLI never execve's into the blessed venv while you work.

## Scope

**In scope** (the only files you may modify/create):
- `token_oracle/live/__init__.py` (create)
- `token_oracle/live/contract.py` (create)
- `token_oracle/live/store.py` (create)
- `token_oracle/live/legacy.py` (create)
- `token_oracle/live/overlay.py` (create)
- `token_oracle/live/web.py` (create — moved from `sources/live_web.py`)
- `token_oracle/sources/live_web.py` (delete)
- `token_oracle/sources/__init__.py`
- `token_oracle/core/engine.py`
- `token_oracle/dashboard/app.py`
- `token_oracle/cli/main.py`
- `tests/test_live_contract.py` (create)
- `tests/test_live_overlay.py` (create)
- `tests/test_engine.py`, `tests/test_dashboard.py` (only if a test asserts
  removed behavior — see Step 7)
- `plans/README.md` (status row)

**Out of scope** (do NOT touch):
- `token_oracle/core/windows.py`, `profile.py`, `cache.py`, `pricing.py`,
  `events.py` — pure math, untouched by this plan.
- The `try_get_claude_five_hour_data` overlay in `engine.py`/`config.py` —
  that is a *local file / token_forecast* overlay, not browser scraping.
  Leave both call sites in `engine.py` exactly as they are.
- `token_oracle/sources/grok.py`, `claude_code.py`, `generic.py`, `base.py` —
  log-file adapters, unrelated.
- Extraction heuristics inside the moved `live/web.py` — plans 031/032 rewrite
  them; in this plan you move the file and change only what Steps 3–4 name.

## Git workflow

- Branch: `advisor/030-live-truthfulness-contract`
- Conventional commits, e.g. `refactor(live): quarantine scraper into live/ package with typed readings`
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Baseline

Run `pip install -e ".[dev]"` then `python -m pytest -q`. Record the pass
count. If any test fails **before you change anything**, STOP and report —
the uncommitted WIP base is broken and the operator must decide.

**Verify**: `python -m pytest -q` → `N passed` (record N; expected ≥ 135).

### Step 2: Create the contract module

Create `token_oracle/live/__init__.py` (empty except a one-line docstring) and
`token_oracle/live/contract.py`:

```python
"""Typed live-web readings with provenance. A LiveReading is only ever created
by an extractor that can cite its evidence; consumers apply readings through
overlay.py, which refuses anything not high-confidence and fresh. 'No reliable
live data' is a first-class outcome, never an error."""

from dataclasses import dataclass, field, asdict

# Provider states (superset of the strings get_live_status already uses)
STATE_OK = "ok"                      # >=1 high-confidence usage reading
STATE_RATE_DATA_ONLY = "rate_data_only"      # only rate-limit window data
STATE_AUTH_NO_DATA = "authenticated_no_data" # page loaded, nothing extracted
STATE_NEEDS_LOGIN = "needs_login"
STATE_UNAVAILABLE = "unavailable"    # playwright/venv missing
STATE_ERROR = "error"
STATE_STALE = "stale"                # snapshot older than freshness TTL

CONF_HIGH = "high"      # structured source or label-scoped DOM attribute
CONF_MEDIUM = "medium"  # label-scoped text match, single extractor
CONF_LOW = "low"        # legacy heuristic — NEVER applied to display

# Metric ids. rate_window is a short-term chat rate limit; it must NEVER be
# mapped onto a usage-cap window (that mistake is what this round fixes).
METRIC_WEEKLY_PCT = "weekly_pct"
METRIC_MODEL_WEEKLY_PCT = "model_weekly_pct"   # reading.model says which model
METRIC_FIVE_HOUR_PCT = "five_hour_pct"
METRIC_FIVE_HOUR_STATE = "five_hour_state"     # value: "starts_on_first_message"
METRIC_RESET_AT = "reset_at"                   # value: epoch seconds (float)
METRIC_RATE_WINDOW = "rate_window"             # value: used fraction 0-100; info only


@dataclass(frozen=True)
class LiveReading:
    provider: str          # "grok" | "claude"
    metric: str            # one of the METRIC_* ids
    value: float | str | None
    confidence: str        # CONF_HIGH | CONF_MEDIUM | CONF_LOW
    extractor: str         # e.g. "grok.network_json", "claude.usage_row"
    evidence: str          # <=160 chars of the labeled source text / JSON keys
    fetched_at: float
    model: str | None = None   # for METRIC_MODEL_WEEKLY_PCT, e.g. "fable"


@dataclass
class ProviderLive:
    provider: str
    state: str                       # STATE_* value
    readings: list[LiveReading] = field(default_factory=list)
    fetched_at: float | None = None
    error: str | None = None
    note: str = ""                   # short human note, e.g. final_url
```

Add `to_dict()` / `from_dict()` helpers (plain functions in the same module,
using `asdict` and manual reconstruction) so store.py can serialize without
pickling. Truncate `evidence` to 160 chars in `LiveReading.__post_init__`?
No — frozen dataclass; instead enforce truncation in the constructor helpers
extractors will use later; for this plan just document the limit in the
docstring.

**Verify**: `python -c "from token_oracle.live.contract import LiveReading, ProviderLive, METRIC_RATE_WINDOW; print('ok')"` → `ok`

### Step 3: Create the store

Create `token_oracle/live/store.py`: atomic persistence of a snapshot dict
`{"version": 1, "written_at": <epoch>, "providers": {"grok": <ProviderLive dict>, "claude": ...}}`
at `os.path.join(XDG_DATA_HOME or ~/.local/share, "token-oracle", "live.json")`.

- `default_live_path()` — mirror `default_cache_path()` in
  `token_oracle/core/config.py:216-217`.
- `save_snapshot(providers: dict[str, ProviderLive], path=None) -> str | None`
  — atomic write copying the mkstemp + `os.replace` pattern from
  `token_oracle/snapshot/writer.py` (open that file and match it exactly,
  including the `None`-on-failure contract).
- `load_snapshot(path=None) -> dict | None` — returns the parsed dict or
  `None` on missing/corrupt file; never raises.

**Verify**: `python -m pytest -q tests/test_live_contract.py` (written in
Step 7 — at this point just verify import): `python -c "from token_oracle.live.store import save_snapshot, load_snapshot; print('ok')"` → `ok`

### Step 4: Move the scraper and make its import side-effect-free

1. `git mv token_oracle/sources/live_web.py token_oracle/live/web.py`.
2. In `token_oracle/live/web.py`, make the blessed-venv detection **lazy**:
   replace the module-level block at (old) lines 39–50 with a
   `_blessed_python()` function that performs the same check on first call and
   caches the result in a module global; update `_delegate_to_blessed` and
   `get_live_status` to call it. Importing the module must no longer spawn any
   subprocess.
3. Update the self-reference inside `_delegate_to_blessed`'s generated code
   string (`from token_oracle.sources.live_web import ...` →
   `from token_oracle.live.web import ...`).
4. `token_oracle/sources/__init__.py`: remove the `live_web` import and the
   whole re-export block; keep only the three adapter imports
   (claude_code, generic, grok).
5. Fix remaining importers mechanically:
   - `token_oracle/dashboard/app.py:11`: `from ..sources import live_web as lw`
     → `from ..live import web as lw` (deeper changes in Step 6).
   - `token_oracle/cli/main.py`: every `from ..sources import live_web` /
     `from token_oracle.sources import live_web` → `from ..live import web as live_web`
     (occurrences at ~137, ~163, ~301, ~364).

Do not otherwise edit the extraction logic in `web.py` — plans 031/032 own it.

**Verify**:
- `rtk proxy grep -rn "sources.live_web\|sources import live_web" token_oracle/ --include="*.py"` → no matches (use plain `grep -rn` if rtk is absent)
- `python -X importtime -c "import token_oracle.sources" 2>&1 | grep -c playwright` → `0`

### Step 5: Purify the engine

In `token_oracle/core/engine.py`:

1. Delete line 9 (`from ..sources.live_web import ...`).
2. In `_forecast_one`, delete the entire block starting at the comment
   `# Live web authoritative override (real Grok.com / claude.ai numbers)`
   (lines ~97–142) up to but **not** including `return cslice, forecasts`.
3. In `forecast()` (legacy path), delete the matching block starting at
   `# Live web authoritative override for legacy single-source claude/grok`
   (lines ~208–249), keeping the `for f in fs: object.__setattr__(f, "profile", "default")`
   tail and `return fs`.
4. Leave both `try_get_claude_five_hour_data` blocks untouched.

**Verify**:
- `rtk proxy grep -n "live" token_oracle/core/engine.py` → only hits in comments about the five-hour local overlay, no `live_web`/`fetch_` matches
- `python -m pytest -q tests/test_engine.py` → all pass

### Step 6: Overlay + legacy adapter, and route the dashboard through them

Create `token_oracle/live/legacy.py`:

```python
"""Adapter from the legacy fetcher dicts (live/web.py) to typed ProviderLive.
Deliberately conservative: every percentage produced by the old regex
heuristics is CONF_LOW (withheld from display); only structurally-anchored
facts get medium/high. Plans 031/032 replace the fetchers with extractors
that emit high-confidence readings natively."""
```

`provider_live_from_legacy(provider: str, raw: dict | None, now: float) -> ProviderLive`
mapping rules (implement exactly):

| raw content | reading | confidence |
|---|---|---|
| `raw is None` | no readings, state `needs_login` | — |
| `authenticated` truthy, nothing else mapped | state `authenticated_no_data` | — |
| `build_pct` / `overall_pct` (grok) | METRIC_WEEKLY_PCT | **low** |
| `all_pct` (claude) | METRIC_WEEKLY_PCT | **low** |
| `fable_pct` (claude) | METRIC_MODEL_WEEKLY_PCT, model="fable" | **low** |
| `five_hour_pct` (claude) | METRIC_FIVE_HOUR_PCT | **low** |
| `five_hour_state == "starts_on_first_message"` | METRIC_FIVE_HOUR_STATE | **medium** |
| `query_remaining`+`query_total` (grok) | METRIC_RATE_WINDOW, value = used pct | **high** (but info-only by metric class) |
| `reset_in_secs` | METRIC_RESET_AT, value = now + secs | **low** |

State selection: `ok` only if ≥1 usage-class reading (weekly/model_weekly/5h)
has confidence high; else `rate_data_only` if a rate_window reading exists;
else `authenticated_no_data` / `needs_login` as above. (Consequence: after
this plan, live percentages are *withheld* until 031/032 land honest
extractors. That is intended — wrong numbers off the screen immediately.)
Set `evidence` from whatever short string is available (`scrape_note`,
`final_url`, or the raw key name), truncated to 160 chars.

Create `token_oracle/live/overlay.py`:

```python
@dataclass(frozen=True)
class LiveCell:
    pct: float | None       # applied live percentage, or None
    state: str              # provider STATE_* (STATE_STALE if outdated)
    age_secs: float | None
    evidence: str = ""
    extractor: str = ""

FRESH_TTL_SECS = 180.0

def overlay_cells(forecasts, snapshot: dict | None, now: float,
                  ttl: float = FRESH_TTL_SECS) -> dict[tuple[str, str], LiveCell]:
```

Mapping table (exact, no fuzzy matching):
- grok METRIC_WEEKLY_PCT → key `(profile containing "grok", "weekly")`
- claude METRIC_WEEKLY_PCT → `("claude"/"default" profile, "weekly")`
- claude METRIC_MODEL_WEEKLY_PCT model="fable" → `(claude profile, "fable")`
- claude METRIC_FIVE_HOUR_PCT / _STATE → `(claude profile, "5h")` (also match
  window names "session", "current" — same set engine.py uses)
- METRIC_RATE_WINDOW → **never** mapped to any window; expose via a separate
  helper `rate_info(snapshot) -> dict` for the status line.

Application policy: a reading is applied (pct set on the cell) **only if**
`confidence == CONF_HIGH` **and** `now - fetched_at <= ttl`. Fresh-but-medium/low
→ cell with `pct=None` and the provider state; older than ttl → `state=STATE_STALE`,
`pct=None`. Profile matching: use `Forecast.profile` values present in the
forecasts list ("grok", "claude", "default"); "default" counts as claude
(matches `_profile_icon` logic in `dashboard/app.py:23-29`).

Then rewrite the live plumbing in `token_oracle/dashboard/app.py`:

1. Delete the direct-fetch provenance code: the `block_is_live` /
   `cl_live` block (lines ~59–79) and the per-window re-fetch block
   (lines ~130–151). `_render_profile_block` gains a
   `cells: dict[tuple[str, str], LiveCell]` parameter instead.
2. A window row's provenance line now derives **only** from its cell:
   - `cell.pct is not None` → show live pct as the primary number, keep the
     local `f.projected_pct` visible as `proj NN%` (dim), provenance
     `live from <provider> (<age>s ago)`.
   - `cell.pct is None` and state in (`authenticated_no_data`,
     `rate_data_only`, `stale`, `needs_login`) → show local number labeled
     `proj (local)` and a dim honesty line: `no reliable live data (<state>)`.
   - The `starts_on_first_message` special-case (lines ~85–94) keys off a
     METRIC_FIVE_HOUR_STATE reading with confidence ≥ medium in the cell —
     add an optional `state_value: str | None` field to LiveCell for it.
3. `run()`: replace the `lw.get_live_status()` throttled probe with: call the
   legacy fetchers (`lw.fetch_grok_live_usage` / `lw.fetch_claude_live_usage`)
   on the same 8s throttle, convert via `provider_live_from_legacy`, persist
   with `store.save_snapshot`, and build `cells` via `overlay_cells` for
   `render_frame`. Header/status strings keep their current wording but read
   provider states from the snapshot dict. (Plan 033 moves this probing
   out-of-process; keep the env-var silencing hack for now, but move the
   `TOKEN_ORACLE_SILENT_LIVE_PROBE=1` assignment to **before** the
   `run_forecast` call at the top of the loop — with the engine purified in
   Step 5 this is belt-and-braces, not load-bearing.)
4. `render_frame` signature becomes
   `render_frame(forecasts, now, color=None, prev_forecasts=None, live_status=None, cells=None)`
   — `cells=None` must behave as "no live data" so existing pure-render tests
   keep passing.

Doctor (`cli/main.py` `_doctor_lines` live section, lines ~135–196): change
only what Step 4's import move forces plus: after `st = lw.get_live_status()`,
also convert and `store.save_snapshot(...)` the fetched data if the fetchers
were invoked (acceptable to skip if get_live_status doesn't expose raw dicts —
in that case leave doctor semantics unchanged and note it in your report;
plan 033 restructures doctor properly).

**Verify**:
- `python -m pytest -q tests/test_dashboard.py` → all pass
- `rtk proxy grep -n "fetch_claude_live_usage\|fetch_grok_live_usage" token_oracle/dashboard/app.py` → matches only inside `run()` (the throttled probe), none in `_render_profile_block`/`render_frame`

### Step 7: Tests

Create `tests/test_live_contract.py` (model after the plain-function style of
`tests/test_snapshot.py`):
- round-trip: build a ProviderLive with 2 readings → `to_dict` → `from_dict`
  → equal fields.
- `save_snapshot`/`load_snapshot` round-trip in `tmp_path`; corrupt file →
  `load_snapshot` returns None.

Create `tests/test_live_overlay.py`:
- high-confidence fresh claude weekly reading → cell for `("claude","weekly")`
  has `pct` set.
- same reading with `CONF_LOW` → `pct is None` (regression: heuristic numbers
  withheld).
- same reading with `fetched_at = now - 3600` → `state == "stale"`, `pct is None`.
- a METRIC_RATE_WINDOW reading (150/150 queries) → **no** cell carries its
  value for any window (regression: rate limit never becomes usage %).
- METRIC_MODEL_WEEKLY_PCT model="fable" maps to `("claude","fable")` and NOT
  to `("claude","weekly")`.
- `provider_live_from_legacy("grok", {"authenticated": True, "overall_pct": 13.0}, now)`
  → state `authenticated_no_data`-or-better, and the 13.0 reading has
  confidence `low`.
- engine purity: `import token_oracle.core.engine as e` then
  `assert not hasattr(e, "fetch_claude_live_usage")`.

Update `tests/test_dashboard.py` only if a test asserts the removed
direct-fetch behavior; the existing `render_frame(...)` call signatures must
keep working unchanged.

**Verify**: `python -m pytest -q` → baseline N + new tests, 0 failures.

### Step 8: Gates

**Verify**, in order:
- `ruff check token_oracle/` → exit 0
- `ruff format --check token_oracle/` → exit 0 (format only files you touched)
- `mypy token_oracle/ --ignore-missing-imports` → exit 0
- `TOKEN_ORACLE_SKIP_BOOTSTRAP=1 python -m token_oracle.cli.main forecast` →
  prints a forecast line, returns in < 5s, and never prints any
  "launching browser" text (engine purity smoke test).

## Test plan

Covered in Step 7. Structural pattern: `tests/test_engine.py` /
`tests/test_snapshot.py` (plain functions, `tmp_path`, `monkeypatch.setenv`
for XDG isolation — see `tests/test_cli.py:183-199` for the XDG pattern; you
MUST isolate `XDG_DATA_HOME` in every store test so you never touch the real
`~/.local/share/token-oracle/live.json`).

## Done criteria

ALL must hold:

- [ ] `python -m pytest -q` exits 0 (≥ baseline count + ~10 new)
- [ ] `ruff check` / `ruff format --check` / `mypy` all exit 0
- [ ] `token_oracle/sources/live_web.py` no longer exists; `token_oracle/live/web.py` does
- [ ] `grep -rn "live_web" token_oracle/ --include="*.py"` → no matches
- [ ] `grep -n "fetch_" token_oracle/core/engine.py` → no matches
- [ ] `python -X importtime -c "import token_oracle.sources"` spawns no subprocess and mentions no playwright module
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- `token_oracle/sources/live_web.py` or `token_oracle/sources/grok.py` is
  absent from your worktree — the operator did not commit the live-web WIP;
  your base is wrong.
- Step 1 baseline pytest has ANY failure.
- The engine override blocks don't match the excerpts (search for the comment
  `# Live web authoritative override` — if it appears ≠ 2 times, drift).
- Removing the dashboard direct-fetch block breaks more than 3 existing
  dashboard tests — the coupling is deeper than this plan assumed.
- You find a third call site applying live percentages to forecasts beyond
  the two engine blocks and the dashboard.

## Maintenance notes

- Plans 031/032 rewrite `live/web.py` extraction into `live/grok_extract.py` /
  `live/claude_extract.py` emitting `LiveReading` natively; `legacy.py` is then
  deleted. Plan 033 replaces the dashboard's in-process probe with an
  `oracle live-probe` subprocess writing the same store.
- Reviewer scrutiny: confirm no code path recomputes `used` from a live pct
  (`int(round(pct / 100.0 * cap))` must be gone from engine and dashboard).
- Deferred deliberately: using live readings to re-anchor the *forecast math*
  (e.g. correcting local `used`). That is a modeling decision, not a display
  fix — record interest in plans/README if the operator wants it later.
- The `try_get_claude_five_hour_data` server overlay still writes
  `projected_pct` with a current-% semantic (engine.py:81-94). Same semantic
  smell, different (local, non-browser) source — left for a future plan.
