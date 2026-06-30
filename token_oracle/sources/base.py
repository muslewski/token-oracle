"""Source adapter registry. A source turns provider data into neutral
(timestamp, tokens) events, owning its own incremental file/cache state."""

_REGISTRY: dict[str, type] = {}


def register(name):
    def deco(cls):
        _REGISTRY[name] = cls
        return cls

    return deco


def available():
    return sorted(_REGISTRY)


def get_source(name, opts=None):
    if name not in _REGISTRY:
        raise KeyError(f"unknown source: {name!r}; available: {available()}")
    return _REGISTRY[name](opts or {})
