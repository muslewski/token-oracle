"""Stdlib TUI over the Forecast list. render_frame is pure (tested); run() is the
refresh loop. Enhanced for multi-sub (Claude + Grok side-by-side), rich boxes,
progress, and RESET alarm animations that people will remember."""

import os
import time

from ..cli import colors as c
from ..core.engine import detect_resets
from ..core.engine import forecast as run_forecast
from ..core.timeutil import fmt_dh_long, fmt_reset, fmt_tokens
from ..live import web as lw
from ..live.contract import (
    STATE_AUTH_NO_DATA,
    STATE_NEEDS_LOGIN,
    STATE_RATE_DATA_ONLY,
    STATE_STALE,
    provider_live_to_dict,
)
from ..live.legacy import provider_live_from_legacy
from ..live.overlay import overlay_cells
from ..live.store import save_snapshot

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


def _render_profile_block(pname, forecasts, now, enabled, st=None, cells=None, width=66):
    """Render a nice boxed panel. Prioritize: BIG BOLD % + progress bar + 'resets in Xm'.
    Used numbers and source labels are secondary (dim). Clean, no duplicate titles."""
    icon = _profile_icon(pname)
    title = f"{icon} {pname.upper()}"
    if "grok" in pname.lower():
        title += "  SuperGrok Heavy"
    elif pname.lower() in ("claude", "default"):
        title += "  Max20x + cloud"
    lines = [c.violet(c.box_top(title, width, enabled), enabled)]
    if not forecasts:
        lines.append(c.box_line(c.dim("(no data)", enabled), width, enabled))
        lines.append(c.box_bot(width, enabled))
        return lines

    # Use top-level st (from single get_live_status) to avoid redundant work and
    # to know if a live attempt happened even if this window has no pct data yet.
    st = st or {}
    top_live_attempted = bool(st.get("last_attempt"))

    cells = cells or {}
    p_canon = "grok" if "grok" in pname.lower() else "claude"

    for f in sorted(forecasts, key=lambda x: x.window):
        wname = f.window
        if f.idle:
            is_5h = (
                "5h" in wname.lower() or "session" in wname.lower() or "current" in wname.lower()
            )
            cell = cells.get((p_canon, "5h"))
            if is_5h and cell and cell.state_value == "starts_on_first_message":
                # ONLY show website phrasing for medium+ state; no fabricate from local.
                bar = _bar(0.0, enabled, BAR_W)
                head = f"{c.M_BULLET} {wname:<6}  0% {bar} starts when a message is sent"
                lines.append(c.box_line(head, width, enabled))
                meta = "   (5h window activates on first use; resets 5h later)"
                lines.append(c.box_line(c.dim(meta, enabled), width, enabled))
                age = int(cell.age_secs) if cell and cell.age_secs is not None else 0
                prov5 = (
                    f"5h — live from claude.ai ({age}s ago)" if age else "5h — live from claude.ai"
                )
                lines.append(c.box_line(c.dim("   " + prov5, enabled), width, enabled))
            elif is_5h:
                # Honest local state: we don't know the exact server message yet.
                line = (
                    f"{c.M_BULLET} {wname:<6} idle  resets {_fmt_reset_abs(f.reset_in_secs, now)}"
                )
                lines.append(c.box_line(c.dim(line, enabled), width, enabled))
                lines.append(
                    c.box_line(
                        c.dim(
                            "   5h — no recent activity (live web gives exact after login)",
                            enabled,
                        ),
                        width,
                        enabled,
                    )
                )
            else:
                line = (
                    f"{c.M_BULLET} {wname:<6} idle  resets {_fmt_reset_abs(f.reset_in_secs, now)}"
                )
                lines.append(c.box_line(c.dim(line, enabled), width, enabled))
            continue
        # Derive primary display pct + provenance ONLY from cell (plan 030 contract).
        # Never recompute used from a live pct here.
        wkey = None
        ww = (wname or "").lower()
        if ww in ("weekly", "week"):
            wkey = "weekly"
        elif ww == "fable":
            wkey = "fable"
        elif ww in ("5h", "5-hour", "session", "current"):
            wkey = "5h"
        cell = cells.get((p_canon, wkey)) if wkey else None
        if cell and cell.pct is not None:
            display_pct = cell.pct
        else:
            display_pct = f.projected_pct

        bar = _bar(display_pct, enabled, BAR_W)
        pct_num = f"{round(display_pct):3d}%"
        # Key windows get BOLD % as requested: SuperGrok weekly, Claude weekly cloud, Fable
        is_key = (wname.lower() in ("weekly", "fable")) and (
            ("grok" in pname.lower() and wname.lower() == "weekly")
            or (pname.lower() in ("claude", "default") and wname.lower() in ("weekly", "fable"))
        )
        pct_str = c.gauge(pct_num, display_pct, enabled)
        if (is_key or wname.lower() in ("5h", "session")) and enabled:
            pct_str = f"\033[1m{pct_str}\033[0m"

        # PROMINENT first line: window  **XX%**  [bar]   resets in Xm
        reset_str = _fmt_reset_abs(f.reset_in_secs, now)
        # Compact prominent: % bar reset-time all on the main visible line
        head = f"{c.M_BULLET} {wname:<6} {pct_str} {bar} {reset_str}"
        lines.append(c.box_line(head, width, enabled))

        # secondary (dim): tokens + optional ETA (always from local f)
        used_str = f"{fmt_tokens(f.used)}/{fmt_tokens(f.cap)}"
        meta = f"   {used_str}"
        if f.eta_to_cap_secs is not None:
            meta += f"  ETA {fmt_dh_long(f.eta_to_cap_secs)}"
        lines.append(c.box_line(c.dim(meta, enabled), width, enabled))

        # ONE short provenance line derived only from cell (no direct fetch, no recompute).
        prov = ""
        if cell and cell.pct is not None:
            age = int(cell.age_secs) if cell.age_secs is not None else 0
            prov = f"live from {p_canon} ({age}s ago)"
            if cell.extractor:
                prov += f" [{cell.extractor}]"
        elif cell and cell.state in (
            STATE_AUTH_NO_DATA,
            STATE_RATE_DATA_ONLY,
            STATE_STALE,
            STATE_NEEDS_LOGIN,
        ):
            prov = f"no reliable live data ({cell.state})"
        else:
            # fallback to old-style labels when no cell at all (pure local render)
            if "grok" in pname.lower() and wname.lower() == "weekly":
                prov = "Weekly SuperGrok (local ~/.grok logs)"
            elif pname.lower() in ("claude", "default"):
                nm = wname.lower()
                if nm in ("weekly", "week"):
                    prov = "Weekly cloud (All) — ~/.claude/usage-limits.json anchor"
                elif nm == "fable":
                    prov = "Fable (model weekly) — bold = real cap + anchor"
                elif nm in ("5h", "session", "current"):
                    prov = "5h current (server rate limits when avail. / local engine; ticks live)"
            if not prov and top_live_attempted:
                prov = "live web attempted recently, no reliable data"
        if prov:
            lines.append(c.box_line(c.dim("   " + prov, enabled), width, enabled))

    lines.append(c.box_bot(width, enabled))
    return lines


def render_frame(forecasts, now, color=None, prev_forecasts=None, live_status=None, cells=None):
    """Beautiful multi-profile dashboard frame.

    Supports flat list (with .profile tags). Side-by-side for exactly 2 profiles.
    RESET alarm banner with pulse animation that blinks on refreshes.
    """
    enabled = c.color_enabled() if color is None else color
    # group by profile (engine tags them)
    groups = {}
    for f in forecasts or []:
        p = getattr(f, "profile", "default")
        groups.setdefault(p, []).append(f)

    resets = detect_resets(prev_forecasts, forecasts) if prev_forecasts else []

    lines = []
    # header — make it obvious whether live web succeeded or not
    # Use caller-provided live_status if given (to avoid repeated expensive calls
    # and to allow run() to throttle the live probe rate for smooth updates).
    st = live_status or {}
    if not st:
        # cells=None path for pure tests: do not trigger any fetch here
        st = {
            "grok": "unavailable",
            "claude": "unavailable",
            "message": "no live_status passed (pure render)",
        }

    cl = st.get("claude", "unavailable")
    gr = st.get("grok", "unavailable")
    last = st.get("last_fetch")
    last_attempt = st.get("last_attempt") or last
    delegated = st.get("delegated", False)

    if cl == "ok" and gr == "ok":
        header = f"{c.M_ORACLE} token-oracle  •  LIVE WEB ACTIVE"
        ts = last_attempt or last
        if ts:
            import time as _t

            age = int(_t.time() - ts)
            header += f"  •  real data from grok.com + claude.ai (checked {age}s ago)"
        else:
            header += "  •  real data from grok.com + claude.ai"
        if delegated:
            header += "  [via dedicated venv]"
    elif cl == "ok" or gr == "ok":
        header = f"{c.M_ORACLE} token-oracle  •  live web partial"
        header += f"  •  grok={gr} claude={cl} — run live-setup for the missing one"
    else:
        if delegated:
            # Outer process using the dedicated venv via delegation
            header = f"{c.M_ORACLE} token-oracle  •  live web (via dedicated venv)"
            if (
                cl == "authenticated_no_data"
                or gr == "authenticated_no_data"
                or cl == "rate_data_only"
                or gr == "rate_data_only"
            ):
                detail = (
                    "authenticated, but no usage numbers parsed yet "
                    "(use TOKEN_ORACLE_LIVE_DEBUG=1 to inspect)"
                )
                if gr == "rate_data_only" or cl == "rate_data_only":
                    detail = (
                        "live rate limit data (queries), but no build/weekly "
                        "usage % (use DEBUG to inspect)"
                    )
                header += f"  •  {detail}"
            else:
                header += f"  •  configured (grok={gr} claude={cl})"
        elif lw.PLAYWRIGHT_AVAILABLE:
            # Native playwright available (best case: we are inside the dedicated venv)
            header = f"{c.M_ORACLE} token-oracle  •  live web"
            if (
                cl == "authenticated_no_data"
                or gr == "authenticated_no_data"
                or cl == "rate_data_only"
                or gr == "rate_data_only"
            ):
                detail = (
                    "authenticated to sites, but no usage numbers parsed yet "
                    "(TOKEN_ORACLE_LIVE_DEBUG=1 dumps the DOM text)"
                )
                if gr == "rate_data_only" or cl == "rate_data_only":
                    detail = (
                        "live rate limit data (queries), but no build/weekly "
                        "usage % (DEBUG for details)"
                    )
                header += f"  •  {detail}"
            else:
                header += "  •  ready (no data from live web yet)"
        else:
            header = f"{c.M_ORACLE} token-oracle  •  logs + limits"
            header += "  •  run `oracle live-setup` to enable real web numbers"

    lines.append(c.violet(header, enabled))
    lines.append(c.dim("═" * 58, enabled))

    # Explicit "did live web work?" line so user always knows "it tried"
    # This is the main signal for "did the live web path run on this dash?"
    # Reuse the single st fetched above.
    try:
        live_line = "live web: "
        if cl == "ok" and gr == "ok":
            live_line += "✓ both grok + claude (real data)"
        elif cl == "ok":
            live_line += f"✓ claude  ✗ grok (partial: {gr})"
        elif gr == "ok":
            live_line += f"✗ claude ({cl})  ✓ grok"
        elif (
            cl == "authenticated_no_data"
            or gr == "authenticated_no_data"
            or cl == "rate_data_only"
            or gr == "rate_data_only"
        ):
            detail = (
                f"authenticated to sites, but no usage numbers extracted yet "
                f"(grok={gr} claude={cl})"
            )
            if gr == "rate_data_only" or cl == "rate_data_only":
                qrem = st.get("grok_query_remaining") or st.get("claude_query_remaining")
                qtot = st.get("grok_query_total") or st.get("claude_query_total")
                qw = st.get("grok_query_window_secs") or st.get("claude_query_window_secs")
                qinfo = (
                    f"queries {qrem}/{qtot}" + (f" per {qw}s" if qw else "")
                    if qrem is not None
                    else ""
                )
                detail = (
                    f"live rate limit data only ({qinfo}), no build/weekly "
                    f"usage % (grok={gr} claude={cl})"
                )
            live_line += f"⚠ {detail}"
            live_line += " (TOKEN_ORACLE_LIVE_DEBUG=1 + rerun to dump raw page text)"
        elif cl == "checking" or gr == "checking":
            live_line += "starting browser + loading live data..."
        else:
            live_line += f"✗ no live data (grok={gr} claude={cl})"
        ts = last_attempt
        if ts:
            age = int(time.time() - ts)
            live_line += f"  (last attempt {age}s ago)"
        if delegated:
            live_line += "  [via dedicated venv]"
        elif not lw.PLAYWRIGHT_AVAILABLE and getattr(lw, "_BLESSED_PYTHON", None):
            live_line += "  [via dedicated venv]"
        lines.append(c.dim(live_line, enabled))
    except Exception:
        lines.append(c.dim("live web: status check failed", enabled))
    lines.append("")

    # reset alarm banner (pulses across refreshes) — "Your reset happened"
    if resets:
        names = ", ".join(sorted({f"{r['profile']}:{r['window']}" for r in resets}))
        banner = f"{c.M_RESET} Your reset happened — {names}  (limits refreshed!)"
        lines.append(c.pulse(c.violet(banner, enabled), enabled))
        lines.append("")

    if not groups:
        lines.append(c.dim("(no windows / no data — run with active Claude/Grok usage)", enabled))
        return "\n".join(lines)

    pnames = list(groups.keys())
    # Side-by-side only when both profiles have matching # of windows (avoids ragged boxes).
    # Otherwise stack cleanly (reliable, titles never collide).
    if len(pnames) == 2 and len(groups[pnames[0]]) == len(groups[pnames[1]]):
        left = _render_profile_block(
            pnames[0], groups[pnames[0]], now, enabled, st, cells, width=60
        )
        right = _render_profile_block(
            pnames[1], groups[pnames[1]], now, enabled, st, cells, width=60
        )
        maxl = max(len(left), len(right))
        left += [" " * 60] * (maxl - len(left))
        right += [" " * 60] * (maxl - len(right))
        for left_line, right_line in zip(left, right, strict=False):
            lines.append(left_line + "   " + right_line)
    else:
        for pn in sorted(pnames):
            blk = _render_profile_block(pn, groups[pn], now, enabled, st, cells, width=66)
            lines.extend(blk)
            lines.append("")

    # footer — make live attempt status obvious
    # Reuse st from top of function
    src_note = "claude_code + grok"
    try:
        if cl == "ok" or gr == "ok":
            src_note = "LIVE WEB from websites + local logs"
        elif delegated:
            src_note = "live web via dedicated venv (may need re-auth)"
        elif lw.PLAYWRIGHT_AVAILABLE:
            src_note = "live web (native)"
        else:
            src_note = "local logs + limits (no live web)"
        if last_attempt:
            age = int(time.time() - last_attempt)
            src_note += f" (checked {age}s ago)"
    except Exception:
        src_note = "local logs + limits (status error)"
    extra = c.dim(f"sources: {src_note}  •  bold % = key limits  •  ctrl-c quit", enabled)
    lines.append(extra)
    return "\n".join(lines)


def run(cfg):
    """Live refreshing dashboard. Remembers prev state for reset detection + animation."""
    last_fs = None
    last_live_t = 0
    last_live_st = None
    last_live_cells = None
    LIVE_STATUS_INTERVAL = (
        8  # seconds; live probes are expensive (browser), don't do every 1.2s tick
    )

    # Immediate feedback so the user knows the command is working during slow
    # bootstrap + first browser launch (which can easily take 10-30s every time).
    dim = getattr(c, "dim", lambda s, e=True: s)
    col = c.color_enabled()
    print(dim("⏳ Starting oracle dash...", col))
    print(dim("   Starting browser and fetching live usage from grok.com + claude.ai", col))
    print(dim("   (this usually takes 10–30s; step-by-step progress will be printed)", col))
    print()

    # Fast first paint: show something immediately with a placeholder.
    # Real live status (which can take many seconds on first browser launch) is fetched
    # right after the first frame or on the normal throttle schedule.
    placeholder_st = {
        "grok": "checking",
        "claude": "checking",
        "last_attempt": None,
        "delegated": False,
        "message": "starting browser + loading live data...",
    }

    try:
        first_frame = True
        while True:
            t = time.time()

            # Move silent probe env before run_forecast (belt-and-braces now that engine is pure).
            # The fetchers inside probe still print progress unless silenced.
            prev_silent = os.environ.get("TOKEN_ORACLE_SILENT_LIVE_PROBE")
            os.environ["TOKEN_ORACLE_SILENT_LIVE_PROBE"] = "1"
            try:
                curr = run_forecast(t, cfg)
            finally:
                if prev_silent is None:
                    os.environ.pop("TOKEN_ORACLE_SILENT_LIVE_PROBE", None)
                else:
                    os.environ["TOKEN_ORACLE_SILENT_LIVE_PROBE"] = prev_silent

            st_for_this_frame = last_live_st or (placeholder_st if first_frame else None)

            # Throttle expensive live probes after the first frame.
            do_probe = first_frame or last_live_st is None or t - last_live_t > LIVE_STATUS_INTERVAL
            if do_probe:
                # Silence during the actual legacy fetches (they may still log inside web).
                prev_silent2 = os.environ.get("TOKEN_ORACLE_SILENT_LIVE_PROBE")
                os.environ["TOKEN_ORACLE_SILENT_LIVE_PROBE"] = "1"
                try:
                    g_raw = lw.fetch_grok_live_usage(headless=True)
                    c_raw = lw.fetch_claude_live_usage(headless=True)
                    nowt = time.time()
                    g_pl = provider_live_from_legacy("grok", g_raw, nowt)
                    c_pl = provider_live_from_legacy("claude", c_raw, nowt)
                    providers = {"grok": g_pl, "claude": c_pl}
                    save_snapshot(providers)
                    last_live_st = {
                        "grok": g_pl.state,
                        "claude": c_pl.state,
                        "last_attempt": nowt,
                        "last_fetch": nowt,
                        "delegated": bool(getattr(lw, "_BLESSED_PYTHON", None))
                        and not bool(getattr(lw, "PLAYWRIGHT_AVAILABLE", False)),
                        "message": (g_pl.note or c_pl.note or "")[:120],
                    }
                    snap_dict = {
                        "version": 1,
                        "written_at": nowt,
                        "providers": {
                            "grok": provider_live_to_dict(g_pl),
                            "claude": provider_live_to_dict(c_pl),
                        },
                    }
                    last_live_cells = overlay_cells(curr, snap_dict, nowt)
                except Exception:
                    last_live_st = {
                        "grok": "error",
                        "claude": "error",
                        "message": "status check failed",
                    }
                    last_live_cells = last_live_cells or {}
                finally:
                    if prev_silent2 is None:
                        os.environ.pop("TOKEN_ORACLE_SILENT_LIVE_PROBE", None)
                    else:
                        os.environ["TOKEN_ORACLE_SILENT_LIVE_PROBE"] = prev_silent2
                last_live_t = t
                first_frame = False

            frame = render_frame(
                curr,
                t,
                prev_forecasts=last_fs,
                live_status=last_live_st or st_for_this_frame,
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
