"""Typed live-web readings with provenance. A LiveReading is only ever created
by an extractor that can cite its evidence; consumers apply readings through
overlay.py, which refuses anything not high-confidence and fresh. 'No reliable
live data' is a first-class outcome, never an error."""

from dataclasses import asdict, dataclass, field

# Provider states (superset of the strings get_live_status already uses)
STATE_OK = "ok"  # >=1 high-confidence usage reading
STATE_RATE_DATA_ONLY = "rate_data_only"  # only rate-limit window data
STATE_AUTH_NO_DATA = "authenticated_no_data"  # page loaded, nothing extracted
STATE_NEEDS_LOGIN = "needs_login"
STATE_UNAVAILABLE = "unavailable"  # playwright/venv missing
STATE_ERROR = "error"
STATE_STALE = "stale"  # snapshot older than freshness TTL

CONF_HIGH = "high"  # structured source or label-scoped DOM attribute
CONF_MEDIUM = "medium"  # label-scoped text match, single extractor
CONF_LOW = "low"  # legacy heuristic — NEVER applied to display

# Metric ids. rate_window is a short-term chat rate limit; it must NEVER be
# mapped onto a usage-cap window (that mistake is what this round fixes).
METRIC_WEEKLY_PCT = "weekly_pct"
METRIC_MODEL_WEEKLY_PCT = "model_weekly_pct"  # reading.model says which model
METRIC_FIVE_HOUR_PCT = "five_hour_pct"
METRIC_FIVE_HOUR_STATE = "five_hour_state"  # value: "starts_on_first_message"
METRIC_RESET_AT = "reset_at"  # value: epoch seconds (float)
METRIC_RATE_WINDOW = "rate_window"  # value: used fraction 0-100; info only


@dataclass(frozen=True)
class LiveReading:
    """A single extracted fact from a live page.

    evidence: <=160 chars of the labeled source text / JSON keys (enforce
    truncation at construction site in extractors; documented limit here).
    """

    provider: str  # "grok" | "claude"
    metric: str  # one of the METRIC_* ids
    value: float | str | None
    confidence: str  # CONF_HIGH | CONF_MEDIUM | CONF_LOW
    extractor: str  # e.g. "grok.network_json", "claude.usage_row"
    evidence: str  # <=160 chars of the labeled source text / JSON keys
    fetched_at: float
    model: str | None = None  # for METRIC_MODEL_WEEKLY_PCT, e.g. "fable"


@dataclass
class ProviderLive:
    provider: str
    state: str  # STATE_* value
    readings: list[LiveReading] = field(default_factory=list)
    fetched_at: float | None = None
    error: str | None = None
    note: str = ""  # short human note, e.g. final_url


def live_reading_to_dict(r: LiveReading) -> dict:
    return asdict(r)


def live_reading_from_dict(d: dict) -> LiveReading:
    return LiveReading(
        provider=d["provider"],
        metric=d["metric"],
        value=d.get("value"),
        confidence=d["confidence"],
        extractor=d["extractor"],
        evidence=d["evidence"],
        fetched_at=d["fetched_at"],
        model=d.get("model"),
    )


def provider_live_to_dict(p: ProviderLive) -> dict:
    # asdict recurses into LiveReading items automatically
    return asdict(p)


def provider_live_from_dict(d: dict) -> ProviderLive:
    readings = [live_reading_from_dict(r) for r in (d.get("readings") or [])]
    return ProviderLive(
        provider=d["provider"],
        state=d.get("state", STATE_UNAVAILABLE),
        readings=readings,
        fetched_at=d.get("fetched_at"),
        error=d.get("error"),
        note=d.get("note", ""),
    )
