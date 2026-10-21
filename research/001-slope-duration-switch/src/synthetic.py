"""Synthetic constant-maturity total returns from FRED yields (§5.2, duration
leg as amended in §16 on 2026-10-21).

Daily returns are defined between consecutive valid FRED observations; the
calendar-day accrual term handles weekends and holidays (§6.5).  The exact
repricing is the series used for results; the duration/convexity version is
a cross-check only and must agree to within 0.5 bp per day on average.

Duration leg: from ``BLEND_START`` (1969-07-01, the first DGS7 observation)
an equal-weight blend of a 7-year par bond (DGS7, 14 semi-annual periods)
and a 10-year par bond (DGS10, 20 periods).  Each leg is repriced exactly
from its own purchase yield to its own sale yield, earns its own carry at
the purchase yield, and bears half the expense ratio.  The blend is reset to
equal weights at every observation (a daily-rebalanced 50/50).  Before
``BLEND_START`` the 10-year par bond alone, as in the original §5.2; no
window uses those dates since the in-sample period starts in 1969-08.
"""
from __future__ import annotations

import pandas as pd

from .bey import discount_to_bey, duration_convexity, par_bond_price
from .config import (BIL_EXPENSE_RATIO, BLEND_START, BLEND_WEIGHT_SEVEN_YEAR,
                     DC_CROSSCHECK_TOLERANCE, IEF_EXPENSE_RATIO, SEVEN_YEAR_PERIODS,
                     TEN_YEAR_PERIODS)

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


def par_bond_returns(yield_pct: pd.Series, n_periods: int, expense_ratio: float) -> pd.DataFrame:
    """Daily returns of a par bond with ``n_periods`` semi-annual periods to
    maturity, from a constant-maturity yield in percent (§5.2).

    Columns: ``r_exact`` (exact repricing of a par bond bought at y_s and sold
    at y_t, plus carry at y_s, minus ``expense_ratio`` pro rata), ``r_dc``
    (duration/convexity approximation of the same quantity), ``y_prev``,
    ``y``, ``days``.
    """
    y_prev, y, days = _consecutive(yield_pct / 100.0)
    year_frac = days / DAYS_PER_YEAR
    price = par_bond_price(y_prev.values, y.values, n_periods)
    carry = y_prev * year_frac - expense_ratio * year_frac
    r_exact = (price / 100.0 - 1.0) + carry
    d_mod, convexity = duration_convexity(y_prev.values, y_prev.values, n_periods)
    dy = y - y_prev
    r_dc = carry - d_mod * dy + 0.5 * convexity * dy ** 2
    return pd.DataFrame({"r_exact": r_exact, "r_dc": r_dc, "y_prev": y_prev,
                         "y": y, "days": days})


def ten_year_returns(dgs10_pct: pd.Series,
                     expense_ratio: float = IEF_EXPENSE_RATIO) -> pd.DataFrame:
    """Synthetic 10-year daily returns from DGS10 in percent (original §5.2
    construction; used alone only before ``BLEND_START``)."""
    return par_bond_returns(dgs10_pct, TEN_YEAR_PERIODS, expense_ratio)


def blend_returns(dgs10_pct: pd.Series, dgs7_pct: pd.Series,
                  expense_ratio: float = IEF_EXPENSE_RATIO,
                  weight_seven: float = BLEND_WEIGHT_SEVEN_YEAR,
                  blend_start: str = BLEND_START) -> pd.DataFrame:
    """Synthetic duration-leg daily returns (§5.2 as amended in §16).

    On dates from ``blend_start`` where both DGS7 and DGS10 are observed, the
    return is ``w * r_7 + (1 - w) * r_10`` with each leg repriced exactly on
    the common observation calendar.  Each leg's return is computed net of
    the full expense ratio pro rata, so after weighting the 7-year leg bears
    ``w`` of the fee and the 10-year leg ``1 - w`` (half each at ``w = 0.5``)
    and the blend pays the expense ratio exactly once.  Before
    ``blend_start`` the 10-year leg alone.  Columns: ``r_exact``, ``r_dc``,
    ``days``, ``blended`` (True where the blend applies).
    """
    start = pd.Timestamp(blend_start)
    both = pd.concat([dgs10_pct.rename("dgs10"), dgs7_pct.rename("dgs7")], axis=1, sort=True)
    both = both.loc[both.index >= start].dropna()
    before = dgs10_pct.loc[dgs10_pct.index < start].dropna()

    def ten_alone(series: pd.Series) -> pd.DataFrame:
        ten = ten_year_returns(series, expense_ratio)
        return pd.DataFrame({"r_exact": ten["r_exact"], "r_dc": ten["r_dc"],
                             "days": ten["days"], "blended": False})

    pieces = []
    if len(before) >= 2:
        pieces.append(ten_alone(before))
    if len(before) >= 1 and len(both) >= 1:
        # Bridge: the return into the first observation on or after
        # ``blend_start`` is still the 10-year bond alone, bought at the last
        # pre-blend yield; the blend starts with the next observation.
        pieces.append(ten_alone(pd.concat([before.iloc[-1:], both["dgs10"].iloc[:1]])))
    if len(both) >= 2:
        seven = par_bond_returns(both["dgs7"], SEVEN_YEAR_PERIODS, expense_ratio)
        ten = par_bond_returns(both["dgs10"], TEN_YEAR_PERIODS, expense_ratio)
        pieces.append(pd.DataFrame({
            "r_exact": weight_seven * seven["r_exact"] + (1.0 - weight_seven) * ten["r_exact"],
            "r_dc": weight_seven * seven["r_dc"] + (1.0 - weight_seven) * ten["r_dc"],
            "days": ten["days"], "blended": True}))
    if not pieces:
        raise ValueError("need at least two valid observations")
    out = pd.concat(pieces)
    if out.index.has_duplicates or not out.index.is_monotonic_increasing:
        raise ValueError("blend pieces overlap")
    return out


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


def synthetic_indices(dgs10_pct: pd.Series, dtb3_pct: pd.Series,
                      dgs7_pct: pd.Series) -> dict[str, pd.Series]:
    """Total-return indices of both synthetic legs keyed by instrument role
    (``IEF`` for the 7/10-year blend, ``BIL`` for cash) so that the backtest
    can treat synthetic and actual series identically."""
    duration = blend_returns(dgs10_pct, dgs7_pct)
    cash = cash_returns(dtb3_pct)
    return {
        "IEF": total_return_index(duration["r_exact"], dgs10_pct.dropna().index[0]),
        "BIL": total_return_index(cash["r"], dtb3_pct.dropna().index[0]),
    }
