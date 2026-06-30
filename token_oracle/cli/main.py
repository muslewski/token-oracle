"""oracle CLI: forecast / snapshot / statusline / tmux / doctor / dash."""

import argparse
import json
import time

from ..adapters import statusline as sl
from ..adapters import tmux as tx
from ..cli import colors
from ..core.config import default_config_path, load_config
from ..core.engine import forecast as run_forecast
from ..snapshot.writer import build_snapshot, write_snapshot
from ..sources.base import available


def _add_common(p):
    p.add_argument("--config", default=None)
    p.add_argument("--now", type=float, default=None, help=argparse.SUPPRESS)


def _now(args):
    return args.now if args.now is not None else time.time()


def _doctor_lines(cfg, config_path, color):
    avail = available()
    rows = [
        ("config", config_path or default_config_path(), True),
        ("source", f"{cfg.source} (available: {', '.join(avail)})", cfg.source in avail),
        ("cache", cfg.cache_path, True),
        ("windows", f"{len(cfg.windows)} → {[w.name for w in cfg.windows]}", len(cfg.windows) > 0),
    ]
    out = [colors.violet(f"{colors.M_ORACLE} oracle doctor", color)]
    ok = 0
    for name, detail, good in rows:
        ok += 1 if good else 0
        out.append(f"  {colors.ok_badge(good, color)} {name:<8} — {detail}")
    bad = len(rows) - ok
    out.append(colors.dim(f"  {ok} ok · {bad} need attention", color))
    return out


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
        print(path)
        return 0
    if args.cmd == "statusline":
        print(sl.render(run_forecast(now, cfg)))
        return 0
    if args.cmd == "tmux":
        print(tx.render(run_forecast(now, cfg)))
        return 0
    if args.cmd == "doctor":
        for line in _doctor_lines(cfg, args.config, colors.color_enabled()):
            print(line)
        return 0
    if args.cmd == "dash":
        from ..dashboard.app import run as run_dash

        return run_dash(cfg, now)
    return 1
