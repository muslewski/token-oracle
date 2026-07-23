# Quality Pass — DONE plans under Grok 4.5

**Status:** approved for execution  
**Date:** 2026-07-13  
**Baseline HEAD:** `b5092bc`  
**Baseline suite:** 280 tests collected  
**Scope:** all **DONE** advisor plans (001–008, 016–017, 030–047, 049, 051–057) — 35 plans  
**Out of scope:** TODO plans 009–015, 018–029, 048, 050, 058–060 (unless a DONE fix requires a tiny adjacent change — escalate, don't improvise)

## Problem

Plans were written by a high-ceiling advisor (Claude Opus / Fable) and executed largely via **grok-xhigh** armory executors. Operator reports ongoing product issues consistent with executor under-delivery relative to plan intent. Model version is not recorded per commit; quality is verified by **plan ↔ code ↔ tests**, not by git author metadata.

## Goal

Raise fidelity of every DONE plan so HEAD matches (or intentionally supersedes) plan intent at Grok 4.5 quality — correctness, tests, UX/display honesty, live extractors, install paths — **without discarding merged progress**.

## Non-goals

- Do not re-open settled tradeoffs in `plans/README.md` "Findings considered and rejected"
- Do not implement TODO feature work as part of this pass
- Do not rewrite git history
- Do not re-execute green plans from scratch for sport

## Method (Approach B — audit-first → delta fixes)

1. **Wave 1 — Audit (12 parallel read-only agents)** by code cluster  
2. **Advisor vet** — confirm evidence, drop noise/by-design, prioritize  
3. **Wave 2 — Fix** — write self-contained fix plans `061+`, dispatch Grok 4.5 executors in worktrees  
4. **Wave 3 — Loop** — re-audit touched clusters; full gates; max 2 fix loops  

### Per-plan quality statuses

| Status | Meaning |
|--------|---------|
| `QP-PASS` | Intent + done criteria + tests hold |
| `QP-FIX` | Real gap; fix plan written / in flight |
| `QP-FIXED` | Fix merged + re-verified |
| `QP-ACCEPT` | Gap real; not worth fixing (one-line reason) |
| `QP-SUPERSEDED` | Later plan intentionally replaced behavior |

### Audit rubric (every DONE plan)

1. **Intent** — "Why this matters" still true  
2. **Done criteria** — machine checks hold (or stronger superseding checks)  
3. **Scope hygiene** — no half-implements; removed APIs stay gone  
4. **Tests** — meaningful asserts; hermetic where required; not gamed/weakened  
5. **Conventions** — stdlib-only, never-raise contracts, live semantics (current % ≠ projected %)  
6. **Known nits** — index-noted issues resolved or accepted  

### Wave 1 clusters

| ID | Plans | Surface |
|----|-------|---------|
| A1 | 001, 003, 004, 008 | config, doctor, atomic write, init/clean |
| A2 | 002, 005, 006 | docs drift, characterization tests, dead API |
| A3 | 016, 017 | events v2, pricing/presets |
| A4 | 030, 033, 036 | live contract/store/probe, engine purity, live toggle |
| A5 | 031, 032, 037, 038, 040 | extractors, fabrication holes |
| A6 | 007, 034, 035 | dash scene, headed display lifecycle |
| A7 | 039, 041, 051 | caps, JSONL guards, hermetic fallback |
| A8 | 042, 043, 044 | help, first-run, SIGPIPE |
| A9 | 045, 046, 047, 049 | demo GIF, npm, install.sh, README install |
| A10 | 052, 055 | width-responsive, color-safe truncate |
| A11 | 056, 057 | low-width triage, borderless bars |
| A12 | 053, 054 | ratelimits self-ingest, weekly header cell |

### Fix policy

- **All severities** considered (operator: go all-in); ship HIGH/MED first, then LOW if cheap  
- Prefer disjoint file ownership for parallel executors  
- Advisor does not edit product code; executors work in isolated worktrees  
- User merges to main  

### Gates (every fix + final)

```bash
python -m pytest -q
ruff check token_oracle tests
ruff format --check token_oracle tests
mypy token_oracle
NO_COLOR=1 oracle doctor
```

(Exact tooling may vary by env; use what `pyproject.toml` / CI define.)

## Success

- Every DONE plan has a terminal QP status  
- No open HIGH findings; MED either FIXED or ACCEPTed with reason  
- Suite green; doctor green (or known empty-data caveats only)  
- Final report lists residual risk  

## Operator notes

User reports real-world issues from poor executor quality — prioritize **live truth**, **dashboard layout**, and **config/cap** paths over cosmetic docs nits when triaging.
