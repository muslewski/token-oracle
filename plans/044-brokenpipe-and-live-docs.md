# Plan 044 — clean `dash | head` (SIGPIPE) + document live web / Xvfb

**Status:** TODO
**Priority:** P1 (Phase 1 — robustness + docs)
**Effort:** S
**Risk:** low (one process-level signal reset at CLI entry; a docs section)
**Written against commit:** `7264a71`
**Files in scope:** `token_oracle/cli/main.py`, `SETUP.md`, `tests/test_cli.py`
**Do NOT touch:** any command dispatch body, the dashboard, extractors, or
`_bootstrap_playwright_if_needed`.

---

## Part A — clean pipe handling (SIGPIPE)

### Why

Piping any oracle output into a consumer that closes early — the classic
`oracle dash | head`, or `oracle forecast | head -1` — currently lets Python
raise `BrokenPipeError` and dump a traceback to stderr when the interpreter
flushes stdout at shutdown. Real Unix filters die quietly on `SIGPIPE`; oracle
should too.

### Root cause

Python installs its own `SIGPIPE` handler that turns a closed-pipe write into
`BrokenPipeError` (and prints "Exception ignored in: ... BrokenPipeError" at
exit). The standard fix for a CLI is to restore the **default** disposition
(`SIG_DFL`) at startup, so the OS terminates the process on `SIGPIPE` with no
Python-level noise. This must run inside `main()` because the installed
entrypoints call `token_oracle.cli.main:main` **directly** (see
`pyproject.toml` `[project.scripts]`), never `if __name__ == "__main__"`.

### The fix (`token_oracle/cli/main.py`)

Add this helper just after `_now` (after line 29):

```python
def _reset_sigpipe():
    """Restore default SIGPIPE so `oracle ... | head` dies quietly like a normal
    Unix filter, instead of raising BrokenPipeError + a shutdown traceback.

    No-op on platforms without SIGPIPE (Windows) or when not on the main thread.
    """
    try:
        import signal

        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (ImportError, AttributeError, ValueError):
        pass
```

Then call it on the **first line** of `main()` (before building the parser).
Current line 240–241:

```python
def main(argv=None):
    parser = argparse.ArgumentParser(prog="token-oracle")
```

becomes:

```python
def main(argv=None):
    _reset_sigpipe()
    parser = argparse.ArgumentParser(prog="token-oracle")
```

> NOTE FOR THE EXECUTOR: plan 042 (real `--help`) also edits this
> `argparse.ArgumentParser(...)` construction. If you are applying 042 and 044
> in the same worktree, apply 042 first; then this step just inserts the
> `_reset_sigpipe()` call as the first statement of `main()`, above whatever the
> parser construction now looks like. The two edits do not conflict — 044 adds a
> line at the very top of the function body.

### Part A test (`tests/test_cli.py`)

SIGPIPE end-to-end behavior is awkward to trigger deterministically; test the
mechanism instead. Skip on platforms without `SIGPIPE`:

```python
import signal
import pytest

@pytest.mark.skipif(not hasattr(signal, "SIGPIPE"), reason="no SIGPIPE on this platform")
def test_reset_sigpipe_restores_default():
    # start from Python's default-changed state, then assert our reset wins
    signal.signal(signal.SIGPIPE, signal.SIG_IGN)
    cli_main._reset_sigpipe()
    assert signal.getsignal(signal.SIGPIPE) == signal.SIG_DFL
```

(Use whatever import alias the file already uses for the main module; if none,
add `from token_oracle.cli import main as cli_main`.)

Add one end-to-end smoke test that a normal run emits no BrokenPipe traceback
(does not force a close, but guards against regressions that print one
spuriously):

```python
import os
import subprocess
import sys

def test_forecast_subprocess_no_brokenpipe_noise():
    p = subprocess.run(
        [sys.executable, "-m", "token_oracle.cli.main", "forecast", "--now", "1000"],
        env={**os.environ, "TOKEN_ORACLE_SKIP_BOOTSTRAP": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.getcwd(),
    )
    assert b"BrokenPipeError" not in p.stderr
    assert b"Traceback" not in p.stderr
```

If the subprocess cannot import the package (installed-copy shadowing), pass
`env={... "PYTHONPATH": os.getcwd()}` as well.

---

## Part B — document live web data + Xvfb (`SETUP.md`)

### Why

`oracle live` / `oracle live-setup` / `oracle live-probe` and the headed-mode
`Xvfb` requirement are the tool's biggest differentiator (browser-verified real
numbers), but SETUP.md never explains them. A user who wants real numbers has no
document to follow. The in-CLI `_xvfb_hint()` already names the install
commands; this section makes them discoverable up front.

### Where

`SETUP.md` currently has these top-level sections (verify by reading the file):
`## Installation tiers`, `## Configuration`, `## Optional integrations`. Insert a
new top-level section titled `## Live web data (real, browser-verified numbers)`
**immediately before** `## Optional integrations`.

### Exact content to insert

```markdown
## Live web data (real, browser-verified numbers)

By default token-oracle forecasts entirely offline from local logs. It can also
read your **real** current usage directly from `grok.com` and `claude.ai` using a
headless/headed browser session you log into once. This is opt-in and honest: if
it cannot verify a number, it reports the state (`unavailable`, `needs_login`,
`rate_data_only`) rather than guessing.

### Enable it

```bash
oracle live on          # turn on real (headed) live probing; writes it to your config
oracle live-setup       # one-time browser login to grok.com / claude.ai
oracle dash             # the dashboard now shows live, browser-verified numbers
oracle live status      # check whether it's on and what was last probed
oracle live off         # back to offline-only
```

`oracle live-probe` runs a single probe now and prints what it found
(`--provider grok|claude|all`, `--json` for machine output).

### Xvfb (for machines without a graphical display)

Headed probing needs a display. On a normal desktop it uses your existing one.
On a server / container / SSH session with no `$DISPLAY`, install **Xvfb** (a
virtual display) and token-oracle will use it automatically:

```bash
# Arch / Manjaro
sudo pacman -S xorg-server-xvfb
# Debian / Ubuntu
sudo apt install xvfb
```

Without a display or Xvfb, live probing honestly reports `unavailable` — it
never fabricates a number.

### Notes

- **No fingerprint evasion.** token-oracle drives a real browser with your own
  logged-in session; it does not spoof fingerprints or solve CAPTCHAs. If a site
  serves a bot challenge it reports that state and suggests
  `TOKEN_ORACLE_LIVE_HEADED=1 oracle live-probe`.
- Grok exposes no weekly-usage page, so grok's truthful live state is often
  `rate_data_only` (rate-limit window only) — that is expected, not a bug.
- Live numbers are display-only; they never alter the offline forecast math.
```

> The fenced ```bash blocks are nested inside the block above for readability in
> this plan — when you paste into SETUP.md, they are normal top-level fenced code
> blocks within the new section. Keep the section's own heading level at `##`
> (matching the neighboring sections) and the sub-headings at `###`.

---

## Files out of scope / must not change

- No command behavior changes anywhere. Part A only resets a signal disposition;
  Part B is docs.
- Do not touch `_xvfb_hint()` (its wording is intentionally mirrored here).

## Done criteria (machine-checkable — run from repo root)

1. `python -c "import token_oracle, os; print(os.path.dirname(token_oracle.__file__))"`
   prints a path under THIS worktree (else prefix commands with `PYTHONPATH="$PWD"`).
2. Pipe test does not print a traceback:
   `TOKEN_ORACLE_SKIP_BOOTSTRAP=1 python -m token_oracle.cli.main forecast --now 1000 | head -1`
   — exits cleanly, no `BrokenPipeError` / `Traceback` on stderr.
3. `grep -c "Live web data" SETUP.md` returns `1`; `grep -c "xorg-server-xvfb" SETUP.md`
   returns at least `1`.
4. All gates pass:
   - `python -m pytest -q`
   - `ruff check token_oracle tests`
   - `ruff format --check token_oracle tests`
   - `python -m mypy token_oracle --ignore-missing-imports`
5. `git diff --stat` shows only `token_oracle/cli/main.py`, `SETUP.md`, and
   `tests/test_cli.py`.

Do NOT run `pip install -e`.

## Escape hatches

- If `signal.SIGPIPE` does not exist in the test environment, the
  `@pytest.mark.skipif` handles it — do not add a Windows-specific branch.
- If SETUP.md's section names differ from those listed above (the file may have
  been edited since `7264a71`), insert the new section before
  `## Optional integrations` if present, otherwise at the end of the file, and
  note the placement in your report. Do not restructure existing sections.

## Maintenance note

The SETUP.md commands duplicate the CLI's own `_xvfb_hint()` and `oracle live`
help. If the `live` subcommand's flags change, update this section too. The
SIGPIPE reset is intentionally the first line of `main()` so it applies to every
subcommand including `dash`.
