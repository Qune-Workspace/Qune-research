"""Trend signals and volatility-targeted weights (Study 004 §6.1–§6.2).

Every function takes only data dated on or before the signal date it is
asked about; the look-ahead tests in ``tests/`` perturb later prices and
assert that nothing here changes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .dates import months_before

TRADING_DAYS = 252


def excess_momentum(tri: pd.Series, cash_tri: pd.Series, signal_date: pd.Timestamp,
                    lookback_months: int) -> float | None:
    """``TRI(t)/TRI(t_L) − cash(t)/cash(t_L)`` (§6.1), or None if the asset has
    no bar at t_L (it has not entered the universe)."""
    t = pd.Timestamp(signal_date)
    t_l = months_before(t, lookback_months, pd.DatetimeIndex(tri.dropna().index))
    if t_l is None or t not in tri.index or np.isnan(tri.loc[t]):
        return None
    cash = cash_tri.reindex([t_l, t], method="ffill")
    if cash.isna().any():
        return None
    return float(tri.loc[t] / tri.loc[t_l] - cash.iloc[1] / cash.iloc[0])


def trend_signal(tri: pd.Series, cash_tri: pd.Series, signal_date: pd.Timestamp,
                 lookback_months: int) -> float | None:
    """1 if the excess momentum is strictly positive, 0 otherwise; None if the
    asset has not entered (§6.1, threshold exactly zero)."""
    m = excess_momentum(tri, cash_tri, signal_date, lookback_months)
    return None if m is None else (1.0 if m > 0 else 0.0)


def realised_vol(tri: pd.Series, signal_date: pd.Timestamp, window: int = 63) -> float | None:
    """Annualised standard deviation of the last ``window`` daily simple
    returns ending at the signal date (§6.2); None if fewer are available."""
    t = pd.Timestamp(signal_date)
    s = tri.dropna()
    s = s[s.index <= t]
    if len(s) < window + 1:
        return None
    r = s.iloc[-(window + 1):].pct_change().dropna()
    if len(r) < window:
        return None
    return float(r.std(ddof=1) * np.sqrt(TRADING_DAYS))


def target_weights(signals: dict[str, float], vols: dict[str, float], sigma_a: float = 0.10,
                   cap: float = 0.25) -> dict[str, float]:
    """``w_i = s_i × min(σ_a / (N × σ_i), cap)`` over the assets present in
    ``signals`` (N = their count, long or flat), then a proportional
    scale-down if the weights sum to more than one (§6.2).  Assets whose
    signal or volatility is None are absent (not in N)."""
    present = [a for a in signals if signals[a] is not None and vols.get(a) is not None]
    n = len(present)
    w = {}
    for a in present:
        sigma = vols[a]
        raw = sigma_a / (n * sigma) if sigma > 0 else cap
        w[a] = float(signals[a]) * min(raw, cap)
    total = sum(w.values())
    if total > 1.0:
        w = {a: v / total for a, v in w.items()}
    return w
