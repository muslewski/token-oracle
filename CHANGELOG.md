# Changelog

All notable changes to token-oracle are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1](https://github.com/muslewski/token-oracle/compare/token-oracle-v0.1.0...token-oracle-v0.1.1) (2026-06-30)


### Features

* **adapters:** thin statusline + tmux reference renderers ([9050cfb](https://github.com/muslewski/token-oracle/commit/9050cfb0a3399bea45233d5aff02019480cfa83d))
* **cli:** oracle forecast/snapshot/statusline/tmux/doctor/dash ([f0144e8](https://github.com/muslewski/token-oracle/commit/f0144e82b04efce0e2da71f3c0f518219e1ddd91))
* **colors:** central palette, gauge thresholds, terminal gating ([21fd5a3](https://github.com/muslewski/token-oracle/commit/21fd5a361d324834cf6112e10396b08155e16be5))
* **core:** atomic aggregation cache + event collection ([8b04b4c](https://github.com/muslewski/token-oracle/commit/8b04b4cbe7a691909734052ed47bc59782b80a91))
* **core:** config loader + max20 preset + XDG paths ([b3cec08](https://github.com/muslewski/token-oracle/commit/b3cec08f89bb6fee86c2da7fabe6c8bf6632b1c5))
* **core:** forecast facade orchestrating source-&gt;cache-&gt;windows ([a058dc8](https://github.com/muslewski/token-oracle/commit/a058dc81bd5b8d82ccb3853cbe1c7562039657dc))
* **core:** generalized window forecast + eta_to_cap ([9c651e1](https://github.com/muslewski/token-oracle/commit/9c651e1fecefc6bd4d328a7f17bbb16083e32b92))
* **core:** neutral UsageEvent/Window/Forecast contracts ([d96370b](https://github.com/muslewski/token-oracle/commit/d96370bd1327f2f9c6f2d841ff78c3d793657876))
* **core:** pattern-aware burn profile (decay + EB shrinkage) ([4126292](https://github.com/muslewski/token-oracle/commit/4126292568f2053f0b46cf06130e0b3f942a0148))
* **core:** time parsing + display formatters ([580ff24](https://github.com/muslewski/token-oracle/commit/580ff2418bb46cc83765453d767c4ed2b9966da4))
* **dashboard:** minimal stdlib forecast TUI ([7997d01](https://github.com/muslewski/token-oracle/commit/7997d012ebdfcb49072f9bf03f8cd70d5f964354))
* **dash:** colored block-bar TUI with violet header, dim metadata ([98ff6e1](https://github.com/muslewski/token-oracle/commit/98ff6e13be5dac0a61d45be9309275035b87e9d2))
* **doctor:** badge rows with real checks + ok/attention footer ([585160f](https://github.com/muslewski/token-oracle/commit/585160f1febf1bc0ccd7bde038be96fe178f24a5))
* **install:** reversible non-clobbering installer + uninstaller ([eda808c](https://github.com/muslewski/token-oracle/commit/eda808cd551cb0254e401fa38d0494a2b252d87c))
* rename importable package oracle → token_oracle; add token-oracle console script ([041e6de](https://github.com/muslewski/token-oracle/commit/041e6dec7c73e3b00954b40db48f11960b8f0d40))
* scaffold token-oracle package + packaging ([35c598b](https://github.com/muslewski/token-oracle/commit/35c598b9d8087fe47472d21d0fa39ca50c31d8d5))
* **snapshot:** versioned forecast.json contract writer ([2dd9330](https://github.com/muslewski/token-oracle/commit/2dd93308b51896cb58e2c38d2f844e1af6a2f081))
* **sources:** generic stub source for custom feeders ([c049f9d](https://github.com/muslewski/token-oracle/commit/c049f9d024703535b72a66031c6641bfa31c3f8c))
* **sources:** source registry + claude_code adapter ([a3ea851](https://github.com/muslewski/token-oracle/commit/a3ea8510fd0dee83f25bc4ef6e2db4957a36e9aa))


### Bug Fixes

* correct author attribution to Mateusz Muślewski ([a3ff011](https://github.com/muslewski/token-oracle/commit/a3ff011ba92aa2d3c33ad6ef81ca982a6e01fb2c))
* correct README to real CLI surface, publish trigger, command-name coherence ([98dce68](https://github.com/muslewski/token-oracle/commit/98dce6845b550ff0770a23a19475d9b345729fb2))
* **engine:** cache events for warm replay (source-agnostic); annotations, doc counts, hidden --now ([886c296](https://github.com/muslewski/token-oracle/commit/886c2966c59fec29ed7042ee117a5b754f5b305a))
* **sources:** bound scan output to [now-window, now]; gitignore bytecode ([6f60f00](https://github.com/muslewski/token-oracle/commit/6f60f003b7cf0358a63917c674f7270e62f9dcc1))


### Documentation

* add repo hygiene — CONTRIBUTING, CoC, SECURITY, templates, dependabot, CHANGELOG ([bfec45e](https://github.com/muslewski/token-oracle/commit/bfec45ef1f2fc4b92730762a1e841deb7a62f7f9))
* polished README (badges, acronym tagline, colors section) ([6acbff3](https://github.com/muslewski/token-oracle/commit/6acbff3f55abeb65deb56f5744237efb6bd60f5b))
* presentation-polish design spec ([b0de524](https://github.com/muslewski/token-oracle/commit/b0de524cb4a56c6ae90b118dcc215d2523260beb))
* presentation-polish implementation plan ([0e8dafd](https://github.com/muslewski/token-oracle/commit/0e8dafdc52286a0ff91d2bc611a4aeee805f710a))
* README, SETUP, AGENTS, ADAPTERS ([23204d9](https://github.com/muslewski/token-oracle/commit/23204d9f30b0fe34f5d41dc02edfee26768edb07))
* rewrite README — badge row, how-it-works, token-oracle command, fix copyright ([c98995f](https://github.com/muslewski/token-oracle/commit/c98995f69f4252ca1d8ace9adf0b805576a1d6e8))
* rewrite README from authoritative spec (badges, install, dify structure) ([99c6aa8](https://github.com/muslewski/token-oracle/commit/99c6aa8d6dd9971cf30db03b4c7b6adbf7492182))
* tighten Task 13 statusline test assertion ([880df8e](https://github.com/muslewski/token-oracle/commit/880df8ec681c7cc4814397f27e083b1274ecfe0c))
* token-oracle design spec ([bfc71a9](https://github.com/muslewski/token-oracle/commit/bfc71a906ce09f16de49c2bab7d91f40bb2cd429))
* token-oracle implementation plan (16 tasks, TDD) ([1f95caf](https://github.com/muslewski/token-oracle/commit/1f95caf1a514f4c13fcd34cadd4deabbe12a418d))

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
