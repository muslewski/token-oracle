"""oracle CLI: forecast / snapshot / statusline / tmux / doctor / dash."""

import argparse
import json
import os
import sys
import time

from ..adapters import statusline as sl
from ..adapters import tmux as tx
from ..cli import colors
from ..core.config import default_config_path, load_config
from ..core.engine import forecast as run_forecast
from ..core.profile import HIST_SECS
from ..core.timeutil import fmt_dur
from ..snapshot.writer import build_snapshot, write_snapshot
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

    try:
        src = get_source(cfg.source, cfg.source_opts)
        files, events = src.scan({}, now, HIST_SECS)
        if events:
            age = fmt_dur(now - events[-1][0])
            data_row = ("data", f"{len(files)} files, {len(events)} events, last {age} ago", True)
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
            if isinstance(cache_data, dict) and "files" in cache_data:
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

    rows = [
        config_row,
        ("source", f"{cfg.source} (available: {', '.join(avail)})", cfg.source in avail),
        data_row,
        cache_row,
        ("windows", f"{len(cfg.windows)} → {[w.name for w in cfg.windows]}", len(cfg.windows) > 0),
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
    return out, bad


def main(argv=None):
    parser = argparse.ArgumentParser(prog="token-oracle")
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
        lines, bad = _doctor_lines(cfg, args.config, colors.color_enabled(), now)
        for line in lines:
            print(line)
        return 0 if bad == 0 else 1
    if args.cmd == "dash":
        from ..dashboard.app import run as run_dash

        return run_dash(cfg)
    return 1
