"""Self-calibrating effective cap per (profile, window) — plan 063 Layer 1 moat.

The server rate-limit header exposes a `used_percentage` but no token cap, and
`usage-limits.json`'s caps are a different unit than local token `used`. So
instead of adopting any cap at face value, Oracle derives the effective cap from
the corroborated ratio `used_tokens / (server_pct / 100)` — a cap in the correct
token unit that self-corrects as the tier moves.

Grow-only: adopt `cap_inst` toward `cap_eff` (EMA) only when it exceeds the
preset (server reporting a *smaller* % than the preset implies → real cap bigger,
i.e. a tier-up). Growing the cap only moves the local projection toward the
server truth, so it is always safe. A smaller `cap_inst` may just mean incomplete
local logs on a multi-machine account, so it is never adopted below preset.

Persist is atomic and never raises (mirrors `ratelimits._save`). Stdlib only.
"""

from __future__ import annotations

import json
import os
import tempfile

from . import ratelimits

# Corroboration + smoothing constants.
P_FLOOR = 8.0  # server_pct below which used/(pct) is too noisy to trust
TOK_FLOOR = 2000  # local used_tokens below which the ratio is too noisy
ALPHA = 0.25  # EMA weight toward the instantaneous estimate
CAL_CEIL = 20.0  # absurdity clamp: cap_eff <= preset * CAL_CEIL
NOTE_RATIO = 1.1  # emit a human note once cap_eff / preset exceeds this


def default_path(path=None) -> str:
    """`capcal.json` sibling of `ratelimits.default_path()` (XDG data dir)."""
    if path:
        return os.path.expanduser(path)
    return os.path.join(os.path.dirname(ratelimits.default_path()), "capcal.json")


def _key(profile, window) -> str:
    return f"{profile}|{window}"


def _load(path=None) -> dict:
    """Never raises; {} on missing/corrupt/unreadable."""
    p = default_path(path)
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _save(snap, path=None) -> None:
    """Atomic mkstemp + os.replace in target dir; never raises to caller."""
    p = default_path(path)
    try:
        d = os.path.dirname(p)
        if d:
            os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d or ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(snap, fh)
            os.replace(tmp, p)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError:
        pass  # swallow; must not raise on the hot path


def current_cap(profile, window, preset_cap, path=None) -> int:
    """Last persisted `cap_eff` for (profile, window), or `preset_cap`."""
    try:
        preset = int(preset_cap)
        snap = _load(path)
        rec = snap.get(_key(profile, window)) if isinstance(snap, dict) else None
        if isinstance(rec, dict):
            eff = rec.get("cap_eff")
            if isinstance(eff, (int, float)) and eff >= preset:
                return int(eff)
        return preset
    except Exception:
        try:
            return int(preset_cap)
        except (TypeError, ValueError):
            return 0


def calibrate(profile, window, used_tokens, server_pct, preset_cap, now, path=None):
    """Fold a corroborated (used_tokens, server_pct) into cap_eff, grow-only.

    Returns (cap_eff, note_or_None). `note` is a human string when cap_eff has
    moved materially (> NOTE_RATIO) above preset. Never raises.
    """
    try:
        preset = int(preset_cap)
    except (TypeError, ValueError):
        return 0, None

    prev = current_cap(profile, window, preset, path=path)

    try:
        pct = float(server_pct)
        tok = float(used_tokens)
    except (TypeError, ValueError):
        return prev, None

    # Corroboration floors: near-empty window or trivial usage -> too noisy.
    if pct < P_FLOOR or tok < TOK_FLOOR:
        return prev, None

    cap_inst = tok / (pct / 100.0)

    # Grow-only: only adopt when the corroborated cap exceeds preset.
    if cap_inst <= preset:
        return prev, None

    cap_eff = round((1.0 - ALPHA) * prev + ALPHA * cap_inst)
    # Absurdity clamp + never shrink below preset.
    cap_eff = int(min(max(cap_eff, preset), preset * CAL_CEIL))

    snap = _load(path)
    if not isinstance(snap, dict):
        snap = {}
    snap[_key(profile, window)] = {"cap_eff": cap_eff, "updated_at": now}
    _save(snap, path)

    note = None
    if preset > 0 and cap_eff / preset > NOTE_RATIO:
        note = f"cap recalibrated {preset}→{cap_eff} (from live usage — tier changed?)"
    return cap_eff, note
