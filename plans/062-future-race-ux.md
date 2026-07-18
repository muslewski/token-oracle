# Future tab — live-aware cap race UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Future tab a distinct, honest cap-race surface: per-profile SAFE/TIGHT/OVER from live-aware window truth, showing both live now % and local end-proj when they disagree.

**Architecture:** Pure helpers in `token_oracle/dashboard/race.py` (Truth, status, eta, margin). `render_future` in `future.py` becomes race layout; `app.py` Future branch passes `st.cells` already loaded for Present. No engine changes in v1.

**Tech Stack:** Python 3.10+, stdlib only, existing `Forecast` / `LiveCell` / `cli.colors` / `fmt_dh_long` / `fmt_reset`.

**Design source:** `plans/062-future-race-ux-design.md` (approved).

## Global Constraints

- Stdlib only; no new dependencies.
- Quiet oracle tone: one word SAFE / TIGHT / OVER / IDLE / UNKNOWN (+ color via existing `gauge`); no pulse banners; no invented probability %.
- Window truth blend must match Present: 5h → local used/cap; weekly/fable → live cell when `pct is not None`; else local used/cap or projected.
- Profile canon: `"grok"` if name contains grok else `"claude"`.
- Status first-match: IDLE → OVER (`now_pct >= 100` or `eta < reset_in`) → TIGHT (`now_pct|end_pct >= 85`) → SAFE → UNKNOWN.
- Profile verdict worst-of: OVER > TIGHT > SAFE > IDLE > UNKNOWN.
- Present render unchanged (no intentional Present edits).
- Color off → no `\033` in Future output.
- Keep `spark_next24` / `cost_pace_line` as secondary footer; `prophecy_line` may remain for existing unit tests but is not the Future hero.

## File map

| File | Role |
|------|------|
| Create `token_oracle/dashboard/race.py` | Pure: `Truth`, `window_truth`, `eta_for_race`, `race_status`, `profile_verdict`, `margin_line`, `STATUS_RANK` |
| Modify `token_oracle/dashboard/future.py` | `render_future(..., cells=None)` race layout + width collapse |
| Modify `token_oracle/dashboard/app.py` | Pass `st.cells` into `render_future` |
| Modify `tests/test_dashboard.py` | Race unit table + live disagree + multi-profile + color-off; update old Future assertions |
| Modify `plans/README.md` | Row 062 → IN PROGRESS / DONE |

---

### Task 1: Pure race module + unit tests

**Files:**
- Create: `token_oracle/dashboard/race.py`
- Test: `tests/test_dashboard.py` (new section plan 062) or `tests/test_future_race.py` if preferred (prefer same file for consistency with 020 tests)

**Interfaces:**
- Consumes: `Forecast` (`window`, `used`, `cap`, `projected_pct`, `eta_to_cap_secs`, `reset_in_secs`, `idle`, `profile`); `cells: dict[tuple[str,str], LiveCell] | None`
- Produces:
  - `@dataclass(frozen=True) class Truth`: `now_pct: float | None`, `source: str` (`live`/`local`/`proj`/`none`), `end_pct: float | None`, `reset_in: float`, `idle: bool`, `window: str`, `cap: int`, `profile: str`
  - `def profile_canon(name: str) -> str`
  - `def window_truth(f, cells=None) -> Truth`
  - `def eta_for_race(f, truth: Truth) -> float | None`
  - `def race_status(truth: Truth, eta: float | None) -> str`  # IDLE|OVER|TIGHT|SAFE|UNKNOWN
  - `def profile_verdict(statuses: list[str]) -> str`
  - `def margin_line(truth: Truth, eta: float | None) -> str`

- [ ] **Step 1: Write failing tests for race_status table**

```python
from token_oracle.core.contracts import Forecast
from token_oracle.dashboard.race import (
    Truth,
    eta_for_race,
    margin_line,
    profile_verdict,
    race_status,
    window_truth,
)
from token_oracle.live.overlay import LiveCell
from token_oracle.live.contract import STATE_OK


def _truth(**kw):
    base = dict(
        now_pct=50.0, source="local", end_pct=50.0, reset_in=3600.0,
        idle=False, window="5h", cap=10000, profile="claude",
    )
    base.update(kw)
    return Truth(**base)


def test_race_status_table():
    assert race_status(_truth(idle=True), None) == "IDLE"
    assert race_status(_truth(now_pct=100.0), None) == "OVER"
    assert race_status(_truth(now_pct=50.0, end_pct=50.0, reset_in=7200.0), 3600.0) == "OVER"
    assert race_status(_truth(now_pct=90.0, end_pct=40.0), None) == "TIGHT"
    assert race_status(_truth(now_pct=40.0, end_pct=90.0), None) == "TIGHT"
    assert race_status(_truth(now_pct=40.0, end_pct=40.0), None) == "SAFE"
    assert race_status(_truth(now_pct=None, end_pct=None, source="none"), None) == "UNKNOWN"


def test_profile_verdict_worst_of():
    assert profile_verdict(["SAFE", "OVER", "TIGHT"]) == "OVER"
    assert profile_verdict(["IDLE", "SAFE"]) == "SAFE"
    assert profile_verdict(["IDLE", "UNKNOWN"]) == "IDLE"
    assert profile_verdict([]) == "UNKNOWN"


def test_window_truth_live_weekly():
    f = Forecast("weekly", 100, 1000, 23.0, None, 400000.0, False, profile="claude")
    cells = {("claude", "weekly"): LiveCell(pct=99.0, state=STATE_OK, age_secs=10.0)}
    t = window_truth(f, cells)
    assert t.now_pct == 99.0 and t.source == "live" and t.end_pct == 23.0


def test_window_truth_5h_local():
    f = Forecast("5h", 5000, 10000, 78.0, 90000.0, 8000.0, False, profile="claude")
    cells = {("claude", "5h"): LiveCell(pct=12.0, state=STATE_OK, age_secs=5.0)}
    t = window_truth(f, cells)
    assert t.now_pct == 50.0 and t.source == "local"  # used/cap, ignore live 5h


def test_window_truth_no_cells():
    f = Forecast("weekly", 400, 1000, 68.0, None, 1000.0, False, profile="claude")
    t = window_truth(f, None)
    assert t.source in ("local", "proj")
    assert t.now_pct is not None


def test_eta_for_race_at_wall():
    f = Forecast("weekly", 100, 1000, 23.0, None, 1000.0, False, profile="claude")
    t = _truth(now_pct=100.0, source="live", end_pct=23.0, cap=1000, reset_in=1000.0)
    assert eta_for_race(f, t) == 0.0


def test_eta_for_race_live_burn():
    # live 50%, end proj 100% over 3600s remaining → rate hits cap in 3600s from 50%
    f = Forecast("weekly", 100, 1000, 100.0, 999.0, 3600.0, False, profile="claude")
    t = _truth(now_pct=50.0, source="live", end_pct=100.0, cap=1000, reset_in=3600.0)
    eta = eta_for_race(f, t)
    assert eta is not None and abs(eta - 3600.0) < 1.0


def test_margin_line_variants():
    assert "already at the wall" in margin_line(_truth(now_pct=100.0), 0.0)
    assert "lose by" in margin_line(_truth(now_pct=50.0, reset_in=7200.0), 3600.0)
    assert "clear by" in margin_line(_truth(now_pct=50.0, end_pct=110.0, reset_in=3600.0), 7200.0)
    assert "headroom" in margin_line(_truth(now_pct=40.0, end_pct=50.0, reset_in=3600.0), None)
```

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

```bash
python -m pytest tests/test_dashboard.py -k "race_status or window_truth or eta_for_race or margin_line or profile_verdict" -v
```

Expected: `ModuleNotFoundError` or import error for `token_oracle.dashboard.race`.

- [ ] **Step 3: Implement `token_oracle/dashboard/race.py`**

```python
"""Pure cap-race helpers for the Future tab (plan 062). No I/O."""
from __future__ import annotations

from dataclasses import dataclass

from ..core.timeutil import fmt_dh_long

STATUS_RANK = {"OVER": 0, "TIGHT": 1, "SAFE": 2, "IDLE": 3, "UNKNOWN": 4}


@dataclass(frozen=True)
class Truth:
    now_pct: float | None
    source: str  # live | local | proj | none
    end_pct: float | None
    reset_in: float
    idle: bool
    window: str
    cap: int
    profile: str


def profile_canon(name: str) -> str:
    return "grok" if "grok" in (name or "").lower() else "claude"


def _window_kind(window: str) -> str:
    ww = (window or "").lower()
    if "5h" in ww or "session" in ww or "current" in ww:
        return "5h"
    if ww in ("weekly", "week"):
        return "weekly"
    if ww == "fable":
        return "fable"
    return "other"


def window_truth(f, cells=None) -> Truth:
    """Blend now_pct the same way Present does (see dashboard/app.py row blend).

    5h/session: local used/cap (web 5h lags; Present ignores it for the number).
    weekly/fable: live cell when pct is not None; else local used/cap or end-proj.
    Live is authoritative for **now** when present; end-proj alone can lag the site.
    """
    cells = cells or {}
    pname = getattr(f, "profile", "default") or "default"
    p_canon = profile_canon(pname)
    ww = getattr(f, "window", "?") or "?"
    kind = _window_kind(ww)
    idle = bool(getattr(f, "idle", False))
    end_pct = float(getattr(f, "projected_pct", 0.0) or 0.0)
    reset_in = float(getattr(f, "reset_in_secs", 0) or 0)
    cap = int(getattr(f, "cap", 0) or 0)
    used = int(getattr(f, "used", 0) or 0)

    now_pct: float | None = None
    source = "none"

    cell = None
    if kind in ("weekly", "fable", "5h"):
        cell = cells.get((p_canon, kind if kind != "5h" else "5h"))

    if kind == "5h":
        if cap > 0:
            now_pct = 100.0 * used / cap
            source = "local"
        elif end_pct is not None and not idle:
            now_pct = end_pct
            source = "proj"
    elif kind in ("weekly", "fable"):
        if cell is not None and getattr(cell, "pct", None) is not None:
            now_pct = float(cell.pct)
            source = "live"
        elif cap > 0 and not idle:
            now_pct = 100.0 * used / cap
            source = "local"
        elif not idle:
            now_pct = end_pct
            source = "proj"
    else:
        if cap > 0 and not idle:
            now_pct = 100.0 * used / cap
            source = "local"
        elif not idle:
            now_pct = end_pct
            source = "proj"

    return Truth(
        now_pct=now_pct,
        source=source,
        end_pct=end_pct,
        reset_in=reset_in,
        idle=idle,
        window=ww,
        cap=cap,
        profile=pname,
    )


def eta_for_race(f, truth: Truth) -> float | None:
    """Live-aware seconds-to-cap for the race clock."""
    now_pct = truth.now_pct
    if now_pct is not None and now_pct >= 100.0:
        return 0.0
    engine_eta = getattr(f, "eta_to_cap_secs", None)
    if truth.source == "live" and now_pct is not None and truth.cap > 0:
        live_used = (now_pct / 100.0) * truth.cap
        end_pct = truth.end_pct if truth.end_pct is not None else now_pct
        reset_in = truth.reset_in
        if end_pct > now_pct and reset_in > 0:
            remaining_tokens = (end_pct / 100.0) * truth.cap - live_used
            rate = remaining_tokens / reset_in
            if rate > 0:
                return (truth.cap - live_used) / rate
            return None
        return float(engine_eta) if engine_eta is not None else None
    return float(engine_eta) if engine_eta is not None else None


def race_status(truth: Truth, eta: float | None) -> str:
    if truth.idle:
        return "IDLE"
    now = truth.now_pct
    end = truth.end_pct
    if now is None and end is None:
        return "UNKNOWN"
    if (now is not None and now >= 100.0) or (
        eta is not None and truth.reset_in is not None and eta < truth.reset_in
    ):
        return "OVER"
    if (now is not None and now >= 85.0) or (end is not None and end >= 85.0):
        return "TIGHT"
    if now is not None or end is not None:
        return "SAFE"
    return "UNKNOWN"


def profile_verdict(statuses) -> str:
    best = "UNKNOWN"
    best_rank = STATUS_RANK["UNKNOWN"]
    for s in statuses or []:
        r = STATUS_RANK.get(s, STATUS_RANK["UNKNOWN"])
        if r < best_rank:
            best, best_rank = s, r
    return best


def margin_line(truth: Truth, eta: float | None) -> str:
    now = truth.now_pct
    if now is not None and now >= 100.0:
        return "already at the wall"
    reset_in = truth.reset_in
    if eta is not None and reset_in is not None:
        if eta < reset_in:
            return f"lose by {fmt_dh_long(reset_in - eta)}"
        if eta > reset_in:
            return f"clear by {fmt_dh_long(eta - reset_in)}"
    end = truth.end_pct if truth.end_pct is not None else 0.0
    n = now if now is not None else end
    headroom = max(0.0, 100.0 - max(n or 0.0, end or 0.0))
    return f"headroom ~{round(headroom)}% of cap"
```

- [ ] **Step 4: Run race tests — expect PASS**

```bash
python -m pytest tests/test_dashboard.py -k "race_status or window_truth or eta_for_race or margin_line or profile_verdict" -q
```

- [ ] **Step 5: Commit**

```bash
git add token_oracle/dashboard/race.py tests/test_dashboard.py
git commit -m "$(cat <<'EOF'
feat(dash): pure Future cap-race helpers (plan 062)

Add window_truth / eta_for_race / race_status / profile_verdict /
margin_line so Future can blend live cells with local end-proj.
EOF
)"
```

---

### Task 2: `render_future` race layout + `cells` wiring

**Files:**
- Modify: `token_oracle/dashboard/future.py`
- Modify: `token_oracle/dashboard/app.py` (~line 1326 `render_future` call)
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: Task 1 helpers; `cells` from `DashStore`
- Produces: `render_future(forecasts, profile, now, width, enabled, cost_line=None, cells=None) -> list[str]`

**Layout contract (width):**
- `width >= 72`: full lines + mini-bar on live/now row
- `48 <= width < 72`: drop mini-bar; keep status, live now, resets, race one-liner
- `width < 48`: profile status + one line per window: `{name} {STATUS} live {n}% · reset {fmt_reset}`

**Copy rules:**
- Header: `Future — cap race (live when available)` if any truth.source == live else `Future — cap race`
- Profile header when multi or always: `{PNAME}  ·  {VERDICT}` (verdict colored via gauge at 50/85/100)
- Per window:
  - `live now   {n}%   {bar}` when source==live; else `now        {n}%` / omit bar under 72
  - `resets in  {fmt_dh_long(reset)}` or compact `fmt_reset`
  - `cap race   hit in {fmt_dh_long(eta)} if pace holds` | `no hit before reset` | omit if idle
  - `margin     {margin_line}`
  - `end proj   {end}%  (local logs · may lag live)` only when source==live and end differs from now by >= 1.0; when local-only omit the lag note (just `end proj` if useful, or skip if same as now)
- Footer: existing spark + cost_line

- [ ] **Step 1: Write failing render tests**

```python
def test_render_future_live_disagree_shows_both():
    fs = [Forecast("fable", 100, 1000, 23.0, None, 400000.0, False, profile="claude")]
    cells = {("claude", "fable"): LiveCell(pct=99.0, state=STATE_OK, age_secs=5.0)}
    text = "\n".join(render_future(fs, None, 0.0, 100, False, cells=cells))
    assert "99%" in text and "23%" in text
    assert "TIGHT" in text or "OVER" in text  # 99% => TIGHT by rules; not SAFE
    assert "may lag live" in text
    assert "\033" not in text


def test_render_future_multi_profile_verdicts():
    fs = [
        Forecast("weekly", 100, 1000, 20.0, None, 1000.0, False, profile="claude"),
        Forecast("weekly", 100, 1000, 40.0, None, 1000.0, False, profile="grok"),
    ]
    cells = {
        ("claude", "weekly"): LiveCell(pct=100.0, state=STATE_OK, age_secs=1.0),
        ("grok", "weekly"): LiveCell(pct=40.0, state=STATE_OK, age_secs=1.0),
    }
    text = "\n".join(render_future(fs, None, 0.0, 100, False, cells=cells))
    assert "CLAUDE" in text and "OVER" in text
    assert "GROK" in text and "SAFE" in text


def test_render_future_no_cells_no_crash():
    fs = [Forecast("5h", 1000, 10000, 40.0, None, 3600.0, False)]
    text = "\n".join(render_future(fs, None, 0.0, 80, False))
    assert "SAFE" in text or "5h" in text
    assert "may lag live" not in text


def test_render_future_narrow_one_liner():
    fs = [Forecast("weekly", 100, 1000, 20.0, None, 200000.0, False, profile="claude")]
    cells = {("claude", "weekly"): LiveCell(pct=99.0, state=STATE_OK, age_secs=1.0)}
    text = "\n".join(render_future(fs, None, 0.0, 40, False, cells=cells))
    assert "99%" in text
    assert "TIGHT" in text or "OVER" in text
```

Update existing tests that assert old prophecy chrome:

```python
def test_render_future_window_and_warning():
    fs = [
        Forecast("5h", 1000, 10000, 78.0, 90000.0, 8000.0, False, profile="claude"),
        Forecast("weekly", 100, 1000, 40.0, None, 400000.0, False, profile="claude"),
    ]
    text = "\n".join(render_future(fs, [1.0] * 168, 1_000_000.0, 100, False))
    assert "5h" in text
    assert "cap race" in text.lower() or "resets" in text
    assert "next 24h" in text
    assert "\033" not in text
    # prophecy is no longer the hero — do not require "prophecy" / "cap in"


def test_render_future_no_warning_without_eta():
    fs = [Forecast("5h", 1000, 10000, 40.0, None, 3600.0, False)]
    text = "\n".join(render_future(fs, None, 0.0, 80, False))
    assert "no hit before reset" in text or "SAFE" in text
```

Keep `test_prophecy_*` as pure unit tests of the leftover helper (still exported).

- [ ] **Step 2: Run — expect FAIL on new strings**

- [ ] **Step 3: Implement layout in `future.py`**

Key signature change:

```python
def render_future(
    forecasts,
    profile,
    now: float,
    width: int,
    enabled: bool,
    cost_line: str | None = None,
    cells=None,
) -> list[str]:
```

Use `race_status` + color: map status to a synthetic pct for `c.gauge` — SAFE→50, TIGHT→90, OVER→100, IDLE/UNKNOWN→dim only.

Race one-liner:

```python
def _race_line(eta, truth, enabled) -> str:
    if truth.idle:
        return c.dim("    cap race   (idle)", enabled)
    if eta is None:
        return "    cap race   no hit before reset"
    if truth.now_pct is not None and truth.now_pct >= 100:
        return c.gauge("    cap race   already at the wall", 100.0, enabled)
    return c.gauge(f"    cap race   hit in {fmt_dh_long(eta)} if pace holds", 100.0 if eta < truth.reset_in else 50.0, enabled)
```

- [ ] **Step 4: Wire app.py**

```python
body = render_future(
    st.forecasts if st.has_present else [],
    st.profile,
    now,
    w,
    enabled,
    cost_line=st.cost_line,
    cells=st.cells,
)
```

- [ ] **Step 5: Run full dashboard tests**

```bash
python -m pytest tests/test_dashboard.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add token_oracle/dashboard/future.py token_oracle/dashboard/app.py tests/test_dashboard.py
git commit -m "$(cat <<'EOF'
feat(dash): Future tab live-aware cap-race layout (plan 062)

Pass DashStore cells into render_future; show SAFE/TIGHT/OVER with
live now vs end-proj when they disagree.
EOF
)"
```

---

### Task 3: Suite + README + manual smoke notes

**Files:**
- Modify: `plans/README.md` row 062 status
- Optional: touch nothing else if suite green

- [ ] **Step 1: Full suite**

```bash
python -m pytest -q
```

Expected: all passed (count ≥ prior).

- [ ] **Step 2: Present regression spot-check (optional assert)**

```bash
python -m pytest tests/test_dashboard.py -k "render_frame or compact or bars" -q
```

- [ ] **Step 3: Update README row 062 to DONE with commit tip**

- [ ] **Step 4: Commit docs**

```bash
git add plans/README.md plans/062-future-race-ux.md
git commit -m "docs(plans): 062 Future race UX impl plan + DONE status"
```

- [ ] **Step 5: Manual smoke (operator)**

```bash
oracle dash
# open Future tab — multi-profile: when Present weekly/fable ~full live, Future shows TIGHT/OVER + both %
```

---

## Spec coverage checklist

| Design requirement | Task |
|--------------------|------|
| race_status table | T1 |
| window_truth live blend | T1 |
| eta_for_race at wall / live burn | T1 |
| margin_line | T1 |
| profile_verdict | T1 |
| render layout + live/end both | T2 |
| multi-profile headers | T2 |
| width collapse | T2 |
| cells from app, no extra scrape | T2 |
| no fake probability | T2 (omit) |
| color off | T2 tests |
| Present unchanged | T2/T3 |
| spark/cost secondary | T2 |
| Non-goals (engine, 012, Present redesign) | not in plan |

## Placeholder scan

None intentional. All signatures and test bodies are concrete.
