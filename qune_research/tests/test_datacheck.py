"""NYSE calendar on known dates (ported from Study 003's test), coverage on
a constructed bar index, and overlap statistics on constructed series."""
import numpy as np
import pandas as pd
import pytest

from qune_research import datacheck, nyse

CLOSED = ["2018-01-01", "2018-01-15", "2018-02-19", "2018-03-30", "2018-05-28", "2018-07-04",
          "2018-09-03", "2018-11-22", "2018-12-05", "2018-12-25", "2007-01-02", "2001-09-12",
          "2012-10-29", "2021-12-24", "2022-06-20", "2023-01-02", "2025-01-09", "2016-03-25",
          "2004-06-11", "2010-04-02", "2015-11-26", "2026-01-19"]
OPEN = ["2018-01-02", "2018-10-08", "2018-11-12", "2018-11-23", "2010-12-31", "2011-12-30",
        "2021-12-31", "2016-01-04", "2019-01-02", "2002-07-31", "2003-07-31", "2018-03-29",
        "2022-06-17", "2026-09-30"]


def test_easter():
    assert nyse.easter_sunday(2018) == pd.Timestamp("2018-04-01").date()
    assert nyse.easter_sunday(2026) == pd.Timestamp("2026-04-05").date()


@pytest.mark.parametrize("day", CLOSED)
def test_nyse_closed(day):
    assert pd.Timestamp(day) not in nyse.nyse_trading_days("2000-01-01", "2026-12-31")


@pytest.mark.parametrize("day", OPEN)
def test_nyse_open(day):
    assert pd.Timestamp(day) in nyse.nyse_trading_days("2000-01-01", "2026-12-31")


def test_trading_days_have_no_weekends_and_about_252_per_year():
    days = nyse.nyse_trading_days("2003-01-01", "2018-12-31")
    assert (days.dayofweek < 5).all()
    per_year = days.to_series().groupby(days.year).size()
    assert per_year.between(250, 253).all()


def test_coverage_counts_missing_runs_and_extra_bars():
    days = nyse.nyse_trading_days("2018-01-01", "2018-03-31")
    full = datacheck.coverage(days, "2018-01-01", "2018-03-31")
    assert full["pass"] and full["missing_days"] == [] and full["bars_present"] == full["nyse_trading_days"]
    gap = days.drop(days[10:14])                               # four consecutive trading days missing
    four = datacheck.coverage(gap, "2018-01-01", "2018-03-31")
    assert not four["pass"] and four["max_consecutive_missing_days"] == 4 and len(four["missing_days"]) == 4
    assert datacheck.coverage(gap, "2018-01-01", "2018-03-31", max_consecutive_missing=4)["pass"]
    holiday = days.append(pd.DatetimeIndex(["2018-01-15"]))     # a bar on Martin Luther King Jr. Day
    assert datacheck.coverage(holiday, "2018-01-01", "2018-03-31")["extra_bars_on_rule_calendar_closures"] == ["2018-01-15"]
    assert datacheck.longest_run([True, True, False, True]) == 2


def test_overlap_statistics_on_identical_and_drifted_series():
    days = pd.bdate_range("2015-12-31", "2018-12-31")
    rng = np.random.default_rng(11)
    base = 100 * np.exp(np.cumsum(rng.normal(0, 0.005, len(days))))
    broker = pd.Series(base, index=days)
    same = datacheck.overlap_statistics(broker, broker, "2016-01-04", "2018-12-31")
    assert same["mean_diff_annual_vendor_minus_broker"] == 0.0 and same["correlation_descriptive"] == pytest.approx(1.0)
    assert same["common_return_days"] == len(days.to_series().loc["2016-01-04":"2018-12-31"])
    drift = np.exp(0.005 / 252 * np.arange(len(days)))
    off = datacheck.overlap_statistics(pd.Series(base * drift, index=days), broker, "2016-01-04", "2018-12-31")
    assert off["mean_diff_annual_vendor_minus_broker"] == pytest.approx(0.005, rel=0.05)
    assert off["days_abs_diff_over_large"] == 0
    short = datacheck.overlap_statistics(broker.iloc[:-5], broker, "2016-01-04", "2018-12-31")
    assert len(short["days_only_in_broker"]) == 5 and short["days_only_in_vendor"] == []
