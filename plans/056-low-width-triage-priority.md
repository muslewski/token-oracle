# Plan 056: Low-width dashboard shows the most important info first (priority triage that fits any screen)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on. If a
> STOP condition occurs, stop and report — do not improvise. When done, update
> the status row for this plan in `plans/README.md` (a reviewer maintains the
> index — still flip your row).
>
> **Drift check (run first)**:
> `git diff --stat 9df923b..HEAD -- token_oracle/dashboard/app.py tests/test_dashboard.py`
> If either changed since this plan was written, compare the "Current state"
> excerpts to the live code before proceeding; on a mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED (display logic; fully guarded by fit + priority tests)
- **Depends on**: none (builds on 052's width ladder, already merged)
- **Category**: bug / UX
- **Planned at**: commit `9df923b`, 2026-07-13

## Why this matters

When the terminal is narrow, the dashboard collapses to a one-line-per-provider
"compact" view. Two problems make it useless exactly when space is scarcest:

1. **It's importance-blind.** `_compact_profile_line` lists windows in
   **alphabetical** order (`sorted(..., key=lambda x: x.window)` → `5h, fable,
   weekly`), then `Scene.render` truncates the END to fit the width. So the
   window that gets dropped is whichever sorts last — not the least important
   one. Reproduced at W=30: the line became `✳ claude  5h 2% · fable 99% · ` —
   `weekly 33%` was cut and a dangling `· ` left behind, while `fable 99%` (the
   window about to hit its cap!) survived only by luck of the alphabet.
2. **No triage floor.** Below the compact level there is only `tiny` = the header
   banner alone (no numbers). There is no "show me just the one number that
   matters" level for a very small screen.

The user's rule (decided): **the most important window is the one closest to its
cap (highest current %)** — that's the limit about to cut you off. After this
plan, at any width the binding number leads and always survives; lower-priority
windows drop cleanly (no dangling separators); and a single-line **glance** floor
shows the worst-per-provider on even a tiny screen.

Target shapes (illustrative):
```
compact:  ✳ claude  99% fable · 33% wk · 2% 5h        (ordered high→low, fit to width)
narrower: ✳ claude  99% fable                          (only what fits; binding kept)
glance:   🔮 fable 99% · weekly 24%                     (single line, worst per provider)
```

## Current state

`token_oracle/dashboard/app.py`:

- `_compact_profile_line(pname, forecasts, now, enabled, cells=None)` (lines
  108-131) — TODAY:
  ```python
  def _compact_profile_line(pname, forecasts, now, enabled, cells=None) -> str:
      cells = cells or {}
      p_canon = "grok" if "grok" in pname.lower() else "claude"
      icon = _profile_icon(pname)
      parts: list[str] = []
      for f in sorted(forecasts, key=lambda x: x.window):     # <-- alphabetical
          ww = (f.window or "").lower()
          if bool(getattr(f, "idle", False)):
              continue
          is_5h = "5h" in ww or "session" in ww or "current" in ww
          if is_5h:
              pct = (100.0 * f.used / f.cap) if getattr(f, "cap", 0) else 0.0
              short = "5h"
          else:
              wkey = "weekly" if ww in ("weekly", "week") else ("fable" if ww == "fable" else None)
              cell = cells.get((p_canon, wkey)) if wkey else None
              pct = cell.pct if (cell and cell.pct is not None) else f.projected_pct
              short = "wk" if ww in ("weekly", "week") else (ww or "?")
          parts.append(f"{short} {round(pct)}%")
      body = " · ".join(parts) if parts else "no active windows"
      return c.dim(f"{icon} {pname.lower()}  {body}", enabled)
  ```
  Note the pct blend (5h → used/cap; else cell.pct or projected_pct) and the
  `short` names — REUSE these exactly; only the ORDER, the fit-to-width, and the
  coloring change.

- `compact_fill()` inside `render_frame` (lines 492-495):
  ```python
  def compact_fill() -> list[str]:
      if not groups:
          return [c.dim("(no data)", enabled)]
      return [_compact_profile_line(pn, groups[pn], now, enabled, cells) for pn in sorted(groups)]
  ```
  `w` (the terminal width, `max(1, cols)`) is in scope here.

- The level ladder `_regions_for(level)` + selection loop (lines ~518-558):
  ```python
  for level in ("full", "meta", "heads", "oneline", "tiny"):
      regs = _regions_for(level)
      total = sum(r.height for r in regs)
      if avail_h == 0 or total <= avail_h:
          out = Scene(regs).render(w)
          return out[:avail_h] if avail_h else out
  ```
  `oneline` = header(2) + alert(1) + compact(len(clines)); `tiny` = header only.
  `avail_h == 0` (tests / no size) always picks `full` — PRESERVE that.

- Color helpers: `c.dim(text, enabled)`, `c.gauge(text, pct, enabled)` (gauge
  colors by severity tier — use it to make the binding number pop),
  `_profile_icon(pname)`, `c.M_ORACLE` (the 🔮 glyph). Width measure:
  `from ..cli.colors import display_width` is NOT imported in app.py yet — import
  it (colors already exposes it) OR use `c.display_width`.

Conventions:
- Pure function output; `render_frame` stays pure. Stdlib only.
- Fixed-height contract: any region's `fill()` must return exactly its declared
  height. `glance` is height 1 → `glance_fill()` returns exactly one line.
- Every produced line must satisfy `c.display_width(line) <= w` **by
  construction** (build to fit; do not rely on Scene truncation to save you).

## Commands you will need

| Purpose   | Command                                                   | Expected  |
|-----------|-----------------------------------------------------------|-----------|
| Tests (focus) | `python -m pytest -q tests/test_dashboard.py`         | pass      |
| Tests (all)   | `python -m pytest -q`                                 | all pass  |
| Lint      | `ruff check token_oracle tests`                           | exit 0    |
| Format    | `ruff format --check token_oracle tests`                  | exit 0    |
| Types     | `python -m mypy token_oracle --ignore-missing-imports`    | 0 errors  |

Confirm worktree code with
`python -c "import token_oracle, os; print(os.path.dirname(token_oracle.__file__))"`
(prefix `PYTHONPATH="$PWD"` if needed). Do NOT `pip install -e`.

## Scope

**In scope**:
- `token_oracle/dashboard/app.py`
- `tests/test_dashboard.py`

**Out of scope** (do NOT touch):
- `token_oracle/dashboard/scene.py`, `token_oracle/cli/colors.py` — unchanged.
- `token_oracle/core/**`, `token_oracle/live/**` — no data-path change; this is
  display only. The pct values and cells are consumed as-is.
- The boxed layouts (`_render_profile_block`, `_panels_arrangement`) and the
  width sweep from 052 — do NOT regress them; the 052 tests must still pass.

## Git workflow

- Branch: `advisor/056-low-width-triage` (worktree already on it).
- One commit per step (2-3 commits). Conventional messages, e.g.
  `feat(dash): priority-order + fit the compact line to width`.
- Do NOT push or merge.

## Steps

### Step 1: A width-budget join helper

Add near the other helpers in `app.py`:

```python
def _fit_join(prefix: str, items: list[str], width: int, sep: str = " · ") -> str:
    """Return `prefix` + as many `items` (in order) as fit within `width` display
    cells, joined by `sep`. Never emits a trailing separator; never exceeds
    `width`. `prefix` and `items` may already contain ANSI (measured by
    display_width). If not even the first item fits after the prefix, returns the
    prefix trimmed to width (caller orders items so items[0] is most important)."""
    from ..cli.colors import display_width
    if not items:
        return prefix
    out = prefix
    used = display_width(prefix)
    first = True
    for it in items:
        add = (0 if first else display_width(sep)) + display_width(it)
        if used + add > width:
            break
        out = out + ("" if first else sep) + it
        used += add
        first = False
    return out
```

**Verify**: `python -c "from token_oracle.dashboard.app import _fit_join; print(repr(_fit_join('P: ', ['aaa','bbb','ccc'], 8)))"` → `'P: aaa'` (only the first item fits in 8 cells; no trailing sep).

### Step 2: Priority-order + fit the compact line

Rewrite `_compact_profile_line` to take `width`, order windows by pct DESC, format
pct-first, color the binding (top) item with its gauge tier, and fit to width:

```python
def _compact_profile_line(pname, forecasts, now, enabled, cells=None, width=80) -> str:
    cells = cells or {}
    p_canon = "grok" if "grok" in pname.lower() else "claude"
    icon = _profile_icon(pname)
    rows = []  # (pct, short)
    for f in forecasts:
        ww = (f.window or "").lower()
        if bool(getattr(f, "idle", False)):
            continue
        is_5h = "5h" in ww or "session" in ww or "current" in ww
        if is_5h:
            pct = (100.0 * f.used / f.cap) if getattr(f, "cap", 0) else 0.0
            short = "5h"
        else:
            wkey = "weekly" if ww in ("weekly", "week") else ("fable" if ww == "fable" else None)
            cell = cells.get((p_canon, wkey)) if wkey else None
            pct = cell.pct if (cell and cell.pct is not None) else f.projected_pct
            short = "wk" if ww in ("weekly", "week") else (ww or "?")
        rows.append((float(pct), short))
    prefix = c.dim(f"{icon} {pname.lower()}  ", enabled)
    if not rows:
        return c.dim(f"{icon} {pname.lower()}  idle", enabled)
    rows.sort(key=lambda r: r[0], reverse=True)              # binding (highest %) first
    items = []
    for i, (pct, short) in enumerate(rows):
        text = f"{round(pct)}% {short}"
        # make the single most-critical item pop with its gauge color
        items.append(c.gauge(text, pct, enabled) if i == 0 else c.dim(text, enabled))
    return _fit_join(prefix, items, width)
```

Update `compact_fill()` to pass `w`:
```python
    def compact_fill() -> list[str]:
        if not groups:
            return [c.dim("(no data)", enabled)]
        return [_compact_profile_line(pn, groups[pn], now, enabled, cells, w) for pn in sorted(groups)]
```

Key behavior: because items are ordered high→low and `_fit_join` drops from the
END, the binding window is the LAST thing to be dropped, and a narrow line
degrades to just `✳ claude  99% fable` (or, if even that overflows, the prefix).
No dangling `· `.

**Verify**: `python -m pytest -q tests/test_dashboard.py` (existing pass; new
tests added in Step 4). Manual:
```
python -c "
from types import SimpleNamespace as NS
from token_oracle.dashboard import app
from token_oracle.cli import colors as c
fs=[NS(profile='claude',window='5h',used=1140000,cap=57000000,projected_pct=2.0,reset_in_secs=7200,eta_to_cap_secs=None,idle=False),
    NS(profile='claude',window='fable',used=5940000,cap=6000000,projected_pct=99.0,reset_in_secs=7200,eta_to_cap_secs=None,idle=False),
    NS(profile='claude',window='weekly',used=90000000,cap=270000000,projected_pct=33.0,reset_in_secs=7200,eta_to_cap_secs=None,idle=False)]
import re
for W in (40,24,16,12):
    line=app._compact_profile_line('claude', fs, 100000.0, True, {}, W)
    plain=re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]','',line)
    print(W, c.display_width(line)<=W, '99%' in plain, repr(plain))
"
```
→ each row: `True True ...` (fits width AND the binding `99%` present), and no
trailing `· `.

### Step 3: Add a single-line `glance` floor to the ladder

Add a `glance_fill()` inside `render_frame` (after `compact_fill`): one line, the
binding (highest-%) window per provider, gauge-colored, fit to width, prefixed
with 🔮:

```python
    def glance_fill() -> list[str]:
        if not groups:
            return [c.dim(f"{c.M_ORACLE} token-oracle  (no data)", enabled)]
        items = []
        for pn in sorted(groups):
            best = None  # (pct, short)
            p_canon = "grok" if "grok" in pn.lower() else "claude"
            for f in groups[pn]:
                if bool(getattr(f, "idle", False)):
                    continue
                ww = (f.window or "").lower()
                if "5h" in ww or "session" in ww or "current" in ww:
                    pct = (100.0 * f.used / f.cap) if getattr(f, "cap", 0) else 0.0
                    short = "5h"
                else:
                    wkey = "weekly" if ww in ("weekly", "week") else ("fable" if ww == "fable" else None)
                    cell = cells.get((p_canon, wkey)) if wkey else None
                    pct = cell.pct if (cell and cell.pct is not None) else f.projected_pct
                    short = "wk" if ww in ("weekly", "week") else (ww or "?")
                if best is None or float(pct) > best[0]:
                    best = (float(pct), short)
            if best is not None:
                items.append(c.gauge(f"{best[1]} {round(best[0])}%", best[0], enabled))
        prefix = c.violet(f"{c.M_ORACLE} ", enabled)
        return [_fit_join(prefix, items, w)]
```

Insert a `glance` level BETWEEN `oneline` and `tiny` in `_regions_for` and in the
selection tuple:
```python
    if level == "glance":
        return [Region("glance", 1, glance_fill)]
    ...
    for level in ("full", "meta", "heads", "oneline", "glance", "tiny"):
```
`glance` is a single 1-row region (self-labeled by 🔮), so it fits any terminal
with ≥1 row and is chosen before the header-only `tiny` fallback.

**Verify**: `python -m pytest -q tests/test_dashboard.py`. Manual: render at a
1-row height and confirm one 🔮 line whose display_width ≤ w and that contains the
highest-% window (see Step 4 test).

### Step 4: Tests (the regression guards)

Add to `tests/test_dashboard.py` (reuse the existing `Forecast`/`render_frame`
fixture style; build a claude profile with 5h=2%, weekly=33%, fable=99%):

- `test_compact_line_orders_binding_first`: `_compact_profile_line(..., width=200)`
  → in the plain (ANSI-stripped) text, `99%` appears before `33%` appears before
  `2%` (highest-% leads).
- `test_compact_line_fits_and_keeps_binding`: for `W in (40,32,24,20,16,12,10)`,
  `c.display_width(line) <= W` AND `"99%"` is present (binding never dropped) AND
  the line does not end with `"· "` or `"·"`.
- `test_glance_level_used_when_one_row`: `render_frame(fs, now, color=True,
  size=os.terminal_size((30, 1)))` → exactly the lines that fit 1 row; the (only)
  line starts with the 🔮 glyph, `display_width <= 30`, and contains `99%`.
- `test_glance_before_tiny`: at `size=(24, 1)` the frame is the glance line (not
  the header-only tiny) — assert the 🔮 line with a `%` number is present.
- `test_compact_no_dangling_separator`: at several widths, no rendered compact/
  glance line ends with a separator or has `"·  ·"`/`" · "` at the very end.

Also confirm 052 is not regressed: the existing width-sweep test still passes.

**Verify**: `python -m pytest -q tests/test_dashboard.py` → all pass incl. new;
then `python -m pytest -q` (full).

## Test plan

- New tests (all `tests/test_dashboard.py`): binding-first ordering, fits-and-
  keeps-binding across widths, glance-at-one-row, glance-before-tiny, no-dangling-
  separator.
- Structural pattern: existing `render_frame`/compact tests in the same file.
- Verification: `python -m pytest -q` → all pass; 052 width-sweep still green.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `python -m pytest -q` exits 0; ≥5 new tests exist and pass.
- [ ] `_fit_join` sanity (Step 1) and the compact manual check (Step 2) print the expected `True`s.
- [ ] The 052 width-sweep test (`display_width(line) <= W` for all lines/widths) still passes unchanged.
- [ ] `ruff check token_oracle tests` = 0; `ruff format --check token_oracle tests` = 0; `python -m mypy token_oracle --ignore-missing-imports` = 0 errors.
- [ ] `git diff --name-only 9df923b..HEAD` lists ONLY `token_oracle/dashboard/app.py` and `tests/test_dashboard.py`.
- [ ] `render_frame(..., size=None)` output unchanged for the default shape (spot-check: the existing `test_size_none_unchanged` from 052 still passes).
- [ ] `plans/README.md` status row for 056 updated.

## STOP conditions

Stop and report if:

- The "Current state" excerpts don't match live code (drift since `9df923b`).
- A compact/glance line cannot be made `<= w` while still containing the binding
  `%` at some width ≥ ~10 cells (report the width; do not silently drop the
  binding number — that defeats the whole plan).
- Adding the `glance` level breaks the fixed-height contract (frame line count ≠
  sum of region heights) or regresses the 052 width-sweep — STOP.

## Maintenance notes

- "Most important" = highest current %. If a future need is "5h first" instead,
  change only the sort key in `_compact_profile_line`/`glance_fill`.
- `_fit_join` is the shared width-budget primitive; reuse it for any future
  narrow line rather than re-truncating.
- Deferred (not in this plan): trimming the 2-row header (banner + status chip)
  at narrow levels to reclaim rows — the glance floor already covers the tiny-
  screen case, and touching header height complicates the fixed-region model.
- Reviewer: confirm the binding number survives at every tested width and that
  the gauge color makes it stand out; confirm no dangling separators.
