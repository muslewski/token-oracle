---
type: zone
summary: "Optional browser-verified live layer under token_oracle/live: Playwright probe of grok.com/claude.ai, row extractors, trust states, snapshot store, and overlay that annotates Present-tab cells without inventing usage."
tags: [live, playwright, probe, extractors, truthfulness]
status: seeded
created: 2026-07-21
updated: 2026-07-21
verifiedAt: unverified
owns:
  routes: []
  testids: []
  globs:
    - "token_oracle/live/**"
  tools: []
depends: []
invariants: []
skills: []
related:
  - "[[dashboard]]"
  - "[[cli]]"
sources: []
---

## What this is

Opt-in real-data path (`oracle live`, `live-setup`, `live-probe`): web probe orchestration, Claude/Grok DOM extractors, shared extract helpers, trust/contract states (needs login, stale, rate-data-only, …), fill/overlay into the dashboard Present view. Offline forecast remains primary; live is verification, not a second ledger.

## Anchors

- `probe.py`, `web.py` — browser orchestration.
- `claude_extract.py`, `grok_extract.py`, `extract_common.py` — evidence-bound row parsing.
- `contract.py`, `trust.py`, `store.py`, `overlay.py`, `fill.py` — typed state + persistence + UI merge.

## Invariants

None asserted on seed (live-truthfulness / no-fabrication rules belong in a later verified pass with plan lineage).

## Lineage

Inferred from `live/` package docstring (plan 030 contract) and CLI live* subcommands on 2026-07-21 atlas-seed pass.
