# Plan 024: Create the design-exploration workspace and shared brief for the Token Oracle marketing site

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ada32e9..HEAD -- explore/ plans/README.md`
> If `explore/` already contains files, or the `plans/README.md` table no
> longer matches the excerpt in "Current state", treat it as a STOP condition.

## Status

- **Priority**: P2 (gates the whole marketing-design round — run before 025–029)
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: direction
- **Planned at**: commit `ada32e9`, 2026-07-02

## Why this matters

token-oracle will eventually get a marketing site in a **separate repository**.
Before committing to one visual direction, the operator wants several complete,
opinionated prototypes that can be compared side by side. This plan creates the
workspace those prototypes live in (`explore/`) and the shared brief they all
argue from — the same product facts, the same canonical copy, the same honesty
and accessibility rules — so that when the prototypes exist, the *only*
difference between them is design. Plans 025–029 each build one exploration and
depend on the two files this plan creates.

## Current state

- `explore/` does not exist in the repo (verify: `ls explore` → "No such file or directory").
- Product facts live in `README.md` (install, subcommands, how-it-works, color
  thresholds), `ADAPTERS.md` (snapshot JSON schema — the source of honest sample
  data), and `plans/research-competitive-landscape.md` (positioning: no
  competitor is prediction-first; that's the whitespace the copy exploits).
- The existing brand identity is the repo banner `assets/oracle-banner.webp`
  (also `.avif`): "TOKEN ORACLE" wordmark in a bold condensed sans, navy fading
  to violet-blue on "ORACLE" with a star glyph; an anime-style masked oracle in
  white-and-lavender robes; an hourglass inside a magic circle; a crescent moon;
  soft lavender watercolor sky; a small gold sparkle divider; four pillar cards
  (CLARITY / FORESIGHT / CONFIDENCE / INTENTION); a badge strip
  (Provider-agnostic · Zero dependencies · CLI first · Extensible).
- The `plans/README.md` index table ends with pre-registered rows 024–029
  (status `TODO`), added by the advisor when this round was planned. This plan
  changes nothing in that table except its own 024 status cell (see Step 3).
  The "024 gates 025–029" dependency note is likewise already present under
  "## Dependency notes".
- Repo commit style is conventional commits (see `git log --oneline`:
  `fix(dash): ...`, `chore(core): ...`, `test: ...`).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Confirm workspace absent | `ls explore` | error: No such file or directory |
| Create workspace | `mkdir -p explore` | exit 0 |
| Check headings | `grep -c '^## ' explore/BRIEF.md` | ≥ 8 |
| Scope check | `git status --porcelain` | only `explore/` and `plans/` paths |

No Python, Node, or build tooling is needed for this plan.

## Scope

**In scope** (the only files you should create/modify):
- `explore/README.md` (create)
- `explore/BRIEF.md` (create)
- `plans/README.md` (flip the pre-registered 024 row's status cell only)

**Out of scope** (do NOT touch):
- Everything under `token_oracle/`, `tests/`, `assets/`, `docs/` — this plan
  writes markdown only.
- The root `README.md` — the explorations are internal; do not advertise them.
- Any file under `explore/0*-*/` — those folders belong to plans 025–029.

## Git workflow

- Branch: `advisor/024-explore-scaffold-brief`
- One commit: `feat(explore): add design-exploration workspace and shared brief`
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Create `explore/README.md`

Create the file with exactly this content:

```markdown
# explore/ — marketing-site design explorations

Prototypes for the future Token Oracle marketing site (which will live in a
**separate repository**). Each exploration is a complete, opinionated,
self-contained landing page — same product, same copy, radically different
design. They exist to be compared; the winning direction gets re-implemented
properly in the marketing-site repo, and this folder stays behind as the
design archive.

Read [BRIEF.md](./BRIEF.md) first — every exploration builds from it.

## Rules

- One folder per exploration: `explore/NN-slug/`. Fully self-contained:
  its own `package.json` (or none, for zero-build pages), its own assets.
- Explorations never share code, styles, or components with each other —
  isolation is deliberate; it keeps the comparison honest.
- Every exploration ships its own `README.md` with: the run command, the
  design rationale (brand stance, palette, type, signature element), and a
  screenshot (`screenshot.png`) when browser tooling is available.
- Built explorations must produce a static `dist/` via `npm run build`.
  Zero-build explorations must open directly via `index.html`.

## Gallery

| # | Exploration | Stance | Stack | Run | Plan | Status |
|---|-------------|--------|-------|-----|------|--------|
| 01 | Teletype Ledger | contrast | zero-dep HTML/CSS/JS | open `index.html` | plans/025 | planned |
| 02 | Night Observatory | remix | Vite + GSAP ScrollTrigger | `npm i && npm run dev` | plans/026 | planned |
| 03 | Instrument Panel | adopt | Vite + React + Motion | `npm i && npm run dev` | plans/027 | planned |
| 04 | Particle Hourglass | remix | Vite + Three.js | `npm i && npm run dev` | plans/028 | planned |
| 05 | Token Almanac | contrast | zero-dep HTML/CSS | open `index.html` | plans/029 | planned |

Status values: planned | built | needs-fix | archived
```

**Verify**: `grep -c '^| 0' explore/README.md` → `5`

### Step 2: Create `explore/BRIEF.md`

Create the file with exactly this content:

```markdown
# Token Oracle — shared design brief

Every exploration in this folder builds from this brief. Design freely;
facts, copy, and floors below are fixed.

## Product facts (do not embellish)

- **token-oracle** is an offline CLI that forecasts when you will hit your
  AI-provider token cap. It reads the provider's **local usage logs** (Claude
  Code built in; adapters add more), computes an observed burn rate over a
  sliding window, and projects time-to-cap. **No API calls. Nothing leaves
  your machine.**
- Python, zero runtime dependencies, MIT licensed, on PyPI.
- Subcommands: `forecast` (live forecast, `--json`), `dash` (full-screen
  terminal dashboard), `statusline` (one-line ANSI fragment for any status
  bar), `tmux` (status-right fragment), `snapshot` (writes `forecast.json`
  for other tools), `doctor` (checks configuration and data sources).
- Color semaphore on projected usage at window end (as % of cap):
  green < 85 % · lime 85–100 % · orange 100–120 % · red ≥ 120 %.
- Positioning whitespace (from competitive research): every other usage tool
  reports what you **spent**; token-oracle is **prediction-first** — past /
  present / future, with future as the headline act.

## Audience & voice

- Audience: Claude Code power users and terminal-dwelling developers on
  capped plans. They read man pages for fun and distrust marketing.
- Voice: plain verbs, specific over clever, calm confidence. The oracle
  metaphor is seasoning, never fog. Sentence case everywhere.

## Canonical copy (use verbatim where the design calls for it)

- Tagline (MUST appear somewhere on every page, exactly, straight
  apostrophe): `Know when you'll hit the limit.`
- Positioning: `Usage monitors tell you what you spent. Token Oracle tells
  you what happens next.`
- Secondary line: `It's a forecast, not a bill.`
- How it works (three steps):
  1. **Read** — token-oracle reads your provider's local usage logs. Claude
     Code is built in; adapters add more. No API calls — nothing leaves your
     machine.
  2. **Measure** — it computes your observed burn rate over a sliding
     window, weighted by your own weekly usage profile.
  3. **Forecast** — it projects usage to window end and tells you what's
     left before the cap: a percentage, an ETA, and a color.
- Pillars (from the banner): **Clarity** — understand your true token usage.
  **Foresight** — plan ahead with accuracy. **Confidence** — avoid
  surprises, stay in control. **Intention** — spend tokens with purpose.
- Proof badges: Provider-agnostic · Zero dependencies · CLI first · Extensible
- Install (primary CTA): `pipx install token-oracle`
  (alternatives: `pip install token-oracle`, `uvx token-oracle`)
- Secondary CTA: `View on GitHub` → https://github.com/muslewski/token-oracle
- Footer: `MIT licensed. Built by Mateusz Muślewski.` + links: PyPI
  (token-oracle), GitHub (muslewski/token-oracle), companion project
  agentic-sage.

## Honest sample data (matches the real forecast.json schema)

Calm scenario: window `5h`, used 45,200 / cap 220,000, projected 21 % at
window end, resets in 3 h 42 m → green.
Drama scenario: window `5h`, used 178,400 / cap 220,000, projected 108 %,
ETA to cap 1 h 12 m, resets in 2 h 48 m → orange.
Statusline mock (representative, not claimed as exact CLI output):
`[5h] 45.2k/220k · 21% · resets 3h42m`

## Honesty guardrails (hard rules)

- No testimonials, no user counts, no "trusted by" logos, no star counts,
  no invented benchmarks, no named competitors.
- Every claim must trace to README.md, ADAPTERS.md, or the facts above.
- Sample numbers must come from the two scenarios above.

## Brand identity & stance

The existing identity is the repo banner (`assets/oracle-banner.webp`):
lavender watercolor sky, masked oracle in white-and-lavender robes, hourglass
in a magic circle, crescent moon, navy→violet gradient wordmark, gold sparkle
accents. Each exploration declares one stance in its README:
- **adopt** — extend this identity faithfully,
- **remix** — keep its motifs (hourglass, night sky, semaphore), change the
  execution,
- **contrast** — argue for a different identity; say why.

## Accessibility floor (every exploration)

Semantic landmarks (`header/main/footer`, one `h1`); visible
`:focus-visible` styles; body-text contrast ≥ 4.5:1; every animation gated
behind `prefers-reduced-motion: reduce` (page fully readable with it on);
interactive demos keyboard-operable; images have alt text; `lang="en"`;
usable at 360 px width.

## Performance floor

`font-display: swap` on webfonts; canvas/WebGL capped at devicePixelRatio 2;
no scroll-handler layout thrash (use transforms/opacity); zero-build pages
carry ≤ 200 lines of JS; built pages keep the JS bundle < 250 KB gzipped
(Three.js exploration exempt, but must lazy-init and offer a static
fallback).

## Tech rules

- Fonts: Google Fonts `<link>` is allowed (prototypes), always with a
  system fallback stack. No other runtime CDNs — all JS dependencies come
  pinned via npm.
- No analytics, no trackers, no external network calls at runtime beyond
  fonts.
- Node ≥ 18 assumed for built explorations.

## Evaluation rubric (how the operator compares explorations)

| Criterion | Question |
|-----------|----------|
| 5-second test | Does a cold visitor know what this is and why it's different within one screen? |
| Distinctiveness | Could this design be mistaken for a template or for another exploration? |
| Craft | Type scale, spacing, and motion feel intentional at every breakpoint? |
| Honesty | Zero violations of the guardrails? |
| A11y & perf | Floors met (spot-check keyboard, reduced motion, 360 px)? |
| Fit | Does the stance argument hold — would this sell token-oracle to its actual audience? |

## Graduation

The winning direction is re-implemented cleanly in the separate
marketing-site repository. `explore/` is never deployed; it is the design
record.
```

**Verify**: `grep -c "Know when you'll hit the limit." explore/BRIEF.md` → ≥ 1,
and `grep -c '^## ' explore/BRIEF.md` → ≥ 8

### Step 3: Register this plan in the index

In `plans/README.md`, the execution-order table already carries a
pre-registered row:

```markdown
| 024 | Design-exploration workspace + shared brief (`explore/`) | P2 | S | — | TODO |
```

Change ONLY its Status cell from `TODO` to `DONE` plus the commit hash, e.g.
`DONE (commit <hash>)`. The "024 gates 025–029" dependency note already
exists under "## Dependency notes" — do not duplicate it. If the 024 row is
unexpectedly absent, append it (after the 023 row) with Status `DONE
(commit <hash>)` instead.

**Verify**: `grep -c '| 024 |' plans/README.md` → `1`, and
`grep '| 024 |' plans/README.md | grep -c 'TODO'` → `0`

## Test plan

No automated tests apply (markdown only). Verification is the grep gates in
each step plus:

- `git status --porcelain` → only `explore/README.md`, `explore/BRIEF.md`,
  `plans/README.md` listed.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `test -f explore/README.md && test -f explore/BRIEF.md` → exit 0
- [ ] `grep -c '^| 0' explore/README.md` → `5` (gallery has five rows)
- [ ] `grep -c "Know when you'll hit the limit." explore/BRIEF.md` → ≥ 1
- [ ] `grep -c '| 024 |' plans/README.md` → `1`
- [ ] `git status --porcelain` shows no paths outside `explore/` and `plans/`
- [ ] `plans/README.md` status row for 024 updated

## STOP conditions

Stop and report back (do not improvise) if:

- `explore/` already exists and contains any file — the workspace may have
  been created by another session; reconcile with the operator instead of
  overwriting.
- The `plans/README.md` table no longer ends at plan 023 and a `| 024 |` row
  already exists.
- You are tempted to change canonical copy or guardrails — the brief's
  wording is operator-approved as written; wording changes are a report,
  not an edit.

## Maintenance notes

- Plans 025–029 each add one exploration folder and flip their gallery row
  from `planned` to `built`. If an exploration is abandoned, mark its row
  `archived` rather than deleting the folder.
- If the product's install command, subcommand list, or threshold table
  changes, `explore/BRIEF.md` must be re-synced with `README.md` — the brief
  is a copy, and copies drift.
- When the marketing-site repo is created, link it from `explore/README.md`
  and freeze this folder (status column → `archived`).
