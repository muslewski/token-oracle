<p align="center">
  <picture>
    <source srcset="./assets/oracle-banner.avif" type="image/avif">
    <source srcset="./assets/oracle-banner.webp" type="image/webp">
    <img src="./assets/oracle-banner.webp" alt="token-oracle — know when you'll hit the limit" width="900">
  </picture>
</p>

<p align="center">
  <a href="https://pypi.org/project/token-oracle/"><img src="https://img.shields.io/pypi/v/token-oracle?label=PyPI&cacheSeconds=3600" alt="PyPI version"></a>
  <a href="https://github.com/muslewski/token-oracle/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/muslewski/token-oracle/ci.yml?label=CI&cacheSeconds=3600" alt="CI"></a>
  <a href="https://pypi.org/project/token-oracle/"><img src="https://img.shields.io/pypi/pyversions/token-oracle?cacheSeconds=3600" alt="Python versions"></a>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license">
</p>

<p align="center"><img src="./assets/demo-dash.gif" width="720" alt="oracle dash demo"></p>

<p align="center">
  <sub><b>Live dashboard</b> — staged multi-subscription forecast for <b>Claude Code and Grok</b>, with time left before each cap. No API keys; reads local logs, optionally verifies against the sites.</sub>
</p>

## Live usage in your status bar

Wire it once:

```bash
oracle statusline --install
```

Claude Code (and tmux) then shows a live headline such as:

```
◔ 5h 26% · wk 60% · $8 today
```

(The 5h/wk numbers come from the rate-limit header self-ingest; cost uses local ledger.)

---

## Install

**Run it instantly** — no install, using a runner you probably already have:

```bash
npx token-oracle dash         # Node
bunx token-oracle dash        # Bun
uvx token-oracle dash         # uv
```

**Or install** the `token-oracle` command onto your PATH:

```bash
curl -fsSL https://raw.githubusercontent.com/muslewski/token-oracle/main/install.sh | sh
uv tool install token-oracle   # uv (isolated, fast)
pipx install token-oracle      # pipx (isolated)
pip install token-oracle       # pip
```

> `npx`/`bunx`/`uvx` fetch and run the latest release on demand; the installers
> put it on your PATH. All routes are the same offline-first tool — see
> [SETUP.md](./SETUP.md) for live web data and configuration.

## Quickstart

```bash
token-oracle init         # guided setup (or --preset max20 for non-interactive)
token-oracle forecast     # live forecast — time left before your cap
token-oracle report       # what you spent, day by day (tokens + cost + % of weekly cap)
token-oracle dash         # full-screen TUI — Past ledger / Present live / Future prophecy
token-oracle doctor       # check configuration + data sources
```

<p align="center"><img src="./assets/demo-forecast.gif" width="600" alt="oracle forecast demo"></p>

<details><summary>▶ demo</summary>
<p><img src="./assets/demo-doctor.gif" width="600" alt="oracle doctor demo"></p>
</details>

Config can live globally (`~/.config/token-oracle/config.json`) or per-project
(`.token-oracle.json` walking up from the cwd). Run `token-oracle --help` for
all subcommands.

## How it works

token-oracle reads your agent's local usage logs, computes an observed token-consumption rate over a configurable sliding window, and estimates how long you have before you exhaust your current allowance or hit your plan cap. No provider API calls — purely offline inference from log files already on your machine. Ships with `pro`/`max5`/`max20` plan presets and an offline USD pricing snapshot for cost estimates, both user-overridable via `plan`, `cost_mode`, and `pricing` config keys.

Supported sources (first-class agent harnesses):

| Source | `source` value | Log location |
|--------|----------------|--------------|
| Claude Code | `claude_code` | `~/.claude/projects/*/*.jsonl` |
| Grok Build | `grok` | `~/.grok/sessions/*/*/updates.jsonl` + `signals.json` (contextTokensUsed for live) |
| Generic (file) | `generic` | JSON file of `[timestamp, tokens]` pairs via `source_opts.events_path` |

Multi-subscription: put `"profiles": {"claude": {...}, "grok": {...}}` in config.json to track both Claude Code (Max20 etc) and Grok/SuperGrok Heavy simultaneously. `oracle dash` shows side-by-side with reset alarms.

**Future tab** (in `oracle dash`): per-window prophecy lines, observational
cap ETA warnings, and a next-24h expected-burn sparkline from the hour-of-week
profile — the projection math rendered, not just a single %.

## Parts & options

All subcommands accept `--config FILE`. Without it, resolution is
`$TOKEN_ORACLE_CONFIG` → `.token-oracle.json` (cwd walk-up) → XDG global.

| Subcommand | Extra flags | Description |
|------------|-------------|-------------|
| `init` | `--preset`, `--force` | Starter config (TTY wizard if no flags; non-clobbering) |
| `forecast` | `--json` | Print forecast (default: statusline format) |
| `snapshot` | `--out FILE` | Write snapshot JSON to a file, print the path |
| `statusline` | — | Emit plain-text/ANSI statusline fragment |
| `tmux` | — | Emit tmux `status-right` fragment |
| `doctor` | — | Check configuration and data sources |
| `report` | `--days`, `--by`, `--json`, `--since/--until` | Daily (or week/model) token + cost ledger |
| `dash` | — | Full-screen TUI: Past ledger, Present live, Future prophecy + 24h sparkline |
| `clean` | `--yes` | Remove config, cache, and snapshot files |

Grok Build users: `{"source": "grok"}` (or with `source_opts.sessions_dir`) in config; then `oracle tmux` / `statusline` / `forecast` surface usage. Hooks in `~/.grok/hooks/` can drive `oracle snapshot`.

Full reference: `token-oracle <subcommand> --help`

## CLI reference

```
token-oracle {forecast,report,snapshot,statusline,tmux,doctor,dash,init,clean} [OPTIONS]

token-oracle init       [--config FILE] [--preset NAME] [--force]
token-oracle forecast   [--config FILE] [--json]
token-oracle report     [--config FILE] [--days N] [--by day|week|model] [--json]
token-oracle snapshot   [--config FILE] [--out FILE]
token-oracle statusline [--config FILE]
token-oracle tmux       [--config FILE]
token-oracle doctor     [--config FILE]
token-oracle dash       [--config FILE]
token-oracle clean      [--config FILE] [--yes]
```

## Adapters

Output adapters let token-oracle feed your status bar or terminal multiplexer (works for Grok, Claude, etc.):

- **tmux** — writes a tmux-formatted `status-right` fragment (e.g. `set -g status-right '#(oracle tmux)'`)
- **statusline** — writes a plain-text/ANSI fragment for any status line

See [ADAPTERS.md](ADAPTERS.md) for setup and configuration. Grok users in tmux get token status in bottom bar directly.

## Colors

The forecast bar uses colour thresholds on projected usage at window end (as
a % of cap) to signal urgency:

| Colour | Projected % of cap |
|--------|--------------------|
| 🟢 Green | < 85 % |
| 🟡 Lime | 85 – 100 % |
| 🟠 Orange | 100 – 120 % |
| 🔴 Red | ≥ 120 % |

## Works with agentic-sage

[agentic-sage](https://github.com/muslewski/agentic-sage) is a companion JS tool.
Division of labor: **oracle** owns tokens, cost, and forecasts; **sage** owns
sessions, fleet coordination, and guidance. Point sage at oracle's snapshot:

```json
{
  "tokenForecastPath": "~/.local/share/token-oracle/forecast.json"
}
```

`oracle doctor` detects sage and prints the exact link hint (or flags a stale
snapshot). Enable `"snapshot_writethrough": true` so forecast/statusline/tmux
keep the file fresh automatically.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In brief: fork → branch from `main` → `pytest` + `ruff check` + `mypy` → pull request.

## License

MIT — Copyright (c) 2026 Mateusz Muślewski.
