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
| `source` | string | `"claude_code"` | Input adapter name: `claude_code`, `grok`, or `generic` |
| `source_opts` | object | `{}` | Options passed to the source adapter |
| `cache_path` | string | XDG data dir | Path to the rolling event cache |
| `windows` | array | `max20` preset | List of forecast windows |
| `plan` | string | `"max20"` | Named plan preset (`pro`, `max5`, `max20`) supplying default `windows`; unknown names fall back to `max20` with a reported issue |
| `cost_mode` | string | `"auto"` | Cost computation mode: `"auto"` (use recorded cost when present, else calculate), `"calculate"` (always calculate from token counts), `"display"` (only ever use recorded cost), or `"off"` (cost tracking disabled) |
| `pricing` | object | `{}` | Per-model-prefix USD-per-million-token overrides (same shape as the built-in snapshot in `core/pricing.py`); these win over the built-in snapshot |

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

## Live web data (real, browser-verified numbers)

By default token-oracle forecasts entirely offline from local logs. It can also
read your **real** current usage directly from `grok.com` and `claude.ai` using a
headless/headed browser session you log into once. This is opt-in and honest: if
it cannot verify a number, it reports the state (`unavailable`, `needs_login`,
`rate_data_only`) rather than guessing.

### Enable it

```bash
oracle live on          # turn on real (headed) live probing; writes it to your config
oracle live-setup       # one-time browser login to grok.com / claude.ai
oracle dash             # the dashboard now shows live, browser-verified numbers
oracle live status      # check whether it's on and what was last probed
oracle live off         # back to offline-only
```

`oracle live-probe` runs a single probe now and prints what it found
(`--provider grok|claude|all`, `--json` for machine output).

### Xvfb (for machines without a graphical display)

Headed probing needs a display. On a normal desktop it uses your existing one.
On a server / container / SSH session with no `$DISPLAY`, install **Xvfb** (a
virtual display) and token-oracle will use it automatically:

```bash
# Arch / Manjaro
sudo pacman -S xorg-server-xvfb
# Debian / Ubuntu
sudo apt install xvfb
```

Without a display or Xvfb, live probing honestly reports `unavailable` — it
never fabricates a number.

### Notes

- **No fingerprint evasion.** token-oracle drives a real browser with your own
  logged-in session; it does not spoof fingerprints or solve CAPTCHAs. If a site
  serves a bot challenge it reports that state and suggests
  `TOKEN_ORACLE_LIVE_HEADED=1 oracle live-probe`.
- Grok weekly usage is on the `?_s=usage` modal (`https://grok.com/?_s=usage`),
  not `/settings/usage` (that route bounces to chat). When only the 2h rate
  window is available the state is `rate_data_only` — that is expected until a
  headed probe captures the modal.
- Live numbers are display-only on the dash overlay path; they never rewrite
  offline projection math in the pure engine. (Statusline/forecast may prefer
  self-ingested Claude rate-limit headers for the 5h window — see below.)

---

## Live server-truth (5h / weekly)

token-oracle reads Claude Code's authoritative rate-limit header. Wire
token-oracle as your Claude Code statusline once, in `~/.claude/settings.json`:

```json
{ "statusLine": { "type": "command", "command": "oracle statusline" } }
```

Claude Code then hands `oracle statusline` the `rate_limits` header on each
render; token-oracle captures it (stdlib only, never raises), and `oracle dash`,
`forecast`, etc. show the exact 5h (and weekly, see plan 054) numbers the website
shows — no browser needed. Verify with `oracle doctor` (look for "live 5h truth: ON").

If you already use a custom statusline, compose: e.g. call `oracle statusline`
from your wrapper or pipe its effect.

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
