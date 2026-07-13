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
from ..core import events as events_mod
from ..core import report as report_mod
from ..core.config import (
    PRESETS,
    _window_from_dict,
    default_config_path,
    load_config,
    write_default_config,
)
from ..core.engine import cached_events
from ..core.engine import forecast as run_forecast
from ..core.profile import HIST_SECS
from ..core.timeutil import fmt_dur, fmt_tokens
from ..snapshot.writer import build_snapshot, default_snapshot_path, write_snapshot
from ..sources.base import available, get_source

_CMD_HELP = {
    "forecast": "print a compact usage forecast (time left before your cap)",
    "report": "daily token + cost ledger with pct of your weekly cap",
    "snapshot": "write the current forecast to a JSON snapshot file",
    "statusline": "print a one-line status for shell prompts / status bars",
    "tmux": "print a tmux-formatted status string",
    "doctor": "check config, data sources, cache, and live status",
    "dash": "full-screen live dashboard (Ctrl-C to quit)",
    "init": "write a starter config file",
    "clean": "remove token-oracle's config, cache, and snapshot files",
    "live": "turn real (browser-verified) live data on / off (or show status)",
    "live-setup": "one-time browser login to grok.com / claude.ai for live data",
    "live-probe": "run the live web probe now and print what it found",
}


def _add_common(p):
    p.add_argument(
        "--config",
        default=None,
        help="path to config file (default: ~/.config/token-oracle/config.json)",
    )
    p.add_argument("--now", type=float, default=None, help=argparse.SUPPRESS)


def _now(args):
    return args.now if args.now is not None else time.time()


def _reset_sigpipe():
    """Restore default SIGPIPE so `oracle ... | head` dies quietly like a normal
    Unix filter, instead of raising BrokenPipeError + a shutdown traceback.

    No-op on platforms without SIGPIPE (Windows) or when not on the main thread.
    """
    try:
        import signal

        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (ImportError, AttributeError, ValueError):
        pass


def _is_interactive():
    """True when stdout is an interactive terminal (not a pipe / file / capture).

    Isolated into a helper so tests can monkeypatch it; capturing stdout in a
    test makes the real isatty() False, which would hide the guidance branch.
    """
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def _first_run_hint():
    """Actionable guidance shown when `forecast` finds no data on a real TTY."""
    return (
        "no usage data yet.\n"
        "\n"
        "token-oracle forecasts from your agent's local logs — there is nothing\n"
        "to forecast until some exist.\n"
        "  • Claude Code: use it once; logs appear under ~/.claude/projects/\n"
        "  • see what oracle found:   oracle doctor\n"
        "  • create a config:         oracle init\n"
        "  • turn on live web numbers: oracle live on   (then: oracle live-setup)\n"
        "\n"
        "docs: https://github.com/muslewski/token-oracle"
    )


def _parse_date(s):
    """Parse YYYY-MM-DD to unix ts (local midnight); None on bad input."""
    if not s:
        return None
    try:
        return time.mktime(time.strptime(s, "%Y-%m-%d"))
    except Exception:
        return None


def _report_sections(cfg, now, args):
    """Return list of section dicts, one per profile (or single). Each has
    profile, cap, by, rows (list of dicts from LedgerRow)."""
    sections = []
    multi = bool(cfg.profiles)
    if multi:
        for pname in sorted(cfg.profiles.keys()):
            pdef = cfg.profiles[pname]
            src_name = pdef.get("source", cfg.source)
            opts = pdef.get("source_opts", cfg.source_opts or {})
            wraw = pdef.get("windows") or cfg.windows
            wins = []
            for w in wraw or []:
                if isinstance(w, dict):
                    try:
                        wins.append(_window_from_dict(w))
                    except Exception:
                        continue
                else:
                    wins.append(w)
            cap = report_mod.weekly_cap(wins) or 0
            try:
                src = get_source(src_name, opts)
                _f, evs = src.scan({}, now, HIST_SECS)
                events = [events_mod.normalize(e) for e in evs]
            except Exception:
                events = []
            # apply since/until filter (local day)
            since_ts = _parse_date(getattr(args, "since", None))
            until_ts = _parse_date(getattr(args, "until", None))
            if since_ts is not None or until_ts is not None:
                filtered = []
                for e in events:
                    dk = report_mod.day_key(e[0])
                    if since_ts is not None:
                        sday = report_mod.day_key(since_ts)
                        if dk < sday:
                            continue
                    if until_ts is not None:
                        uday = report_mod.day_key(until_ts)
                        if dk > uday:
                            continue
                    filtered.append(e)
                events = filtered
            by = getattr(args, "by", "day")
            days = getattr(args, "days", 7)
            mode = getattr(cfg, "cost_mode", "auto")
            ov = getattr(cfg, "pricing", {})
            if by == "day":
                rows = report_mod.daily_ledger(
                    events, cap or None, now, days=days, mode=mode, overrides=ov
                )
            else:
                rows = report_mod.group_ledger(events, by, now, mode=mode, overrides=ov)
            secs = [
                {
                    "label": r.label,
                    "tokens": r.tokens,
                    "cost": r.cost,
                    "unpriced_tokens": r.unpriced_tokens,
                    "pct_cap": r.pct_cap,
                }
                for r in rows
            ]
            sections.append({"profile": pname, "cap": cap, "by": by, "rows": secs})
    else:
        try:
            src = get_source(cfg.source, cfg.source_opts)
            _f, evs = src.scan({}, now, HIST_SECS)
            events = [events_mod.normalize(e) for e in evs]
        except Exception:
            events = []
        since_ts = _parse_date(getattr(args, "since", None))
        until_ts = _parse_date(getattr(args, "until", None))
        if since_ts is not None or until_ts is not None:
            filtered = []
            for e in events:
                dk = report_mod.day_key(e[0])
                if since_ts is not None:
                    sday = report_mod.day_key(since_ts)
                    if dk < sday:
                        continue
                if until_ts is not None:
                    uday = report_mod.day_key(until_ts)
                    if dk > uday:
                        continue
                filtered.append(e)
            events = filtered
        wins = cfg.windows or []
        cap = report_mod.weekly_cap(wins) or 0
        by = getattr(args, "by", "day")
        days = getattr(args, "days", 7)
        mode = getattr(cfg, "cost_mode", "auto")
        ov = getattr(cfg, "pricing", {})
        if by == "day":
            rows = report_mod.daily_ledger(
                events, cap or None, now, days=days, mode=mode, overrides=ov
            )
        else:
            rows = report_mod.group_ledger(events, by, now, mode=mode, overrides=ov)
        secs = [
            {
                "label": r.label,
                "tokens": r.tokens,
                "cost": r.cost,
                "unpriced_tokens": r.unpriced_tokens,
                "pct_cap": r.pct_cap,
            }
            for r in rows
        ]
        sections.append({"profile": cfg.source, "cap": cap, "by": by, "rows": secs})
    return sections


def _statusline_render(cfg, now, fs, enabled):
    """Compose statusline. Headline if ratelimits 5h header present; else
    old sl.render + optional cost tail (byte-identical fallback)."""
    try:
        evs = cached_events(cfg)
        usd = report_mod.cost_today(
            evs, now, getattr(cfg, "cost_mode", "auto"), getattr(cfg, "pricing", {})
        )["usd"]
    except Exception:
        usd = 0.0
    from ..core import ratelimits as RL

    fh = RL.five_hour(now)
    wk = RL.weekly(now)
    cost_tail = sl.cost_segment(usd, enabled) if hasattr(sl, "cost_segment") else ""
    # headline when we have current-usage 5h from header (never use projected_pct here)
    if (
        isinstance(fh, dict)
        and not fh.get("stale")
        and isinstance(fh.get("used_percentage"), (int, float))
    ):
        p5 = round(fh["used_percentage"])
        parts = [colors.violet("◔", enabled) + " " + colors.gauge(f"5h {p5}%", p5, enabled)]
        if (
            isinstance(wk, dict)
            and not wk.get("stale")
            and isinstance(wk.get("used_percentage"), (int, float))
        ):
            pw = round(wk["used_percentage"])
            parts.append(colors.gauge(f"wk {pw}%", pw, enabled))
        line = " · ".join(parts)
        if cost_tail:
            line += cost_tail
        return line
    # fallback: exact old render + cost (when no RL snapshot)
    base = sl.render(fs, enabled) if fs else ""
    if cost_tail:
        base = (base + cost_tail) if base else cost_tail.lstrip()
    return base or "idle"


def _statusline_install(force=False, path=None):
    """Safe --install: backup, idempotent, refuse non-oracle unless --force,
    atomic write, touches only statusLine key. Returns exit code."""
    import shutil
    import tempfile

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
                print(f"{settings} is not a JSON object — refusing to edit.")
                return 1
        except (OSError, ValueError) as e:
            print(f"could not read {settings}: {e} — refusing to edit.")
            return 1
    desired = {"type": "command", "command": "oracle statusline", "padding": 0}
    existing = data.get("statusLine")
    if existing == desired:
        print(colors.ok_badge(True, color) + " statusLine already wired to oracle.")
        return 0
    if existing and not force:
        print("A statusLine is already configured:")
        print("  " + json.dumps(existing))
        print("Pass --force to replace it with `oracle statusline`.")
        return 1
    # backup
    if os.path.exists(settings):
        try:
            shutil.copy2(settings, settings + ".oracle.bak")
            print(colors.ok_badge(True, color) + f" backed up → {settings}.oracle.bak")
        except OSError:
            pass
    data["statusLine"] = desired
    # atomic write
    try:
        fd, tmp = tempfile.mkstemp(dir=claude_dir or ".", suffix=".tmp", text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, settings)
    except OSError as e:
        print(f"write failed: {e}")
        return 1
    print(colors.ok_badge(True, color) + " statusLine → oracle statusline")
    print("Restart Claude Code to see it. 5h / weekly light up as it feeds usage headers.")
    return 0


def _maybe_ingest_rate_limits() -> None:
    """If Claude Code piped its statusline JSON on stdin, fold the rate_limits
    header into our snapshot. Silent + never raises (statusline hot path)."""
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return
        raw = sys.stdin.read()
        if not raw.strip():
            return
        payload = json.loads(raw)
        rl = payload.get("rate_limits") if isinstance(payload, dict) else None
        if rl:
            from ..core import ratelimits as RL

            RL.ingest(rl)
    except Exception:
        pass


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
            for _pname, pdef in cfg.profiles.items():
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
                (
                    f"profiles={len(cfg.profiles)} · {total_files} files, "
                    f"{total_evs} events, {age_str}"
                ),
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
                    "  limits   — real caps + weeklyResetAnchor from "
                    "~/.claude/usage-limits.json (exact resets)",
                    color,
                )
            )
    except Exception:
        pass

    # Live web status (snapshot-derived, instant, no probe/browser text)
    try:
        from token_oracle.live import web as lw

        from ..live.store import load_snapshot

        st = lw.get_live_status()
        gr = st.get("grok", "unavailable")
        cl = st.get("claude", "unavailable")
        ts = st.get("last_fetch") or st.get("last_attempt")
        if ts:
            secs = int(time.time() - ts)
            if secs < 120:
                age_str = f"{secs}s ago"
            else:
                age_str = f"{secs // 60}m ago"
        else:
            age_str = ""

        def _fmt_one(pn, pst):
            if pst == "ok":
                snap = load_snapshot() or {}
                pdat = (snap.get("providers") or {}).get(pn, {})
                for r in pdat.get("readings") or []:
                    m = r.get("metric")
                    if m in ("weekly_pct", "five_hour_pct", "model_weekly_pct"):
                        val = r.get("value")
                        extr = r.get("extractor", "")
                        if isinstance(val, (int, float)):
                            return f"{pn}=ok ({m} {val:.1f}% · {extr}, {age_str})"
                return f"{pn}=ok ({age_str})"
            elif pst == "stale":
                last = st.get(f"{pn}_last_state", "")
                return f"{pn}=stale (was {last})" if last else f"{pn}=stale"
            else:
                return f"{pn}={pst}"

        if gr == "stale" or cl == "stale":
            out.append(
                colors.dim(f"  live     — snapshot is {age_str} old — run oracle live-probe", color)
            )
        elif gr == "unavailable" and cl == "unavailable":
            out.append(
                colors.dim(
                    "  live     — not probed yet (run oracle live-probe; live-setup if needed)",
                    color,
                )
            )
        else:
            parts = [_fmt_one("grok", gr), _fmt_one("claude", cl)]
            live_msg = "  live     — " + " ".join(parts)
            # When a provider note mentions bot challenge, include the actionable hint in live row.
            try:
                snap = load_snapshot() or {}
                for pn in ("grok", "claude"):
                    pdat = (snap.get("providers") or {}).get(pn, {})
                    note = str(pdat.get("note", "")) if isinstance(pdat, dict) else ""
                    if "bot challenge" in note.lower():
                        live_msg = (
                            "  live     — bot challenge — try "
                            "TOKEN_ORACLE_LIVE_HEADED=1 oracle live-probe"
                        )
                        break
            except Exception:
                pass
            # Step 5: compact surface of the persistent real-data toggle (one line)
            try:
                if cfg.headed_enabled():
                    has_d = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
                    has_x = bool(__import__("shutil").which("Xvfb"))
                    if has_d or has_x:
                        suffix = " [real data: ON]"
                    else:
                        suffix = " [real data: ON (Xvfb missing)]"
                    live_msg += suffix
            except Exception:
                pass
            out.append(colors.dim(live_msg, color))
    except Exception:
        out.append(colors.dim("  live     — status check failed", color))

    # Informational 5h server-truth status from our own ingested header (never affects
    # the doctor exit code / bad count; present even if no events).
    try:
        from ..core import ratelimits as RL

        d = RL.five_hour(now)
        if d and isinstance(d, dict) and not d.get("stale", False):
            pct = d.get("used_percentage")
            obs = d.get("observed_at")
            if obs is not None:
                age_s = int(time.time() - float(obs))
                age_str = f"{age_s}s ago"
            else:
                age_str = ""
            pct_str = f"{float(pct):.0f}%" if isinstance(pct, (int, float)) else "?"
            out.append(
                colors.dim(f"  ✓ live 5h truth: ON (server header, {pct_str} · {age_str})", color)
            )
        else:
            out.append(
                colors.dim(
                    "  ◌ live 5h truth: OFF — wire `oracle statusline` as your Claude Code "
                    "statusLine to enable it (see SETUP.md)",
                    color,
                )
            )
    except Exception:
        pass
    return out, bad


def main(argv=None):
    _reset_sigpipe()
    parser = argparse.ArgumentParser(
        prog="token-oracle",
        description=(
            "token-oracle — forecast when you'll hit your Claude Code / Grok "
            "token limits, computed offline from local agent logs (with optional "
            "browser-verified live numbers)."
        ),
        epilog=(
            "examples:\n"
            "  token-oracle forecast          time left before your next cap\n"
            "  token-oracle dash              full-screen live dashboard (Ctrl-C to quit)\n"
            "  token-oracle doctor            check config, data sources, and live status\n"
            "  token-oracle init              write a starter config file\n"
            "  token-oracle live on           turn on real, browser-verified numbers\n"
            "\n"
            "docs: https://github.com/muslewski/token-oracle"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="<command>")
    for name in (
        "forecast",
        "report",
        "snapshot",
        "statusline",
        "tmux",
        "doctor",
        "dash",
        "init",
        "clean",
        "live",
        "live-setup",
        "live-probe",
    ):
        sp = sub.add_parser(
            name,
            help=_CMD_HELP[name],
            description=_CMD_HELP[name],
        )
        _add_common(sp)
        if name == "forecast":
            sp.add_argument(
                "--json",
                action="store_true",
                help="emit machine-readable JSON instead of text",
            )
        if name == "report":
            sp.add_argument("--json", action="store_true", help="emit machine-readable JSON")
            sp.add_argument(
                "--by",
                choices=["day", "week", "model"],
                default="day",
                help="grouping axis (default: day)",
            )
            sp.add_argument(
                "--since",
                default=None,
                metavar="YYYY-MM-DD",
                help="only include events on/after this local date",
            )
            sp.add_argument(
                "--until",
                default=None,
                metavar="YYYY-MM-DD",
                help="only include events on/before this local date",
            )
            sp.add_argument(
                "--days",
                type=int,
                default=7,
                help="number of days for the default daily view (default: 7)",
            )
        if name == "statusline":
            sp.add_argument(
                "--install",
                action="store_true",
                help=(
                    "wire `oracle statusline` into ~/.claude/settings.json "
                    "as your Claude Code statusLine"
                ),
            )
            sp.add_argument(
                "--force",
                action="store_true",
                help="with --install, replace an existing statusLine",
            )
        if name == "snapshot":
            sp.add_argument(
                "--out",
                default=None,
                help="output path (default: the standard snapshot location)",
            )
        if name == "init":
            sp.add_argument(
                "--preset",
                default="max20",
                choices=sorted(PRESETS),
                help="plan preset for the new config (default: max20)",
            )
            sp.add_argument(
                "--force",
                action="store_true",
                help="overwrite an existing config file",
            )
        if name == "clean":
            sp.add_argument(
                "--yes",
                action="store_true",
                help="actually delete (without this, only prints what would be removed)",
            )
        if name == "live":
            sp.add_argument(
                "action",
                choices=["on", "off", "status"],
                help="on | off | status",
            )
        if name == "live-probe":
            sp.add_argument(
                "--provider",
                choices=["grok", "claude", "all"],
                default="all",
                help="which provider(s) to probe (default: all)",
            )
            sp.add_argument(
                "--json",
                action="store_true",
                help="emit machine-readable JSON instead of text",
            )
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
            out = sl.render(fs)
            if not out:
                # No data. A human at a terminal gets guidance; everything
                # non-interactive (pipes, status bars, scripts) keeps the
                # stable "idle" token it has always emitted.
                if _is_interactive():
                    print(_first_run_hint())
                    return 0
                out = "idle"
            if cfg.profiles:
                out = "(multi) " + out
            print(out)
        return 0
    if args.cmd == "report":
        # bad date check (before sections)
        for flag in ("since", "until"):
            val = getattr(args, flag, None)
            if val is not None and _parse_date(val) is None:
                print(f"report: invalid --{flag} date (use YYYY-MM-DD)", file=sys.stderr)
                return 2
        sections = _report_sections(cfg, now, args)
        # first-run hint only for interactive no-data TTY (like forecast)
        has_data = any(any(r.get("tokens", 0) > 0 for r in s.get("rows", [])) for s in sections)
        if not has_data and _is_interactive() and not getattr(args, "json", False):
            print(_first_run_hint())
            return 0
        if getattr(args, "json", False):
            print(json.dumps({"generated_at": now, "sections": sections}, indent=2))
            return 0
        # text render
        color = colors.color_enabled()
        for sec in sections:
            prof = sec.get("profile", "?")
            by = sec.get("by", "day")
            rows = sec.get("rows", [])
            header = (
                colors.violet(
                    f"{prof} · {len([r for r in rows if r['label'] != 'TOTAL'])} {by}-ledger", color
                )
                if by != "day"
                else colors.violet(f"{prof} · {getattr(args, 'days', 7)}-day ledger", color)
            )
            print(header)
            # decide columns
            show_pct = by == "day"
            # header row
            cols = ["DAY" if by == "day" else ("WEEK" if by == "week" else "MODEL"), "TOK", "COST"]
            if show_pct:
                cols.append("%CAP")
            # widths rough
            print("  ".join(cols))
            print("  ".join(["-" * max(3, len(c)) for c in cols]))
            for r in rows:
                is_total = r["label"] == "TOTAL"
                if is_total:
                    print("  " + "-" * 30)
                lab = r["label"]
                tok = fmt_tokens(r["tokens"])
                if r["cost"] is None:
                    cst = "—"
                else:
                    cst = f"${r['cost']:,.2f}"
                line = f"{lab:12}  {tok:>6}  {cst:>10}"
                if show_pct:
                    if r["pct_cap"] is not None:
                        pct_str = colors.gauge(f"{r['pct_cap']:.0f}%", r["pct_cap"], color)
                        line += f"  {pct_str}"
                    else:
                        line += "  —"
                print(line)
            # note if all unpriced
            all_none = all(r["cost"] is None for r in rows if r["tokens"] > 0)
            if all_none and any(r["tokens"] > 0 for r in rows):
                print(colors.dim("cost unavailable (cost_mode=off or unpriced models)", color))
            if not any(r["tokens"] > 0 for r in rows):
                print(colors.dim(f"no usage data for {prof} in range", color))
            print()
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
        _maybe_ingest_rate_limits()
        if getattr(args, "install", False):
            return _statusline_install(force=getattr(args, "force", False))
        print(_statusline_render(cfg, now, run_forecast(now, cfg), colors.color_enabled()))
        return 0
    if args.cmd == "tmux":
        print(tx.render(run_forecast(now, cfg)))
        return 0
    if args.cmd == "doctor":
        print("⏳ oracle doctor — running checks")
        lines, bad = _doctor_lines(cfg, args.config, colors.color_enabled(), now)
        for line in lines:
            print(line)
        return 0 if bad == 0 else 1
    if args.cmd == "dash":
        from ..dashboard.app import run as run_dash

        return run_dash(cfg)

    if args.cmd == "live":
        return _live_toggle(cfg, args)

    if args.cmd == "live-probe":
        _bootstrap_playwright_if_needed()
        from ..live.probe import run_probe

        prov = args.provider
        headed = os.environ.get("TOKEN_ORACLE_LIVE_HEADED") == "1" or cfg.headed_enabled()
        headless = not headed
        snap = run_probe(
            providers=prov,
            headless=headless,
            progress=lambda m: print(m, file=sys.stderr),
        )
        if args.json:
            print(json.dumps(snap, indent=2, default=str))
        else:
            # short human summary
            for name in ("grok", "claude"):
                if name in (snap.get("providers") or {}):
                    p = (snap["providers"] or {}).get(name, {})
                    st = p.get("state", "?")
                    # pick a top reading if present
                    readings = p.get("readings") or []
                    top = ""
                    for r in readings:
                        if r.get("metric") in ("weekly_pct", "five_hour_pct", "model_weekly_pct"):
                            val = r.get("value")
                            if isinstance(val, (int, float)):
                                top = f" {val:.1f}%"
                                break
                    age = ""
                    fa = p.get("fetched_at")
                    if fa:
                        age = f" ({int(time.time() - fa)}s ago)"
                    print(f"{name}: {st}{top}{age}")
                else:
                    print(f"{name}: not probed")
        # exit codes per plan
        states = []
        for name in ("grok", "claude"):
            p = (snap.get("providers") or {}).get(name, {})
            states.append(p.get("state"))
        has_ok = any(s in ("ok", "rate_data_only") for s in states if s)
        has_needs = any(s == "needs_login" for s in states if s)
        if has_ok:
            return 0
        if has_needs:
            return 3
        return 4

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


def _live_toggle(cfg, args):
    import shutil

    from ..cli import colors as c
    from ..core.config import update_config_file
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


def _live_setup(cfg, args):
    """Simple flow for everyone:
    1. Run `oracle live-setup`
    2. (first time) it may set up a venv + playwright automatically
    3. Headed browsers open for one-time login to grok.com and claude.ai
    4. After that `oracle dash` shows the real numbers from the websites.
    """
    from ..cli import colors as c
    from ..live import web as live_web

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
            "      rsync -av ~/.config/token-oracle/browser-profiles/ "
            "user@remote:~/.config/token-oracle/"
        )
        print("  • Use X11 forwarding: ssh -X user@host  then run `oracle live-setup`")
        print("  • We will try Xvfb (virtual display) automatically if available.")
        print()
        print(
            "Once the profiles on this machine have valid sessions, "
            "`oracle dash` will use real live data."
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


if __name__ == "__main__":
    sys.exit(main())
