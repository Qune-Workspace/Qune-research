"""Study 007 engine for a fractional weight path (PREREGISTRATION.md §6.4-§6.5).

Each holding period: the target weight w_t in the duration leg is set at the
execution date; the traded fraction is |w_t - w~_{t-1}|, where w~_{t-1} is the
previous weight after drifting with the two legs' returns over the period
just ended (the convention of Study 001's static benchmarks,
``backtest.run_static``); both sides pay ``cost_per_side`` on that fraction
(``backtest._switch_factor``, the frozen cost formula).  The loop starts from
the cash leg (weight 0), as the copied switching engine does, so the first
period pays the cost of the first purchase.

Equalities proved by tests before any run (§6.5): a 0/1 path reproduces
``backtest.run_switching`` period by period; a constant path reproduces
``backtest.run_static`` from the second period onward.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import _switch_factor
from .config import CASH_LEG, DURATION_LEG


def run_tilt(weights: pd.Series, returns: pd.DataFrame, cost_per_side: float,
             initial_weight: float = 0.0) -> pd.DataFrame:
    """Monthly loop for a weight path.  ``weights`` is indexed like
    ``returns`` (one target per holding period, set at that period's
    execution date) and must be defined on every period, in [0, 1]."""
    weights = weights.reindex(returns.index)
    if weights.isna().any():
        raise ValueError("every holding period needs a weight")
    w = weights.to_numpy(dtype=float)
    if (w < 0).any() or (w > 1).any():
        raise ValueError("weights must lie in [0, 1]")
    r_leg = returns[DURATION_LEG].to_numpy(dtype=float)
    r_cash = returns[CASH_LEG].to_numpy(dtype=float)
    n = len(w)
    drifted_from = np.empty(n)
    traded = np.empty(n)
    gross = np.empty(n)
    r = np.empty(n)
    prev = float(initial_weight)
    for i in range(n):
        drifted_from[i] = prev
        traded[i] = abs(w[i] - prev)
        factor = _switch_factor(cost_per_side, traded[i])
        gross[i] = w[i] * r_leg[i] + (1.0 - w[i]) * r_cash[i]
        r[i] = factor * (1.0 + gross[i]) - 1.0
        prev = w[i] * (1.0 + r_leg[i]) / (1.0 + gross[i])
    cost = 1.0 - np.array([_switch_factor(cost_per_side, t) for t in traded])
    return pd.DataFrame(
        {"weight": w, "drifted_from": drifted_from, "traded_fraction": traded,
         "r_gross": gross, "cost": cost, "r": r},
        index=returns.index,
    )


def total_turnover(result: pd.DataFrame) -> float:
    """Total one-way turnover of §8.1: the sum of the traded fractions."""
    return float(result["traded_fraction"].sum())


def mean_weight(weights: pd.Series) -> float:
    """The frozen weight of a trial's exposure-matched benchmark B3 (§8.1,
    §9.1): the mean of its weight path over its window, from signals only."""
    w = weights.dropna()
    if len(w) == 0:
        raise ValueError("no weights")
    return float(w.mean())
