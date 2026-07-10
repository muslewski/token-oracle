"""Pure extraction: page facts in, LiveReadings out. Every reading cites its
evidence. No generic fallbacks: a percentage with no recognized label is not
data, it is noise. Returns [] rather than guessing."""

import re
from typing import Any

from .contract import (
    CONF_HIGH,
    CONF_MEDIUM,
    METRIC_RATE_WINDOW,
    METRIC_RESET_AT,
    METRIC_WEEKLY_PCT,
    LiveReading,
)
from .extract_common import (  # noqa: F401 - re-exports for callers
    _make_reading,
    build_provider_live,
    merge_readings,
    monotonic_guard,
)

# Re-exports so that "from .grok_extract import build_provider_live" etc continue
# to work for web.py and tests/test_live_grok_extract.py (zero caller changes).


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
