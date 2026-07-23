---
title: "Configuration"
description: "Profiles, windows, caps, and cost mode"
---

# Configuration

### Guided setup

On a real TTY, bare `token-oracle init` opens a short wizard (plan preset,
global vs project scope, cost display). Non-interactive / agent use should
pass flags instead:

```bash
token-oracle init --preset max20              # global XDG config
token-oracle init --preset pro --config ./.token-oracle.json
token-oracle init --force                     # overwrite existing
```

Example wizard transcript:

```
🔮 token-oracle setup

1) Which plan are you on?
   1. max20      (5h cap ≈ 220k tokens)   [default]
   2. max5       (5h cap ≈ 88k tokens)
   3. pro        (5h cap ≈ 19k tokens)
   …
   choice [1]:

2) Where should config live?
   1. global — ~/.config/token-oracle/config.json (all repos)  [default]
   2. this project — ./.token-oracle.json (wins over global here)

3) Show cost estimates in USD? [Y/n]
```

### File location

Config resolution order (first hit wins; no merging across scopes):

1. `--config FILE` on the CLI
2. `$TOKEN_ORACLE_CONFIG` environment variable
3. `.token-oracle.json` in the current directory or any ancestor (stops at
   `$HOME` / filesystem root; hard cap 40 levels)
4. Global XDG: `~/.config/token-oracle/config.json` (respects `$XDG_CONFIG_HOME`)

`oracle doctor` prints which rule won as a dim suffix:
`(--config)`, `(env)`, `(project)`, or `(global)`.

`oracle clean` removes the global config path (or `--config`); it does not
walk up to delete project files — remove `.token-oracle.json` yourself if needed.

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
| `source` | string | `"claude_code"` | Input adapter name: `claude_code`, `grok`, or `generic` |
| `source_opts` | object | `{}` | Options passed to the source adapter |
| `cache_path` | string | XDG data dir | Path to the rolling event cache |
| `windows` | array | `max20` preset | List of forecast windows |
| `plan` | string | `"max20"` | Named plan preset (`pro`, `max5`, `max20`) supplying default `windows`; unknown names fall back to `max20` with a reported issue |
| `cost_mode` | string | `"auto"` | Cost computation mode: `"auto"` (use recorded cost when present, else calculate), `"calculate"` (always calculate from token counts), `"display"` (only ever use recorded cost), or `"off"` (cost tracking disabled) |
| `pricing` | object | `{}` | Per-model-prefix USD-per-million-token overrides (same shape as the built-in snapshot in `core/pricing.py`); these win over the built-in snapshot |
| `snapshot_writethrough` | bool | `false` | When true, `forecast` / `statusline` / `tmux` also refresh the snapshot file (kills the need for a 5-minute cron) |

### Window object

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Label shown in output |
| `cap` | integer | yes | Token cap for this window |
| `period_secs` | integer | yes | Window length in seconds |
| `anchor` | string or null | no | ISO 8601 timestamp (fixed-grid mode) or omit/null for rolling-from-first-event mode |

**Rolling mode** (omit `anchor` or set to `null`): window starts at its first
observed event and re-anchors after each expiry. Matches common 5-hour
rolling block behavior (Claude Code, similar for other harnesses).

**Fixed-grid mode** (`anchor` set to an ISO 8601 string, e.g. `"2026-01-05T00:00:00Z"`):
window starts at `anchor + n * period_secs`. Useful for weekly/monthly caps that
reset on a known calendar boundary.

### Plan presets

Set `"plan"` in your config (or `token-oracle init --preset NAME`) to start
from one of the built-in caps instead of writing `windows` by hand:

| Preset | 5h cap | Weekly cap |
|---|---|---|
| `pro` | 19,000 | 700,000 |
| `max5` | 88,000 | 3,200,000 |
| `max20` | 220,000 | 8,000,000 |

5h caps follow published approximations for Claude Pro/Max (and similar for Grok usage); weekly
caps are proportional estimates — override `windows` for exact values.

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

### Example — Grok (default windows + grok source)

```json
{
  "source": "grok",
  "source_opts": {"sessions_dir": "~/.grok/sessions"},
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
| Grok Build sessions | `"grok"` | `"sessions_dir"` (default `~/.grok/sessions`) |
| Neutral JSON file | `"generic"` | `"events_path"` (required) |

The `generic` source reads a JSON file of `[[timestamp_epoch, tokens], ...]` pairs (or full event rows). The `grok` source extracts deltas from `totalTokens` reports in `updates.jsonl`.

---
