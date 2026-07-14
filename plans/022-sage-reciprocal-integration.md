# Plan 022: agentic-sage reciprocal integration — detect, hint, stay optional

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ada32e9..HEAD -- token_oracle/cli/main.py token_oracle/snapshot/writer.py tests/test_cli.py README.md SETUP.md AGENTS.md`
> If `_doctor_lines` in `main.py` differs from the excerpt below beyond
> plans 003/008/019/021 drift (new rows/subcommands are fine; the
> rows-list + ok_badge structure must remain), STOP.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW (read-only detection + docs; fail-open everywhere)
- **Depends on**: none hard. Soft: 015 (snapshot write-through — makes the
  hinted setup actually stay fresh), 021 (wizard hook)
- **Category**: direction / dx
- **Planned at**: commit `ada32e9`, 2026-07-02
- **Executed**: 2026-07-14 — DONE. `_sage_row` + doctor row; 6 hermetic branch tests; README/SETUP/AGENTS docs.

## Why this matters

token-oracle and agentic-sage are siblings with a clean division of labor:
**oracle owns tokens, usage, cost, forecasts; sage owns session awareness,
fleet coordination, and guidance.** The integration contract already
half-exists — sage ships an optional `tokenForecastPath` config key with a
fail-green doctor check that probes any path you point it at, and
oracle's SETUP.md tells users to set it. What's missing is the reciprocal
half: oracle doesn't detect sage, so a user with both installed gets no
nudge that one command would light up the integration. This plan adds a
fail-open sage detection row to `oracle doctor` with a copy-pasteable hint,
and tightens the docs on both the division of labor and the wiring. No hard
dependency in either direction — Occam's razor: two tools, one JSON file
between them.

## Current state

**oracle side** (this repo):

- `token_oracle/snapshot/writer.py:1-3` docstring: "Stable JSON snapshot any
  external consumer (agentic-sage, a status bar) can read." —
  `default_snapshot_path()` (writer.py:25-27) →
  `$XDG_DATA_HOME|~/.local/share` + `/token-oracle/forecast.json`;
  `SCHEMA_VERSION = 1`.
- `token_oracle/cli/main.py` `_doctor_lines(cfg, config_path, color, now)`
  (main.py:29-95): builds `rows = [(name, detail, good), ...]`, renders each
  as `ok_badge + name + detail`, returns `(lines, bad_count)`; doctor exits 1
  when `bad > 0`.
- `SETUP.md:160-177` "Optional integrations → agentic-sage" — documents
  setting `tokenForecastPath` in sage's config and keeping the snapshot
  fresh via cron/hook. `README.md:96` has a "Works with agentic-sage"
  section; `AGENTS.md:168` Step 7 "(Optional) Wire agentic-sage".

**sage side** (read-only facts, verified 2026-07-02 in
`/home/kento/Repositories/agentic-sage` — do NOT modify that repo):

- Global config: `~/.claude/agentic-sage/config.json`; legacy fallback dir
  `~/.claude/sage/` (sage `lib/roots.mjs:28,33`). Registry:
  `~/.claude/agentic-sage/registry.json`.
- The key: `"tokenForecastPath"` in that global config — sage's doctor probes
  the path's existence, stays green when unset ("not configured (optional)"),
  and `sage on|off` toggles preserve the key (sage `lib/control.mjs:18,189-203`,
  tested in its `test/control.test.mjs`). The probe is a generic existence
  check — pointing it at oracle's `forecast.json` just works.
- Sage is Node/ESM, zero deps, "FAIL-OPEN, DEFAULT-OFF" invariants; no
  `--json` CLI output — file-level integration is the intended surface.

## Design (decided — do not redesign)

**One new doctor row, `sage`, appended to `rows` in `_doctor_lines`** —
fail-open in every branch (`good=True` unless the integration is *configured
wrong*):

New helper `_sage_row(now)` in `cli/main.py` (keep it beside
`_doctor_lines`; ~25 lines):

1. Locate sage config: first existing of
   `~/.claude/agentic-sage/config.json`, `~/.claude/sage/config.json`
   (expanduser; honor no env overrides — sage's own resolution is more
   complex, but the default home covers the real install base; a custom
   sage root simply reads as "not detected", which is fail-open).
2. Not found → `("sage", "agentic-sage not detected (optional)", True)`.
3. Found, JSON parses, `tokenForecastPath` absent/empty →
   `("sage", 'detected — link it: add "tokenForecastPath": "<snapshot_path>" to <sage_config>', True)`
   where `<snapshot_path>` is `default_snapshot_path()` (import from
   `..snapshot.writer`). Still `good=True`: unlinked is a valid state.
4. Found, key set and its expanduser'd value == `default_snapshot_path()` →
   detail `linked via <path>`; additionally, if the snapshot file itself is
   missing or older than 24 h (`os.path.getmtime` vs `now`), detail becomes
   `linked but snapshot is <stale/missing> — run: token-oracle snapshot`
   with `good=False` (this is the one red case: a configured-but-dead link
   silently feeds sage stale data).
5. Found, key set to some other path → `linked to <path> (not oracle's
   default snapshot — fine if intentional)`, `good=True`.
6. Any OSError/ValueError anywhere → branch 2's detail with
   `(unreadable config)` appended, `good=True`. Never raise.

**Wizard hook** (only if plan 021 is DONE): after the wizard's last
question, when `_sage_row(now)` hits branch 3, print its hint line dim.
Guard by checking the landed wizard code; if 021 isn't landed, skip — do not
block on it.

**Docs**:
- README "Works with agentic-sage": add the reciprocal sentence — oracle's
  doctor detects sage and prints the exact key to set; one line on division
  of labor ("oracle: tokens, cost, forecasts · sage: sessions, fleet,
  guidance").
- SETUP.md integration section: add "oracle doctor tells you the state of
  this link" + the stale-snapshot remedy (`token-oracle snapshot` via cron,
  or plan 015's write-through once landed — reference it as "if your
  version has `snapshot_writethrough`, enable it").
- AGENTS.md Step 7: append the doctor-driven flow (run doctor, follow hint).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass |
| Lint | `ruff check token_oracle/ && ruff format --check token_oracle/` | exit 0 |
| Types | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |

## Scope

**In scope**:
- `token_oracle/cli/main.py` (`_sage_row` + one row append; wizard hook only
  if 021 landed)
- `tests/test_cli.py` (extend)
- `README.md`, `SETUP.md`, `AGENTS.md` (sections named above)

**Out of scope**:
- **The agentic-sage repository — absolutely no edits there.** Sage-side
  follow-ups live in its own backlog (see Maintenance).
- Writing to sage's config from oracle (auto-linking) — rejected: mutating a
  sibling tool's config crosses the loose-coupling line; the hint is the
  product.
- `snapshot/writer.py`, `forecast.json` schema, engine, dashboard.
- Plan 015's write-through flag (its own plan).

## Git workflow

- Branch: `advisor/022-sage-reciprocal-integration`
- Conventional commits, e.g. `feat(doctor): detect agentic-sage and hint the link`
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: `_sage_row` + doctor wiring

Implement per Design; append the row after the `windows` row in
`_doctor_lines` (main.py:78-84 rows list). The sage-home candidates must be
overridable for tests — read base dir from
`os.environ.get("SAGE_HOME_FOR_TESTS")` first? No — keep production code
clean: take an optional `home=None` parameter defaulting to
`os.path.expanduser("~")` and monkeypatch `expanduser` in tests (the
existing config tests already monkeypatch XDG/HOME this way — follow
`tests/test_config.py`).

**Verify**: `python -m pytest -q tests/test_cli.py` → existing doctor tests
still pass (row count changes — fix fixtures if they assert counts).

### Step 2: tests for every branch

In `tests/test_cli.py`, one test per branch (fake home via `tmp_path` +
monkeypatched `expanduser`): not detected; detected-unlinked (hint contains
`tokenForecastPath` and the snapshot path); linked-fresh (write a snapshot
file with current mtime → `good`, doctor exit 0); linked-stale (mtime 2 days
old via `os.utime` → doctor exit 1, detail says stale); linked-elsewhere
(`good=True`); corrupt sage config (invalid JSON → `good=True`, unreadable
note). Drive through `main(["doctor", "--config", ..., "--now", ...])` and
capsys, matching the existing doctor-test style.

**Verify**: `python -m pytest -q tests/test_cli.py` → all pass.

### Step 3: docs (+ wizard hook if 021 landed)

Per Design. Check `plans/README.md`: if 021 is DONE, add the wizard hint
line and one wizard test asserting it appears when a fake sage config
exists.

**Verify**: `grep -n "tokenForecastPath" README.md SETUP.md AGENTS.md` →
hits in all three; `python -m pytest -q` green.

## Test plan

- `tests/test_cli.py`: +6 branch tests (Step 2), +1 wizard test (conditional).
- Pattern: existing doctor tests in `tests/test_cli.py`.
- Verification: `python -m pytest -q` → all pass.

## Done criteria

- [ ] `python -m pytest -q` exits 0
- [ ] `ruff check`, `ruff format --check`, `mypy` exit 0
- [ ] With no sage install present: `oracle doctor` exits with the same code
  as before this plan (the sage row must not flip a healthy system red)
- [ ] All 6 detection branches have a test each
- [ ] `grep -rn "agentic-sage" token_oracle/` shows hits only in
  `cli/main.py` (detection) — no other module knows sage exists
- [ ] `git status` clean outside in-scope list; `plans/README.md` row updated

## STOP conditions

- `_doctor_lines`' rows structure changed beyond recognition (drift).
- You are tempted to write into `~/.claude/agentic-sage/config.json` — the
  design explicitly rejects auto-linking; report if a reviewer asked for it.
- Sage's config location facts appear wrong on this machine (e.g. the file
  exists but is a directory) — report; don't broaden the probe heuristics
  unilaterally.

## Maintenance notes

- **Sage-side follow-ups (separate repo, separate planning, do not do here):**
  (a) sage's board has a dead `ctx_used`/`ctx_window` cell
  (`lib/board.mjs:73`, flagged in sage's own backlog) that a
  token-oracle-fed writer could light up; (b) sage's README example path for
  `tokenForecastPath` is `~/.local/share/token-forecast` — a docs PR there
  could show oracle's real default. Both are sage-repo decisions.
- If sage ever adds root-relocation env vars to its install base, branch 1's
  candidate list is the single place to extend.
- The 24 h staleness threshold is a judgment call — ADAPTERS.md's snapshot
  staleness section is the place to document it; keep the two in sync.
- Plan 015 (write-through) turns the stale-link remedy from "set up cron"
  into "set one config flag" — when 015 lands, update SETUP's remedy text.
