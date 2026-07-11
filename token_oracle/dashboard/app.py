"""Stdlib TUI over the Forecast list. render_frame is pure (tested); run() is the
refresh loop. Enhanced for multi-sub (Claude + Grok side-by-side), rich boxes,
progress, and RESET alarm animations that people will remember."""

import json
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
from .scene import Painter, Region, Scene

BAR_W = 22  # balanced for % + bar + reset time to fit boxes without early truncate


def _bar(pct, enabled, width=BAR_W):
    pct = max(0.0, min(100.0, pct))
    filled = max(0, min(width, int(round(pct / 100.0 * width))))
    bar = "█" * filled + "░" * (width - filled)
    return c.gauge(bar, pct, enabled)


def _profile_icon(profile):
    p = (profile or "").lower()
    if "grok" in p or p == "grok":
        return c.M_GROK
    if "claude" in p or p == "claude" or p == "default":
        return c.M_CLAUDE
    return c.M_ORACLE


def _fmt_reset_abs(reset_in, now):
    # Use friendly format: minutes first, proper d/h for long (no 156:00)
    return fmt_reset(reset_in)


# Fixed-height layout (plan 034): heights depend ONLY on config shape (#windows per profile),
# never on idle/active state or presence of live data. Every window row is exactly 3 lines.
HEADER_H = 2
ALERT_H = 1
ACTIVITY_H = 3
FOOTER_H = 1


def _panel_block_height(n_windows: int, detail: int = 2) -> int:
    """Top + bottom + (detail+1) lines per window row."""
    n = max(1, int(n_windows or 1))
    return 2 + (detail + 1) * n


def panel_height(groups: dict, detail: int = 2) -> int:
    """Compute the panels region height for the current groups shape + detail.

    Side-by-side when exactly two profiles with equal window counts: use the
    block height of one (shorter is padded in render). Stacked otherwise.
    The value is independent of per-frame data content (only shape + detail).
    """
    if not groups:
        return _panel_block_height(1, detail)  # (no data) padded block
    pnames = list(groups.keys())
    if len(pnames) == 2 and len(groups[pnames[0]]) == len(groups[pnames[1]]):
        n = len(groups[pnames[0]])
        return _panel_block_height(n, detail)
    total = 0
    for _pn, fs in groups.items():
        n = len(fs) or 1
        total += _panel_block_height(n, detail)
        total += 1  # inter-block gap line
    return total


def _compact_profile_line(pname, forecasts, now, enabled, cells=None) -> str:
    """One-line summary for a profile (used when the terminal is too short for
    boxes): icon + name + each active window's freshest %. 5h uses local
    real-time usage; caps use the web cell when present, else local projection."""
    cells = cells or {}
    p_canon = "grok" if "grok" in pname.lower() else "claude"
    icon = _profile_icon(pname)
    parts: list[str] = []
    for f in sorted(forecasts, key=lambda x: x.window):
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
        parts.append(f"{short} {round(pct)}%")
    body = " · ".join(parts) if parts else "no active windows"
    return c.dim(f"{icon} {pname.lower()}  {body}", enabled)


def _row_glyph(cell, is_idle: bool) -> str:
    """Glyph encoding provenance origin for the head line (per plan 034 3-line contract)."""
    if is_idle:
        return "–"
    if cell is not None and getattr(cell, "pct", None) is not None:
        return "●"
    return "◌"


def _render_profile_block(pname, forecasts, now, enabled, cells=None, width=66, detail=2):
    """Render a boxed panel. `detail` sets lines per window row (height ladder):
      2 = head + meta + provenance (full), 1 = head + meta, 0 = head only.
    Row count per window is constant for a given detail, preserving height
    invariance within a level. Glyphs: ● live, ◌ local projection, – idle.
    Meta/provenance distinguish live vs local; source wording names the truth.
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

        glyph = "●" if row_live else "◌"
        bar = _bar(display_pct, enabled, BAR_W)
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


def render_frame(forecasts, now, color=None, cells=None, probe_log=None, size=None, snapshot=None):
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

    # width: honor explicit size if passed; default wide enough for boxes
    if size is not None and hasattr(size, "columns"):
        w = max(40, int(getattr(size, "columns", 80)))
    else:
        w = 80

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
                l5 = local_5h_by.get(pc)
                if l5 is not None:
                    chips.append(f"{pc} ● live {int(round(l5))}%")
                else:
                    age = int(getattr(live_c, "age_secs", 0) or 0)
                    chips.append(f"{pc} ● live {int(live_c.pct)}% ({age}s)")
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
        if len(pnames) == 2 and len(groups[pnames[0]]) == len(groups[pnames[1]]):
            left = _render_profile_block(
                pnames[0], groups[pnames[0]], now, enabled, cells, width=60, detail=detail
            )
            right = _render_profile_block(
                pnames[1], groups[pnames[1]], now, enabled, cells, width=60, detail=detail
            )
            maxl = max(len(left), len(right))
            left += [" " * 60] * (maxl - len(left))
            right += [" " * 60] * (maxl - len(right))
            for lline, rline in zip(left, right, strict=False):
                out.append(lline + "   " + rline)
        else:
            for pn in sorted(pnames):
                blk = _render_profile_block(
                    pn, groups[pn], now, enabled, cells, width=66, detail=detail
                )
                out.extend(blk)
                out.append("")
        return out

    def compact_fill() -> list[str]:
        if not groups:
            return [c.dim("(no data)", enabled)]
        return [_compact_profile_line(pn, groups[pn], now, enabled, cells) for pn in sorted(groups)]

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
        ts = time.strftime("%H:%M:%S")
        return [c.dim(f"sources: claude_code + grok  •  ctrl-c quit  •  {ts}", enabled)]

    # Height ladder: pick the richest level whose total height fits the terminal.
    # size None (tests / non-interactive) => avail_h 0 => always FULL (unchanged).
    #   full    header+alert+panels(3/row)+activity+footer   (the original layout)
    #   meta    header+alert+panels(2/row)+footer            (drop provenance + activity)
    #   heads   header+alert+panels(1/row)+footer            (key % rows only)
    #   oneline header+alert+one compact line per profile    (no boxes)
    #   tiny    header only (title + live summary chip)
    def _regions_for(level: str) -> list["Region"]:
        if level == "full":
            return [
                Region("header", HEADER_H, header_fill),
                Region("alert", ALERT_H, alert_fill),
                Region("panels", panel_height(groups, 2), lambda: panels_fill(2)),
                Region("activity", ACTIVITY_H, activity_fill),
                Region("footer", FOOTER_H, footer_fill),
            ]
        if level == "meta":
            return [
                Region("header", HEADER_H, header_fill),
                Region("alert", ALERT_H, alert_fill),
                Region("panels", panel_height(groups, 1), lambda: panels_fill(1)),
                Region("footer", FOOTER_H, footer_fill),
            ]
        if level == "heads":
            return [
                Region("header", HEADER_H, header_fill),
                Region("alert", ALERT_H, alert_fill),
                Region("panels", panel_height(groups, 0), lambda: panels_fill(0)),
                Region("footer", FOOTER_H, footer_fill),
            ]
        if level == "oneline":
            clines = compact_fill()
            return [
                Region("header", HEADER_H, header_fill),
                Region("alert", ALERT_H, alert_fill),
                Region("compact", len(clines), lambda: clines),
            ]
        return [Region("header", HEADER_H, header_fill)]  # tiny

    avail_h = int(getattr(size, "lines", 0) or 0) if size is not None else 0
    for level in ("full", "meta", "heads", "oneline", "tiny"):
        regs = _regions_for(level)
        total = sum(r.height for r in regs)
        if avail_h == 0 or total <= avail_h:
            out = Scene(regs).render(w)
            return out[:avail_h] if avail_h else out
    # Even tiny overflows a tiny terminal: hard-truncate the header.
    return Scene(_regions_for("tiny")).render(w)[: max(1, avail_h)]


def render_frame_str(
    forecasts, now, color=None, cells=None, probe_log=None, size=None, snapshot=None
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
        )
    )


def run(cfg):
    """Live refreshing dashboard using fixed-height scene + Painter (plan 034).

    The 033 probe worker runs in daemon thread and populates the live snapshot
    (via live-probe) + captures its stderr tail for the activity region.
    Every frame: load snapshot -> overlay_cells -> build/repaint via painter.
    Resets feed the alert region (pulsed, then blank) without changing height.
    Full clear ONLY on resize (handled by Painter); in-place \033[K per line.
    """
    last_fs = None
    # Web scrape only feeds the slow authoritative caps (weekly/fable/grok-weekly + reset);
    # the fast 5h/session number comes from local logs every render tick, so we can scrape
    # far less often (heavy Chromium relaunch each time).
    LIVE_PROBE_INTERVAL = 240

    # Ring buffer for probe stderr (routed to activity region). Worker writes lists
    # but we normalize to deque for ring semantics.
    last_probe_result = {"st": None, "stderr_tail": deque(maxlen=3)}

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
                    # keep as deque
                    last_probe_result["stderr_tail"] = deque(tail, maxlen=3)
                except Exception:
                    # swallow; next cycle retries
                    pass
                time.sleep(LIVE_PROBE_INTERVAL)
        except Exception:
            pass

    worker = threading.Thread(target=_probe_worker, daemon=True, name="live-probe-worker")
    worker.start()

    # Wrap entire refresh loop in Painter (alt screen + cursor hidden; restores on any exit)
    with Painter() as painter:
        try:
            while True:
                t = time.time()
                curr = run_forecast(t, cfg)

                snap = load_snapshot() or {}
                cells = overlay_cells(curr, snap, t)
                probe_log = list(last_probe_result.get("stderr_tail") or [])

                # detect resets here (per plan: stays in run, feeds alert region for N ticks)
                resets = detect_resets(last_fs, curr) if last_fs is not None else []

                # render base, adapting detail to the real terminal size (height ladder
                # + true width). base[HEADER_H] is the alert line for every level that
                # keeps the alert region (all but the header-only "tiny" level).
                size = shutil.get_terminal_size((80, 24))
                base = render_frame(
                    curr, t, color=None, cells=cells, probe_log=probe_log, snapshot=snap, size=size
                )
                if resets:
                    names = ", ".join(sorted({f"{r['profile']}:{r['window']}" for r in resets}))
                    banner = f"{c.M_RESET} Your reset happened — {names}  (limits refreshed!)"
                    # alert line is at index HEADER_H (after 2 header lines); keep length
                    if len(base) > HEADER_H:
                        base[HEADER_H] = c.pulse(
                            c.violet(banner, c.color_enabled()), c.color_enabled()
                        )

                painter.paint(base)
                last_fs = curr
                time.sleep(1.2)
        except KeyboardInterrupt:
            # __exit__ of Painter runs on return (restores alt screen + cursor)
            return 0
