# Present-truth anchoring — reliable limits & honest forecasting

**Date:** 2026-07-18
**Status:** Approved (brainstorming → spec)
**Branch:** `feat/present-truth-anchoring`
**Implements:** plan 063 (engine truth) + plan 064 (Future/Past UX). Builds on committed plan 062 (Future cap-race display).

## Problem

Three linked complaints from the operator:

1. **Truth reliability is the moat, but it breaks when limits move.** AI usage caps change constantly. Oracle's cap validation (`config._validate_external_caps`, band `0.2x–5x`) silently rejects a legitimately-moved cap and keeps a stale preset, so displayed `%` deflates or inflates. Retained-last-good readings (up to 6h) render as `live` with an OK dot and no age — a confidently-wrong number that reads as fresh.
2. **The Future/Past layers do not feel natural, professional, or predictable.** The Future tab can print `cap race hit in {1.25×reset} if pace holds` for a window that *resets before it can ever hit cap*; the race caption and the margin line contradict each other in the same block; a 99% live-now sits above `no hit before reset`; the burn sparkline normalizes to peak so flat usage renders as a wall of full blocks; the Past `%weekly-cap` TOTAL row shows several-hundred-% (a 14-day sum over a weekly cap) and reads as over-limit.
3. **The forecast hallucinates against plainly-visible present data.** `windows.compute_window` projects end-of-window from a 168-bucket burn profile whose `prior_term` gets weight ≈ 1 early in a fresh window; one heavy burst projects weekly to many-hundred-%. `projected_pct` has no ceiling, and `eta_to_cap` derives its burn rate from the projection itself (self-referential), so inflation feeds a too-soon ETA. Meanwhile `idle` is a hard veto decided purely from local logs — stale logs show idle/0% while the server says the window is 60% full.

The in-flight uncommitted work (`live/fill.py`, `windows.recompute_with_used`, `engine._apply_live_fills`, store/overlay retain-last-good — the "Body 2" checkpoint at `bdc0614`) is the right *instinct* (feed live truth into the forecast math) but crosses the line the 2026-07-13 quality pass deliberately deferred ("scraped garbage would corrupt projections") and, as written, does not bound the hallucination, picks readings non-deterministically, and presents 6h-stale data as live.

## Decisions (operator-approved)

- **Anchor + bound math.** Trusted present-time truth is both the anchor for "now" and a physical bound on the forecast; the local-log projection may only extrapolate *from* the anchor, never contradict it. Scraped/header values touch the forecast *math* only when fresh + high-confidence.
- **Adopt server cap — via self-calibration.** The server header exposes `used_percentage` + `resets_at`, **no token-cap**; `usage-limits.json`'s caps are a different unit than local token `used` (the `57M/270M` the audit flagged), so they are never adopted at face value. Instead Oracle derives the effective cap from the corroborated ratio `local_used ÷ (server_pct/100)` — a cap in the correct token unit that self-corrects as the tier moves.
- **Commit 062, rework Body 2 under plan 063.** 062 is committed as-is (display-only, clean). Body 2 is checkpointed then reworked under a proper plan with the guardrails below.

## Core principle

Present-time truth (server rate-limit header `%`, or a fresh high-confidence scrape) is the **anchor** and the **bound** for every number the tool shows. The local-log projection extrapolates *from* the anchor and is capped by physical reality. Every "live" number carries its true age and source.

## The contract — five invariants

These are the acceptance criteria. Every change below exists to establish one of them, and plan 063/064 tests pin them by name.

- **I1 — Anchor.** When a *trusted* present reading (state OK, confidence HIGH, age < `FRESH_TTL`) exists for a `(profile, window)`, the displayed "now" number **is** that reading. Local logs never overrule it.
- **I2 — Bound.** The projection starts from the anchored now and is physically bounded: `projected_pct` and `eta` can never imply an outcome the anchor or observed burn forbids. No cap-hit shown after the window resets; ETA derives from **observed** recent burn, not from the projection's own rate; `projected_pct` never drops below the anchored now.
- **I3 — Trust gate.** Only fresh (age < `FRESH_TTL`, currently 600s) **and** high-confidence readings may touch the forecast *math*. Stale, retained (`+retained`), or header-older-than-fresh readings are **display-only** and always shown with their age. This is the "no scrape garbage in projections" line, honored explicitly.
- **I4 — Honest provenance.** No number is shown as `live` without its true age and source. Retained = `retained · ~Nh old`; header = `server · Ns ago`; scrape = `site · Ns ago`; local-only = `local logs`. The same cell reads identically on Present and Future.
- **I5 — Truth beats idle.** A trusted present reading of real usage means the window is *active*, regardless of local logs — the idle veto cannot suppress a live truth.

## Layer 1 — Reliable source of truth (the moat) — plan 063 part A

**Header `%` is the cap-free authoritative "now"** for 5h and weekly. Anchoring on it (I1) makes the *now* number immune to cap changes — no cap required to be correct.

**Self-calibrating effective cap** (the realized "adopt server cap"): keep a small persisted state (JSON under the XDG data dir, sibling to `ratelimits.json`) of `cap_eff` per `(profile, window)`.

- When a trusted reading gives `server_pct = p` and local logs give `used_tokens` for the same window, and `p ≥ P_FLOOR` (≈ 8%, ratio is unstable near an empty window) and `used_tokens ≥ TOK_FLOOR`, compute `cap_inst = used_tokens ÷ (p / 100)`.
- **Grow-only, corroborated.** Adopt `cap_inst` toward `cap_eff` (EMA, small α) **only when it is larger than the preset** — i.e. when the server says you have used a *smaller* `%` than the preset implies, meaning your real cap is bigger (tier up). Growing the cap can only move the local projection toward the server truth, so it is always safe. Never shrink `cap_eff` below the preset from calibration (a smaller `cap_inst` may mean incomplete local logs on a multi-machine account, not a smaller cap — and the now-number is the server anchor regardless).
- Absurdity clamp: `cap_eff ∈ [preset, preset × CAL_CEIL]` with `CAL_CEIL` generous (≈ 20×) because the estimate is corroborated (needs both `used` and `p`), unlike the raw `usage-limits.json` number.
- Surface it: when `cap_eff` diverges materially from preset, emit a visible issue/note — `cap recalibrated 220k→440k (from live usage — tier changed?)` — and use `cap_eff` for statusline `k/cap` and for scaling local projections to `%`.
- `usage-limits.json`: keep the band-reject (unit-mismatch guard) unchanged; re-pick the preset when its `plan` key changes.

**Honest-provenance plumbing:**
- Age badge on retained/header cells wherever a number renders (kills stale-as-live). The data (`cell.age_secs`, `cell.extractor.endswith('+retained')`) already exists.
- Give retained / over-fresh-TTL cells a distinct state (`STATE_RETAINED` or an `is_retained` flag) so "confirmed now" is visually distinct from "assumed still true"; currently they inherit `STATE_OK`.
- `_pct_from_snapshot` / reading selection: **newest-wins** — compare `fetched_at`, not last-in-iteration-order.
- `extract_common.monotonic_guard`: add a symmetric **upward-jump guard** — a large unexplained increase with no corroboration from a second extractor is held/flagged (catches decoy-DOM / relabel misparse).
- `web.get_live_status`: compute per-provider freshness from the newest reading `fetched_at` (as `store._reading_age` does), not the merge-rewritten snapshot `written_at`, so a snapshot of retained readings does not report `ok/fresh` to doctor/dash.
- `store.merge_with_previous`: record a per-provider retain-cycle counter so a provider stuck retaining across many probe cycles escalates to a visible `stale — probe failing` state instead of silently serving 6h-old data.

## Layer 2 — Anti-hallucination forecast (the math) — plan 063 part B

Rework of Body 2 with the guardrails.

- **Observed-rate ETA.** Replace the projection-implied rate in `eta_to_cap` with a rate measured over a recent trailing window (`observed_rate = tokens burned in the last min(elapsed, RATE_WINDOW≈1h) ÷ that duration`). `eta = (cap_eff − used_now) ÷ observed_rate` when `observed_rate > 0`, else `None`.
- **Bounded projection.** The Future verdict + ETA are driven by observed burn anchored at the server now: `observed_bound = used_now + observed_rate × time_left × SLACK` (SLACK ≈ 1.5 to allow some acceleration). `projected_tok = clamp(profile_blend_projected, used_now, observed_bound)`. So the 168-bucket profile can no longer explode the hero number; it is demoted to a secondary "vs your typical pace" context line, never the alarm trigger. `projected_pct` is floored at the anchored now (I2).
- **`recompute_with_used` rework:** clamp `used` to `[0, cap_eff]`; derive residual burn from `observed_rate` (not the old projection residual that carried a local over-projection onto a server fill); floor projected at `used_now`, ceiling at `observed_bound`.
- **I5 idle override:** a trusted server reading above an active-floor marks the window active even when local logs say idle.
- **I3 freshness + confidence gate** on all write-through: retained / stale / header-older-than-fresh never touch the math (they remain display-only). Honor `Forecast.confidence < 1.0` (plan 012) when it lands.
- **Single 5h truth source:** `fill.py` is the one write-through authority; drop the duplicate inline 5h `recompute_with_used` in `engine.py` so the two paths cannot diverge (the current double-rebase, `fill r4`).
- **No silent degradation:** keep the `try/except` so a broken live store never blanks forecasts, but record a degraded flag surfaced through `get_live_status`/doctor so a regression inside fill is visible instead of silently reverting to local-only numbers.

## Layer 3 — Future/Past UX (natural, professional, predictable) — plan 064

Depends on Layer 1/2 (so the display reflects already-correct numbers and can render honest provenance).

- **Kill the impossible hit:** when `eta ≥ reset_in`, the caption reads `resets first — no hit`, never `cap in {eta}`.
- **Resolve the caption-vs-margin contradiction:** one reconciled line per window; `_race_caption` and `margin_line` never claim opposite outcomes.
- **Live-now above end-proj (logs lag):** when `now_pct > local end_pct`, derive the race clock from the live burn or clamp `end_pct` up to `now_pct` — no `no hit before reset` sitting under a 99% now.
- **Provenance parity (I4):** thread `cell.age_secs` + `cell.extractor` into `race.Truth` so Future appends the same `· Ns ago` / `retained` / `header` caveat as Present's `_render_profile_block`. A cell never reads `live now` on Future and `retained/stale` on Present.
- **Sparkline:** normalize hour levels against a cap-anchored or fixed scale (or annotate "relative to peak") so a flat low-burn profile stops rendering as a wall of full blocks.
- **Past `%weekly-cap` TOTAL:** give the summed 14-day-over-weekly-cap ratio its own label (e.g. `×weekly` or `of cap over N days`) distinct from the per-day `%weekly-cap`, or drop `pct` on the TOTAL row, so it is not read as an over-cap percentage.
- **Alignment + safe truncation:** unify the `now` / `live now` label column width; route Future/Past overflow through `scene.truncate_display` (ANSI/cell-aware) instead of raw `line[:width]`.

## Sequencing

1. **062 committed** (`8b0c8c4`) — display-only cap-race, done.
2. **Body 2 checkpoint** (`bdc0614`) — reverted-to-able base for the rework.
3. **Plan 063** — Layers 1 + 2 (engine truth), TDD, invariants I1–I5 pinned by tests.
4. **Plan 064** — Layer 3 UX polish, after 063.

## Testing strategy

- Unit tests named for each invariant (`test_i1_anchor_*`, `test_i2_bound_*`, …).
- Characterization tests for `recompute_with_used` and the forecaster: `projected_pct` never below anchored now; ETA never earlier than observed-rate ETA; no cap-hit implied after reset; the profile-integral explosion scenario (one heavy burst early in a fresh weekly window) yields a bounded projection.
- Trust-gate tests: a retained/stale/older-than-fresh reading never changes the forecast math but *is* rendered with its age.
- Self-calibration tests: grow-only, corroboration floor, absurdity clamp, persistence round-trip, "tier doubled" scenario recalibrates.
- Provenance-parity render tests: same cell → same caveat on Present and Future.
- Regression: full suite stays green (baseline 421) and grows; Present render output for the trusted-fresh common case is unchanged except the honest-age badge.

## Non-goals

- No new scraping surfaces; no fingerprint-evasion; no invented probability `%`; stdlib-only / zero-dependency preserved.
- No redesign of the Present tab beyond the honest-age badge.
- Not solving multi-machine log completeness in general — the header `%` remains the correct now-number there; only the *derived cap* is gated (grow-only) against undercount.
