"""Stdlib TUI over the Forecast list. render_frame is pure (tested); run() is the
refresh loop. Enhanced for multi-sub (Claude + Grok side-by-side), rich boxes,
progress, and RESET alarm animations that people will remember."""

import json
import os
import subprocess
import sys
import threading
import time

from ..cli import colors as c
from ..core.engine import detect_resets
from ..core.engine import forecast as run_forecast
from ..core.timeutil import fmt_dh_long, fmt_reset, fmt_tokens
from ..live import web as lw
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

from .scene import Region, Scene, strip_ansi

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


def _panel_block_height(n_windows: int) -> int:
    """Top + bottom + exactly 3 lines per window (head/meta/provenance)."""
    n = max(1, int(n_windows or 1))
    return 2 + 3 * n


def panel_height(groups: dict) -> int:
    """Compute the panels region height for the current groups shape.

    Side-by-side when exactly two profiles with equal window counts: use the
    block height of one (shorter is padded in render). Stacked otherwise.
    The value is independent of per-frame data content.
    """
    if not groups:
        return _panel_block_height(1)  # (no data) padded block
    pnames = list(groups.keys())
    if len(pnames) == 2 and len(groups[pnames[0]]) == len(groups[pnames[1]]):
        n = len(groups[pnames[0]])
        return _panel_block_height(n)
    total = 0
    for pn, fs in groups.items():
        n = len(fs) or 1
        total += _panel_block_height(n)
        total += 1  # inter-block gap line
    return total


def _row_glyph(cell, is_idle: bool) -> str:
    """Glyph encoding provenance origin for the head line (per plan 034 3-line contract)."""
    if is_idle:
        return "–"
    if cell is not None and getattr(cell, "pct", None) is not None:
        return "●"
    return "◌"


def _render_profile_block(pname, forecasts, now, enabled, cells=None, width=66):
    """Render a boxed panel using fixed 3-line rows (head/meta/provenance).

    Every window (idle or active) contributes exactly 3 lines after top/bot.
    The displayed % is live (from cell.pct) when available, else local projection.
    Glyphs: ● live, ◌ local projection, – idle.
    Meta and provenance explicitly distinguish live vs local; "live"/"real data"
    wording only appears for rows where cell.pct is not None.
    """
    icon = _profile_icon(pname)
    title = f"{icon} {pname.upper()}"
    if "grok" in pname.lower():
        title += "  SuperGrok Heavy"
    elif pname.lower() in ("claude", "default"):
        title += "  Max20x + cloud"
    lines = [c.violet(c.box_top(title, width, enabled), enabled)]
    if not forecasts:
        # (no data) block padded to exactly 3 lines for height invariance
        lines.append(c.box_line(c.dim("(no data)", enabled), width, enabled))
        lines.append(c.box_line(c.dim("", enabled), width, enabled))
        lines.append(c.box_line(c.dim("", enabled), width, enabled))
        lines.append(c.box_bot(width, enabled))
        return lines

    cells = cells or {}
    p_canon = "grok" if "grok" in pname.lower() else "claude"

    for f in sorted(forecasts, key=lambda x: x.window):
        wname = f.window
        is_idle = bool(getattr(f, "idle", False))
        is_5h = (
            "5h" in wname.lower() or "session" in wname.lower() or "current" in wname.lower()
        )
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
            # idle head: always show idle + reset (even 5h); special state_value only affects meta/provenance
            reset_str = _fmt_reset_abs(f.reset_in_secs, now)
            head = f"{glyph} {wname:<6} idle  resets {reset_str}"
            lines.append(c.box_line(head, width, enabled))

            if is_5h and cell and cell.state_value == "starts_on_first_message":
                # ONLY website phrasing when the cell carries the state (plan 034 + 030)
                meta = "   (5h window activates on first use; resets 5h later)"
                lines.append(c.box_line(c.dim(meta, enabled), width, enabled))
                age = int(cell.age_secs) if getattr(cell, "age_secs", None) is not None else 0
                # avoid "live" wording when this row does not carry a live pct number (0% placeholder)
                prov = f"5h — from claude.ai ({age}s ago)" if age else "5h — from claude.ai"
                lines.append(c.box_line(c.dim("   " + prov, enabled), width, enabled))
            elif is_5h:
                meta = "   5h — no recent activity (live web gives exact after login)"
                lines.append(c.box_line(c.dim(meta, enabled), width, enabled))
                prov = "local projection — no reliable live data (unavailable)"
                lines.append(c.box_line(c.dim("   " + prov, enabled), width, enabled))
            else:
                # blank meta + honest local prov for ordinary idle windows
                lines.append(c.box_line(c.dim("", enabled), width, enabled))
                prov = "local projection — live disabled"
                lines.append(c.box_line(c.dim("   " + prov, enabled), width, enabled))
            continue

        # active (or non-idle) row: display_pct prefers live cell.pct when present
        if cell and cell.pct is not None:
            display_pct = cell.pct
        else:
            display_pct = f.projected_pct

        bar = _bar(display_pct, enabled, BAR_W)
        pct_num = f"{round(display_pct):3d}%"
        is_key = (wname.lower() in ("weekly", "fable")) and (
            ("grok" in pname.lower() and wname.lower() == "weekly")
            or (pname.lower() in ("claude", "default") and wname.lower() in ("weekly", "fable"))
        )
        pct_str = c.gauge(pct_num, display_pct, enabled)
        if (is_key or wname.lower() in ("5h", "session")) and enabled:
            pct_str = f"\033[1m{pct_str}\033[0m"

        reset_str = _fmt_reset_abs(f.reset_in_secs, now)
        head = f"{glyph} {wname:<6} {pct_str} {bar} {reset_str}"
        lines.append(c.box_line(head, width, enabled))

        # meta: always local tokens; when live shown, also show the distinct local proj
        used_str = f"{fmt_tokens(f.used)}/{fmt_tokens(f.cap)}"
        meta = f"   {used_str}"
        if cell and cell.pct is not None:
            # live number shown in head; also surface the local projection explicitly
            proj_pct = round(f.projected_pct)
            meta += f"  proj {proj_pct}% end-of-window"
        elif f.eta_to_cap_secs is not None:
            meta += f"  ETA {fmt_dh_long(f.eta_to_cap_secs)}"
        lines.append(c.box_line(c.dim(meta, enabled), width, enabled))

        # provenance: exactly the specified forms; "live" wording ONLY when cell.pct is not None
        if cell and cell.pct is not None:
            age = int(cell.age_secs) if getattr(cell, "age_secs", None) is not None else 0
            ex = cell.extractor or ""
            base = f"live {p_canon}.ai"
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
        lines.append(c.box_line(c.dim("   " + prov, enabled), width, enabled))

    lines.append(c.box_bot(width, enabled))
    return lines


def render_frame(forecasts, now, color=None, cells=None, probe_log=None, size=None):
    """Fixed-region dashboard frame (plan 034).

    Layout is always exactly:
      header (2) + alert (1 blank/reserved) + panels (shape-dependent but fixed)
      + activity (3) + footer (1)

    The displayed % is live when cell.pct is not None, else local projection.
    Returns list[str] (use render_frame_str for tests expecting joined str).
    Drops prev_forecasts/live_status (reset detection stays in run()).
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

    def header_fill() -> list[str]:
        title = f"{c.M_ORACLE} token-oracle"
        # compact per-provider chips (inferred from cells; rate detail enhanced in run)
        prov_map: dict[str, list] = {}
        for (pc, _wk), cell in (cells or {}).items():
            prov_map.setdefault(pc, []).append(cell)
        chips: list[str] = []
        for pc in ("claude", "grok"):
            cs = prov_map.get(pc, [])
            live_c = next((cc for cc in cs if getattr(cc, "pct", None) is not None), None)
            stt = getattr(cs[0], "state", STATE_UNAVAILABLE) if cs else STATE_UNAVAILABLE
            if live_c is not None:
                age = int(getattr(live_c, "age_secs", 0) or 0)
                chips.append(f"{pc} ● live {int(live_c.pct)}% ({age}s)")
            elif stt == STATE_RATE_DATA_ONLY:
                chips.append(f"{pc} ▲ rate-only")
            else:
                chips.append(f"{pc} ◌ no data ({stt})")
        status = "  •  ".join(chips)
        return [c.violet(title, enabled), c.dim(status, enabled)]

    def alert_fill() -> list[str]:
        # Reserved 1-line slot for reset alarm (populated by run() via its scene fills)
        return [""]

    def panels_fill() -> list[str]:
        if not groups:
            return [c.dim("(no windows / no data — run with active usage)", enabled)]
        pnames = list(groups.keys())
        out: list[str] = []
        if len(pnames) == 2 and len(groups[pnames[0]]) == len(groups[pnames[1]]):
            left = _render_profile_block(pnames[0], groups[pnames[0]], now, enabled, cells, width=60)
            right = _render_profile_block(pnames[1], groups[pnames[1]], now, enabled, cells, width=60)
            maxl = max(len(left), len(right))
            left += [" " * 60] * (maxl - len(left))
            right += [" " * 60] * (maxl - len(right))
            for lline, rline in zip(left, right, strict=False):
                out.append(lline + "   " + rline)
        else:
            for pn in sorted(pnames):
                blk = _render_profile_block(pn, groups[pn], now, enabled, cells, width=66)
                out.extend(blk)
                out.append("")
        return out

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

    regions = [
        Region("header", HEADER_H, header_fill),
        Region("alert", ALERT_H, alert_fill),
        Region("panels", panel_height(groups), panels_fill),
        Region("activity", ACTIVITY_H, activity_fill),
        Region("footer", FOOTER_H, footer_fill),
    ]
    sc = Scene(regions)
    return sc.render(w)


def render_frame_str(forecasts, now, color=None, cells=None, probe_log=None, size=None):
    """Join wrapper for test convenience (old call sites expect str)."""
    return "\n".join(render_frame(forecasts, now, color=color, cells=cells, probe_log=probe_log, size=size))


def run(cfg):
    """Live refreshing dashboard. Remembers prev state for reset detection + animation.

    Probing happens in a daemon background thread via `oracle live-probe --json`
    (or the blessed venv oracle). This run() only reads the snapshot file and
    renders — no browser launch, no stdout pollution from progress.
    """
    last_fs = None
    last_live_cells = None
    last_live_st = None
    LIVE_PROBE_INTERVAL = 60  # seconds; probes are 10-30s, avoid overlap

    # last_probe_result guarded by simple assignment (daemon worker never prints)
    last_probe_result = {"st": None, "stderr_tail": []}

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
                    last_probe_result["stderr_tail"] = tail
                except Exception:
                    # swallow (timeout, no binary, etc); next cycle will retry
                    pass
                time.sleep(LIVE_PROBE_INTERVAL)
        except Exception:
            # daemon, never surface stack on shutdown
            pass

    # start background prober immediately (daemon)
    worker = threading.Thread(target=_probe_worker, daemon=True, name="live-probe-worker")
    worker.start()

    # first frame uses whatever snapshot exists right now (may be stale/unavailable — honest)
    try:
        while True:
            t = time.time()
            curr = run_forecast(t, cfg)

            # cheap read every frame; overlay decides what to show from provenance
            snap = load_snapshot() or {}
            last_live_cells = overlay_cells(curr, snap, t)

            # derive minimal st for footer/src_note (render_frame untouched)
            provs = snap.get("providers") or {}
            if snap:
                last_live_st = {
                    "grok": (provs.get("grok") or {}).get("state", "unavailable"),
                    "claude": (provs.get("claude") or {}).get("state", "unavailable"),
                    "last_fetch": snap.get("written_at"),
                    "last_attempt": snap.get("written_at"),
                    "delegated": False,
                    "message": "",
                }
            else:
                last_live_st = None

            frame = render_frame(
                curr,
                t,
                prev_forecasts=last_fs,
                live_status=last_live_st,
                cells=last_live_cells,
            )
            footer = c.dim("(ctrl-c to quit)  •  " + time.strftime("%H:%M:%S"), c.color_enabled())
            # Robust redraw: full clear, then draw line-by-line with explicit clear-to-EOL.
            print("\033[2J\033[H", end="")
            for line in (frame + "\n\n" + footer).splitlines():
                print(line + "\033[K", end="\n")
            # reset attributes at end of frame
            print("\033[0m", end="", flush=True)
            last_fs = curr
            time.sleep(1.2)  # snappier for live feel + alarm pulse
    except KeyboardInterrupt:
        return 0
