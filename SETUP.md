# SETUP

## Installation tiers

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
oracle dash                      # live TUI, refreshes ~2 s
```

### Tier 3 — + statusline / tmux integration

The ANSI statusline and tmux adapters are also in-package:

```bash
oracle statusline                # ANSI line (pipe to your shell prompt)
oracle tmux                      # tmux #(command) substitution
```

Example `~/.tmux.conf` entry:

```
set -g status-right '#(oracle tmux)'
```

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

## Configuration

Run `token-oracle init` to write a starter config at the default location
(non-clobbering — pass `--force` to overwrite, or `--config FILE` for a
custom path). Edit the resulting file to customize sources or windows; the
format is documented below.

### File location

Default: `~/.config/token-oracle/config.json`  
Respects `$XDG_CONFIG_HOME` when set.  
Override at runtime: `oracle forecast --config /path/to/config.json`

Cache default: `~/.local/share/token-oracle/cache.json`  
Snapshot default: `~/.local/share/token-oracle/forecast.json`  
Both respect `$XDG_DATA_HOME`.

### Format

```json
{
  "source": "claude_code",
  "source_opts": {},
  "cache_path": "~/.local/share/token-oracle/cache.json",
  "windows": [
    {"name": "5h",     "cap": 220000,  "period_secs": 18000},
    {"name": "weekly", "cap": 8000000, "period_secs": 604800, "anchor": null}
  ]
}
```

All fields are optional. If the config file is absent (or unreadable), the
built-in `max20` preset above is used.

### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `source` | string | `"claude_code"` | Input adapter name |
| `source_opts` | object | `{}` | Options passed to the source adapter |
| `cache_path` | string | XDG data dir | Path to the rolling event cache |
| `windows` | array | `max20` preset | List of forecast windows |

### Window object

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Label shown in output |
| `cap` | integer | yes | Token cap for this window |
| `period_secs` | integer | yes | Window length in seconds |
| `anchor` | string or null | no | ISO 8601 timestamp (fixed-grid mode) or omit/null for rolling-from-first-event mode |

**Rolling mode** (omit `anchor` or set to `null`): window starts at its first
observed event and re-anchors after each expiry. Matches Claude's 5-hour
rolling block behavior.

**Fixed-grid mode** (`anchor` set to an ISO 8601 string, e.g. `"2026-01-05T00:00:00Z"`):
window starts at `anchor + n * period_secs`. Useful for weekly/monthly caps that
reset on a known calendar boundary.

### Example — Claude max20 preset (default)

```json
{
  "source": "claude_code",
  "windows": [
    {"name": "5h",     "cap": 220000,  "period_secs": 18000},
    {"name": "weekly", "cap": 8000000, "period_secs": 604800}
  ]
}
```

### Example — custom windows

```json
{
  "source": "generic",
  "source_opts": {"events_path": "~/my-usage.json"},
  "windows": [
    {"name": "1h",    "cap": 50000,   "period_secs": 3600},
    {"name": "daily", "cap": 500000,  "period_secs": 86400,
     "anchor": "2026-01-01T00:00:00Z"}
  ]
}
```

### Sources

| Source | `source` value | Key `source_opts` |
|---|---|---|
| Claude Code transcripts | `"claude_code"` | `"projects_dir"` (default `~/.claude/projects`) |
| Neutral JSON file | `"generic"` | `"events_path"` (required) |

The `generic` source reads a JSON file of `[[timestamp_epoch, tokens], ...]` pairs.

---

## Optional integrations

### agentic-sage — `tokenForecastPath`

[agentic-sage](https://github.com/muslewski/agentic-sage) accepts an optional
`tokenForecastPath` key in its config. Point it at Oracle's snapshot file:

```json
{
  "tokenForecastPath": "~/.local/share/token-oracle/forecast.json"
}
```

Then keep the snapshot fresh with a periodic `oracle snapshot` call (e.g. cron,
a shell hook, or a tmux `status-interval` triggered script).

Oracle and sage are fully independent — token forecasting is optional input to
session awareness, not a hard dependency.
