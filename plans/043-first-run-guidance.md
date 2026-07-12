# Plan 043 — first-run guidance (stop showing a bare `idle` to new users)

**Status:** TODO
**Priority:** P1 (Phase 1 "make it visible" — first-run experience)
**Effort:** S
**Risk:** low-medium (touches the `forecast` output path; the machine-readable
outputs — `--json`, non-TTY, `statusline`, `tmux` — must stay byte-for-byte
identical)
**Written against commit:** `7264a71`
**Files in scope:** `token_oracle/cli/main.py`, `tests/test_cli.py`
**Do NOT touch:** `statusline`/`tmux`/`snapshot`/`doctor`/`dash` dispatch, the
dashboard, or any extractor. Only the `forecast` branch + one small helper.

---

## Why this matters

A brand-new user's first command (per the README quickstart) is
`token-oracle forecast`. If they have no usage logs yet — or their source is
misconfigured — the entire program output is one cryptic word:

```
$ token-oracle forecast
idle
```

`idle` gives a newcomer nothing: no reason, no next step, no sign the tool even
works. This is the first-run cliff. This plan replaces that bare `idle` with a
short, actionable hint **when (and only when) a human is watching an interactive
terminal**. Scripts, status bars, pipes, and `--json` must be unaffected — they
depend on the stable `idle` token.

## Current state (exact excerpt — `token_oracle/cli/main.py`, lines 304–313)

```python
    if args.cmd == "forecast":
        fs = run_forecast(now, cfg)
        if args.json:
            print(json.dumps(build_snapshot(fs, now), indent=2))
        else:
            out = sl.render(fs) or "idle"
            if cfg.profiles:
                out = "(multi) " + out
            print(out)
        return 0
```

`run_forecast` returns an empty list when there is no data; `sl.render([])`
returns `""`, so `or "idle"` produces the bare word. The "no data" signal is
therefore simply: `sl.render(fs)` is empty.

`sys` is already imported at the top of the file (line 9).

## The fix — steps in order

### Step 1 — add two module-level helpers

Add these just after `_now` (after line 29), before `_doctor_lines`:

```python
def _is_interactive():
    """True when stdout is an interactive terminal (not a pipe / file / capture).

    Isolated into a helper so tests can monkeypatch it; capturing stdout in a
    test makes the real isatty() False, which would hide the guidance branch.
    """
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def _first_run_hint():
    """Actionable guidance shown when `forecast` finds no data on a real TTY."""
    return (
        "no usage data yet.\n"
        "\n"
        "token-oracle forecasts from your agent's local logs — there is nothing\n"
        "to forecast until some exist.\n"
        "  • Claude Code: use it once; logs appear under ~/.claude/projects/\n"
        "  • see what oracle found:   oracle doctor\n"
        "  • create a config:         oracle init\n"
        "  • turn on live web numbers: oracle live on   (then: oracle live-setup)\n"
        "\n"
        "docs: https://github.com/muslewski/token-oracle"
    )
```

### Step 2 — branch the `forecast` else-block on no-data + interactivity

Replace the `else:` block (lines 308–312) with:

```python
        else:
            out = sl.render(fs)
            if not out:
                # No data. A human at a terminal gets guidance; everything
                # non-interactive (pipes, status bars, scripts) keeps the
                # stable "idle" token it has always emitted.
                if _is_interactive():
                    print(_first_run_hint())
                    return 0
                out = "idle"
            if cfg.profiles:
                out = "(multi) " + out
            print(out)
```

Do not change the `if args.json:` branch or the `return 0` at the end of the
`forecast` block.

## Behavior matrix (what must hold after the change)

| Situation | Output |
|---|---|
| no data, `--json` | unchanged JSON (empty forecast) |
| no data, piped / non-TTY | `idle` (or `(multi) idle` with profiles) — **unchanged** |
| no data, interactive TTY | the multi-line first-run hint |
| has data (any) | unchanged status line, **no hint** |
| `statusline`, `tmux` | unchanged (this plan does not touch them) |

## Files out of scope / must not change

- The `--json` forecast path, `statusline`, `tmux`, `snapshot`, `doctor`, `dash`.
- The dashboard (`token_oracle/dashboard/app.py`) — its empty-state is already
  honest and is out of scope for this plan.
- The meaning of `idle` for non-interactive callers. If you change what a pipe
  sees, you have broken statusline/tmux consumers — STOP.

## Test plan (`tests/test_cli.py`)

Import `main` (and the module itself for monkeypatching) the same way the file
already does. Use `monkeypatch` to force `run_forecast` to return `[]` and to
flip `_is_interactive`. Reference the module object (e.g. `from token_oracle.cli
import main as cli_main`) so you can monkeypatch its names.

Add:

1. `test_forecast_no_data_interactive_shows_hint`
   ```python
   def test_forecast_no_data_interactive_shows_hint(monkeypatch, capsys):
       monkeypatch.setattr(cli_main, "run_forecast", lambda now, cfg: [])
       monkeypatch.setattr(cli_main, "_is_interactive", lambda: True)
       rc = cli_main.main(["forecast", "--now", "1000"])
       assert rc == 0
       out = capsys.readouterr().out
       assert "no usage data yet" in out
       assert "oracle doctor" in out
       assert out.strip() != "idle"
   ```

2. `test_forecast_no_data_noninteractive_still_idle`
   ```python
   def test_forecast_no_data_noninteractive_still_idle(monkeypatch, capsys):
       monkeypatch.setattr(cli_main, "run_forecast", lambda now, cfg: [])
       monkeypatch.setattr(cli_main, "_is_interactive", lambda: False)
       rc = cli_main.main(["forecast", "--now", "1000"])
       assert rc == 0
       assert capsys.readouterr().out.strip() == "idle"
   ```

3. `test_forecast_no_data_json_unaffected`
   ```python
   def test_forecast_no_data_json_unaffected(monkeypatch, capsys):
       monkeypatch.setattr(cli_main, "run_forecast", lambda now, cfg: [])
       monkeypatch.setattr(cli_main, "_is_interactive", lambda: True)
       rc = cli_main.main(["forecast", "--json", "--now", "1000"])
       assert rc == 0
       out = capsys.readouterr().out
       assert "no usage data yet" not in out   # json path never shows the hint
   ```

If `run_forecast` cannot be monkeypatched by that name (check how it is imported
— it is `from ..core.engine import forecast as run_forecast`, so the name on the
`main` module is `run_forecast`), monkeypatch `cli_main.run_forecast`.

## Done criteria (machine-checkable — run from repo root)

1. `python -c "import token_oracle, os; print(os.path.dirname(token_oracle.__file__))"`
   prints a path under THIS worktree (else prefix commands with `PYTHONPATH="$PWD"`).
2. `TOKEN_ORACLE_SKIP_BOOTSTRAP=1 python -m token_oracle.cli.main forecast | cat`
   still prints exactly `idle` or `(multi) idle` (piped → non-interactive →
   unchanged). *(On your worktree there may actually be data; if so this prints a
   real status line instead — that is fine, the point is no traceback and no hint
   text when piped.)*
3. All gates pass:
   - `python -m pytest -q`
   - `ruff check token_oracle tests`
   - `ruff format --check token_oracle tests`
   - `python -m mypy token_oracle --ignore-missing-imports`
4. `git diff --stat` shows only `token_oracle/cli/main.py` and
   `tests/test_cli.py`.

Do NOT run `pip install -e`.

## Escape hatches

- If `sl.render([])` does NOT return a falsy value in this codebase (verify:
  `python -c "from token_oracle.adapters import statusline as s; print(repr(s.render([])))"`
  — expect `''`), then the `if not out:` trigger is wrong. STOP and report the
  actual return value instead of guessing a different trigger.
- If any existing test asserts `forecast` prints `idle` while faking an
  interactive TTY, that assertion encodes the old behavior — STOP and report;
  do not silently rewrite unrelated tests.

## Maintenance note

The hint text names three commands (`doctor`, `init`, `live on`) and a log path
(`~/.claude/projects/`). If any of those are renamed, update the hint. The
interactivity gate (`_is_interactive`) is the load-bearing part: never emit the
multi-line hint on a non-TTY — status bars and scripts parse this output.
