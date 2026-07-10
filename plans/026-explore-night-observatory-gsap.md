# Plan 026: Exploration 02: Night Observatory — GSAP ScrollTrigger scrollytelling

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ada32e9..HEAD -- explore/ plans/README.md`
> Changes creating `explore/README.md`, `explore/BRIEF.md`, and index rows in
> `plans/README.md` are EXPECTED (plan 024 and advisor index maintenance land
> them after `ada32e9`). An EMPTY diff is also fine: `git diff` sees only
> tracked changes, and on a fresh clone `plans/` (and `explore/` before 024's
> commit) may still be untracked. Any change touching
> `explore/02-night-observatory/` or the `| 02 | Night Observatory` gallery
> row (i.e. it no longer says `planned`) is a STOP condition.

## Status

- **Priority**: P2
- **Effort**: L
- **Risk**: MED
- **Depends on**: plans/024-explore-scaffold-brief.md
- **Category**: direction
- **Planned at**: commit `ada32e9`, 2026-07-02

## Why this matters

token-oracle will get a marketing site in a separate repository. Before
committing to one visual direction, the operator is building several
complete, opinionated landing-page prototypes under `explore/`, all from the
same shared brief, so the only difference between them is design. This plan
builds exploration 02, "Night Observatory": a cinematic scrollytelling page
where one scroll is one night of observation — dusk to dawn — in three
pinned acts that mirror the product's three tenses (past / present /
future). It tests whether a narrative, film-like page can sell a
prediction-first CLI to terminal-dwelling developers.

## Current state

- `explore/README.md` and `explore/BRIEF.md` exist only after plan 024 has
  run (at `ada32e9` they do not exist yet). Step 1 gates on this.
- The gallery row this plan flips, exactly as plan 024 writes it in
  `explore/README.md`:

  ```
  | 02 | Night Observatory | remix | Vite + GSAP ScrollTrigger | `npm i && npm run dev` | plans/026 | planned |
  ```

- `explore/02-night-observatory/` does not exist.
- The repo is a Python CLI project. This plan touches **no Python** — it
  adds only a self-contained static-site prototype folder plus two markdown
  row edits. No Python tooling is involved.
- Commit style is conventional commits (see `git log --oneline`:
  `fix(dash): ...`, `chore(core): ...`, `test: ...`).
- The existing brand identity (the "remix" source) is the repo banner
  `assets/oracle-banner.webp`: lavender watercolor sky, masked oracle in
  white-and-lavender robes, hourglass in a magic circle, crescent moon,
  navy→violet gradient wordmark, gold sparkle accents, four pillar cards
  (CLARITY / FORESIGHT / CONFIDENCE / INTENTION), badge strip
  (Provider-agnostic · Zero dependencies · CLI first · Extensible).

### Rules inlined from `explore/BRIEF.md` (you do not need to open it)

- **Honesty guardrails (hard rules)**: no testimonials, no user counts, no
  "trusted by" logos, no star counts, no invented benchmarks, no named
  competitors. Every claim must trace to the product facts below. Sample
  numbers must come only from the two scenarios below.
- **Honest sample data**: Calm scenario: window `5h`, used 45,200 / cap
  220,000, projected 21 % at window end, resets in 3 h 42 m → green.
  Drama scenario: window `5h`, used 178,400 / cap 220,000, projected 108 %,
  ETA to cap 1 h 12 m, resets in 2 h 48 m → orange. Statusline mock:
  `[5h] 45.2k/220k · 21% · resets 3h42m`.
- **Product facts**: token-oracle is an offline CLI that forecasts when you
  will hit your AI-provider token cap. It reads the provider's local usage
  logs (Claude Code built in; adapters add more), computes an observed burn
  rate over a sliding window, and projects time-to-cap. No API calls;
  nothing leaves your machine. Python, zero runtime dependencies, MIT, on
  PyPI. Subcommands: `forecast`, `dash`, `statusline`, `tmux`, `snapshot`,
  `doctor`. Color semaphore on projected usage at window end (as % of cap):
  green < 85 % · lime 85–100 % · orange 100–120 % · red ≥ 120 %.
- **Accessibility floor**: semantic landmarks (`header/main/footer`, one
  `h1`); visible `:focus-visible` styles; body-text contrast ≥ 4.5:1; every
  animation gated behind `prefers-reduced-motion: reduce` (page fully
  readable with it on); interactive demos keyboard-operable; images have
  alt text; `lang="en"`; usable at 360 px width.
- **Performance floor**: `font-display: swap` on webfonts; canvas capped at
  devicePixelRatio 2; no scroll-handler layout thrash (transforms/opacity
  only); built pages keep the JS bundle < 250 KB gzipped.
- **Tech rules**: Google Fonts `<link>` allowed, always with a system
  fallback stack. No other runtime CDNs — all JS dependencies pinned via
  npm. No analytics, no trackers, no external network calls at runtime
  beyond fonts. Node ≥ 18.
- **Voice**: plain verbs, specific over clever, calm confidence; the oracle
  metaphor is seasoning, never fog; sentence case everywhere.

## Design specification

### (a) Brand stance

**Remix** — the page keeps the banner's night motifs (crescent, stars, gold
sparkle, violet) but trades watercolor-mascot softness for a cinematic
observatory night, because the audience distrusts cute and trusts
instruments. **Named aesthetic risk**: a single uninterrupted narrative — no
nav, no section links until the dawn section; the page commits to being
read like a film.

### (b) Design tokens

| Token | Hex | Used for |
|-------|-----|----------|
| zenith | `#0B1026` | top of sky / page background, dawn-card text, footer bg |
| indigo | `#1B2447` | lower sky, gauge track, panel/code backgrounds |
| horizon violet | `#6E6BD8` | brand nod; act transitions and the dawn gradient — **never body text** (contrast on zenith is below 4.5:1) |
| star gold | `#E8C36A` | stars, sparkle accents, kickers, links on dark, constellation trace |
| moonlight | `#F2EFE4` | text on dark, faint stars, dawn card background |
| dawn peach | `#F0B08C` | act III beam tint into the CTA section |
| night semaphore | green `#7DDB8A` / lime `#CDE060` / orange `#F0A05A` / red `#E86A5E` | forecast colors, brightened for dark-bg contrast; every text usage must verify ≥ 4.5:1 against `#0B1026` (step 9 script does this) |

### (c) Type

| Role | Google Fonts family | Weights | System fallback stack |
|------|--------------------|---------|----------------------|
| display | Fraunces (optical size large, variable) | 560 | `Georgia, serif` |
| body | Instrument Sans | 400, 500 | `system-ui, sans-serif` |
| data | IBM Plex Mono | 400, 500 | `ui-monospace, monospace` |

Loaded via one `<link>` with `display=swap` (exact URL in step 3). Headings
set `font-optical-sizing: auto` so Fraunces uses its large optical size.

### (d) Page wireframe (top to bottom)

```
┌──────────────────────────────────────────────────────┐
│ HERO (static, 100vh, zenith→indigo + CSS star field) │
│   ☾ crescent moon (pure CSS, decorative)             │
│   TOKEN ORACLE                (mono gold eyebrow)    │
│   Know when you'll hit the limit.        (the h1)    │
│   positioning line · secondary line (gold italic)    │
│   "Scroll — the night begins at dusk. ↓"             │
├──────────────────────────────────────────────────────┤
│ ACT I — PAST (pinned, scrub 0.5, end "+=150%")       │
│   kicker · h2 "Your week, as the sky saw it." · Read │
│   ┌ canvas #constellation ─────────────┐             │
│   │ 168 stars, 7 rows × 24 cols,       │ stars light │
│   │ jittered; faint gold line traces   │ up Mon→Sun  │
│   │ Mon 00:00 → Sun 23:00 with scrub   │ with p      │
│   └────────────────────────────────────┘             │
│   caption: sample-data honesty line                  │
├──────────────────────────────────────────────────────┤
│ ACT II — PRESENT (pinned, scrub 0.5, end "+=100%")   │
│   kicker · h2 · Measure copy                         │
│   SVG semicircle gauge fills to 20.5 % (green)       │
│   45,200 / 220,000 · window label · statusline mock  │
│   live burn counter (~2.5 tokens/s, labeled estimate)│
├──────────────────────────────────────────────────────┤
│ ACT III — FUTURE (pinned, scrub 0.5, end "+=150%")   │
│   kicker · h2 · Forecast copy                        │
│   ┌ canvas #beam ──────────────────────┐             │
│   │ dawn cone grows left→right; color  │             │
│   │ walks green→lime→orange (drama     │             │
│   │ readout), then relaxes to calm     │             │
│   └────────────────────────────────────┘             │
│   mono readout line + semaphore-legend caption       │
├──────────────────────────────────────────────────────┤
│ DAWN (static, warm; zenith→violet→peach gradient)    │
│   moonlight card: h2 install CTA                     │
│   pipx install token-oracle  (+ pip / uvx alts)      │
│   View on GitHub                                     │
│   six-command mono grid · four pillars as ★ stars    │
│   proof-badge strip                                  │
├──────────────────────────────────────────────────────┤
│ FOOTER (zenith bg)                                   │
│   MIT licensed. Built by Mateusz Muślewski.          │
│   PyPI · GitHub · agentic-sage                       │
└──────────────────────────────────────────────────────┘
```

### (e) Signature element: the constellation ledger

One 2D canvas (`#constellation`), no WebGL. 168 stars — one per hour bucket
of a sample week, 7 rows (Mon top → Sun bottom) × 24 columns (00:00 →
23:00), jittered so it reads as sky, not grid.

**Mock weekly data (deterministic — invent nothing).** For star index
`i = d*24 + h` (`d` 0..6 Mon..Sun, `h` 0..23):

```
HOUR_CURVE = [1,1,0,0,0,0,1,2,5,8,9,7,5,8,10,9,8,6,4,3,3,2,2,1]   # 24 values
DAY_FACTOR = [0.9, 1.0, 1.0, 0.95, 0.8, 0.25, 0.15]               # Mon..Sun
USAGE[i]   = round(HOUR_CURVE[h] * DAY_FACTOR[d] * 10) + ((i*37) % 5)
MAX_USAGE  = max(USAGE)                                            # = 104
```

This yields workday daytime peaks and low weekends. Sanity triple:
`len=168, max=104, USAGE[14]=93, USAGE[38]=101` (verified in step 5).

**Geometry** (all in CSS pixels; `w`,`h` = canvas CSS size):

```
jx = (((i*73)  % 100) / 100 - 0.5) * 0.6        # horizontal jitter, fraction of cell
jy = (((i*131) % 100) / 100 - 0.5) * 0.6        # vertical jitter
x  = (h + 0.5 + jx) * (w / 24)
y  = (d + 0.5 + jy) * (h_canvas / 7)
r  = 0.8 + 2.6 * (USAGE[i] / MAX_USAGE)          # radius in CSS px
litAlpha = 0.25 + 0.75 * (USAGE[i] / MAX_USAGE)
color    = star gold #E8C36A if USAGE[i] >= 0.6*MAX_USAGE else moonlight #F2EFE4
```

**States and behavior**: at act-I timeline progress `p` (0..1), stars with
`i <= floor(p*167)` are lit at `litAlpha`; the rest render at alpha `0.08`
(unlit). A faint constellation line — polyline through stars `0..floor(p*167)`
in `i` order (Mon 00:00 → Sun 23:00), `rgba(232,195,106,0.12)`, lineWidth 1 —
traces the week as the user scrubs. Backing store capped at
devicePixelRatio 2. **Reduced motion**: no timeline; draw once at `p = 1`
(all stars lit, full trace). The canvas carries `role="img"` and a
descriptive `aria-label` (copy section).

### (f) Motion spec

- `gsap.registerPlugin(ScrollTrigger)`. One GSAP timeline/tween per act,
  each in a pinned section: act I `end: "+=150%"`, act II `end: "+=100%"`,
  act III `end: "+=150%"`, all `start: "top top"`, `pin: true`,
  `scrub: 0.5`, `ease: "none"` (scrub provides the smoothing; triggers
  scrub at 0.5 s lag).
- Canvas draw loops are driven by GSAP timeline progress (`onUpdate` on the
  tween), never by raw scroll events. No scroll-jacking: native scroll
  only; pinning via ScrollTrigger `pin`.
- Act II additionally animates the SVG gauge `stroke-dashoffset` 100 → 79.5
  and a count-up 0 → 45,200; the burn counter is a 1 Hz `setInterval`
  (time-driven, not scroll-driven).
- Act III: beam reveal `reveal = min(p/0.7, 1)`; beam color walks
  green→lime over `p` 0–0.35, lime→orange over 0.35–0.7, holds orange
  0.7–0.85 (drama readout), then snaps to calm green for `p ≥ 0.85`
  (calm readout).
- **`prefers-reduced-motion: reduce` (exact behavior)**: NO pinning, no
  scrub, no ScrollTrigger instances at all — the three acts render as
  static stacked sections with their end-state visuals pre-drawn
  (constellation at `p=1`, gauge filled to 20.5 % showing 45,200, beam in
  the calm state), and the burn counter shows a static line (copy section).
  A CSS media block also kills any CSS animation/transition.
- **`<noscript>`**: all copy is plain static HTML, readable without JS; a
  noscript note says so. The HTML ships end-state text (gauge number,
  calm readout, static counter line) so a no-JS render is honest, not
  zeroed.

## Copy (final, verbatim)

The executor writes ZERO copy. Every string on the page is below, in
display order. The tagline `Know when you'll hit the limit.` (straight
apostrophe) is the `h1` and also appears in the `<title>`.

**Head**
- `<title>`: `Token Oracle — Know when you'll hit the limit.`
- meta description: `Usage monitors tell you what you spent. Token Oracle tells you what happens next.`

**Noscript note**
- `This page uses JavaScript only for its scroll animations. Everything below is fully readable without it.`

**Hero**
- Eyebrow (mono): `TOKEN ORACLE`
- h1 (the tagline, exact): `Know when you'll hit the limit.`
- Positioning: `Usage monitors tell you what you spent. Token Oracle tells you what happens next.`
- Secondary: `It's a forecast, not a bill.`
- Scroll hint: `Scroll — the night begins at dusk. ↓`

**Act I — Past**
- Kicker: `Act I — Past`
- h2: `Your week, as the sky saw it.`
- Body: `token-oracle reads your provider's local usage logs. Claude Code is built in; adapters add more. No API calls — nothing leaves your machine.`
- Canvas aria-label: `Constellation chart: 168 stars, one per hour of a sample week. Brighter stars mark heavier token usage; weekday afternoons shine brightest.`
- Caption: `168 hours of a sample week, one star per hour. Brighter star, heavier hour. Sample data — your sky will look different.`

**Act II — Present**
- Kicker: `Act II — Present`
- h2: `Where the night stands now.`
- Body: `It computes your observed burn rate over a sliding window, weighted by your own weekly usage profile.`
- Gauge number: `45,200` ` / 220,000` (the first number is the count-up target)
- Gauge label: `tokens used this window · [5h]`
- Statusline mock (mono, code): `[5h] 45.2k/220k · 21% · resets 3h42m`
- Burn counter, static/no-JS/reduced-motion text: `At the sample average rate, reading this page burns about 150 tokens a minute — an estimate, not a measurement.`
- Burn counter, live template (JS, motion allowed): `` tokens burned while you read this page: ~${n} — at the sample average rate `` (n = seconds on page × 2.51, rounded, locale-formatted)
- Caption: `The counter is an estimate from the sample scenario's average rate (45,200 tokens over a 5-hour window ≈ 2.5 tokens/s), not a measurement.`

**Act III — Future**
- Kicker: `Act III — Future`
- h2: `The dawn you can see coming.`
- Body: `It projects usage to window end and tells you what's left before the cap: a percentage, an ETA, and a color.`
- Canvas aria-label: `A cone of dawn light projecting across the night sky. Its color walks the forecast semaphore from green through orange as projected usage rises, then relaxes to green.`
- Readout, phase 1 template (p < 0.7): `` projected ${pct}% of cap `` with `pct = round(108 * p / 0.7)`
- Readout, drama hold (0.7 ≤ p < 0.85): `projected 108% of cap · ETA 1h12m · resets in 2h48m`
- Readout, calm relax (p ≥ 0.85, also the initial/no-JS/reduced text): `projected 21% of cap · resets in 3h42m`
- Caption: `Two sample forecasts from the shared brief — a heavy afternoon, then a calm one. green < 85% · lime 85–100% · orange 100–120% · red ≥ 120%.`

**Dawn**
- h2: `Morning. Install it before the next window opens.`
- Install primary (code): `pipx install token-oracle`
- Install alternates: `also: ` `pip install token-oracle` ` · ` `uvx token-oracle`
- Secondary CTA link text: `View on GitHub` → `https://github.com/muslewski/token-oracle`
- h3: `Six commands`
- Command grid (six tiles, command + description):
  - `token-oracle forecast` — `live forecast — time left before your cap (--json available)`
  - `token-oracle dash` — `full-screen terminal dashboard`
  - `token-oracle statusline` — `one-line ANSI fragment for any status bar`
  - `token-oracle tmux` — `status-right fragment for tmux`
  - `token-oracle snapshot` — `writes forecast.json for other tools`
  - `token-oracle doctor` — `checks configuration and data sources`
- h3: `Four fixed stars`
- Pillars (★ glyph is decorative, `aria-hidden="true"`):
  - `Clarity — understand your true token usage.`
  - `Foresight — plan ahead with accuracy.`
  - `Confidence — avoid surprises, stay in control.`
  - `Intention — spend tokens with purpose.`
- Badges: `Provider-agnostic · Zero dependencies · CLI first · Extensible`

**Footer**
- `MIT licensed. Built by Mateusz Muślewski.`
- Links: `PyPI` → `https://pypi.org/project/token-oracle/` · `GitHub` → `https://github.com/muslewski/token-oracle` · `agentic-sage` → `https://github.com/muslewski/agentic-sage`

## Commands you will need

All commands run from `/home/kento/Repositories/token-oracle` unless a `cd`
is shown — with ONE exception: Verify commands that reference bare file
names (`index.html`, `style.css`, `main.js`, `./package.json`) run from
inside `explore/02-night-observatory/`; `cd` there first (Steps 2, 4, 6, 7
and 10 use this shorthand). Node ≥ 18 required (v22.12.0 verified on this
machine).

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Node version | `node --version` | `v18` or higher |
| Scaffold | `npm_config_yes=true npm create vite@latest . -- --template vanilla` (inside the exploration folder) | files scaffolded, "Done" message |
| Install deps | `npm install && npm install "gsap@^3.12.0"` | exit 0, `package-lock.json` present |
| Build | `npm run build` | exit 0, `dist/` created |
| Preview | `npm run preview -- --port 4173 --strictPort` | serves `dist/` on :4173 |
| Smoke | `curl -s -o /dev/null -w "%{http_code}" http://localhost:4173/` | `200` |
| Scope | `git status --porcelain` | only in-scope paths |

No Python, pytest, ruff, or mypy anywhere in this plan.

## Suggested executor toolkit

- If a browser/screenshot tool is available in your environment, use it in
  step 12 to capture `screenshot.png` at 1280 px wide. If not, the README
  note in step 12 covers it — missing browser tooling is NOT a stop.

## Scope

**In scope** (the only paths you may create/modify):
- `explore/02-night-observatory/` — the whole folder (create)
- `explore/README.md` — ONLY the `| 02 | Night Observatory ... |` gallery row
- `plans/README.md` — ONLY this plan's status row

**Out of scope** (do NOT touch, even though they look related):
- `token_oracle/`, `tests/`, `assets/` — the Python product; this plan has
  no Python surface.
- Root `README.md` — explorations are internal; do not advertise them.
- Every OTHER `explore/` folder (`01-*`, `03-*`, `04-*`, `05-*`) — they
  belong to plans 025/027/028/029.
- `explore/BRIEF.md` — operator-approved wording; a wording problem is a
  report, not an edit.

## Git workflow

- Branch: `advisor/026-explore-night-observatory-gsap` (from `main`)
- Conventional commits, one per logical unit, e.g.:
  - `feat(explore): scaffold night observatory exploration`
  - `feat(explore): night observatory constellation ledger act`
  - `docs(explore): night observatory readme; flip gallery row to built`
- Do NOT push or open a PR unless the operator instructed it.
- Note: the Vite template's `.gitignore` keeps `node_modules/` and `dist/`
  out of git — never commit either.

## Steps

### Step 1: Prerequisites and drift check

```bash
cd /home/kento/Repositories/token-oracle
test -f explore/BRIEF.md && echo BRIEF-OK || echo BRIEF-MISSING
```

If `BRIEF-MISSING`: **STOP** — plan 024 has not run; it must run first.

```bash
test -e explore/02-night-observatory && echo EXISTS || echo ABSENT
grep -F '| 02 | Night Observatory' explore/README.md
node --version
git switch -c advisor/026-explore-night-observatory-gsap
```

**Verify**: the folder check prints `ABSENT`; the grep prints one row ending
in `| planned |`; `node --version` is ≥ v18;
`git branch --show-current` → `advisor/026-explore-night-observatory-gsap`.
If the folder exists or the row is missing/not `planned`, STOP (another
session may own it).

### Step 2: Scaffold Vite (vanilla) and install GSAP

```bash
cd /home/kento/Repositories/token-oracle
mkdir -p explore/02-night-observatory
cd explore/02-night-observatory
npm_config_yes=true npm create vite@latest . -- --template vanilla
```

Expected scaffold layout (flat — the vanilla template has no `src/`):
`index.html`, `main.js`, `style.css`, `counter.js`, `javascript.svg`,
`public/vite.svg`, `package.json`, `.gitignore`. If `index.html`,
`main.js`, `style.css`, or `package.json` is missing from the folder root
(e.g. a newer create-vite moved to a `src/` layout), **STOP** — the plan's
file references would all be wrong. If create-vite prompts despite the
flags, choose framework "Vanilla", variant "JavaScript", then re-check the
layout.

```bash
npm install
npm install "gsap@^3.12.0"
rm counter.js javascript.svg public/vite.svg
rmdir public
```

**Verify**:
`test -f index.html && test -f main.js && test -f style.css && test -f package.json && echo LAYOUT-OK` → `LAYOUT-OK`;
`node -e "console.log(require('./package.json').dependencies.gsap)"` →
`^3.12.0`; `test -f package-lock.json && echo LOCK-OK` → `LOCK-OK`.

### Step 3: Full page markup (`index.html`) + base styles + JS skeleton

Replace `explore/02-night-observatory/index.html` entirely with:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Token Oracle — Know when you'll hit the limit.</title>
    <meta name="description" content="Usage monitors tell you what you spent. Token Oracle tells you what happens next." />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,560&family=IBM+Plex+Mono:wght@400;500&family=Instrument+Sans:wght@400;500&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="/style.css" />
  </head>
  <body>
    <noscript>
      <p class="noscript-note">This page uses JavaScript only for its scroll animations. Everything below is fully readable without it.</p>
    </noscript>

    <header id="hero">
      <div class="moon" aria-hidden="true"></div>
      <p class="wordmark">TOKEN ORACLE</p>
      <h1>Know when you'll hit the limit.</h1>
      <p class="positioning">Usage monitors tell you what you spent. Token Oracle tells you what happens next.</p>
      <p class="secondary">It's a forecast, not a bill.</p>
      <p class="scroll-hint" aria-hidden="true">Scroll — the night begins at dusk. ↓</p>
    </header>

    <main>
      <section id="act-past" class="act" aria-labelledby="act-past-title">
        <div class="act-inner">
          <p class="kicker">Act I — Past</p>
          <h2 id="act-past-title">Your week, as the sky saw it.</h2>
          <p class="act-body">token-oracle reads your provider's local usage logs. Claude Code is built in; adapters add more. No API calls — nothing leaves your machine.</p>
          <canvas id="constellation" width="960" height="420" role="img" aria-label="Constellation chart: 168 stars, one per hour of a sample week. Brighter stars mark heavier token usage; weekday afternoons shine brightest."></canvas>
          <p class="caption">168 hours of a sample week, one star per hour. Brighter star, heavier hour. Sample data — your sky will look different.</p>
        </div>
      </section>

      <section id="act-present" class="act" aria-labelledby="act-present-title">
        <div class="act-inner">
          <p class="kicker">Act II — Present</p>
          <h2 id="act-present-title">Where the night stands now.</h2>
          <p class="act-body">It computes your observed burn rate over a sliding window, weighted by your own weekly usage profile.</p>
          <div class="gauge-wrap">
            <svg id="gauge" viewBox="0 0 240 140" aria-hidden="true" focusable="false">
              <path class="gauge-track" d="M 20 130 A 100 100 0 0 1 220 130" pathLength="100" />
              <path id="gauge-fill" d="M 20 130 A 100 100 0 0 1 220 130" pathLength="100" />
            </svg>
            <p class="gauge-number mono"><span id="gauge-count">45,200</span> / 220,000</p>
            <p class="gauge-label">tokens used this window · [5h]</p>
          </div>
          <p class="statusline"><code>[5h] 45.2k/220k · 21% · resets 3h42m</code></p>
          <p id="burn-counter" class="burn">At the sample average rate, reading this page burns about 150 tokens a minute — an estimate, not a measurement.</p>
          <p class="caption">The counter is an estimate from the sample scenario's average rate (45,200 tokens over a 5-hour window ≈ 2.5 tokens/s), not a measurement.</p>
        </div>
      </section>

      <section id="act-future" class="act" aria-labelledby="act-future-title">
        <div class="act-inner">
          <p class="kicker">Act III — Future</p>
          <h2 id="act-future-title">The dawn you can see coming.</h2>
          <p class="act-body">It projects usage to window end and tells you what's left before the cap: a percentage, an ETA, and a color.</p>
          <canvas id="beam" width="960" height="420" role="img" aria-label="A cone of dawn light projecting across the night sky. Its color walks the forecast semaphore from green through orange as projected usage rises, then relaxes to green."></canvas>
          <p id="forecast-readout" class="readout">projected 21% of cap · resets in 3h42m</p>
          <p class="caption">Two sample forecasts from the shared brief — a heavy afternoon, then a calm one. green &lt; 85% · lime 85–100% · orange 100–120% · red ≥ 120%.</p>
        </div>
      </section>

      <section id="dawn" aria-labelledby="dawn-title">
        <div class="dawn-card">
          <h2 id="dawn-title">Morning. Install it before the next window opens.</h2>
          <p class="install-primary"><code>pipx install token-oracle</code></p>
          <p class="install-alt">also: <code>pip install token-oracle</code> · <code>uvx token-oracle</code></p>
          <p><a class="cta-secondary" href="https://github.com/muslewski/token-oracle">View on GitHub</a></p>
          <h3>Six commands</h3>
          <ul class="cmd-grid">
            <li><code>token-oracle forecast</code><span>live forecast — time left before your cap (<code>--json</code> available)</span></li>
            <li><code>token-oracle dash</code><span>full-screen terminal dashboard</span></li>
            <li><code>token-oracle statusline</code><span>one-line ANSI fragment for any status bar</span></li>
            <li><code>token-oracle tmux</code><span>status-right fragment for tmux</span></li>
            <li><code>token-oracle snapshot</code><span>writes forecast.json for other tools</span></li>
            <li><code>token-oracle doctor</code><span>checks configuration and data sources</span></li>
          </ul>
          <h3>Four fixed stars</h3>
          <ul class="pillars">
            <li><span class="star" aria-hidden="true">★</span><strong>Clarity</strong> — understand your true token usage.</li>
            <li><span class="star" aria-hidden="true">★</span><strong>Foresight</strong> — plan ahead with accuracy.</li>
            <li><span class="star" aria-hidden="true">★</span><strong>Confidence</strong> — avoid surprises, stay in control.</li>
            <li><span class="star" aria-hidden="true">★</span><strong>Intention</strong> — spend tokens with purpose.</li>
          </ul>
          <p class="badges mono">Provider-agnostic · Zero dependencies · CLI first · Extensible</p>
        </div>
      </section>
    </main>

    <footer>
      <p>MIT licensed. Built by Mateusz Muślewski.</p>
      <p>
        <a href="https://pypi.org/project/token-oracle/">PyPI</a> ·
        <a href="https://github.com/muslewski/token-oracle">GitHub</a> ·
        <a href="https://github.com/muslewski/agentic-sage">agentic-sage</a>
      </p>
    </footer>

    <script type="module" src="/main.js"></script>
  </body>
</html>
```

Replace `explore/02-night-observatory/style.css` entirely with the design
tokens and base styles (sections add their styles in later steps —
**append**, never rewrite):

```css
:root {
  --zenith: #0B1026;
  --indigo: #1B2447;
  --violet: #6E6BD8;
  --gold: #E8C36A;
  --moonlight: #F2EFE4;
  --peach: #F0B08C;
  --sem-green: #7DDB8A;
  --sem-lime: #CDE060;
  --sem-orange: #F0A05A;
  --sem-red: #E86A5E;
  --font-display: "Fraunces", Georgia, serif;
  --font-body: "Instrument Sans", system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

html { scroll-behavior: auto; } /* native scroll; GSAP pins, never hijacks */

body {
  background: var(--zenith);
  color: var(--moonlight);
  font-family: var(--font-body);
  font-weight: 400;
  font-size: 1.0625rem;
  line-height: 1.6;
}

h1, h2, h3 {
  font-family: var(--font-display);
  font-weight: 560;
  font-optical-sizing: auto;
  line-height: 1.15;
}

code, .mono { font-family: var(--font-mono); }

a { color: var(--gold); }

:focus-visible { outline: 3px solid var(--gold); outline-offset: 3px; border-radius: 2px; }

img, svg { max-width: 100%; height: auto; }
canvas { max-width: 100%; }

.noscript-note { padding: 1rem; background: var(--indigo); text-align: center; }

@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
  html { scroll-behavior: auto !important; }
}
```

Replace `explore/02-night-observatory/main.js` entirely with this skeleton
(acts append below the markers in steps 5–7):

```js
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

// prefers-reduced-motion: reduce → no pinning, no scrub, static end-states.
const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const DPR = Math.min(window.devicePixelRatio || 1, 2); // perf floor: cap at 2

// Size a canvas backing store to its CSS box (dpr-capped); drawing then
// uses CSS-pixel coordinates.
function setupCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.round(rect.width * DPR);
  canvas.height = Math.round(rect.height * DPR);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  return { ctx, w: rect.width, h: rect.height };
}

function lerp(a, b, t) { return a + (b - a) * t; }
function hexToRgb(hex) { return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)); }
function mix(a, b, t) { return a.map((v, i) => Math.round(v + (b[i] - v) * t)); }

// --- ACT I: constellation ledger (step 5) ---
// --- ACT II: burn gauge + counter (step 6) ---
// --- ACT III: projection beam (step 7) ---
```

**Verify**: `cd explore/02-night-observatory && npm run build` → exit 0;
`grep -c "Know when you'll hit the limit." index.html` → `2`;
`grep -c 'lang="en"' index.html` → `1`;
`grep -c "display=swap" index.html` → `1`.

### Step 4: Hero and shared act styles

Append to `style.css`:

```css
#hero {
  min-height: 100vh;
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  gap: 1.25rem; text-align: center; padding: 2rem 1.25rem;
  background:
    radial-gradient(1.5px 1.5px at 12% 22%, rgba(242,239,228,0.9), transparent 60%),
    radial-gradient(1px 1px at 28% 12%, rgba(242,239,228,0.7), transparent 60%),
    radial-gradient(2px 2px at 41% 30%, rgba(232,195,106,0.8), transparent 60%),
    radial-gradient(1px 1px at 57% 8%, rgba(242,239,228,0.6), transparent 60%),
    radial-gradient(1.5px 1.5px at 66% 25%, rgba(242,239,228,0.8), transparent 60%),
    radial-gradient(1px 1px at 78% 15%, rgba(232,195,106,0.6), transparent 60%),
    radial-gradient(2px 2px at 88% 34%, rgba(242,239,228,0.7), transparent 60%),
    radial-gradient(1px 1px at 8% 55%, rgba(242,239,228,0.5), transparent 60%),
    linear-gradient(180deg, var(--zenith) 0%, var(--indigo) 100%);
}
.moon { position: relative; width: 56px; height: 56px; border-radius: 50%; background: var(--moonlight); overflow: hidden; }
.moon::after { content: ""; position: absolute; top: -8px; left: 14px; width: 56px; height: 56px; border-radius: 50%; background: var(--zenith); }
.wordmark { font-family: var(--font-mono); font-size: 0.8125rem; letter-spacing: 0.35em; color: var(--gold); }
#hero h1 { font-size: clamp(2.25rem, 6vw, 4.25rem); max-width: 16ch; }
.positioning { font-size: clamp(1.0625rem, 2.2vw, 1.375rem); max-width: 42ch; }
.secondary { color: var(--gold); font-style: italic; }
.scroll-hint { margin-top: 2.5rem; font-family: var(--font-mono); font-size: 0.8125rem; opacity: 0.75; }

.act { min-height: 100vh; display: flex; align-items: center; background: linear-gradient(180deg, var(--zenith), var(--indigo) 140%); }
.act-inner { width: min(960px, 100% - 2.5rem); margin: 0 auto; padding: 3rem 0; }
.kicker { font-family: var(--font-mono); color: var(--gold); letter-spacing: 0.2em; text-transform: uppercase; font-size: 0.8125rem; margin-bottom: 0.75rem; }
.act h2 { font-size: clamp(1.75rem, 4.5vw, 3rem); margin-bottom: 1rem; }
.act-body { max-width: 58ch; margin-bottom: 2rem; }
.caption { font-size: 0.875rem; opacity: 0.85; max-width: 60ch; margin-top: 1rem; }
#constellation, #beam { display: block; width: 100%; height: 420px; }
@media (max-width: 767.98px) { #constellation, #beam { height: 300px; } }
```

**Verify**: `npm run build` → exit 0; `grep -c '#hero' style.css` → ≥ 1.

### Step 5: Act I — the constellation ledger (signature element)

Append to `main.js`, replacing nothing (the mock-data rule is authoritative
— type it exactly):

```js
const HOUR_CURVE = [1,1,0,0,0,0,1,2,5,8,9,7,5,8,10,9,8,6,4,3,3,2,2,1]; // 24 values
const DAY_FACTOR = [0.9, 1.0, 1.0, 0.95, 0.8, 0.25, 0.15]; // Mon..Sun
const USAGE = Array.from({ length: 168 }, (_, i) => {
  const d = Math.floor(i / 24), h = i % 24;
  return Math.round(HOUR_CURVE[h] * DAY_FACTOR[d] * 10) + ((i * 37) % 5);
});
const MAX_USAGE = Math.max(...USAGE);

function computeStars(w, h) {
  const stars = [];
  for (let i = 0; i < 168; i++) {
    const d = Math.floor(i / 24), hr = i % 24;
    const jx = (((i * 73) % 100) / 100 - 0.5) * 0.6;
    const jy = (((i * 131) % 100) / 100 - 0.5) * 0.6;
    stars.push({
      x: (hr + 0.5 + jx) * (w / 24),
      y: (d + 0.5 + jy) * (h / 7),
      r: 0.8 + 2.6 * (USAGE[i] / MAX_USAGE),
      alpha: 0.25 + 0.75 * (USAGE[i] / MAX_USAGE),
      bright: USAGE[i] >= 0.6 * MAX_USAGE,
    });
  }
  return stars;
}

function drawConstellation(ctx, w, h, stars, p) {
  ctx.clearRect(0, 0, w, h);
  const lit = Math.floor(p * 167);
  ctx.strokeStyle = "rgba(232,195,106,0.12)"; // star gold, faint trace
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let i = 0; i <= lit; i++) {
    const s = stars[i];
    if (i === 0) ctx.moveTo(s.x, s.y); else ctx.lineTo(s.x, s.y);
  }
  ctx.stroke();
  for (let i = 0; i < 168; i++) {
    const s = stars[i];
    ctx.globalAlpha = i <= lit ? s.alpha : 0.08;
    ctx.fillStyle = s.bright ? "#E8C36A" : "#F2EFE4";
    ctx.beginPath();
    ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

function initConstellation() {
  const { ctx, w, h } = setupCanvas(document.getElementById("constellation"));
  const stars = computeStars(w, h);
  if (REDUCED) { drawConstellation(ctx, w, h, stars, 1); return; }
  const state = { p: 0 };
  gsap.to(state, {
    p: 1,
    ease: "none",
    scrollTrigger: { trigger: "#act-past", start: "top top", end: "+=150%", pin: true, scrub: 0.5 },
    onUpdate: () => drawConstellation(ctx, w, h, stars, state.p),
  });
  drawConstellation(ctx, w, h, stars, 0);
}
initConstellation();
```

**Verify** (data rule typed correctly):

```bash
node -e 'const HC=[1,1,0,0,0,0,1,2,5,8,9,7,5,8,10,9,8,6,4,3,3,2,2,1],DF=[0.9,1,1,0.95,0.8,0.25,0.15];const U=Array.from({length:168},(_,i)=>{const d=Math.floor(i/24),h=i%24;return Math.round(HC[h]*DF[d]*10)+((i*37)%5)});console.log(U.length,Math.max(...U),U[14],U[38])'
```

→ prints `168 104 93 101`. Then `npm run build` → exit 0.

### Step 6: Act II — burn gauge and live counter

Append to `style.css`:

```css
.gauge-wrap { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; margin: 1.5rem 0; }
#gauge { width: min(320px, 80%); }
.gauge-track { fill: none; stroke: var(--indigo); stroke-width: 12; stroke-linecap: round; }
#gauge-fill { fill: none; stroke: var(--sem-green); stroke-width: 12; stroke-linecap: round; stroke-dasharray: 100; stroke-dashoffset: 79.5; }
.gauge-number { font-size: clamp(1.5rem, 4vw, 2.25rem); }
.gauge-label { font-size: 0.875rem; opacity: 0.85; }
.statusline code { display: inline-block; background: var(--indigo); padding: 0.5rem 0.875rem; border-radius: 6px; }
.burn { font-family: var(--font-mono); color: var(--gold); margin-top: 1.25rem; }
```

(`stroke-dashoffset: 79.5` = 100 − 20.5; 45,200 / 220,000 ≈ 20.5 %. The
CSS default is the END state so no-JS and reduced-motion renders are
honest.)

Append to `main.js`:

```js
function initGauge() {
  const fill = document.getElementById("gauge-fill");
  const count = document.getElementById("gauge-count");
  const END_OFFSET = 79.5; // 100 - 20.5; 45,200 / 220,000 ≈ 20.5 %
  if (REDUCED) {
    fill.style.strokeDashoffset = END_OFFSET;
    count.textContent = "45,200";
    return;
  }
  count.textContent = "0";
  const state = { n: 0 };
  const tl = gsap.timeline({
    scrollTrigger: { trigger: "#act-present", start: "top top", end: "+=100%", pin: true, scrub: 0.5 },
  });
  tl.fromTo(fill, { strokeDashoffset: 100 }, { strokeDashoffset: END_OFFSET, ease: "none" }, 0);
  tl.to(state, {
    n: 45200,
    ease: "none",
    onUpdate: () => { count.textContent = Math.round(state.n).toLocaleString("en-US"); },
  }, 0);
}
initGauge();

function initBurnCounter() {
  if (REDUCED) return; // static line already in the HTML
  const el = document.getElementById("burn-counter");
  const RATE = 45200 / (5 * 3600); // ≈ 2.51 tokens/s — calm scenario average
  const t0 = Date.now();
  setInterval(() => {
    const n = Math.round(((Date.now() - t0) / 1000) * RATE);
    el.textContent = `tokens burned while you read this page: ~${n.toLocaleString("en-US")} — at the sample average rate`;
  }, 1000);
}
initBurnCounter();
```

**Verify**: `npm run build` → exit 0;
`grep -c "45200 / (5 \* 3600)" main.js` → `1`;
`grep -c "79.5" style.css` → `1`.

### Step 7: Act III — the projection beam

Append to `style.css`:

```css
.readout { font-family: var(--font-mono); font-size: clamp(1.125rem, 3vw, 1.5rem); color: var(--sem-green); margin-top: 1rem; }
```

Append to `main.js`:

```js
const GREEN = "#7DDB8A", LIME = "#CDE060", ORANGE = "#F0A05A";

function beamRgb(p) {
  const g = hexToRgb(GREEN), l = hexToRgb(LIME), o = hexToRgb(ORANGE);
  if (p < 0.35) return mix(g, l, p / 0.35);
  if (p < 0.7) return mix(l, o, (p - 0.35) / 0.35);
  if (p < 0.85) return o;          // drama hold
  return g;                        // relaxed to the calm scenario
}

function readoutText(p) {
  if (p < 0.7) return `projected ${Math.round((108 * p) / 0.7)}% of cap`;
  if (p < 0.85) return "projected 108% of cap · ETA 1h12m · resets in 2h48m";
  return "projected 21% of cap · resets in 3h42m";
}

function drawBeam(ctx, w, h, p) {
  ctx.clearRect(0, 0, w, h);
  const reveal = p < 0.85 ? Math.min(p / 0.7, 1) : 1;
  const [r, g, b] = beamRgb(p);
  const ox = 0.08 * w, oy = 0.78 * h;                       // beam origin: the coming dawn
  const ux = lerp(ox, w, reveal), uy = lerp(oy, 0.12 * h, reveal); // upper edge tip
  const lx = lerp(ox, w, reveal), ly = lerp(oy, 0.70 * h, reveal); // lower edge tip
  const grad = ctx.createLinearGradient(ox, oy, w, 0.4 * h);
  grad.addColorStop(0, `rgba(${r},${g},${b},0.55)`);
  grad.addColorStop(1, "rgba(240,176,140,0.10)");           // dawn peach #F0B08C, near-transparent
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.moveTo(ox, oy);
  ctx.lineTo(ux, uy);
  ctx.lineTo(lx, ly);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = "rgba(240,176,140,0.9)";                  // dawn glow at the origin
  ctx.beginPath();
  ctx.arc(ox, oy, 6, 0, Math.PI * 2);
  ctx.fill();
}

function initBeam() {
  const readout = document.getElementById("forecast-readout");
  const { ctx, w, h } = setupCanvas(document.getElementById("beam"));
  if (REDUCED) { drawBeam(ctx, w, h, 1); return; } // HTML text is already the calm readout
  const state = { p: 0 };
  gsap.to(state, {
    p: 1,
    ease: "none",
    scrollTrigger: { trigger: "#act-future", start: "top top", end: "+=150%", pin: true, scrub: 0.5 },
    onUpdate: () => {
      drawBeam(ctx, w, h, state.p);
      const [r, g, b] = beamRgb(state.p);
      readout.style.color = `rgb(${r},${g},${b})`;
      readout.textContent = readoutText(state.p);
    },
  });
  readout.textContent = readoutText(0);
  drawBeam(ctx, w, h, 0);
}
initBeam();
```

**Verify**: `npm run build` → exit 0;
`grep -c "ETA 1h12m" main.js` → `1`;
`grep -c "resets in 3h42m" main.js` → `1`.

### Step 8: Dawn section and footer styles

Append to `style.css`:

```css
#dawn { background: linear-gradient(180deg, var(--zenith) 0%, var(--violet) 45%, var(--peach) 100%); padding: 6rem 1.25rem 4rem; }
.dawn-card { width: min(880px, 100%); margin: 0 auto; background: var(--moonlight); color: var(--zenith); border-radius: 16px; padding: clamp(1.5rem, 4vw, 3rem); display: grid; gap: 1.5rem; }
.dawn-card a { color: var(--zenith); }
.dawn-card h2 { font-size: clamp(1.625rem, 4vw, 2.5rem); }
.install-primary code { display: inline-block; background: var(--zenith); color: var(--moonlight); padding: 0.75rem 1.25rem; border-radius: 8px; font-size: 1.125rem; }
.install-alt { font-size: 0.9375rem; }
.cta-secondary { font-weight: 500; }
.cmd-grid { list-style: none; display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 0.75rem; }
.cmd-grid li { border: 1px solid var(--indigo); border-radius: 8px; padding: 0.75rem; display: grid; gap: 0.25rem; }
.cmd-grid span { font-size: 0.875rem; }
.pillars { list-style: none; display: grid; gap: 0.5rem; }
.pillars .star { color: var(--gold); margin-right: 0.5rem; } /* decorative glyph, aria-hidden */
.badges { font-size: 0.875rem; letter-spacing: 0.02em; }

footer { background: var(--zenith); color: var(--moonlight); text-align: center; padding: 2.5rem 1.25rem; display: grid; gap: 0.5rem; }
footer a { color: var(--gold); }
```

**Verify**: `npm run build` → exit 0; `grep -c '.dawn-card' style.css` → ≥ 1.

### Step 9: Accessibility and reduced-motion pass

Structural gates (run from `explore/02-night-observatory/`):

```bash
grep -c "<h1" index.html                      # → 1  (exactly one h1)
grep -c "<header" index.html                  # → 1
grep -c "<main" index.html                    # → 1
grep -c "<footer" index.html                  # → 1
grep -c 'role="img"' index.html               # → 2  (both canvases labeled)
grep -c "focus-visible" style.css             # → 1
grep -rl "prefers-reduced-motion" style.css main.js   # → both files listed
grep -c "REDUCED" main.js                     # → 5 (gate + three acts + counter)
grep -c "<noscript" index.html                # → 1
```

Contrast gate — every text color on the zenith background must be ≥ 4.5:1:

```bash
node -e '
const L=h=>{const v=[1,3,5].map(i=>parseInt(h.slice(i,i+2),16)/255).map(c=>c<=0.03928?c/12.92:((c+0.055)/1.055)**2.4);return .2126*v[0]+.7152*v[1]+.0722*v[2]};
const cr=(a,b)=>{const[hi,lo]=[L(a),L(b)].sort((x,y)=>y-x);return (hi+.05)/(lo+.05)};
const bg="#0B1026";
const t={moonlight:"#F2EFE4",gold:"#E8C36A",green:"#7DDB8A",lime:"#CDE060",orange:"#F0A05A",red:"#E86A5E",peach:"#F0B08C"};
let ok=true;for(const[n,h]of Object.entries(t)){const r=cr(h,bg);ok&&=r>=4.5;console.log(n,r.toFixed(2))}
console.log(ok?"ALL PASS":"FAIL");process.exit(ok?0:1)'
```

**Verify**: the script prints seven ratios (lowest is `red` ≈ 5.96), then
`ALL PASS`, exit 0. All greps above return their expected counts. Notes:
horizon violet `#6E6BD8` is never used as a text color (backgrounds only);
the gold ★ pillar glyphs on the moonlight card are decorative and
`aria-hidden`, exempt from the text floor; dawn-card text is zenith on
moonlight (≈ 17:1). Links are native `<a>` elements — keyboard focusable
with the `:focus-visible` outline by default.

### Step 10: Responsive pass (360 px)

Append to `style.css`:

```css
@media (max-width: 400px) {
  .act-inner { width: calc(100% - 1.5rem); }
  .cmd-grid { grid-template-columns: 1fr; }
  .gauge-number { font-size: 1.375rem; }
}
```

If browser tooling is available, load the dev server (`npm run dev`) at a
360 px viewport and scroll the full page: no horizontal scrollbar, and the
three pinned acts must not jump or overlap. **Escape hatch** (only if
pinned sections jump or overlap at small widths — a real ScrollTrigger
failure mode): disable pinning below 768 px by wrapping the three init
calls in `gsap.matchMedia()`:

```js
const mm = gsap.matchMedia();
mm.add("(min-width: 768px)", () => { initConstellation(); initGauge(); initBeam(); initBurnCounter(); });
mm.add("(max-width: 767.98px)", () => {
  // no pinning on small screens: render static end states
  const c = setupCanvas(document.getElementById("constellation"));
  drawConstellation(c.ctx, c.w, c.h, computeStars(c.w, c.h), 1);
  const b = setupCanvas(document.getElementById("beam"));
  drawBeam(b.ctx, b.w, b.h, 1);
});
```

(and remove the four unconditional `init*()` calls). Note the change in the
exploration README. Only STOP if the matchMedia fallback also fails. If no
browser tooling is available, keep the unconditional code, note the
unchecked item in the exploration README, and continue — that is not a
STOP.

**Verify**: `npm run build` → exit 0;
`grep -c "max-width: 400px" style.css` → `1`.

### Step 11: Build and serve smoke test

```bash
cd /home/kento/Repositories/token-oracle/explore/02-night-observatory
npm run build
npm run preview -- --port 4173 --strictPort >/dev/null 2>&1 &
PREVIEW_PID=$!
sleep 3
curl -s -o /dev/null -w "%{http_code}" http://localhost:4173/
kill "$PREVIEW_PID"
cat dist/assets/*.js | gzip | wc -c
grep -c "Know when you'll hit the limit." dist/index.html
```

**Verify**: `npm run build` exit 0 and `dist/index.html` exists; curl
prints `200`; the gzipped JS byte count is `< 250000` (expect roughly
70–90 KB — gsap core + ScrollTrigger ≈ 70 KB gz); the dist grep is ≥ 1.
(This page is vanilla JS — the tagline lives in `index.html` and passes
through to `dist/index.html` unescaped. The source-of-truth grep is
`explore/02-night-observatory/index.html`; if this were JSX, dist output
could escape the apostrophe and only the source grep would count.)

### Step 12: Write the exploration README

Create `explore/02-night-observatory/README.md` with exactly this content
(if you applied the step-10 escape hatch or skipped the browser check, add
one line saying so under "Design rationale"):

````markdown
# 02 — Night Observatory

GSAP ScrollTrigger scrollytelling prototype for the Token Oracle marketing
site. One scroll = one night of observation, dusk to dawn, in three pinned
acts that mirror the product's three tenses (past / present / future).

## Run

```bash
npm i
npm run dev        # dev server
npm run build      # static dist/
npm run preview    # serve dist/ on :4173
```

## Brand stance

**Remix.** Keeps the banner's night motifs — crescent, stars, gold sparkle,
violet — but trades watercolor-mascot softness for a cinematic observatory
night. Aesthetic risk taken: a single uninterrupted narrative — no nav, no
section links until the dawn section; the page commits to being read like
a film.

## Design rationale

- Palette: zenith `#0B1026`, indigo `#1B2447`, horizon violet `#6E6BD8`,
  star gold `#E8C36A`, moonlight `#F2EFE4`, dawn peach `#F0B08C`, plus a
  brightened night semaphore green `#7DDB8A` / lime `#CDE060` / orange
  `#F0A05A` / red `#E86A5E`.
- Type: Fraunces (display, optical size large, weight 560), Instrument
  Sans (body, 400/500), IBM Plex Mono (data); system fallbacks Georgia /
  system-ui / ui-monospace.
- Signature element: the constellation ledger — 168 stars, one per hour of
  a sample week (7 jittered rows × 24 columns); brightness and size
  proportional to that hour's mock usage; a faint gold line traces Mon→Sun
  as you scrub.
- Motion: one GSAP timeline per act, pinned sections, `scrub: 0.5`, canvas
  drawing driven by timeline progress. `prefers-reduced-motion: reduce`
  disables pinning and scrubbing entirely; the acts render as static
  sections with end-state visuals and a static burn-counter line.

## Screenshot

screenshot.png — to be added when browser tooling is available; it was not
available at build time, so this note stands in.
````

If you CAN take a screenshot: save it as `screenshot.png` (1280 px wide) in
this folder and replace the Screenshot section body with
`![Night Observatory landing page](./screenshot.png)`.

**Verify**: `grep -c "Remix." explore/02-night-observatory/README.md` → `1`;
`grep -c "constellation ledger" explore/02-night-observatory/README.md` → `1`.

### Step 13: Flip the gallery row, update the plan index, final scope check

1. In `explore/README.md`, change ONLY the exploration-02 row's Status cell
   from `planned` to `built`:

   ```
   | 02 | Night Observatory | remix | Vite + GSAP ScrollTrigger | `npm i && npm run dev` | plans/026 | built |
   ```

2. In `plans/README.md`: if a `| 026 |` row exists in the execution-order
   table, set its Status cell to `DONE`; if it does not exist, append this
   row after the table's last plan row:

   ```
   | 026 | Exploration 02: Night Observatory — GSAP scrollytelling (`explore/02-night-observatory/`) | P2 | L | 024 | DONE |
   ```

3. Final scope check and commit.

**Verify**:
`grep -c 'Night Observatory.*built' explore/README.md` → `1`;
`grep -Fc '| 026 |' plans/README.md` → `1`;
`git status --porcelain -- explore/ plans/README.md` lists ONLY paths under
`explore/02-night-observatory/`, plus `explore/README.md` and
`plans/README.md` (no `node_modules/` or `dist/` — the template
`.gitignore` covers them; `git check-ignore explore/02-night-observatory/node_modules`
echoes the path). The repo carries PRE-EXISTING untracked entries you did
not create — notably the sibling plan files under `plans/` (the whole
`plans/` directory may be untracked, shown as `?? plans/`, or individual
`?? plans/0NN-*.md` lines) and possibly `.claude/`. Those are ignorable and
must NOT be added, committed, or deleted; an unscoped `git status
--porcelain` will always show them.

## Test plan

No unit tests — this is a design prototype; the product's test suite is
untouched and irrelevant here. The gates are:

- Build gate after every code step: `npm run build` → exit 0 (Vite fails
  the build on JS syntax errors and bad imports).
- Data-rule gate (step 5): the node one-liner prints `168 104 93 101`.
- Contrast gate (step 9): the node script prints `ALL PASS`, exit 0.
- Structure gates (step 9): landmark/h1/role/focus-visible/reduced-motion
  greps at their expected counts.
- Smoke gate (step 11): `curl` → `200`; gzipped JS < 250,000 bytes.
- Spot-checks if a browser is available: keyboard-Tab shows the gold
  focus outline on every link; with reduced motion forced (DevTools →
  Rendering → emulate `prefers-reduced-motion`), the page scrolls as
  plain stacked sections with all visuals in end state and no pinning.

## Done criteria

Machine-checkable. ALL must hold (run from the repo root):

- [ ] `test -f explore/BRIEF.md` → exit 0
- [ ] `(cd explore/02-night-observatory && npm run build)` → exit 0 and `test -f explore/02-night-observatory/dist/index.html` → exit 0
- [ ] Preview smoke: `curl -s -o /dev/null -w "%{http_code}" http://localhost:4173/` → `200` while `npm run preview -- --port 4173 --strictPort` runs
- [ ] `grep -c "Know when you'll hit the limit." explore/02-night-observatory/index.html` → ≥ 1 (source of truth; also present in `dist/index.html`)
- [ ] `grep -rl "prefers-reduced-motion" explore/02-night-observatory/style.css explore/02-night-observatory/main.js` → prints both paths
- [ ] `grep -c "focus-visible" explore/02-night-observatory/style.css` → ≥ 1
- [ ] `grep -c 'lang="en"' explore/02-night-observatory/index.html` → `1`
- [ ] `cat explore/02-night-observatory/dist/assets/*.js | gzip | wc -c` → number < 250000
- [ ] `test -f explore/02-night-observatory/README.md` → exit 0
- [ ] `grep -c 'Night Observatory.*built' explore/README.md` → `1`
- [ ] `git status --porcelain -- explore/ plans/README.md` shows no paths outside `explore/02-night-observatory/`, `explore/README.md`, `plans/README.md` (pre-existing untracked entries elsewhere — e.g. sibling `plans/*.md` files or `.claude/` — are ignorable and out of scope)
- [ ] `grep -Fc '| 026 |' plans/README.md` → `1` (status row present and updated)

## STOP conditions

Stop and report back (do not improvise) if:

- `explore/BRIEF.md` does not exist — plan 024 has not run; it must run
  first. Do not create the brief yourself.
- `explore/02-night-observatory/` already exists with files in it, or the
  gallery's `| 02 | Night Observatory` row is missing or not `planned` —
  another session may own this exploration.
- The npm registry is unreachable (`npm create` / `npm install` fails with
  `ENOTFOUND`, `ETIMEDOUT`, or a proxy error) — the page cannot be built
  offline; report instead of vendoring gsap by hand.
- `npm create vite` emits a file layout that does not match step 2's
  expected list (`index.html`, `main.js`, `style.css`, `package.json` at
  the folder root) — every later step's file references would be wrong.
- Pinned sections jump or overlap at 360 px AND the step-10
  `gsap.matchMedia()` escape hatch (no pinning below 768 px) also fails.
  (The escape hatch itself is not a STOP; apply it and note it.)
- The drift check finds changes to `explore/02-night-observatory/` or the
  02 gallery row beyond what plan 024 creates.
- A step's verification fails twice after a reasonable fix attempt.
- Any fix would require touching an out-of-scope file (root `README.md`,
  `explore/BRIEF.md`, another exploration's folder, anything Python).

## Maintenance notes

- Canvas backing stores are sized once at init; a live window resize does
  not re-lay-out the stars or beam (prototype trade-off). If this
  direction graduates to the marketing-site repo, add a debounced resize
  handler that re-runs `setupCanvas` + redraw and calls
  `ScrollTrigger.refresh()`.
- gsap is pinned through `package-lock.json` within `^3.12.0`; ScrollTrigger
  ships inside the gsap package — no second dependency.
- The page embeds copy from `explore/BRIEF.md`. If the brief's canonical
  copy, scenarios, or thresholds change, this page must be re-synced —
  copies drift.
- Reviewer should scrutinize: the two readout strings and the burn-counter
  caption (honesty guardrails), the reduced-motion path (zero
  ScrollTrigger instances, end-state visuals), and semaphore text contrast
  on `#0B1026`.
- Deferred deliberately: `screenshot.png` when browser tooling is absent;
  live-resize handling; self-hosted fonts (Google Fonts `<link>` is
  brief-sanctioned for prototypes only).
