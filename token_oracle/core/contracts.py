"""Neutral data contracts shared by core math and consumers. Sources emit bare
(timestamp, tokens) tuples — see ADAPTERS.md."""

from dataclasses import dataclass


@dataclass
class Window:
    """A usage window the forecast targets.

    anchor is None  -> rolling-from-first-event (Anthropic 5h-block style):
                       the window starts at its first event and re-anchors
                       to the first event after each expiry.
    anchor is set   -> fixed grid: window starts at anchor + n*period_secs.
    """

    name: str
    cap: int
    period_secs: int
    anchor: float | None = None


@dataclass
class Forecast:
    window: str
    used: int
    cap: int
    projected_pct: float
    eta_to_cap_secs: float | None
    reset_in_secs: float
    idle: bool
    confidence: float = 1.0
