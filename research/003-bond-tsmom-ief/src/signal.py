"""Signals T1, T2 and T3 (§6.1, §7) from total-return indices.

Every signal is a function of index levels on month-end bar dates only.  The
caller supplies ``month_ends`` (``calendar.month_end_bars`` of the ETF bar
index: the last bar of every calendar month, including the months before the
first signal month that the lookback needs) and the schedule's
``signal_dates``.  For signal month m with signal date t:

    T1  mom = TRI_IEF(t)/TRI_IEF(t_12) - TRI_cash(t)/TRI_cash(t_12)
    T2  the same measured to t_1 (the month-end of m - 1) instead of t
    T3  adjclose_t / mean(adjclose at the last 10 month-ends incl. t) - 1

where t_k is the month-end bar of month m - k.  Target = IEF when the value
is strictly positive, BIL otherwise; the threshold is exactly zero and no
observation dated after t is used (§6.3).  An index observed on another
calendar (the FRED-day cash accrual) is taken as of each month-end bar.

A signal month whose lookback reaches before the first month-end available is
dropped (a trial whose input starts later simply has fewer holding periods);
a gap after the first defined value is an error.
"""
from __future__ import annotations

import pandas as pd

from .config import CASH_LEG, DURATION_LEG, MOMENTUM_LOOKBACK_MONTHS, T2_SKIP_MONTHS, T3_SMA_MONTHS


def target_from_value(value: pd.Series) -> pd.Series:
    """``IEF if value > 0 else BIL`` (§6.1)."""
    return pd.Series(pd.NA, index=value.index, dtype="string").mask(
        value > 0, DURATION_LEG).mask(value <= 0, CASH_LEG).rename("target")


def month_end_levels(tri: pd.Series, month_ends: pd.Series) -> pd.Series:
    """Index level as of each month-end bar date (the last observation on or
    before it), indexed by month period."""
    tri = tri.sort_index()
    levels = tri.reindex(pd.DatetimeIndex(month_ends.values), method="ffill")
    if levels.isna().any():
        first_defined = month_ends[~levels.isna().to_numpy()]
        if first_defined.empty:
            raise ValueError("index starts after every month-end bar")
        levels = levels[~levels.isna().to_numpy()]
        month_ends = first_defined
    return pd.Series(levels.to_numpy(), index=month_ends.index, name="level")


def excess_momentum(tri_ief: pd.Series, tri_cash: pd.Series, month_ends: pd.Series,
                    lookback: int = MOMENTUM_LOOKBACK_MONTHS, skip: int = 0) -> pd.Series:
    """Monthly series of the excess return of IEF over cash from the month-end
    of m - lookback to the month-end of m - skip (§6.1; §7 for skip = 1)."""
    ief = month_end_levels(tri_ief, month_ends)
    cash = month_end_levels(tri_cash, month_ends).reindex(ief.index)
    end_ief, start_ief = ief.shift(skip), ief.shift(lookback)
    end_cash, start_cash = cash.shift(skip), cash.shift(lookback)
    return (end_ief / start_ief - end_cash / start_cash).dropna().rename("value")


def sma_signal(tri_ief: pd.Series, month_ends: pd.Series, window: int = T3_SMA_MONTHS) -> pd.Series:
    """Monthly series of the month-end level relative to the mean of the last
    ``window`` month-end levels including the current one, minus one (§7,
    Faber 2007): positive when the price is above its moving average.  The
    ratio is scale-free, so an adjusted close and a total-return index built
    from it give the same value."""
    levels = month_end_levels(tri_ief, month_ends)
    average = levels.rolling(window, min_periods=window).mean()
    return (levels / average - 1.0).dropna().rename("value")


def _at_signal_months(values: pd.Series, signal_dates: pd.Series, name: str) -> pd.DataFrame:
    """Signal values on the schedule's months.  Months before the first
    defined value are dropped; a later gap is an error."""
    months = signal_dates.index
    months = months[months >= values.index[0]]
    missing = months[~months.isin(values.index)]
    if len(missing):
        raise ValueError(f"{name} undefined on signal months {[str(m) for m in missing]}")
    value = pd.Series(values.loc[months].to_numpy(), index=months, name="value")
    return pd.DataFrame({"signal_date": signal_dates.loc[months], "value": value,
                         "target": target_from_value(value)})


def _check_signal_dates(month_ends: pd.Series, signal_dates: pd.Series) -> None:
    """A signal date must be the month-end bar of its month (§6.3)."""
    expected = month_ends.reindex(signal_dates.index)
    if not expected.eq(signal_dates).all():
        raise ValueError("signal dates are not the month-end bars of their months")


def t1(tri_ief: pd.Series, tri_cash: pd.Series, month_ends: pd.Series,
       signal_dates: pd.Series) -> pd.DataFrame:
    """T1: sign of the 12-month excess return on the signal date (§6.1)."""
    _check_signal_dates(month_ends, signal_dates)
    return _at_signal_months(excess_momentum(tri_ief, tri_cash, month_ends), signal_dates, "T1")


def t2(tri_ief: pd.Series, tri_cash: pd.Series, month_ends: pd.Series,
       signal_dates: pd.Series) -> pd.DataFrame:
    """T2: 12-1, the excess return from t_12 to t_1 (§7)."""
    _check_signal_dates(month_ends, signal_dates)
    values = excess_momentum(tri_ief, tri_cash, month_ends, MOMENTUM_LOOKBACK_MONTHS, T2_SKIP_MONTHS)
    return _at_signal_months(values, signal_dates, "T2")


def t3(tri_ief: pd.Series, month_ends: pd.Series, signal_dates: pd.Series) -> pd.DataFrame:
    """T3: month-end close above its 10-month moving average (§7); price only."""
    _check_signal_dates(month_ends, signal_dates)
    return _at_signal_months(sma_signal(tri_ief, month_ends), signal_dates, "T3")
