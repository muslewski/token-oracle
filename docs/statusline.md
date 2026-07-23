---
title: "Statusline & tmux"
description: "Put token-oracle time-left into Claude/Grok status bars and tmux"
---

# Statusline & tmux

## One-shot install

```bash
oracle statusline --install
```

Print a line for your shell:

```bash
oracle statusline
```

## tmux

```bash
# ~/.tmux.conf
set -g status-right '#(oracle tmux)'
```

Reload tmux config after install. Ensure profiles point at the agent you care about (`claude` / `grok` sources in config).

## With status-herald

Herald can surface sibling status chips; oracle remains the **token/cap** source via snapshot. See [Works with](./works-with.md).

## Troubleshooting

```bash
oracle doctor
oracle live status
```

If the bar is empty: check `oracle forecast` and that log paths exist for the active profile.
