# Contributing to token-oracle

Bug reports and pull requests are welcome. Please read this before opening an issue or PR.


## Community

| Kind | Where |
|---|---|
| Questions, ideas, show-and-tell | [Discussions](https://github.com/muslewski/token-oracle/discussions) |
| Bugs & concrete feature requests | [Issues](https://github.com/muslewski/token-oracle/issues/new/choose) |
| Security | [SECURITY.md](./SECURITY.md) — private only |

Please follow the [Code of Conduct](./CODE_OF_CONDUCT.md).

## Development setup

```bash
git clone https://github.com/muslewski/token-oracle.git
cd token-oracle
pip install -e ".[dev]"
```

## Running tests

```bash
pytest
```

## Lint and type check

```bash
ruff check token_oracle/
mypy token_oracle/ --ignore-missing-imports
```

## Project mind (informal knowledge base)

This repository keeps a small **[memory-atlas](https://github.com/muslewski/memory-atlas)** vault
(`token-oracle-mind/` at the repo root) — plain markdown that maps architecture for **humans and coding agents**.

| | |
|--|--|
| **Convention** | Informal and optional for tiny fixes — **appreciated** when you change how a subsystem works |
| **Why** | Better orientation, higher-quality agent-assisted edits, less “where does this live?” thrash |
| **Not npm** | The mind is **git-only**. It is not shipped in this project’s npm package (if any), and not downloaded when someone installs the separate `memory-atlas` CLI |

**How (when it matters):** open `token-oracle-mind/map/index.md` → read the zone you touch → update that zone if ownership or invariants moved → optional `npx memory-atlas stamp <slug>` after you verified → `npx memory-atlas build`. Honest short notes beat silence or fake stamps.

Skip without guilt for typos and drive-by nits. Prefer leaving a PR note if the mind should be updated later rather than inventing ceremony.

## Commit conventions

token-oracle uses [Conventional Commits](https://www.conventionalcommits.org/). release-please reads these to auto-bump versions and generate the changelog:

| Prefix | Version effect |
|--------|----------------|
| `feat: …` | bumps minor |
| `fix: …` | bumps patch |
| `docs: …` | no bump |
| `chore: …` | no bump |
| `ci: …` | no bump |

## Submitting a change

1. Fork the repo and create a branch from `main`.
2. Add or update tests for any changed behaviour.
3. Ensure `pytest`, `ruff check token_oracle/`, and `mypy token_oracle/ --ignore-missing-imports` all pass.
4. Open a pull request against `main`.

## License

By contributing you agree your work is released under the [MIT License](LICENSE).
