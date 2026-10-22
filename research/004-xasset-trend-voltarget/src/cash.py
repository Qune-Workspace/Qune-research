"""The in-sample cash leg (§5.2): Study 001's DTB3 accrual, unchanged.

Copied by attribution from Study 003's frozen ``src/cash.py`` and ``src/bey.py``
(which inherited them from Studies 001 and 002).  On each FRED business day t
with a valid DTB3 observation, and s the previous valid observation::

    bey_s = 365 * d_s / (360 - 91 * d_s)             d = DTB3 / 100
    r_t   = (bey_s - 0.001356) * days(s, t) / 365

compounded into ``TRI_cash`` equal to 1.0 at the first valid observation.
The level check against actual BIL was run once under Study 003 and is
inherited, not re-run (§5.3.3).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import BIL_EXPENSE_RATIO

BILL_DAYS = 91
DAYS_PER_YEAR = 365.0


def discount_to_bey(discount_yield):
    d = np.asarray(discount_yield, dtype=float)
    return 365.0 * d / (360.0 - BILL_DAYS * d)


def cash_returns(dtb3_pct: pd.Series, expense_ratio: float = BIL_EXPENSE_RATIO) -> pd.DataFrame:
    valid = dtb3_pct.dropna().astype(float) / 100.0
    if len(valid) < 2:
        raise ValueError("need at least two valid observations")
    current = valid.iloc[1:]
    previous = pd.Series(valid.values[:-1], index=current.index)
    days = pd.Series((current.index - valid.index[:-1]).days, index=current.index, dtype=float)
    bey_prev = pd.Series(discount_to_bey(previous.values), index=previous.index)
    year_frac = days / DAYS_PER_YEAR
    return pd.DataFrame({"r": bey_prev * year_frac - expense_ratio * year_frac, "bey_prev": bey_prev, "days": days})


def cash_index(dtb3_pct: pd.Series, expense_ratio: float = BIL_EXPENSE_RATIO) -> pd.Series:
    """``TRI_cash`` of §5.2 on the FRED calendar of valid DTB3 observations."""
    returns = cash_returns(dtb3_pct, expense_ratio)["r"]
    index = (1.0 + returns).cumprod()
    base = pd.Series([1.0], index=pd.DatetimeIndex([dtb3_pct.dropna().index[0]]))
    return pd.concat([base, index]).rename("tri")
