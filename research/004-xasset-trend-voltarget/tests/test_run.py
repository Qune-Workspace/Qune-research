"""The study's run module on constructed series (no raw file, no network):
the daily index agrees with the compounded period returns, the switch count,
the breakeven interpolation, the §9.5 verdict precedence and the universe
coming only from the data-check evaluation."""
import json

import numpy as np
import pandas as pd
import pytest
from src import run

from qune_research import engine
from qune_research.dates import month_end_signal_dates, schedule

COSTS = {"AAA": 2.0, "BBB": 2.5, "CCC": 3.0}   # bp, constructed symbols only


def _prices(seed: int = 3) -> tuple[pd.DataFrame, pd.Series]:
    days = pd.bdate_range("2010-01-04", "2013-12-31")
    rng = np.random.default_rng(seed)
    cols = {}
    for i, a in enumerate(("AAA", "BBB", "CCC")):
        r = rng.normal(0.0003, 0.008 + 0.004 * i, len(days))
        cols[a] = pd.Series(np.cumprod(1 + r), index=days)
    cols["BBB"].iloc[:300] = np.nan                       # BBB lists later: staggered entry (§8.1)
    prices = pd.DataFrame(cols)
    cash = pd.Series(np.cumprod(1 + np.full(len(days), 0.00005)), index=days)
    return prices, cash


def test_daily_index_matches_compounded_period_returns():
    prices, cash = _prices()
    universe = list(prices.columns)
    bars = prices.index
    sched = schedule(bars, month_end_signal_dates(bars, "2011-01-31", "2013-11-30"))
    table = run.signal_table(prices, cash, universe, pd.DatetimeIndex(sched["signal_date"]))
    results, signals, k = run.run_strategies(prices, cash, sched, table, universe, None, 1.0, COSTS)
    for name in ("T1", "B1", "B3", "B4"):
        daily = run.daily_index(results[name], sched, prices, cash)
        monthly_end = float(np.prod(1.0 + results[name]["net"]))
        assert daily.iloc[-1] == pytest.approx(monthly_end, rel=1e-9)
        assert daily.index[0] > sched["execution_date"].iloc[0]
        assert daily.index[-1] == sched["period_end"].iloc[-2]
    assert 0.0 < k <= 1.0
    assert (results["B4"]["gross_exposure"] <= 1.0 + 1e-12).all()
    assert table["present"]["BBB"].iloc[0] == False  # noqa: E712  (absent before its 12-month bar)
    assert table["present"]["BBB"].iloc[-1]


def test_switches_counted_only_on_present_months_and_t4_levels():
    idx = pd.DatetimeIndex(["2010-01-29", "2010-02-26", "2010-03-31", "2010-04-30", "2010-05-28"])
    s = pd.DataFrame({"X": [np.nan, 1.0, 0.0, 0.0, 1.0], "Y": [1.0, 1.0, 1.0, 1.0, 1.0],
                      "Z": [0.0, 1 / 3, 1 / 3, 2 / 3, 1.0]}, index=idx)
    assert run.switches_per_asset(s) == {"X": 2, "Y": 0, "Z": 3}
    assert run.power_statement(s)["label"] == "low-powered"


def test_zero_crossing_interpolates_between_multiples():
    assert run.zero_crossing({0.0: 0.2, 1.0: 0.1, 2.0: -0.1}) == pytest.approx(1.5)
    assert run.zero_crossing({0.0: 0.2, 1.0: 0.1, 2.0: 0.05}) is None
    assert run.zero_crossing({0.0: -0.1, 1.0: -0.2}) is None


def test_verdict_precedence_not_supported_first():
    c_ok = {"C1": True, "C2": True, "C3": True, "C4": True}
    o_ok = {"O1": True, "O2": True}
    assert run.verdict(c_ok, o_ok, 2.0, -0.10, -0.20) == "supported"
    assert run.verdict(dict(c_ok, C3=False), o_ok, 2.0, -0.10, -0.20) == "not supported"
    assert run.verdict(c_ok, o_ok, 2.0, -0.25, -0.20) == "not supported"       # deeper drawdown than B4
    assert run.verdict(c_ok, {"O1": False, "O2": True}, -0.5, -0.10, -0.20) == "inconclusive"
    assert run.verdict(c_ok, {"O1": False, "O2": True}, -1.5, -0.10, -0.20) == "not supported"


def test_universe_comes_from_the_check_evaluation(tmp_path):
    report = {"evaluation": {"halt": False, "universe": ["IWM", "IEF"]}}
    (tmp_path / "data_checks.json").write_text(json.dumps(report), encoding="utf-8")
    assert run.universe_from_checks(tmp_path) == ["IWM", "IEF"]
    report["evaluation"]["halt"] = True
    (tmp_path / "data_checks.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(SystemExit):
        run.universe_from_checks(tmp_path)


def test_b4_is_b3_scaled_by_k():
    prices, cash = _prices(5)
    universe = list(prices.columns)
    bars = prices.index
    sched = schedule(bars, month_end_signal_dates(bars, "2011-01-31", "2013-11-30"))
    table = run.signal_table(prices, cash, universe, pd.DatetimeIndex(sched["signal_date"]))
    results, _, k = run.run_strategies(prices, cash, sched, table, universe, None, 1.0, COSTS)
    for a in universe:
        assert np.allclose(results["B4"][f"w_{a}"], k * results["B3"][f"w_{a}"])
    assert k == pytest.approx(engine.exposure_ratio(results["T1"], results["B3"]))


def test_oos_schedule_ends_at_the_common_last_bar_for_every_instrument():
    # §16 (2026-10-22): two reused files reach past 2026-09-30, the fetched ten stop there.
    long_bars = pd.bdate_range("2018-11-01", "2026-10-21")
    short_bars = pd.bdate_range("2018-11-01", "2026-09-30")
    prices = pd.DataFrame({"IEF": pd.Series(100.0, index=long_bars),
                           "TLT": pd.Series(100.0, index=short_bars)}).sort_index()
    last = run.common_last_bar(prices, ["IEF", "TLT"])
    assert last == pd.Timestamp("2026-09-30")
    bars = prices.dropna(how="all").index
    bars = bars[bars <= last]
    sched = run.oos_schedule(bars)
    assert sched["signal_date"].iloc[0] == pd.Timestamp("2018-12-31")
    assert sched["execution_date"].iloc[0] == pd.Timestamp("2019-01-01")   # bdate_range has no holidays
    assert sched["signal_date"].iloc[-1] == pd.Timestamp("2026-09-30")
    assert pd.isna(sched["execution_date"].iloc[-1])
    assert sched["period_end"].iloc[-2] == pd.Timestamp("2026-09-30")
    assert len(sched) - 1 == 93                                            # holding periods, §8.2
    # the union index alone would have silently used 2026-10-01 for IEF and forward-filled TLT
    union = run.oos_schedule(prices.dropna(how="all").index)
    assert union["period_end"].iloc[-2] == pd.Timestamp("2026-10-01")
