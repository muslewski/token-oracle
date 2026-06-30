# 🔮 token-oracle

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)

**O**bserved-**R**ate **A**llowance **&** **C**ap-**L**imit **E**stimator — a
provider-agnostic engine that forecasts **when you'll hit a usage cap before its
reset**, learned from your own observed burn patterns. Companion to
[agentic-sage](https://github.com/muslewski/agentic-sage).

> The engine is the product. UIs — statusline, tmux, dashboard — are optional
> consumers of a neutral `Forecast`. Zero dependencies, stdlib only, Python 3.10+.

## Quickstart

```bash
pipx install token-oracle        # or: pip install token-oracle
oracle doctor                    # config + source + windows, with ✓/✗ checks
oracle forecast                  # human status line
oracle forecast --json           # the snapshot schema
oracle dash                      # live colored TUI
```

Works out of the box with Claude Code (`claude_code` source, selected by default).
Other providers feed in via the `generic` source or a custom adapter.

## Parts & options

| Part | What it does | Need it? |
|---|---|---|
| core engine | forecast math (burn profile + window math) | required |
| `claude_code` source | reads `~/.claude/projects/*/*.jsonl` | default source |
| `generic` source | feed your own `[[ts, tokens]]` JSON file | optional |
| `oracle` CLI | `forecast` / `snapshot` / `doctor` / statusline / tmux | required |
| TUI dashboard (`oracle dash`) | live colored forecast view, refreshes ~2 s | optional |
| statusline adapter | ANSI status-line reference renderer | optional |
| tmux adapter | tmux-formatted line reference renderer | optional |
| snapshot (`forecast.json`) | stable JSON contract for external consumers | optional |

See [SETUP.md](SETUP.md) for full configuration reference.
See [ADAPTERS.md](ADAPTERS.md) for the source and consumer interfaces.
See [AGENTS.md](AGENTS.md) for a deterministic coding-agent runbook.

## CLI reference

| Command | Description |
|---|---|
| `oracle forecast` | Human status line |
| `oracle forecast --json` | Print the full snapshot JSON |
| `oracle snapshot [--out PATH]` | Write `forecast.json`, print path |
| `oracle statusline` | ANSI status line (reference adapter) |
| `oracle tmux` | tmux-formatted line (reference adapter) |
| `oracle doctor` | Config, source, cache, windows — with ✓/✗ checks |
| `oracle dash` | Live colored TUI dashboard (refreshes ~2 s) |

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

MIT — Copyright (c) Kento.
