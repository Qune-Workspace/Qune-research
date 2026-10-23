"""Wiring of the frozen Study 003 engine to this study's rule for one window
(§6, §8, §9.1–9.2): indices, schedule, trend signal, regime, targets, paths.

Every return of a strategy in this study comes through ``window_paths``; the
tests of §5.3.5 (i) call it with forced regimes and compare B2 with Study
003's committed file.  Nothing here reads a raw file: the loaders are in
``data.py`` and the callers (``checks``, ``report``) pass series in.
"""
from __future__ import annotations

import pandas as pd

from . import switching
from .cash import cash_index
from .conditional import conditional_targets, trend_minus_hold
from .config import CASH_LEG, DURATION_LEG
from .schedule import build_schedule, month_end_bars
from .trend_signal import t1 as trend_t1


def insample_indices(close_ief: pd.Series, dtb3_pct: pd.Series) -> dict[str, pd.Series]:
    """IEF: the vendor's adjusted close as a total-return index; BIL: the
    §5.2 cash accrual from DTB3 (Study 003's in-sample convention)."""
    close = close_ief.astype(float).dropna().sort_index()
    return {DURATION_LEG: (close / close.iloc[0]).rename("tri"), CASH_LEG: cash_index(dtb3_pct)}


def etf_indices(closes: dict[str, pd.Series]) -> dict[str, pd.Series]:
    """Both ETFs from ``adjustment='all'`` closes, normalised to 1.0 on the
    first bar (Study 003's episode convention)."""
    out = {}
    for name in (DURATION_LEG, CASH_LEG):
        close = closes[name].astype(float).dropna().sort_index()
        out[name] = (close / close.iloc[0]).rename("tri")
    return out


def window_bars(indices: dict[str, pd.Series], etf_cash: bool) -> pd.DatetimeIndex:
    """The bar index a window is scheduled on, as Study 003 did it: IEF's bars
    in-sample (the cash accrual lives on the FRED calendar and is taken as of
    each bar), the two ETFs' common bars when BIL is an actual ETF."""
    bars = indices[DURATION_LEG].index
    return bars.intersection(indices[CASH_LEG].index) if etf_cash else bars


def window_schedule(bars: pd.DatetimeIndex, first_month: str, last_month: str) -> tuple[pd.DataFrame, pd.Series]:
    """Resolved monthly schedule and the month-end bars (Study 003's
    ``run_insample`` / ``run_oos`` conventions)."""
    schedule = switching.resolve_execution_dates(build_schedule(bars, first_month, last_month), bars)
    return schedule, month_end_bars(bars)


def trend_frame(indices: dict[str, pd.Series], month_ends: pd.Series, schedule: pd.DataFrame) -> pd.DataFrame:
    """Study 003's T1 signal frame on the schedule's signal dates (B2's rule)."""
    return trend_t1(indices[DURATION_LEG], indices[CASH_LEG], month_ends, schedule["signal_date"])


def period_targets(signal_frame: pd.DataFrame, schedule: pd.DataFrame) -> pd.Series:
    """Targets of the holding periods (every schedule row but the last)."""
    return signal_frame["target"].reindex(schedule.index[:-1]).dropna()


def window_paths(indices: dict[str, pd.Series], schedule: pd.DataFrame, trend_targets: pd.Series,
                 positive: pd.Series, cost_per_side: float, weight_b3: float | None = None) -> dict:
    """B0, B1, B2 (the unconditional trend rule), B3 (the frozen mix) and T1
    (the conditional rule) on the trend targets' holding periods, plus the
    instrument returns and ``d_t``.  ``positive`` must cover every period."""
    returns = switching.instrument_returns(indices, schedule).loc[trend_targets.index]
    targets_t1 = conditional_targets(trend_targets, positive)
    if weight_b3 is None:
        weight_b3 = switching.exposure_fraction(targets_t1)
    results = {"B0": switching.run_static(0.0, returns, 0.0),
               "B1": switching.run_static(1.0, returns, 0.0),
               "B2": switching.run_switching(trend_targets, returns, cost_per_side),
               "B3": switching.run_static(weight_b3, returns, cost_per_side),
               "T1": switching.run_switching(targets_t1, returns, cost_per_side)}
    d = trend_minus_hold(results["B2"]["r"], results["B1"]["r"])
    return {"results": results, "returns": returns, "targets_T1": targets_t1, "weight_b3": weight_b3, "d": d,
            "b2_in_bills": (results["B2"]["holding"] == CASH_LEG).rename("b2_in_bills"),
            "ief_excess": (returns[DURATION_LEG] - returns[CASH_LEG]).rename("ief_excess")}
