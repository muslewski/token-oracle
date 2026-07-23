---
title: "Adapters & snapshot"
description: "How token-oracle reads local logs and the forecast.json contract consumers use"
---

# Adapters & snapshot

token-oracle is **provider-agnostic at the core**: adapters emit neutral usage events; the engine projects caps; consumers read **`forecast.json`**.

## Sources (high level)

- **Claude Code** — local session transcripts / usage logs on disk  
- **Grok Build** — local Grok session trails  
- Optional **live** overlay — browser-verified numbers (opt-in; never invents)

## Snapshot contract

Statuslines, tmux, herald, and judges should consume the snapshot file — not scrape the TUI.

Typical location (see config): under the oracle data dir as `forecast.json` (schema version 1).

Properties that matter to consumers:

- per-window used / cap / projected %
- ETA / time-left when known  
- honest states when data is missing (never fake green)

Deep adapter interface notes for integrators live in the repo [`ADAPTERS.md`](https://github.com/muslewski/token-oracle/blob/main/ADAPTERS.md) (source + consumer interfaces). Public install path stays offline-first; live is optional.

## Related

- [CLI reference](./cli.md)
- [Live data](./live.md)
- [Works with](./works-with.md)
