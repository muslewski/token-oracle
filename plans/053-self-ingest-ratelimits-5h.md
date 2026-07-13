# Plan 053: token-oracle captures Claude's rate-limit header itself → live 5h works for EVERY user (no private dependency)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` (a reviewer maintains the index — still flip your row).
>
> **Drift check (run first)**:
> `git diff --stat 5de6aac..HEAD -- token_oracle/core/config.py token_oracle/cli/main.py token_oracle/adapters/statusline.py SETUP.md`
> If any in-scope file changed since this plan was written, compare the "Current
> state" excerpts against the live code before proceeding; on a mismatch, treat
> it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED (adds a data source consumed by the engine; strictly additive — absent header = today's exact behavior)
- **Depends on**: none (plan 054 depends on THIS)
- **Category**: direction / correctness
- **Planned at**: commit `5de6aac`, 2026-07-13

## Why this matters

The dashboard's live 5h number (the one that matches claude.ai exactly) is the
tool's headline feature. But it is **not produced by token-oracle** — it is read
from an external, private project (`~/token-forecast/`, module
`token_forecast.ratelimits`) that the author happens to have installed and wired
as their Claude Code statusline. A stranger who `pipx install token-oracle` has
none of that plumbing, so they get only token-oracle's own log-based estimate —
never the authoritative server number. In short: **the killer feature only works
on the author's machine.**

Claude Code hands its configured statusline command an authoritative
`rate_limits` block on **stdin every render** (~1.4 s cadence). That is exactly
what `token_forecast` captures today. token-oracle already ships a statusline
(`oracle statusline`) but it renders and throws the stdin away. This plan makes
token-oracle **capture that header itself**, persist it, and feed the live 5h
number from it — so any user who wires `oracle statusline` gets the same
server-truth number the author gets, with zero external dependency.

(The per-turn ~20 s cadence of the number is the SERVER's — unbeatable, and not
in scope. This plan removes the *setup dependency*, not the cadence.)

Plan 054 builds on this to also surface the weekly number from the same header.

## Current state

- `token_oracle/core/config.py` — `try_get_claude_five_hour_data(now)` (lines
  105-176) and `try_get_claude_five_hour_remaining(now)` (lines 25-102) resolve
  the 5h number. TODAY their FIRST source is the external `token_forecast`:
  ```python
  # try_get_claude_five_hour_data, lines 114-137 (abridged)
  try:
      try:
          import token_forecast.ratelimits as RL
      except Exception:
          p = os.path.expanduser("~/token-forecast/src")
          if p not in sys.path:
              sys.path.insert(0, p)
          import token_forecast.ratelimits as RL
      if hasattr(RL, "five_hour"):
          d = RL.five_hour(now)
          if d and isinstance(d, dict) and not d.get("stale", False):
              rem = d.get("secs_to_reset")
              sp = d.get("used_percentage")
              if rem is not None:
                  return {"reset_in_secs": float(rem),
                          "projected_pct": float(sp) if sp is not None else None,
                          "source": "server"}
  except Exception:
      pass
  # ... then a local ~/.claude/usage_limits.py fallback ...
  ```
  The engine consumes this at `token_oracle/core/engine.py:96` and `:172` — no
  engine change is needed; a new source that returns the same
  `{reset_in_secs, projected_pct, source}` shape flows through automatically.

- `token_oracle/cli/main.py` — the statusline command (lines 447-449) throws
  stdin away:
  ```python
  if args.cmd == "statusline":
      print(sl.render(run_forecast(now, cfg)))
      return 0
  ```
  `main()` already imports `json`, `os`, `sys`. The subparser list is at lines
  322-334.

- `token_oracle/adapters/statusline.py` — `render(forecasts, color=None)` (lines
  24-26). Pure; leave it pure.

- `token_oracle/live/store.py` — the atomic-write pattern to mirror
  (mkstemp in target dir → fdopen write → `os.replace`; never raises; returns
  None on failure). Lines 30-79. Reuse this shape for the new module's persist.

- **Reference algorithm to port** — `~/token-forecast/src/token_forecast/
  ratelimits.py` (READ-ONLY reference; do NOT modify or import it). Its proven
  logic, which you will reimplement stdlib-only inside token-oracle:
  - Windows: `{"five_hour": 5*3600, "seven_day": 7*24*3600}`.
  - `_coerce(reading)` → `{used_percentage: float, resets_at: float}` or None
    (rejects non-dict, missing keys, `resets_at <= 0`).
  - Monotonicity: within one window `used_percentage` only rises, so for the SAME
    reset time the HIGHER used% is the more recent reading; keep the max.
  - `_is_new_window(old,new,secs)`: `new.resets_at - old.resets_at > secs/2` → a
    reset happened; replace.
  - `_is_older_window(old,new,secs)`: `< -secs/2` → a stale older reading; ignore.
  - `_window_view(win, now)`: if the stored `resets_at <= now`, roll it forward by
    `secs` and mark `stale=True` and `used=None` (the window rolled unseen).
    Returns `{used_percentage, resets_at, secs_to_reset, observed_at, stale}`.
  The header shape Claude Code delivers (what `_coerce` consumes) is
  `rate_limits = {"five_hour": {"used_percentage": <float>, "resets_at": <epoch float>}, "seven_day": {...}}` — mirror `_coerce` exactly and treat anything that
  doesn't match as "skip" (never raise).

Conventions to match:
- Stdlib only. **The new module must NEVER raise to a caller** (it runs inside
  Claude Code's statusline hot path). Wrap every public function so exceptions
  become a no-op / None, exactly like `token_forecast.ratelimits` ("Never raises
  to callers") and `live/store.py`.
- Put the new module in **`token_oracle/core/`**, not `live/`: `core.config`
  (which consumes it) may import `core.*` but must not depend on `live.*`. The
  module itself imports nothing from token-oracle (pure stdlib) so there is no
  cycle.
- Persistence path: XDG-aware, mirroring `store.default_live_path()`:
  `os.path.join(XDG_DATA_HOME or ~/.local/share, "token-oracle", "ratelimits.json")`.

## Commands you will need

| Purpose   | Command                                                   | Expected            |
|-----------|-----------------------------------------------------------|---------------------|
| Tests (all)   | `python -m pytest -q`                                 | all pass            |
| Tests (focus) | `python -m pytest -q tests/test_ratelimits.py tests/test_config.py tests/test_cli.py` | pass |
| Lint      | `ruff check token_oracle tests`                           | exit 0              |
| Format    | `ruff format --check token_oracle tests`                  | exit 0              |
| Types     | `python -m mypy token_oracle --ignore-missing-imports`    | 0 errors            |
| Confirm worktree code | `python -c "import token_oracle, os; print(os.path.dirname(token_oracle.__file__))"` | path under this worktree |

If the import check does not print a path under this worktree, prefix python
commands with `PYTHONPATH="$PWD"`. Do NOT run `pip install -e`.

## Scope

**In scope**:
- `token_oracle/core/ratelimits.py` (create)
- `token_oracle/core/config.py` (add own-snapshot as a 5h source)
- `token_oracle/cli/main.py` (statusline stdin ingest + a doctor status line)
- `SETUP.md` (document wiring `oracle statusline` to enable live truth)
- `tests/test_ratelimits.py` (create)
- `tests/test_config.py` (add source-priority + hermeticity tests)
- `tests/test_cli.py` (add the statusline-ingest test)

**Out of scope** (do NOT touch):
- `~/token-forecast/**` — read-only reference; never modify or import it into shipped code.
- `token_oracle/core/engine.py` — it already consumes `try_get_claude_five_hour_data`; no change needed.
- The weekly number / `token_oracle/live/overlay.py` — that is plan 054.
- `token_oracle/adapters/statusline.py` — keep `render()` pure; do the stdin read in the CLI handler, not the adapter.

## Git workflow

- Branch: `advisor/053-self-ingest-ratelimits` (worktree already on it).
- One commit per step. Conventional commits, e.g.
  `feat(core): self-ingest Claude rate-limit header for live 5h`.
- Do NOT push or open a PR. (Plan 054 will be implemented in this same worktree
  after this plan is complete and committed.)

## Steps

### Step 1: Create `token_oracle/core/ratelimits.py`

Port the reference algorithm, stdlib-only, never-raises, persisting atomically.
Target public API:

```python
"""Self-ingested Claude rate-limit header (server truth for 5h / weekly).

Claude Code hands its statusline command a `rate_limits` block on stdin each
render. ingest() folds the freshest reading per window into a small JSON
snapshot; five_hour()/weekly() read it back. Monotonic within a window; a
forward jump in resets_at means a reset. Stdlib only. Never raises to callers.
"""
import json, os, tempfile, time

WINDOWS = {"five_hour": 5 * 3600, "seven_day": 7 * 24 * 3600}

def default_path() -> str:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "token-oracle", "ratelimits.json")

def _coerce(reading):        # -> {"used_percentage": float, "resets_at": float} | None
    ...

def _load(path) -> dict:     # never raises; {} on missing/corrupt
    ...

def _save(path, snap) -> None:   # atomic mkstemp+os.replace, mirrors live/store.py; never raises
    ...

def ingest(rate_limits, now=None, path=None) -> dict:
    """Fold a Claude `rate_limits` payload into the snapshot, keeping the
    freshest reading per window. Returns the snapshot dict. Never raises."""
    ...

def _window_view(win, now=None, path=None):   # {used_percentage, resets_at, secs_to_reset, observed_at, stale} | None
    ...

def five_hour(now=None, path=None): return _window_view("five_hour", now, path)
def weekly(now=None, path=None):    return _window_view("seven_day", now, path)
```

Implementation notes:
- `ingest`: for each window in `WINDOWS`, `_coerce` the sub-dict; skip if None.
  Stamp `observed_at = now`. Replace the stored reading when: no prior; OR
  `_is_new_window` (reset); keep prior when `_is_older_window`; else replace only
  if `inc.used_percentage >= old.used_percentage` (monotonic max). Persist via
  `_save` only if something changed. NEVER raise — wrap the whole body in
  try/except returning the (possibly unchanged) snapshot.
- `_window_view`: load snapshot; if the window's `resets_at <= now`, roll forward
  by `WINDOWS[win]` and set `stale=True`, `used_percentage=None`. Return the dict.
- `_save`: mkstemp in the target dir, fdopen+json.dump, `os.replace`, unlink tmp
  on error — copy the structure of `live/store.py:save_snapshot` (lines 30-63).
- All public functions accept an explicit `path=None` (defaulting to
  `default_path()`) so tests can pass a temp file and stay hermetic.

**Verify** (write `tests/test_ratelimits.py` in Step 5, but sanity-check now):
```
python -c "from token_oracle.core import ratelimits as r; import tempfile,os,time; p=os.path.join(tempfile.mkdtemp(),'rl.json'); now=1000.0; r.ingest({'five_hour':{'used_percentage':2.0,'resets_at':now+3600},'seven_day':{'used_percentage':33.0,'resets_at':now+86400}}, now=now, path=p); print(r.five_hour(now, p)); print(r.weekly(now, p))"
```
→ prints a five_hour dict with `used_percentage 2.0`, `stale False`, and a weekly
dict with `used_percentage 33.0`.

### Step 2: Add the own-snapshot as the FIRST 5h source in `config.py`

In `try_get_claude_five_hour_data(now)`, BEFORE the existing `token_forecast`
block (before line 114), insert token-oracle's own source:

```python
    # Own ingested header (works for any user who wires `oracle statusline`).
    try:
        from . import ratelimits as _own_rl
        d = _own_rl.five_hour(now)
        if d and isinstance(d, dict) and not d.get("stale", False):
            rem = d.get("secs_to_reset")
            sp = d.get("used_percentage")
            if rem is not None:
                return {
                    "reset_in_secs": float(rem),
                    "projected_pct": float(sp) if sp is not None else None,
                    "source": "server",
                }
    except Exception:
        pass
```

Do the analogous insertion at the top of `try_get_claude_five_hour_remaining(now)`
(before its `token_forecast` block at line 42): if `_own_rl.five_hour(now)` is
fresh and has `secs_to_reset`, `return float(secs_to_reset)`.

Rationale for own-first: it is the shipped path and, for a user who wires the
statusline, is exactly as authoritative as (and usually fresher than) any
external source. `token_forecast` and the local `usage_limits.py` remain as
fallbacks below — so the author's current machine behavior does not regress.

**Verify**: `python -m pytest -q tests/test_config.py` → all pass (existing tests
unaffected — with no snapshot present `_own_rl.five_hour` returns None and it
falls through to the old sources).

### Step 3: Capture the header in the statusline command

In `token_oracle/cli/main.py`, add a helper near the other module-level helpers:

```python
def _maybe_ingest_rate_limits() -> None:
    """If Claude Code piped its statusline JSON on stdin, fold the rate_limits
    header into our snapshot. Silent + never raises (statusline hot path)."""
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return
        raw = sys.stdin.read()
        if not raw.strip():
            return
        payload = json.loads(raw)
        rl = payload.get("rate_limits") if isinstance(payload, dict) else None
        if rl:
            from ..core import ratelimits as RL
            RL.ingest(rl)
    except Exception:
        pass
```

Then change the statusline handler (lines 447-449) to call it first:

```python
    if args.cmd == "statusline":
        _maybe_ingest_rate_limits()
        print(sl.render(run_forecast(now, cfg)))
        return 0
```

Guard rails: only reads stdin when it is NOT a tty (so `oracle statusline` in a
shell `$PROMPT`, where stdin is the terminal, never blocks). Claude Code always
pipes JSON, so the read completes immediately there.

**Verify**:
```
printf '{"rate_limits":{"five_hour":{"used_percentage":7.0,"resets_at":9999999999}}}' | XDG_DATA_HOME=$(mktemp -d) python -m token_oracle.cli.main statusline >/dev/null; echo "ingest exit $?"
```
→ `ingest exit 0` (and, with that same `XDG_DATA_HOME`, `five_hour()` would now
return 7.0 — asserted properly in the Step 5 test).

### Step 4: Doctor + SETUP.md — make the wiring discoverable ("works once set up" → one documented step)

1. In the doctor output (`_doctor_lines` in `main.py` — find it via
   `grep -n "_doctor_lines" token_oracle/cli/main.py`), add ONE status line:
   read `core.ratelimits.five_hour(now)`; if it returns fresh (non-stale) data,
   print e.g. `✓ live 5h truth: ON (server header, {pct}% · {age}s ago)`; else
   print `◌ live 5h truth: OFF — wire `oracle statusline` as your Claude Code
   statusLine to enable it (see SETUP.md)`. Use the existing color helpers /
   badge style already used in `_doctor_lines`. Do not change the doctor exit
   code based on this line (informational only).
2. In `SETUP.md`, add a section "## Live server-truth (5h / weekly)" documenting
   the one-time wiring. Content to include (adapt wording to the file's voice):
   > token-oracle reads Claude Code's authoritative rate-limit header. Wire
   > token-oracle as your Claude Code statusline once, in `~/.claude/settings.json`:
   > ```json
   > { "statusLine": { "type": "command", "command": "oracle statusline" } }
   > ```
   > Claude Code then hands `oracle statusline` the `rate_limits` header on each
   > render; token-oracle captures it, and `oracle dash` shows the exact 5h (and
   > weekly) numbers the website shows — no browser needed. Verify with
   > `oracle doctor` (look for "live 5h truth: ON").

**Verify**: `python -m token_oracle.cli.main doctor` runs and prints the new
"live 5h truth" line (ON or OFF depending on the machine). `grep -c "statusLine"
SETUP.md` ≥ 1.

### Step 5: Tests

`tests/test_ratelimits.py` (new) — model hermetic tests, each using a temp
`path`. Cover:
- `test_ingest_and_read_roundtrip`: ingest 5h=2% + weekly=33% → `five_hour`/
  `weekly` return them, `stale=False`.
- `test_monotonic_same_window_keeps_max`: ingest 2% then 1% at the same
  `resets_at` → read stays 2%.
- `test_new_window_replaces_on_forward_reset_jump`: ingest at `resets_at=R`, then
  at `resets_at=R + 5*3600 + 10` → new reading wins (reset detected).
- `test_stale_when_reset_in_past`: ingest with `resets_at = now-1` then read at a
  later `now` → `stale=True`, `used_percentage=None`.
- `test_never_raises_on_garbage`: `ingest("not a dict")`, `ingest({"five_hour":
  {}})`, `five_hour(path="/nonexistent/x")` → no exception, sane None/{}.

`tests/test_config.py` (add): `test_five_hour_data_prefers_own_snapshot`:
monkeypatch/point `core.ratelimits.default_path` (or pass through env
`XDG_DATA_HOME`) at a temp file, ingest a known 5h%, set
`TOKEN_ORACLE_NO_REAL_LIMITS` unset, call
`config.try_get_claude_five_hour_data(now)` → returns `source == "server"` with
that pct. Keep it hermetic (temp path; do NOT read the real machine snapshot).

`tests/test_cli.py` (add): `test_statusline_ingests_rate_limits`: monkeypatch
`sys.stdin` to a `io.StringIO` of a JSON payload with `rate_limits`, monkeypatch
`sys.stdin.isatty` to return False, set `XDG_DATA_HOME` to tmp, run the
statusline command (`main(["statusline"])`), then assert
`core.ratelimits.five_hour(path=<tmp>)` reflects the ingested value. Model after
the existing statusline/CLI tests already in `tests/test_cli.py`.

**Verify**: `python -m pytest -q` → all pass; ≥7 new tests.

## Test plan

- New file `tests/test_ratelimits.py` (5 tests above). New tests in
  `tests/test_config.py` (source priority) and `tests/test_cli.py` (stdin
  ingest). All hermetic via explicit `path`/`XDG_DATA_HOME` temp dirs — never
  touch the real `~/.local/share/token-oracle/ratelimits.json`.
- Structural pattern: `tests/test_ratelimits.py` mirrors the pure-unit style of
  `tests/test_live_contract.py`; the CLI test mirrors existing statusline tests
  in `tests/test_cli.py`.
- Verification: `python -m pytest -q` → all pass.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `python -m pytest -q` exits 0; ≥7 new tests exist and pass.
- [ ] `token_oracle/core/ratelimits.py` exists, imports nothing from `token_oracle` (stdlib only): `grep -nE "^from |^import " token_oracle/core/ratelimits.py` shows only stdlib.
- [ ] The stdin-ingest smoke command in Step 3 exits 0 and writes the snapshot.
- [ ] `oracle doctor` prints a "live 5h truth: ON|OFF" line.
- [ ] `grep -c "statusLine" SETUP.md` ≥ 1.
- [ ] `ruff check token_oracle tests` = 0; `ruff format --check token_oracle tests` = 0; `python -m mypy token_oracle --ignore-missing-imports` = 0 errors.
- [ ] `git diff --name-only 5de6aac..HEAD` lists only in-scope files.
- [ ] `plans/README.md` status row for 053 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The "Current state" excerpts don't match live code (drift since `5de6aac`).
- Reading `sys.stdin` in the statusline path blocks or breaks a non-Claude-Code
  invocation (e.g. `oracle statusline` at an interactive shell) — the isatty
  guard must prevent this; if it doesn't on your platform, STOP and report
  rather than removing the guard.
- Making `config.try_get_claude_five_hour_data` prefer the own snapshot changes
  the result of any EXISTING config/engine test (it must not — the own source
  returns None when no snapshot exists). If an existing test flips, STOP: it may
  be the non-hermetic overlay-leak pattern from plan 051 — report it, don't
  weaken the assertion.
- The Claude Code header turns out to use different key names than
  `rate_limits.five_hour.used_percentage/resets_at` (you cannot verify this from
  the worktree — implement to the documented shape and rely on the unit tests;
  do NOT invent alternate parsing).

## Maintenance notes

- The number's per-turn (~20 s) cadence is the SERVER's and is intentionally not
  addressed here; this plan removes the *setup* dependency, not the cadence.
- Source priority in `config.try_get_claude_five_hour_data` is now:
  own snapshot → `token_forecast` → local `usage_limits.py`. If a future change
  reorders these, keep "own snapshot first" so shipped behavior does not silently
  depend on an external project again.
- Plan 054 reuses `core.ratelimits.weekly()` to surface the weekly number as a
  live cell; do not remove `weekly()` even though nothing consumes it yet in 053.
- Reviewer: scrutinize that `core/ratelimits.py` truly never raises (it runs in
  Claude Code's render hot path) and that all new tests are hermetic (temp
  `path`/`XDG_DATA_HOME`, never the real snapshot).
