# Plan 042 — real `--help` text (descriptions, per-subcommand help, examples)

**Status:** TODO
**Priority:** P1 (Phase 1 "make it visible" — discoverability)
**Effort:** S
**Risk:** low (pure argparse metadata; no behavior change to any command)
**Written against commit:** `7264a71`
**Files in scope:** `token_oracle/cli/main.py`, `tests/test_cli.py`
**Do NOT touch:** any command dispatch body (lines 276–394), `_doctor_lines`, `_bootstrap_playwright_if_needed`, `_live_*`, or any other file.

---

## Why this matters

A new user's first move after install is `token-oracle --help`. Today it is
skeletal — subcommands are listed with **no descriptions**, and every
`<subcommand> --help` shows bare flags with no explanation or examples:

```
$ token-oracle --help
usage: token-oracle [-h]
                    {forecast,snapshot,statusline,tmux,doctor,dash,init,clean,live,live-setup,live-probe} ...

positional arguments:
  {forecast,snapshot,statusline,tmux,doctor,dash,init,clean,live,live-setup,live-probe}

options:
  -h, --help            show this help message and exit
```

```
$ token-oracle dash --help
usage: token-oracle dash [-h] [--config CONFIG]

options:
  -h, --help       show this help message and exit
  --config CONFIG
```

For a CLI whose whole pitch is "know when you'll hit the limit", the help
output should teach the tool in one screen. This plan adds argparse metadata
only — **no command behavior changes.**

## Current state (exact excerpt — `token_oracle/cli/main.py`)

`_add_common` (lines 23–25):

```python
def _add_common(p):
    p.add_argument("--config", default=None)
    p.add_argument("--now", type=float, default=None, help=argparse.SUPPRESS)
```

The parser construction (lines 240–271):

```python
def main(argv=None):
    parser = argparse.ArgumentParser(prog="token-oracle")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in (
        "forecast",
        "snapshot",
        "statusline",
        "tmux",
        "doctor",
        "dash",
        "init",
        "clean",
        "live",
        "live-setup",
        "live-probe",
    ):
        sp = sub.add_parser(name)
        _add_common(sp)
        if name == "forecast":
            sp.add_argument("--json", action="store_true")
        if name == "snapshot":
            sp.add_argument("--out", default=None)
        if name == "init":
            sp.add_argument("--preset", default="max20", choices=sorted(PRESETS))
            sp.add_argument("--force", action="store_true")
        if name == "clean":
            sp.add_argument("--yes", action="store_true")
        if name == "live":
            sp.add_argument("action", choices=["on", "off", "status"])
        if name == "live-probe":
            sp.add_argument("--provider", choices=["grok", "claude", "all"], default="all")
            sp.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
```

## The fix — steps in order (one commit for the whole plan is fine)

### Step 1 — top-level parser: description + examples epilog

Replace the `parser = argparse.ArgumentParser(prog="token-oracle")` line (241)
with a parser that carries a description, an examples epilog, and a
`RawDescriptionHelpFormatter` (so the epilog keeps its line breaks). Also give
the subparsers a clean metavar. Use exactly:

```python
    parser = argparse.ArgumentParser(
        prog="token-oracle",
        description=(
            "token-oracle — forecast when you'll hit your Claude Code / Grok "
            "token limits, computed offline from local agent logs (with optional "
            "browser-verified live numbers)."
        ),
        epilog=(
            "examples:\n"
            "  token-oracle forecast          time left before your next cap\n"
            "  token-oracle dash              full-screen live dashboard (Ctrl-C to quit)\n"
            "  token-oracle doctor            check config, data sources, and live status\n"
            "  token-oracle init              write a starter config file\n"
            "  token-oracle live on           turn on real, browser-verified numbers\n"
            "\n"
            "docs: https://github.com/muslewski/token-oracle"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="<command>")
```

### Step 2 — per-subcommand `help=` + `description=`

Add a module-level constant near the top of the file (just after the imports,
before `def _add_common`) mapping each subcommand to a one-line help string.
The same string doubles as that subcommand's `description` (shown at
`<cmd> --help`):

```python
_CMD_HELP = {
    "forecast": "print a compact usage forecast (time left before your cap)",
    "snapshot": "write the current forecast to a JSON snapshot file",
    "statusline": "print a one-line status for shell prompts / status bars",
    "tmux": "print a tmux-formatted status string",
    "doctor": "check config, data sources, cache, and live status",
    "dash": "full-screen live dashboard (Ctrl-C to quit)",
    "init": "write a starter config file",
    "clean": "remove token-oracle's config, cache, and snapshot files",
    "live": "turn real (browser-verified) live data on / off (or show status)",
    "live-setup": "one-time browser login to grok.com / claude.ai for live data",
    "live-probe": "run the live web probe now and print what it found",
}
```

Then change the `add_parser` call (line 256) to pass help + description:

```python
        sp = sub.add_parser(
            name,
            help=_CMD_HELP[name],
            description=_CMD_HELP[name],
        )
```

### Step 3 — per-argument `help=` strings

Give every visible argument a `help=`. Leave `--now` as
`help=argparse.SUPPRESS` (it is an internal test hook — keep it hidden).

In `_add_common`, add help to `--config` only:

```python
def _add_common(p):
    p.add_argument(
        "--config",
        default=None,
        help="path to config file (default: ~/.config/token-oracle/config.json)",
    )
    p.add_argument("--now", type=float, default=None, help=argparse.SUPPRESS)
```

In the subparser loop, add `help=` to each option/positional:

```python
        if name == "forecast":
            sp.add_argument(
                "--json", action="store_true",
                help="emit machine-readable JSON instead of text",
            )
        if name == "snapshot":
            sp.add_argument(
                "--out", default=None,
                help="output path (default: the standard snapshot location)",
            )
        if name == "init":
            sp.add_argument(
                "--preset", default="max20", choices=sorted(PRESETS),
                help="plan preset for the new config (default: max20)",
            )
            sp.add_argument(
                "--force", action="store_true",
                help="overwrite an existing config file",
            )
        if name == "clean":
            sp.add_argument(
                "--yes", action="store_true",
                help="actually delete (without this, only prints what would be removed)",
            )
        if name == "live":
            sp.add_argument(
                "action", choices=["on", "off", "status"],
                help="on | off | status",
            )
        if name == "live-probe":
            sp.add_argument(
                "--provider", choices=["grok", "claude", "all"], default="all",
                help="which provider(s) to probe (default: all)",
            )
            sp.add_argument(
                "--json", action="store_true",
                help="emit machine-readable JSON instead of text",
            )
```

## Files out of scope / must not change

- Any `if args.cmd == ...:` dispatch block — behavior is unchanged.
- The set of subcommand names, flags, choices, defaults — **identical** to now.
  You are adding `help=`/`description=` text ONLY. If you find yourself removing
  or renaming a flag, STOP — that is out of scope.
- `--now` stays SUPPRESS.

## Test plan (`tests/test_cli.py`)

Add a small test class. Follow the existing test style in this file (it invokes
`main([...])` and/or captures stdout — match whichever pattern is already used
there; if tests call `main()` directly, use `capsys`).

Add these tests:

1. `test_top_help_lists_all_subcommands_with_descriptions` — run
   `main(["--help"])` inside `pytest.raises(SystemExit)` (argparse exits 0 on
   `--help`), capture stdout with `capsys`, and assert the output contains
   `"forecast"`, the description substring `"time left before your cap"` (from
   the forecast help), and `"examples:"`. This proves subcommand help strings
   and the epilog render.
2. `test_subcommand_help_has_description` — `main(["dash", "--help"])` in
   `pytest.raises(SystemExit)`; assert stdout contains
   `"full-screen live dashboard"`.
3. `test_now_flag_is_hidden` — `main(["forecast", "--help"])` in
   `pytest.raises(SystemExit)`; assert `"--now"` is NOT in stdout (stays
   suppressed) while `"--json"` IS.

Pattern for capturing argparse `--help` (argparse calls `sys.exit(0)`):

```python
import pytest

def test_top_help_lists_all_subcommands_with_descriptions(capsys):
    with pytest.raises(SystemExit) as ei:
        main(["--help"])
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert "forecast" in out
    assert "time left before your cap" in out
    assert "examples:" in out
```

(Import `main` the same way the other tests in the file import it.)

## Done criteria (machine-checkable — run from repo root)

1. `python -c "import token_oracle, os; print(os.path.dirname(token_oracle.__file__))"`
   prints a path under THIS worktree (not an installed copy). If not, prefix the
   commands below with `PYTHONPATH="$PWD"`.
2. `TOKEN_ORACLE_SKIP_BOOTSTRAP=1 python -m token_oracle.cli.main --help` shows a
   description line, every subcommand with a help string beside it, and the
   `examples:` epilog.
3. `TOKEN_ORACLE_SKIP_BOOTSTRAP=1 python -m token_oracle.cli.main dash --help`
   shows `full-screen live dashboard` in its description.
4. `TOKEN_ORACLE_SKIP_BOOTSTRAP=1 python -m token_oracle.cli.main forecast --help`
   does NOT contain `--now`.
5. All gates pass:
   - `python -m pytest -q`
   - `ruff check token_oracle tests`
   - `ruff format --check token_oracle tests`
   - `python -m mypy token_oracle --ignore-missing-imports`
6. `git diff --stat` shows only `token_oracle/cli/main.py` and
   `tests/test_cli.py` changed.

Do NOT run `pip install -e` (it clobbers the shared `oracle` entrypoint). The
package is pure-stdlib; it imports directly from the worktree.

## Escape hatches (STOP and report instead of improvising)

- If an existing test in `tests/test_cli.py` asserts on the **exact** old
  `--help` text (e.g. a golden-string match) and your change breaks it: that is
  expected — update that assertion to the new text and note it in your report.
  But if a test that has nothing to do with help output starts failing, STOP —
  you changed behavior you should not have.
- If `argparse` rejects `metavar="<command>"` on `add_subparsers` in this Python
  version, drop the `metavar` argument (keep everything else) and note it.

## Maintenance note

When a new subcommand is added to the loop, add a matching entry to `_CMD_HELP`
(a `KeyError` at parser-build time will catch a missing one immediately). The
epilog examples list is hand-curated — keep it to the 5 highest-value commands,
not an exhaustive list.
