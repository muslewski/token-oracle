# Plan 033: `oracle live-probe` — one probe path, out-of-process, silent by construction

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `token_oracle/live/store.py` and
> `token_oracle/live/web.py` must exist (plan 030 landed). Plans 031/032
> ideally landed too (extractors return `ProviderLive`); if not, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/030-live-truthfulness-contract.md, plans/031-grok-extractor-evidence-bound.md, plans/032-claude-extractor-row-scoped.md
- **Category**: tech-debt / bug
- **Planned at**: commit `2660dd1` + live-web WIP, 2026-07-10

## Why this matters

Even after plans 030–032, live probing still happens **inside** consumer
processes: the dashboard's render loop calls the fetchers synchronously
(multi-second freezes every 8s tick), doctor launches browsers mid-report,
and the scraper's step-by-step `print()` calls are suppressed only by a
fragile env-var handshake (`TOKEN_ORACLE_SILENT_LIVE_PROBE`) that has already
failed once — progress lines leak into the TUI and shift the layout. Also,
`oracle dash`/`oracle doctor` silently create a venv, pip-install packages,
and `os.execve` the process on first run — heavyweight side effects for
commands that should just read data.

This plan gives probing exactly one home: `oracle live-probe`, which fetches,
converts, and atomically writes `live.json`. Every consumer (dash, doctor,
future statusline) *reads the snapshot file* — a reader physically cannot leak
browser progress into its output or block on Chromium. The dashboard refreshes
by spawning `live-probe` as a background subprocess. All scraper progress goes
to a callback (stderr by default), never stdout.

## Current state

- `token_oracle/live/web.py` — fetchers print progress to **stdout** unless
  `TOKEN_ORACLE_SILENT_LIVE_PROBE` is set (e.g.
  `print("   • launching browser (Chromium) for grok.com ...")`); module-level
  `_LIVE_CACHE` / `_LIVE_TTL = 25` in-memory TTL cache; `get_live_status()`
  actively probes both providers.
- `token_oracle/dashboard/app.py` — `run()` probes in-loop on an 8s throttle
  (post-030: fetch → legacy/native convert → `store.save_snapshot`), wrapped
  in the env-var silencing hack; startup prints "⏳ Starting oracle dash..."
  plus browser-progress expectations.
- `token_oracle/cli/main.py`:
  - `_bootstrap_playwright_if_needed()` (lines ~294–353) — venv creation +
    pip install + `os.execve`, called by **doctor** (line ~272) and **dash**
    (~283) and `_live_setup` (~368).
  - doctor's live section (~135–196) calls `lw.get_live_status()` (browser
    launch) and prints a progress line *from inside the line-builder*
    (`print("   → starting browser + loading live pages ...")`, line ~138).
- `token_oracle/live/store.py` (plan 030) — `save_snapshot`, `load_snapshot`,
  `default_live_path()`.
- Repo conventions: argparse subcommands defined in the loop at
  `cli/main.py:203-214`; exit codes returned from `main()`; conventional
  commits; plain pytest.

## Commands you will need

| Purpose | Command | Expected |
|---------|---------|----------|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests   | `python -m pytest -q` | all pass |
| Lint    | `ruff check token_oracle/` + `ruff format --check token_oracle/` | exit 0 |
| Types   | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |
| Smoke   | `TOKEN_ORACLE_SKIP_BOOTSTRAP=1 oracle live-probe --json 2>/dev/null` | valid JSON on stdout, nothing else |

## Scope

**In scope**:
- `token_oracle/live/probe.py` (create)
- `token_oracle/live/web.py` (progress callback; delete stdout prints + env-var hack + `_LIVE_CACHE`; `get_live_status` becomes snapshot-derived)
- `token_oracle/cli/main.py` (new subcommand; doctor/dash de-bootstrap; doctor reads snapshot)
- `token_oracle/dashboard/app.py` (`run()` probe → background subprocess)
- `tests/test_live_probe.py` (create), `tests/test_cli.py` (extend)
- `plans/README.md`

**Out of scope**:
- Extraction logic (`grok_extract.py`, `claude_extract.py`, driver internals
  other than the progress/caching/status changes named here).
- `overlay.py`, `contract.py`, `store.py` APIs.
- Rendering/layout of the dashboard (plan 034). Keep `render_frame` untouched.
- `_live_setup` login flow (it stays interactive and stays bootstrapped).

## Git workflow

- Branch: `advisor/033-live-probe-orchestration`
- Conventional commits, e.g. `feat(live): oracle live-probe subcommand; consumers read live.json only`

## Steps

### Step 1: Progress callback instead of prints

In `token_oracle/live/web.py`:

1. Add module-level type: `ProgressFn = Callable[[str], None]`. Every fetcher
   gains a keyword arg `progress: ProgressFn | None = None`; internal helper
   `_emit(progress, msg)` calls it when set, else writes to **stderr**
   (`print(msg, file=sys.stderr)`).
2. Replace every `if not os.environ.get('TOKEN_ORACLE_SILENT_LIVE_PROBE'): print(...)`
   with `_emit(progress, ...)`. Delete all remaining live-path prints to
   stdout (login-flow prints in `launch_login_session` may stay — it is an
   interactive command).
3. Delete `_LIVE_CACHE` / `_LIVE_TTL` and the cache reads/writes in both
   fetchers — cross-process caching is now the snapshot file's job, and the
   in-memory cache is what made values differ between processes.
4. `get_live_status()` no longer probes. New behavior: read
   `store.load_snapshot()`; derive per-provider state from it, mapping
   missing/old snapshots honestly:
   - no snapshot at all → `unavailable` with message
     `"no live snapshot — run oracle live-probe"`;
   - snapshot older than `STALE_AFTER = 600` seconds → per-provider state
     `stale` (keep original state in a `last_state` key);
   - fresh → the stored states verbatim, plus `last_fetch`/`last_attempt`
     from the snapshot.
   Keep the return shape (dict with "grok", "claude", "last_fetch",
   "last_attempt", "message") so doctor/dash string code keeps working.

**Verify**: `rtk proxy grep -rn "TOKEN_ORACLE_SILENT_LIVE_PROBE" token_oracle/` → no matches; `rtk proxy grep -n "print(" token_oracle/live/web.py` → only stderr `_emit` fallback + `launch_login_session` interactive prints.

### Step 2: probe module + subcommand

Create `token_oracle/live/probe.py`:

```python
"""The ONLY place that actively probes providers. Everything else reads
live.json. Progress goes to the callback (stderr by default) so no consumer
surface can be polluted by browser chatter."""

def run_probe(providers=("grok", "claude"), headless=True,
              progress=None, path=None) -> dict:
    """Fetch each provider, build {name: ProviderLive}, save_snapshot, and
    return the snapshot dict. Per-provider exceptions become
    ProviderLive(state=STATE_ERROR, error=str(e)[:200]) — one provider
    failing must not lose the other's data."""
```

In `token_oracle/cli/main.py`:

1. Add `"live-probe"` to the subcommand loop with flags:
   `--provider {grok,claude,all}` (default all), `--json` (machine output).
2. Handler: call `_bootstrap_playwright_if_needed()` (probe IS a legitimate
   bootstrap trigger — it needs the browser), then
   `run_probe(...)` with `progress=lambda m: print(m, file=sys.stderr)`.
   Output: with `--json`, dump the snapshot dict to stdout; otherwise print a
   short per-provider summary line
   (`grok: ok — weekly 10.0% (grok.progressbar, 3s ago)` /
   `claude: authenticated_no_data — no reliable live data`).
   Exit codes: 0 if any provider state is `ok` or `rate_data_only`;
   3 if any is `needs_login` (and none ok); 4 otherwise.
3. Remove `_bootstrap_playwright_if_needed()` from the **doctor** and **dash**
   handlers (leave it in `live-setup` and `live-probe`). Doctor and dash must
   run to completion with no playwright anywhere.

**Verify**: `TOKEN_ORACLE_SKIP_BOOTSTRAP=1 oracle live-probe --json 2>/dev/null | python -m json.tool > /dev/null` → exit 0 (valid JSON, stdout clean).

### Step 3: doctor reads the snapshot

Rewrite doctor's live section (`_doctor_lines`) to use the new
`get_live_status()` (snapshot-derived, instant):

- Delete the `print("   → starting browser + loading live pages ...")` line
  and the raw `lw.fetch_*` diagnostic re-probe block (~161–189).
- Rows to emit:
  - fresh snapshot → `live — grok=ok (weekly 10.0% · 42s ago) claude=authenticated_no_data`
    — when a provider is `ok`, include its top usage reading value +
    extractor id + age; when not, include the state and the honest message.
  - stale → `live — snapshot is 23m old — run oracle live-probe`
  - missing → `live — not probed yet (run oracle live-probe; oracle live-setup first if never logged in)`
- Also delete the "⏳ oracle doctor ... expect 10-30s" banner in the doctor
  handler (`main()` ~273–274) — doctor is instant now.

**Verify**: `TOKEN_ORACLE_SKIP_BOOTSTRAP=1 oracle doctor; echo exit=$?` →
completes in < 5s, no browser text, exit reflects existing pass/fail logic.

### Step 4: dashboard probes via background subprocess

In `token_oracle/dashboard/app.py` `run()`:

1. Delete the in-loop fetcher calls, the env-var silencing block, and the
   "Starting browser..." startup prints.
2. Add a probe worker: a `threading.Thread(daemon=True)` running a loop:
   spawn `subprocess.run([sys.executable, "-m", "token_oracle.cli.main", "live-probe", "--json"], capture_output=True, text=True, timeout=90)`
   — but prefer the blessed venv binary when present
   (`~/.local/share/token-oracle/venv/bin/oracle`, absolute path via
   `os.path.expanduser`); sleep `LIVE_PROBE_INTERVAL = 60` between runs
   (the probe takes 10–30s; the old 8s/25s cadence guaranteed overlap).
   The worker only writes to a `threading.Event`-guarded "last probe result"
   slot; it never prints. stderr from the subprocess is captured and its last
   3 lines stored for display (plan 034 renders them; until then discard).
3. The render loop reads `store.load_snapshot()` every frame (cheap file
   read) and builds overlay cells; first frame renders immediately with
   whatever snapshot exists (honest `stale`/`unavailable` states included).
4. On dash exit (KeyboardInterrupt) no join needed (daemon thread), but wrap
   the worker body in try/except to avoid stack traces on shutdown.

**Verify**: `python -m pytest -q tests/test_dashboard.py` → pass. Manual (if
possible): `TOKEN_ORACLE_SKIP_BOOTSTRAP=1 oracle dash` for ~10s → frame
renders instantly, no browser text ever appears on screen.

### Step 5: tests

`tests/test_live_probe.py`:
1. `run_probe` with monkeypatched fetchers (one returns a ProviderLive, one
   raises) → snapshot written (assert via `load_snapshot` under isolated
   `XDG_DATA_HOME`), failing provider has `state == "error"`, healthy
   provider's readings intact.
2. `run_probe` progress callback receives ≥1 message; nothing written to
   stdout (capsys).
3. `get_live_status` with no snapshot → `unavailable` + message mentions
   `live-probe`; with a stale snapshot (written_at = now − 3600, pass a fixed
   `now` — add a `now=None` param for testability) → `stale`.

`tests/test_cli.py` additions (follow the existing `test_clean_*` pattern for
XDG isolation and `TOKEN_ORACLE_SKIP_BOOTSTRAP`):
4. `main(["live-probe", "--json"])` with monkeypatched `run_probe` → stdout is
   parseable JSON only; exit code table honored (parametrize ok/needs_login/error).
5. `main(["doctor"])` with a pre-written fresh snapshot in isolated
   XDG_DATA_HOME → output contains the provider state string, completes
   without importing playwright (monkeypatch `token_oracle.live.web.PLAYWRIGHT_AVAILABLE` to False and assert no exception).

## Test plan

Above. All tests playwright-free and network-free; monkeypatch fetchers at
`token_oracle.live.probe.<fetcher>` import site.

## Done criteria

- [ ] `python -m pytest -q` exits 0 with ≥ 7 new tests
- [ ] `ruff check` / `ruff format --check` / `mypy` exit 0
- [ ] `grep -rn "TOKEN_ORACLE_SILENT_LIVE_PROBE" token_oracle/ tests/` → no matches
- [ ] `grep -n "_LIVE_CACHE" token_oracle/live/web.py` → no matches
- [ ] `grep -n "_bootstrap_playwright_if_needed" token_oracle/cli/main.py` → called only in the `live-setup` and `live-probe` handlers
- [ ] `oracle live-probe --json 2>/dev/null` emits JSON-only stdout
- [ ] `plans/README.md` status row updated

## STOP conditions

- Plans 031/032 not landed (fetchers still return legacy dicts) — the probe
  module would need the legacy adapter; stop and report rather than
  resurrecting it.
- Doctor's live section depends on actively-probed data in a way the snapshot
  can't provide (should not happen — report specifics if it does).
- The dashboard render loop turns out to need probe results mid-frame in a
  way the snapshot file can't satisfy.

## Maintenance notes

- The snapshot file is now the single cross-process cache; anyone adding a
  new consumer (statusline live hints, MCP endpoint) must read the store, not
  the fetchers. Reviewer: reject any new direct `fetch_*` call outside
  `live/probe.py`.
- `LIVE_PROBE_INTERVAL = 60` and `STALE_AFTER = 600` are the two freshness
  knobs; if users want faster refresh, expose them via config in a future
  plan rather than hardcoding lower values (each probe is a full browser
  session).
- Deferred: a `--watch` daemon mode for live-probe (systemd timer / cron is
  the honest answer today); statusline consuming live.json (trivial once
  needed — read store, apply overlay, never probe).
