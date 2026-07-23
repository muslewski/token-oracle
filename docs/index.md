---
title: "Documentation"
description: "Token-oracle product docs — install, forecast, dashboard, and fleet interop."
section: home
order: 0
---

# token-oracle documentation

**token-oracle** forecasts when you will hit Claude Code / Grok token caps. Offline from local logs; optional browser-verified live overlay. No provider API keys.

Site: [oracle.muslewski.com](https://oracle.muslewski.com) · PyPI: [`token-oracle`](https://pypi.org/project/token-oracle/) · npm shim: [`token-oracle`](https://www.npmjs.com/package/token-oracle)

## Start here

| Path | For |
|------|-----|
| [Getting started](./getting-started.md) | Install → `init` → `forecast` / `dash` → `doctor` |
| [Works with](./works-with.md) | Fleet siblings (herald, sage, atlas, armory, ferry) |

## Doctrine (short)

1. **Offline-first** — projections come from logs already on disk; live web is opt-in.
2. **Honest states** — missing data, needs-login, or rate-only never invents a number.
3. **Snapshot is the contract** — `forecast.json` (schema 1) is what status bars and judges consume.
4. **Loose coupling** — consumers read the file; oracle never mutates sibling configs.

## Where other knowledge lives

| Kind | Location |
|------|----------|
| **Public product docs** | `docs/` (this tree) |
| **Architecture mind (Atlas)** | [`token-oracle-mind/`](../token-oracle-mind/) — zones, decisions, specs, plans |
| **Agent install runbook** | [`AGENTS.md`](../AGENTS.md) |
| **Human setup deep-dive** | [`SETUP.md`](../SETUP.md) |
| **Source / consumer contracts** | [`ADAPTERS.md`](../ADAPTERS.md) |
| **Changelog** | [`CHANGELOG.md`](../CHANGELOG.md) |

Agent design specs and implementation plans live in the mind vault (`token-oracle-mind/specs/`, `plans/`), not under public `docs/`.
