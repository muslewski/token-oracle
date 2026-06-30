# token-oracle — Presentation Polish

**Date:** 2026-06-30
**Status:** Design approved (2026-06-30). Ready for implementation plan.
**Scope:** Presentation/UX only. No forecast math, contracts, or source/snapshot
behavior changes. Builds on the shipped v0.1.0 (`main`, 56 tests green).

---

## 0. Thesis

Bring `agentic-sage`'s presentation discipline to `token-oracle`: one central color
module, semantic palette, terminal-aware color gating, a polished TUI, a scannable
`doctor`, and OSS-grade docs — while preserving the **zero-runtime-deps, stdlib-only**
principle. The engine is unchanged; only what the user *sees* improves.

## 1. Goals / Non-goals

**Goals**
- One color module (`oracle/cli/colors.py`) owning the palette, terminal detection,
  and the gauge thresholds — a single source of truth, ending the current two-palette
  drift between the statusline and tmux adapters.
- Oracle visual identity: a violet accent for headers and the oracle "voice", `dim`
  for metadata, and the existing green→lime→orange→red **gauge gradient** for severity.
- A polished stdlib TUI: block-char bars (`█░`), color, header, visual hierarchy.
- A scannable `doctor`: `✓`/`✗` badges with real pass/fail checks + a summary footer.
- OSS docs polish mirroring sage: badges, bolded acronym tagline, blockquote asides.

**Non-goals**
- No `rich`/`textual` or any runtime dependency. Stdlib ANSI only.
- No theme-config system. Violet *is* the identity (YAGNI).
- No changes to forecast math, `UsageEvent`/`Window`/`Forecast`, sources, or the
  snapshot schema.

## 2. Color foundation — `oracle/cli/colors.py`

A consumer-ring utility (the core never imports it; adapters, dashboard, and CLI do).

**Palette (256-color foreground codes):** violet `141` (accent), dim `240`,
and the gauge gradient green `42` / lime `154` / orange `214` / red `196`.

**Markers:** `🔮` (oracle/header), `⚠` (cap warning), `●` (window bullet),
`✓`/`✗` (doctor).

**Terminal gating — two rules, both honoring `NO_COLOR`:**
- `color_enabled()` (interactive surfaces — dashboard, doctor): `NO_COLOR` unset AND
  (`FORCE_COLOR` set non-`"0"` OR `stdout.isatty()`). Piping `oracle doctor > f` is clean.
- `pipe_color()` (adapter media — statusline, tmux): color is intrinsic to the medium
  (Claude Code / tmux interpret the codes from a *pipe*, never a TTY), so gate on
  `NO_COLOR` only, ignoring TTY.

**Single threshold source:** `gauge_tier(pct)` → `"green"|"lime"|"orange"|"red"` at the
existing cuts (`>=120` red, `>=100` orange, `>=85` lime, else green). Each medium maps
the tier to its own codes: `gauge_ansi_code(pct)` (ANSI), `gauge_tmux(pct)`
(`#[fg=...]`). No consumer hardcodes a threshold again.

**Helpers:** `paint(text, code, enabled)`, `violet(t, enabled)`, `dim(t, enabled)`,
`gauge(t, pct, enabled)` (paints text in its tier color). `enabled` defaults are
explicit at call sites so render functions stay deterministic and testable.

**Principle (from sage):** render functions return plain strings; color is applied via
these helpers at the output site. Color-off output is identical minus escape codes —
keeps tests color-free and output pipe-clean.

## 3. Surfaces

| Surface | Before | After |
|---|---|---|
| statusline adapter | own 256-color palette, baked codes | maps `gauge_ansi_code`; violet clock; `pipe_color()` gating |
| tmux adapter | own named-color palette | maps `gauge_tmux`; same thresholds as statusline |
| dashboard (`dash`) | plain ASCII, `[###---]` bar, no color | violet header, `█░` gauge-colored bars, dim metadata, `color_enabled()` |
| `doctor` | 4 bare f-string lines | `🔮` header, `✓/✗` rows (real checks), `N ok · M need attention` footer |
| README/docs | plain | badges, bolded **ORACLE** tagline, parts table kept, blockquote asides |

**Dashboard frame target:**
```
🔮 token-oracle
────────────────────────
  ●  5h  ███████░░░░░  62%
         120k/200k · resets 2:14
  ●  wk  ███░░░░░░░░░  28%  ⚠ cap in 5d
```

**doctor target:**
```
🔮 oracle doctor
  ✓ config   — ~/.config/token-oracle/config.json
  ✓ source   — claude_code (available: claude_code, generic)
  ✓ cache    — ~/.local/share/token-oracle/cache.json
  ✓ windows  — 2 → ['5h', 'weekly']
  4 ok · 0 need attention
```
Real checks: `source` ✗ when `cfg.source not in available()`; `windows` ✗ when zero.
`config`/`cache` are informational (always ✓).

## 4. Testing

- `gauge_tier` golden tests at boundaries: 84→green, 85→lime, 99→lime, 100→orange,
  119→orange, 120→red.
- `NO_COLOR` forced → adapter/dashboard output contains zero `\033` escapes.
- `color_enabled`/`pipe_color` honor `NO_COLOR` and `FORCE_COLOR` (monkeypatched env).
- Render functions assert plain structure (window names, pcts) under color-off — the
  existing dashboard/adapter assertions stay valid.
- `doctor` footer test: `N ok · M need attention` present; a bad source yields a `✗`.
- All existing 56 tests remain green; refactors preserve output substrings.

## 5. Non-goals recap / ring rule

`oracle/cli/colors.py` lives in the consumer ring. `oracle/core/*` must not import it.
Adapters, dashboard, and CLI import it. The three-ring rule from the v1 design holds.
