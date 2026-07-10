# Plan 029: Exploration 05: Token Almanac — Swiss timetable, CSS-only motion

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ada32e9..HEAD -- explore/05-token-almanac/ explore/README.md plans/README.md`
> Changes to `explore/README.md` and `plans/README.md` made by plan 024
> (workspace + brief creation, plan-024 index row) are EXPECTED. Any change
> under `explore/05-token-almanac/` means another session already started
> this exploration — treat that as a STOP condition. Also STOP if the
> `explore/README.md` gallery row for exploration 05 is missing or its
> status is not `planned` (see Step 1).

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans/024-explore-scaffold-brief.md
- **Category**: direction
- **Planned at**: commit `ada32e9`, 2026-07-02

## Why this matters

token-oracle will get a marketing site in a separate repository. Before
committing to a visual direction, the operator is building several complete,
opinionated landing-page prototypes under `explore/` so they can be compared
side by side (plan 024 created the workspace and the shared brief). This plan
builds exploration 05, "Token Almanac": the argument that this audience —
terminal-dwelling developers who distrust marketing — trusts a schedule more
than a mascot, so the oracle should speak in tabular numerals on a rational
Swiss grid. When this lands, `explore/05-token-almanac/` contains a finished,
zero-build landing page and the gallery row flips from `planned` to `built`.

## Current state

- `explore/BRIEF.md` and `explore/README.md` exist only if plan 024 has run.
  Step 1 verifies this; if `explore/BRIEF.md` is missing, STOP and report
  "run plan 024 first".
- The gallery row this plan flips (in `explore/README.md`) currently reads:

  ```
  | 05 | Token Almanac | contrast | zero-dep HTML/CSS | open `index.html` | plans/029 | planned |
  ```

- `explore/05-token-almanac/` does not exist yet. This plan creates it with
  exactly four files: `index.html`, `styles.css`, `main.js`, `README.md`
  (plus `screenshot.png` if browser tooling is available).
- This repo is a Python CLI project. Nothing in this plan touches Python
  code; `python3` is used only as a static file server for the smoke test.
- Repo commit style is conventional commits (see `git log --oneline`:
  `fix(dash): ...`, `chore(core): ...`, `test: ...`).

**Product facts** (from the root `README.md` and `explore/BRIEF.md` — every
claim on the page must trace to these):

- token-oracle is an offline CLI that forecasts when you will hit your
  AI-provider token cap. It reads the provider's local usage logs (Claude
  Code built in; adapters add more), computes an observed burn rate over a
  sliding window, and projects time-to-cap. No API calls; nothing leaves
  your machine. Python, zero runtime dependencies, MIT licensed, on PyPI.
- Subcommands: `forecast` (live forecast, `--json`), `dash` (full-screen
  terminal dashboard), `statusline` (one-line ANSI fragment for any status
  bar), `tmux` (status-right fragment), `snapshot` (writes `forecast.json`
  for other tools), `doctor` (checks configuration and data sources).
- Color semaphore on projected usage at window end (as % of cap):
  green < 85% · lime 85–100% · orange 100–120% · red ≥ 120%.
- Install: `pipx install token-oracle` (primary), `pip install token-oracle`,
  `uvx token-oracle`.
- Honest sample data (the ONLY numbers allowed on the page):
  - Calm scenario: window 5h, used 45,200 / cap 220,000, projected 21% at
    window end, resets in 3h 42m → green.
  - Drama scenario: window 5h, used 178,400 / cap 220,000, projected 108%,
    ETA to cap 1h 12m, resets in 2h 48m → orange.
  - Statusline mock (representative, not claimed as exact CLI output):
    `[5h] 45.2k/220k · 21% · resets 3h42m`

**Honesty guardrails** (hard rules from the brief): no testimonials, no user
counts, no "trusted by" logos, no star counts, no invented benchmarks, no
named competitors. Sample numbers only from the two scenarios above.

**Accessibility floor** (from the brief): semantic landmarks
(`header`/`main`/`footer`, exactly one `h1`); visible `:focus-visible`
styles; body-text contrast ≥ 4.5:1; every animation gated behind
`prefers-reduced-motion: reduce` (page fully readable with it on);
interactive demos keyboard-operable; images have alt text; `lang="en"`;
usable at 360px width.

**Performance / tech rules** (from the brief): `font-display: swap` on
webfonts (via `&display=swap` in the Google Fonts URL); Google Fonts
`<link>` allowed, always with a system fallback stack; no other runtime
CDNs; no analytics, no trackers, no external network calls at runtime beyond
fonts; zero-build pages carry ≤ 200 lines of JS (this plan self-caps at 80);
no scroll-handler layout thrash (this page has zero scroll JS — motion is
CSS-only); canvas/WebGL rules are not applicable (no canvas here); Node ≥ 18
is assumed available (used here only for `node --check`).

## Design specification

### Brand stance

**Contrast** — prophecy as timetable: the oracle speaks in tabular numerals
on a rational Swiss grid, because this audience trusts a schedule more than a
mascot. The ONE named aesthetic risk this design takes: **near-zero
decoration** — no images, no icons, no gradients, no border-radius anywhere;
typography, rules, and two data visualizations carry the entire page.
Precision IS the aesthetic, so the spacing and type scales below are exact
and must be used as given.

**Anti-cliché guard**: this is a TIMETABLE, not a newspaper — no
multi-column body text, no dense hairlines everywhere. Horizontal rules
only: 2px ink for major section breaks, 1px `#B9B9B9` for rows. Generous
whitespace. Huge scale contrast between the countdown
(`clamp(4rem, 14vw, 11rem)`) and everything else.

### Design tokens (colors)

| Token | Hex | Used for |
|-------|-----|----------|
| `--bg` | `#FFFFFF` | page background |
| `--ink` | `#101010` | all text, major 2px rules |
| `--rule` | `#B9B9B9` | minor 1px row rules, footer hairline |
| `--blue` | `#2B45D9` | the ONLY accent: links, install-strip rules, eyebrows, focus outlines (a nod to the brand's violet-blue without the lavender wash) |
| `--sem-green` | `#1F7A33` | semaphore — heatmap cells + the calm 21% chip ONLY |
| `--sem-lime` | `#93A11A` | semaphore — heatmap cells ONLY |
| `--sem-orange` | `#C2681C` | semaphore — heatmap cells + the drama 108% chip ONLY |
| `--sem-red` | `#BF3B2F` | semaphore — reserved; the mock week never reaches the red tier, so it renders nowhere (expected — define the token anyway) |

Semaphore colors appear strictly inside the heatmap cells and the two status
chips. Nowhere else.

Contrast pairs (precomputed — use exactly these pairings, do not "improve"
them): ink `#101010` on white ≈ 19:1; blue `#2B45D9` on white ≈ 7.1:1;
white text on green `#1F7A33` ≈ 5.4:1; **ink `#101010` text on orange
`#C2681C` ≈ 4.8:1** (white on that orange is only ≈ 4.0:1 and would fail
the 4.5:1 floor — that is why the two chips use different text colors).

### Type

| Role | Google Fonts family | Weights / axes | Fallback stack | Notes |
|------|--------------------|----------------|----------------|-------|
| Display | Archivo (variable) | wdth 125 (expanded), wght 700 | `system-ui, sans-serif` | wordmark, countdown, section eyebrows; tracked tight (`letter-spacing: -0.01em`, countdown `-0.02em`). Archivo Expanded falls back to normal-width system type — acceptable. |
| Body | Archivo | 400, 500 | `system-ui, sans-serif` | all prose |
| Data | IBM Plex Mono | 400, 500 | `ui-monospace, monospace` | timetable, commands table, install strip, captions, statusline mock |

`font-display: swap` comes from `&display=swap` in the fonts URL.
`font-variant-numeric: tabular-nums` on the countdown and every table
numeral. Width axis is applied in CSS via `font-stretch: 125%`.

### Spacing scale (8px base) and type scale (ratio 1.25)

```css
--s-1: 0.5rem;  --s-2: 1rem;  --s-3: 1.5rem;  --s-4: 2rem;
--s-6: 3rem;    --s-8: 4rem;  --s-12: 6rem;
--t--1: 0.8rem; --t-0: 1rem;  --t-1: 1.25rem; --t-2: 1.563rem;
--t-3: 1.953rem; --t-4: 2.441rem; --t-5: 3.052rem;
```

The countdown alone overrides the scale with `clamp(4rem, 14vw, 11rem)`.

### Wireframe (top to bottom)

```
┌──────────────────────────────────────────────────────────────────────┐
│ ══════════ 2px ink rule #101010, full page width ═══════════════════ │
│ TOKEN ORACLE                                          View on GitHub │ header
│                                                                      │
│ DEPARTURES — WINDOW 5H                     h2 eyebrow, blue #2B45D9  │
│  [0][3] : [4][2] : [1][0]    countdown: Archivo 700 wdth 125,        │
│                              clamp(4rem,14vw,11rem), ticks 1/s,      │ hero
│                              each digit in a fixed-width cell        │
│ live demo — your real numbers come from token-oracle forecast (mono) │
│ Know when you'll hit the limit.               h1, quiet, 1.25rem     │
│ Usage monitors tell you what you spent. Token Oracle tells you       │
│ what happens next.                            body, max 55ch         │
│ ══════════ 2px ink rule ════════════════════════════════════════════ │
│ TIMETABLE                                                            │
│ WINDOW  USED     CAP      PROJECTED  ETA     RESETS  ← th, 2px rule  │
│ ─────── 1px #B9B9B9 ──────────────────────────────────────────────── │
│ 5h      45,200   220,000  [21%]      —       3h 42m  ← green chip    │ timetable
│ ─────── 1px #B9B9B9 ──────────────────────────────────────────────── │
│ 5h      178,400  220,000  [108%]     1h 12m  2h 48m  ← orange chip   │
│ as a statusline: [5h] 45.2k/220k · 21% · resets 3h42m       (mono)   │
│ It's a forecast, not a bill.                                         │
│ ══════════ 2px ink rule ════════════════════════════════════════════ │
│ WEEK PROFILE                                                         │
│ MON ▢▢▢▢▢▢▢▢▢■■■■■■■■■▣▣▣▣▣▢   7 rows (Mon–Sun) × 24 hour cells,     │ heat
│ ...                            squares, 2px gap, aria-hidden         │ calendar
│ SUN ▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢   legend: ▢ light ▣ medium ■ heavy      │
│ Mock week for illustration: heavy on weekday working hours, ...      │
│ ══════════ 2px ink rule ════════════════════════════════════════════ │
│ HOW IT WORKS                                                         │
│ 01 READ ...       02 MEASURE ...      03 FORECAST ...   3 × span-4   │
│ ══════════ 2px ink rule ════════════════════════════════════════════ │
│ PILLARS                                                              │
│ CLARITY ...  FORESIGHT ...  CONFIDENCE ...  INTENTION ... 4 × span-3 │
│ ══════════ 2px ink rule ════════════════════════════════════════════ │
│ COMMANDS                                                             │
│ COMMAND                 WHAT IT DOES        mono table, 6 rows       │
│ ══════════ 2px ink rule ════════════════════════════════════════════ │
│ INSTALL                                                              │
│ ────────── 2px blue rule #2B45D9 ──────────────────────────────────  │
│        pipx install token-oracle       large mono, centered          │
│ ────────── 2px blue rule #2B45D9 ──────────────────────────────────  │
│ pip install token-oracle · uvx token-oracle            small mono    │
│ Provider-agnostic · Zero dependencies · CLI first · Extensible       │
│ ────────── 1px hairline #B9B9B9 ───────────────────────────────────  │
│ MIT licensed. Built by Mateusz Muślewski.  PyPI · GitHub ·           │ footer
│ agentic-sage                                                         │
└──────────────────────────────────────────────────────────────────────┘
```

Layout: one `.wrap` container (`max-width: 72rem; margin-inline: auto;
padding-inline: clamp(1rem, 4vw, 2rem)`). How-it-works and pillars use a
strict 12-column grid (`display: grid; grid-template-columns:
repeat(12, 1fr); gap: var(--s-3)`); steps span 4 columns, pillars span 3;
below 720px everything spans 12. No other multi-column text anywhere.

### Signature element: the departures-board countdown

- **Geometry**: six digits + two colons in one row. Each digit sits in its
  own fixed-width cell: `display: inline-block; width: 0.62em; text-align:
  center;` (colons: `width: 0.35em`). Font: Archivo, `font-stretch: 125%`,
  weight 700, `font-size: clamp(4rem, 14vw, 11rem)`, `line-height: 1`,
  `letter-spacing: -0.02em`, `font-variant-numeric: tabular-nums` (fixed
  cells + tabular-nums = belt-and-braces against jitter). Parent board:
  `display: inline-flex; perspective: 500px;`.
- **Behavior**: starts at `03:42:10` (the calm scenario says "resets in
  3h 42m"; the `:10` seconds digit is a display artifact of rendering that
  duration as a ticking clock, chosen so the minute rollover demos ~11s
  after load — it is not an additional sample number), ticks down once per
  second via `setInterval(..., 1000)`. At `00:00:00` the next tick wraps
  back to `03:42:10` — it is a demo, not a real clock; the caption under
  the board says so ("live demo — your real numbers come from
  token-oracle forecast").
- **Minute rollover flip**: when the minutes pair changes (seconds go 00 →
  59), each minute digit cell whose value changed does a 90-degree flip
  (the Step 7 JS adds `.flip` only to changed cells — usually just the
  ones cell, e.g. `42 → 41`; both cells flip only when the tens digit also
  changes, e.g. `40 → 39`): a `flip` class triggers `@keyframes digit-flip
  { from { transform: rotateX(90deg); } to { transform: rotateX(0deg); }
  }`, 300ms, easing `cubic-bezier(0.66, 0, 0.34, 1)` (steps-like snap).
- **States**: default (ticking), `.flip` on changed minute cells during
  rollover, reduced-motion (see below).
- **Reduced motion**: `@media (prefers-reduced-motion: reduce) { .digit.flip
  { animation: none; } }` — no flip, but digits STILL update every second:
  the countdown is content, not decoration.
- **Accessibility**: the board wrapper gets `role="timer"` and
  `aria-label="Demo countdown to window reset, starting at 3 hours 42
  minutes 10 seconds."`; the digit spans live inside an
  `aria-hidden="true"` span so screen readers are not spammed every second.
  The static markup ships with the digits `0 3 : 4 2 : 1 0` so the page is
  complete without JS.

### Motion spec

1. **Digit flip** (above). Trigger: minute rollover. 300ms,
   `cubic-bezier(0.66, 0, 0.34, 1)`. Reduced motion: no flip, digits still
   update.
2. **Section reveals** — CSS scroll-driven animations ONLY
   (`animation-timeline: view()`), applied via a `.reveal` class on each
   `<section>` inside `<main>`: `@keyframes rise { from { opacity: 0;
   transform: translateY(12px); } }` with `animation: rise linear both;
   animation-timeline: view(); animation-range: entry 0% entry 40%;`. The
   whole rule is wrapped in `@supports (animation-timeline: view())` nested
   with `@media (prefers-reduced-motion: no-preference)` — the base
   (unwrapped) state is fully visible, so non-supporting browsers and
   reduced-motion users see a complete static page. Scroll reveals are
   disabled under reduced motion.
3. Nothing else animates. JS budget ≤ 80 lines total: the clock and nothing
   more (the heatmap is static HTML generated once at authoring time, not
   by runtime JS).

## Copy (final, verbatim)

The executor writes ZERO copy. Every string on the page comes from this
section, in display order. Use straight ASCII apostrophes (`'`, U+0027)
everywhere — the done-criteria grep for the tagline depends on it. Honesty
guardrails are hard: no testimonials, no user counts, no trusted-by logos,
no star counts, no named competitors, no invented benchmarks.

**`<head>`**
- Title: `Token Oracle — Know when you'll hit the limit.`
- Meta description: `token-oracle is an offline CLI that forecasts when you
  will hit your AI-provider token cap. No API calls — nothing leaves your
  machine.`

**Header**
- Wordmark: `TOKEN ORACLE`
- Link: `View on GitHub` → `https://github.com/muslewski/token-oracle`

**Hero (departures board)**
- Eyebrow (h2): `DEPARTURES — WINDOW 5H`
- Countdown initial digits: `03:42:10`
- Countdown aria-label: `Demo countdown to window reset, starting at 3 hours
  42 minutes 10 seconds.`
- Caption (mono, small): `live demo — your real numbers come from
  token-oracle forecast`
- Tagline (the page's ONE h1, exactly): `Know when you'll hit the limit.`
- Positioning line: `Usage monitors tell you what you spent. Token Oracle
  tells you what happens next.`

**Timetable**
- Eyebrow (h2): `TIMETABLE`
- Column headers: `WINDOW` · `USED` · `CAP` · `PROJECTED` · `ETA` · `RESETS`
- Row 1 (calm): `5h` · `45,200` · `220,000` · `21%` (green chip) · `—` ·
  `3h 42m`
- Row 2 (drama): `5h` · `178,400` · `220,000` · `108%` (orange chip) ·
  `1h 12m` · `2h 48m`
- Visually-hidden `<caption>`: `Two example forecast windows: a calm one
  projected at 21% of cap, and a hot one projected at 108% with 1 hour 12
  minutes to the cap. Demo data.`
- Statusline caption (mono): `as a statusline: [5h] 45.2k/220k · 21% ·
  resets 3h42m`
- Secondary line: `It's a forecast, not a bill.`

**Week heat calendar**
- Eyebrow (h2): `WEEK PROFILE`
- Day labels (mono, inside the aria-hidden figure): `MON` `TUE` `WED` `THU`
  `FRI` `SAT` `SUN`
- Legend labels (inside the aria-hidden figure): `light` · `medium` ·
  `heavy`, plus the axis note `hours 00–23 →`
- Summary (a normal visible paragraph — this is the screen-reader text for
  the aria-hidden grid): `Mock week for illustration: heavy on weekday
  working hours, medium in the evenings, light at night and on weekends.
  token-oracle weights its forecast by your own weekly usage profile.`

**How it works**
- Eyebrow (h2): `HOW IT WORKS`
- Entry `01` — h3 `Read`: `token-oracle reads your provider's local usage
  logs. Claude Code is built in; adapters add more. No API calls — nothing
  leaves your machine.`
- Entry `02` — h3 `Measure`: `it computes your observed burn rate over a
  sliding window, weighted by your own weekly usage profile.`
- Entry `03` — h3 `Forecast`: `it projects usage to window end and tells you
  what's left before the cap: a percentage, an ETA, and a color.`

**Pillars**
- Eyebrow (h2): `PILLARS`
- `Clarity` — `understand your true token usage.`
- `Foresight` — `plan ahead with accuracy.`
- `Confidence` — `avoid surprises, stay in control.`
- `Intention` — `spend tokens with purpose.`
  (Pillar names are styled uppercase via CSS `text-transform`; keep the
  source text as written here.)

**Commands**
- Eyebrow (h2): `COMMANDS`
- Column headers: `COMMAND` · `WHAT IT DOES`
- `token-oracle forecast` — `live forecast; --json for machine-readable output`
- `token-oracle dash` — `full-screen terminal dashboard`
- `token-oracle statusline` — `one-line ANSI fragment for any status bar`
- `token-oracle tmux` — `tmux status-right fragment`
- `token-oracle snapshot` — `writes forecast.json for other tools`
- `token-oracle doctor` — `checks configuration and data sources`

**Install strip**
- Eyebrow (h2): `INSTALL`
- Primary (large mono, between the two blue rules): `pipx install token-oracle`
- Alternates (small mono): `pip install token-oracle · uvx token-oracle`
- Badges (small mono): `Provider-agnostic · Zero dependencies · CLI first ·
  Extensible`

**Footer**
- `MIT licensed. Built by Mateusz Muślewski.`
- Links: `PyPI` → `https://pypi.org/project/token-oracle/` · `GitHub` →
  `https://github.com/muslewski/token-oracle` · `agentic-sage` →
  `https://github.com/muslewski/agentic-sage`

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Prereq: brief exists | `test -f explore/BRIEF.md && echo OK` | `OK` (else STOP: run plan 024 first) |
| Serve the page | `python3 -m http.server 8045 --directory explore/05-token-almanac` | serves on :8045 (run in background) |
| Smoke | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8045/index.html` | `200` |
| JS syntax | `node --check explore/05-token-almanac/main.js` | exit 0, no output |
| JS budget | `wc -l < explore/05-token-almanac/main.js` | ≤ 80 |
| Fonts width axis | see the fenced command in Step 4 (it contains a shell pipe, which cannot be written copy-paste-runnable inside a markdown table) | ≥ 1 (else Step 4 fallback — NOT a STOP) |
| Scope check | `git status --porcelain` | only `explore/05-token-almanac/`, `explore/README.md`, `plans/README.md` paths |

Verified on the planning machine: `python3` 3.14.5 and `node` v22.12.0 are
installed. This page is zero-build: no npm, no `package.json`, no `dist/`.

## Suggested executor toolkit

- Screenshot (optional): if headless Chromium is available, with the server
  from the smoke step still running:
  `chromium --headless --screenshot=explore/05-token-almanac/screenshot.png --window-size=1440,3400 http://127.0.0.1:8045/index.html`
  If no browser tooling exists, note that in the exploration README and
  continue — missing screenshot tooling is NOT a STOP condition.

## Scope

**In scope** (the only files you may create/modify):
- `explore/05-token-almanac/index.html` (create)
- `explore/05-token-almanac/styles.css` (create)
- `explore/05-token-almanac/main.js` (create)
- `explore/05-token-almanac/README.md` (create)
- `explore/05-token-almanac/screenshot.png` (create, only if tooling allows)
- `explore/README.md` — ONLY the status cell of the `| 05 |` gallery row
- `plans/README.md` — ONLY this plan's status row

**Out of scope** (do NOT touch):
- `token_oracle/`, `tests/`, `assets/`, the root `README.md`
- `explore/BRIEF.md` — the brief is operator-approved; wording changes are
  a report, not an edit
- Every other `explore/` folder (01–04) and every other plan file

## Git workflow

- Branch: `advisor/029-explore-almanac-swiss` (create from the current
  default branch: `git checkout -b advisor/029-explore-almanac-swiss`)
- Conventional commits, one per logical unit. Suggested sequence:
  - `feat(explore): scaffold token almanac exploration`
  - `feat(explore): almanac page sections and timetable`
  - `feat(explore): almanac countdown clock and css motion`
  - `docs(explore): almanac readme, gallery row, plan index`
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Prerequisites and drift check

Run from the repo root (`/home/kento/Repositories/token-oracle`):

1. `test -f explore/BRIEF.md && echo OK` → `OK`. If not: **STOP — run plan
   024 first.**
2. `grep -c "Know when you'll hit the limit." explore/BRIEF.md` → ≥ 1. If
   0, the brief's canonical copy has drifted from this plan — STOP.
3. `grep '| 05 |' explore/README.md` → one row containing `Token Almanac`
   and `planned`. If missing or not `planned`, STOP (another session owns
   this exploration).
4. `test ! -e explore/05-token-almanac && echo CLEAR` → `CLEAR`. If the
   folder exists, STOP.
5. `python3 --version && node --version` → both print versions (any Python
   3, Node ≥ 18).

**Verify**: all five commands returned the expected output above.

### Step 2: Create the branch

`git checkout -b advisor/029-explore-almanac-swiss`

**Verify**: `git branch --show-current` → `advisor/029-explore-almanac-swiss`

### Step 3: Scaffold the exploration folder

Create `explore/05-token-almanac/` with three files.

`index.html` — exactly this skeleton (sections are filled in Steps 5–14):

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Token Oracle — Know when you'll hit the limit.</title>
  <meta name="description" content="token-oracle is an offline CLI that forecasts when you will hit your AI-provider token cap. No API calls — nothing leaves your machine.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@100,400;100,500;125,700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
  <script src="main.js" defer></script>
</head>
<body>
  <header>
    <!-- Step 5 -->
  </header>
  <main>
    <!-- Steps 6-13 -->
  </main>
  <footer>
    <!-- Step 14 -->
  </footer>
</body>
</html>
```

`styles.css` — empty for now (filled from Step 4 on).
`main.js` — a single line for now: `// countdown added in Step 7`

**Verify**: `grep -c '<html lang="en">' explore/05-token-almanac/index.html`
→ `1`, and `test -f explore/05-token-almanac/styles.css && test -f
explore/05-token-almanac/main.js && echo OK` → `OK`

### Step 4: Verify the Archivo width axis, then write tokens and base styles

First check that Google Fonts actually serves the width axis (the URL shape
`family=Archivo:wdth,wght@100,400;100,500;125,700` requests wdth+wght
tuples; tuples must stay in ascending order):

```
curl -s -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
  "https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@100,400;100,500;125,700&family=IBM+Plex+Mono:wght@400;500&display=swap" \
  | grep -Ec "wdth|font-stretch"
```

- Result ≥ 1: the width axis is served; proceed as written.
- Result 0 (axis not served): **fallback, NOT a STOP** — change the `<link>`
  URL to `family=Archivo:wght@400;500;700`, delete every `font-stretch:
  125%;` declaration below, and on `.wordmark` and `.eyebrow` REPLACE the
  existing `letter-spacing: -0.01em;` with `letter-spacing: 0.04em;`
  (replace, don't add a second declaration — letter-spaced Archivo 700 at
  normal width). Leave `.board` and heading tracking exactly as written
  (tight tracking is fine at normal width). Record the deviation in the
  exploration README (Step 19).
- curl cannot reach fonts.googleapis.com at all: keep the `<link>` (system
  fallbacks carry the page), note it in the exploration README, continue.

Then write this to `styles.css`:

```css
:root {
  --bg: #FFFFFF;
  --ink: #101010;
  --rule: #B9B9B9;
  --blue: #2B45D9;
  --sem-green: #1F7A33;
  --sem-lime: #93A11A;
  --sem-orange: #C2681C;
  --sem-red: #BF3B2F; /* reserved: mock week never reaches red — expected */

  --s-1: 0.5rem;  --s-2: 1rem;  --s-3: 1.5rem;  --s-4: 2rem;
  --s-6: 3rem;    --s-8: 4rem;  --s-12: 6rem;

  --t--1: 0.8rem; --t-0: 1rem;  --t-1: 1.25rem; --t-2: 1.563rem;
  --t-3: 1.953rem; --t-4: 2.441rem; --t-5: 3.052rem;

  --font-display: "Archivo", system-ui, sans-serif;
  --font-body: "Archivo", system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
}

* { box-sizing: border-box; margin: 0; }

body {
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font-body);
  font-weight: 400;
  font-size: var(--t-0);
  line-height: 1.5;
}

.wrap { max-width: 72rem; margin-inline: auto; padding-inline: clamp(1rem, 4vw, 2rem); }
.grid-12 { display: grid; grid-template-columns: repeat(12, 1fr); gap: var(--s-3); }
section { padding-block: var(--s-8); }

hr.rule-major { border: 0; border-top: 2px solid var(--ink); margin: 0; }

a { color: var(--blue); text-decoration: underline; text-underline-offset: 2px; }
:focus-visible { outline: 2px solid var(--blue); outline-offset: 2px; }

.eyebrow {
  font-family: var(--font-display);
  font-stretch: 125%;
  font-weight: 700;
  font-size: var(--t--1);
  letter-spacing: -0.01em; /* display type tracked tight */
  text-transform: uppercase;
  color: var(--blue);
  margin-bottom: var(--s-4);
}

.mono { font-family: var(--font-mono); font-size: var(--t--1); }

.visually-hidden {
  position: absolute; width: 1px; height: 1px; overflow: hidden;
  clip: rect(0 0 0 0); white-space: nowrap;
}
```

Rules of the aesthetic (enforced by done criteria): NO `border-radius`, NO
gradients, NO `<img>` elements, no icon fonts, anywhere in this page.

**Verify**: `grep -c -- '--sem-red: #BF3B2F' explore/05-token-almanac/styles.css`
→ `1`, and `grep -c ':focus-visible' explore/05-token-almanac/styles.css` → `1`

### Step 5: Header

Replace the `<!-- Step 5 -->` comment inside `<header>` with:

```html
<div class="wrap masthead">
  <p class="wordmark">TOKEN ORACLE</p>
  <a class="mono" href="https://github.com/muslewski/token-oracle">View on GitHub</a>
</div>
```

Append to `styles.css`:

```css
header { border-top: 2px solid var(--ink); }
.masthead { display: flex; justify-content: space-between; align-items: baseline; padding-block: var(--s-2); }
.wordmark {
  font-family: var(--font-display);
  font-stretch: 125%;
  font-weight: 700;
  font-size: var(--t-1);
  letter-spacing: -0.01em;
  text-transform: uppercase;
}
```

**Verify**: `grep -c 'TOKEN ORACLE' explore/05-token-almanac/index.html` → `1`

### Step 6: Hero — departures board (static markup)

Add as the first section inside `<main>` (all `<main>` sections in Steps
6–13 follow the pattern `<section class="wrap reveal">…</section>`, each
preceded by `<hr class="rule-major">` EXCEPT this hero, which has no rule
above it — the header rule serves that role):

```html
<section class="wrap reveal hero">
  <h2 class="eyebrow">DEPARTURES — WINDOW 5H</h2>
  <div class="countdown" role="timer"
       aria-label="Demo countdown to window reset, starting at 3 hours 42 minutes 10 seconds.">
    <span class="board" aria-hidden="true"><span class="digit" data-digit>0</span><span class="digit" data-digit>3</span><span class="colon">:</span><span class="digit" data-digit>4</span><span class="digit" data-digit>2</span><span class="colon">:</span><span class="digit" data-digit>1</span><span class="digit" data-digit>0</span></span>
  </div>
  <p class="mono caption">live demo — your real numbers come from token-oracle forecast</p>
  <h1>Know when you'll hit the limit.</h1>
  <p class="positioning">Usage monitors tell you what you spent. Token Oracle tells you what happens next.</p>
</section>
```

Append to `styles.css`:

```css
.hero { padding-block: var(--s-12) var(--s-8); }
.board {
  display: inline-flex;
  perspective: 500px;
  font-family: var(--font-display);
  font-stretch: 125%;
  font-weight: 700;
  font-size: clamp(4rem, 14vw, 11rem);
  letter-spacing: -0.02em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.digit { display: inline-block; width: 0.62em; text-align: center; }
.colon { display: inline-block; width: 0.35em; text-align: center; }
.caption { margin-top: var(--s-2); }
.hero h1 { font-size: var(--t-1); font-weight: 500; margin-top: var(--s-6); }
.positioning { max-width: 55ch; margin-top: var(--s-2); }
```

**Verify**: `grep -o 'data-digit' explore/05-token-almanac/index.html | wc -l` → `6`
(all six spans sit on ONE source line, so `grep -c` — which counts lines —
would print `1`; count occurrences with `-o | wc -l`),
and `grep -c "Know when you'll hit the limit." explore/05-token-almanac/index.html`
→ `2` (title + h1)

### Step 7: Signature element — the countdown clock (JS + flip CSS)

Replace the entire content of `main.js` with exactly:

```js
// Departures-board countdown. Demo clock: counts down from 03:42:10
// (the calm scenario's resets-in time) and wraps back to it at zero.
(function () {
  "use strict";

  var START_SECONDS = 3 * 3600 + 42 * 60 + 10; // 03:42:10
  var remaining = START_SECONDS;

  var cells = document.querySelectorAll(".countdown [data-digit]");
  if (cells.length !== 6) return; // markup mismatch: leave static digits

  function digitsOf(total) {
    var h = Math.floor(total / 3600);
    var m = Math.floor((total % 3600) / 60);
    var s = total % 60;
    function two(n) { return n < 10 ? "0" + n : "" + n; }
    return (two(h) + two(m) + two(s)).split("");
  }

  function render(next, flipMinutes) {
    for (var i = 0; i < 6; i++) {
      var cell = cells[i];
      if (cell.textContent !== next[i]) {
        cell.textContent = next[i];
        if (flipMinutes && (i === 2 || i === 3)) {
          cell.classList.remove("flip");
          void cell.offsetWidth; // restart the animation
          cell.classList.add("flip");
        }
      }
    }
  }

  render(digitsOf(remaining), false);

  setInterval(function () {
    var prevMinute = Math.floor((remaining % 3600) / 60);
    remaining = remaining > 0 ? remaining - 1 : START_SECONDS;
    var nextMinute = Math.floor((remaining % 3600) / 60);
    render(digitsOf(remaining), nextMinute !== prevMinute);
  }, 1000);
})();
```

Append to `styles.css`:

```css
.digit.flip { animation: digit-flip 300ms cubic-bezier(0.66, 0, 0.34, 1); }
@keyframes digit-flip {
  from { transform: rotateX(90deg); }
  to   { transform: rotateX(0deg); }
}
@media (prefers-reduced-motion: reduce) {
  .digit.flip { animation: none; } /* countdown is content: digits still update */
}
```

**Verify**: `node --check explore/05-token-almanac/main.js` → exit 0, and
`wc -l < explore/05-token-almanac/main.js` → ≤ 80

### Step 8: Timetable section

Add after the hero section, inside `<main>`:

```html
<hr class="rule-major">
<section class="wrap reveal">
  <h2 class="eyebrow">TIMETABLE</h2>
  <div class="table-scroll">
    <table>
      <caption class="visually-hidden">Two example forecast windows: a calm one projected at 21% of cap, and a hot one projected at 108% with 1 hour 12 minutes to the cap. Demo data.</caption>
      <thead>
        <tr><th scope="col">WINDOW</th><th scope="col">USED</th><th scope="col">CAP</th><th scope="col">PROJECTED</th><th scope="col">ETA</th><th scope="col">RESETS</th></tr>
      </thead>
      <tbody>
        <tr><td>5h</td><td>45,200</td><td>220,000</td><td><span class="chip chip--green">21%</span></td><td>—</td><td>3h 42m</td></tr>
        <tr><td>5h</td><td>178,400</td><td>220,000</td><td><span class="chip chip--orange">108%</span></td><td>1h 12m</td><td>2h 48m</td></tr>
      </tbody>
    </table>
  </div>
  <p class="mono statusline">as a statusline: [5h] 45.2k/220k · 21% · resets 3h42m</p>
  <p class="secondary">It's a forecast, not a bill.</p>
</section>
```

Append to `styles.css` (chip text colors are contrast-driven — see the
Design specification; do not change them):

```css
.table-scroll { overflow-x: auto; }
table {
  border-collapse: collapse;
  width: 100%;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
th {
  text-align: left; font-weight: 500; font-size: var(--t--1);
  border-bottom: 2px solid var(--ink);
  padding: var(--s-1) var(--s-3) var(--s-1) 0;
}
td { border-bottom: 1px solid var(--rule); padding: var(--s-2) var(--s-3) var(--s-2) 0; }
.chip { display: inline-block; padding: 0.125rem 0.5rem; font-weight: 500; }
.chip--green  { background: var(--sem-green);  color: #FFFFFF; } /* 5.4:1 */
.chip--orange { background: var(--sem-orange); color: #101010; } /* 4.8:1 */
.statusline { margin-top: var(--s-3); }
.secondary { margin-top: var(--s-2); }
```

**Verify**: `grep -c 'chip--orange' explore/05-token-almanac/index.html` → `1`,
and `grep -c '178,400' explore/05-token-almanac/index.html` → `1`

### Step 9: Week heat calendar

Generate the 168 hourly cells once, at authoring time (NOT runtime JS —
the JS budget belongs to the clock). Mock-data rule: days 0–4 = Mon–Fri,
5–6 = Sat–Sun; weekday hours 9–17 → `heavy`, weekday hours 18–22 →
`medium`, everything else (weekday nights and all weekend) → `light`.

```bash
python3 - <<'EOF' > /tmp/almanac-heatmap.html
days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
rows = []
for d, day in enumerate(days):
    cells = ['<span class="day">%s</span>' % day]
    for hour in range(24):
        if d >= 5:
            tier = "light"
        elif 9 <= hour <= 17:
            tier = "heavy"
        elif 18 <= hour <= 22:
            tier = "medium"
        else:
            tier = "light"
        cells.append('<i class="cell %s"></i>' % tier)
    rows.append("".join(cells))
print("\n".join(rows))
EOF
grep -o 'class="cell' /tmp/almanac-heatmap.html | wc -l   # must print 168
```

Add after the timetable section:

```html
<hr class="rule-major">
<section class="wrap reveal">
  <h2 class="eyebrow">WEEK PROFILE</h2>
  <figure class="week-figure" aria-hidden="true">
    <div class="week">
      <!-- paste the 7 generated rows from /tmp/almanac-heatmap.html here -->
    </div>
    <p class="mono axis">hours 00–23 →</p>
    <p class="mono legend"><i class="cell light"></i>light <i class="cell medium"></i>medium <i class="cell heavy"></i>heavy</p>
  </figure>
  <p class="week-summary">Mock week for illustration: heavy on weekday working hours, medium in the evenings, light at night and on weekends. token-oracle weights its forecast by your own weekly usage profile.</p>
</section>
```

Append to `styles.css`:

```css
.week { display: grid; grid-template-columns: 3.5ch repeat(24, 1fr); gap: 2px; }
.week .day { font-family: var(--font-mono); font-size: var(--t--1); line-height: 1; align-self: center; }
.week .cell { display: block; aspect-ratio: 1 / 1; }
.cell.light  { background: var(--sem-green); }
.cell.medium { background: var(--sem-lime); }
.cell.heavy  { background: var(--sem-orange); }
.axis { margin-top: var(--s-1); }
.legend { margin-top: var(--s-1); display: flex; gap: var(--s-2); align-items: center; }
.legend .cell { width: 0.8rem; height: 0.8rem; aspect-ratio: auto; }
.week-summary { max-width: 60ch; margin-top: var(--s-3); }
```

**Verify**: `grep -o 'class="cell' explore/05-token-almanac/index.html | wc -l`
→ `171` (168 grid cells + 3 legend swatches)

### Step 10: How it works

Add after the week-profile section (three numbered timetable entries —
numbering is justified here: it is a real sequence):

```html
<hr class="rule-major">
<section class="wrap reveal">
  <h2 class="eyebrow">HOW IT WORKS</h2>
  <div class="grid-12">
    <div class="step"><p class="mono no">01</p><h3>Read</h3><p>token-oracle reads your provider's local usage logs. Claude Code is built in; adapters add more. No API calls — nothing leaves your machine.</p></div>
    <div class="step"><p class="mono no">02</p><h3>Measure</h3><p>it computes your observed burn rate over a sliding window, weighted by your own weekly usage profile.</p></div>
    <div class="step"><p class="mono no">03</p><h3>Forecast</h3><p>it projects usage to window end and tells you what's left before the cap: a percentage, an ETA, and a color.</p></div>
  </div>
</section>
```

Append to `styles.css`:

```css
.step { grid-column: span 4; }
.no { color: var(--blue); }
h3 {
  font-family: var(--font-display);
  font-stretch: 125%;
  font-weight: 700;
  font-size: var(--t-1);
  letter-spacing: -0.01em;
  text-transform: uppercase;
  margin-block: var(--s-1) var(--s-2);
}
```

**Verify**: `grep -c 'class="step"' explore/05-token-almanac/index.html` → `3`

### Step 11: Pillars

Add after the how-it-works section:

```html
<hr class="rule-major">
<section class="wrap reveal">
  <h2 class="eyebrow">PILLARS</h2>
  <div class="grid-12">
    <div class="pillar"><h3>Clarity</h3><p>understand your true token usage.</p></div>
    <div class="pillar"><h3>Foresight</h3><p>plan ahead with accuracy.</p></div>
    <div class="pillar"><h3>Confidence</h3><p>avoid surprises, stay in control.</p></div>
    <div class="pillar"><h3>Intention</h3><p>spend tokens with purpose.</p></div>
  </div>
</section>
```

Append to `styles.css`: `.pillar { grid-column: span 3; }`

**Verify**: `grep -c 'class="pillar"' explore/05-token-almanac/index.html` → `4`

### Step 12: Commands table

Add after the pillars section (reuses the table styles from Step 8; also
wrapped in `.table-scroll`):

```html
<hr class="rule-major">
<section class="wrap reveal">
  <h2 class="eyebrow">COMMANDS</h2>
  <div class="table-scroll">
    <table>
      <thead><tr><th scope="col">COMMAND</th><th scope="col">WHAT IT DOES</th></tr></thead>
      <tbody>
        <tr><td>token-oracle forecast</td><td>live forecast; --json for machine-readable output</td></tr>
        <tr><td>token-oracle dash</td><td>full-screen terminal dashboard</td></tr>
        <tr><td>token-oracle statusline</td><td>one-line ANSI fragment for any status bar</td></tr>
        <tr><td>token-oracle tmux</td><td>tmux status-right fragment</td></tr>
        <tr><td>token-oracle snapshot</td><td>writes forecast.json for other tools</td></tr>
        <tr><td>token-oracle doctor</td><td>checks configuration and data sources</td></tr>
      </tbody>
    </table>
  </div>
</section>
```

**Verify**: `grep -c 'token-oracle ' explore/05-token-almanac/index.html` → ≥ 6

### Step 13: Install strip

Add after the commands section:

```html
<hr class="rule-major">
<section class="wrap reveal">
  <h2 class="eyebrow">INSTALL</h2>
  <div class="install-strip">
    <p class="primary">pipx install token-oracle</p>
  </div>
  <p class="mono alternates">pip install token-oracle · uvx token-oracle</p>
  <p class="mono badges">Provider-agnostic · Zero dependencies · CLI first · Extensible</p>
</section>
```

Append to `styles.css`:

```css
.install-strip {
  border-top: 2px solid var(--blue);
  border-bottom: 2px solid var(--blue);
  padding-block: var(--s-6);
  text-align: center;
}
.primary {
  font-family: var(--font-mono);
  font-weight: 500;
  font-size: clamp(var(--t-1), 3.5vw, var(--t-3));
}
.alternates, .badges { text-align: center; margin-top: var(--s-3); }
```

**Verify**: `grep -c 'pipx install token-oracle' explore/05-token-almanac/index.html` → `1`

### Step 14: Footer

Replace the `<!-- Step 14 -->` comment inside `<footer>` with:

```html
<div class="wrap footer-inner">
  <p>MIT licensed. Built by Mateusz Muślewski.</p>
  <p class="links"><a href="https://pypi.org/project/token-oracle/">PyPI</a> · <a href="https://github.com/muslewski/token-oracle">GitHub</a> · <a href="https://github.com/muslewski/agentic-sage">agentic-sage</a></p>
</div>
```

Append to `styles.css`:

```css
footer { border-top: 1px solid var(--rule); font-size: var(--t--1); }
.footer-inner {
  display: flex; justify-content: space-between; flex-wrap: wrap;
  gap: var(--s-2); padding-block: var(--s-4);
}
```

**Verify**: `grep -c 'Mateusz Muślewski' explore/05-token-almanac/index.html` → `1`

### Step 15: CSS scroll-driven reveals

Append to `styles.css`. Base state (no wrapper) is fully visible, so
browsers without `animation-timeline: view()` support and reduced-motion
users get a complete static page — this fallback layering is deliberate:

```css
@supports (animation-timeline: view()) {
  @media (prefers-reduced-motion: no-preference) {
    .reveal {
      animation: rise linear both;
      animation-timeline: view();
      animation-range: entry 0% entry 40%;
    }
  }
}
@keyframes rise {
  from { opacity: 0; transform: translateY(12px); }
}
```

**Verify**: `grep -c 'animation-timeline' explore/05-token-almanac/styles.css`
→ `2` (the `@supports` query + the declaration), and
`grep -c 'prefers-reduced-motion' explore/05-token-almanac/styles.css` → `2`

### Step 16: Accessibility + reduced-motion pass

Confirm every line of the floor with commands (fix and re-run on any miss):

```bash
cd /home/kento/Repositories/token-oracle/explore/05-token-almanac
grep -c '<html lang="en">' index.html        # 1
grep -c '<h1' index.html                     # 1  (exactly one h1)
grep -c '<header' index.html                 # 1
grep -c '<main' index.html                   # 1
grep -c '<footer' index.html                 # 1
grep -c ':focus-visible' styles.css          # 1
grep -c 'prefers-reduced-motion' styles.css  # 2  (flip gate + reveal gate)
grep -c 'aria-hidden="true"' index.html      # 2  (board digits + week figure)
grep -c 'role="timer"' index.html            # 1
grep -c '<img' index.html                    # 0  (no images by design)
grep -c 'border-radius' styles.css           # 0
```

Contrast is guaranteed by construction: the page uses only the precomputed
pairs from the Design specification (ink/white ≈ 19:1, blue/white ≈ 7.1:1,
white-on-green chip ≈ 5.4:1, ink-on-orange chip ≈ 4.8:1 — all ≥ 4.5:1).
The heatmap is `aria-hidden` decoration summarized by the visible
`week-summary` paragraph. The only interactive elements are links —
keyboard-operable by default with the blue `:focus-visible` outline.

**Verify**: every grep above returns exactly the annotated count.

### Step 17: Responsive pass (usable at 360px)

Append to `styles.css`:

```css
@media (max-width: 720px) {
  .step, .pillar { grid-column: span 12; }
  section { padding-block: var(--s-6); }
  .hero { padding-block: var(--s-8) var(--s-6); }
}
```

Notes (already handled, listed so you can spot-check): the countdown scales
with `clamp(4rem, 14vw, 11rem)`; both tables scroll inside `.table-scroll`
(`overflow-x: auto`) instead of overflowing the page; heatmap cells are
`1fr` of a 24-column grid, ≈ 12px at 360px — readable.

**Verify**: `grep -c '@media (max-width: 720px)' explore/05-token-almanac/styles.css`
→ `1`, and `grep -c 'overflow-x: auto' explore/05-token-almanac/styles.css` → `1`

### Step 18: Smoke test

```bash
cd /home/kento/Repositories/token-oracle
node --check explore/05-token-almanac/main.js
python3 -m http.server 8045 --directory explore/05-token-almanac >/dev/null 2>&1 &
SERVER_PID=$!
sleep 1
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8045/index.html
curl -s http://127.0.0.1:8045/index.html | grep -c "Know when you'll hit the limit."
kill $SERVER_PID
```

This page is zero-build: there is no `dist/`; the tagline grep runs against
the served `index.html` source directly (no JSX apostrophe-escaping concern
applies here).

**Verify**: `node --check` exits 0 silently; first curl prints `200`;
second curl prints `2`.

### Step 19: Exploration README (+ screenshot if possible)

If browser tooling is available, take the screenshot per "Suggested
executor toolkit" (server running). If not available, skip the file and say
so in the README — that is NOT a STOP condition.

Create `explore/05-token-almanac/README.md`:

```markdown
# 05 — Token Almanac

Swiss timetable, CSS-only motion. Zero-build: open `index.html` directly,
or serve it:

    python3 -m http.server 8045 --directory explore/05-token-almanac

## Brand stance

**Contrast.** Prophecy as timetable: the oracle speaks in tabular numerals
on a rational Swiss grid. The argument: this audience trusts a schedule
more than a mascot.

## Design rationale

- **Aesthetic risk**: near-zero decoration — no images, no icons, no
  gradients, no border-radius; typography, rules, and two data
  visualizations (departures countdown, week heat calendar) carry the page.
- **Palette**: white `#FFFFFF`, ink `#101010`, rule `#B9B9B9`, timetable
  blue `#2B45D9` (the only accent); semaphore green/lime/orange/red
  (`#1F7A33` / `#93A11A` / `#C2681C` / `#BF3B2F`) confined to the heatmap
  cells and the two status chips.
- **Type**: Archivo (display at width 125 / weight 700; body 400/500) +
  IBM Plex Mono for all data; tabular numerals throughout; 1.25 modular
  type scale on an 8px spacing scale.
- **Signature element**: departures-board countdown ticking down from
  03:42:10 (the calm scenario's reset time) with a 300ms minute-rollover
  flip; wraps at zero — it is a labeled demo. Reduced motion: digits still
  update, no flip.
- **Motion**: CSS scroll-driven reveals behind
  `@supports (animation-timeline: view())`; fully visible without support
  or with reduced motion. Total JS: the clock only (≤ 80 lines).

## Screenshot

![Token Almanac landing page](./screenshot.png)

<!-- If no browser tooling was available, replace the image line with:
"No screenshot: browser tooling unavailable in the build environment." -->
```

Record here any Step 4 font fallback you had to apply.

**Verify**: `grep -c 'Contrast' explore/05-token-almanac/README.md` → ≥ 1

### Step 20: Flip the gallery row

In `explore/README.md`, in the row starting `| 05 | Token Almanac`, change
the final Status cell from `planned` to `built`. Change nothing else in the
file.

**Verify**: `grep '| 05 |' explore/README.md | grep -c 'built'` → `1`, and
`git diff --stat explore/README.md` → `1 file changed, 1 insertion(+), 1 deletion(-)`
(note: `git diff` compares worktree to index — if you already ran `git add`
on the file this prints nothing; use `git diff --cached --stat
explore/README.md` instead)

### Step 21: Update the plan index, final scope check, commit

1. In `plans/README.md`: if a `| 029 |` row exists in the execution-order
   table, set its Status cell to `DONE`. If it does not exist, append after
   the last numbered row:
   `| 029 | Exploration 05: Token Almanac — Swiss timetable, CSS-only motion | P2 | M | 024 | DONE |`
2. `git status --porcelain -- explore/ plans/README.md` → only paths under
   `explore/05-token-almanac/`, plus `explore/README.md` and
   `plans/README.md`. (The repo may carry OTHER pre-existing untracked
   entries — e.g. sibling plan files under `plans/` or a `.claude/`
   directory; entries you did not create are ignorable and must NOT be
   added or committed.)
3. Commit remaining work per the Git workflow section.

**Verify**: `grep -c '| 029 |' plans/README.md` → `1`, and after committing
`git status --porcelain -- explore/ plans/README.md` → empty (pre-existing
untracked entries you did not create are ignorable)

## Test plan

No unit-test framework applies (static page). The test surface is:

- The verification gates in every step above (greps, `node --check`,
  HTTP 200 smoke).
- Manual (do these in a browser if one is available; otherwise the
  command gates stand):
  - Watch the countdown tick once per second; roughly 11 seconds after
    load (03:42:10 → 03:41:59) the minutes-ones digit (`2` → `1`) does one
    90-degree flip (only cells whose value changed flip).
  - Emulate `prefers-reduced-motion: reduce` (DevTools → Rendering): digits
    still update every second, no flip, all sections fully visible.
  - Narrow the window to 360px: no horizontal page scroll; tables scroll
    inside their own containers; countdown shrinks to 4rem.
  - Tab through the page: every link shows the 2px blue focus outline.

## Done criteria

Machine-checkable. ALL must hold (paths relative to the repo root):

- [ ] `test -f explore/05-token-almanac/index.html && test -f explore/05-token-almanac/styles.css && test -f explore/05-token-almanac/main.js && test -f explore/05-token-almanac/README.md` → exit 0
- [ ] `node --check explore/05-token-almanac/main.js` → exit 0
- [ ] `[ "$(wc -l < explore/05-token-almanac/main.js)" -le 80 ] && echo OK` → `OK`
- [ ] Serve + smoke: `python3 -m http.server 8045 --directory explore/05-token-almanac & SERVER_PID=$!` then `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8045/index.html` → `200`; afterwards `kill "$SERVER_PID"` so the checklist doesn't leave an orphan server holding the port
- [ ] `grep -c "Know when you'll hit the limit." explore/05-token-almanac/index.html` → `2` (zero-build page — grep the source `index.html`; there is no `dist/`)
- [ ] `grep -c "prefers-reduced-motion" explore/05-token-almanac/styles.css` → `2`
- [ ] `grep -c "focus-visible" explore/05-token-almanac/styles.css` → ≥ 1
- [ ] `grep -c "animation-timeline" explore/05-token-almanac/styles.css` → `2`
- [ ] `grep -c "border-radius" explore/05-token-almanac/styles.css` → `0`
- [ ] `grep -c "<img" explore/05-token-almanac/index.html` → `0`
- [ ] `grep -c 'src="http' explore/05-token-almanac/index.html` → `0` (no external scripts/images; fonts arrive via `<link>` only)
- [ ] `grep -o 'class="cell' explore/05-token-almanac/index.html | wc -l` → `171`
- [ ] `grep '| 05 |' explore/README.md | grep -c 'built'` → `1`
- [ ] `git diff --name-only main..HEAD` (on the plan branch) lists only `explore/05-token-almanac/*`, `explore/README.md`, `plans/README.md`
- [ ] `grep -c '| 029 |' plans/README.md` → `1`, with its Status cell set to `DONE`

## STOP conditions

Stop and report back (do not improvise) if:

- `explore/BRIEF.md` does not exist — plan 024 has not run; this plan
  depends on it.
- The canonical copy in `explore/BRIEF.md` no longer matches the copy
  inlined in this plan (Step 1 tagline grep returns 0) — the brief drifted
  after this plan was written; the copy deck must be reconciled by the
  operator, not by you.
- `explore/05-token-almanac/` already exists with any file in it, or the
  `| 05 |` gallery row in `explore/README.md` is missing or not `planned` —
  another session owns this exploration.
- Any step's verification fails twice after a reasonable fix attempt.
- Completing a step would require editing an out-of-scope file
  (`explore/BRIEF.md`, another exploration folder, the root `README.md`,
  anything under `token_oracle/`, `tests/`, or `assets/`).

Explicitly NOT stop conditions (escape hatches are inside the steps):
the Archivo width axis not being served (Step 4 fallback), a browser
without `animation-timeline: view()` support (the `@supports` fallback is
the design), fonts.googleapis.com being unreachable (system fallback
stacks carry the page; note it in the README), and missing screenshot
tooling (note it in the README and continue).

## Maintenance notes

- The countdown start value (`START_SECONDS` = 03:42:10), its aria-label,
  the timetable rows, and the statusline caption are all coupled to the two
  honest scenarios in `explore/BRIEF.md`. If the brief's scenarios change,
  all four must change together.
- If the product's install command, subcommand list, or semaphore
  thresholds change, `explore/BRIEF.md` is re-synced from the root
  `README.md` first, then this page's copy follows the brief.
- Reviewer should scrutinize: honesty guardrails (no invented numbers or
  social proof anywhere), the straight apostrophe in the tagline, the
  chip contrast pairing (white-on-green but ink-on-orange — intentional),
  and that `main.js` stayed ≤ 80 lines with no scroll handlers.
- Deferred by design: no dark mode, no `<picture>`/asset pipeline, no
  favicon — this is a comparison prototype, not the shipping site. The
  winning direction gets re-implemented in the separate marketing-site
  repository; when that happens, mark the gallery row `archived`.
