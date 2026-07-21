---
type: zone
summary: "Forecast domain layer under token_oracle/core: config presets, event cache, sliding-window burn profile, per-window cap ETA, pricing, report ledger, and versioned forecast.json snapshot writer."
tags: [forecast, engine, config, pricing, snapshot]
status: seeded
created: 2026-07-21
updated: 2026-07-21
verifiedAt: unverified
owns:
  routes: []
  testids: []
  globs:
    - "token_oracle/core/**"
    - "token_oracle/snapshot/**"
  tools: []
depends: []
invariants: []
skills: []
related: []
sources: []
---

## What this is

The offline forecast pipeline: load plan/window config, scan → cache → hour-of-week profile → `compute_window` ETAs, multi-profile support (`claude` + `grok`), USD pricing snapshot, daily report aggregation, and atomic `forecast.json` for consumers.

## Anchors

- `token_oracle/core/**` — config, engine, windows, cache, profile, pricing, report, ratelimits, contracts, events, timeutil, capcal.
- `token_oracle/snapshot/**` — schema-versioned snapshot write path (ADAPTERS consumer contract).

## Invariants

Left empty on seed; load-bearing rules (e.g. engine never-crash, obs_rate not in public snapshot) need verified `enforcedBy` paths later.

## Lineage

Inferred from tree + README "How it works" / ADAPTERS.md snapshot schema on 2026-07-21 atlas-seed pass.
