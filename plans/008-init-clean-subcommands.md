# Plan 008: `token-oracle init` and `token-oracle clean` — bring installer/uninstaller to pipx users

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat d2b4d32..HEAD -- token_oracle/cli/main.py token_oracle/core/config.py install.py tests/test_cli.py tests/test_install.py README.md SETUP.md AGENTS.md`
> Plans 001–007 all landed on main; excerpts below were refreshed against
> `ada32e9` (2026-07-02). If files changed after `ada32e9`, compare the
> excerpts against live code; on mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none strictly; 001 already landed (`e0d1869`+`c278ed4` on main) — dependency satisfied
- **Category**: dx
- **Planned at**: commit `d2b4d32`, 2026-07-01; excerpts refreshed at `ada32e9`, 2026-07-02

## Why this matters

The repo ships a reversible installer (`install.py`: write a starter config, non-clobbering) and uninstaller (`uninstall.py`: remove config/cache/snapshot), both tested. But they live at the repo root, outside the wheel (`pyproject.toml` packages only `token_oracle/`), so users on the **recommended** install path (`pipx install token-oracle`) can never run them — SETUP.md documents the JSON format for hand-writing config, and AGENTS.md Step 4 teaches a `mkdir -p` + heredoc. Exposing the same logic as `token-oracle init` and `token-oracle clean` gives every installed user a one-command setup and a clean uninstall story, using code that already exists.

## Current state

- `install.py` (repo root, 30 lines) — the logic to move. Excerpt `install.py:10-19`:

```python
def write_default_config(path=None, preset="max20", force=False) -> str:
    path = os.path.expanduser(path or default_config_path())
    if os.path.exists(path) and not force:
        return path
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(PRESETS[preset], fh, indent=2)
    return path
```

  It imports `PRESETS, default_config_path` from `token_oracle.core.config`.

- `uninstall.py` (repo root, 37 lines) — removes `default_config_path()`, `default_cache_path()`, `default_snapshot_path()` via `os.remove` in try/except. Stays as a standalone script; `clean` reimplements its 6 lines in the CLI (cheaper than sharing).
- `token_oracle/core/config.py` — has `PRESETS` (line 12), `default_config_path()` (line 37), `default_cache_path()` (line 41). Receiving module for `write_default_config`.
- `token_oracle/cli/main.py` — argparse wiring at lines 98-110 (Plan 003's doctor rework added `_doctor_lines` above `main`; the wiring itself is unchanged):

```python
def main(argv=None):
    parser = argparse.ArgumentParser(prog="token-oracle")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("forecast", "snapshot", "statusline", "tmux", "doctor", "dash"):
        sp = sub.add_parser(name)
        _add_common(sp)
        if name == "forecast":
            sp.add_argument("--json", action="store_true")
        if name == "snapshot":
            sp.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    now = _now(args)
```

  `_add_common` adds `--config` and hidden `--now`. `default_snapshot_path` lives in `token_oracle/snapshot/writer.py:25-27`.

- `tests/test_install.py` — imports `from install import write_default_config` and `from uninstall import remove_config`; 3 tests. Must keep passing **unchanged** (delegation preserves the import surface).
- `tests/test_cli.py` — `_cfg()` helper + `main([...])` pattern for CLI tests.
- Docs that list subcommands: `README.md` "Parts & options" table + CLI reference block (lines ~47-73); `SETUP.md` "## Configuration" section (line 68 — documents hand-writing the JSON); `AGENTS.md` Step 4 (line 70) writes config via `mkdir -p` + heredoc.

Conventions: stdlib only; flat pytest functions; conventional commits; ruff line-length 100. `feat:` commit → release-please bumps the minor version — correct for a new user-facing command.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass |
| Lint | `ruff check token_oracle/ && ruff format --check token_oracle/` | exit 0 |
| Types | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |
| Manual | `token-oracle init --config /tmp/to-test/config.json` | prints the path; file exists |

## Scope

**In scope** (the only files you should modify):
- `token_oracle/core/config.py` (add `write_default_config`)
- `token_oracle/cli/main.py` (two subcommands)
- `install.py` (delegate to the moved function)
- `tests/test_cli.py` (new tests)
- `README.md`, `SETUP.md`, `AGENTS.md` (document the commands)

**Out of scope** (do NOT touch):
- `uninstall.py` and `tests/test_install.py` — keep working as-is; do not refactor them.
- `pyproject.toml` — no new entry points; `init`/`clean` are subcommands.
- Removing `install.py`/`uninstall.py` — they stay for repo-checkout users; deprecating them is a maintainer decision, not yours.

## Git workflow

- Branch: `advisor/008-init-clean-subcommands`.
- Conventional commit, e.g.: `feat(cli): init and clean subcommands (config bootstrap + user-data removal)`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Move `write_default_config` into `core/config.py`

Copy the function (verbatim behavior) into `token_oracle/core/config.py` below `load_config`, using the module's existing `json`/`os` imports and local `PRESETS`/`default_config_path`. Then reduce `install.py` to a delegating import:

```python
from token_oracle.core.config import write_default_config  # noqa: F401  (re-export for scripts/tests)
```

replacing its local definition; keep `install.py`'s `main()` working unchanged.

**Verify**: `python -m pytest tests/test_install.py -q` → 3 pass (imports still resolve).

### Step 2: Add the `init` subcommand

In `main.py`'s parser loop, extend the tuple to include `"init"` and `"clean"`, and add their flags:

```python
        if name == "init":
            sp.add_argument("--preset", default="max20", choices=sorted(PRESETS))
            sp.add_argument("--force", action="store_true")
        if name == "clean":
            sp.add_argument("--yes", action="store_true")
```

(import `PRESETS` alongside the existing config imports). Dispatch, before the `forecast` branch — note `init` must not require an existing valid config, and `--config` doubles as the target path:

```python
    if args.cmd == "init":
        target = os.path.expanduser(args.config or default_config_path())
        existed = os.path.exists(target)
        path = write_default_config(target, preset=args.preset, force=args.force)
        if existed and not args.force:
            print(f"{path} exists — pass --force to overwrite")
        else:
            print(path)
        return 0
```

`main.py` already imports `os` (line 5). Placement constraint: `cfg = load_config(args.config)` at line 109 runs before dispatch and is harmless for `init` (Plan 001 landed — it never raises); leave it.

**Verify**: `token-oracle init --config /tmp/to-plan8/config.json && cat /tmp/to-plan8/config.json | python -c "import json,sys; json.load(sys.stdin)"` → prints path; JSON parses. Re-run without `--force` → prints the `exists — pass --force` line, exit 0.

### Step 3: Add the `clean` subcommand

```python
    if args.cmd == "clean":
        targets = [
            os.path.expanduser(args.config or default_config_path()),
            cfg.cache_path,
            default_snapshot_path(),
        ]
        if not args.yes:
            print("would remove:")
            for t in targets:
                print(f"  {t}")
            print("re-run with --yes to delete")
            return 1
        for t in targets:
            try:
                os.remove(t)
                print(f"removed {t}")
            except OSError:
                pass
        return 0
```

Import `default_snapshot_path` from `..snapshot.writer`. Deletion is guarded: without `--yes` it only lists and exits 1 (scripts can't delete by accident).

**Verify**: `token-oracle clean --config /tmp/to-plan8/config.json` → lists 3 paths, exit 1, file still present. `token-oracle clean --config /tmp/to-plan8/config.json --yes` → `removed /tmp/to-plan8/config.json`, exit 0, file gone.

### Step 4: Document

- `README.md`: add `init` and `clean` rows to the "Parts & options" table (`init` — `--preset`, `--force`: "Write a starter config (non-clobbering)"; `clean` — `--yes`: "Remove config, cache, and snapshot files") and to the CLI reference block, including the `{forecast,snapshot,…}` choices line.
- `SETUP.md` Configuration section: lead with `token-oracle init` as the way to create the file; keep the JSON format documentation.
- `AGENTS.md` Step 4: replace the `mkdir -p` + heredoc with `token-oracle init` followed by editing the file if customization is needed (keep the JSON block as the reference for what gets written).

**Verify**: `grep -n "init" README.md SETUP.md AGENTS.md | grep -iv "initial" | head` → hits in all three files.

### Step 5: Tests + full gates

Write the tests below.

**Verify**: `python -m pytest -q` all pass; `ruff check token_oracle/ && ruff format --check token_oracle/` exit 0; `mypy token_oracle/ --ignore-missing-imports` exit 0.

## Test plan

In `tests/test_cli.py` (pattern: build paths under `tmp_path`, call `main([...])`, assert exit code + filesystem + `capsys`):

1. `test_init_writes_config(tmp_path, capsys)` — `main(["init", "--config", str(tmp_path/"c.json")]) == 0`; file exists; JSON has `windows` with names `{"5h","weekly"}`; stdout contains the path.
2. `test_init_no_clobber(tmp_path, capsys)` — pre-write `{"source":"custom"}`; run init → exit 0, content unchanged, stdout mentions `--force`; run with `--force` → content replaced (has `windows`).
3. `test_clean_requires_yes(tmp_path, capsys, monkeypatch)` — **first** `monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))` so cache/snapshot resolve under tmp; create a config via init; `main(["clean", "--config", ...]) == 1`; file still exists; stdout lists it.
4. `test_clean_yes_removes(tmp_path, monkeypatch)` — **first** `monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))`; init a config; plant dummy `<tmp>/token-oracle/cache.json` + `forecast.json` (`os.makedirs(..., exist_ok=True)`); `main(["clean", "--config", ..., "--yes"]) == 0`; assert config + cache + snapshot all gone; re-run `clean --yes` → still 0 (missing files silently skipped, no exception).

> **CRITICAL — tests must be hermetic.** `clean` resolves `cfg.cache_path`/`default_snapshot_path()` to the **real** `~/.local/share/token-oracle/{cache,forecast}.json` when the config sets no `cache_path` (the max20 preset doesn't). Both honor `$XDG_DATA_HOME`, read at call time. Without the `monkeypatch.setenv` above, `test_clean_yes_removes` DELETES real user data on any dev machine with token-oracle history. `tmp_path` alone only isolates the config file. This was caught and fixed in the 2026-07-08 execution.

Structural pattern: `test_snapshot_writes_file` in the same file. Verification: `python -m pytest tests/test_cli.py -q` → all pass (4 new).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `python -m pytest -q` exits 0, including 4 new CLI tests and the unchanged `tests/test_install.py`.
- [ ] `token-oracle init --config /tmp/to-done8/c.json` → exit 0, valid JSON written; `token-oracle clean --config /tmp/to-done8/c.json --yes` → exit 0, file removed.
- [ ] `grep -n "def write_default_config" token_oracle/core/config.py install.py` → definition in `config.py` only; `install.py` has the re-export import.
- [ ] `ruff check token_oracle/`, `ruff format --check token_oracle/`, `mypy token_oracle/ --ignore-missing-imports` all exit 0.
- [ ] README CLI reference lists `init` and `clean`.
- [ ] `git status --short` → only in-scope files (plus `plans/README.md`).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report back (do not improvise) if:

- `main.py`'s parser loop no longer matches the excerpt (refreshed at `ada32e9`).
- `load_config` can raise on a broken existing config (it should not — Plan 001 landed at `e0d1869`; if you observe a raise, that's a regression) — report instead of adding a workaround.
- `tests/test_install.py` fails after Step 1 — the delegation broke the script import surface; do not modify that test file to make it pass.
- You're tempted to also delete/deprecate `install.py`/`uninstall.py` — maintainer decision, out of scope.

## Maintenance notes

- `clean` removes the *configured* `cfg.cache_path` but the *default* snapshot path — if a `snapshot_path` config field is ever added (Plan 015 discussion), extend `clean` to honor it.
- Reviewer: check `init` exit-code semantics (0 on no-clobber — idempotent bootstrap) and that `clean` without `--yes` cannot delete anything.
- Follow-up deliberately deferred: a `--preset` beyond `max20` (there is only one preset today; the flag is future-proofing that costs one line).
