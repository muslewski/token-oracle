# Plan 012: Design spike — make the `confidence` field real (today it is hardcoded 1.0)

> **Executor instructions**: This is a **design/spike plan**, not a build plan.
> The deliverable is a written design + a throwaway prototype + open questions
> for the maintainer, saved to `plans/012-confidence-results.md`. Production
> code changes are explicitly NOT part of this plan. Follow the steps in
> order; on any STOP condition, stop and report. When done, update the status
> row in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d2b4d32..HEAD -- token_oracle/core/windows.py token_oracle/core/profile.py token_oracle/core/contracts.py token_oracle/snapshot/writer.py`
> Plans 004 and 006 landed (`writer.py` atomic-write rework; `UsageEvent`/`to_pairs`
> removed from `contracts.py`) — expected, already reflected below. Excerpts
> refreshed at `ada32e9` (2026-07-02). On changes after `ada32e9` that touch
> the excerpts, treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: M (spike; the eventual build is a separate, later plan)
- **Risk**: LOW (no production changes in this plan)
- **Depends on**: plans/005-characterization-tests-core-math.md (DONE — the prototype must keep its tests green)
- **Category**: direction
- **Planned at**: commit `d2b4d32`, 2026-07-01; excerpts refreshed at `ada32e9`, 2026-07-02

## Why this matters

The public snapshot schema documents `confidence` as a "0–1 confidence score for the projection" (ADAPTERS.md field reference), and external consumers — agentic-sage is the named one — are invited to read it. But the value is a constant: `Forecast.confidence` defaults to `1.0` (`contracts.py:32`) and `compute_window` never sets it (`windows.py:70` builds `Forecast(...)` without passing it). A documented signal that never varies is worse than no signal — a consumer gating behavior on "confidence ≥ 0.8" believes it has certainty it doesn't have. The projection math already computes the two ingredients an honest score needs: how much of the current window is measured (`f`), and how much evidence backs the prior (profile exposure). This spike designs the score, prototypes it, and surfaces the decisions only the maintainer can make.

## Current state

- `token_oracle/core/contracts.py:23-32` — `Forecast` dataclass; last field `confidence: float = 1.0` (line numbers shifted down after Plan 006 removed the dead `UsageEvent`/`to_pairs` API above it).
- `token_oracle/core/windows.py:45-70` — `compute_window`; the blend:

```python
    f = min(1.0, max(0.0, elapsed / P))
    measured_term = (used / elapsed) * (reset - now)
    if profile is None:
        ...raw-history prior...
    else:
        prior_term = profile_integral(profile, now, reset)
    projected = used + (1.0 - f) * prior_term + f * measured_term
    ...
    return Forecast(window.name, int(used), cap, projected_pct, eta, float(reset_in), False)
```

  Idle windows return `Forecast(window.name, 0, cap, 0.0, None, float(P), True)` — also defaulting confidence to 1.0, which is its own oddity (an idle guess is not "fully confident").

- `token_oracle/core/profile.py` — `build_profile` computes decay-weighted token sums `S[b]` and exposure seconds `E[b]` per bucket, then shrinks with pseudo-count `SHRINK_K = 3.0` via `(n·raw + K·parent)/(n + K)` where `n = e/3600` (effective observed hours). **Crucially, `E` is discarded** — only the final rates are returned/stored (`cache["profile"]` is a flat `list[float]` of 168 rates). Any confidence formula needing evidence *mass* must either recompute exposure or extend what the cache stores.
- `token_oracle/snapshot/writer.py:13-22` — `forecast_to_dict` is a plain `asdict`; snapshot schema v1 already carries `confidence` per window, so **varying the value is schema-compatible** (no `schema` bump needed; the field's documented meaning finally becomes true). Plan 004's atomic-write rework changed only `write_snapshot` below — irrelevant here.
- Consumers of the field today: `tests/test_contracts.py::test_forecast_confidence_default` (pins the default) and `tests/test_snapshot.py::test_schema_shape_is_stable` (pins the key's presence, uses an explicit `0.9`). Neither statusline, tmux, nor dash render confidence anywhere.
- Constraint from the local design spec (docs/superpowers/specs/2026-06-30, "Out of scope"): no MCP/skill packaging — irrelevant here, but the spec's D3 ("Alpha — interfaces may change") is why tightening the field's semantics now, pre-Beta, is the right window.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass (prototype must not break them) |
| Focused | `python -m pytest tests/test_windows.py tests/test_snapshot.py -q` | all pass |

## Scope

**In scope**:
- `plans/012-confidence-results.md` (create — the deliverable)
- A prototype implemented on a **throwaway branch** (`advisor/012-confidence-spike`), never merged by you.

**Out of scope** (do NOT do):
- Merging any production change — the follow-up build plan (written after the maintainer answers the open questions) does that.
- Changing `SCHEMA_VERSION`, ADAPTERS.md, or any adapter rendering.
- Touching the profile cache format on the main branch.

## Git workflow

- Branch: `advisor/012-confidence-spike` — prototype commits live here only.
- The results file `plans/012-confidence-results.md` is the mergeable artifact.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Analyze candidate formulas

Work through (on paper, in the results doc) at least these three candidates, with their behavior at window start (f≈0), mid-window, window end (f≈1), cold-start (no history), and rich-history cases:

1. **`confidence = f`** — pure window-fraction. Trivial, monotonic, but insults a well-trained profile: a user with 9 weeks of stable history gets confidence≈0 at every window start even though the prior is excellent.
2. **`confidence = f + (1-f) · prior_quality`** — mirrors the projection blend itself: the measured share is certain (weight f), the prior share is discounted by how much evidence backs it. Requires defining `prior_quality ∈ [0,1]`.
3. **`prior_quality` from shrinkage mass** — reuse the module's own epistemology: `n_eff/(n_eff + SHRINK_K)` where `n_eff` = decay-weighted observed hours behind the buckets covering `[now, reset)`. This is exactly the weight `build_profile` gives data over the parent prior, so the score matches how much the profile *actually* trusted data. Requires exposure per bucket at compute time (see Step 2's storage question).
4. Note the idle case explicitly: propose `confidence` for idle forecasts (candidate: `prior_quality` alone, or `0.0`; today it silently reads 1.0).

### Step 2: Prototype candidate 2+3 on the spike branch

Minimal viable plumbing (acceptable hacks, it's throwaway): extend `build_profile` to also return per-bucket effective-hours `n[b] = E[b]/3600`, store it in the cache as `profile_n` alongside `profile` (loader `setdefault("profile_n", [])` for legacy caches → treat absent as `prior_quality = 0`), and compute in `compute_window`:

```python
    # exposure-weighted prior quality over the remaining horizon
    n_eff = mean(profile_n[bucket] for buckets covering [now, reset))   # pseudo-code
    prior_q = n_eff / (n_eff + SHRINK_K)
    conf = f + (1.0 - f) * prior_q
    return Forecast(..., False, confidence=round(conf, 3))
```

Then generate a comparison table: for 4 scenarios (fresh install; 1 week of history; 9 weeks of history; window 90% elapsed) print `f`, `prior_q`, `conf` — a short script driving `build_profile`/`compute_window` with synthetic events is enough. Paste the table into the results doc.

**Verify**: on the spike branch, `python -m pytest -q` → all pass EXCEPT possibly `test_forecast_confidence_default` if your prototype changes the default — record which tests the real build would need to update (expected: that one; `test_schema_shape_is_stable` keeps passing since it sets confidence explicitly).

### Step 3: Write `plans/012-confidence-results.md`

Structure: (a) recommendation — one formula, stated plainly with the reasoning; (b) the scenario table from Step 2; (c) implementation sketch for the build plan (files touched: `profile.py`, `engine.py` cache keys, `windows.py`, tests; cache back-compat via `setdefault`; no schema bump); (d) **open questions for the maintainer**, at minimum:
   1. Should adapters *render* low confidence (dim the segment? suffix `?`) or is the field snapshot-only for now?
   2. Idle-window confidence: `prior_quality`, `0.0`, or keep `1.0`?
   3. Is `round(conf, 3)` precision fine for the public schema?
   4. Does agentic-sage already read the field (coordinate before semantics change)?
(e) rejected alternatives with one line each (pure `f`; statistical prediction intervals — overkill for stdlib and this data density).

**Verify**: file exists; contains a recommendation section, a table with ≥ 4 scenario rows, and ≥ 4 open questions.

### Step 4: Clean up

Leave the spike branch intact (named above) for the build plan's author; switch back to `main`. Confirm `main` working tree contains only the results file + index update.

**Verify**: `git status --short` on `main` → only `plans/012-confidence-results.md` and `plans/README.md`.

## Test plan

Spike-level: the prototype must keep the full suite green except the explicitly-recorded default-pin test. The *build* plan (future) owns real tests: monotonicity in `f`, cold-start ≈ low, rich-history window-start ≈ `prior_q`, legacy-cache fallback.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `plans/012-confidence-results.md` exists with recommendation + scenario table + ≥ 4 open questions + rejected alternatives.
- [ ] Spike branch `advisor/012-confidence-spike` exists with the prototype and a green-except-recorded-pins test run.
- [ ] No production file changed on `main` (`git diff main -- token_oracle/` empty).
- [ ] `plans/README.md` status row updated (DONE = spike delivered, build pending maintainer answers).

## STOP conditions

Stop and report back (do not improvise) if:

- Plan 005 is not DONE — the prototype needs its safety net.
- `compute_window`'s blend differs from the excerpt (the formula this design mirrors has changed — the design must be re-derived).
- You find an external consumer already depending on `confidence == 1.0` semantics (search agentic-sage if accessible) — that turns question (d.4) into a blocker worth reporting immediately.

## Maintenance notes

- The recommendation deliberately reuses `SHRINK_K` so "how much the score trusts data" and "how much the math trusted data" can never drift apart — if a future change replaces the shrinkage model (the profile docstring's "ML seam"), confidence must be re-derived from the new model's evidence measure.
- Plan 010 (cache trim) and this spike both touch what the cache stores; whichever build lands second must re-check cache back-compat defaults.
