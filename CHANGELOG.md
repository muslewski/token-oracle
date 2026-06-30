# Changelog

All notable changes to token-oracle are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-06-30

### Added

- Initial release: provider-agnostic token usage-cap forecaster
- Claude Code source adapter (reads `~/.claude/usage/` JSONL logs)
- Generic sliding-window forecast engine
- Tmux and statusline output adapters
- Interactive dashboard (`token-oracle dashboard`)
- Doctor command (`token-oracle doctor`)
- 71 unit tests; zero runtime dependencies

[Unreleased]: https://github.com/muslewski/token-oracle/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/muslewski/token-oracle/releases/tag/v0.1.0
