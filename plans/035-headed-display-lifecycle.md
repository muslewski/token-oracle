# Plan 035: Headed browser probing works end-to-end via a shared virtual display, and never lies when it can't

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index (they do here: the reviewer maintains the index, so you
> may skip the README edit and just report).
>
> **Drift check (run first)**:
> `git diff --stat 059ad33..HEAD -- token_oracle/live/web.py token_oracle/live/probe.py`
> If either file changed since this plan was written, compare the "Current
> state" excerpts against the live code before proceeding; on a mismatch,
> treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED (touches the only live-probe browser path; regression-tested)
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `059ad33`, 2026-07-10

## Why this matters

Headed browser probing (`TOKEN_ORACLE_LIVE_HEADED=1 oracle live-probe`) is the
only way to get real Claude usage numbers — headless Chromium is stopped by
claude.ai's Cloudflare bot challenge, while a headed browser (real display or
Xvfb virtual display) passes it. This was **verified live**: `claude` probed
alone headed returns `state=ok` with real readings (five-hour 16%, weekly 58%).

But three bugs make it unreliable and, worse, **untruthful** — which is the one
thing this project must never be (see `plans/030-live-truthfulness-contract.md`):

1. **RC-A (the blocker):** The virtual display (Xvfb) is started and torn down
   *inside each provider fetch*, but the `DISPLAY` env var it sets **persists
   globally after teardown**. In a multi-provider run (`--provider all`, and the
   dash's background probe), the first provider (grok) starts Xvfb `:99`, sets
   `DISPLAY=:99`, then terminates that Xvfb in its `finally`. The second provider
   (claude) sees `DISPLAY=:99` still set, believes a display exists, skips
   starting its own Xvfb, and launches Chromium onto the now-**dead** `:99` →
   fails. Proven by isolation: `claude` alone = `ok`; `claude` after `grok` =
   failure. This is why the dash shows "no data" even with headed enabled.

2. **RC-C (stdout pollution):** `_maybe_start_virtual_display()` announces itself
   with `print(...)` to **stdout**, corrupting `oracle live-probe --json`
   (the JSON no longer parses). Progress must never touch stdout — it goes to
   the progress callback / stderr (this is the same contract the rest of the
   live package already follows, see `token_oracle/live/probe.py` docstring).

3. **RC-D (the lie):** When a headed launch genuinely can't get a display
   (no `$DISPLAY`, no Xvfb installed), Chromium raises `TargetClosedError`
   ("Looks like you launched a headed browser without having a XServer
   running"). The broad `except Exception: return None` swallows it, and
   `run_probe` maps the `None` to `state="needs_login"` with note
   `"no playwright data"` — a **false** state. The honest state is "headed mode
   has no display available", which must be reported so the user knows to
   install Xvfb rather than chasing a non-existent login problem.

After this plan: one virtual display is started once per probe run and reused by
all providers (RC-A), no progress reaches stdout (RC-C), and a missing display
produces an honest, actionable state instead of a fake `needs_login` (RC-D).

## Current state

Files:
- `token_oracle/live/web.py` — the live scraper. Contains the display helpers
  and the two provider fetch functions plus a login-session helper. All three
  do their own per-call Xvfb start/teardown (the bug).
- `token_oracle/live/probe.py` — `run_probe()`, the ONLY orchestrator; loops
  over providers calling the fetch functions, builds the snapshot. This is
  where display management belongs (once per run).
- `tests/test_live_probe.py` — existing probe tests (147 lines); monkeypatches
  `fetch_grok_live_usage` / `fetch_claude_live_usage` on the probe module.

### The display helpers — `token_oracle/live/web.py:171-206`

```python
def _has_graphical_display() -> bool:
    """Best effort detection of whether we can show a real browser window."""
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return True
    # On macOS/Windows the assumption is usually GUI is available when running locally
    if os.name == "nt" or sys.platform == "darwin":
        return True
    return False


def _maybe_start_virtual_display():
    """If no real display, try to start Xvfb so headed Playwright can run.
    Returns the Popen object (or None) so caller can clean it up.
    """
    if _has_graphical_display():
        return None
    if not shutil.which("Xvfb"):
        return None
    # Try to find a free display number
    for disp_num in range(99, 150):
        disp = f":{disp_num}"
        try:
            proc = subprocess.Popen(
                ["Xvfb", disp, "-screen", "0", "1280x1024x24", "-ac", "-nolisten", "tcp"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.3)
            if proc.poll() is None:  # still running
                os.environ["DISPLAY"] = disp          # <-- RC-A: never restored
                print("  Started virtual display (Xvfb) for browser.")  # <-- RC-C: stdout
                return proc
            proc.terminate()
        except Exception:
            pass
    return None
```

### Per-fetch display use — three identical sites in `token_oracle/live/web.py`

Grok fetch (`fetch_grok_live_usage`): start at **line 247-250**, teardown in
`finally` at **line 496-501**:
```python
    xvfb_proc = None
    try:
        if not headless:
            xvfb_proc = _maybe_start_virtual_display()
        _emit(progress, "   • launching browser (Chromium) for grok.com ...")
        with sync_playwright() as p:
            ...
    except Exception:
        return None
    finally:
        if xvfb_proc:
            try:
                xvfb_proc.terminate()
            except Exception:
                pass
```

Claude fetch (`fetch_claude_live_usage`): start at **line 537-540**, teardown in
`finally` at **line 788-793** — identical shape (`except Exception: return None`
then `finally: if xvfb_proc: xvfb_proc.terminate()`).

Login session (`launch_login_session`, defined at **line 796**): start at
**line 832** (`xvfb_proc = _maybe_start_virtual_display()`), teardown at
**line 929-931** — same shape. This is a one-shot interactive helper (used by
`oracle live-setup`), NOT part of the multi-provider loop, so it does not hit
RC-A — but it shares RC-C (the stdout print) and should use the same helper.

### The orchestrator — `token_oracle/live/probe.py` (full)

```python
def run_probe(
    providers=("grok", "claude"), headless: bool = True, progress=None, path: str | None = None
) -> dict:
    if os.environ.get("TOKEN_ORACLE_LIVE_HEADED") == "1":
        headless = False
    if isinstance(providers, str):
        if providers.lower() == "all":
            prov_list = ["grok", "claude"]
        else:
            prov_list = [providers.lower()]
    else:
        prov_list = [p.lower() for p in providers]

    snap_providers: dict[str, ProviderLive] = {}

    for name in prov_list:
        if name not in ("grok", "claude"):
            continue
        if progress:
            try:
                progress(f"   • probing {name} ...")
            except Exception:
                pass
        try:
            if name == "grok":
                pl = fetch_grok_live_usage(headless=headless, progress=progress)
            else:
                pl = fetch_claude_live_usage(headless=headless, progress=progress)

            if isinstance(pl, ProviderLive):
                snap_providers[name] = pl
            else:
                # None or unexpected (e.g. no playwright) → treat as needs_login honest state
                snap_providers[name] = ProviderLive(
                    provider=name,
                    state="needs_login",                 # <-- RC-D: this is the lie
                    readings=[],
                    fetched_at=time.time(),
                    error=None,
                    note="no playwright data",
                )
            ...
        except Exception as e:
            snap_providers[name] = ProviderLive(
                provider=name,
                state=STATE_ERROR,
                readings=[],
                fetched_at=time.time(),
                error=str(e)[:200],
            )

    save_snapshot(snap_providers, path)
    snap_dict = { ... }
    return snap_dict
```

### Contract constants — `token_oracle/live/contract.py`

The honest states already exist. Confirm before use:
```
grep -n "STATE_" token_oracle/live/contract.py
```
You will see `STATE_UNAVAILABLE = "unavailable"`, `STATE_NEEDS_LOGIN = "needs_login"`,
`STATE_ERROR = "error"`, etc. Use `STATE_UNAVAILABLE` for "no display for headed
mode" (it is the existing not-usable state). Do NOT invent a new state string.

### Repo conventions to match

- **Truthfulness first**: never emit a state the evidence doesn't support. A
  swallowed exception must not become `needs_login`. See `plans/030-*.md`.
- **Progress → callback/stderr only, never stdout.** `_emit(progress, msg)`
  already exists in `web.py` for this (grep `def _emit`); use it, or fall back
  to `print(..., file=sys.stderr)`. Never bare `print(...)` for progress.
- **Broad `except` is used deliberately** in the fetch bodies (network flakiness
  must not crash the probe) — keep that behavior, but the RC-D honesty fix is at
  the `run_probe` / preflight layer, not by narrowing those excepts.
- stdlib only (`dependencies = []` in `pyproject.toml`); do not add packages.

## Commands you will need

| Purpose   | Command                                              | Expected on success |
|-----------|------------------------------------------------------|---------------------|
| Install   | `pip install -e ".[dev]"`                            | exit 0              |
| Tests     | `python -m pytest -q tests/test_live_probe.py tests/test_live_display.py` | all pass |
| Full suite| `python -m pytest -q`                                | all pass            |
| Lint      | `ruff check token_oracle/live/ tests/`               | no issues           |
| Format    | `ruff format --check token_oracle/live/ tests/`      | already formatted   |
| Types     | `mypy --ignore-missing-imports token_oracle/live/`   | no new errors       |

Note: the full suite is fast (~1s) because the live tests are fixture-based and
never launch a browser. Do NOT set `TOKEN_ORACLE_LIVE_HEADED=1` in tests.

## Scope

**In scope** (the only files you should modify):
- `token_oracle/live/web.py`
- `token_oracle/live/probe.py`
- `tests/test_live_probe.py`
- `tests/test_live_display.py` (create)

**Out of scope** (do NOT touch):
- `token_oracle/live/grok_extract.py`, `claude_extract.py`, `extract_common.py`,
  `contract.py`, `store.py`, `overlay.py` — the extraction/contract layer is
  correct; this plan is only about *when/where the browser gets a display* and
  *what state is reported when it can't*.
- `token_oracle/cli/main.py`, `token_oracle/dashboard/app.py` — the CLI/dash
  wiring and the persistent toggle are Plan 036. Do not add config plumbing here.
- The actual DOM extraction, navigation URLs, or Cloudflare handling.

## Git workflow

- Branch: `advisor/035-headed-display-lifecycle` (the reviewer creates the
  worktree/branch; you work inside it).
- Commit per step (conventional commits, matching `git log`, e.g.
  `fix(live): share one virtual display across probe run`).
- **Commit early and often** — after each green step. Do NOT push or open a PR.

## Steps

### Step 1: Add a `virtual_display()` context manager to `web.py` (fixes RC-A + RC-C)

Add a context manager that owns the display for a whole probe run and **restores
`DISPLAY` on exit**. Target shape (place it near `_maybe_start_virtual_display`,
keep that function or inline its Xvfb-spawn logic into the CM — your choice, but
the CM is the new public entry):

```python
import contextlib

@contextlib.contextmanager
def virtual_display(progress=None):
    """Ensure a usable display for a headed browser for the duration of the
    `with` block. Yields True if a display is usable (real display already
    present, or an Xvfb we started), False if none is available.

    Restores os.environ['DISPLAY'] to its prior value on exit (RC-A): if we
    set it, we unset/restore it so a later consumer never inherits a dead
    display. Progress goes to the callback/stderr, never stdout (RC-C).
    """
    if _has_graphical_display():
        yield True
        return
    if not shutil.which("Xvfb"):
        yield False
        return
    prev = os.environ.get("DISPLAY")          # may be None
    proc = None
    started_disp = None
    try:
        for disp_num in range(99, 150):
            disp = f":{disp_num}"
            try:
                p = subprocess.Popen(
                    ["Xvfb", disp, "-screen", "0", "1280x1024x24",
                     "-ac", "-nolisten", "tcp"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                time.sleep(0.3)
                if p.poll() is None:
                    proc = p
                    started_disp = disp
                    os.environ["DISPLAY"] = disp
                    _emit(progress, "   • started virtual display (Xvfb) for browser")
                    break
                p.terminate()
            except Exception:
                pass
        yield proc is not None
    finally:
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass
        # RC-A: restore DISPLAY to its prior value (unset if it was unset),
        # but only if we're the one who set it.
        if started_disp is not None and os.environ.get("DISPLAY") == started_disp:
            if prev is None:
                os.environ.pop("DISPLAY", None)
            else:
                os.environ["DISPLAY"] = prev
```

Confirm `_emit` exists (`grep -n "def _emit" token_oracle/live/web.py`) and takes
`(progress, message)`. If its signature differs, match it. If `contextlib` /
`shutil` / `subprocess` / `time` aren't already imported at the top of `web.py`,
add the missing ones (check first — most already are).

**Verify**: `python -c "from token_oracle.live.web import virtual_display; print('ok')"`
→ prints `ok`.

### Step 2: Make each provider fetch NOT manage the display itself (fixes RC-A)

In `fetch_grok_live_usage` and `fetch_claude_live_usage`, **remove** the
per-fetch display lifecycle:
- Delete the `xvfb_proc = None` line and the `if not headless: xvfb_proc =
  _maybe_start_virtual_display()` line (grok ~247-250, claude ~537-540).
- In each `finally`, delete the `if xvfb_proc: xvfb_proc.terminate()` block
  (grok ~496-501, claude ~788-793). If that leaves an empty `finally:`, remove
  the `finally:` entirely (keep the `except Exception: return None`).

Add a **preflight** at the top of each fetch body (right after the
`if os.environ.get("TOKEN_ORACLE_LIVE_HEADED") == "1": headless = False` line),
so a direct headed call with no display returns an honest state instead of
crashing/None:

```python
    if not headless and not _has_graphical_display():
        return build_provider_live(
            [], authenticated=False,
            note="headed mode needs a display or Xvfb (install xorg-server-xvfb)",
            now=time.time(),
        )
```

Check `build_provider_live`'s real signature first
(`grep -n "def build_provider_live" token_oracle/live/extract_common.py`) and
match it. It must yield `state="unavailable"` (or the closest honest not-usable
state) for empty readings + `authenticated=False`. If `build_provider_live`
does not produce `unavailable` for this input, construct the `ProviderLive`
directly with `state=STATE_UNAVAILABLE` instead. **Verify your choice** by
asserting the state in the Step 5 test — do not guess.

### Step 3: Own the display once in `run_probe` (fixes RC-A + RC-D)

Wrap the provider loop in `virtual_display()` when headed, and replace the
`needs_login` lie with an honest state:

```python
    ...
    if os.environ.get("TOKEN_ORACLE_LIVE_HEADED") == "1":
        headless = False
    # (prov_list computed as before)

    snap_providers: dict[str, ProviderLive] = {}

    from .web import virtual_display          # local import, mirrors existing style
    display_ok = True
    cm = virtual_display(progress) if not headless else contextlib.nullcontext(True)
    with cm as _disp:
        if not headless:
            display_ok = bool(_disp)
        for name in prov_list:
            ...
            try:
                if not headless and not display_ok:
                    # RC-D: honest — headed requested but no display/Xvfb
                    snap_providers[name] = ProviderLive(
                        provider=name, state="unavailable", readings=[],
                        fetched_at=time.time(), error=None,
                        note="headed mode needs a display or Xvfb (install xorg-server-xvfb)",
                    )
                    # still emit the progress line, then continue
                    continue
                if name == "grok":
                    pl = fetch_grok_live_usage(headless=headless, progress=progress)
                else:
                    pl = fetch_claude_live_usage(headless=headless, progress=progress)
                if isinstance(pl, ProviderLive):
                    snap_providers[name] = pl
                else:
                    # RC-D: None no longer means "needs_login". If we got here
                    # headed with a display, it's an honest unavailable, not a
                    # login problem.
                    snap_providers[name] = ProviderLive(
                        provider=name, state="unavailable", readings=[],
                        fetched_at=time.time(), error=None,
                        note="no data returned",
                    )
                ...
            except Exception as e:
                ...   # unchanged STATE_ERROR path
```

Add `import contextlib` to `probe.py`. Keep `save_snapshot` + `snap_dict` return
exactly as they are, AFTER the `with` block (so the display is torn down before
the snapshot is written; both are fine, but keep the write outside the loop).

**Important**: preserve the existing progress emission (`   • probing {name} ...`
and `   • {name} → {state}`) for every provider, including the unavailable path,
so the dash activity region still narrates.

**Verify**: `python -c "import token_oracle.live.probe as p; print('ok')"` → `ok`.

### Step 4: Point `launch_login_session` at the shared helper (RC-C consistency)

In `launch_login_session` (line ~796), replace its
`xvfb_proc = _maybe_start_virtual_display()` + `finally` teardown with a
`with virtual_display(...) as disp:` wrapping the browser work. This is a
one-shot interactive helper; behavior is unchanged except the stdout print is
gone and DISPLAY is restored. If this function's structure makes the wrap
awkward, at minimum ensure it no longer calls the old `print(...)` to stdout.
If `_maybe_start_virtual_display` is now unused everywhere, delete it.

**Verify**: `grep -rn "_maybe_start_virtual_display\|print(\"  Started virtual" token_oracle/live/web.py`
→ no matches (or only inside `virtual_display` if you inlined it there without the print).

### Step 5: Tests (create `tests/test_live_display.py`, extend `tests/test_live_probe.py`)

See Test plan below. Write the tests, run them, confirm green.

## Test plan

New file `tests/test_live_display.py` — model structure after existing
`tests/test_live_probe.py` (same import style, `monkeypatch`, no browser):

- `test_virtual_display_real_display_noop`: set `os.environ["DISPLAY"]=":0"`
  (monkeypatch), enter `virtual_display()`, assert it yields `True` and does NOT
  call `subprocess.Popen` (monkeypatch `web.subprocess.Popen` to a sentinel that
  raises if called). After exit, `DISPLAY` unchanged (`:0`).
- `test_virtual_display_starts_and_restores_xvfb` **(RC-A regression)**: unset
  `DISPLAY`/`WAYLAND_DISPLAY`; monkeypatch `web.shutil.which` to return
  `/usr/bin/Xvfb`; monkeypatch `web.subprocess.Popen` to return a fake proc
  whose `.poll()` returns `None` (alive) and records `.terminate()` calls.
  Enter the CM: assert yields `True` and `os.environ["DISPLAY"]` is now set
  (`:99`). Exit the CM: assert the fake proc was terminated AND
  `os.environ.get("DISPLAY")` is back to its pre-call value (unset → not in
  environ). This is the core teardown-restore assertion that fails on today's
  code.
- `test_virtual_display_no_display_no_xvfb`: unset display; monkeypatch
  `web.shutil.which` → `None`; enter CM → yields `False`; `Popen` never called.
- `test_virtual_display_no_stdout` **(RC-C regression)**: run the Xvfb-start
  path with `capsys`; assert `capsys.readouterr().out == ""` (nothing on stdout;
  the "started virtual display" line, if any, went to the progress callback).

Extend `tests/test_live_probe.py`:

- `test_run_probe_headed_no_display_is_honest` **(RC-D regression)**: call
  `run_probe(providers="all", headless=False, ...)` in an environment with no
  display and no Xvfb (monkeypatch `web._has_graphical_display` → `False` and
  `web.shutil.which` → `None`, and monkeypatch the two fetch functions to raise
  if called — they must NOT be called when there's no display). Assert both
  providers land in the snapshot with `state == "unavailable"` and a note
  mentioning `Xvfb` — and specifically **NOT** `state == "needs_login"`.
- `test_run_probe_headed_shares_display_across_providers` **(RC-A regression at
  the probe level)**: monkeypatch `web._has_graphical_display` → `False`,
  `web.shutil.which` → `/usr/bin/Xvfb`, `web.subprocess.Popen` → fake-alive
  proc. Monkeypatch `fetch_grok_live_usage` and `fetch_claude_live_usage` on the
  probe module to record `os.environ.get("DISPLAY")` at call time and return a
  minimal `ProviderLive(state="ok"|"rate_data_only", ...)`. Call
  `run_probe(providers="all", headless=False)`. Assert BOTH recorded a non-empty
  `DISPLAY` equal to the same `:99` (i.e. the second provider still saw a live
  display — the bug would leave it dead/stale). After the call, assert the fake
  Xvfb was terminated exactly once (one display for the whole run, not one per
  provider).
- Keep the existing tests green — the current `needs_login` behavior for the
  *headless* None case is being changed; if an existing test asserts
  `needs_login` for a headless None fetch, update it to the new honest
  `unavailable`/`no data returned` expectation and note the change in your
  report. (Grep: `grep -n "needs_login" tests/test_live_probe.py`.)

Verification: `python -m pytest -q tests/test_live_display.py tests/test_live_probe.py`
→ all pass, including the 6 new tests. Then full suite `python -m pytest -q`.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `python -m pytest -q` exits 0 (full suite green)
- [ ] `tests/test_live_display.py` exists with the 4 display tests; the 2 new
      probe tests exist — all pass
- [ ] `grep -rn "print(\"  Started virtual" token_oracle/live/` → no matches (RC-C)
- [ ] `grep -rn "no playwright data" token_oracle/live/probe.py` → no matches
      (the RC-D lie is gone)
- [ ] `grep -rn "xvfb_proc" token_oracle/live/web.py` → no matches (per-fetch
      teardown removed; all display mgmt is in `virtual_display`)
- [ ] `ruff check token_oracle/live/ tests/` → no issues;
      `ruff format --check token_oracle/live/ tests/` → clean
- [ ] `mypy --ignore-missing-imports token_oracle/live/` → no new errors
- [ ] Only the four in-scope files modified (`git status`)
- [ ] `plans/README.md` status row updated (or skipped — reviewer maintains it)

## STOP conditions

Stop and report back (do not improvise) if:

- The drift check shows `web.py` or `probe.py` changed since `059ad33` and the
  "Current state" excerpts no longer match.
- `build_provider_live` does not produce an `unavailable`-family state for
  empty readings and you cannot determine the correct honest state to emit —
  report what states exist and what you observed.
- Removing the per-fetch `finally` teardown reveals another consumer that
  depended on it (grep `_maybe_start_virtual_display` and `virtual_display`
  across the repo before deleting).
- Any test needs a real browser / network to pass — tests must be
  fixture/monkeypatch only. If you cannot test RC-A without a browser, report
  the design problem rather than shipping an untested fix.
- The full suite has pre-existing failures unrelated to this change — report
  them; do not "fix while you're here".

## Maintenance notes

- The virtual display is now a **probe-run resource**, not a per-fetch one. Any
  future code that calls `fetch_*_live_usage(headless=False)` directly (outside
  `run_probe`) must wrap it in `with virtual_display():` or ensure a real
  `$DISPLAY` — otherwise the fetch's own preflight will honestly return
  `unavailable`.
- RC-B (grok's `settings/usage` redirecting to the chat shell, so grok yields
  only `rate_data_only`) is **out of scope** and is a *truthful* outcome, not a
  bug to fix here. Do not add navigation hacks for grok.
- Plan 036 (persistent "real data" toggle) builds on this: it makes headed the
  default via config and adds the Xvfb install guidance surfaced by the honest
  `unavailable` note this plan introduces.
- Reviewer should scrutinize: the DISPLAY restore logic (the exact bug), that no
  progress reaches stdout, and that the honest `unavailable` state is emitted on
  the no-display path (never `needs_login`).
