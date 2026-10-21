"""Synthetic constant-maturity total returns from FRED yields (§5.2).

Daily returns are defined between consecutive valid FRED observations; the
calendar-day accrual term handles weekends and holidays (§6.5).  The exact
repricing is the series used for results; the duration/convexity version is
a cross-check only and must agree to within 0.5 bp per day on average.
"""
from __future__ import annotations

import pandas as pd

from .bey import discount_to_bey, duration_convexity, par_bond_price
from .config import BIL_EXPENSE_RATIO, DC_CROSSCHECK_TOLERANCE, IEF_EXPENSE_RATIO

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


def ten_year_returns(dgs10_pct: pd.Series,
                     expense_ratio: float = IEF_EXPENSE_RATIO) -> pd.DataFrame:
    """Synthetic 10-year daily returns from DGS10 in percent (§5.2).

    Columns: ``r_exact`` (exact repricing of a par bond bought at y_s and sold
    at y_t, plus carry at y_s, minus the expense ratio pro rata), ``r_dc``
    (duration/convexity approximation of the same quantity), ``y_prev``,
    ``y``, ``days``.
    """
    y_prev, y, days = _consecutive(dgs10_pct / 100.0)
    year_frac = days / DAYS_PER_YEAR
    price = par_bond_price(y_prev.values, y.values)
    carry = y_prev * year_frac - expense_ratio * year_frac
    r_exact = (price / 100.0 - 1.0) + carry
    d_mod, convexity = duration_convexity(y_prev.values, y_prev.values)
    dy = y - y_prev
    r_dc = carry - d_mod * dy + 0.5 * convexity * dy ** 2
    return pd.DataFrame({"r_exact": r_exact, "r_dc": r_dc, "y_prev": y_prev,
                         "y": y, "days": days})


def cash_returns(dtb3_pct: pd.Series,
                 expense_ratio: float = BIL_EXPENSE_RATIO) -> pd.DataFrame:
    """Synthetic cash daily returns from DTB3 in percent (§5.2): bond-equivalent
    yield at the previous valid observation accrued over calendar days, minus
    the expense ratio pro rata.  Columns: ``r``, ``bey_prev``, ``days``."""
    d_prev, _, days = _consecutive(dtb3_pct / 100.0)
    bey_prev = pd.Series(discount_to_bey(d_prev.values), index=d_prev.index)
    year_frac = days / DAYS_PER_YEAR
    r = bey_prev * year_frac - expense_ratio * year_frac
    return pd.DataFrame({"r": r, "bey_prev": bey_prev, "days": days})


def crosscheck_mean_abs_error(returns: pd.DataFrame) -> float:
    """Mean absolute daily difference between exact repricing and the
    duration/convexity approximation (§5.2 acceptance: <= 0.5 bp)."""
    return float((returns["r_exact"] - returns["r_dc"]).abs().mean())


def crosscheck_passes(returns: pd.DataFrame) -> bool:
    return crosscheck_mean_abs_error(returns) <= DC_CROSSCHECK_TOLERANCE


def total_return_index(returns: pd.Series, base_date: pd.Timestamp) -> pd.Series:
    """Total-return index equal to 1.0 at ``base_date`` (the valid observation
    preceding the first return) and compounded forward on the return dates."""
    index = (1.0 + returns).cumprod()
    base = pd.Series([1.0], index=pd.DatetimeIndex([base_date]))
    return pd.concat([base, index]).rename("tri")


def synthetic_indices(dgs10_pct: pd.Series, dtb3_pct: pd.Series) -> dict[str, pd.Series]:
    """Total-return indices of both synthetic legs keyed by instrument role
    (``IEF`` for the 10-year leg, ``BIL`` for cash) so that the backtest can
    treat synthetic and actual series identically."""
    ten = ten_year_returns(dgs10_pct)
    cash = cash_returns(dtb3_pct)
    return {
        "IEF": total_return_index(ten["r_exact"], dgs10_pct.dropna().index[0]),
        "BIL": total_return_index(cash["r"], dtb3_pct.dropna().index[0]),
    }
