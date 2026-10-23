"""Synthetic total returns from FRED yields (§5.2).

Daily returns are defined between consecutive valid FRED observations; the
calendar-day accrual term handles weekends and holidays (Study 001 §6.5).
The exact repricing is the series used for results; the duration/convexity
version is a cross-check only and must agree to within 0.5 bp per day on
average.

Duration leg (§5.2, replacing Study 001's constant-maturity constructions):
on each day t with valid DGS7 and DGS10 at t and at the previous valid
observation s, a bond with ``BOND_YEARS`` (8.5) to maturity is bought at par
at the yield interpolated linearly between DGS7 and DGS10 at s, held to t,
and sold with its maturity shortened by the elapsed time at the interpolated
par yield **for that shortened maturity**.  Roll-down is therefore inside the
instrument: on an upward-sloping curve the shorter bond is repriced at a
lower yield even when the curve itself has not moved.  Coupon accrues at the
purchase yield; the expense ratio is deducted pro rata.  A fresh 8.5-year
bond is bought at every observation (the constant-maturity convention).

Cash leg: unchanged from Study 001 §5.2 (DTB3 as a bond-equivalent yield,
accrued over calendar days, minus BIL's expense ratio).
"""
from __future__ import annotations

import pandas as pd

from .bey import discount_to_bey, duration_convexity, par_bond_price
from .config import (
    BIL_EXPENSE_RATIO,
    BOND_PERIODS,
    BOND_YEARS,
    CURVE_LONG_YEARS,
    CURVE_SHORT_YEARS,
    DC_CROSSCHECK_TOLERANCE,
    IEF_EXPENSE_RATIO,
)

DAYS_PER_YEAR = 365.0
PERIODS_PER_YEAR = 2.0


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


def interpolated_par_yield(y_short, y_long, maturity_years) -> float:
    """Par yield at ``maturity_years`` by linear interpolation between the
    ``CURVE_SHORT_YEARS`` and ``CURVE_LONG_YEARS`` points (§5.2):
    ``y_short + (y_long - y_short) * (m - 7) / 3``.  Decimals in, decimal out.
    ``maturity_years`` may be a scalar or an array aligned with the yields."""
    weight = (maturity_years - CURVE_SHORT_YEARS) / (CURVE_LONG_YEARS - CURVE_SHORT_YEARS)
    return y_short + (y_long - y_short) * weight


def ageing_bond_returns(dgs7_pct: pd.Series, dgs10_pct: pd.Series,
                        expense_ratio: float = IEF_EXPENSE_RATIO,
                        bond_years: float = BOND_YEARS) -> pd.DataFrame:
    """Daily returns of the §5.2 ageing par bond from DGS7 and DGS10 in percent.

    Only dates where both series are observed count as observations.  Columns:
    ``r_exact`` (exact repricing), ``r_dc`` (duration/convexity cross-check with
    ``dy = y_t - y_s`` and the 17-period par bond's D_mod and convexity at
    ``y_s``), ``y_prev`` (purchase yield y_s), ``y`` (sale yield y_t at the
    shortened maturity), ``days``.
    """
    both = pd.concat([dgs7_pct.rename("y7"), dgs10_pct.rename("y10")], axis=1, sort=True).dropna() / 100.0
    if len(both) < 2:
        raise ValueError("need at least two valid observations")
    y7_prev, y7, days = _consecutive(both["y7"])
    y10_prev, y10, _ = _consecutive(both["y10"])
    year_frac = days / DAYS_PER_YEAR
    y_prev = interpolated_par_yield(y7_prev, y10_prev, bond_years)                 # bought at par
    y = interpolated_par_yield(y7, y10, bond_years - year_frac)                    # repriced, shorter
    periods_left = PERIODS_PER_YEAR * (bond_years - year_frac)
    price = par_bond_price(y_prev.values, y.values, periods_left.values)
    carry = y_prev * year_frac - expense_ratio * year_frac
    r_exact = (price / 100.0 - 1.0) + carry
    d_mod, convexity = duration_convexity(y_prev.values, y_prev.values, BOND_PERIODS)
    dy = y - y_prev
    r_dc = carry - d_mod * dy + 0.5 * convexity * dy ** 2
    return pd.DataFrame({"r_exact": r_exact, "r_dc": r_dc, "y_prev": y_prev, "y": y, "days": days})


def duration_returns(dgs10_pct: pd.Series, dgs7_pct: pd.Series,
                     expense_ratio: float = IEF_EXPENSE_RATIO) -> pd.DataFrame:
    """Synthetic duration-leg daily returns (§5.2); argument order matches the
    Study 001 engine's (DGS10 first)."""
    return ageing_bond_returns(dgs7_pct, dgs10_pct, expense_ratio)


def cash_returns(dtb3_pct: pd.Series,
                 expense_ratio: float = BIL_EXPENSE_RATIO) -> pd.DataFrame:
    """Synthetic cash daily returns from DTB3 in percent (Study 001 §5.2):
    bond-equivalent yield at the previous valid observation accrued over
    calendar days, minus the expense ratio pro rata.  Columns: ``r``,
    ``bey_prev``, ``days``."""
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


def synthetic_indices(dgs10_pct: pd.Series, dtb3_pct: pd.Series,
                      dgs7_pct: pd.Series) -> dict[str, pd.Series]:
    """Total-return indices of both synthetic legs keyed by instrument role
    (``IEF`` for the ageing 8.5-year par bond, ``BIL`` for cash) so that the
    backtest treats synthetic and actual series identically.  The duration
    index starts at the first date on which both DGS7 and DGS10 are observed
    (1969-07-01 on the real data; §8.1 starts the in-sample period after it)."""
    duration = duration_returns(dgs10_pct, dgs7_pct)
    cash = cash_returns(dtb3_pct)
    both = pd.concat([dgs7_pct, dgs10_pct], axis=1, sort=True).dropna()
    return {
        "IEF": total_return_index(duration["r_exact"], both.index[0]),
        "BIL": total_return_index(cash["r"], dtb3_pct.dropna().index[0]),
    }
