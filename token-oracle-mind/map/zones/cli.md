---
type: zone
summary: "User-facing CLI entrypoints token-oracle/oracle (token_oracle.cli.main): init, forecast, report, snapshot, statusline, tmux, doctor, dash, clean, live* palette and ANSI colors."
tags: [cli, entrypoint, subcommands]
status: seeded
created: 2026-07-21
updated: 2026-07-21
verifiedAt: unverified
owns:
  routes: []
  testids: []
  globs:
    - "token_oracle/cli/**"
    - "token_oracle/__init__.py"
  tools: []
depends:
  - "[[core]]"
invariants: []
skills: []
related: []
sources: []
---

## What this is

Argparse surface and zero-arg fzf command palette for all product subcommands. Resolves config paths, wires adapters/engine/dashboard/live, and owns terminal color helpers used by status fragments.

## Anchors

- `token_oracle/cli/main.py` — subcommand dispatch (`forecast`, `report`, `dash`, `doctor`, `live-probe`, …).
- `token_oracle/cli/colors.py` — pipe-aware ANSI.
- `token_oracle/__init__.py` — package root.

## Invariants

None asserted on seed.

## Lineage

Inferred from `pyproject.toml` `[project.scripts]` and `cli/main.py` module docstring on 2026-07-21 atlas-seed pass.
