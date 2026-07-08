"""Forecast facade: source scan -> cache -> burn profile -> per-window compute.
Never raises; returns [] on hard failure."""

from . import events as events_mod
from .cache import AGGREGATE_INTERVAL, load_cache, save_cache
from .config import load_config
from .profile import HIST_SECS, build_profile
from .windows import compute_window


def forecast(now, config=None):
    try:
        cfg = config or load_config()
        from ..sources.base import get_source

        source = get_source(cfg.source, cfg.source_opts)
        cache = load_cache(cfg.cache_path)
        if now - cache.get("lastAggregate", 0) >= AGGREGATE_INTERVAL:
            files, events = source.scan(cache.get("files", {}), now, HIST_SECS)
            events = [events_mod.normalize(e) for e in events]
            cache["files"] = files
            cache["events"] = [list(e) for e in events]
            cache["lastAggregate"] = now
            pairs = events_mod.as_pairs(events)
            cache["profile"] = build_profile(pairs, now)
            save_cache(cache, cfg.cache_path)
        else:
            events = [events_mod.normalize(e) for e in cache.get("events", [])]
        pairs = events_mod.as_pairs(events)
        profile = cache.get("profile") or None
        return [compute_window(pairs, now, w, profile) for w in cfg.windows]
    except Exception:
        return []
