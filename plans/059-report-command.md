# Plan 059 — `oracle report` subcommand (daily cost+cap ledger)

**Written against commit `bd54990`.** Depends on **plan 058** (`core/report.py`
**Status:** DONE — merged to main via advisor/058-sticky-hooks (2026-07-14)
+ `engine.cached_events`) being applied first in the same worktree. If
`core/report.py` does not export `daily_ledger`, `group_ledger`, `weekly_cap`,
`LedgerRow` — STOP; run 058 first.

## Why this matters

This is the shareable, differentiated surface: a per-day ledger of tokens **and
USD** with the one column ccusage cannot show — **% of the weekly cap burned**,
tying the report to token-oracle's "know when you'll hit the limit" identity.
Ships as a standalone print command (NOT inside the future TUI tab shell, plan
018 — do not touch that).

## Scope

**In scope — edit/create ONLY:**
- `token_oracle/cli/main.py` (add the `report` subcommand: help entry, subparser
  flags, dispatch block, and small render helpers)
- `tests/test_cli.py` (add report tests)

**Out of scope — do NOT touch:** `core/report.py` (done in 058 — call it, don't
edit), `core/engine.py`, `core/pricing.py`, `core/config.py`, `dashboard/`,
`adapters/`, README/SETUP (plan 060 owns docs). Do NOT add `--by project`
(events carry no project id — see 058). Do NOT modify any existing subcommand.

## Current-state excerpts (from `cli/main.py` @ `bd54990`)

Subcommands are declared in a name tuple, per-command flags added by `if name ==`
blocks, dispatched by `if args.cmd ==` blocks. `_CMD_HELP` maps name→one-liner.
Config + now are already resolved before dispatch:
```python
_CMD_HELP = { "forecast": "...", "snapshot": "...", "statusline": "...",
    "tmux": "...", "doctor": "...", "dash": "...", "init": "...", "clean": "...",
    "live": "...", "live-setup": "...", "live-probe": "..." }
...
sub = parser.add_subparsers(dest="cmd", required=True, metavar="<command>")
for name in ("forecast","snapshot","statusline","tmux","doctor","dash","init","clean","live","live-setup","live-probe"):
    sp = sub.add_parser(name, help=_CMD_HELP[name], description=_CMD_HELP[name])
    _add_common(sp)
    if name == "forecast":
        sp.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of text")
    ...
args = parser.parse_args(argv)
cfg = load_config(args.config)
now = _now(args)
...
if args.cmd == "forecast":
    fs = run_forecast(now, cfg)
    if args.json: print(json.dumps(build_snapshot(fs, now), indent=2))
    ...
    return 0
```
How doctor scans events per profile (mirror this pattern to obtain events):
```python
from ..core.profile import HIST_SECS
from ..sources.base import get_source
# single:
src = get_source(cfg.source, cfg.source_opts)
files, events = src.scan({}, now, HIST_SECS)
# multi:
for _pname, pdef in cfg.profiles.items():
    src_name = pdef.get("source", cfg.source)
    opts = pdef.get("source_opts", cfg.source_opts or {})
    src = get_source(src_name, opts)
    fs, evs = src.scan({}, now, HIST_SECS)
```
`cfg.windows` is `list[Window]` (`.name/.cap/.period_secs`); for multi, each
profile's windows come from `pdef.get("windows")` (raw dicts) falling back to
`cfg.windows`. `cfg.cost_mode` (str) and `cfg.pricing` (dict) feed the report
core's `mode`/`overrides`. Colors: `from ..cli import colors` — use
`colors.gauge(text, pct, enabled)` for the %CAP cell and `colors.color_enabled()`.

## What to build

### 1. Register the subcommand
- Add `"report": "daily token + cost ledger with % of your weekly cap"` to `_CMD_HELP`.
- Add `"report"` to the name tuple (put it right after `"forecast"`).
- Add a flags block:
  ```python
  if name == "report":
      sp.add_argument("--json", action="store_true", help="emit machine-readable JSON")
      sp.add_argument("--by", choices=["day", "week", "model"], default="day",
                      help="grouping axis (default: day)")
      sp.add_argument("--since", default=None, metavar="YYYY-MM-DD",
                      help="only include events on/after this local date")
      sp.add_argument("--until", default=None, metavar="YYYY-MM-DD",
                      help="only include events on/before this local date")
      sp.add_argument("--days", type=int, default=7,
                      help="number of days for the default daily view (default: 7)")
  ```

### 2. Dispatch (`if args.cmd == "report":`)
A `_report_sections(cfg, now, args) -> list[dict]` helper that returns one
section per profile (single-source configs → one section keyed by `cfg.source`):
- For each profile: scan events (doctor pattern), normalize via
  `events_mod.normalize`, filter by `--since`/`--until` (inclusive local-date
  bounds; parse with a small `_parse_date(s) -> float|None` using
  `time.strptime(s, "%Y-%m-%d")` + `time.mktime`; a bad date → argparse-style
  error to stderr + return code 2).
- Resolve that profile's `weekly_cap` from its windows (build `Window` objs for
  multi via the same `_window_from_dict` engine uses, or read `cfg.windows` for
  single). Use `report.weekly_cap(windows)`.
- Build rows: `--by day` (default) → `report.daily_ledger(events, cap, now,
  days=args.days, mode=cfg.cost_mode, overrides=cfg.pricing)`; otherwise
  `report.group_ledger(events, args.by, now, mode=cfg.cost_mode, overrides=cfg.pricing)`.
- Section dict: `{"profile": pname, "cap": cap, "by": args.by, "rows": [row_to_dict(r)...]}`.

**Text render** (`--json` off): a fixed-width table per section. Header line
`profile · N-day ledger` (violet). Columns: `DAY/WEEK/MODEL`, `TOK`, `COST`,
`%CAP` (omit `%CAP` for `--by week/model` where pct_cap is None). Formatting:
- tokens via existing `fmt_tokens` (`from ..core.timeutil import fmt_tokens`).
- cost: `f"${r['cost']:,.2f}"` when not None, else `"—"` (never `$0.00` for
  unpriced). If the section's rows are ALL cost=None (e.g. grok / `cost_mode=off`),
  print a dim note under the table: `cost unavailable (cost_mode=off or unpriced models)`.
- `%CAP`: `colors.gauge(f"{r['pct_cap']:.0f}%", r['pct_cap'], enabled)` when not None.
- TOTAL row (label `TOTAL`) rendered with a rule line above it.
- If a section has zero events: `no usage data for <profile> in range` (dim).
- Right-align numeric columns; keep it readable at 80 cols. This is a print
  command, not the width-responsive dash — no Scene, no fixed-height contract.

**JSON render** (`--json`): `print(json.dumps({"generated_at": now, "sections":
sections}, indent=2))` — stable machine shape (`row_to_dict` = the LedgerRow
fields). This is the scriptable contract; keep keys stable.

Return `0` on success, `2` on a bad `--since/--until` date.

### 3. First-run / no-data honesty
If every section has zero events AND stdout is a TTY (`_is_interactive()`),
print `_first_run_hint()` (exists already) instead of empty tables, return 0.
Non-interactive (pipe/`--json`) → still emit the (empty) structure/`idle`-style
output, never the hint (mirror the `forecast` rule).

## Verification (worktree root, `TOKEN_ORACLE_SKIP_BOOTSTRAP=1`)

1. `oracle report --help` lists `--by {day,week,model}`, `--since`, `--until`,
   `--days`, `--json`; description mentions weekly cap.
2. Deterministic run against a temp config + generic source fixture (build a
   `[ts,tokens]` events JSON, `source=generic`, `source_opts.events_path=...`,
   one weekly window `cap` set) with `--now`:
   ```
   TOKEN_ORACLE_SKIP_BOOTSTRAP=1 oracle report --config <tmpcfg> --now <T> --days 3
   ```
   → 3 day rows + TOTAL; %CAP column present and colored; tokens match the fixture.
3. `oracle report --config <tmpcfg> --now <T> --json` → valid JSON with
   `sections[0].rows`, each row carrying `label/tokens/cost/unpriced_tokens/pct_cap`.
4. `--by model` → per-model rows, no %CAP column, TOTAL last.
5. `--since 2026-01-01 --until 2026-01-02` narrows correctly; `--since notadate`
   → stderr error + exit 2.
6. Piped no-data (`oracle report --config <emptycfg> --now <T> | cat`) prints no
   `_first_run_hint` text (stable); interactive no-data path shows the hint
   (assert via monkeypatched `_is_interactive`, as `test_cli.py` already does for 043).
7. `python -m pytest -q tests/test_cli.py` and full `python -m pytest -q` pass.
8. Gates: `ruff check token_oracle tests` ; `ruff format --check token_oracle tests` ;
   `python -m mypy token_oracle --ignore-missing-imports` → 0 errors.
9. `git diff --name-only bd54990..HEAD` (for THIS plan's commits) touches only
   `token_oracle/cli/main.py` and `tests/test_cli.py` (plus 058's files already committed).

## Test plan (`tests/test_cli.py`, follow existing hermetic patterns)

Reuse the file's config-monkeypatch / `--now` idioms. Use a `generic` source
with a `tmp_path` events file so the tests are hermetic (no real `~/.claude`).
Cover: daily table row count + TOTAL, `--json` shape + stable keys, `--by model`,
`--since/--until` filtering + bad-date exit 2, no-data TTY-hint vs piped-stable.
Set `XDG_DATA_HOME` to `tmp_path` in any test that could touch ratelimits/live
snapshots, to stay hermetic (the plan-051/054 real-machine-state trap).

## STOP conditions
- `core/report.py` missing the 058 exports → STOP (058 not applied).
- If adding `report` forces edits to another subcommand's block → STOP; they are
  independent, keep them so.
- Do NOT implement `--by project`.

## Contract
One commit per step (subparser+dispatch; render helpers; tests — 2–3 commits,
conventional, e.g. `feat(cli): oracle report — daily cost+cap ledger`).
PROGRESS.md ledger (untracked). Final line exactly:
`RESULT: ok|partial|failed — commits: <n> — <summary>`.
