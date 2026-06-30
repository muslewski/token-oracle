<h1 align="center">🔮 token-oracle</h1>

<p align="center">Provider-agnostic token usage-cap forecaster — know when you'll hit your limit before you hit it.</p>

<p align="center">
  <a href="https://pypi.org/project/token-oracle/"><img src="https://img.shields.io/pypi/v/token-oracle?label=PyPI" alt="PyPI version"></a>
  <a href="https://github.com/muslewski/token-oracle/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/muslewski/token-oracle/ci.yml?label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/token-oracle/"><img src="https://img.shields.io/pypi/pyversions/token-oracle" alt="Python versions"></a>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license">
</p>

---

## Install

```bash
pipx install token-oracle   # recommended — isolated environment
pip install token-oracle    # fallback
uvx token-oracle            # uv users
```

## Quickstart

```bash
token-oracle forecast     # live forecast — time left before your cap
token-oracle dash         # full-screen TUI dashboard
token-oracle doctor       # check configuration + data sources
```

Run `token-oracle --help` to list all subcommands.

## How it works

token-oracle reads your provider's local usage logs, computes an observed token-consumption rate over a configurable sliding window, and estimates how long you have before you exhaust your current allowance or hit your plan cap. No provider API calls — purely offline inference from log files already on your machine.

Supported sources:

| Source | Log location |
|--------|-------------|
| Claude Code | `~/.claude/projects/*/*.jsonl` |
| Generic (stdin) | pipe any JSON usage stream |

## Parts & options

All subcommands accept `--config FILE` (default: `~/.config/token-oracle/config.toml`).

| Subcommand | Extra flags | Description |
|------------|-------------|-------------|
| `forecast` | `--json` | Print forecast (default: statusline format) |
| `snapshot` | `--out FILE` | Write snapshot JSON to a file, print the path |
| `statusline` | — | Emit plain-text/ANSI statusline fragment |
| `tmux` | — | Emit tmux `status-right` fragment |
| `doctor` | — | Check configuration and data sources |
| `dash` | — | Launch full-screen TUI dashboard |

Full reference: `token-oracle <subcommand> --help`

## CLI reference

```
token-oracle {forecast,snapshot,statusline,tmux,doctor,dash} [OPTIONS]

token-oracle forecast   [--config FILE] [--json]
token-oracle snapshot   [--config FILE] [--out FILE]
token-oracle statusline [--config FILE]
token-oracle tmux       [--config FILE]
token-oracle doctor     [--config FILE]
token-oracle dash       [--config FILE]
```

## Adapters

Output adapters let token-oracle feed your status bar or terminal multiplexer:

- **tmux** — writes a tmux-formatted `status-right` fragment
- **statusline** — writes a plain-text/ANSI fragment for any status line

See [ADAPTERS.md](ADAPTERS.md) for setup and configuration.

## Colors

The forecast bar uses colour thresholds to signal urgency:

| Colour | Meaning |
|--------|---------|
| 🟢 Green | > 40 % remaining |
| 🟡 Yellow | 15 – 40 % remaining |
| 🔴 Red | < 15 % remaining |

## Works with agentic-sage

[agentic-sage](https://github.com/muslewski/agentic-sage) is a companion JS tool for managing Claude Code skill definitions. token-oracle is provider-agnostic and complements it by surfacing usage-cap forecasts independently of any AI framework.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In brief: fork → branch from `main` → `pytest` + `ruff check` + `mypy` → pull request.

## License

MIT — Copyright (c) 2026 Mateusz Muślewski.
