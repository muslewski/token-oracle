"""Pure extraction: page facts in, LiveReadings out. Every reading cites its
evidence. No generic fallbacks: a percentage with no recognized label is not
data, it is noise. Returns [] rather than guessing."""

import datetime as _dt
import re
from typing import Any

from .contract import (
    CONF_HIGH,
    CONF_MEDIUM,
    METRIC_MODEL_WEEKLY_PCT,
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
    # ONLY exact allowlisted percent keys (plan 031: do NOT loosen to any-numeric-value
    # or substring 'hint' checks on usage/quota/build/weekly/percent).
    # The generic used+limit pair path was removed (plan 040) because plan 038 proved
    # grok exposes no clean JSON endpoint for weekly usage — the number lives only in
    # the ?_s=usage modal text. {used,limit} is a ubiquitous generic shape with no
    # anchor to weekly; it fabricated CONF_HIGH weekly % readings from unrelated data.
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

    # top level exact percent keys
    for k in exact_pct_keys:
        if k in obj:
            _emit_pct(obj[k], k)

    # one level deep
    for subk, subv in obj.items():
        if isinstance(subv, dict):
            p = str(subk)
            for k in exact_pct_keys:
                if k in subv:
                    _emit_pct(subv[k], f"{p}.{k}")

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


# --- Usage modal (grok.com/?_s=usage) ---------------------------------------
# The real weekly usage cap lives only in the ?_s=usage modal DOM text (there are
# no aria-valuenow bars, no clean JSON endpoint). Extraction is text-anchored on
# the fixed UI labels. Live-captured shape:
#   "Weekly SuperGrok Heavy Limit 23% used Resets July 17, 2026 at 7:46 AM
#    Grok Build 22% API 1%"

_ABS_RESET_RE = re.compile(
    r"(?i)resets?\s+([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})\s+at\s+(\d{1,2}):(\d{2})\s*([AP]M)"
)
_WEEKLY_LIMIT_RE = re.compile(
    r"(?i)(?:weekly\s+supergrok\s+heavy\s+limit|weekly\b[^%]{0,30}?\blimit)"
    r"\D{0,40}?(\d{1,3}(?:\.\d)?)\s*%\s*used"
)
_GROK_BUILD_RE = re.compile(r"(?i)grok\s*build\D{0,6}(\d{1,3}(?:\.\d)?)\s*%")
_API_RE = re.compile(r"(?i)\bAPI\b\D{0,6}(\d{1,3}(?:\.\d)?)\s*%")


def parse_absolute_reset(text: str, now: float) -> LiveReading | None:
    """Parse 'Resets July 17, 2026 at 7:46 AM' -> METRIC_RESET_AT epoch.

    The date is rendered by grok.com in the viewer's local timezone, so a naive
    strptime + .timestamp() (local) matches what the user sees. Returns None when
    no absolute reset phrase is present or the result is not a plausible future
    reset (within ~40 days).
    """
    if not text:
        return None
    m = _ABS_RESET_RE.search(text)
    if not m:
        return None
    month, day, year, hh, mm, ap = m.groups()
    try:
        dt = _dt.datetime.strptime(
            f"{month} {day} {year} {hh}:{mm} {ap.upper()}", "%B %d %Y %I:%M %p"
        )
        epoch = dt.timestamp()  # naive -> local tz, matches grok.com's rendering
    except Exception:
        return None
    if not (now < epoch < now + 40 * 86400):
        return None
    return LiveReading(
        provider="grok",
        metric=METRIC_RESET_AT,
        value=epoch,
        confidence=CONF_HIGH,
        extractor="grok.usage_modal.reset",
        evidence=m.group(0)[:160],
        fetched_at=now,
    )


def readings_from_usage_modal(text: str, now: float) -> list[LiveReading]:
    """Extract grok's weekly usage cap from the ?_s=usage modal text.

    Anchored strictly on the 'Weekly ... Limit ... N% used' label — a bare N%
    with no weekly-limit label emits nothing (that is noise, per the contract).
    Also emits the Grok Build / API sub-breakdown as model_weekly_pct readings,
    and the absolute reset time.
    """
    readings: list[LiveReading] = []
    if not text:
        return readings

    m = _WEEKLY_LIMIT_RE.search(text)
    if m:
        try:
            val = round(float(m.group(1)), 1)
            if 0 <= val <= 100:
                readings.append(
                    LiveReading(
                        provider="grok",
                        metric=METRIC_WEEKLY_PCT,
                        value=val,
                        confidence=CONF_HIGH,
                        extractor="grok.usage_modal.text",
                        evidence=text[max(0, m.start()) : m.end() + 20][:160],
                        fetched_at=now,
                    )
                )
        except Exception:
            pass

    # Sub-breakdown: only trust the API row when the Grok Build row is also present
    # (they always render together in the modal). This stops a stray "API" elsewhere
    # on the page from becoming a reading.
    gb = _GROK_BUILD_RE.search(text)
    if gb:
        try:
            gbv = round(float(gb.group(1)), 1)
            if 0 <= gbv <= 100:
                readings.append(
                    LiveReading(
                        provider="grok",
                        metric=METRIC_MODEL_WEEKLY_PCT,
                        value=gbv,
                        confidence=CONF_HIGH,
                        extractor="grok.usage_modal.text",
                        evidence=gb.group(0)[:160],
                        fetched_at=now,
                        model="grok_build",
                    )
                )
        except Exception:
            pass
        api = _API_RE.search(text)
        if api:
            try:
                apv = round(float(api.group(1)), 1)
                if 0 <= apv <= 100:
                    readings.append(
                        LiveReading(
                            provider="grok",
                            metric=METRIC_MODEL_WEEKLY_PCT,
                            value=apv,
                            confidence=CONF_HIGH,
                            extractor="grok.usage_modal.text",
                            evidence=api.group(0)[:160],
                            fetched_at=now,
                            model="api",
                        )
                    )
            except Exception:
                pass

    rst = parse_absolute_reset(text, now)
    if rst is not None:
        readings.append(rst)
    return readings
