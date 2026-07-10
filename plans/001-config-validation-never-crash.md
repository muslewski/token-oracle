# Plan 001: Make config loading crash-proof and record config problems as diagnosable issues

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat d2b4d32..HEAD -- token_oracle/core/config.py token_oracle/cli/main.py tests/test_config.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `d2b4d32`, 2026-07-01
- **Executed**: 2026-07-02 — DONE, approved after 1 revision round. Branch `advisor/001-config-validation` (commits `e0d1869`, `c278ed4`) in worktree `.claude/worktrees/agent-a1eb7bfb07c6077c1`. Revision fixed a residual crash: non-string `cache_path` raised `TypeError` at `os.path.expanduser`. Merge is the operator's call.

## Why this matters

token-oracle is a status-bar tool: its CLI is invoked automatically by tmux and editor statuslines. Today, a single malformed entry in the user's `windows` config array (missing `"name"`, `"cap": "abc"`, a bad `anchor` string) makes `load_config()` raise, and because `main()` calls it before any error handling, **every** subcommand — including `doctor`, the diagnostic tool — dies with a raw Python traceback. Status bars then render stack-trace fragments. Separately, a config file that is present but unparseable is silently replaced by the built-in preset with no record of the failure, so nothing downstream can ever tell the user their config is being ignored. This plan makes `load_config()` never raise on user input and records every problem on a new `Config.issues` list that Plan 003 (doctor overhaul) will render.

## Current state

- `token_oracle/core/config.py` — config loading + `max20` preset. The bug: `_window_from_dict` is called at line 63, *outside* the `try` that guards JSON parsing.
- `token_oracle/cli/main.py` — line 54 `cfg = load_config(args.config)` runs before any subcommand dispatch, uncaught.
- `tests/test_config.py` — existing config tests (4 tests), the structural pattern to follow.

Excerpt — `token_oracle/core/config.py:44-70` as of `d2b4d32`:

```python
def _window_from_dict(d) -> Window:
    anchor = d.get("anchor")
    if isinstance(anchor, str):
        anchor = parse_ts(anchor)
    return Window(
        name=d["name"], cap=int(d["cap"]), period_secs=int(d["period_secs"]), anchor=anchor
    )


def load_config(path: str | None = None) -> "Config":
    path = path or default_config_path()
    raw: dict[str, Any] = dict(PRESETS["max20"])
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            raw.update(data)
    except (OSError, ValueError):
        pass
    windows = [_window_from_dict(w) for w in raw.get("windows", [])]
    cache_path = os.path.expanduser(raw.get("cache_path") or default_cache_path())
    return Config(
        source=raw.get("source", "claude_code"),
        source_opts=raw.get("source_opts", {}),
        cache_path=cache_path,
        windows=windows,
    )
```

Excerpt — the `Config` dataclass, `config.py:23-28`:

```python
@dataclass
class Config:
    source: str = "claude_code"
    source_opts: dict = field(default_factory=dict)
    cache_path: str = ""
    windows: list[Window] = field(default_factory=list)
```

Failure traces to confirm you understand the bug (do not need to reproduce):
- `{"windows": [{"cap": 100, "period_secs": 60}]}` → `KeyError: 'name'` at `d["name"]`.
- `{"windows": [{"name": "x", "cap": "abc", "period_secs": 60}]}` → `ValueError` at `int(d["cap"])`.
- `{"windows": [{"name": "x", "cap": 1, "period_secs": 60, "anchor": "not-a-date"}]}` → `parse_ts` returns `None`, silently converting a fixed-grid window into a rolling one (wrong semantics, no error).

Conventions that apply (match them):
- Zero runtime dependencies — stdlib only (`pyproject.toml` declares `dependencies = []`; this is a deliberate design decision).
- Modules carry a one-paragraph design-note docstring; inline comments are sparse and only state non-obvious constraints.
- Most functions are unannotated or lightly annotated; mypy runs with `--ignore-missing-imports` and is lenient. Match the file's existing annotation level.
- Tests are flat pytest functions using `tmp_path`, direct asserts, no classes/fixtures files — model after `tests/test_config.py`.
- Ruff config: `select = ["E","F","I","UP","B","W"]`, line-length 100, target py310.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass, 0 failures |
| Lint | `ruff check token_oracle/` | exit 0 |
| Format | `ruff format --check token_oracle/` | exit 0 (run `ruff format token_oracle/` to fix) |
| Types | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |

## Scope

**In scope** (the only files you should modify):
- `token_oracle/core/config.py`
- `tests/test_config.py`

**Out of scope** (do NOT touch, even though they look related):
- `token_oracle/cli/main.py` — after this plan, `load_config` never raises, so no CLI change is needed. Doctor rendering of `issues` is Plan 003.
- `token_oracle/core/engine.py` — its blanket `except Exception` stays as-is (documented "never raises" design).
- `install.py` / `uninstall.py` — untouched by this change.
- Docs (`README.md`, `SETUP.md`, …) — doc corrections are Plan 002.

## Git workflow

- Branch: `advisor/001-config-validation` (repo uses short-lived feature branches off `main`).
- Conventional commits (release-please parses them). Example from this repo's log: `fix(engine): cache events for warm replay (source-agnostic)`. Suggested: `fix(config): validate window entries, never raise on malformed config`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add an `issues` field to `Config`

In `token_oracle/core/config.py`, extend the dataclass:

```python
@dataclass
class Config:
    source: str = "claude_code"
    source_opts: dict = field(default_factory=dict)
    cache_path: str = ""
    windows: list[Window] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
```

Each entry is one human-readable sentence describing a config problem that was tolerated. Empty list = clean config.

**Verify**: `python -c "from token_oracle.core.config import Config; assert Config().issues == []"` → exits 0.

### Step 2: Validate windows entries individually; never raise

Rework `_window_from_dict` and `load_config` so that:

1. JSON parse failure on an **existing** file appends an issue like
   `config file <path> is unreadable or not valid JSON — using built-in max20 preset` and falls back to the preset (current fallback behavior, now recorded). A **missing** file is NOT an issue (running with the built-in preset is a documented, supported mode).
2. If `raw.get("windows")` is present but not a list, append
   `config "windows" must be a list — using built-in max20 preset windows` and use `PRESETS["max20"]["windows"]` instead.
3. Each window entry is validated independently. An invalid entry is **skipped** and appends `windows[<i>]: <reason> — entry skipped`. Validation rules:
   - entry must be a dict with keys `name`, `cap`, `period_secs`;
   - `cap` and `period_secs` must be `int()`-convertible with `cap > 0` and `period_secs > 0`;
   - `name` is coerced with `str()`;
   - `anchor`, when present, must be `None`, an `int`/`float` (epoch seconds, passed through), or a string that `parse_ts` can parse. A string `parse_ts` returns `None` for is a validation failure (**skip the entry** — do not silently degrade a fixed-grid window to rolling mode).
4. `load_config` must never raise for any file content. Wrap per-entry construction in `try/except (KeyError, TypeError, ValueError)` and route the message into `issues`.

Target shape (adapt freely, keep behavior exact):

```python
def _window_from_dict(d) -> Window:
    """Build one Window from a config dict. Raises ValueError on any invalid field."""
    if not isinstance(d, dict):
        raise ValueError("window entry must be an object")
    try:
        name = str(d["name"])
        cap = int(d["cap"])
        period = int(d["period_secs"])
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"missing or invalid field: {e}") from e
    if cap <= 0 or period <= 0:
        raise ValueError("cap and period_secs must be > 0")
    anchor = d.get("anchor")
    if isinstance(anchor, str):
        parsed = parse_ts(anchor)
        if parsed is None:
            raise ValueError(f"anchor {anchor!r} is not a parseable ISO 8601 timestamp")
        anchor = parsed
    elif anchor is not None and not isinstance(anchor, (int, float)):
        raise ValueError("anchor must be null, a number, or an ISO 8601 string")
    return Window(name=name, cap=cap, period_secs=period, anchor=anchor)
```

and in `load_config`, replace the single list comprehension at line 63 with a loop that appends valid windows and collects issue strings for invalid ones, then passes `issues=issues` to the returned `Config`.

Preserve existing behavior everywhere else: preset merge via `raw.update(data)`, `cache_path` expansion, `source`/`source_opts` defaults, and the existing test `test_corrupt_falls_back` (corrupt JSON → preset windows) must still pass — it now ALSO produces one issue.

**Verify**: `python -m pytest tests/test_config.py -q` → existing 4 tests pass.

### Step 3: Add regression tests

See "Test plan" below. Write them in `tests/test_config.py`.

**Verify**: `python -m pytest tests/test_config.py -q` → all pass (4 existing + 7 new).

### Step 4: Full gates

**Verify**:
- `python -m pytest -q` → all pass.
- `ruff check token_oracle/ && ruff format --check token_oracle/` → exit 0.
- `mypy token_oracle/ --ignore-missing-imports` → exit 0.

## Test plan

New tests in `tests/test_config.py`, modeled on the existing flat style there:

1. `test_window_missing_name_is_skipped_with_issue` — config `{"windows": [{"cap": 100, "period_secs": 60}]}` → `load_config` returns, `windows == []`, exactly one issue containing `windows[0]`.
2. `test_window_bad_cap_is_skipped` — `"cap": "abc"` → entry skipped, issue recorded, no exception.
3. `test_window_nonpositive_period_is_skipped` — `"period_secs": 0` → skipped with issue.
4. `test_bad_anchor_string_is_skipped_not_degraded` — `"anchor": "not-a-date"` on an otherwise valid entry → entry skipped (assert `windows == []`), issue mentions `anchor`. This is the regression test for the silent fixed-grid→rolling degradation.
5. `test_windows_not_a_list_falls_back_with_issue` — `{"windows": "5h"}` → preset windows (`{"5h","weekly"}` names), one issue.
6. `test_corrupt_json_records_issue` — reuse the `"{ broken"` content from `test_corrupt_falls_back`; assert `len(c.issues) == 1` and preset windows load.
7. `test_valid_config_has_no_issues` — the valid config from `test_loads_custom_windows_and_anchor` → `issues == []`. Also assert a **missing** file (`tmp_path / "none.json"`) yields `issues == []`.

One mixed case worth folding into test 1 or adding separately: a config with one valid and one invalid entry loads the valid window and reports exactly one issue.

Verification: `python -m pytest tests/test_config.py -q` → all pass.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `python -m pytest -q` exits 0.
- [ ] `python - <<'EOF'` exits 0 (no traceback — the original crash repro):
  ```python
  import json, tempfile, os
  from token_oracle.core.config import load_config
  d = tempfile.mkdtemp(); p = os.path.join(d, "c.json")
  json.dump({"windows": [{"cap": 100, "period_secs": 60}]}, open(p, "w"))
  c = load_config(p)
  assert c.windows == [] and len(c.issues) == 1, (c.windows, c.issues)
  EOF
  ```
- [ ] `ruff check token_oracle/`, `ruff format --check token_oracle/`, `mypy token_oracle/ --ignore-missing-imports` all exit 0.
- [ ] `git status --short` shows changes only in `token_oracle/core/config.py`, `tests/test_config.py` (plus `plans/README.md` status update).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report back (do not improvise) if:

- `config.py:44-70` no longer matches the excerpt above (drifted since `d2b4d32`).
- An existing test in `tests/test_config.py` fails in a way that requires changing its assertion *semantics* (loosening `test_corrupt_falls_back` to accept issues is expected and fine; anything else is not).
- You find `Config.issues` (or an equivalent field) already exists — Plan 003 may have landed first out of order; reconcile with its author/reviewer instead of merging blindly.

## Maintenance notes

- Plan 003 (doctor overhaul) consumes `Config.issues` and renders one doctor row per issue — keep issue strings one-line and free of newlines.
- Plan 015 adds another `Config` field (`snapshot_writethrough`); if executed concurrently, expect a trivial dataclass merge conflict.
- Reviewer should scrutinize: no behavior change for *valid* configs (the preset merge and XDG path logic are untouched), and `load_config` has no remaining path that can raise on arbitrary file content (try fuzzing mentally: file is a JSON array, a number, `null` — `isinstance(data, dict)` guard covers those).
