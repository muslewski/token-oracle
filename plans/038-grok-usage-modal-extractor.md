# Plan 038 — Grok live weekly usage via the `?_s=usage` modal

**Status:** DONE — implemented directly by advisor 2026-07-11 on `advisor/038-grok-usage-modal`. LIVE-verified (headed Xvfb): grok `state=ok`, `weekly_pct=23.0` HIGH, `model_weekly_pct=22.0 grok_build` HIGH, `reset_at`=Jul 17 2026; dash header `grok ● live 23%`. Gates: 219 passed (+8), ruff/format/mypy clean. (Step 4 `api` breakdown emits from full text but drops out of the live tightest-element slice — info-only/undisplayed, left as-is.)
**Written against commit:** `b40dbbc`
**Depends on:** 030 (truthfulness contract), 031 (grok extractor), 035 (headed display), 037 (row separation) — all merged.
**Supersedes the "RC-B: grok has no usage page" note in `plans/README.md`** — that conclusion was WRONG. Grok *does* expose a weekly usage cap; the probe just navigated to the wrong route.

---

## Why this matters

In the dash, the grok panel shows `local projection — live disabled` while claude shows real live percentages. The user (a SuperGrok **Heavy** subscriber) wants grok to show live weekly usage exactly like claude does.

Prior rounds concluded grok exposes no weekly usage page (only a 2h query rate window) and documented this as "RC-B, not fixable." **That was a wrong diagnosis caused by probing the wrong route.**

## Root cause (corrected, evidence-backed)

`fetch_grok_live_usage` navigates to `https://grok.com/settings/usage`. That path does **not** exist — it client-side-redirects to `https://grok.com/` (the chat shell), where there are no usage meters. The only reading produced is `rate_window` (the 2h query limit from `/rest/rate-limits`), which `overlay.py` deliberately never maps to a usage cell → the grok row renders `live disabled`.

The **real** usage surface is a modal opened by the query param **`_s=usage`** on any grok.com URL:

```
https://grok.com/?_s=usage
```

Opening it (verified live, logged-in Heavy account, headed via Xvfb) renders this text block:

```
Usage
Weekly SuperGrok Heavy Limit
23% used
Resets July 17, 2026 at 7:46 AM
Grok Build 22%
API 1%
```

Key facts confirmed by live probing:
- The route `https://grok.com/?_s=usage` reliably opens the modal (final_url stays `.../?_s=usage`).
- The percentages are **plain text**, NOT `aria-valuenow` progressbars (claude used aria; grok does not — there are zero `[aria-valuenow]` elements in the modal).
- No clean JSON endpoint carries these numbers — `/rest/products` is the Stripe catalog, `/rest/subscriptions` is the tier, `/rest/rate-limits` is the 2h window, `/rest/tasks` is a Tasks quota. **The weekly usage % lives only in the modal DOM text.** So extraction is text-anchored (this is fine and stable — the labels are fixed UI strings).
- The reset time is an **absolute date** (`Resets July 17, 2026 at 7:46 AM`), unlike claude's relative `Resets in 3 hr`.

## Metric mapping (grok ⟷ existing claude model)

| Grok modal line | Metric | model | Confidence |
|---|---|---|---|
| `Weekly SuperGrok Heavy Limit — 23% used` | `METRIC_WEEKLY_PCT` | — | HIGH |
| `Resets July 17, 2026 at 7:46 AM` | `METRIC_RESET_AT` | — | HIGH |
| `Grok Build 22%` | `METRIC_MODEL_WEEKLY_PCT` | `grok_build` | HIGH |
| `API 1%` | `METRIC_MODEL_WEEKLY_PCT` | `api` | HIGH |

`build_provider_live` already returns `STATE_OK` when a high-confidence `weekly_pct` reading is present, and `overlay.overlay_cells` already maps `METRIC_WEEKLY_PCT` → `(grok, "weekly")`. So emitting `weekly_pct=23` alone flips the grok weekly row from `live disabled` to `● live 23%`. That is the **core deliverable**.

The `grok_build` / `api` breakdown (Step 4) is an **optional enhancement** — implement only if Steps 1–3 pass cleanly. Do NOT block the core on it.

---

## Files in scope

- `token_oracle/live/web.py` — `fetch_grok_live_usage`: change the route to the `?_s=usage` modal + collect the modal text block.
- `token_oracle/live/grok_extract.py` — add `readings_from_usage_modal(text, now)` (text-anchored) + `parse_absolute_reset(text, now)` (absolute date → epoch).
- `tests/test_sources_grok.py` **or** a new `tests/test_live_grok_usage_modal.py` — unit tests over the exact fixture text below.

## Files explicitly OUT of scope (do NOT touch)

- `token_oracle/live/overlay.py` — already maps `weekly_pct` → `(grok, weekly)`. Only touch it in the OPTIONAL Step 4 (to map `grok_build`), and only if you do Step 4.
- `token_oracle/live/claude_extract.py`, `token_oracle/live/contract.py`, `token_oracle/dashboard/app.py` — no changes needed for the core. (Step 4 optional dash meta line is described but may be skipped.)
- The existing `rate_window` / `readings_from_network_json` grok logic — leave it; it is still valid supplementary data. Just make sure a successful weekly reading yields `STATE_OK` (it will, via `build_provider_live`).
- Do NOT delete or rewrite the existing progressbar/labeled-text extractors — they are the fallback.

---

## Steps

### Step 1 — Add `parse_absolute_reset` to `grok_extract.py`

Add a helper that parses grok's absolute reset phrasing into an epoch float. Anchor on the word `Resets`.

Accepted format (from live evidence): `Resets July 17, 2026 at 7:46 AM` (also handle no comma, and `PM`).

```python
import datetime as _dt
from .contract import CONF_HIGH, METRIC_RESET_AT, LiveReading  # extend existing imports

_ABS_RESET_RE = re.compile(
    r"(?i)resets?\s+([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})\s+at\s+(\d{1,2}):(\d{2})\s*([AP]M)"
)

def parse_absolute_reset(text: str, now: float) -> LiveReading | None:
    """Parse 'Resets July 17, 2026 at 7:46 AM' -> METRIC_RESET_AT epoch (local tz).
    Returns None if no absolute reset phrase present."""
    if not text:
        return None
    m = _ABS_RESET_RE.search(text)
    if not m:
        return None
    month, day, year, hh, mm, ap = m.groups()
    try:
        dt = _dt.datetime.strptime(
            f"{month} {day} {year} {hh}:{mm} {ap.upper()}", "%B %d %Y %I:%M %p"
        )
        epoch = dt.timestamp()  # naive -> local tz, matches how grok.com renders it
    except Exception:
        return None
    # sanity: must be in the future and within ~40 days
    if not (now < epoch < now + 40 * 86400):
        return None
    return LiveReading(
        provider="grok",
        metric=METRIC_RESET_AT,
        value=epoch,
        confidence=CONF_HIGH,
        extractor="grok.usage_modal.reset",
        evidence=m.group(0)[:160],
        fetched_at=now,
    )
```

**Verify:**
```
python -c "import time; from token_oracle.live.grok_extract import parse_absolute_reset as p; r=p('Resets July 17, 2026 at 7:46 AM', time.time()); print(r.metric, r.value, r.confidence)"
```
Expected: `reset_at <a float ~ Jul 17 2026 local> high`. (If `now` is past Jul 17 2026 when you run it, the sanity window will reject it — that's correct behavior. For the unit test, freeze `now` to a value shortly before the date; see Test plan.)

### Step 2 — Add `readings_from_usage_modal` to `grok_extract.py`

Text-anchored extraction of the weekly cap. Import `METRIC_WEEKLY_PCT` (already imported).

```python
_WEEKLY_LIMIT_RE = re.compile(
    r"(?i)(weekly\s+supergrok\s+heavy\s+limit|weekly\s+.{0,30}?limit)\D{0,40}?(\d{1,3}(?:\.\d)?)\s*%\s*used"
)

def readings_from_usage_modal(text: str, now: float) -> list[LiveReading]:
    """Extract grok's weekly usage cap from the ?_s=usage modal text.
    Anchored strictly on the 'Weekly ... Limit ... N% used' label."""
    readings: list[LiveReading] = []
    if not text:
        return readings
    m = _WEEKLY_LIMIT_RE.search(text)
    if m:
        try:
            val = round(float(m.group(2)), 1)
            if 0 <= val <= 100:
                readings.append(
                    LiveReading(
                        provider="grok",
                        metric=METRIC_WEEKLY_PCT,
                        value=val,
                        confidence=CONF_HIGH,
                        extractor="grok.usage_modal.text",
                        evidence=text[max(0, m.start()):m.end() + 20][:160],
                        fetched_at=now,
                    )
                )
        except Exception:
            pass
    rst = parse_absolute_reset(text, now)
    if rst is not None:
        readings.append(rst)
    return readings
```

**Design rules (do not violate):**
- Anchor on the **"Weekly ... Limit"** label. Never emit `weekly_pct` from a bare `N%` with no weekly-limit label — that is the noise the truthfulness contract forbids.
- The `_WEEKLY_LIMIT_RE` second alternative (`weekly ... limit`) is a resilience hedge if xAI renames "SuperGrok Heavy" (e.g. to a different tier). Keep it narrow: it still requires the words "weekly" AND "limit" AND "% used".

### Step 3 — Repoint `fetch_grok_live_usage` to the usage modal (`web.py`)

In `fetch_grok_live_usage`, after the warm `page.goto("https://grok.com", ...)`, replace the `page.goto(url, ...)` for `https://grok.com/settings/usage` with opening the modal and collecting its text:

1. Change nothing about the preflight / launch / `_on_response` capture / bot-challenge / login-wall blocks. Keep them.
2. Replace the deep-link navigation target. Instead of `url = "https://grok.com/settings/usage"`, warm `https://grok.com`, read the landed URL, then:
   ```python
   landed = getattr(page, "url", "https://grok.com/") or "https://grok.com/"
   sep = "&" if "?" in landed else "?"
   usage_url = landed + sep + "_s=usage"
   page.goto(usage_url, wait_until="domcontentloaded", timeout=timeout_ms)
   ```
3. Replace the `wait_for_selector('[role="progressbar"], progress', ...)` wait (the modal has NO progressbars). Wait for the modal text instead:
   ```python
   try:
       page.wait_for_function(
           "() => /Heavy Limit|%\\s*used/i.test(document.body.innerText||'')",
           timeout=10000,
       )
   except Exception:
       pass
   page.wait_for_timeout(1500)
   ```
4. After the login-wall check, collect the modal text block and feed the new extractor. Grab a bounded slice of the usage region (not the whole body), then still also run the existing extractors as fallback:
   ```python
   modal_text = ""
   try:
       modal_text = page.evaluate(
           """() => {
             // find the tightest element whose text has both a weekly limit label and '% used'
             let best = '';
             for (const el of document.querySelectorAll('div,section,main,aside')) {
               const t = (el.innerText||'').trim();
               if (/Heavy Limit|Weekly.{0,30}Limit/i.test(t) && /%\\s*used/i.test(t) && t.length < 600) {
                 if (!best || t.length < best.length) best = t;
               }
             }
             return best || (document.body.innerText||'').slice(0, 1500);
           }"""
       )
   except Exception:
       modal_text = ""
   ```
   Then, in the readings-assembly section, ADD (before `merge_readings`):
   ```python
   try:
       from .grok_extract import readings_from_usage_modal
       readings.extend(readings_from_usage_modal(modal_text, now))
   except Exception:
       pass
   ```
   Keep the existing `readings_from_network_json` / `readings_from_progressbars` / `readings_from_labeled_text` / `readings_from_reset_text` calls as-is (fallbacks). `merge_readings` + `monotonic_guard` stay.
5. Update the debug-dump `URL:` line and the `note`/`final_url` handling to reflect the new `usage_url`. Keep the `TOKEN_ORACLE_LIVE_DEBUG` dump but make it also write `modal_text[:1500]`.

**Verify (live, headed — the executor likely CANNOT run this; the advisor will).** Leave a note in PROGRESS.md that live verification is deferred to the advisor. The executor's job is that the code is correct + unit tests pass.

### Step 4 — OPTIONAL: grok_build / api breakdown

Only if Steps 1–3 are green and time allows.

- In `readings_from_usage_modal`, also emit `METRIC_MODEL_WEEKLY_PCT` readings:
  - `Grok Build 22%` → `model="grok_build"`, CONF_HIGH
  - `API 1%` → `model="api"`, CONF_HIGH
  Anchor each on its literal label immediately followed by `N%`. Regex e.g. `r"(?i)grok\s*build\D{0,6}(\d{1,3}(?:\.\d)?)\s*%"` and `r"(?i)\bAPI\b\D{0,6}(\d{1,3}(?:\.\d)?)\s*%"`. Guard the API one so it does not match unrelated "API" text elsewhere — only accept when a `Grok Build N%` match was also found in the same text (they always appear together in the modal).
- In `overlay.py`, the `METRIC_MODEL_WEEKLY_PCT` branch currently maps only `model=="fable"`. Extend it to also map `model=="grok_build"` → `cells[(p_c, "grok_build")]`. Do NOT change the fable mapping. Leave `api` unmapped (info only) unless you also add a dash row for it (you should not).
- Dash: showing the `grok_build`/`api` split is a nice-to-have. If the grok forecast has no `grok_build` window row, do NOT invent one — instead skip the dash change and leave the breakdown in the snapshot only. **Do not restructure the dash.** If unsure, STOP at Step 3 and report.

---

## Test plan

Create `tests/test_live_grok_usage_modal.py` (follow the style of `tests/test_live_claude_extract.py`). Use this EXACT fixture (the real captured modal text):

```python
FIXTURE = (
    "Usage Weekly SuperGrok Heavy Limit 23% used "
    "Resets July 17, 2026 at 7:46 AM Grok Build 22% API 1%"
)
```

Freeze `now` to a fixed epoch shortly BEFORE Jul 17 2026 so the reset sanity window passes deterministically, e.g.:
```python
NOW = 1783000000.0  # ~ 2026-07-01; before the Jul 17 reset in the fixture
```

Tests:
1. `readings_from_usage_modal(FIXTURE, NOW)` yields a `weekly_pct` reading with `value == 23.0`, `confidence == "high"`, `extractor == "grok.usage_modal.text"`, `provider == "grok"`.
2. It also yields a `reset_at` reading whose value is a float > NOW and < NOW + 40 days.
3. `parse_absolute_reset("Resets July 17, 2026 at 7:46 AM", NOW)` returns a reading; `parse_absolute_reset("no reset here", NOW)` returns `None`.
4. A text with a bare `"45%"` and NO "Weekly ... Limit" label yields NO `weekly_pct` reading (anti-noise guard).
5. `build_provider_live(readings_from_usage_modal(FIXTURE, NOW), authenticated=True, note="", now=NOW, provider="grok").state == "ok"`.
6. (If Step 4 done) `grok_build` model reading `value == 22.0`; `api` model reading `value == 1.0`; and `overlay_cells` produces a `(grok, "grok_build")` cell with `pct == 22.0` given a snapshot built from these readings.

## Verification gates (run all; all must pass)

```
pip install -e ".[dev]"          # NOTE: this clobbers the user's oracle entrypoint — advisor re-symlinks after; not your concern
python -m pytest -q
ruff check token_oracle tests
ruff format --check token_oracle tests
mypy --ignore-missing-imports token_oracle
```

Expected: all green. New tests pass. No existing test regresses (there are ~211 currently).

## Done criteria (machine-checkable)

- `python -m pytest -q` passes with the new grok usage-modal tests included.
- `python -c "import time; from token_oracle.live.grok_extract import readings_from_usage_modal as f; rs=f('Weekly SuperGrok Heavy Limit 23% used', 1783000000.0); print([(r.metric,r.value,r.confidence) for r in rs])"` prints a list containing `('weekly_pct', 23.0, 'high')`.
- `ruff check` / `ruff format --check` / `mypy` all clean.
- `git log --oneline` shows one commit per completed step (or a small number of logically-grouped commits).

## Escape hatches — STOP and report instead of improvising if:

- The `?_s=usage` route or the "Weekly ... Limit ... N% used" text shape is NOT what this plan describes when you inspect the codebase's fixtures/tests (you cannot re-probe live — trust this plan's fixture, which came from a live capture).
- Wiring `grok_build` into the dash would require restructuring `dashboard/app.py` or inventing a new forecast window — do NOT. Stop at Step 3 + snapshot-only breakdown and report.
- Any existing test breaks in a way that implies the grok fetch is used by other code paths you'd have to change — report the coupling rather than editing broadly.

## Maintenance note

- The extraction is text-label-anchored. If xAI renames "SuperGrok Heavy" or restructures the modal, the `_WEEKLY_LIMIT_RE` fallback (`weekly ... limit ... % used`) is the safety net; watch for it in review.
- The reset parser assumes the site renders the date in the viewer's local timezone (it does today). If grok ever switches to UTC/explicit-tz text, `parse_absolute_reset` must be updated to honor it.
- Live verification is the advisor's responsibility (headed Xvfb probe against the logged-in grok profile) — the executor validates code + units only.
