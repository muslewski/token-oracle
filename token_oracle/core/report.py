"""Pure aggregation over normalized event lists; cost via core.pricing;
no I/O; the caller supplies events + caps."""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from . import events as events_mod
from . import pricing


@dataclass
class LedgerRow:
    label: str
    tokens: int
    cost: float | None
    unpriced_tokens: int
    pct_cap: float | None


def weekly_cap(windows) -> int | None:
    """The cap of the window that best represents the weekly limit: the window
    whose period_secs is nearest 7*24*3600; ties/none -> the largest cap among
    windows; empty -> None. Pure."""
    if not windows:
        return None
    target = 7 * 24 * 3600
    best_diff = float("inf")
    best_cap = None
    for w in windows:
        try:
            per = int(getattr(w, "period_secs", 0) or 0)
            cap = int(getattr(w, "cap", 0) or 0)
        except Exception:
            continue
        d = abs(per - target)
        if d < best_diff or (d == best_diff and (best_cap is None or cap > best_cap)):
            best_diff = d
            best_cap = cap
    if best_cap is None:
        # fallback to largest cap among any
        caps = []
        for w in windows:
            try:
                caps.append(int(getattr(w, "cap", 0) or 0))
            except Exception:
                pass
        return max(caps) if caps else None
    return best_cap


def day_key(ts, now=None) -> str:
    """Local calendar day label 'YYYY-MM-DD' for a unix ts."""
    lt = time.localtime(ts)
    return time.strftime("%Y-%m-%d", lt)


def daily_ledger(events, cap, now, days=7, mode="auto", overrides=None) -> list[LedgerRow]:
    """One row per local calendar day for the last `days` days ending at `now`
    (most-recent last), plus a final TOTAL row (label='TOTAL').
      tokens        = sum event[1] that day
      cost          = sum event_cost(...) that day; None only if EVERY priced
                      attempt returned None AND tokens>0 (fully unpriced day);
                      0.0 for a genuinely empty day
      unpriced_tokens = tokens whose cost could not be resolved
      pct_cap       = 100*tokens/cap if cap else None   (that day's share of the weekly cap)
    Days with zero events still emit a row (tokens=0, cost=0.0) so the table is
    a continuous calendar. Never raises on well-typed input."""
    normed = [
        events_mod.normalize(e)
        for e in (events or [])
        if isinstance(e, (list, tuple)) and len(e) >= 2
    ]
    # generate the day labels: oldest first, most-recent last
    now_lt = time.localtime(now)
    d = datetime(now_lt.tm_year, now_lt.tm_mon, now_lt.tm_mday).date()
    day_labels = []
    for i in range(days - 1, -1, -1):
        dd = d - timedelta(days=i)
        day_labels.append(dd.isoformat())
    # bucket by day key
    buckets: dict = {}
    for e in normed:
        dk = day_key(e[0])
        buckets.setdefault(dk, []).append(e)
    rows = []
    total_tokens = 0
    total_usd = 0.0
    total_unpriced = 0
    for lbl in day_labels:
        evs = buckets.get(lbl, [])
        toks = sum(int(e[1]) for e in evs)
        summary = pricing.cost_summary(evs, mode, overrides)
        usd = summary["usd"]
        unpr = summary["unpriced_tokens"]
        if toks > 0 and unpr == toks:
            cst = None
        else:
            cst = usd  # 0.0 for empty
        pct = (100.0 * toks / cap) if cap else None
        rows.append(LedgerRow(label=lbl, tokens=toks, cost=cst, unpriced_tokens=unpr, pct_cap=pct))
        total_tokens += toks
        if cst is not None:
            total_usd += cst
        total_unpriced += unpr
    # TOTAL
    if total_tokens > 0 and total_unpriced == total_tokens:
        total_cost = None
    else:
        total_cost = total_usd
    total_pct = (100.0 * total_tokens / cap) if cap else None
    rows.append(
        LedgerRow(
            label="TOTAL",
            tokens=total_tokens,
            cost=total_cost,
            unpriced_tokens=total_unpriced,
            pct_cap=total_pct,
        )
    )
    return rows


def group_ledger(events, key, now, mode="auto", overrides=None) -> list[LedgerRow]:
    """Aggregate ALL given events by `key`:
      key='day'   -> one row per calendar day present (no zero-fill), TOTAL last
      key='week'  -> one row per ISO week (label 'YYYY-Www'), TOTAL last
      key='model' -> one row per model (label = model or '(unknown)'), sorted by
                     cost desc then tokens desc, TOTAL last
    pct_cap is left None for group_ledger (grouping axis is not per-day-vs-cap).
    Unknown key -> raise ValueError('unsupported group key: ...') so the
    command can report it honestly."""
    normed = [
        events_mod.normalize(e)
        for e in (events or [])
        if isinstance(e, (list, tuple)) and len(e) >= 2
    ]
    if key not in ("day", "week", "model"):
        raise ValueError(f"unsupported group key: {key!r}")
    buckets: dict = {}
    for e in normed:
        if key == "day":
            k = day_key(e[0])
        elif key == "week":
            dt = datetime.fromtimestamp(e[0])
            iso_y, iso_w, _ = dt.isocalendar()
            k = f"{iso_y}-W{iso_w:02d}"
        else:  # model
            k = e[2] or "(unknown)"
        buckets.setdefault(k, []).append(e)
    rows = []
    total_t = 0
    total_u = 0.0
    total_unp = 0
    if key == "model":
        items = []
        for k, evs in buckets.items():
            s = pricing.cost_summary(evs, mode, overrides)
            usd = s["usd"]
            toks = sum(int(e[1]) for e in evs)
            unp = s["unpriced_tokens"]
            items.append((k, toks, usd, unp))
        items.sort(key=lambda x: (-x[2], -x[1], x[0]))
        for k, toks, usd, unp in items:
            cst = None if (toks > 0 and unp == toks) else usd
            rows.append(
                LedgerRow(label=k, tokens=toks, cost=cst, unpriced_tokens=unp, pct_cap=None)
            )
            total_t += toks
            if cst is not None:
                total_u += cst
            total_unp += unp
    else:
        for k in sorted(buckets.keys()):
            evs = buckets[k]
            s = pricing.cost_summary(evs, mode, overrides)
            toks = sum(int(e[1]) for e in evs)
            unp = s["unpriced_tokens"]
            usd = s["usd"]
            cst = None if (toks > 0 and unp == toks) else usd
            rows.append(
                LedgerRow(label=k, tokens=toks, cost=cst, unpriced_tokens=unp, pct_cap=None)
            )
            total_t += toks
            if cst is not None:
                total_u += cst
            total_unp += unp
    total_c = None if (total_t > 0 and total_unp == total_t) else total_u
    rows.append(
        LedgerRow(
            label="TOTAL", tokens=total_t, cost=total_c, unpriced_tokens=total_unp, pct_cap=None
        )
    )
    return rows


def cost_today(events, now, mode="auto", overrides=None) -> dict:
    """{'usd': float, 'unpriced_tokens': int} over events whose ts falls in the
    local calendar day containing `now`. Reuses pricing.cost_summary on the
    filtered slice. Cheap; called on the statusline hot path (plan 060)."""
    normed = [
        events_mod.normalize(e)
        for e in (events or [])
        if isinstance(e, (list, tuple)) and len(e) >= 2
    ]
    today = day_key(now)
    todays = [e for e in normed if day_key(e[0]) == today]
    return pricing.cost_summary(todays, mode, overrides)
