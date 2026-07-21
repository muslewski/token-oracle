# token-oracle — overview

**token-oracle** (CLI: `token-oracle` / `oracle`) is an offline-first Observed-Rate
Allowance & Cap-Limit Estimator: it reads local Claude Code and Grok Build usage
logs, estimates burn rate and time-to-cap, optionally verifies against the
provider sites via a Playwright live layer, and surfaces results in forecast /
report / statusline / tmux / full-screen dash TUI. No provider API keys for the
core path; multi-subscription profiles track Claude + Grok side-by-side.

## Seeded zones (2026-07-21 atlas-seed)

| Zone | Owns | Purpose |
|------|------|---------|
| [[core]] | `token_oracle/core/**`, `snapshot/**` | Config, engine, windows, pricing, report, forecast.json |
| [[cli]] | `token_oracle/cli/**` | Subcommand entrypoints and colors |
| [[sources]] | `token_oracle/sources/**` | Claude / Grok / generic log scanners |
| [[dashboard]] | `token_oracle/dashboard/**` | Past / Present / Future TUI |
| [[live]] | `token_oracle/live/**` | Browser probe, extractors, trust overlay |
| [[adapters]] | `token_oracle/adapters/**`, `ADAPTERS.md` | Statusline / tmux consumers + contracts |
| [[install]] | installers + `npm/**` | curl/npm/PyPI distribution shims |

All cards: `status: seeded`, `verifiedAt: unverified` until a reviewed stamp pass.

## Out of zone (for now)

- `tests/**` — characterization suite (not a product surface zone)
- `assets/**`, `demo/**` — marketing gifs / vhs tapes
- `docs/**`, `plans/**` — launch notes and implementation plans (route plans into vault `plans/` when adopted)
- `pyproject.toml` / CI — packaging meta, claimed later if needed
