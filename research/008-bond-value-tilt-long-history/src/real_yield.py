"""Study 008 signals (PREREGISTRATION.md §6.1-§6.2, with the two §16
clarifications of 2026-10-25 18:27 GMT): which CPI month each signal month
may use, the 12-month inflation rate from it, the real yield at the signal
dates, and the two ranks that are the weights (expanding, from the copied
``carry_rank``; trailing 120, new here).  Pure functions of the inputs they
are given; this module imports nothing from ``backtest.py`` or ``tilt.py``
(§13 test 1) and never forms a return of any rule.

Months are pandas monthly ``Period`` values throughout, as in ``calendar``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .carry_rank import expanding_rank

HEADLINE = "CPIAUCNS"
CORE = "CPILFENS"
TRAILING_WINDOW = 120  # §6.2, T1b


def monthly(cpi: pd.Series) -> pd.Series:
    """A FRED monthly file (first-of-month dates, NaN where empty) indexed by
    monthly period instead.  Missing values stay NaN."""
    out = pd.Series(cpi.to_numpy(dtype=float), index=pd.DatetimeIndex(cpi.index).to_period("M"),
                    name=cpi.name)
    if out.index.has_duplicates:
        raise ValueError("one value per month expected")
    return out


def k_months(availability: pd.DataFrame, series_id: str) -> pd.Series:
    """k for each signal month (§6.1), from the data step's
    ``results/cpi_availability.csv``.

    * Release read: k as recorded (m - 1 if published by t, else the latest
      month published by t).
    * No vintage of ``series_id`` at t (branch ``assumed_known``): for the
      core series, the headline's release for the same signal date when that
      was read (§16 (a): one BLS release carries both); otherwise k = m - 1.
    """
    months = pd.PeriodIndex(availability["signal_month"], freq="M")
    own_k = pd.PeriodIndex(availability[f"{series_id}_k"], freq="M")
    own_branch = availability[f"{series_id}_branch"].to_numpy()
    k = pd.Series(own_k, index=months, name=f"k_{series_id}")
    if series_id != HEADLINE:
        head_k = pd.PeriodIndex(availability[f"{HEADLINE}_k"], freq="M")
        head_read = availability[f"{HEADLINE}_branch"].to_numpy() == "release_date_read"
        use_head = (own_branch == "assumed_known") & head_read
        k[use_head] = head_k[use_head]
    if (k > months - 1).any():
        raise ValueError("k must be m - 1 or earlier, never m")
    return k


def inflation_12m(cpi_m: pd.Series, k: pd.Series) -> pd.Series:
    """π_m = CPI(k) / CPI(k - 12) - 1 per signal month m (index of ``k``).

    Undefined (NaN) when CPI(k) or CPI(k - 12) is missing, and, under §16 (b),
    whenever CPI(m - 1) is missing from the current file (an index that was
    never published takes the hold rule, not the availability rule)."""
    m = k.index
    level_k = cpi_m.reindex(pd.PeriodIndex(k.to_numpy(), freq="M")).to_numpy()
    level_k12 = cpi_m.reindex(pd.PeriodIndex(k.to_numpy(), freq="M") - 12).to_numpy()
    level_m1 = cpi_m.reindex(m - 1).to_numpy()
    pi = level_k / level_k12 - 1.0
    pi[np.isnan(level_m1)] = np.nan
    return pd.Series(pi, index=m, name="pi")


def real_yield(dgs10_pct: pd.Series, signal_dates: pd.Series, pi: pd.Series) -> pd.Series:
    """r_m = DGS10_t / 100 - π_m, with t the signal date of month m
    (``signal_dates`` indexed by month, as ``calendar.signal_dates``)."""
    t = pd.DatetimeIndex(signal_dates.reindex(pi.index).to_numpy())
    y = dgs10_pct.reindex(t).to_numpy(dtype=float) / 100.0
    return pd.Series(y - pi.to_numpy(dtype=float), index=pi.index, name="real_yield")


def trailing_rank(values: pd.Series, window: int = TRAILING_WINDOW) -> pd.Series:
    """§6.2 for T1b: over the last ``window`` values including today's,

        (#{s in window : r_s < r_m} + 0.5 * #{s in window, s < m : r_s = r_m}) / (window - 1),

    NaN until ``window`` values exist.  ``values`` must be defined throughout
    (use ``rank_defined``)."""
    if window < 2:
        raise ValueError("window must be at least 2")
    v = values.to_numpy(dtype=float)
    if np.isnan(v).any():
        raise ValueError("values must be defined on every month passed in")
    out = np.full(len(v), np.nan)
    for i in range(window - 1, len(v)):
        seen = v[i - window + 1 : i + 1]
        below = np.count_nonzero(seen < v[i])
        ties_before = np.count_nonzero(seen[:-1] == v[i])
        out[i] = (below + 0.5 * ties_before) / (window - 1)
    return pd.Series(out, index=values.index, name=f"trailing_rank_{window}")


def rank_defined(r: pd.Series, kind: str, n: int) -> pd.Series:
    """Rank only the defined real yields (§6.1: an undefined month is left out
    of the rank history, so n counts defined values) and put the result back
    on every month; undefined months get NaN (the trial holds there).
    ``kind`` is "expanding" (minimum history ``n``) or "trailing" (window
    ``n``)."""
    defined = r.dropna()
    if kind == "expanding":
        ranked = expanding_rank(defined, n)
    elif kind == "trailing":
        ranked = trailing_rank(defined, n)
    else:
        raise ValueError(f"unknown rank kind {kind!r}")
    return ranked.reindex(r.index).rename(f"w_{kind}_{n}")
