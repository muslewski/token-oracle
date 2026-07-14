"""Shared dash state between the UI paint loop and a background data worker.

Web conventions we mirror (without a browser):
  - UI thread never blocks on I/O / heavy compute (requestAnimationFrame-ish)
  - Stale-while-revalidate: keep showing last good payload while a refresh runs
  - Skeleton / loading placeholders until the first payload arrives
  - Data fetching lives off the main thread (classic SPA worker / React Query)

Stdlib only: threading + lock. All fields are replaced atomically under the lock
so readers always see a consistent snapshot.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class DashSnapshot:
    """Immutable-ish view the UI paints from. Build a new one per publish."""

    forecasts: list = field(default_factory=list)
    cells: dict = field(default_factory=dict)
    snap: dict = field(default_factory=dict)
    past_sections: list | None = None  # None = never loaded
    profile: list | None = None
    cost_line: str | None = None
    reset_msg: str = ""
    reset_until: float = 0.0
    # loading flags: True while a refresh is in flight
    loading_present: bool = True
    loading_past: bool = True
    loading_future: bool = True
    # first successful publish
    has_present: bool = False
    has_past: bool = False
    has_future: bool = False
    updated_at: float = 0.0
    error: str | None = None


class DashStore:
    """Thread-safe mailbox. UI calls snapshot(); worker calls publish_*()."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._s = DashSnapshot()
        self._last_fs: list | None = None  # for reset detection (worker-owned under lock)

    def snapshot(self) -> DashSnapshot:
        with self._lock:
            s = self._s
            # shallow copy so UI can mutate animation state without racing
            return DashSnapshot(
                forecasts=list(s.forecasts),
                cells=dict(s.cells),
                snap=dict(s.snap) if isinstance(s.snap, dict) else {},
                past_sections=list(s.past_sections) if s.past_sections is not None else None,
                profile=list(s.profile) if s.profile is not None else s.profile,
                cost_line=s.cost_line,
                reset_msg=s.reset_msg,
                reset_until=s.reset_until,
                loading_present=s.loading_present,
                loading_past=s.loading_past,
                loading_future=s.loading_future,
                has_present=s.has_present,
                has_past=s.has_past,
                has_future=s.has_future,
                updated_at=s.updated_at,
                error=s.error,
            )

    def set_loading(self, which: str, on: bool) -> None:
        with self._lock:
            if which == "present":
                self._s.loading_present = on
            elif which == "past":
                self._s.loading_past = on
            elif which == "future":
                self._s.loading_future = on

    def publish_present(self, forecasts, cells, snap, reset_msg="", reset_until=0.0) -> None:
        with self._lock:
            self._s.forecasts = list(forecasts or [])
            self._s.cells = dict(cells or {})
            self._s.snap = dict(snap or {}) if isinstance(snap, dict) else {}
            if reset_msg:
                self._s.reset_msg = reset_msg
                self._s.reset_until = reset_until
            self._s.loading_present = False
            self._s.has_present = True
            self._s.updated_at = time.time()
            self._s.error = None

    def publish_past(self, sections) -> None:
        with self._lock:
            self._s.past_sections = list(sections or [])
            self._s.loading_past = False
            self._s.has_past = True
            self._s.updated_at = time.time()

    def publish_future(self, profile, cost_line) -> None:
        with self._lock:
            self._s.profile = list(profile) if profile is not None else None
            self._s.cost_line = cost_line
            self._s.loading_future = False
            self._s.has_future = True
            self._s.updated_at = time.time()

    def publish_error(self, msg: str) -> None:
        with self._lock:
            self._s.error = msg
            self._s.loading_present = False
            self._s.loading_past = False
            self._s.loading_future = False

    def take_prev_forecasts(self):
        """Worker: get last forecasts for reset detection and store current later."""
        with self._lock:
            return self._last_fs

    def set_prev_forecasts(self, fs) -> None:
        with self._lock:
            self._last_fs = list(fs) if fs is not None else None
