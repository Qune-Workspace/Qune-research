"""Signal and execution dates from a bar index (Study 004 §6.3).

The bar index is the set of trading days on which the instruments have a
close.  Signal date t = the last bar of each calendar month; execution date
e = the first bar strictly after t.  Holding periods run from the close of
one execution date to the close of the next.
"""
from __future__ import annotations

import pandas as pd


def month_end_signal_dates(bars: pd.DatetimeIndex, start: str | pd.Timestamp,
                           end: str | pd.Timestamp) -> pd.DatetimeIndex:
    """Last bar of every calendar month whose last bar lies in [start, end]."""
    idx = pd.DatetimeIndex(bars).sort_values()
    s = pd.Series(idx, index=idx)
    last = s.groupby([idx.year, idx.month]).max()
    out = pd.DatetimeIndex(last.values)
    return out[(out >= pd.Timestamp(start)) & (out <= pd.Timestamp(end))]


def schedule(bars: pd.DatetimeIndex, signal_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """One row per signal date: ``signal_date``, ``execution_date`` (the first
    bar strictly after the signal date) and ``period_end`` (the next row's
    execution date; NaT on the last row, which starts no holding period).
    Raises if the bars end before the execution date of any signal."""
    idx = pd.DatetimeIndex(bars).sort_values()
    pos = idx.searchsorted(pd.DatetimeIndex(signal_dates).values, side="right")
    if len(pos) and pos[-1] >= len(idx):
        raise ValueError("bars end before the execution date of the last signal")
    exe = pd.DatetimeIndex(idx[pos])
    out = pd.DataFrame({"signal_date": pd.DatetimeIndex(signal_dates), "execution_date": exe})
    out["period_end"] = out["execution_date"].shift(-1)
    return out


def months_before(date: pd.Timestamp, months: int, bars: pd.DatetimeIndex) -> pd.Timestamp | None:
    """The last bar of the calendar month ``months`` before ``date``'s month,
    or None if the bars do not reach it (the asset has not entered, §8.1)."""
    idx = pd.DatetimeIndex(bars)
    target = (pd.Timestamp(date).to_period("M") - months).to_timestamp(how="end").normalize()
    cand = idx[idx <= target]
    if len(cand) == 0:
        return None
    last = cand[-1]
    if last.to_period("M") != target.to_period("M"):
        return None
    return last
