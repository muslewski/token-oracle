# Plan 021: Interactive `init` wizard + per-project config discovery

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ada32e9..HEAD -- token_oracle/cli/main.py token_oracle/core/config.py install.py tests/test_cli.py tests/test_config.py tests/test_install.py SETUP.md README.md AGENTS.md`
> Plans 008 (init/clean subcommands) and 017 (presets) MUST be DONE — verify
> `token-oracle init` exists (`oracle init --help` exits 0) and
> `PRESETS` in `token_oracle/core/config.py` has `pro`/`max5`/`max20` keys.
> If either is missing, STOP. The `load_config` excerpt below predates 017's
> `plan` key — expect that drift; the discovery changes below compose with it.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED (touches config resolution used by every command)
- **Depends on**: plans 008, 017 (both DONE required)
- **Category**: dx / direction
- **Planned at**: commit `ada32e9`, 2026-07-02

## Why this matters

Setup today means hand-writing JSON at one global XDG path. Users of
competing tools get one-command onboarding (ccmonitor stores last-used
flags; TokenTracker markets "zero to dashboard in 30 seconds"). And config
is global-only: someone tracking a work repo against a different plan (or a
`generic` source) than their personal default has no per-project story.
This plan adds (a) an interactive first-run wizard on top of plan 008's
`init` — pick a plan preset, pick global vs project scope, pick cost
display — and (b) project-config discovery: a `.token-oracle.json` found by
walking up from the cwd wins over the global file. Flexibility where people
store config was an explicit product ask.

## Current state

- Plan 008 (DONE by prerequisite) moved `install.py`'s
  `write_default_config(path, preset, force)` into
  `token_oracle/core/config.py` and added non-interactive `init` / `clean`
  subcommands to `token_oracle/cli/main.py`. Read the landed code first —
  the wizard wraps that same writer.
- `token_oracle/core/config.py` (at `ada32e9`):
  - `default_config_path()` (config.py:37-38) → `$XDG_CONFIG_HOME|~/.config`
    + `/token-oracle/config.json`.
  - `load_config(path=None)` (config.py:68-107) — `path = path or
    default_config_path()`; missing file → silent fallback to preset;
    unreadable → issue. Validation is accumulate-not-raise into
    `Config.issues`.
- `token_oracle/cli/main.py` — every subcommand takes `--config` via
  `_add_common` (main.py:20-22); `cfg = load_config(args.config)` once at
  main.py:109; doctor renders the config path + provenance rows
  (main.py:32-38).
- After 017: `PRESETS` has `pro` (5h cap 19000), `max5` (88000),
  `max20` (220000); `Config.cost_mode` exists.
- Conventions: stdlib only (no questionary/inquirer — wizard uses `input()`);
  tests function-style with `monkeypatch`/`tmp_path`
  (exemplars: `tests/test_config.py`, `tests/test_cli.py` which drives
  `main([...])` directly); `colors.color_enabled()` gates styling.

## Design (decided — do not redesign)

**Config discovery** in `core/config.py`:

```python
PROJECT_CONFIG_NAME = ".token-oracle.json"

def find_config_path(cwd=None):
    """Resolution order (first hit wins):
    1. $TOKEN_ORACLE_CONFIG (env)
    2. .token-oracle.json in cwd or any ancestor (stop after the user's home
       directory or filesystem root; hard cap 40 levels)
    3. default_config_path()  (global XDG — returned even if absent)
    """
```

- `load_config(path=None)` becomes: explicit `path` argument (the `--config`
  flag) → use it; else `find_config_path()`. No other behavior changes;
  the "missing file → preset defaults" path still applies to whatever path
  wins.
- Doctor provenance: the config row (main.py:32-38) must say which rule won:
  `(--config)`, `(env)`, `(project)`, or `(global)` — one dim suffix.

**Wizard** in `cli/main.py` (helper `_init_wizard(args) -> int`):

- Trigger: `oracle init` with no `--preset`/`--path`/`--force` flags AND
  `sys.stdin.isatty()` AND `sys.stdout.isatty()`. Any flag present, or no
  tty → plan 008's non-interactive behavior unchanged.
- Three questions, numbered-choice `input()` prompts, default in brackets,
  empty answer = default, EOF/KeyboardInterrupt → print `aborted` and
  return 1 without writing:

  ```
  🔮 token-oracle setup

  1) Which plan are you on?
     1. pro    (5h cap ≈ 19k tokens)
     2. max5   (5h cap ≈ 88k)
     3. max20  (5h cap ≈ 220k)   [default]
     Build the choice list from sorted(PRESETS) + caps read from PRESETS —
     never hardcode; new presets must appear automatically.

  2) Where should config live?
     1. global — ~/.config/token-oracle/config.json (all repos)  [default]
     2. this project — ./.token-oracle.json (wins over global here)

  3) Show cost estimates in USD? [Y/n]
  ```

- Writes `{"plan": <choice>, "cost_mode": "auto"|"off"}` via the plan-008
  writer to the chosen path (non-clobbering; if the file exists, print its
  path and `already configured — pass --force to overwrite`, exit 1 — same
  semantics as 008).
- Closing output: written path, then next steps:
  `next: token-oracle doctor · token-oracle dash`.
- If a sage installation is detected, print one extra dim line pointing at
  the integration — but ONLY if plan 022 has landed (it owns detection);
  otherwise skip. Do not implement detection here.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Install | `pip install -e ".[dev]"` | exit 0 |
| Tests | `python -m pytest -q` | all pass |
| Lint | `ruff check token_oracle/ && ruff format --check token_oracle/` | exit 0 |
| Types | `mypy token_oracle/ --ignore-missing-imports` | exit 0 |
| Manual | `oracle init` in a scratch dir (tty) | wizard runs, config written, doctor green |

## Scope

**In scope**:
- `token_oracle/core/config.py` (`find_config_path`, `PROJECT_CONFIG_NAME`)
- `token_oracle/cli/main.py` (wizard + doctor provenance suffix)
- `tests/test_config.py`, `tests/test_cli.py` (extend)
- `SETUP.md` (File location section rewrite + wizard section),
  `README.md` (quickstart: `oracle init` first), `AGENTS.md` (Step 4
  config instructions — mention wizard and project scope)

**Out of scope**:
- `install.py` / `uninstall.py` root scripts (008 already reconciled them).
- `clean` subcommand changes (except: if 008's `clean` removes the global
  config only, leave project-file cleanup out — note it in SETUP instead).
- Sage detection (plan 022), dashboard, sources, pricing values.
- Any prompt library dependency.

## Git workflow

- Branch: `advisor/021-init-wizard-config-discovery`
- Conventional commits, e.g. `feat(cli): interactive init wizard + project config discovery`
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: `find_config_path` + load_config wiring + tests

Implement per Design. Extend `tests/test_config.py`:
env var wins over a project file (monkeypatch both); project file in cwd
found (`monkeypatch.chdir(tmp_path)`); project file two levels up found;
walk stops at home (create `tmp_path/home/user/repo`, monkeypatch
`os.path.expanduser`/`HOME` so "home" is `tmp_path/home/user`, put a
`.token-oracle.json` in `tmp_path/home` — must NOT be found from
`.../user/repo`... place the marker *above* home to assert the stop);
nothing found → `default_config_path()`.

**Verify**: `python -m pytest -q tests/test_config.py` → all pass.

### Step 2: doctor provenance suffix

Doctor's config row gains the winning-rule suffix. Extend the doctor test in
`tests/test_cli.py` (there is an existing doctor test — follow it): with a
project file in cwd, the row contains `(project)`.

**Verify**: `python -m pytest -q tests/test_cli.py` → all pass.

### Step 3: wizard + tests

Implement `_init_wizard` per Design. Tests (in `tests/test_cli.py`):
simulate tty + answers via `monkeypatch.setattr("sys.stdin", io.StringIO("1\n2\n\n"))`
plus monkeypatching `sys.stdin.isatty`/`sys.stdout.isatty` to `lambda: True`
— asserts the project file is written with `plan == "pro"` and
`cost_mode == "auto"`; empty-answers run writes the defaults
(`max20`, global path redirected via `XDG_CONFIG_HOME` monkeypatch);
existing file → exit 1, file unchanged; non-tty → falls through to 008's
non-interactive path (assert no prompt text in capsys).

**Verify**: `python -m pytest -q tests/test_cli.py` → all pass.

### Step 4: docs

SETUP.md File-location section: document the 4-rule resolution order and
`.token-oracle.json`; add a "Guided setup" block showing the wizard
transcript. README quickstart puts `oracle init` as line one. AGENTS.md
Step 4: replace/augment the heredoc instructions with the wizard +
`--preset` non-interactive form (agents should use the flags, not the tty
path — say so explicitly).

**Verify**: `grep -n "token-oracle.json" SETUP.md README.md` → hits;
`python -m pytest -q` green.

## Test plan

- `tests/test_config.py`: +5 discovery cases (Step 1).
- `tests/test_cli.py`: +1 doctor provenance, +4 wizard cases (Steps 2–3).
- Pattern: existing files' style; wizard tests must never require a real tty.
- Verification: `python -m pytest -q` → all pass.

## Done criteria

- [ ] `python -m pytest -q` exits 0
- [ ] `ruff check`, `ruff format --check`, `mypy` exit 0
- [ ] In a tmp dir with a `.token-oracle.json` containing `{"plan":"pro"}`:
  `cd <tmpdir> && oracle doctor` shows the project path with `(project)`
  and windows reflect the pro caps
- [ ] `TOKEN_ORACLE_CONFIG=/tmp/x oracle doctor` shows `(env)` provenance
- [ ] Non-interactive `oracle init --preset max5 --path <tmp>` still works
  exactly as after plan 008 (regression gate)
- [ ] `git status` clean outside in-scope list; `plans/README.md` row updated

## STOP conditions

- Plan 008 or 017 not landed (prerequisite check in the drift block).
- 008's landed `init` flag names differ from `--preset`/`--path`/`--force` —
  reconcile the wizard trigger with the real flags and note the deviation,
  but if the landed design conflicts structurally (e.g. 008 made init
  interactive already), STOP and report.
- Discovery breaks any existing test that assumed global-only resolution —
  report which; do not weaken the test.
- The wizard needs raw-mode/arrow input to feel right — it doesn't; numbered
  `input()` prompts are the design. Do not import `dashboard/keys.py`.

## Maintenance notes

- Every future config key automatically works in both scopes — discovery
  returns one path; no merging across scopes (deliberate: merged configs are
  hell to debug; the doctor provenance line tells users which file won).
- Plan 022's wizard hook: the "sage detected" line slots in after Question 3.
- Reviewer focus: walk-up termination (home boundary, 40-level cap, fs root),
  wizard abort paths writing nothing, non-tty regression.
- Deferred: `oracle config get/set` CLI (YAGNI until asked); sticky
  last-used-flags file (ccmonitor's pattern — our durable config covers it).
