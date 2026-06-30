# token-oracle Presentation Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a central color module and apply agentic-sage-grade presentation polish to token-oracle's adapters, dashboard, doctor, and docs — without touching forecast math.

**Architecture:** New consumer-ring module `oracle/cli/colors.py` owns the palette, terminal-detection, and the gauge thresholds (one source of truth). Adapters/dashboard/doctor render plain strings and apply color via that module at the output site. `oracle/core/*` never imports it.

**Tech Stack:** Python ≥3.10, stdlib only (zero runtime deps). pytest (dev).

## Global Constraints

- **Zero runtime dependencies.** Stdlib only. No `rich`/`textual`/`colorama`.
- **Ring rule:** `oracle/core/*` must not import `oracle/cli/colors.py` or any consumer.
- **Render functions stay pure/plain:** color applied only via `colors` helpers; color-off output must contain zero `\033` escapes and identical text otherwise.
- **One threshold source:** gauge severity cuts live ONLY in `colors.gauge_tier` (`>=120` red, `>=100` orange, `>=85` lime, else green). No other file hardcodes 85/100/120.
- **No forecast/contract/source/snapshot behavior changes.** Presentation only.
- **`NO_COLOR`** disables color everywhere; **`FORCE_COLOR`** (non-empty, non-`"0"`) forces it on interactive surfaces.
- All existing tests stay green (was 56). Test dir is `tests/`.

---

### Task 1: Color foundation module

**Files:**
- Create: `oracle/cli/colors.py`
- Test: `tests/test_colors.py`

**Interfaces:**
- Produces: `color_enabled(stream=None) -> bool`, `pipe_color() -> bool`, `paint(text, code, enabled) -> str`, `violet(text, enabled) -> str`, `dim(text, enabled) -> str`, `gauge_tier(pct) -> str`, `gauge_ansi_code(pct) -> str`, `gauge(text, pct, enabled) -> str`, `gauge_tmux(pct) -> str`, `ok_badge(good, enabled) -> str`; constants `RESET`, `VIOLET`, `DIMC`, `M_ORACLE`, `M_WARN`, `M_BULLET`, `M_OK`, `M_BAD`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_colors.py
import oracle.cli.colors as c


def test_gauge_tier_boundaries():
    assert c.gauge_tier(84) == "green"
    assert c.gauge_tier(85) == "lime"
    assert c.gauge_tier(99) == "lime"
    assert c.gauge_tier(100) == "orange"
    assert c.gauge_tier(119) == "orange"
    assert c.gauge_tier(120) == "red"


def test_paint_off_is_plain():
    assert c.paint("x", c.VIOLET, False) == "x"


def test_paint_on_wraps():
    s = c.paint("x", c.VIOLET, True)
    assert s.startswith("\033[38;5;141m") and s.endswith(c.RESET)


def test_no_color_env_disables(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert c.color_enabled() is False
    assert c.pipe_color() is False


def test_force_color_enables(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert c.color_enabled() is True


def test_pipe_color_ignores_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert c.pipe_color() is True


def test_gauge_codes_differ_by_severity():
    assert c.gauge_ansi_code(130) != c.gauge_ansi_code(10)
    assert c.gauge_tmux(130) != c.gauge_tmux(10)


def test_ok_badge_uses_markers():
    assert c.M_OK in c.ok_badge(True, False)
    assert c.M_BAD in c.ok_badge(False, False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_colors.py -q`
Expected: FAIL — `ModuleNotFoundError: oracle.cli.colors`

- [ ] **Step 3: Write minimal implementation**

```python
# oracle/cli/colors.py
"""Color/ANSI foundation: one palette, one set of gauge thresholds, terminal-aware
gating. Render functions stay plain; color is applied here at the output site so
color-off output is identical minus escape codes. Stdlib only. Consumer-ring util —
oracle.core never imports this."""
import os
import sys

RESET = "\033[0m"

# 256-color foreground codes
VIOLET = "141"
DIMC = "240"
_TIER_CODE = {"green": "42", "lime": "154", "orange": "214", "red": "196"}
_TIER_TMUX = {"green": "green", "lime": "colour154",
              "orange": "colour214", "red": "red"}

# semantic markers
M_ORACLE = "🔮"
M_WARN = "⚠"
M_BULLET = "●"
M_OK = "✓"
M_BAD = "✗"


def _no_color():
    return os.environ.get("NO_COLOR") is not None


def color_enabled(stream=None):
    """Interactive surfaces (dashboard, doctor): NO_COLOR off AND (FORCE_COLOR or tty)."""
    if _no_color():
        return False
    fc = os.environ.get("FORCE_COLOR")
    if fc not in (None, "", "0"):
        return True
    stream = stream if stream is not None else sys.stdout
    return bool(getattr(stream, "isatty", lambda: False)())


def pipe_color():
    """Adapter media (statusline, tmux): codes are read from a pipe, never a TTY —
    gate on NO_COLOR only."""
    return not _no_color()


def paint(text, code, enabled):
    return f"\033[38;5;{code}m{text}{RESET}" if enabled else text


def violet(text, enabled):
    return paint(text, VIOLET, enabled)


def dim(text, enabled):
    return paint(text, DIMC, enabled)


def gauge_tier(pct):
    """Severity tier for a projected pct. The one source of truth for thresholds."""
    if pct >= 120:
        return "red"
    if pct >= 100:
        return "orange"
    if pct >= 85:
        return "lime"
    return "green"


def gauge_ansi_code(pct):
    return _TIER_CODE[gauge_tier(pct)]


def gauge(text, pct, enabled):
    return paint(text, gauge_ansi_code(pct), enabled)


def gauge_tmux(pct):
    return "#[fg=%s]" % _TIER_TMUX[gauge_tier(pct)]


def ok_badge(good, enabled):
    return (paint(M_OK, _TIER_CODE["green"], enabled) if good
            else paint(M_BAD, _TIER_CODE["red"], enabled))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_colors.py -q`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add oracle/cli/colors.py tests/test_colors.py
git commit -m "feat(colors): central palette, gauge thresholds, terminal gating"
```

---

### Task 2: Refactor statusline adapter onto colors

**Files:**
- Modify: `oracle/adapters/statusline.py` (full rewrite below)
- Test: `tests/test_adapters.py` (rewrite the statusline portion)

**Interfaces:**
- Consumes: `oracle.cli.colors` (`pipe_color`, `gauge`, `violet`, `M_WARN`).
- Produces: `render(forecasts, color=None) -> str` (color None → `pipe_color()`); drops the old `color_for`.

- [ ] **Step 1: Write the failing test**

Replace the entire contents of `tests/test_adapters.py` with:

```python
import oracle.cli.colors as colors
from oracle.core.contracts import Forecast
from oracle.adapters import statusline, tmux

F_OK = Forecast("5h", 12000, 220000, 42.0, None, 3 * 3600 + 46 * 60, False)
F_HOT = Forecast("weekly", 5_000_000, 8_000_000, 130.0, 90000.0,
                 5 * 86400 + 18 * 3600, False)


def test_statusline_contains_numbers():
    s = statusline.render([F_OK], color=False)
    assert "12k/220k" in s and "42%" in s


def test_statusline_warns_on_eta():
    s = statusline.render([F_HOT], color=False)
    assert "cap" in s


def test_statusline_color_thresholds():
    assert colors.gauge_ansi_code(130) != colors.gauge_ansi_code(10)


def test_statusline_no_color_has_no_escapes():
    assert "\033" not in statusline.render([F_HOT], color=False)


def test_statusline_color_on_has_escapes():
    assert "\033" in statusline.render([F_OK], color=True)


def test_statusline_skips_idle():
    idle = Forecast("5h", 0, 220000, 0.0, None, 100.0, True)
    assert statusline.render([idle], color=False) == ""


def test_tmux_render_uses_tmux_color_syntax():
    s = tmux.render([F_OK])
    assert "#[fg=" in s and "12k/220k" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_adapters.py -q`
Expected: FAIL — `statusline.render()` takes no `color` kwarg (TypeError).

- [ ] **Step 3: Write minimal implementation**

Replace the entire contents of `oracle/adapters/statusline.py` with:

```python
"""Thin reference adapter: render a Forecast list to one ANSI status line.
Proof the engine renders anywhere; a polished status bar is a separate project."""
from ..core.timeutil import fmt_tokens, fmt_hms, fmt_dh_long
from ..cli import colors as c


def _segment(f, enabled):
    pct = f.projected_pct
    body = (f"{fmt_hms(f.reset_in_secs)} "
            f"{fmt_tokens(f.used)}/{fmt_tokens(f.cap)} →{round(pct)}%")
    if f.eta_to_cap_secs is not None:
        body += f" {c.M_WARN} cap {fmt_dh_long(f.eta_to_cap_secs)}"
    return f"{c.violet('🕐', enabled)} {c.gauge(body, pct, enabled)}"


def render(forecasts, color=None):
    enabled = c.pipe_color() if color is None else color
    return "  ".join(_segment(f, enabled) for f in forecasts if not f.idle)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_adapters.py -q`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add oracle/adapters/statusline.py tests/test_adapters.py
git commit -m "refactor(statusline): render via colors module, color-off clean"
```

---

### Task 3: Refactor tmux adapter onto colors

**Files:**
- Modify: `oracle/adapters/tmux.py` (full rewrite below)
- Test: covered by `tests/test_adapters.py::test_tmux_render_uses_tmux_color_syntax` (already written in Task 2).

**Interfaces:**
- Consumes: `oracle.cli.colors` (`gauge_tmux`). Drops the old `color_for`.
- Produces: `render(forecasts) -> str` (unchanged signature).

- [ ] **Step 1: Verify the covering test exists and currently passes against the old code**

Run: `python -m pytest tests/test_adapters.py::test_tmux_render_uses_tmux_color_syntax -q`
Expected: PASS (old `tmux.color_for` still present). This is the regression guard for the rewrite.

- [ ] **Step 2: Write the implementation**

Replace the entire contents of `oracle/adapters/tmux.py` with:

```python
"""Thin reference adapter: render a Forecast list to a tmux status string."""
from ..core.timeutil import fmt_tokens, fmt_hms, fmt_dh_long
from ..cli import colors as c


def _segment(f):
    pct = f.projected_pct
    body = (f"{fmt_hms(f.reset_in_secs)} "
            f"{fmt_tokens(f.used)}/{fmt_tokens(f.cap)} ->{round(pct)}%")
    if f.eta_to_cap_secs is not None:
        body += f" cap {fmt_dh_long(f.eta_to_cap_secs)}"
    return f"{c.gauge_tmux(pct)}{body}#[default]"


def render(forecasts):
    return " ".join(_segment(f) for f in forecasts if not f.idle)
```

- [ ] **Step 3: Run test to verify it passes**

Run: `python -m pytest tests/test_adapters.py -q`
Expected: PASS (7 tests)

- [ ] **Step 4: Commit**

```bash
git add oracle/adapters/tmux.py
git commit -m "refactor(tmux): single threshold source via colors.gauge_tmux"
```

---

### Task 4: Polish dashboard TUI

**Files:**
- Modify: `oracle/dashboard/app.py` (full rewrite below)
- Test: `tests/test_dashboard.py` (add two color tests; keep the three existing)

**Interfaces:**
- Consumes: `oracle.cli.colors` (`color_enabled`, `violet`, `dim`, `gauge`, `M_ORACLE`, `M_BULLET`, `M_WARN`).
- Produces: `render_frame(forecasts, now, color=None) -> str` (new `color` kwarg, default `color_enabled()`); `run(cfg, now) -> int` unchanged.

- [ ] **Step 1: Write the failing test**

Replace the entire contents of `tests/test_dashboard.py` with:

```python
from oracle.core.contracts import Forecast
from oracle.dashboard.app import render_frame


def test_render_frame_lists_windows():
    fs = [Forecast("5h", 12000, 220000, 42.0, None, 3600.0, False),
          Forecast("weekly", 5_000_000, 8_000_000, 130.0, 90000.0, 400000.0, False)]
    frame = render_frame(fs, now=100000.0, color=False)
    assert "5h" in frame and "weekly" in frame
    assert "42%" in frame and "130%" in frame


def test_render_frame_handles_idle():
    fs = [Forecast("5h", 0, 220000, 0.0, None, 18000.0, True)]
    frame = render_frame(fs, now=1.0, color=False)
    assert "idle" in frame.lower()


def test_render_frame_empty():
    assert isinstance(render_frame([], now=1.0, color=False), str)


def test_render_frame_no_color_clean():
    fs = [Forecast("5h", 12000, 220000, 130.0, 5000.0, 3600.0, False)]
    assert "\033" not in render_frame(fs, now=1.0, color=False)


def test_render_frame_color_on():
    fs = [Forecast("5h", 12000, 220000, 130.0, 5000.0, 3600.0, False)]
    assert "\033" in render_frame(fs, now=1.0, color=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dashboard.py -q`
Expected: FAIL — `render_frame()` takes no `color` kwarg (TypeError).

- [ ] **Step 3: Write minimal implementation**

Replace the entire contents of `oracle/dashboard/app.py` with:

```python
"""Stdlib TUI over the Forecast list. render_frame is pure (tested); run() is the
refresh loop."""
import os
import time

from ..core.engine import forecast as run_forecast
from ..core.timeutil import fmt_tokens, fmt_hms, fmt_dh_long
from ..cli import colors as c

BAR_W = 12


def _bar(pct, enabled, width=BAR_W):
    filled = max(0, min(width, int(round(pct / 100.0 * width))))
    return c.gauge("█" * filled + "░" * (width - filled), pct, enabled)


def render_frame(forecasts, now, color=None):
    enabled = c.color_enabled() if color is None else color
    lines = [c.violet(f"{c.M_ORACLE} token-oracle", enabled),
             c.dim("─" * 24, enabled)]
    if not forecasts:
        lines.append(c.dim("(no windows / no data)", enabled))
        return "\n".join(lines)
    for f in forecasts:
        if f.idle:
            lines.append(c.dim(
                f"  {c.M_BULLET} {f.window:<6} idle · resets {fmt_hms(f.reset_in_secs)}",
                enabled))
            continue
        pct = f.projected_pct
        lines.append(
            f"  {c.M_BULLET} {f.window:<6} {_bar(pct, enabled)}  "
            f"{c.gauge(f'{round(pct)}%', pct, enabled)}")
        meta = c.dim(
            f"         {fmt_tokens(f.used)}/{fmt_tokens(f.cap)} "
            f"· resets {fmt_hms(f.reset_in_secs)}", enabled)
        if f.eta_to_cap_secs is not None:
            meta += "  " + c.gauge(
                f"{c.M_WARN} cap in {fmt_dh_long(f.eta_to_cap_secs)}", pct, enabled)
        lines.append(meta)
    return "\n".join(lines)


def run(cfg, now):
    try:
        while True:
            os.system("clear")
            t = time.time()
            print(render_frame(run_forecast(t, cfg), t))
            print(c.dim("\n(ctrl-c to quit)", c.color_enabled()))
            time.sleep(2)
    except KeyboardInterrupt:
        return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_dashboard.py -q`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add oracle/dashboard/app.py tests/test_dashboard.py
git commit -m "feat(dash): colored block-bar TUI with violet header, dim metadata"
```

---

### Task 5: Polish doctor output

**Files:**
- Modify: `oracle/cli/main.py` (add `_doctor_lines`, rewrite the `doctor` branch, add colors import)
- Test: `tests/test_cli.py` (add a footer/badge test; keep the existing four)

**Interfaces:**
- Consumes: `oracle.cli.colors` (`color_enabled`, `violet`, `dim`, `ok_badge`, `M_ORACLE`), `oracle.core.config.default_config_path`, `oracle.sources.base.available`.
- Produces: `_doctor_lines(cfg, config_path, color) -> list[str]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`:

```python
def test_doctor_footer_and_badges(tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [], now)
    main(["doctor", "--config", cfg, "--now", str(now)])
    out = capsys.readouterr().out
    assert "oracle doctor" in out
    assert "ok ·" in out and "need attention" in out
    assert "✓" in out  # source + windows are valid here → at least one pass


def test_doctor_flags_bad_source(tmp_path, capsys):
    from oracle.cli.main import _doctor_lines
    from oracle.core.config import load_config
    cfg_path = _cfg(tmp_path, [], 100000.0)
    cfg = load_config(cfg_path)
    cfg.source = "nope-not-real"
    out = "\n".join(_doctor_lines(cfg, cfg_path, color=False))
    assert "✗" in out and "1 need attention" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -q`
Expected: FAIL — `cannot import name '_doctor_lines'` / footer strings absent.

- [ ] **Step 3: Write minimal implementation**

In `oracle/cli/main.py`, add the colors import near the other imports:

```python
from ..cli import colors as colors
```

Add this helper function above `def main(`:

```python
def _doctor_lines(cfg, config_path, color):
    from ..core.config import default_config_path
    from ..sources.base import available
    avail = available()
    rows = [
        ("config", config_path or default_config_path(), True),
        ("source", f"{cfg.source} (available: {', '.join(avail)})",
         cfg.source in avail),
        ("cache", cfg.cache_path, True),
        ("windows", f"{len(cfg.windows)} → {[w.name for w in cfg.windows]}",
         len(cfg.windows) > 0),
    ]
    out = [colors.violet(f"{colors.M_ORACLE} oracle doctor", color)]
    ok = 0
    for name, detail, good in rows:
        ok += 1 if good else 0
        out.append(f"  {colors.ok_badge(good, color)} {name:<8} — {detail}")
    bad = len(rows) - ok
    out.append(colors.dim(f"  {ok} ok · {bad} need attention", color))
    return out
```

Replace the entire `if args.cmd == "doctor":` block with:

```python
    if args.cmd == "doctor":
        for line in _doctor_lines(cfg, args.config, colors.color_enabled()):
            print(line)
        return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py -q`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add oracle/cli/main.py tests/test_cli.py
git commit -m "feat(doctor): badge rows with real checks + ok/attention footer"
```

---

### Task 6: README + docs presentation polish

**Files:**
- Modify: `README.md` (full rewrite below)

**Interfaces:** none (docs only).

- [ ] **Step 1: Rewrite README.md**

Replace the entire contents of `README.md` with:

```markdown
# 🔮 token-oracle

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)

**O**bserved-**R**ate **A**llowance **&** **C**ap-**L**imit **E**stimator — a
provider-agnostic engine that forecasts **when you'll hit a usage cap before its
reset**, learned from your own observed burn patterns. Companion to
[agentic-sage](https://github.com/muslewski/agentic-sage).

> The engine is the product. UIs — statusline, tmux, dashboard — are optional
> consumers of a neutral `Forecast`. Zero dependencies, stdlib only, Python 3.10+.

## Quickstart

```bash
pipx install token-oracle        # or: pip install token-oracle
oracle doctor                    # config + source + windows, with ✓/✗ checks
oracle forecast                  # human status line
oracle forecast --json           # the snapshot schema
oracle dash                      # live colored TUI
```

Works out of the box with Claude Code (`claude_code` source, selected by default).
Other providers feed in via the `generic` source or a custom adapter.

## Parts & options

| Part | What it does | Need it? |
|---|---|---|
| core engine | forecast math (burn profile + window math) | required |
| `claude_code` source | reads `~/.claude/projects/*/*.jsonl` | default source |
| `generic` source | feed your own `[[ts, tokens]]` JSON file | optional |
| `oracle` CLI | `forecast` / `snapshot` / `doctor` / statusline / tmux | required |
| TUI dashboard (`oracle dash`) | live colored forecast view, refreshes ~2 s | optional |
| statusline adapter | ANSI status-line reference renderer | optional |
| tmux adapter | tmux-formatted line reference renderer | optional |
| snapshot (`forecast.json`) | stable JSON contract for external consumers | optional |

See [SETUP.md](SETUP.md) for full configuration reference.
See [ADAPTERS.md](ADAPTERS.md) for the source and consumer interfaces.
See [AGENTS.md](AGENTS.md) for a deterministic coding-agent runbook.

## CLI reference

| Command | Description |
|---|---|
| `oracle forecast` | Human status line |
| `oracle forecast --json` | Print the full snapshot JSON |
| `oracle snapshot [--out PATH]` | Write `forecast.json`, print path |
| `oracle statusline` | ANSI status line (reference adapter) |
| `oracle tmux` | tmux-formatted line (reference adapter) |
| `oracle doctor` | Config, source, cache, windows — with ✓/✗ checks |
| `oracle dash` | Live colored TUI dashboard (refreshes ~2 s) |

Every subcommand accepts `--config PATH` to override the default config location.

## Colors

Output is colored by **severity** (the gauge gradient: green → lime → orange → red
as projected usage rises) with a violet accent for headers. Color is applied only at
output, so piped output stays clean.

- `NO_COLOR=1` disables color everywhere.
- `FORCE_COLOR=1` forces color on non-TTY interactive output.

## Works with agentic-sage

Oracle writes a stable `forecast.json`; [agentic-sage](https://github.com/muslewski/agentic-sage)
can optionally surface it via its `tokenForecastPath` config key. Each tool works
fully standalone — token prediction is an *optional* input to session awareness.
See [SETUP.md § Optional integrations](SETUP.md#optional-integrations) for the
one-line wiring step.

## License

MIT — Copyright (c) Kento.
```

- [ ] **Step 2: Verify no broken internal references**

Run: `python -m pytest -q`
Expected: PASS (full suite green — docs change touches no code).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: polished README (badges, acronym tagline, colors section)"
```

---

## Final verification

After all tasks:

```bash
python -m pytest -q          # expect all green (was 56, +~15 new)
oracle forecast --json | python -m json.tool >/dev/null  # snapshot still valid
NO_COLOR=1 oracle doctor     # confirm no escapes when NO_COLOR set
```
