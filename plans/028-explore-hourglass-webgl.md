# Plan 028: Exploration 04: Particle Hourglass — Three.js generative hero

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ada32e9..HEAD -- explore/04-particle-hourglass/ explore/README.md explore/BRIEF.md`
> Expected: `explore/README.md` and `explore/BRIEF.md` appear as created by
> plan 024 (that is normal — 024 runs after the planned-at SHA). Other
> explorations flipping THEIR gallery rows is also normal. What must be true:
> the diff shows NOTHING under `explore/04-particle-hourglass/`, and the
> `| 04 | Particle Hourglass` row in `explore/README.md` still ends in
> `| planned |`. On any mismatch, treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: L
- **Risk**: MED
- **Depends on**: plans/024-explore-scaffold-brief.md
- **Category**: direction
- **Planned at**: commit `ada32e9`, 2026-07-02

## Why this matters

The operator is comparing five complete landing-page prototypes for the future
Token Oracle marketing site (a separate repo, later). This plan builds
exploration 04 of 5: the maximal generative direction — the repo banner's
hourglass-in-a-magic-circle rebuilt as a single luminous WebGL object that IS
the page. It exists so the comparison round contains one honest answer to the
question "what does the boldest version look like, built with discipline?"
(static fallback, reduced-motion path, DPR cap, pause when hidden). Without
this exploration the round only compares safe directions.

## Current state

- This repo is a **Python CLI project** (`token_oracle/`, `tests/`). This plan
  touches **no Python**; pytest/ruff/mypy are irrelevant to it.
- Plan 024 (a prerequisite) created:
  - `explore/BRIEF.md` — the shared design brief. Everything you need from it
    is inlined below; you never need to open it.
  - `explore/README.md` — the gallery. It contains this row (verbatim), which
    Step 12 flips from `planned` to `built`:

    ```
    | 04 | Particle Hourglass | remix | Vite + Three.js | `npm i && npm run dev` | plans/028 | planned |
    ```

- `explore/04-particle-hourglass/` does not exist yet; this plan creates it.
- Repo commit style is conventional commits (see `git log --oneline`:
  `fix(dash): ...`, `chore(core): ...`, `test: ...`).
- The working tree contains a **pre-existing untracked `plans/` directory**
  (and possibly `.claude/`). Never expect `git status --porcelain` to be
  empty; scope checks below are phrased accordingly.
- Node ≥ 18 is assumed available (a brief rule for built explorations).

### Rules inlined from `explore/BRIEF.md` (you do not need to open it)

**Product facts (do not embellish)**: token-oracle is an offline CLI that
forecasts when you will hit your AI-provider token cap. It reads the
provider's **local usage logs** (Claude Code built in; adapters add more),
computes an observed burn rate over a sliding window, and projects
time-to-cap. **No API calls. Nothing leaves your machine.** Python, zero
runtime dependencies, MIT licensed, on PyPI. Six subcommands: `forecast`
(live forecast, `--json`), `dash` (full-screen terminal dashboard),
`statusline` (one-line ANSI fragment for any status bar), `tmux`
(status-right fragment), `snapshot` (writes `forecast.json` for other
tools), `doctor` (checks configuration and data sources). Color semaphore on
projected usage at window end (as % of cap): green < 85% · lime 85–100% ·
orange 100–120% · red ≥ 120%.

**Honest sample data (the ONLY numbers allowed on the page)**:
- Calm scenario: window `5h`, used 45,200 / cap 220,000, projected 21% at
  window end, resets in 3h42m → green.
- Drama scenario: window `5h`, used 178,400 / cap 220,000, projected 108%,
  ETA to cap 1h12m, resets in 2h48m → orange.
- Statusline mock (representative, not claimed as exact CLI output):
  `[5h] 45.2k/220k · 21% · resets 3h42m`

**Honesty guardrails (hard rules)**: no testimonials, no user counts, no
"trusted by" logos, no star counts, no invented benchmarks, no named
competitors. Every claim must trace to the facts above. Sample numbers must
come from the two scenarios above.

**Accessibility floor**: semantic landmarks (`header/main/footer`, one
`h1`); visible `:focus-visible` styles; body-text contrast ≥ 4.5:1; every
animation gated behind `prefers-reduced-motion: reduce` (page fully readable
with it on); interactive demos keyboard-operable; images have alt text;
`lang="en"`; usable at 360px width.

**Performance floor**: `font-display: swap` on webfonts; canvas/WebGL capped
at devicePixelRatio 2; no scroll-handler layout thrash (use
transforms/opacity); built pages keep the JS bundle < 250 KB gzipped —
**the Three.js exploration is exempt from the size budget, but must
lazy-init and offer a static fallback** (both are mandatory in this plan).

**Tech rules**: Google Fonts via `<link>` is allowed (prototypes), always
with a system fallback stack. No other runtime CDNs — all JS dependencies
come pinned via npm. No analytics, no trackers, no external network calls at
runtime beyond fonts. Node ≥ 18.

**Voice**: plain verbs, specific over clever, calm confidence. The oracle
metaphor is seasoning, never fog. Sentence case everywhere.

## Design specification

### (a) Brand stance

**Remix.** This design takes the banner's hourglass-in-a-magic-circle and
rebuilds it as the entire experience: one generative object in a dark room —
the motif survives, the watercolor execution does not. The ONE named
aesthetic risk this design takes: **a WebGL object as the entire hero of a
marketing page** — defensible only with the discipline this plan mandates
(static fallback, reduced-motion behavior, DPR cap, pause when
offscreen/hidden).

### (b) Design tokens

| Token           | Value                       | What it is for |
|-----------------|-----------------------------|----------------|
| `--obsidian`    | `#0A0A0D`                   | Page background, footer background, install-block fill, WebGL clear color |
| `--fog`         | `#17161C`                   | Glass-card fill, applied at ~85% opacity → `rgba(23, 22, 28, 0.85)` |
| `--lavender`    | `#B8B0F5`                   | Particle gradient light end; headings, links, mono accents, focus outline |
| `--deep-violet` | `#7C6FE8`                   | Particle gradient dark end; decorative gradient use only — never body text |
| `--ivory`       | `#EDEAE0`                   | Body text |
| `--ember`       | `#D96C2C`                   | Ignition state 1 — canvas particles + the orange swatch chip only; never text |
| `--alarm`       | `#CC3D33`                   | Ignition state 2 — canvas particles + the red swatch chip only; never text (3.9:1 on obsidian — below the text floor) |
| `--hairline`    | `rgba(184, 176, 245, 0.18)` | Glass-card borders, footer top border |

Note on the semaphore card's green/lime swatch chips: the palette above has
no green/lime. The chips use `#4caf6e` (green) and `#c9d34b` (lime) — these
are **display constants chosen by this plan** so the decorative chips are
visible on the card fill; they are `aria-hidden` and carry no claim. The
semaphore *thresholds* come from the brief. Orange/red chips reuse
`--ember`/`--alarm`.

### (c) Type

| Role    | Google Fonts family | Weights  | Fallback stack            | Use |
|---------|---------------------|----------|---------------------------|-----|
| Display | Marcellus           | 400 only | `Georgia, serif`          | Inscriptional roman capitals — temple-oracle register. Single weight, used large and letterspaced; headings + wordmark only. |
| Body    | Source Sans 3       | 400, 600 | `system-ui, sans-serif`   | All body copy. |
| Data    | Overpass Mono       | 400      | `ui-monospace, monospace` | Counter HUD, code, statusline mock, badges, closing line, scroll hint. |

`font-display: swap` is delivered via `&display=swap` in this exact
stylesheet URL (used verbatim in Step 3):

```
https://fonts.googleapis.com/css2?family=Marcellus&family=Overpass+Mono&family=Source+Sans+3:wght@400;600&display=swap
```

### (d) Page wireframe (top to bottom)

```
┌──────────────────────────────────────────────────────────────┐
│ header (z=1): TOKEN ORACLE wordmark      [mono counter HUD]  │ counter: fixed top-right
│                                                              │
│                  .  · PARTICLE HOURGLASS ·  .                │ full-bleed FIXED canvas,
│               ~15,000 additive points; top bulb              │ z=0, behind everything,
│               = remaining, bottom = spent; slow              │ persists across all beats
│               idle spin; grains stream the neck              │
│                                                              │
│   Know when you'll hit the limit.                (h1)        │ hero: 100vh, text bottom-
│   Scroll to run the window forward ↓        (scroll hint)    │ left; static SVG fallback
├──────────────────────────────────────────────────────────────┤ sits here when WebGL off
│  ┌── glass card 1 ───────────────┐                           │
│  │ WHAT HAPPENS NEXT             │  canvas behind: grains    │ beat 1: 90vh, card left-
│  │ positioning + secondary line  │  fall as t rises          │ aligned, fog @85% fill
│  └───────────────────────────────┘                           │
├── beat 2: HOW IT WORKS — Read / Measure / Forecast ──────────┤
├── beat 3: THE SEMAPHORE — 4 chips; ignition happens here:    │ t≈0.63 ember, t≈0.72
│           the falling stream turns ember, then alarm         │ alarm (drama scenario)
├── beat 4: SIX COMMANDS + statusline mock ────────────────────┤
├── beat 5: FOUR PILLARS + proof badges ───────────────────────┤ t≈0.82: settle-back begins
├── beat 6: INSTALL — pipx…, View on GitHub,                   │ counter returns to calm;
│           closing line: resets in 3h42m ─────────────────────┤ grains flow back up
├──────────────────────────────────────────────────────────────┤
│ footer (static, opaque obsidian, z=1, normal flow):          │
│ MIT licensed. Built by Mateusz Muślewski. PyPI GitHub agen…  │
└──────────────────────────────────────────────────────────────┘
```

### (e) Signature element: the particle hourglass

One `THREE.Points` object, ~15,000 grains, **no custom shaders**. Step 6
contains the complete reference implementation; this section is the spec it
implements.

**Material** (exactly):
`new THREE.PointsMaterial({ vertexColors: true, size: 0.02, sizeAttenuation: true, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true })`
— `size` is in world units.

**Geometry** — two stacked cone volumes sharing a neck at the origin, axis
`z ∈ [-1, 1]` (top bulb `z > 0`, bottom bulb `z < 0`):

- Silhouette radius: `radius(z) = 0.08 + (0.55 - 0.08) * pow(abs(z), 1.6)`
- Sampling a point at height z: rejection-sample `x, y` uniformly in the
  square `[-radius(z), radius(z)]²` until `x² + y² ≤ radius(z)²` (a disc).
- The geometry's z-axis is rotated to the screen-vertical at scene setup
  (`points.rotation.x = -Math.PI / 2` inside a `THREE.Group` rig; the rig's
  `rotation.y` carries the idle spin).

**Per-grain data** (all precomputed once):
- `start` — a sampled point in the top bulb (`z ∈ [0.02, 1]`). Starts are
  sorted ascending by z so lower grains fall first.
- `neck` — the fixed point `(0, 0, 0)`.
- `pile` — a sampled point in the bottom bulb (`z ∈ [-1, -0.02]`), sorted
  ascending by z so the first faller lands deepest.
- `delay d_i = z_start_i * D_MAX` — proportional to start height.
- Base color: per-vertex lerp from `--deep-violet` (low grains) to
  `--lavender` (high grains) by `z_start_i`.

**Progress mapping.** Scroll position maps to global progress `t ∈ [0, 1]`
(`t = clamp(scrollY / (scrollHeight - innerHeight), 0, 1)`). A fill fraction
`g(t)` drives the grains: `ramp = t ≤ 0.82 ? t/0.82 : 1 - (t-0.82)/0.18`,
then `g = 0.2 + 0.8 * ramp`. So the hourglass rests at ~20% fallen (the calm
scenario), runs to fully fallen at the drama peak, and flows back to calm by
the CTA. Each grain's local progress is
`local_i = clamp((g - d_i) / (1 - D_MAX), 0, 1)`; its position is a
piecewise lerp: `local < 0.5` → lerp(start → neck, local·2), else
lerp(neck → pile, local·2 − 1).

**Named constants** (every number attributed — none claim to be product data):

| Constant      | Value       | Derivation |
|---------------|-------------|------------|
| `GRAIN_COUNT` | 15000       | Per the design direction; the Step 7 performance gate may reduce it to 8000. |
| `BEATS.ignite`| 0.63        | Derived so the fill fraction matches the drama scenario when ignition starts: g(0.63) = 0.2 + 0.8·(0.63/0.82) ≈ 0.815 ≈ 178,400/220,000 (0.811). |
| `BEATS.alarm` | 0.72        | Display constant — gives ember ~9% of the scroll before deepening to alarm. |
| `BEATS.settle`| 0.82        | Display constant — leaves the last 18% of scroll for the return to calm at the CTA. |
| `REST_FILL`   | 0.2         | ≈ calm scenario used/cap = 45,200/220,000 = 0.205, rounded for the demo. |
| `D_MAX`       | 0.7         | Display constant — max grain delay; every grain falls over a 0.3-wide window of g. |
| `EASE`        | 0.08        | Per the design direction — per-frame lerp factor of current t toward target t. |
| `ROT_SPEED`   | 0.05 rad/s  | Per the design direction — idle rotation. |

**Scroll discipline**: ONE scroll listener writes a target t (it reads only
`window.scrollY` — `scrollHeight` is measured at init and on resize, never
in the scroll handler). A `requestAnimationFrame` loop lerps current t
toward target (`current += (target - current) * EASE`) and rewrites the
position/color buffers (`attribute.needsUpdate = true`). No layout reads in
the scroll handler.

**Ignition** (the drama beat): for `t ∈ [0.63, 0.72)` the vertex colors of
**in-flight grains only** (`0 < local < 1`) lerp from base toward `--ember`
with strength ramping 0→1; for `t ∈ [0.72, 0.82)` the target is `--alarm`
at full strength; for `t ≥ 0.82` the strength eases back to 0 by `t = 1`
(colors settle back to the lavender→violet base). Waiting and landed grains
never ignite.

**States**:
1. *Loading/fallback* — before JS init, and permanently when WebGL is
   unavailable or reduced motion is set: canvas empty/hidden, static SVG
   hourglass visible in the hero, counter HUD hidden. The page is complete
   in this state.
2. *Running* — renderer active: SVG fallback hidden, counter HUD visible,
   idle rotation + scroll-driven grains.
3. *Paused* — canvas offscreen (IntersectionObserver) or tab hidden
   (`visibilitychange`): the rAF loop is cancelled; resuming restarts it.
4. *Ignited / settling* — color states driven purely by t (see above).

**Performance discipline**: `renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))`
(DPR cap 2, a brief floor); lazy init — the renderer (and the whole `three`
module, via dynamic `import()`) is constructed only after first paint, via
`requestIdleCallback` with a `setTimeout` fallback.

**Reduced-motion behavior**: if `prefers-reduced-motion: reduce` matches at
load, the renderer is **never constructed** — no rotation, no fall, no
ignition, no counter ticking. CSS additionally hides the canvas and counter.
The static SVG fallback and full copy render in normal document flow.

**Static SVG fallback** (exact markup in Step 3): an inline SVG,
`viewBox="0 0 200 280"`, two triangles sharing a pinched neck — top
`40,20 160,20 100,138`, bottom `100,142 40,260 160,260` — filled with a
vertical `linearGradient` from `#B8B0F5` to `#7C6FE8` at `fill-opacity`
0.28, hairline strokes, plus ten scattered grain dots (`<circle>` r 1.5–2.5):
four in the top bulb, three streaming through the neck, three piled in the
bottom bulb. `role="img"` with a descriptive `aria-label`.

### (f) Motion spec

| What animates | Trigger | Duration / easing intent | Reduced-motion behavior |
|---------------|---------|--------------------------|-------------------------|
| Grain fall + ignition colors (canvas) | Scroll scrubs target t; rAF loop chases it | Continuous; exponential chase, factor `EASE = 0.08`/frame (~200 ms settle feel) | Renderer never starts; canvas hidden; static SVG shown |
| Idle rotation of the hourglass rig | Always while running | Constant 0.05 rad/s, linear | Renderer never starts |
| Counter HUD text | Same rAF loop, derived from current t | Text swap per frame; no CSS transition | Counter hidden entirely |
| Glass cards fade/rise 12px | IntersectionObserver, first view only (threshold 0.2) | 300ms ease-out, opacity + translateY(12px)→0 | Cards fully visible immediately; no transition |
| Nothing else animates | — | — | — |

## Copy (final, verbatim)

ALL page copy, in display order. You write ZERO copy — paste from here (the
exact markup is in Step 3). Use straight apostrophes (`'`) exactly as
written — **never** `&#39;`, never curly quotes — several verification
greps depend on the literal characters.

**Document title** (browser tab):
> Token Oracle — Know when you'll hit the limit.

**Meta description**:
> Token Oracle is an offline CLI that forecasts when you will hit your AI-provider token cap. No API calls — nothing leaves your machine.

**Header wordmark**: `Token Oracle`

**Hero** (h1 + scroll hint):
> Know when you'll hit the limit.
>
> Scroll to run the window forward ↓

**SVG fallback aria-label**:
> An hourglass drawn in luminous grains. The top bulb holds the window allowance that remains; the bottom bulb holds what is spent.

**Counter HUD strings** (Overpass Mono; `aria-hidden` — the same numbers
appear in readable card copy):
- Calm resting line (t near 0 and t near 1):
  `45,200 / 220,000 tokens used · projected 21% · resets in 3h42m`
- Drama line (held for t ∈ [0.63, 0.82)):
  `178,400 / 220,000 tokens used · projected 108% · ETA to cap 1h12m`
- In between, the used count and percent interpolate linearly between those
  two anchors (e.g. `98,410 / 220,000 tokens used · projected 56%`). These
  transient values are **display interpolation between the two honest
  scenario anchors**, not claims; the resting states are exactly the
  scenario strings.

**Card 1 — heading `What happens next`**:
> Usage monitors tell you what you spent. Token Oracle tells you what happens next.
>
> It's a forecast, not a bill.
>
> token-oracle is an offline CLI that forecasts when you will hit your AI-provider token cap. It reads your provider's local usage logs — Claude Code built in, adapters add more — and projects time-to-cap. No API calls. Nothing leaves your machine.

**Card 2 — heading `How it works`** (ordered list, canonical three steps):
> 1. **Read** — token-oracle reads your provider's local usage logs. Claude Code is built in; adapters add more. No API calls — nothing leaves your machine.
> 2. **Measure** — it computes your observed burn rate over a sliding window, weighted by your own weekly usage profile.
> 3. **Forecast** — it projects usage to window end and tells you what's left before the cap: a percentage, an ETA, and a color.

**Card 3 — heading `The semaphore`**:
> Every forecast lands as a color: projected usage at window end, as a percent of your cap.
>
> - Green — under 85%
> - Lime — 85 to 100%
> - Orange — 100 to 120%
> - Red — 120% and up
>
> The ignition you just watched is the drama scenario: 178,400 / 220,000 tokens used, projected 108% at window end, ETA to cap 1h12m — an orange forecast.

**Card 4 — heading `Six commands`** (definition list; command names in mono):
> `forecast` — Live forecast — time left before your cap. `--json` for machines.
> `dash` — Full-screen terminal dashboard.
> `statusline` — One-line ANSI fragment for any status bar.
> `tmux` — status-right fragment for tmux.
> `snapshot` — Writes forecast.json for other tools to read.
> `doctor` — Checks configuration and data sources.
>
> `[5h] 45.2k/220k · 21% · resets 3h42m`
>
> Representative statusline output.

**Card 5 — heading `Four pillars`**:
> - **Clarity** — understand your true token usage.
> - **Foresight** — plan ahead with accuracy.
> - **Confidence** — avoid surprises, stay in control.
> - **Intention** — spend tokens with purpose.
>
> Provider-agnostic · Zero dependencies · CLI first · Extensible

**Card 6 — heading `Install`**:
> `pipx install token-oracle`
>
> or `pip install token-oracle` · `uvx token-oracle`
>
> View on GitHub  *(link → https://github.com/muslewski/token-oracle)*
>
> `resets in 3h42m`  *(the closing line, mono)*

**Footer**:
> MIT licensed. Built by Mateusz Muślewski.
>
> PyPI *(→ https://pypi.org/project/token-oracle/)* · GitHub *(→ https://github.com/muslewski/token-oracle)* · agentic-sage *(→ https://github.com/muslewski/agentic-sage)*

## Commands you will need

All run from `/home/kento/Repositories/token-oracle` unless a step says
otherwise. Commands containing pipes live only in fenced blocks inside steps
(a markdown table would break their copy-paste form).

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Node present | `node --version` | `v18` or higher |
| Prereq: brief exists | `test -f explore/BRIEF.md` | exit 0 |
| Scaffold | see Step 2 | exact file list in Step 2 |
| Install deps | `npm install` (inside `explore/04-particle-hourglass`) | exit 0 |
| Dev server | `npm run dev` (inside the folder; background + PID, see Step 7) | serves on http://localhost:5173/ |
| Build | `npm run build` (inside the folder) | exit 0; `dist/` written |
| Preview smoke | see Step 10 | `HTTP 200` |
| Tagline gate | `grep -c "Know when you'll hit the limit." explore/04-particle-hourglass/index.html` | `2` |
| Scope check | `git status --porcelain` | see Step 12 — NOT expected to be empty |

## Suggested executor toolkit

- If a `frontend-design` skill is available, you may consult it while styling
  Steps 3–4 — but the tokens, type, and copy in this plan are fixed; the
  skill must not change them.
- Three.js docs (only if the Step 6 code needs interpreting):
  https://threejs.org/docs/ — the plan pins `three@^0.170.0`.

## Scope

**In scope** (the only paths you may create/modify):
- `explore/04-particle-hourglass/` — the whole exploration folder (created
  by this plan; includes scaffold files, `index.html`, `style.css`,
  `main.js`, `hourglass.js`, `README.md`, optional `screenshot.png`).
- `explore/README.md` — ONLY the `| 04 | Particle Hourglass` gallery row's
  Status cell.
- `plans/README.md` — ONLY this plan's status row (+ its dependency note if
  absent).

**Out of scope** (do NOT touch, even though they look related):
- `token_oracle/`, `tests/`, `assets/`, root `README.md` — the product is
  not part of this exploration.
- `explore/BRIEF.md` — operator-approved wording; a change is a report, not
  an edit.
- Every OTHER `explore/` folder (`01-*`, `02-*`, `03-*`, `05-*`) and every
  other gallery row — they belong to plans 025/026/027/029.

## Git workflow

- Branch: `advisor/028-explore-hourglass-webgl`
- Conventional commits, one per logical unit. Suggested sequence:
  - `feat(explore): scaffold particle hourglass exploration` (Step 2)
  - `feat(explore): particle hourglass markup, copy, styles` (Steps 3–4)
  - `feat(explore): particle hourglass canvas, counter, fallback` (Steps 5–6)
  - `docs(explore): particle hourglass readme; mark 04 built` (Steps 11–12)
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Prerequisites and drift check

```bash
cd /home/kento/Repositories/token-oracle
test -f explore/BRIEF.md && echo BRIEF-OK || echo BRIEF-MISSING
```

If it prints `BRIEF-MISSING`: **STOP** — plan 024 has not run; it must run
first. Do not create the brief yourself.

```bash
test -e explore/04-particle-hourglass && echo EXISTS || echo ABSENT
grep -F '| 04 | Particle Hourglass' explore/README.md
node --version
git switch -c advisor/028-explore-hourglass-webgl
```

Also run the drift check from the header blockquote.

**Verify**: the folder check prints `ABSENT`; the grep prints exactly one
row ending in `| planned |`; `node --version` prints v18 or higher;
`git branch --show-current` → `advisor/028-explore-hourglass-webgl`. If the
folder exists, or the row is missing or not `planned`, STOP (another session
may own this exploration).

### Step 2: Scaffold Vite (vanilla) and install Three.js

```bash
cd /home/kento/Repositories/token-oracle
mkdir -p explore/04-particle-hourglass
cd explore/04-particle-hourglass
npm_config_yes=true npm create vite@latest . -- --template vanilla
```

Expected scaffold layout (flat — the vanilla template has no `src/`):
`index.html`, `main.js`, `style.css`, `counter.js`, `javascript.svg`,
`public/vite.svg`, `package.json`, `.gitignore`. If `index.html`, `main.js`,
`style.css`, or `package.json` is missing from the folder root (e.g. a newer
create-vite moved to a `src/` layout), **STOP** — every later step's file
references would be wrong. If create-vite prompts despite the flag, choose
framework "Vanilla", variant "JavaScript", then re-check the layout.

Then install the dependency, remove boilerplate, and stub the entry so the
build stays green between steps:

```bash
npm install
npm install "three@^0.170.0"
rm counter.js javascript.svg public/vite.svg
rmdir public
printf 'import "./style.css";\n' > main.js
printf '/* replaced in step 4 */\n' > style.css
npm run build
```

**Verify**:
`test -f index.html && test -f main.js && test -f style.css && test -f package.json && echo LAYOUT-OK`
→ `LAYOUT-OK`;
`node -e "console.log(require('./package.json').dependencies.three)"` →
`^0.170.0`; `test -f package-lock.json && echo LOCK-OK` → `LOCK-OK`;
`npm run build` → exit 0.

### Step 3: Replace `index.html` — full markup and all copy

Replace the entire contents of
`explore/04-particle-hourglass/index.html` with exactly this (note: straight
apostrophes throughout; the `·` separators and `Muślewski` are UTF-8):

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta
      name="description"
      content="Token Oracle is an offline CLI that forecasts when you will hit your AI-provider token cap. No API calls — nothing leaves your machine."
    />
    <title>Token Oracle — Know when you'll hit the limit.</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⏳</text></svg>" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Marcellus&family=Overpass+Mono&family=Source+Sans+3:wght@400;600&display=swap"
      rel="stylesheet"
    />
    <script type="module" src="/main.js"></script>
  </head>
  <body>
    <canvas id="hourglass-canvas" aria-hidden="true"></canvas>
    <p id="counter" class="counter" aria-hidden="true" hidden></p>

    <header class="site-header">
      <p class="wordmark">Token Oracle</p>
    </header>

    <main>
      <section class="hero">
        <div id="hourglass-fallback" class="hourglass-fallback">
          <svg
            viewBox="0 0 200 280"
            width="200"
            height="280"
            role="img"
            aria-label="An hourglass drawn in luminous grains. The top bulb holds the window allowance that remains; the bottom bulb holds what is spent."
          >
            <defs>
              <linearGradient id="grain-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="#B8B0F5" />
                <stop offset="1" stop-color="#7C6FE8" />
              </linearGradient>
            </defs>
            <polygon points="40,20 160,20 100,138" fill="url(#grain-grad)" fill-opacity="0.28" stroke="#B8B0F5" stroke-opacity="0.45" />
            <polygon points="100,142 40,260 160,260" fill="url(#grain-grad)" fill-opacity="0.28" stroke="#7C6FE8" stroke-opacity="0.45" />
            <circle cx="85" cy="60" r="2.5" fill="#B8B0F5" />
            <circle cx="112" cy="74" r="2" fill="#B8B0F5" />
            <circle cx="98" cy="96" r="2.5" fill="#B8B0F5" />
            <circle cx="105" cy="50" r="1.5" fill="#B8B0F5" />
            <circle cx="100" cy="150" r="1.5" fill="#B8B0F5" />
            <circle cx="100" cy="162" r="1.5" fill="#B8B0F5" />
            <circle cx="100" cy="174" r="1.5" fill="#7C6FE8" />
            <circle cx="88" cy="244" r="2.5" fill="#7C6FE8" />
            <circle cx="104" cy="236" r="2.5" fill="#7C6FE8" />
            <circle cx="116" cy="246" r="2" fill="#7C6FE8" />
          </svg>
        </div>
        <h1>Know when you'll hit the limit.</h1>
        <p class="scroll-hint">Scroll to run the window forward <span aria-hidden="true">↓</span></p>
      </section>

      <section class="beat">
        <article class="glass-card">
          <h2>What happens next</h2>
          <p class="positioning">Usage monitors tell you what you spent. Token Oracle tells you what happens next.</p>
          <p>It's a forecast, not a bill.</p>
          <p>
            token-oracle is an offline CLI that forecasts when you will hit your AI-provider token cap. It reads
            your provider's local usage logs — Claude Code built in, adapters add more — and projects time-to-cap.
            No API calls. Nothing leaves your machine.
          </p>
        </article>
      </section>

      <section class="beat">
        <article class="glass-card">
          <h2>How it works</h2>
          <ol class="steps">
            <li><strong>Read</strong> — token-oracle reads your provider's local usage logs. Claude Code is built in; adapters add more. No API calls — nothing leaves your machine.</li>
            <li><strong>Measure</strong> — it computes your observed burn rate over a sliding window, weighted by your own weekly usage profile.</li>
            <li><strong>Forecast</strong> — it projects usage to window end and tells you what's left before the cap: a percentage, an ETA, and a color.</li>
          </ol>
        </article>
      </section>

      <section class="beat">
        <article class="glass-card">
          <h2>The semaphore</h2>
          <p>Every forecast lands as a color: projected usage at window end, as a percent of your cap.</p>
          <ul class="semaphore-list">
            <li><span class="swatch swatch-green" aria-hidden="true"></span>Green — under 85%</li>
            <li><span class="swatch swatch-lime" aria-hidden="true"></span>Lime — 85 to 100%</li>
            <li><span class="swatch swatch-orange" aria-hidden="true"></span>Orange — 100 to 120%</li>
            <li><span class="swatch swatch-red" aria-hidden="true"></span>Red — 120% and up</li>
          </ul>
          <p>
            The ignition you just watched is the drama scenario: 178,400 / 220,000 tokens used, projected 108% at
            window end, ETA to cap 1h12m — an orange forecast.
          </p>
        </article>
      </section>

      <section class="beat">
        <article class="glass-card">
          <h2>Six commands</h2>
          <dl class="cmd-list">
            <dt><code>forecast</code></dt>
            <dd>Live forecast — time left before your cap. <code>--json</code> for machines.</dd>
            <dt><code>dash</code></dt>
            <dd>Full-screen terminal dashboard.</dd>
            <dt><code>statusline</code></dt>
            <dd>One-line ANSI fragment for any status bar.</dd>
            <dt><code>tmux</code></dt>
            <dd>status-right fragment for tmux.</dd>
            <dt><code>snapshot</code></dt>
            <dd>Writes forecast.json for other tools to read.</dd>
            <dt><code>doctor</code></dt>
            <dd>Checks configuration and data sources.</dd>
          </dl>
          <p class="statusline-mock"><code>[5h] 45.2k/220k · 21% · resets 3h42m</code></p>
          <p class="mock-note">Representative statusline output.</p>
        </article>
      </section>

      <section class="beat">
        <article class="glass-card">
          <h2>Four pillars</h2>
          <ul class="pillars">
            <li><strong>Clarity</strong> — understand your true token usage.</li>
            <li><strong>Foresight</strong> — plan ahead with accuracy.</li>
            <li><strong>Confidence</strong> — avoid surprises, stay in control.</li>
            <li><strong>Intention</strong> — spend tokens with purpose.</li>
          </ul>
          <p class="badges">Provider-agnostic · Zero dependencies · CLI first · Extensible</p>
        </article>
      </section>

      <section class="beat">
        <article class="glass-card">
          <h2>Install</h2>
          <pre class="install"><code>pipx install token-oracle</code></pre>
          <p class="alt-install">or <code>pip install token-oracle</code> · <code>uvx token-oracle</code></p>
          <p><a class="cta-link" href="https://github.com/muslewski/token-oracle">View on GitHub</a></p>
          <p class="closing-line"><code>resets in 3h42m</code></p>
        </article>
      </section>
    </main>

    <footer class="site-footer">
      <p>MIT licensed. Built by Mateusz Muślewski.</p>
      <nav aria-label="Project links">
        <a href="https://pypi.org/project/token-oracle/">PyPI</a>
        <a href="https://github.com/muslewski/token-oracle">GitHub</a>
        <a href="https://github.com/muslewski/agentic-sage">agentic-sage</a>
      </nav>
    </footer>
  </body>
</html>
```

**Verify** (run inside `explore/04-particle-hourglass`):
`npm run build` → exit 0;
`grep -c "Know when you'll hit the limit." index.html` → `2` (title + h1);
`grep -c '<h1' index.html` → `1`;
`grep -c 'lang="en"' index.html` → `1`;
`grep -c '<section class="beat"' index.html` → `6`.
Heading count (grep -o because -c counts lines, not occurrences):

```bash
grep -o '<h2' index.html | wc -l
```

→ `6`.

### Step 4: Replace `style.css` — tokens and all page styles

Replace the entire contents of
`explore/04-particle-hourglass/style.css` with exactly this:

```css
/* Exploration 04 — Particle Hourglass. Tokens per plan 028 design spec. */
:root {
  --obsidian: #0A0A0D;
  --fog: #17161C;
  --card-fill: rgba(23, 22, 28, 0.85);
  --lavender: #B8B0F5;
  --deep-violet: #7C6FE8;
  --ivory: #EDEAE0;
  --ember: #D96C2C;
  --alarm: #CC3D33;
  --hairline: rgba(184, 176, 245, 0.18);
  --font-display: "Marcellus", Georgia, serif;
  --font-body: "Source Sans 3", system-ui, sans-serif;
  --font-data: "Overpass Mono", ui-monospace, monospace;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--obsidian);
  color: var(--ivory);
  font-family: var(--font-body);
  font-weight: 400;
  font-size: 1.0625rem;
  line-height: 1.6;
}

/* Full-bleed canvas behind everything */
#hourglass-canvas {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
}

/* Mono counter HUD */
.counter {
  position: fixed;
  top: 1rem;
  right: 1.25rem;
  z-index: 2;
  margin: 0;
  font-family: var(--font-data);
  font-size: 0.8125rem;
  color: var(--lavender);
  text-align: right;
}

.site-header {
  position: relative;
  z-index: 1;
  padding: 1.25rem 1.5rem;
}

.wordmark {
  margin: 0;
  font-family: var(--font-display);
  font-size: 0.9375rem;
  letter-spacing: 0.35em;
  text-transform: uppercase;
  color: var(--lavender);
}

main {
  position: relative;
  z-index: 1;
}

/* Hero: text bottom-left, hourglass center-screen behind */
.hero {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 0 1.5rem 14vh;
}

.hero h1 {
  margin: 0 0 0.75rem;
  font-family: var(--font-display);
  font-weight: 400;
  font-size: clamp(2rem, 5vw, 3.5rem);
  letter-spacing: 0.06em;
  line-height: 1.15;
  max-width: 16ch;
}

.scroll-hint {
  margin: 0;
  font-family: var(--font-data);
  font-size: 0.875rem;
  color: var(--lavender);
}

/* Static SVG fallback (visible by default; JS hides it when WebGL runs) */
.hourglass-fallback {
  display: flex;
  justify-content: center;
  margin-bottom: 2rem;
}

.hourglass-fallback[hidden] {
  display: none;
}

/* Beats and glass cards */
.beat {
  min-height: 90vh;
  display: flex;
  align-items: center;
  padding: 3rem 1.5rem;
}

.glass-card {
  max-width: 30rem;
  padding: 2rem;
  background: var(--card-fill);
  border: 1px solid var(--hairline);
  border-radius: 10px;
  backdrop-filter: blur(6px);
  margin-left: clamp(0rem, 8vw, 8rem);
}

.glass-card h2 {
  margin: 0 0 1rem;
  font-family: var(--font-display);
  font-weight: 400;
  font-size: 1.375rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--lavender);
}

.glass-card p {
  margin: 0 0 0.75rem;
}

.glass-card p:last-child {
  margin-bottom: 0;
}

.positioning {
  font-weight: 600;
}

.steps {
  margin: 0;
  padding-left: 1.25rem;
}

.steps li {
  margin-bottom: 0.75rem;
}

code {
  font-family: var(--font-data);
  font-size: 0.9em;
  color: var(--lavender);
}

.semaphore-list,
.pillars {
  list-style: none;
  margin: 0 0 0.75rem;
  padding: 0;
}

.semaphore-list li,
.pillars li {
  margin-bottom: 0.5rem;
}

/* Swatch chips: decorative (aria-hidden). Green/lime hexes are display
   constants chosen by plan 028; thresholds come from the brief. */
.swatch {
  display: inline-block;
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 50%;
  margin-right: 0.5rem;
}

.swatch-green { background: #4caf6e; }
.swatch-lime { background: #c9d34b; }
.swatch-orange { background: var(--ember); }
.swatch-red { background: var(--alarm); }

.cmd-list {
  margin: 0 0 1rem;
}

.cmd-list dt {
  float: left;
  clear: left;
  width: 6.5rem;
  font-family: var(--font-data);
}

.cmd-list dd {
  margin: 0 0 0.5rem 7rem;
}

.statusline-mock {
  margin-bottom: 0.25rem;
}

.mock-note {
  font-size: 0.8125rem;
  opacity: 0.75;
}

.badges {
  font-family: var(--font-data);
  font-size: 0.8125rem;
  color: var(--lavender);
}

.install {
  margin: 0 0 0.75rem;
  padding: 0.875rem 1rem;
  background: var(--obsidian);
  border: 1px solid var(--hairline);
  border-radius: 6px;
  overflow-x: auto;
}

.install code {
  font-size: 1rem;
}

a {
  color: var(--lavender);
}

:focus-visible {
  outline: 2px solid var(--lavender);
  outline-offset: 3px;
}

.closing-line {
  font-family: var(--font-data);
  color: var(--lavender);
}

/* Card reveal: JS adds .pre-reveal at init, .is-visible on first view */
.pre-reveal {
  opacity: 0;
  transform: translateY(12px);
}

.is-visible {
  opacity: 1;
  transform: translateY(0);
  transition: opacity 300ms ease-out, transform 300ms ease-out;
}

/* Footer: static, opaque, below the narrative */
.site-footer {
  position: relative;
  z-index: 1;
  padding: 2rem 1.5rem;
  background: var(--obsidian);
  border-top: 1px solid var(--hairline);
  font-size: 0.9375rem;
}

.site-footer p {
  margin: 0 0 0.5rem;
}

.site-footer nav a {
  margin-right: 1.25rem;
}

/* Reduced motion: no canvas, no counter, no reveal animation.
   The page is fully readable in normal document flow. */
@media (prefers-reduced-motion: reduce) {
  #hourglass-canvas,
  .counter {
    display: none;
  }

  .pre-reveal {
    opacity: 1;
    transform: none;
  }

  .is-visible {
    transition: none;
  }
}

/* Narrow screens: usable at 360px */
@media (max-width: 480px) {
  .glass-card {
    margin-left: 0;
    padding: 1.5rem;
  }

  .beat {
    padding: 2rem 1rem;
  }

  .counter {
    left: 1rem;
    right: 1rem;
    font-size: 0.6875rem;
  }

  .cmd-list dt {
    float: none;
    width: auto;
  }

  .cmd-list dd {
    margin-left: 0;
  }
}
```

**Verify** (inside `explore/04-particle-hourglass`):
`npm run build` → exit 0;
`grep -c 'prefers-reduced-motion' style.css` → `1`;
`grep -c 'focus-visible' style.css` → `1`;
`grep -c 'max-width: 480px' style.css` → `1`;
`grep -c 'overflow-x: auto' style.css` → `1`;
`grep -c -- '--obsidian: #0A0A0D' style.css` → `1`.

### Step 5: Replace `main.js` — boot, scroll progress, counter, card reveal, lazy init

Replace the entire contents of
`explore/04-particle-hourglass/main.js` with exactly this:

```js
// main.js — boot: scroll progress, counter text, card reveal, lazy hourglass
// init. The Three.js hourglass lives in hourglass.js and is imported lazily
// (dynamic import after first paint) so the heavy dependency never blocks
// the initial render.
import "./style.css";

// --- honest scenario anchors (from explore/BRIEF.md) ---
const CAP = 220000;
const CALM = { used: 45200, pct: 21 };
const DRAMA = { used: 178400, pct: 108 };
const CALM_LINE = "45,200 / 220,000 tokens used · projected 21% · resets in 3h42m";
const DRAMA_LINE = "178,400 / 220,000 tokens used · projected 108% · ETA to cap 1h12m";

// --- scroll beats (display constants; keep in sync with hourglass.js) ---
const BEATS = { ignite: 0.63, alarm: 0.72, settle: 0.82 };

const canvas = document.getElementById("hourglass-canvas");
const fallback = document.getElementById("hourglass-fallback");
const counterEl = document.getElementById("counter");

const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// --- scroll progress: the handler reads only scrollY and writes targetT ---
let maxScroll = 1;
let targetT = 0;

function measure() {
  maxScroll = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
}

function onScroll() {
  targetT = Math.min(1, Math.max(0, window.scrollY / maxScroll));
}

// --- counter text: interpolates between the two honest anchors ---
const fmt = (n) => Math.round(n).toLocaleString("en-US");

function counterText(t) {
  if (t < 0.02) return CALM_LINE;
  if (t < BEATS.ignite) {
    const u = t / BEATS.ignite;
    const used = CALM.used + (DRAMA.used - CALM.used) * u;
    const pct = Math.round(CALM.pct + (DRAMA.pct - CALM.pct) * u);
    return `${fmt(used)} / ${fmt(CAP)} tokens used · projected ${pct}%`;
  }
  if (t < BEATS.settle) return DRAMA_LINE;
  if (t > 0.98) return CALM_LINE;
  const u = (t - BEATS.settle) / (1 - BEATS.settle);
  const used = DRAMA.used + (CALM.used - DRAMA.used) * u;
  const pct = Math.round(DRAMA.pct + (CALM.pct - DRAMA.pct) * u);
  return `${fmt(used)} / ${fmt(CAP)} tokens used · projected ${pct}%`;
}

// --- glass-card reveal: fade/rise 12px on first view; skipped under reduced motion ---
function setupCards() {
  if (prefersReduced || !("IntersectionObserver" in window)) return;
  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          io.unobserve(entry.target);
        }
      }
    },
    { threshold: 0.2 }
  );
  for (const card of document.querySelectorAll(".glass-card")) {
    card.classList.add("pre-reveal");
    io.observe(card);
  }
}

// --- fps meter for plan 028's performance gate: open the page with ?fps ---
function setupFpsMeter() {
  if (!new URLSearchParams(location.search).has("fps")) return;
  const el = document.createElement("p");
  el.className = "counter";
  el.style.top = "auto";
  el.style.bottom = "1rem";
  el.setAttribute("aria-hidden", "true");
  document.body.appendChild(el);
  let frames = 0;
  let seconds = 0;
  let last = performance.now();
  function tick(now) {
    frames += 1;
    if (now - last >= 1000) {
      seconds += 1;
      console.log(`[fps] second ${seconds}: ${frames} frames`);
      el.textContent = `[fps] second ${seconds}: ${frames} frames`;
      frames = 0;
      last = now;
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

// --- WebGL probe (cheap; renderer construction is also try/caught) ---
function supportsWebGL() {
  try {
    const probe = document.createElement("canvas");
    return Boolean(probe.getContext("webgl2") || probe.getContext("webgl"));
  } catch {
    return false;
  }
}

// --- lazy init: three + renderer load only after first paint / idle ---
async function startHourglass() {
  try {
    const { initHourglass } = await import("./hourglass.js");
    const hourglass = initHourglass(canvas, () => targetT, (t) => {
      counterEl.textContent = counterText(t);
    });
    if (!hourglass) {
      canvas.hidden = true; // renderer failed — static SVG fallback stays
      return;
    }
    fallback.hidden = true;
    counterEl.hidden = false;
    counterEl.textContent = CALM_LINE;
  } catch (err) {
    canvas.hidden = true;
    console.warn("hourglass init failed; static fallback remains", err);
  }
}

measure();
window.addEventListener("resize", measure);
window.addEventListener("scroll", onScroll, { passive: true });
onScroll();
setupCards();
setupFpsMeter();

if (!prefersReduced && supportsWebGL()) {
  if ("requestIdleCallback" in window) {
    requestIdleCallback(startHourglass, { timeout: 1500 });
  } else {
    setTimeout(startHourglass, 200);
  }
}
```

Then create `explore/04-particle-hourglass/hourglass.js` with exactly this
one-line placeholder so the dynamic import resolves (Step 6 replaces it):

```js
export function initHourglass() { return null; }
```

**Verify** (inside `explore/04-particle-hourglass`): `npm run build` →
exit 0;
`grep -c 'prefers-reduced-motion' main.js` → `1`;
`grep -c 'requestIdleCallback' main.js` → `2` (feature test + call);
`grep -c 'passive: true' main.js` → `1`.

### Step 6: Replace `hourglass.js` — the signature element

Replace the entire contents of
`explore/04-particle-hourglass/hourglass.js` with exactly this. It
implements the Design specification (e) recipe verbatim — do not invent
geometry or shaders; if the installed three version rejects any of this code
shape, see STOP conditions.

```js
// hourglass.js — the particle hourglass (plan 028 signature element).
// THREE.Points + BufferGeometry + PointsMaterial. No custom shaders.
import * as THREE from "three";

// GRAIN_COUNT may be reduced to 8000 by the plan's performance gate.
const GRAIN_COUNT = 15000;
const D_MAX = 0.7; // max grain delay; each grain falls over a 0.3 window of g
const REST_FILL = 0.2; // fill at rest ≈ calm scenario 45,200/220,000 (0.205)
const ROT_SPEED = 0.05; // rad/s idle rotation
const EASE = 0.08; // per-frame lerp of current t toward target t
// Display-constant beats; keep in sync with main.js.
const BEATS = { ignite: 0.63, alarm: 0.72, settle: 0.82 };

const LAVENDER = new THREE.Color("#B8B0F5");
const DEEP_VIOLET = new THREE.Color("#7C6FE8");
const EMBER = new THREE.Color("#D96C2C");
const ALARM = new THREE.Color("#CC3D33");

// Silhouette radius at height z, z in [-1, 1].
function radiusAt(z) {
  return 0.08 + (0.55 - 0.08) * Math.pow(Math.abs(z), 1.6);
}

// Rejection-sample one point inside the cone volume between zMin and zMax.
function samplePoint(zMin, zMax) {
  for (;;) {
    const z = zMin + Math.random() * (zMax - zMin);
    const r = radiusAt(z);
    const x = (Math.random() * 2 - 1) * r;
    const y = (Math.random() * 2 - 1) * r;
    if (x * x + y * y <= r * r) return [x, y, z];
  }
}

export function initHourglass(canvas, getTargetT, onProgress) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: false });
  } catch {
    return null; // caller keeps the static SVG fallback visible
  }
  renderer.setClearColor("#0A0A0D", 1);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 10);
  camera.position.set(0, 0, 3.2);

  // --- per-grain data: start (top bulb), neck (0,0,0), pile (bottom bulb) ---
  const starts = [];
  const piles = [];
  for (let i = 0; i < GRAIN_COUNT; i += 1) starts.push(samplePoint(0.02, 1));
  for (let i = 0; i < GRAIN_COUNT; i += 1) piles.push(samplePoint(-1, -0.02));
  starts.sort((a, b) => a[2] - b[2]); // lower grains fall first
  piles.sort((a, b) => a[2] - b[2]); // first faller lands deepest

  const delays = new Float32Array(GRAIN_COUNT);
  const baseColors = new Float32Array(GRAIN_COUNT * 3);
  const positions = new Float32Array(GRAIN_COUNT * 3);
  const colors = new Float32Array(GRAIN_COUNT * 3);
  const tint = new THREE.Color();
  for (let i = 0; i < GRAIN_COUNT; i += 1) {
    delays[i] = starts[i][2] * D_MAX; // delay proportional to start height
    // Per-vertex gradient: high grains lavender, low grains deep violet.
    tint.copy(DEEP_VIOLET).lerp(LAVENDER, starts[i][2]);
    baseColors[i * 3] = tint.r;
    baseColors[i * 3 + 1] = tint.g;
    baseColors[i * 3 + 2] = tint.b;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    vertexColors: true,
    size: 0.02, // world units
    sizeAttenuation: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    transparent: true,
  });

  const points = new THREE.Points(geometry, material);
  points.rotation.x = -Math.PI / 2; // geometry z-axis becomes screen-vertical
  const rig = new THREE.Group();
  rig.add(points);
  scene.add(rig);

  // --- progress mapping (see plan 028 design spec (e)) ---
  const FALL_WINDOW = 1 - D_MAX;

  function fillFraction(t) {
    const ramp =
      t <= BEATS.settle
        ? t / BEATS.settle
        : 1 - (t - BEATS.settle) / (1 - BEATS.settle);
    return REST_FILL + (1 - REST_FILL) * ramp;
  }

  function ignitionState(t) {
    if (t < BEATS.ignite) return { target: null, k: 0 };
    if (t < BEATS.alarm) {
      return { target: EMBER, k: (t - BEATS.ignite) / (BEATS.alarm - BEATS.ignite) };
    }
    if (t < BEATS.settle) return { target: ALARM, k: 1 };
    return { target: ALARM, k: Math.max(0, 1 - (t - BEATS.settle) / (1 - BEATS.settle)) };
  }

  function writeBuffers(t) {
    const g = fillFraction(t);
    const ign = ignitionState(t);
    for (let i = 0; i < GRAIN_COUNT; i += 1) {
      const local = Math.min(1, Math.max(0, (g - delays[i]) / FALL_WINDOW));
      const s = starts[i];
      const p = piles[i];
      let x;
      let y;
      let z;
      if (local < 0.5) {
        const u = local * 2; // start -> neck (neck is the origin)
        x = s[0] * (1 - u);
        y = s[1] * (1 - u);
        z = s[2] * (1 - u);
      } else {
        const u = local * 2 - 1; // neck -> pile
        x = p[0] * u;
        y = p[1] * u;
        z = p[2] * u;
      }
      const j = i * 3;
      positions[j] = x;
      positions[j + 1] = y;
      positions[j + 2] = z;
      if (ign.target && local > 0 && local < 1) {
        // Ignite in-flight grains only.
        colors[j] = baseColors[j] + (ign.target.r - baseColors[j]) * ign.k;
        colors[j + 1] = baseColors[j + 1] + (ign.target.g - baseColors[j + 1]) * ign.k;
        colors[j + 2] = baseColors[j + 2] + (ign.target.b - baseColors[j + 2]) * ign.k;
      } else {
        colors[j] = baseColors[j];
        colors[j + 1] = baseColors[j + 1];
        colors[j + 2] = baseColors[j + 2];
      }
    }
    geometry.attributes.position.needsUpdate = true;
    geometry.attributes.color.needsUpdate = true;
  }

  // --- sizing (DPR cap 2 is a brief performance floor) ---
  function resize() {
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
  resize();
  window.addEventListener("resize", resize);

  // --- run/pause: offscreen and hidden-tab pause ---
  let rafId = 0;
  let running = false;
  let lastTime = 0;
  let onscreen = true;
  let currentT = 0;

  function frame(now) {
    if (!running) return;
    const dt = Math.min(0.05, (now - lastTime) / 1000);
    lastTime = now;
    rig.rotation.y += ROT_SPEED * dt; // slow idle rotation
    currentT += (getTargetT() - currentT) * EASE;
    writeBuffers(currentT);
    onProgress(currentT);
    renderer.render(scene, camera);
    rafId = requestAnimationFrame(frame);
  }

  function setRunning(next) {
    if (next === running) return;
    running = next;
    if (running) {
      lastTime = performance.now();
      rafId = requestAnimationFrame(frame);
    } else {
      cancelAnimationFrame(rafId);
    }
  }

  new IntersectionObserver((entries) => {
    onscreen = entries[0].isIntersecting;
    setRunning(onscreen && !document.hidden);
  }).observe(canvas);
  document.addEventListener("visibilitychange", () => {
    setRunning(onscreen && !document.hidden);
  });

  writeBuffers(0);
  renderer.render(scene, camera);
  setRunning(true);
  return { setRunning };
}
```

**Verify** (inside `explore/04-particle-hourglass`):
`npm run build` → exit 0;
`grep -c 'AdditiveBlending' hourglass.js` → `1`;
`grep -c 'devicePixelRatio' hourglass.js` → `1` (the DPR-2 cap);
`grep -c 'visibilitychange' hourglass.js` → `1`;
`grep -c 'IntersectionObserver' hourglass.js` → `1`;
`grep -c 'Math.pow(Math.abs(z), 1.6)' hourglass.js` → `1` (silhouette formula intact);
`grep -c 'vertexColors' hourglass.js` → `1`.

### Step 7: Performance gate (~30fps with the DPR cap applied)

Measurement method (explicit): the `?fps` meter added in Step 5 logs
`[fps] second N: X frames` to the console once per second AND renders the
same line bottom-right on the page. The gate reads **three consecutive
seconds** of those deltas while the hourglass is animating.

```bash
cd /home/kento/Repositories/token-oracle/explore/04-particle-hourglass
npm run dev &
SERVER_PID=$!
echo "$SERVER_PID" > /tmp/oracle-028-dev.pid
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/)
  if [ "$CODE" = "200" ]; then break; fi
  sleep 1
done
echo "HTTP $CODE"
```

(The PID is captured AND written to `/tmp/oracle-028-dev.pid` because
neither shell job specs like `%1` nor environment variables survive across
separate tool invocations — the manual browser measurement below means the
kill almost certainly runs in a NEW shell, where `$SERVER_PID` is empty.
The pid file is what survives.)

With the server up, open `http://localhost:5173/?fps` in a browser, scroll
to mid-page so grains are falling, and read three consecutive
`[fps] second N` lines:

- All three ≥ ~30 frames → gate passed. Record the numbers for the Step 11
  README.
- Any below ~30 → edit `hourglass.js`: change `const GRAIN_COUNT = 15000;`
  to `const GRAIN_COUNT = 8000;`, reload, re-measure three seconds.
- Still below ~30 at 8000 → **STOP** and report both measurement sets
  (grain count, the three per-second frame counts each).
- **No browser tooling available** → you cannot run this measurement. That
  is NOT a STOP condition: record
  `fps gate not measured — no browser tooling available` for the Step 11
  README and continue.

Then stop the server (from any shell):

```bash
kill "$(cat /tmp/oracle-028-dev.pid)" && rm /tmp/oracle-028-dev.pid
```

**Verify**: `HTTP 200` was printed above; `kill` exits 0; you have either
three per-second frame counts ≥ ~30 or the "not measured" note recorded.

### Step 8: Accessibility and reduced-motion pass

The markup/styles/JS from Steps 3–6 were written to meet the floor; this
step PROVES it. Run inside `explore/04-particle-hourglass`:

Structure gates:
- `grep -c '<header' index.html` → `1`
- `grep -c '<main>' index.html` → `1`
- `grep -c '<footer' index.html` → `1`
- `grep -c '<h1' index.html` → `1`
- `grep -c 'lang="en"' index.html` → `1`
- `grep -c 'aria-hidden' index.html` → `7` (canvas, counter, hint arrow, 4 swatches)
- `grep -c 'aria-label' index.html` → `2` (fallback SVG, footer nav)
- `grep -c 'focus-visible' style.css` → `1`
- `grep -c 'prefers-reduced-motion' style.css` → `1`
- `grep -c 'prefers-reduced-motion' main.js` → `1`
- `grep -c 'prefers-reduced-motion' hourglass.js` → exit code 1, no output
  (correct — the renderer gate lives in main.js, which never constructs the
  hourglass under reduced motion)

Contrast gate (body-text pairs ≥ 4.5:1; `#161418` is `--fog` at 85% opacity
composited over `--obsidian`):

```bash
node <<'EOF'
const lum = ([r, g, b]) => {
  const f = (c) => {
    c /= 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const [R, G, B] = [r, g, b].map(f);
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
};
const hex = (h) => [h.slice(1, 3), h.slice(3, 5), h.slice(5, 7)].map((s) => parseInt(s, 16));
const ratio = (a, b) => {
  const [hi, lo] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (hi + 0.05) / (lo + 0.05);
};
const pairs = [
  ["ivory on obsidian", "#EDEAE0", "#0A0A0D"],
  ["ivory on card", "#EDEAE0", "#161418"],
  ["lavender on obsidian", "#B8B0F5", "#0A0A0D"],
  ["lavender on card", "#B8B0F5", "#161418"],
];
let ok = true;
for (const [name, fg, bg] of pairs) {
  const r = ratio(hex(fg), hex(bg));
  const pass = r >= 4.5;
  ok = ok && pass;
  console.log(name, r.toFixed(2), pass ? "PASS" : "FAIL");
}
console.log(ok ? "ALL PASS" : "FAIL");
process.exit(ok ? 0 : 1);
EOF
```

Expected: four `PASS` lines then `ALL PASS`, exit 0.

Spot-checks if a browser is available (skip silently if not): Tab shows the
lavender focus outline on every link; with reduced motion emulated
(DevTools → Rendering → `prefers-reduced-motion: reduce`, then reload) the
canvas and counter are gone, the static SVG hourglass shows in the hero,
cards are fully visible without animation, and all copy reads top to bottom.

**Verify**: every gate above at its expected value; the contrast script
prints `ALL PASS` and exits 0.

### Step 9: Responsive pass (usable at 360px)

Run inside `explore/04-particle-hourglass/` (the bare `style.css` paths and
`npm run build` below resolve only there):

The narrow-screen rules were written in Step 4; this step proves they are
present and complete:

- `grep -c 'max-width: 480px' style.css` → `1` (cards full-width, counter
  shrinks and may wrap to two lines, `dl` unfloats)
- `grep -c 'overflow-x: auto' style.css` → `1` (the install `<pre>` scrolls
  inside itself instead of widening the page)
- `grep -c 'clamp(2rem, 5vw, 3.5rem)' style.css` → `1` (h1 scales down)

Spot-check if a browser is available: at 360px viewport width there is no
horizontal page scroll, every card is fully readable, and the hero h1 wraps
without clipping.

**Verify**: the three greps at their expected values; `npm run build` →
exit 0.

### Step 10: Build and preview smoke test

```bash
cd /home/kento/Repositories/token-oracle/explore/04-particle-hourglass
npm run build
test -f dist/index.html && echo BUILD-OK
npm run preview -- --port 4174 --strictPort &
SERVER_PID=$!
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:4174/)
  if [ "$CODE" = "200" ]; then break; fi
  sleep 1
done
echo "HTTP $CODE"
kill $SERVER_PID
```

Expected: `BUILD-OK`, then `HTTP 200`, then `kill` exits 0.

Lazy-init evidence — the dynamic import must have produced a separate chunk
so `three` is not in the entry bundle:

```bash
ls dist/assets/*.js | wc -l
```

→ `2` or more (entry chunk + hourglass/three chunk). If it prints `1`, the
dynamic `import("./hourglass.js")` was turned into a static import — fix
main.js to match Step 5 before proceeding.

Record the gzipped JS size (informational — the brief exempts the Three.js
exploration from the < 250 KB budget; lazy-init is the mandated mitigation):

```bash
cat dist/assets/*.js | gzip -c | wc -c
```

→ a byte count (expect very roughly 100,000–200,000); write it down for the
Step 11 README. Also informational, NOT a gate (the build may transform
quotes — the source grep in Step 3 is the authoritative tagline gate):
`grep -c "Know when you'll hit the limit." dist/index.html` → normally ≥ 1.

**Verify**: `BUILD-OK`; `HTTP 200`; chunk count ≥ 2.

### Step 11: Write the exploration README

Create `explore/04-particle-hourglass/README.md` with this content, filling
the three `<...>` placeholders from Steps 7 and 10 (they are the only edits
you make to it):

````markdown
# 04 — Particle Hourglass

Vite + Three.js. One generative object in a dark room: a luminous hourglass
built from ~15,000 additive points floats in a full-bleed canvas. The top
bulb holds the remaining window allowance, the bottom holds what is spent;
scrolling scrubs time toward window end, the falling stream ignites ember
then alarm at the drama beat, and everything settles back to calm at the
install CTA.

## Run

```bash
npm install
npm run dev       # http://localhost:5173
npm run build     # writes dist/
npm run preview   # serves dist/
```

## Brand stance

Remix. The banner's hourglass-in-a-magic-circle motif, rebuilt as the entire
experience. The named aesthetic risk: a WebGL object as the entire hero of a
marketing page — taken with discipline: static SVG fallback, reduced-motion
path (the renderer never starts), devicePixelRatio capped at 2, renderer
paused when offscreen or when the tab is hidden, Three.js lazy-loaded after
first paint.

## Design rationale

- Palette: obsidian #0A0A0D (bg), fog #17161C at 85% (glass cards), particle
  gradient lavender #B8B0F5 → deep violet #7C6FE8, ivory #EDEAE0 (text),
  ember #D96C2C / alarm #CC3D33 (ignition, canvas-only),
  hairline rgba(184,176,245,0.18) (borders).
- Type: Marcellus 400 (display, letterspaced capitals) / Source Sans 3
  400+600 (body) / Overpass Mono 400 (data), all with system fallback stacks
  and font-display: swap.
- Signature element: a THREE.Points hourglass, no custom shaders — two cone
  volumes, per-grain start/neck/pile positions, scroll-scrubbed fall with
  per-grain delays, vertex-color ignition at the drama beat.
- Sample numbers are the brief's two honest scenarios only (calm
  45,200/220,000 → 21%; drama 178,400/220,000 → 108%, ETA 1h12m).
- Fallback: a static inline SVG hourglass plus the full copy in normal
  document flow whenever WebGL is unavailable or reduced motion is set.

## Performance

- fps gate (plan 028 step 7): <RESULT — either the three per-second frame
  counts plus the grain count used, or the sentence "fps gate not measured
  — no browser tooling available">
- Gzipped JS (informational; the Three.js exploration is budget-exempt per
  the brief): <BYTES> bytes across <N> chunks; three loads lazily after
  first paint.

## Screenshot

screenshot.png — to be added when browser tooling is available; it was not
available at build time, so this note stands in.
````

If you CAN take a screenshot: save it as `screenshot.png` (1280px wide) in
this folder and replace the Screenshot section body with
`![Particle Hourglass landing page](./screenshot.png)`. Browser tooling
being unavailable is NOT a STOP condition — the note above stands in.

**Verify**:
`grep -c "Remix." explore/04-particle-hourglass/README.md` → `1`;
`grep -c "fps gate" explore/04-particle-hourglass/README.md` → ≥ `1`;
no literal `<RESULT`, `<BYTES`, or `<N>` remains:
`grep -c '<RESULT' explore/04-particle-hourglass/README.md` → exit code 1,
no output.

### Step 12: Flip the gallery row, update the plan index, final scope check

1. In `explore/README.md`, change ONLY the exploration-04 row — the Status
   cell goes from `planned` to `built`; every other cell stays identical:

   ```
   | 04 | Particle Hourglass | remix | Vite + Three.js | `npm i && npm run dev` | plans/028 | built |
   ```

2. In `plans/README.md`: if a `| 028 |` row exists in the execution-order
   table, set its Status cell to `DONE`; if it does not exist, append this
   row after the table's last plan row:

   ```
   | 028 | Exploration 04: Particle Hourglass — Three.js generative hero (`explore/04-particle-hourglass/`) | P3 | L | 024 | DONE |
   ```

3. Final scope check, then commit.

**Verify**:
`grep -c 'Particle Hourglass.*built' explore/README.md` → `1`;
`grep -Fc '| 028 |' plans/README.md` → `1`;
`git diff --stat -- explore/README.md` → `1 file changed, 1 insertion(+), 1 deletion(-)`
(note: run this BEFORE staging — `git diff --stat` shows nothing once the
file is staged; after staging use `git diff --cached --stat` instead. It
also shows nothing if plan 024 left `explore/README.md` UNTRACKED rather
than committed — in that case skip this gate and rely on the
`Particle Hourglass.*built` grep above);
`git status --porcelain -- explore/ plans/README.md` → every listed entry is
under `explore/04-particle-hourglass/` or is `explore/README.md` or
`plans/README.md` (the pathspec makes this machine-checkable). An unscoped
`git status --porcelain` will NOT be empty: pre-existing untracked entries
you did not create (e.g. `?? plans/`, `?? .claude/`) are expected and
ignorable.
`node_modules/` and `dist/` must not appear —
`git check-ignore explore/04-particle-hourglass/node_modules` echoes the
path (the scaffold `.gitignore` covers both).

## Test plan

No unit tests — this is a design prototype; the product's Python test suite
is untouched and irrelevant here. The gates are:

- Build gate after every code step: `npm run build` → exit 0 (Vite fails
  the build on JS syntax errors and bad imports).
- Performance gate (Step 7): three consecutive seconds of rAF frame counts,
  each ≥ ~30, at DPR ≤ 2 — with the 8000-grain fallback and an explicit
  not-measurable escape when no browser exists.
- Accessibility gates (Step 8): landmark/h1/aria/focus-visible/
  reduced-motion greps at their expected counts; the node contrast script
  prints `ALL PASS`, exit 0.
- Responsive gates (Step 9): narrow-screen greps at expected counts.
- Smoke gate (Step 10): `curl` → `200`; dynamic-import chunk split (≥ 2 JS
  chunks in `dist/assets/`).
- Browser spot-checks when available: keyboard Tab shows the lavender focus
  outline; reduced-motion emulation shows the static SVG page with no
  canvas, no counter, no card animation; 360px width has no horizontal
  scroll.

## Done criteria

Machine-checkable. ALL must hold (run from the repo root):

- [ ] `test -f explore/BRIEF.md` → exit 0
- [ ] `(cd explore/04-particle-hourglass && npm run build)` → exit 0, and `test -f explore/04-particle-hourglass/dist/index.html` → exit 0
- [ ] Preview smoke (Step 10): `curl -s -o /dev/null -w "%{http_code}" http://localhost:4174/` → `200` while `npm run preview -- --port 4174 --strictPort` runs
- [ ] `grep -c "Know when you'll hit the limit." explore/04-particle-hourglass/index.html` → `2` (SOURCE gate — the build may transform quotes in `dist/`, so dist is not the gate)
- [ ] `grep -rl "prefers-reduced-motion" explore/04-particle-hourglass/style.css explore/04-particle-hourglass/main.js` → prints both paths
- [ ] `grep -c "focus-visible" explore/04-particle-hourglass/style.css` → `1`
- [ ] `grep -c 'lang="en"' explore/04-particle-hourglass/index.html` → `1`
- [ ] `grep -c 'devicePixelRatio' explore/04-particle-hourglass/hourglass.js` → `1` (DPR cap present)
- [ ] `test -f explore/04-particle-hourglass/README.md` → exit 0
- [ ] `grep -c 'Particle Hourglass.*built' explore/README.md` → `1` (gallery row flipped)
- [ ] `grep -Fc '| 028 |' plans/README.md` → `1` (status row present and updated)
- [ ] `git status --porcelain -- explore/ plans/README.md`: no entries outside `explore/04-particle-hourglass/`, `explore/README.md`, `plans/README.md` (scoped pathspec — an unscoped run additionally shows pre-existing untracked entries like `?? plans/` or `?? .claude/`, which the executor did not create and must not add)

## STOP conditions

Stop and report back (do not improvise) if:

- `explore/BRIEF.md` does not exist — plan 024 has not run; run it first. Do
  not create the brief yourself.
- `explore/04-particle-hourglass/` already exists with files in it, or the
  gallery's `| 04 | Particle Hourglass` row is missing or not `planned` —
  another session may own this exploration.
- The npm registry is unreachable (`npm create` / `npm install` fails with
  `ENOTFOUND`, `ETIMEDOUT`, or a proxy error) — the page cannot be built
  offline; report instead of vendoring three by hand.
- `npm create vite` emits a file layout that does not match Step 2's
  expected list (`index.html`, `main.js`, `style.css`, `package.json` at the
  folder root) — every later step's file references would be wrong.
- The installed `three@^0.170.0` does not match the plan's code shape — e.g.
  `THREE.PointsMaterial` rejects the Step 6 options, `BufferAttribute` /
  `setAttribute` signatures differ, or
  `geometry.attributes.position.needsUpdate = true` is no longer the
  attribute-update mechanism. Report the installed version (`npm ls three`)
  and the exact error rather than improvising against a different API.
- Performance gate failure: measured below ~30fps for three consecutive
  seconds at 8000 grains with the DPR cap applied — report both measurement
  sets (15000 and 8000). (An UNMEASURABLE gate — no browser — is NOT a STOP;
  see Step 7.)
- The header drift check shows changes under `explore/04-particle-hourglass/`
  or the 04 gallery row not reading `planned`.
- A step's verification fails twice after a reasonable fix attempt.
- Any fix would require touching an out-of-scope file (root `README.md`,
  `explore/BRIEF.md`, another exploration's folder, anything Python).

## Maintenance notes

- The canvas is `position: fixed`, so the IntersectionObserver reports it
  visible whenever the page is on screen — in THIS layout the effective
  pause is `visibilitychange` (hidden tab). The observer is deliberately
  kept: it is the direction's spec and becomes load-bearing the moment the
  canvas stops being fixed (e.g. if this design graduates and the hero
  becomes a scrolling section). Do not remove it as "dead code".
- `BEATS` is duplicated in `main.js` and `hourglass.js` (a prototype
  trade-off to keep the lazy-loaded chunk self-contained). If the beats
  change, change both.
- Grain geometry is sampled once at init; a window resize rescales the
  viewport but does not re-sample the volumes. Fine for a prototype; a
  production port should re-seed on significant aspect changes.
- The page embeds copy from `explore/BRIEF.md`. If the brief's canonical
  copy, scenarios, or thresholds change, this page must be re-synced —
  copies drift.
- Reviewer should scrutinize: the counter's transient numbers (they must
  read as display interpolation between the two honest anchors, never as
  product claims), ember/alarm never appearing as text color (alarm is
  3.9:1 on obsidian), the fallback path (page complete with WebGL off), and
  the dynamic-import chunk split (lazy-init is the brief's condition for the
  size exemption).
- Deferred deliberately: `screenshot.png` when browser tooling is absent;
  self-hosted fonts (Google Fonts `<link>` is brief-sanctioned for
  prototypes only); resize re-sampling.

