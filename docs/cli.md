---
title: "CLI reference"
description: "token-oracle / oracle subcommands: forecast, dash, doctor, statusline, tmux, live, report"
---

# CLI reference

Binary names: `token-oracle` and `oracle` (aliases).

## Everyday

```bash
oracle forecast          # time left before caps
oracle dash              # full-screen Past / Present / Future TUI
oracle doctor            # config, sources, live status
oracle init              # guided config / presets
oracle report --days 14  # daily ledger
```

## Live overlay

```bash
oracle live on           # enable browser-verified numbers
oracle live off          # offline projection only
oracle live status       # show live mode state
```

## Status surfaces

```bash
oracle statusline        # ANSI line for shell prompts
oracle statusline --install
oracle tmux              # for tmux status-right
```

## Machine output

```bash
oracle forecast --json
oracle report --json
oracle snapshot          # write forecast.json contract
```

See [Configuration](./configuration.md) for profiles and windows, and [Live data](./live.md) for browser verification.
