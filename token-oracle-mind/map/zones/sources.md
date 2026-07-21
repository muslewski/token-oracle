---
type: zone
summary: "Provider log scanners under token_oracle/sources: claude_code JSONL, grok sessions updates.jsonl/signals, generic events file — register via base.get_source into neutral [ts, tokens, …] events."
tags: [sources, adapters, claude, grok, logs]
status: seeded
created: 2026-07-21
updated: 2026-07-21
verifiedAt: unverified
owns:
  routes: []
  testids: []
  globs:
    - "token_oracle/sources/**"
  tools: []
depends: []
invariants: []
skills: []
related:
  - "[[core]]"
sources: []
---

## What this is

First-class source adapters that turn local agent harness logs into the engine's neutral event tuples. No provider API keys — file/path scan only (`~/.claude/projects`, `~/.grok/sessions`, or a configured events path).

## Anchors

- `token_oracle/sources/base.py` — registry / `get_source`.
- `claude_code.py`, `grok.py`, `generic.py` — concrete scanners registered on import.

## Invariants

None asserted on seed (event field shape lives in ADAPTERS.md / contracts).

## Lineage

Inferred from README supported-sources table and `sources/` package on 2026-07-21 atlas-seed pass.
