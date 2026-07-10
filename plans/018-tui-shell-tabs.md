# Plan 018: TUI shell — alternate screen, keyboard input, past/present/future tabs

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ada32e9..HEAD -- token_oracle/dashboard/ token_oracle/cli/colors.py token_oracle/cli/main.py tests/test_dashboard.py README.md SETUP.md`
> If any in-scope file changed since `ada32e9`, compare "Current state"
> excerpts against live code; on mismatch, STOP. (Plans 016/017 don't touch
> these files; plan 008 adds `init`/`clean` branches to `main.py` — that is
> expected drift, not a STOP.)

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED (raw terminal mode — must restore terminal state on every exit path)
- **Depends on**: none hard. Ships placeholder Past/Future panels; plans 019/020 fill them.
- **Category**: direction
- **Planned at**: commit `ada32e9`, 2026-07-02

## Why this matters

`oracle dash` today is a 60-line fixed-width repaint loop: one view, no
keyboard input (only ctrl-c), fixed 2 s cadence, fixed 12-char bars, no
terminal-width awareness. The product vision is an Oracle that tells the
past, present, and future — three tabs switched with arrow keys. No
competitor ships this (ccusage is a static report CLI; the 8.3k★
Claude-Code-Usage-Monitor is a single live view behind flags — see
`plans/research-competitive-landscape.md`), so this shell is the
differentiator. This plan builds the interactive frame: alternate screen,
raw-mode non-blocking key reading (stdlib only), a tab bar, width-responsive
rendering, decoupled data-vs-render cadence, and a polished Present tab.
Past/Future render an informative placeholder until plans 019/020 land.

## Current state

- `token_oracle/dashboard/app.py` (60 lines, whole file) — key parts:

  ```python
  BAR_W = 12                                            # app.py:10
  def _bar(pct, enabled, width=BAR_W): ...              # app.py:13-15  █/░ gauge
  def render_frame(forecasts, now, color=None): ...     # app.py:18-48  pure, tested
  def run(cfg):                                         # app.py:51-60
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

- `token_oracle/cli/main.py:138-141` — `dash` lazy-imports and calls `run(cfg)`.
- `token_oracle/cli/colors.py` — the ANSI foundation: `paint/violet/dim`
  (256-color), `gauge(text, pct, enabled)` + `gauge_tier` thresholds
  (≥120 red, ≥100 orange, ≥85 lime, else green; colors.py:58-66),
  `color_enabled()` gating on NO_COLOR/FORCE_COLOR/tty (colors.py:29-37),
  markers `M_ORACLE="🔮" M_WARN="⚠" M_BULLET="●"` (colors.py:18-22).
  Docstring rule: "Consumer-ring util — oracle.core never imports this."
- `token_oracle/core/engine.py:10-29` — `forecast(now, cfg)` is cheap when
  called repeatedly: it re-scans sources only every `AGGREGATE_INTERVAL = 30`
  seconds (cache.py:8), otherwise serves cached events. So the render loop
  may call it every tick.
- `tests/test_dashboard.py` (33 lines) — pure-render tests; pattern to
  extend: build `Forecast(...)` fixtures, assert substrings, assert
  `"\033" not in render(...)` when color off.
- `Forecast` fields (core/contracts.py:24-32): `window, used, cap,
  projected_pct, eta_to_cap_secs, reset_in_secs, idle, confidence`.
- Zero-dependency stance: `pyproject.toml` `dependencies = []`;
  AGENTS.md:14 ("no dependencies beyond stdlib"). **Decided: no Rich, no
  Textual, no curses.** curses is absent on Windows; the repo already
  hand-rolls ANSI. Keyboard input uses `termios`+`tty`+`select` on POSIX and
  `msvcrt` on Windows — both stdlib.

## Design (decided — do not redesign)

Three new/changed pieces, keeping "render functions stay pure" (colors.py
docstring) so everything except the loop is unit-testable:

**1. `token_oracle/dashboard/keys.py` (create)** — input handling split into
a pure decoder and a thin platform reader:

```python
"""Non-blocking key input for the dash. decode() is pure (tested); the
readers own platform specifics. Stdlib only: termios/tty/select on POSIX,
msvcrt on Windows."""

LEFT, RIGHT, QUIT, OTHER = "left", "right", "quit", "other"

def decode(data: bytes) -> list[str]:
    """Raw stdin bytes -> semantic keys. Understands arrow escapes
    (b"\x1b[D" LEFT / b"\x1b[C" RIGHT), vim keys (h/l), digits 1-3 mapped
    by the caller, q/Q and ctrl-c (b"\x03") -> QUIT. Unknown -> OTHER."""

class PosixReader:
    """Context manager: tty.setcbreak on __enter__, restore termios attrs on
    __exit__ (try/finally in the caller guarantees restore). poll(timeout)
    uses select.select on sys.stdin; returns decode()d keys."""

class WindowsReader:
    """msvcrt.kbhit()/getwch(); arrow keys arrive as '\xe0' + code ('K' left,
    'M' right). Same poll(timeout) interface (timeout via time.sleep slice)."""

def reader():
    """Return the platform reader; None when stdin is not a tty (dash then
    runs in the old no-input mode)."""
```

Digits `1/2/3` and `\t` (cycle) also switch tabs — decode returns them as
`"tab1"/"tab2"/"tab3"/"cycle"`.

**2. `token_oracle/dashboard/screen.py` (create)** — terminal session guard:

```python
"""Alternate-screen guard: enter alt buffer + hide cursor on start, ALWAYS
restore on exit (normal return, exception, ctrl-c). Pure-ANSI, stdlib."""
ENTER = "\033[?1049h\033[?25l"   # alt screen + hide cursor
LEAVE = "\033[?1049l\033[?25h"   # restore
```

Used via try/finally in `run()`. When stdout is not a tty, skip both.

**3. `token_oracle/dashboard/app.py` (rewrite `run`, keep `render_frame`)**:

- Tabs: `TABS = ("past", "present", "future")`, start on `present`.
- `render_tab_bar(active, width, enabled)` — pure. Format:
  `🔮 token-oracle   ‹ Past │ Present │ Future ›` with the active name
  violet+bright and others dim; right-aligned clock `HH:MM:SS`; a dim `─`
  rule underneath, both spanning `width`.
- `render_present(forecasts, now, width, enabled)` — today's
  `render_frame` body, with bar width scaled: `bar_w = max(12, min(40,
  width - 46))`, and an added per-window dim line showing observed burn
  (`fmt_tokens(used/elapsed*3600)}/h` is NOT computable from Forecast — skip;
  keep the existing used/cap/reset/ETA lines). Keep `render_frame` as a thin
  alias delegating to `render_present` with `width=80` so the existing tests
  and any external callers stay valid.
- `render_placeholder(tab, width, enabled)` — pure; dim panel:
  `"the oracle is still learning to read the past"` / `"...the future"` plus
  `"arrives with plan 019/020"` line. (Plans 019/020 replace these calls.)
- `render_footer(width, enabled)` — key hints:
  `←/→ or h/l switch · 1-3 jump · q quit`, dim.
- Frame assembly: tab bar + active panel + footer, joined, then the existing
  home-and-clear repaint (`"\033[H" + frame + "\033[J"`).
- Loop (decoupled cadences, per ccmonitor's refresh-rate/render-rate split):
  poll keys with `poll(0.25)` → 4 renders/s for a live clock and instant key
  response; call `run_forecast(t, cfg)` at most once per second (engine's
  own 30 s aggregate gate makes that cheap); `shutil.get_terminal_size()`
  every frame (handles resize without SIGWINCH).
- First frame before data: render tab bar + dim `⠋ consulting the oracle…`
  spinner char cycling through `"⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"` while the first
  `run_forecast` call runs in the main thread (render once before calling it,
  then proceed — no threads).
- No tty (piped): fall back to exactly today's behavior — loop rendering
  Present at 2 s without keys or alt screen (keeps `oracle dash | head`
  usable and CI-safe).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass |
| Lint | `ruff check token_oracle/ && ruff format --check token_oracle/` | exit 0 |
| Types | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |
| Manual smoke | `oracle dash` in a real terminal | tabs switch with ←/→, q quits, terminal restored |

## Scope

**In scope**:
- `token_oracle/dashboard/keys.py` (create)
- `token_oracle/dashboard/screen.py` (create)
- `token_oracle/dashboard/app.py` (rewrite run/rendering; keep render_frame alias)
- `tests/test_dashboard.py` (extend), `tests/test_keys.py` (create)
- `README.md` (dash description), `SETUP.md` (Tier 2 section)

**Out of scope**:
- `token_oracle/cli/colors.py` — use it, don't change it. If a helper is
  missing (e.g. bright/bold), add it to the dashboard module, not colors.py.
- Past/Future real content (plans 019/020), cost display (017/019),
  `core/`, `sources/`, `adapters/`, `snapshot/`.
- Any new dependency, curses, threads, or asyncio.
- `cli/main.py` — the `dash` dispatch already works; only touch it if the
  `run(cfg)` signature must change (it must not).

## Git workflow

- Branch: `advisor/018-tui-shell-tabs`
- Conventional commits, e.g. `feat(dash): tabbed TUI shell with arrow-key input`
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: `keys.py` decode() + tests

Write the pure decoder first with `tests/test_keys.py`: bytes for left/right
arrows (`b"\x1b[D"`, `b"\x1b[C"`), `b"h"`, `b"l"`, `b"q"`, `b"\x03"`,
digits, tab, a chunk containing several keys back-to-back
(`b"\x1b[C\x1b[C q"` → right, right, other(space), quit), and a lone
`b"\x1b"` (returns nothing / OTHER, must not crash).

**Verify**: `python -m pytest -q tests/test_keys.py` → all pass.

### Step 2: platform readers + screen guard

Implement `PosixReader`, `WindowsReader`, `reader()`, and `screen.py`.
Guard the Windows import (`import msvcrt` inside the class or a
`sys.platform` check) so POSIX test runs never import it. `PosixReader`
must restore the exact `termios.tcgetattr` state captured on enter.

**Verify**: `python -m pytest -q && ruff check token_oracle/` → green.
Manual: `python -c "from token_oracle.dashboard.keys import reader; print(reader() is None)"`
piped (non-tty) prints `True`.

### Step 3: pure renderers

`render_tab_bar`, `render_placeholder`, `render_footer`, `render_present`
(+ `render_frame` alias). Extend `tests/test_dashboard.py` following its
existing style: active tab name present and others rendered; `"\033" not in`
output with color off (the discipline test_dashboard.py:27 pins today);
width 60 vs width 120 produce different bar widths; placeholder mentions the
tab name; footer lists `q`.

**Verify**: `python -m pytest -q tests/test_dashboard.py` → all pass.

### Step 4: the loop

Rewrite `run(cfg)` per Design: try/finally around the whole loop with
`screen.LEAVE` + termios restore in the finally; tab state machine
(left/right wraps around); no-tty fallback path. Keep `return 0` on quit
and on KeyboardInterrupt.

**Verify**: `python -m pytest -q` all green; manual smoke in a real
terminal: run `oracle dash`, switch tabs with arrows and `2`, resize the
window (bars adapt), press `q` — the shell prompt returns with a sane
terminal (type `echo ok` to confirm echo works; if echo is broken the
termios restore is wrong).

### Step 5: docs

README.md: replace the one-line dash description with tabs + keys. SETUP.md
Tier 2: mention past/present/future tabs, key bindings, and that piped
output falls back to a non-interactive present view.

**Verify**: `grep -n "Future" README.md SETUP.md` → hits; full test suite green.

## Test plan

- `tests/test_keys.py`: decoder table (~8 cases, Step 1).
- `tests/test_dashboard.py`: +6 renderer cases (Step 3), existing 5 stay
  green via the `render_frame` alias.
- The loop itself and platform readers are exercised by the manual smoke
  test only — do not write pty-based tests (fragile in CI); the pure/impure
  split exists precisely so the untested surface is thin.
- Verification: `python -m pytest -q` → all pass.

## Done criteria

- [ ] `python -m pytest -q` exits 0; `tests/test_keys.py` exists with ≥8 cases
- [ ] `ruff check`, `ruff format --check`, `mypy` exit 0
- [ ] `grep -n "dependencies = \[\]" pyproject.toml` → still matches (no new deps)
- [ ] `grep -rn "import curses\|import rich\|import textual" token_oracle/` → no matches
- [ ] `python -c "from token_oracle.dashboard.app import render_frame"` exits 0 (alias kept)
- [ ] Manual smoke (Step 4) performed and reported in the completion note:
  tabs switch, q quits, terminal state restored
- [ ] `git status` clean outside in-scope list; `plans/README.md` row updated

## STOP conditions

- Excerpt mismatch in "Current state" (drift).
- Terminal state cannot be reliably restored on some exit path — report the
  path rather than shipping a dash that corrupts terminals.
- You find yourself wanting curses/Rich or a thread to make the loop work —
  the design above needs neither; report what blocked you.
- `render_frame`'s existing 5 tests can't pass unchanged via the alias.

## Maintenance notes

- Plans 019/020 replace `render_placeholder` calls with `render_past` /
  `render_future` — keep the tab→renderer dispatch a small dict so that's a
  two-line change.
- Windows reader is untested by CI (POSIX runners); any Windows bug report
  lands there first — keep `WindowsReader` trivial.
- Reviewer focus: the finally-block restore ordering (screen LEAVE before
  termios restore is fine, but both must run), the non-tty fallback, and
  that no `core/` module imports anything from `dashboard/`.
- Deferred: configurable refresh rates via config (add `dash_refresh_secs`
  only if users ask); theme auto-detection (rejected — see research doc).
