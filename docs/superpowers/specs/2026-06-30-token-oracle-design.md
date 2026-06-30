# token-oracle — Design

**Date:** 2026-06-30
**Status:** Design approved (2026-06-30). Ready for implementation plan.
**Name:** `token-oracle` — **ORACLE** = *Observed-Rate Allowance & Cap-Limit Estimator*.
Companion to `agentic-sage` (**SAGE** = Session Awareness & Guidance Engine); same
"agnostic core + adapters" shape, divination theme (a pattern-reading oracle).

---

## 0. Thesis

A **provider-agnostic engine that forecasts when you will hit a usage cap before its
reset**, learned from your own observed burn patterns. The engine is the product. UIs
(statusline, tmux, dashboard) are **optional consumers**. The forecast targets a
**user-defined reset/end moment** — never a hardcoded Claude-specific window.

Extracted from a working personal system in `~/.claude/` (`usage_limits.py`,
`claude_sessions.py`, `statusline-context.py`, `session-sync.py`, `session-dash.py`),
generalized for open source.

## 1. Goals / Non-goals

**Goals**
- Pure, dependency-free forecast **core** that operates only on neutral usage events.
- **Provider-agnostic input** from day one: a `Source` interface; Claude Code is the
  first source adapter, not a baked-in assumption.
- **Fully configurable forecast target**: arbitrary windows defined by `cap` +
  (`length` or `reset_anchor`) + `horizon`. The user sets the "reset/end moment".
- Self-sufficient repo: its own `oracle` CLI + a TUI dashboard, runnable day one.
- Loose, optional, file-contract coupling with `agentic-sage` — each works alone.
- OSS-ready: `README.md`, `SETUP.md`, `AGENTS.md`, `ADAPTERS.md`, MIT, reversible install.

**Non-goals (v1)**
- The polished, customizable status bar — a **separate future OSS project**. This repo
  ships only thin reference adapters.
- A trained ML model — leave a clean seam; v1 forecast is statistical (burn profile).
- Non-Claude source adapters beyond a documented stub.

## 2. Architecture — three rings, one rule

```
 SOURCE ADAPTERS          CORE ENGINE (pure math)         CONSUMERS
 (input, pluggable)       (neutral events only)           (output, optional)
┌────────────────────┐   ┌─────────────────────────┐   ┌──────────────────────┐
│ claude-code source │──►│ ingest → normalize       │──►│ oracle CLI (here)    │
│  (reads jsonl)     │   │ build burn profile       │   │ TUI dashboard (here) │
│ generic stub       │──►│ compute_window(cap,reset)│──►│ statusline ref-adapter│
│  (custom feeders)  │   │ eta_to_cap / projected % │   │ tmux ref-adapter     │
└────────────────────┘   └─────────────────────────┘   │ JSON snapshot ───────┼─► sage / future status-bar
                          config: caps, windows,        └──────────────────────┘
                          reset anchor, horizon
```

**One rule:** the core never imports a source or a consumer. Sources produce neutral
`UsageEvent`s; consumers read a neutral `Forecast`. Either ring swaps without touching
the math.

## 3. Neutral contracts (the universality)

### `UsageEvent` (input)
```
{ timestamp: epoch_seconds, tokens: int, model: str|None,
  session_id: str|None, kind: str|None }
```
A source adapter's only job is to emit these. `model` and derived work-hour signals
become forecast **features**, not Claude assumptions. The Claude Code adapter is
today's jsonl reader repackaged behind this contract.

### `Window` config (target)
```
{ cap: int, length_secs: int|None, reset_anchor: iso8601|None, horizon_secs: int }
```
Generalizes today's hardcoded 5h-block + weekly into **arbitrary** windows. Either a
rolling `length_secs` window or an absolute `reset_anchor` defines the "reset/end
moment" the forecast targets. Claude's `max20` caps ship as **one preset**, not law.
A config can declare multiple named windows (e.g. `short`, `weekly`, or anything).

### `Forecast` (output)
```
{ window: str, used: int, cap: int, projected_pct: float,
  eta_to_cap_secs: int|None, reset_in_secs: int, confidence: float }
```
Pure data — no ANSI, no formatting. Consumers render. `eta_to_cap_secs` answers the
core question: *when, at current learned burn, do I hit the cap.* `None` ⇒ not on track
to hit it before reset.

## 4. Core engine (port + generalize)

Port from `usage_limits.py` (the burn engine) and the forecast functions of
`claude_sessions.py` (`eta_to_cap`, `usage_blocks`, formatters). Keep **stdlib-only,
zero deps**; never raises to the caller.

- **Burn profile** (kept from the proven engine): hour-of-week buckets (168), recency
  decay (configurable half-life), empirical-Bayes shrinkage. This is the
  "pattern-aware" prior — what makes the forecast yours, not a naive linear extrapolation.
- **`compute_window(events, now, window, profile)`** — generalizes `compute_block` /
  `compute_weekly` into one function over any `Window`.
- **`eta_to_cap(used, projected_pct, time_left, cap)`** — preserved.
- **Aggregation cache** (`usage-cache.json`-style): the 30s aggregate gate + atomic
  replace, generalized; cache path configurable, not `~/.claude`-bound.
- **Config** loaded from a documented file (caps, windows, reset anchor, horizon,
  source selection); Claude defaults shipped as a preset.
- **ML seam:** the profile builder is one swappable function. v1 = statistical; later a
  learned model implements the same signature. Optional deps live behind an extra.

## 5. What lives in this repo

| Piece | What | Status |
|---|---|---|
| `core/` | engine: ingest, normalize, profile, `compute_window`, `eta_to_cap`, cache, config | required |
| `sources/claude_code.py` | first source adapter (jsonl reader → `UsageEvent`) | required |
| `sources/generic.py` | documented stub for custom feeders | required (stub) |
| `oracle` CLI | query forecast, manage config/presets, `oracle doctor`, write snapshot | required |
| `dashboard` (TUI) | prediction-focused popup, port of `session-dash.py` | required |
| `adapters/statusline.py` | **thin reference** Claude Code statusline renderer | reference only |
| `adapters/tmux.py` | **thin reference** tmux statusbar renderer | reference only |
| `snapshot` | writes `forecast.json` for external consumers | required |

Polished/customizable status bar = **separate future project**; these adapters exist
only to prove the engine renders anywhere and to give day-one visible output.

## 6. Sage ↔ Oracle convention (loose, optional)

Separate projects, **wired by a file contract** — no shared code, no hard dependency.

- **Oracle → Sage:** Oracle writes `~/.local/share/token-oracle/forecast.json` (the
  snapshot). Sage *optionally* reads it — it already has `tokenForecastPath` + a doctor
  check; reuse exactly that, now pointing at a **documented, stable schema**.
- **Sage → Oracle (optional, later):** Sage exposes per-session `{model, effort}`;
  Oracle may ingest it as a forecast feature via the optional session-context
  descriptor. Neither tool requires the other.
- Each tool works 100% standalone. Docs cross-link with a "works great with…" note.
  Conceptually: token prediction is an **optional input to session awareness**, not part
  of it. That is the entire overlap — it earns its keep and stays clean.

## 7. OSS packaging (mirror agentic-sage)

- `README.md` — §0 thesis, quickstart, parts-&-options table (what each piece is, need
  it?, how to turn on), works-with-sage note.
- `SETUP.md` — tiers + the exact config to run; optional integrations.
- `AGENTS.md` — deterministic setup runbook so a coding agent can install/enable/wire/verify.
- `ADAPTERS.md` — the `Source` and `Consumer` interfaces + how to write one.
- `LICENSE` — MIT. Publish-shaped packaging. Reversible install.
- **Installer: Python-native** (pipx/uv installable + a `setup`/`doctor` command),
  since the core is Python — diverges from sage's `install.mjs` intentionally.

## 8. Testing approach

- Core math: pure functions over synthetic event lists — golden tests for
  `compute_window`, `eta_to_cap`, profile decay/shrinkage at known inputs.
- Source adapter: fixture jsonl → expected `UsageEvent` stream.
- Snapshot schema: round-trip + schema-stability test (the Sage contract must not drift
  silently).
- Reference adapters: render-from-`Forecast` smoke tests (no engine coupling).
- Installer: non-clobber + reversible, mirroring sage's install discipline.

## 9. File inventory (target)

```
token-oracle/
  core/            engine.py  profile.py  windows.py  config.py  cache.py  contracts.py
  sources/         claude_code.py  generic.py
  adapters/        statusline.py  tmux.py
  cli/             oracle (entry)  doctor
  dashboard/       app.py
  snapshot/        writer.py
  README.md  SETUP.md  AGENTS.md  ADAPTERS.md  LICENSE  pyproject.toml
  docs/superpowers/specs/2026-06-30-token-oracle-design.md
  test/
```
(Layout indicative; finalize in the implementation plan.)

## 10. Open questions (deferred to plan)

- Exact snapshot JSON schema version field + location default (XDG vs `~/.claude`).
- CLI command surface (`forecast`, `config`, `doctor`, `snapshot`, `dash`?).
- Whether v1 ships one Claude `max20` preset or a small preset library.
