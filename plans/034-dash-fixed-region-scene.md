# Plan 034: Dash — fixed-region scene renderer (stable layout, honest provenance, no full-screen clears)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: plans 030 and 033 must be merged
> (`token_oracle/live/overlay.py` exists; `dashboard/app.py` `run()` uses the
> background probe subprocess, not in-loop fetchers). If not → STOP.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED (terminal behavior varies; bounded by pure-render tests + fixed-height invariant)
- **Depends on**: plans/030-live-truthfulness-contract.md, plans/033-live-probe-orchestration.md. Coordinates with plan 018 (see Maintenance notes).
- **Category**: dx / bug
- **Planned at**: commit `2660dd1` + live-web WIP, 2026-07-10

## Why this matters

`oracle dash` repaints by clearing the whole screen (`\033[2J\033[H`) every
1.2 s and printing a frame whose **height varies** with data (idle windows
render 1 line, active ones 3; banners appear and vanish; provenance lines come
and go). Every height change scrolls or jumps the terminal; every probe used
to inject progress text mid-frame. The operator experience: "history scrolls
in a weird way, updates feel janky, layout shifts whenever live data arrives."

The fix is a scene with **fixed-height regions**: the frame is always exactly
the same number of lines for a given config, every line is repainted in place
with erase-to-EOL, the alternate screen buffer keeps the user's scrollback
clean, and probe activity gets its own dedicated status region instead of
leaking anywhere. Provenance becomes a first-class UI element: every window
row states whether its number is live (with age), a local projection, or
absent — the user must never wonder which one they are looking at. This stays
stdlib-only (the repo's documented stance — Rich/Textual were considered and
rejected in the 2026-07-02 round; see plans/README.md).

## Current state

- `token_oracle/dashboard/app.py` (~411 lines pre-030):
  - `render_frame(forecasts, now, color=None, prev_forecasts=None, live_status=None, cells=None)`
    (signature post-030) → returns a `"\n"`-joined string of *variable* height.
  - `_render_profile_block(...)` — box-drawing per profile: active window = 3
    lines (head, tokens meta, provenance), idle = 1–3 lines depending on
    state; blocks stack vertically or side-by-side (lines ~303–318) depending
    on window-count equality.
  - `run(cfg)` (post-033) — loop: `run_forecast` → `load_snapshot` →
    `overlay_cells` → `render_frame` → full-clear + per-line print with
    `\033[K` (~lines 399–409); probe worker thread collects last stderr lines
    (currently discarded).
  - Reset-alarm banner inserted between header and panels when
    `detect_resets` fires (lines ~292–297) — a 2-line layout shift.
- `token_oracle/cli/colors.py` — `violet`, `dim`, `gauge`, `pulse`,
  `box_top`, `box_line`, `box_bot`, `color_enabled`, `M_*` glyph constants.
  Reuse these; do not add a color system.
- `token_oracle/core/timeutil.py` — `fmt_reset`, `fmt_tokens`, `fmt_dh_long`,
  `fmt_hms`. Reuse.
- `tests/test_dashboard.py` — pure render tests calling
  `render_frame(fs, now=..., color=False)` and asserting substrings
  (`"5h" in frame`, `"42%" in frame`). These must keep passing (update only
  where this plan changes wording, listed in Step 5).
- Windows per profile come from config; typical: claude = 5h + weekly +
  fable, grok = weekly. Idle vs active is data-dependent — which is exactly
  why height must NOT be.

Conventions: stdlib only; pure render functions tested without a TTY; ANSI
escapes written directly (see current `run()`); ruff line length 100.

## Commands you will need

| Purpose | Command | Expected |
|---------|---------|----------|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests   | `python -m pytest -q` | all pass |
| Lint    | `ruff check token_oracle/` + `ruff format --check token_oracle/` | exit 0 |
| Types   | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |
| Manual  | `TOKEN_ORACLE_SKIP_BOOTSTRAP=1 oracle dash` (10 s, ctrl-c) | stable frame, no jumps, scrollback intact after exit |

## Scope

**In scope**:
- `token_oracle/dashboard/scene.py` (create — region model + painter)
- `token_oracle/dashboard/app.py` (render functions become region fillers; `run()` uses the painter)
- `tests/test_dashboard.py` (update), `tests/test_scene.py` (create)
- `plans/README.md`

**Out of scope**:
- `live/` package — consume `overlay_cells` / `load_snapshot` as-is.
- `cli/colors.py`, `core/timeutil.py` — reuse, don't extend (a missing
  formatter is a STOP-worthy surprise, not a license to add one).
- Key input / tabs / alt-screen *navigation* — plan 018's scope. This plan
  uses the alt screen only as a static canvas.
- Engine, sources, snapshot writer.

## Git workflow

- Branch: `advisor/034-dash-fixed-region-scene`
- Conventional commits, e.g. `feat(dash): fixed-region scene renderer with provenance cells`

## Steps

### Step 1: Scene primitives

Create `token_oracle/dashboard/scene.py`:

```python
"""Fixed-region terminal scene. A Scene is an ordered list of Regions, each
with a constant height. render() returns exactly sum(heights) lines every
frame — layout stability is a type-level property here, not a hope. The
painter repaints in place (cursor home + erase-to-EOL per line); the only
full clear happens on terminal resize."""

@dataclass
class Region:
    name: str
    height: int
    fill: Callable[[], list[str]]   # returns UP TO height lines; padded/truncated

class Scene:
    def __init__(self, regions: list[Region]): ...
    def render(self, width: int) -> list[str]:
        # for each region: lines = fill(); pad with "" to height; truncate over-height
        # truncate every line to width (ANSI-aware: never cut inside an escape;
        # simplest correct approach: if visible length > width, drop styling for
        # that line via a strip_ansi() helper and cut plainly)

class Painter:
    """Owns the terminal. enter(): alt screen (\033[?1049h) + hide cursor
    (\033[?25l). exit(): restore (\033[?1049l, \033[?25h) — MUST run on any
    exit path (context manager + signal-safe try/finally in run()).
    paint(lines): cursor home (\033[H), then per line: write line + \033[K + newline
    (no newline after the last line). Full clear (\033[2J) ONLY when
    shutil.get_terminal_size() changed since the previous paint."""
```

Also `strip_ansi(s)` and `visible_len(s)` helpers (regex `\x1b\[[0-9;?]*[a-zA-Z]`).

**Verify**: `python -c "from token_oracle.dashboard.scene import Scene, Region, Painter, visible_len; print('ok')"` → `ok`

### Step 2: Fixed-height frame layout

In `app.py`, define the layout as a pure function of **config shape only**
(never of per-frame data):

| Region | Height | Content |
|---|---|---|
| header | 2 | title + live-status summary line |
| alert | 1 | reset alarm (blank when none — reserved, so no shift) |
| panels | `panel_height(groups)` | profile boxes |
| activity | 3 | last probe events, dim (from the 033 worker's stderr ring buffer) |
| footer | 1 | `sources … • ctrl-c quit • HH:MM:SS` |

`panel_height(groups)`: every window renders **exactly 3 lines** (head,
meta, provenance) whether idle or active — idle windows show
`idle · resets …` in the head, honest state in the provenance line, and a
blank meta line. Box top/bottom add 2 per profile. Stacked layout height =
Σ(2 + 3·n_windows) + gaps; side-by-side = max of the two blocks (pad the
shorter, as today at lines ~309–313). Window count comes from `cfg.windows` /
`cfg.profiles` at startup; if a profile produces no forecasts at runtime the
box shows `(no data)` lines padded to the same height — height NEVER follows
data.

### Step 3: Provenance cells in the row renderer

Rework `_render_profile_block` rows (the 3-line contract):

1. **head**: `● weekly  38% ██████░░░░ resets 2d 4h` — the big number is the
   **live pct** when `cell.pct is not None`, else the **local projection**.
   Glyph before the window name encodes origin: `●` live, `◌` local, `–` idle.
2. **meta** (dim): tokens `1.2M/8.0M` + when live is shown, the local
   projection too: `proj 41% end-of-window` — both numbers visible, labeled,
   never conflated (they are different quantities: current vs projected).
3. **provenance** (dim): exactly one of:
   - `live claude.ai · fable row · 42s ago` (extractor + age from the cell)
   - `local projection — no reliable live data (<state>)` where `<state>` ∈
     `authenticated_no_data | rate_data_only | stale | needs_login | unavailable | error`
   - `local projection — live disabled` (no playwright/no snapshot ever)
   Wording rule: the words "live" / "real data" may ONLY appear on rows whose
   number came from a cell with `pct is not None`. Grep-able invariant.
4. Header live-status line (region `header`, line 2): per provider one compact
   chip: `grok ● live 10% (58s)` / `claude ◌ no data (authenticated_no_data)`
   / `claude ▲ rate-only 150/150 per 2h` (rate info via `overlay.rate_info`,
   clearly labeled as a rate window, never as usage). Drop the old
   LIVE-WEB-ACTIVE banner variants (lines ~212–250) and the "did it try" prose
   block (~257–289) — the chips + activity region replace them.
5. `render_frame(forecasts, now, color=None, cells=None, probe_log=None, size=None)`
   returns `list[str]` of exactly the layout height (it becomes a thin
   composition over Scene.render). Keep a `"\n".join` wrapper
   `render_frame_str(...)` for test convenience. Delete `prev_forecasts` /
   `live_status` params — reset detection stays in `run()` (it feeds the
   alert region), status comes from cells/snapshot.

### Step 4: run() on the painter

1. Wrap the loop in `Painter` as context manager; SIGINT path must restore
   the terminal (existing `except KeyboardInterrupt: return 0` sits inside the
   `with`).
2. Delete `print("\033[2J\033[H", ...)` and the startup "⏳ Starting oracle
   dash..." prints — the first frame IS the feedback (activity region shows
   `probing grok.com…` from the worker immediately).
3. Probe worker (from 033) keeps a ring buffer `deque(maxlen=3)` of
   timestamped stderr lines + probe exit summaries → `activity` region fill.
4. Tick stays 1.2 s; repaint every tick (cheap — same-height in-place lines);
   `detect_resets(prev, curr)` output fills the `alert` region for N ticks
   (keep the existing `c.pulse` treatment) then blanks — height constant.

### Step 5: Tests

`tests/test_scene.py`:
1. Scene with a 3-line region whose fill returns 1 line → render returns
   exactly 3 lines (padding).
2. fill returns 5 lines → truncated to 3.
3. `visible_len("\033[1m42%\033[0m") == 3`; over-width line is cut to width.
4. **Height invariance** (the regression test for this whole plan): same
   config-shaped layout rendered with (a) all windows idle, (b) all active,
   (c) live cells present, (d) empty probe log → identical line counts.

`tests/test_dashboard.py` updates:
- Keep substring assertions on `render_frame_str` output; adjust calls for
  the new signature.
- `test_render_frame_handles_idle` — idle rows now say `idle` in the head and
  honest provenance; the "starts when a message is sent" phrase appears ONLY
  when a cell carries the five-hour-state value. Rewrite the assertion
  accordingly (it currently accepts either).
- New: a frame with `cells` containing a live claude weekly pct → row shows
  both `38%` and `proj` label; the word `live` does NOT appear on any row
  whose cell has `pct=None`.

## Test plan

Above; all pure, no TTY (Painter itself is exercised only manually — keep it
thin enough that eyeballing `oracle dash` for 30 s is the acceptance test;
that manual check is listed in Done criteria).

## Done criteria

- [ ] `python -m pytest -q` exits 0 with ≥ 4 scene tests + updated dashboard tests
- [ ] `ruff check` / `ruff format --check` / `mypy` exit 0
- [ ] `grep -n '2J' token_oracle/dashboard/app.py token_oracle/dashboard/scene.py` → only the resize path in scene.py
- [ ] Height-invariance test exists and passes
- [ ] Manual: 30 s of `oracle dash` in a ≥ 80×24 terminal — no line jumps, no
      scrollback pollution after ctrl-c (alt screen restored), probe activity
      confined to its region. Record your observation in the status row.
- [ ] `plans/README.md` status row updated

## STOP conditions

- Plan 033's probe worker/ring buffer is absent from `run()` (dependency not
  actually landed).
- `render_frame`'s current structure resists the 3-line row contract without
  touching out-of-scope files.
- Existing dashboard tests assert variable-height behavior in > 5 places —
  the test-update budget of this plan is wrong; report before rewriting the
  suite.
- You need a formatter/color helper that doesn't exist — report; don't grow
  `colors.py` under this plan.

## Maintenance notes

- **Plan 018 (TUI shell, tabs — currently TODO)**: after this plan, 018
  should be revised to HOST these regions — its "present" tab body = the
  panels+activity regions; its alt-screen/key-input shell wraps Painter
  rather than reimplementing repaint. Whoever executes 018 next must read
  scene.py first; the index note for 018 says so.
- The 3-lines-per-window contract is the layout's load-bearing invariant;
  any future row content must fit it or change `panel_height` in the same
  commit (the height-invariance test will catch drift).
- Terminal narrower than ~66 cols truncates plainly (styling stripped on
  over-width lines); a responsive narrow layout is deferred — record demand
  before designing it.
- Deferred: bar fill animation between frames (ease toward new value) — pure
  eye-candy; the scene model supports it (fill functions are stateful-capable)
  but it was not worth blocking honesty work on.
