---
type: zone
summary: "Distribution and install channels: install.sh/install.py curl installer, uninstall.py, and npm package shim (npx token-oracle) that launches the PyPI Python CLI via uvx/pipx/python."
tags: [install, npm, distribution, packaging]
status: seeded
created: 2026-07-21
updated: 2026-07-21
verifiedAt: unverified
owns:
  routes: []
  testids: []
  globs:
    - "install.py"
    - "install.sh"
    - "uninstall.py"
    - "npm/**"
  tools: []
depends: []
invariants: []
skills: []
related:
  - "[[cli]]"
sources: []
---

## What this is

How users get the `oracle` / `token-oracle` command without cloning: shell installer, Python install/uninstall helpers, and the thin Node launcher under `npm/` so `npx`/`bunx` routes into the same offline-first Python tool published on PyPI.

## Anchors

- `install.sh`, `install.py`, `uninstall.py` — PATH install / cleanup.
- `npm/bin/cli.js`, `npm/package.json` — npm shim package.

## Invariants

None asserted on seed.

## Lineage

Inferred from README Install channels and tree on 2026-07-21 atlas-seed pass.
