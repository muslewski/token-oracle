# Plan 037: Claude's Fable weekly meter is extracted as its own high-confidence reading, distinct from "All models"

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, report your result; the reviewer
> maintains `plans/README.md` (you may skip the index edit).
>
> **Drift check (run first)**:
> `git diff --stat 059ad33..HEAD -- token_oracle/live/web.py token_oracle/live/claude_extract.py`
> Note: plan 035 (merged) changed `web.py`'s *display* handling and the
> `fetch_claude_live_usage` preflight, NOT the DOM-collection JS you edit here.
> Confirm the "Current state" excerpt below matches before editing; on a
> mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED (touches the live claude DOM collector; row-level regression-tested against real captured data)
- **Depends on**: `plans/035-headed-display-lifecycle.md` (DONE, merged — headed probing works, which is how this bug was captured). No file conflict with plan 036.
- **Category**: bug
- **Planned at**: commit `059ad33` (base for excerpts; you branch from current main), 2026-07-10

## Why this matters

On claude.ai's usage page, the **Fable** model has its own weekly limit meter,
separate from the **All models** weekly pool. Ground truth captured live
2026-07-10 from the operator's logged-in account:

```
Current session   Resets in 3 hr 21 min   23% used     (five-hour / session)
Weekly limits
  All models      Resets Thu 9:00 PM      59% used     (weekly pool)
  Fable           Resets Thu 9:00 PM      99% used     (Fable-specific weekly)   <-- nearly exhausted
```

The live probe currently reports only **`weekly_pct = 59` (All models)** and
**drops Fable entirely** — its evidence string even truncates to
`"... 59% used\nFabl"`, proving it grabbed a merged block and stopped at the
first percentage. So the tool hides that Fable is at **99%** (effectively out) —
the single most important number for a Fable-heavy user, and exactly the
"Fable not distinguished from All models" symptom from the original brief.

Root cause is **precisely located** and is entirely in the DOM *collection*
step in `web.py`, not the pure extractor:

- The page renders each meter as a `<div aria-valuenow="N" aria-valuemax="100">`
  progress bar. Captured live, there are exactly **4** such bars:
  `23` (bg-accent, session), `59` (bg-accent, All models), `99` (bg-danger,
  Fable), `0` (bg-accent, aria-label "Usage credits").
- The current JS climbs each bar up to the nearest
  `section|li|card|usage|row` ancestor. For both weekly bars (59 and 99) that
  ancestor is the **same merged "Weekly limits" card** (which contains both
  meters). The collector then dedups rows by the first 80 chars of text, so the
  two weekly bars collapse into **one** row. `readings_from_rows` sees one row
  containing two percentages and emits only the first (`59`). Fable is lost.

**Proven** (run against the current pure extractor):
- Feed it **atomic** rows (one meter each, each carrying its bar's
  `valuenow`) → it already emits `weekly_pct=59` **and**
  `model_weekly_pct=99 (model="fable")` **and** `five_hour_pct=23`, all correct.
- Feed it the **merged** block → it emits only `weekly_pct=59`; Fable gone.

So the fix is to make the collector produce **one atomic row per bar** (climb to
the *maximal single-`%` ancestor*, not the coarse card), plus a defensive
Python splitter so a merged row can never again silently swallow a second meter.
The pure classifier (`classify_row`, `readings_from_rows`, `distinctness_check`)
is already correct and needs no change.

After this: the claude probe emits a high-confidence `model_weekly_pct=99
(model=fable)` reading distinct from `weekly_pct=59`, so the dash shows Fable's
real 99%.

## Current state

Files:
- `token_oracle/live/web.py` — `fetch_claude_live_usage`. The DOM collection is
  a single `page.evaluate(...)` JS string producing `{rows: [...]}` where each
  row is `{valuenow, valuemax, label, text}`. This is the buggy part.
- `token_oracle/live/claude_extract.py` — pure classifier. `classify_row`
  already maps "all models"→`weekly_pct`, "fable|opus|sonnet|haiku" (and not
  "all models")→`model_weekly_pct`, "current session|5h"→`five_hour_pct`.
  `readings_from_rows`, `distinctness_check` already correct. You will ADD one
  defensive splitter here; do not change the existing classification.
- `tests/test_live_claude_extract.py` — existing pure-extractor tests (10).

### The buggy collector — `token_oracle/live/web.py:695-744` (inside `fetch_claude_live_usage`)

```javascript
() => {
  const rows = [];
  const seen = new Set();
  const barSel = '[role=progressbar], progress, [aria-valuenow]';
  document.querySelectorAll(barSel).forEach(el => {
    const vn = el.getAttribute('aria-valuenow') || (el.value != null ? String(el.value) : null);
    const vm = el.getAttribute('aria-valuemax') || null;
    let container = el.closest('section, li, [class*="card" i], [class*="usage" i], [class*="row" i]') || el.parentElement || el;
    // climb a few levels if needed
    for (let i = 0; i < 3 && container && container.parentElement; i++) {
      const p = container.parentElement;
      const pc = (p.className || '').toString();
      if (/section|li|card|usage|row/i.test(pc) || ['SECTION','LI'].indexOf(p.tagName) >= 0) {
        container = p; break;                         // <-- lands on the MERGED weekly card
      }
      container = p;
    }
    const txt = (container && (container.innerText || container.textContent) || '').trim().replace(/\s+/g, ' ').slice(0, 300);
    let lb = '';
    if (container) {
      const heads = container.querySelectorAll('h1,h2,h3,h4,h5,strong,span,[class*="label" i],[class*="heading" i]');
      if (heads.length) lb = (heads[0].innerText || heads[0].textContent || '').trim().replace(/\s+/g, ' ').slice(0, 120);
    }
    if (!lb) lb = txt.slice(0, 120);
    const key = (txt || lb).slice(0, 80);
    if (key && !seen.has(key)) { seen.add(key); rows.push({valuenow: vn, valuemax: vm, label: lb, text: txt}); }
  });
  // Also capture session/current containers that may lack a progressbar (idle 5h)
  const csel = 'section, li, [class*="card" i], [class*="usage" i], [class*="row" i], [class*="session" i]';
  document.querySelectorAll(csel).forEach(el => {
    const t = (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 300);
    if (t && /(current\s*session|session|5.?h|5-hour)/i.test(t)) {
      const k = t.slice(0, 80);
      if (!seen.has(k)) {
        seen.add(k);
        const hasBar = el.querySelector(barSel);
        if (!hasBar) rows.push({valuenow: null, valuemax: null, label: 'Current session', text: t});
      }
    }
  });
  return {rows: rows.slice(0, 40)};
}
```

The extracted rows feed the pure classifier at `web.py:759-763`:
```python
            try:
                rows = facts.get("rows") or []
                readings.extend(readings_from_rows(rows, now))
            except Exception:
                pass
```

### Ground-truth DOM (captured live 2026-07-10) — use for fixtures

Four `[aria-valuenow]` bars, each `aria-valuemax="100"`:

| valuenow | class token | atomic (maximal single-`%`) ancestor text |
|---|---|---|
| 23 | bg-accent | `Current session\nResets in 3 hr 21 min\n23% used` |
| 59 | bg-accent | `All models\nResets Thu 9:00 PM\n59% used` |
| 99 | bg-danger | `Fable\nResets Thu 9:00 PM\n99% used` |
| 0  | bg-accent (aria-label "Usage credits") | `€0.00 spent\nResets Aug 1\n0% used` |

The merged card the current code lands on (single row today):
`Weekly limits\nLearn more about usage limits\nAll models\nResets Thu 9:00 PM\n59% used\nFable\nResets Thu 9:00 PM\n99% used`

### Repo conventions

- **Truthfulness / evidence-bound**: every reading carries `evidence` from its
  *own* row. Do not widen matching. See `plans/030-*.md`, `032-*.md`.
- **Confidence**: aria `valuenow`/`valuemax` → high confidence
  (`claude.usage_row.aria`); text-only `%` → medium (`claude.usage_row.text`).
  The dash overlay only applies HIGH-confidence readings — so Fable must come
  from the bar's aria value (keep the per-bar `valuenow`), not a text re-parse,
  or it won't display.
- Pure functions get pure tests with fixtures (see `tests/test_live_claude_extract.py`).
- stdlib only.

## Commands you will need

| Purpose   | Command                                              | Expected |
|-----------|------------------------------------------------------|----------|
| Install   | `pip install -e ".[dev]"`                            | exit 0   |
| Tests     | `python -m pytest -q tests/test_live_claude_extract.py` | all pass |
| Full suite| `python -m pytest -q`                                | all pass |
| Lint      | `ruff check token_oracle/live/ tests/test_live_claude_extract.py` | your files clean* |
| Format    | `ruff format --check token_oracle/live/`             | clean    |
| Types     | `mypy --ignore-missing-imports token_oracle/live/`   | no new errors |

\* NOTE: `tests/test_engine.py`, `tests/test_pricing.py`, `tests/test_sources_grok.py`,
and pre-existing lines in `tests/test_live_claude_extract.py` have **pre-existing**
lint issues you did NOT cause. Do not fix them (out of scope). Only your own new
/ edited lines must be clean.

## Scope

**In scope**:
- `token_oracle/live/web.py` — the claude DOM-collection JS (the bar-climb).
- `token_oracle/live/claude_extract.py` — ADD a defensive `split_multi_meter_rows`
  helper; call it at the top of `readings_from_rows`. Do NOT alter `classify_row`
  logic.
- `tests/test_live_claude_extract.py` — new fixtures + tests.
- `tests/fixtures/live/` — add a JSON fixture if you follow the existing fixture
  pattern there (check `ls tests/fixtures/live/` first; match it).

**Out of scope** (do NOT touch):
- `token_oracle/live/probe.py`, `contract.py`, `store.py`, `overlay.py`,
  `extract_common.py`, `grok_extract.py`, and the display/`virtual_display`
  logic in `web.py` (plan 035, merged — leave it).
- `token_oracle/cli/main.py`, `token_oracle/dashboard/app.py`, `core/config.py`
  (plan 036 territory).
- grok extraction/navigation.

## Git workflow

- Branch: `advisor/037-claude-fable-row-separation` (reviewer created the worktree).
- Commit per step (conventional commits, e.g.
  `fix(live): collect atomic per-meter claude rows so Fable is not swallowed`).
- **Commit early and often.** Do NOT push, PR, or merge.

## Steps

### Step 1: Collector climbs to the maximal single-`%` ancestor (web.py JS)

In the `document.querySelectorAll(barSel).forEach(...)` block, REPLACE the
container-selection (the `el.closest(...)` line + the 3-level climb loop that
breaks on `section|li|card|usage|row`) with a climb that finds the **largest
ancestor whose innerText still contains exactly ONE `%`**. Target shape:

```javascript
    // Climb to the MAXIMAL ancestor whose text has exactly one "%" — this is
    // the atomic meter block (its own label + reset + "N% used"), NOT the
    // merged multi-meter card. Prevents All-models and Fable collapsing to one row.
    const pctCount = (s) => ((s || '').match(/%/g) || []).length;
    let container = el.parentElement || el;
    let best = container;
    for (let i = 0; i < 6 && container && container.parentElement; i++) {
      const p = container.parentElement;
      const t = (p.innerText || p.textContent || '');
      if (pctCount(t) === 1 && t.length < 220) { best = p; container = p; }
      else break;   // next level up would merge a second meter (or is too big)
    }
    container = best;
```

Keep the rest (txt/label/seen/push) as-is — but change the `seen` dedup key so
distinct meters aren't collapsed: dedup on the **full** `txt` (not `slice(0,80)`),
since "All models … 59% used" and "Fable … 99% used" differ. Everything else
(label heading pick, the second `csel` idle-session pass, `rows.slice(0,40)`)
stays.

This JS runs in the browser and can't be unit-tested from pytest — its
correctness is covered by (a) the row-level fixture tests below, which assert the
extractor produces the right readings from the atomic rows this JS now yields,
and (b) the reviewer's live headed probe on merge.

**Verify**: `python -c "import token_oracle.live.web"` → no error (JS is a string;
this just checks the file still parses).

### Step 2: Defensive splitter in `claude_extract.py`

Add a pure helper and call it first in `readings_from_rows`, so even if a row
still arrives with multiple meters, each meter becomes its own atomic row (this
also makes the fix testable without a browser):

```python
_METER_RE = re.compile(
    r"(?i)(all\s*models|fable|opus|sonnet|haiku|current\s*session)"
    r"(?P<body>.*?)(?P<pct>\d{1,3}(?:\.\d)?)\s*%\s*used"
)

def split_multi_meter_rows(rows: list[dict]) -> list[dict]:
    """If a row's text contains >=2 'N% used' meters, split it into one atomic
    row per meter (label = the meter name, text = that meter's slice). Rows with
    0 or 1 meters pass through unchanged. Atomic rows keep their aria valuenow;
    split rows drop it (valuenow=None) so the % comes from the meter's own text
    (medium confidence) — better a medium Fable reading than a lost one."""
    out: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "")
        matches = list(_METER_RE.finditer(text))
        if len(matches) <= 1:
            out.append(row)
            continue
        for m in matches:
            label = re.sub(r"\s+", " ", m.group(1)).strip()
            seg = m.group(0).strip()
            out.append({"valuenow": None, "valuemax": None, "label": label, "text": seg})
    return out
```

Then at the very top of `readings_from_rows`, before the loop:
```python
    rows = split_multi_meter_rows(rows)
```
Confirm `re` is imported (it is). Do not change `classify_row`,
`distinctness_check`, or anything else.

**Verify**: quick REPL (or fold into Step 3 tests):
```
python -c "
from token_oracle.live.claude_extract import split_multi_meter_rows as s
merged=[{'valuenow':'59','valuemax':'100','label':'Weekly limits','text':'Weekly limits Learn more All models Resets Thu 9:00 PM 59% used Fable Resets Thu 9:00 PM 99% used'}]
print([r['label'] for r in s(merged)])
"
```
→ `['all models', 'Fable']` (or similar two-element list).

### Step 3: Tests (`tests/test_live_claude_extract.py`)

Add tests using the captured ground truth. Model structure after existing tests
in the file.

1. `test_atomic_rows_emit_fable_high_conf`: build the 4 atomic rows AS THE FIXED
   JS PRODUCES THEM (with aria valuenow):
   ```python
   rows = [
     {"valuenow":"23","valuemax":"100","label":"Current session","text":"Current session Resets in 3 hr 21 min 23% used"},
     {"valuenow":"59","valuemax":"100","label":"All models","text":"All models Resets Thu 9:00 PM 59% used"},
     {"valuenow":"99","valuemax":"100","label":"Fable","text":"Fable Resets Thu 9:00 PM 99% used"},
     {"valuenow":"0","valuemax":"100","label":"Usage credits","text":"€0.00 spent Resets Aug 1 0% used"},
   ]
   ```
   Call `distinctness_check(readings_from_rows(rows, 1000.0))`. Assert:
   - a `weekly_pct` reading with value `59.0`, `model is None`, confidence `high`;
   - a `model_weekly_pct` reading with value `99.0`, `model == "fable"`,
     confidence `high`;
   - a `five_hour_pct` reading with value `23.0`;
   - NO reading with value `0.0` from the credits row (credits is not a usage
     meter — `classify_row` returns None for "Usage credits"/"€0.00 spent"; if it
     leaks, tighten by asserting no reading has `model`/metric tied to credits).
2. `test_merged_row_still_yields_fable`: feed the single MERGED block (from
   "Ground-truth DOM" above) as one row. Assert the result still contains
   `model_weekly_pct == 99.0 (model="fable")` AND `weekly_pct == 59.0` — i.e. the
   defensive splitter prevents the swallow. (This is the regression lock for the
   exact bug.)
3. `test_fable_and_all_models_distinct`: assert that when both are present they
   are two separate readings with different values (59 vs 99) and
   `distinctness_check` keeps both (they come from different rows/evidence).

Verification: `python -m pytest -q tests/test_live_claude_extract.py` → all pass
incl. new tests; then full `python -m pytest -q`.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `python -m pytest -q` exits 0 (full suite)
- [ ] New tests exist and pass: atomic-rows→Fable-high-conf, merged-row→Fable-not-swallowed, distinctness
- [ ] `split_multi_meter_rows` exists in `claude_extract.py` and is called at the
      top of `readings_from_rows`
- [ ] The web.py collector no longer climbs to `section|li|card` for the meter
      container: `grep -n "closest('section" token_oracle/live/web.py` returns no
      match in `fetch_claude_live_usage` (the `barSel` closest line is gone/replaced)
- [ ] `ruff check` clean on your edited files; `ruff format --check token_oracle/live/` clean;
      `mypy --ignore-missing-imports token_oracle/live/` no new errors
- [ ] Only in-scope files modified (`git status`)

## STOP conditions

Stop and report back (do not improvise) if:
- The drift check shows `web.py`/`claude_extract.py` changed since `059ad33` and
  the "Current state" JS excerpt no longer matches (035 changed display code, not
  this JS — if the JS itself differs, STOP).
- `classify_row` does NOT already map "fable" → `model_weekly_pct` (grep it) — if
  the classifier differs from this plan's description, STOP and report; do not
  rewrite the classifier.
- A test needs a real browser/network — all tests here are pure/fixture-based.
- The pure extractor fails to emit `model_weekly_pct=99` from the atomic-rows
  fixture even after your changes — that means classification changed; STOP.

## Maintenance notes

- The definitive proof (a live headed probe returning
  `model_weekly_pct=99 model=fable` for claude) will be run by the reviewer on
  merge — the executor's gates are the row-level fixture tests because
  `page.evaluate` JS can't be unit-tested from pytest.
- The "maximal single-`%` ancestor" climb is the load-bearing heuristic. If
  claude's usage page markup changes (e.g. two meters share one `%`-bearing
  block), the defensive `split_multi_meter_rows` is the backstop; the aria
  `valuenow` per bar is the high-confidence source. A reviewer should re-capture
  the DOM (headed probe + debug dump) if claude restructures the page.
- Credits meter (`aria-label="Usage credits"`, "€… spent … 0% used") is
  intentionally NOT a usage reading; keep `classify_row` returning None for it.
- Reset timestamps: "Resets Thu 9:00 PM" is an absolute weekday/time, which the
  current relative-time reset parser may not handle — that's fine and out of
  scope here (this plan is about the percentage rows). Do not add absolute-date
  reset parsing in this plan.
