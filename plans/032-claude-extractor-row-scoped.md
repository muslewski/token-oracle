# Plan 032: Claude extractor — row-scoped readings that tell Fable apart from All models

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `token_oracle/live/contract.py`,
> `token_oracle/live/grok_extract.py`, and `tests/fixtures/live/` must exist
> (plans 030 and 031 landed). If 031 is not merged, you may still proceed —
> but then also keep `legacy.py`'s grok branch intact; note it in your report.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED (live-site DOM assumptions; bounded by fixtures + STOP conditions)
- **Depends on**: plans/030-live-truthfulness-contract.md (hard); plans/031-grok-extractor-evidence-bound.md (soft — mirrors its architecture)
- **Category**: bug
- **Planned at**: commit `2660dd1` + live-web WIP, 2026-07-10 (excerpt line numbers refer to pre-030 `sources/live_web.py`; after 030 the code lives in `token_oracle/live/web.py`)

## Why this matters

Two observed lies come from the Claude scraper:

1. **Fable shown identical to "All models"** even though claude.ai displays
   clearly different meters. Cause: `fable_pct` is extracted with
   `re.search(r'(?i)\bfable\b.*?(\d+(?:\.\d+)?)\s*%', text, re.S)`
   (`live_web.py:674`) over the **whole page text**. "Fable" appears in the
   model picker / nav long before the usage section, and with `re.S` the
   regex happily crosses the entire page to the first % after it — which is
   usually the All-models meter.
2. **Weekly shows 41 when the site shows 38.** Same class of bug: the
   `all models.*?%` regex (`:664`) binds to whatever % happens to follow the
   first "All models" occurrence, plus the value silently alternates with the
   local *projection* when a fetch misses (that half was fixed by plan 030).

The fix mirrors plan 031: collect per-row facts (progressbar value + the text
of its own container), classify each row by ITS OWN label, and emit
`LiveReading`s with evidence. A "Fable" reading can then only come from a row
whose container actually says Fable — and when the page genuinely shows two
different meters, we extract two different numbers.

## Current state

- `token_oracle/live/web.py` — `fetch_claude_live_usage` (pre-030 lines
  568–732): goto `claude.ai/settings/usage`, whole-page `inner_text`, the two
  whole-page regexes above, a five-hour text probe (`:689-704`) that matches
  `start.*(message|sent)` against the **entire page** lowercased (`:694`) —
  chat content containing those words would false-positive the
  "starts_on_first_message" state.
- `token_oracle/live/contract.py` (plan 030): `LiveReading`, `ProviderLive`,
  `METRIC_WEEKLY_PCT`, `METRIC_MODEL_WEEKLY_PCT` (with `model` field),
  `METRIC_FIVE_HOUR_PCT`, `METRIC_FIVE_HOUR_STATE`, `METRIC_RESET_AT`,
  `CONF_*`. Read before coding.
- `token_oracle/live/grok_extract.py` (plan 031): the architectural exemplar —
  pure functions over collected facts, `merge_readings`, `monotonic_guard`,
  `build_provider_live`. **Reuse its helpers where generic** (see Scope).
- What the operator sees on claude.ai/settings/usage (recon facts, encode in
  fixtures): a "Current session" (5-hour) block; a weekly "All models" meter
  with a percentage and a "Resets <day time>" line; a separate weekly meter
  for the premium model (labeled with the model name, e.g. "Fable"); when the
  5h window is inactive, the session block shows a phrase like
  "starts when a message is sent" / "Starts when you send a message".

Repo conventions: same as plan 031 (stdlib core, playwright only in
`live/web.py`, pure extraction importable without playwright, plain pytest).

## Commands you will need

| Purpose | Command | Expected |
|---------|---------|----------|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests   | `python -m pytest -q` | all pass |
| Lint    | `ruff check token_oracle/` + `ruff format --check token_oracle/` | exit 0 |
| Types   | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |
| Manual probe (optional, logged-in profile) | `TOKEN_ORACLE_SKIP_BOOTSTRAP=1 ~/.local/share/token-oracle/venv/bin/python -c "from token_oracle.live.web import fetch_claude_live_usage; print(fetch_claude_live_usage(headless=True))"` | ProviderLive with row-scoped readings or honest empty state |

## Scope

**In scope**:
- `token_oracle/live/claude_extract.py` (create — pure, no playwright import)
- `token_oracle/live/web.py` — only `fetch_claude_live_usage` (+ shared
  return-type plumbing it forces in `get_live_status` / `_looks_logged_in`)
- `token_oracle/live/grok_extract.py` — ONLY to move genuinely generic helpers
  (`merge_readings`, `monotonic_guard`, `build_provider_live`) into a new
  `token_oracle/live/extract_common.py` if you need them for claude; pure
  move + import updates, zero behavior change (grok tests must still pass
  unmodified except import paths).
- `token_oracle/live/extract_common.py` (create, optional per above)
- `token_oracle/live/legacy.py` — delete entirely once both providers return
  `ProviderLive` natively (if 031 landed); otherwise delete only the claude
  branch.
- `tests/test_live_claude_extract.py` (create)
- `tests/fixtures/live/claude_*.json` (create)
- `plans/README.md` (status row)

**Out of scope**:
- The grok driver in web.py (031's work).
- `overlay.py`, `store.py`, `contract.py` — consume as-is; gaps → STOP.
- Dashboard, CLI, engine, config's `try_get_claude_five_hour_data`.

## Git workflow

- Branch: `advisor/032-claude-extractor-row-scoped`
- Conventional commits, e.g. `fix(live): row-scoped claude extractor separates Fable from All models`

## Steps

### Step 1: Pure extraction module

Create `token_oracle/live/claude_extract.py`:

1. `classify_row(label: str) -> tuple[str, str | None] | None` — given a row
   container's text (first ~200 chars), return `(metric, model)`:
   - `(?i)\ball\s*models\b` → `(METRIC_WEEKLY_PCT, None)`
   - `(?i)\b(fable|opus|sonnet|haiku)\b` **without** an "all models" match in
     the same label → `(METRIC_MODEL_WEEKLY_PCT, <matched name lowercased>)`
   - `(?i)(current\s*session|5.?h|5-hour|session\s*limit)` →
     `(METRIC_FIVE_HOUR_PCT, None)`
   - otherwise `None` (row ignored — this is what keeps nav/model-picker
     mentions of "Fable" out of the data).
2. `readings_from_rows(rows: list[dict], now: float) -> list[LiveReading]` —
   rows are `{"valuenow": str|None, "valuemax": str|None, "label": str, "text": str}`
   (label = short heading-ish text, text = fuller container text ≤ 300 chars):
   - classify by `classify_row(label) or classify_row(text)`.
   - percentage source priority: (a) `valuenow` scaled by `valuemax`
     (0–1 → ×100) → confidence **high**, extractor `"claude.usage_row.aria"`;
     (b) else first `(\d{1,3}(?:\.\d)?)\s*%` **within this row's `text`
     only** → confidence **medium**, extractor `"claude.usage_row.text"`.
   - evidence = the row label + matched value snippet (≤160 chars).
   - within the row text, `(?i)\bresets?\b[^\n]{0,80}` → attach a companion
     METRIC_RESET_AT reading (medium) if a relative time parses (reuse the
     relative-time rule from `grok_extract.readings_from_reset_text`); store
     the raw phrase in evidence even when unparseable.
   - out-of-range values ([0,100] after scaling) → drop the reading.
3. `five_hour_state_from_rows(rows, now) -> LiveReading | None` — ONLY within
   a row classified as five-hour: `(?i)(starts?\s+when\s+(a|you)\s+(message|send)|not\s+(yet\s+)?active|begins\s+when)`
   → METRIC_FIVE_HOUR_STATE, value `"starts_on_first_message"`, confidence
   **high** (it is row-scoped now), extractor `"claude.session_state"`.
   The old whole-page `start.*(message|sent)` probe must not survive.
4. `distinctness_check(readings) -> list[LiveReading]` — if a
   METRIC_MODEL_WEEKLY_PCT and the METRIC_WEEKLY_PCT reading have **identical
   evidence source rows** (same label text), the model reading is a
   double-match of one row: drop the model reading, keep weekly. If they come
   from different rows, keep both even when values are equal (genuinely equal
   meters are possible; the row separation is the truth criterion, not the
   value difference).
5. Reuse (import) `merge_readings`, `monotonic_guard`, `build_provider_live`
   from `extract_common.py` (Step 0 move) or duplicate-with-comment if 031
   has not landed (then note it for reconciliation).
   `monotonic_guard` applies to METRIC_WEEKLY_PCT and each
   METRIC_MODEL_WEEKLY_PCT independently (keyed by (metric, model)).

**Verify**: `python -c "import token_oracle.live.claude_extract as m, inspect; assert 'playwright' not in inspect.getsource(m); print('ok')"` → `ok`

### Step 2: Rewrite the driver

In `token_oracle/live/web.py`, rewrite `fetch_claude_live_usage`:

1. Keep: profile dir, TTL cache key `claude:{headless}`, blessed-venv
   delegation, sign-in-wall check, DEBUG dump (retarget to
   `~/.local/share/token-oracle/debug/claude-usage.txt`).
2. Register a JSON response listener **before** navigation (same pattern as
   031's grok driver); claude.ai loads usage data via API — capture raw
   (url, json) pairs and pass any dicts whose key names contain
   `usage`/`limit`/`reset` through a
   `claude_extract.readings_from_network_json(url, obj, now)` function with an
   explicit allowlist analogous to grok's (start conservative: emit nothing
   until a fixture from a real captured payload exists; the function may
   return `[]` initially with a `# tighten from real capture` comment — an
   honest no-op beats a fuzzy match).
3. `goto("https://claude.ai/settings/usage")`, `wait_for_load_state("networkidle")`
   (tolerant), then `page.wait_for_selector('[role="progressbar"], progress', timeout=8000)`
   in try/except. Record final_url/title. Delete the blind
   `get_by_text("Usage").click()` loop (`live_web.py:607-617`).
4. ONE `page.evaluate` collecting rows: for each progressbar-ish element
   (`[role=progressbar], progress, [aria-valuenow]`), walk up to the nearest
   ancestor matching `section, li, [class*="card" i], [class*="usage" i], [class*="row" i]`
   (fallback parent chain ≤3 levels); emit
   `{valuenow, valuemax, label: <first heading/strong/span text in container, ≤120 chars>, text: <container innerText ≤300 chars>}`.
   ALSO collect containers matching `(?i)session|current` headings even when
   they contain no progressbar (the idle 5h block may render without one) —
   emit them as rows with `valuenow: null`.
5. Feed rows through the pure functions → `ProviderLive`. Delete the old
   whole-page regexes (`all models.*?%`, `\bfable\b.*?%`, the whole-page
   five-hour probe, `pcts_found` for claude).
6. Return `ProviderLive | None`; update `get_live_status` /
   `_looks_logged_in` claude branches like 031 did for grok; delete
   `legacy.py` (or its claude branch — see Scope).

**Verify**: `python -m pytest -q` → all pass;
`rtk proxy grep -n "all\\\\s\\*models\|fable" token_oracle/live/web.py` → no regex-over-whole-page matches remain (the words may appear only in comments/label tables of claude_extract.py).

### Step 3: Fixtures + tests

`tests/fixtures/live/claude_rows.json` — realistic row dicts:
- `{"valuenow": "38", "valuemax": "100", "label": "All models", "text": "All models 38% used Resets Thu 9:00 PM"}`
- `{"valuenow": "24", "valuemax": "100", "label": "Fable", "text": "Fable 24% used Resets Thu 9:00 PM"}`
- decoy: `{"valuenow": null, "valuemax": null, "label": "New chat", "text": "Fable — our most capable model"}` (model-picker mention)
- `{"valuenow": null, "valuemax": null, "label": "Current session", "text": "Current session Starts when you send a message"}`

`tests/test_live_claude_extract.py`:
1. rows fixture → weekly 38.0 (high) AND model_weekly fable 24.0 (high) —
   **different values from different rows** (THE Fable-vs-All regression).
2. decoy model-picker row → no reading (regression: nav "Fable" ignored).
3. identical-row double match → distinctness_check drops the model reading.
4. two distinct rows with EQUAL values (38/38) → both kept.
5. session row → METRIC_FIVE_HOUR_STATE high; a chat-text row containing
   "when you send a message" but classified None → no state reading
   (regression: whole-page probe removed).
6. row text without aria (`valuenow: null`, text "All models 38% used") →
   medium-confidence reading from row text; text "All models" with NO % →
   no reading.
7. valuenow "0.38", valuemax null → scales to 38.0.
8. monotonic guard on model_weekly keyed independently from weekly.

## Test plan

Above; pattern identical to `tests/test_live_grok_extract.py` (or
`tests/test_snapshot.py` if 031 hasn't landed). No playwright, no network.

## Done criteria

- [ ] `python -m pytest -q` exits 0 with ≥ 8 new claude-extract tests
- [ ] `ruff check` / `ruff format --check` / `mypy` exit 0
- [ ] In `token_oracle/live/web.py`, `fetch_claude_live_usage` contains no
      `re.search` over whole-page text (grep for `re.S` in the claude driver → 0)
- [ ] `token_oracle/live/legacy.py` deleted (or claude branch removed, with a
      note if 031 hadn't landed)
- [ ] If `extract_common.py` was created: `python -m pytest -q tests/test_live_grok_extract.py` passes with only import-path changes to that file
- [ ] `plans/README.md` status row updated

## STOP conditions

- Plan 030's contract/store are absent or API-mismatched.
- The contract lacks a needed metric — report, don't extend.
- Moving shared helpers to `extract_common.py` would require changing any
  grok extractor **behavior** (not just imports) — stop and report the
  entanglement.
- A manual probe shows claude.ai's usage page has no progressbar/row structure
  the collector can see (e.g. fully canvas-rendered) — capture the debug dump
  and report.

## Maintenance notes

- When Anthropic renames the premium-model row (model names change roughly
  yearly), `classify_row`'s model alternation `(fable|opus|sonnet|haiku)` is
  the single line to update — and the fixture. A reviewer should check no
  other place hardcodes model names.
- The network-JSON path starts as a conservative no-op; first real captured
  payload (debug dump) should become a fixture + tightened allowlist —
  structured data beats DOM scraping when available.
- Deferred: absolute reset parsing ("Resets Thu 9:00 PM") into epoch — needs
  timezone/locale care; the raw phrase is preserved in evidence meanwhile.
- Deferred: per-model windows beyond fable — the `Window.model` filter
  (`core/contracts.py:20-26`) already supports them locally; live extraction
  emits any model row it sees, so overlay mapping (plan 030) is the only
  place to extend.
