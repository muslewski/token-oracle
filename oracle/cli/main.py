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
