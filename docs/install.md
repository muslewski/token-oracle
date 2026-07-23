---
title: "Install"
description: "Install token-oracle via pipx, npm, or source"
---

# Install

### Tier 1 — engine + CLI (most users)

```bash
pipx install token-oracle
```

Or with pip:

```bash
pip install token-oracle
```

This registers the `token-oracle` command (plus the `oracle` alias) and gives
you `forecast`, `snapshot`, `doctor`, `statusline`, and `tmux` subcommands.

### Tier 2 — + live dashboard

The TUI dashboard ships in the same package; no extra install step needed.

```bash
oracle dash                      # live TUI — Past / Present / Future tabs
```

Interactive terminal: arrow keys (or `h`/`l`) switch tabs, `1`–`3` jump,
`Tab` cycles, `q` quits.

- **Present** — live multi-profile forecast (boxes / bars, live overlay)
- **Past** — last 14 days token + cost ledger (same engine as `oracle report`)
- **Future** — per-window prophecy, ETA warnings, next-24h burn sparkline

Piped / non-TTY output falls back to a non-interactive Present refresh
(~2 s) so `oracle dash | head` stays usable.

```bash
oracle report --days 14          # static daily ledger
oracle report --json             # machine-readable sections
```

### Tier 3 — + statusline / tmux integration

The ANSI statusline and tmux adapters are also in-package:

```bash
oracle statusline                # ANSI line (pipe to your shell prompt)
oracle tmux                      # tmux #(command) substitution
```

Example `~/.tmux.conf` entry (works for Grok Build + Claude Code):

```
set -g status-right '#(oracle tmux)'
```

Grok users: ensure `"source": "grok"` (with sessions_dir if non-default) before relying on the bar.

### Tier 4 — development install

```bash
git clone <repo>
cd token-oracle
pip install -e ".[dev]"
python -m pytest -q              # all green
```

### Tier 5 — library use (no CLI)

Install the same package and import directly:

```python
import time
from token_oracle.core.engine import forecast
from token_oracle.core.config import load_config

forecasts = forecast(time.time())
for f in forecasts:
    print(f.window, f.used, f.cap, f.projected_pct)
```

---
