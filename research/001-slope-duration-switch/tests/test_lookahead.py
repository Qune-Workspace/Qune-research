"""§6.3 look-ahead tests and §10 engine tests on toy data.

The shift test uses a toy world in which yields are observed every calendar
day and every calendar day is a trading day, so that shifting the whole
world by one day moves every date by exactly one day and nothing else.
"""
import numpy as np
import pandas as pd
import pytest

from src import backtest
from src.calendar import build_schedule
from src.config import CASH_LEG, DURATION_LEG
from src.signal import daily_spread, t1, t2, t3
from src.synthetic import synthetic_indices
from tests.toy import toy_yields

FIRST, LAST = "2000-02", "2005-10"


@pytest.fixture(scope="module")
def world():
    fred = toy_yields()
    schedule = build_schedule(fred["DGS10"], fred["DTB3"], FIRST, LAST)
    indices = synthetic_indices(fred["DGS10"], fred["DTB3"])
    returns = backtest.instrument_returns(indices, schedule)
    return fred, schedule, indices, returns


def _targets(frame, schedule):
    return frame["target"].reindex(schedule.index[:-1])


def test_shifting_the_world_by_one_day_moves_trade_dates_by_one_day_only():
    fred = toy_yields(calendar="D")
    days = pd.date_range(fred["DGS10"].index[0], fred["DGS10"].index[-1] + pd.Timedelta(days=5), freq="D")
    schedule = build_schedule(fred["DGS10"], fred["DTB3"], FIRST, LAST, trading_days=days)
    shifted = {k: pd.Series(v.values, index=v.index + pd.Timedelta(days=1)) for k, v in fred.items()}
    schedule_shifted = schedule.copy()
    for col in ("signal_date", "execution_date", "period_end"):
        schedule_shifted[col] = schedule[col] + pd.Timedelta(days=1)
    for fn in (lambda f, s: t1(f["DGS10"], f["DTB3"], s["signal_date"]),
               lambda f, s: t2(f["DGS10"], f["DTB3"], s["signal_date"]),
               lambda f, s: t3(f["DGS10"], f["DGS7"], f["DTB3"], s["signal_date"])):
        a, b = fn(fred, schedule), fn(shifted, schedule_shifted)
        assert ((b["signal_date"] - a["signal_date"]) == pd.Timedelta(days=1)).all()
        assert a["value"].to_numpy() == pytest.approx(b["value"].to_numpy(), abs=0)
        assert a["target"].tolist() == b["target"].tolist()
    ra = backtest.instrument_returns(synthetic_indices(fred["DGS10"], fred["DTB3"]), schedule)
    rb = backtest.instrument_returns(synthetic_indices(shifted["DGS10"], shifted["DTB3"]), schedule_shifted)
    assert ra.to_numpy() == pytest.approx(rb.to_numpy(), abs=0)


def test_signal_uses_no_observation_after_the_signal_date(world):
    fred, schedule, _, _ = world
    base = t1(fred["DGS10"], fred["DTB3"], schedule["signal_date"])
    t2_base = t2(fred["DGS10"], fred["DTB3"], schedule["signal_date"])
    t3_base = t3(fred["DGS10"], fred["DGS7"], fred["DTB3"], schedule["signal_date"])
    rng = np.random.default_rng(1)
    for t in schedule["signal_date"].iloc[::7]:
        perturbed = {}
        for k, s in fred.items():
            s = s.copy()
            later = s.index > t
            s.loc[later] = s.loc[later] + rng.normal(0, 3.0, later.sum())   # scramble the future
            perturbed[k] = s
        upto = schedule.index[schedule["signal_date"] <= t]
        for fn, ref in (
            (lambda f: t1(f["DGS10"], f["DTB3"], schedule["signal_date"]), base),
            (lambda f: t2(f["DGS10"], f["DTB3"], schedule["signal_date"]), t2_base),
            (lambda f: t3(f["DGS10"], f["DGS7"], f["DTB3"], schedule["signal_date"]), t3_base),
        ):
            got = fn(perturbed)
            assert got.loc[upto, "value"].to_numpy() == pytest.approx(ref.loc[upto, "value"].to_numpy(), abs=0)


def test_adding_later_data_does_not_change_past_signals(world):
    fred, schedule, _, _ = world
    cut = schedule["signal_date"].iloc[20]
    truncated = {k: s.loc[:cut] for k, s in fred.items()}
    short_schedule = build_schedule(truncated["DGS10"], truncated["DTB3"], FIRST, str(cut.to_period("M")))
    full = t1(fred["DGS10"], fred["DTB3"], schedule["signal_date"])
    part = t1(truncated["DGS10"], truncated["DTB3"], short_schedule["signal_date"])
    pd.testing.assert_frame_equal(full.loc[part.index], part)
    pd.testing.assert_frame_equal(schedule.loc[short_schedule.index, ["signal_date", "execution_date"]],
                                  short_schedule[["signal_date", "execution_date"]])


def test_forced_always_ief_equals_b1_and_always_bil_equals_b0(world):
    _, schedule, _, returns = world
    always_ief = pd.Series(DURATION_LEG, index=returns.index)
    always_bil = pd.Series(CASH_LEG, index=returns.index)
    b = backtest.benchmarks(returns, 0.5, 2e-4)
    np.testing.assert_array_equal(backtest.run_switching(always_ief, returns, 0.0)["r"].to_numpy(),
                                  b["B1"]["r"].to_numpy())
    np.testing.assert_array_equal(backtest.run_switching(always_bil, returns, 0.0)["r"].to_numpy(),
                                  b["B0"]["r"].to_numpy())
    np.testing.assert_array_equal(b["B1"]["r"].to_numpy(), returns[DURATION_LEG].to_numpy())
    np.testing.assert_array_equal(b["B0"]["r"].to_numpy(), returns[CASH_LEG].to_numpy())
    assert (b["B0"]["cost"] == 0).all() and (b["B1"]["cost"] == 0).all()


def test_switch_cost_is_charged_on_both_sides_only_when_switching(world):
    _, schedule, _, returns = world
    c = 2e-4
    targets = pd.Series(CASH_LEG, index=returns.index)
    targets.iloc[3:6] = DURATION_LEG
    res = backtest.run_switching(targets, returns, c)
    assert res["switched"].tolist() == [False] * 3 + [True, False, False, True] + [False] * (len(res) - 7)
    assert res["r"].iloc[3] == pytest.approx((1 - c) ** 2 * (1 + returns[DURATION_LEG].iloc[3]) - 1)
    assert res["r"].iloc[4] == returns[DURATION_LEG].iloc[4]
    assert res["r"].iloc[6] == pytest.approx((1 - c) ** 2 * (1 + returns[CASH_LEG].iloc[6]) - 1)


def test_static_mix_rebalances_and_pays_cost_on_drift(world):
    _, _, _, returns = world
    c = 2e-4
    b2 = backtest.run_static(0.5, returns, c)
    gross0 = 0.5 * returns[DURATION_LEG].iloc[0] + 0.5 * returns[CASH_LEG].iloc[0]
    assert b2["r"].iloc[0] == pytest.approx(gross0)                      # no drift yet
    drift = 0.5 * (1 + returns[DURATION_LEG].iloc[0]) / (1 + gross0)
    gross1 = 0.5 * returns[DURATION_LEG].iloc[1] + 0.5 * returns[CASH_LEG].iloc[1]
    assert b2["r"].iloc[1] == pytest.approx((1 - c * abs(drift - 0.5)) ** 2 * (1 + gross1) - 1)
    assert (b2["cost"].iloc[1:] > 0).all()
    assert backtest.run_static(0.5, returns, 0.0)["r"].to_numpy() == pytest.approx(b2["r_gross"].to_numpy())


def test_exposure_fraction_depends_on_the_signal_only(world):
    fred, schedule, _, _ = world
    targets = _targets(t1(fred["DGS10"], fred["DTB3"], schedule["signal_date"]), schedule)
    spread = daily_spread(fred["DGS10"], fred["DTB3"]).reindex(schedule["signal_date"].iloc[:-1])
    assert backtest.exposure_fraction(targets) == pytest.approx((spread > 0).mean())
    assert 0.0 < backtest.exposure_fraction(targets) < 1.0           # the toy spread changes sign


def test_daily_index_compounds_to_the_monthly_result(world):
    fred, schedule, indices, returns = world
    targets = _targets(t1(fred["DGS10"], fred["DTB3"], schedule["signal_date"]), schedule)
    res = backtest.run_switching(targets, returns, 2e-4)
    daily = backtest.daily_strategy_index(res, schedule, indices)
    assert daily.iloc[-1] == pytest.approx(np.prod(1 + res["r"]), rel=1e-12)
    assert daily.index.is_monotonic_increasing and not daily.index.has_duplicates


def test_execution_dates_resolve_to_available_bars():
    schedule = pd.DataFrame({"signal_date": pd.to_datetime(["2020-01-31", "2020-02-28", "2020-03-31"]),
                             "execution_date": pd.to_datetime(["2020-02-03", "2020-03-02", "2020-04-01"])},
                            index=pd.period_range("2020-01", "2020-03", freq="M"))
    schedule["period_end"] = schedule["execution_date"].shift(-1)
    bars = pd.bdate_range("2020-01-01", "2020-05-01").drop(pd.Timestamp("2020-03-02"))
    resolved = backtest.resolve_execution_dates(schedule, bars)
    assert resolved["execution_date"].tolist() == list(pd.to_datetime(["2020-02-03", "2020-03-03", "2020-04-01"]))
    assert resolved["days_slipped"].tolist() == [0, 1, 0]
    assert resolved["period_end"].iloc[0] == pd.Timestamp("2020-03-03")
    with pytest.raises(ValueError):
        backtest.resolve_execution_dates(schedule, bars.drop(pd.bdate_range("2020-03-03", "2020-03-06")))
