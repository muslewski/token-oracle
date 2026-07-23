---
title: "Documentation"
description: "token-oracle product docs — install, forecast, dashboard, live data, statusline, and fleet interop."
section: home
order: 0
---

# token-oracle documentation

**token-oracle** forecasts when you will hit Claude Code / Grok token caps — offline from local logs, with optional browser-verified live overlay. No provider API keys required for the core path.

Site: [oracle.muslewski.com](https://oracle.muslewski.com) · PyPI · npm shim · GitHub

## Start here

| Path | For |
|------|-----|
| [Getting started](./getting-started.md) | First hour: install → init → forecast / dash |
| [Install](./install.md) | pipx, npm, source, library use |
| [Configuration](./configuration.md) | Profiles, windows, caps, cost |
| [CLI reference](./cli.md) | Every day-one command |

## Live & status surfaces

| Path | For |
|------|-----|
| [Live data](./live.md) | Browser-verified numbers (opt-in) |
| [Server truth](./live-server-truth.md) | 5h / weekly live windows |
| [Statusline & tmux](./statusline.md) | Shell bar + tmux `status-right` |
| [Integrations](./integrations.md) | Fleet and optional hooks |

## Reference & fleet

| Path | For |
|------|-----|
| [Adapters & snapshot](./adapters.md) | `forecast.json` contract |
| [Works with](./works-with.md) | herald, sage, atlas, armory, ferry |

## Doctrine

1. **Offline-first** — projections from logs on disk; live is opt-in.  
2. **Honest states** — missing data never invents a number.  
3. **Snapshot is the contract** — consumers read `forecast.json`.  
4. **Loose coupling** — oracle does not mutate sibling tool configs.

Internal specs/plans live in [`token-oracle-mind/`](../token-oracle-mind/) (Atlas), not under public `docs/`.
