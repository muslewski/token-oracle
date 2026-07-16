# token-oracle CLI surfaces to dash-quality — design spec

**Date:** 2026-07-17 · **Status:** approved · **Phase:** 4 of the fleet UI campaign
**Inputs (binding):** the token-oracle section of `~/.cache/armory-research/UPGRADE-BRIEF.md`, the four audits `~/.cache/armory-research/repos/token-oracle-*.md`, `~/.cache/armory-research/PLAYBOOK.md`.

## North star
The `dash` TUI (violet boxes, gauges, tabs) is already best-in-fleet. Extend ITS visual language to every CLI surface. Pure Python stdlib stays the rule — no Rich, no pip deps. The kit law applies in Python form: stdout=data, chrome→stderr where applicable, TTY-gated color, NO_COLOR/TERM=dumb honored, pipe-safe. Consolidate on ONE color system (the existing shared colors module — kill the argparse second 16-color dialect and the duplicated bar-rendering code the audit found).

## Absolute constraints
- The capture firehose and any running processes are untouchable (no restarts, no edits to live state/data files).
- `--json` outputs, exit codes, and anything machine-parsed stay byte-stable.
- `statusline`/`tmux` surfaces are hot paths for status bars: keep them fast (<50ms) and parse-stable for tmux consumption.
- `dash` itself is OUT of scope (its L-items are deferred) — only borrow its visual language.

## Features (the brief's five rows)
1. **Zero-arg `oracle`** — instead of an argparse required-arg error: when TTY + fzf available, a command palette (each subcommand with a one-line description; preview pane shows that command's --help); non-TTY or no fzf → current behavior. S.
2. **`forecast`** — hero cap card (biggest number first: current cap window %, styled like a dash box) + secondary chips per window + a 12h burn sparkline. Fix the duplicate weekly segments and the `→` vs `->` glyph drift. M.
3. **`statusline` / `tmux`** — adaptive HUD: render by available cell budget (segments degrade gracefully: full → compact → minimal), one shared segment-body implementation for both surfaces (kill duplication). M.
4. **`doctor`** — severity banner (ok/warn/crit) + checklist with per-failure fix-hint lines; recovery commands surfaced, not buried. M.
5. **`report`** — aligned table with a %CAP sparkline column; when TTY + fzf: day/week drill-in picker. Fix current misalignment. M.

## Acceptance
- o1: `oracle` non-TTY (piped) behaves exactly as today (help/error, same exit code); TTY+fzf fixture → palette rows include every subcommand.
- o2: `forecast` shows each window exactly once (duplicate-segment regression test); one arrow glyph everywhere; hero card + sparkline present in TTY fixture output.
- o3: statusline output for a narrow cell budget ≤ its budget; wide budget shows full segments; both surfaces share one segment function (import graph asserts it); non-TTY output parse-stable vs current format (golden test where consumed by tmux).
- o4: doctor exit codes unchanged; severity banner reflects worst finding; every ✗ line is followed by a fix hint.
- o5: report columns align for ragged fixture data; %CAP sparkline renders; NO_COLOR strips all ANSI.
- o6: NO_COLOR=1 and piped output contain zero ANSI bytes across all five surfaces.
- Existing pytest suite green; new tests follow repo conventions; no new deps (`git grep -E "^import |^from "` shows stdlib only).
