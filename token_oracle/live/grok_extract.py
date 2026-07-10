"""Pure extraction: page facts in, LiveReadings out. Every reading cites its
evidence. No generic fallbacks: a percentage with no recognized label is not
data, it is noise. Returns [] rather than guessing."""

import re
from typing import Any

from .contract import (
    CONF_HIGH,
    CONF_LOW,
    CONF_MEDIUM,
    METRIC_FIVE_HOUR_PCT,
    METRIC_MODEL_WEEKLY_PCT,
    METRIC_RATE_WINDOW,
    METRIC_RESET_AT,
    METRIC_WEEKLY_PCT,
    STATE_AUTH_NO_DATA,
    STATE_NEEDS_LOGIN,
    STATE_OK,
    STATE_RATE_DATA_ONLY,
    LiveReading,
    ProviderLive,
)


def _truncate_evidence(ev: str) -> str:
    if not ev:
        return ""
    return ev[:160]


def _make_reading(
    provider: str,
    metric: str,
    value: float | str | None,
    confidence: str,
    extractor: str,
    evidence: str,
    fetched_at: float,
    model: str | None = None,
) -> LiveReading:
    return LiveReading(
        provider=provider,
        metric=metric,
        value=value,
        confidence=confidence,
        extractor=extractor,
        evidence=_truncate_evidence(evidence),
        fetched_at=fetched_at,
        model=model,
    )


def readings_from_network_json(url: str, obj: dict, now: float) -> list[LiveReading]:
    """Extract from network JSON payload. Explicit allowlist only."""
    if not isinstance(obj, dict):
        return []
    readings: list[LiveReading] = []
    u = url or ""

    # Rate window: remainingQueries + totalQueries (2h chat limit, NOT weekly)
    rem = obj.get("remainingQueries")
    tot = obj.get("totalQueries")
    w = obj.get("windowSizeSeconds")
    if isinstance(rem, (int, float)) and isinstance(tot, (int, float)) and tot > 0:
        try:
            used = round((tot - rem) / tot * 100.0, 1)
            ev = f"remainingQueries={rem} totalQueries={tot} windowSizeSeconds={w} url={u[-60:]}"
            readings.append(
                _make_reading(
                    "grok",
                    METRIC_RATE_WINDOW,
                    used,
                    CONF_HIGH,
                    "grok.network_json.rate",
                    ev,
                    now,
                )
            )
        except Exception:
            pass
        # Never emit weekly from this shape.

    # Usage: top-level or one level deep.
    # 1. ONLY exact allowlisted percent keys (plan 031: do NOT loosen to any-numeric-value
    #    or substring 'hint' checks on usage/quota/build/weekly/percent).
    # 2. used+limit pair ONLY when BOTH numeric in the SAME dict (top or 1-deep) and limit>0.
    #    Emit ONE METRIC_WEEKLY_PCT = round(used/limit*100,1), CONF_HIGH; evidence cites both.
    #    Bare used or bare limit emit nothing. No parent-hint loops.
    exact_pct_keys = ("usagePercent", "weeklyUsagePercent", "buildUsagePercent")

    def _emit_pct(val: Any, key_path: str) -> None:
        try:
            if not isinstance(val, (int, float)):
                return
            v = float(val)
            if not (0 <= v <= 100):
                if 0 < v <= 1:
                    v = round(v * 100.0, 1)
                else:
                    return
            val = round(v, 1)
            ev = f"{key_path}={val} url={u[-60:]}"
            readings.append(
                _make_reading(
                    "grok",
                    METRIC_WEEKLY_PCT,
                    val,
                    CONF_HIGH,
                    "grok.network_json.usage",
                    ev,
                    now,
                )
            )
        except Exception:
            pass

    def _try_emit_used_limit_pair(d: dict, prefix: str = "") -> None:
        if not isinstance(d, dict):
            return
        if "used" in d and "limit" in d:
            used = d.get("used")
            limit = d.get("limit")
            if isinstance(used, (int, float)) and isinstance(limit, (int, float)) and limit > 0:
                try:
                    pct = round(float(used) / float(limit) * 100.0, 1)
                    if 0 <= pct <= 100:
                        if prefix:
                            ev = f"{prefix}.used={used} {prefix}.limit={limit} url={u[-60:]}"
                        else:
                            ev = f"used={used} limit={limit} url={u[-60:]}"
                        readings.append(
                            _make_reading(
                                "grok",
                                METRIC_WEEKLY_PCT,
                                pct,
                                CONF_HIGH,
                                "grok.network_json.usage",
                                ev,
                                now,
                            )
                        )
                except Exception:
                    pass

    # top level exact percent keys
    for k in exact_pct_keys:
        if k in obj:
            _emit_pct(obj[k], k)

    # top level used+limit pair
    _try_emit_used_limit_pair(obj)

    # one level deep
    for subk, subv in obj.items():
        if isinstance(subv, dict):
            p = str(subk)
            for k in exact_pct_keys:
                if k in subv:
                    _emit_pct(subv[k], f"{p}.{k}")
            _try_emit_used_limit_pair(subv, p)

    return readings


def readings_from_progressbars(bars: list[dict], now: float) -> list[LiveReading]:
    """Bars collected from DOM: only emit when label matches known usage keywords."""
    readings: list[LiveReading] = []
    label_re = re.compile(r"(?i)\b(grok\s*build|build|heavy|weekly|usage)\b")
    for b in bars or []:
        if not isinstance(b, dict):
            continue
        vnow = b.get("valuenow")
        vmax = b.get("valuemax")
        label = b.get("label") or ""
        if vnow is None or not label:
            continue
        if not label_re.search(str(label)):
            continue
        try:
            num = float(vnow)
            if vmax is not None:
                try:
                    mx = float(vmax)
                    if mx > 0:
                        if mx <= 1.0 and num <= 1.0:
                            num = num * 100.0
                        else:
                            num = num / mx * 100.0
                except Exception:
                    pass
            else:
                if 0 < num <= 1.0:
                    num *= 100.0
            if not (0 <= num <= 100):
                continue
            val = round(num, 1)
            readings.append(
                _make_reading(
                    "grok",
                    METRIC_WEEKLY_PCT,
                    val,
                    CONF_HIGH,
                    "grok.progressbar",
                    str(label)[:120],
                    now,
                )
            )
        except Exception:
            pass
    return readings


def readings_from_labeled_text(sections: list[str], now: float) -> list[LiveReading]:
    """Labeled section texts: anchor to explicit build/weekly label + % or rate frac."""
    readings: list[LiveReading] = []
    pct_re = re.compile(r"(\d{1,3}(?:\.\d)?)\s*%")
    frac_re = re.compile(r"(\d+)\s*/\s*(\d+)")
    label_build_re = re.compile(r"(?i)(grok\s*build|build|heavy|weekly)\b")
    rate_label_re = re.compile(r"(?i)quer|rate|per\s*\d+\s*h")

    for sec in sections or []:
        if not isinstance(sec, str):
            continue
        s = sec
        # weekly/build %
        if label_build_re.search(s):
            m = pct_re.search(s)
            if m:
                try:
                    val = round(float(m.group(1)), 1)
                    if 0 <= val <= 100:
                        ev = s[max(0, m.start() - 40) : m.end() + 40]
                        readings.append(
                            _make_reading(
                                "grok",
                                METRIC_WEEKLY_PCT,
                                val,
                                CONF_MEDIUM,
                                "grok.labeled_text",
                                ev,
                                now,
                            )
                        )
                except Exception:
                    pass
                continue  # one reading max per section for this
        # rate frac in rate-ish section (never weekly)
        if rate_label_re.search(s):
            fm = frac_re.search(s)
            if fm:
                try:
                    used = float(fm.group(1))
                    tot = float(fm.group(2))
                    if tot > 0:
                        val = round(used / tot * 100.0, 1)
                        if 0 <= val <= 100:
                            ev = s[max(0, fm.start() - 30) : fm.end() + 30]
                            readings.append(
                                _make_reading(
                                    "grok",
                                    METRIC_RATE_WINDOW,
                                    val,
                                    CONF_MEDIUM,
                                    "grok.labeled_text",
                                    ev,
                                    now,
                                )
                            )
                except Exception:
                    pass
    return readings


def readings_from_reset_text(sections: list[str], now: float) -> list[LiveReading]:
    """Relative reset times anchored to 'reset' keyword."""
    readings: list[LiveReading] = []
    reset_re = re.compile(r"(?i)\breset(s)?\b")
    rel_re = re.compile(r"(\d+)\s*(d|day|h|hr|hour|m|min)")
    for sec in sections or []:
        if not isinstance(sec, str):
            continue
        if not reset_re.search(sec):
            continue
        m = rel_re.search(sec)
        if not m:
            continue
        try:
            val = int(m.group(1))
            unit = m.group(2).lower()
            secs = val * (
                86400
                if "d" in unit or "day" in unit
                else 3600
                if "h" in unit or "hr" in unit
                else 60
            )
            if 120 < secs < 86400 * 32:
                readings.append(
                    _make_reading(
                        "grok",
                        METRIC_RESET_AT,
                        now + float(secs),
                        CONF_MEDIUM,
                        "grok.reset_text",
                        sec[:120],
                        now,
                    )
                )
        except Exception:
            pass
    return readings


def merge_readings(readings: list[LiveReading]) -> list[LiveReading]:
    """Agreement/conflict policy; dedupe identical (metric, extractor)."""
    if not readings:
        return []
    # dedupe identical (metric, extractor) keeping first
    seen: dict[tuple[str, str], LiveReading] = {}
    for r in readings:
        key = (r.metric, r.extractor)
        if key not in seen:
            seen[key] = r

    uniq = list(seen.values())

    # group by metric for weekly mainly
    by_metric: dict[str, list[LiveReading]] = {}
    for r in uniq:
        by_metric.setdefault(r.metric, []).append(r)

    result: list[LiveReading] = []
    for metric, lst in by_metric.items():
        if metric != METRIC_WEEKLY_PCT or len(lst) < 2:
            result.extend(lst)
            continue
        # weekly agreement policy
        kept: list[LiveReading] = []
        n = len(lst)
        any_conflict = False
        for i in range(n):
            for j in range(i + 1, n):
                a = lst[i]
                b = lst[j]
                va = float(a.value) if a.value is not None else 0.0
                vb = float(b.value) if b.value is not None else 0.0
                if abs(va - vb) <= 1.0:
                    # agree within 1pt: keep higher-conf, upgrade to high
                    if a.confidence == CONF_HIGH:
                        winner = a
                    elif b.confidence == CONF_HIGH:
                        winner = b
                    else:
                        ca = 2 if a.confidence == CONF_MEDIUM else 1
                        cb = 2 if b.confidence == CONF_MEDIUM else 1
                        winner = a if ca >= cb else b
                    up = LiveReading(
                        provider=winner.provider,
                        metric=winner.metric,
                        value=winner.value,
                        confidence=CONF_HIGH,
                        extractor=winner.extractor,
                        evidence=winner.evidence,
                        fetched_at=winner.fetched_at,
                        model=winner.model,
                    )
                    if up not in kept:
                        kept.append(up)
                else:
                    any_conflict = True

                    # downgrade pair
                    def _downgrade(r: LiveReading, other: LiveReading) -> LiveReading:
                        ev = r.evidence
                        suffix = f"; conflicts with {other.extractor} {other.value}"
                        if "; conflicts with" not in ev:
                            ev = ev + suffix
                        return LiveReading(
                            provider=r.provider,
                            metric=r.metric,
                            value=r.value,
                            confidence=CONF_LOW,
                            extractor=r.extractor,
                            evidence=_truncate_evidence(ev),
                            fetched_at=r.fetched_at,
                            model=r.model,
                        )

                    ka = _downgrade(a, b)
                    kb = _downgrade(b, a)
                    if ka not in kept:
                        kept.append(ka)
                    if kb not in kept:
                        kept.append(kb)
        if not any_conflict:
            # no conflicts seen: pick best single upgraded
            best = None
            for r in lst:
                if best is None or (r.confidence == CONF_HIGH and best.confidence != CONF_HIGH):
                    best = r
                elif r.confidence == CONF_MEDIUM and best.confidence not in (
                    CONF_HIGH,
                    CONF_MEDIUM,
                ):
                    best = r
            if best is not None:
                up = LiveReading(
                    provider=best.provider,
                    metric=best.metric,
                    value=best.value,
                    confidence=CONF_HIGH,
                    extractor=best.extractor,
                    evidence=best.evidence,
                    fetched_at=best.fetched_at,
                    model=best.model,
                )
                if up not in kept:
                    kept.append(up)
        # dedupe kept
        seen2: dict[tuple[str, str], LiveReading] = {}
        for k in kept:
            kk = (k.metric, k.extractor)
            if kk not in seen2:
                seen2[kk] = k
        result.extend(seen2.values())
    # final dedupe by (metric, extractor)
    final_seen: dict[tuple[str, str], LiveReading] = {}
    for rr in result:
        key = (rr.metric, rr.extractor)
        if key not in final_seen:
            final_seen[key] = rr
    return list(final_seen.values())


def monotonic_guard(
    readings: list[LiveReading], previous_snapshot: dict | None, now: float
) -> list[LiveReading]:
    """Downgrade unexplained drops in weekly usage for grok."""
    if not readings:
        return readings
    snap = previous_snapshot or {}
    provs = snap.get("providers") or {}
    g = provs.get("grok") or {}
    prev_readings = g.get("readings") or []
    prev_weekly = None
    prev_reset = None
    for r in prev_readings:
        if isinstance(r, dict):
            if r.get("metric") == METRIC_WEEKLY_PCT:
                try:
                    v = r.get("value")
                    prev_weekly = float(v) if v is not None else None
                except Exception:
                    pass
            if r.get("metric") == METRIC_RESET_AT:
                try:
                    v = r.get("value")
                    prev_reset = float(v) if v is not None else None
                except Exception:
                    pass
        elif hasattr(r, "metric"):
            if r.metric == METRIC_WEEKLY_PCT:
                prev_weekly = float(r.value) if getattr(r, "value", None) is not None else None
            if r.metric == METRIC_RESET_AT:
                prev_reset = float(r.value) if getattr(r, "value", None) is not None else None

    reset_happened = False
    if prev_reset is not None and prev_reset <= now:
        reset_happened = True

    out: list[LiveReading] = []
    for r in readings:
        if r.metric == METRIC_WEEKLY_PCT and prev_weekly is not None and r.value is not None:
            try:
                delta = prev_weekly - float(r.value)
                if delta > 2.0 and not reset_happened:
                    ev = r.evidence
                    if "; dropped from" not in ev:
                        ev = ev + f"; dropped from {prev_weekly} without observed reset"
                    out.append(
                        LiveReading(
                            provider=r.provider,
                            metric=r.metric,
                            value=r.value,
                            confidence=CONF_LOW,
                            extractor=r.extractor,
                            evidence=_truncate_evidence(ev),
                            fetched_at=r.fetched_at,
                            model=r.model,
                        )
                    )
                    continue
            except Exception:
                pass
        out.append(r)
    return out


def build_provider_live(
    readings: list[LiveReading], authenticated: bool, note: str, now: float
) -> ProviderLive:
    """Select state based on readings present."""
    usage_high = any(
        r.confidence == CONF_HIGH
        and r.metric in (METRIC_WEEKLY_PCT, METRIC_MODEL_WEEKLY_PCT, METRIC_FIVE_HOUR_PCT)
        for r in readings
    )
    has_rate = any(r.metric == METRIC_RATE_WINDOW for r in readings)
    if usage_high:
        state = STATE_OK
    elif has_rate:
        state = STATE_RATE_DATA_ONLY
    elif authenticated:
        state = STATE_AUTH_NO_DATA
    else:
        state = STATE_NEEDS_LOGIN
    return ProviderLive(
        provider="grok",
        state=state,
        readings=readings,
        fetched_at=now,
        error=None,
        note=note[:160] if note else "",
    )
