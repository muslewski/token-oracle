# Plan 039 — Validate external Claude caps; reject semantically-impossible values

**Status:** TODO
**Written against commit:** `646a2ac`
**Priority:** P0 (truthfulness gate — blocks any launch)
**Effort:** S–M
**Depends on:** 001 (config `issues` mechanism — DONE), 017 (plan presets — DONE). No file conflict with 040/041; may run in parallel.

---

## Why this matters (the bug)

`token_oracle` forecasts usage as `used_tokens / cap`. The `cap` for a Claude-sourced
window comes from a shipped **preset** (`max20` → 5h cap `220000`, weekly cap `8000000`).
But `load_config` then **overrides** those preset caps with whatever is in the user's
`~/.claude/usage-limits.json`, applied with **zero validation** (`config.py`
`load_claude_limits()` → application at `config.py:349-371` and `config.py:408-436`).

On the operator's real machine that file contains:

```json
{"plan":"max20","fiveHourCap":57000000,"weeklyCap":270000000, ...}
```

These are **impossible**:
- `fiveHourCap = 57,000,000` is **259× the max20 preset** (`220,000`).
- `fiveHourCap (57M)` is **larger than the weekly cap** (`8M` preset). A 5-hour token
  budget cannot exceed a 7-day budget — this is a hard semantic contradiction,
  independent of what the "right" absolute number is.
- `weeklyCap = 270,000,000` is **34× the max20 preset** (`8,000,000`).

Effect: weekly `%` is computed as `used / 270,000,000`, i.e. **~34× too small**, so the
dashboard shows ~0–1% when the user is really at (say) 30%. This is the **"local
projection shows tiny numbers"** symptom. It is masked only when a live/server overlay
is present (that path recomputes `used = round(pct/100 * cap)`, so the bogus cap cancels
out in the displayed %) — which is exactly why it hid for so long.

**We do not know the single "correct" absolute cap, and this plan does NOT try to guess
it.** The fix is to reject values that are *provably impossible* and fall back to the
shipped preset, recording an honest `issue`. Truthfulness-first: a preset-based % that is
labelled and roughly right beats a file-based % that is 34× wrong.

## Root cause (verified by direct read at `646a2ac`)

`token_oracle/core/config.py`:

- `load_claude_limits()` (line 252) reads `fiveHourCap`/`weeklyCap`/`weeklyResetAnchor`/`plan`
  and returns them **as-is** — no numeric/range/sanity checks.
- In `load_config`, the **top-level** window loop (lines 349–371) does:
  ```python
  if five_cap and ("5h" in nm or ... or nm in ("5h","session","current")):
      ww["cap"] = int(five_cap)
  if wk_cap and nm in ("weekly","week","fable"):
      ww["cap"] = int(wk_cap)
  ```
  `ww["cap"]` before this line is the **preset** cap. So the external value blindly wins.
- The **per-profile** window loop (lines 408–436) repeats the identical blind override.

The `weeklyResetAnchor` handling is fine and **must be preserved** — the anchor (reset
timing) is genuinely useful and is not what's broken. Only the **cap magnitudes** are.

## The fix (design — implement exactly this)

Add a **pure validator** and route both application sites through it. A candidate external
cap is applied **only if it passes every invariant**; otherwise the preset cap is kept and
an `issue` is appended.

### Invariants (a candidate external cap `ext` for kind ∈ {"5h","weekly"} vs its preset cap `preset`)

1. `ext` is an `int`/`float`, finite, and `> 0`. (else reject)
2. **Band vs preset:** `preset * 0.2 <= ext <= preset * 5.0`.
   - Legit plan changes (Anthropic bumps a cap ±a few ×) stay in band and are honored.
   - `57M` vs preset `220k` → 259× → **rejected**. `270M` vs `8M` → 34× → **rejected**.
3. **Cross-window:** the effective `5h` cap must be **strictly less than** the effective
   `weekly` cap. If a validated 5h cap ends up `>=` the validated weekly cap, reject the
   **5h** one (5h is the smaller-by-definition window) and keep its preset.

When a cap is rejected, keep the preset value and append **one** issue string of the form:
```
external fiveHourCap 57000000 rejected (259x the max20 preset 220000, implausible) — keeping preset
external weeklyCap 270000000 rejected (34x the max20 preset 8000000, implausible) — keeping preset
```

### Step 1 — Add the pure validator to `config.py`

Add this module-level function (place it directly **above** `load_config`). It takes the
raw external caps and the preset caps and returns the effective caps (external where valid,
else `None` meaning "use preset") plus issues. Returning `None` for a rejected cap lets the
application loops simply skip the override.

```python
# Bands for accepting an external cap relative to the shipped preset cap.
_CAP_BAND_LOW = 0.2
_CAP_BAND_HIGH = 5.0


def _preset_caps(plan: str) -> tuple[int | None, int | None]:
    """(five_hour_cap, weekly_cap) from the shipped preset for `plan` (max20 fallback)."""
    pdef = PRESETS.get(plan) or PRESETS.get("max20") or {}
    five = wk = None
    for w in pdef.get("windows", []):
        if not isinstance(w, dict):
            continue
        nm = str(w.get("name", "")).lower()
        cap = w.get("cap")
        if not isinstance(cap, (int, float)):
            continue
        if nm in ("5h", "5-hour", "session", "current"):
            five = int(cap)
        elif nm in ("weekly", "week", "fable"):
            wk = int(cap)
    return five, wk


def _validate_external_caps(raw_five, raw_wk, preset_five, preset_wk):
    """Reject semantically-impossible external caps. Returns
    (five_or_None, wk_or_None, issues). None means 'rejected — use the preset'."""
    issues: list[str] = []

    def _check(ext, preset, label):
        if ext is None:
            return None  # nothing supplied -> preset (no issue)
        if not isinstance(ext, (int, float)) or isinstance(ext, bool):
            issues.append(f"external {label} {ext!r} rejected (not a number) — keeping preset")
            return None
        try:
            extf = float(ext)
        except (TypeError, ValueError):
            issues.append(f"external {label} {ext!r} rejected (not a number) — keeping preset")
            return None
        if not (extf > 0) or extf != extf or extf in (float("inf"), float("-inf")):
            issues.append(f"external {label} {ext} rejected (non-positive/non-finite) — keeping preset")
            return None
        if preset and preset > 0:
            ratio = extf / preset
            if ratio < _CAP_BAND_LOW or ratio > _CAP_BAND_HIGH:
                issues.append(
                    f"external {label} {int(extf)} rejected "
                    f"({ratio:.0f}x the preset {int(preset)}, implausible) — keeping preset"
                )
                return None
        return int(extf)

    five = _check(raw_five, preset_five, "fiveHourCap")
    wk = _check(raw_wk, preset_wk, "weeklyCap")

    # Cross-window invariant: a 5h cap cannot be >= the weekly cap.
    eff_five = five if five is not None else preset_five
    eff_wk = wk if wk is not None else preset_wk
    if eff_five is not None and eff_wk is not None and eff_five >= eff_wk:
        # Only complain if the *external* 5h value is the culprit (don't fault a clean preset).
        if five is not None:
            issues.append(
                f"external fiveHourCap {int(five)} rejected "
                f"(>= weekly cap {int(eff_wk)}, impossible) — keeping preset"
            )
        five = None

    return five, wk, issues
```

### Step 2 — Route the top-level application through the validator

In `load_config`, the block at lines ~339-343 currently does:

```python
claude_limits = load_claude_limits()
five_cap = claude_limits.get("fiveHourCap")
wk_cap = claude_limits.get("weeklyCap")
wk_anchor_str = claude_limits.get("weeklyResetAnchor")
wk_anchor = parse_ts(wk_anchor_str) if wk_anchor_str else None
```

Replace the two cap lines so the caps are validated against the active plan's preset, and
push any issues into the `issues` list:

```python
claude_limits = load_claude_limits()
_pf, _pw = _preset_caps(plan)
five_cap, wk_cap, _cap_issues = _validate_external_caps(
    claude_limits.get("fiveHourCap"), claude_limits.get("weeklyCap"), _pf, _pw
)
issues.extend(_cap_issues)
wk_anchor_str = claude_limits.get("weeklyResetAnchor")
wk_anchor = parse_ts(wk_anchor_str) if wk_anchor_str else None
```

**Leave the window loop (lines 350-371) unchanged** — because `five_cap`/`wk_cap` are now
`None` when rejected, the existing `if five_cap and ...` / `if wk_cap and ...` guards
already skip the override and the preset `ww["cap"]` survives. Do NOT change the anchor
logic.

### Step 3 — Route the per-profile application through the same validator

The second block (lines ~403-407) re-fetches limits:

```python
claude_limits = load_claude_limits()
five_cap = claude_limits.get("fiveHourCap")
wk_cap = claude_limits.get("weeklyCap")
wk_anchor_str = claude_limits.get("weeklyResetAnchor")
wk_anchor = parse_ts(wk_anchor_str) if wk_anchor_str else None
```

Replace the two cap lines the same way. **Do not** append these issues a second time (the
top-level block already recorded them for the same underlying file). Use `_` to discard:

```python
claude_limits = load_claude_limits()
_pf, _pw = _preset_caps(plan)
five_cap, wk_cap, _ = _validate_external_caps(
    claude_limits.get("fiveHourCap"), claude_limits.get("weeklyCap"), _pf, _pw
)
wk_anchor_str = claude_limits.get("weeklyResetAnchor")
wk_anchor = parse_ts(wk_anchor_str) if wk_anchor_str else None
```

The per-profile loop below it is likewise unchanged (same `None`-skips-override behavior).

## Files in scope

- `token_oracle/core/config.py` — add `_preset_caps`, `_validate_external_caps`; reroute the
  two cap-application blocks. **No other logic changes.**
- `tests/test_config.py` — add the tests below.

## Files explicitly OUT of scope (do NOT touch)

- The `weeklyResetAnchor` / anchor handling anywhere — it is correct.
- `try_get_claude_five_hour_data` / `try_get_claude_five_hour_remaining` — the server/live
  5h path is a separate concern; do not touch.
- `token_oracle/core/engine.py`, `windows.py`, any `live/` or `sources/` file.
- The preset magnitudes themselves (`19000/700000`, `88000/3200000`, `220000/8000000`) —
  do not "correct" them; they are the reference truth this plan validates against.

## Test plan

Add to `tests/test_config.py` (follow the existing `tmp_path` + `CFG.load_config` style).

**A. Pure validator unit tests (deterministic, no env, no monkeypatch):**

```python
def test_validate_caps_rejects_impossible_magnitudes():
    five, wk, issues = CFG._validate_external_caps(57000000, 270000000, 220000, 8000000)
    assert five is None and wk is None
    assert len(issues) == 2
    assert any("fiveHourCap" in i for i in issues)
    assert any("weeklyCap" in i for i in issues)


def test_validate_caps_accepts_in_band_plan_change():
    # a plausible cap bump (~1.1x / ~1.15x) is honored, no issues
    five, wk, issues = CFG._validate_external_caps(240000, 9200000, 220000, 8000000)
    assert five == 240000 and wk == 9200000
    assert issues == []


def test_validate_caps_rejects_5h_ge_weekly():
    # both individually in-band vs their presets, but 5h >= weekly is impossible
    five, wk, issues = CFG._validate_external_caps(900000, 800000, 220000, 8000000)
    # 900000 is >5x 220000 -> already rejected by band; use an in-band-but-crossed case:
    five, wk, issues = CFG._validate_external_caps(700000, 700000, 220000, 8000000)
    # 700000 vs 220000 = 3.18x (in band); 700000 vs 8000000 = 0.0875x -> weekly rejected by band
    # so craft one where both pass band but cross:
    five, wk, issues = CFG._validate_external_caps(1000000, 1100000, 220000, 8000000)
    # 1_000_000/220_000=4.5x (<=5 ok); 1_100_000/8_000_000=0.14x (<0.2 -> weekly rejected)
    # weekly falls back to preset 8_000_000; 5h 1_000_000 < 8_000_000 -> ok
    assert wk is None  # weekly rejected by band
    assert five == 1000000


def test_validate_caps_rejects_nonpositive_and_nonnumeric():
    assert CFG._validate_external_caps(0, -5, 220000, 8000000)[0] is None
    assert CFG._validate_external_caps("big", None, 220000, 8000000)[0] is None
    # None weekly supplied -> no issue for weekly
    five, wk, issues = CFG._validate_external_caps(None, None, 220000, 8000000)
    assert five is None and wk is None and issues == []


def test_preset_caps_reads_shipped_presets():
    assert CFG._preset_caps("max20") == (220000, 8000000)
    assert CFG._preset_caps("pro") == (19000, 700000)
    assert CFG._preset_caps("nonsense") == (220000, 8000000)  # max20 fallback
```

> NOTE for the executor: craft the cross-window test so **both** caps pass the band check
> yet `5h >= weekly`, to exercise invariant #3 in isolation. Presets `220000/8000000` make
> that awkward (band forces weekly ≥ 1.6M while 5h ≤ 1.1M, so they can't cross). Therefore
> **prefer testing invariant #3 via a direct call with custom preset args**, e.g.
> `CFG._validate_external_caps(900, 800, 500, 900)` → 900 vs 500 = 1.8x ok, 800 vs 900 = 0.89x ok,
> but 900 >= 800 → 5h rejected. Replace the messy block above with this clean case:
> ```python
> def test_validate_caps_rejects_5h_ge_weekly():
>     five, wk, issues = CFG._validate_external_caps(900, 800, 500, 900)
>     assert wk == 800
>     assert five is None
>     assert any("impossible" in i for i in issues)
> ```

**B. Integration test (validator is actually wired into `load_config`):**

`load_config` skips the external-cap override under pytest (`_should_apply_real_claude_limits`
returns `False` when `pytest` is imported). Force it on and stub the file read:

```python
def test_load_config_rejects_bogus_external_caps(monkeypatch, tmp_path):
    monkeypatch.setattr(CFG, "_should_apply_real_claude_limits", lambda: True)
    monkeypatch.setattr(
        CFG, "load_claude_limits",
        lambda: {"fiveHourCap": 57000000, "weeklyCap": 270000000, "plan": "max20"},
    )
    c = CFG.load_config(str(tmp_path / "none.json"))  # -> max20 preset windows
    weekly = next(w for w in c.windows if w.name == "weekly")
    five = next(w for w in c.windows if w.name == "5h")
    assert weekly.cap == 8000000   # preset kept, NOT 270000000
    assert five.cap == 220000      # preset kept, NOT 57000000
    assert any("weeklyCap" in i and "rejected" in i for i in c.issues)
    assert any("fiveHourCap" in i and "rejected" in i for i in c.issues)


def test_load_config_honors_plausible_external_caps(monkeypatch, tmp_path):
    monkeypatch.setattr(CFG, "_should_apply_real_claude_limits", lambda: True)
    monkeypatch.setattr(
        CFG, "load_claude_limits",
        lambda: {"fiveHourCap": 240000, "weeklyCap": 9200000, "plan": "max20"},
    )
    c = CFG.load_config(str(tmp_path / "none.json"))
    weekly = next(w for w in c.windows if w.name == "weekly")
    assert weekly.cap == 9200000  # in-band external value honored
    assert not any("rejected" in i for i in c.issues)
```

## Verification gates (run all; all must pass)

```
pip install -e ".[dev]"   # NOTE: clobbers the user's `oracle` entrypoint; the advisor re-symlinks after merge — not your concern
python -m pytest -q
ruff check token_oracle tests
ruff format --check token_oracle tests
mypy token_oracle --ignore-missing-imports
```

Expected: all green; ~219 existing tests still pass + the ~7 new ones. No pre-existing test
regresses (especially `test_default_is_max20_when_missing`, `test_plan_pro_yields_19000_cap`
— those run under the pytest guard so they are unaffected by the override path).

## Done criteria (machine-checkable)

- `python -m pytest -q tests/test_config.py` passes including all new tests.
- `python -c "from token_oracle.core import config as C; print(C._validate_external_caps(57000000,270000000,220000,8000000))"`
  prints `(None, None, [<two rejection strings>])`.
- `python -c "from token_oracle.core import config as C; print(C._validate_external_caps(240000,9200000,220000,8000000))"`
  prints `(240000, 9200000, [])`.
- `ruff check` / `ruff format --check` / `mypy` all clean on `token_oracle` + `tests`.
- One commit per step (or a small number of logically-grouped commits).

## Escape hatches — STOP and report instead of improvising if:

- The preset magnitudes at `config.py:180-215` are NOT `19000/700000`, `88000/3200000`,
  `220000/8000000` when you read them (this plan's band math assumes them).
- Rerouting the cap blocks breaks an existing test in a way implying another module reads
  `fiveHourCap`/`weeklyCap` directly (grep first: `rg fiveHourCap token_oracle`). If so,
  report the coupling rather than editing that module.
- You find the band `[0.2, 5.0]` rejects a shipped preset value against another preset
  (it must not — presets are the reference, external is the candidate). If confused, the
  band is **external ÷ its-own-plan preset**, never preset-vs-preset.

## Maintenance note

- The band `[0.2×, 5.0×]` is deliberately generous — it only fires on order-of-magnitude
  errors. If Anthropic ever ships a legitimately >5× cap change, widen the band **and** add
  a test pinning the new ratio; do not remove the cross-window invariant (#3), which is
  unit-independent and the strongest signal.
- This validator is the truthfulness gate for the **weekly** number and the **5h-without-
  overlay** number. When a live/server overlay is present, cap cancels out of the displayed
  % anyway (`engine.py` recomputes `used` from the server %), so this mainly protects the
  offline/local-projection path — which is the default a new user sees first.
