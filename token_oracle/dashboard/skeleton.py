"""Skeleton / loading frames for the tab shell.

Mirrors web conventions (content placeholders while data loads) so tab
switches stay instant even when the background worker is still chewing
through a large event cache. Pure renderers — no I/O.
"""

from __future__ import annotations

from ..cli import colors as c

_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def spinner_char(i: int) -> str:
    return _SPINNER[int(i) % len(_SPINNER)]


def render_skeleton(
    tab: str,
    width: int,
    enabled: bool,
    *,
    spin: str = "⠋",
    hint: str | None = None,
) -> list[str]:
    """Dim placeholder body for a tab that has never received data."""
    tab = (tab or "present").lower()
    titles = {
        "past": "Past — ledger",
        "present": "Present — live usage",
        "future": "Future — projections",
    }
    title = titles.get(tab, "Loading")
    out = [
        c.dim(title, enabled),
        "",
        c.dim(f"  {spin} loading…", enabled),
    ]
    # fake skeleton rows (gray bars) — familiar web pattern
    bar_w = max(8, min(32, width - 8))
    for _ in range(4):
        out.append(c.dim("  " + "░" * bar_w, enabled))
    out.append("")
    if hint:
        out.append(c.dim(f"  {hint}", enabled))
    else:
        out.append(
            c.dim(
                "  tab switches are instant — numbers fill in when ready",
                enabled,
            )
        )
    return out


def render_stale_banner(enabled: bool, spin: str = "⠋") -> str:
    """One-line 'refreshing' chip for stale-while-revalidate (data still shown)."""
    return c.dim(f"  {spin} updating…", enabled)
