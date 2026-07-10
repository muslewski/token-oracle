# Plan 027: Exploration 03: Instrument Panel — React + Motion interactive product page

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ada32e9..HEAD -- explore/ plans/README.md`
> Expected drift: `explore/README.md` and `explore/BRIEF.md` created by plan
> 024, plus rows added to `plans/README.md`. STOP if `explore/03-instrument-panel/`
> already contains files, or if the gallery row for exploration 03 in
> `explore/README.md` is not in status `planned` (see "Current state").

## Status

- **Priority**: P2
- **Effort**: L
- **Risk**: MED
- **Depends on**: plans/024-explore-scaffold-brief.md
- **Category**: direction
- **Planned at**: commit `ada32e9`, 2026-07-02

## Why this matters

token-oracle will get a marketing site in a separate repository. Before
committing to one visual direction, the operator is building several complete,
opinionated landing-page prototypes under `explore/` so they can be compared
side by side. This plan builds exploration 03, "Instrument Panel" — the
**adopt-stance official-site candidate**: it keeps the brand's light lavender
identity and translates it into a precision cockpit instrument for token fuel.
It is deliberately a **light theme** (a counterweight to the two dark
explorations, 02 and 04) and it carries the round's largest interactive
surface: the hero is a working SVG gauge demo, not a screenshot. If this
direction wins, it gets re-implemented properly in the marketing-site repo;
either way this folder stays as the design record.

## Current state

- `explore/BRIEF.md` and `explore/README.md` exist (created by plan 024). You
  do **not** need to open `BRIEF.md` — every fact, copy string, and rule you
  need is inlined in this plan. If you notice a conflict between this plan and
  `BRIEF.md`, that is a STOP condition, not something to reconcile yourself.
- The gallery table in `explore/README.md` contains exactly this row for this
  exploration (created by plan 024, status `planned`):

  ```
  | 03 | Instrument Panel | adopt | Vite + React + Motion | `npm i && npm run dev` | plans/027 | planned |
  ```

- `explore/03-instrument-panel/` does not exist yet. You will create it.
- The repo root is a Python CLI project. This plan touches **no Python** and no
  root-level tooling. There is no `package.json` at the repo root; all Node
  work happens inside `explore/03-instrument-panel/`.
- Repo commit style is conventional commits (from `git log --oneline`:
  `fix(dash): ...`, `chore(core): ...`, `test: ...`).
- The existing brand identity (which this exploration ADOPTS) is the repo
  banner `assets/oracle-banner.webp`: lavender watercolor sky, masked oracle in
  white-and-lavender robes, hourglass in a magic circle, crescent moon,
  navy→violet gradient wordmark, gold sparkle accents, four pillar cards
  (CLARITY / FORESIGHT / CONFIDENCE / INTENTION), and a badge strip
  (Provider-agnostic · Zero dependencies · CLI first · Extensible).

### Rules inlined from the shared brief (hard constraints)

- **Honesty guardrails**: no testimonials, no user counts, no "trusted by"
  logos, no star counts, no invented benchmarks, no named competitors. Every
  claim must trace to the product facts in this plan. Sample numbers must come
  only from the two honest scenarios below, plus arithmetic derived from them
  via the demo formula, and the three demo plan-preset cap constants
  (19,000 / 88,000 / 220,000 tokens per 5h window). Those preset constants are
  NOT in explore/BRIEF.md — they come from this plan's settled design
  direction (widely-published community approximations of the pro/max5/max20
  plan windows, recorded in `plans/research-competitive-landscape.md`); the
  page must present them as demo presets, never as verified vendor limits.
- **Honest sample data**:
  - Calm scenario: window `5h`, used 45,200 / cap 220,000, projected 21 % at
    window end, resets in 3 h 42 m → green.
  - Drama scenario: window `5h`, used 178,400 / cap 220,000, projected 108 %,
    ETA to cap 1 h 12 m, resets in 2 h 48 m → orange.
  - Statusline mock: `[5h] 45.2k/220k · 21% · resets 3h42m`
- **Color semaphore** (projected % of cap at window end): green < 85 % · lime
  85–100 % · orange 100–120 % · red ≥ 120 %.
- **Accessibility floor**: semantic landmarks (`header`/`main`/`footer`, one
  `h1`); visible `:focus-visible` styles; body-text contrast ≥ 4.5:1; every
  animation gated behind `prefers-reduced-motion: reduce` (page fully readable
  with it on); interactive demos keyboard-operable; images have alt text;
  `lang="en"`; usable at 360 px width.
- **Performance floor**: `font-display: swap` on webfonts; no scroll-handler
  layout thrash (transforms/opacity only); JS bundle < 250 KB gzipped.
- **Tech rules**: Google Fonts via `<link>` is allowed, always with a system
  fallback stack. No other runtime CDNs — all JS dependencies pinned via npm.
  No analytics, no trackers, no external network calls at runtime beyond
  fonts. Node ≥ 18.
- **Voice**: plain verbs, specific over clever, calm confidence, sentence case
  everywhere. The oracle metaphor is seasoning, never fog.

## Design specification

### Brand stance

**ADOPT** — this is the official-site candidate: it keeps the brand's light
lavender identity and translates it into a precision cockpit instrument for
token fuel, on a deliberate light theme that counterweights the two dark
explorations. **The one named aesthetic risk this design takes**: the hero is
a working instrument instead of a screenshot or a big number — the demo IS the
headline image.

### Design tokens — core palette

| Token | Hex | What it is for |
|---|---|---|
| `--porcelain` | `#F6F5F9` | page background |
| `--panel` | `#FFFFFF` | cards, instrument face |
| `--graphite` | `#23222A` | ALL text (body, headings, numerals, statusline) |
| `--violet` | `#6D5AE6` | primary accent: CTA button, links, active-tab underline |
| `--periwinkle` | `#A9A4F0` | soft accents, `:focus-visible` ring |
| `--hairline` | `#E3E1EC` | rules, card borders, dial ticks, gauge background track |

### Design tokens — semaphore (gauge + statusline ONLY)

| Token | Hex | Band |
|---|---|---|
| `--sem-green` | `#1E9E4A` | projected < 85 % |
| `--sem-lime` | `#A3B316` | 85–100 % |
| `--sem-orange` | `#E07B26` | 100–120 % |
| `--sem-red` | `#D64541` | ≥ 120 % |

**Contrast rule (checked, non-negotiable)**: none of the four semaphore colors
passes 4.5:1 as text on white (`#A3B316` ≈ 2.3:1, `#E07B26` ≈ 3.0:1,
`#1E9E4A` ≈ 3.5:1, `#D64541` ≈ 4.4:1). Therefore semaphore colors are used
**only as strokes/fills** (gauge arc, needle, threshold ticks, a small status
dot, the statusline strip's left border) and **never as text color**. All text
stays `--graphite` (≈ 14.5:1 on porcelain). `--violet` on white is ≈ 4.9:1 and
may be used for link/button text.

### Type

| Role | Google Fonts family | Weights | Fallback stack |
|---|---|---|---|
| Display (h1, h2, wordmark) | Schibsted Grotesk | 500, 700 | `system-ui, sans-serif` |
| Body | Schibsted Grotesk | 400 | `system-ui, sans-serif` |
| Data (statusline, numerals, commands, code) | Geist Mono | 400, 500 | `ui-monospace, monospace` |

Loaded via one Google Fonts `<link>` with `&display=swap` (font-display swap).
**Tabular numbers on all animated numerals** (`font-variant-numeric:
tabular-nums`) so spring animation does not cause layout jitter.

### Wireframe (top to bottom)

```
┌────────────────────────────────────────────────────────────────────┐
│ NAV — slim, sticky. left: "Token Oracle" wordmark; right: GitHub   │  porcelain bg,
├────────────────────────────────────────────────────────────────────┤  hairline bottom rule
│ HERO — 2 columns ≥ 900 px, stacked below                           │
│ ┌ LEFT ───────────────────────┐ ┌ RIGHT: THE INSTRUMENT ─────────┐ │
│ │ overline (facts chips)      │ │ white panel card, hairline edge│ │
│ │ h1: Know when you'll hit    │ │  ┌ 240° SVG arc gauge ┐        │ │
│ │     the limit.              │ │  │ track + value arc  │        │ │
│ │ positioning line            │ │  │ + needle + ticks   │        │ │
│ │ $ pipx install token-oracle │ │  └────────────────────┘        │ │
│ │   [Copy]  (aria-live)       │ │  big % numeral + used/cap      │ │
│ │ [View on GitHub]            │ │  statusline strip (mono)       │ │
│ └─────────────────────────────┘ │  (pro|max5|max20) radiogroup   │ │
│                                 │  burn-rate slider + readout    │ │
│                                 │  demo note                     │ │
│                                 └────────────────────────────────┘ │
├─ HOW IT WORKS ─────────────────────────────────────────────────────┤
│  h2 · 3 numbered cards: Read / Measure / Forecast                  │
│  (staggered whileInView reveal, once)                              │
├─ PAST / PRESENT / FUTURE ──────────────────────────────────────────┤
│  h2 + intro line                                                   │
│  [Past][Present][Future]  ← radio tab strip, layoutId underline    │
│  ┌ one mock panel: report table / dash screen / forecast line ┐    │
├─ PILLARS ──────────────────────────────────────────────────────────┤
│  4 cards: Clarity · Foresight · Confidence · Intention             │
├─ COMMANDS ─────────────────────────────────────────────────────────┤
│  h2 · mono grid (3×2 desktop, 1-col mobile): forecast, dash,       │
│  statusline, tmux, snapshot, doctor                                │
├─ ADAPTERS / PROOF ─────────────────────────────────────────────────┤
│  h2 + one paragraph + badge chips (Provider-agnostic · Zero        │
│  dependencies · CLI first · Extensible)                            │
├─ FOOTER ───────────────────────────────────────────────────────────┤
│  MIT licensed. Built by Mateusz Muślewski. · PyPI · GitHub ·       │
│  agentic-sage                                                      │
└────────────────────────────────────────────────────────────────────┘
```

### Signature element — the instrument (build exactly this)

A working SVG arc gauge showing projected % of cap, with a needle,
threshold-colored arc, live numerals, a statusline strip, and two controls.

**Fixed mock constants** (from the calm scenario — the executor implements
arithmetic, not modeling):

- `USED_NOW = 45200` (tokens already used this window)
- `HOURS_REMAINING = 3.7` (= 3 h 42 m until the window resets)
- Plan presets (tokens per 5 h window): `pro = 19000`, `max5 = 88000`,
  `max20 = 220000`. Default preset: `max20`.
- Burn-rate slider: `<input type="range">`, min 0, max 60000, step 100,
  default **300** tokens/hour.

**The formula** (state it in a code comment, verbatim):

```
projected_pct = (used_now + rate × hours_remaining) / cap × 100
```

At the defaults (rate 300, cap 220,000): (45,200 + 300 × 3.7) / 220,000 × 100
= 21.05 → rounds to **21 %**, so the default statusline renders exactly the
brief's mock: `[5h] 45.2k/220k · 21% · resets 3h42m`.

**Geometry** — 240° arc from −210° to +30°, SVG `viewBox="0 0 200 150"`,
center (100, 100), radius 80. Angle convention: 0° points right (+x), positive
angles turn clockwise in screen coordinates. Point at angle θ:
`(100 + r·cos(θ·π/180), 100 + r·sin(θ·π/180))`. Endpoints: θ = −210° →
(30.72, 140); θ = +30° → (169.28, 140). Both arcs use this exact path:

```
ARC_D = "M 30.72 140 A 80 80 0 1 1 169.28 140"
```

- **Background track**: `<path d={ARC_D}>`, stroke `--hairline`, stroke-width
  10, fill none, stroke-linecap round.
- **Value arc**: `<motion.path d={ARC_D}>`, same stroke geometry, stroke =
  current semaphore color (via `--sem-current`, see below), revealed with
  `style={{ pathLength: arcFrac }}` where `arcFrac = min(pct, 150) / 150`.
  The gauge face reads 0–150 % of cap (`GAUGE_MAX = 150`).
- **Needle**: `<motion.line x1="100" y1="100" x2="162" y2="100">` (drawn
  pointing right = 0°), rotated by
  `angle = −210 + (min(pct, 150) / 150) × 240` degrees. Use a Motion value
  bound to `style={{ rotate: angle }}` plus CSS
  `transform-box: view-box; transform-origin: 100px 100px;` on the needle so
  the rotation pivots on the gauge center. Stroke `--sem-current`, width 3,
  linecap round. Add a small center hub circle (r 5, fill `--graphite`).
- **Threshold ticks** at 85, 100, 120 (the semaphore boundaries): for each t,
  tick angle = −210 + (t / 150) × 240 (i.e. −74°, −50°, −18°); draw a line
  from radius 86 to radius 96 at that angle, stroke-width 2, colored with the
  semaphore color of the band above the threshold (85 → lime, 100 → orange,
  120 → red).
- The `<svg>` is `aria-hidden="true"` — meaning is carried by the real-text
  readouts below it, not the drawing.

**Readouts** (real DOM text below the gauge, all `tabular-nums`):

- Big numeral: `{pct}%` (rounded, spring-animated, UNclamped — if a preset
  makes pct exceed 150, the needle/arc clamp at the gauge end but the numeral
  shows the true rounded value), with a small dot swatch in `--sem-current`
  beside it. Numeral text color stays `--graphite`.
- Label: `projected at window end`
- Sub-readout: `used 45,200 / {cap} tokens · resets in 3h 42m` where cap is
  the selected preset formatted with commas (19,000 / 88,000 / 220,000).
- Statusline strip (Geist Mono, graphite text, `--panel` background, 3 px left
  border in `--sem-current`): `[5h] 45.2k/{capk} · {pct}% · resets 3h42m`
  where capk ∈ {19k, 88k, 220k} and pct is the same spring-animated rounded
  value.

**Controls** (below the statusline strip):

- Plan-preset segmented control: a real `<fieldset>` radiogroup —
  `<legend>Plan preset — tokens per 5h window</legend>` and three
  `<input type="radio" name="preset">` with labels `pro · 19k`,
  `max5 · 88k`, `max20 · 220k`, styled as segments. `max20` checked by
  default. Checked segment: violet border + violet text on white.
- Burn-rate slider: `<input type="range" id="burn-rate" min="0" max="60000"
  step="100">` with a **visible** `<label for="burn-rate">Burn rate</label>`,
  a live mono readout `{rate} tokens/hour`, and
  `aria-valuetext="{rate} tokens per hour — projected {pct} percent of cap"`
  (e.g. "52,000 tokens per hour — projected 108 percent of cap").

**States / behavior**:

- Moving either control recomputes `pct` via the formula and spring-animates:
  the needle rotation, the value-arc `pathLength`, the big numeral, and the
  statusline's pct (all driven by the same spring source).
- Crossing a semaphore threshold (85 / 100 / 120, either direction): the arc,
  needle, dot, and statusline border **snap** to the new color with a 150 ms
  ease (CSS `transition: stroke 150ms ease` / `border-color 150ms ease` /
  `background-color 150ms ease` on the affected elements), and the gauge
  housing does **one** subtle horizontal shake: keyframes
  `x: [0, -4, 4, -2, 2, 0]` over 300 ms (4 px amplitude), fired once per band
  change via `animate()` from `motion/react`.
- **Reduced motion**: springs become instant (via `MotionConfig
  reducedMotion="user"`, see motion spec); the shake is **skipped entirely**
  (guard it with `useReducedMotion()`); the 150 ms color snap may remain (it
  is a color change, not movement); the instrument remains fully functional —
  values simply jump.

### Motion spec

- Library: npm package **`motion`** (the framer-motion successor), pinned
  `motion@^12.0.0`. Imports come from **`motion/react`**:
  `import { motion, AnimatePresence, MotionConfig, useSpring, useTransform,
  useReducedMotion, animate } from "motion/react"`.
- **Global**: the whole app is wrapped in `<MotionConfig reducedMotion="user">`
  — this makes the library honor the OS `prefers-reduced-motion` setting, so
  springs and transform animations become instant. State this in a code
  comment.
- **Gauge springs**: `useSpring` with `{ stiffness: 120, damping: 20 }`;
  derive needle angle / arc fraction / rounded numeral from it with
  `useTransform`. Trigger: any control change.
- **Threshold snap + shake**: trigger — semaphore band change; 150 ms ease
  color snap; one 300 ms 4 px shake via `animate()`; shake skipped when
  `useReducedMotion()` is true.
- **How-it-works cards**: staggered reveal on scroll — each card
  `initial={{ opacity: 0, y: 16 }}`, `whileInView={{ opacity: 1, y: 0 }}`,
  `viewport={{ once: true }}`, duration ≈ 0.5 s ease-out, stagger 0.12 s
  between cards (via per-card `transition={{ delay: i * 0.12 }}`).
- **Tabs**: the active-tab underline is a single `<motion.span
  layoutId="tab-underline">` rendered inside the checked tab's label — Motion
  animates its layout between tabs. Panel swap: `<AnimatePresence
  mode="wait">` with fade + 8 px rise, 0.2 s.
- **CSS safety net**: `src/index.css` carries a `prefers-reduced-motion:
  reduce` media query that zeroes all CSS animation/transition durations
  (exact block in Step 6). Between `MotionConfig reducedMotion="user"`, the
  `useReducedMotion()` shake guard, and this block, every animation on the
  page is gated.

## Copy (final, verbatim)

The executor writes ZERO copy. Every visible string on the page is below, in
display order. Type all apostrophes as straight apostrophes (U+0027, `'`).
Sentence case throughout.

### Document head

- `<title>`: `Token Oracle — Know when you'll hit the limit.`
- Meta description: `Token Oracle is an offline CLI that forecasts when you'll
  hit your AI-provider token cap. It reads local usage logs — no API calls,
  nothing leaves your machine.`

### Nav (sticky)

- Wordmark (left): `Token Oracle`
- Link (right): `GitHub` → `https://github.com/muslewski/token-oracle`

### Hero — left column

- Overline chips: `Offline CLI` · `Zero dependencies` · `MIT`
- h1 (the ONLY h1 on the page, exact string): `Know when you'll hit the limit.`
- Positioning line: `Usage monitors tell you what you spent. Token Oracle
  tells you what happens next.`
- Install block label: `Install`
- Install command (mono): `pipx install token-oracle`
- Copy button visible label: `Copy` (aria-label: `Copy install command`)
- Copy success message (aria-live region): `Copied to clipboard.`
- Copy failure message (aria-live region): `Copy failed — select the text
  manually.`
- Alternatives line (small, mono): `also: pip install token-oracle · uvx
  token-oracle`
- Secondary CTA link: `View on GitHub` →
  `https://github.com/muslewski/token-oracle`

### Hero — right column (the instrument)

- Panel overline: `Projected at window end`
- Big numeral: `{pct}%` (dynamic; 21% at defaults)
- Numeral label: `projected at window end`
- Sub-readout: `used 45,200 / {cap} tokens · resets in 3h 42m`
- Statusline strip (dynamic template): `[5h] 45.2k/{capk} · {pct}% · resets
  3h42m` — renders `[5h] 45.2k/220k · 21% · resets 3h42m` at defaults.
- Radiogroup legend: `Plan preset — tokens per 5h window`
- Radio labels: `pro · 19k` / `max5 · 88k` / `max20 · 220k`
- Slider label: `Burn rate`
- Slider readout: `{rate} tokens/hour`
- Demo note (small): `Interactive demo with sample numbers. It's a forecast,
  not a bill.`

### How it works

- h2: `How it works`
- Card 1: heading `Read` — body: `token-oracle reads your provider's local
  usage logs. Claude Code is built in; adapters add more. No API calls —
  nothing leaves your machine.`
- Card 2: heading `Measure` — body: `It computes your observed burn rate over
  a sliding window, weighted by your own weekly usage profile.`
- Card 3: heading `Forecast` — body: `It projects usage to window end and
  tells you what's left before the cap: a percentage, an ETA, and a color.`

### Past / Present / Future (tabs)

- h2: `Past. Present. Future.`
- Intro line: `Every usage tool reports what you spent. Token Oracle treats
  that as the opening act — the forecast is the headline.`
- Tab labels: `Past` / `Present` / `Future`
- Past panel — panel heading: `What you spent` — mono mock table:

  ```
  window   used      cap       projected
  5h       45,200    220,000   21%
  5h       178,400   220,000   108%
  ```

  Caption: `The rear-view mirror. Useful, but it can't warn you.`
- Present panel — panel heading: `Where you are now` — mono mock dash screen:

  ```
  TOKEN ORACLE · dash
  window  5h                      resets 2h48m
  used    178,400 / 220,000
  [████████████████░░░░]  81% used · projected 108%
  ```

  Caption: `The live dashboard — token-oracle dash.`
- Future panel — panel heading: `What happens next` — mono mock forecast line:

  ```
  [5h] 178.4k/220k · projected 108% · ETA 1h12m · resets 2h48m
  ```

  Caption: `A percentage, an ETA, and a color — before it happens.`

### Pillars

- h2: `What you get`
- Card 1: `Clarity` — `Understand your true token usage.`
- Card 2: `Foresight` — `Plan ahead with accuracy.`
- Card 3: `Confidence` — `Avoid surprises, stay in control.`
- Card 4: `Intention` — `Spend tokens with purpose.`

### Commands

- h2: `Six commands`
- `token-oracle forecast` — `Live forecast — time left before your cap.
  Supports --json.`
- `token-oracle dash` — `Full-screen terminal dashboard.`
- `token-oracle statusline` — `One-line ANSI fragment for any status bar.`
- `token-oracle tmux` — `status-right fragment for tmux.`
- `token-oracle snapshot` — `Writes forecast.json for other tools.`
- `token-oracle doctor` — `Checks configuration and data sources.`

### Adapters / proof

- h2: `Built to be piped`
- Paragraph: `Provider-agnostic by design: Claude Code support is built in,
  and adapters add more sources. The statusline and tmux fragments drop into
  any status bar; snapshot writes forecast.json for everything else.`
- Badge chips (four): `Provider-agnostic` · `Zero dependencies` · `CLI first`
  · `Extensible`

### Footer

- Line: `MIT licensed. Built by Mateusz Muślewski.`
- Links: `PyPI` → `https://pypi.org/project/token-oracle/` · `GitHub` →
  `https://github.com/muslewski/token-oracle` · `agentic-sage` →
  `https://github.com/muslewski/agentic-sage`

## Commands you will need

All npm commands run **inside** `explore/03-instrument-panel/`.

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Node version | `node --version` | v18 or higher |
| Registry reachable | `npm ping` | exit 0 |
| Scaffold | `npm create vite@latest . -- --template react` | exit 0; creates `index.html`, `src/App.jsx`, `src/main.jsx` |
| Install deps | `npm install` | exit 0 |
| Add motion | `npm i motion@^12.0.0` | exit 0 |
| Dev server (manual checks) | `npm run dev` | serves on http://localhost:5173 |
| Build | `npm run build` | exit 0; `dist/index.html` exists |
| Preview | `npm run preview -- --port 4173 --strictPort` | serves on http://127.0.0.1:4173 |
| Smoke | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4173/` | `200` |
| Scope check | `git status --porcelain -- explore/ plans/README.md` (repo root) | only in-scope paths (the repo may carry pre-existing untracked entries elsewhere, e.g. under `plans/` or `.claude/` — ignore them, never add them) |

Environment note: on the operator's machine a shell hook may proxy `grep`
through another tool (`rtk`), which can alter output format for some flag
combinations. If a verify command's output shape differs from the expected
result for no apparent reason, re-run it as `rtk proxy grep ...` (raw,
unfiltered) or `command grep ...` before concluding the gate failed.

## Suggested executor toolkit

If a frontend-design or similar design-guidance skill exists in your
environment, do **not** invoke it: the design above is final and fully
specified, and per-exploration consistency is what makes the operator's
side-by-side comparison meaningful.

## Scope

**In scope** (the only paths you may create/modify):
- `explore/03-instrument-panel/` — the whole folder (create). Do not commit
  `node_modules/` or `dist/` — the Vite scaffold's own `.gitignore` already
  excludes them; leave it in place.
- `explore/README.md` — flip exploration 03's gallery row from `planned` to
  `built` (that one row only).
- `plans/README.md` — this plan's status row only.

**Out of scope** (do NOT touch, even though they look related):
- `token_oracle/`, `tests/`, `assets/` — the Python product; this plan is
  design-only.
- Root `README.md` — the explorations are internal; do not advertise them.
- `explore/BRIEF.md` — operator-approved wording; conflicts are a report, not
  an edit.
- Every other `explore/` folder (`01-*`, `02-*`, `04-*`, `05-*`) and every
  other gallery row — they belong to plans 025/026/028/029.

## Git workflow

- Branch: `advisor/027-explore-instrument-panel-motion` (from `main`).
- Conventional commits, one per logical unit. Suggested sequence:
  - `feat(explore): scaffold instrument panel exploration`
  - `feat(explore): add instrument gauge with presets and burn slider`
  - `feat(explore): add landing sections and copy`
  - `docs(explore): add instrument panel readme and flip gallery row`
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Prerequisite checks

From the repo root:

1. `test -f explore/BRIEF.md` — if this fails, **STOP: run plan 024 first**.
2. `test ! -e explore/03-instrument-panel` — if the folder exists, STOP
   (another session may own this exploration).
3. `grep -c '| plans/027 | planned |' explore/README.md` must print `1` — if
   not, STOP (gallery row missing or already flipped).
4. `node --version` must print v18 or higher; `npm ping` must exit 0 — if the
   registry is unreachable, STOP.

**Verify**: `test -f explore/BRIEF.md && test ! -e explore/03-instrument-panel && test "$(grep -c '| plans/027 | planned |' explore/README.md)" = 1 && node --version && npm ping && echo PREREQS-OK` → last line `PREREQS-OK` (the `test ... = 1` form is deliberate: a duplicated gallery row must fail this gate)

### Step 2: Create the branch

`git checkout -b advisor/027-explore-instrument-panel-motion`

**Verify**: `git branch --show-current` → `advisor/027-explore-instrument-panel-motion`

### Step 3: Scaffold Vite + React and install motion

```bash
mkdir -p explore/03-instrument-panel
cd explore/03-instrument-panel
npm create vite@latest . -- --template react
```

Expected scaffold layout (STOP if missing): `index.html`, `src/App.jsx`,
`src/main.jsx`, `src/index.css`, `package.json`, `vite.config.js`. If the
scaffolder prompts interactively, choose whatever options produce the plain
React JavaScript template; if the result still lacks `src/App.jsx` /
`src/main.jsx` / `index.html`, STOP and report the actual layout.

Then, still inside the folder:

```bash
npm install
npm i motion@^12.0.0
```

Delete the template art the design does not use:
`rm -f src/assets/react.svg public/vite.svg src/App.css` (also remove the
`import './App.css'` line from `src/App.jsx` — the whole file is rewritten in
Step 7 anyway).

**Verify**: `test -f index.html && test -f src/App.jsx && test -f src/main.jsx && npm ls motion` → exits 0 and prints `motion@12.x`

### Step 4: Probe the motion/react import surface

From inside `explore/03-instrument-panel/`:

```bash
node -e "import('motion/react').then(m=>{const need=['motion','AnimatePresence','MotionConfig','useSpring','useTransform','useReducedMotion','animate'];const miss=need.filter(n=>!(n in m));if(miss.length){console.error('MISSING: '+miss.join(', '));process.exit(1)}console.log('motion/react OK')}).catch(e=>{console.error(e.message);process.exit(1)})"
```

If this prints `MISSING: ...` or errors, **STOP** (see STOP conditions —
report `npm ls motion` output and the import style shown in
`node_modules/motion/README.md`; do not guess alternative import paths).

**Verify**: the command above → prints `motion/react OK`, exit 0

### Step 5: Set up `index.html` (lang, title, meta, fonts, favicon)

Edit `explore/03-instrument-panel/index.html`:

- `<html lang="en">`
- `<title>Token Oracle — Know when you'll hit the limit.</title>`
- `<meta name="description" content="...">` with the meta description from the
  Copy section, verbatim.
- Replace the vite.svg favicon link with an inline hourglass favicon:
  `<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⏳</text></svg>">`
- Google Fonts (the only permitted external requests):

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist+Mono:wght@400;500&family=Schibsted+Grotesk:wght@400;500;700&display=swap" rel="stylesheet">
```

**Verify**: `grep -c 'display=swap' index.html && grep -c 'lang="en"' index.html` → `1` then `1`

### Step 6: Design tokens and base styles in `src/index.css`

Replace the template `src/index.css` entirely. It must contain this token
block verbatim:

```css
:root {
  --porcelain: #F6F5F9;
  --panel: #FFFFFF;
  --graphite: #23222A;
  --violet: #6D5AE6;
  --periwinkle: #A9A4F0;
  --hairline: #E3E1EC;
  --sem-green: #1E9E4A;
  --sem-lime: #A3B316;
  --sem-orange: #E07B26;
  --sem-red: #D64541;
  --font-display: "Schibsted Grotesk", system-ui, sans-serif;
  --font-body: "Schibsted Grotesk", system-ui, sans-serif;
  --font-mono: "Geist Mono", ui-monospace, monospace;
}
```

And these three blocks verbatim:

```css
:focus-visible {
  outline: 3px solid var(--periwinkle);
  outline-offset: 2px;
}

.num { font-variant-numeric: tabular-nums; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

Plus base styles per the design spec: `body { background: var(--porcelain);
color: var(--graphite); font-family: var(--font-body); margin: 0; }`;
headings in `--font-display` weight 700; a `.vh` visually-hidden utility
class; a content container `max-width: 1080px; margin-inline: auto;
padding-inline: 24px` (16 px below 480 px); `.panel { background: var(--panel);
border: 1px solid var(--hairline); border-radius: 12px; }`; mono elements use
`var(--font-mono)`. Semaphore colors appear in CSS only as stroke/fill/border
values, never as `color` on text. Mobile-first: base styles are the stacked
layout; widen with `@media (min-width: 900px)`.

**Verify**: `grep -c -- '--porcelain' src/index.css && grep -c 'prefers-reduced-motion' src/index.css && grep -c 'focus-visible' src/index.css && grep -c 'tabular-nums' src/index.css` → each line ≥ `1`

### Step 7: App shell — landmarks, MotionConfig, nav, footer

Rewrite `src/App.jsx` as the page skeleton (leave `src/main.jsx` as scaffolded):

```jsx
import { motion, AnimatePresence, MotionConfig } from "motion/react";

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <header>{/* sticky nav */}</header>
      <main>
        {/* hero, how-it-works, tabs, pillars, commands, adapters */}
      </main>
      <footer>{/* footer */}</footer>
    </MotionConfig>
  );
}
```

- Nav: sticky (`position: sticky; top: 0`), porcelain background with
  `backdrop-filter: blur(8px)`, hairline bottom border; wordmark `Token
  Oracle` (display font, 700) on the left, `GitHub` link on the right (copy
  and URL from the Copy section).
- Footer: the footer line and three links from the Copy section, hairline top
  border.
- Exactly one `<header>`, one `<main>`, one `<footer>` at the top level.

**Verify**: `grep -c '<MotionConfig reducedMotion="user">' src/App.jsx && npm run build` → `1`, then build exits 0

### Step 8: Hero left column — tagline, positioning, install, clipboard

Build the hero section in `src/App.jsx` (left column of a 2-column grid that
stacks below 900 px):

- Overline chips, `<h1>Know when you'll hit the limit.</h1>` (straight
  apostrophe, U+0027 — do NOT write `&apos;` or a curly quote), positioning
  line, install block, alternatives line, and the `View on GitHub` link — all
  strings verbatim from the Copy section.
- Copy button: on click, `navigator.clipboard.writeText("pipx install
  token-oracle")`; on resolve, set the message state to `Copied to
  clipboard.`; on reject, `Copy failed — select the text manually.`; clear it
  after 2 s. The message renders inside a `<span aria-live="polite">` that is
  always present in the DOM (empty when idle). Button has visible text `Copy`
  and `aria-label="Copy install command"`.

**Verify**: `grep -cF "Know when you'll hit the limit." src/App.jsx && grep -c 'aria-live' src/App.jsx && npm run build` → `1`, ≥ `1`, build exits 0

### Step 9: Instrument — gauge geometry, state, formula (static first)

Create `src/Instrument.jsx`. Start with the constants, formula, and static SVG
(no animation yet); render it as the hero's right column inside a `.panel`
card. Load-bearing code shape:

```jsx
// src/Instrument.jsx — the signature element
import { useEffect, useRef, useState } from "react";
import {
  motion, useSpring, useTransform, useReducedMotion, animate,
} from "motion/react";

// ---- fixed mock constants (calm scenario from the shared brief) ----
const USED_NOW = 45200;        // tokens already used this window
const HOURS_REMAINING = 3.7;   // 3h42m until the window resets
const CAPS = { pro: 19000, max5: 88000, max20: 220000 }; // tokens / 5h window
const CAP_LABEL = { pro: "19k", max5: "88k", max20: "220k" };
const CAP_TEXT = { pro: "19,000", max5: "88,000", max20: "220,000" };

// ---- gauge geometry: 240° arc, -210°..+30°, center (100,100), r=80 ----
const ARC_D = "M 30.72 140 A 80 80 0 1 1 169.28 140";
const GAUGE_MAX = 150; // the face reads 0–150 % of cap

// The ONLY formula in this demo — arithmetic, not modeling:
// projected_pct = (used_now + rate × hours_remaining) / cap × 100
function projectedPct(rate, cap) {
  return ((USED_NOW + rate * HOURS_REMAINING) / cap) * 100;
}

// Semaphore: green <85, lime 85–100, orange 100–120, red ≥120
function semaphore(pct) {
  if (pct < 85) return "var(--sem-green)";
  if (pct < 100) return "var(--sem-lime)";
  if (pct < 120) return "var(--sem-orange)";
  return "var(--sem-red)";
}

function polar(r, deg) {
  const a = (deg * Math.PI) / 180;
  return [100 + r * Math.cos(a), 100 + r * Math.sin(a)];
}
const TICKS = [85, 100, 120]; // angle_t = -210 + (t / 150) * 240
```

State: `const [preset, setPreset] = useState("max20")` and
`const [rate, setRate] = useState(300)`. Derived:
`const pct = projectedPct(rate, CAPS[preset])` and
`const clamped = Math.min(pct, GAUGE_MAX)`.

SVG (inside the panel, `aria-hidden="true"`, `viewBox="0 0 200 150"`, width
100 %, max-width 420 px): background track path (stroke `var(--hairline)`,
width 10, linecap round), value arc, needle line from (100,100) to (162,100),
hub circle, and the three threshold ticks (each from `polar(86, angle)` to
`polar(96, angle)`, stroke `semaphore(t)`, width 2). Set the current color
once on the instrument root: `style={{ "--sem-current": semaphore(pct) }}`;
arc/needle/dot/statusline-border all reference `var(--sem-current)`, with
`transition: stroke 150ms ease` (and `border-color`/`background-color` 150 ms
where relevant) in CSS. Below the SVG: the readouts and statusline strip with
the exact strings/templates from the Copy section (class `num` on every
dynamic numeral).

Import and render `<Instrument />` in the hero right column of `App.jsx`.

**Verify**: `grep -c 'M 30.72 140 A 80 80 0 1 1 169.28 140' src/Instrument.jsx && grep -c 'projected_pct = (used_now + rate × hours_remaining) / cap × 100' src/Instrument.jsx && npm run build` → `1`, `1`, build exits 0

### Step 10: Instrument — controls, springs, shake, statusline wiring

Still in `src/Instrument.jsx`:

1. **Controls**: the radiogroup fieldset and range slider exactly as specified
   in "Signature element" (real inputs, visible label, legend, defaults
   `max20` / 300, `aria-valuetext` template). Radios call
   `setPreset`, the slider calls `setRate(Number(e.target.value))` on
   `onChange`.
2. **Springs**: two spring motion values, both `{ stiffness: 120, damping: 20 }`:
   - `const springClamped = useSpring(clamped, { stiffness: 120, damping: 20 })`
     driving geometry: `const angle = useTransform(springClamped, p => -210 +
     (Math.min(p, GAUGE_MAX) / GAUGE_MAX) * 240)` bound to the needle
     `style={{ rotate: angle }}` (needle CSS: `transform-box: view-box;
     transform-origin: 100px 100px;`), and `const arcFrac =
     useTransform(springClamped, p => Math.min(p, GAUGE_MAX) / GAUGE_MAX)`
     bound to the value arc `style={{ pathLength: arcFrac }}`.
   - `const springPct = useSpring(pct, { stiffness: 120, damping: 20 })`
     driving numerals: `const shown = useTransform(springPct, v =>
     Math.round(v))`, rendered as `<motion.span className="num">{shown}
     </motion.span>` in both the big numeral and the statusline strip.
   - Retarget on change: `useEffect(() => { springClamped.set(clamped);
     springPct.set(pct); }, [clamped, pct])`.
3. **Threshold shake**: `const reduced = useReducedMotion()`; a
   `useRef`-stored previous band; in an effect, when `semaphore(pct)` differs
   from the previous value and `!reduced`, run
   `animate(housingRef.current, { x: [0, -4, 4, -2, 2, 0] }, { duration: 0.3 })`
   where `housingRef` is on a `<motion.div className="instrument-housing">`
   wrapping the SVG; then store the new band. One shake per crossing, never a
   loop, skipped under reduced motion.

Manual check: `npm run dev`, open http://localhost:5173 — defaults show 21 %
green and the statusline `[5h] 45.2k/220k · 21% · resets 3h42m`; dragging the
slider to 52,000 on max20 shows ~108 % orange (with a shake when crossing 85
and 100); preset `pro` pegs the needle at the gauge end while the numeral
keeps counting. Then stop the dev server.

**Verify**: `grep -c 'useSpring' src/Instrument.jsx && grep -c 'aria-valuetext' src/Instrument.jsx && grep -c 'type="range"' src/Instrument.jsx && grep -c 'useReducedMotion' src/Instrument.jsx && npm run build` → ≥ `1` each, build exits 0

### Step 11: How-it-works section with staggered reveal

In `src/App.jsx`, add the `How it works` section: h2 plus three numbered cards
(`.panel` styling), headings and bodies verbatim from the Copy section. Each
card is a `motion.div` with `initial={{ opacity: 0, y: 16 }}`,
`whileInView={{ opacity: 1, y: 0 }}`, `viewport={{ once: true }}`,
`transition={{ duration: 0.5, ease: "easeOut", delay: i * 0.12 }}`.

**Verify**: `grep -c 'whileInView' src/App.jsx && grep -cF 'nothing leaves your machine.' src/App.jsx && npm run build` → ≥ `1`, `1`, build exits 0

### Step 12: Past / Present / Future tabs

Create `src/Surfaces.jsx` and render it after how-it-works. Implementation
choice (fixed — do not substitute the ARIA tab pattern): **radio inputs styled
as tabs**, which gives arrow-key switching natively:

- `<fieldset>` with `<legend className="vh">Product surface</legend>` and
  three `<input type="radio" name="surface">` (ids `surface-past`,
  `surface-present`, `surface-future`; `Past` checked by default) with
  `<label>` elements styled as the tab strip. Do NOT add `role="tab"` /
  `role="tabpanel"` — these are radios semantically; mixing in tab roles would
  break them.
- Active-tab underline: inside the checked radio's label only, render
  `<motion.span layoutId="tab-underline" className="tab-underline" />`
  (2 px bar, `background: var(--violet)`) — Motion's layout animation slides
  it between labels.
- Panels: `<AnimatePresence mode="wait">` around one
  `<motion.div key={active} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1,
  y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}>`
  containing the active panel: heading, mono mock block (in a `<pre>` with
  `overflow-x: auto`), and caption — all three panels' content verbatim from
  the Copy section.
- Section h2 and intro line verbatim from the Copy section.

**Verify**: `grep -c 'layoutId="tab-underline"' src/Surfaces.jsx && grep -c 'AnimatePresence' src/Surfaces.jsx && grep -c '178,400' src/Surfaces.jsx && npm run build` → `1`, ≥ `1`, ≥ `1`, build exits 0

### Step 13: Pillars, commands grid, adapters strip

In `src/App.jsx`, add the last three content sections, copy verbatim from the
Copy section:

- **Pillars**: h2 `What you get`; four `.panel` cards in a grid (4-across
  ≥ 900 px, 2×2 at medium, 1-col at 360 px).
- **Commands**: h2 `Six commands`; six entries in a mono grid (3×2 desktop,
  1-col mobile): command in Geist Mono 500, description in body type.
- **Adapters/proof**: h2 `Built to be piped`; the paragraph; four badge chips
  (hairline border, panel background, body text — not semaphore colors).

**Verify**: `grep -c 'Foresight' src/App.jsx && grep -c 'token-oracle doctor' src/App.jsx && grep -c 'Provider-agnostic' src/App.jsx && grep -cF 'Mateusz Muślewski' src/App.jsx && npm run build` → ≥ `1` each, build exits 0

### Step 14: Accessibility and reduced-motion pass

Audit and fix against the floor. Machine gates:

1. Exactly one h1: `grep -rc '<h1' src/ | grep -v ':0'` → only `src/App.jsx:1`.
2. Landmarks: `grep -c '<header' src/App.jsx && grep -c '<main' src/App.jsx && grep -c '<footer' src/App.jsx` → `1` each.
3. `grep -c 'lang="en"' index.html` → `1`.
4. `grep -c 'focus-visible' src/index.css` → ≥ `1`.
5. `grep -c 'prefers-reduced-motion' src/index.css` → ≥ `1`.
6. `grep -c 'reducedMotion="user"' src/App.jsx` → `1`.
7. `grep -c 'useReducedMotion' src/Instrument.jsx` → ≥ `1`.
8. No `<img>` at all: `! grep -rn '<img' src/ index.html && echo NO-IMG` →
   `NO-IMG` (this page uses no raster images; the leading `!` is required
   because grep exits 1 on zero matches, which would otherwise read as a
   failure in an `&&` chain). If you deliberately added an `<img>`, every
   match must carry an `alt` attribute instead.

Manual checks with `npm run dev` (fix anything that fails, then stop the
server):

- Keyboard-only walk: Tab reaches nav link, Copy button, GitHub link, the
  three preset radios (arrow keys switch), the slider (arrow keys change
  value and the gauge follows), the surface tabs (arrow keys switch), footer
  links. Focus ring visible on each.
- DevTools → Rendering → emulate `prefers-reduced-motion: reduce`: values
  jump instantly, no shake fires, reveal-on-scroll content is readable, tabs
  still switch.
- Text contrast: all text is graphite on porcelain/white or violet on white —
  no semaphore-colored text anywhere (`grep -n 'color: var(--sem' src/*.css
  src/index.css` → no matches).

**Verify**: run gates 1–8 above → all pass, and `npm run build` exits 0

### Step 15: Responsive pass

Mobile-first CSS was written in Steps 6–13; confirm and fix at 360 px using
dev-tools device emulation (`npm run dev`):

- No horizontal page scroll at 360 px (mock `<pre>` blocks scroll inside
  their own `overflow-x: auto` container instead).
- Hero stacks: copy column above the instrument; the gauge SVG scales to
  container width (max-width 420 px).
- Preset segments and slider remain tappable (≥ 44 px hit targets).
- Grids collapse: pillars and commands to one column.

**Verify**: `grep -c 'min-width: 900px' src/index.css && grep -c 'overflow-x: auto' src/index.css && npm run build` → ≥ `1`, ≥ `1`, build exits 0

### Step 16: Build, bundle budget, preview smoke test

From inside `explore/03-instrument-panel/`:

```bash
npm run build
test -f dist/index.html
cat dist/assets/*.js | gzip -c | wc -c          # must print < 250000
npm run preview -- --port 4173 --strictPort >/tmp/preview-027.log 2>&1 &
PREVIEW_PID=$!
for i in $(seq 1 15); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4173/) && [ "$CODE" = "200" ] && break
  sleep 1
done
echo "$CODE"
kill $PREVIEW_PID
```

(The retry loop replaces a fixed sleep: preview startup time varies, and a
single early curl would report a spurious failure.)

**Verify**: build exits 0; gzip byte count < 250000; curl prints `200`

### Step 17: Write the exploration README (and screenshot, if possible)

Create `explore/03-instrument-panel/README.md` containing, in this order:

1. Title: `# 03 — Instrument Panel`
2. Run commands: `npm i && npm run dev` (dev), `npm run build && npm run
   preview` (static build).
3. Brand stance: adopt — one short paragraph: keeps the light lavender brand
   identity and translates it into a precision cockpit instrument for token
   fuel; light theme as the counterweight to the two dark explorations; the
   named risk: the hero is a working instrument, not a screenshot — the demo
   is the headline image.
4. Design rationale: signature element (240° SVG arc gauge + presets + burn
   slider, spring physics, threshold snap + single shake), motion via the
   `motion` package with `MotionConfig reducedMotion="user"`.
5. Palette summary: porcelain `#F6F5F9`, panel `#FFFFFF`, graphite `#23222A`,
   violet `#6D5AE6`, periwinkle `#A9A4F0`, hairline `#E3E1EC`, semaphore
   `#1E9E4A`/`#A3B316`/`#E07B26`/`#D64541` (fills/strokes only, never text).
6. Type summary: Schibsted Grotesk 400/500/700 (display + body), Geist Mono
   400/500 (data), system fallbacks, tabular numerals on animated numbers.
7. Screenshot: if browser/screenshot tooling is available in your
   environment, capture the hero at 1280 px wide as `screenshot.png` in this
   folder and embed it. If not available, write the line
   `Screenshot pending — browser tooling unavailable in the build session.`
   and continue. **This is NOT a STOP condition.**

**Verify**: `test -f explore/03-instrument-panel/README.md && grep -ci 'adopt' explore/03-instrument-panel/README.md` → exit 0, ≥ `1`

### Step 18: Flip the gallery row, update the plans index, final scope check

1. From the repo root, flip exploration 03's status (this exact substitution
   touches only the one row):

   ```bash
   sed -i 's#| plans/027 | planned |#| plans/027 | built |#' explore/README.md
   ```

2. In `plans/README.md`: if a `| 027 |` row exists in the execution-order
   table, set its Status cell to `DONE`; if it does not exist, append this row
   after the highest-numbered row:

   ```markdown
   | 027 | Exploration 03: Instrument Panel (React + Motion) | P2 | L | 024 | DONE |
   ```

3. Scope check: `git status --porcelain` must list only paths under
   `explore/03-instrument-panel/`, plus `explore/README.md` and
   `plans/README.md`. (`node_modules/` and `dist/` must NOT appear — the
   scaffold's `.gitignore` covers them.)
4. Commit remaining work with the conventional-commit messages from the Git
   workflow section.

**Verify**: `grep -c '| plans/027 | built |' explore/README.md && grep -c '| 027 |' plans/README.md && git status --porcelain` → `1`, `1`, and an empty status after the final commit

## Test plan

No automated unit tests — this is a throwaway design prototype whose value is
visual comparison; the repo's Python test tooling does not apply to it.
Verification is:

- The per-step machine gates (grep/build/curl commands above).
- The Step 14 accessibility gates (1–8) plus the manual keyboard /
  reduced-motion / contrast walkthrough.
- The Step 15 manual 360 px responsive check.
- The Step 16 build + gzip budget + preview `200` smoke test.

## Done criteria

Machine-checkable, run from the repo root. ALL must hold:

- [ ] `test -f explore/03-instrument-panel/package.json` → exit 0
- [ ] `(cd explore/03-instrument-panel && npm run build)` → exit 0
- [ ] Preview smoke: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4173/` → `200` (with `npm run preview -- --port 4173 --strictPort` running; kill it after)
- [ ] `grep -rlF "Know when you'll hit the limit." explore/03-instrument-panel/src/` → prints at least one file (expected: `src/App.jsx`). Grep `src/`, NOT `dist/` — the JSX toolchain may escape the apostrophe in the minified bundle; the source file is the target.
- [ ] `grep -c 'prefers-reduced-motion' explore/03-instrument-panel/src/index.css` → ≥ `1`
- [ ] `grep -c 'reducedMotion="user"' explore/03-instrument-panel/src/App.jsx` → `1`
- [ ] `grep -c 'focus-visible' explore/03-instrument-panel/src/index.css` → ≥ `1`
- [ ] `cat explore/03-instrument-panel/dist/assets/*.js | gzip -c | wc -c` → number < `250000`
- [ ] `grep -c '| plans/027 | built |' explore/README.md` → `1`
- [ ] `git status --porcelain` → nothing outside `explore/03-instrument-panel/`, `explore/README.md`, `plans/README.md` (empty after final commit)
- [ ] `plans/README.md` has a `| 027 |` row with status `DONE`

## STOP conditions

Stop and report back (do not improvise) if:

- `explore/BRIEF.md` does not exist — plan 024 has not run; report "run plan
  024 first".
- `explore/03-instrument-panel/` already exists, or the gallery row for 03 in
  `explore/README.md` is not `planned` — another session may own this
  exploration; do not overwrite.
- `npm ping` fails, or `npm install` / `npm i motion@^12.0.0` cannot reach the
  npm registry.
- The scaffold emits a different file layout than `index.html` +
  `src/App.jsx` + `src/main.jsx` (create-vite drift), or offers no plain
  React JavaScript template — report the actual layout/prompt.
- The Step 4 probe fails: `motion/react` does not resolve or does not export
  `motion`, `AnimatePresence`, `MotionConfig`, `useSpring`, `useTransform`,
  `useReducedMotion`, `animate` (API drift). Report the installed version
  from `npm ls motion` and the import style shown in
  `node_modules/motion/README.md` — do NOT guess alternative import paths.
- Any canonical copy string in this plan conflicts with `explore/BRIEF.md`
  (e.g. the tagline differs) — the brief is operator-approved; report the
  conflict, do not harmonize either file yourself.
- `npm run build` fails twice on the same step after a reasonable fix
  attempt.
- Completing a step appears to require touching an out-of-scope file.

## Maintenance notes

- This exploration is a design prototype, never deployed. If its direction
  wins the comparison, it is re-implemented cleanly in the separate
  marketing-site repository; this folder stays as the design record. If it is
  abandoned, flip its gallery row to `archived` — do not delete the folder.
- The copy here is a copy of the shared brief, which is itself a copy of the
  product README — if the install command, subcommand list, or semaphore
  thresholds change in the product, `explore/BRIEF.md` gets re-synced first
  and this page after it.
- What a reviewer should scrutinize: honesty guardrails (the only numbers on
  the page are the two brief scenarios, the three demo preset caps, and
  arithmetic derived via the stated formula); semaphore colors used strictly
  as fills/strokes, never text (contrast); the reduced-motion behavior
  (instant springs, no shake, page fully readable); keyboard operability of
  the radios/slider/tabs.
- Deferred out of this plan: `screenshot.png` when browser tooling is
  unavailable (note it in the exploration README); any dark-mode variant
  (this exploration argues the light theme deliberately); real forecast data
  wiring (the demo intentionally uses fixed mock constants).
