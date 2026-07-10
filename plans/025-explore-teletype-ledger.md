# Plan 025: Exploration 01: Teletype Ledger — zero-dependency paper-terminal landing page

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ada32e9..HEAD -- explore/01-teletype-ledger/ explore/README.md plans/README.md`
> Expected: no committed changes under `explore/01-teletype-ledger/`.
> (`git diff` cannot see untracked files — the folder-must-not-exist check is
> Step 1's `test ! -e`.) `explore/README.md` and `plans/README.md` MAY show
> changes — but only the ones plan 024 makes (creating the gallery) plus
> advisor index maintenance (pre-registered rows 024–029 and status flips as
> sibling plans land).
> Compare the gallery-row excerpt in "Current state" below against the live
> `explore/README.md`; on a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans/024-explore-scaffold-brief.md
- **Category**: direction
- **Planned at**: commit `ada32e9`, 2026-07-02

## Why this matters

token-oracle will get a marketing site in a separate repository. Before
committing to one visual direction, the operator wants several complete,
opinionated landing-page prototypes in `explore/`, one folder each, built from
the same brief so the only variable is design. This plan builds exploration 01,
"Teletype Ledger": the whole page is a continuous-form teletype printout of one
oracle session. It is the lowest-risk exploration of the round — zero build
step, three files — and it argues the CONTRAST stance: the artifact (a printed
forecast) is more credible to terminal-dwelling developers than any mascot or
illustration.

## Current state

- `explore/BRIEF.md` and `explore/README.md` exist only if plan 024 has run.
  Step 1 verifies this; if they are missing, STOP — run plan 024 first.
- `explore/README.md` contains a gallery table. The row this plan will flip
  from `planned` to `built` reads exactly:

  ```
  | 01 | Teletype Ledger | contrast | zero-dep HTML/CSS/JS | open `index.html` | plans/025 | planned |
  ```

- `explore/01-teletype-ledger/` does not exist yet. This plan creates it with
  exactly four files: `index.html`, `styles.css`, `main.js`, `README.md`
  (plus an optional `screenshot.png` if browser tooling is available).
- Product facts (from the repo root `README.md`, inlined here so you never
  need to open it): install is `pipx install token-oracle` (alternatives
  `pip install token-oracle`, `uvx token-oracle`); six subcommands —
  `forecast` (live forecast, `--json`), `dash` (full-screen terminal
  dashboard), `statusline` (one-line ANSI fragment for any status bar),
  `tmux` (status-right fragment), `snapshot` (writes `forecast.json` for
  other tools), `doctor` (checks configuration and data sources); the CLI
  usage line is `token-oracle {forecast,snapshot,statusline,tmux,doctor,dash} [OPTIONS]`;
  color thresholds on projected usage at window end as % of cap:
  green < 85%, lime 85–100%, orange 100–120%, red ≥ 120%. It reads local
  usage logs only — no API calls, nothing leaves your machine. MIT licensed,
  copyright Mateusz Muślewski.
- Honesty guardrails (hard rules from `explore/BRIEF.md`, inlined): no
  testimonials, no user counts, no "trusted by" logos, no star counts, no
  invented benchmarks, no named competitors. Sample numbers must come only
  from the two scenarios in the "Copy" section below.
- Repo commit style is conventional commits (`feat(...)`, `fix(...)`,
  `docs(...)` — see `git log --oneline`).
- The repo is a Python CLI project, but this plan touches no Python source
  and needs no Python tooling; `python3` is used only as a static file
  server, and `node` only for a JavaScript syntax check.

## Design specification

### Brand stance

**CONTRAST.** The artifact is the brand: the oracle speaks through a printout,
not a mascot — for an audience that reads man pages for fun and distrusts
marketing, a printed forecast is the most persuasive object we can show.
The ONE named aesthetic risk this design takes: **no imagery at all, and color
used ONLY as data** — the four semaphore colors appear exclusively where they
encode urgency; every other pixel is ink on paper.

### Design tokens

| Token | Hex | Used for |
|-------|-----|----------|
| `--paper` | `#FAFAF7` | page background (the paper) |
| `--ink` | `#1C1B18` | all text, rules, focus outline (contrast on paper ≈ 15.9:1) |
| `--feed-gray` | `#DDDAD2` | tractor-feed hole-strip background |
| `--hole-shadow` | `#C9C6BD` | punched holes in the strips; perforation dashes |
| `--sem-green` | `#1F7A33` | semaphore data only: green status text/glyphs (≈ 5.1:1 on paper) |
| `--sem-lime` | `#93A11A` | semaphore data only: lime glyphs (≈ 2.7:1 — glyph-only rule below) |
| `--sem-orange` | `#C2681C` | semaphore data only: orange status text/glyphs (≈ 3.8:1 — glyph-only rule) |
| `--sem-red` | `#BF3B2F` | semaphore data only: red glyphs (≈ 5.2:1 on paper) |

No other colors anywhere. Glyph-only rule: because lime and orange fall below
4.5:1 on paper, they may tint only data glyphs whose information is duplicated
in adjacent ink text (sparkline blocks, whose weight encodes the same value as
their color, sit next to ink captions; a tinted `[orange]` tag sits on a line
whose ink text already says `108% of cap`). Body text is always `--ink`.

### Type

| Role | Google Fonts family | Weights | Fallback stack |
|------|--------------------|---------|----------------|
| display (h1, h2, masthead) | IBM Plex Mono | 600 | `ui-monospace, SFMono-Regular, Menlo, monospace` |
| body (paragraphs, links) | IBM Plex Mono | 400 | `ui-monospace, SFMono-Regular, Menlo, monospace` |
| data (transcripts, `pre`) | IBM Plex Mono | 400 (600 for status lines) | `ui-monospace, SFMono-Regular, Menlo, monospace` |
| margin annotations | Newsreader italic | 400 | `Georgia, serif` |

Loaded via one Google Fonts `<link>` with `display=swap` in the URL (this is
the `font-display: swap` mechanism for Google Fonts):
`https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Newsreader:ital,wght@1,400&display=swap`
Hierarchy comes from size, weight, and letter-spacing — never a family change
(except the serif annotations, which read as pencil notes on the printout).

### Wireframe (top to bottom)

```
┌──┬──────────────────────────────────────────────────────────┬──┬─────────┐
│o │ ========= TOKEN ORACLE · SESSION PRINTOUT =========      │o │         │
│o │ DATE 2026-07-02 · TIME 09:14 UTC · HOST devbox · PAGE 1  │o │ note 1  │
│o │ Know when you'll hit the limit.              <h1>        │o │ (wide   │
│o │ Usage monitors tell you what you spent. Token Oracle     │o │ screens:│
│o │ tells you what happens next.                              │o │ serif   │
│o │ - - - - - - perforation <hr class="perf"> - - - - - -    │o │ notes   │
│o │ INSTALL                                      <h2>        │o │ hang in │
│o │ $ pipx install token-oracle  (+ output, + alternatives)  │o │ a third │
│o │ - - - - - - - - - - perforation - - - - - - - - - -      │o │ column  │
│o │ A QUIET SESSION                              <h2>        │o │ right of│
│o │ $ token-oracle forecast   <- PROPHECY BLOCK: types       │o │ the     │
│o │   45,200/220,000, 21% [green]  itself into view, ends    │o │ ribbon; │
│o │   ░░▒░░░▒▒░▒░░▒▒▒░░▒▓▒░░░░ █   with blinking cursor      │o │ mobile: │
│o │ - - - - - - - - - - perforation - - - - - - - - - -      │o │ inline  │
│o │ A HEAVY SESSION                              <h2>        │o │ under   │
│o │ $ token-oracle forecast   <- second prophecy block:      │o │ their   │
│o │   178,400/220,000, 108% [orange] — status lines orange   │o │ section)│
│o │ - - - - - - - - - - perforation - - - - - - - - - -      │o │         │
│o │ HOW IT WORKS  man-page excerpt: READ/MEASURE/FORECAST    │o │ note 5  │
│o │               + COLORS threshold legend                  │o │         │
│o │ - - - - - - - - - - perforation - - - - - - - - - -      │o │         │
│o │ SUBCOMMANDS   $ token-oracle --help (six one-liners)     │o │ note 6  │
│o │ WHAT THE ORACLE IS FOR  (four pillars, ledger-style)     │o │         │
│o │ - - - - - - - - - - perforation - - - - - - - - - -      │o │         │
│o │ ---------------- end of session ----------------         │o │         │
│o │ badges · links (View on GitHub / PyPI / agentic-sage)    │o │         │
│o │ MIT licensed. Built by Mateusz Muślewski.    <footer>    │o │         │
└──┴──────────────────────────────────────────────────────────┴──┴─────────┘
 ^ feed strip: --feed-gray,     ^ paper ribbon, 72ch max          ^ notes
   punched holes every 2rem       (transcripts scroll-x if needed)  column
```

Geometry recipe: the ribbon is a CSS grid —
`grid-template-columns: 2.5rem minmax(0, 72ch) 2.5rem;` with
`width: min(100%, calc(72ch + 5rem)); margin-inline: auto;`. The two feed
strips span all rows (`grid-row: 1 / -1`), background `--feed-gray`, holes via
`background-image: radial-gradient(circle, var(--hole-shadow) 4px, transparent 5px); background-size: 100% 2rem; background-position: center;`.
Perforations are `<hr class="perf">` styled
`border: 0; border-top: 2px dashed var(--hole-shadow); margin: 2.5rem 0;`.
Below 420px viewport width the feed strips narrow to `1.25rem`.

### Signature element: the prophecy block

The two `token-oracle forecast` outputs (`pre.prophecy`, one calm, one drama)
type themselves character-by-character when scrolled into view.

- **Geometry**: each prophecy block is a `<pre class="transcript prophecy">`
  inside its section, 72ch ribbon width, `overflow-x: auto`. Its final line
  ends with a block cursor `<span class="cursor" aria-hidden="true">█</span>`
  present in the static markup.
- **Behavior**: an `IntersectionObserver` (threshold 0.35) fires once per
  block. On first intersection, JS freezes the block's final height
  (`min-height` = measured `offsetHeight`, so typing causes no layout shift),
  inserts a visually-hidden untouched clone for screen readers, sets
  `aria-hidden="true"` on the animated block, empties every text node (a
  `TreeWalker` collects them in document order — this preserves the colored
  sparkline `<span>`s), then restores characters on a 16ms interval at a rate
  computed so the whole block completes in ~2000ms. The cursor's `█` is the
  last text node, so it appears last, then blinks via CSS.
- **States**: untyped (full static content — visible until JS intersects it),
  typing (characters appearing), typed (class `typed` added; cursor blinking).
  Each block types once; the observer unobserves it.
- **Sparkline**: each prophecy block contains a 24-character ASCII sparkline
  of the last 24h of burn, one block character per hour. Character weight and
  color rise together and both encode the same intensity bucket:
  `░` = light burn = `--sem-green`, `▒` = moderate = `--sem-lime`,
  `▓` = heavy = `--sem-orange`, `█` = peak = `--sem-red`. Exact strings and
  span markup are given in Steps 7–8. The sparkline is wrapped in a span with
  `role="img"` and a plain-language `aria-label`.
- **Reduced motion**: if `prefers-reduced-motion: reduce` matches, `main.js`
  returns immediately — output renders instantly (the static HTML is already
  complete) and the cursor does not blink (its blink animation lives inside a
  `prefers-reduced-motion: no-preference` media query). No JS fallback is
  needed because the page is complete without JavaScript.

### Motion spec

Only three things move on the entire page. This restraint is the design.

| What | Trigger | Duration / easing | Reduced-motion behavior |
|------|---------|-------------------|-------------------------|
| Prophecy typing | block enters viewport (IntersectionObserver, once) | ~2000ms total, linear per-character on a 16ms tick | Does not run; content is static |
| Cursor blink | always, after markup renders (typed content reveals it) | `1s steps(1) infinite`, 50% opacity keyframe | Cursor visible, does not blink |
| Margin-note reveal | `:hover` / `:focus-within` on the note's section | `opacity 200ms ease-out`, 0.72 → 1.0 | Notes always at opacity 1, no transition |

Nothing else animates: no smooth scrolling, no parallax, no hover growth.
No canvas or WebGL (the brief's devicePixelRatio-2 cap is trivially met).

## Copy (final, verbatim)

You write ZERO copy. Every visible string on the page is below, in display
order. Copy blocks byte-exact — straight apostrophes (`'`), the `·`
separators, the em dashes, and the `–` en dashes in ranges are intentional.
When a block goes inside `<pre>`, escape literal `<` as `&lt;`.

**M — document metadata**

```
title:            Token Oracle — Know when you'll hit the limit.
meta description: Token Oracle is an offline CLI that forecasts when you will hit your AI-provider token cap. No API calls — nothing leaves your machine.
```

**C1 — printout header + hero** (masthead `=` runs are decorative,
`aria-hidden`; the tagline line is the page's only `<h1>`)

```
================= TOKEN ORACLE · SESSION PRINTOUT =================
DATE 2026-07-02 · TIME 09:14 UTC · HOST devbox · PAGE 1 OF 1

Know when you'll hit the limit.
Usage monitors tell you what you spent. Token Oracle tells you what happens next.
```

**C2 — install section** (h2: `Install`)

```
$ pipx install token-oracle
  installed package token-oracle
  these apps are now globally available
    - token-oracle
done!

# alternatives: pip install token-oracle · uvx token-oracle
```

**C3 — calm prophecy** (h2: `A quiet session`)

```
$ token-oracle forecast
  window     5h · resets in 3h42m
  used       45,200 / 220,000 tokens
  projected  21% of cap at window end   [green]

  burn, last 24h · one block per hour
  ░░▒░░░▒▒░▒░░▒▒▒░░▒▓▒░░░░ █
```

**C4 — drama prophecy** (h2: `A heavy session`)

```
$ token-oracle forecast    # later, same window
  window     5h · resets in 2h48m
  used       178,400 / 220,000 tokens
  projected  108% of cap at window end   [orange]
  at this rate, cap in 1h12m

  burn, last 24h · one block per hour
  ░▒▒▓▒▒▓▓█▓▒▓██▓▓█▓▓██▓▓█ █
```

**C5 — how it works, as a man-page excerpt** (h2: `How it works`)

```
TOKEN-ORACLE(1)              User Commands              TOKEN-ORACLE(1)

NAME
    token-oracle — an offline CLI that forecasts when you will hit
    your AI-provider token cap

HOW IT WORKS
    READ       token-oracle reads your provider's local usage logs.
               Claude Code is built in; adapters add more. No API
               calls — nothing leaves your machine.
    MEASURE    it computes your observed burn rate over a sliding
               window, weighted by your own weekly usage profile.
    FORECAST   it projects usage to window end and tells you what's
               left before the cap: a percentage, an ETA, and a color.

COLORS
    green < 85%  ·  lime 85–100%  ·  orange 100–120%  ·  red ≥ 120%
    (projected usage at window end, as % of cap)
```

**C6 — subcommands** (h2: `Subcommands`)

```
$ token-oracle --help
usage: token-oracle {forecast,snapshot,statusline,tmux,doctor,dash}
                    [--config FILE]

  forecast     live forecast — time left before your cap (--json)
  dash         full-screen terminal dashboard
  statusline   one-line ANSI fragment for any status bar
  tmux         status-right fragment for tmux
  snapshot     writes forecast.json for other tools to read
  doctor       checks configuration and data sources
```

**C7 — pillars** (h2: `What the oracle is for`; same section as C6, after it)

```
CLARITY      understand your true token usage
FORESIGHT    plan ahead with accuracy
CONFIDENCE   avoid surprises, stay in control
INTENTION    spend tokens with purpose
```

**C8 — footer** (the three arrows introduce real `<a>` links; dashes in the
`end of session` line are decorative, `aria-hidden`)

```
------------------------- end of session -------------------------

Provider-agnostic · Zero dependencies · CLI first · Extensible

View on GitHub → https://github.com/muslewski/token-oracle
PyPI → https://pypi.org/project/token-oracle/
Companion project: agentic-sage → https://github.com/muslewski/agentic-sage

MIT licensed. Built by Mateusz Muślewski.
```

Link targets: "View on GitHub" links to
`https://github.com/muslewski/token-oracle`; "PyPI" links to
`https://pypi.org/project/token-oracle/`; "agentic-sage" links to
`https://github.com/muslewski/agentic-sage`. Anchor text is the words, the
printed URL after each arrow is plain text.

**N1–N6 — margin annotations** (Newsreader italic; one per section, in order:
header, install, calm, drama, man page, subcommands+pillars)

```
N1: A pitch printed the way the product speaks: as terminal output. token-oracle is an offline CLI — no dashboard site, no login, no cloud.
N2: pipx keeps it isolated; pip and uv work too. Python, zero runtime dependencies, MIT licensed, on PyPI. Output shown on this page is representative, not a byte-exact capture.
N3: A quiet afternoon. Projected 21% of cap at window end — green, keep working.
N4: It's a forecast, not a bill. Orange means this pace crosses the cap before the window resets: 1h12m of runway. Slow down, or plan the break.
N5: Prediction-first: usage monitors report the past. The oracle's headline act is the future.
N6: One forecast, six outlets — your terminal, your status bar, tmux, or a JSON file other tools can read.
```

**A1–A2 — sparkline aria-labels**

```
A1: Burn sparkline, last 24 hours: mostly light burn with one heavier hour.
A2: Burn sparkline, last 24 hours: burn rising through the day to repeated peak hours.
```

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Confirm brief exists | `test -f explore/BRIEF.md && echo ok` | `ok` |
| Serve the page | `python3 -m http.server 8041 --directory explore/01-teletype-ledger` | `Serving HTTP on ... port 8041` |
| Smoke test | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8041/` | `200` |
| JS syntax check | `node --check explore/01-teletype-ledger/main.js` | exit 0, no output |
| JS budget | `wc -l < explore/01-teletype-ledger/main.js` | number ≤ 150 |
| Scope check | `git status --porcelain` | only in-scope paths (ignore pre-existing untracked entries you did not create) |

No npm install, no build step, no Python tooling. If port 8041 is busy, use
8042 (adjust the curl URL accordingly); that substitution is fine everywhere
below.

## Suggested executor toolkit

If a frontend-design or similar skill is available it may inform craft, but
the Design specification and Copy sections of this plan are authoritative —
no tool or skill may change the tokens, the copy, or the scope.

## Scope

**In scope** (the only files you should create/modify):
- `explore/01-teletype-ledger/index.html` (create)
- `explore/01-teletype-ledger/styles.css` (create)
- `explore/01-teletype-ledger/main.js` (create)
- `explore/01-teletype-ledger/README.md` (create)
- `explore/01-teletype-ledger/screenshot.png` (create only if browser tooling is available)
- `explore/README.md` (flip ONE gallery row: `planned` → `built`)
- `plans/README.md` (this plan's status row only)

**Out of scope** (do NOT touch, even though they look related):
- `explore/BRIEF.md` — the shared brief is operator-approved; wording changes
  are a report, not an edit.
- Every other `explore/` folder (`02-*` through `05-*`) — they belong to
  plans 026–029.
- `token_oracle/`, `tests/`, `assets/`, the root `README.md`, and every other
  repo file — this plan ships a self-contained prototype only.

## Git workflow

- Branch: `advisor/025-explore-teletype-ledger` (from `main`)
- Conventional commits, one per logical unit, e.g.:
  - `feat(explore): scaffold teletype ledger exploration`
  - `feat(explore): teletype ledger page sections and copy`
  - `feat(explore): prophecy typing effect and motion gates`
  - `docs(explore): teletype ledger readme; mark gallery row built`
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Verify prerequisites (plan 024 ran; workspace is clean)

Run, from the repo root:

1. `test -f explore/BRIEF.md && echo ok` → `ok`. If this fails, STOP: plan
   024 has not run; report "run plans/024-explore-scaffold-brief.md first".
2. `grep -c '| plans/025 | planned |' explore/README.md` → `1`. If `0`, the
   gallery row is missing or already flipped — STOP.
3. `test ! -e explore/01-teletype-ledger && echo clear` → `clear`. If the
   folder exists, STOP (another session may have started it).
4. Run the drift check from the header blockquote and compare as described.

**Verify**: all four checks produce the expected output.

### Step 2: Create the branch

`git checkout -b advisor/025-explore-teletype-ledger`

**Verify**: `git branch --show-current` → `advisor/025-explore-teletype-ledger`

### Step 3: Scaffold the folder and the HTML skeleton

Create `explore/01-teletype-ledger/` containing empty `styles.css` and
`main.js`, and `index.html` with this exact skeleton (content filled in later
steps):

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Token Oracle — Know when you'll hit the limit.</title>
  <meta name="description" content="Token Oracle is an offline CLI that forecasts when you will hit your AI-provider token cap. No API calls — nothing leaves your machine.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Newsreader:ital,wght@1,400&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="ribbon">
    <div class="feed feed-left" aria-hidden="true"></div>
    <header class="sheet"></header>
    <main></main>
    <footer class="sheet"></footer>
    <div class="feed feed-right" aria-hidden="true"></div>
  </div>
  <script src="main.js" defer></script>
</body>
</html>
```

Inside `<main>` (filled by Steps 5–10) the structure will be five
`<section class="sheet" id="...">` elements with ids `install`, `calm`,
`drama`, `how`, `commands` — the header, each section, and the footer are
separated by `<hr class="perf">` placed between them inside the middle grid
column. (Grid note: header, main, footer, and the hr elements all take
`grid-column: 2`; the feeds take columns 1 and 3 with `grid-row: 1 / -1`.
Simplest implementation: put the `<hr class="perf">` elements inside `<main>`
between sections, plus one at the top and bottom of `<main>`.)

**Verify**: `grep -c 'lang="en"' explore/01-teletype-ledger/index.html` → `1`
and `test -f explore/01-teletype-ledger/styles.css && test -f explore/01-teletype-ledger/main.js && echo ok` → `ok`

### Step 4: Design tokens and base styles

Write `styles.css` starting with the tokens (exact hex values, exact names):

```css
:root {
  --paper: #FAFAF7;
  --ink: #1C1B18;
  --feed-gray: #DDDAD2;
  --hole-shadow: #C9C6BD;
  --sem-green: #1F7A33;
  --sem-lime: #93A11A;
  --sem-orange: #C2681C;
  --sem-red: #BF3B2F;
  --font-mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  --font-note: "Newsreader", Georgia, serif;
}
```

Then, using the geometry recipe from the Design specification: body on
`--paper` in `--ink`, `font-family: var(--font-mono)`, `line-height: 1.55`;
the `.ribbon` grid (`2.5rem minmax(0, 72ch) 2.5rem`, centered,
`width: min(100%, calc(72ch + 5rem))`); `.feed` strips with the punched-hole
radial-gradient recipe; `hr.perf` dashed perforations; `pre.transcript`
(`font-size: 0.95rem; white-space: pre; overflow-x: auto;`); `h1` at 1.5rem
weight 600; `h2` uppercase, 0.8rem, weight 600, `letter-spacing: 0.08em`;
semaphore classes `.c-green/.c-lime/.c-orange/.c-red` setting `color` to the
matching token; `.status { font-weight: 600; }`; a visible focus style
`:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }`;
and the screen-reader utility:

```css
.visually-hidden {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip-path: inset(50%); white-space: nowrap; border: 0;
}
```

**Verify**: `grep -cE '#(FAFAF7|1C1B18|DDDAD2|C9C6BD|1F7A33|93A11A|C2681C|BF3B2F)' explore/01-teletype-ledger/styles.css` → `8`
and `grep -c 'focus-visible' explore/01-teletype-ledger/styles.css` → ≥ 1

### Step 5: Header + hero (copy C1, note N1)

Fill `<header class="sheet">` with copy block C1:

- Masthead line: `<p class="masthead"><span aria-hidden="true">=================</span> TOKEN ORACLE · SESSION PRINTOUT <span aria-hidden="true">=================</span></p>`
- Meta line: `<p class="meta">DATE 2026-07-02 · TIME 09:14 UTC · HOST devbox · PAGE 1 OF 1</p>`
- `<h1>Know when you'll hit the limit.</h1>` — the tagline must stay on one
  source line, byte-exact, straight apostrophe.
- `<p class="positioning">Usage monitors tell you what you spent. Token Oracle tells you what happens next.</p>`
- `<p class="note">` with N1.

**Verify**: `grep -c "Know when you'll hit the limit." explore/01-teletype-ledger/index.html` → `2` (title + h1)

### Step 6: Install section (copy C2, note N2)

`<section class="sheet" id="install">` with `<h2>Install</h2>`, a
`<pre class="transcript"><code>` holding C2 exactly, and N2 as its
`<p class="note">`. Style the leading `$` prompt with
`<span class="prompt">$</span>` (weight 600 via CSS).

**Verify**: `grep -c 'install token-oracle' explore/01-teletype-ledger/index.html` → `2` (the `pipx install` transcript line + the alternatives comment line — the alternatives line says `pip install`, not `pipx install`, so grep for the shared substring)

### Step 7: Calm prophecy block (copy C3, note N3, aria-label A1)

`<section class="sheet" id="calm">` with `<h2>A quiet session</h2>` and a
`<pre class="transcript prophecy"><code>` holding C3 with this markup:

- Tint only the bracketed status tag: `<span class="c-green status">[green]</span>`.
  All other calm text is ink.
- The sparkline line is wrapped:
  `<span class="spark" role="img" aria-label="Burn sparkline, last 24 hours: mostly light burn with one heavier hour.">…</span>`
  where `…` is exactly these spans (run-length encoded, 24 characters total):

```html
<span class="c-green">░░</span><span class="c-lime">▒</span><span class="c-green">░░░</span><span class="c-lime">▒▒</span><span class="c-green">░</span><span class="c-lime">▒</span><span class="c-green">░░</span><span class="c-lime">▒▒▒</span><span class="c-green">░░</span><span class="c-lime">▒</span><span class="c-orange">▓</span><span class="c-lime">▒</span><span class="c-green">░░░░</span>
```

- After the sparkline, a space and the cursor:
  `<span class="cursor" aria-hidden="true">█</span>` (last content in the pre).
- N3 as the section's `<p class="note">`.

**Verify**: `grep -c '45,200 / 220,000' explore/01-teletype-ledger/index.html` → `1`

### Step 8: Drama prophecy block (copy C4, note N4, aria-label A2)

`<section class="sheet" id="drama">` with `<h2>A heavy session</h2>` and a
second `<pre class="transcript prophecy"><code>` holding C4:

- The two status-bearing lines render in orange at weight 600 — wrap each
  whole line: `<span class="c-orange status">projected  108% of cap at window end   [orange]</span>` and
  `<span class="c-orange status">at this rate, cap in 1h12m</span>`. The rest
  of the transcript (window, used, caption) stays ink: color only where it
  encodes urgency.
- Sparkline wrapped with `role="img"` and aria-label A2; exact spans
  (24 characters total):

```html
<span class="c-green">░</span><span class="c-lime">▒▒</span><span class="c-orange">▓</span><span class="c-lime">▒▒</span><span class="c-orange">▓▓</span><span class="c-red">█</span><span class="c-orange">▓</span><span class="c-lime">▒</span><span class="c-orange">▓</span><span class="c-red">██</span><span class="c-orange">▓▓</span><span class="c-red">█</span><span class="c-orange">▓▓</span><span class="c-red">██</span><span class="c-orange">▓▓</span><span class="c-red">█</span>
```

- Cursor span at the end, N4 as the note.

**Verify**: `grep -c '178,400 / 220,000' explore/01-teletype-ledger/index.html` → `1`
and `grep -c '1h12m' explore/01-teletype-ledger/index.html` → ≥ 1

### Step 9: Man-page section (copy C5, note N5)

`<section class="sheet" id="how">` with `<h2>How it works</h2>` and a
`<pre class="transcript"><code>` holding C5. Escape the literal `<` in
`green < 85%` as `green &lt; 85%`. In the COLORS line, tint each color word
with its own class at weight 600 (`<span class="c-green status">green</span>`
etc.) — the ink threshold numbers beside each word carry the information, so
the below-4.5:1 lime/orange tints follow the glyph-only rule. N5 as the note.

**Verify**: `grep -c 'MEASURE' explore/01-teletype-ledger/index.html` → `1`

### Step 10: Subcommands + pillars (copy C6, C7, note N6)

`<section class="sheet" id="commands">` with `<h2>Subcommands</h2>`, a
`<pre class="transcript"><code>` holding C6, then
`<h2>What the oracle is for</h2>` and a `<pre class="transcript"><code>`
holding C7 (pillar names at weight 600 via
`<span class="status">CLARITY</span>` etc.). N6 as the section's note.

**Verify**: `grep -c 'statusline' explore/01-teletype-ledger/index.html` → ≥ 1
and `grep -c 'FORESIGHT' explore/01-teletype-ledger/index.html` → `1`

### Step 11: Footer (copy C8)

Fill `<footer class="sheet">` with C8: the `end of session` line (dash runs
in `aria-hidden` spans like the masthead), the proof-badge line as plain text,
the three link lines as paragraphs each containing a real `<a>` (anchor text
and hrefs as specified under C8), and the MIT line. No note in the footer.

**Verify**: `grep -c 'View on GitHub' explore/01-teletype-ledger/index.html` → `1`
and `grep -c 'Muślewski' explore/01-teletype-ledger/index.html` → `1`

### Step 12: Margin-annotation layout

Style `.note` per the design spec:

```css
.sheet { position: relative; }
.note {
  font-family: var(--font-note);
  font-style: italic;
  font-size: 0.85rem;
  line-height: 1.5;
  opacity: 0.72; /* composites to ≈ 6.6:1 on paper — above the 4.5:1 floor */
}
.sheet:hover .note, .sheet:focus-within .note { opacity: 1; }
@media (min-width: 1200px) {
  .note { position: absolute; left: calc(100% + 1.5rem); top: 0; width: 15rem; }
}
```

(The breakpoint is 1200px, not lower: the ribbon is ~771px centered, and the
absolutely-positioned note column adds ~264px to its right — below ~1200px
viewport width that column would overflow and cause body-level horizontal
scroll.)

Below 1200px the notes flow inline beneath their section content (the default
static position). Confirm all six notes N1–N6 are present.

**Verify**: `grep -c 'class="note"' explore/01-teletype-ledger/index.html` → `6`

### Step 13: Signature element — write `main.js`

Write exactly this file (≈72 lines, well under the 150-line cap; adjust only
if a syntax error forces it):

```js
/* Teletype Ledger — prophecy typing effect.
   Motion policy: if the user prefers reduced motion, this file does
   nothing; the page is fully readable and complete without JavaScript. */
(function () {
  "use strict";

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  var DURATION_MS = 2000; /* total typing time per prophecy block */
  var TICK_MS = 16;

  var blocks = document.querySelectorAll(".prophecy");
  if (!blocks.length || !("IntersectionObserver" in window)) return;

  function textNodes(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    var nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    return nodes;
  }

  function prepare(block) {
    /* Screen readers get an untouched, visually hidden clone. */
    var clone = block.cloneNode(true);
    clone.classList.add("visually-hidden");
    clone.classList.remove("prophecy");
    block.parentNode.insertBefore(clone, block);
    block.setAttribute("aria-hidden", "true");

    /* Freeze final height so typing causes no layout shift. */
    block.style.minHeight = block.offsetHeight + "px";

    var nodes = textNodes(block);
    var total = 0;
    var originals = nodes.map(function (n) {
      total += n.data.length;
      var text = n.data;
      n.data = "";
      return text;
    });
    return { block: block, nodes: nodes, originals: originals, total: total };
  }

  function type(state) {
    var perTick = Math.max(1, Math.ceil(state.total / (DURATION_MS / TICK_MS)));
    var i = 0, offset = 0;
    var timer = setInterval(function () {
      var budget = perTick;
      while (budget > 0 && i < state.nodes.length) {
        var take = Math.min(state.originals[i].length - offset, budget);
        offset += take;
        budget -= take;
        state.nodes[i].data = state.originals[i].slice(0, offset);
        if (offset === state.originals[i].length) { i += 1; offset = 0; }
      }
      if (i >= state.nodes.length) {
        clearInterval(timer);
        state.block.classList.add("typed");
      }
    }, TICK_MS);
  }

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      observer.unobserve(entry.target);
      type(prepare(entry.target));
    });
  }, { threshold: 0.35 });

  blocks.forEach(function (b) { observer.observe(b); });
})();
```

Known, accepted quirk: a block already fully in the viewport at load may show
its content for a frame before typing begins. That is fine for a prototype.
Escape hatch (allowed, NOT a STOP): if the typing effect proves fiddly after
two fix attempts, delete the observer/typing code and ship instant render
with the blinking cursor only, and note that in the exploration README.

**Verify**: `node --check explore/01-teletype-ledger/main.js` → exit 0, and
`wc -l < explore/01-teletype-ledger/main.js` → ≤ 150

### Step 14: Motion CSS with reduced-motion gates

Add to `styles.css`:

```css
.cursor { color: var(--ink); }
@media (prefers-reduced-motion: no-preference) {
  .cursor { animation: blink 1s steps(1) infinite; }
  .note { transition: opacity 200ms ease-out; }
}
@keyframes blink { 50% { opacity: 0; } }
@media (prefers-reduced-motion: reduce) {
  .note { opacity: 1; }
}
```

Every animation on the page is now gated: typing (JS early-return in Step
13), cursor blink and note transition (inside `no-preference`), and notes
rest at full opacity under `reduce`.

**Verify**: `grep -c 'prefers-reduced-motion' explore/01-teletype-ledger/styles.css` → `2`
and `grep -c 'prefers-reduced-motion' explore/01-teletype-ledger/main.js` → `1`

### Step 15: Accessibility pass

Check each item; fix in place if one fails:

1. Exactly one `h1`: `grep -c '<h1' explore/01-teletype-ledger/index.html` → `1`
2. Landmarks present (run from `explore/01-teletype-ledger/`):
   `grep -c '<header' index.html` → `1`, `grep -c '<main' index.html` → `1`,
   `grep -c '<footer' index.html` → `1`
3. `lang="en"` on `<html>` (verified in Step 3).
4. `:focus-visible` styles exist (Step 4) and every `<a>` in the footer shows
   the outline when tabbed to.
5. Sparklines carry `role="img"`: `grep -c 'role="img"' index.html` → `2`
6. Contrast: body text is `--ink` on `--paper` (≈ 15.9:1); notes rest at
   opacity 0.72 (≈ 6.6:1); lime/orange appear only on data glyphs whose
   information is duplicated in adjacent ink text (Steps 7–9). Do not use
   lime or orange for body text anywhere.
7. External hosts allowlist (no CDNs, no analytics, no trackers):
   `grep -oE 'https?://[^" ]+' index.html | cut -d/ -f3 | sort -u` →
   exactly four lines: `fonts.googleapis.com`, `fonts.gstatic.com`,
   `github.com`, `pypi.org`
8. No images on the page (the risk is the design): `grep -c '<img' index.html` → `0`

**Verify**: all eight checks pass.

### Step 16: Responsive pass

Add media queries so the page is usable at 360px wide:

- `@media (max-width: 420px) { .feed { ... } }` — narrow the feed strips to
  `1.25rem` and change the ribbon grid columns to
  `1.25rem minmax(0, 1fr) 1.25rem`.
- Transcripts already scroll horizontally inside the ribbon
  (`overflow-x: auto` from Step 4) — the page body itself must never scroll
  horizontally at 360px.
- Notes are already inline below 1200px (Step 12).

If browser tooling is available, load the page at 360px width and confirm no
body-level horizontal scrollbar. If not available, rely on the CSS rules
above and note it in the exploration README (Step 18).

**Verify**: `grep -c '@media' explore/01-teletype-ledger/styles.css` → ≥ 3

### Step 17: Smoke test

From the repo root:

1. Start the server in the background and record its PID:
   `python3 -m http.server 8041 --directory explore/01-teletype-ledger & SERVER_PID=$!`
2. `curl -s -o /dev/null -w "%{http_code}" http://localhost:8041/` → `200`
3. `curl -s http://localhost:8041/ | grep -c "Know when you'll hit the limit."` → `2`
4. `node --check explore/01-teletype-ledger/main.js` → exit 0
5. Stop the server: `kill "$SERVER_PID"` (job specs like `kill %1` do not
   survive across separate shell invocations — always use the recorded PID).

**Verify**: steps 2–4 above produce exactly the expected outputs.

### Step 18: Write the exploration README

Create `explore/01-teletype-ledger/README.md` with exactly this content,
choosing the correct bracketed screenshot phrase and deleting the other; if
you used the Step-13 escape hatch, append the sentence noting it:

```markdown
# 01 — Teletype Ledger

Zero-dependency landing-page exploration for the Token Oracle marketing
site. See [`../BRIEF.md`](../BRIEF.md) for the shared brief.

## Run

No build step. Open `index.html` directly in a browser, or serve it:

    python3 -m http.server 8041 --directory .

then visit http://localhost:8041/.

## Brand stance: contrast

The artifact is the brand. token-oracle speaks in terminal output, so the
page is one continuous-form teletype printout of an oracle session —
tractor-feed hole strips, perforation form feeds, an annotated transcript.
No mascot, no watercolor sky: the argument is that a printed forecast is
more credible to terminal-dwelling developers than any illustration.

Aesthetic risk taken: no imagery at all, and color used only as data — the
four semaphore colors appear exclusively where they encode urgency; every
other pixel is ink on paper.

## Palette

paper `#FAFAF7` · ink `#1C1B18` · feed-gray `#DDDAD2` · hole-shadow
`#C9C6BD` · semaphore green `#1F7A33` / lime `#93A11A` / orange `#C2681C` /
red `#BF3B2F` (data only).

## Type

IBM Plex Mono 400/600 for everything (hierarchy by size, weight, spacing);
Newsreader italic 400 for the pencil-note margin annotations. Fallbacks:
ui-monospace/SFMono-Regular/Menlo/monospace and Georgia/serif.

## Signature element

The "prophecy block": the two `token-oracle forecast` outputs type
themselves character-by-character when scrolled into view (about 2 s), then
a block cursor blinks. With `prefers-reduced-motion: reduce` the output
renders instantly and the cursor does not blink. Each forecast carries an
ASCII sparkline of the last 24 h of burn (░▒▓█, one block per hour, weight
and color rising together with that hour's intensity).

## Screenshot

`screenshot.png` — [captured at 1280px wide | not captured: browser tooling
unavailable in the build environment; capture manually when comparing
explorations].
```

If browser tooling IS available, also capture `screenshot.png` (viewport
around 1280px wide, full page or at least the first two sections). If it is
not available, that is fine — keep the "not captured" phrase and continue;
this is NOT a STOP condition.

**Verify**: `test -f explore/01-teletype-ledger/README.md && grep -c 'contrast' explore/01-teletype-ledger/README.md` → ≥ 1

### Step 19: Flip the gallery row

In `explore/README.md`, change the exploration-01 row's Status cell from
`planned` to `built`. The row currently reads:

```
| 01 | Teletype Ledger | contrast | zero-dep HTML/CSS/JS | open `index.html` | plans/025 | planned |
```

and must become:

```
| 01 | Teletype Ledger | contrast | zero-dep HTML/CSS/JS | open `index.html` | plans/025 | built |
```

Change nothing else in that file.

**Verify**: `grep -c '| plans/025 | built |' explore/README.md` → `1`
and `grep -c '| plans/025 | planned |' explore/README.md` → `0`

### Step 20: Commit and update the plan index

1. Commit the work on the branch using the conventional-commit messages from
   "Git workflow" (one commit at the end is acceptable if you did not commit
   per step; use `feat(explore): add teletype ledger exploration (plan 025)`).
2. In `plans/README.md`: if a `| 025 |` row exists, set its Status cell to
   `DONE`; if it does not exist, add this row directly after the `| 024 |`
   row:

```markdown
| 025 | Exploration 01: Teletype Ledger (`explore/01-teletype-ledger/`) | P2 | M | 024 | DONE |
```

3. Commit that index change too. Do NOT push or open a PR unless the
   operator instructed it.

**Verify**: `git status --porcelain -- explore/01-teletype-ledger explore/README.md plans/README.md` → empty
(everything in scope committed — the repo may carry pre-existing untracked
entries elsewhere, e.g. an untracked `plans/` or `.claude/` directory on a
fresh clone; entries you did not create are ignorable and must NOT be added),
and `grep -c '| 025 |' plans/README.md` → `1`

## Test plan

No unit-test framework applies — this is a static prototype in a folder the
product code never imports. The verification gates in each step ARE the test
suite; the aggregate checks are:

- HTTP smoke test: serve + curl → `200` (Step 17).
- Content checks: tagline, both scenario numbers, six subcommand names,
  pillars, footer — all via the greps in Steps 5–11.
- Behavior checks: `node --check` for JS syntax; reduced-motion and
  focus-visible greps (Steps 13–15).
- If browser tooling is available, additionally do one manual pass: scroll to
  each prophecy block and watch it type; toggle reduced motion in devtools
  and confirm instant render with a non-blinking cursor; tab to the footer
  links and confirm visible focus outlines; view at 360px width.

## Done criteria

Machine-checkable. ALL must hold (run from the repo root):

- [ ] `test -f explore/01-teletype-ledger/index.html && test -f explore/01-teletype-ledger/styles.css && test -f explore/01-teletype-ledger/main.js && test -f explore/01-teletype-ledger/README.md` → exit 0
- [ ] With `python3 -m http.server 8041 --directory explore/01-teletype-ledger` running: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8041/` → `200`
- [ ] `grep -c "Know when you'll hit the limit." explore/01-teletype-ledger/index.html` → ≥ 1 (plain HTML page — grep the source file directly; no JSX escaping applies to this exploration)
- [ ] `grep -c "prefers-reduced-motion" explore/01-teletype-ledger/styles.css` → ≥ 2
- [ ] `grep -c "prefers-reduced-motion" explore/01-teletype-ledger/main.js` → ≥ 1
- [ ] `grep -c "focus-visible" explore/01-teletype-ledger/styles.css` → ≥ 1
- [ ] `node --check explore/01-teletype-ledger/main.js` → exit 0
- [ ] `wc -l < explore/01-teletype-ledger/main.js` → ≤ 150
- [ ] `grep -c '<h1' explore/01-teletype-ledger/index.html` → `1`
- [ ] `grep -oE 'https?://[^" ]+' explore/01-teletype-ledger/index.html | cut -d/ -f3 | sort -u` → exactly `fonts.googleapis.com`, `fonts.gstatic.com`, `github.com`, `pypi.org`
- [ ] `grep -c '| plans/025 | built |' explore/README.md` → `1`
- [ ] `git status --porcelain` shows no modified/created paths outside `explore/01-teletype-ledger/`, `explore/README.md`, `plans/README.md`
- [ ] `plans/README.md` status row for 025 says `DONE`

## STOP conditions

Stop and report back (do not improvise) if:

- `explore/BRIEF.md` does not exist — plan 024 has not run; this plan's
  dependency is unmet. Report: "run plans/024-explore-scaffold-brief.md
  first".
- `explore/01-teletype-ledger/` already exists with any file in it — another
  session may have started this exploration; reconcile with the operator
  instead of overwriting.
- The gallery row for exploration 01 in `explore/README.md` is missing, or
  its Status is not `planned` (drift check fails — the gallery no longer
  matches the excerpt in "Current state").
- The canonical copy in `explore/BRIEF.md` differs from the copy inlined in
  this plan's "Copy" section (tagline, positioning line, three steps,
  pillars, proof badges, footer, or either scenario's numbers) — the brief
  changed after this plan was written; the operator must re-approve the deck.
- The smoke test cannot produce `200`: `python3 -m http.server` fails to bind
  on both 8041 and 8042, or curl never returns 200 after two fix attempts.
- `node --check` reports a syntax error you cannot fix in two attempts.
- Completing any step appears to require touching an out-of-scope file
  (most likely `explore/BRIEF.md` or another exploration's folder).
- You are tempted to change canonical copy, add social proof, or invent
  sample numbers — wording and honesty rules are operator-approved as
  written; changes are a report, not an edit.

NOT stop conditions (explicit, per the design direction): browser/screenshot
tooling being unavailable (note it in the exploration README and continue);
the typing effect proving fiddly (use the Step-13 escape hatch: instant
render + blinking cursor, noted in the exploration README). There are no
npm-registry concerns for this plan — it installs nothing.

## Maintenance notes

- The copy deck now lives in three places: root `README.md` (product facts),
  `explore/BRIEF.md` (canonical deck), and this page. If install commands,
  subcommands, or thresholds change, the page must be re-synced with the
  brief — copies drift.
- If the operator abandons this exploration, flip its gallery row to
  `archived`; do not delete the folder — `explore/` is the design record.
- If `screenshot.png` was not captured, capture it before the side-by-side
  comparison round; the gallery comparison assumes screenshots exist.
- If the Step-13 escape hatch was used (instant render, no typing), the
  signature element is diminished — a reviewer comparing explorations should
  weigh that, and re-attempting the typing effect is a reasonable follow-up.
- Reviewer scrutiny points: byte-exactness of the tagline and canonical copy;
  the color-only-as-data rule (no decorative color leaked in); the
  reduced-motion behavior; that no file outside the scope list changed.
- The winning direction gets re-implemented properly in the separate
  marketing-site repository; this folder stays behind as the design archive.
