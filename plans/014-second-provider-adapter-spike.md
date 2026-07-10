# Plan 014: Research spike — a second real provider adapter (validate "provider-agnostic")

> **Executor instructions**: This is a **research/design spike**, not a build
> plan. The deliverable is `plans/014-provider-results.md` plus, if the format
> research succeeds, a prototype adapter with synthetic-fixture tests on a
> throwaway branch. On any STOP condition, stop and report. When done, update
> the status row in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat d2b4d32..HEAD -- token_oracle/sources/`
> Plan 013 legitimately extended `base.py` (entry-point discovery). On other
> mismatches vs. the excerpts below, treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: M (coarse — spike; format research dominates)
- **Risk**: LOW (no production changes on main)
- **Depends on**: plans/013-entry-point-source-discovery.md (the prototype should ship as an entry-point package, exercising that mechanism end to end)
- **Category**: direction
- **Planned at**: commit `d2b4d32`, 2026-07-01
- **Confidence note**: the audit grounded the *need* (pitch says provider-agnostic; only one real provider exists). The *log-format details below are unverified leads*, not facts — verifying them is this spike's job.

## Why this matters

`pyproject.toml` describes the package as a "provider-agnostic token usage-cap forecaster" and the architecture backs it: sources emit neutral `(timestamp, tokens)` tuples through a registry. But shipping reality is one real provider (Claude Code transcripts) plus a documented stub (`generic`). A second real adapter is the cheapest way to (a) prove the abstraction holds against a log format nobody designed for it, (b) exercise Plan 013's entry-point mechanism with a real package, and (c) widen the user base beyond Claude subscribers. Candidate providers whose CLIs are known to write local session logs: OpenAI Codex CLI and Google Gemini CLI. This spike verifies one provider's format, prototypes an adapter against synthetic fixtures, and reports whether/where the neutral contract strains.

## Current state

What an adapter must implement — the whole contract, from `token_oracle/sources/base.py` and ADAPTERS.md:

```python
@register("name")            # or via entry point group "token_oracle.sources" (Plan 013)
class MySource:
    def __init__(self, opts: dict): ...      # opts = config.json "source_opts"
    def scan(self, files_state, now, window) -> tuple[dict, list[tuple[float, int]]]:
        """files_state: opaque dict persisted in the cache between calls
        (use for mtime/size incremental parsing). Return only events in
        [now - window, now], sorted ascending."""
```

The reference implementation to copy is `token_oracle/sources/claude_code.py` (83 lines):
- `_limit_tokens(usage)` sums `input_tokens + output_tokens + cache_creation_input_tokens` from a message's `usage` object (note: excludes `cache_read_input_tokens` — a deliberate accounting choice ported from the original reference tool; mirror the *shape* of this decision for the new provider and document whichever inclusion rule you pick).
- `iter_usage_events(path)` — line-by-line JSONL, tolerant of blank/garbage lines, timestamps parsed via `token_oracle/core/timeutil.py::parse_ts` (ISO 8601, trailing `Z` ok).
- `scan()` — glob, mtime-cutoff pruning, mtime+size skip, deleted-file pruning (all characterized by Plan 005's tests — mirror them for the new adapter).
- Fixture-test pattern: `tests/test_sources_claude.py` — a `_line(...)` helper builds synthetic JSONL; no real provider logs are ever committed.

Unverified leads to check (research targets, NOT facts):
- **Codex CLI**: reportedly writes session files under `~/.codex/sessions/` (JSONL), entries carrying model responses with token usage; also `~/.codex/history.jsonl` for prompts.
- **Gemini CLI**: reportedly writes under `~/.gemini/tmp/<hash>/` (chats/telemetry); token usage availability in local files is less certain.
- Preference order: whichever provider's local files (a) exist by default without telemetry opt-in, (b) carry per-response token counts, (c) carry parseable timestamps.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Local evidence | `ls ~/.codex/sessions/ 2>/dev/null | head; ls ~/.gemini/ 2>/dev/null | head` | any listing = live samples available on this machine |
| Sample inspection | `head -c 2000 <one session file>` | JSON(L) you can characterize |
| Tests | `python -m pytest -q` | all pass |
| Docs research | web search for "<provider> CLI session log format" and the provider CLI's GitHub source (config/persistence modules) | format described by source code, not blog hearsay |

## Scope

**In scope**:
- `plans/014-provider-results.md` (create — the deliverable)
- Prototype on throwaway branch `advisor/014-provider-spike`: either a new module `token_oracle/sources/<provider>.py` + fixture tests (if the maintainer later wants it in-tree) **or** a sibling mini-package demonstrating the Plan 013 entry point — the results doc recommends which packaging the maintainer should choose.

**Out of scope** (do NOT do):
- Merging anything to `main`.
- Committing ANY real log content — session logs contain conversation data (potentially sensitive); fixtures must be synthetic, following the `_line()` pattern. If you inspect real local logs for research, quote *field names and structure only*, never values.
- Network calls to provider APIs — this tool is offline-by-design (README: "No provider API calls").

## Git workflow

- Branch: `advisor/014-provider-spike` for the prototype; the results doc is the mergeable artifact.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Establish the format from primary sources

For Codex CLI first (fall back to Gemini CLI if Codex fails criterion (b)):
1. Check the local machine for live samples (commands above). If present, characterize structure from a *small* sample — field names, timestamp format, where token counts live, one-file-per-session vs. rolling.
2. Regardless of local availability, confirm against the provider CLI's own source code (it's open source: find the session-persistence module and the usage/telemetry structs) — local samples show one version; source shows the contract.
3. Record: default log path(s), file format, event granularity, token fields available (input/output/cached/reasoning?), timestamp field + format, log rotation/retention behavior, and version caveats.

**Verify**: results doc section "Format" filled with citations (file paths inspected locally; source-code URLs/permalinks for the upstream persistence code).

### Step 2: Decision gate

- If NO candidate provider exposes per-response token counts in local files → write the results doc with verdict **NOT FEASIBLE NOW**, list what each provider *does* persist, note what upstream change would unlock it, mark the plan DONE (spike answered the question), and stop.
- Otherwise pick the winner and proceed.

### Step 3: Prototype the adapter

On the spike branch, copy `claude_code.py`'s shape: `iter_usage_events`-equivalent for the provider's schema, `scan()` with the same incremental state pattern (mtime+size skip, cutoff pruning, deletion pruning), token accounting rule documented in the module docstring. Add fixture tests mirroring `tests/test_sources_claude.py` (registration, parse-with-garbage-lines, window bounds, incremental skip) with synthetic lines only.

**Verify**: `python -m pytest -q` on the spike branch → all pass including the new adapter tests.

### Step 4: Write `plans/014-provider-results.md`

Sections: (a) provider chosen and why (with the losing provider's blockers); (b) format reference (from Step 1); (c) token-accounting decision and its uncertainty (which fields count toward the provider's real limits — flag what's unverifiable offline, exactly as the Claude adapter's accounting is a documented approximation); (d) packaging recommendation — in-tree module vs. separate `token-oracle-<provider>` entry-point package (weigh: in-tree = zero-install UX + this repo carries provider churn; separate = validates Plan 013, isolates churn); (e) window-preset question — the provider's actual rate-limit windows/caps, if discoverable, as a config preset candidate; (f) open questions for the maintainer.

**Verify**: file exists with all six sections; verdict stated in the first paragraph.

## Test plan

Spike-level: prototype fixture tests on the branch (Step 3). A future build plan owns: preset addition, docs (README sources table, ADAPTERS example), and any doctor probe nuance.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `plans/014-provider-results.md` exists; verdict in the first paragraph; all six sections present.
- [ ] Either the Step 2 NOT-FEASIBLE verdict, or: spike branch with adapter + ≥ 4 fixture tests, full suite green on the branch.
- [ ] `git diff main -- token_oracle/` empty on `main`.
- [ ] No real log content anywhere in the diff (`git diff advisor/014-provider-spike` contains only synthetic fixture values).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report back (do not improvise) if:

- You cannot establish the format from primary sources (no local samples AND upstream source unclear) — do not build against guessed field names; report what you found.
- The provider's logs turn out to contain no usable timestamps or token counts mid-prototype — downgrade to the Step 2 NOT-FEASIBLE verdict rather than inventing derived metrics.
- The neutral `(timestamp, tokens)` contract genuinely cannot express the provider's usage model (e.g. request-count limits rather than token limits) — that's a *finding about the architecture*; write it up prominently, it's more valuable than the adapter.

## Maintenance notes

- Provider log formats are third-party internals and WILL drift; whichever packaging is chosen, the adapter needs a "format version observed at" note and tolerant parsing (skip-don't-crash, as `iter_usage_events` does).
- If the separate-package route is chosen, that package is also the canonical example for ADAPTERS.md — link it there in the build plan.
