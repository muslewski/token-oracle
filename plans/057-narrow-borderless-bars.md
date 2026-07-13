# Plan 057: Borderless slider bars for narrow terminals (keep the bars, don't fall to text)

> **Executor instructions**: Implement this plan EXACTLY, step by step. The design
> + root cause are already worked out by the advisor (systematic-debugging pass,
> reproduced, and the renderer PROTOTYPED against the real helpers — the code
> below is validated, do NOT redesign it). Run every "Verify" command and confirm
> its expected result before the next step. Honor the STOP conditions. A reviewer
> maintains `plans/README.md` — do NOT edit it.
>
> **Drift check (run first)**:
> `git diff --stat b6bf30e..HEAD -- token_oracle/dashboard/app.py`
> If `app.py` changed since this plan was written, compare the "Current state"
> excerpts against the live code before proceeding; on a mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MEDIUM (touches the fixed-height contract: panel_height and panels_fill must agree)
- **Depends on**: none (follow-up to 052/056, both merged)
- **Category**: feature / UX
- **Planned at**: commit `b6bf30e`, 2026-07-13

## Why this matters

The user likes the slider bars. Today, at any terminal width below `MIN_BOX`
(34 cells) the panels collapse from bordered sliders straight to a plain-text
compact line (`✳ claude  33% wk · 2% 5h`) — the bars vanish. The user reports
this as "worse than before": they want the **bars to shrink and survive**, not be
replaced by text. Chosen style (confirmed): **borderless bars, labeled** — a
provider header plus one `label pct% bar` row per window, no box frame.

Reproduced: at tall height + width 16–33 the dashboard shows the text line
instead of bars. Above 34 the bordered box already shrinks its bar gracefully
(22→8 cells) — this plan extends that graceful shrink below 34 by dropping the
box chrome and keeping just the bar.

## Current state

`token_oracle/dashboard/app.py`.

Constants (lines 31-34):
```python
BAR_W = 22  # default/maximum gauge width
BAR_W_MIN = 6  # narrowest legible gauge
MIN_BOX = 34  # min box width that still fits "glyph name pct bar reset"
BOX_MAX = 66  # widest stacked box (unchanged from today)
```

`_panels_arrangement` (lines 130-147) returns `(mode, box_w, bar_w)` with mode in
`side`/`stack`/`oneline`:
```python
def _panels_arrangement(groups: dict, w: int):
    pnames = list(groups.keys())
    two_equal = len(pnames) == 2 and len(groups[pnames[0]]) == len(groups[pnames[1]])
    if two_equal and w >= 2 * MIN_BOX + 3:
        box_w = _clamp((w - 3) // 2, MIN_BOX, 60)
        return "side", box_w, _bar_w_for(box_w)
    if w >= MIN_BOX:
        box_w = _clamp(w, MIN_BOX, BOX_MAX)
        return "stack", box_w, _bar_w_for(box_w)
    return "oneline", w, BAR_W_MIN
```

`panel_height` (lines 150-169):
```python
def panel_height(groups: dict, detail: int = 2, w: int = 999) -> int:
    if not groups:
        return _panel_block_height(1, detail)  # (no data) padded block
    mode, _bw, _barw = _panels_arrangement(groups, w)
    if mode == "oneline":
        return len(groups)  # one compact line per profile
    if mode == "side":
        n = len(groups[list(groups.keys())[0]])
        return _panel_block_height(n, detail)
    total = 0  # stack
    for _pn, fs in groups.items():
        total += _panel_block_height(len(fs) or 1, detail)
        total += 1  # inter-block gap line
    return total
```

`panels_fill` inside `render_frame` (around lines 491-546) has a `side` branch, a
`stack` branch, and an `else` that returns `compact_fill()` for `oneline`. The
relevant tail:
```python
        elif mode == "stack":
            for pn in sorted(pnames):
                blk = _render_profile_block(
                    pn, groups[pn], now, enabled, cells,
                    width=box_w, detail=detail, anim_pct=anim_pct, pulse=pulse, bar_w=bar_w,
                )
                out.extend(blk)
                out.append("")
        else:
            # oneline (width too narrow for any box)
            return compact_fill()
        return out
```

Helpers to REUSE (do not modify): `_bar(pct, enabled, width)` (sub-cell gauge,
always exactly `width` cells), `_profile_icon(pname)`, `_clamp(v, lo, hi)`,
`c.violet`, `c.dim`, `c.gauge` (from `token_oracle.cli.colors as c`).

Convention: stdlib only. Every produced line must satisfy
`colors.display_width(line) <= w` BY CONSTRUCTION. `render_frame(size=None)` must
stay byte-identical (it renders at w=80 → `stack`/`side`, never `bars`, so it is
unaffected — do not special-case it).

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Import path | `python -c "import token_oracle,os;print(os.path.dirname(token_oracle.__file__))"` | path UNDER this worktree (else prefix `PYTHONPATH="$PWD"`) |
| Tests (focus) | `python -m pytest -q tests/test_dashboard.py` | all pass |
| Tests (all) | `python -m pytest -q` | all pass |
| Lint | `ruff check token_oracle tests` | exit 0 |
| Format | `ruff format --check token_oracle tests` | exit 0 |
| Types | `python -m mypy token_oracle --ignore-missing-imports` | 0 errors (notes OK) |

Do NOT `pip install -e`. Set `TOKEN_ORACLE_SKIP_BOOTSTRAP=1` for direct python invocations.

## Scope

**In scope** (only these two files):
- `token_oracle/dashboard/app.py`
- `tests/test_dashboard.py`

**Out of scope** (do NOT touch): anything under `token_oracle/core/`,
`token_oracle/live/`, `token_oracle/cli/`, `token_oracle/dashboard/scene.py`,
`plans/README.md`. Do NOT change `_render_profile_block`, `_bar`,
`_compact_profile_line`, `glance_fill`, or the height ladder / level tuple.

## Git workflow

- Branch: `advisor/057-narrow-bars` (worktree already on it).
- One commit per step (3 commits). Conventional messages.
- Do NOT push or merge.

## Steps

### Step 1: Add `BARS_MIN` + `_bars_bar_w_for`

After the `BOX_MAX = 66` line, add the constant:
```python
BARS_MIN = 16  # min width for borderless slider bars (below this -> compact text)
```

After `_bar_w_for` (the function ending `return _clamp(box_w - 26, BAR_W_MIN, BAR_W)`),
add:
```python
def _bars_bar_w_for(w: int) -> int:
    """Gauge width for a borderless bar row. The row prefix spends 13 cells on
    '  {label:<5} {pct:>4} '; the rest is the bar, clamped to a legible minimum
    so the % (which precedes the bar) always survives."""
    return _clamp(w - 13, 3, BAR_W)
```

**Verify**:
```
python -c "from token_oracle.dashboard.app import _bars_bar_w_for as b; print([b(w) for w in (33,30,24,20,16)])"
```
→ `[20, 17, 11, 7, 3]`

### Step 2: Add the `_render_profile_bars` renderer

Add this module-level function immediately BEFORE `def _row_glyph(` (i.e. right
after `_compact_profile_line`):
```python
def _render_profile_bars(pname, forecasts, now, enabled, cells, w, bar_w):
    """Borderless slider rows for narrow terminals (BARS_MIN <= w < MIN_BOX):
    a provider header line + one `label pct% bar` row per window. The number
    precedes the bar (pct-first) so it survives truncation; the bar is exactly
    `bar_w` cells so each row is exactly `w` cells. No box, no provenance, no
    glide animation (narrow fallback shows the true pct directly). Source blend
    matches the box: 5h from local logs, caps from the web cell else local proj."""
    cells = cells or {}
    p_canon = "grok" if "grok" in pname.lower() else "claude"
    icon = _profile_icon(pname)
    out = [c.violet(f"{icon} {pname.lower()}", enabled)]
    for f in sorted(forecasts, key=lambda x: x.window):
        ww = (f.window or "").lower()
        is_5h = "5h" in ww or "session" in ww or "current" in ww
        label = "5h" if is_5h else ("wk" if ww in ("weekly", "week") else (ww or "?"))
        label = label[:5].ljust(5)
        if bool(getattr(f, "idle", False)):
            out.append(c.dim(f"  {label} idle", enabled))
            continue
        if is_5h:
            pct = (100.0 * f.used / f.cap) if getattr(f, "cap", 0) else 0.0
        else:
            wkey = "weekly" if ww in ("weekly", "week") else ("fable" if ww == "fable" else None)
            cell = cells.get((p_canon, wkey)) if wkey else None
            pct = cell.pct if (cell and cell.pct is not None) else f.projected_pct
        pct = float(pct)
        pct_str = c.gauge(f"{round(pct)}%".rjust(4), pct, enabled)
        if enabled:
            pct_str = f"\033[1m{pct_str}\033[0m"
        bar = _bar(pct, enabled, bar_w)
        out.append(f"  {label} {pct_str} {bar}")
    return out
```

**Verify (fits + pct-first, no color)**:
```
python - <<'PY'
from token_oracle.cli.colors import display_width
from token_oracle.core.contracts import Forecast
from token_oracle.dashboard.app import _render_profile_bars, _bars_bar_w_for
fs = [Forecast("5h",20,1000,2.0,None,3600.0,False,profile="claude"),
      Forecast("weekly",3300000,10000000,33.0,None,400000.0,False,profile="claude")]
for W in (33,30,24,20,16):
    rows = _render_profile_bars("claude", fs, 100000.0, False, {}, W, _bars_bar_w_for(W))
    bar_rows = rows[1:]  # skip header
    print(W, all(display_width(r)==W for r in bar_rows), rows)
PY
```
→ first token each line is the width, then `True`, then the rows (header `✳ claude`,
then `  5h      2% …` / `  wk     33% …`). Every bar row's display_width == W.

### Step 3: Wire `bars` into arrangement, height, and fill

**3a.** In `_panels_arrangement`, insert a `bars` branch BETWEEN the `stack`
branch and the final `oneline` return:
```python
    if w >= MIN_BOX:
        box_w = _clamp(w, MIN_BOX, BOX_MAX)
        return "stack", box_w, _bar_w_for(box_w)
    if w >= BARS_MIN:
        return "bars", w, _bars_bar_w_for(w)
    return "oneline", w, BAR_W_MIN
```

**3b.** In `panel_height`, add a `bars` branch. Place it right after the
`if mode == "oneline":` block (before the `side` block):
```python
    if mode == "oneline":
        return len(groups)  # one compact line per profile
    if mode == "bars":
        # header (1) + one row per window + inter-block gap (1), per provider
        return sum(1 + (len(fs) or 1) + 1 for fs in groups.values())
    if mode == "side":
```

**3c.** In `panels_fill` (inside `render_frame`), add a `bars` branch before the
final `else`/`oneline`:
```python
        elif mode == "bars":
            for pn in sorted(pnames):
                out.extend(
                    _render_profile_bars(pn, groups[pn], now, enabled, cells, box_w, bar_w)
                )
                out.append("")
        else:
            # oneline (width too narrow for even a minimal bar)
            return compact_fill()
        return out
```
(`box_w` in bars mode equals `w`; `bar_w` is `_bars_bar_w_for(w)` — both come from
the `mode, box_w, bar_w = _panels_arrangement(...)` line already at the top of
`panels_fill`.)

**Verify (arrangement + fixed-height contract)**:
```
python - <<'PY'
import os
from token_oracle.cli.colors import display_width
from token_oracle.core.contracts import Forecast
from token_oracle.dashboard.app import render_frame, panel_height, _panels_arrangement
fs = [Forecast("5h",20,1000,2.0,None,3600.0,False,profile="claude"),
      Forecast("weekly",3300000,10000000,33.0,None,400000.0,False,profile="claude"),
      Forecast("5h",990,1000,99.0,None,3600.0,False,profile="fable")]
groups={}
for f in fs: groups.setdefault(f.profile,[]).append(f)
for W in (30,24,16):
    mode,bw,barw=_panels_arrangement(groups,W)
    frame=render_frame(fs,100000.0,color=False,size=os.terminal_size((W,40)))
    fits=all(display_width(l)<=W for l in frame)
    has_bar=any(any(ch in l for ch in "█░") for l in frame)
    has_box=any(any(ch in l for ch in "┌│└") for l in frame)
    has99=any("99%" in l for l in frame)
    print(f"W={W} mode={mode} fits={fits} has_bar={has_bar} has_box={has_box} has99={has99} ph={panel_height(groups,2,W)}")
PY
```
→ each line: `mode=bars fits=True has_bar=True has_box=False has99=True`.

### Step 4: Tests

Add to `tests/test_dashboard.py` (reuse `_two_profile_two_window_fs` /
`_claude_binding_fs` if present, else build inline with `Forecast`):

- `test_bars_mode_between_box_and_oneline`: for W in (33, 30, 24, 18), the frame
  has bar glyphs (`█` or `░`), NO box chars (`┌│└`), and NO `·` compact joiner.
- `test_bars_rows_fit_and_keep_number`: for W in (33, 24, 16), every rendered line
  `display_width <= W`, and the binding `99%` is present.
- `test_bars_height_matches_fill`: for W in (30, 20, 16), the number of non-empty
  + empty panel lines produced equals `panel_height(groups, 2, W)` (fixed-height
  contract). Concretely: build `groups`, call
  `render_frame(..., size=os.terminal_size((W, 40)))`, and assert the panels
  region height is what `panel_height` predicts. (Simplest robust check: assert
  `panel_height(groups, 2, W) == panel_height(groups, 0, W)` — bars ignore detail
  — AND that a full render at that width contains both providers' headers and all
  their window labels.)
- `test_bars_show_all_windows_labeled`: at W=24, claude's block shows both `5h`
  and `wk` rows and a `claude` header; fable shows `5h` and a `fable` header.
- **Update `test_arrangement_collapses_with_width`**: the existing W=30 assertion
  expects "no box chars AND has `·`". That is now WRONG (W=30 renders bars). Change
  the very-narrow assertion to W=**14** for the `·` compact line
  (`has_compact = any("·" in ln ...)`), and add a W=**24** assertion that there are
  NO box chars but there ARE bar glyphs (`█`/`░`) and NO `·`.

**Verify**: `python -m pytest -q tests/test_dashboard.py` → all pass (existing +
≥4 new). Then full suite `python -m pytest -q`.

## Test plan

- New tests above in `tests/test_dashboard.py` (model after the existing
  `test_no_line_exceeds_terminal_width_at_any_width` / `test_arrangement_collapses_with_width`).
- The 052 width-sweep (`test_no_line_exceeds_terminal_width_at_any_width`, W down
  to 16) must STILL pass — bars build to fit, so it holds.
- `test_size_none_unchanged` must STILL pass unchanged (size=None → w=80 → stack).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] Step 1 verify prints `[20, 17, 11, 7, 3]`.
- [ ] Step 3 verify prints `mode=bars fits=True has_bar=True has_box=False has99=True` for W=30/24/16.
- [ ] `python -m pytest -q` exits 0; ≥4 new tests pass; `test_arrangement_collapses_with_width` updated and green; `test_size_none_unchanged` green; 052 width-sweep green.
- [ ] `ruff check token_oracle tests` = 0; `ruff format --check token_oracle tests` = 0; `python -m mypy token_oracle --ignore-missing-imports` = 0 errors.
- [ ] `git diff --name-only b6bf30e..HEAD` lists ONLY `token_oracle/dashboard/app.py` and `tests/test_dashboard.py`.

## STOP conditions

Stop and report if:
- The "Current state" excerpts don't match live code (drift).
- After wiring, `panel_height(groups, 2, w)` ever disagrees with the actual number
  of panel lines `panels_fill` emits in bars mode (fixed-height contract broken) —
  report the failing width rather than padding around it.
- Any bars row's `display_width` exceeds `w` at any width in [BARS_MIN, MIN_BOX)
  — report the failing case; the bar-width math must make every row exactly `w`.
- The 052 width-sweep or `test_size_none_unchanged` regresses.

## Maintenance notes

- Three width regimes now: bordered box (`w >= MIN_BOX`), borderless bars
  (`BARS_MIN <= w < MIN_BOX`), compact text (`w < BARS_MIN`, then glance/tiny by
  height). `_panels_arrangement` is the single source of truth; `panel_height` and
  `panels_fill` both branch on its `mode` — keep them in lockstep.
- Bars mode deliberately does NOT animate (no anim_pct/pulse plumbing) — the glide
  is a full-view nicety; the narrow fallback shows truth directly. If animation is
  wanted later, thread `anim_pct`/`pulse` like `_render_profile_block` does.
- Reviewer: confirm every bars row is exactly `w` cells, the `%` precedes the bar,
  and panel_height matches the emitted line count.
