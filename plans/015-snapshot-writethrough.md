# Plan 015: Opt-in snapshot write-through (kill the 5-minute cron)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat d2b4d32..HEAD -- token_oracle/core/config.py token_oracle/cli/main.py token_oracle/snapshot/writer.py tests/test_cli.py SETUP.md ADAPTERS.md`
> Plans 001/003/004 landed (changes reflected in the excerpts below, refreshed
> at `ada32e9`, 2026-07-02). Plan 008 is still TODO and also edits `main.py`/
> `config.py` — if it has landed since, expect `init`/`clean` branches in
> `main.py` and re-verify excerpts. Confirm specifically: `Config` has an
> `issues` field (001 landed), `write_snapshot` returns `None` on failure
> (004 landed). If either is absent, STOP — the dependencies regressed.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/004-atomic-write-hardening.md — DONE (merged at `c0a91bf`); plans/001 — DONE (`e0d1869`+`c278ed4`). All dependencies satisfied.
- **Category**: direction
- **Planned at**: commit `d2b4d32`, 2026-07-01; excerpts refreshed at `ada32e9`, 2026-07-02
- **Executed**: 2026-07-14 — DONE (quality-pass follow-on). `snapshot_writethrough` on Config; forecast/statusline/tmux opportunistic write; SETUP+ADAPTERS docs; 4 tests.

## Why this matters

The snapshot file (`forecast.json`) is the integration surface for external consumers — agentic-sage reads it by config. But it only updates when someone runs `oracle snapshot`, so both ADAPTERS.md and SETUP.md instruct users to build a cron job / shell hook to keep it fresh. Meanwhile `oracle statusline` and `oracle tmux` already run on tight intervals in exactly the deployments that want a fresh snapshot, computing the identical forecast list and then throwing it away. Write-through — statusline/tmux/forecast opportunistically writing the snapshot they just computed — absorbs the user's cron into one config flag. Opt-in (default off) preserves current behavior exactly for everyone who hasn't asked for it.

## Current state

- `token_oracle/core/config.py:23-29` — `Config` dataclass, current at `ada32e9`:

```python
@dataclass
class Config:
    source: str = "claude_code"
    source_opts: dict = field(default_factory=dict)
    cache_path: str = ""
    windows: list[Window] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
```

  `load_config` builds it from `raw` (preset merged with the user's JSON) — new scalar fields follow the `raw.get(...)` pattern visible in the constructor call at `config.py:101-107`.

- `token_oracle/cli/main.py:112-132` — the three read-only render branches, verified at `ada32e9` (shape unchanged by Plans 003/004; Plan 008, if landed, adds `init`/`clean` branches after them — match by shape):

```python
    if args.cmd == "forecast":
        fs = run_forecast(now, cfg)
        if args.json:
            print(json.dumps(build_snapshot(fs, now)))
        else:
            print(sl.render(fs) or "idle")
        return 0
    ...
    if args.cmd == "statusline":
        print(sl.render(run_forecast(now, cfg)))
        return 0
    if args.cmd == "tmux":
        print(tx.render(run_forecast(now, cfg)))
        return 0
```

- `token_oracle/snapshot/writer.py` — `write_snapshot(forecasts, now, path=None)` (lines 30-49); Plan 004 landed: it returns the path on success, `None` on failure, atomically via `tempfile.mkstemp` unique temp. `default_snapshot_path()` honors `$XDG_DATA_HOME` (`writer.py:25-27`) — this is what makes the write-through testable with `monkeypatch.setenv("XDG_DATA_HOME", ...)`.
- Docs teaching the cron workaround: `ADAPTERS.md` "Snapshot staleness" section (~lines 200-211: "Keep it fresh with a cron job, a shell alias, or a tmux `status-interval` hook", plus the `*/5 * * * *` example); `SETUP.md` agentic-sage section (~line 173: "keep the snapshot fresh with a periodic `oracle snapshot` call").
- SETUP.md "Fields" table (header at line 97) lists config fields — the new flag needs a row.
- Test pattern: `tests/test_cli.py` `_cfg()` helper writes a config dict to a tmp file; extend the dict per-test via a parameter or a local variant.

Conventions: stdlib only; flat pytest functions with `tmp_path`/`monkeypatch`; conventional commits (`feat:` — minor bump, user-facing); ruff line-length 100.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass |
| Focused | `python -m pytest tests/test_cli.py tests/test_config.py -q` | all pass |
| Lint/type | `ruff check token_oracle/ && ruff format --check token_oracle/ && mypy token_oracle/ --ignore-missing-imports` | exit 0 |
| Manual | config with `"snapshot_writethrough": true` + `XDG_DATA_HOME=/tmp/to15 oracle statusline` | `/tmp/to15/token-oracle/forecast.json` exists afterwards |

## Scope

**In scope** (the only files you should modify):
- `token_oracle/core/config.py` (one field + one `raw.get`)
- `token_oracle/cli/main.py` (write-through calls)
- `tests/test_cli.py`, `tests/test_config.py`
- `SETUP.md`, `ADAPTERS.md` (document the flag; soften the cron advice)

**Out of scope** (do NOT touch):
- `token_oracle/snapshot/writer.py` — Plan 004's contract is consumed as-is.
- `token_oracle/core/engine.py` — write-through is a CLI-layer concern; the library `forecast()` must stay pure/read-only-except-cache.
- A `--watch` daemon mode for `oracle snapshot` — considered and rejected for now (a long-running process brings lifecycle problems the flag avoids); note it as future work only.
- Making write-through default-on — maintainer decision for a later release.
- The `dash` loop — refreshing every 2 s would write 30×/min for marginal benefit; leave it read-only.

## Git workflow

- Branch: `advisor/015-snapshot-writethrough`.
- Conventional commit, e.g.: `feat(cli): opt-in snapshot write-through from forecast/statusline/tmux`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add the config flag

In `config.py`: add `snapshot_writethrough: bool = False` to `Config`, and in `load_config`'s constructor call add `snapshot_writethrough=bool(raw.get("snapshot_writethrough", False))`.

**Verify**: `python -c "from token_oracle.core.config import Config; assert Config().snapshot_writethrough is False"` → exit 0.

### Step 2: Wire the three render branches

In `main.py`, after computing `fs` in the `forecast` branch and inline in `statusline`/`tmux` (bind the forecast list to a local first — the current one-liners must become two lines):

```python
    if args.cmd == "statusline":
        fs = run_forecast(now, cfg)
        if cfg.snapshot_writethrough:
            write_snapshot(fs, now)   # best-effort: None return deliberately ignored
        print(sl.render(fs))
        return 0
```

Same pattern for `tmux` and `forecast` (both `--json` and plain paths — write once, before the print). `write_snapshot` is already imported in `main.py`. The explicit `snapshot` subcommand keeps its strict exit-code behavior from Plan 004 — only the *opportunistic* writes ignore failure (a broken data dir must not take down the status bar; the strict path exists for anyone who wants the error).

**Verify**: manual check from the commands table — config with the flag true, `XDG_DATA_HOME` pointed at a tmp dir, run `oracle statusline`, snapshot file exists and parses (`python -c "import json; json.load(open('/tmp/to15/token-oracle/forecast.json'))"`).

### Step 3: Tests

- `tests/test_config.py`: `test_snapshot_writethrough_flag_parsed` — config JSON with `"snapshot_writethrough": true` → `cfg.snapshot_writethrough is True`; absent → `False`.
- `tests/test_cli.py` (extend `_cfg()` with an optional `extra: dict` merged into the config JSON, defaulting to `{}` so existing tests are untouched):
  - `test_statusline_writethrough_writes_snapshot(tmp_path, monkeypatch, capsys)` — `monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))`; config with flag on + one event; run `main(["statusline", ...])` → exit 0, and `tmp_path/"data"/"token-oracle"/"forecast.json"` exists with `schema == 1` and one window.
  - `test_statusline_no_writethrough_by_default(tmp_path, monkeypatch)` — same setup, flag absent → snapshot file does NOT exist.
  - `test_forecast_json_writethrough(tmp_path, monkeypatch, capsys)` — flag on, `forecast --json` → stdout is the JSON snapshot AND the file exists (both artifacts from one run).

**Verify**: `python -m pytest tests/test_cli.py tests/test_config.py -q` → all pass (4 new).

### Step 4: Document

- `SETUP.md`: add a `snapshot_writethrough` row to the Fields table (`bool`, default `false`, "when true, `forecast`/`statusline`/`tmux` also refresh the snapshot file"), and in the agentic-sage section offer it as the primary option, cron as the fallback.
- `ADAPTERS.md` "Snapshot staleness": lead with the flag, keep the cron example as the alternative for setups that never run the render commands.

**Verify**: `grep -n "snapshot_writethrough" SETUP.md ADAPTERS.md` → ≥ 2 matches.

### Step 5: Full gates

**Verify**: `python -m pytest -q` all pass; `ruff check token_oracle/ && ruff format --check token_oracle/` exit 0; `mypy token_oracle/ --ignore-missing-imports` exit 0.

## Test plan

The four tests in Step 3. Structural patterns: `tests/test_config.py::test_paths_honor_xdg` (monkeypatched XDG), `tests/test_cli.py::test_statusline_runs` (CLI invocation shape). No test may write outside `tmp_path`-derived locations — the XDG monkeypatch is what guarantees that.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `python -m pytest -q` exits 0 with 4 new tests.
- [ ] Default behavior unchanged: with no flag, `oracle statusline` writes no snapshot (pinned by test).
- [ ] With the flag, `statusline`/`tmux`/`forecast` produce a fresh, schema-valid snapshot (pinned by tests + manual check).
- [ ] `grep -n "snapshot_writethrough" token_oracle/core/config.py token_oracle/cli/main.py SETUP.md ADAPTERS.md` → ≥ 4 matches across the four files.
- [ ] `ruff check token_oracle/`, `ruff format --check token_oracle/`, `mypy token_oracle/ --ignore-missing-imports` all exit 0.
- [ ] `git status --short` → only in-scope files (plus `plans/README.md`).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report back (do not improvise) if:

- `write_snapshot` still returns the path unconditionally / uses the fixed `.tmp` name — Plan 004 has not landed; this plan must not proceed without it.
- `Config` lacks the `issues` field — Plan 001 hasn't landed; coordinate ordering (the dataclass edit would conflict).
- You're tempted to add the write-through inside `engine.forecast()` — that breaks the library contract (ADAPTERS.md Option B documents `forecast()` as side-effect-free apart from the cache); CLI layer only.

## Maintenance notes

- If Plan 012's confidence work later changes snapshot contents, write-through needs no change (it serializes whatever `Forecast` carries).
- Future candidates deliberately deferred: default-on after a release of soak time; a `--watch` daemon; honoring a configurable `snapshot_path` (today the default path is the integration contract — Plan 008's `clean` also assumes it).
- Reviewer: confirm the strict/opportunistic split — `oracle snapshot` still exits 1 on failure, render commands never do because of a snapshot problem.
