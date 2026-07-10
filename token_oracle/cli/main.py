"""oracle CLI: forecast / snapshot / statusline / tmux / doctor / dash.

Source-agnostic: supports claude_code (default), grok (Grok Build), generic, etc.
Set via config "source". tmux/statusline work for all."""

import argparse
import json
import os
import sys
import time

from ..adapters import statusline as sl
from ..adapters import tmux as tx
from ..cli import colors
from ..core.config import PRESETS, default_config_path, load_config, write_default_config
from ..core.engine import forecast as run_forecast
from ..core.profile import HIST_SECS
from ..core.timeutil import fmt_dur
from ..snapshot.writer import build_snapshot, default_snapshot_path, write_snapshot
from ..sources.base import available, get_source


def _add_common(p):
    p.add_argument("--config", default=None)
    p.add_argument("--now", type=float, default=None, help=argparse.SUPPRESS)


def _now(args):
    return args.now if args.now is not None else time.time()


def _doctor_lines(cfg, config_path, color, now):
    avail = available()

    path = config_path or default_config_path()
    if not os.path.exists(os.path.expanduser(path)):
        config_row = ("config", f"{path} (missing — using built-in max20 preset)", True)
    elif cfg.issues:
        config_row = ("config", f"{path} ({len(cfg.issues)} issue(s) — see below)", False)
    else:
        config_row = ("config", path, True)

    # multi-aware data probe
    multi = bool(cfg.profiles)
    try:
        total_files = 0
        total_evs = 0
        last_age = None
        if multi:
            for pname, pdef in cfg.profiles.items():
                src_name = pdef.get("source", cfg.source)
                opts = pdef.get("source_opts", cfg.source_opts or {})
                try:
                    src = get_source(src_name, opts)
                    fs, evs = src.scan({}, now, HIST_SECS)
                    total_files += len(fs)
                    total_evs += len(evs)
                    if evs:
                        age = now - evs[-1][0]
                        if last_age is None or age < last_age:
                            last_age = age
                except Exception:
                    pass
            age_str = f"last {fmt_dur(last_age)} ago" if last_age is not None else "mixed"
            data_row = (
                "data",
                f"profiles={len(cfg.profiles)} · {total_files} files, {total_evs} events, {age_str}",
                total_evs > 0 or True,
            )
        else:
            src = get_source(cfg.source, cfg.source_opts)
            files, events = src.scan({}, now, HIST_SECS)
            if events:
                age = fmt_dur(now - events[-1][0])
                data_row = (
                    "data",
                    f"{len(files)} files, {len(events)} events, last {age} ago",
                    True,
                )
            else:
                data_row = (
                    "data",
                    "no events found in the last 9 weeks — check source settings",
                    False,
                )
    except Exception as e:
        data_row = ("data", f"source probe failed: {e!r}", False)

    cache_path = cfg.cache_path
    if not os.path.exists(cache_path):
        cache_row = ("cache", f"{cache_path} (will be created on first forecast)", True)
    else:
        try:
            with open(cache_path, encoding="utf-8") as fh:
                cache_data = json.load(fh)
            if isinstance(cache_data, dict) and ("files" in cache_data or "profiles" in cache_data):
                age = fmt_dur(now - cache_data.get("lastAggregate", 0))
                cache_row = ("cache", f"{cache_path} (updated {age} ago)", True)
            else:
                cache_row = (
                    "cache",
                    f"{cache_path} (corrupt — will be rebuilt on next forecast)",
                    False,
                )
        except (OSError, ValueError):
            cache_row = (
                "cache",
                f"{cache_path} (corrupt — will be rebuilt on next forecast)",
                False,
            )

    win_desc = f"{len(cfg.windows)} → {[w.name for w in cfg.windows]}"
    if multi:
        win_desc = f"multi-profiles: {list(cfg.profiles.keys())}"
    rows = [
        config_row,
        (
            "source",
            f"{cfg.source} (available: {', '.join(avail)})" + (" [multi]" if multi else ""),
            cfg.source in avail or multi,
        ),
        data_row,
        cache_row,
        ("windows", win_desc, (len(cfg.windows) > 0) or multi),
    ]
    for issue in cfg.issues:
        rows.append(("issue", issue, False))

    out = [colors.violet(f"{colors.M_ORACLE} oracle doctor", color)]
    ok = 0
    for name, detail, good in rows:
        ok += 1 if good else 0
        out.append(f"  {colors.ok_badge(good, color)} {name:<8} — {detail}")
    bad = len(rows) - ok
    out.append(colors.dim(f"  {ok} ok · {bad} need attention", color))
    if multi:
        out.append(colors.dim("  multi mode: both Claude + Grok tracked together", color))
    # show when we are using real cloud caps for claude (the actual source of truth)
    try:
        from token_oracle.core.config import load_claude_limits

        cl = load_claude_limits()
        if cl:
            out.append(
                colors.dim(
                    "  limits   — real caps + weeklyResetAnchor from ~/.claude/usage-limits.json (exact resets)",
                    color,
                )
            )
    except Exception:
        pass

    # Live web status (very visible so you know if it worked / if it tried)
    try:
        from token_oracle.live import web as lw

        print(
            "   → starting browser + loading live pages (step-by-step progress will appear below)..."
        )
        st = lw.get_live_status()
        extra = ""
        ts = st.get("last_attempt") or st.get("last_fetch")
        if ts:
            age = int(time.time() - ts)
            extra = f" (attempted {age}s ago)"
        if st.get("claude") == "ok" and st.get("grok") == "ok":
            out.append(
                colors.dim(
                    f"  live     — ✓ ACTIVE (pulling real % + reset times from the websites){extra}",
                    color,
                )
            )
        elif st.get("claude") == "ok" or st.get("grok") == "ok":
            out.append(
                colors.dim(
                    f"  live     — partial (grok={st.get('grok')} claude={st.get('claude')}){extra}",
                    color,
                )
            )
        elif getattr(lw, "_BLESSED_PYTHON", None) or getattr(lw, "PLAYWRIGHT_AVAILABLE", False):
            cl = st.get("claude", "?")
            gr = st.get("grok", "?")
            is_native = getattr(lw, "PLAYWRIGHT_AVAILABLE", False) and not st.get("delegated")
            prefix = "live web" if is_native else "live web (via dedicated venv)"
            if (
                cl == "authenticated_no_data"
                or gr == "authenticated_no_data"
                or cl == "rate_data_only"
                or gr == "rate_data_only"
            ):
                msg = "authenticated but no usage numbers parsed"
                if gr == "rate_data_only" or cl == "rate_data_only":
                    msg = "live rate limit data (queries) but no build/weekly usage % parsed"
                out.append(
                    colors.dim(f"  {prefix}     — {msg} (grok={gr} claude={cl}){extra}", color)
                )
                out.append(
                    colors.dim(
                        "            → scraper needs work (or re-run live-setup after fresh login)",
                        color,
                    )
                )
                out.append(
                    colors.dim(
                        "            → tip: TOKEN_ORACLE_LIVE_DEBUG=1 oracle doctor ; cat /tmp/token-oracle-*-usage.txt",
                        color,
                    )
                )
                # Try one raw fetch to surface scrape diagnostics (len, pcts_found, note) for immediate grasp
                try:
                    from token_oracle.live import web as lw

                    raw = None
                    if gr in ("authenticated_no_data", "rate_data_only"):
                        raw = lw.fetch_grok_live_usage(headless=True)
                    elif cl in ("authenticated_no_data", "rate_data_only"):
                        raw = lw.fetch_claude_live_usage(headless=True)
                    if raw:
                        # Support both legacy dict (pre-031/032) and native ProviderLive
                        if hasattr(raw, "note"):
                            note = raw.note or ""
                            fu = raw.note  # note often contains landed url
                            extra_info = [f"state={raw.state}"]
                            if note:
                                extra_info.append(str(note)[:70])
                            for r in (raw.readings or [])[:3]:
                                extra_info.append(f"{r.metric}={r.value}")
                        else:
                            note = raw.get("scrape_note") if isinstance(raw, dict) else ""
                            fu = raw.get("final_url") if isinstance(raw, dict) else ""
                            pt = raw.get("page_title") if isinstance(raw, dict) else ""
                            extra_info = []
                            if note:
                                extra_info.append(str(note)[:70])
                            if fu:
                                extra_info.append("url=" + str(fu)[:70])
                            if pt:
                                extra_info.append("title=" + str(pt)[:50])
                            if isinstance(raw, dict) and raw.get("query_remaining") is not None:
                                qrem = raw.get("query_remaining")
                                qtot = raw.get("query_total")
                                qw = raw.get("query_window_secs")
                                extra_info.append(
                                    f"queries {qrem}/{qtot}" + (f" (window {qw}s)" if qw else "")
                                )
                        if extra_info:
                            out.append(
                                colors.dim("            raw: " + " | ".join(extra_info), color)
                            )
                except Exception:
                    pass
            else:
                out.append(
                    colors.dim(f"  {prefix}     — configured (grok={gr} claude={cl}){extra}", color)
                )
                out.append(
                    colors.dim(
                        "            → run `oracle live-setup` to authenticate (or fix scraper)",
                        color,
                    )
                )
        else:
            out.append(colors.dim("  live     — not configured (run `oracle live-setup`)", color))
    except Exception:
        out.append(colors.dim("  live     — status check failed", color))
    return out, bad


def main(argv=None):
    parser = argparse.ArgumentParser(prog="token-oracle")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in (
        "forecast",
        "snapshot",
        "statusline",
        "tmux",
        "doctor",
        "dash",
        "init",
        "clean",
        "live-setup",
    ):
        sp = sub.add_parser(name)
        _add_common(sp)
        if name == "forecast":
            sp.add_argument("--json", action="store_true")
        if name == "snapshot":
            sp.add_argument("--out", default=None)
        if name == "init":
            sp.add_argument("--preset", default="max20", choices=sorted(PRESETS))
            sp.add_argument("--force", action="store_true")
        if name == "clean":
            sp.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    now = _now(args)

    if args.cmd == "init":
        target = os.path.expanduser(args.config or default_config_path())
        existed = os.path.exists(target)
        path = write_default_config(target, preset=args.preset, force=args.force)
        if existed and not args.force:
            print(f"{path} exists — pass --force to overwrite")
        else:
            print(path)
        return 0
    if args.cmd == "clean":
        targets = [
            os.path.expanduser(args.config or default_config_path()),
            cfg.cache_path,
            default_snapshot_path(),
        ]
        if not args.yes:
            print("would remove:")
            for t in targets:
                print(f"  {t}")
            print("re-run with --yes to delete")
            return 1
        for t in targets:
            try:
                os.remove(t)
                print(f"removed {t}")
            except OSError:
                pass
        return 0
    if args.cmd == "forecast":
        fs = run_forecast(now, cfg)
        if args.json:
            print(json.dumps(build_snapshot(fs, now), indent=2))
        else:
            out = sl.render(fs) or "idle"
            if cfg.profiles:
                out = "(multi) " + out
            print(out)
        return 0
    if args.cmd == "snapshot":
        fs = run_forecast(now, cfg)
        path = write_snapshot(fs, now, args.out)
        if path is None:
            print("snapshot: write failed", file=sys.stderr)
            return 1
        print(path)
        return 0
    if args.cmd == "statusline":
        print(sl.render(run_forecast(now, cfg)))
        return 0
    if args.cmd == "tmux":
        print(tx.render(run_forecast(now, cfg)))
        return 0
    if args.cmd == "doctor":
        _bootstrap_playwright_if_needed()
        print("⏳ oracle doctor — running checks")
        print(
            "   (live web: starting browser to read current usage from the sites — expect 10-30s)"
        )
        lines, bad = _doctor_lines(cfg, args.config, colors.color_enabled(), now)
        for line in lines:
            print(line)
        return 0 if bad == 0 else 1
    if args.cmd == "dash":
        # Ensure we are running inside the dedicated venv (with playwright)
        # so that live web status/fetch is native + fast (in-process cache,
        # no repeated expensive delegation subprocess per frame).
        _bootstrap_playwright_if_needed()
        from ..dashboard.app import run as run_dash

        return run_dash(cfg)

    if args.cmd == "live-setup":
        return _live_setup(cfg, args)

    return 1


def _bootstrap_playwright_if_needed():
    """Auto-bootstrap a dedicated venv + playwright + the package so that
    `oracle live-setup` and `oracle dash` "just work" for normal users
    (including on Arch/Manjaro and other externally-managed Pythons).
    """
    import subprocess

    from ..live import web as live_web

    # Never bootstrap (or execve) when running under pytest — it would
    # either hang creating venvs or exec-replace the test runner process.
    if (
        os.environ.get("PYTEST_CURRENT_TEST")
        or "pytest" in sys.modules
        or os.environ.get("TOKEN_ORACLE_SKIP_BOOTSTRAP")
    ):
        return

    if getattr(live_web, "PLAYWRIGHT_AVAILABLE", False):
        return
    if os.environ.get("TOKEN_ORACLE_LIVE_BOOTSTRAPPED"):
        return

    venv_root = os.path.expanduser("~/.local/share/token-oracle/venv")
    venv_py = os.path.join(venv_root, "bin", "python")
    venv_pip = os.path.join(venv_root, "bin", "pip")
    venv_oracle = os.path.join(venv_root, "bin", "oracle")

    if not os.path.exists(venv_py):
        print("→ Creating dedicated environment for live web features...")
        print("   (this only happens once)")
        subprocess.check_call([sys.executable, "-m", "venv", venv_root])

    # playwright
    try:
        subprocess.check_call(
            [venv_py, "-c", "import playwright"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        print("→ Installing playwright + Chromium (this can take a minute or two)...")
        subprocess.check_call([venv_pip, "install", "playwright"])
        subprocess.check_call([venv_py, "-m", "playwright", "install", "chromium"])

    # the token-oracle package (creates the 'oracle' entrypoint in the venv)
    try:
        subprocess.check_call(
            [venv_py, "-c", "import token_oracle"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        print("→ Installing token-oracle (with live support) into the dedicated env ...")
        here = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if os.path.exists(os.path.join(here, "pyproject.toml")):
            try:
                subprocess.check_call([venv_pip, "install", "-e", f"{here}[live]"])
            except Exception:
                subprocess.check_call([venv_pip, "install", "token-oracle[live]"])
        else:
            subprocess.check_call([venv_pip, "install", "token-oracle[live]"])

    env = os.environ.copy()
    env["TOKEN_ORACLE_LIVE_BOOTSTRAPPED"] = "1"

    if os.path.exists(venv_oracle):
        # Silent switch for normal use. The user only sees creation messages on first setup.
        # This avoids surprising "Using dedicated environment" + delay on every `oracle` invocation.
        os.execve(venv_oracle, [venv_oracle] + sys.argv[1:], env)
    else:
        os.execve(venv_py, [venv_py, "-m", "token_oracle.cli.main"] + sys.argv[1:], env)


def _live_setup(cfg, args):
    """Simple flow for everyone:
    1. Run `oracle live-setup`
    2. (first time) it may set up a venv + playwright automatically
    3. Headed browsers open for one-time login to grok.com and claude.ai
    4. After that `oracle dash` shows the real numbers from the websites.
    """
    import subprocess
    from ..live import web as live_web
    from ..cli import colors as c

    # This makes it "just work" for community users on all kinds of systems
    _bootstrap_playwright_if_needed()

    color = c.color_enabled()
    print(c.violet("=== token-oracle live web setup ===", color))
    print("Goal: make `oracle dash` show the *real* numbers from grok.com and claude.ai\n")

    for prov in ("grok", "claude"):
        live_web.get_browser_profile_dir(prov)

    if not getattr(live_web, "PLAYWRIGHT_AVAILABLE", False):
        print(
            c.ok_badge(False, color)
            + ' playwright not available. Try `pip install "token-oracle[live]"`'
        )
        return 1

    print(c.ok_badge(True, color) + " playwright ready")
    print()

    # Check if we already have valid sessions from previous one-time login.
    # If yes, skip all browser opening. This makes auth truly "one time".
    try:
        status = live_web.get_live_status()
        grok_ok = status.get("grok") == "ok"
        claude_ok = status.get("claude") == "ok"
    except Exception:
        grok_ok = claude_ok = False

    if grok_ok and claude_ok:
        print(c.ok_badge(True, color) + " Already authenticated for both Grok and Claude.")
        print("Saved sessions detected — no browser windows will be opened.")
        print("Headless live data is ready. You can run `oracle dash`.")
        return 0

    print("A browser window will open for the providers that still need login.")
    print()

    has_display = bool(os.environ.get("DISPLAY"))

    if not has_display:
        print("No graphical display detected (no $DISPLAY/Wayland).")
        print("Common on remote machines, servers, containers, or SSH-only sessions.")
        print()
        print("Practical options:")
        print("  • Run `oracle live-setup` on a machine that has a GUI, then copy the profiles:")
        print(
            "      rsync -av ~/.config/token-oracle/browser-profiles/ user@remote:~/.config/token-oracle/"
        )
        print("  • Use X11 forwarding: ssh -X user@host  then run `oracle live-setup`")
        print("  • We will try Xvfb (virtual display) automatically if available.")
        print()
        print(
            "Once the profiles on this machine have valid sessions, `oracle dash` will use real live data."
        )
        return 0

    # Real login — only for providers that are not yet authenticated
    completed = {"grok": False, "claude": False}
    for prov in ("grok", "claude"):
        already = (prov == "grok" and grok_ok) or (prov == "claude" and claude_ok)
        print(c.violet(f"→ {prov.upper()} login", color))
        if already:
            print("   ✓ Already logged in from previous session (skipping).")
            completed[prov] = True
            continue
        try:
            ok = live_web.launch_login_session(prov, headless=False)
            completed[prov] = bool(ok)
        except Exception as e:
            print("   " + c.ok_badge(False, color) + f" {e}")

    print()
    for prov, ok in completed.items():
        status = "✓" if ok else "✗"
        print(f"  {status} {prov.upper()} login")

    if all(completed.values()):
        print()
        print(c.ok_badge(True, color) + " All logins saved.")
        print()
        print("Now run:")
        print(c.violet("  oracle dash", color))
        print()
        print("Look at the top line and the new 'live web:' line — it will tell you")
        print("whether it is pulling real numbers from the websites right now.")
    else:
        print()
        print("Run `oracle live-setup` again to retry the ones that failed.")
        print("(It will automatically skip providers that are already logged in.)")
    return 0
