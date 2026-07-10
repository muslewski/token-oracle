"""Pure extraction for Claude: row-scoped facts only.

Collects per-progressbar (or session container) rows with their label/text + aria values,
classifies strictly from the row's own content (never whole-page), emits LiveReading
with evidence. This separates "Fable" meter from "All models" and stops nav text
from polluting readings.

Network JSON path is intentionally a no-op until real captured claude payloads
are turned into fixtures (see Step 2).
"""

import re
from typing import Any

from .contract import (
    CONF_HIGH,
    CONF_MEDIUM,
    METRIC_FIVE_HOUR_PCT,
    METRIC_FIVE_HOUR_STATE,
    METRIC_MODEL_WEEKLY_PCT,
    METRIC_RESET_AT,
    METRIC_WEEKLY_PCT,
    LiveReading,
)
from .extract_common import (  # noqa: F401 - reused by callers (web + tests) per plan
    build_provider_live,
    merge_readings,
    monotonic_guard,
)
from .grok_extract import readings_from_reset_text


def classify_row(label: str) -> tuple[str, str | None] | None:
    """Classify a row container's label (or fallback text) to a metric.

    Returns (metric, model_or_None) or None (ignore this row).
    Only rows whose *own* text mentions the label are considered — this
    is what prevents "Fable" in the model picker nav from becoming a reading.
    """
    if not label:
        return None
    s = label
    # All models weekly (main pool)
    if re.search(r"(?i)\ball\s*models\b", s):
        return (METRIC_WEEKLY_PCT, None)
    # Premium model row (fable etc) — but only if "all models" not also in this label
    m_model = re.search(r"(?i)\b(fable|opus|sonnet|haiku)\b", s)
    if m_model and not re.search(r"(?i)\ball\s*models\b", s):
        return (METRIC_MODEL_WEEKLY_PCT, m_model.group(1).lower())
    # 5h / current session
    if re.search(r"(?i)(current\s*session|5.?h|5-hour|session\s*limit)", s):
        return (METRIC_FIVE_HOUR_PCT, None)
    return None


def _scale_pct(valuenow: Any, valuemax: Any) -> float | None:
    """Return 0-100 float or None. Handles 0-1 fractions or raw counts."""
    try:
        if valuenow is None:
            return None
        num = float(valuenow)
        if valuemax is not None:
            mx = float(valuemax)
            if mx > 0:
                if mx <= 1.0 and num <= 1.0:
                    num = num * 100.0
                else:
                    num = num / mx * 100.0
        else:
            if 0 < num <= 1.0:
                num = num * 100.0
        val = round(num, 1)
        if 0 <= val <= 100:
            return val
    except Exception:
        pass
    return None


def _first_pct_in_text(text: str) -> float | None:
    r"""First \d{1,3}(?:\.\d)? % strictly inside this row's text."""
    if not text:
        return None
    m = re.search(r"(\d{1,3}(?:\.\d)?)\s*%", text)
    if m:
        try:
            v = round(float(m.group(1)), 1)
            if 0 <= v <= 100:
                return v
        except Exception:
            pass
    return None


def readings_from_rows(rows: list[dict], now: float) -> list[LiveReading]:
    """Turn collected row dicts into LiveReadings. Row-scoped only.

    Row shape: {"valuenow": str|None, "valuemax": str|None, "label": str, "text": str}
    Classification prefers label, falls back to text. Pct from aria preferred.
    """
    readings: list[LiveReading] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip()
        text = str(row.get("text") or "").strip()
        vn = row.get("valuenow")
        vm = row.get("valuemax")

        cls = classify_row(label) or classify_row(text)
        if cls is None:
            continue
        metric, model = cls

        # pct priority: aria scaled (high) else text % (medium)
        val = _scale_pct(vn, vm)
        extractor = "claude.usage_row.aria"
        conf = CONF_HIGH
        if val is None:
            val = _first_pct_in_text(text)
            if val is None:
                continue
            extractor = "claude.usage_row.text"
            conf = CONF_MEDIUM

        # build evidence: label + value snippet
        ev_parts = [label or text[:80]]
        # include a small snippet of matched value
        if "%" in (text or ""):
            m = re.search(r"\d+(?:\.\d)?\s*%", text)
            if m:
                ev_parts.append(text[max(0, m.start() - 10) : m.end() + 10].strip())
        evidence = " | ".join(p for p in ev_parts if p)[:160]

        readings.append(
            LiveReading(
                provider="claude",
                metric=metric,
                value=val,
                confidence=conf,
                extractor=extractor,
                evidence=evidence,
                fetched_at=now,
                model=model,
            )
        )

        # companion reset_at from *this row's* text (if parses)
        rst = _parse_reset_companion(text or label, now)
        if rst is not None:
            readings.append(rst)

    return readings


def _parse_reset_companion(text: str, now: float) -> LiveReading | None:
    """If row text contains a 'resets ...' phrase, try to parse relative time
    by reusing grok's rule. Attach only on successful parse; raw phrase in evidence.
    """
    if not text:
        return None
    m = re.search(r"(?i)\bresets?\b[^\n]{0,80}", text)
    if not m:
        return None
    phrase = m.group(0).strip()
    # Reuse the relative-time rule (grok_extract); it will only emit on parseable rel time
    try:
        rs = readings_from_reset_text([phrase], now)
        for r in rs:
            if r.metric == METRIC_RESET_AT and r.value is not None:
                return LiveReading(
                    provider="claude",
                    metric=METRIC_RESET_AT,
                    value=r.value,
                    confidence=CONF_MEDIUM,
                    extractor="claude.usage_row.reset",
                    evidence=phrase[:160],
                    fetched_at=now,
                )
    except Exception:
        pass
    # unparseable: do not attach reading (raw phrase noted only if we had a reading)
    return None


def five_hour_state_from_rows(rows: list[dict], now: float) -> LiveReading | None:
    """Row-scoped only: look inside a five-hour-classified row for idle phrasing."""
    state_re = re.compile(
        r"(?i)(starts?\s+when\s+(a|you)\s+(message|send)|not\s+(yet\s+)?active|begins\s+when)"
    )
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "")
        text = str(row.get("text") or "")
        cls = classify_row(label) or classify_row(text)
        if cls is None or cls[0] != METRIC_FIVE_HOUR_PCT:
            continue
        container = (text or label or "").lower()
        if state_re.search(container):
            return LiveReading(
                provider="claude",
                metric=METRIC_FIVE_HOUR_STATE,
                value="starts_on_first_message",
                confidence=CONF_HIGH,
                extractor="claude.session_state",
                evidence=(text or label)[:160],
                fetched_at=now,
            )
    return None


def distinctness_check(readings: list[LiveReading]) -> list[LiveReading]:
    """If model_weekly and weekly came from the *same* source row (identical label-ish evidence),
    drop the model one (it was a double-match on the "All models" row).
    If different rows, keep both (even if numeric values happen to match).
    """
    if not readings:
        return readings
    weekly = [r for r in readings if r.metric == METRIC_WEEKLY_PCT]
    model_w = [r for r in readings if r.metric == METRIC_MODEL_WEEKLY_PCT]
    if not weekly or not model_w:
        return readings

    # group by a normalized "row key" derived from evidence (the label part before | )
    def _row_key(ev: str) -> str:
        if not ev:
            return ""
        # evidence often "All models | 38% ..." or just the label
        head = ev.split("|")[0].strip().lower()
        return head

    kept = list(readings)
    for mw in model_w:
        mw_key = _row_key(mw.evidence)
        for w in weekly:
            if _row_key(w.evidence) == mw_key:
                # same source row → this model reading is spurious double-match; drop it
                if mw in kept:
                    kept.remove(mw)
                break
    return kept


def readings_from_network_json(url: str, obj: dict, now: float) -> list[LiveReading]:
    """Claude network JSON extraction (if any usage payloads are ever captured).

    Start conservative: exact allowlist only. No substring hints.
    Return [] (with comment) until a real captured payload exists as a fixture.
    An honest no-op is preferred over fuzzy matching.
    """
    # tighten from real capture — do not guess keys until we have a fixture
    # from an actual claude.ai network response containing usage/limit/reset.
    if not isinstance(obj, dict):
        return []
    # For now: emit nothing. First real payload → fixture + explicit allowlist
    # (modeled on grok's exact_pct_keys + used/limit pair rule).
    return []
