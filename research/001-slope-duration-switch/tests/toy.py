"""Deterministic toy data for the tests.  Nothing here is real market data;
yields are a seeded random walk and the calendars are synthetic."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import SEED


def toy_yields(start: str = "2000-01-03", years: int = 6, seed: int = SEED,
               calendar: str = "B") -> dict[str, pd.Series]:
    """DGS10, DTB3 and DGS7 in percent on a weekday (or daily) calendar, with
    a few missing values to exercise the holiday handling."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=int(years * (260 if calendar == "B" else 365)), freq=calendar)
    n = len(dates)
    dgs10 = 4.0 + np.cumsum(rng.normal(0, 0.04, n))
    # The slope cycles through zero (a two-year cycle plus noise) so that the
    # rule switches several times in the toy sample.
    slope = 1.5 * np.sin(2 * np.pi * np.arange(n) / (2 * 260)) + np.cumsum(rng.normal(0, 0.01, n))
    dtb3 = np.clip(dgs10 - slope, 0.01, None)
    dgs7 = dgs10 - 0.15 + np.cumsum(rng.normal(0, 0.005, n))
    frame = pd.DataFrame({"DGS10": dgs10, "DTB3": dtb3, "DGS7": dgs7}, index=dates)
    holidays = dates[rng.random(n) < 0.03]
    frame.loc[holidays] = np.nan
    return {k: frame[k] for k in frame}
