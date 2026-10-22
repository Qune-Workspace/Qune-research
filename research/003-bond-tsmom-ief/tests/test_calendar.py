"""§6.3 calendars: NYSE holiday rules on known dates, month-end signal dates
from a bar index, execution dates, and (when the raw files are present) the
counts of holding periods in each window.  Dates only; no return is computed."""
import pandas as pd
import pytest

from src import calendar as cal
from src.config import (DURATION_LEG, INSAMPLE_FIRST_SIGNAL_MONTH, INSAMPLE_LAST_SIGNAL_MONTH,
                        OOS_FIRST_SIGNAL_MONTH, OOS_LAST_SIGNAL_MONTH)
from src.alpaca_bars import load_bars
from src.alpaca_bars import raw_path as alpaca_raw_path
from src.tiingo_bars import load_prices
from src.tiingo_bars import raw_path as tiingo_raw_path
from tests.toy import toy_bars

CLOSED = ["2018-01-01", "2018-01-15", "2018-02-19", "2018-03-30", "2018-05-28", "2018-07-04",
          "2018-09-03", "2018-11-22", "2018-12-05", "2018-12-25", "2007-01-02", "2001-09-12",
          "2012-10-29", "2021-12-24", "2022-06-20", "2023-01-02", "2025-01-09", "2016-03-25",
          "2004-06-11", "2010-04-02", "2015-11-26", "2026-01-19"]
OPEN = ["2018-01-02", "2018-10-08", "2018-11-12", "2018-11-23", "2010-12-31", "2011-12-30",
        "2021-12-31", "2016-01-04", "2019-01-02", "2002-07-31", "2003-07-31", "2018-03-29",
        "2022-06-17", "2026-09-30"]


def test_easter():
    assert cal.easter_sunday(2018) == pd.Timestamp("2018-04-01").date()
    assert cal.easter_sunday(2026) == pd.Timestamp("2026-04-05").date()


@pytest.mark.parametrize("day", CLOSED)
def test_nyse_closed(day):
    assert pd.Timestamp(day) not in cal.nyse_trading_days("2000-01-01", "2026-12-31")


@pytest.mark.parametrize("day", OPEN)
def test_nyse_open(day):
    assert pd.Timestamp(day) in cal.nyse_trading_days("2000-01-01", "2026-12-31")


def test_trading_days_have_no_weekends_and_about_252_per_year():
    days = cal.nyse_trading_days("2003-01-01", "2018-12-31")
    assert (days.dayofweek < 5).all()
    per_year = days.to_series().groupby(days.year).size()
    assert per_year.between(250, 253).all()


def test_month_end_bars_pick_the_last_bar_of_each_month():
    bars = pd.DatetimeIndex(["2003-01-02", "2003-01-30", "2003-01-31", "2003-02-03", "2003-02-27",
                             "2003-04-01", "2003-04-30"])            # March has no bar at all
    ends = cal.month_end_bars(bars)
    assert ends.tolist() == list(pd.to_datetime(["2003-01-31", "2003-02-27", "2003-04-30"]))
    assert [str(m) for m in ends.index] == ["2003-01", "2003-02", "2003-04"]
    signal = cal.signal_dates(bars, "2003-01", "2003-04")
    assert pd.isna(signal.loc[pd.Period("2003-03", "M")])
    with pytest.raises(ValueError):
        cal.month_end_bars(bars.append(bars[:1]))


def test_execution_is_first_trading_day_strictly_after_signal():
    signal = pd.Series(pd.to_datetime(["2018-03-29", "2018-08-31", "2006-12-29", "2018-11-30"]),
                       index=pd.PeriodIndex(["2018-03", "2018-08", "2006-12", "2018-11"], freq="M"))
    days = cal.nyse_trading_days("2006-01-01", "2019-12-31")
    got = cal.execution_dates(signal, days).tolist()
    # Good Friday 2018-03-30; Labor Day 2018-09-03; Ford funeral 2007-01-02; plain next day
    assert got == list(pd.to_datetime(["2018-04-02", "2018-09-04", "2007-01-03", "2018-12-03"]))


def test_schedule_on_toy_bars_is_consistent():
    bars = toy_bars()
    schedule = cal.build_schedule(bars, "2001-01", "2007-10")
    assert (schedule["execution_date"] > schedule["signal_date"]).all()
    assert (schedule["period_end"].iloc[:-1] > schedule["execution_date"].iloc[:-1]).all()
    assert pd.isna(schedule["period_end"].iloc[-1])
    assert len(cal.holding_periods(schedule)) == len(schedule) - 1
    assert schedule["signal_date"].isin(bars).all()
    assert (schedule["signal_date"].dt.to_period("M") == schedule.index).all()
    # every signal date is the last bar of its month
    for month, t in schedule["signal_date"].items():
        assert bars[bars.to_period("M") == month].max() == t


@pytest.mark.skipif(not tiingo_raw_path(DURATION_LEG).exists(), reason="vendor IEF file not present")
def test_real_insample_calendar_counts_match_preregistration():
    """§8.1: first signal date the last trading day of July 2003, first
    execution the first trading day of August 2003, about 185 holding periods
    ending at the first execution date of January 2019.  Dates only."""
    bars = load_prices(DURATION_LEG).index
    schedule = cal.build_schedule(bars, INSAMPLE_FIRST_SIGNAL_MONTH, INSAMPLE_LAST_SIGNAL_MONTH)
    assert schedule.attrs["months_without_signal"] == 0
    assert len(cal.holding_periods(schedule)) == 185
    assert schedule["signal_date"].iloc[0] == pd.Timestamp("2003-07-31")
    assert schedule["execution_date"].iloc[0] == pd.Timestamp("2003-08-01")
    assert schedule["period_end"].iloc[-2] == pd.Timestamp("2019-01-02")
    assert cal.month_end_bars(bars).loc[pd.Period("2002-07", "M")] == pd.Timestamp("2002-07-31")


@pytest.mark.skipif(not (alpaca_raw_path("IEF").exists() and alpaca_raw_path("BIL").exists()),
                    reason="Alpaca bars not present")
def test_real_oos_calendar_counts_match_preregistration():
    """§8.2: first signal date the last trading day of December 2018, 93
    holding periods, the last ending at the first execution date of October 2026."""
    bars = load_bars("IEF").index.intersection(load_bars("BIL").index)
    schedule = cal.build_schedule(bars, OOS_FIRST_SIGNAL_MONTH, OOS_LAST_SIGNAL_MONTH)
    assert schedule.attrs["months_without_signal"] == 0
    assert len(cal.holding_periods(schedule)) == 93
    assert schedule["signal_date"].iloc[0] == pd.Timestamp("2018-12-31")
    assert schedule["execution_date"].iloc[0] == pd.Timestamp("2019-01-02")
    assert schedule["period_end"].iloc[-2] == pd.Timestamp("2026-10-01")
