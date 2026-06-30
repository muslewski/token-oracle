"""Forecast facade: source scan -> cache -> burn profile -> per-window compute.
Never raises; returns [] on hard failure."""
from .cache import (load_cache, save_cache, events_from_cache,
                    AGGREGATE_INTERVAL)
from .profile import build_profile, HIST_SECS
from .windows import compute_window
from .config import load_config


def forecast(now, config=None):
    try:
        cfg = config or load_config()
        from ..sources.base import get_source
        source = get_source(cfg.source, cfg.source_opts)
        cache = load_cache(cfg.cache_path)
        if now - cache.get("lastAggregate", 0) >= AGGREGATE_INTERVAL:
            files, events = source.scan(cache.get("files", {}), now, HIST_SECS)
            cache["files"] = files
            cache["events"] = [[float(ts), int(tok)] for ts, tok in events]
            cache["lastAggregate"] = now
            cache["profile"] = build_profile(events, now)
            save_cache(cache, cfg.cache_path)
        else:
            events = [(float(ts), int(tok)) for ts, tok in cache.get("events", [])]
        profile = cache.get("profile") or None
        return [compute_window(events, now, w, profile) for w in cfg.windows]
    except Exception:
        return []
