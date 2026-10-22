"""Deterministic toy data for the tests.  Nothing here is real market data:
the ETF price is a seeded random walk with a slow cycle so that the momentum
rule switches several times, the bill yield is a seeded random walk, and the
calendars are synthetic."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.cash import cash_index
from src.config import SEED


def toy_bars(start: str = "2000-01-03", years: int = 8, seed: int = SEED,
             calendar: str = "B") -> pd.DatetimeIndex:
    """A weekday (or daily) bar calendar with a few random closures."""
    rng = np.random.default_rng(seed + 1)
    dates = pd.date_range(start, periods=int(years * (260 if calendar == "B" else 365)), freq=calendar)
    closed = rng.random(len(dates)) < 0.02
    return dates[~closed]


def toy_ief(bars: pd.DatetimeIndex, seed: int = SEED, drift: float = 0.0001) -> pd.Series:
    """Adjusted-close style price series on ``bars``: random walk plus a cycle
    of about two years so that the 12-month return changes sign."""
    rng = np.random.default_rng(seed)
    n = len(bars)
    cycle = 0.06 * np.sin(2 * np.pi * np.arange(n) / 520)
    log_price = np.log(100.0) + np.cumsum(rng.normal(drift, 0.004, n)) + cycle
    return pd.Series(np.exp(log_price), index=bars, name="adjClose")


def toy_dtb3(start: str = "2000-01-03", years: int = 8, seed: int = SEED) -> pd.Series:
    """DTB3 in percent on a weekday calendar with a few missing values."""
    rng = np.random.default_rng(seed + 2)
    dates = pd.bdate_range(start, periods=int(years * 260))
    level = np.clip(2.0 + np.cumsum(rng.normal(0, 0.02, len(dates))), 0.01, None)
    series = pd.Series(level, index=dates, name="DTB3")
    series.loc[dates[rng.random(len(dates)) < 0.03]] = np.nan
    return series


def toy_bil(bars: pd.DatetimeIndex, dtb3: pd.Series, seed: int = SEED, drift_annual: float = 0.0) -> pd.Series:
    """A toy bill ETF close that follows the cash accrual on ``bars`` with
    basis-point noise and an optional annual drift against it."""
    rng = np.random.default_rng(seed + 3)
    tri = cash_index(dtb3).reindex(bars, method="ffill")
    noise = np.cumsum(rng.normal(0, 0.3e-4, len(bars)))
    drift = drift_annual / 252 * np.arange(len(bars))
    return pd.Series(91.0 * tri.to_numpy() * np.exp(noise + drift), index=bars, name="close")


def toy_world(years: int = 8) -> dict:
    """Bars, indices and the inputs the engine needs."""
    bars = toy_bars(years=years)
    dtb3 = toy_dtb3(years=years)
    ief = toy_ief(bars)
    return {"bars": bars, "dtb3": dtb3, "ief_close": ief,
            "indices": {"IEF": (ief / ief.iloc[0]).rename("tri"), "BIL": cash_index(dtb3)}}
