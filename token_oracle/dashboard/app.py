"""Stdlib TUI over the Forecast list. render_frame is pure (tested); run() is the
refresh loop. Enhanced for multi-sub (Claude + Grok side-by-side), rich boxes,
progress, and RESET alarm animations that people will remember."""

import os
import time

from ..cli import colors as c
from ..core.engine import detect_resets, forecast as run_forecast
from ..core.timeutil import fmt_dh_long, fmt_hms, fmt_reset, fmt_tokens
from ..sources import live_web as lw

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


def _render_profile_block(pname, forecasts, now, enabled, st=None, width=66):
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
    top_authenticated_no_data = (st.get("claude") == "authenticated_no_data" or
                                 st.get("grok") == "authenticated_no_data")

    # Determine once if this block has live web *data* (pcts) available.
    # If top level already says we tried but got no data, skip the per-block fetches
    # (they would just confirm the same and waste time/browser launches).
    block_is_live = False
    cl_live = None
    if top_authenticated_no_data:
        # We know live was attempted globally and produced no numbers.
        block_is_live = False
    else:
        try:
            if lw.PLAYWRIGHT_AVAILABLE:
                cl_live = lw.fetch_claude_live_usage(headless=True)
                gr = lw.fetch_grok_live_usage(headless=True)
                if cl_live and cl_live.get("source") == "claude-web":
                    if cl_live.get("fable_pct") is not None or cl_live.get("all_pct") is not None or cl_live.get("five_hour_state") or cl_live.get("five_hour_pct") is not None:
                        block_is_live = True
                if gr and gr.get("source") == "grok-web" and (gr.get("build_pct") is not None or gr.get("overall_pct") is not None):
                    block_is_live = True
        except Exception:
            block_is_live = False
            cl_live = None

    for f in sorted(forecasts, key=lambda x: x.window):
        wname = f.window
        if f.idle:
            is_5h = "5h" in wname.lower() or "session" in wname.lower() or "current" in wname.lower()
            if is_5h and cl_live and cl_live.get("five_hour_state") == "starts_on_first_message":
                # ONLY show the exact website phrasing when we actually scraped it.
                # Do not fabricate "starts when a message is sent" from local idle alone.
                bar = _bar(0.0, enabled, BAR_W)
                head = f"{c.M_BULLET} {wname:<6}  0% {bar} starts when a message is sent"
                lines.append(c.box_line(head, width, enabled))
                meta = "   (5h window activates on first use; resets 5h later)"
                lines.append(c.box_line(c.dim(meta, enabled), width, enabled))
                prov5 = "5h — live from claude.ai"
                lines.append(c.box_line(c.dim("   " + prov5, enabled), width, enabled))
            elif is_5h:
                # Honest local state: we don't know the exact server message yet.
                line = f"{c.M_BULLET} {wname:<6} idle  resets {_fmt_reset_abs(f.reset_in_secs, now)}"
                lines.append(c.box_line(c.dim(line, enabled), width, enabled))
                lines.append(c.box_line(c.dim("   5h — no recent activity (live web will give exact status after login)", enabled), width, enabled))
            else:
                line = f"{c.M_BULLET} {wname:<6} idle  resets {_fmt_reset_abs(f.reset_in_secs, now)}"
                lines.append(c.box_line(c.dim(line, enabled), width, enabled))
            continue
        pct = f.projected_pct
        bar = _bar(pct, enabled, BAR_W)
        pct_num = f"{round(pct):3d}%"
        # Key windows get BOLD % as requested: SuperGrok weekly, Claude weekly cloud, Fable
        is_key = (wname.lower() in ("weekly", "fable")) and (
            ("grok" in pname.lower() and wname.lower() == "weekly") or
            (pname.lower() in ("claude", "default") and wname.lower() in ("weekly", "fable"))
        )
        pct_str = c.gauge(pct_num, pct, enabled)
        if (is_key or wname.lower() in ("5h", "session")) and enabled:
            pct_str = f"\033[1m{pct_str}\033[0m"

        # PROMINENT first line: window  **XX%**  [bar]   resets in Xm
        reset_str = _fmt_reset_abs(f.reset_in_secs, now)
        # Compact prominent: % bar reset-time all on the main visible line
        head = f"{c.M_BULLET} {wname:<6} {pct_str} {bar} {reset_str}"
        lines.append(c.box_line(head, width, enabled))

        # secondary (dim): tokens + optional ETA
        used_str = f"{fmt_tokens(f.used)}/{fmt_tokens(f.cap)}"
        meta = f"   {used_str}"
        if f.eta_to_cap_secs is not None:
            meta += f"  ETA {fmt_dh_long(f.eta_to_cap_secs)}"
        lines.append(c.box_line(c.dim(meta, enabled), width, enabled))

        # ONE short provenance line (no repeats). Prefer live web labels when we have them.
        # Use pre-fetched cl_live when available to avoid extra work and be consistent.
        prov = ""
        is_live = block_is_live
        try:
            cl = cl_live
            gr = None  # not pre-fetched for gr, but rare to need
            if lw.PLAYWRIGHT_AVAILABLE and cl is None:
                cl = lw.fetch_claude_live_usage(headless=True)
            if cl and cl.get("source") == "claude-web":
                nm = wname.lower()
                if nm == "fable" and cl.get("fable_pct") is not None:
                    is_live = True
                if nm in ("weekly", "week") and cl.get("all_pct") is not None:
                    is_live = True
                if nm in ("5h", "session", "current") and (cl.get("five_hour_state") or cl.get("five_hour_pct") is not None or cl.get("five_hour_reset_in_secs")):
                    is_live = True
            # quick gr check only if needed
            if not is_live and lw.PLAYWRIGHT_AVAILABLE and wname.lower() == "weekly" and "grok" in pname.lower():
                gr = gr or lw.fetch_grok_live_usage(headless=True)
                if gr and gr.get("source") == "grok-web" and (gr.get("build_pct") is not None or gr.get("overall_pct") is not None):
                    is_live = True
        except Exception:
            is_live = False

        if "grok" in pname.lower() and wname.lower() == "weekly":
            base = "Weekly SuperGrok (live from grok.com)" if is_live else "Weekly SuperGrok (local ~/.grok logs)"
            if not is_live and top_live_attempted:
                base += " (live web attempted recently, no data)"
            prov = base
        elif pname.lower() in ("claude", "default"):
            nm = wname.lower()
            if nm in ("weekly", "week"):
                base = "Weekly cloud (All) — live from claude.ai" if is_live else "Weekly cloud (All) — ~/.claude/usage-limits.json anchor"
            elif nm == "fable":
                base = "Fable (model weekly) — live from claude.ai" if is_live else "Fable (model weekly) — bold = real cap + anchor"
            elif nm in ("5h", "session", "current"):
                base = "5h current — live from claude.ai (starts on send when idle)" if is_live else "5h current (server rate limits when avail. / local engine; ticks live)"
            else:
                base = ""
            if not is_live and top_live_attempted and base:
                base += " (live web attempted recently)"
            prov = base
        if prov:
            lines.append(c.box_line(c.dim("   " + prov, enabled), width, enabled))

    lines.append(c.box_bot(width, enabled))
    return lines


def render_frame(forecasts, now, color=None, prev_forecasts=None, live_status=None):
    """Beautiful multi-profile dashboard frame.

    Supports flat list (with .profile tags). Side-by-side for exactly 2 profiles.
    RESET alarm banner with pulse animation that blinks on refreshes.
    """
    enabled = c.color_enabled() if color is None else color
    # group by profile (engine tags them)
    groups = {}
    for f in (forecasts or []):
        p = getattr(f, "profile", "default")
        groups.setdefault(p, []).append(f)

    resets = detect_resets(prev_forecasts, forecasts) if prev_forecasts else []

    lines = []
    # header — make it obvious whether live web succeeded or not
    # Use caller-provided live_status if given (to avoid repeated expensive calls
    # and to allow run() to throttle the live probe rate for smooth updates).
    st = live_status or {}
    if not st:
        try:
            st = lw.get_live_status()
        except Exception:
            st = {"grok": "error", "claude": "error", "message": "status check failed"}

    cl = st.get("claude", "unavailable")
    gr = st.get("grok", "unavailable")
    last = st.get("last_fetch")
    last_attempt = st.get("last_attempt") or last
    delegated = st.get("delegated", False)
    msg = st.get("message", "")

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
            if cl == "authenticated_no_data" or gr == "authenticated_no_data" or cl == "rate_data_only" or gr == "rate_data_only":
                detail = "authenticated, but no usage numbers parsed yet (use TOKEN_ORACLE_LIVE_DEBUG=1 to inspect)"
                if gr == "rate_data_only" or cl == "rate_data_only":
                    detail = "live rate limit data (queries), but no build/weekly usage % (use DEBUG to inspect)"
                header += f"  •  {detail}"
            else:
                header += f"  •  configured (grok={gr} claude={cl})"
        elif lw.PLAYWRIGHT_AVAILABLE:
            # Native playwright available (best case: we are inside the dedicated venv)
            header = f"{c.M_ORACLE} token-oracle  •  live web"
            if cl == "authenticated_no_data" or gr == "authenticated_no_data" or cl == "rate_data_only" or gr == "rate_data_only":
                detail = "authenticated to sites, but no usage numbers parsed yet (TOKEN_ORACLE_LIVE_DEBUG=1 dumps the DOM text)"
                if gr == "rate_data_only" or cl == "rate_data_only":
                    detail = "live rate limit data (queries), but no build/weekly usage % (DEBUG for details)"
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
        elif cl == "authenticated_no_data" or gr == "authenticated_no_data" or cl == "rate_data_only" or gr == "rate_data_only":
            detail = f"authenticated to sites, but no usage numbers extracted yet (grok={gr} claude={cl})"
            if gr == "rate_data_only" or cl == "rate_data_only":
                qrem = st.get("grok_query_remaining") or st.get("claude_query_remaining")
                qtot = st.get("grok_query_total") or st.get("claude_query_total")
                qw = st.get("grok_query_window_secs") or st.get("claude_query_window_secs")
                qinfo = f"queries {qrem}/{qtot}" + (f" per {qw}s" if qw else "") if qrem is not None else ""
                detail = f"live rate limit data only ({qinfo}), no build/weekly usage % (grok={gr} claude={cl})"
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
        left = _render_profile_block(pnames[0], groups[pnames[0]], now, enabled, st, width=60)
        right = _render_profile_block(pnames[1], groups[pnames[1]], now, enabled, st, width=60)
        maxl = max(len(left), len(right))
        left += [" " * 60] * (maxl - len(left))
        right += [" " * 60] * (maxl - len(right))
        for l, r in zip(left, right):
            lines.append(l + "   " + r)
    else:
        for pn in sorted(pnames):
            blk = _render_profile_block(pn, groups[pn], now, enabled, st, width=66)
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
    LIVE_STATUS_INTERVAL = 8  # seconds; live probes are expensive (browser), don't do every 1.2s tick

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
        "message": "starting browser + loading live data..."
    }

    try:
        first_frame = True
        while True:
            t = time.time()
            curr = run_forecast(t, cfg)

            st_for_this_frame = last_live_st or (placeholder_st if first_frame else None)

            # Throttle expensive live probes after the first frame.
            do_probe = (first_frame or
                        last_live_st is None or
                        t - last_live_t > LIVE_STATUS_INTERVAL)
            if do_probe:
                # Silence the step-by-step progress prints from inside the fetch
                # so they don't leak into the live TUI stdout and cause layout shifts.
                # The "checking" placeholder + initial messages already inform the user.
                prev_silent = os.environ.get('TOKEN_ORACLE_SILENT_LIVE_PROBE')
                os.environ['TOKEN_ORACLE_SILENT_LIVE_PROBE'] = '1'
                try:
                    last_live_st = lw.get_live_status()
                except Exception:
                    last_live_st = {"grok": "error", "claude": "error", "message": "status check failed"}
                finally:
                    if prev_silent is None:
                        os.environ.pop('TOKEN_ORACLE_SILENT_LIVE_PROBE', None)
                    else:
                        os.environ['TOKEN_ORACLE_SILENT_LIVE_PROBE'] = prev_silent
                last_live_t = t
                first_frame = False

            frame = render_frame(curr, t, prev_forecasts=last_fs,
                                 live_status=last_live_st or st_for_this_frame)
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
