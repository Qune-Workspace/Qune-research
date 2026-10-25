"""Study 007 signals (PREREGISTRATION.md §6.1-§6.3): carry at the signal
dates, the expanding percentile rank that is the weight, the 12-month trend
signal on total-return indices, and the T2 blend.  Pure functions of the
inputs they are given; this module imports nothing from ``backtest.py`` or
``tilt.py`` (§13 test 1) and never forms a return of any rule.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config007 import BLEND_CARRY_WEIGHT, TREND_LAG_ROWS
from .signal import t3


def carry_at_signal_dates(dgs10_pct: pd.Series, dgs7_pct: pd.Series, dtb3_pct: pd.Series,
                          signal_dates: pd.Series) -> pd.Series:
    """c_t of §6.1 on each signal date: Study 001 §7's carry including
    roll-down, read through the copied ``signal.t3`` so that the formula is
    the frozen code's.  Indexed like ``signal_dates`` (signal month)."""
    return t3(dgs10_pct, dgs7_pct, dtb3_pct, signal_dates)["value"].rename("carry")


def expanding_rank(carry: pd.Series, min_history: int) -> pd.Series:
    """w_t of §6.2: among the carries observed up to and including t
    (n_t of them), the average-rank percentile of today's,

        (#{s <= t : c_s < c_t} + 0.5 * #{s < t : c_s = c_t}) / (n_t - 1),

    in [0, 1]; NaN while n_t < ``min_history``.  Uses only values at or
    before t (no look-ahead), by construction of the loop."""
    if min_history < 2:
        raise ValueError("min_history must be at least 2")
    values = carry.to_numpy(dtype=float)
    if np.isnan(values).any():
        raise ValueError("carry must be defined on every signal date passed in")
    out = np.full(len(values), np.nan)
    for i in range(len(values)):
        n = i + 1
        if n < min_history:
            continue
        seen = values[: i + 1]
        below = np.count_nonzero(seen < values[i])
        ties_before = np.count_nonzero(seen[:i] == values[i])
        out[i] = (below + 0.5 * ties_before) / (n - 1)
    return pd.Series(out, index=carry.index, name=f"rank_{min_history}")


def excess_return_12m(index_leg: pd.Series, index_cash: pd.Series, signal_dates: pd.Series,
                      lag_rows: int = TREND_LAG_ROWS) -> pd.Series:
    """D(t)/D(t-12) - C(t)/C(t-12) of §6.3, with t-12 the signal date
    ``lag_rows`` rows earlier in the schedule; NaN for the first ``lag_rows``
    rows.  The indices are read on the signal dates only."""
    dates = pd.DatetimeIndex(signal_dates.values)
    leg = index_leg.reindex(dates).to_numpy(dtype=float)
    cash = index_cash.reindex(dates).to_numpy(dtype=float)
    if np.isnan(leg).any() or np.isnan(cash).any():
        raise ValueError("an index is undefined on a signal date")
    out = np.full(len(dates), np.nan)
    out[lag_rows:] = leg[lag_rows:] / leg[:-lag_rows] - cash[lag_rows:] / cash[:-lag_rows]
    return pd.Series(out, index=signal_dates.index, name="excess_12m")


def trend_signal(index_leg: pd.Series, index_cash: pd.Series, signal_dates: pd.Series,
                 lag_rows: int = TREND_LAG_ROWS) -> pd.Series:
    """h_t of §6.3: 1 if the 12-month excess return is positive, else 0; NaN
    where it is undefined.  Study 003 §6.1's rule on the given indices."""
    x = excess_return_12m(index_leg, index_cash, signal_dates, lag_rows)
    h = pd.Series(np.where(x > 0, 1.0, 0.0), index=x.index, name="trend")
    return h.mask(x.isna())


def blend(weight: pd.Series, trend: pd.Series, carry_weight: float = BLEND_CARRY_WEIGHT) -> pd.Series:
    """T2's weight (§6.3, §7): carry_weight x w_t + (1 - carry_weight) x h_t;
    NaN wherever either input is."""
    return (carry_weight * weight + (1.0 - carry_weight) * trend).rename("blend")


def turnover(weights: pd.Series, initial_weight: float = 0.0) -> float:
    """Sum of |w_t - w_{t-1}| over the path, the first step from
    ``initial_weight``: the one-way turnover without drift, used only as a
    descriptive figure beside the gate (§5.3.4).  The decision statistic of
    §8.1 is the engine's traded fraction with drift (``tilt.run_tilt``)."""
    w = weights.dropna().to_numpy(dtype=float)
    if len(w) == 0:
        return 0.0
    return float(abs(w[0] - initial_weight) + np.abs(np.diff(w)).sum())
