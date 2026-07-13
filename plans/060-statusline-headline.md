# Plan 060 — statusline headline: `$today` cost + `--install` auto-wire

**Written against commit `bd54990`.** Depends on **plan 058** (`core/report.py`
`cost_today` + `engine.cached_events`). Apply 058 (and ideally 059) first in the
same worktree. If `report.cost_today` / `engine.cached_events` are missing —
STOP.

## Why this matters

The statusLine is the stickiest surface a usage tracker has — always in view,
zero commands. cc-statusline earned 624★ doing only this. token-oracle already
self-ingests Claude's server rate-limit header (plans 053/054) but (a) shows no
cost, and (b) makes the user hand-edit `~/.claude/settings.json` to wire it —
the friction that loses installs. This plan makes `oracle statusline` a headline:
`◔ 5h 26% · wk 60% · $8 today`, and adds `oracle statusline --install` to wire
itself safely.

## Scope

**In scope — edit/create ONLY:**
- `token_oracle/cli/main.py` (statusline flags + dispatch + install helper + line compose)
- `token_oracle/adapters/statusline.py` (allow appending a `$today` segment — small, optional)
- `SETUP.md` (update the existing statusLine wiring note to feature `--install`)
- `README.md` (add a short "usage in your status bar" section — TEXT only, no `<img>`)
- `tests/test_cli.py` (install + compose tests)

**Out of scope — do NOT touch:** `core/report.py`, `core/engine.py`,
`core/ratelimits.py`, `core/config.py`, `dashboard/`, `tmux.py`, the `report`
subcommand (plan 059). Do NOT add an `<img>` tag to README — the advisor seeds
the screenshot separately (a committed but missing image would 404 on main). Do
NOT add a `--print` flag (explicitly out of scope this round).

## Semantics — read carefully (the binding project rule)

`Forecast.projected_pct` is a **projection to end-of-window**. The rate-limit
header `used_percentage` is **current usage now** (how full the bucket is).
These are different quantities and must never be written into each other's slot
(this is the rule the whole live round enforced). The headline format shows
**current usage** for 5h/weekly because that is what a glanceable bar wants —
label them `5h` / `wk`, source them from `ratelimits.five_hour()/weekly()`,
never from `projected_pct`.

## Current-state excerpts (@ `bd54990`)

`cli/main.py` statusline dispatch (the whole thing today):
```python
if args.cmd == "statusline":
    _maybe_ingest_rate_limits()
    print(sl.render(run_forecast(now, cfg)))
    return 0
```
`_maybe_ingest_rate_limits()` already folds Claude Code's stdin `rate_limits`
header into the ratelimits snapshot (keep calling it first). `ratelimits`
readback API (do not modify the module):
```python
from ..core import ratelimits as RL
RL.five_hour(now)  # -> {"used_percentage": float|None, "resets_at","secs_to_reset","observed_at","stale": bool} | None
RL.weekly(now)     # same shape; None when never ingested
```
`adapters/statusline.py` today:
```python
def render(forecasts, color=None):
    enabled = c.pipe_color() if color is None else color
    return "  ".join(_segment(f, enabled) for f in forecasts if not f.idle)
```
Colors: `from ..cli import colors as c` — `c.gauge(text, pct, enabled)`,
`c.violet(text, enabled)`, `c.dim(...)`, `c.pipe_color()`. Cost core (plan 058):
`report.cost_today(events, now, mode, overrides) -> {"usd": float, "unpriced_tokens": int}`
and `engine.cached_events(cfg) -> list[event]`.

## What to build

### 1. `$today` segment helper (adapters/statusline.py)
Add a tiny pure helper so both the headline and fallback paths can append cost:
```python
def cost_segment(usd, enabled):
    """' · $X.XX' when usd is a positive float, else '' (never $0.00 noise)."""
    if not isinstance(usd, (int, float)) or usd <= 0:
        return ""
    return c.dim(f" · ${usd:,.2f} today", enabled)
```
Do NOT change `render()`'s existing signature/behavior — only add this helper.

### 2. Compose the statusline (cli/main.py, `if args.cmd == "statusline":`)
Replace the 3-line body with a `_statusline_render(cfg, now, enabled)` helper:
```python
_maybe_ingest_rate_limits()
if getattr(args, "install", False):
    return _statusline_install(force=args.force)
fs = run_forecast(now, cfg)                      # also refreshes the cache
enabled = colors.color_enabled()
print(_statusline_render(cfg, now, fs, enabled))
return 0
```
`_statusline_render`:
- `usd = report.cost_today(engine.cached_events(cfg), now, cfg.cost_mode, cfg.pricing)["usd"]`
  (wrap in try/except → 0.0; this is a hot path, never raise).
- `fh = RL.five_hour(now)`; `wk = RL.weekly(now)`.
- **Headline path** — when `fh` is a dict with a numeric non-stale
  `used_percentage`: build
  `◔ {gauge('5h NN%')} · {gauge('wk NN%')}{cost_segment}` where each gauge uses
  its own pct for the color; drop the `wk` piece if `wk` is None/stale/no pct;
  append `sl.cost_segment(usd, enabled)`. Prefix icon `◔` via `c.violet("◔", enabled)`.
  Round pcts with `round()`. (This is the format a wired Claude Code user sees.)
- **Fallback path** — when there is no usable 5h header (grok/generic, or not yet
  wired): `sl.render(fs) + sl.cost_segment(usd, enabled)` — i.e. **exactly the
  old output** plus an optional cost tail. Preserves every existing behavior and
  test when the ratelimits snapshot is absent.
- `cfg.profiles` prefixing: keep the existing `(multi)`-style behavior only if
  the old code applied it here — it did NOT for statusline (only `forecast`), so
  do not add it.

### 3. `--install` — safe auto-wire (cli/main.py)
Flags under `if name == "statusline":`
```python
if name == "statusline":
    sp.add_argument("--install", action="store_true",
        help="wire `oracle statusline` into ~/.claude/settings.json as your Claude Code statusLine")
    sp.add_argument("--force", action="store_true",
        help="with --install, replace an existing statusLine")
```
Helper (hermetic via `path` param; real default `~/.claude/settings.json`):
```python
def _statusline_install(force=False, path=None):
    import json
    from .cli import colors as c   # adjust import to match file (already `from ..cli import colors`)
    color = colors.color_enabled()
    settings = os.path.expanduser(path or "~/.claude/settings.json")
    claude_dir = os.path.dirname(settings)
    if not os.path.isdir(claude_dir):
        print("~/.claude not found — is Claude Code installed? (nothing changed)")
        return 1
    data = {}
    if os.path.exists(settings):
        try:
            with open(settings, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                print(f"{settings} is not a JSON object — refusing to edit."); return 1
        except (OSError, ValueError) as e:
            print(f"could not read {settings}: {e} — refusing to edit."); return 1
    desired = {"type": "command", "command": "oracle statusline", "padding": 0}
    existing = data.get("statusLine")
    if existing == desired:
        print(colors.ok_badge(True, color) + " statusLine already wired to oracle."); return 0
    if existing and not force:
        print("A statusLine is already configured:")
        print("  " + json.dumps(existing))
        print("Pass --force to replace it with `oracle statusline`.")
        return 1
    # back up, then atomic write
    if os.path.exists(settings):
        try:
            import shutil; shutil.copy2(settings, settings + ".oracle.bak")
            print(colors.ok_badge(True, color) + f" backed up → {settings}.oracle.bak")
        except OSError:
            pass
    data["statusLine"] = desired
    # atomic mkstemp + os.replace in claude_dir (mirror ratelimits._save)
    ...write data as json.dumps(indent=2)...
    print(colors.ok_badge(True, color) + " statusLine → oracle statusline")
    print("Restart Claude Code to see it. 5h / weekly light up as it feeds usage headers.")
    return 0
```
Rules (enforce all): only ever writes the `statusLine` key; preserves every
other key; backs up before writing; idempotent (already-ours → exit 0 no
change); refuses a different existing statusLine unless `--force` (exit 1);
refuses when `~/.claude` is absent (exit 1); atomic write (mkstemp+`os.replace`);
never raises to the user. The Claude Code statusLine schema is
`{"type":"command","command":<str>}` (`padding` optional) — this is the
established contract; do not invent other keys.

### 4. Docs
- **SETUP.md**: in the existing "wire `oracle statusline` as your Claude Code
  statusLine" area (added by plan 053), lead with the one-command path:
  `oracle statusline --install` (then restart Claude Code), and keep the manual
  JSON snippet below as the "or do it by hand" fallback. Mention that 5h/weekly
  become live once Claude Code feeds the header.
- **README.md**: add a compact section after the dashboard demo, e.g.
  `## Live usage in your status bar` — one paragraph + the command
  `oracle statusline --install` + a fenced example line
  `◔ 5h 26% · wk 60% · $8 today`. **No `<img>` tag** (advisor seeds the
  screenshot). Keep it short; do not disturb the banner/badges/demo block.

## Verification (worktree root, `TOKEN_ORACLE_SKIP_BOOTSTRAP=1`)

1. **Fallback unchanged**: with `XDG_DATA_HOME=<tmp>` (no ratelimits snapshot)
   and a data-bearing generic config, `oracle statusline --config <cfg> --now <T>`
   emits the *old* forecast-segment line (optionally + ` · $X.XX today` when
   priced events exist today) — no `◔ 5h` headline. Existing statusline tests
   still pass.
2. **Headline path**: pre-seed a ratelimits snapshot (write via
   `python -c "from token_oracle.core import ratelimits as RL; RL.ingest({'five_hour':{'used_percentage':26,'resets_at':<T+3600>},'seven_day':{'used_percentage':60,'resets_at':<T+600000>}}, now=<T>)"`
   with `XDG_DATA_HOME=<tmp>`), then `oracle statusline --now <T>` contains
   `5h 26%` and `wk 60%`.
3. **`--install` fresh**: `oracle statusline --install` against a `tmp` HOME with
   an empty `~/.claude/` → writes `statusLine`, prints backup+success, exit 0;
   the file now has `{"statusLine":{"type":"command","command":"oracle statusline",...}}`.
4. **`--install` idempotent**: second run → "already wired", exit 0, no `.bak`
   churn / no change.
5. **`--install` refuses**: pre-existing different `statusLine` + no `--force` →
   exit 1, original untouched; with `--force` → replaced, original backed up.
6. **`--install` no ~/.claude** → exit 1, nothing created.
7. `python -m pytest -q tests/test_cli.py` and full `python -m pytest -q` pass.
8. Gates: `ruff check token_oracle tests` ; `ruff format --check token_oracle tests` ;
   `python -m mypy token_oracle --ignore-missing-imports` → 0 errors.
9. `git diff --name-only bd54990..HEAD` for THIS plan's commits touches only:
   `token_oracle/cli/main.py`, `token_oracle/adapters/statusline.py`, `SETUP.md`,
   `README.md`, `tests/test_cli.py`.

## Test plan (`tests/test_cli.py`)
Hermetic: `XDG_DATA_HOME=tmp_path` everywhere (no real ratelimits leak — the
plan-054 trap); `_statusline_install(path=tmp_settings)` with a `tmp_path`
settings file for all install cases (never the real `~/.claude`). Cover items
1–6 above. For the headline test, ingest a snapshot into the tmp XDG dir. Assert
the fallback line is byte-stable vs the pre-change output when no snapshot
exists (guard against accidental format drift for existing users/tmux parity).

## Maintenance note
- A `--print` (dry-run snippet) is a cheap future add if users ask for a
  no-write path.
- If Claude Code changes its statusLine schema, `_statusline_install`'s
  `desired` dict is the single place to update.
- The `◔` headline currently keys off Claude's header only; a future pass could
  show grok's weekly here too once a stable grok cost model exists.

## STOP conditions
- `report.cost_today` / `engine.cached_events` absent → STOP (058 not applied).
- If making the headline work would require writing `used_percentage` into
  `projected_pct` (or vice-versa) → STOP; you have the semantics wrong.
- If an existing statusline/tmux test can only pass by changing the fallback
  output → STOP and report; the fallback must stay byte-stable when no snapshot.

## Contract
One commit per step (adapter helper; compose + install; docs; tests — ~3–4
commits, conventional, e.g. `feat(cli): statusline $today + safe --install`).
PROGRESS.md ledger (untracked). Final line exactly:
`RESULT: ok|partial|failed — commits: <n> — <summary>`.
