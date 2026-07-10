# Plan 004: Unique-temp atomic writes for cache/snapshot; snapshot failures exit non-zero

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat d2b4d32..HEAD -- token_oracle/core/cache.py token_oracle/snapshot/writer.py token_oracle/cli/main.py tests/test_cache.py tests/test_snapshot.py tests/test_cli.py ADAPTERS.md`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch (beyond Plans 001–003's declared changes to `main.py`/`test_cli.py`),
> treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none (merge-order note: Plans 001/003 also touch `main.py`; rebase is trivial)
- **Category**: bug
- **Planned at**: commit `d2b4d32`, 2026-07-01

## Why this matters

Both persistent writers (cache and snapshot) implement "atomic write" as: write to `<path>.tmp`, then `os.replace`. The temp path is **fixed and shared**, and this tool's advertised deployment is concurrent invocation — a tmux `status-right` running `oracle tmux` on an interval plus an editor statusline running `oracle statusline`, both hitting the same cache. Two concurrent writers open the same `.tmp` file, truncate and interleave each other's bytes, and one of them `os.replace`s a corrupted file into place. Corrupt cache is self-healing (loader falls back) but silently triggers a full 9-week transcript rescan — a visible multi-second statusline stall. A corrupt snapshot breaks external consumers (agentic-sage) outright. Second defect in the same file: `write_snapshot` swallows `OSError` and still returns the path, so `oracle snapshot` prints a path that was never written and exits 0 — a cron'd `oracle snapshot >/dev/null 2>&1` (the documented setup) hides the failure forever.

## Current state

- `token_oracle/core/cache.py` — cache persistence. Excerpt `cache.py:23-33` at `d2b4d32`:

```python
def save_cache(cache, path):
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cache, fh)
        os.replace(tmp, path)
    except OSError:
        pass
```

- `token_oracle/snapshot/writer.py` — snapshot persistence. Excerpt `writer.py:28-40`:

```python
def write_snapshot(forecasts, now, path=None):
    path = os.path.expanduser(path or default_snapshot_path())
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(build_snapshot(forecasts, now), fh)
        os.replace(tmp, path)
    except OSError:
        pass
    return path
```

- `token_oracle/cli/main.py:64-68` — the snapshot subcommand prints the returned path unconditionally and returns 0:

```python
    if args.cmd == "snapshot":
        fs = run_forecast(now, cfg)
        path = write_snapshot(fs, now, args.out)
        print(path)
        return 0
```

- `main.py` currently imports `argparse`, `json`, `time` — no `sys`.
- Design constraints from module docstrings (honor them): `cache.py` — "Atomic writes. Never raises to the caller."; `writer.py` — "Atomic write, never raises." For the snapshot writer, "never raises" stays true — failure is signalled by returning `None`, not by an exception.
- Existing tests: `tests/test_cache.py:11-16` (`test_save_then_load_roundtrip` — parent dir auto-created), `tests/test_snapshot.py:34-38` (`test_write_snapshot_roundtrip`), `tests/test_cli.py:32-38` (`test_snapshot_writes_file`).
- `ADAPTERS.md` "Snapshot staleness" section (lines ~200-211) documents the cron pattern — one sentence about the new exit code belongs there.

Conventions: stdlib only; flat pytest functions with `tmp_path`; ruff line-length 100; conventional commits.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass |
| Focused | `python -m pytest tests/test_cache.py tests/test_snapshot.py tests/test_cli.py -q` | all pass |
| Lint | `ruff check token_oracle/ && ruff format --check token_oracle/` | exit 0 |
| Types | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |

## Scope

**In scope** (the only files you should modify):
- `token_oracle/core/cache.py`
- `token_oracle/snapshot/writer.py`
- `token_oracle/cli/main.py` (snapshot branch + `import sys` only)
- `tests/test_cache.py`, `tests/test_snapshot.py`, `tests/test_cli.py`
- `ADAPTERS.md` (one sentence, Step 4)

**Out of scope** (do NOT touch):
- `token_oracle/core/engine.py` — the 30-second `lastAggregate` check-then-act race (two processes both rescanning) is benign duplicate work, deliberately not addressed here.
- File locking (`fcntl` etc.) — rejected: unique temp files + `os.replace` fully solve write-write corruption; locks add platform-specific complexity for no additional correctness.
- fsync/durability — crash-consistency is not a goal for a regenerable cache.

## Git workflow

- Branch: `advisor/004-atomic-write-hardening`.
- Conventional commit, e.g.: `fix(io): unique temp files for atomic writes; snapshot failure exits non-zero`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Unique temp file in `save_cache`

Rewrite `save_cache` to use `tempfile.mkstemp` in the destination directory (same filesystem → `os.replace` stays atomic), cleaning up the temp file on failure:

```python
import json
import os
import tempfile

def save_cache(cache, path):
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d or ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(cache, fh)
            os.replace(tmp, path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError:
        pass
```

Keep the module docstring's "Never raises to the caller" true — the outer `except OSError: pass` stays.

**Verify**: `python -m pytest tests/test_cache.py -q` → all pass.

### Step 2: Same pattern in `write_snapshot`, returning `None` on failure

Apply the identical mkstemp pattern in `writer.py`, and change the contract: return `path` on success, `None` on failure:

```python
def write_snapshot(forecasts, now, path=None):
    path = os.path.expanduser(path or default_snapshot_path())
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d or ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(build_snapshot(forecasts, now), fh)
            os.replace(tmp, path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError:
        return None
    return path
```

Update the module docstring's last line to reflect the new contract (e.g. "Atomic write; returns the path, or None when the write failed.").

**Verify**: `python -m pytest tests/test_snapshot.py -q` → `test_write_snapshot_roundtrip` passes (it ignores the return value today; you will extend it in Step 5).

### Step 3: `oracle snapshot` reports failure

In `main.py`, add `import sys` to the imports and change the snapshot branch:

```python
    if args.cmd == "snapshot":
        fs = run_forecast(now, cfg)
        path = write_snapshot(fs, now, args.out)
        if path is None:
            print("snapshot: write failed", file=sys.stderr)
            return 1
        print(path)
        return 0
```

stdout contract preserved: on success, stdout is exactly the path (consumers parse it); the error goes to stderr.

**Verify**: `python -m pytest tests/test_cli.py -q` → all pass.

### Step 4: Document the exit code

In `ADAPTERS.md`, "Snapshot staleness" section, after the cron example add one line:

> `oracle snapshot` exits non-zero and prints to stderr if the file could not be written — don't discard stderr in cron if you want to notice.

**Verify**: `grep -n "exits non-zero" ADAPTERS.md` → 1 match.

### Step 5: Tests + full gates

Write the tests below, then run everything.

**Verify**: `python -m pytest -q` all pass; `ruff check token_oracle/ && ruff format --check token_oracle/` exit 0; `mypy token_oracle/ --ignore-missing-imports` exit 0.

## Test plan

- `tests/test_cache.py` (model on the existing flat style):
  - `test_save_leaves_no_tmp_files(tmp_path)` — `save_cache` then `os.listdir` the parent: exactly one file, the cache itself (no `*.tmp` leftovers).
  - `test_save_failure_is_silent_and_leaves_no_tmp(tmp_path)` — make the destination directory impossible: `p = tmp_path/"blocker"/"cache.json"` after `(tmp_path/"blocker").write_text("file, not a dir")` → `save_cache` returns without raising; `list(tmp_path.iterdir())` contains only `blocker`.
- `tests/test_snapshot.py`:
  - Extend `test_write_snapshot_roundtrip` to assert the return value equals the path.
  - `test_write_snapshot_returns_none_on_failure(tmp_path)` — same blocked-parent trick → returns `None`, no `*.tmp` in `tmp_path`.
- `tests/test_cli.py` (model on `test_snapshot_writes_file`):
  - `test_snapshot_exit_one_on_write_failure(tmp_path, capsys)` — `--out` pointing under a blocked parent → `main([...]) == 1`, `capsys.readouterr().out` is empty (nothing on stdout), `err` contains `write failed`.

The write-write race itself is not deterministically testable in-process; the mkstemp uniqueness property is the fix, and the no-leftover/failure tests pin the new code path. Note this in the test file only if a comment is needed — do not add a flaky concurrency test.

Verification: `python -m pytest -q` → all pass (5 new/extended tests).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -rn '+ ".tmp"' token_oracle/` → 0 matches (fixed-name temp pattern gone).
- [ ] `grep -n "mkstemp" token_oracle/core/cache.py token_oracle/snapshot/writer.py` → 2 matches.
- [ ] `python -m pytest -q` exits 0, including the new failure-path tests.
- [ ] `oracle snapshot --out /nonexistent-dir-parent-is-file/x.json` style failure exits 1 with stderr message (covered by the CLI test).
- [ ] `ruff check token_oracle/`, `ruff format --check token_oracle/`, `mypy token_oracle/ --ignore-missing-imports` all exit 0.
- [ ] `git status --short` → only in-scope files (plus `plans/README.md`).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The excerpts above don't match live code (drifted).
- Any *existing* test asserts on the old `.tmp` filename or on `write_snapshot` always returning a path in a way that contradicts the new contract beyond the extensions listed here.
- You are tempted to add file locking or fsync — out of scope by decision; report if you believe it's genuinely required.

## Maintenance notes

- Plan 015 (snapshot write-through from statusline/tmux) depends on this plan: it multiplies write frequency, so unique temps must land first, and it deliberately ignores a `None` return (best-effort write-through).
- Reviewer: confirm `mkstemp(dir=...)` targets the destination directory (same-filesystem rename), not the system tmp dir; confirm the snapshot stdout contract (path only) survived.
- Known-and-accepted: two concurrent processes may still both do the 30s re-aggregate (duplicate work, no corruption). If that ever matters, an `fcntl` advisory lock around the aggregate step is the follow-up — deliberately deferred.
