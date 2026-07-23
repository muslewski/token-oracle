---
title: "Getting started"
description: "Install token-oracle, run a forecast, and verify with oracle doctor."
section: guide
order: 10
---

# Getting started

Four steps. Then you know how long until the cap.

## 1. Install

**Run without installing** (fetches latest on demand):

```bash
npx token-oracle dash         # Node
bunx token-oracle dash        # Bun
uvx token-oracle dash         # uv
```

**Or put `oracle` / `token-oracle` on your PATH:**

```bash
pipx install token-oracle     # isolated Python (recommended)
# or
uv tool install token-oracle
pip install token-oracle
npm install -g token-oracle   # thin Node shim → uvx/pipx/python under the hood
curl -fsSL https://raw.githubusercontent.com/muslewski/token-oracle/main/install.sh | sh
```

Requires **Python ≥ 3.10**. Bins: `oracle` and `token-oracle` (same CLI).

## 2. Init

```bash
token-oracle init             # guided setup on a TTY
token-oracle init --preset max20   # non-interactive / agents
```

Presets: `pro`, `max5`, `max20` (default). Config lands at
`~/.config/token-oracle/config.json` or project `.token-oracle.json`.

## 3. Forecast / dash

```bash
oracle forecast               # one-line projection
oracle forecast --json        # machine-readable (schema 1)
oracle report --days 14       # past spend ledger
oracle dash                   # full TUI — Past / Present / Future
```

Optional status surfaces (same engine):

```bash
oracle statusline --install   # Claude Code statusline + rate-limit self-ingest
# tmux: set -g status-right '#(oracle tmux)'
```

## 4. Doctor

```bash
oracle doctor
```

Fix anything red. Green doctor means config, source, data, cache, and windows
are coherent.

## Snapshot feed (fleet consumers)

```bash
oracle snapshot               # write ~/.local/share/token-oracle/forecast.json
```

Or set `"snapshot_writethrough": true` in config so `forecast` / `statusline` /
`tmux` refresh the file automatically.

That snapshot is what **status-herald** (bar gauges) and **agentic-sage**
(`tokenForecastPath`) read when present — optional, fail-open, no hard
dependency either way. Details: [Works with](./works-with.md).

## Agent path

If an agent is installing for you, follow the machine-oriented runbook:

→ **[`AGENTS.md`](../AGENTS.md)** (install → doctor → forecast → snapshot → optional sage)

## Next

- Full config, live web probes, multi-profile: **[`SETUP.md`](../SETUP.md)**
- Source / consumer adapter contracts: **[`ADAPTERS.md`](../ADAPTERS.md)**
- Fleet map: [Works with](./works-with.md)
