# Plan 036: A first-class `oracle live on` toggle turns real (headed) data on persistently, with honest Xvfb guidance

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index (they do here — you may skip the README edit and report).
>
> **Drift check (run first)**:
> `git diff --stat 059ad33..HEAD -- token_oracle/core/config.py token_oracle/cli/main.py token_oracle/dashboard/app.py`
> Note: Plan 035 lands first and changes `token_oracle/live/*`, NOT these files,
> so this plan's in-scope files should be unchanged by 035. If any in-scope file
> below changed since `059ad33`, compare "Current state" excerpts before
> proceeding; on a mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW (additive config + a new subcommand; no change to forecast math)
- **Depends on**: `plans/035-headed-display-lifecycle.md` (headed probing must
  actually work and report honest states before we make it the default)
- **Category**: dx
- **Planned at**: commit `059ad33`, 2026-07-10

## Why this matters

Today the only way to get real Claude usage numbers in the dash is the
undiscoverable env var `TOKEN_ORACLE_LIVE_HEADED=1`. Nobody would guess it, and
it doesn't persist. The dash's background probe never sets it, so `oracle dash`
shows "no data (unavailable)" for both providers even though the machine is
logged in and capable of real data (proven: headed claude probe returns weekly
58% Fable, five-hour 16%).

This plan adds a **persistent, first-class switch**: `oracle live on` writes a
`live.headed = true` setting to the config; every probe path (the `live-probe`
CLI and the dash's background worker) then runs headed automatically, so the
dash flips to real `● live` data with no env var. `oracle live off` reverts;
`oracle live status` shows the setting, whether a display/Xvfb is available, and
the last probed states. Because headed needs a display or Xvfb, the command is
**honest**: if neither is present it still enables the setting but tells the user
exactly what to install (`xorg-server-xvfb` on Arch, `xvfb` on Debian) — matching
the honest `unavailable` state Plan 035 introduced.

Good for everyone: it's the "turn on real data" affordance, and it works the
same on a desktop (real display) or a server/SSH box (Xvfb virtual display).

## Current state

Files:
- `token_oracle/core/config.py` — the `Config` dataclass and `load_config()`.
  No `live` setting exists yet. Config is a JSON file at
  `~/.config/token-oracle/config.json` (see `default_config_path()`).
- `token_oracle/cli/main.py` — argparse subcommands + dispatch in `main()`; the
  `live-probe` handler resolves headless purely from the env var.
- `token_oracle/dashboard/app.py` — the dash; `_probe_worker()` spawns
  `oracle live-probe --json` as a subprocess every 60s.

### `Config` dataclass — `token_oracle/core/config.py:220-232`

```python
@dataclass
class Config:
    source: str = "claude_code"
    source_opts: dict = field(default_factory=dict)
    cache_path: str = ""
    windows: list[Window] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    plan: str = "max20"
    cost_mode: str = "auto"
    pricing: dict = field(default_factory=dict)
    profiles: dict = field(
        default_factory=dict
    )  # multi-sub: {"claude": {...}, "grok": ...}
```

`load_config()` builds `raw` (a merged dict of preset + file keys) then returns
`Config(source=raw.get(...), ..., profiles=norm_profiles)` at
`token_oracle/core/config.py:442-452`:
```python
    return Config(
        source=raw.get("source", "claude_code"),
        source_opts=raw.get("source_opts", {}),
        cache_path=cache_path,
        windows=windows,
        issues=issues,
        plan=plan,
        cost_mode=cost_mode,
        pricing=pricing,
        profiles=norm_profiles,
    )
```

Config is written by `write_default_config()` (`config.py`, near line 455) which
dumps a whole preset. There is **no** partial-update helper yet — you will add
one.

### `live-probe` headless resolution — `token_oracle/cli/main.py:324-334`

```python
    if args.cmd == "live-probe":
        _bootstrap_playwright_if_needed()
        from ..live.probe import run_probe

        prov = args.provider
        headless = os.environ.get("TOKEN_ORACLE_LIVE_HEADED") != "1"
        snap = run_probe(
            providers=prov,
            headless=headless,
            progress=lambda m: print(m, file=sys.stderr),
        )
```

### Subcommand registration — `token_oracle/cli/main.py:231-256`

```python
    for name in (
        "forecast", "snapshot", "statusline", "tmux", "doctor", "dash",
        "init", "clean", "live-setup", "live-probe",
    ):
        sp = sub.add_parser(name)
        _add_common(sp)
        ...
        if name == "live-probe":
            sp.add_argument("--provider", choices=["grok", "claude", "all"], default="all")
            sp.add_argument("--json", action="store_true")
```

### Dash probe worker — `token_oracle/dashboard/app.py:362-389`

```python
    def _probe_worker():
        try:
            while True:
                blessed = os.path.expanduser("~/.local/share/token-oracle/venv/bin/oracle")
                if os.path.isfile(blessed) and os.access(blessed, os.X_OK):
                    cmd = [blessed, "live-probe", "--json"]
                else:
                    cmd = [sys.executable, "-m", "token_oracle.cli.main", "live-probe", "--json"]
                try:
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
                    ...
                time.sleep(LIVE_PROBE_INTERVAL)
```

The subprocess inherits the parent's environment and loads the **default config**
(no `--config` passed). So once the `live-probe` handler honors `cfg.live.headed`
(Step 3), the dash worker probes headed automatically with **no change needed**
to `app.py` — the persisted setting is enough. (You will still add a small
doctor/status surface, Step 5.)

### Repo conventions to match

- Subcommand handlers are `if args.cmd == "...":` blocks in `main()` returning an
  int exit code. Match that style; don't refactor to a dispatch table.
- Config validation is defensive: unknown/invalid values append to `issues` and
  fall back to a default, never crash (see how `cost_mode` is validated at
  `config.py:382-385`). Match that for the new `live` setting.
- Atomic writes: the project writes files atomically elsewhere (see
  `token_oracle/live/store.py` `save_snapshot` — mkstemp + `os.replace`). The
  config-update helper should preserve existing keys and write atomically.
- stdlib only (`dependencies = []`); no new packages.
- Color/badges: use `token_oracle/cli/colors.py` helpers (`ok_badge`, `violet`,
  `dim`) as `_live_setup` does (`cli/main.py:459-495`).

## Commands you will need

| Purpose   | Command                                                    | Expected |
|-----------|------------------------------------------------------------|----------|
| Install   | `pip install -e ".[dev]"`                                  | exit 0   |
| Tests     | `python -m pytest -q tests/test_cli.py tests/test_config.py`| all pass |
| Full suite| `python -m pytest -q`                                      | all pass |
| Lint      | `ruff check token_oracle/ tests/`                          | no issues|
| Format    | `ruff format --check token_oracle/ tests/`                 | clean    |
| Types     | `mypy --ignore-missing-imports token_oracle/`              | no new errors |
| Manual    | `TOKEN_ORACLE_SKIP_BOOTSTRAP=1 oracle live status`         | prints setting + display/Xvfb availability |

Use `TOKEN_ORACLE_SKIP_BOOTSTRAP=1` for any manual `oracle` run so it doesn't try
to build the bootstrap venv. In tests, always pass an explicit `--config` in a
tmp dir (see existing `tests/test_cli.py` patterns) so you never touch the real
`~/.config`.

## Scope

**In scope**:
- `token_oracle/core/config.py` — add `live` field + parsing + an
  `update_config_file()` helper.
- `token_oracle/cli/main.py` — new `live` subcommand (on/off/status); make
  `live-probe` honor `cfg.live.headed`.
- `token_oracle/dashboard/app.py` — only if needed for a status surface; the
  probe worker itself should need no change (see note above). Prefer touching it
  minimally or not at all.
- `tests/test_config.py`, `tests/test_cli.py` — new tests.

**Out of scope** (do NOT touch):
- `token_oracle/live/*` — Plan 035 owns the live package; the probe already
  accepts `headless`. Do not change probe/web here.
- Forecast math, windows, engine, pricing — unrelated.
- The bootstrap venv logic (`_bootstrap_playwright_if_needed`) — leave as is.
- Grok navigation / extraction (RC-B) — grok's `rate_data_only` is truthful; do
  not add usage-page hunting. (See Maintenance notes.)

## Git workflow

- Branch: `advisor/036-live-real-data-toggle` (reviewer creates the worktree).
- Commit per step; conventional commits (e.g.
  `feat(cli): add 'oracle live on/off/status' persistent real-data toggle`).
- **Commit early and often.** Do NOT push or open a PR.

## Steps

### Step 1: Add the `live` setting to config (`config.py`)

Add a field to the `Config` dataclass:
```python
    live: dict = field(default_factory=dict)  # {"headed": bool} — real (headed) live probing
```
In `load_config()`, parse it defensively just before the `return Config(...)`:
```python
    live = raw.get("live", {})
    if not isinstance(live, dict):
        issues.append('config "live" must be an object — ignoring')
        live = {}
    else:
        h = live.get("headed", False)
        if not isinstance(h, bool):
            issues.append('config "live.headed" must be true/false — ignoring')
            live = {}
        else:
            live = {"headed": h}
```
Add `live=live,` to the `Config(...)` return. Add a convenience method on
`Config`:
```python
    def headed_enabled(self) -> bool:
        return bool(self.live.get("headed"))
```

Add an atomic partial-update helper (near `write_default_config`):
```python
def update_config_file(path: str | None, updates: dict) -> str:
    """Deep-ish merge `updates` into the JSON config at `path` (or the default
    path), preserving all other keys, and write atomically. Returns the path."""
    import tempfile
    path = os.path.expanduser(path or default_config_path())
    data = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            data = {}
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(data.get(k), dict):
            merged = dict(data[k]); merged.update(v); data[k] = merged
        else:
            data[k] = v
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d or ".", prefix=".config-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return path
```

**Verify**: `python -c "from token_oracle.core.config import update_config_file, load_config; print('ok')"` → `ok`.

### Step 2: Register the `live` subcommand (`cli/main.py`)

Add `"live"` to the subcommand tuple (Step "Subcommand registration" excerpt),
and give it a positional action:
```python
        if name == "live":
            sp.add_argument("action", choices=["on", "off", "status"])
```

### Step 3: Implement the `live` handler + make `live-probe` honor config

Add a handler block in `main()` (near the `live-setup` block). Factor a small
helper for display/Xvfb detection so status and warnings share it:
```python
    if args.cmd == "live":
        return _live_toggle(cfg, args)
```
Implement `_live_toggle(cfg, args)`:
```python
def _live_toggle(cfg, args):
    import shutil
    from ..cli import colors as c
    from ..core.config import update_config_file, default_config_path
    from ..live.store import load_snapshot

    color = c.color_enabled()
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    has_xvfb = bool(shutil.which("Xvfb"))
    can_headed = has_display or has_xvfb

    if args.action == "status":
        on = cfg.headed_enabled()
        print(c.violet("real data (headed live probing): ", color) + ("ON" if on else "OFF"))
        print(f"  display present: {has_display}   Xvfb installed: {has_xvfb}")
        if on and not can_headed:
            print(_xvfb_hint())
        # last probed states, if any
        snap = load_snapshot() or {}
        for pn in ("grok", "claude"):
            pdat = (snap.get("providers") or {}).get(pn, {})
            st = pdat.get("state", "not probed") if isinstance(pdat, dict) else "not probed"
            print(f"  {pn}: {st}")
        return 0

    if args.action == "on":
        path = update_config_file(args.config, {"live": {"headed": True}})
        print(c.ok_badge(True, color) + f" real data enabled (headed probing) — {path}")
        if not can_headed:
            print(_xvfb_hint())
        else:
            print("  Run `oracle dash` (or `oracle live-probe`) to see live data.")
        return 0

    # off
    path = update_config_file(args.config, {"live": {"headed": False}})
    print(c.ok_badge(True, color) + f" real data disabled — {path}")
    return 0


def _xvfb_hint():
    return (
        "  ⚠ headed mode needs a graphical display or Xvfb (virtual display).\n"
        "    Install Xvfb:  Arch: sudo pacman -S xorg-server-xvfb   "
        "Debian/Ubuntu: sudo apt install xvfb\n"
        "    Until then, live probing will honestly report 'unavailable'."
    )
```
Then make `live-probe` honor the config (edit the `live-probe` handler):
```python
        headed = os.environ.get("TOKEN_ORACLE_LIVE_HEADED") == "1" or cfg.headed_enabled()
        headless = not headed
```
(The env var still force-enables headed even if the config is off — useful for
one-off tests. The config makes it persistent.)

**Verify**:
`TOKEN_ORACLE_SKIP_BOOTSTRAP=1 oracle live status` → prints "OFF" + display/Xvfb
lines (exit 0).
`TOKEN_ORACLE_SKIP_BOOTSTRAP=1 oracle --config /tmp/toc-test.json live on` then
`... live status` → prints "ON".

### Step 4: Confirm the dash inherits the setting (usually no code change)

The dash worker spawns `oracle live-probe --json` with the default config, which
now honors `cfg.headed_enabled()`. Confirm by reasoning + a manual check; do NOT
add env-var plumbing unless a test proves it's needed. If you find the dash uses
a non-default config path that wouldn't see the toggle, add the minimal wiring
(pass the toggle through) and note it — otherwise leave `app.py` untouched.

**Verify**: `grep -n "live-probe" token_oracle/dashboard/app.py` and confirm no
`--config` override that would bypass the default config. State your conclusion
in the report.

### Step 5: Surface the toggle in `doctor` (small, optional-but-preferred)

In the doctor live section (`cli/main.py` around lines 194-224), when the live
row is shown, append whether real data is ON and whether Xvfb is available if
ON-but-not-capable. Keep it one line; reuse `_xvfb_hint()` sparingly (doctor
already has a headed hint for bot-challenge — don't duplicate; prefer a compact
`real data: ON (Xvfb missing)` marker). If wiring this cleanly is more than ~10
lines, skip it and note the deferral — Step 3's `live status` already covers it.

### Step 6: Tests

See Test plan. Write, run, confirm green.

## Test plan

`tests/test_config.py` (extend):
- `test_live_headed_parsed_true`: write a tmp config `{"plan":"max20","live":{"headed":true}}`,
  `load_config(path)`, assert `cfg.headed_enabled() is True`.
- `test_live_headed_default_false`: config without `live` → `cfg.headed_enabled() is False`.
- `test_live_headed_invalid_ignored`: `{"live":{"headed":"yes"}}` → `headed_enabled()`
  False and an `issues` entry mentioning `live.headed` (config never crashes).
- `test_update_config_file_roundtrip`: `update_config_file(tmp, {"live":{"headed":True}})`,
  then re-load raw JSON and assert `live.headed is True` AND a pre-existing key
  (e.g. `plan`) is preserved. Call it again with `{"live":{"headed":False}}` and
  assert it flips without dropping `plan`.

`tests/test_cli.py` (extend — model after existing subcommand tests):
- `test_live_status_off_by_default`: `main(["--config", tmp, "live", "status"])`
  returns 0 and (capsys) prints `OFF`.
- `test_live_on_persists`: `main(["--config", tmp, "live", "on"])` returns 0;
  then `load_config(tmp).headed_enabled() is True`; then
  `main(["--config", tmp, "live", "off"])` → `headed_enabled() is False`.
- `test_live_probe_honors_config_headed`: monkeypatch
  `token_oracle.live.probe.run_probe` (or the imported `run_probe` symbol in
  `cli.main`) to capture the `headless` kwarg; write a tmp config with
  `live.headed=true`; run `main(["--config", tmp, "live-probe", "--json"])` with
  `TOKEN_ORACLE_SKIP_BOOTSTRAP=1` set (monkeypatch env) and `TOKEN_ORACLE_LIVE_HEADED`
  unset; assert `run_probe` was called with `headless=False`. Then set config
  `headed=false` and assert `headless=True`. (This is the core wiring test.)

Verification: `python -m pytest -q tests/test_config.py tests/test_cli.py`
→ all pass incl. new tests; then full `python -m pytest -q`.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `python -m pytest -q` exits 0
- [ ] `TOKEN_ORACLE_SKIP_BOOTSTRAP=1 oracle live status` prints ON/OFF + display/Xvfb (exit 0)
- [ ] `oracle --config <tmp> live on` then `load_config(<tmp>).headed_enabled()` is True;
      `live off` flips it to False (covered by a test)
- [ ] `live-probe` passes `headless=False` to `run_probe` when config `headed=true`
      and env var unset (covered by a test)
- [ ] New tests exist in `tests/test_config.py` and `tests/test_cli.py` and pass
- [ ] `ruff check token_oracle/ tests/` no issues; `ruff format --check` clean
- [ ] `mypy --ignore-missing-imports token_oracle/` no new errors
- [ ] Only in-scope files modified (`git status`); `app.py` untouched unless
      Step 4 proved a change is required (state which in the report)
- [ ] `plans/README.md` status row updated (or skipped — reviewer maintains it)

## STOP conditions

Stop and report back (do not improvise) if:

- Plan 035 has NOT landed on your base branch (headed probing won't actually
  work). Verify: `grep -rn "virtual_display" token_oracle/live/` returns the
  context manager from Plan 035. If absent, STOP — this plan depends on it.
- The drift check shows `config.py`/`main.py`/`app.py` changed since `059ad33`
  and excerpts no longer match.
- A test requires launching a real browser or network — all tests here must be
  monkeypatch/tmp-config only.
- Making `live-probe` honor config would require changing `run_probe`'s
  signature (it already accepts `headless`) — if so, you've misread; re-check.
- You find the dash spawns `live-probe` with a config path that bypasses the
  toggle in a way that needs more than a trivial env pass-through — report the
  design question rather than restructuring the worker.

## Maintenance notes

- **RC-B (grok):** grok's `settings/usage` URL redirects to the chat shell, so
  grok yields only `rate_data_only` (its real quota model is the rate window:
  ~150 queries / 2h). That is the *truthful* state and this plan does not try to
  invent a grok usage %. If a real grok Build usage endpoint is discovered
  later, it's a separate extractor plan — the toggle here already probes grok
  headed, so it would benefit automatically.
- The env var `TOKEN_ORACLE_LIVE_HEADED=1` remains as a one-off override that
  wins over config — keep it working (tests assert config-only path; don't
  remove the env check).
- Reviewer should scrutinize: the atomic `update_config_file` (no partial writes,
  preserves other keys), that `live-probe` honors config AND env, and that the
  Xvfb guidance appears exactly when headed is on but no display/Xvfb exists.
- Follow-up deferred: a dash hotkey to toggle at runtime (write-back to config)
  — considered in brainstorming, not built now; the persistent config + `live
  on/off` is the chosen surface.
