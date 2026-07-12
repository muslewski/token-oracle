# Plan 045 — embed the animated dashboard demo in the README

**Status:** TODO
**Priority:** P1 (Phase 1 "make it visible" — the single highest-impact lever)
**Effort:** S
**Risk:** low (README markup + committing two prepared asset files)
**Written against commit:** `7264a71`
**Files in scope:** `README.md`, `assets/dash-demo.gif`, `assets/dash-demo.tape`
**Do NOT touch:** any Python, any test, `SETUP.md`, or the existing banner
assets (`assets/oracle-banner.*`).

---

## Why this matters

The audit's biggest single visibility lever: the README shows a static brand
banner but **no demo of the tool actually running**. A visitor cannot see what
`oracle dash` looks like before installing. This plan embeds a short animated
GIF of the live dashboard (real, browser-verified numbers for Claude Code +
Grok) high in the README.

## Precondition (already satisfied by the advisor — verify, do not regenerate)

The advisor generated the demo on a machine with real usage data and a real
terminal (a headless executor cannot capture this) and seeded two files into
your worktree:

- `assets/dash-demo.gif` — the animated demo (~64 KB, 760×560).
- `assets/dash-demo.tape` — the `vhs` script that regenerates it.

**First action:** confirm both exist in your worktree:

```bash
test -f assets/dash-demo.gif && test -f assets/dash-demo.tape && echo "assets present" || echo "MISSING"
```

If either is MISSING, **STOP and report** — do not attempt to create or
regenerate them (you have no display or real usage data; any GIF you produce
would be wrong or empty).

## Current state (exact excerpt — `README.md`, lines 1–18)

```markdown
<p align="center">
  <picture>
    <source srcset="./assets/oracle-banner.avif" type="image/avif">
    <source srcset="./assets/oracle-banner.webp" type="image/webp">
    <img src="./assets/oracle-banner.webp" alt="token-oracle — know when you'll hit the limit" width="900">
  </picture>
</p>

<p align="center">
  <a href="https://pypi.org/project/token-oracle/"><img src="https://img.shields.io/pypi/v/token-oracle?label=PyPI&cacheSeconds=3600" alt="PyPI version"></a>
  <a href="https://github.com/muslewski/token-oracle/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/muslewski/token-oracle/ci.yml?label=CI&cacheSeconds=3600" alt="CI"></a>
  <a href="https://pypi.org/project/token-oracle/"><img src="https://img.shields.io/pypi/pyversions/token-oracle?cacheSeconds=3600" alt="Python versions"></a>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license">
</p>

---

## Install
```

## The fix — steps in order

### Step 1 — insert the demo block

Insert the following **between the badges `</p>` (line 14) and the `---`
separator (line 16)** — i.e. the banner stays first, then badges, then the live
demo, then the `---`:

```markdown

<p align="center">
  <img src="./assets/dash-demo.gif" alt="token-oracle dash — live forecast of Claude Code and Grok token usage, with time left before each cap" width="720">
</p>

<p align="center">
  <sub><b>Live dashboard</b> — real, browser-verified usage for <b>Claude Code and Grok</b>, with time left before each cap. No API keys; reads local logs, optionally verifies against the sites.</sub>
</p>
```

Keep one blank line above and below the inserted block so the markdown parses
cleanly. Do not modify the banner `<picture>` block or the badges.

### Step 2 — commit the prepared assets alongside the README edit

Stage all three paths and commit together:

```bash
git add README.md assets/dash-demo.gif assets/dash-demo.tape
git commit -m "docs(readme): embed animated dashboard demo (plan 045)"
```

## Files out of scope / must not change

- No Python, no tests, no `SETUP.md`.
- Do not touch, re-encode, or "optimize" `assets/dash-demo.gif` — commit it
  exactly as seeded. Do not touch the banner assets.

## Done criteria (machine-checkable — run from repo root)

1. `grep -c "assets/dash-demo.gif" README.md` returns `1`.
2. `git ls-files --error-unmatch assets/dash-demo.gif assets/dash-demo.tape`
   exits 0 (both are tracked after your commit).
3. The GIF is intact and animated:
   `python -c "from PIL import Image; im=Image.open('assets/dash-demo.gif'); print(im.size, getattr(im,'n_frames',1))"`
   OR, if Pillow is unavailable, `file assets/dash-demo.gif` reports
   `GIF image data` with dimensions `760 x 560`. (Either check is sufficient —
   pick whichever tool is present; do not add a dependency.)
4. `git diff --stat main...HEAD` (or `git show --stat HEAD`) lists only
   `README.md`, `assets/dash-demo.gif`, `assets/dash-demo.tape`.

There are no pytest/ruff/mypy gates for this plan (no Python touched), but if you
run the suite it must still pass unchanged.

Do NOT run `pip install -e`.

## Escape hatches

- Assets missing (Step-1 precondition fails) → STOP and report; do not fabricate
  a GIF.
- If README.md's opening differs from the excerpt above (banner/badges moved),
  place the demo block so it appears **after the badges and before the first
  `---`/`## Install`**; if you cannot locate that anchor, STOP and report rather
  than guessing.

## Maintenance note

`assets/dash-demo.tape` is the reproducible source for the GIF: on a machine with
`vhs`, `ttyd`, `ffmpeg`, and a populated `oracle`, `vhs assets/dash-demo.tape`
regenerates `assets/dash-demo.gif`. Re-record when the dashboard layout changes
materially. The GIF shows real usage numbers captured at record time — that is
intentional (authentic > synthetic), but re-recording will show whatever the
current data is.
