"""The regime variables (§6.1, §7): the sign of the trailing SPY–IEF
correlation over a fixed count of common return days (T1: 63, T2: 252), and
the CPI inflation regime (T3).

The correlation window is count-based: the ``window`` most recent trading
days on or before the signal date on which *both* series have a daily total
return.  A missing bar lengthens the calendar span and never shortens the
sample (§6.1).  No dead band, no smoothing: ``positive`` is ``rho > 0``.

The CPI flag at the signal date of month m reads the twelve-month change of
the index for month m − 2 (§6.1, §5.3.5 (v)); no later month is visible.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CPI_LAG_MONTHS, CPI_THRESHOLD, REGIME_WINDOWS


def daily_returns(close: pd.Series) -> pd.Series:
    """``close_t / close_{t-1} - 1`` on the series' own bar dates (§5.1)."""
    close = close.astype(float).dropna().sort_index()
    return (close / close.shift(1) - 1.0).dropna()


def common_returns(close_spy: pd.Series, close_ief: pd.Series) -> pd.DataFrame:
    """Daily returns of both series on the days both have one; columns
    ``SPY`` and ``IEF``.  Each return is computed on its own series first, so a
    day missing in one series does not change the other's return."""
    r_spy, r_ief = daily_returns(close_spy), daily_returns(close_ief)
    common = r_spy.index.intersection(r_ief.index).sort_values()
    return pd.DataFrame({"SPY": r_spy.loc[common].to_numpy(), "IEF": r_ief.loc[common].to_numpy()}, index=common)


def trailing_correlation(returns: pd.DataFrame, signal_dates: pd.Series, window: int) -> pd.Series:
    """Pearson correlation of the ``window`` most recent common return days on
    or before each signal date, indexed like ``signal_dates`` (by month).
    NaN where fewer than ``window`` common returns exist (the caller drops or
    refuses those months); never fewer than ``window`` days are used."""
    returns = returns.sort_index()
    out = {}
    for month, t in signal_dates.items():
        upto = returns.loc[:pd.Timestamp(t)]
        if len(upto) < window:
            out[month] = np.nan
            continue
        tail = upto.iloc[-window:]
        out[month] = float(np.corrcoef(tail["SPY"].to_numpy(), tail["IEF"].to_numpy())[0, 1])
    return pd.Series(out, name="rho", dtype=float)


def regime_from_rho(rho: pd.Series) -> pd.Series:
    """``positive`` flag: ``rho > 0`` exactly; NaN rho is an error for the
    caller to raise, never silently negative."""
    if rho.isna().any():
        raise ValueError(f"correlation undefined on months {[str(m) for m in rho.index[rho.isna()]]}")
    return (rho > 0.0).rename("positive")


def correlation_regime(returns: pd.DataFrame, signal_dates: pd.Series, trial: str) -> pd.DataFrame:
    """Frame indexed by month with ``signal_date``, ``rho``, ``positive`` for
    trial ``T1`` or ``T2`` (§7); months whose window reaches before the first
    common return are dropped, a later undefined month is an error."""
    rho = trailing_correlation(returns, signal_dates, REGIME_WINDOWS[trial])
    defined = rho.dropna()
    if defined.empty:
        raise ValueError("no signal date has a full correlation window")
    later = rho.loc[defined.index[0]:]
    positive = regime_from_rho(later)
    return pd.DataFrame({"signal_date": signal_dates.reindex(later.index), "rho": later, "positive": positive})


def cpi_twelve_month_change(cpi: pd.Series) -> pd.Series:
    """Twelve-month change of a monthly index level series indexed by month
    period: ``level_m / level_{m-12} - 1``."""
    levels = cpi.astype(float).copy()
    levels.index = pd.PeriodIndex(levels.index, freq="M") if not isinstance(levels.index, pd.PeriodIndex) \
        else levels.index
    levels = levels.sort_index()
    full = levels.reindex(pd.period_range(levels.index[0], levels.index[-1], freq="M"))
    return (full / full.shift(12) - 1.0).rename("cpi_12m_change")


def cpi_regime(cpi: pd.Series, signal_dates: pd.Series, threshold: float = CPI_THRESHOLD,
               lag_months: int = CPI_LAG_MONTHS) -> pd.DataFrame:
    """T3 (§6.1): at the signal date of month m the flag is
    ``change(m - lag) > threshold``; frame with ``signal_date``,
    ``cpi_month``, ``cpi_12m_change``, ``positive``.  A month whose lagged
    change is undefined is dropped at the start and an error later."""
    change = cpi_twelve_month_change(cpi)
    months = pd.PeriodIndex(signal_dates.index, freq="M")
    lagged = months - lag_months
    values = change.reindex(lagged)
    values.index = signal_dates.index
    defined = values.dropna()
    if defined.empty:
        raise ValueError("no signal month has a defined lagged CPI change")
    later = values.loc[defined.index[0]:]
    if later.isna().any():
        raise ValueError(f"CPI change undefined on months {[str(m) for m in later.index[later.isna()]]}")
    return pd.DataFrame({"signal_date": signal_dates.reindex(later.index),
                         "cpi_month": [str(p) for p in lagged[signal_dates.index.get_indexer(later.index)]],
                         "cpi_12m_change": later, "positive": (later > threshold).rename("positive")})


def regime_episodes(positive: pd.Series) -> dict:
    """§5.3.4 descriptives: count and share of positive months, number of
    regime changes, mean and longest positive episode."""
    flags = positive.astype(bool).to_numpy()
    n = int(len(flags))
    changes = int((flags[1:] != flags[:-1]).sum()) if n > 1 else 0
    starts = flags & ~np.concatenate([[False], flags[:-1]])
    n_episodes = int(starts.sum())
    lengths = []
    run = 0
    for f in flags:
        if f:
            run += 1
        elif run:
            lengths.append(run)
            run = 0
    if run:
        lengths.append(run)
    return {"months": n, "positive_months": int(flags.sum()), "positive_share": float(flags.mean()) if n else float("nan"),
            "regime_changes": changes, "positive_episodes": n_episodes,
            "mean_positive_episode_months": float(np.mean(lengths)) if lengths else float("nan"),
            "longest_positive_episode_months": int(max(lengths)) if lengths else 0}
