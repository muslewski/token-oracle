# token-oracle

**ORACLE** = *Observed-Rate Allowance & Cap-Limit Estimator*. A provider-agnostic
engine that forecasts **when you'll hit a usage cap before its reset**, learned from
your own observed burn patterns. Companion to [agentic-sage](https://github.com/muslewski/agentic-sage).

Zero dependencies — stdlib only. Python 3.10+.

## Quickstart

```bash
pipx install token-oracle        # or: pip install token-oracle
oracle doctor                    # show config + source + windows
oracle forecast                  # human status line
oracle forecast --json           # the snapshot schema
oracle dash                      # live TUI
```

Works out of the box with Claude Code (`claude_code` source, selected by default).
Other providers are supported via the `generic` source or a custom adapter.

## Parts & options

| Part | What it does | Need it? |
|---|---|---|
| core engine | forecast math (burn profile + window math) | required |
| `claude_code` source | reads `~/.claude/projects/*/*.jsonl` | default source |
| `generic` source | feed your own `[[ts, tokens]]` JSON file | optional |
| `oracle` CLI | `forecast` / `snapshot` / `doctor` / statusline / tmux | required |
| TUI dashboard (`oracle dash`) | live forecast view, refreshes ~2 s | optional |
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
| `oracle doctor` | Show config path, source, cache path, windows |
| `oracle dash` | Live TUI dashboard (refreshes ~2 s) |

Every subcommand accepts `--config PATH` to override the default config location.

## Works with agentic-sage

Oracle writes a stable `forecast.json`; [agentic-sage](https://github.com/muslewski/agentic-sage)
can optionally surface it via its `tokenForecastPath` config key. Each tool works
fully standalone — token prediction is an *optional* input to session awareness.
See [SETUP.md § Optional integrations](SETUP.md#optional-integrations) for the
one-line wiring step.

## License

MIT — Copyright (c) Kento.
