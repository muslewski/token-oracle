"""Shared pure extraction helpers for live providers.

Moved from grok_extract.py (plan 032) so claude_extract and future
providers can reuse merge_readings / monotonic_guard / build_provider_live
without duplication. Grok behavior is unchanged (defaults preserve it).
"""

import re

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
    readings: list[LiveReading], previous_snapshot: dict | None, now: float, provider: str = "grok"
) -> list[LiveReading]:
    """Downgrade unexplained drops in weekly usage (and per-model weekly).

    Keyed by (metric, model) so METRIC_MODEL_WEEKLY_PCT for "fable" is
    independent of the bare METRIC_WEEKLY_PCT. Reset is subscription-global.
    Default provider="grok" preserves exact prior grok behavior.
    """
    if not readings:
        return readings
    snap = previous_snapshot or {}
    provs = snap.get("providers") or {}
    p = provs.get(provider) or {}
    prev_readings = p.get("readings") or []
    prev_by_key: dict[tuple[str, str | None], float | None] = {}
    prev_reset = None
    for r in prev_readings:
        if isinstance(r, dict):
            met = r.get("metric")
            if met in (METRIC_WEEKLY_PCT, METRIC_MODEL_WEEKLY_PCT):
                try:
                    v = r.get("value")
                    val = float(v) if v is not None else None
                    mdl = r.get("model")
                    prev_by_key[(met, mdl)] = val
                except Exception:
                    pass
            if r.get("metric") == METRIC_RESET_AT:
                try:
                    v = r.get("value")
                    prev_reset = float(v) if v is not None else None
                except Exception:
                    pass
        elif hasattr(r, "metric"):
            met = r.metric
            if met in (METRIC_WEEKLY_PCT, METRIC_MODEL_WEEKLY_PCT):
                try:
                    val = float(r.value) if getattr(r, "value", None) is not None else None
                    prev_by_key[(met, getattr(r, "model", None))] = val
                except Exception:
                    pass
            if r.metric == METRIC_RESET_AT:
                try:
                    v = r.value
                    prev_reset = float(v) if v is not None else None
                except Exception:
                    pass

    reset_happened = False
    if prev_reset is not None and prev_reset <= now:
        reset_happened = True

    out: list[LiveReading] = []
    for r in readings:
        if r.metric in (METRIC_WEEKLY_PCT, METRIC_MODEL_WEEKLY_PCT) and r.value is not None:
            pval = prev_by_key.get((r.metric, r.model))
            if pval is not None:
                try:
                    delta = pval - float(r.value)
                    if delta > 2.0 and not reset_happened:
                        ev = r.evidence
                        if "; dropped from" not in ev:
                            ev = ev + f"; dropped from {pval} without observed reset"
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
    readings: list[LiveReading], authenticated: bool, note: str, now: float, provider: str = "grok"
) -> ProviderLive:
    """Select state based on readings present. Provider may be 'grok' or 'claude'."""
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
        provider=provider,
        state=state,
        readings=readings,
        fetched_at=now,
        error=None,
        note=note[:160] if note else "",
    )


def is_bot_challenge(title: str, body_text: str) -> bool:
    """Return True for Cloudflare 'Just a moment...' interstitials that block headless.

    Matches:
    - title containing 'just a moment' (case-insensitive)
    - body containing any of: 'performing security verification',
      'security service to protect', 'cloudflare' (case-insensitive)
    """
    t = (title or "").lower()
    b = (body_text or "").lower()
    if "just a moment" in t:
        return True
    if re.search(r"performing security verification|security service to protect|cloudflare", b):
        return True
    return False
