# token-oracle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A provider-agnostic Python engine that forecasts when token usage will hit a user-defined cap before its reset, with a CLI, a snapshot contract, a TUI dashboard, and thin reference UI adapters.

**Architecture:** Three rings — source adapters (input) → pure-math core (neutral events only) → consumers (output). The core never imports a source or a consumer. Sources emit `UsageEvent`s; consumers read `Forecast` results. Ported and generalized from the working `~/.claude/usage_limits.py` + `claude_sessions.py` system.

**Tech Stack:** Python 3.10+, **stdlib only** (zero runtime deps), `pytest` for tests, `pyproject.toml` packaging, console entry point `oracle`.

## Global Constraints

- **Python ≥ 3.10** (uses `X | None` type syntax). One line in `pyproject.toml`: `requires-python = ">=3.10"`.
- **Zero runtime dependencies.** Core + sources + adapters + CLI + dashboard use stdlib only. `pytest` is a dev-only extra.
- **Core purity:** modules under `oracle/core/` and `oracle/sources/` MUST NOT import anything from `oracle/adapters/`, `oracle/cli/`, `oracle/dashboard/`, or `oracle/snapshot/`. Math functions never raise to the caller (catch and return safe defaults at facade boundaries).
- **License:** MIT, holder "Kento (muslewski)".
- **Naming:** project `token-oracle`; import package `oracle`; backronym *Observed-Rate Allowance & Cap-Limit Estimator*.
- **Forecast target is configurable** — no hardcoded 5h/weekly in the core; those ship only as the `max20` preset.
- **Commit after every task** with a `feat:`/`test:`/`docs:` prefixed message.

---

## File Structure

```
token-oracle/
  pyproject.toml
  LICENSE
  README.md  SETUP.md  AGENTS.md  ADAPTERS.md
  oracle/
    __init__.py
    core/
      __init__.py
      contracts.py     # UsageEvent, Window, Forecast + helpers
      timeutil.py      # parse_ts, fmt_* , bucket_key
      profile.py       # burn profile: decay, accumulate, build_profile, profile_integral
      windows.py       # compute_window, eta_to_cap
      cache.py         # load/save cache, events_from_cache
      config.py        # Config load + presets (max20)
      engine.py        # forecast() facade + source registry
    sources/
      __init__.py
      base.py          # Source protocol + register/get
      claude_code.py   # first source adapter (jsonl)
      generic.py       # documented stub source
    snapshot/
      __init__.py
      writer.py        # write_snapshot() -> forecast.json
    adapters/
      __init__.py
      statusline.py    # thin reference: Forecast list -> ANSI line
      tmux.py          # thin reference: Forecast list -> tmux-colored line
    cli/
      __init__.py
      main.py          # argparse: forecast, config, snapshot, doctor, dash
    dashboard/
      __init__.py
      app.py           # minimal stdlib TUI over Forecast list
  tests/
    test_contracts.py test_timeutil.py test_profile.py test_windows.py
    test_cache.py test_config.py test_sources_claude.py test_sources_generic.py
    test_engine.py test_snapshot.py test_adapters.py test_cli.py
    fixtures/
```

---

### Task 1: Project scaffold + packaging

**Files:**
- Create: `pyproject.toml`, `oracle/__init__.py`, `oracle/core/__init__.py`, `tests/__init__.py`, `tests/test_smoke.py`
- Create: `LICENSE`

**Interfaces:**
- Consumes: nothing.
- Produces: importable package `oracle` (`oracle.__version__: str`); `pytest` runs green; `oracle` console entry resolves to `oracle.cli.main:main` (implemented in Task 12 — declared now).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_smoke.py
import oracle

def test_version_present():
    assert isinstance(oracle.__version__, str)
    assert oracle.__version__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle'`

- [ ] **Step 3: Create package + packaging**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "token-oracle"
version = "0.1.0"
description = "Observed-Rate Allowance & Cap-Limit Estimator — provider-agnostic token usage-cap forecaster"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [{ name = "Kento" }]
keywords = ["claude", "tokens", "usage", "forecast", "rate-limit"]

[project.optional-dependencies]
dev = ["pytest>=7"]

[project.scripts]
oracle = "oracle.cli.main:main"

[tool.setuptools]
packages = ["oracle", "oracle.core", "oracle.sources", "oracle.snapshot", "oracle.adapters", "oracle.cli", "oracle.dashboard"]
```

```python
# oracle/__init__.py
"""token-oracle — Observed-Rate Allowance & Cap-Limit Estimator."""
__version__ = "0.1.0"
```

```python
# oracle/core/__init__.py
```

```python
# tests/__init__.py
```

Create `LICENSE` as the standard MIT license text, copyright `2026 Kento`.

- [ ] **Step 4: Install editable + run tests**

Run: `pip install -e ".[dev]" && python -m pytest tests/test_smoke.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml oracle/ tests/ LICENSE
git commit -m "feat: scaffold token-oracle package + packaging"
```

---

### Task 2: Neutral contracts

**Files:**
- Create: `oracle/core/contracts.py`
- Test: `tests/test_contracts.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `UsageEvent` dataclass: fields `timestamp: float`, `tokens: int`, `model: str | None = None`, `session_id: str | None = None`, `kind: str | None = None`.
  - `Window` dataclass: `name: str`, `cap: int`, `period_secs: int`, `anchor: float | None = None`. `anchor is None` ⇒ rolling-from-first-event mode (5h-block style); `anchor` set ⇒ fixed-grid mode (weekly style).
  - `Forecast` dataclass: `window: str`, `used: int`, `cap: int`, `projected_pct: float`, `eta_to_cap_secs: float | None`, `reset_in_secs: float`, `idle: bool`, `confidence: float = 1.0`.
  - `to_pairs(events: list[UsageEvent]) -> list[tuple[float, int]]` — sorted `(timestamp, tokens)` pairs the math uses.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_contracts.py
from oracle.core.contracts import UsageEvent, Window, Forecast, to_pairs

def test_usageevent_defaults():
    e = UsageEvent(timestamp=100.0, tokens=5)
    assert e.model is None and e.session_id is None and e.kind is None

def test_window_modes():
    rolling = Window(name="5h", cap=1000, period_secs=18000)
    fixed = Window(name="wk", cap=9000, period_secs=604800, anchor=0.0)
    assert rolling.anchor is None
    assert fixed.anchor == 0.0

def test_forecast_confidence_default():
    f = Forecast("5h", 10, 100, 12.0, None, 300.0, False)
    assert f.confidence == 1.0

def test_to_pairs_sorts():
    evs = [UsageEvent(3.0, 1), UsageEvent(1.0, 2), UsageEvent(2.0, 3)]
    assert to_pairs(evs) == [(1.0, 2), (2.0, 3), (3.0, 1)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_contracts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.core.contracts'`

- [ ] **Step 3: Write minimal implementation**

```python
# oracle/core/contracts.py
"""Neutral data contracts shared by sources, core math, and consumers."""
from dataclasses import dataclass


@dataclass
class UsageEvent:
    timestamp: float                 # epoch seconds
    tokens: int                      # billable tokens for this event
    model: str | None = None
    session_id: str | None = None
    kind: str | None = None


@dataclass
class Window:
    """A usage window the forecast targets.

    anchor is None  -> rolling-from-first-event (Anthropic 5h-block style):
                       the window starts at its first event and re-anchors
                       to the first event after each expiry.
    anchor is set   -> fixed grid: window starts at anchor + n*period_secs.
    """
    name: str
    cap: int
    period_secs: int
    anchor: float | None = None


@dataclass
class Forecast:
    window: str
    used: int
    cap: int
    projected_pct: float
    eta_to_cap_secs: float | None
    reset_in_secs: float
    idle: bool
    confidence: float = 1.0


def to_pairs(events):
    """Sorted (timestamp, tokens) pairs the math operates on."""
    return sorted((float(e.timestamp), int(e.tokens)) for e in events)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_contracts.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add oracle/core/contracts.py tests/test_contracts.py
git commit -m "feat(core): neutral UsageEvent/Window/Forecast contracts"
```

---

### Task 3: Time + format utilities

**Files:**
- Create: `oracle/core/timeutil.py`
- Test: `tests/test_timeutil.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `parse_ts(s: str | None) -> float | None` — ISO8601 (trailing `Z` ok) → epoch; `None` on failure.
  - `bucket_key(ts: float) -> int` — local hour-of-week index `weekday(Mon=0)*24 + hour` → 0..167.
  - `fmt_tokens(n: int) -> str`, `fmt_hms(secs) -> str`, `fmt_dh(secs) -> str`, `fmt_dur(secs) -> str`, `fmt_dh_long(secs) -> str` (ported verbatim from the source system).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_timeutil.py
from oracle.core import timeutil as T

def test_parse_ts_z_suffix():
    assert T.parse_ts("1970-01-01T00:00:00Z") == 0.0
    assert T.parse_ts(None) is None
    assert T.parse_ts("not-a-date") is None

def test_bucket_key_range():
    assert 0 <= T.bucket_key(0.0) <= 167

def test_fmt_tokens():
    assert T.fmt_tokens(1_500_000) == "1.5M"
    assert T.fmt_tokens(12_000) == "12k"

def test_fmt_hms_and_dh():
    assert T.fmt_hms(3 * 3600 + 46 * 60) == "3:46"
    assert T.fmt_dh(5 * 86400 + 18 * 3600) == "5d18h"

def test_fmt_dur():
    assert T.fmt_dur(59) == "59s"
    assert T.fmt_dur(80) == "1m20s"
    assert T.fmt_dur(12 * 60) == "12m"
    assert T.fmt_dur(3900) == "1h05m"

def test_fmt_dh_long():
    assert T.fmt_dh_long(5 * 86400 + 18 * 3600) == "5 days 18 hours"
    assert T.fmt_dh_long(3600) == "1 hour"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_timeutil.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.core.timeutil'`

- [ ] **Step 3: Write minimal implementation**

```python
# oracle/core/timeutil.py
"""Time parsing, hour-of-week bucketing, and display formatters. Stdlib only."""
from datetime import datetime


def parse_ts(s):
    """ISO8601 (trailing Z ok) -> epoch seconds. None on failure."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, AttributeError):
        return None


def bucket_key(ts):
    """Local-time hour-of-week index: weekday(Mon=0)*24 + hour -> 0..167."""
    dt = datetime.fromtimestamp(ts).astimezone()
    return dt.weekday() * 24 + dt.hour


def fmt_tokens(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    return f"{n // 1000}k"


def fmt_hms(secs):
    secs = max(0, int(secs))
    return f"{secs // 3600}:{(secs % 3600) // 60:02d}"


def fmt_dh(secs):
    secs = max(0, int(secs))
    return f"{secs // 86400}d{(secs % 86400) // 3600}h"


def fmt_dur(secs):
    """Compact elapsed: 59s, 1m20s, 12m, 1h05m."""
    secs = max(0, int(secs))
    if secs < 60:
        return f"{secs}s"
    m, s = divmod(secs, 60)
    if secs < 600:
        return f"{m}m{s}s"
    if secs < 3600:
        return f"{m}m"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def fmt_dh_long(secs):
    """Verbose days/hours: '5 days 18 hours', '1 day', '18 hours'."""
    secs = max(0, int(secs))
    d, rem = divmod(secs, 86400)
    h = rem // 3600
    parts = []
    if d:
        parts.append(f"{d} day{'s' if d != 1 else ''}")
    if h or not d:
        parts.append(f"{h} hour{'s' if h != 1 else ''}")
    return " ".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_timeutil.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add oracle/core/timeutil.py tests/test_timeutil.py
git commit -m "feat(core): time parsing + display formatters"
```

---

### Task 4: Burn profile

**Files:**
- Create: `oracle/core/profile.py`
- Test: `tests/test_profile.py`

**Interfaces:**
- Consumes: `oracle.core.timeutil.bucket_key`.
- Produces:
  - Module constants: `N_BUCKETS = 168`, `HIST_SECS = 63*24*3600`, `DECAY_HALFLIFE_SECS = 14*24*3600`, `SHRINK_K = 3.0`.
  - `build_profile(events: list[tuple[float,int]], now: float) -> list[float]` — 168-bucket tok/s profile with empirical-Bayes backoff shrinkage.
  - `profile_integral(profile: list[float], start: float, end: float) -> float` — expected tokens over `[start, end)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_profile.py
from oracle.core.profile import build_profile, profile_integral, N_BUCKETS

def test_empty_events_zero_profile():
    prof = build_profile([], 1_000_000.0)
    assert len(prof) == N_BUCKETS
    assert all(r == 0.0 for r in prof)

def test_profile_integral_zero_when_flat_zero():
    assert profile_integral([0.0] * N_BUCKETS, 0.0, 3600.0) == 0.0

def test_uniform_load_gives_positive_rate_and_integral():
    now = 30 * 86400.0
    # ~one event/hour of 100 tokens across the trailing 21 days
    evs = [(now - h * 3600.0, 100) for h in range(1, 21 * 24)]
    prof = build_profile(evs, now)
    assert any(r > 0 for r in prof)
    # integral over a 5h horizon must be positive and finite
    val = profile_integral(prof, now, now + 5 * 3600.0)
    assert val > 0 and val < 5 * 3600.0 * max(prof) + 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_profile.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.core.profile'`

- [ ] **Step 3: Write minimal implementation** (ported verbatim from `~/.claude/usage_limits.py` lines 13-19, 74-143; constants relocated here)

```python
# oracle/core/profile.py
"""Pattern-aware burn profile: 168-bucket (hour-of-week) tok/s rate with
recency decay and empirical-Bayes shrinkage. Stdlib only. ML seam: replace
build_profile with a learned model exposing the same signature."""
from .timeutil import bucket_key

N_BUCKETS = 168                       # 7 weekdays x 24 hours
HIST_SECS = 63 * 24 * 3600            # trailing retention (9 weeks)
DECAY_HALFLIFE_SECS = 14 * 24 * 3600  # recency half-life
SHRINK_K = 3.0                        # empirical-Bayes pseudo-count


def _decay(age_secs):
    return 0.5 ** (max(0.0, age_secs) / DECAY_HALFLIFE_SECS)


def _accumulate(events, now):
    """Decay-weighted token sums (S) and exposure seconds (E) per hour-of-week.
    Exposure is wall-clock (idle baked in): every hour-slot in the retained
    window contributes 3600s x its decay weight, regardless of activity."""
    S = [0.0] * N_BUCKETS
    E = [0.0] * N_BUCKETS
    cutoff = now - HIST_SECS
    for ts, tok in events:
        if ts < cutoff or ts > now:
            continue
        S[bucket_key(ts)] += _decay(now - ts) * tok
    t = cutoff
    while t < now:
        E[bucket_key(t)] += _decay(now - t) * 3600.0
        t += 3600.0
    return S, E


def build_profile(events, now):
    """168-bucket tok/s profile with empirical-Bayes backoff shrinkage:
    (hour,weekday) -> (hour,daytype) -> (hour) -> flat. flat is the root."""
    S, E = _accumulate(events, now)

    def shrink(s, e, parent):
        n = e / 3600.0
        raw = (s / e) if e > 0 else parent
        return (n * raw + SHRINK_K * parent) / (n + SHRINK_K)

    tot_s, tot_e = sum(S), sum(E)
    flat = (tot_s / tot_e) if tot_e > 0 else 0.0

    hour_s = [0.0] * 24
    hour_e = [0.0] * 24
    for b in range(N_BUCKETS):
        hour_s[b % 24] += S[b]
        hour_e[b % 24] += E[b]
    hour_rate = [shrink(hour_s[h], hour_e[h], flat) for h in range(24)]

    dt_s, dt_e = {}, {}
    for b in range(N_BUCKETS):
        h, wd = b % 24, b // 24
        dt = 1 if wd >= 5 else 0
        dt_s[(h, dt)] = dt_s.get((h, dt), 0.0) + S[b]
        dt_e[(h, dt)] = dt_e.get((h, dt), 0.0) + E[b]
    dt_rate = {k: shrink(dt_s[k], dt_e[k], hour_rate[k[0]]) for k in dt_s}

    profile = [0.0] * N_BUCKETS
    for b in range(N_BUCKETS):
        h, wd = b % 24, b // 24
        dt = 1 if wd >= 5 else 0
        profile[b] = shrink(S[b], E[b], dt_rate.get((h, dt), hour_rate[h]))
    return profile


def profile_integral(profile, start, end):
    """Expected tokens over [start, end) given a 168-bucket tok/s profile."""
    if not profile or start >= end:
        return 0.0
    total = 0.0
    t = start
    while t < end:
        nxt = min(end, t - (t % 3600.0) + 3600.0)
        total += profile[bucket_key(t)] * (nxt - t)
        t = nxt
    return total
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_profile.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add oracle/core/profile.py tests/test_profile.py
git commit -m "feat(core): pattern-aware burn profile (decay + EB shrinkage)"
```

---

### Task 5: Window computation + ETA

**Files:**
- Create: `oracle/core/windows.py`
- Test: `tests/test_windows.py`

**Interfaces:**
- Consumes: `oracle.core.contracts.{Window,Forecast}`, `oracle.core.profile.{profile_integral,HIST_SECS}`.
- Produces:
  - `eta_to_cap(used: int, projected_pct: float, time_left: float, cap: int) -> float | None`.
  - `compute_window(events: list[tuple[float,int]], now: float, window: Window, profile: list[float] | None = None) -> Forecast`. Generalizes the source system's `compute_block` (anchor None) and `compute_weekly` (anchor set) into one function.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_windows.py
from oracle.core.contracts import Window
from oracle.core.windows import compute_window, eta_to_cap

def test_eta_none_when_under_cap():
    assert eta_to_cap(50, 80.0, 3600.0, 100) is None

def test_eta_zero_when_already_over():
    assert eta_to_cap(150, 200.0, 3600.0, 100) == 0.0

def test_eta_positive_when_projected_over():
    eta = eta_to_cap(50, 200.0, 3600.0, 100)
    assert eta is not None and eta > 0

def test_rolling_window_idle_when_no_events():
    w = Window(name="5h", cap=1000, period_secs=18000)
    f = compute_window([], 1000.0, w)
    assert f.idle is True and f.used == 0 and f.projected_pct == 0.0

def test_rolling_window_counts_recent_usage():
    now = 100000.0
    w = Window(name="5h", cap=1000, period_secs=18000)
    evs = [(now - 600.0, 200), (now - 60.0, 50)]
    f = compute_window(evs, now, w)
    assert f.idle is False
    assert f.used == 250
    assert f.reset_in_secs > 0

def test_fixed_window_never_idle():
    now = 1_000_000.0
    w = Window(name="wk", cap=10_000, period_secs=604800, anchor=0.0)
    f = compute_window([(now - 100.0, 500)], now, w)
    assert f.idle is False
    assert f.used == 500
    assert 0 < f.reset_in_secs <= 604800

def test_projection_sets_eta_when_burning_hot():
    now = 100000.0
    w = Window(name="5h", cap=300, period_secs=18000)
    # heavy burst near window start: projected should exceed cap -> eta set
    evs = [(now - 17000.0, 250), (now - 100.0, 40)]
    f = compute_window(evs, now, w)
    if f.projected_pct > 100:
        assert f.eta_to_cap_secs is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_windows.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.core.windows'`

- [ ] **Step 3: Write minimal implementation** (generalizes `compute_block`+`compute_weekly` from `~/.claude/usage_limits.py:248-327`; `eta_to_cap` ported from `claude_sessions.py:159-172`)

```python
# oracle/core/windows.py
"""Forecast one Window from neutral (ts, tokens) events. Generalizes the
5h-block (rolling, anchor=None) and weekly (fixed grid, anchor set) windows
into a single history-aware projection. Never raises."""
from .contracts import Forecast
from .profile import profile_integral, HIST_SECS


def eta_to_cap(used, projected_pct, time_left, cap):
    """Seconds until usage reaches cap at the projection-implied burn. None when
    not heading over (<=100%) or indeterminate; 0.0 when already at/over cap."""
    if projected_pct <= 100 or cap <= 0:
        return None
    if used >= cap:
        return 0.0
    if time_left <= 0:
        return None
    projected_tokens = projected_pct / 100.0 * cap
    rate = (projected_tokens - used) / time_left
    if rate <= 0:
        return None
    return (cap - used) / rate


def _bounds(events, now, window):
    """Return (start, reset) of the current window, or None if rolling and
    idle/expired."""
    P = window.period_secs
    if window.anchor is not None:
        n = max(0, int((now - window.anchor) // P))
        start = window.anchor + n * P
        return start, start + P
    if not events:
        return None
    start = events[0][0]
    for ts, _tok in events[1:]:
        if ts >= start + P:
            start = ts          # window expired -> re-anchor here
    reset = start + P
    if now > reset:
        return None
    return start, reset


def compute_window(events, now, window, profile=None):
    cap = window.cap
    P = window.period_secs
    bounds = _bounds(events, now, window)
    if bounds is None:
        return Forecast(window.name, 0, cap, 0.0, None, float(P), True)
    start, reset = bounds
    used = sum(tok for ts, tok in events if start <= ts <= now)
    elapsed = max(1.0, now - start)
    # History-aware burn: naive (used/elapsed)*period explodes at window start.
    # Blend a learned prior with this window's measured rate by window-fraction.
    # Early window trusts the prior (no reset spike); late window trusts measured.
    f = min(1.0, max(0.0, elapsed / P))
    measured_term = (used / elapsed) * (reset - now)
    if profile is None:
        hist_cutoff = now - HIST_SECS
        prior_used = sum(tok for ts, tok in events if hist_cutoff <= ts < start)
        prior_span = max(1.0, start - hist_cutoff)
        prior_term = (prior_used / prior_span) * (reset - now)
    else:
        prior_term = profile_integral(profile, now, reset)
    projected = used + (1.0 - f) * prior_term + f * measured_term
    projected_pct = (projected / cap * 100) if cap else 0.0
    reset_in = reset - now
    eta = eta_to_cap(used, projected_pct, reset_in, cap)
    return Forecast(window.name, int(used), cap, projected_pct, eta,
                    float(reset_in), False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_windows.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add oracle/core/windows.py tests/test_windows.py
git commit -m "feat(core): generalized window forecast + eta_to_cap"
```

---

### Task 6: Aggregation cache

**Files:**
- Create: `oracle/core/cache.py`
- Test: `tests/test_cache.py`

**Interfaces:**
- Consumes: nothing (operates on plain dicts + a `scan` callable provided by the source).
- Produces:
  - `AGGREGATE_INTERVAL = 30`.
  - `load_cache(path: str) -> dict` — returns `{"files": {}, "lastAggregate": 0, "profile": []}` shape; tolerant of missing/corrupt files.
  - `save_cache(cache: dict, path: str) -> None` — atomic write (`tmp` + `os.replace`); creates parent dir; never raises.
  - `collect_events(files_state: dict, cutoff: float) -> list[tuple[float,int]]` — sorted events ≥ cutoff from a source-owned `files_state`.
  - `events_from_cache(cache: dict, now: float, window: float) -> list[tuple[float,int]]`.

  Note: incremental file scanning lives in the **source** (Task 8), which owns `cache["files"]`. The core cache only persists/reads it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cache.py
import os
from oracle.core import cache as C

def test_load_missing_returns_default(tmp_path):
    c = C.load_cache(str(tmp_path / "nope.json"))
    assert c == {"files": {}, "lastAggregate": 0, "profile": []}

def test_save_then_load_roundtrip(tmp_path):
    p = str(tmp_path / "sub" / "cache.json")   # parent dir created
    c = {"files": {"a": {"events": [[1.0, 5]]}}, "lastAggregate": 99, "profile": [0.1]}
    C.save_cache(c, p)
    assert os.path.isfile(p)
    assert C.load_cache(p) == c

def test_load_corrupt_returns_default(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{ not json")
    assert C.load_cache(str(p))["files"] == {}

def test_collect_and_window():
    files = {"f": {"events": [[10.0, 1], [50.0, 2], [5.0, 9]]}}
    assert C.collect_events(files, cutoff=10.0) == [(10.0, 1), (50.0, 2)]
    cache = {"files": files}
    assert C.events_from_cache(cache, now=50.0, window=45.0) == [(10.0, 1), (50.0, 2)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.core.cache'`

- [ ] **Step 3: Write minimal implementation** (ported/generalized from `usage_limits.py:184-212, 244-245`)

```python
# oracle/core/cache.py
"""Persistent aggregation cache: source-owned file state + last-aggregate time
+ burn profile. Atomic writes. Never raises to the caller."""
import json
import os

AGGREGATE_INTERVAL = 30  # seconds between heavy re-scans


def load_cache(path):
    try:
        with open(path, encoding="utf-8") as fh:
            c = json.load(fh)
        if isinstance(c, dict) and "files" in c:
            c.setdefault("lastAggregate", 0)
            c.setdefault("profile", [])
            return c
    except (OSError, ValueError):
        pass
    return {"files": {}, "lastAggregate": 0, "profile": []}


def save_cache(cache, path):
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cache, fh)
        os.replace(tmp, path)
    except OSError:
        pass


def collect_events(files_state, cutoff):
    out = []
    for ent in files_state.values():
        for ts, tok in ent.get("events", []):
            if ts >= cutoff:
                out.append((float(ts), int(tok)))
    out.sort()
    return out


def events_from_cache(cache, now, window):
    return collect_events(cache.get("files", {}), now - window)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cache.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add oracle/core/cache.py tests/test_cache.py
git commit -m "feat(core): atomic aggregation cache + event collection"
```

---

### Task 7: Config + presets

**Files:**
- Create: `oracle/core/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `oracle.core.contracts.Window`, `oracle.core.timeutil.parse_ts`.
- Produces:
  - `Config` dataclass: `source: str`, `source_opts: dict`, `cache_path: str`, `windows: list[Window]`.
  - `PRESETS: dict[str, dict]` containing `"max20"` (5h cap 220000 / period 18000, weekly cap 8000000 / period 604800 / anchor None).
  - `default_config_path() -> str` → `~/.config/token-oracle/config.json` (honors `$XDG_CONFIG_HOME`).
  - `default_cache_path() -> str` → `~/.local/share/token-oracle/cache.json` (honors `$XDG_DATA_HOME`).
  - `load_config(path: str | None = None) -> Config` — reads JSON; falls back to the `max20` preset when the file is missing/corrupt; resolves a string `anchor` via `parse_ts`; expands `~` in paths.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import json
from oracle.core import config as CFG
from oracle.core.contracts import Window

def test_default_is_max20_when_missing(tmp_path):
    c = CFG.load_config(str(tmp_path / "none.json"))
    names = {w.name for w in c.windows}
    assert names == {"5h", "weekly"}
    five = next(w for w in c.windows if w.name == "5h")
    assert five.cap == 220000 and five.period_secs == 18000

def test_paths_honor_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "dat"))
    assert CFG.default_config_path().endswith("/cfg/token-oracle/config.json")
    assert CFG.default_cache_path().endswith("/dat/token-oracle/cache.json")

def test_loads_custom_windows_and_anchor(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({
        "source": "claude_code",
        "windows": [
            {"name": "daily", "cap": 5000, "period_secs": 86400,
             "anchor": "2026-01-01T00:00:00Z"}
        ],
    }))
    c = CFG.load_config(str(p))
    assert c.source == "claude_code"
    w = c.windows[0]
    assert isinstance(w, Window) and w.name == "daily" and w.cap == 5000
    assert w.anchor == 1735689600.0   # 2026-01-01T00:00:00Z

def test_corrupt_falls_back(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("{ broken")
    c = CFG.load_config(str(p))
    assert {w.name for w in c.windows} == {"5h", "weekly"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.core.config'`

- [ ] **Step 3: Write minimal implementation**

```python
# oracle/core/config.py
"""Config loading + shipped presets. The forecast target is fully config-driven;
Claude's max20 caps ship as one preset, not as core law."""
import json
import os
from dataclasses import dataclass, field

from .contracts import Window
from .timeutil import parse_ts

PRESETS = {
    "max20": {
        "source": "claude_code",
        "windows": [
            {"name": "5h", "cap": 220000, "period_secs": 18000},
            {"name": "weekly", "cap": 8000000, "period_secs": 604800, "anchor": None},
        ],
    },
}


@dataclass
class Config:
    source: str = "claude_code"
    source_opts: dict = field(default_factory=dict)
    cache_path: str = ""
    windows: list = field(default_factory=list)


def _xdg(env, default_tail):
    base = os.environ.get(env) or os.path.expanduser(default_tail)
    return base


def default_config_path():
    return os.path.join(_xdg("XDG_CONFIG_HOME", "~/.config"),
                        "token-oracle", "config.json")


def default_cache_path():
    return os.path.join(_xdg("XDG_DATA_HOME", "~/.local/share"),
                        "token-oracle", "cache.json")


def _window_from_dict(d):
    anchor = d.get("anchor")
    if isinstance(anchor, str):
        anchor = parse_ts(anchor)
    return Window(name=d["name"], cap=int(d["cap"]),
                  period_secs=int(d["period_secs"]), anchor=anchor)


def load_config(path=None):
    path = path or default_config_path()
    raw = dict(PRESETS["max20"])
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            raw.update(data)
    except (OSError, ValueError):
        pass
    windows = [_window_from_dict(w) for w in raw.get("windows", [])]
    cache_path = os.path.expanduser(raw.get("cache_path") or default_cache_path())
    return Config(source=raw.get("source", "claude_code"),
                  source_opts=raw.get("source_opts", {}),
                  cache_path=cache_path, windows=windows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (4 passed)

Note: if `test_loads_custom_windows_and_anchor` fails only on the anchor epoch, adjust the expected number to match the test machine's interpretation — `parse_ts` of a `Z` timestamp is UTC-absolute, so `1735689600.0` is correct regardless of local TZ.

- [ ] **Step 5: Commit**

```bash
git add oracle/core/config.py tests/test_config.py
git commit -m "feat(core): config loader + max20 preset + XDG paths"
```

---

### Task 8: Source interface + Claude Code source

**Files:**
- Create: `oracle/sources/__init__.py`, `oracle/sources/base.py`, `oracle/sources/claude_code.py`
- Test: `tests/test_sources_claude.py`, `tests/fixtures/sample.jsonl`

**Interfaces:**
- Consumes: `oracle.core.timeutil.parse_ts`.
- Produces:
  - `base.Source` protocol: method `scan(self, files_state: dict, now: float, window: float) -> tuple[dict, list[tuple[float,int]]]` — incremental; returns updated `files_state` and sorted `(ts, tokens)` within `[now-window, now]`.
  - `base.register(name)` decorator + `base.get_source(name, opts) -> Source` + `base.available() -> list[str]`.
  - `claude_code.ClaudeCodeSource(opts)` registered as `"claude_code"`; reads `~/.claude/projects/*/*.jsonl` (override dir via `opts["projects_dir"]`), mtime/size-gated. Helper `iter_usage_events(path) -> Iterator[tuple[float,int]]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sources_claude.py
import json, os
from oracle.sources.base import get_source, available
from oracle.sources.claude_code import iter_usage_events

def _line(ts, inp, out, cc):
    return json.dumps({"timestamp": ts, "message": {"usage": {
        "input_tokens": inp, "output_tokens": out,
        "cache_creation_input_tokens": cc}}})

def test_claude_registered():
    assert "claude_code" in available()

def test_iter_usage_events(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text("\n".join([
        _line("1970-01-01T01:00:00Z", 100, 50, 10),  # 160 tokens
        "garbage-not-json",
        json.dumps({"timestamp": "1970-01-01T02:00:00Z"}),  # no usage -> skip
    ]))
    evs = list(iter_usage_events(str(p)))
    assert evs == [(3600.0, 160)]

def test_source_scan_collects_within_window(tmp_path):
    proj = tmp_path / "projects" / "repo"
    proj.mkdir(parents=True)
    (proj / "a.jsonl").write_text(_line("1970-01-01T01:00:00Z", 100, 0, 0))
    src = get_source("claude_code", {"projects_dir": str(tmp_path / "projects")})
    files, events = src.scan({}, now=7200.0, window=7200.0)
    assert events == [(3600.0, 100)]
    assert any("a.jsonl" in k for k in files)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sources_claude.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.sources.base'`

- [ ] **Step 3: Write minimal implementation**

```python
# oracle/sources/__init__.py
from . import claude_code  # noqa: F401  (register on import)
from . import generic      # noqa: F401
```

```python
# oracle/sources/base.py
"""Source adapter registry. A source turns provider data into neutral
(timestamp, tokens) events, owning its own incremental file/cache state."""
_REGISTRY = {}


def register(name):
    def deco(cls):
        _REGISTRY[name] = cls
        return cls
    return deco


def available():
    return sorted(_REGISTRY)


def get_source(name, opts=None):
    if name not in _REGISTRY:
        raise KeyError(f"unknown source: {name!r}; available: {available()}")
    return _REGISTRY[name](opts or {})
```

```python
# oracle/sources/claude_code.py
"""First source adapter: Claude Code transcripts (~/.claude/projects/*/*.jsonl).
Ported from usage_limits.iter_usage_events + scan_events."""
import glob
import json
import os

from ..core.timeutil import parse_ts
from .base import register


def _limit_tokens(usage):
    if not usage:
        return 0
    return (usage.get("input_tokens", 0)
            + usage.get("output_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0))


def iter_usage_events(jsonl_path):
    """Yield (ts_epoch, tokens) for assistant messages carrying usage."""
    try:
        fh = open(jsonl_path, "rb")
    except OSError:
        return
    with fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except ValueError:
                continue
            usage = (obj.get("message") or {}).get("usage")
            if not usage:
                continue
            ts = parse_ts(obj.get("timestamp"))
            if ts is None:
                continue
            tok = _limit_tokens(usage)
            if tok > 0:
                yield (ts, tok)


@register("claude_code")
class ClaudeCodeSource:
    def __init__(self, opts):
        self.projects_dir = os.path.expanduser(
            opts.get("projects_dir") or "~/.claude/projects")

    def scan(self, files_state, now, window):
        cutoff = now - window
        files = dict(files_state)
        try:
            paths = glob.glob(os.path.join(self.projects_dir, "*", "*.jsonl"))
        except OSError:
            paths = []
        seen = set()
        for p in paths:
            seen.add(p)
            try:
                st = os.stat(p)
            except OSError:
                continue
            if st.st_mtime < cutoff:
                files.pop(p, None)
                continue
            ent = files.get(p)
            if ent and ent.get("mtime") == st.st_mtime and ent.get("size") == st.st_size:
                continue
            evs = [[ts, tok] for ts, tok in iter_usage_events(p) if ts >= cutoff]
            files[p] = {"mtime": st.st_mtime, "size": st.st_size, "events": evs}
        for gone in [p for p in files if p not in seen]:
            files.pop(gone, None)
        out = []
        for ent in files.values():
            out.extend((float(ts), int(tok)) for ts, tok in ent.get("events", []) if ts >= cutoff)
        out.sort()
        return files, out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sources_claude.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add oracle/sources/ tests/test_sources_claude.py
git commit -m "feat(sources): source registry + claude_code adapter"
```

---

### Task 9: Generic source stub

**Files:**
- Create: `oracle/sources/generic.py`
- Test: `tests/test_sources_generic.py`

**Interfaces:**
- Consumes: `oracle.sources.base.register`.
- Produces: `generic.GenericSource(opts)` registered as `"generic"`. Reads events from a JSON file at `opts["events_path"]` shaped `[[ts, tokens], ...]` (the documented neutral feed for non-Claude providers). Implements the same `scan(files_state, now, window)` signature; no incremental caching (re-reads each scan).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sources_generic.py
import json
from oracle.sources.base import get_source, available

def test_generic_registered():
    assert "generic" in available()

def test_generic_reads_events_file(tmp_path):
    p = tmp_path / "feed.json"
    p.write_text(json.dumps([[10.0, 5], [50.0, 7], [1.0, 99]]))
    src = get_source("generic", {"events_path": str(p)})
    files, events = src.scan({}, now=50.0, window=45.0)
    assert events == [(10.0, 5), (50.0, 7)]

def test_generic_missing_file_is_empty(tmp_path):
    src = get_source("generic", {"events_path": str(tmp_path / "nope.json")})
    files, events = src.scan({}, now=100.0, window=100.0)
    assert events == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sources_generic.py -v`
Expected: FAIL — `AttributeError`/registry miss on `"generic"`

- [ ] **Step 3: Write minimal implementation**

```python
# oracle/sources/generic.py
"""Documented stub source for non-Claude providers. Feed it a JSON file of
neutral [[timestamp, tokens], ...] pairs. Copy this file to build your own
adapter; see ADAPTERS.md."""
import json
import os

from .base import register


@register("generic")
class GenericSource:
    def __init__(self, opts):
        self.events_path = os.path.expanduser(opts.get("events_path") or "")

    def scan(self, files_state, now, window):
        cutoff = now - window
        out = []
        try:
            with open(self.events_path, encoding="utf-8") as fh:
                data = json.load(fh)
            for ts, tok in data:
                ts = float(ts)
                if cutoff <= ts <= now:
                    out.append((ts, int(tok)))
        except (OSError, ValueError, TypeError):
            pass
        out.sort()
        return files_state, out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sources_generic.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add oracle/sources/generic.py tests/test_sources_generic.py
git commit -m "feat(sources): generic stub source for custom feeders"
```

---

### Task 10: Engine facade

**Files:**
- Create: `oracle/core/engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: `oracle.core.cache.{load_cache,save_cache,events_from_cache,AGGREGATE_INTERVAL}`, `oracle.core.profile.{build_profile,HIST_SECS}`, `oracle.core.windows.compute_window`, `oracle.sources.base.get_source`, `oracle.core.config.{Config,load_config}`.
- Produces: `forecast(now: float, config: Config | None = None) -> list[Forecast]`. Orchestrates source scan → cache → profile → per-window compute. Mirrors `usage_blocks` orchestration (30s aggregate gate, atomic save). Never raises (returns `[]` on hard failure).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_engine.py
import json
from oracle.core.config import Config
from oracle.core.contracts import Window
from oracle.core.engine import forecast

def test_forecast_over_generic_source(tmp_path):
    feed = tmp_path / "feed.json"
    now = 100000.0
    feed.write_text(json.dumps([[now - 600.0, 200], [now - 60.0, 50]]))
    cfg = Config(source="generic", source_opts={"events_path": str(feed)},
                 cache_path=str(tmp_path / "cache.json"),
                 windows=[Window("5h", 1000, 18000)])
    out = forecast(now, cfg)
    assert len(out) == 1
    assert out[0].window == "5h"
    assert out[0].used == 250
    assert json.load(open(str(tmp_path / "cache.json")))["lastAggregate"] == now

def test_forecast_empty_on_bad_source(tmp_path):
    cfg = Config(source="does-not-exist", source_opts={},
                 cache_path=str(tmp_path / "c.json"),
                 windows=[Window("5h", 1000, 18000)])
    assert forecast(100.0, cfg) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.core.engine'`

- [ ] **Step 3: Write minimal implementation**

```python
# oracle/core/engine.py
"""Forecast facade: source scan -> cache -> burn profile -> per-window compute.
Never raises; returns [] on hard failure."""
from .cache import (load_cache, save_cache, events_from_cache,
                    AGGREGATE_INTERVAL)
from .profile import build_profile, HIST_SECS
from .windows import compute_window
from .config import load_config


def forecast(now, config=None):
    try:
        cfg = config or load_config()
        from ..sources.base import get_source
        source = get_source(cfg.source, cfg.source_opts)
        cache = load_cache(cfg.cache_path)
        if now - cache.get("lastAggregate", 0) >= AGGREGATE_INTERVAL:
            files, events = source.scan(cache.get("files", {}), now, HIST_SECS)
            cache["files"] = files
            cache["lastAggregate"] = now
            cache["profile"] = build_profile(events, now)
            save_cache(cache, cfg.cache_path)
        else:
            events = events_from_cache(cache, now, HIST_SECS)
        profile = cache.get("profile") or None
        return [compute_window(events, now, w, profile) for w in cfg.windows]
    except Exception:
        return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_engine.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add oracle/core/engine.py tests/test_engine.py
git commit -m "feat(core): forecast facade orchestrating source->cache->windows"
```

---

### Task 11: Snapshot writer (the Sage/external contract)

**Files:**
- Create: `oracle/snapshot/__init__.py`, `oracle/snapshot/writer.py`
- Test: `tests/test_snapshot.py`

**Interfaces:**
- Consumes: `oracle.core.contracts.Forecast`.
- Produces:
  - `SCHEMA_VERSION = 1`.
  - `forecast_to_dict(f: Forecast) -> dict`.
  - `build_snapshot(forecasts: list[Forecast], now: float) -> dict` — `{"schema": 1, "generated_at": now, "windows": [..]}`.
  - `default_snapshot_path() -> str` → `~/.local/share/token-oracle/forecast.json` (honors `$XDG_DATA_HOME`).
  - `write_snapshot(forecasts, now, path=None) -> str` — atomic write; returns path.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_snapshot.py
import json
from oracle.core.contracts import Forecast
from oracle.snapshot.writer import (build_snapshot, write_snapshot,
                                     forecast_to_dict, SCHEMA_VERSION)

def test_schema_shape_is_stable():
    f = Forecast("5h", 100, 1000, 42.0, 1234.5, 3600.0, False, 0.9)
    d = forecast_to_dict(f)
    assert set(d) == {"window", "used", "cap", "projected_pct",
                      "eta_to_cap_secs", "reset_in_secs", "idle", "confidence"}

def test_build_snapshot_envelope():
    snap = build_snapshot([Forecast("5h", 1, 2, 3.0, None, 4.0, False)], now=10.0)
    assert snap["schema"] == SCHEMA_VERSION
    assert snap["generated_at"] == 10.0
    assert len(snap["windows"]) == 1

def test_write_snapshot_roundtrip(tmp_path):
    p = str(tmp_path / "d" / "forecast.json")
    write_snapshot([Forecast("wk", 5, 9, 55.0, None, 600.0, False)], 7.0, p)
    snap = json.load(open(p))
    assert snap["windows"][0]["window"] == "wk"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.snapshot.writer'`

- [ ] **Step 3: Write minimal implementation**

```python
# oracle/snapshot/__init__.py
```

```python
# oracle/snapshot/writer.py
"""Stable JSON snapshot any external consumer (agentic-sage, a status bar) can
read. Schema is versioned; see ADAPTERS.md. Atomic write, never raises."""
import json
import os
from dataclasses import asdict

SCHEMA_VERSION = 1


def forecast_to_dict(f):
    return asdict(f)


def build_snapshot(forecasts, now):
    return {"schema": SCHEMA_VERSION, "generated_at": now,
            "windows": [forecast_to_dict(f) for f in forecasts]}


def default_snapshot_path():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "token-oracle", "forecast.json")


def write_snapshot(forecasts, now, path=None):
    path = os.path.expanduser(path or default_snapshot_path())
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(build_snapshot(forecasts, now), fh)
        os.replace(tmp, path)
    except OSError:
        pass
    return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_snapshot.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add oracle/snapshot/ tests/test_snapshot.py
git commit -m "feat(snapshot): versioned forecast.json contract writer"
```

---

### Task 12: Reference adapters (statusline + tmux)

**Files:**
- Create: `oracle/adapters/__init__.py`, `oracle/adapters/statusline.py`, `oracle/adapters/tmux.py`
- Test: `tests/test_adapters.py`

**Interfaces:**
- Consumes: `oracle.core.contracts.Forecast`, `oracle.core.timeutil.{fmt_tokens,fmt_hms,fmt_dh_long}`.
- Produces:
  - `statusline.color_for(pct: float) -> str` (ANSI), `statusline.render(forecasts: list[Forecast]) -> str` — one line, e.g. `🕐 3:46 12k/220k →42%  📅 5 days 18 hours →63%`, ANSI-colored, `⚠ cap …` appended when `eta_to_cap_secs` is not None.
  - `tmux.color_for(pct: float) -> str` (tmux `#[fg=...]`), `tmux.render(forecasts) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_adapters.py
from oracle.core.contracts import Forecast
from oracle.adapters import statusline, tmux

F_OK = Forecast("5h", 12000, 220000, 42.0, None, 3 * 3600 + 46 * 60, False)
F_HOT = Forecast("weekly", 5_000_000, 8_000_000, 130.0, 90000.0,
                 5 * 86400 + 18 * 3600, False)

def test_statusline_contains_numbers():
    s = statusline.render([F_OK])
    assert "12k/220k" in s and "42%" in s

def test_statusline_warns_on_eta():
    s = statusline.render([F_HOT])
    assert "cap" in s   # eta -> cap warning appended

def test_statusline_color_thresholds():
    assert statusline.color_for(130) != statusline.color_for(10)

def test_tmux_render_uses_tmux_color_syntax():
    s = tmux.render([F_OK])
    assert "#[fg=" in s and "12k/220k" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_adapters.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.adapters'`

- [ ] **Step 3: Write minimal implementation** (color scale generalized from `usage_limits.color_weekly`)

```python
# oracle/adapters/__init__.py
```

```python
# oracle/adapters/statusline.py
"""Thin reference adapter: render a Forecast list to one ANSI status line.
Proof the engine renders anywhere; a polished status bar is a separate project."""
from ..core.timeutil import fmt_tokens, fmt_hms, fmt_dh_long

GREEN, LIME, ORANGE, RED, RESET = (
    "\033[38;5;42m", "\033[38;5;154m", "\033[38;5;214m", "\033[38;5;196m",
    "\033[0m",
)


def color_for(pct):
    if pct >= 120:
        return RED
    if pct >= 100:
        return ORANGE
    if pct >= 85:
        return LIME
    return GREEN


def _segment(f):
    pct = f.projected_pct
    body = (f"{fmt_hms(f.reset_in_secs)} "
            f"{fmt_tokens(f.used)}/{fmt_tokens(f.cap)} →{round(pct)}%")
    if f.eta_to_cap_secs is not None:
        body += f" ⚠ cap {fmt_dh_long(f.eta_to_cap_secs)}"
    return f"{color_for(pct)}🕐 {body}{RESET}"


def render(forecasts):
    return "  ".join(_segment(f) for f in forecasts if not f.idle)
```

```python
# oracle/adapters/tmux.py
"""Thin reference adapter: render a Forecast list to a tmux status string."""
from ..core.timeutil import fmt_tokens, fmt_hms, fmt_dh_long


def color_for(pct):
    if pct >= 120:
        return "#[fg=red]"
    if pct >= 100:
        return "#[fg=colour214]"
    if pct >= 85:
        return "#[fg=colour154]"
    return "#[fg=green]"


def _segment(f):
    pct = f.projected_pct
    body = (f"{fmt_hms(f.reset_in_secs)} "
            f"{fmt_tokens(f.used)}/{fmt_tokens(f.cap)} ->{round(pct)}%")
    if f.eta_to_cap_secs is not None:
        body += f" cap {fmt_dh_long(f.eta_to_cap_secs)}"
    return f"{color_for(pct)}{body}#[default]"


def render(forecasts):
    return " ".join(_segment(f) for f in forecasts if not f.idle)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_adapters.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add oracle/adapters/ tests/test_adapters.py
git commit -m "feat(adapters): thin statusline + tmux reference renderers"
```

---

### Task 13: CLI

**Files:**
- Create: `oracle/cli/__init__.py`, `oracle/cli/main.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `oracle.core.config.load_config`, `oracle.core.engine.forecast`, `oracle.snapshot.writer.{write_snapshot,build_snapshot}`, `oracle.adapters.{statusline,tmux}`, `oracle.sources.base.available`.
- Produces: `main(argv: list[str] | None = None) -> int`. Subcommands:
  - `forecast [--json] [--config PATH]` — print human lines or the snapshot JSON.
  - `snapshot [--config PATH] [--out PATH]` — write `forecast.json`, print its path.
  - `statusline [--config PATH]` / `tmux [--config PATH]` — print the reference adapter line.
  - `doctor [--config PATH]` — print config path, source availability, cache path, window count; exit 0.
  - `dash [--config PATH]` — launch the dashboard (Task 15).
  - `now` is read from `time.time()`; tests inject via `--now` (hidden float flag).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
import json
from oracle.cli.main import main

def _cfg(tmp_path, feed_events, now):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps(feed_events))
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({
        "source": "generic", "source_opts": {"events_path": str(feed)},
        "cache_path": str(tmp_path / "cache.json"),
        "windows": [{"name": "5h", "cap": 1000, "period_secs": 18000}],
    }))
    return str(cfg)

def test_forecast_json(tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 250]], now)
    rc = main(["forecast", "--json", "--config", cfg, "--now", str(now)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["windows"][0]["used"] == 250

def test_snapshot_writes_file(tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 10]], now)
    out_path = str(tmp_path / "snap.json")
    rc = main(["snapshot", "--config", cfg, "--out", out_path, "--now", str(now)])
    assert rc == 0
    assert json.load(open(out_path))["schema"] == 1

def test_doctor_exit_zero(tmp_path):
    now = 100000.0
    cfg = _cfg(tmp_path, [], now)
    assert main(["doctor", "--config", cfg, "--now", str(now)]) == 0

def test_statusline_runs(tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 250]], now)
    assert main(["statusline", "--config", cfg, "--now", str(now)]) == 0
    out = capsys.readouterr().out
    assert out.strip()                 # renders a non-empty status line
    assert "/1k" in out or "0k" in out  # used/cap tokens segment present
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.cli.main'`

- [ ] **Step 3: Write minimal implementation**

```python
# oracle/cli/__init__.py
```

```python
# oracle/cli/main.py
"""oracle CLI: forecast / snapshot / statusline / tmux / doctor / dash."""
import argparse
import json
import time

from ..core.config import load_config, default_config_path
from ..core.engine import forecast as run_forecast
from ..snapshot.writer import build_snapshot, write_snapshot
from ..adapters import statusline as sl, tmux as tx
from ..sources.base import available


def _add_common(p):
    p.add_argument("--config", default=None)
    p.add_argument("--now", type=float, default=None)


def _now(args):
    return args.now if args.now is not None else time.time()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="oracle")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("forecast", "snapshot", "statusline", "tmux", "doctor", "dash"):
        sp = sub.add_parser(name)
        _add_common(sp)
        if name == "forecast":
            sp.add_argument("--json", action="store_true")
        if name == "snapshot":
            sp.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    now = _now(args)

    if args.cmd == "forecast":
        fs = run_forecast(now, cfg)
        if args.json:
            print(json.dumps(build_snapshot(fs, now)))
        else:
            print(sl.render(fs) or "idle")
        return 0
    if args.cmd == "snapshot":
        fs = run_forecast(now, cfg)
        path = write_snapshot(fs, now, args.out)
        print(path)
        return 0
    if args.cmd == "statusline":
        print(sl.render(run_forecast(now, cfg)))
        return 0
    if args.cmd == "tmux":
        print(tx.render(run_forecast(now, cfg)))
        return 0
    if args.cmd == "doctor":
        print(f"config:  {args.config or default_config_path()}")
        print(f"source:  {cfg.source}  (available: {', '.join(available())})")
        print(f"cache:   {cfg.cache_path}")
        print(f"windows: {len(cfg.windows)} -> {[w.name for w in cfg.windows]}")
        return 0
    if args.cmd == "dash":
        from ..dashboard.app import run as run_dash
        return run_dash(cfg, now)
    return 1
```

- [ ] **Step 4: Run test to verify it passes** (and confirm the console entry resolves)

Run: `python -m pytest tests/test_cli.py -v && oracle doctor --now 100000`
Expected: tests PASS (4 passed); `oracle doctor` prints config/source/cache/windows lines.

- [ ] **Step 5: Commit**

```bash
git add oracle/cli/ tests/test_cli.py
git commit -m "feat(cli): oracle forecast/snapshot/statusline/tmux/doctor/dash"
```

---

### Task 14: TUI dashboard

**Files:**
- Create: `oracle/dashboard/__init__.py`, `oracle/dashboard/app.py`
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: `oracle.core.engine.forecast`, `oracle.core.timeutil.{fmt_tokens,fmt_hms,fmt_dh_long}`, `oracle.core.contracts.Forecast`.
- Produces:
  - `render_frame(forecasts: list[Forecast], now: float) -> str` — a multi-line plain-text frame (one block per window: name, used/cap, projected %, reset-in, eta, a textual bar). Pure + testable.
  - `run(cfg, now) -> int` — clears screen, prints `render_frame`, refreshes every 2s until `KeyboardInterrupt`; returns 0. (Loop is not unit-tested; `render_frame` is.)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dashboard.py
from oracle.core.contracts import Forecast
from oracle.dashboard.app import render_frame

def test_render_frame_lists_windows():
    fs = [Forecast("5h", 12000, 220000, 42.0, None, 3600.0, False),
          Forecast("weekly", 5_000_000, 8_000_000, 130.0, 90000.0, 400000.0, False)]
    frame = render_frame(fs, now=100000.0)
    assert "5h" in frame and "weekly" in frame
    assert "42%" in frame and "130%" in frame

def test_render_frame_handles_idle():
    fs = [Forecast("5h", 0, 220000, 0.0, None, 18000.0, True)]
    frame = render_frame(fs, now=1.0)
    assert "idle" in frame.lower()

def test_render_frame_empty():
    assert isinstance(render_frame([], now=1.0), str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dashboard.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'oracle.dashboard.app'`

- [ ] **Step 3: Write minimal implementation**

```python
# oracle/dashboard/__init__.py
```

```python
# oracle/dashboard/app.py
"""Minimal stdlib TUI over the Forecast list. render_frame is pure (tested);
run() is the refresh loop."""
import os
import time

from ..core.engine import forecast as run_forecast
from ..core.timeutil import fmt_tokens, fmt_hms, fmt_dh_long


def _bar(pct, width=24):
    filled = max(0, min(width, int(round(pct / 100.0 * width))))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def render_frame(forecasts, now):
    lines = ["token-oracle", "=" * 40]
    if not forecasts:
        lines.append("(no windows / no data)")
        return "\n".join(lines)
    for f in forecasts:
        if f.idle:
            lines.append(f"{f.window:>8}: idle  (resets in {fmt_hms(f.reset_in_secs)})")
            continue
        eta = (f" | cap in {fmt_dh_long(f.eta_to_cap_secs)}"
               if f.eta_to_cap_secs is not None else "")
        lines.append(
            f"{f.window:>8}: {fmt_tokens(f.used)}/{fmt_tokens(f.cap)} "
            f"->{round(f.projected_pct)}%  resets {fmt_hms(f.reset_in_secs)}{eta}")
        lines.append(f"          {_bar(f.projected_pct)}")
    return "\n".join(lines)


def run(cfg, now):
    try:
        while True:
            os.system("clear")
            print(render_frame(run_forecast(time.time(), cfg), time.time()))
            print("\n(ctrl-c to quit)")
            time.sleep(2)
    except KeyboardInterrupt:
        return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_dashboard.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add oracle/dashboard/ tests/test_dashboard.py
git commit -m "feat(dashboard): minimal stdlib forecast TUI"
```

---

### Task 15: Full suite green + OSS docs

**Files:**
- Create: `README.md`, `SETUP.md`, `AGENTS.md`, `ADAPTERS.md`
- Modify: none (verification step for the whole suite first)

**Interfaces:**
- Consumes: the whole package.
- Produces: documentation only.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest -q`
Expected: ALL PASS (every `tests/test_*.py`). Fix any cross-module drift before writing docs.

- [ ] **Step 2: Write `README.md`** (mirror agentic-sage shape: thesis, quickstart, parts table, works-with-sage)

Contents (verbatim skeleton to fill with the real commands from Tasks 12-14):
```markdown
# token-oracle

**ORACLE** = *Observed-Rate Allowance & Cap-Limit Estimator*. A provider-agnostic
engine that forecasts **when you'll hit a usage cap before its reset**, learned from
your own observed burn patterns. Companion to [agentic-sage](https://github.com/muslewski/agentic-sage).

## Quickstart
```bash
pipx install token-oracle        # or: pip install token-oracle
oracle doctor                    # show config + source + windows
oracle forecast                  # human line
oracle forecast --json           # the snapshot schema
oracle dash                      # live TUI
```

## What it does
- Reads usage events from a **source adapter** (Claude Code by default).
- Builds a pattern-aware burn profile (hour-of-week, recency-decayed).
- Forecasts each configured **window** (cap + reset moment) and the ETA to cap.

## Parts & options
| Part | What it does | Need it? |
|---|---|---|
| core engine | the forecast math | required |
| `claude_code` source | reads Claude Code transcripts | default source |
| `generic` source | feed your own `[[ts,tokens]]` JSON | optional |
| `oracle` CLI | query / snapshot / doctor | required |
| TUI dashboard (`oracle dash`) | live forecast view | optional |
| statusline / tmux adapters | thin reference renderers | optional |
| snapshot (`forecast.json`) | stable contract for other tools | optional |

## Works with agentic-sage
Oracle writes a stable `forecast.json`; sage optionally surfaces it (see SETUP.md).
The two stay separate — token prediction is an *optional* input to session awareness.

## License
MIT.
```

- [ ] **Step 3: Write `SETUP.md`** — tiers (engine-only → +CLI → +dashboard → +statusline/tmux → +sage wiring), the exact config file format (the `Config` JSON from Task 7, with a worked `max20` example and a custom-window example), and the **Optional integrations** section documenting `tokenForecastPath` pointing sage at `~/.local/share/token-oracle/forecast.json`.

- [ ] **Step 4: Write `ADAPTERS.md`** — the two interfaces verbatim:
  - **Source**: `scan(files_state, now, window) -> (files_state, [(ts, tokens)])`; copy `oracle/sources/generic.py`; register with `@register("name")`.
  - **Consumer**: read the snapshot schema (`{schema, generated_at, windows:[{window,used,cap,projected_pct,eta_to_cap_secs,reset_in_secs,idle,confidence}]}`), or import `oracle.core.engine.forecast` and read `Forecast` directly.

- [ ] **Step 5: Write `AGENTS.md`** — deterministic runbook for a coding agent: `pip install -e ".[dev]"` → `python -m pytest -q` → `oracle doctor` → write `~/.config/token-oracle/config.json` (or accept `max20`) → optional: wire sage's `tokenForecastPath`. Each step with the exact command and expected output.

- [ ] **Step 6: Commit**

```bash
git add README.md SETUP.md AGENTS.md ADAPTERS.md
git commit -m "docs: README, SETUP, AGENTS, ADAPTERS"
```

---

### Task 16: Installer + doctor polish (reversible)

**Files:**
- Create: `install.py`, `uninstall.py`
- Test: `tests/test_install.py`

**Interfaces:**
- Consumes: `oracle.core.config.{default_config_path,PRESETS}`.
- Produces:
  - `install.py`: `write_default_config(path=None, preset="max20", force=False) -> str` — writes a `config.json` from a preset **without clobbering** an existing file unless `force`; returns path. `main()` calls it + prints next steps. Non-clobber discipline mirrors agentic-sage.
  - `uninstall.py`: `remove_config(path=None) -> bool` and `remove_cache_and_snapshot() -> None`; `main()` removes oracle's config/cache/snapshot, leaving the pip package to `pip uninstall`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_install.py
import json, os
from install import write_default_config
from uninstall import remove_config

def test_writes_preset_config(tmp_path):
    p = str(tmp_path / "config.json")
    write_default_config(p, preset="max20")
    data = json.load(open(p))
    assert {w["name"] for w in data["windows"]} == {"5h", "weekly"}

def test_no_clobber_without_force(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"source":"custom"}')
    write_default_config(str(p), preset="max20")           # must NOT overwrite
    assert json.load(open(p))["source"] == "custom"
    write_default_config(str(p), preset="max20", force=True)  # force overwrites
    assert "windows" in json.load(open(p))

def test_remove_config(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{}")
    assert remove_config(str(p)) is True
    assert not p.exists()
    assert remove_config(str(p)) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_install.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'install'`

- [ ] **Step 3: Write minimal implementation**

```python
# install.py
"""Reversible installer: write a starter config from a preset (non-clobbering)."""
import json
import os
import sys

from oracle.core.config import default_config_path, PRESETS


def write_default_config(path=None, preset="max20", force=False):
    path = os.path.expanduser(path or default_config_path())
    if os.path.exists(path) and not force:
        return path
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(PRESETS[preset], fh, indent=2)
    return path


def main():
    path = write_default_config()
    print(f"config: {path}")
    print("next: `oracle doctor` then `oracle forecast`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

```python
# uninstall.py
"""Reversible uninstall: remove oracle's config/cache/snapshot. The pip package
is removed separately via `pip uninstall token-oracle`."""
import os
import sys

from oracle.core.config import default_config_path, default_cache_path
from oracle.snapshot.writer import default_snapshot_path


def remove_config(path=None):
    path = os.path.expanduser(path or default_config_path())
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def remove_cache_and_snapshot():
    for p in (default_cache_path(), default_snapshot_path()):
        try:
            os.remove(os.path.expanduser(p))
        except OSError:
            pass


def main():
    removed = remove_config()
    remove_cache_and_snapshot()
    print("removed config" if removed else "no config to remove")
    print("run `pip uninstall token-oracle` to remove the package")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_install.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add install.py uninstall.py tests/test_install.py
git commit -m "feat(install): reversible non-clobbering installer + uninstaller"
```

---

## Final verification

- [ ] Run full suite: `python -m pytest -q` → all green.
- [ ] Smoke the CLI end-to-end: `oracle doctor && oracle forecast --json` → valid JSON snapshot.
- [ ] Confirm core purity: `grep -rE "import (oracle\\.adapters|oracle\\.cli|oracle\\.dashboard)" oracle/core oracle/sources` → no matches.
- [ ] Confirm zero runtime deps: `pyproject.toml` lists deps only under `[project.optional-dependencies].dev`.

## Deferred (post-v1, noted so they aren't silently dropped)

- **Server-truth source adapter** — port `~/token-forecast/src/token_forecast/ratelimits.py` + the `_server_overlay` logic (`claude_sessions.py:264-356`) as a second source/overlay that re-levels the local forecast onto Anthropic's real `used_percentage`. Optional; needs live headers.
- **ML profile** — swap `build_profile` for a learned model behind the same signature (optional dep extra).
- **Polished customizable status bar** — separate OSS project; consumes `forecast.json`.
- **Sage → Oracle reverse feed** — per-session `{model, effort}` as a forecast feature.
