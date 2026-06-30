# Contributing to token-oracle

Bug reports and pull requests are welcome. Please read this before opening an issue or PR.

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
