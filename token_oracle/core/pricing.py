"""Cost pricing: an offline USD-per-million-token snapshot, longest-prefix
model resolution, and per-event/aggregate cost math. Stdlib only, no I/O, no
network — SNAPSHOT is a plan-time constant; per-model overrides are supplied
by the caller (config.py's "pricing" key), never fetched."""

# snapshot verified 2026-07-02; update on model releases
SNAPSHOT = {
    "claude-opus-4": {
        "input": 15.0,
        "output": 75.0,
        "cache_write": 15.0 * 1.25,
        "cache_read": 15.0 * 0.10,
    },
    "claude-sonnet-4": {
        "input": 3.0,
        "output": 15.0,
        "cache_write": 3.0 * 1.25,
        "cache_read": 3.0 * 0.10,
    },
    "claude-haiku-4-5": {
        "input": 1.0,
        "output": 5.0,
        "cache_write": 1.0 * 1.25,
        "cache_read": 1.0 * 0.10,
    },
}

_MODES = {"auto", "calculate", "display", "off"}


def _longest_prefix(model, table):
    best = None
    best_len = -1
    for prefix, prices in table.items():
        if model.startswith(prefix) and len(prefix) > best_len:
            best = prices
            best_len = len(prefix)
    return best


def resolve(model, overrides=None):
    """Longest-prefix lookup of per-Mtok prices for `model`. `overrides`
    (same shape as SNAPSHOT: model-prefix -> price dict) win over SNAPSHOT
    as a whole — any override match is returned before SNAPSHOT is even
    consulted. Returns None for an unknown or falsy model."""
    if not model:
        return None
    if overrides:
        hit = _longest_prefix(model, overrides)
        if hit is not None:
            return hit
    return _longest_prefix(model, SNAPSHOT)


def event_cost(event, mode="auto", overrides=None):
    """USD cost of one 8-field event `[ts, tok, model, input, output,
    cache_create, cache_read, cost_usd]` under `mode`:

      auto      - the event's own cost_usd (index 7) when present, else
                  calculated from token classes x resolved prices.
      calculate - always calculated from token classes x resolved prices,
                  ignoring any recorded cost_usd.
      display   - only ever the event's own cost_usd; never calculated.
      off       - cost tracking disabled; always None.

    Returns None whenever the needed value can't be produced (unresolvable
    model price, or a missing cost_usd in display/off mode) — callers must
    treat None as "unpriced", never silently as $0."""
    if mode not in _MODES:
        mode = "auto"
    cost_usd = event[7] if len(event) > 7 else None
    if mode == "off":
        return None
    if mode == "display":
        return float(cost_usd) if cost_usd is not None else None
    if mode == "auto" and cost_usd is not None:
        return float(cost_usd)

    # calculate (also the auto fallback when cost_usd is absent)
    model = event[2] if len(event) > 2 else None
    prices = resolve(model, overrides)
    if prices is None:
        return None
    input_tok = event[3] if len(event) > 3 and event[3] is not None else 0
    output_tok = event[4] if len(event) > 4 and event[4] is not None else 0
    cache_create = event[5] if len(event) > 5 and event[5] is not None else 0
    cache_read = event[6] if len(event) > 6 and event[6] is not None else 0
    total = (
        input_tok * prices.get("input", 0.0)
        + output_tok * prices.get("output", 0.0)
        + cache_create * prices.get("cache_write", 0.0)
        + cache_read * prices.get("cache_read", 0.0)
    )
    return total / 1_000_000


def cost_summary(events, mode="auto", overrides=None):
    """Aggregate cost over `events` under `mode`. Returns
    `{"usd": float, "unpriced_tokens": int, "by_model": {model: usd}}`.
    Events whose cost can't be resolved contribute their token count to
    unpriced_tokens instead of a silent $0 to usd."""
    usd = 0.0
    unpriced_tokens = 0
    by_model: dict = {}
    for event in events:
        cost = event_cost(event, mode, overrides)
        tok = int(event[1]) if len(event) > 1 and event[1] is not None else 0
        model = event[2] if len(event) > 2 else None
        if cost is None:
            unpriced_tokens += tok
            continue
        usd += cost
        by_model[model] = by_model.get(model, 0.0) + cost
    return {"usd": usd, "unpriced_tokens": unpriced_tokens, "by_model": by_model}
