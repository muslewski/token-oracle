# 🔮 token-oracle

[![PyPI version](https://img.shields.io/pypi/v/token-oracle)](https://pypi.org/project/token-oracle/)
[![CI](https://img.shields.io/github/actions/workflow/status/muslewski/token-oracle/ci.yml?label=CI)](https://github.com/muslewski/token-oracle/actions/workflows/ci.yml)
[![Python versions](https://img.shields.io/pypi/pyversions/token-oracle)](https://pypi.org/project/token-oracle/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**O**bserved-**R**ate **A**llowance **&** **C**ap-**L**imit **E**stimator — a
provider-agnostic engine that forecasts **when you'll hit a usage cap before its
reset**, learned from your own observed burn patterns. Companion to
[agentic-sage](https://github.com/muslewski/agentic-sage).

> The engine is the product. UIs — statusline, tmux, dashboard — are optional
> consumers of a neutral `Forecast`. Zero dependencies, stdlib only, Python 3.10+.

## Quickstart

```bash
pipx install token-oracle        # or: pip install token-oracle
token-oracle doctor              # config + source + windows, with ✓/✗ checks
token-oracle forecast            # human status line
token-oracle forecast --json     # the snapshot schema
token-oracle dash                # live colored TUI
```

Works out of the box with Claude Code (`claude_code` source, selected by default).
Other providers feed in via the `generic` source or a custom adapter.

## How it works

token-oracle builds a **burn profile** from your recent usage history — observed
token consumption bucketed into sliding windows. Each window is compared against
the provider cap it belongs to, and the engine extrapolates forward to estimate
projected usage at reset time.

The output is a provider-agnostic `Forecast` object:

1. **Source adapter** — reads usage logs (e.g. Claude Code's `~/.claude/projects/*/*.jsonl`) and emits `(timestamp, tokens)` pairs.
2. **Burn profiler** — aggregates observed pairs into per-window burn rates.
3. **Window resolver** — maps each window to its cap and reset time from your config.
4. **Forecast engine** — projects forward, computes `projected / cap` ratio, and derives a severity gauge (`ok → warning → critical → over`).
5. **Consumer** — CLI (`forecast`, `dash`, `statusline`, `tmux`) or any external tool reading `forecast.json`.

## Parts & options

| Part | What it does | Need it? |
|---|---|---|
| core engine | forecast math (burn profile + window math) | required |
| `claude_code` source | reads `~/.claude/projects/*/*.jsonl` | default source |
| `generic` source | feed your own `[[ts, tokens]]` JSON file | optional |
| `token-oracle` CLI | `forecast` / `snapshot` / `doctor` / statusline / tmux | required |
| TUI dashboard (`token-oracle dash`) | live colored forecast view, refreshes ~2 s | optional |
| statusline adapter | ANSI status-line reference renderer | optional |
| tmux adapter | tmux-formatted line reference renderer | optional |
| snapshot (`forecast.json`) | stable JSON contract for external consumers | optional |

See [SETUP.md](SETUP.md) for full configuration reference.
See [ADAPTERS.md](ADAPTERS.md) for the source and consumer interfaces.
See [AGENTS.md](AGENTS.md) for a deterministic coding-agent runbook.

## CLI reference

| Command | Description |
|---|---|
| `token-oracle forecast` | Human status line |
| `token-oracle forecast --json` | Print the full snapshot JSON |
| `token-oracle snapshot [--out PATH]` | Write `forecast.json`, print path |
| `token-oracle statusline` | ANSI status line (reference adapter) |
| `token-oracle tmux` | tmux-formatted line (reference adapter) |
| `token-oracle doctor` | Config, source, cache, windows — with ✓/✗ checks |
| `token-oracle dash` | Live colored TUI dashboard (refreshes ~2 s) |

Every subcommand accepts `--config PATH` to override the default config location.

## Colors

Output is colored by **severity** (the gauge gradient: green → lime → orange → red
as projected usage rises) with a violet accent for headers. Color is applied only at
output, so piped output stays clean.

- `NO_COLOR=1` disables color everywhere.
- `FORCE_COLOR=1` forces color on non-TTY interactive output.

## Works with agentic-sage

Oracle writes a stable `forecast.json`; [agentic-sage](https://github.com/muslewski/agentic-sage)
can optionally surface it via its `tokenForecastPath` config key. Each tool works
fully standalone — token prediction is an *optional* input to session awareness.
See [SETUP.md § Optional integrations](SETUP.md#optional-integrations) for the
one-line wiring step.

## License

MIT — Copyright (c) Mateusz Muślewski.
