"""Generic data-check statistics (Study 004 §5.3.1–§5.3.2).

Two functions a study applies its own thresholds and branches to; nothing
here decides anything.  Ported by attribution from Study 003's frozen
``src/checks.py`` (``coverage_check``) and ``src/bil_overlap_check.py``
(``overlap_statistics``), tree a18d02c, with the study constants removed.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .nyse import nyse_trading_days

TRADING_DAYS_PER_YEAR = 252


def longest_run(flags) -> int:
    longest = current = 0
    for flag in np.asarray(flags, dtype=bool):
        current = current + 1 if flag else 0
        longest = max(longest, current)
    return int(longest)


def coverage(bar_index: pd.DatetimeIndex, start, end, max_consecutive_missing: int = 3) -> dict:
    """Bars against the rule-based NYSE calendar on [start, end]: the trading
    days with no bar, the longest run of them, and the bars dated on days the
    rule calendar lists as closed (a calendar finding, reported, not a
    failure).  Dates only.  ``pass`` means the longest run of missing trading
    days is within ``max_consecutive_missing``."""
    bars = pd.DatetimeIndex(bar_index).sort_values()
    trading = nyse_trading_days(start, end)
    present = trading.isin(bars)
    missing = trading[~present]
    inside = bars[(bars >= pd.Timestamp(start)) & (bars <= pd.Timestamp(end))]
    extra = inside[~inside.isin(trading)]
    longest = longest_run(~present)
    return {"window": {"start": pd.Timestamp(start).strftime("%Y-%m-%d"), "end": pd.Timestamp(end).strftime("%Y-%m-%d")},
            "nyse_trading_days": int(len(trading)), "bars_present": int(present.sum()),
            "missing_days": [d.strftime("%Y-%m-%d") for d in missing],
            "max_consecutive_missing_days": longest, "max_consecutive_missing_allowed": int(max_consecutive_missing),
            "extra_bars_on_rule_calendar_closures": [d.strftime("%Y-%m-%d") for d in extra],
            "pass": bool(longest <= max_consecutive_missing)}


def daily_returns(close: pd.Series) -> pd.Series:
    close = close.astype(float).dropna()
    return (close / close.shift(1) - 1.0).dropna()


def overlap_statistics(vendor_close: pd.Series, broker_close: pd.Series, start, end,
                       large_diff: float = 0.0010) -> dict:
    """Vendor-minus-broker daily returns on the common return days inside
    [start, end]: annualised mean difference (mean daily difference × 252,
    the convention of Studies 001–003), correlation, annualised tracking
    error, the largest daily gap, the count of days over ``large_diff``, the
    mean difference by calendar year, and the days each series has that the
    other lacks.  No threshold is applied here."""
    r_v = daily_returns(vendor_close).loc[start:end]
    r_b = daily_returns(broker_close).loc[start:end]
    common = r_v.index.intersection(r_b.index)
    v, b = r_v.loc[common], r_b.loc[common]
    diff = v - b
    return {
        "window": {"start": pd.Timestamp(start).strftime("%Y-%m-%d"), "end": pd.Timestamp(end).strftime("%Y-%m-%d")},
        "common_return_days": int(len(common)),
        "first_common_return_date": common[0].strftime("%Y-%m-%d") if len(common) else None,
        "last_common_return_date": common[-1].strftime("%Y-%m-%d") if len(common) else None,
        "days_only_in_vendor": [d.strftime("%Y-%m-%d") for d in r_v.index.difference(r_b.index)],
        "days_only_in_broker": [d.strftime("%Y-%m-%d") for d in r_b.index.difference(r_v.index)],
        "mean_diff_annual_vendor_minus_broker": float(diff.mean() * TRADING_DAYS_PER_YEAR) if len(common) else float("nan"),
        "correlation_descriptive": float(v.corr(b)) if len(common) > 1 else float("nan"),
        "tracking_error_annual_descriptive": float(diff.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)) if len(common) > 1 else float("nan"),
        "max_abs_daily_diff": float(diff.abs().max()) if len(common) else float("nan"),
        "days_abs_diff_over_large": int((diff.abs() > large_diff).sum()),
        "large_diff": large_diff,
        "mean_diff_annual_by_year": {str(y): float(g.mean() * TRADING_DAYS_PER_YEAR) for y, g in diff.groupby(diff.index.year)},
    }
