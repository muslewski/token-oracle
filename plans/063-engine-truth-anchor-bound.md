# Engine truth — present-truth anchor & bound Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the forecast math anchor on trusted present-time truth and stay physically bounded, so the numbers in `forecast.json` / statusline / Future tab can never contradict what the server plainly shows now.

**Architecture:** A pure trust-gate + newest-wins reading selector decides which live readings may touch the math (I3). `windows.py` gains an observed-burn rate and a bounded projection so the 168-bucket profile can no longer explode the hero number or a self-referential ETA (I2). A new pure `core/capcal.py` derives a self-calibrating effective cap from the corroborated `used ÷ (server_pct/100)` ratio (grow-only). `live/fill.py` becomes the single write-through authority (drops the engine double-rebase), applies only trusted readings, and honours the idle override (I1, I5). Honest-provenance plumbing (retained state, retain-cycle escalation, reading-age freshness, upward misparse guard) closes the stale-as-live gaps.

**Tech Stack:** Python 3.10+, stdlib only. Existing `Forecast`/`LiveCell`/`ratelimits`/`overlay`/`contract`/`extract_common`.

**Design source:** `plans/063-present-truth-anchoring-design.md` (approved). Builds on committed 062 (`8b0c8c4`) + Body-2 checkpoint (`bdc0614`).

## Global Constraints

- Stdlib only; no new dependencies; no new scrape surfaces; no fingerprint-evasion.
- `FRESH_TTL_SECS` (600s) = the freshness bar for touching MATH. `RETAIN_FRESH_TTL_SECS` / `HEADER_FRESH_TTL_SECS` (6h) gate DISPLAY only.
- Confidence bar for math = `CONF_HIGH` (from `live/contract.py`).
- The five invariants (verbatim acceptance criteria — every task cites the ones it establishes):
  - **I1 Anchor** — a trusted present reading IS the displayed now; local logs never overrule it.
  - **I2 Bound** — `projected_pct ≥ anchored now`; ETA from observed burn; no cap-hit implied after `reset_in`.
  - **I3 Trust gate** — only fresh (`age < FRESH_TTL_SECS`) + `CONF_HIGH` + non-`+retained` readings touch math.
  - **I4 Honest provenance** — no number shown `live` without true age+source; same cell reads identically on Present and Future.
  - **I5 Truth beats idle** — a trusted reading of real usage marks the window active regardless of local logs.
- `projected_pct` stays an END-of-window projection (plan-030 invariant): the current fill `%` is NEVER aliased into `projected_pct`.
- Profile-integral projection is demoted to a secondary context number, never the alarm trigger.
- Self-calibration is GROW-ONLY: never shrink `cap_eff` below preset from calibration.
- Never blank a forecast on a live-store error, but never degrade silently — surface a degraded flag.
- Suite starts green at 421; must end green and larger. `ruff`, `ruff format`, `mypy` clean.

## File map

| File | Role |
|------|------|
| Create `token_oracle/live/trust.py` | Pure: `is_trusted_for_math(reading_or_cell, now)`, `newest_first(readings)` |
| Create `token_oracle/core/capcal.py` | Pure+persist: self-calibrating `cap_eff` per (profile,window), grow-only EMA, note |
| Modify `token_oracle/core/windows.py` | `observed_rate`, bounded `eta_to_cap`, reworked `recompute_with_used` (clamp/observed-residual/idle-override) |
| Modify `token_oracle/live/fill.py` | Single write-through authority: trust-gate + newest-wins + cap_eff + idle override + degraded flag |
| Modify `token_oracle/core/engine.py` | Drop inline 5h double-rebase; feed cap_eff; expose degraded flag |
| Modify `token_oracle/live/overlay.py` | `is_retained` / distinct retained state once age > FRESH_TTL |
| Modify `token_oracle/live/store.py` | per-provider retain-cycle counter → visible `stale — probe failing` |
| Modify `token_oracle/live/web.py` | `get_live_status` freshness from newest reading `fetched_at` |
| Modify `token_oracle/live/extract_common.py` | symmetric upward-jump guard in `monotonic_guard` |
| Modify tests + `plans/README.md` | new tests per invariant; 063 row |

---

### Task 1: Trust gate + newest-wins selector (I3)

**Files:**
- Create: `token_oracle/live/trust.py`
- Test: `tests/test_live_trust.py`

**Interfaces:**
- Consumes: `live/contract.py` `CONF_HIGH`, `STATE_OK`; `live/overlay.py` `FRESH_TTL_SECS`.
- Produces:
  - `def is_trusted_for_math(*, state, confidence, age_secs, extractor) -> bool`
  - `def newest_first(readings: list[dict]) -> list[dict]`  # sorted by `fetched_at` desc, missing → oldest

- [ ] **Step 1: Write failing tests**

```python
from token_oracle.live.trust import is_trusted_for_math, newest_first
from token_oracle.live.contract import CONF_HIGH, CONF_MEDIUM, STATE_OK, STATE_AUTH_NO_DATA

def _kw(**o):
    base = dict(state=STATE_OK, confidence=CONF_HIGH, age_secs=10.0, extractor="modal")
    base.update(o); return base

def test_trusted_fresh_high_ok():
    assert is_trusted_for_math(**_kw()) is True

def test_untrusted_stale():
    assert is_trusted_for_math(**_kw(age_secs=601.0)) is False

def test_untrusted_retained():
    assert is_trusted_for_math(**_kw(extractor="modal+retained")) is False

def test_untrusted_low_conf():
    assert is_trusted_for_math(**_kw(confidence=CONF_MEDIUM)) is False

def test_untrusted_bad_state():
    assert is_trusted_for_math(**_kw(state=STATE_AUTH_NO_DATA)) is False

def test_untrusted_missing_age():
    assert is_trusted_for_math(**_kw(age_secs=None)) is False

def test_newest_first_orders_by_fetched_at():
    rs = [{"v":1,"fetched_at":100.0},{"v":2,"fetched_at":300.0},{"v":3,"fetched_at":200.0}]
    assert [r["v"] for r in newest_first(rs)] == [2,3,1]

def test_newest_first_missing_ts_sinks():
    rs = [{"v":1},{"v":2,"fetched_at":50.0}]
    assert [r["v"] for r in newest_first(rs)] == [2,1]
```

- [ ] **Step 2: Run — expect FAIL** (`ModuleNotFoundError`).

```bash
python -m pytest tests/test_live_trust.py -q
```

- [ ] **Step 3: Implement `token_oracle/live/trust.py`**

```python
"""Pure trust gate for present-time readings that may touch forecast MATH (plan 063, I3).

Retained / stale / low-confidence readings stay display-only; only a fresh,
high-confidence, non-retained OK reading is allowed to re-anchor the forecast.
"""
from __future__ import annotations

from .contract import CONF_HIGH, STATE_OK
from .overlay import FRESH_TTL_SECS


def is_trusted_for_math(*, state, confidence, age_secs, extractor) -> bool:
    if state != STATE_OK:
        return False
    if confidence is None or confidence < CONF_HIGH:
        return False
    if age_secs is None or age_secs > FRESH_TTL_SECS:
        return False
    if isinstance(extractor, str) and extractor.endswith("+retained"):
        return False
    return True


def newest_first(readings):
    def _key(r):
        ts = r.get("fetched_at") if isinstance(r, dict) else None
        return ts if isinstance(ts, (int, float)) else float("-inf")
    return sorted(readings or [], key=_key, reverse=True)
```

> Note: confirm `CONF_HIGH`/`STATE_OK` import paths and `FRESH_TTL_SECS` value by reading `live/contract.py` and `live/overlay.py` first; if `CONF_HIGH` is an int rank, `<` comparison holds; if it is a string, replace the `< CONF_HIGH` check with `confidence != CONF_HIGH`.

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit**

```bash
git add token_oracle/live/trust.py tests/test_live_trust.py
git commit -m "feat(live): trust gate + newest-wins selector for forecast math (plan 063, I3)"
```

---

### Task 2: Observed-rate + bounded projection in windows.py (I2)

**Files:**
- Modify: `token_oracle/core/windows.py`
- Test: `tests/test_windows.py`

**Interfaces:**
- Consumes: `Forecast` (`window, used, cap, projected_pct, eta_to_cap_secs, reset_in_secs, idle, profile`); event list `[(ts, tokens), ...]` already summed by `compute_window`.
- Produces:
  - `def observed_rate(events, start, now, rate_window_secs=3600.0) -> float | None` (tokens/sec over the recent trailing window; `None` if no burn)
  - `def bounded_projection(used_now, obs_rate, time_left, cap, slack=1.5) -> float` (projected tokens, floored at `used_now`)
  - `def eta_to_cap(used, cap, obs_rate) -> float | None` (observed-rate ETA; `0.0` if `used>=cap`; `None` if `obs_rate<=0`)
  - `recompute_with_used(f, used, *, obs_rate=None, active=None) -> Forecast` (reworked)

**Rules established:** I2 — `projected_pct ≥ 100*used_now/cap`; ETA from `obs_rate`; if `eta is None or eta >= reset_in` then no cap-hit is implied; a heavy early burst yields a projection bounded by `observed_bound`.

- [ ] **Step 1: Write failing tests**

```python
from token_oracle.core.contracts import Forecast
from token_oracle.core.windows import (
    observed_rate, bounded_projection, eta_to_cap, recompute_with_used,
)

def test_observed_rate_trailing_window():
    # 3000 tokens across the last 3000s -> 1 tok/s
    now = 10_000.0
    events = [(now-2999.0, 1000), (now-1500.0, 1000), (now-1.0, 1000), (now-8000.0, 9999)]
    r = observed_rate(events, start=0.0, now=now, rate_window_secs=3000.0)
    assert abs(r - 1.0) < 0.01  # the 9999 outside the 3000s window is excluded

def test_observed_rate_none_when_idle():
    assert observed_rate([], 0.0, 100.0) is None

def test_bounded_projection_floors_at_now_and_caps_at_slack():
    # used 500, rate 0 -> projection == used (no future burn)
    assert bounded_projection(500, 0.0, 3600.0, 1000, slack=1.5) == 500
    # used 100, 1 tok/s, 400s left, slack 1.5 -> 100 + 400*1.5 = 700
    assert bounded_projection(100, 1.0, 400.0, 1000, slack=1.5) == 700

def test_eta_observed_none_without_rate():
    assert eta_to_cap(500, 1000, None) is None
    assert eta_to_cap(500, 1000, 0.0) is None

def test_eta_observed_zero_at_wall():
    assert eta_to_cap(1000, 1000, 5.0) == 0.0

def test_eta_observed_from_rate():
    # 500 to go at 1 tok/s = 500s
    assert abs(eta_to_cap(500, 1000, 1.0) - 500.0) < 0.01

def test_recompute_clamps_used_to_cap():
    f = Forecast("weekly", 100, 1000, 30.0, None, 3600.0, False, profile="claude")
    g = recompute_with_used(f, 1500)  # server says >cap
    assert g.used <= 1000 and g.projected_pct >= 100.0

def test_recompute_projected_never_below_now():
    # server now=80% (800 tok), local end-proj was 40% -> projected must be >= 80%
    f = Forecast("weekly", 400, 1000, 40.0, None, 3600.0, False, profile="claude")
    g = recompute_with_used(f, 800, obs_rate=0.0)
    assert g.projected_pct >= 80.0

def test_recompute_no_impossible_projection_from_history():
    # heavy early burst: local proj 900% must be bounded to observed_bound
    f = Forecast("weekly", 200000, 1000000, 900.0, 100.0, 500000.0, False, profile="claude")
    g = recompute_with_used(f, 200000, obs_rate=0.1)  # 0.1 tok/s * 500000s = 50000 extra
    # projected tok <= used + 0.1*500000*slack; pct well under 900
    assert g.projected_pct < 100.0

def test_recompute_idle_override_marks_active():
    f = Forecast("weekly", 0, 1000, 0.0, None, 3600.0, True, profile="claude")  # idle by logs
    g = recompute_with_used(f, 600, active=True)  # trusted server says 60%
    assert g.idle is False and g.projected_pct >= 60.0

def test_recompute_idle_stays_idle_when_not_active():
    f = Forecast("weekly", 0, 1000, 0.0, None, 3600.0, True, profile="claude")
    g = recompute_with_used(f, 0, active=None)
    assert g.idle is True
```

- [ ] **Step 2: Run — expect FAIL.**

```bash
python -m pytest tests/test_windows.py -k "observed_rate or bounded_projection or eta_ or recompute" -q
```

- [ ] **Step 3: Implement in `windows.py`**

Add the pure helpers and rework `recompute_with_used`. `eta_to_cap` currently takes projection-implied rate — replace its body/signature per the tests (keep any existing callers compiling; grep `eta_to_cap(` and update call sites to pass `obs_rate`).

```python
def observed_rate(events, start, now, rate_window_secs=3600.0):
    """Tokens/sec burned over the recent trailing window [max(start, now-W), now]."""
    lo = max(float(start), float(now) - float(rate_window_secs))
    total = 0
    for ts, tok in events or []:
        if lo <= ts <= now:
            total += int(tok or 0)
    span = now - lo
    if span <= 0 or total <= 0:
        return None
    return total / span


def bounded_projection(used_now, obs_rate, time_left, cap, slack=1.5):
    """End-of-window projected tokens: linear observed burn, floored at now."""
    extra = 0.0 if not obs_rate or obs_rate <= 0 else obs_rate * max(0.0, time_left) * slack
    return max(int(used_now), int(round(used_now + extra)))


def eta_to_cap(used, cap, obs_rate):
    """Seconds to cap from OBSERVED burn. 0 at/over cap; None if no burn."""
    if used >= cap:
        return 0.0
    if not obs_rate or obs_rate <= 0:
        return None
    return (cap - used) / obs_rate
```

`recompute_with_used` rework (keep it a frozen-dataclass rebuild; preserve `projected_pct` as end-of-window, never alias current fill):

```python
def recompute_with_used(f, used, *, obs_rate=None, active=None):
    if getattr(f, "idle", False) and not active:
        return f
    cap = int(getattr(f, "cap", 0) or 0)
    used_now = max(0, min(int(round(used)), cap)) if cap > 0 else max(0, int(round(used)))
    reset_in = float(getattr(f, "reset_in_secs", 0) or 0)
    proj_tok = bounded_projection(used_now, obs_rate, reset_in, cap)
    proj_tok = max(proj_tok, used_now)
    projected_pct = (100.0 * proj_tok / cap) if cap > 0 else float(getattr(f, "projected_pct", 0.0))
    eta = eta_to_cap(used_now, cap, obs_rate) if cap > 0 else None
    idle = False if active else bool(getattr(f, "idle", False))
    # rebuild the frozen Forecast preserving all other fields
    return replace_forecast(f, used=used_now, projected_pct=projected_pct,
                            eta_to_cap_secs=eta, idle=idle)
```

> `replace_forecast` = whatever the codebase uses to copy a frozen `Forecast` (likely `dataclasses.replace` or `object.__setattr__` on a copy). Read `core/contracts.py` and use the existing idiom. If `Forecast` is a frozen dataclass, `from dataclasses import replace` and `return replace(f, ...)`.

- [ ] **Step 4: Run — expect PASS.** Then run full `test_windows.py` and fix any call-site regressions from the `eta_to_cap` signature change.
- [ ] **Step 5: Commit**

```bash
git add token_oracle/core/windows.py tests/test_windows.py
git commit -m "feat(core): observed-rate ETA + bounded projection, recompute clamps (plan 063, I2)"
```

---

### Task 3: Self-calibrating effective cap (Layer 1 moat)

**Files:**
- Create: `token_oracle/core/capcal.py`
- Test: `tests/test_capcal.py`

**Interfaces:**
- Produces:
  - `def calibrate(profile, window, used_tokens, server_pct, preset_cap, now, path=None) -> tuple[int, str | None]` → `(cap_eff, note_or_None)`. Grow-only EMA; persists per `(profile, window)`; returns a human note when `cap_eff` moved materially from preset.
  - `def current_cap(profile, window, preset_cap, path=None) -> int` → last persisted `cap_eff` or `preset_cap`.
- Persist path: `capcal.json` sibling to `ratelimits.default_path()` (XDG data dir). Atomic write, never raises (mirror `ratelimits._save`).

**Constants:** `P_FLOOR = 8.0` (server_pct below which the ratio is too noisy), `TOK_FLOOR = 2000`, `ALPHA = 0.25` (EMA), `CAL_CEIL = 20.0` (× preset absurdity clamp).

- [ ] **Step 1: Write failing tests**

```python
import os, tempfile
from token_oracle.core.capcal import calibrate, current_cap

def _p(): 
    d = tempfile.mkdtemp(); return os.path.join(d, "capcal.json")

def test_grow_only_adopts_bigger_cap():
    p = _p()
    # server says 25% used at 110k tokens -> real cap ~440k > preset 220k -> grow
    cap, note = calibrate("claude", "weekly", 110_000, 25.0, 220_000, now=1.0, path=p)
    assert cap > 220_000 and note is not None

def test_never_shrinks_below_preset():
    p = _p()
    # server says 90% at 110k -> implied cap ~122k < preset 220k -> keep preset (grow-only)
    cap, note = calibrate("claude", "weekly", 110_000, 90.0, 220_000, now=1.0, path=p)
    assert cap == 220_000 and note is None

def test_noise_floor_ignored():
    p = _p()
    cap, _ = calibrate("claude", "weekly", 100, 2.0, 220_000, now=1.0, path=p)  # pct<8, tok<2000
    assert cap == 220_000

def test_absurdity_ceiling():
    p = _p()
    # pct tiny-but-above-floor with huge tokens -> clamp at 20x preset
    cap, _ = calibrate("claude", "weekly", 100_000_000, 9.0, 220_000, now=1.0, path=p)
    assert cap <= 220_000 * 20

def test_persistence_roundtrip():
    p = _p()
    calibrate("claude", "weekly", 110_000, 25.0, 220_000, now=1.0, path=p)
    assert current_cap("claude", "weekly", 220_000, path=p) > 220_000
    assert current_cap("grok", "weekly", 700_000, path=p) == 700_000  # untouched -> preset

def test_ema_smooths_toward_estimate():
    p = _p()
    c1, _ = calibrate("claude", "weekly", 110_000, 25.0, 220_000, now=1.0, path=p)   # inst ~440k
    c2, _ = calibrate("claude", "weekly", 110_000, 25.0, 220_000, now=2.0, path=p)   # closer to 440k
    assert 220_000 < c1 < c2 <= 440_000 + 1
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement `capcal.py`** (grow-only EMA, corroboration floors, ceiling clamp, atomic persist). `cap_inst = used_tokens / (server_pct/100)`; adopt only if `cap_inst > preset_cap` and floors pass; `cap_eff = round((1-ALPHA)*prev + ALPHA*cap_inst)` starting `prev=preset`; clamp `≤ preset*CAL_CEIL`; note = `f"cap recalibrated {preset_cap}→{cap_eff} (from live usage — tier changed?)"` when `cap_eff/preset > 1.1`.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit**

```bash
git add token_oracle/core/capcal.py tests/test_capcal.py
git commit -m "feat(core): self-calibrating effective cap from server pct (plan 063, moat)"
```

---

### Task 4: fill.py = single trusted write-through authority (I1, I3, I5)

**Files:**
- Modify: `token_oracle/live/fill.py`
- Modify: `token_oracle/core/engine.py`
- Test: `tests/test_live_fill.py`, `tests/test_engine.py`

**Interfaces:**
- Consumes: Task 1 `is_trusted_for_math`/`newest_first`; Task 2 `recompute_with_used(..., obs_rate=, active=)`; Task 3 `current_cap`/`calibrate`.
- Produces: `apply_live_fills(forecasts, now, events_by_profile=None) -> tuple[list[Forecast], bool]` where the bool is `degraded` (an exception was swallowed). `_pct_from_snapshot` selects via `newest_first` + `is_trusted_for_math`.

**Rules established:** I1 (trusted reading becomes the anchor), I3 (only trusted readings applied; retained/stale skipped), I5 (`active=True` passed when a trusted reading shows usage ≥ active-floor).

- [ ] **Step 1: Write failing tests** (add to `tests/test_live_fill.py`)

```python
def test_i1_trusted_reading_anchors_used(monkeypatch, tmp_path):
    # a fresh CONF_HIGH weekly reading of 60% rebases used to 60% of cap
    ...  # build a Forecast + snapshot with one fresh high-conf weekly reading
    filled, degraded = apply_live_fills([f], now)
    assert filled[0].used == round(0.60 * f.cap) and degraded is False

def test_i3_retained_reading_not_applied():
    # a '+retained' reading (age within 6h retain TTL but > FRESH_TTL) must NOT change used
    filled, _ = apply_live_fills([f], now)
    assert filled[0].used == f.used  # unchanged; retained is display-only

def test_i5_idle_forecast_activated_by_trusted_usage():
    idle_f = Forecast("weekly", 0, 1000, 0.0, None, 3600.0, True, profile="claude")
    filled, _ = apply_live_fills([idle_f], now)  # snapshot has fresh 40% weekly
    assert filled[0].idle is False and filled[0].used == 400

def test_newest_wins_on_duplicate_readings():
    # two fresh high-conf weekly readings, newer=55%, older=99% -> apply 55%
    filled, _ = apply_live_fills([f], now)
    assert filled[0].used == round(0.55 * f.cap)

def test_degraded_flag_on_store_error(monkeypatch):
    monkeypatch.setattr("token_oracle.live.fill._load_snapshot", _boom)
    filled, degraded = apply_live_fills([f], now)
    assert degraded is True and filled == [f]  # never blanks, but signals
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement fill rework**
  - Replace `_pct_from_snapshot` best-selection with: filter readings for the `(profile, window)` through `is_trusted_for_math`, order `newest_first`, take the first; return `(pct, fetched_at, extractor)` or `None`.
  - In `apply_live_fills`: for each non-idle-or-activatable forecast, resolve trusted pct; compute `cap_eff = current_cap(profile, window, f.cap)`; `used = round(pct/100 * cap_eff)`; feed `calibrate(...)` to update `cap_eff`; call `recompute_with_used(f, used, obs_rate=observed_rate(...), active=(pct >= ACTIVE_FLOOR))`.
  - Return `(forecasts, degraded)`; wrap in try/except that sets `degraded=True` and returns originals (never blanks).
  - `ACTIVE_FLOOR` small (e.g. 1.0%).
- [ ] **Step 4: Drop the engine double-rebase**
  - In `engine.py`, remove the inline 5h `recompute_with_used` calls (the two server-fill sites); let `_apply_live_fills` own ALL windows. `_apply_live_fills` now unpacks `(forecasts, degraded)` and stashes `degraded` where `get_live_status`/doctor can read it (module-level or a returned flag threaded to the caller). Keep the try/except so a broken fill never blanks.
- [ ] **Step 5: Run `test_live_fill.py` + `test_engine.py` — expect PASS**, fix regressions.
- [ ] **Step 6: Commit**

```bash
git add token_oracle/live/fill.py token_oracle/core/engine.py tests/test_live_fill.py tests/test_engine.py
git commit -m "feat(live): fill = single trusted write-through, idle override, degraded flag (plan 063, I1/I3/I5)"
```

---

### Task 5: Honest-provenance plumbing (I4) + misparse guard

**Files:**
- Modify: `token_oracle/live/overlay.py`, `token_oracle/live/store.py`, `token_oracle/live/web.py`, `token_oracle/live/extract_common.py`
- Test: `tests/test_live_overlay.py`, `tests/test_live_store.py` (create if absent), `tests/test_live_web.py` (or existing), `tests/test_extract_common.py`

**Rules established:** I4 (retained/over-fresh cells are visibly distinct with age); plus the upward-misparse guard and the reading-age freshness fix.

- [ ] **Step 1: Write failing tests**

```python
# overlay: a cell built from a '+retained' reading (or age > FRESH_TTL) is flagged
def test_retained_cell_is_flagged():
    cell = ...  # overlay_cells() for a retained reading
    assert cell.is_retained is True

def test_fresh_cell_not_flagged():
    cell = ...  # fresh high-conf reading
    assert cell.is_retained is False

# store: a provider retained across >N probe cycles escalates to stale
def test_retain_cycle_escalates_to_stale():
    ...  # merge_with_previous N+1 times with empty probes -> provider marked stale

# web.get_live_status uses newest reading fetched_at, not snapshot written_at
def test_get_live_status_uses_reading_age():
    ...  # snapshot written_at=now but readings fetched_at hours old -> status 'stale'

# extract_common upward guard: uncorroborated jump held
def test_monotonic_upward_guard_holds_uncorroborated_jump():
    ...  # single extractor 30% -> 95% with no second-source corroboration -> not adopted
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement**
  - `overlay.py`: add `is_retained: bool` to `LiveCell` (default False); set True when `reading extractor endswith '+retained'` OR `age_secs > FRESH_TTL_SECS`. Keep `state=STATE_OK` (don't break existing consumers) but expose the flag.
  - `store.py`: add `retain_cycles` per provider in the snapshot; `merge_with_previous` increments on each retained cycle, resets to 0 on a real reading; when `retain_cycles > RETAIN_MAX_CYCLES` (e.g. 6) mark the provider's readings so `get_live_status` reports `stale — probe failing`.
  - `web.get_live_status`: derive per-provider freshness from the newest reading `fetched_at` (reuse `store._reading_age`), not `written_at`.
  - `extract_common.monotonic_guard`: add a symmetric upward-jump branch — an increase beyond a threshold (e.g. +40 pts) with no second corroborating extractor at similar value is held (kept at prior) or downgraded in confidence.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit**

```bash
git add token_oracle/live/overlay.py token_oracle/live/store.py token_oracle/live/web.py token_oracle/live/extract_common.py tests/
git commit -m "feat(live): honest retained/stale provenance + upward misparse guard (plan 063, I4)"
```

---

### Task 6: Suite, gates, README, integration smoke

**Files:** `plans/README.md`, no code unless a gate fails.

- [ ] **Step 1: Full suite** — `python -m pytest -q` (expect all pass, count > 421).
- [ ] **Step 2: Gates** — `ruff check token_oracle`, `ruff format --check token_oracle`, `mypy token_oracle` (match repo config). Fix any breakage.
- [ ] **Step 3: Invariant regression grep** — confirm no test asserts the old unbounded-projection / projection-implied-ETA behavior; update any left over.
- [ ] **Step 4: Manual smoke (operator)** — `oracle dash`; verify 5h/weekly now-numbers match Claude Code / browser; force a stale probe and confirm the cell shows an age, not bare `live`.
- [ ] **Step 5: Update `plans/README.md`** row 063 → DONE with commit range.
- [ ] **Step 6: Commit** — `git commit -am "docs(plans): 063 engine truth DONE"`.

---

## Spec coverage checklist

| Design requirement | Task |
|---|---|
| I1 anchor | T4 |
| I2 bound (observed ETA, bounded projection, floor) | T2 |
| I3 trust gate (fresh+high+non-retained) | T1, T4 |
| I4 honest provenance (retained state, age, retain-cycle, reading-age freshness) | T5 |
| I5 truth beats idle | T2, T4 |
| self-calibrating cap (grow-only, corroborated, persisted, note) | T3 |
| newest-wins selection | T1, T4 |
| single 5h truth source (drop double-rebase) | T4 |
| no silent degradation (degraded flag) | T4 |
| upward misparse guard | T5 |
| suite green + gates | T6 |
| Non-goals (no new scrape, stdlib, no probability %) | all |

## Placeholder scan

Test bodies in Task 4/5 use `...` for fixture setup ONLY where the fixture shape depends on the exact `overlay_cells`/snapshot signatures in the tree; the asserted behavior is fully specified. The implementer reads the neighbouring existing tests (`test_live_fill.py`, `test_live_overlay.py`) for the fixture idiom before filling them. All pure-function tasks (T1–T3) are fully concrete.
