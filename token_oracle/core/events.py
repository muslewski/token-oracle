"""Event record shape shared by sources, cache, and consumers. An event is
[ts, tokens, model, input, output, cache_create, cache_read, cost_usd];
legacy [ts, tokens] pairs stay valid. Prediction math only ever reads the
first two fields — see as_pairs. Stdlib only."""

N_FIELDS = 8


def normalize(e):
    """Any 2..8-element sequence -> canonical 8-tuple. Never raises on
    well-typed short input."""
    ts, tok = float(e[0]), int(e[1])
    model = e[2] if len(e) > 2 else None
    ints = [int(e[i]) if len(e) > i and e[i] is not None else 0 for i in (3, 4, 5, 6)]
    cost = float(e[7]) if len(e) > 7 and e[7] is not None else None
    return (ts, tok, model, *ints, cost)


def as_pairs(events):
    """The 2-field view the forecast math consumes."""
    return [(float(e[0]), int(e[1])) for e in events]
