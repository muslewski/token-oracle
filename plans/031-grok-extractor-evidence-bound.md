# Plan 031: Grok extractor — evidence-bound readings, no fabricated percentages

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git log --oneline -5` must show plan 030's
> commit (branch `advisor/030-*` merged). `token_oracle/live/contract.py` and
> `token_oracle/live/web.py` must exist. If not → STOP (030 not landed).

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED (live-site DOM may differ from assumptions; fixtures + STOP conditions bound it)
- **Depends on**: plans/030-live-truthfulness-contract.md
- **Category**: bug
- **Planned at**: commit `2660dd1` + live-web WIP, 2026-07-10 (excerpt line numbers refer to the pre-030 `sources/live_web.py`; after 030 the same code lives in `token_oracle/live/web.py`)

## Why this matters

The Grok scraper currently *manufactures* percentages. Observed in real usage:
it reported ~13% while grok.com showed 10%, and it has turned the short-term
chat rate limit ("150/150 queries per 2h") into a usage number. The root
causes are all in the extraction heuristics, which run regexes over a giant
concatenated soup of page text + `__NEXT_DATA__` JSON + captured API JSON:

- "first % anywhere on the page wins" (`live_web.py:410-413`);
- any `aria-valuenow`/CSS `style.width` value from ANY element is promoted to
  `overall_pct` (`:441-453`) — a style width of `13%` on an unrelated element
  becomes 13% usage;
- keyword-within-90-chars regex windows (`:456-465`) where the keyword set
  includes the literal word "grok" — which matches everywhere on grok.com;
- fraction patterns (`:417-437`) that can convert "150/150" query counts into
  a percentage even though a later guard (`:487-500`) only protects the
  structured-API path.

This plan replaces those heuristics with a small set of **pure, fixture-tested
extraction functions** that only emit a `LiveReading` when the number is
anchored to an explicit label or a known structured payload, with the evidence
string carried on the reading. If nothing anchors, the honest result is
`authenticated_no_data` — never a guess.

## Current state

- `token_oracle/live/web.py` — `fetch_grok_live_usage` (pre-030 lines 140–565):
  browser driver + all the heuristics listed above, interleaved.
- `token_oracle/live/contract.py` (from plan 030) — `LiveReading`,
  `ProviderLive`, `METRIC_*`, `CONF_*` constants. Read it fully before coding.
- `token_oracle/live/legacy.py` (from plan 030) — the conservative adapter this
  plan makes obsolete for grok.
- A real captured-payload fact you must preserve: the app fetches a JSON body
  containing `remainingQueries`, `totalQueries`, `windowSizeSeconds` — this is
  the **2h chat rate limit**, not the weekly cap (existing comment at
  `live_web.py:487-500` documents this; keep that semantics).
- Known failure mode to fix: the `page.on("response", ...)` listener is
  registered **after** `page.goto(url)` (`live_web.py:200-231`), so the
  initial XHR burst — which typically includes the authoritative usage
  payload — is missed. Register listeners before any navigation.
- Navigation drift: the scraper often ends up on the main chat shell instead
  of a populated `/settings/usage` (existing mitigation is a pile of blind
  `get_by_text(...).click()` loops at `:254-316`).

Repo conventions: stdlib-only core; playwright only inside `live/web.py`
guarded by `PLAYWRIGHT_AVAILABLE`; pure logic must be importable and testable
without playwright installed. Tests: plain pytest functions. Ruff line 100.

## Commands you will need

| Purpose | Command | Expected |
|---------|---------|----------|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests   | `python -m pytest -q` | all pass |
| Lint    | `ruff check token_oracle/` + `ruff format --check token_oracle/` | exit 0 |
| Types   | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |
| Manual probe (optional, needs logged-in profile) | `TOKEN_ORACLE_SKIP_BOOTSTRAP=1 ~/.local/share/token-oracle/venv/bin/python -c "from token_oracle.live.web import fetch_grok_live_usage; print(fetch_grok_live_usage(headless=True))"` | dict with readings or honest empty state |

## Scope

**In scope**:
- `token_oracle/live/grok_extract.py` (create — pure functions, no playwright import)
- `token_oracle/live/web.py` — only the grok driver (`fetch_grok_live_usage`)
- `token_oracle/live/legacy.py` — delete the grok branch once web.py returns
  `ProviderLive` natively for grok (keep the claude branch until plan 032)
- `tests/test_live_grok_extract.py` (create)
- `tests/fixtures/live/` (create — JSON/text fixtures)
- `plans/README.md` (status row)

**Out of scope**:
- The Claude fetcher (`fetch_claude_live_usage`) — plan 032.
- `live/overlay.py`, `live/store.py`, `live/contract.py` — consume as-is; if
  the contract is missing something, STOP and report instead of extending it.
- `token_oracle/sources/grok.py` (local log adapter) — unrelated.
- Dashboard/CLI/engine.

## Git workflow

- Branch: `advisor/031-grok-extractor-evidence-bound`
- Conventional commits, e.g. `fix(live): grok extractor emits evidence-bound readings only`

## Steps

### Step 1: Pure extraction module

Create `token_oracle/live/grok_extract.py` with these functions (no playwright
import anywhere in this file):

```python
"""Pure extraction: page facts in, LiveReadings out. Every reading cites its
evidence. No generic fallbacks: a percentage with no recognized label is not
data, it is noise. Returns [] rather than guessing."""
```

1. `readings_from_network_json(url: str, obj: dict, now: float) -> list[LiveReading]`
   — explicit allowlist table, nothing fuzzy:
   - key set ⊇ `{remainingQueries, totalQueries}` → one METRIC_RATE_WINDOW
     reading, value = `(total-remaining)/total*100`, confidence **high**,
     extractor `"grok.network_json.rate"`, evidence
     `f"remainingQueries={rem} totalQueries={tot} windowSizeSeconds={w} url={url[-60:]}"`.
     Never emit weekly/usage metrics from this shape.
   - a dict (top-level or one level deep) whose keys match a documented
     usage shape — search the captured payloads for keys named exactly like
     `usagePercent`, `weeklyUsagePercent`, `buildUsagePercent`, `used`+`limit`
     under a parent key containing `usage`/`quota` — emit METRIC_WEEKLY_PCT,
     confidence **high**, extractor `"grok.network_json.usage"`, evidence =
     the matched key path + values. If the real payload uses different key
     names, the fixture step (Step 4) will catch it; do NOT loosen matching to
     "any numeric value" (that is the bug this plan deletes).
   - anything else → `[]`.
2. `readings_from_progressbars(bars: list[dict], now: float) -> list[LiveReading]`
   — input: a list of `{"valuenow": str|None, "valuemax": str|None, "label": str}`
   dicts (the driver collects them; label = the innerText of the bar's nearest
   labeled container, first 120 chars). Rules:
   - `valuenow` parseable and `label` matches
     `re.search(r"(?i)\b(grok\s*build|build|heavy|weekly|usage)\b", label)`
     → METRIC_WEEKLY_PCT, value scaled by valuemax (default 100; a 0–1
     valuenow with valuemax None is a fraction → ×100), confidence **high**,
     extractor `"grok.progressbar"`, evidence = the label text.
   - no label match → NO reading (not low-confidence — none).
   - value outside [0, 100] after scaling → no reading.
3. `readings_from_labeled_text(sections: list[str], now: float) -> list[LiveReading]`
   — input: innerText of individual labeled containers (NOT the whole page).
   Within one section string: if it matches
   `(?i)(grok\s*build|build|heavy|weekly)\b` AND contains a percent
   `(\d{1,3}(?:\.\d)?)\s*%`, emit METRIC_WEEKLY_PCT with confidence
   **medium**, extractor `"grok.labeled_text"`, evidence = the 80 chars around
   the match. One reading max per section. Also: a fraction `(\d+)\s*/\s*(\d+)`
   in a section whose label matches `(?i)quer|rate|per\s*\d+\s*h` →
   METRIC_RATE_WINDOW (medium), never weekly.
4. `readings_from_reset_text(sections: list[str], now: float) -> list[LiveReading]`
   — a section containing `(?i)\breset(s)?\b` plus a relative time
   `(\d+)\s*(d|day|h|hr|hour|m|min)` → METRIC_RESET_AT (medium), value =
   now + seconds, only when 120 < seconds < 32 days (keep the existing bound
   from `live_web.py:524`).
5. `merge_readings(readings: list[LiveReading]) -> list[LiveReading]` —
   agreement/conflict policy per metric:
   - two extractors agree on METRIC_WEEKLY_PCT within 1.0 point → keep the
     higher-confidence one, upgraded to **high**.
   - two extractors disagree by > 1.0 point → keep both but downgrade both to
     **low** and append `"; conflicts with <other extractor> <value>"` to each
     evidence (overlay will withhold them — honest uncertainty).
   - dedupe identical (metric, extractor) pairs.
6. `monotonic_guard(readings, previous_snapshot: dict | None, now) -> list[LiveReading]`
   — if the previous persisted snapshot (from `live/store.py`) has a grok
   METRIC_WEEKLY_PCT reading and the new value is **lower by > 2.0 points**
   with no METRIC_RESET_AT in between (previous reset_at value in the past
   counts as "reset happened"), downgrade the new reading to **low** with
   evidence suffix `"; dropped from <prev> without observed reset"`. Weekly
   usage only goes up between resets — an unexplained drop means we scraped
   the wrong element.
7. `build_provider_live(readings, authenticated: bool, note: str, now) -> ProviderLive`
   — state selection: `ok` if any usage-class reading is high; else
   `rate_data_only` if any METRIC_RATE_WINDOW; else `authenticated_no_data`
   if authenticated; else `needs_login`.

**Verify**: `python -c "import token_oracle.live.grok_extract as g; import inspect; assert 'playwright' not in inspect.getsource(g); print('ok')"` → `ok`

### Step 2: Rewrite the driver

In `token_oracle/live/web.py`, rewrite `fetch_grok_live_usage` to be a thin
fact-collector around the pure module. Keep: persistent profile dir, headless
arg, TTL cache keyed `grok:{headless}`, blessed-venv delegation, the
login-wall detection, and the `TOKEN_ORACLE_LIVE_DEBUG` dump (retarget the
dump file to `~/.local/share/token-oracle/debug/grok-usage.txt`, creating the
dir — world-writable `/tmp` paths are a hijack risk for a file another tool
might read). Replace the body between login-check and return with:

1. **Before any `goto`**: register the response listener. Capture (url, parsed
   JSON) tuples for responses with JSON content-type into a list — store raw
   payloads, do not pre-filter keys (the pure module decides).
2. Navigate: `goto("https://grok.com")` (session warm), then
   `goto("https://grok.com/settings/usage")`, `wait_for_load_state("networkidle")`
   with the existing timeout tolerance. Then ONE targeted wait:
   `page.wait_for_selector('[role="progressbar"], progress', timeout=8000)`
   inside try/except. Record `final_url` and `page.title()`.
   Delete the blind click loops (`for label in ("Usage", "usage", ...)` and
   the user-menu selector cascade) — if the usage view doesn't populate at the
   deep link, that is an honest `authenticated_no_data` with
   `note=f"landed on {final_url}"`, not a reason to click random text nodes.
3. Collect facts via ONE `page.evaluate` returning
   `{"bars": [{valuenow, valuemax, label}...], "sections": [str...]}`:
   - bars: for each `[role=progressbar], progress, [aria-valuenow]` element,
     valuenow/valuemax attributes plus label = innerText (first 120 chars) of
     the nearest ancestor matching `section, li, [class*="card"], [class*="usage"], [class*="quota"]`
     (fallback: parentElement.parentElement).
   - sections: innerText (first 300 chars each, max 40 sections) of each
     distinct labeled ancestor found above, PLUS every element matching
     `h1,h2,h3,h4,[class*="usage" i],[class*="limit" i],[class*="quota" i]`
     with its own container text. No whole-body text walk. No `__NEXT_DATA__`
     string concatenation (if you want __NEXT_DATA__, parse it and pass the
     dict through `readings_from_network_json` with url `"__NEXT_DATA__"`).
4. Feed facts through the pure functions; `merge_readings`; `monotonic_guard`
   (load previous snapshot via `live.store.load_snapshot()`);
   `build_provider_live`. Return the `ProviderLive` (see Step 3 for the
   return-type migration).
5. Delete from web.py: the old grok heuristics — first-%-fallback, `progress:`
   style-width parsing, `frac_patterns`, the 90-char contextual regex, the
   `__CAPTURED_API__`/`__NEXT_DATA__` text concatenation, `pcts_found`
   accumulation for grok.

### Step 3: Return-type migration

`fetch_grok_live_usage` now returns `ProviderLive | None` (None only when
playwright is unavailable and delegation failed). Update the callers:

- `token_oracle/live/legacy.py`: `provider_live_from_legacy("grok", ...)`
  branch → replace with a passthrough (if input is already ProviderLive,
  return it). Keep the claude branch untouched.
- `get_live_status` in web.py: grok branch reads `ProviderLive.state` and
  readings directly instead of dict keys.
- Dashboard `run()` probe (from plan 030 Step 6): grok path skips the legacy
  adapter.
- `_looks_logged_in`: grok branch → `data.state not in ("needs_login", "unavailable", "error")`.
- Blessed-venv delegation serializes via `contract.to_dict`/`from_dict`
  (JSON-safe), not raw dataclass printing.

**Verify**: `python -m pytest -q` → all pass; `rtk proxy grep -n "pcts_found\|frac_patterns\|__NEXT_DATA__" token_oracle/live/web.py` → no grok-path matches (claude path may still have its own until plan 032).

### Step 4: Fixtures + tests

Create `tests/fixtures/live/`:
- `grok_rate_limit.json` — `{"remainingQueries": 150, "totalQueries": 150, "windowSizeSeconds": 7200}`
- `grok_usage_bars.json` — bar dicts: one `{"valuenow": "10", "valuemax": "100", "label": "Grok build weekly usage 10% used Resets Jul 17"}`,
  one decoy `{"valuenow": "13", "valuemax": null, "label": "Sidebar collapse"}`
  (regression for the 13%-vs-10% bug), one fraction-style
  `{"valuenow": "0.1", "valuemax": null, "label": "Heavy usage"}`.
- `grok_sections.json` — section strings incl. a decoy chat message containing
  `"I used 45% of my time"` with no build/weekly label, and a real
  `"Grok build — 10% used. Resets in 3 days"`.

`tests/test_live_grok_extract.py` (pure — no playwright, no network):
1. rate-limit JSON → exactly one METRIC_RATE_WINDOW reading, zero
   METRIC_WEEKLY_PCT (THE regression test for "150/150 became a usage %").
2. bars fixture → one weekly reading, value 10.0, confidence high; the decoy
   bar produces nothing; the 0.1-fraction bar scales to 10.0.
3. sections fixture → decoy chat text yields nothing; labeled section yields
   weekly 10.0 (medium) + reset_at reading.
4. merge: progressbar 10.0 (high) + labeled text 10.0 (medium) → single high
   reading. Conflict: 10.0 vs 13.0 → both present, both low, evidence notes
   the conflict.
5. monotonic guard: prev snapshot weekly 10.0, new 4.0, no reset observed →
   new reading is low with the drop note; with a past reset_at in prev →
   stays high.
6. `build_provider_live([], authenticated=True, ...)` → state
   `authenticated_no_data`; with only rate reading → `rate_data_only`.
7. arbitrary unknown JSON (e.g. `{"version": "1.2.3", "count": 41}`) → `[]`
   (regression: no fuzzy numeric capture).

## Test plan

Above. Pattern: plain pytest functions; load fixtures with
`json.loads((pathlib.Path(__file__).parent / "fixtures/live/x.json").read_text())`.
No test may require playwright or network — CI has neither.

## Done criteria

- [ ] `python -m pytest -q` exits 0 including ≥ 7 new grok-extract tests
- [ ] `ruff check` / `ruff format --check` / `mypy` exit 0
- [ ] `grep -c "overall_pct" token_oracle/live/web.py` → 0 in the grok path (the generic first-% fallback is gone)
- [ ] `grep -n "style.width\|style && el.style" token_oracle/live/web.py` → no matches in the grok driver
- [ ] `token_oracle/live/grok_extract.py` contains no `playwright` import
- [ ] `plans/README.md` status row updated

## STOP conditions

- Plan 030's `live/contract.py` / `live/store.py` are absent or their APIs
  don't match this plan's usage.
- The contract lacks a needed metric/constant — report the gap; do not extend
  `contract.py` yourself.
- The claude fetcher shares helper code you'd have to modify beyond imports —
  report the entanglement instead of refactoring claude code (plan 032's job).
- A manual probe (if you have a logged-in profile) shows grok.com's usage page
  has NO progressbar/labeled-section structure this plan's collectors can see —
  capture the debug dump and report; do not invent new heuristics.

## Maintenance notes

- Site DOM will drift. The design intent: drift produces
  `authenticated_no_data` (honest) instead of wrong numbers; fixing drift =
  updating the fact collectors + adding a fixture, never adding a generic
  fallback. A reviewer should reject any future PR that reintroduces
  "first % on the page".
- The network-JSON usage key allowlist is a guess pending a real captured
  payload; when a real payload is captured (debug dump), turn it into a
  fixture and tighten the allowlist to the real shape.
- Deferred: parsing absolute reset timestamps ("Resets Jul 17") — relative
  times only for now; absolute-date parsing needs timezone care.
