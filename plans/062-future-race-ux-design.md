# Future tab — cap race UX (live-aware)

**Status:** approved for implementation planning  
**Date:** 2026-07-14  
**Plan id:** 062  
**Depends on:** plan 018/020 (tab shell + Future panel), live overlay cells (Present blend), Forecast fields  
**Note:** Canonical copy lives under `plans/` (repo `docs/superpowers/` is gitignored).  

## Problem

1. **Future looks like Present.** Same bar + % idiom; users do not get a distinct “oracle” surface.
2. **Future is wrong when live data exists.** Present blends web/live fill for weekly/fable; Future only renders local `Forecast.projected_pct`. On a real multi-sub machine this produced:

   | Window | Present (live) | Future (local proj) |
   |--------|----------------|---------------------|
   | Claude weekly | ~93% | ~68% |
   | Claude fable | ~99% | ~23% |

   A race based only on local end-projection can say SAFE while the site already shows near-full limits.

3. **Goal:** When a user opens Future, they should know in one glance whether they are **good or fucked** — honestly, without invented probabilities.

## Decisions (locked)

| Decision | Choice |
|----------|--------|
| Verdict basis | **Race clock only:** compare cap-hit ETA vs reset-in (plus live “already at wall”) |
| Multi-sub | **Per-profile** verdicts (CLAUDE / GROK), not one global score |
| Tone | **Quiet oracle:** one word SAFE / TIGHT / OVER (+ color), no pulse banners |
| Probability | **No fake %.** No “73% chance” until real confidence math (plan 012). Optional dim confidence footnote only if `confidence < 1.0` later |
| Live disagreement | **Show both:** live now % and local end-proj when they differ; never silently replace one with the other |

## Product definition

**Future answers:** *At the pace implied by our model, and given how full you are **now** (live when available), do you hit the cap before the window resets?*

- **Present** = current usage truth (live overlay).
- **Future** = race between **fill trajectory** and **reset clock**, labeled so live vs log-based end-proj cannot be confused.

## Status rules

Inputs per window (after blend — see “Window truth”):

- `now_pct` — current fill %
- `end_pct` — local end-of-window projected % (`Forecast.projected_pct`)
- `reset_in` — seconds until reset (`Forecast.reset_in_secs`)
- `eta` — seconds until cap at implied burn (`None` if not heading over from that burn model)
- `idle` — window idle

| Status | Condition (first match wins) |
|--------|------------------------------|
| **IDLE** | `idle` |
| **OVER** | `now_pct >= 100` **or** (`eta is not None` and `eta < reset_in`) |
| **TIGHT** | not OVER and (`now_pct >= 85` or `end_pct >= 85`) |
| **SAFE** | not OVER/TIGHT/IDLE and signals exist |
| **UNKNOWN** | no usable now/end signal |

**Profile verdict** = worst of its windows ordered: OVER > TIGHT > SAFE > IDLE > UNKNOWN.

**Margin (when eta and reset both finite):**

- If `eta < reset_in`: `lose by {fmt_dh_long(reset_in - eta)}`
- If `eta > reset_in`: `clear by {fmt_dh_long(eta - reset_in)}` (optional; only if we still show eta for over-100 end proj after reset — usually hide eta when SAFE and end_pct ≤ 100)
- If `now_pct >= 100`: `already at the wall`
- Else if no eta: `headroom ~{max(0, 100 - max(now_pct, end_pct))}% of cap`

Color: map SAFE→green, TIGHT→lime/orange band via existing `gauge` thresholds (≈85 lime, ≥100 orange/red), OVER→red. No new palette.

## Window truth (must match Present blend)

Reuse the same keying as `dashboard/app.py` row blend:

| Window kind | `now_pct` source |
|-------------|------------------|
| 5h / session / current | Local `100 * used / cap` when not idle; live cell for 5h if present and used for display consistency where Present uses local for the number |
| weekly / week | Live cell `(profile_canon, "weekly")` when `pct is not None`; else local used/cap or end-proj as fallback |
| fable | Live cell `(profile_canon, "fable")` when available; else local |
| other | Local used/cap or projected |

**Profile canon:** `"grok"` if name contains grok else `"claude"` (same as Present).

**Cap-hit ETA with live:**

- If `now_pct >= 100`: `eta = 0.0`
- Else if live now is available: recompute using live fill as used:

  ```
  live_used = now_pct/100 * cap
  # burn rate: prefer projection-implied remaining burn over reset window
  # if end_pct > now_pct and reset_in > 0:
  #   rate = (end_pct/100*cap - live_used) / reset_in
  #   eta = (cap - live_used) / rate if rate > 0 else None
  # elif Forecast.eta_to_cap_secs is not None: keep engine eta
  # else: None
  ```

- Else: use engine `Forecast.eta_to_cap_secs` unchanged.

Document in code that end-proj alone underestimates site fill when logs lag; live is authoritative for **now**.

## Layout (v1)

```
Future — cap race (live when available)

  CLAUDE  ·  OVER
  weekly
    live now   93%   ████████████████████░
    resets in  2d 17h
    cap race   hit in 1d 13h if pace holds
    margin     lose by 1d 4h
    end proj   68%  (local logs · may lag live)

  fable
    live now   99%   …
    …
    end proj   23%  (local logs · may lag live)

  GROK  ·  SAFE
  weekly
    live now   60%
    resets in  …
    cap race   no hit before reset
    end proj   57%

  next 24h  ▁▂▄…  expected Nk tokens     # secondary
  spend pace: ~$…/day …                  # secondary, if cost on
```

**Differentiation from Present:**

- No multi-box side-by-side Present chrome.
- Hero is **race + status word**, not “current usage dashboard.”
- Sparkline and cost are footer context only.

**Width collapse:**

- `< 72`: drop mini-bar; keep status, live now, resets, race one-liner.
- `< 48`: profile status + one line per window: `5h OVER live 99% · reset 2d17h`.

**Height:** respect existing Painter clip to terminal rows; prefer hide empty/idle windows behind a dim count if needed.

## Architecture

### Pure module: `token_oracle/dashboard/future.py` (expand)

| Function | Responsibility |
|----------|----------------|
| `window_truth(f, cells) -> Truth` | now_pct, source (`live`/`local`/`proj`/`none`), end_pct, reset_in, idle |
| `eta_for_race(f, truth) -> float \| None` | live-aware cap-hit ETA |
| `race_status(truth, eta) -> Status` | IDLE/OVER/TIGHT/SAFE/UNKNOWN |
| `profile_verdict(statuses) -> Status` | worst-of |
| `margin_line(truth, eta) -> str` | human margin copy |
| `render_future(forecasts, profile, now, width, enabled, cost_line=None, cells=None)` | layout above |

Keep `spark_next24` / `cost_pace_line` as secondary.

### Wiring: `dashboard/app.py` Future branch

- Pass `st.cells` from `DashStore` into `render_future` (already loaded for Present; **no extra scrape**).
- Do not recompute forecast in the UI thread.

### Core

- **v1: no required change** to `compute_window` / engine if display-time overlay is correct.
- Optional follow-up (out of v1 scope): feed live fill into engine used for multi-profile so statusline/json also match — separate plan if needed.

## Error / empty states

| Case | UI |
|------|-----|
| No forecasts yet | Skeleton / “waiting on forecast…” (existing) |
| No live cells | Race from local only; omit “live now” label — use `now` from used/cap; no “may lag live” on end proj |
| Live only, idle logs | Show live now; end proj may be weak — still race on live + eta_for_race |
| All idle | Profile IDLE; quiet copy |

## Testing

- Unit: `race_status` table (OVER/TIGHT/SAFE/IDLE/UNKNOWN).
- Unit: live 99% + end 23% → OVER, both numbers in rendered lines.
- Unit: no cells → no crash; uses local.
- Unit: multi-profile two verdict headers.
- Unit: color off → no `\033`.
- Unit: `eta_for_race` when now_pct ≥ 100 → 0.
- Regression: Present render unchanged (no intentional Present edits).

## Non-goals (v1)

- Statistical probability / plan 012 implementation.
- Changing Present layout or live probe cadence.
- Alarm pulse / max-panic banners.
- Merging Claude+Grok into one score.
- Rewriting `core/windows.py` burn model.

## Implementation notes for the plan

1. Extract Present blend keying into a shared pure helper **or** duplicate carefully in `window_truth` with a comment + test parity cases (prefer small shared helper under `dashboard/` if Present import would cycle — avoid `app.py` importing heavy run loop).
2. Prefer `dashboard/race.py` pure helpers if `future.py` grows past ~250 lines.
3. Update `plans/README.md` only if a plan row is added; this is a product iteration on 020, not a renumber of old plans.
4. Manual smoke: multi-profile dash → Future shows OVER when Present weekly/fable are near full live.

## Success criteria

- [ ] User can open Future and state profile status (SAFE/TIGHT/OVER) without reading Present.
- [ ] When live weekly/fable is ≥90% and local end-proj is much lower, Future still shows OVER/TIGHT from live and displays both numbers.
- [ ] Future layout is visually distinct from Present (race lines, not box panels).
- [ ] No invented probability percentages.
- [ ] Tests green; no new dependencies.

## Open follow-ups (not blocking v1)

- Plan 012 real confidence as footnote.
- Engine-level live used write-through for forecast.json / statusline parity.
- Optional “binding window” pin at top of each profile.
