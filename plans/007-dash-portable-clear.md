# Plan 007: Portable, flicker-free dashboard refresh (drop `os.system("clear")`)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat d2b4d32..HEAD -- token_oracle/dashboard/app.py token_oracle/cli/main.py`
> If either file changed since this plan was written (beyond Plans 001–004's
> declared `main.py` changes), compare the "Current state" excerpts against
> the live code before proceeding; on a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `d2b4d32`, 2026-07-01

## Why this matters

`oracle dash` clears the screen every 2 seconds with `os.system("clear")`. On Windows there is no `clear` command (`cls` is the cmd built-in), so the dashboard prints an error line every refresh — while `pyproject.toml` classifies the package `Operating System :: OS Independent`. On every platform, spawning a shell per frame plus a full clear causes visible flicker. A two-character ANSI sequence fixes both. Bonus cleanup: `run(cfg, now)` takes a `now` parameter it never uses (the hidden `--now` test hook silently does nothing for `dash`), which misleads readers.

## Current state

- `token_oracle/dashboard/app.py` — stdlib TUI. `render_frame` is pure and tested (`tests/test_dashboard.py`, 5 tests); `run()` is the untested refresh loop. Excerpt `app.py:52-61` at `d2b4d32`:

```python
def run(cfg, now):
    try:
        while True:
            os.system("clear")
            t = time.time()
            print(render_frame(run_forecast(t, cfg), t))
            print(c.dim("\n(ctrl-c to quit)", c.color_enabled()))
            time.sleep(2)
    except KeyboardInterrupt:
        return 0
```

  Imports at `app.py:4-9`: `os`, `time`, colors, engine, timeutil. After this change `os` becomes unused in this file — remove the import (ruff `F401` enforces).

- `token_oracle/cli/main.py:79-82` — the call site:

```python
    if args.cmd == "dash":
        from ..dashboard.app import run as run_dash

        return run_dash(cfg, now)
```

ANSI background: `\033[H` moves the cursor home; `\033[J` erases from cursor to end of screen. Home-then-overdraw (`\033[H` + full frame + `\033[J` semantics) repaints in place without the blank-screen flash of `\033[2J`. Windows 10+ terminals (Windows Terminal, VS Code, ConHost with VT enabled) honor these; legacy pre-VT cmd degrades to printed escape bytes — strictly no worse than today's `'clear' is not recognized…` error line, and that legacy case is explicitly not a support target.

Conventions: stdlib only; module docstring style preserved; ruff line-length 100.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass |
| Lint | `ruff check token_oracle/ && ruff format --check token_oracle/` | exit 0 |
| Types | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |
| Manual | `timeout 5 oracle dash; echo done` | dashboard repaints without full-screen flash; exits after 5 s |

## Scope

**In scope** (the only files you should modify):
- `token_oracle/dashboard/app.py`
- `token_oracle/cli/main.py` (the `dash` branch call only)

**Out of scope** (do NOT touch):
- `render_frame` and its tests — pure renderer, unaffected.
- Refresh cadence (`time.sleep(2)`), colors, layout — no redesign.
- Adding curses/alternate-screen buffers — deliberate non-goal at this size.

## Git workflow

- Branch: `advisor/007-dash-portable-clear`.
- Conventional commit, e.g.: `fix(dash): ANSI in-place repaint instead of os.system("clear"); drop unused now param`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Replace the clear and drop the dead parameter

In `app.py`, change `run` to:

```python
def run(cfg):
    try:
        while True:
            t = time.time()
            frame = render_frame(run_forecast(t, cfg), t)
            footer = c.dim("\n(ctrl-c to quit)", c.color_enabled())
            print("\033[H" + frame + "\n" + footer + "\033[J", end="", flush=True)
            time.sleep(2)
    except KeyboardInterrupt:
        return 0
```

(Compose one string and print once: home, overdraw the new frame, erase any remainder of the previous frame below, flush.) Remove the now-unused `import os`.

**Verify**: `ruff check token_oracle/` → exit 0 (would flag an unused `os` import if you forgot).

### Step 2: Update the call site

In `main.py`, change the dash branch to `return run_dash(cfg)`.

**Verify**: `python -m pytest -q` → all pass (nothing tests `run()`, but import-time and CLI wiring are exercised by `test_dashboard.py`/`test_cli.py`).

### Step 3: Manual smoke + full gates

Run `timeout 5 oracle dash` in a real terminal: the header stays fixed, values repaint in place, no full-screen blank flash, and after Ctrl-C or timeout the shell prompt returns cleanly.

**Verify**: `python -m pytest -q` all pass; `ruff check token_oracle/ && ruff format --check token_oracle/` exit 0; `mypy token_oracle/ --ignore-missing-imports` exit 0.

## Test plan

No new automated tests: `run()` is an infinite interactive loop; testing it would need subprocess/timeout machinery disproportionate to a 2-line change. The pure part (`render_frame`) keeps its 5 existing tests. The manual smoke in Step 3 is the behavioral gate — record in your report that you performed it and what terminal you used.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -rn "os.system" token_oracle/` → 0 matches.
- [ ] `grep -n "def run(cfg)" token_oracle/dashboard/app.py` → 1 match (no `now` param).
- [ ] `python -m pytest -q` exits 0.
- [ ] `ruff check token_oracle/`, `ruff format --check token_oracle/`, `mypy token_oracle/ --ignore-missing-imports` all exit 0.
- [ ] Manual smoke performed and reported (Step 3).
- [ ] `git status --short` → only the two in-scope files (plus `plans/README.md`).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report back (do not improvise) if:

- `run()` in live code differs from the excerpt (drifted).
- The manual smoke shows garbled output in *your* modern terminal (would indicate the escape sequence composition is wrong — report the terminal and raw output rather than iterating blindly).
- You feel the urge to add Windows-specific branches (`cls`, colorama, …) — out of scope; the ANSI path is the decision.

## Maintenance notes

- If the dashboard ever grows interactive controls, that's the moment to move to an alternate-screen buffer (`\033[?1049h/l`) — noted here so the next person doesn't bolt it onto this loop ad hoc.
- Reviewer: check the single-print composition (home → frame → footer → erase-below) — printing the erase *before* the frame reintroduces flicker.
