"""Neutral data contracts shared by core math and consumers. Sources emit
neutral event records (see core/events.py); minimally bare (timestamp,
tokens) tuples — see ADAPTERS.md."""

from dataclasses import dataclass


@dataclass
class Window:
    """A usage window the forecast targets.

    anchor is None  -> rolling-from-first-event (Anthropic 5h-block style):
                       the window starts at its first event and re-anchors
                       to the first event after each expiry.
    anchor is set   -> fixed grid: window starts at anchor + n*period_secs.

    model (optional): if set, only events whose model contains this substring
                      (case-insensitive) contribute to this window's used.
                      Enables e.g. "fable" specific limits for Claude.
    """

    name: str
    cap: int
    period_secs: int
    anchor: float | None = None
    model: str | None = None


@dataclass
class Forecast:
    """A computed usage window forecast. The `profile` tags the subscription
    (e.g. "claude", "grok") for multi-subscription support. Backward-compat:
    defaults to "default" so single-source code and old tests continue to work."""

    window: str
    used: int
    cap: int
    projected_pct: float
    eta_to_cap_secs: float | None
    reset_in_secs: float
    idle: bool
    confidence: float = 1.0
    profile: str = "default"
