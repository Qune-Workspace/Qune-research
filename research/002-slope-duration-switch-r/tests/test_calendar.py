"""§6.3 calendars: NYSE holiday rules on known dates, signal and execution
date mapping on toy data, and (when the FRED files are present) the counts of
holding periods in each window.  Dates only; no return is computed."""
import numpy as np
import pandas as pd
import pytest

from src import calendar as cal
from src.config import (INSAMPLE_FIRST_SIGNAL_MONTH, INSAMPLE_LAST_SIGNAL_MONTH,
                        OOS_FIRST_SIGNAL_MONTH, OOS_LAST_SIGNAL_MONTH, RAW_DIR)
from src.fred import load_series, raw_path
from tests.toy import toy_yields

CLOSED = ["2018-01-01", "2018-01-15", "2018-02-19", "2018-03-30", "2018-05-28", "2018-07-04",
          "2018-09-03", "2018-11-22", "2018-12-05", "2018-12-25", "2007-01-02", "2001-09-12",
          "2012-10-29", "2021-12-24", "2022-06-20", "2023-01-02", "2025-01-09", "2016-03-25",
          "1963-11-25", "1968-07-05", "1968-10-02", "1964-11-03", "1972-11-07", "1970-02-23"]
OPEN = ["2018-01-02", "2018-10-08", "2018-11-12", "2018-11-23", "2010-12-31", "2011-12-30",
        "2021-12-31", "2016-01-04", "2019-01-02", "1968-07-03", "1968-09-04", "1973-11-06",
        "2018-03-29", "2022-06-17"]


def test_easter():
    assert cal.easter_sunday(2018) == pd.Timestamp("2018-04-01").date()
    assert cal.easter_sunday(1962) == pd.Timestamp("1962-04-22").date()
    assert cal.easter_sunday(2026) == pd.Timestamp("2026-04-05").date()


@pytest.mark.parametrize("day", CLOSED)
def test_nyse_closed(day):
    assert pd.Timestamp(day) not in cal.nyse_trading_days("1962-01-01", "2026-12-31")


@pytest.mark.parametrize("day", OPEN)
def test_nyse_open(day):
    assert pd.Timestamp(day) in cal.nyse_trading_days("1962-01-01", "2026-12-31")


def test_trading_days_have_no_weekends_and_about_252_per_year():
    days = cal.nyse_trading_days("2010-01-01", "2019-12-31")
    assert (days.dayofweek < 5).all()
    per_year = days.to_series().groupby(days.year).size()
    assert per_year.between(250, 253).all()


def test_signal_date_is_last_day_with_both_valid():
    idx = pd.bdate_range("2003-01-01", "2003-02-28")
    dgs10 = pd.Series(4.0, index=idx)
    dtb3 = pd.Series(1.0, index=idx)
    dgs10.loc["2003-01-31"] = np.nan                       # 10-year missing on the last weekday
    dtb3.loc["2003-01-30"] = np.nan                        # bill missing the day before
    signal = cal.signal_dates(dgs10, dtb3, "2003-01", "2003-02")
    assert signal.loc[pd.Period("2003-01", "M")] == pd.Timestamp("2003-01-29")
    assert signal.loc[pd.Period("2003-02", "M")] == pd.Timestamp("2003-02-28")


def test_execution_is_first_trading_day_strictly_after_signal():
    signal = pd.Series(pd.to_datetime(["2018-03-29", "2018-08-31", "2006-12-29", "2018-11-30"]),
                       index=pd.PeriodIndex(["2018-03", "2018-08", "2006-12", "2018-11"], freq="M"))
    days = cal.nyse_trading_days("2006-01-01", "2019-12-31")
    got = cal.execution_dates(signal, days).tolist()
    # Good Friday 2018-03-30; Labor Day 2018-09-03; Ford funeral 2007-01-02; plain next day
    assert got == list(pd.to_datetime(["2018-04-02", "2018-09-04", "2007-01-03", "2018-12-03"]))


def test_schedule_on_toy_data_is_consistent():
    fred = toy_yields()
    schedule = cal.build_schedule(fred["DGS10"], fred["DTB3"], "2000-02", "2005-10")
    assert (schedule["execution_date"] > schedule["signal_date"]).all()
    assert (schedule["period_end"].iloc[:-1] > schedule["execution_date"].iloc[:-1]).all()
    assert pd.isna(schedule["period_end"].iloc[-1])
    assert len(cal.holding_periods(schedule)) == len(schedule) - 1
    both = pd.concat([fred["DGS10"], fred["DTB3"]], axis=1).dropna().index
    assert schedule["signal_date"].isin(both).all()
    assert (schedule["signal_date"].dt.to_period("M") == schedule.index).all()


@pytest.mark.skipif(not (raw_path("DGS10").exists() and raw_path("DTB3").exists()),
                    reason="FRED files not downloaded")
def test_real_calendar_counts_match_preregistration():
    """§8.1 as amended in §16 (2026-10-21): in-sample from the first execution
    date of August 1969, about 593 holding periods; §8.2: about 93
    out-of-sample."""
    dgs10, dtb3 = load_series("DGS10", RAW_DIR), load_series("DTB3", RAW_DIR)
    insample = cal.build_schedule(dgs10, dtb3, INSAMPLE_FIRST_SIGNAL_MONTH, INSAMPLE_LAST_SIGNAL_MONTH)
    oos = cal.build_schedule(dgs10, dtb3, OOS_FIRST_SIGNAL_MONTH, OOS_LAST_SIGNAL_MONTH)
    assert insample.attrs["months_without_signal"] == 0 and oos.attrs["months_without_signal"] == 0
    assert len(cal.holding_periods(insample)) == 593
    assert len(cal.holding_periods(oos)) == 93
    assert insample["signal_date"].iloc[0].to_period("M") == pd.Period("1969-07", "M")
    assert insample["execution_date"].iloc[0].to_period("M") == pd.Period("1969-08", "M")
    assert insample["period_end"].iloc[-2].to_period("M") == pd.Period("2019-01", "M")
    assert oos["execution_date"].iloc[0].to_period("M") == pd.Period("2019-01", "M")
    assert oos["period_end"].iloc[-2].to_period("M") == pd.Period("2026-10", "M")
    assert insample["period_end"].iloc[-2] == oos["execution_date"].iloc[0]
