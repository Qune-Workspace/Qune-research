"""Deterministic toy data for the tests.  Nothing here is real market data:
the two ETF prices are seeded random walks whose daily returns are
correlated with a sign that flips by construction, the bill yield is a seeded
random walk, and the calendar is the rule-based NYSE calendar."""
from __future__ import annotations

import numpy as np
import pandas as pd

from qune_research.nyse import nyse_trading_days
from src.cash import cash_index

SEED = 2005


def toy_bars(start: str = "2000-01-03", end: str = "2007-12-31") -> pd.DatetimeIndex:
    return nyse_trading_days(start, end)


def toy_closes(bars: pd.DatetimeIndex, seed: int = SEED, flip_every: int = 252) -> dict[str, pd.Series]:
    """IEF and SPY closes whose daily-return correlation is about +0.6 in
    the first ``flip_every`` days, −0.6 in the next, and so on; IEF carries
    a two-year cycle so that the 12-month trend signal changes sign."""
    rng = np.random.default_rng(seed)
    n = len(bars)
    z1, z2 = rng.normal(0, 1, n), rng.normal(0, 1, n)
    sign = np.where((np.arange(n) // flip_every) % 2 == 0, 1.0, -1.0)
    r_ief = 0.004 * z1 + 0.0001
    r_spy = 0.010 * (0.6 * sign * z1 + 0.8 * z2) + 0.0003
    cycle = 0.06 * np.sin(2 * np.pi * np.arange(n) / 520)
    ief = 100.0 * np.exp(np.cumsum(r_ief) + cycle)
    spy = 100.0 * np.exp(np.cumsum(r_spy))
    return {"IEF": pd.Series(ief, index=bars, name="adjClose"), "SPY": pd.Series(spy, index=bars, name="adjClose"),
            "sign": pd.Series(sign, index=bars)}


def toy_dtb3(start: str = "2000-01-03", end: str = "2007-12-31", seed: int = SEED) -> pd.Series:
    rng = np.random.default_rng(seed + 2)
    dates = pd.bdate_range(start, end)
    level = np.clip(2.0 + np.cumsum(rng.normal(0, 0.02, len(dates))), 0.01, None)
    series = pd.Series(level, index=dates, name="DTB3")
    series.loc[dates[rng.random(len(dates)) < 0.03]] = np.nan
    return series


def toy_world() -> dict:
    bars = toy_bars()
    closes = toy_closes(bars)
    dtb3 = toy_dtb3()
    ief = closes["IEF"]
    return {"bars": bars, "closes": closes, "dtb3": dtb3,
            "indices": {"IEF": (ief / ief.iloc[0]).rename("tri"), "BIL": cash_index(dtb3)}}


def toy_cpi(start: str = "1999-01", end: str = "2008-12", seed: int = SEED) -> pd.Series:
    """A monthly index level whose twelve-month change crosses 3% a few times."""
    rng = np.random.default_rng(seed + 5)
    months = pd.period_range(start, end, freq="M")
    monthly = 0.0025 + 0.002 * np.sin(2 * np.pi * np.arange(len(months)) / 36) + rng.normal(0, 0.0005, len(months))
    return pd.Series(100.0 * np.cumprod(1 + monthly), index=months, name="CPIAUCNS")
