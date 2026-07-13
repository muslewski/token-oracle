# Plan 061 — Quality pass Wave 1 findings + Wave 2 fixes (Grok 4.5)

**Status:** DONE — Wave 2 HIGH + Wave 3 MED residuals fixed; 291 tests green  
**Design:** `docs/superpowers/specs/2026-07-13-quality-pass-done-plans-design.md`  
**Baseline:** `b5092bc` · 280 tests → **291 passed** after quality-pass fixes  

## Method

Audit-first clusters (Approach B). 12 parallel auditors; several failed mid-stream on API; re-dispatched tighter audits completed A1–A12 coverage.

## HIGH findings (fixed this wave)

| ID | Plan | Fix |
|----|------|-----|
| **F-A12** | 054 | `overlay_cells` no longer early-returns on empty/`None` snapshot — header weekly works without browser |
| **F-A1-1** | 003 | multi-profile doctor `total_evs > 0 or True` → `total_evs > 0` |
| **F-A4-1** | 030 residual | engine stops writing server current % into `Forecast.projected_pct`; only `used` + `reset_in_secs` |
| **F-A5-1** | 031/038 | `merge_readings` prefers higher-trust extractor (modal > network > progressbar) on conflict |
| **F-A5-2** | 031 | progressbar labels: drop bare `usage`/`build`; require weekly/build-limit phrases |
| **F-A5-4** | 038 | live-setup grok URL → `https://grok.com/?_s=usage` |
| **F-A8-1** | 043 | first-run hint only when true first-run (`used==0` all windows), not session-idle |
| **F-A8-2** | 043 | first-run copy mentions Grok + `~/.grok/sessions` |
| **F-A8-3** | 044 | SETUP.md Grok weekly note corrected for usage modal |

## MED residual — Wave 3 status

| ID | Plan | Status |
|----|------|--------|
| F-A1-2 | 001 | **FIXED** — non-object JSON records issue |
| F-A1-3 | 003 | **FIXED** — doctor distinguishes rejected caps |
| F-A5-5 | 037 | residual — multi-meter split → MEDIUM (accept / later) |
| F-A5-6 | 031 | **FIXED** (wave 2) dual-MEDIUM no HIGH upgrade |
| F-A5-7 | 032 | **FIXED** — collector requires current session / 5h |
| F-A6-1 | 035 | **FIXED** Xvfb wait/kill |
| F-A6-2 | 035 | **FIXED** RC-C test asserts stderr message |
| F-A6-3 | 035 | **FIXED** login aborts without display |
| F-A7-1 | 041 | **FIXED** non-numeric usage fields coerced |
| F-A8-4 | 044 | **FIXED** dash skips SIG_DFL so Painter can restore |
| F-A10-1 | 052 | residual LOW — size=None test still soft |
| F-A11-1 | 057 | **FIXED** `bars_only` height level |
| F-A11-3 | 056 | **FIXED** tiny chip binding-first |
| F-A11-4 | 057 | **FIXED** height assert tightened (wave 2) |

## LOW / ACCEPT

- A3 016/017 QP-PASS (pricing unwired by design → 058+)
- A2 005/006 PASS; docs nits AGENTS test count / README omits live\*
- A9 install channels PASS
- A12 053 PASS

## Files touched (this fix wave)

- `token_oracle/live/overlay.py`
- `token_oracle/live/extract_common.py`
- `token_oracle/live/grok_extract.py`
- `token_oracle/live/web.py`
- `token_oracle/core/engine.py`
- `token_oracle/cli/main.py`
- `SETUP.md`
- tests: overlay, grok_extract, engine, cli, dashboard, fixture bars

## Verification

```bash
python -m pytest -q
ruff check token_oracle tests
ruff format --check token_oracle tests
mypy token_oracle
```
