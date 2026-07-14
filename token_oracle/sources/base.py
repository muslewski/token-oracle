"""Source adapter registry. A source turns provider data into neutral event
records (see core/events.py); minimally (timestamp, tokens), owning its own
incremental file/cache state.

Built-ins: claude_code, grok, generic. Register more via @register or
entry points under the group token_oracle.sources (lazy-loaded on demand).
Use "source" in config.json to select."""

_REGISTRY: dict[str, type] = {}
_EP_GROUP = "token_oracle.sources"


def register(name):
    def deco(cls):
        _REGISTRY[name] = cls
        return cls

    return deco


def _entry_points():
    try:
        from importlib.metadata import entry_points

        return list(entry_points(group=_EP_GROUP))
    except Exception:
        return []


def _load_entry_point(name):
    """Import the entry point matching name, if any; it registers on import."""
    for ep in _entry_points():
        if ep.name == name and name not in _REGISTRY:
            try:
                ep.load()
            except Exception:
                pass
            return


def available():
    names = set(_REGISTRY)
    names.update(ep.name for ep in _entry_points())
    return sorted(names)


def get_source(name, opts=None):
    if name not in _REGISTRY:
        _load_entry_point(name)
    if name not in _REGISTRY:
        raise KeyError(f"unknown source: {name!r}; available: {available()}")
    return _REGISTRY[name](opts or {})
