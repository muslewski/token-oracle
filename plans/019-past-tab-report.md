# Plan 019: Past tab + `oracle report` — the historical ledger

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ada32e9..HEAD -- token_oracle/core/ token_oracle/dashboard/ token_oracle/cli/main.py tests/ README.md SETUP.md`
> Plans 016, 017, and 018 MUST be DONE (check their rows in
> `plans/README.md`). Verify: `token_oracle/core/events.py` exists,
> `token_oracle/core/pricing.py` exists, and `token_oracle/dashboard/app.py`
> dispatches tabs to renderers with a `render_placeholder` for "past". If any
> of those is absent, STOP.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW (new pure aggregation + rendering; one additive CLI subcommand)
- **Depends on**: plans 016 (events v2), 017 (pricing), 018 (TUI shell)
- **Category**: direction
- **Planned at**: commit `ada32e9`, 2026-07-02

## Why this matters

The Oracle currently only projects forward; it cannot tell you what you
already spent. ccusage (16.7k★) built its entire product on exactly this —
daily/weekly/monthly per-model token+cost tables — and it is a static
report tool. This plan gives token-oracle the same ledger twice over: a
live **Past tab** in the TUI and a scriptable **`oracle report`**
subcommand with `--json` (competitor parity + automation surface). Data
comes from the existing event cache, which retains 9 weeks
(`HIST_SECS = 63*24*3600`, core/profile.py:8) — enough for a 30-day daily
table and weekly rollups without touching raw transcripts again.

## Current state

- After plan 016: cached events are 8-field records
  `[ts, tok, model, input, output, cache_create, cache_read, cost_usd]`
  (`token_oracle/core/events.py`, `normalize`/`as_pairs`). The engine keeps
  them in `cache["events"]`; `token_oracle/core/cache.py` `load_cache(path)`
  returns the dict (never raises).
- After plan 017: `token_oracle/core/pricing.py` has
  `cost_summary(events, mode, overrides) -> {"usd", "unpriced_tokens", "by_model"}`
  and `Config` has `cost_mode` / `pricing` fields.
- After plan 018: `token_oracle/dashboard/app.py` has a tab→renderer dict
  where "past" maps to `render_placeholder`; pure renderers take
  `(…, width, enabled)`; `render_tab_bar`/`render_footer` exist;
  `tests/test_dashboard.py`/`tests/test_keys.py` show the test style.
- `token_oracle/cli/main.py` (pre-018 excerpt, still accurate for dispatch):
  subcommands are registered in a loop at main.py:101-107 and dispatched by
  `if args.cmd == "...":` blocks; `forecast --json` prints
  `json.dumps(build_snapshot(fs, now))` (main.py:114-115). A hidden `--now`
  flag exists on every subcommand for deterministic tests (main.py:22, 25-26).
- Day bucketing convention: `token_oracle/core/timeutil.py` `bucket_key`
  (timeutil.py:16-19) uses **local time** (`datetime.fromtimestamp(ts).astimezone()`)
  — the report must bucket days the same way (local calendar days).
- Formatters available (timeutil.py): `fmt_tokens` (`12k`, `1.2M`),
  `fmt_dur`, `fmt_dh`. Note the known nit: `fmt_tokens(<1000)` renders `0k`
  (recorded in plans/README.md rejected list) — for report cells use a new
  `fmt_tokens_exact` helper in report.py if sub-1k precision matters; do not
  change timeutil.py.
- Colors: `token_oracle/cli/colors.py` — `dim`, `violet`, `gauge`,
  `color_enabled()`. Core-ring modules must not import it.

## Design (decided — do not redesign)

**New pure module `token_oracle/core/report.py`** (core ring: no colors, no
printing):

```python
"""Historical aggregation over cached events: local-calendar daily rows and
weekly totals, with optional cost via core.pricing. Pure; stdlib only."""

def daily_rows(events, now, days=14, cost_mode="auto", pricing=None):
    """-> list of dicts, oldest first, one per local calendar day that has
    events (empty days included so the sequence has no gaps):
    {"date": "2026-07-02", "tokens": int, "input": int, "output": int,
     "cache_create": int, "cache_read": int, "usd": float | None,
     "unpriced_tokens": int, "by_model": {model: tokens}}"""

def totals(rows):
    """Sum a rows list into one dict of the same shape (date -> "total")."""

def report_dict(events, now, days, cost_mode, pricing):
    """Stable JSON shape: {"schema": 1, "generated_at": now, "days": rows,
    "totals": {...}} — the `oracle report --json` payload."""
```

`usd` is `None` (and the column hidden) when `cost_mode == "off"`.

**New dashboard renderer `render_past(rows, width, enabled)`** in
`token_oracle/dashboard/app.py` (or `dashboard/past.py` if app.py would pass
~250 lines — executor's call; keep renderers pure either way):

- Header: `Past — last 14 days` (dim).
- One row per day:
  `Jul 02  ▇▇▇▇▇▇░░  1.2M   $4.31   top: sonnet-4-5`
  where the mini-bar is that day's tokens relative to the max day (`▇`,
  8 cells), `top:` is the highest-token model with its family prefix only
  (strip `claude-` prefix and date suffix for display).
- Width-responsive (ccusage's <100-column collapse, see research doc): at
  width < 100 drop the `top:` column; at width < 72 drop the bar.
- Totals row separated by a dim rule; if `unpriced_tokens > 0` render a dim
  `(+Nk tokens unpriced)` warning — never silently $0.
- Cost column omitted entirely when `cost_mode == "off"`.

**Wire into the TUI**: replace the "past" placeholder in the tab dispatch
with a function that pulls events via `load_cache(cfg.cache_path)["events"]`
(normalized) and calls `daily_rows` — computed at most once per 30 s (reuse
the fetched rows between frames; a simple `(fetched_at, rows)` closure/box in
`run()` is fine).

**New CLI subcommand `report`** in `cli/main.py`:

```
oracle report [--days N] [--json] [--config FILE]
```

- default `--days 14`, max 63 (clamp + note when clamped).
- plain mode: print the same rows via `render_past` (static, width from
  `shutil.get_terminal_size()`, color via `colors.color_enabled()`).
- `--json`: `json.dumps(report_dict(...))`.
- Register it in the existing subcommand loop; it accepts `--config`/`--now`
  like the rest.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass |
| Lint | `ruff check token_oracle/ && ruff format --check token_oracle/` | exit 0 |
| Types | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |
| Manual | `oracle report --days 7` then `oracle report --json | python -m json.tool` | table renders; valid JSON |

## Scope

**In scope**:
- `token_oracle/core/report.py` (create)
- `token_oracle/dashboard/app.py` (past renderer + tab wiring; or new
  `token_oracle/dashboard/past.py`)
- `token_oracle/cli/main.py` (report subcommand)
- `tests/test_report.py` (create), `tests/test_dashboard.py` (extend),
  `tests/test_cli.py` (extend)
- `README.md` (subcommand table + quickstart line), `SETUP.md` (CLI reference)

**Out of scope**:
- `token_oracle/core/{engine,profile,windows,cache,events,pricing}.py` —
  consume, don't modify.
- `snapshot/writer.py` / `forecast.json` schema — report JSON is a separate
  payload with its own `schema: 1`.
- Future tab (plan 020), configurator (021).
- Reading raw transcripts for >9-week history (see Maintenance).

## Git workflow

- Branch: `advisor/019-past-tab-report`
- Conventional commits, e.g. `feat(report): daily ledger — past tab + oracle report`
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: `core/report.py` + tests

Implement per Design. `tests/test_report.py` (function style, fixed `now`,
synthetic 8-field events): rows bucket by local day with no gaps; token-class
sums correct; `by_model` groups; `usd` computed via a `pricing` override so
the test doesn't depend on SNAPSHOT values (pass
`pricing={"testmodel": {"input": 1.0, "output": 2.0, "cache_write": 0, "cache_read": 0}}`
and events with `model="testmodel"`); `cost_mode="off"` → `usd is None`;
unknown model → counted in `unpriced_tokens`; `totals` sums; `report_dict`
has `schema == 1`. To keep local-day bucketing deterministic, set
`monkeypatch.setenv("TZ", "UTC")` + `time.tzset()` in a fixture (POSIX-only
is acceptable — CI is Linux; guard with `hasattr(time, "tzset")`).

**Verify**: `python -m pytest -q tests/test_report.py` → all pass.

### Step 2: past renderer + TUI wiring

`render_past` per Design; swap the placeholder in the tab dispatch; add the
30 s row-refresh box in `run()`. Extend `tests/test_dashboard.py`: rows
render dates and token counts; width 60 hides the bar column; color-off
output contains no `\033`; unpriced warning appears when set.

**Verify**: `python -m pytest -q tests/test_dashboard.py` → all pass.
Manual: `oracle dash` → arrow to Past → table renders live.

### Step 3: `report` subcommand

Wire per Design. Extend `tests/test_cli.py` (see its existing style — it
invokes `main([...])` with `--config`/`--now` against tmp fixtures): plain
run exits 0 and prints a date; `--json` output parses and has
`schema == 1` and `len(days) <= days`; `--days 200` clamps to 63.

**Verify**: `python -m pytest -q tests/test_cli.py` → all pass.

### Step 4: docs

README subcommand table + one quickstart line (`oracle report  # what you
spent, day by day`); SETUP CLI reference gains `report` with flags.

**Verify**: `grep -n "report" README.md SETUP.md` → hits; full suite green.

## Test plan

- `tests/test_report.py`: ~8 cases (Step 1).
- `tests/test_dashboard.py`: +4 cases (Step 2).
- `tests/test_cli.py`: +3 cases (Step 3).
- Verification: `python -m pytest -q` → all pass.

## Done criteria

- [ ] `python -m pytest -q` exits 0
- [ ] `ruff check`, `ruff format --check`, `mypy` exit 0
- [ ] `oracle report --json --now 1751500000 --config /nonexistent 2>/dev/null | python -m json.tool` exits 0 (empty-data path: valid JSON, empty days)
- [ ] `grep -n "import" token_oracle/core/report.py` shows no `cli.colors` / `dashboard` imports (core-ring discipline)
- [ ] Past tab renders in a manual `oracle dash` smoke (reported in completion note)
- [ ] `git status` clean outside in-scope list; `plans/README.md` row updated

## STOP conditions

- Any of plans 016/017/018 not actually landed (missing modules above).
- Local-day bucketing produces gaps or duplicates around DST in your tests —
  report rather than papering over with UTC-only bucketing (local days are
  the product decision; DST days are 23/25 h long and that's fine).
- The TUI wiring requires touching `run()`'s key/screen handling beyond
  adding the rows-refresh box.

## Maintenance notes

- History depth is capped by cache retention (9 weeks). If users want more,
  the right move is a separate archival rollup file written by the engine
  (rolled-up days are tiny), NOT extending `HIST_SECS` — the profile math's
  cost is linear in retained events. Deferred deliberately.
- The `report_dict` JSON is now a public contract (`schema: 1`) — additive
  changes only, bump on breaking change (same policy as forecast.json,
  ADAPTERS.md).
- Reviewer focus: no-gap day sequence, unpriced-token surfacing, core-ring
  import discipline.
- Nice follow-up (unplanned): a GitHub-style hour×weekday heat strip from the
  existing 168-bucket profile — the data is already in `cache["profile"]`.
