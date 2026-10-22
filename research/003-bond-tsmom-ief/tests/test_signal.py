"""§6.1 and §7 signal definitions on hand-built inputs, including §5.3.4
tests (iv) and (v)."""
import numpy as np
import pandas as pd
import pytest

from src import signal
from src.calendar import month_end_bars
from src.config import CASH_LEG, DURATION_LEG


def _monthly_world(monthly_returns, start="2000-01-03"):
    """A price series with one bar per weekday whose month-to-month return
    (last bar to last bar) equals ``monthly_returns``; a constant cash index."""
    bars = pd.bdate_range(start, periods=len(monthly_returns) * 23)
    ends = month_end_bars(bars)
    ends = ends.iloc[:len(monthly_returns)]
    level = 100.0 * np.cumprod(1.0 + np.asarray(monthly_returns))
    price = pd.Series(np.nan, index=bars)
    price.loc[ends.values] = level
    price = price.ffill().bfill()                       # flat inside the month, steps at month-ends
    cash = pd.Series(1.0, index=bars)
    return bars, ends, price, cash


def test_threshold_is_exactly_zero():
    value = pd.Series([1e-12, 0.0, -1e-12])
    assert signal.target_from_value(value).tolist() == [DURATION_LEG, CASH_LEG, CASH_LEG]


def test_twelve_month_return_is_the_product_of_twelve_monthly_returns():
    """§5.3.4 (iv): with cash flat, T1's value at month m equals the product
    of the twelve calendar-month returns ending at m, minus one; T2 excludes
    exactly the most recent month."""
    rng = np.random.default_rng(5)
    monthly = rng.normal(0.003, 0.02, 30)
    bars, ends, price, cash = _monthly_world(monthly)
    months = ends.index[12:]
    dates = ends.loc[months]
    t1 = signal.t1(price, cash, ends, dates)
    t2 = signal.t2(price, cash, ends, dates)
    for k, m in enumerate(months):
        i = k + 12                                      # position of m in the monthly array
        expected_t1 = np.prod(1.0 + monthly[i - 11:i + 1]) - 1.0     # twelve months ending at m
        expected_t2 = np.prod(1.0 + monthly[i - 11:i]) - 1.0         # eleven months ending at m - 1
        assert t1.at[m, "value"] == pytest.approx(expected_t1, rel=1e-12)
        assert t2.at[m, "value"] == pytest.approx(expected_t2, rel=1e-12)
    assert (t1["target"] == np.where(t1["value"] > 0, DURATION_LEG, CASH_LEG)).all()


def test_cash_term_enters_the_excess_return():
    bars = pd.bdate_range("2000-01-03", periods=14 * 23)
    ends = month_end_bars(bars)
    price = pd.Series(100.0, index=bars)                 # IEF flat
    cash = pd.Series(np.exp(0.0001 * np.arange(len(bars))), index=bars)   # cash rises
    dates = ends.iloc[12:13]
    out = signal.t1(price, cash, ends, dates)
    expected = 1.0 - cash.loc[dates.iloc[0]] / cash.loc[ends.iloc[0]]
    assert out["value"].iloc[0] == pytest.approx(expected, rel=1e-12)
    assert out["target"].iloc[0] == CASH_LEG            # flat IEF lost to rising cash


def test_sma_flips_on_the_month_the_price_first_crosses_the_average():
    """§5.3.4 (v): a price that falls for a while and then rises flips T3 to
    IEF in the first month in which the month-end close exceeds the mean of
    the last ten month-end closes, and not before."""
    monthly = [-0.02] * 14 + [0.015] * 10
    bars, ends, price, cash = _monthly_world(monthly)
    levels = pd.Series(100.0 * np.cumprod(1.0 + np.asarray(monthly)), index=ends.index)
    sma = levels.rolling(10).mean()
    first_cross = (levels > sma).idxmax()
    months = ends.index[9:]
    out = signal.t3(price, ends, ends.loc[months])
    assert first_cross > months[0]                       # the crossing is inside the tested range
    before = out.loc[out.index < first_cross, "target"]
    assert (before == CASH_LEG).all()
    assert out.at[first_cross, "target"] == DURATION_LEG
    assert out.at[first_cross, "value"] == pytest.approx(levels[first_cross] / sma[first_cross] - 1.0, rel=1e-12)
    # scale-free: an index built from the same closes gives the same values
    same = signal.t3(price / price.iloc[0], ends, ends.loc[months])
    assert same["value"].to_numpy() == pytest.approx(out["value"].to_numpy(), rel=1e-12)


def test_cash_index_on_another_calendar_is_taken_as_of_the_month_end_bar():
    bars = pd.bdate_range("2000-01-03", periods=14 * 23).drop(pd.Timestamp("2000-01-31"))
    ends = month_end_bars(bars)
    assert ends.iloc[0] == pd.Timestamp("2000-01-28")
    price = pd.Series(100.0, index=bars)
    cash_days = pd.bdate_range("2000-01-03", periods=14 * 23)        # observed on 2000-01-31 as well
    cash = pd.Series(np.arange(len(cash_days), dtype=float) + 1.0, index=cash_days)
    out = signal.t1(price, cash, ends, ends.iloc[12:13])
    expected = 1.0 - cash.loc[ends.iloc[12]] / cash.loc[pd.Timestamp("2000-01-28")]   # flat IEF: ratio 1
    assert out["value"].iloc[0] == pytest.approx(expected, rel=1e-12)


def test_signal_months_before_the_lookback_are_dropped_and_mismatched_dates_rejected():
    bars = pd.bdate_range("2000-01-03", periods=15 * 23)
    ends = month_end_bars(bars)
    price = pd.Series(100.0 + np.arange(len(bars), dtype=float), index=bars)
    cash = pd.Series(1.0, index=bars)
    out = signal.t1(price, cash, ends, ends)              # asks for every month incl. the first twelve
    assert out.index[0] == ends.index[12] and len(out) == len(ends) - 12
    with pytest.raises(ValueError):
        signal.t1(price, cash, ends, ends.iloc[12:13] + pd.Timedelta(days=1))
