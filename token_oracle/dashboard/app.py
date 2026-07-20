"""Stdlib TUI over the Forecast list. render_frame is pure (tested); run() is the
refresh loop. Enhanced for multi-sub (Claude + Grok side-by-side), rich boxes,
progress, and RESET alarm animations that people will remember."""

import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from collections import deque

from ..cli import colors as c
from ..core.engine import detect_resets
from ..core.engine import forecast as run_forecast
from ..core.timeutil import fmt_dh_long, fmt_reset, fmt_tokens
from ..live.contract import (
    STATE_AUTH_NO_DATA,
    STATE_ERROR,
    STATE_NEEDS_LOGIN,
    STATE_RATE_DATA_ONLY,
    STATE_STALE,
    STATE_UNAVAILABLE,
)
from ..live.overlay import overlay_cells, rate_info
from ..live.store import load_snapshot
from .future import cost_pace_line, render_future
from .keys import CYCLE, LEFT, QUIT, RIGHT, TAB1, TAB2, TAB3
from .keys import reader as key_reader
from .past import render_past_sections, top_models_by_day
from .scene import Painter, Region, Scene
from .skeleton import render_skeleton, spinner_char
from .store import DashStore

BAR_W = 22  # default/maximum gauge width
BAR_W_MIN = 6  # narrowest legible gauge
MIN_BOX = 34  # min box width that still fits "glyph name pct bar reset"
BOX_MAX = 66  # widest stacked box (unchanged from today)
BARS_MIN = 16  # min width for borderless slider bars (below this -> compact text)

# Tab shell (plan 018). Present = fixed-region scene (034); past/future filled by 019/020.
TABS = ("past", "present", "future")
TAB_LABELS = {"past": "Past", "present": "Present", "future": "Future"}
_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
PAST_DAYS = 14
TAB_DATA_TTL = 30.0  # seconds between past/future data refreshes


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def render_tab_bar(active: str, width: int, enabled: bool) -> str:
    """Pure tab bar: `🔮 token-oracle   ‹ Past │ Present │ Future ›` + clock.

    Active tab name is violet; others dim. Right-aligned HH:MM:SS. Truncated
    to `width` display cells when needed.
    """
    from ..cli.colors import display_width

    active = active if active in TABS else "present"
    parts = []
    for name in TABS:
        label = TAB_LABELS[name]
        if name == active:
            parts.append(c.violet(label, enabled) if enabled else label)
        else:
            parts.append(c.dim(label, enabled) if enabled else label)
    # join with dim separators (use plain "│" so width math is stable)
    mid = " │ ".join(parts)
    left = f"{c.M_ORACLE} token-oracle   ‹ {mid} ›"
    clock = time.strftime("%H:%M:%S")
    clock_s = c.dim(clock, enabled) if enabled else clock
    # pad between left and clock
    gap = width - display_width(left) - display_width(clock_s)
    if gap < 1:
        # too narrow: drop the clock, then truncate left
        line = left
        if display_width(line) > width:
            # fall back to a short title + active only
            short = f"{c.M_ORACLE} {TAB_LABELS[active]}"
            if display_width(short) > width:
                return c.violet(f"{c.M_ORACLE}", enabled)[:width] if enabled else c.M_ORACLE
            return c.violet(short, enabled) if (enabled and active) else short
        return line
    return left + (" " * gap) + clock_s


def render_placeholder(tab: str, width: int, enabled: bool) -> list[str]:
    """Legacy placeholder (kept for tests / unknown tabs). Past/Future use real renderers."""
    tab = (tab or "past").lower()
    if tab == "future":
        msg = "the oracle is still learning to read the future"
        note = "arrives with plan 020"
    else:
        msg = "the oracle is still learning to read the past"
        note = "arrives with plan 019"
    lines = [
        "",
        c.dim(f"  {msg}", enabled),
        c.dim(f"  {note}", enabled),
        "",
        c.dim(f"  tab: {tab}", enabled),
    ]
    while len(lines) < 8:
        lines.append("")
    return lines


def _wins_from_raw(wraw):
    """Normalize window configs to Window-like objects for weekly_cap."""
    wins = []
    for w in wraw or []:
        if hasattr(w, "cap"):
            wins.append(w)
        elif isinstance(w, dict):
            try:
                from ..core.config import _window_from_dict

                wins.append(_window_from_dict(w))
            except Exception:
                continue
    return wins


def _events_since(evs, cutoff: float) -> list:
    """Keep only events with ts >= cutoff (cheap prefilter before ledger/cost)."""
    out = []
    for e in evs or []:
        if isinstance(e, (list, tuple)) and len(e) >= 2:
            try:
                if float(e[0]) >= cutoff:
                    out.append(e)
            except (TypeError, ValueError):
                continue
    return out


def _past_sections_for_dash(cfg, now: float, days: int = 14, cache=None) -> list[dict]:
    """Build past-tab sections from the on-disk event cache (reuse report core).

    Prefilters events to the last `days` so cost_summary does not walk 9 weeks.
    Multi-profile: skip empty profiles so the tab does not look duplicated.
    """
    from ..core import report as report_mod
    from ..core.cache import load_cache
    from ..core.engine import cached_events

    mode = getattr(cfg, "cost_mode", "auto") or "auto"
    overrides = getattr(cfg, "pricing", None) or {}
    sections: list[dict] = []
    cutoff = now - max(1, int(days)) * 86400.0 - 86400.0  # +1d TZ slack

    if getattr(cfg, "profiles", None):
        if cache is None:
            try:
                cache = load_cache(getattr(cfg, "cache_path", "") or "") or {}
            except Exception:
                cache = {}
        profiles_cache = cache.get("profiles") if isinstance(cache, dict) else {}
        if not isinstance(profiles_cache, dict):
            profiles_cache = {}
        for pname in sorted(cfg.profiles.keys()):
            pdef = cfg.profiles.get(pname) or {}
            slc = profiles_cache.get(pname) or {}
            raw = (slc.get("events") if isinstance(slc, dict) else None) or []
            evs = _events_since(raw, cutoff)
            wins = _wins_from_raw(pdef.get("windows") or cfg.windows)
            cap = report_mod.weekly_cap(wins) or 0
            rows = report_mod.daily_ledger(evs, cap, now, days=days, mode=mode, overrides=overrides)
            total = next((r for r in rows if getattr(r, "label", None) == "TOTAL"), None)
            if total is not None and int(getattr(total, "tokens", 0) or 0) == 0:
                continue
            sections.append(
                {
                    "profile": pname,
                    "rows": rows,
                    "tops": top_models_by_day(evs, now, days=days),
                }
            )
        if sections:
            return sections

    try:
        raw = cached_events(cfg) or []
    except Exception:
        raw = []
    evs = _events_since(raw, cutoff)
    cap = report_mod.weekly_cap(getattr(cfg, "windows", None) or []) or 0
    rows = report_mod.daily_ledger(evs, cap, now, days=days, mode=mode, overrides=overrides)
    sections.append(
        {
            "profile": getattr(cfg, "source", "default") or "default",
            "rows": rows,
            "tops": top_models_by_day(evs, now, days=days),
        }
    )
    return sections


def _future_extras(cfg, now: float, cache=None, events=None):
    """Return (profile_list, cost_line). Reuse cache/events when the worker has them."""
    from ..core import pricing as pricing_mod
    from ..core.cache import load_cache
    from ..core.engine import cached_events

    if cache is None:
        try:
            cache = load_cache(getattr(cfg, "cache_path", "") or "") or {}
        except Exception:
            cache = {}

    profile = None
    try:
        profile = (cache or {}).get("profile") or None
        if not profile and isinstance((cache or {}).get("profiles"), dict):
            for slc in cache["profiles"].values():
                if isinstance(slc, dict) and slc.get("profile"):
                    profile = slc.get("profile")
                    break
    except Exception:
        profile = None

    cost_line = None
    mode = getattr(cfg, "cost_mode", "auto") or "auto"
    if mode != "off":
        try:
            if events is None:
                events = cached_events(cfg) or []
            recent = _events_since(events, now - 7 * 86400)
            summary = pricing_mod.cost_summary(recent, mode, getattr(cfg, "pricing", None) or {})
            usd = summary.get("usd")
            if recent and summary.get("unpriced_tokens", 0) == sum(
                int(e[1]) for e in recent if len(e) > 1
            ):
                cost_line = None
            elif usd is not None:
                cost_line = cost_pace_line(float(usd), days=7)
        except Exception:
            cost_line = None
    return profile, cost_line


def render_footer(width: int, enabled: bool) -> str:
    """Key-hint footer for the tabbed TUI."""
    hints = "←/→ or h/l switch · 1-3 jump · q quit"
    ts = time.strftime("%H:%M:%S")
    text = f"{hints}  ·  {ts}"
    from ..cli.colors import display_width

    if display_width(text) > width:
        text = "←/→ · 1-3 · q"
    return c.dim(text, enabled)


def _apply_tab_key(active: str, key: str) -> str | None:
    """Return new active tab, or None if key means quit. Unknown keys keep tab."""
    if key == QUIT:
        return None
    idx = TABS.index(active) if active in TABS else 1
    if key == LEFT:
        return TABS[(idx - 1) % len(TABS)]
    if key == RIGHT or key == CYCLE:
        return TABS[(idx + 1) % len(TABS)]
    if key == TAB1:
        return TABS[0]
    if key == TAB2:
        return TABS[1]
    if key == TAB3:
        return TABS[2]
    return active


def _bar_w_for(box_w: int) -> int:
    """Gauge width derived from the box's inner width. The head line spends
    ~26 cells on 'glyph name<6> pct<4> reset<~7>' plus spacing; the rest is
    the bar, clamped to a legible range."""
    return _clamp(box_w - 26, BAR_W_MIN, BAR_W)


def _bars_bar_w_for(w: int) -> int:
    """Gauge width for a borderless bar row. The row prefix spends 13 cells on
    '  {label:<5} {pct:>4} '; the rest is the bar, clamped to a legible minimum
    so the % (which precedes the bar) always survives."""
    return _clamp(w - 13, 3, BAR_W)


_EIGHTHS = "▏▎▍▌▋▊▉"  # 1/8..7/8 left-fraction blocks; a full cell is █


def _bar(pct, enabled, width=BAR_W):
    """Gauge bar with sub-cell (1/8) resolution so animated fills glide smoothly
    instead of jumping a whole cell at a time. Always exactly `width` cells."""
    pct = max(0.0, min(100.0, pct))
    total8 = int(round(pct / 100.0 * width * 8))
    full = min(width, total8 // 8)
    rem = total8 - full * 8
    if full >= width:
        bar = "█" * width
    elif rem:
        bar = "█" * full + _EIGHTHS[rem - 1] + "░" * (width - full - 1)
    else:
        bar = "█" * full + "░" * (width - full)
    return c.gauge(bar, pct, enabled)


def _profile_icon(profile):
    p = (profile or "").lower()
    if "grok" in p or p == "grok":
        return c.M_GROK
    if "claude" in p or p == "claude" or p == "default":
        return c.M_CLAUDE
    return c.M_ORACLE


def _fit_join(prefix: str, items: list[str], width: int, sep: str = " · ") -> str:
    """Return `prefix` + as many `items` (in order) as fit within `width` display
    cells, joined by `sep`. Never emits a trailing separator; never exceeds
    `width`. `prefix` and `items` may already contain ANSI (measured by
    display_width). If not even the first item fits after the prefix, returns the
    first (binding) item alone so the most-important number always survives at
    widths >= ~10 cells (caller orders items[0] as highest %)."""
    from ..cli.colors import display_width

    if not items:
        return prefix
    out = prefix
    used = display_width(prefix)
    first = True
    for it in items:
        add = (0 if first else display_width(sep)) + display_width(it)
        if used + add > width:
            break
        out = out + ("" if first else sep) + it
        used += add
        first = False
    if first and items:
        # prefix too wide to leave room for binding item; emit just the binding
        # item (ensures e.g. '99% fable' appears even when '✳ claude  ' prefix
        # would overflow a ~12-cell terminal)
        return items[0]
    return out


def _fmt_reset_abs(reset_in, now):
    # Use friendly format: minutes first, proper d/h for long (no 156:00)
    return fmt_reset(reset_in)


# Fixed-height layout (plan 034): heights depend ONLY on config shape (#windows per profile),
# never on idle/active state or presence of live data. Every window row is exactly 3 lines.
HEADER_H = 2
ALERT_H = 1
ACTIVITY_H = 3
FOOTER_H = 1

# Seconds between web scrapes (heavy Chromium relaunch). Only feeds the slow
# authoritative caps; the fast 5h number comes from local logs every tick, so
# this can be long. MUST stay well below overlay.FRESH_TTL_SECS (+ probe time)
# or cap cells go "stale" between probes. Guarded by a test.
LIVE_PROBE_INTERVAL = 240


def _panel_block_height(n_windows: int, detail: int = 2) -> int:
    """Top + bottom + (detail+1) lines per window row."""
    n = max(1, int(n_windows or 1))
    return 2 + (detail + 1) * n


def _panels_arrangement(groups: dict, w: int):
    """Decide how panels lay out for terminal width `w`.

    Returns (mode, box_w, bar_w):
      mode "side"    -> two boxes side by side, each box_w wide, joined by 3 spaces
      mode "stack"   -> one box_w-wide box per profile, stacked
      mode "oneline" -> compact one line per profile (no boxes)
    Never returns a geometry wider than `w`.
    """
    pnames = list(groups.keys())
    two_equal = len(pnames) == 2 and len(groups[pnames[0]]) == len(groups[pnames[1]])
    if two_equal and w >= 2 * MIN_BOX + 3:
        box_w = _clamp((w - 3) // 2, MIN_BOX, 60)
        return "side", box_w, _bar_w_for(box_w)
    if w >= MIN_BOX:
        box_w = _clamp(w, MIN_BOX, BOX_MAX)
        return "stack", box_w, _bar_w_for(box_w)
    if w >= BARS_MIN:
        return "bars", w, _bars_bar_w_for(w)
    return "oneline", w, BAR_W_MIN


def panel_height(groups: dict, detail: int = 2, w: int = 999) -> int:
    """Compute the panels region height for the current groups shape + detail.

    Arrangement (side / stack / oneline) is chosen from width `w` via the shared
    helper so that panel_height and panels_fill agree on line count for the
    chosen geometry (fixed-height contract).
    """
    if not groups:
        return _panel_block_height(1, detail)  # (no data) padded block
    mode, _bw, _barw = _panels_arrangement(groups, w)
    if mode == "oneline":
        return len(groups)  # one compact line per profile
    if mode == "bars":
        # header (1) + one row per window + inter-block gap (1), per provider
        return sum(1 + (len(fs) or 1) + 1 for fs in groups.values())
    if mode == "side":
        n = len(groups[list(groups.keys())[0]])
        return _panel_block_height(n, detail)
    total = 0  # stack
    for _pn, fs in groups.items():
        total += _panel_block_height(len(fs) or 1, detail)
        total += 1  # inter-block gap line
    return total


def _compact_profile_line(pname, forecasts, now, enabled, cells=None, width=80) -> str:
    cells = cells or {}
    p_canon = "grok" if "grok" in pname.lower() else "claude"
    icon = _profile_icon(pname)
    rows = []  # (pct, short)
    for f in forecasts:
        ww = (f.window or "").lower()
        if bool(getattr(f, "idle", False)):
            continue
        is_5h = "5h" in ww or "session" in ww or "current" in ww
        if is_5h:
            pct = (100.0 * f.used / f.cap) if getattr(f, "cap", 0) else 0.0
            short = "5h"
        else:
            wkey = "weekly" if ww in ("weekly", "week") else ("fable" if ww == "fable" else None)
            cell = cells.get((p_canon, wkey)) if wkey else None
            pct = cell.pct if (cell and cell.pct is not None) else f.projected_pct
            short = "wk" if ww in ("weekly", "week") else (ww or "?")
        rows.append((float(pct), short))
    prefix = c.dim(f"{icon} {pname.lower()}  ", enabled)
    if not rows:
        return c.dim(f"{icon} {pname.lower()}  idle", enabled)
    rows.sort(key=lambda r: r[0], reverse=True)  # binding (highest %) first
    items = []
    for i, (pct, short) in enumerate(rows):
        text = f"{round(pct)}% {short}"
        # make the single most-critical item pop with its gauge color
        items.append(c.gauge(text, pct, enabled) if i == 0 else c.dim(text, enabled))
    return _fit_join(prefix, items, width)


def _render_profile_bars(pname, forecasts, now, enabled, cells, w, bar_w):
    """Borderless slider rows for narrow terminals (BARS_MIN <= w < MIN_BOX):
    a provider header line + one `label pct% bar` row per window. The number
    precedes the bar (pct-first) so it survives truncation; the bar is exactly
    `bar_w` cells so each row is exactly `w` cells. No box, no provenance, no
    glide animation (narrow fallback shows the true pct directly). Source blend
    matches the box: 5h from local logs, caps from the web cell else local proj."""
    cells = cells or {}
    p_canon = "grok" if "grok" in pname.lower() else "claude"
    icon = _profile_icon(pname)
    out = [c.violet(f"{icon} {pname.lower()}", enabled)]
    for f in sorted(forecasts, key=lambda x: x.window):
        ww = (f.window or "").lower()
        is_5h = "5h" in ww or "session" in ww or "current" in ww
        label = "5h" if is_5h else ("wk" if ww in ("weekly", "week") else (ww or "?"))
        label = label[:5].ljust(5)
        if bool(getattr(f, "idle", False)):
            out.append(c.dim(f"  {label} idle", enabled))
            continue
        if is_5h:
            pct = (100.0 * f.used / f.cap) if getattr(f, "cap", 0) else 0.0
        else:
            wkey = "weekly" if ww in ("weekly", "week") else ("fable" if ww == "fable" else None)
            cell = cells.get((p_canon, wkey)) if wkey else None
            pct = cell.pct if (cell and cell.pct is not None) else f.projected_pct
        pct = float(pct)
        pct_str = c.gauge(f"{round(pct)}%".rjust(4), pct, enabled)
        if enabled:
            pct_str = f"\033[1m{pct_str}\033[0m"
        bar = _bar(pct, enabled, bar_w)
        out.append(f"  {label} {pct_str} {bar}")
    return out


def _row_glyph(cell, is_idle: bool) -> str:
    """Glyph encoding provenance origin for the head line (per plan 034 3-line contract)."""
    if is_idle:
        return "–"
    if cell is not None and getattr(cell, "pct", None) is not None:
        return "●"
    return "◌"


# --- row-change animation: smooth bar glide + a pulse on the changed row ------
CHANGE_EPS = 0.4  # min target delta (pct points) that triggers a pulse
SETTLE_EPS = 0.15  # snap displayed pct to target within this
EASE = 0.28  # fraction of the remaining gap closed per animation frame
PULSE_SECS = 2.4  # how long a row pulses after its value changes
FAST_DT = 0.06  # frame interval while a bar is gliding / a row is pulsing
IDLE_DT = 1.2  # frame interval when everything is settled


def _pulse_level(start: float, now: float, dur: float = PULSE_SECS) -> float:
    """Decaying 3-cycle shimmer 1->0 over `dur` seconds; 0 outside the window."""
    e = now - start
    if e < 0 or e >= dur:
        return 0.0
    phase = e / dur
    env = 1.0 - phase
    osc = 0.5 * (1.0 + math.cos(phase * 2.0 * math.pi * 3.0))
    return max(0.0, min(1.0, env * osc))


def _pulse_glyph(ch: str, level: float, enabled: bool) -> str:
    """Emphasize a status glyph proportional to pulse level (bright at the peak)."""
    if not enabled or level <= 0:
        return ch
    if level > 0.6:
        return f"\033[1;97m{ch}\033[0m"  # bold bright white (peak)
    if level > 0.25:
        return f"\033[1;38;5;141m{ch}\033[0m"  # bold violet
    return f"\033[38;5;141m{ch}\033[0m"  # violet


def _row_akey(p_canon: str, f) -> tuple | None:
    ww = (getattr(f, "window", "") or "").lower()
    if "5h" in ww or "session" in ww or "current" in ww:
        return (p_canon, "5h")
    if ww in ("weekly", "week"):
        return (p_canon, "weekly")
    if ww == "fable":
        return (p_canon, "fable")
    return None


def _active_row_targets(forecasts, cells) -> dict:
    """Map (p_canon, wkey) -> current target pct for every active row, using the
    same blend as the panel (5h from local logs, caps from web cell or proj)."""
    cells = cells or {}
    out: dict = {}
    for f in forecasts or []:
        if bool(getattr(f, "idle", False)):
            continue
        pn = getattr(f, "profile", "default")
        p_canon = "grok" if "grok" in pn.lower() else "claude"
        akey = _row_akey(p_canon, f)
        if akey is None:
            continue
        if akey[1] == "5h":
            tgt = (100.0 * f.used / f.cap) if getattr(f, "cap", 0) else 0.0
        else:
            cell = cells.get(akey)
            tgt = cell.pct if (cell and cell.pct is not None) else f.projected_pct
        out[akey] = float(tgt)
    return out


def _render_profile_block(
    pname,
    forecasts,
    now,
    enabled,
    cells=None,
    width=66,
    detail=2,
    anim_pct=None,
    pulse=None,
    bar_w=BAR_W,
):
    """Render a boxed panel. `detail` sets lines per window row (height ladder):
      2 = head + meta + provenance (full), 1 = head + meta, 0 = head only.
    Row count per window is constant for a given detail, preserving height
    invariance within a level. Glyphs: ● live, ◌ local projection, – idle.
    Meta/provenance distinguish live vs local; source wording names the truth.

    anim_pct maps (p_canon, wkey) -> the currently-DISPLAYED bar pct (glides
    toward the true value); the head NUMBER always shows the true value. pulse
    maps (p_canon, wkey) -> 0..1 emphasis applied to the row glyph after a change.
    """
    per_row = detail + 1  # lines emitted per window row
    icon = _profile_icon(pname)
    title = f"{icon} {pname.upper()}"
    if "grok" in pname.lower():
        title += "  SuperGrok Heavy"
    elif pname.lower() in ("claude", "default"):
        title += "  Max 20×"
    lines = [c.violet(c.box_top(title, width, enabled), enabled)]
    if not forecasts:
        # (no data) block padded to per_row lines for height invariance
        lines.append(c.box_line(c.dim("(no data)", enabled), width, enabled))
        for _ in range(per_row - 1):
            lines.append(c.box_line(c.dim("", enabled), width, enabled))
        lines.append(c.box_bot(width, enabled))
        return lines

    cells = cells or {}
    p_canon = "grok" if "grok" in pname.lower() else "claude"

    for f in sorted(forecasts, key=lambda x: x.window):
        wname = f.window
        is_idle = bool(getattr(f, "idle", False))
        is_5h = "5h" in wname.lower() or "session" in wname.lower() or "current" in wname.lower()
        wkey = None
        ww = (wname or "").lower()
        if ww in ("weekly", "week"):
            wkey = "weekly"
        elif ww == "fable":
            wkey = "fable"
        elif ww in ("5h", "5-hour", "session", "current"):
            wkey = "5h"
        cell = cells.get((p_canon, wkey)) if wkey else None

        glyph = _row_glyph(cell, is_idle)

        if is_idle:
            # idle head: always show idle + reset (even 5h); special state_value only
            # affects meta/provenance
            reset_str = _fmt_reset_abs(f.reset_in_secs, now)
            head = f"{glyph} {wname:<6} idle  resets {reset_str}"
            if is_5h and cell and cell.state_value == "starts_on_first_message":
                # ONLY website phrasing when the cell carries the state (plan 034 + 030)
                meta = "   (5h window activates on first use; resets 5h later)"
                age = int(cell.age_secs) if getattr(cell, "age_secs", None) is not None else 0
                # avoid "live" wording when this row does not carry a live pct number
                prov = f"5h — from claude.ai ({age}s ago)" if age else "5h — from claude.ai"
            elif is_5h:
                meta = "   5h — no recent activity (live web gives exact after login)"
                prov = "local projection — no reliable live data (unavailable)"
            else:
                # blank meta + honest local prov for ordinary idle windows
                meta = ""
                prov = "local projection — live disabled"
            lines.append(c.box_line(head, width, enabled))
            if detail >= 1:
                lines.append(c.box_line(c.dim(meta, enabled), width, enabled))
            if detail >= 2:
                lines.append(c.box_line(c.dim("   " + prov, enabled), width, enabled))
            continue

        # active row — pick the FRESHEST truthful source for THIS window (blend):
        #   5h/session -> local logs (real-time, matches claude code); the web scrape
        #     lags minutes and is deliberately NOT used for this fast-moving number.
        #   weekly/fable/grok-weekly -> authoritative web cap when present, else local proj.
        if is_5h:
            display_pct = (100.0 * f.used / f.cap) if f.cap else 0.0
            row_src = "local"
        elif cell and cell.pct is not None:
            display_pct = cell.pct
            row_src = "web"
        else:
            display_pct = f.projected_pct
            row_src = "proj"
        row_live = row_src in ("local", "web")

        # bar glides toward the true value (anim_pct); the number is always truth
        akey = (p_canon, wkey) if wkey else None
        bar_pct = display_pct
        if anim_pct is not None and akey is not None and akey in anim_pct:
            bar_pct = anim_pct[akey]
        glyph = "●" if row_live else "◌"
        plevel = pulse.get(akey, 0.0) if (pulse and akey) else 0.0
        if plevel > 0:
            glyph = _pulse_glyph(glyph, plevel, enabled)
        bar = _bar(bar_pct, enabled, bar_w)
        pct_num = f"{round(display_pct):3d}%"
        is_key = (wname.lower() in ("weekly", "fable")) and (
            ("grok" in pname.lower() and wname.lower() == "weekly")
            or (pname.lower() in ("claude", "default") and wname.lower() in ("weekly", "fable"))
        )
        pct_str = c.gauge(pct_num, display_pct, enabled)
        if (is_key or is_5h) and enabled:
            pct_str = f"\033[1m{pct_str}\033[0m"

        reset_str = _fmt_reset_abs(f.reset_in_secs, now)
        head = f"{glyph} {wname:<6} {pct_str} {bar} {reset_str}"
        lines.append(c.box_line(head, width, enabled))

        # meta: local token counts; projection for live rows, ETA otherwise
        used_str = f"{fmt_tokens(f.used)}/{fmt_tokens(f.cap)}"
        meta = f"   {used_str}"
        if row_live:
            proj_pct = round(f.projected_pct)
            meta += f"  proj {proj_pct}% end-of-window"
        elif f.eta_to_cap_secs is not None:
            meta += f"  ETA {fmt_dh_long(f.eta_to_cap_secs)}"
        if detail >= 1:
            lines.append(c.box_line(c.dim(meta, enabled), width, enabled))

        # provenance names the ACTUAL source of the head number
        if row_src == "local":
            prov = "local logs · live (this session)"
        elif row_src == "web":
            age = int(cell.age_secs) if getattr(cell, "age_secs", None) is not None else 0
            ex = cell.extractor or ""
            if ex == "header" or ex.startswith("header"):
                base = "live header (Claude Code rate_limits)"
            elif ex.endswith("+retained"):
                base = "retained last-good (probe empty / bot challenge)"
                bare = ex[: -len("+retained")] or "web"
                if bare:
                    base += f" · was {bare}"
            else:
                domain = "claude.ai" if p_canon == "claude" else "grok.com"
                base = f"live {domain}"
                if ex:
                    base += f" · {ex}"
            prov = f"{base} · {age}s ago" if age else base
        elif cell and cell.state in (
            STATE_AUTH_NO_DATA,
            STATE_RATE_DATA_ONLY,
            STATE_STALE,
            STATE_NEEDS_LOGIN,
            STATE_UNAVAILABLE,
            STATE_ERROR,
        ):
            prov = f"local projection — no reliable live data ({cell.state})"
        else:
            prov = "local projection — live disabled"
        if detail >= 2:
            lines.append(c.box_line(c.dim("   " + prov, enabled), width, enabled))

    lines.append(c.box_bot(width, enabled))
    return lines


def render_frame(
    forecasts,
    now,
    color=None,
    cells=None,
    probe_log=None,
    size=None,
    snapshot=None,
    anim_pct=None,
    pulse=None,
):
    """Fixed-region dashboard frame (plan 034).

    Layout is always exactly:
      header (2) + alert (1 blank/reserved) + panels (shape-dependent but fixed)
      + activity (3) + footer (1)

    The displayed % is live when cell.pct is not None, else local projection.
    Returns list[str] (use render_frame_str for tests expecting joined str).
    Drops prev_forecasts/live_status (reset detection stays in run()).
    snapshot (optional) used for rate_info chips.
    """
    enabled = c.color_enabled() if color is None else color

    groups = {}
    for f in forecasts or []:
        p = getattr(f, "profile", "default")
        groups.setdefault(p, []).append(f)

    # width: honor explicit size if passed; default wide enough for boxes.
    # arrange_w used for layout decision so size=None (w=80 for render) still
    # picks the pre-change geometry (box 60 side-by-side) => Scene.render(80)
    # truncation yields byte-identical bytes for the guard test.
    if size is not None and hasattr(size, "columns"):
        w = max(1, int(getattr(size, "columns", 80)))
        arrange_w = w
    else:
        w = 80
        arrange_w = 999

    # Freshest glance number per provider = local 5h current-usage (real-time),
    # so the header chip matches the panel's 5h head (not the slow web scrape).
    local_5h_by: dict[str, float] = {}
    for pn, fs in (groups or {}).items():
        canon = "grok" if "grok" in pn.lower() else "claude"
        for f in fs:
            wn = (getattr(f, "window", "") or "").lower()
            if (
                ("5h" in wn or "session" in wn or "current" in wn)
                and not getattr(f, "idle", False)
                and getattr(f, "cap", 0)
            ):
                local_5h_by[canon] = 100.0 * f.used / f.cap

    def header_fill() -> list[str]:
        title = f"{c.M_ORACLE} token-oracle"
        # compact per-provider chips (inferred from cells; rate via rate_info when snapshot given)
        prov_map: dict[str, list] = {}
        for (pc, _wk), cell in (cells or {}).items():
            prov_map.setdefault(pc, []).append(cell)
        rinfo = rate_info(snapshot) if snapshot is not None else {}
        chips: list[str] = []
        for pc in ("claude", "grok"):
            cs = prov_map.get(pc, [])
            live_c = next((cc for cc in cs if getattr(cc, "pct", None) is not None), None)
            stt = getattr(cs[0], "state", STATE_UNAVAILABLE) if cs else STATE_UNAVAILABLE
            if live_c is not None:
                # Binding-first chip: show the highest local window % for this
                # provider (not just 5h), so short "tiny" terminals keep the
                # number closest to cap. Fall back to live cell, then local 5h.
                local_max = None
                for pn, pfs in (groups or {}).items():
                    pcan = "grok" if "grok" in pn.lower() else "claude"
                    if pcan != pc:
                        continue
                    for ff in pfs:
                        if getattr(ff, "idle", False) or not getattr(ff, "cap", 0):
                            continue
                        p = 100.0 * ff.used / ff.cap
                        local_max = p if local_max is None else max(local_max, p)
                if local_max is not None:
                    pct = int(round(local_max))
                else:
                    l5 = local_5h_by.get(pc)
                    pct = int(round(l5)) if l5 is not None else int(live_c.pct)
                chips.append(f"{pc} ● live {pct}%")
            elif stt == STATE_RATE_DATA_ONLY:
                ri = rinfo.get(pc, {})
                used = ri.get("used_pct")
                if used is not None:
                    chips.append(f"{pc} ▲ rate {int(used)}%")
                else:
                    chips.append(f"{pc} ▲ rate-only")
            else:
                chips.append(f"{pc} ◌ no data ({stt})")
        status = "  •  ".join(chips)
        return [c.violet(title, enabled), c.dim(status, enabled)]

    def alert_fill() -> list[str]:
        # Reserved 1-line slot for reset alarm (populated by run() via its scene fills)
        return [""]

    def panels_fill(detail: int = 2) -> list[str]:
        if not groups:
            return [c.dim("(no windows / no data — run with active usage)", enabled)]
        pnames = list(groups.keys())
        out: list[str] = []
        mode, box_w, bar_w = _panels_arrangement(groups, arrange_w)
        if mode == "side":
            left = _render_profile_block(
                pnames[0],
                groups[pnames[0]],
                now,
                enabled,
                cells,
                width=box_w,
                detail=detail,
                anim_pct=anim_pct,
                pulse=pulse,
                bar_w=bar_w,
            )
            right = _render_profile_block(
                pnames[1],
                groups[pnames[1]],
                now,
                enabled,
                cells,
                width=box_w,
                detail=detail,
                anim_pct=anim_pct,
                pulse=pulse,
                bar_w=bar_w,
            )
            maxl = max(len(left), len(right))
            left += [" " * box_w] * (maxl - len(left))
            right += [" " * box_w] * (maxl - len(right))
            for lline, rline in zip(left, right, strict=False):
                out.append(lline + "   " + rline)
        elif mode == "stack":
            for pn in sorted(pnames):
                blk = _render_profile_block(
                    pn,
                    groups[pn],
                    now,
                    enabled,
                    cells,
                    width=box_w,
                    detail=detail,
                    anim_pct=anim_pct,
                    pulse=pulse,
                    bar_w=bar_w,
                )
                out.extend(blk)
                out.append("")
        elif mode == "bars":
            for pn in sorted(pnames):
                out.extend(_render_profile_bars(pn, groups[pn], now, enabled, cells, box_w, bar_w))
                out.append("")
        else:
            # oneline (width too narrow for even a minimal bar)
            return compact_fill()
        return out

    def compact_fill() -> list[str]:
        if not groups:
            return [c.dim("(no data)", enabled)]
        clines = [
            _compact_profile_line(pn, groups[pn], now, enabled, cells, w) for pn in sorted(groups)
        ]
        return clines

    def glance_fill() -> list[str]:
        if not groups:
            return [c.dim(f"{c.M_ORACLE} token-oracle  (no data)", enabled)]
        scored = []  # (pct, rendered) — pct-first text so the % survives truncation
        for pn in sorted(groups):
            best = None  # (pct, short)
            p_canon = "grok" if "grok" in pn.lower() else "claude"
            for f in groups[pn]:
                if bool(getattr(f, "idle", False)):
                    continue
                ww = (f.window or "").lower()
                if "5h" in ww or "session" in ww or "current" in ww:
                    pct = (100.0 * f.used / f.cap) if getattr(f, "cap", 0) else 0.0
                    short = "5h"
                else:
                    wkey = (
                        "weekly"
                        if ww in ("weekly", "week")
                        else ("fable" if ww == "fable" else None)
                    )
                    cell = (cells or {}).get((p_canon, wkey)) if wkey else None
                    pct = cell.pct if (cell and cell.pct is not None) else f.projected_pct
                    short = "wk" if ww in ("weekly", "week") else (ww or "?")
                if best is None or float(pct) > best[0]:
                    best = (float(pct), short)
            if best is not None:
                scored.append((best[0], c.gauge(f"{round(best[0])}% {best[1]}", best[0], enabled)))
        scored.sort(key=lambda t: t[0], reverse=True)  # binding (highest %) first
        items = [rendered for _, rendered in scored]
        prefix = c.violet(f"{c.M_ORACLE} ", enabled)
        return [_fit_join(prefix, items, w)]

    def activity_fill() -> list[str]:
        log = list(probe_log or [])[:3]
        out: list[str] = []
        for ln in log:
            s = ln[:76] if len(ln) > 76 else ln
            out.append(c.dim("  " + s, enabled))
        while len(out) < ACTIVITY_H:
            out.append(c.dim("", enabled))
        return out

    def footer_fill() -> list[str]:
        # Key hints live on the tab shell footer (run()); keep a short clock here
        # for levels that still include the scene footer region.
        ts = time.strftime("%H:%M:%S")
        return [c.dim(f"sources: claude_code + grok  •  ←/→ tabs · q quit  •  {ts}", enabled)]

    # Height ladder: pick the richest level whose total height fits the terminal.
    # size None (tests / non-interactive) => avail_h 0 => always FULL (unchanged).
    #   full    header+alert+panels(3/row)+activity+footer   (the original layout)
    #   meta    header+alert+panels(2/row)+footer            (drop provenance + activity)
    #   heads   header+alert+panels(1/row)+footer            (key % rows only)
    #   oneline header+alert+one compact line per profile    (no boxes)
    #   tiny    header only (title + live summary chip)
    #   glance  single-line 🔮 worst-per-provider floor      (when < HEADER_H rows)
    def _regions_for(level: str) -> list["Region"]:
        if level == "full":
            return [
                Region("header", HEADER_H, header_fill),
                Region("alert", ALERT_H, alert_fill),
                Region("panels", panel_height(groups, 2, arrange_w), lambda: panels_fill(2)),
                Region("activity", ACTIVITY_H, activity_fill),
                Region("footer", FOOTER_H, footer_fill),
            ]
        if level == "meta":
            return [
                Region("header", HEADER_H, header_fill),
                Region("alert", ALERT_H, alert_fill),
                Region("panels", panel_height(groups, 1, arrange_w), lambda: panels_fill(1)),
                Region("footer", FOOTER_H, footer_fill),
            ]
        if level == "heads":
            return [
                Region("header", HEADER_H, header_fill),
                Region("alert", ALERT_H, alert_fill),
                Region("panels", panel_height(groups, 0, arrange_w), lambda: panels_fill(0)),
                Region("footer", FOOTER_H, footer_fill),
            ]
        if level == "bars_only":
            # Narrow bars without alert/activity/footer — keeps sliders when
            # short×narrow would otherwise fall through to compact text.
            return [
                Region("header", HEADER_H, header_fill),
                Region("panels", panel_height(groups, 0, arrange_w), lambda: panels_fill(0)),
            ]
        if level == "oneline":
            clines = compact_fill()
            return [
                Region("header", HEADER_H, header_fill),
                Region("alert", ALERT_H, alert_fill),
                Region("compact", len(clines), lambda: clines),
            ]
        if level == "glance":
            return [Region("glance", 1, glance_fill)]
        return [Region("header", HEADER_H, header_fill)]  # tiny

    avail_h = int(getattr(size, "lines", 0) or 0) if size is not None else 0
    arrange_mode, _, _ = _panels_arrangement(groups, arrange_w)
    # When width is in the bars band, try bars_only before compact text so short
    # terminals keep sliders (F-A11-1).
    if arrange_mode == "bars":
        ladder = ("full", "meta", "heads", "bars_only", "oneline", "tiny", "glance")
    else:
        ladder = ("full", "meta", "heads", "oneline", "tiny", "glance")
    for level in ladder:
        regs = _regions_for(level)
        total = sum(r.height for r in regs)
        if avail_h == 0 or total <= avail_h:
            out = Scene(regs).render(w)
            return out[:avail_h] if avail_h else out
    # Even tiny overflows a tiny terminal: hard-truncate the header.
    return Scene(_regions_for("tiny")).render(w)[: max(1, avail_h)]


def render_frame_str(
    forecasts,
    now,
    color=None,
    cells=None,
    probe_log=None,
    size=None,
    snapshot=None,
    anim_pct=None,
    pulse=None,
):
    """Join wrapper for test convenience (old call sites expect str)."""
    return "\n".join(
        render_frame(
            forecasts,
            now,
            color=color,
            cells=cells,
            probe_log=probe_log,
            size=size,
            snapshot=snapshot,
            anim_pct=anim_pct,
            pulse=pulse,
        )
    )


def _inject_tab_bar(lines: list[str], active: str, width: int, enabled: bool) -> list[str]:
    """Replace the first header line with the tab bar (keeps chips / body)."""
    bar = render_tab_bar(active, width, enabled)
    if not lines:
        return [bar]
    out = list(lines)
    out[0] = bar
    return out


def _paint_tab_frame(active_tab, body, w, enabled, footer_extra=None):
    """Tab chrome around a body panel (past/future/skeleton)."""
    lines = [
        render_tab_bar(active_tab, w, enabled),
        c.dim("─" * min(w, 60), enabled),
    ]
    if footer_extra:
        lines.append(footer_extra)
    lines.extend(body)
    lines.append("")
    lines.append(render_footer(w, enabled))
    return lines


def run(cfg):
    """Live dashboard: instant tab shell + background data worker.

    Architecture (web conventions, terminal edition):
      * UI thread — only keys + paint. Never runs forecast / ledger / cache I/O.
      * Data worker — forecast, past ledger, future extras; publishes to DashStore.
      * Stale-while-revalidate — last good frame stays visible while refresh runs.
      * Skeletons — first visit to a tab shows placeholders until data arrives.

    Why: on a large history, forecast alone can take ~10s; blocking the UI thread
    made ←/→ lag. Detaching I/O restores fluent tab switching regardless of
    network or log size. Live probe stays in its own daemon (plan 033).

    Non-tty (piped): present-only, no keys/alt-screen, ~2s sync refresh.
    """
    active_tab = "present"
    kr = key_reader()
    interactive = kr is not None and bool(getattr(sys.stdout, "isatty", lambda: False)())
    store = DashStore()
    stop = threading.Event()

    # Probe stderr ring (activity region on present) — independent of forecast.
    last_probe_result = {"st": None, "stderr_tail": deque(maxlen=3)}

    def _probe_worker():
        try:
            while not stop.is_set():
                blessed = os.path.expanduser("~/.local/share/token-oracle/venv/bin/oracle")
                if os.path.isfile(blessed) and os.access(blessed, os.X_OK):
                    cmd = [blessed, "live-probe", "--json"]
                else:
                    cmd = [sys.executable, "-m", "token_oracle.cli.main", "live-probe", "--json"]
                try:
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
                    out = (proc.stdout or "").strip()
                    err = (proc.stderr or "").strip()
                    tail = [ln for ln in err.splitlines() if ln.strip()][-3:]
                    snap = None
                    if out:
                        try:
                            snap = json.loads(out)
                        except Exception:
                            snap = None
                    last_probe_result["st"] = snap
                    last_probe_result["stderr_tail"] = deque(tail, maxlen=3)
                except Exception:
                    pass
                stop.wait(LIVE_PROBE_INTERVAL)
        except Exception:
            pass

    def _data_worker():
        """Heavy path off the UI thread. Present first, then past/future.

        Stale-while-revalidate: once a tab has data, refreshes are silent
        (no loading banner) so height does not thrash and the top does not flash.
        One load_cache serves both past and future extras.
        """
        from ..core.cache import load_cache

        past_every = TAB_DATA_TTL
        last_past_t = 0.0
        while not stop.is_set():
            cycle_start = time.time()
            now = cycle_start
            snap0 = store.snapshot()

            # --- present (forecast) — publish ASAP for instant home tab ---
            if not snap0.has_present:
                store.set_loading("present", True)
            try:
                prev = store.take_prev_forecasts()
                fs = run_forecast(now, cfg)
                snap = load_snapshot() or {}
                cells = overlay_cells(fs, snap, now)
                resets = detect_resets(prev, fs) if prev is not None else []
                store.set_prev_forecasts(fs)
                rmsg, runtil = "", 0.0
                if resets:
                    names = ", ".join(sorted({f"{r['profile']}:{r['window']}" for r in resets}))
                    rmsg = f"{c.M_RESET} Your reset happened — {names}  (limits refreshed!)"
                    runtil = now + 6.0
                store.publish_present(fs, cells, snap, reset_msg=rmsg, reset_until=runtil)
            except Exception as e:
                store.publish_error(f"forecast failed: {e}")
                store.set_loading("present", False)

            # --- past + future (shared cache; silent if already shown once) ---
            need_aux = (now - last_past_t) >= past_every or not store.snapshot().has_past
            if need_aux:
                had_past = store.snapshot().has_past
                if not had_past:
                    store.set_loading("past", True)
                    store.set_loading("future", True)
                try:
                    cache = load_cache(getattr(cfg, "cache_path", "") or "") or {}
                except Exception:
                    cache = {}
                try:
                    sections = _past_sections_for_dash(cfg, now, days=PAST_DAYS, cache=cache)
                    store.publish_past(sections)
                except Exception:
                    store.publish_past([])
                try:
                    # Flatten profile events once for cost pace (avoid 2nd full load)
                    flat = []
                    if isinstance(cache.get("profiles"), dict):
                        for slc in cache["profiles"].values():
                            if isinstance(slc, dict):
                                flat.extend(slc.get("events") or [])
                    flat.extend(cache.get("events") or [])
                    prof, cline = _future_extras(cfg, now, cache=cache, events=flat)
                    store.publish_future(prof, cline)
                except Exception:
                    store.publish_future(None, None)
                last_past_t = now
            else:
                store.set_loading("past", False)
                store.set_loading("future", False)

            elapsed = time.time() - cycle_start
            # Present-only cycles can be snappy; still yield the GIL.
            stop.wait(max(0.2, 1.0 - elapsed))

    if interactive:
        threading.Thread(target=_probe_worker, daemon=True, name="live-probe-worker").start()
        threading.Thread(target=_data_worker, daemon=True, name="dash-data-worker").start()

    # Present-tab animation state lives only on the UI thread.
    disp: dict = {}
    prev_target: dict = {}
    pulse_start: dict = {}
    spin_i = 0
    prev_tab = active_tab

    key_cm = kr if kr is not None else _NullCM()
    try:
        with key_cm, Painter() as painter:
            try:
                while True:
                    now = time.time()
                    size = shutil.get_terminal_size((80, 24))
                    w = max(1, int(size.columns))
                    enabled = c.color_enabled()
                    spin = spinner_char(spin_i)
                    spin_i += 1

                    # ---- keys: always first, never blocked by data ----
                    if kr is not None:
                        for key in kr.poll(0.0):
                            nxt = _apply_tab_key(active_tab, key)
                            if nxt is None:
                                stop.set()
                                return 0
                            active_tab = nxt

                    tab_changed = active_tab != prev_tab
                    if tab_changed:
                        prev_tab = active_tab

                    if not interactive:
                        # Piped path: original sync present-only loop.
                        fs = run_forecast(now, cfg)
                        snap = load_snapshot() or {}
                        cells = overlay_cells(fs, snap, now)
                        base = render_frame(
                            fs, now, color=None, cells=cells, snapshot=snap, size=size
                        )
                        painter.paint(base)
                        time.sleep(2.0)
                        continue

                    st = store.snapshot()
                    show_cost = (getattr(cfg, "cost_mode", "auto") or "auto") != "off"
                    animating = False

                    if active_tab == "present":
                        if not st.has_present:
                            body = render_skeleton(
                                "present",
                                w,
                                enabled,
                                spin=spin,
                                hint="reading local logs (first load can take a bit)…",
                            )
                            painter.paint(
                                _paint_tab_frame(active_tab, body, w, enabled),
                                force_clear=tab_changed,
                            )
                        else:
                            curr = st.forecasts
                            cells = st.cells
                            snap = st.snap
                            probe_log = list(last_probe_result.get("stderr_tail") or [])
                            targets = _active_row_targets(curr, cells)
                            for k, tgt in targets.items():
                                if k not in disp:
                                    disp[k] = tgt
                                    prev_target[k] = tgt
                                    continue
                                if abs(tgt - prev_target.get(k, tgt)) >= CHANGE_EPS:
                                    pulse_start[k] = now
                                prev_target[k] = tgt
                                d = disp[k]
                                if abs(tgt - d) < SETTLE_EPS:
                                    disp[k] = tgt
                                else:
                                    disp[k] = d + (tgt - d) * EASE
                                    animating = True
                            for k in list(disp.keys()):
                                if k not in targets:
                                    disp.pop(k, None)
                                    prev_target.pop(k, None)
                                    pulse_start.pop(k, None)
                            pulse: dict = {}
                            for k, pst in list(pulse_start.items()):
                                lv = _pulse_level(pst, now)
                                if lv > 0:
                                    pulse[k] = lv
                                    animating = True
                                else:
                                    pulse_start.pop(k, None)

                            base = render_frame(
                                curr,
                                now,
                                color=None,
                                cells=cells,
                                probe_log=probe_log,
                                snapshot=snap,
                                size=size,
                                anim_pct=disp,
                                pulse=pulse,
                            )
                            base = _inject_tab_bar(base, active_tab, w, enabled)
                            if st.reset_msg and now < st.reset_until and len(base) > HEADER_H:
                                base[HEADER_H] = c.pulse(c.violet(st.reset_msg, enabled), enabled)
                                animating = True
                            # No loading banner insert after first paint (height thrash)
                            painter.paint(base, force_clear=tab_changed)
                    elif active_tab == "past":
                        if not st.has_past:
                            body = render_skeleton(
                                "past",
                                w,
                                enabled,
                                spin=spin,
                                hint="building the daily ledger from cached events…",
                            )
                        else:
                            body = render_past_sections(
                                st.past_sections or [],
                                w,
                                enabled,
                                days=PAST_DAYS,
                                show_cost=show_cost,
                            )
                            # Silent SWR — do not prepend banner (was +1 line → flicker)
                        painter.paint(
                            _paint_tab_frame(active_tab, body, w, enabled),
                            force_clear=tab_changed,
                        )
                    else:  # future
                        if not st.has_future and not st.has_present:
                            body = render_skeleton(
                                "future",
                                w,
                                enabled,
                                spin=spin,
                                hint="waiting on forecast + burn profile…",
                            )
                        else:
                            body = render_future(
                                st.forecasts if st.has_present else [],
                                st.profile,
                                now,
                                w,
                                enabled,
                                cost_line=st.cost_line,
                                cells=st.cells,
                            )
                        painter.paint(
                            _paint_tab_frame(active_tab, body, w, enabled),
                            force_clear=tab_changed,
                        )

                    # Short UI tick — keys polled again next loop. Keep ~15–20 fps
                    # when animating; ~10 fps idle is plenty for a live clock.
                    sleep_s = FAST_DT if animating else 0.1
                    end = time.time() + sleep_s
                    while time.time() < end:
                        remaining = end - time.time()
                        if remaining <= 0:
                            break
                        switched = False
                        for key in kr.poll(min(0.05, remaining)):
                            nxt = _apply_tab_key(active_tab, key)
                            if nxt is None:
                                stop.set()
                                return 0
                            if nxt != active_tab:
                                active_tab = nxt
                                switched = True
                                break
                        if switched:
                            break
            except KeyboardInterrupt:
                stop.set()
                return 0
    finally:
        stop.set()
    return 0


class _NullCM:
    """No-op context manager when key input is unavailable."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return None

    def poll(self, timeout=0.25):
        return []
