# Plan 055: `box_line` truncation preserves color (grey provenance text stops turning white when narrow)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on. If a
> STOP condition occurs, stop and report. When done, update the status row for
> this plan in `plans/README.md` (a reviewer maintains the index — still flip
> your row).
>
> **Drift check (run first)**:
> `git diff --stat d52d7b7..HEAD -- token_oracle/cli/colors.py tests/test_colors.py`
> If either file changed since this plan was written, compare the "Current state"
> excerpt against the live code before proceeding; on a mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW (one function; color-only behavior at truncation)
- **Depends on**: none (follow-up to 052, which is already merged)
- **Category**: bug
- **Planned at**: commit `d52d7b7`, 2026-07-13

## Why this matters

After plan 052 made the dashboard shrink its box widths to fit narrow terminals,
the grey (dim) provenance/meta lines *below* each slider turn WHITE when the
terminal is narrow. Root cause (confirmed by repro): `colors.box_line`, when the
interior text is wider than the box, truncates by **stripping all ANSI escapes**
(`_ANSI_RE.sub("", text)`) and rebuilding from plain characters — discarding the
dim color. The slider line keeps its color (the bar/% fit), so only the longer
text below overflows and loses its grey, rendering in the terminal default
(white on a dark background). This looks broken.

Reproduced deterministically: a dim string in a `box_w=40` box keeps its
`38;5;240` (dim) code; at `box_w=36`/`32` the code is gone. In a rendered frame,
every interior meta/provenance line loses its dim at W≤36.

The fix: truncate `box_line`'s interior the way `scene.truncate_display` already
does (added in 052) — keep the ANSI SGR codes, count terminal cells, append the
ellipsis, and append a reset so nothing bleeds. Grey stays grey when truncated.

## Current state

`token_oracle/cli/colors.py`, `box_line` (lines 149-164 as of `d52d7b7`):

```python
def box_line(text, width=40, enabled=True):
    # pad or truncate using *display* width so wide glyphs / colored bars align
    inner_w = width - 2
    if display_width(text) > inner_w:
        # trim character-by-character until it fits the cell budget (leaving 1 for …)
        cut = ""
        used = 0
        for ch in _ANSI_RE.sub("", text):       # <-- STRIPS ANSI: the bug
            w = _char_cells(ch)
            if used + w > inner_w - 1:
                break
            cut += ch
            used += w
        text = cut + "…"
    pad = " " * (inner_w - display_width(text))
    return f"│{text}{pad}│"
```

Helpers already in this file to reuse:
- `_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mK]")` (line 11). Compiled patterns support
  `_ANSI_RE.match(text, pos)` to match an escape at a position.
- `_char_cells(ch)` (lines 116-124) — terminal cell width of one char (0/1/2).
- `display_width(s)` (lines 127-131) — cells ignoring ANSI.
- `RESET = "\033[0m"` (line 15).

Reference for the exact pattern to mirror — `token_oracle/dashboard/scene.py`
`truncate_display` (added in plan 052): it walks the string, appends each ANSI
escape it meets (via `_ANSI_RE.match(s, i)`), counts cells for real chars, stops
at the budget, and appends `RESET` if any SGR was seen. Apply the same, but for a
box interior: leave 1 cell for the ellipsis, append `…` before the reset, then
the existing padding logic pads to `inner_w`.

Convention: stdlib only; `box_line` must still return a string of exactly
`width` display cells (`│` + inner padded to `inner_w` + `│`). The non-truncating
path (short text) must stay byte-identical.

## Commands you will need

| Purpose   | Command                                                   | Expected  |
|-----------|-----------------------------------------------------------|-----------|
| Tests (focus) | `python -m pytest -q tests/test_colors.py tests/test_dashboard.py tests/test_scene.py` | pass |
| Tests (all)   | `python -m pytest -q`                                 | all pass  |
| Lint      | `ruff check token_oracle tests`                           | exit 0    |
| Format    | `ruff format --check token_oracle tests`                  | exit 0    |
| Types     | `python -m mypy token_oracle --ignore-missing-imports`    | 0 errors  |

Confirm worktree code with
`python -c "import token_oracle, os; print(os.path.dirname(token_oracle.__file__))"`
(prefix `PYTHONPATH="$PWD"` if needed). Do NOT `pip install -e`.

## Scope

**In scope**:
- `token_oracle/cli/colors.py` (rewrite the truncation branch of `box_line` only)
- `tests/test_colors.py` (add tests)

**Out of scope** (do NOT touch):
- Anything under `token_oracle/dashboard/` — 052 already handles the scene layer;
  this is purely the `box_line` truncation.
- `display_width`, `_char_cells`, `box_top`, `box_bot`, `gauge`, or any other
  function in `colors.py` — only `box_line`'s truncation branch changes.
- The non-truncating (short text) path of `box_line` — must stay identical.

## Git workflow

- Branch: `advisor/055-box-line-color` (worktree already on it).
- One commit. Conventional commit, e.g.
  `fix(colors): preserve ANSI when box_line truncates (no more white text on narrow)`.
- Do NOT push or merge.

## Steps

### Step 1: Rewrite the truncation branch to preserve SGR

Replace the `if display_width(text) > inner_w:` block so it keeps ANSI escapes:

```python
def box_line(text, width=40, enabled=True):
    # pad or truncate using *display* width so wide glyphs / colored bars align
    inner_w = width - 2
    if display_width(text) > inner_w:
        # Truncate to the cell budget while KEEPING ANSI SGR (so a dim/colored
        # line stays dim/colored), leaving 1 cell for the ellipsis; append a
        # reset so styling never bleeds past the box.
        budget = inner_w - 1
        out = []
        used = 0
        i = 0
        had_sgr = False
        while i < len(text):
            m = _ANSI_RE.match(text, i)
            if m:
                out.append(m.group(0))
                had_sgr = True
                i = m.end()
                continue
            ch = text[i]
            w = _char_cells(ch)
            if used + w > budget:
                break
            out.append(ch)
            used += w
            i += 1
        out.append("…")
        if had_sgr:
            out.append(RESET)
        text = "".join(out)
    pad = " " * (inner_w - display_width(text))
    return f"│{text}{pad}│"
```

Do not change anything else in the function or file.

**Verify (inline sanity)**:
```
python -c "from token_oracle.cli import colors as c; s=c.dim('   570k/57.0M  proj 2% end-of-window', True); out=c.box_line(s,36,True); print('38;5;240' in out, '…' in out, c.display_width(out)==36); print(repr(out))"
```
→ `True True True` (dim code preserved, ellipsis present, exact box width).

### Step 2: Tests

Add to `tests/test_colors.py` (model after its existing box/`display_width`
tests):
- `test_box_line_truncation_preserves_color`: `box_line(colors.dim("x"*80, True),
  30, True)` → the result CONTAINS the dim code `"38;5;240"`, contains `"…"`,
  ends the interior with a reset (`"\033[0m"` present), and
  `display_width(result) == 30`.
- `test_box_line_truncation_fits_exact_width`: for widths 20, 30, 36, 50, a long
  colored string → `display_width(box_line(...)) == width` every time.
- `test_box_line_short_text_unchanged`: a short colored string → NO `"…"`, result
  is `│` + text + padding + `│` with `display_width == width` (non-truncating path
  intact).

**Verify**: `python -m pytest -q tests/test_colors.py` → all pass. Then
`python -m pytest -q tests/test_dashboard.py tests/test_scene.py` (052's tests
still green — the width-sweep still holds: `display_width(line) <= W`). Then full
suite `python -m pytest -q`.

## Test plan

- New tests in `tests/test_colors.py`: truncation-preserves-color,
  truncation-fits-exact-width, short-text-unchanged.
- Structural pattern: existing tests in `tests/test_colors.py`.
- Verification: `python -m pytest -q` → all pass.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] Step 1 inline sanity prints `True True True`.
- [ ] `python -m pytest -q` exits 0; ≥3 new tests exist and pass.
- [ ] 052's width-sweep (`tests/test_dashboard.py`) still passes unchanged.
- [ ] `ruff check token_oracle tests` = 0; `ruff format --check token_oracle tests` = 0; `python -m mypy token_oracle --ignore-missing-imports` = 0 errors.
- [ ] `git diff --name-only d52d7b7..HEAD` lists ONLY `token_oracle/cli/colors.py` and `tests/test_colors.py`.
- [ ] `plans/README.md` status row for 055 updated.

## STOP conditions

Stop and report if:

- The "Current state" `box_line` excerpt doesn't match live code (drift).
- After the change, `display_width(box_line(text, w))` is ever `!= w` for the test
  widths (padding math wrong) — report the failing case rather than adding hacks.
- The width-sweep test in `tests/test_dashboard.py` regresses (a line exceeds its
  width) — that would mean the ellipsis/cell accounting is off; STOP.

## Maintenance notes

- `box_line` and `scene.truncate_display` now share the same color-preserving
  truncation idea. If a third truncation site appears, factor a shared helper
  (place it in `colors.py`, the lowest layer — `scene` already imports
  `display_width` from it).
- Reviewer: confirm the short-text path is byte-identical and the truncated line
  is exactly `width` cells with the dim/gauge color intact up to the ellipsis.
