---
title: "Integrations"
description: "Statusline, tmux, and fleet consumers"
---

# Integrations

### agentic-sage — `tokenForecastPath`

[agentic-sage](https://github.com/muslewski/agentic-sage) accepts an optional
`tokenForecastPath` key in its config. Point it at Oracle's snapshot file:

```json
{
  "tokenForecastPath": "~/.local/share/token-oracle/forecast.json"
}
```

Keep the snapshot fresh by enabling write-through in your config (preferred):

```json
{
  "snapshot_writethrough": true
}
```

Then any `oracle forecast` / `statusline` / `tmux` run also refreshes
`forecast.json`. Alternatively use a periodic `oracle snapshot` call (cron, a
shell hook, or a tmux `status-interval` triggered script).

Oracle and sage are fully independent — token forecasting is optional input to
session awareness, not a hard dependency. `oracle doctor` reports the state of
this link (detected / linked / stale) and prints the exact `tokenForecastPath`
value to set when sage is present but unlinked.
