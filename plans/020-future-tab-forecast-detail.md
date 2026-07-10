# Plan 020: Future tab — the Oracle actually prophesies

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ada32e9..HEAD -- token_oracle/dashboard/ token_oracle/core/profile.py token_oracle/core/windows.py tests/test_dashboard.py`
> Plan 018 MUST be DONE (tab dispatch with a "future" placeholder exists).
> Plans 016/017/019 landing first is expected drift. `profile.py` /
> `windows.py` must be byte-identical to the excerpts below; on mismatch, STOP.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW (pure renderers over existing math; no core changes)
- **Depends on**: plan 018 (TUI shell). Soft: 017 (cost line renders only if pricing landed), 012 (real confidence — display-ready either way)
- **Category**: direction
- **Planned at**: commit `ada32e9`, 2026-07-02

## Why this matters

The projection math is token-oracle's crown jewel — a 168-bucket
hour-of-week burn profile with recency decay and empirical-Bayes shrinkage,
blended with the live window rate — but the UI shows one number (`projected
%`). The 8.3k★ Claude-Code-Usage-Monitor markets far shallower math as "ML
predictions" and "Session Forecasting". This plan renders what the engine
already knows: per-window projection detail, an expected-burn sparkline for
the next 24 h from the profile, plain-language prophecy lines, and
observational threshold warnings (80 %/100 % — never blocking, per
tokentelemetry's model; see `plans/research-competitive-landscape.md`).

## Current state

- After plan 018: `token_oracle/dashboard/app.py` has a tab→renderer dict
  with "future" → `render_placeholder`; pure renderers take
  `(…, width, enabled)`; loop refreshes forecasts ~1×/s.
- `Forecast` (core/contracts.py:24-32): `window, used, cap, projected_pct,
  eta_to_cap_secs (float|None), reset_in_secs, idle, confidence (=1.0
  hardcoded until plan 012)`.
- Profile access: the engine caches it — `load_cache(cfg.cache_path)`
  returns a dict with `"profile"` = list of 168 floats (tok/s per
  hour-of-week bucket), possibly `[]` when unbuilt
  (core/cache.py:11-21; engine.py:26 `profile = cache.get("profile") or None`).
- `token_oracle/core/profile.py:71-81`:

  ```python
  def profile_integral(profile, start, end):
      """Expected tokens over [start, end) given a 168-bucket tok/s profile."""
  ```

  — pure, importable by the dashboard (dashboard may import core; never the
  reverse).
- `bucket_key(ts)` (core/timeutil.py:16-19): local-time hour-of-week index.
- `eta_to_cap` semantics (core/windows.py:9-22): `None` = not heading over;
  `0.0` = already at/over cap.
- Colors: `gauge(text, pct, enabled)` colors by severity tier
  (colors.py:58-74); `M_WARN = "⚠"`.
- Formatters: `fmt_tokens`, `fmt_hms`, `fmt_dh_long` (timeutil.py).
- After plan 017 (if landed): `Config.cost_mode`, `Config.pricing`,
  `pricing.cost_summary(events, mode, overrides)`.

## Design (decided — do not redesign)

All pure renderers in `token_oracle/dashboard/app.py` (or
`dashboard/future.py` mirroring plan 019's choice):

**`render_future(forecasts, profile, now, width, enabled, cost_line=None)`**
per active (non-idle) window:

```
● 5h      ████████░░░░  78%        resets 2:14
  prophecy: at the current pace you reach 78% of cap before reset
  ⚠ cap in 1 day 3 hours            (only when eta_to_cap_secs is not None)
  next 24h  ▁▂▄▇█▆▃▁▁▂▄▆▅▃▂▁▁▂▃▅▇█▅▂   expected 96k tokens
```

- Line 1: reuse the bar/gauge idiom from `render_present`.
- Prophecy line (dim): template by state —
  `projected_pct < 80`: "at the current pace you reach {pct}% of cap before reset";
  `80 ≤ pct < 100`: "approaching the cap — {pct}% projected by reset";
  `pct ≥ 100` with eta: "the cap falls in {fmt_dh_long(eta)} at this pace";
  `idle`: "the {name} window sleeps · resets in {fmt_hms}".
  These exact templates are the product voice — keep the oracle flavor.
- Warning line: render only when `eta_to_cap_secs is not None`; colored via
  `gauge(..., pct, enabled)`. Observational only — nothing blocks.
- Sparkline: `spark_next24(profile, now)` — new pure helper: for each of the
  next 24 hours compute `profile_integral(profile, t, t+3600)`, scale to the
  8-level block ramp `" ▁▂▃▄▅▆▇█"` by max hour, join. Return `("", 0)` when
  profile is falsy → render a dim `(no burn history yet)` instead.
  `expected Nk tokens` = `fmt_tokens(sum)`.
- Confidence: when `f.confidence < 1.0` (plan 012 landed and computed), append
  dim `· confidence {int(f.confidence*100)}%` to the prophecy line. With the
  hardcoded 1.0, render nothing — do not show fake certainty.
- `cost_line`: optional pre-computed string the caller passes (see wiring);
  rendered dim at the panel bottom, e.g.
  `spend pace: ~$3.10/day over the last 7 days → ~$21.70/week`.

**Wiring** in `run()`: "future" tab pulls `cache = load_cache(cfg.cache_path)`
(reuse plan 019's 30 s refresh box if present) for the profile; if plan 017
landed and `cfg.cost_mode != "off"`, compute the cost line from the last 7
days of cached events via `pricing.cost_summary` (guard with a
`try/except ImportError` so this plan is executable before 017 — but if 017
is already DONE per the index, wire it directly without the guard).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass |
| Lint | `ruff check token_oracle/ && ruff format --check token_oracle/` | exit 0 |
| Types | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |
| Manual | `oracle dash` → arrow to Future | detail panel renders, sparkline visible with history |

## Scope

**In scope**:
- `token_oracle/dashboard/app.py` (future renderer + wiring; or
  `dashboard/future.py`)
- `tests/test_dashboard.py` (extend)
- `README.md` (one feature bullet)

**Out of scope**:
- `core/` — everything needed is importable; zero core changes.
- Changing `Forecast` fields or confidence computation (plan 012's spike).
- Notification/bell/desktop alerts — warnings are visual lines only.
- Past tab, report, configurator.

## Git workflow

- Branch: `advisor/020-future-tab-forecast-detail`
- Conventional commits, e.g. `feat(dash): future tab — projection detail + prophecy lines`
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: `spark_next24` + prophecy templates + tests

Pure helpers first. Tests (extend `tests/test_dashboard.py`, existing
fixture style): flat profile (all buckets equal) → all-equal spark chars;
empty profile → `("", 0)`; a profile with one hot bucket → `█` at that
position; prophecy template per state (under-80, 80–99, ≥100-with-eta, idle)
asserts the exact key phrases ("current pace", "approaching", "the cap
falls", "sleeps").

**Verify**: `python -m pytest -q tests/test_dashboard.py` → all pass.

### Step 2: `render_future` + tab wiring

Assemble per Design; replace the "future" placeholder in the dispatch.
Tests: window name + pct + reset present; warning line only when eta set;
color-off output has no `\033`; confidence suffix absent at 1.0 and present
at 0.7; cost_line renders when passed and is absent when None.

**Verify**: `python -m pytest -q` → all pass. Manual smoke: Future tab in
`oracle dash` (report what rendered in the completion note).

### Step 3: README bullet

One line under features: prophecy/forecast detail view.

**Verify**: `grep -in "prophecy\|future tab" README.md` → hit; suite green.

## Test plan

- `tests/test_dashboard.py`: ~9 new cases across Steps 1–2.
- Pattern: existing `test_dashboard.py` (build Forecast fixtures, substring
  asserts, `\033` discipline).
- Verification: `python -m pytest -q` → all pass.

## Done criteria

- [ ] `python -m pytest -q` exits 0
- [ ] `ruff check`, `ruff format --check`, `mypy` exit 0
- [ ] `grep -n "confidence" token_oracle/dashboard/*.py` shows the <1.0 gate
- [ ] Color-off discipline test for `render_future` exists and passes
- [ ] Manual Future-tab smoke reported
- [ ] `git status` clean outside in-scope list; `plans/README.md` row updated

## STOP conditions

- Plan 018's tab dispatch doesn't exist or differs structurally (drift).
- You need to modify anything under `token_oracle/core/` to render — the
  data is all reachable; report the gap instead.
- `profile_integral` performance is visibly poor in the render loop (it
  won't be — 24 calls over 168 floats — but if profiling says otherwise,
  report; do not add caching layers).

## Maintenance notes

- Plan 012 (real confidence) lights up the confidence suffix automatically —
  the <1.0 gate is the contract; 012's executor should know it exists.
- Plan 023 (P90 auto-caps) changes cap values, not this rendering.
- Prophecy templates are product voice — reviewer should read them aloud;
  wording changes are cheap now, expensive after screenshots circulate.
- Deferred: weekly spend *projection* from profile × recent $/token blend
  (the cost_line shows measured pace only — projecting spend mixes model-mix
  assumptions into USD and needs its own design; note kept here so nobody
  half-adds it in review).
