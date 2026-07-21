---
type: zone
summary: "Consumer output adapters under token_oracle/adapters: adaptive statusline segments, tmux status-right fragments, and ADAPTERS.md source/consumer contracts for external plugs into forecast.json."
tags: [adapters, statusline, tmux, integrations]
status: seeded
created: 2026-07-21
updated: 2026-07-21
verifiedAt: unverified
owns:
  routes: []
  testids: []
  globs:
    - "token_oracle/adapters/**"
    - "ADAPTERS.md"
  tools: []
depends:
  - "[[core]]"
invariants: []
skills: []
related: []
sources: []
---

## What this is

Thin renderers that turn a Forecast list into shell/tmux HUD fragments (`oracle statusline`, `oracle tmux`), with cell-budget degradation (full → compact → minimal). Repo-root `ADAPTERS.md` documents the stable source event shape and snapshot consumer contract for external code (e.g. agentic-sage).

## Anchors

- `segments.py` — adaptive multi-encoding segment builder.
- `statusline.py`, `tmux.py` — CLI-facing render entrypoints.
- `ADAPTERS.md` — public integration surface documentation.

## Invariants

None asserted on seed.

## Lineage

Inferred from README Adapters section and adapters package on 2026-07-21 atlas-seed pass.
