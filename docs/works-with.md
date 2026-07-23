---
title: "Works with"
description: "How token-oracle fits the muslewski fleet — real interop, not a laundry list."
section: recipes
order: 5
---

# Works with

Oracle owns **token/cap forecasts**. Sibling tools cover other slices of the same desk. Name them in feature docs when a **real** integration exists; this page is the short map.

| Package | Relationship to token-oracle | Links |
|---------|------------------------------|--------|
| **status-herald** | Status bars / curtain UI. Reads oracle’s `forecast.json` (default `~/.local/share/token-oracle/forecast.json`) for **account bar gauges** via a thin bridge — optional, never throws. Oracle does not depend on herald. | [herald.muslewski.com](https://herald.muslewski.com) · [npm](https://www.npmjs.com/package/status-herald) |
| **agentic-sage** | Fleet judge. Optional `tokenForecastPath` in sage config points at the same snapshot; `oracle doctor` detects sage and prints the exact link (or stale) hint. Oracle never writes sage’s config. | [sage.muslewski.com](https://sage.muslewski.com) · [npm](https://www.npmjs.com/package/agentic-sage) |
| **memory-atlas** | Architecture vaults. This repo’s understanding lives in `token-oracle-mind/` (Atlas); public guides live in `docs/`. Atlas ships a read-only **budget-hint** example that consumes schema-1 `forecast.json` — file-only coupling. | [atlas.muslewski.com](https://atlas.muslewski.com) · [npm](https://www.npmjs.com/package/memory-atlas) |
| **llm-armory** | Named executor loadouts. No hard-coded bridge in this package; sessions armory spawns can still use `oracle statusline` / tmux on the same machine like any other harness. Desk neighbor, not a mutual import. | [armory.muslewski.com](https://armory.muslewski.com) · [npm](https://www.npmjs.com/package/llm-armory) |
| **mossferry** | Remote tmux/mosh “ferry” to the host where your fleet (and oracle) actually run. No code dependency — ferry gets you to the machine; oracle stays local to the logs. | [mossferry.muslewski.com](https://mossferry.muslewski.com) · [npm](https://www.npmjs.com/package/mossferry) |

## Forecast feed contract (shared edge)

Consumers of the snapshot should treat **schema 1** as stable:

- Default path: `~/.local/share/token-oracle/forecast.json` (respects `$XDG_DATA_HOME`)
- Writer: `oracle snapshot`, or any `forecast` / `statusline` / `tmux` run when `snapshot_writethrough` is true
- Fields: see [`ADAPTERS.md`](../ADAPTERS.md) (Consumer interface)

**status-herald** and **agentic-sage** are the two fleet packages that actually consume this feed today. Keep them named where the feed is documented (getting started, adapters, doctor hints).

## Rules for authors

1. **Contextual first** — when documenting a feature that displays or depends on a sibling, say so on that page (one clear sentence + link).
2. **Update this table** when you add or remove a real edge.
3. **Do not invent** — if code does not wire it, do not claim it.

## See also

- [Getting started](./getting-started.md) — install + snapshot
- [`SETUP.md`](../SETUP.md) — sage `tokenForecastPath` deep-dive
- [`ADAPTERS.md`](../ADAPTERS.md) — full consumer contract
