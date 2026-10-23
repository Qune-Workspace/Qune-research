"""§6.3 look-ahead tests and §5.3.4 engine tests (i), (ii), (iii), (vi) on toy
data, plus the Study 002 engine tests (cost charging, static mix, daily
index, execution-date resolution) re-run on this study's inputs.

The shift test uses a toy world with a bar every calendar day, so that moving
the whole world (prices, cash, month-end bars, schedule) by one day moves
every date by exactly one day and nothing else.
"""
import numpy as np
import pandas as pd
import pytest
from src import backtest
from src.calendar import build_schedule, month_end_bars
from src.cash import cash_index
from src.config import CASH_LEG, DURATION_LEG
from src.signal import t1, t2, t3

from tests.toy import toy_bars, toy_dtb3, toy_ief, toy_world

FIRST, LAST = "2001-01", "2007-10"


@pytest.fixture(scope="module")
def world():
    w = toy_world()
    schedule = backtest.resolve_execution_dates(build_schedule(w["bars"], FIRST, LAST), w["bars"])
    ends = month_end_bars(w["bars"])
    returns = backtest.instrument_returns(w["indices"], schedule)
    return w, schedule, ends, returns


def _targets(frame, schedule):
    return frame["target"].reindex(schedule.index[:-1])


def _signals(indices, ends, dates):
    return (t1(indices[DURATION_LEG], indices[CASH_LEG], ends, dates),
            t2(indices[DURATION_LEG], indices[CASH_LEG], ends, dates),
            t3(indices[DURATION_LEG], ends, dates))


def test_shifting_the_world_by_one_day_moves_trade_dates_by_one_day_only():
    """§5.3.4 (ii)."""
    bars = toy_bars(calendar="D")
    ief = toy_ief(bars)
    dtb3 = toy_dtb3()
    indices = {DURATION_LEG: ief / ief.iloc[0], CASH_LEG: cash_index(dtb3)}
    days = pd.date_range(bars[0], bars[-1] + pd.Timedelta(days=5), freq="D")
    schedule = build_schedule(bars, FIRST, LAST, trading_days=days)
    ends = month_end_bars(bars)
    shift = pd.Timedelta(days=1)
    shifted = {k: pd.Series(v.to_numpy(), index=v.index + shift) for k, v in indices.items()}
    ends_shifted = pd.Series((ends + shift).to_numpy(), index=ends.index)
    schedule_shifted = schedule.copy()
    for col in ("signal_date", "execution_date", "period_end"):
        schedule_shifted[col] = schedule[col] + shift
    for a, b in zip(_signals(indices, ends, schedule["signal_date"]),
                    _signals(shifted, ends_shifted, schedule_shifted["signal_date"])):
        assert ((b["signal_date"] - a["signal_date"]) == shift).all()
        assert a["value"].to_numpy() == pytest.approx(b["value"].to_numpy(), abs=0)
        assert a["target"].tolist() == b["target"].tolist()
    ra = backtest.instrument_returns(indices, schedule)
    rb = backtest.instrument_returns(shifted, schedule_shifted)
    assert ra.to_numpy() == pytest.approx(rb.to_numpy(), abs=0)


def test_signal_uses_no_observation_after_the_signal_date(world):
    """§5.3.4 (iii): scrambling every price and yield after t leaves the
    signal of t (and of every earlier month) unchanged."""
    w, schedule, ends, _ = world
    base = _signals(w["indices"], ends, schedule["signal_date"])
    rng = np.random.default_rng(1)
    for t in schedule["signal_date"].iloc[::7]:
        perturbed = {}
        for k, s in w["indices"].items():
            s = s.copy()
            later = s.index > t
            s.loc[later] = s.loc[later] * np.exp(rng.normal(0, 0.5, later.sum()))   # scramble the future
            perturbed[k] = s
        upto = schedule.index[schedule["signal_date"] <= t]
        for got, ref in zip(_signals(perturbed, ends, schedule["signal_date"]), base):
            assert got.loc[upto, "value"].to_numpy() == pytest.approx(ref.loc[upto, "value"].to_numpy(), abs=0)


def test_adding_later_data_does_not_change_past_signals(world):
    w, schedule, ends, _ = world
    cut = schedule["signal_date"].iloc[20]
    truncated = {k: s.loc[:cut] for k, s in w["indices"].items()}
    short_bars = w["bars"][w["bars"] <= cut]
    short_schedule = backtest.resolve_execution_dates(
        build_schedule(short_bars, FIRST, str(cut.to_period("M"))), w["bars"])
    full = t1(w["indices"][DURATION_LEG], w["indices"][CASH_LEG], ends, schedule["signal_date"])
    part = t1(truncated[DURATION_LEG], truncated[CASH_LEG], month_end_bars(short_bars), short_schedule["signal_date"])
    pd.testing.assert_frame_equal(full.loc[part.index], part)
    pd.testing.assert_frame_equal(schedule.loc[short_schedule.index, ["signal_date", "execution_date"]],
                                  short_schedule[["signal_date", "execution_date"]])


def test_forced_always_ief_equals_b1_and_always_bil_equals_b0(world):
    """§5.3.4 (i)."""
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


def test_exposure_fraction_is_the_share_of_periods_t1_holds_ief(world):
    """§5.3.4 (vi)."""
    w, schedule, ends, returns = world
    frame = t1(w["indices"][DURATION_LEG], w["indices"][CASH_LEG], ends, schedule["signal_date"])
    targets = _targets(frame, schedule)
    res = backtest.run_switching(targets, returns, 2e-4)
    assert backtest.exposure_fraction(targets) == pytest.approx((res["holding"] == DURATION_LEG).mean())
    assert backtest.exposure_fraction(targets) == pytest.approx((frame["value"].reindex(targets.index) > 0).mean())
    assert 0.0 < backtest.exposure_fraction(targets) < 1.0           # the toy signal changes sign
    assert res["switched"].sum() >= 3


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


def test_daily_index_compounds_to_the_monthly_result(world):
    w, schedule, ends, returns = world
    targets = _targets(t1(w["indices"][DURATION_LEG], w["indices"][CASH_LEG], ends, schedule["signal_date"]), schedule)
    res = backtest.run_switching(targets, returns, 2e-4)
    daily = backtest.daily_strategy_index(res, schedule, w["indices"])
    assert daily.iloc[-1] == pytest.approx(np.prod(1 + res["r"]), rel=1e-12)
    assert daily.index.is_monotonic_increasing and not daily.index.has_duplicates


def test_holding_period_returns_run_from_execution_close_to_next_execution_close(world):
    w, schedule, _, returns = world
    row = schedule.iloc[5]
    ief = w["indices"][DURATION_LEG]
    assert returns[DURATION_LEG].iloc[5] == pytest.approx(ief.loc[row["period_end"]] / ief.loc[row["execution_date"]] - 1)


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
