# Plan 017: Pricing table, cost engine, and plan presets (pro / max5 / max20)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ada32e9..HEAD -- token_oracle/core/config.py token_oracle/core/events.py tests/test_config.py SETUP.md`
> Plan 016 MUST be DONE first — verify `token_oracle/core/events.py` exists
> and events carry 8 fields. If plan 008 landed, `main.py` has `init`/`clean`
> branches — irrelevant here but expect it in diffs. On excerpt mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW (new pure module + additive config keys; no existing behavior changes)
- **Depends on**: plans/016-event-detail-contract-v2.md (DONE required)
- **Category**: direction
- **Planned at**: commit `ada32e9`, 2026-07-02

## Why this matters

token-oracle has zero cost code: no prices, no USD, no plan concept beyond a
single hardcoded `max20` preset. The two dominant competitors treat cost as
table stakes: ccusage (16.7k★) defines the de-facto standard cost modes
(`auto`/`calculate`/`display`) with an offline bundled price snapshot and a
user override file; Claude-Code-Usage-Monitor (8.3k★) ships plan presets
(`pro`≈19k, `max5`≈88k, `max20`≈220k tokens per 5h window). This plan adds a
stdlib-only pricing module, cost aggregation over the v2 events from plan 016,
and the missing presets — the engine layer that the past view (plan 019), the
future view (plan 020), and the configurator (plan 021) render.

## Current state

- `token_oracle/core/config.py:12-20` — the only preset:

  ```python
  PRESETS = {
      "max20": {
          "source": "claude_code",
          "windows": [
              {"name": "5h", "cap": 220000, "period_secs": 18000},
              {"name": "weekly", "cap": 8000000, "period_secs": 604800, "anchor": None},
          ],
      },
  }
  ```

- `load_config()` (config.py:68-107) starts from `dict(PRESETS["max20"])`,
  overlays the user JSON, accumulates human-readable strings into
  `Config.issues` instead of raising (convention from plan 001 — every new
  config key must follow it; see `_window_from_dict` config.py:45-65 and the
  issue-appending pattern at config.py:84-99).
- `Config` dataclass (config.py:23-29): `source, source_opts, cache_path,
  windows, issues`.
- After plan 016, events are 8-field records
  `[ts, tok, model, input, output, cache_create, cache_read, cost_usd]`
  (`token_oracle/core/events.py`); `cost_usd` is the transcript's `costUSD`
  when present, else `None`.
- No file in `token_oracle/` mentions price/cost/USD (verified by grep at
  plan time).
- Conventions: stdlib only; module-opening invariant docstrings; core never
  imports `cli/colors.py`; tests function-style pytest (exemplar
  `tests/test_config.py`).

## Design (decided — do not redesign)

**New module `token_oracle/core/pricing.py`** — pure, stdlib, no I/O except
reading overrides passed in from config (no network, ever):

- `SNAPSHOT`: dict mapping model-id *prefixes* to USD per **million** tokens:
  `{"input": float, "output": float, "cache_write": float, "cache_read": float}`.
  Prefix matching (longest prefix wins) because transcript model ids carry
  date suffixes (e.g. `claude-haiku-4-5-20251001`).
- Seed rows (VERIFY against https://docs.claude.com/en/docs/about-claude/pricing
  at execution time — see toolkit note; these are plan-time values):
  - `claude-opus-4`: input 15, output 75
  - `claude-sonnet-4`: input 3, output 15
  - `claude-haiku-4-5`: input 1, output 5
  - cache_write = 1.25 × input, cache_read = 0.10 × input for each row
  - add whatever current-generation ids the docs list (e.g. Claude 5 family)
- `resolve(model, overrides=None) -> dict | None` — longest-prefix lookup,
  overrides (same shape, exact-or-prefix keys) win over SNAPSHOT; `None` for
  unknown/`None` model.
- `event_cost(event, mode="auto", overrides=None) -> float | None`:
  - `auto`: use `event[7]` (`cost_usd`) when not None, else calculate
  - `calculate`: always compute from token classes × resolved prices
  - `display`: only ever use `event[7]`
  - computation: `(input*p_in + output*p_out + cache_create*p_cw + cache_read*p_cr) / 1e6`
  - returns `None` when the needed price is unresolvable (caller aggregates
    unpriced tokens separately — never silently $0).
- `cost_summary(events, mode, overrides) -> dict` with keys
  `{"usd": float, "unpriced_tokens": int, "by_model": {model: usd}}`.

**Config additions** (all optional, all validated accumulate-not-raise):

- `"plan"`: preset name. `load_config` resolution order becomes:
  built-in `max20` defaults → `PRESETS[plan]` if `plan` present and known
  (unknown → issue, keep max20) → explicit top-level keys from the file
  (`windows`, `source`, … keep winning over the preset, exactly as today).
- `"cost_mode"`: `"auto" | "calculate" | "display" | "off"`, default `"auto"`;
  invalid value → issue + fallback `"auto"`.
- `"pricing"`: dict of model-prefix → per-Mtok price dict, passed to
  `pricing.resolve` as overrides; non-dict → issue + ignored.
- New `Config` fields: `plan: str = "max20"`, `cost_mode: str = "auto"`,
  `pricing: dict = field(default_factory=dict)`.

**New presets** in `PRESETS` (numbers from ccmonitor, the 8.3k★ reference;
5h caps are its published approximations, weekly caps are proportional
estimates — mark them as such in SETUP.md and make them user-overridable like
everything else):

```python
"pro":  {"source": "claude_code", "windows": [
    {"name": "5h", "cap": 19000, "period_secs": 18000},
    {"name": "weekly", "cap": 700000, "period_secs": 604800, "anchor": None}]},
"max5": {"source": "claude_code", "windows": [
    {"name": "5h", "cap": 88000, "period_secs": 18000},
    {"name": "weekly", "cap": 3200000, "period_secs": 604800, "anchor": None}]},
```

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass |
| Lint | `ruff check token_oracle/ && ruff format --check token_oracle/` | exit 0 |
| Types | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |

## Suggested executor toolkit

- If a `claude-api` skill or https://docs.claude.com/en/docs/about-claude/pricing
  is reachable, verify/update the SNAPSHOT seed rows before writing them. If
  offline, keep the plan-time values above and add a comment
  `# snapshot verified 2026-07-02; update on model releases`.

## Scope

**In scope**:
- `token_oracle/core/pricing.py` (create)
- `token_oracle/core/config.py` (presets + 3 new keys + Config fields)
- `tests/test_pricing.py` (create), `tests/test_config.py` (extend)
- `SETUP.md` (config fields + presets tables), `README.md` (one line in the
  feature list mentioning cost + presets)

**Out of scope**:
- Any rendering of cost (dashboard/CLI) — plans 019/020.
- `Forecast` dataclass, `snapshot/writer.py` — external contract unchanged.
- Network fetches of prices (explicitly rejected; see
  `plans/research-competitive-landscape.md`).
- `install.py` / `init` behavior (plan 008/021 own preset *selection* UX).

## Git workflow

- Branch: `advisor/017-pricing-cost-engine-presets`
- Conventional commits, e.g. `feat(core): pricing snapshot + cost modes + plan presets`
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: `core/pricing.py` + `tests/test_pricing.py`

Implement the module per Design. Tests: prefix resolution (exact id with date
suffix resolves; unknown returns None), longest-prefix beats shorter,
overrides win, `event_cost` in all four modes (incl. `display` with
`cost_usd=None` → None), `cost_summary` sums, groups by model, and counts
unpriced tokens for an unknown model.

**Verify**: `python -m pytest -q tests/test_pricing.py` → all pass.

### Step 2: presets + config keys

Extend `PRESETS`, `Config`, and `load_config` per Design. The `plan` overlay
must be: `raw = dict(PRESETS["max20"]); raw.update(PRESETS.get(plan_from_file, {}))
` — careful: `plan` is read from the file *before* the general overlay, and
explicit file keys still win afterwards (write it as: parse file → pick plan →
rebuild `raw` as max20 ∪ preset ∪ file-data). Unknown plan name appends an
issue and keeps max20 windows.

Extend `tests/test_config.py` (match its existing style — small focused
functions writing tmp JSON): `plan: "pro"` yields the 19000 cap; unknown plan
→ issue + max20 caps; file `windows` override a chosen plan's windows;
bad `cost_mode` → issue + `"auto"`; `pricing` non-dict → issue + `{}`.

**Verify**: `python -m pytest -q tests/test_config.py` → all pass.

### Step 3: docs

SETUP.md: add `plan`, `cost_mode`, `pricing` rows to the Fields table; add a
"Plan presets" section with a 3-row table (pro/max5/max20, caps, and the
sentence "5h caps follow Claude-Code-Usage-Monitor's published approximations;
weekly caps are proportional estimates — override `windows` for exact
values."). README.md: extend the feature bullets with cost/plan support.

**Verify**: `grep -n "cost_mode" SETUP.md` → hits;
`python -m pytest -q` → all pass.

## Test plan

- `tests/test_pricing.py`: ~8 cases listed in Step 1.
- `tests/test_config.py`: +5 cases listed in Step 2.
- Pattern: `tests/test_config.py` function style.
- Verification: `python -m pytest -q` all green.

## Done criteria

- [ ] `python -m pytest -q` exits 0
- [ ] `ruff check`, `ruff format --check`, `mypy` (as in commands table) exit 0
- [ ] `python - <<'EOF'` prints a float and `None`:
  ```python
  from token_oracle.core.pricing import event_cost
  print(event_cost((0.0, 10, "claude-sonnet-4-5-20250929", 1000000, 0, 0, 0, None), "calculate"))
  print(event_cost((0.0, 10, "mystery-model", 5, 5, 0, 0, None), "calculate"))
  EOF
  ```
- [ ] `load_config` on a file containing `{"plan": "pro"}` returns a Config
  whose first window cap is 19000 (write a throwaway check or rely on the
  new test)
- [ ] `git status` clean outside in-scope list; `plans/README.md` row updated

## STOP conditions

- `token_oracle/core/events.py` does not exist (plan 016 not landed).
- The preset-overlay ordering in Step 2 cannot preserve the existing
  behavior "file keys win over preset" without breaking an existing
  test in `tests/test_config.py` — report which test.
- You are tempted to add a network call for prices — that is out of scope.

## Maintenance notes

- The SNAPSHOT rots as models ship: updating it is a two-line PR; consider a
  CI reminder. Users bridge gaps via the `pricing` override key meanwhile.
- Plan 019 consumes `cost_summary`; plan 021 lists `PRESETS` keys in the
  wizard — keep preset dicts flat and JSON-serializable.
- Reviewer focus: overlay ordering (max20 ∪ preset ∪ file), unpriced-token
  accounting (must never silently count as $0).
- Deferred: `auto` weekly-cap discovery from history (plan 023 does P90 caps).
