import os
import tempfile

from token_oracle.core.capcal import calibrate, current_cap


def _p():
    d = tempfile.mkdtemp()
    return os.path.join(d, "capcal.json")


def test_grow_only_adopts_bigger_cap():
    p = _p()
    # server says 25% used at 110k tokens -> real cap ~440k > preset 220k -> grow
    cap, note = calibrate("claude", "weekly", 110_000, 25.0, 220_000, now=1.0, path=p)
    assert cap > 220_000 and note is not None


def test_never_shrinks_below_preset():
    p = _p()
    # server says 90% at 110k -> implied cap ~122k < preset 220k -> keep preset (grow-only)
    cap, note = calibrate("claude", "weekly", 110_000, 90.0, 220_000, now=1.0, path=p)
    assert cap == 220_000 and note is None


def test_noise_floor_ignored():
    p = _p()
    cap, _ = calibrate("claude", "weekly", 100, 2.0, 220_000, now=1.0, path=p)  # pct<8, tok<2000
    assert cap == 220_000


def test_absurdity_ceiling():
    p = _p()
    # pct tiny-but-above-floor with huge tokens -> clamp at 20x preset
    cap, _ = calibrate("claude", "weekly", 100_000_000, 9.0, 220_000, now=1.0, path=p)
    assert cap <= 220_000 * 20


def test_persistence_roundtrip():
    p = _p()
    calibrate("claude", "weekly", 110_000, 25.0, 220_000, now=1.0, path=p)
    assert current_cap("claude", "weekly", 220_000, path=p) > 220_000
    assert current_cap("grok", "weekly", 700_000, path=p) == 700_000  # untouched -> preset


def test_ema_smooths_toward_estimate():
    p = _p()
    c1, _ = calibrate("claude", "weekly", 110_000, 25.0, 220_000, now=1.0, path=p)  # inst ~440k
    c2, _ = calibrate("claude", "weekly", 110_000, 25.0, 220_000, now=2.0, path=p)  # closer to 440k
    assert 220_000 < c1 < c2 <= 440_000 + 1
