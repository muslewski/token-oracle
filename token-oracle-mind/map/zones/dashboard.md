---
type: zone
summary: "Full-screen stdlib TUI (oracle dash) under token_oracle/dashboard: Past ledger, Present live gauges, Future prophecy + 24h sparkline, multi-sub side-by-side boxes and scene/region rendering."
tags: [tui, dashboard, dash, tabs]
status: seeded
created: 2026-07-21
updated: 2026-07-21
verifiedAt: unverified
owns:
  routes: []
  testids: []
  globs:
    - "token_oracle/dashboard/**"
  tools: []
depends:
  - "[[core]]"
  - "[[live]]"
invariants: []
skills: []
related: []
sources: []
---

## What this is

Interactive terminal dashboard: tab shell (past / present / future), pure `render_frame` path for tests, keyboard cycle, responsive box widths, race/future prophecy lines, and DashStore refresh loop over engine forecasts plus live overlay cells.

## Anchors

- `app.py` — run loop / tab shell.
- `past.py`, `future.py`, `race.py` — tab content.
- `scene.py`, `screen.py`, `skeleton.py` — fixed-region paint / loading.
- `store.py`, `keys.py` — state and input.

## Invariants

None asserted on seed.

## Lineage

Inferred from README dash description and `dashboard/app.py` on 2026-07-21 atlas-seed pass.
