"""Shared hermetic fixtures for the suite.

CLI surfaces (statusline, forecast, doctor, report, tmux) read ratelimits /
live / cache under ``$XDG_DATA_HOME`` and may resolve config via
``$XDG_CONFIG_HOME`` or ``$TOKEN_ORACLE_CONFIG``. Adaptive statusline also
reads ``$COLUMNS`` / ``$ORACLE_STATUS_WIDTH``.

Without isolation, a real machine snapshot (notably
``~/.local/share/token-oracle/ratelimits.json``) flips ``oracle statusline``
into the header-headline path (``◔ 5h N% · wk M%``) and drops used/cap
tokens — suite failures that depend on host state and collection order.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _hermetic_xdg_and_term(monkeypatch, tmp_path):
    """Point XDG at per-test tmp; clear width/config env that leak across hosts."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "_xdg_data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "_xdg_config"))
    monkeypatch.delenv("TOKEN_ORACLE_CONFIG", raising=False)
    monkeypatch.delenv("COLUMNS", raising=False)
    monkeypatch.delenv("ORACLE_STATUS_WIDTH", raising=False)
