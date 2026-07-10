# Plan 003: Make `doctor` actually diagnose — config provenance, data-source probe, cache health, exit code

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat d2b4d32..HEAD -- token_oracle/cli/main.py tests/test_cli.py AGENTS.md`
> Plan 001 (config validation) is a declared dependency and WILL have changed
> `token_oracle/core/config.py` — that is expected. For the files above,
> compare the "Current state" excerpts against live code; on a mismatch
> beyond Plan 001/002's declared changes, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans/001-config-validation-never-crash.md (uses `Config.issues`)
- **Category**: dx
- **Planned at**: commit `d2b4d32`, 2026-07-01

## Why this matters

README promises "`token-oracle doctor` — check configuration + data sources". Today doctor checks almost nothing: the config row is hardcoded to pass (`True`), config parse failures were already silently swallowed upstream, and there is no data-source check at all — no "does the projects dir exist", no "how many events were found", no "how old is the newest event". The most common real failure (forecast says `idle` forever because the source finds nothing) shows a full column of ✓. This plan turns doctor into the tool the README describes, and gives it a meaningful exit code so scripts and agents can gate on it.

## Current state

- `token_oracle/cli/main.py` — `_doctor_lines()` builds the report; `main()` dispatches. Excerpt `main.py:25-40` at `d2b4d32`:

```python
def _doctor_lines(cfg, config_path, color):
    avail = available()
    rows = [
        ("config", config_path or default_config_path(), True),
        ("source", f"{cfg.source} (available: {', '.join(avail)})", cfg.source in avail),
        ("cache", cfg.cache_path, True),
        ("windows", f"{len(cfg.windows)} → {[w.name for w in cfg.windows]}", len(cfg.windows) > 0),
    ]
    out = [colors.violet(f"{colors.M_ORACLE} oracle doctor", color)]
    ok = 0
    for name, detail, good in rows:
        ok += 1 if good else 0
        out.append(f"  {colors.ok_badge(good, color)} {name:<8} — {detail}")
    bad = len(rows) - ok
    out.append(colors.dim(f"  {ok} ok · {bad} need attention", color))
    return out
```

and the dispatch, `main.py:75-78`:

```python
    if args.cmd == "doctor":
        for line in _doctor_lines(cfg, args.config, colors.color_enabled()):
            print(line)
        return 0
```

- After Plan 001, `Config` has an `issues: list[str]` field: one sentence per tolerated config problem; a *missing* config file produces no issue (built-in preset is a supported mode).
- Sources expose `scan(files_state, now, window) -> (files_state, events)` where `events` is a sorted list of `(epoch_seconds, tokens)` — see `token_oracle/sources/base.py` (registry: `get_source(name, opts)`, `available()`) and `token_oracle/sources/claude_code.py:53` / `token_oracle/sources/generic.py:16`. A scan with `files_state={}` is a full, read-only parse.
- `token_oracle/core/profile.py:8`: `HIST_SECS = 63 * 24 * 3600` — the scan horizon the engine uses.
- `token_oracle/core/cache.py:10-20` `load_cache(path)`: returns the parsed dict when it has a `files` key, else the default `{"files": {}, "lastAggregate": 0, "profile": []}` — including for corrupt JSON (silent).
- `token_oracle/core/timeutil.py:38-49` `fmt_dur(secs)`: compact durations like `59s`, `12m`, `1h05m` — use it for ages.
- Existing doctor tests, `tests/test_cli.py:41-74`: `test_doctor_exit_zero`, `test_doctor_footer_and_badges`, `test_doctor_flags_bad_source` (the last calls `_doctor_lines(cfg, cfg_path, color=False)` directly — its call site must be updated when the signature changes).
- The `_cfg()` helper at `tests/test_cli.py:6-20` builds a tmp config using the `generic` source with an `events_path` feed file — reuse it for probe tests.

Conventions: stdlib only (no new deps); flat pytest functions with `tmp_path`; keep the badge-row output style (`🔮` header, `✓`/`✗`, `—` separator, `N ok · M need attention` footer) — `tests/test_cli.py:56-63` asserts on those markers; ruff line-length 100.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass |
| One file | `python -m pytest tests/test_cli.py -q` | all pass |
| Lint | `ruff check token_oracle/ && ruff format --check token_oracle/` | exit 0 |
| Types | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |
| Manual | `NO_COLOR=1 oracle doctor` | new row set, exit code 0/1 matches badge column |

## Scope

**In scope** (the only files you should modify):
- `token_oracle/cli/main.py`
- `tests/test_cli.py`
- `AGENTS.md` (re-capture the doctor expected-output blocks — Steps 3 and 4 of the runbook)

**Out of scope** (do NOT touch):
- `token_oracle/core/config.py` — Plan 001 owns it; you only *consume* `cfg.issues`.
- `token_oracle/core/engine.py`, `cache.py` write path — doctor must stay read-only: never write the cache, never call `save_cache`.
- `token_oracle/sources/*` — probe uses the existing `scan()` contract as-is.
- README.md — its one-line doctor description stays accurate.

## Git workflow

- Branch: `advisor/003-doctor-real-checks`.
- Conventional commit, e.g.: `feat(doctor): config provenance, source data probe, cache health, exit code`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Extend `_doctor_lines` with real checks

Change the signature to `_doctor_lines(cfg, config_path, color, now)` and build these rows (keep the existing render loop and footer):

1. **config** — detail = resolved path. Suffixes and status:
   - file exists and `cfg.issues` has no entries → `✓`, detail = path.
   - file does not exist → `✓`, detail = `<path> (missing — using built-in max20 preset)`.
   - `cfg.issues` non-empty → `✗`, detail = `<path> (<n> issue(s) — see below)`.
   Use `os.path.exists(os.path.expanduser(config_path or default_config_path()))`.
2. **source** — unchanged: `f"{cfg.source} (available: {', '.join(avail)})"`, good = `cfg.source in avail`.
3. **data** (new) — probe the source read-only:
   ```python
   try:
       src = get_source(cfg.source, cfg.source_opts)
       files, events = src.scan({}, now, HIST_SECS)
       if events:
           age = fmt_dur(now - events[-1][0])
           row = ("data", f"{len(files)} files, {len(events)} events, last {age} ago", True)
       else:
           row = ("data", "no events found in the last 9 weeks — check source settings", False)
   except Exception as e:
       row = ("data", f"source probe failed: {e!r}", False)
   ```
   Imports needed in `main.py`: `get_source` from `..sources.base`, `HIST_SECS` from `..core.profile`, `fmt_dur` from `..core.timeutil`. Note for `generic`: `files` is the passed-through `files_state` (`{}`), so the file count will read `0 files` — acceptable; the event count is the signal.
4. **cache** — read-only health: if the cache file does not exist → `✓`, `<path> (will be created on first forecast)`. If it exists and `json.load` yields a dict with a `"files"` key → `✓`, `<path> (updated <fmt_dur(now - lastAggregate)> ago)`. If it exists but is unreadable/corrupt → `✗`, `<path> (corrupt — will be rebuilt on next forecast)`. Do NOT call `load_cache` for this (it masks corruption); do a local `try: json.load(open(...))` check.
5. **windows** — unchanged.
6. **issues** (new, only when `cfg.issues` is non-empty) — one `✗` row per issue, name column `issue`, detail = the issue string from Plan 001.

**Verify**: `python -m pytest tests/test_cli.py -q` → the two direct-call tests fail (signature) — expected; fix call sites in Step 3.

### Step 2: Wire exit code and `now` through `main()`

Replace the doctor branch:

```python
    if args.cmd == "doctor":
        lines, bad = _doctor_lines(cfg, args.config, colors.color_enabled(), now)
        for line in lines:
            print(line)
        return 0 if bad == 0 else 1
```

i.e. `_doctor_lines` now returns `(lines, bad_count)`. `now` already exists in `main()` (`_now(args)` — the hidden `--now` flag makes probe ages deterministic in tests).

**Verify**: `NO_COLOR=1 oracle doctor; echo "exit=$?"` → prints the new rows; exit matches the badge column (0 when all ✓).

### Step 3: Update and extend tests

Fix the changed call sites and add coverage (see Test plan).

**Verify**: `python -m pytest tests/test_cli.py -q` → all pass.

### Step 4: Re-capture AGENTS.md doctor blocks

AGENTS.md Steps 3 and 4 embed expected `oracle doctor` output. Run `NO_COLOR=1 oracle doctor`, replace both blocks with the real new output (home dir genericized to `/home/<user>`), and update the surrounding prose to mention the `data` row (e.g. "the `data` row must show a non-zero event count if Claude Code has been used recently; `no events found` with ✗ is expected on a fresh machine"). Update the bottom checklist bullet for doctor accordingly.

**Verify**: `grep -n "data" AGENTS.md` → at least one match inside the Step 3 expected-output block.

### Step 5: Full gates

**Verify**: `python -m pytest -q` all pass; `ruff check token_oracle/ && ruff format --check token_oracle/` exit 0; `mypy token_oracle/ --ignore-missing-imports` exit 0.

## Test plan

In `tests/test_cli.py`, following the existing `_cfg()` + `main([...])` pattern:

1. Update `test_doctor_flags_bad_source` — new signature/return: `lines, bad = _doctor_lines(cfg, cfg_path, color=False, now=100000.0)`; assert `bad >= 1` and `"✗"` in the joined output.
2. Update `test_doctor_exit_zero` — the `_cfg` fixture writes an empty feed (`[]`), which now makes the `data` row fail → doctor exits 1. Rename to `test_doctor_exit_one_when_no_events` asserting `main([...]) == 1`, and add `test_doctor_exit_zero_with_events` using a feed containing one recent event (e.g. `[[now - 100.0, 50]]`) → exit 0.
3. `test_doctor_data_row_counts_events` — feed with two events; assert `"2 events"` in output and `"last"` age text present.
4. `test_doctor_reports_config_issues` — write a config with one invalid window entry (e.g. missing `name`, per Plan 001); assert an `issue` row appears with ✗ and exit code is 1.
5. `test_doctor_missing_config_is_ok` — point `--config` at a nonexistent path; assert `"missing — using built-in max20 preset"` in output; with a valid events feed impossible here (no config → claude_code source scans the real home dir!) — so instead assert only the config row text via `_doctor_lines` called directly with `load_config(<missing path>)`. **Do not** let a test run `claude_code` scan against the real `~/.claude` — always go through `_cfg()`-style configs with the `generic` source, or call `_doctor_lines` directly.
6. `test_doctor_corrupt_cache_flagged` — pre-write garbage (`"{ not json"`) at the configured `cache_path`; assert `"corrupt"` in output and exit 1.
7. Keep `test_doctor_footer_and_badges` passing unchanged (footer format is preserved).

Verification: `python -m pytest tests/test_cli.py -q` → all pass.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `python -m pytest -q` exits 0.
- [ ] `NO_COLOR=1 oracle doctor --config /nonexistent.json --now 100000; test $? -le 1` — runs without traceback (exit 0 or 1, never a crash).
- [ ] Output of the above contains a `data` row and a `config` row mentioning the preset fallback.
- [ ] `ruff check token_oracle/`, `ruff format --check token_oracle/`, `mypy token_oracle/ --ignore-missing-imports` all exit 0.
- [ ] Doctor never writes: `oracle doctor` on a fresh `--config` leaves no new cache file behind (check with a tmp `cache_path` config: file absent after run).
- [ ] `git status --short` → only in-scope files (plus `plans/README.md`).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report back (do not improvise) if:

- `Config` has no `issues` field — Plan 001 has not landed; this plan depends on it.
- `_doctor_lines` in live code differs from the excerpt beyond Plan 001/002 changes.
- The probe (`scan({}, now, HIST_SECS)`) takes more than ~10 seconds against your local `~/.claude/projects` when you manually run `oracle doctor` — report the timing; the full-reparse probe may need a budget cap, which is a design change beyond this plan.
- You find yourself wanting to modify `sources/*.py` to make probing easier — that is a contract change; report instead.

## Maintenance notes

- The `data` probe intentionally bypasses the cache (fresh `files_state={}`) so doctor reflects reality even when the cache is corrupt — that makes doctor O(full parse); fine for a diagnostic run rarely, worth noting if anyone puts doctor in a loop.
- Plan 013 (entry-point source discovery) extends `available()`/`get_source` — doctor's source row picks that up automatically.
- AGENTS.md doctor blocks are now format-coupled to `_doctor_lines`; any future doctor change must re-capture them (same as this plan's Step 4).
- Reviewer: exit-code change (`doctor` could previously only return 0) is intentional and documented here; check no other subcommand's exit behavior changed.
