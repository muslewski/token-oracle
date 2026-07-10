"""Adapter from the legacy fetcher dicts (live/web.py) to typed ProviderLive.
Deliberately conservative: every percentage produced by the old regex
heuristics is CONF_LOW (withheld from display); only structurally-anchored
facts get medium/high. Plans 031/032 replace the fetchers with extractors
that emit high-confidence readings natively."""

from .contract import (
    ProviderLive,
    LiveReading,
    STATE_OK,
    STATE_RATE_DATA_ONLY,
    STATE_AUTH_NO_DATA,
    STATE_NEEDS_LOGIN,
    CONF_HIGH,
    CONF_MEDIUM,
    CONF_LOW,
    METRIC_WEEKLY_PCT,
    METRIC_MODEL_WEEKLY_PCT,
    METRIC_FIVE_HOUR_PCT,
    METRIC_FIVE_HOUR_STATE,
    METRIC_RESET_AT,
    METRIC_RATE_WINDOW,
)


def _evidence(raw: dict | None, key_fallback: str) -> str:
    if not raw:
        return key_fallback
    ev = raw.get("scrape_note") or raw.get("final_url") or raw.get("note") or key_fallback
    if isinstance(ev, str):
        return ev[:160]
    return str(ev)[:160]


def _make_reading(provider: str, metric: str, value, confidence: str, extractor: str, evidence: str, fetched_at: float, model: str | None = None) -> LiveReading:
    return LiveReading(
        provider=provider,
        metric=metric,
        value=value,
        confidence=confidence,
        extractor=extractor,
        evidence=evidence,
        fetched_at=fetched_at,
        model=model,
    )


def provider_live_from_legacy(provider: str, raw: dict | None, now: float) -> ProviderLive:
    """Convert legacy scraper dict (or None) into a ProviderLive with conservative
    confidence levels. Usage percentages from legacy are always CONF_LOW so they
    are withheld from display by overlay until honest extractors land.
    """
    prov = provider.lower()
    if prov not in ("grok", "claude"):
        prov = "claude" if "claude" in prov else "grok"

    readings: list[LiveReading] = []
    state = STATE_NEEDS_LOGIN
    note = (raw or {}).get("scrape_note") or (raw or {}).get("final_url") or ""
    if isinstance(note, str):
        note = note[:160]

    if raw is None:
        # no data at all
        return ProviderLive(provider=prov, state=STATE_NEEDS_LOGIN, readings=[], fetched_at=now, error=None, note=note)

    auth = bool(raw.get("authenticated"))
    has_usage = False

    # Grok weekly (build or overall)
    if prov == "grok":
        pct = None
        if raw.get("build_pct") is not None:
            pct = float(raw["build_pct"])
            key = "build_pct"
        elif raw.get("overall_pct") is not None:
            pct = float(raw["overall_pct"])
            key = "overall_pct"
        if pct is not None:
            readings.append(_make_reading(
                prov, METRIC_WEEKLY_PCT, pct, CONF_LOW,
                "grok.legacy", _evidence(raw, key), now
            ))
            has_usage = True

    # Claude weekly all + fable
    if prov == "claude":
        if raw.get("all_pct") is not None:
            pct = float(raw["all_pct"])
            readings.append(_make_reading(
                prov, METRIC_WEEKLY_PCT, pct, CONF_LOW,
                "claude.legacy", _evidence(raw, "all_pct"), now
            ))
            has_usage = True
        if raw.get("fable_pct") is not None:
            pct = float(raw["fable_pct"])
            readings.append(_make_reading(
                prov, METRIC_MODEL_WEEKLY_PCT, pct, CONF_LOW,
                "claude.legacy", _evidence(raw, "fable_pct"), now, model="fable"
            ))
            has_usage = True
        if raw.get("five_hour_pct") is not None:
            pct = float(raw["five_hour_pct"])
            readings.append(_make_reading(
                prov, METRIC_FIVE_HOUR_PCT, pct, CONF_LOW,
                "claude.legacy", _evidence(raw, "five_hour_pct"), now
            ))
            has_usage = True

    # five_hour_state (medium even from legacy, as it's structural)
    if raw.get("five_hour_state") == "starts_on_first_message":
        readings.append(_make_reading(
            prov, METRIC_FIVE_HOUR_STATE, "starts_on_first_message", CONF_MEDIUM,
            "claude.legacy", _evidence(raw, "five_hour_state"), now
        ))

    # Grok rate window (high, but info-only metric)
    if raw.get("query_remaining") is not None and raw.get("query_total") is not None:
        qrem = raw.get("query_remaining")
        qtot = raw.get("query_total")
        try:
            qrem = float(qrem); qtot = float(qtot)
            if qtot > 0:
                used_pct = (qtot - qrem) / qtot * 100.0
                readings.append(_make_reading(
                    prov, METRIC_RATE_WINDOW, used_pct, CONF_HIGH,
                    "grok.legacy", _evidence(raw, "query_remaining+query_total"), now
                ))
        except Exception:
            pass

    # reset_at (low)
    secs = raw.get("reset_in_secs")
    if secs is not None:
        try:
            reset_val = now + float(secs)
            readings.append(_make_reading(
                prov, METRIC_RESET_AT, reset_val, CONF_LOW,
                "legacy", _evidence(raw, "reset_in_secs"), now
            ))
        except Exception:
            pass

    # State selection per plan: ok ONLY on high usage reading; else rate if present;
    # else authenticated_no_data / needs_login.
    high_usage = any(
        r.confidence == CONF_HIGH and r.metric in (METRIC_WEEKLY_PCT, METRIC_MODEL_WEEKLY_PCT, METRIC_FIVE_HOUR_PCT)
        for r in readings
    )
    has_rate = any(r.metric == METRIC_RATE_WINDOW for r in readings)
    if high_usage:
        state = STATE_OK
    elif has_rate:
        state = STATE_RATE_DATA_ONLY
    elif auth or has_usage:
        # has_usage (low/medium) still means we reached the page while authenticated
        state = STATE_AUTH_NO_DATA
    else:
        state = STATE_NEEDS_LOGIN

    fetched = raw.get("fetched_at") if isinstance(raw.get("fetched_at"), (int, float)) else now
    return ProviderLive(
        provider=prov,
        state=state,
        readings=readings,
        fetched_at=fetched,
        error=raw.get("error"),
        note=note,
    )
