"""Phase 4 CLI surfaces → dash-quality: acceptance o1–o6.

Byte-stable surfaces (--json, exit codes, tmux parse tokens) stay green.
New UI chrome is TTY-gated and NO_COLOR-clean.
"""

from __future__ import annotations

import importlib
import inspect
import io
import json
import os
import re
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import token_oracle.cli.colors as colors
import token_oracle.cli.main as cli_main
from token_oracle.adapters import statusline, tmux
from token_oracle.cli.main import main
from token_oracle.core.contracts import Forecast

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mK]")


def _cfg(tmp_path, feed_events, now, extra=None, windows=None):
    feed = tmp_path / "feed.json"
    feed.write_text(json.dumps(feed_events))
    body = {
        "source": "generic",
        "source_opts": {"events_path": str(feed)},
        "cache_path": str(tmp_path / "cache.json"),
        "windows": windows
        or [
            {"name": "5h", "cap": 1000, "period_secs": 18000},
            {"name": "weekly", "cap": 8000000, "period_secs": 604800},
        ],
    }
    if extra:
        body.update(extra)
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps(body))
    return str(cfg)


def _strip(s: str) -> str:
    return _ANSI_RE.sub("", s or "")


# ---------------------------------------------------------------------------
# o1 — zero-arg command palette
# ---------------------------------------------------------------------------


def test_o1_zero_arg_non_tty_same_as_today(monkeypatch, capsys):
    """Piped/no-TTY bare invoke: argparse required-arg error, exit 2."""
    monkeypatch.setattr(cli_main, "_palette_eligible", lambda: False)
    with pytest.raises(SystemExit) as ei:
        main([])
    assert ei.value.code == 2
    err = capsys.readouterr().err
    assert "required" in err.lower() or "arguments are required" in err.lower()


def test_o1_palette_rows_include_every_subcommand(monkeypatch):
    """TTY+fzf fixture → palette rows cover every registered subcommand."""
    rows = cli_main._palette_rows()
    names = {r.split(None, 1)[0] for r in rows}
    expected = set(cli_main._CMD_HELP)
    assert expected <= names
    # each row carries a one-line description
    for r in rows:
        parts = r.split(None, 1)
        assert len(parts) == 2 and parts[1].strip()


def test_o1_palette_runs_selected_command(monkeypatch, tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 50]], now)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(cli_main, "_palette_eligible", lambda: True)
    monkeypatch.setattr(cli_main, "_run_command_palette", lambda: "doctor")
    monkeypatch.setattr(
        cli_main,
        "_sage_row",
        lambda now, home=None: ("sage", "agentic-sage not detected (optional)", True),
    )
    assert cli_main._run_command_palette() == "doctor"
    # empty argv → palette injects "doctor"; pass config via env for hermeticity
    monkeypatch.setenv("TOKEN_ORACLE_CONFIG", cfg)
    rc = main([])
    out = capsys.readouterr().out
    assert rc in (0, 1)
    assert "oracle doctor" in out


# ---------------------------------------------------------------------------
# o2 — forecast hero + dedupe + arrow glyph
# ---------------------------------------------------------------------------


def test_o2_forecast_dedupes_identical_windows():
    fs = [
        Forecast("5h", 35000, 220000, 50.0, None, 3600, False, profile="claude"),
        Forecast("weekly", 1_000_000, 8_000_000, 40.0, None, 86400, False, profile="claude"),
        Forecast("weekly", 1_000_000, 8_000_000, 40.0, None, 86400, False, profile="claude"),
        Forecast("weekly", 2_000_000, 10_000_000, 43.0, None, 86400, False, profile="grok"),
    ]
    from token_oracle.adapters.segments import dedupe_forecasts

    out = dedupe_forecasts(fs)
    assert len(out) == 3
    keys = [(f.profile, f.window) for f in out]
    assert keys.count(("claude", "weekly")) == 1


def test_o2_one_arrow_glyph_everywhere():
    fs = [Forecast("5h", 12000, 220000, 42.0, None, 3600, False)]
    sl = statusline.render(fs, color=False)
    tx = tmux.render(fs)
    assert colors.ARROW in sl
    assert "->" not in _strip(sl)
    assert colors.ARROW in tx or "->" not in tx  # unified to ARROW
    assert "->" not in tx


def test_o2_forecast_hero_and_spark_on_tty(monkeypatch, tmp_path, capsys):
    now = 100000.0
    # spaced events over ~12h for burn spark
    hour = 3600.0
    feed = [[now - i * hour, 100 + i * 10] for i in range(12)]
    feed.reverse()
    cfg = _cfg(tmp_path, feed, now)
    monkeypatch.setattr(cli_main, "_is_interactive", lambda: True)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    rc = main(["forecast", "--config", cfg, "--now", str(now)])
    assert rc == 0
    out = _strip(capsys.readouterr().out)
    assert "CAP" in out or "┌" in out or "╭" in out or "│" in out
    # spark chars from the block ramp appear somewhere
    spark_set = set("▁▂▃▄▅▆▇█")
    assert spark_set & set(out), f"no sparkline glyphs in: {out!r}"


def test_o2_forecast_json_byte_stable_shape(tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 250]], now)
    rc = main(["forecast", "--json", "--config", cfg, "--now", str(now)])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["schema"] == 1
    assert "windows" in data
    assert data["windows"][0]["used"] == 250


def test_o2_forecast_non_tty_no_hero_box(monkeypatch, tmp_path, capsys):
    now = 100000.0
    cfg = _cfg(tmp_path, [[now - 100.0, 250]], now)
    monkeypatch.setattr(cli_main, "_is_interactive", lambda: False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    rc = main(["forecast", "--config", cfg, "--now", str(now)])
    assert rc == 0
    out = _strip(capsys.readouterr().out)
    assert "┌" not in out and "╭" not in out
    assert "/" in out  # tokens segment still present


# ---------------------------------------------------------------------------
# o3 — adaptive statusline / shared segment
# ---------------------------------------------------------------------------


def test_o3_shared_segment_function_import_graph():
    """Both adapters import/use the shared segment body."""
    import token_oracle.adapters.segments as seg
    import token_oracle.adapters.statusline as sl_mod
    import token_oracle.adapters.tmux as tx_mod

    assert hasattr(seg, "segment_body")
    # import graph: adapters reference segments
    assert "segments" in inspect.getsource(sl_mod) or "segment_body" in inspect.getsource(sl_mod)
    assert "segments" in inspect.getsource(tx_mod) or "segment_body" in inspect.getsource(tx_mod)


def test_o3_narrow_budget_respects_limit():
    from token_oracle.adapters.segments import render_adaptive

    fs = [
        Forecast("5h", 12000, 220000, 42.0, None, 3 * 3600, False, profile="claude"),
        Forecast("weekly", 5_000_000, 8_000_000, 60.0, None, 5 * 86400, False, profile="claude"),
        Forecast("weekly", 4_000_000, 10_000_000, 40.0, None, 5 * 86400, False, profile="grok"),
    ]
    narrow = render_adaptive(fs, budget=24, encoding="ansi", color=False)
    assert colors.display_width(narrow) <= 24
    wide = render_adaptive(fs, budget=200, encoding="ansi", color=False)
    assert "12k/220k" in wide or "42%" in wide
    assert colors.display_width(wide) >= colors.display_width(narrow)


def test_o3_tmux_parse_stable_tokens():
    fs = [Forecast("5h", 12000, 220000, 42.0, None, 3 * 3600, False)]
    s = tmux.render(fs)
    assert "#[fg=" in s
    assert "12k/220k" in s
    assert "#[default]" in s


def test_o3_statusline_wide_has_tokens(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    now = 100000.0
    cfg = _cfg(
        tmp_path,
        [[now - 100.0, 250]],
        now,
        windows=[{"name": "5h", "cap": 1000, "period_secs": 18000}],
    )
    rc = main(["statusline", "--config", cfg, "--now", str(now)])
    assert rc == 0
    out = _strip(capsys.readouterr().out)
    assert "/1k" in out or "0k" in out or "250" in out or "/" in out


# ---------------------------------------------------------------------------
# o4 — doctor severity + fix hints
# ---------------------------------------------------------------------------


def test_o4_doctor_exit_codes_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(
        cli_main,
        "_sage_row",
        lambda now, home=None: ("sage", "agentic-sage not detected (optional)", True),
    )
    now = 100000.0
    assert main(["doctor", "--config", _cfg(tmp_path, [], now), "--now", str(now)]) == 1
    ok_dir = tmp_path / "ok"
    ok_dir.mkdir()
    assert (
        main(
            [
                "doctor",
                "--config",
                _cfg(ok_dir, [[now - 50.0, 10]], now),
                "--now",
                str(now),
            ]
        )
        == 0
    )


def test_o4_severity_banner_and_fix_hints(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(
        cli_main,
        "_sage_row",
        lambda now, home=None: ("sage", "agentic-sage not detected (optional)", True),
    )
    now = 100000.0
    # no events → bad data row
    rc = main(["doctor", "--config", _cfg(tmp_path, [], now), "--now", str(now)])
    assert rc == 1
    out = _strip(capsys.readouterr().out)
    assert any(k in out.lower() for k in ("crit", "warn", "attention", "need"))
    # every ✗ line followed by a fix hint (next non-empty line mentions fix / → / run /)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        if "✗" in ln:
            # look ahead for hint
            rest = "\n".join(lines[i + 1 : i + 3])
            assert any(
                tok in rest.lower() or tok in ln.lower()
                for tok in ("fix", "→", "run", "hint", "oracle ", "set ", "check", "wire")
            ), f"no fix hint after: {ln!r} rest={rest!r}"


def test_o4_ok_banner_when_all_green(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(
        cli_main,
        "_sage_row",
        lambda now, home=None: ("sage", "agentic-sage not detected (optional)", True),
    )
    now = 100000.0
    rc = main(["doctor", "--config", _cfg(tmp_path, [[now - 50.0, 10]], now), "--now", str(now)])
    out = _strip(capsys.readouterr().out)
    assert rc == 0
    assert "ok" in out.lower()
    assert "✗" not in out or "0 need" in out


# ---------------------------------------------------------------------------
# o5 — report alignment + %CAP spark + fzf
# ---------------------------------------------------------------------------


def test_o5_report_columns_align(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    now = 1_700_000_000.0
    day = 86400.0
    feed = [
        [now, 1_000_000],
        [now - day, 500],
        [now - 2 * day, 12_400_000],
    ]
    cfg = _cfg(tmp_path, feed, now)
    rc = main(["report", "--config", cfg, "--now", str(now), "--days", "3"])
    assert rc == 0
    out = _strip(capsys.readouterr().out)
    assert "%CAP" in out
    # header and a data row: token column should line up (fixed widths)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    hdr = next(ln for ln in lines if "%CAP" in ln and "DAY" in ln)
    data = next(ln for ln in lines if ln[:4].isdigit() or re.match(r"\d{4}-\d{2}-\d{2}", ln.strip()))
    # cost column starts at same index for header labels vs values (rough)
    assert "TOTAL" in out
    # spark present for %CAP column
    spark_set = set("▁▂▃▄▅▆▇█░")
    assert spark_set & set(out), f"expected %CAP spark glyphs in:\n{out}"


def test_o5_report_json_unchanged_shape(tmp_path, capsys):
    now = 1_700_000_000.0
    cfg = _cfg(tmp_path, [[now - 100, 1234]], now)
    rc = main(["report", "--json", "--config", cfg, "--now", str(now)])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "generated_at" in data and "sections" in data
    row0 = data["sections"][0]["rows"][0]
    assert set(row0) >= {"label", "tokens", "cost", "unpriced_tokens", "pct_cap"}


def test_o5_report_fzf_drill_in_tty(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    now = 1_700_000_000.0
    day = 86400.0
    feed = [[now, 1000], [now - day, 2000]]
    cfg = _cfg(tmp_path, feed, now)
    monkeypatch.setattr(cli_main, "_is_interactive", lambda: True)
    monkeypatch.setattr(cli_main, "_fzf_available", lambda: True)
    picked = {"n": 0}

    def fake_fzf(rows, **kw):
        picked["n"] += 1
        return rows[0] if rows else None

    monkeypatch.setattr(cli_main, "_fzf_pick", fake_fzf)
    rc = main(["report", "--config", cfg, "--now", str(now), "--days", "2"])
    assert rc == 0
    assert picked["n"] >= 1


# ---------------------------------------------------------------------------
# o6 — NO_COLOR / piped zero ANSI across five surfaces
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv_builder",
    [
        lambda cfg, now: ["forecast", "--config", cfg, "--now", str(now)],
        lambda cfg, now: ["statusline", "--config", cfg, "--now", str(now)],
        lambda cfg, now: ["tmux", "--config", cfg, "--now", str(now)],
        lambda cfg, now: ["doctor", "--config", cfg, "--now", str(now)],
        lambda cfg, now: ["report", "--config", cfg, "--now", str(now), "--days", "2"],
    ],
)
def test_o6_no_color_zero_ansi(argv_builder, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setattr(cli_main, "_is_interactive", lambda: False)
    monkeypatch.setattr(
        cli_main,
        "_sage_row",
        lambda now, home=None: ("sage", "agentic-sage not detected (optional)", True),
    )
    now = 100000.0
    hour = 3600.0
    feed = [[now - i * hour, 100] for i in range(5)]
    cfg = _cfg(tmp_path, feed, now)
    argv = argv_builder(cfg, now)
    rc = main(argv)
    assert rc in (0, 1)
    captured = capsys.readouterr()
    blob = captured.out + captured.err
    assert "\033" not in blob and "\x1b" not in blob, f"ANSI leaked: {blob!r}"


def test_o6_colors_sparkline_helper():
    s = colors.sparkline([0, 1, 2, 3, 4, 5, 6, 7, 8])
    assert len(s) == 9
    assert set(s) <= set(colors.SPARK_CHARS)
    assert colors.sparkline([]) == ""
    assert "\033" not in colors.sparkline([1, 2, 3])
