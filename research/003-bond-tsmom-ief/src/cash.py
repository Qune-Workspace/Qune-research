"""The cash leg (§5.2), the only modelled series in this study.

On each FRED business day t with a valid DTB3 observation, and s the previous
valid observation::

    bey_s = 365 * (DTB3_s/100) / (360 - 91 * (DTB3_s/100))
    r_t   = bey_s * days(s, t) / 365 - 0.001356 * days(s, t) / 365

compounded into a total-return index ``TRI_cash`` equal to 1.0 at the first
valid observation.  It is a rate, not a bond.  The construction is Study
001's §5.2, unchanged; ``cash_returns`` and ``total_return_index`` are copied
from Study 002's ``synthetic.py`` (commit 2dfbdd5), and ``cash_index`` is the
one-call wrapper this study's report and checks use.
"""
from __future__ import annotations

import pandas as pd

from .bey import discount_to_bey
from .config import BIL_EXPENSE_RATIO

DAYS_PER_YEAR = 365.0


def _consecutive(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return (value at s, value at t, calendar days from s to t) for each
    valid observation t and the previous valid observation s."""
    valid = series.dropna().astype(float)
    if len(valid) < 2:
        raise ValueError("need at least two valid observations")
    current = valid.iloc[1:]
    previous = pd.Series(valid.values[:-1], index=current.index)
    days = pd.Series((current.index - valid.index[:-1]).days, index=current.index, dtype=float)
    return previous, current, days


def cash_returns(dtb3_pct: pd.Series,
                 expense_ratio: float = BIL_EXPENSE_RATIO) -> pd.DataFrame:
    """Daily cash returns from DTB3 in percent: bond-equivalent yield at the
    previous valid observation accrued over calendar days, minus the expense
    ratio pro rata.  Columns: ``r``, ``bey_prev``, ``days``."""
    d_prev, _, days = _consecutive(dtb3_pct / 100.0)
    bey_prev = pd.Series(discount_to_bey(d_prev.values), index=d_prev.index)
    year_frac = days / DAYS_PER_YEAR
    r = bey_prev * year_frac - expense_ratio * year_frac
    return pd.DataFrame({"r": r, "bey_prev": bey_prev, "days": days})


def total_return_index(returns: pd.Series, base_date: pd.Timestamp) -> pd.Series:
    """Total-return index equal to 1.0 at ``base_date`` (the valid observation
    preceding the first return) and compounded forward on the return dates."""
    index = (1.0 + returns).cumprod()
    base = pd.Series([1.0], index=pd.DatetimeIndex([base_date]))
    return pd.concat([base, index]).rename("tri")


def cash_index(dtb3_pct: pd.Series, expense_ratio: float = BIL_EXPENSE_RATIO) -> pd.Series:
    """``TRI_cash`` of §5.2 on the FRED calendar of valid DTB3 observations."""
    returns = cash_returns(dtb3_pct, expense_ratio)
    return total_return_index(returns["r"], dtb3_pct.dropna().index[0])
