"""Past-tab renderer: daily ledger from core.report LedgerRows. Pure; no I/O."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from ..cli import colors as c
from ..core import events as events_mod
from ..core.report import LedgerRow
from ..core.timeutil import fmt_tokens

BAR_CELLS = 8
_BAR_FILLED = "▇"
_BAR_EMPTY = "░"


def _fmt_tok(n: int) -> str:
    """Token display that keeps sub-1k precision (fmt_tokens would print 0k)."""
    n = int(n or 0)
    if n < 1000:
        return str(n)
    return fmt_tokens(n)


def _fmt_usd(cost) -> str:
    if cost is None:
        return "—"
    return f"${float(cost):,.2f}"


def short_model(name: str | None) -> str:
    """Family-ish display label: strip claude- prefix and keep it short."""
    s = (name or "?").strip() or "?"
    if s.startswith("claude-"):
        s = s[7:]
    if s.startswith("anthropic."):
        s = s[len("anthropic.") :]
    return s[:20]


def top_models_by_day(events, now: float, days: int = 14) -> dict[str, str]:
    """Map YYYY-MM-DD -> short model name with the most tokens that day."""
    normed = [
        events_mod.normalize(e)
        for e in (events or [])
        if isinstance(e, (list, tuple)) and len(e) >= 2
    ]
    now_lt = time.localtime(now)
    d0 = datetime(now_lt.tm_year, now_lt.tm_mon, now_lt.tm_mday).date()
    wanted = {(d0 - timedelta(days=i)).isoformat() for i in range(days)}
    # day -> model -> tokens
    buckets: dict[str, dict[str, int]] = {}
    for e in normed:
        lt = time.localtime(e[0])
        dk = time.strftime("%Y-%m-%d", lt)
        if dk not in wanted:
            continue
        model = e[2] if len(e) > 2 else ""
        buckets.setdefault(dk, {})
        buckets[dk][model or "(unknown)"] = buckets[dk].get(model or "(unknown)", 0) + int(e[1])
    out: dict[str, str] = {}
    for dk, by_m in buckets.items():
        if not by_m:
            continue
        top = max(by_m.items(), key=lambda kv: (kv[1], kv[0]))
        out[dk] = short_model(top[0])
    return out


def _mini_bar(tokens: int, max_tokens: int, enabled: bool) -> str:
    if max_tokens <= 0 or tokens <= 0:
        bar = _BAR_EMPTY * BAR_CELLS
    else:
        filled = int(round(BAR_CELLS * min(1.0, tokens / max_tokens)))
        filled = max(0, min(BAR_CELLS, filled))
        bar = _BAR_FILLED * filled + _BAR_EMPTY * (BAR_CELLS - filled)
    return c.violet(bar, enabled) if enabled else bar


def _pretty_date(label: str) -> str:
    """'2026-07-02' -> 'Jul 02'; TOTAL stays TOTAL."""
    if label == "TOTAL" or not label:
        return label
    try:
        y, m, d = label.split("-")
        months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
        return f"{months[int(m) - 1]} {int(d):02d}"
    except Exception:
        return label


def render_past(
    rows: list[LedgerRow] | list,
    width: int,
    enabled: bool,
    *,
    days: int = 14,
    tops: dict[str, str] | None = None,
    show_cost: bool = True,
    title: str | None = None,
) -> list[str]:
    """Pure past panel lines.

    Width-responsive (ccusage-style collapse):
      width < 72  — drop mini-bar
      width < 100 — drop top: model column
    Cost column omitted when show_cost is False (cost_mode=off).
    """
    from ..cli.colors import display_width

    tops = tops or {}
    day_rows = [r for r in (rows or []) if getattr(r, "label", None) != "TOTAL"]
    total = next((r for r in (rows or []) if getattr(r, "label", None) == "TOTAL"), None)
    max_tok = max((int(getattr(r, "tokens", 0) or 0) for r in day_rows), default=0)

    show_bar = width >= 72
    show_top = width >= 100
    header = title or f"Past — last {days} days"
    out: list[str] = [c.dim(header, enabled)]

    if not day_rows:
        out.append("")
        out.append(c.dim("  (no usage in this window)", enabled))
        return out

    for r in day_rows:
        lab = _pretty_date(getattr(r, "label", ""))
        toks = int(getattr(r, "tokens", 0) or 0)
        parts = [f"{lab:<6}"]
        if show_bar:
            parts.append(_mini_bar(toks, max_tok, enabled))
        parts.append(f"{_fmt_tok(toks):>6}")
        if show_cost:
            parts.append(f"{_fmt_usd(getattr(r, 'cost', None)):>8}")
        pct = getattr(r, "pct_cap", None)
        if pct is not None and width >= 60:
            pct_s = f"{pct:.0f}%"
            parts.append(c.gauge(pct_s, float(pct), enabled) if enabled else pct_s)
        if show_top:
            top = tops.get(getattr(r, "label", ""), "")
            if top:
                parts.append(c.dim(f"top: {top}", enabled))
        line = "  ".join(parts)
        if display_width(line) > width:
            # hard truncate keeping ANSI safe enough for dim lines
            line = line[: max(0, width)]
        out.append(line)

    out.append(c.dim("─" * min(width, 48), enabled))
    if total is not None:
        tparts = [f"{'TOTAL':<6}"]
        if show_bar:
            tparts.append(" " * BAR_CELLS)
        tparts.append(f"{_fmt_tok(int(total.tokens or 0)):>6}")
        if show_cost:
            tparts.append(f"{_fmt_usd(total.cost):>8}")
        if total.pct_cap is not None and width >= 60:
            tparts.append(f"{total.pct_cap:.0f}%")
        out.append("  ".join(tparts))
        unp = int(total.unpriced_tokens or 0)
        if unp > 0 and show_cost:
            out.append(c.dim(f"  (+{_fmt_tok(unp)} tokens unpriced)", enabled))
    return out


def render_past_sections(
    sections: list[dict],
    width: int,
    enabled: bool,
    *,
    days: int = 14,
    show_cost: bool = True,
) -> list[str]:
    """Stack one render_past panel per profile section (multi-sub)."""
    if not sections:
        return render_past([], width, enabled, days=days, show_cost=show_cost)
    out: list[str] = []
    for i, sec in enumerate(sections):
        if i:
            out.append("")
        prof = sec.get("profile") or "default"
        rows = sec.get("rows") or []
        # rebuild LedgerRow if rows arrived as dicts (CLI JSON shape)
        ledger = []
        for r in rows:
            if isinstance(r, LedgerRow):
                ledger.append(r)
            elif isinstance(r, dict):
                ledger.append(
                    LedgerRow(
                        label=r.get("label", ""),
                        tokens=int(r.get("tokens", 0) or 0),
                        cost=r.get("cost"),
                        unpriced_tokens=int(r.get("unpriced_tokens", 0) or 0),
                        pct_cap=r.get("pct_cap"),
                    )
                )
        tops = sec.get("tops") or {}
        title = f"Past — {prof} · last {days} days"
        out.extend(
            render_past(
                ledger,
                width,
                enabled,
                days=days,
                tops=tops,
                show_cost=show_cost,
                title=title,
            )
        )
    return out
