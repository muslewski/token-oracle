import json

from token_oracle.core import report as R
from token_oracle.core.config import Config
from token_oracle.core.contracts import Window
from token_oracle.core.engine import cached_events


def test_daily_ledger_zero_fill_and_total():
    # events spanning 3 days, 7-day ledger must emit 7 daily + TOTAL
    now = 1_700_000_000.0
    day = 86400.0
    ev = [
        (now - 0 * day, 1000, "claude-opus-4", 1000, 0, 0, 0, None),
        (now - 1 * day, 2000, "claude-sonnet-4", 2000, 0, 0, 0, None),
        (now - 1 * day, 500, "grok-4", 500, 0, 0, 0, None),
    ]
    rows = R.daily_ledger(ev, cap=8_000_000, now=now, days=7)
    assert len(rows) == 8  # 7 days + TOTAL
    assert rows[-1].label == "TOTAL"
    assert rows[-1].tokens == 3500
    # empty days have 0 tokens, 0.0 cost
    zero_rows = [r for r in rows if r.tokens == 0]
    assert len(zero_rows) >= 4
    for zr in zero_rows:
        assert zr.cost == 0.0
        assert zr.unpriced_tokens == 0
    # TOTAL matches sum
    assert rows[-1].tokens == sum(r.tokens for r in rows[:-1])


def test_daily_ledger_pct_cap():
    now = 1_700_000_000.0
    ev = [(now, 800_000, "claude-sonnet-4", 800000, 0, 0, 0, None)]
    rows = R.daily_ledger(ev, cap=8_000_000, now=now, days=1)
    assert len(rows) == 2
    day_row = rows[0]
    assert day_row.pct_cap == 10.0
    assert rows[-1].pct_cap == 10.0


def test_unpriced_accounting_and_fully_unpriced_day():
    now = 1_700_000_000.0
    day = 86400.0
    ev = [
        (now, 1000, "claude-sonnet-4", 1000, 0, 0, 0, None),  # priced
        (now - 1 * day, 420, "grok-4", 420, 0, 0, 0, None),  # unpriced
        (now - 2 * day, 999, "mystery", 999, 0, 0, 0, None),  # unpriced only
    ]
    rows = R.daily_ledger(ev, cap=8_000_000, now=now, days=3)
    # today has priced: cost not None, unpriced=0
    today = rows[-2]  # most recent before TOTAL
    assert today.tokens == 1000
    assert today.cost is not None and today.cost > 0
    assert today.unpriced_tokens == 0
    # yesterday: mixed? wait no, grok unpriced but separate day
    # the day with only grok: cost=None
    grok_day = [r for r in rows if r.unpriced_tokens == 420][0]
    assert grok_day.cost is None
    # mystery day cost None
    mys_day = [r for r in rows if r.unpriced_tokens == 999][0]
    assert mys_day.cost is None
    # TOTAL: has priced part so cost not None, unpriced >0
    total = rows[-1]
    assert total.unpriced_tokens == 420 + 999
    assert total.cost is not None


def test_mode_off_yields_none_cost():
    now = 1_700_000_000.0
    ev = [(now, 1000, "claude-sonnet-4", 1000, 0, 0, 0, 5.0)]
    rows = R.daily_ledger(ev, cap=8_000_000, now=now, days=1, mode="off")
    assert rows[0].cost is None
    assert rows[0].tokens == 1000


def test_group_ledger_model_ordering_and_total():
    now = 1_700_000_000.0
    ev = [
        (now, 100, "claude-opus-4", 100, 0, 0, 0, 1.5),
        (now, 200, "claude-sonnet-4", 200, 0, 0, 0, 0.5),
        (now, 50, "grok-4", 50, 0, 0, 0, None),
    ]
    rows = R.group_ledger(ev, "model", now)
    # TOTAL last
    assert rows[-1].label == "TOTAL"
    assert rows[-1].tokens == 350
    # model rows: sorted cost desc (1.5 > 0.5 > None? but None treated as 0 for sort?)
    # in code we sort by -usd so claude-opus first (1.5), then sonnet(0.5), then grok(0)
    labels = [r.label for r in rows[:-1]]
    assert labels[0] == "claude-opus-4"
    assert labels[1] == "claude-sonnet-4"
    assert labels[2] == "grok-4"
    # grok contributes to unpriced
    grok_row = [r for r in rows if r.label == "grok-4"][0]
    assert grok_row.unpriced_tokens == 50
    assert grok_row.cost is None


def test_group_ledger_week_labels():
    now = 1_700_000_000.0
    ev = [(now, 10, "m", 10, 0, 0, 0, None)]
    rows = R.group_ledger(ev, "week", now)
    assert rows[0].label.startswith("20") and "-W" in rows[0].label
    assert rows[-1].label == "TOTAL"


def test_group_ledger_bad_key():
    now = 1_700_000_000.0
    ev = [(now, 1, "m", 1, 0, 0, 0, None)]
    try:
        R.group_ledger(ev, "project", now)
        raise AssertionError("should have raised")
    except ValueError as e:
        assert "unsupported group key" in str(e)


def test_cost_today_slice():
    now = 1_700_000_000.0
    day = 86400.0
    ev = [
        (now, 1000, "claude-sonnet-4", 1000, 0, 0, 0, 3.0),
        (now - 1 * day, 999, "grok", 999, 0, 0, 0, None),
        (now + 100, 50, "claude", 50, 0, 0, 0, 0.1),  # same local day
    ]
    res = R.cost_today(ev, now)
    assert res["usd"] == 3.1
    assert res["unpriced_tokens"] == 0
    # add unpriced today
    ev2 = ev + [(now, 42, "unknown", 42, 0, 0, 0, None)]
    res2 = R.cost_today(ev2, now)
    assert res2["usd"] == 3.1
    assert res2["unpriced_tokens"] == 42


def test_weekly_cap_selection():
    # nearest 7d
    w1 = Window("5h", 220000, 18000)
    w2 = Window("weekly", 8000000, 604800)
    w3 = Window("other", 1000000, 100000)
    assert R.weekly_cap([]) is None
    assert R.weekly_cap([w1]) == 220000
    # nearest is weekly
    assert R.weekly_cap([w1, w2]) == 8000000
    # tie in diff: pick largest cap
    w4 = Window("w2", 9000000, 604800)
    assert R.weekly_cap([w2, w4]) == 9000000  # larger
    # max fallback if weird
    assert R.weekly_cap([w1, w3]) == 1000000  # nearest tiebreak + max-cap fallback
    # test max cap on exact period tie
    assert R.weekly_cap([Window("a", 1, 604800), Window("b", 2, 604800)]) == 2


def test_cached_events_single_and_multi_and_missing(tmp_path):
    # single shape
    cache_file = tmp_path / "cache.json"
    now = 1_700_000_000.0
    single_cache = {
        "events": [[now - 100, 10, "claude-sonnet-4", 5, 5, 0, 0, 0.1], [now - 50, 20]],
        "files": {},
        "lastAggregate": now,
    }
    cache_file.write_text(json.dumps(single_cache))
    cfg = Config(cache_path=str(cache_file))
    evs = cached_events(cfg)
    assert len(evs) == 2
    assert evs[0][1] == 10
    assert evs[1][1] == 20

    # multi profile shape
    multi_cache = {
        "profiles": {
            "claude": {"events": [[now - 200, 5, "claude", 0, 0, 0, 0, 0.01]]},
            "grok": {"events": [[now - 10, 7]]},
        },
        "lastAggregate": now,
    }
    cache_file.write_text(json.dumps(multi_cache))
    evs2 = cached_events(cfg)
    assert len(evs2) == 2
    assert {e[1] for e in evs2} == {5, 7}

    # missing file -> []
    missing = tmp_path / "nope.json"
    cfg2 = Config(cache_path=str(missing))
    assert cached_events(cfg2) == []

    # bad content safe -> []
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    cfg3 = Config(cache_path=str(bad))
    assert cached_events(cfg3) == []
