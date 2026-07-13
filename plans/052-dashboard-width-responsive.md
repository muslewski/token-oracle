# Plan 052: The dashboard adapts to terminal WIDTH (no color/layout break when narrow)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` (a reviewer maintains the index — still flip your row).
>
> **Drift check (run first)**:
> `git diff --stat 5de6aac..HEAD -- token_oracle/dashboard/app.py token_oracle/dashboard/scene.py token_oracle/cli/colors.py tests/test_dashboard.py tests/test_scene.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED (layout code; fully guarded by a width-sweep test)
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `5de6aac`, 2026-07-13

## Why this matters

The dashboard is responsive in HEIGHT (it drops detail as the terminal gets
shorter) but **not in WIDTH**. Box widths are hardcoded: side-by-side panels are
`60 + 3 + 60 = 123` columns, stacked panels are `66`, and the gauge bar is a
fixed `22`. When the terminal is narrower than the composed layout, every panel
line overflows and `Scene.render` "handles" it by `strip_ansi(line)[:width]` —
which **drops all color and hard-cuts through the middle of a box**. The header
and footer are short, so they keep their color. The result a user sees when they
shrink the window: a colored header on top of colorless, chopped, misaligned
panels — "the color breaks and everything breaks."

This was reproduced deterministically (see "Current state"). After this plan the
dashboard picks a layout that FITS the width — side-by-side → stacked → one-line
→ tiny — so it stays clean and colored in an 80-column terminal, a 60-column
split pane, and a 40-column phone SSH session.

## Current state

Reproduction (confirmed): render a real two-profile frame at descending widths
and count panel lines that lost their color.

```
W=140 | colored_lines=13 | panel_lines_color_STRIPPED=0   ← fine
W=123 | colored_lines=13 | panel_lines_color_STRIPPED=0   ← fine (exact fit)
W=120 | colored_lines= 6 | panel_lines_color_STRIPPED=6   ← BREAKS here
W= 80 | colored_lines= 6 | panel_lines_color_STRIPPED=6
W= 40 | colored_lines= 4 | panel_lines_color_STRIPPED=6   ← still 15 lines of butchered 123-wide layout
```

Breakage starts the instant width < 123 (the composed side-by-side width). At
W=40 the frame is STILL the 15-line side-by-side structure — the layout never
collapses, because level selection ignores width.

Relevant files:

- `token_oracle/dashboard/app.py` — the dashboard renderer. The bug lives here:
  - `BAR_W = 22` (line 31) — fixed gauge width.
  - `_bar(pct, enabled, width=BAR_W)` (lines 37-50) — builds the gauge string; `width` is a parameter but always called with the constant `BAR_W`.
  - `_render_profile_block(pname, forecasts, now, enabled, cells=None, width=66, detail=2, ...)` (lines 207-355) — renders one boxed panel at a FIXED `width`. The head line is built at line 315:
    ```python
    head = f"{glyph} {wname:<6} {pct_str} {bar} {reset_str}"
    ```
  - `panel_height(groups, detail=2)` (lines 87-105) — decides side-by-side vs stacked **by profile count only** (`len(pnames) == 2 and equal window counts`), never by width, and returns the region height.
  - `render_frame(...)` width handling (lines 387-391):
    ```python
    if size is not None and hasattr(size, "columns"):
        w = max(40, int(getattr(size, "columns", 80)))
    else:
        w = 80
    ```
  - `panels_fill(detail=2)` (lines 442-490) — the ACTUAL layout. Side-by-side calls `_render_profile_block(..., width=60, ...)` twice and joins with `"   "` (3 spaces); stacked calls it with `width=66`:
    ```python
    if len(pnames) == 2 and len(groups[pnames[0]]) == len(groups[pnames[1]]):
        left  = _render_profile_block(pnames[0], ..., width=60, detail=detail, ...)
        right = _render_profile_block(pnames[1], ..., width=60, detail=detail, ...)
        ...
        for lline, rline in zip(left, right, strict=False):
            out.append(lline + "   " + rline)     # 60 + 3 + 60 = 123 wide
    else:
        for pn in sorted(pnames):
            blk = _render_profile_block(pn, ..., width=66, detail=detail, ...)
    ```
  - `compact_fill()` (lines 492-495) — already produces a one-line-per-profile layout via `_compact_profile_line` (lines 108-131). Currently only reachable via the `oneline` HEIGHT level.
  - The height ladder (lines 511-558): `_regions_for(level)` builds regions per level; the selection loop chooses a level by HEIGHT only:
    ```python
    avail_h = int(getattr(size, "lines", 0) or 0) if size is not None else 0
    for level in ("full", "meta", "heads", "oneline", "tiny"):
        regs = _regions_for(level)
        total = sum(r.height for r in regs)
        if avail_h == 0 or total <= avail_h:
            out = Scene(regs).render(w)
            return out[:avail_h] if avail_h else out
    ```
    Note `avail_h == 0` (tests / no size) => always picks `full` and returns it whole. **This behavior for `size=None` MUST be preserved** (many tests depend on it).

- `token_oracle/dashboard/scene.py` — the fixed-region compositor. The destructive truncation:
  - `strip_ansi(s)` (lines 16-18) and `visible_len(s) = len(strip_ansi(s))` (lines 21-23) — scene's own width measure is a **raw character count**, NOT terminal-cell aware.
  - `Scene.render(width)` (lines 50-63):
    ```python
    for ln in lines:
        if visible_len(ln) > width:
            # drop styling for over-width lines (simplest correct truncation)
            ln = strip_ansi(ln)[:width]
        out.append(ln)
    ```
    This is what strips color + chops boxes. It also uses the char-count `visible_len`, which disagrees with the cell-aware measure the boxes are padded with (see below) — so for any line containing wide glyphs (emoji), the clip can leave a line still wider than the terminal → it wraps → the Painter's fixed-height in-place repaint corrupts.

- `token_oracle/cli/colors.py` — the CELL-aware width helpers the boxes already use:
  - `display_width(s)` (lines 127-131) — terminal cells, ignoring ANSI, counting emoji/CJK as 2. THIS is the correct measure.
  - `box_top / box_bot / box_line` (lines 139-164) — `box_line` pads/truncates using `display_width`. So the boxes are built cell-aware, but `Scene.render` clips char-count-aware. Two different rulers is the latent wrap bug.

Conventions to match:
- Stdlib only, no new deps. Pure functions where possible (this file's `render_frame` is pure and unit-tested — keep it pure).
- Height is a **type-level invariant** (see `scene.py` docstring): `render()` returns exactly `sum(region heights)` lines. Whatever arrangement you pick for a width, `panel_height` and `panels_fill` MUST agree on the SAME arrangement, or the region will over/under-produce and the frame height will be wrong. This is the single most important correctness constraint in this plan.
- Colors are applied at the render site via `token_oracle/cli/colors.py`; never hand-write `\033[` codes in `app.py` beyond what already exists.

## Commands you will need

| Purpose   | Command                                                   | Expected on success        |
|-----------|-----------------------------------------------------------|----------------------------|
| Tests (all)   | `python -m pytest -q`                                 | all pass                   |
| Tests (focus) | `python -m pytest -q tests/test_dashboard.py tests/test_scene.py` | all pass       |
| Lint      | `ruff check token_oracle tests`                           | exit 0                     |
| Format    | `ruff format --check token_oracle tests`                  | exit 0                     |
| Types     | `python -m mypy token_oracle --ignore-missing-imports`    | 0 errors                   |
| Confirm worktree code | `python -c "import token_oracle, os; print(os.path.dirname(token_oracle.__file__))"` | a path UNDER this worktree |

If the import check does not print a path under this worktree, prefix python
commands with `PYTHONPATH="$PWD"`. Do NOT run `pip install -e`.

## Scope

**In scope** (the only files you should modify):
- `token_oracle/dashboard/app.py`
- `token_oracle/dashboard/scene.py`
- `tests/test_dashboard.py` (add tests)
- `tests/test_scene.py` (add tests)

**Out of scope** (do NOT touch, even though they look related):
- `token_oracle/cli/colors.py` — its `display_width` is already correct; import and USE it, do not modify it.
- Anything under `token_oracle/core/`, `token_oracle/live/`, `token_oracle/sources/` — this is a pure display fix; no data path changes.
- The 5h/weekly NUMBERS or their provenance wording — only the geometry changes.
- `LIVE_PROBE_INTERVAL`, the probe worker, animation/pulse logic — untouched.

## Git workflow

- Branch: `advisor/052-width-responsive` (the worktree is already on it).
- One commit per step (4 commits). Message style: conventional commits, e.g.
  `fix(dash): derive panel width + arrangement from terminal width`.
  Example from `git log`: `feat(core): pricing snapshot + cost modes + plan presets`.
- Do NOT push or open a PR.

## Steps

### Step 1: Make the gauge bar and one panel block width-parametric

Goal: a single profile block can render at any box width with a proportional bar,
without changing today's output at the default sizes.

1. `_bar` already takes `width`; keep it. Add a small clamp helper near the top of
   `app.py` (after `BAR_W = 22`):
   ```python
   BAR_W = 22          # default/maximum gauge width
   BAR_W_MIN = 6       # narrowest legible gauge
   MIN_BOX = 34        # min box width that still fits "glyph name pct bar reset"
   BOX_MAX = 66        # widest stacked box (unchanged from today)

   def _clamp(v, lo, hi):
       return max(lo, min(hi, v))

   def _bar_w_for(box_w: int) -> int:
       """Gauge width derived from the box's inner width. The head line spends
       ~26 cells on 'glyph name<6> pct<4> reset<~7>' plus spacing; the rest is
       the bar, clamped to a legible range."""
       return _clamp(box_w - 26, BAR_W_MIN, BAR_W)
   ```
2. Add a `bar_w` parameter to `_render_profile_block`:
   `def _render_profile_block(pname, forecasts, now, enabled, cells=None, width=66, detail=2, anim_pct=None, pulse=None, bar_w=BAR_W):`
   and change the two bar constructions inside it (currently `bar = _bar(bar_pct, enabled, BAR_W)` at line 304) to use `bar_w`:
   `bar = _bar(bar_pct, enabled, bar_w)`.
   Do NOT change any other line in that function. `box_line`/`box_top`/`box_bot`
   already respect the passed `width`.

**Verify**: `python -m pytest -q tests/test_dashboard.py` → all pass (no behavior
change yet; defaults preserve today's output).

### Step 2: A single source of truth for arrangement, shared by height and content

This is the core of the fix. Both `panel_height` and `panels_fill` must decide
the SAME arrangement for a given width, or the fixed-height contract breaks.

1. Add a helper that both call:
   ```python
   def _panels_arrangement(groups: dict, w: int):
       """Decide how panels lay out for terminal width `w`.

       Returns (mode, box_w, bar_w):
         mode "side"    -> two boxes side by side, each box_w wide, joined by 3 spaces
         mode "stack"   -> one box_w-wide box per profile, stacked
         mode "oneline" -> compact one line per profile (no boxes)
       Never returns a geometry wider than `w`.
       """
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
   Notes: side-by-side per-box width is capped at 60 (today's value) so wide
   terminals look identical to today; stacked is capped at `BOX_MAX=66` (today's
   value). At exactly the old widths the output is unchanged.

2. Rewrite `panel_height` to use the arrangement AND take `w`:
   ```python
   def panel_height(groups: dict, detail: int = 2, w: int = 999) -> int:
       if not groups:
           return _panel_block_height(1, detail)
       mode, _bw, _barw = _panels_arrangement(groups, w)
       if mode == "oneline":
           return len(groups)  # one compact line per profile
       if mode == "side":
           n = len(groups[list(groups.keys())[0]])
           return _panel_block_height(n, detail)
       total = 0                      # stack
       for _pn, fs in groups.items():
           total += _panel_block_height(len(fs) or 1, detail)
           total += 1                 # inter-block gap line
       return total
   ```
   The default `w=999` preserves the old "always side-by-side when shape allows"
   behavior for any caller that does not pass width (keeps `size=None` paths and
   existing `panel_height` unit tests stable — verify in Step 4).

3. Rewrite `panels_fill(detail)` to branch on `_panels_arrangement(groups, w)`
   (`w` is in scope inside `render_frame`). For `"side"` use `box_w`/`bar_w` from
   the arrangement instead of the literal `60`; pad each block to `box_w`
   (`left += [" " * box_w] * (maxl - len(left))`). For `"stack"` pass
   `width=box_w, bar_w=bar_w`. For `"oneline"` return `compact_fill()`.
   The height each branch produces MUST equal `panel_height(groups, detail, w)`
   from step 2 — that is the invariant to preserve.

**Verify**: add a quick inline check (temporary, remove before commit) or rely on
the Step 4 sweep test. `python -m pytest -q tests/test_dashboard.py` → all pass.

### Step 3: Make Scene truncation color-safe and cell-aware (defense in depth)

Even with Step 2, a stray wide line (e.g. a long activity log entry) can exceed
`w`. Today that path strips all color. Replace it with a truncation that keeps
color and never leaves the terminal in a colored state.

In `token_oracle/dashboard/scene.py`:
1. Import the cell-aware width from colors and add a color-preserving truncator:
   ```python
   from ..cli.colors import display_width

   _RESET = "\033[0m"

   def truncate_display(s: str, width: int) -> str:
       """Truncate to at most `width` terminal cells, keeping ANSI SGR styling
       and appending a reset so color never bleeds past the cut. Cell-aware
       (emoji/CJK = 2 cells), so the result never exceeds `width` on screen."""
       if display_width(s) <= width:
           return s
       out = []
       cells = 0
       i = 0
       had_sgr = False
       while i < len(s):
           if s[i] == "\x1b":
               m = _ANSI_RE.match(s, i)
               if m:
                   out.append(m.group(0))
                   had_sgr = True
                   i = m.end()
                   continue
           ch = s[i]
           w = display_width(ch)
           if cells + w > width:
               break
           out.append(ch)
           cells += w
           i += 1
       res = "".join(out)
       if had_sgr:
           res += _RESET
       return res
   ```
   (`_ANSI_RE` already exists at `scene.py:13`; `re.match(pattern, string, pos)`
   is not available — use `_ANSI_RE.match(s, i)` via the compiled pattern's
   `match(string, pos)` overload, which IS supported on compiled patterns.)
2. In `Scene.render`, replace the body of the overflow branch:
   ```python
   for ln in lines:
       if display_width(ln) > width:
           ln = truncate_display(ln, width)
       out.append(ln)
   ```
   Use `display_width` (imported) as the measure, not the old char-count
   `visible_len`. Keep the module-level `strip_ansi`/`visible_len` functions
   (other code/tests may import them) but stop using `visible_len` for the clip.

**Verify**: `python -m pytest -q tests/test_scene.py` → all pass.

### Step 4: Width-sweep tests (the regression guard)

Add to `tests/test_dashboard.py` (model structure after the existing frame tests
in that file — they build `Forecast`s and call `render_frame`/`render_frame_str`;
reuse their fixture/import style). Add a helper that builds a two-profile,
two-window active frame (claude 5h+weekly, grok 5h+weekly) so side-by-side is
possible, then:

- `test_no_line_exceeds_terminal_width_at_any_width`: for `W in (200,140,123,120,100,80,72,60,50,40,32,24,16)`, build `size = os.terminal_size((W, 40))`, call `render_frame(fs, now, color=True, size=size)`, and assert `colors.display_width(line) <= W` for **every** line. (This is the core assertion; it fails on today's code at W≤120.)
- `test_no_dangling_color_after_truncation`: at the same widths, assert no line contains an SGR opener (`\x1b[` … `m`) without a subsequent reset — i.e. `line.count("\x1b[0m") >= number_of_non_reset_SGR_openers`, or more simply assert every line either has no `\x1b[` or ends by re-balancing (a pragmatic check: `strip_ansi` round-trips and the rendered cell width ≤ W). Keep it simple and deterministic.
- `test_arrangement_collapses_with_width`: assert the frame is side-by-side at W=140 (a panel line contains two box borders `│ ... │ ... │ ... │` / two `┌`), stacked at W=80 (one `┌` per panel row region), and one-line/compact at W=30 (no box-drawing chars `┌│└` in the panels region; a `·`-joined compact line present).
- `test_size_none_unchanged`: `render_frame(fs, now, color=False, size=None)` returns the SAME output as before this change for the default shape (guards the `avail_h==0 => full` path). Capture the current output first and assert equality.

Also add to `tests/test_scene.py`:
- `test_truncate_display_keeps_color_and_fits`: a colored over-width string truncates to ≤ width cells AND ends with a reset; a short string is returned unchanged.

**Verify**: `python -m pytest -q tests/test_dashboard.py tests/test_scene.py` →
all pass, including the new tests. Then full suite: `python -m pytest -q`.

## Test plan

- New tests (all in `tests/test_dashboard.py` unless noted):
  `test_no_line_exceeds_terminal_width_at_any_width`,
  `test_no_dangling_color_after_truncation`,
  `test_arrangement_collapses_with_width`,
  `test_size_none_unchanged`;
  and in `tests/test_scene.py`: `test_truncate_display_keeps_color_and_fits`.
- Structural pattern: model after the existing `render_frame` tests already in
  `tests/test_dashboard.py` and the `Scene`/`Region` tests in
  `tests/test_scene.py`.
- Verification: `python -m pytest -q` → all pass, ≥5 new tests added.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `python -m pytest -q` exits 0; the 5+ new tests exist and pass.
- [ ] The width-sweep test proves `display_width(line) <= W` for every line at every swept width (this assertion FAILS on the pre-change code — confirm it does by running it before Step 2 if you like).
- [ ] `ruff check token_oracle tests` exits 0.
- [ ] `ruff format --check token_oracle tests` exits 0.
- [ ] `python -m mypy token_oracle --ignore-missing-imports` → 0 errors.
- [ ] `git diff --name-only 5de6aac..HEAD` lists ONLY the four in-scope files.
- [ ] `render_frame(..., size=None)` output is byte-identical to pre-change for the default shape (the `test_size_none_unchanged` test).
- [ ] `plans/README.md` status row for 052 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The "Current state" excerpts don't match the live code (drift since `5de6aac`).
- After Step 2, the frame height (line count) at some width does NOT equal
  `sum(region heights)` — i.e. `panel_height` and `panels_fill` disagree on
  arrangement. This is the one dangerous failure mode: do NOT paper over it by
  padding in Scene; fix the shared `_panels_arrangement` so both agree, or STOP.
- Making the sweep test pass appears to require editing `colors.py` or any
  out-of-scope file.
- `test_size_none_unchanged` cannot be made to pass without changing default-size
  output — that means a default-path regression; STOP and report.

## Maintenance notes

- Future reviewer: the invariant to scrutinize is that `panel_height(groups,
  detail, w)` and `panels_fill(detail)` derive arrangement from the SAME
  `_panels_arrangement(groups, w)` call shape. Any new layout mode must be added
  to that one helper and to both callers together.
- `MIN_BOX=34` / `BAR_W_MIN=6` / the `- 26` head-budget in `_bar_w_for` are tuned
  to the current head format `"{glyph} {wname:<6} {pct} {bar} {reset}"`. If that
  head line changes (extra field), re-tune the `26` budget or narrow terminals
  will truncate the reset time.
- Deferred out of this plan: true reflow/word-wrap of long provenance lines
  (they truncate with `…` via `box_line`, which is fine); and per-terminal
  emoji-width detection (we count emoji as 2 cells, matching most terminals).
