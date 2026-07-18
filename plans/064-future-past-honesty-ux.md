# Future/Past honesty UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Future and Past tabs read as natural, professional, and predictable — no physically-impossible forecasts, no self-contradicting lines, no misleading sparkline or over-100% "cap" column, and the same provenance a cell shows on Present.

**Architecture:** Pure fixes in `dashboard/race.py` (the impossible-hit guard, caption/margin reconciliation, live-above-end handling, provenance threaded into `Truth`) and `dashboard/future.py` / `dashboard/past.py` (render caveats, sparkline scale, Past TOTAL relabel, ANSI-safe truncation). No engine changes — consumes the already-correct numbers from plan 063.

**Tech Stack:** Python 3.10+, stdlib only. Existing `race.Truth`, `LiveCell`, `cli.colors`, `scene.truncate_display`, `report`.

**Design source:** `plans/063-present-truth-anchoring-design.md` (approved, Layer 3). Runs AFTER plan 063.

## Global Constraints

- Stdlib only; no new dependencies.
- Quiet oracle tone: one-word verdicts, no invented probability %, no pulse banners.
- Color off → no `\033` in output.
- Present render stays stable except the honest-age badge from 063.
- Same `(profile, window)` cell must read identically on Present and Future (I4).
- Suite green (post-063 count) and larger; `ruff`/`format`/`mypy` clean.

## File map

| File | Role |
|------|------|
| Modify `token_oracle/dashboard/race.py` | impossible-hit guard, caption/margin reconcile, live>end handling, age/source on `Truth` |
| Modify `token_oracle/dashboard/future.py` | render caveats (age/retained), sparkline cap-scale, label alignment, safe truncation |
| Modify `token_oracle/dashboard/past.py` | TOTAL `%weekly-cap` relabel, safe truncation |
| Modify `token_oracle/core/report.py` | (only if the TOTAL ratio label lives here) |
| Modify `tests/test_dashboard.py` | new render assertions |
| Modify `plans/README.md` | 064 row |

---

### Task 1: Kill the impossible hit + reconcile caption/margin (predictable)

**Files:** Modify `token_oracle/dashboard/race.py`, `token_oracle/dashboard/future.py`; Test `tests/test_dashboard.py`.

**Rules:** when `eta >= reset_in` the window resets before any hit — caption says so, and the caption never contradicts `margin_line`.

- [ ] **Step 1: Write failing tests**

```python
from token_oracle.dashboard.race import Truth, eta_for_race, margin_line
from token_oracle.dashboard.future import render_future
from token_oracle.core.contracts import Forecast
from token_oracle.live.overlay import LiveCell
from token_oracle.live.contract import STATE_OK

def test_no_hit_shown_when_eta_after_reset():
    # eta 1.25*reset > reset -> "resets first / no hit", never "hit in"
    fs = [Forecast("weekly", 500, 1000, 90.0, None, 3600.0, False, profile="claude")]
    cells = {("claude","weekly"): LiveCell(pct=50.0, state=STATE_OK, age_secs=5.0)}
    text = "\n".join(render_future(fs, None, 0.0, 100, False, cells=cells))
    assert "resets first" in text or "no hit before reset" in text
    assert "hit in" not in text.split("resets first")[0][-40:]  # no contradictory hit caption

def test_caption_and_margin_agree():
    # when caption says clear/no-hit, margin must not say "lose by"
    t = Truth(now_pct=50.0, source="live", end_pct=60.0, reset_in=3600.0,
              idle=False, window="weekly", cap=1000, profile="claude")
    eta = eta_for_race(_fc(reset=3600.0), t)  # eta >= reset
    m = margin_line(t, eta)
    assert "lose by" not in m  # cannot lose a race the window ends first
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement**
  - `future._race_caption`: when `eta is None` or `eta >= truth.reset_in` → `"    cap race   resets first — no hit"`. Only when `eta < reset_in` → `"    cap race   hit in {fmt_dh_long(eta)} if pace holds"`.
  - `race.margin_line`: when `eta is None or eta >= reset_in` → headroom / "clear" wording; only emit `"lose by …"` when `eta < reset_in`. Ensure caption and margin derive the win/lose decision from the SAME `eta < reset_in` test.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -am "fix(dash): no impossible cap-hit; caption/margin agree (plan 064)"`.

---

### Task 2: Live-now above local end-proj (no reassuring caption under an alarming number)

**Files:** Modify `token_oracle/dashboard/race.py`, `token_oracle/dashboard/future.py`; Test `tests/test_dashboard.py`.

**Rules:** when `now_pct > end_pct` (local logs lag the live reading), the race clock derives from the live reading (or clamps `end_pct` up to `now_pct`) — never `no hit before reset` printed under a 99% live-now.

- [ ] **Step 1: Write failing test**

```python
def test_live_now_high_not_reassured():
    fs = [Forecast("weekly", 100, 1000, 23.0, None, 3600.0, False, profile="claude")]  # local proj lags
    cells = {("claude","weekly"): LiveCell(pct=99.0, state=STATE_OK, age_secs=3.0)}
    text = "\n".join(render_future(fs, None, 0.0, 100, False, cells=cells))
    assert "99%" in text
    assert "TIGHT" in text or "OVER" in text
    # the race caption must NOT reassure below a 99% live-now
    assert "no hit before reset" not in text
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement** — in `race.eta_for_race`, when `source == "live"` and `now_pct >= end_pct`, clamp `end_pct = max(end_pct, now_pct)` before deriving the rate (or derive ETA from live burn), so a high live-now can't fall back to a stale engine ETA of `None` that reads as "safe".
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -am "fix(dash): live-now above end-proj drives the race clock (plan 064)"`.

---

### Task 3: Provenance parity — Future shows the same age/source as Present (I4)

**Files:** Modify `token_oracle/dashboard/race.py`, `token_oracle/dashboard/future.py`; Test `tests/test_dashboard.py`.

**Rules:** a cell that reads `retained last-good` / `live header · Ns ago` on Present must carry the same caveat on Future; a retained/over-fresh cell is never labelled bare `live now`.

- [ ] **Step 1: Write failing test**

```python
def test_future_shows_retained_age_like_present():
    fs = [Forecast("weekly", 100, 1000, 23.0, None, 3600.0, False, profile="claude")]
    cells = {("claude","weekly"): LiveCell(pct=48.0, state=STATE_OK, age_secs=7200.0,
                                           extractor="modal+retained")}  # retained, 2h old
    text = "\n".join(render_future(fs, None, 0.0, 100, False, cells=cells))
    assert "48%" in text
    assert "retained" in text or "~2h" in text or "2h ago" in text
    assert "live now  48%" not in text  # must NOT read as fresh live
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement**
  - Add `age_secs: float | None` and `is_retained: bool` (or `source_note: str`) to `race.Truth`; `window_truth` copies them from the chosen cell (`cell.age_secs`, `cell.extractor`, `cell.is_retained` from 063 Task 5).
  - `future._render_window_*`: when the cell is retained or `age > FRESH_TTL`, render `retained · ~{h}h old` / `{n}s ago` next to the number and use a dimmer label than `live now` — mirror Present's `_render_profile_block` wording.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -am "feat(dash): Future/Present provenance parity, no stale-as-live (plan 064, I4)"`.

---

### Task 4: Sparkline scale + Past TOTAL relabel + safe truncation

**Files:** Modify `token_oracle/dashboard/future.py`, `token_oracle/dashboard/past.py`, `token_oracle/core/report.py` (if TOTAL label lives there); Test `tests/test_dashboard.py`.

- [ ] **Step 1: Write failing tests**

```python
def test_spark_flat_profile_not_all_full():
    # a flat low-burn 24h profile must not render 24 full blocks
    fs = [Forecast("5h", 1000, 10000, 40.0, None, 3600.0, False, profile="claude")]
    text = "\n".join(render_future(fs, [1.0]*168, 1_000_000.0, 100, False))
    # not a solid wall of the top glyph
    assert text.count("█") < 24 or "relative to peak" in text

def test_past_total_not_labeled_weekly_pct():
    # the summed 14-day-over-weekly TOTAL must not be a bare %weekly-cap that reads >100 as over-limit
    rows = ...  # build a past ledger whose 14-day sum exceeds one weekly cap
    text = "\n".join(render_past(rows, ...))
    # TOTAL uses a distinct label (×weekly / of cap over N days), not a red per-day-style %
    assert "×weekly" in text or "over" in text
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement**
  - `future.spark_next24`: normalize hour levels against a cap-anchored or fixed scale, OR annotate `relative to peak`, so a flat profile no longer maps every hour to the top glyph.
  - `past` TOTAL row: give the summed ratio its own label (`×weekly` or `of cap over {N}d`), or drop `pct` on TOTAL; keep per-day `%weekly-cap` as is.
  - Route Future/Past overflow through `scene.truncate_display` instead of `line[:width]`; unify the `now`/`live now` label column width so the pct column doesn't shift between rows.
- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -am "fix(dash): honest sparkline scale, Past TOTAL label, ANSI-safe truncation (plan 064)"`.

---

### Task 5: Suite, gates, README, smoke

- [ ] **Step 1:** `python -m pytest -q` — all pass, count grows.
- [ ] **Step 2:** `ruff check`, `ruff format --check`, `mypy` — clean.
- [ ] **Step 3:** Present regression spot-check — `python -m pytest tests/test_dashboard.py -k "render_frame or compact or bars or profile_block" -q`.
- [ ] **Step 4:** Manual smoke (operator) — `oracle dash`, open Future + Past; confirm no "hit in {>reset}", no contradiction, retained cells show age on both tabs.
- [ ] **Step 5:** `plans/README.md` row 064 → DONE.
- [ ] **Step 6:** `git commit -am "docs(plans): 064 Future/Past honesty UX DONE"`.

---

## Spec coverage checklist

| Design requirement | Task |
|---|---|
| kill impossible hit | T1 |
| caption/margin reconcile | T1 |
| live-now above end-proj | T2 |
| provenance parity (I4) | T3 |
| sparkline cap-scale | T4 |
| Past TOTAL relabel | T4 |
| label alignment + safe truncation | T4 |
| suite + gates | T5 |
| Present unchanged (except age badge) | T3/T5 |

## Placeholder scan

`...` appears only in Task 4's Past-ledger fixture where the row shape depends on the exact `render_past`/`report` signatures; the asserted behavior is fully specified. Implementer reads existing `test_dashboard.py` past tests for the fixture idiom.
