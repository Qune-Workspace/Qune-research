"""Monthly backtest engine: switching rule, costs and benchmarks (§6, §9.1, §9.2).

Inputs are total-return indices (synthetic, §5.2, or actual ETF, §5.1) and a
schedule of execution dates (§6.3).  Holding-period returns run from the
close of one execution date to the close of the next; an index that is not
observed on an execution date (a synthetic series on a bond-market holiday)
is taken as of the last observation on or before it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (CASH_LEG, DURATION_LEG, MAX_MISSING_BARS, STOP_DESCRIPTIVE_DRAWDOWN)

INSTRUMENTS = (DURATION_LEG, CASH_LEG)


def resolve_execution_dates(schedule: pd.DataFrame, bar_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Move each execution date to the first bar on or after it and record
    the slippage in bars (§6.5).  Raises if more than ``MAX_MISSING_BARS``
    consecutive bars are missing, which halts the study."""
    resolved = schedule.copy()
    positions = bar_dates.searchsorted(schedule["execution_date"].values, side="left")
    if positions[-1] >= len(bar_dates):
        raise ValueError("bars end before the last execution date")
    actual = pd.DatetimeIndex(bar_dates[positions])
    planned = pd.DatetimeIndex(schedule["execution_date"])
    resolved["days_slipped"] = np.busday_count(planned.values.astype("datetime64[D]"),
                                               actual.values.astype("datetime64[D]"))
    resolved["execution_date"] = actual
    resolved["period_end"] = resolved["execution_date"].shift(-1)
    if (resolved["days_slipped"] > MAX_MISSING_BARS).any():
        raise ValueError("more than three consecutive ETF bars missing on an execution date (§6.5)")
    return resolved


def holding_period_returns(tri: pd.Series, schedule: pd.DataFrame) -> pd.Series:
    """Return from the close of each execution date to the close of the next,
    indexed by the schedule month of the period start."""
    periods = schedule.iloc[:-1]
    start = tri.reindex(periods["execution_date"], method="ffill").to_numpy()
    end = tri.reindex(periods["period_end"], method="ffill").to_numpy()
    if np.isnan(start).any() or np.isnan(end).any():
        raise ValueError("total-return index does not cover the schedule")
    return pd.Series(end / start - 1.0, index=periods.index, name="r")


def instrument_returns(indices: dict[str, pd.Series], schedule: pd.DataFrame) -> pd.DataFrame:
    """Holding-period returns of both instruments, columns ``IEF`` and ``BIL``."""
    return pd.DataFrame({name: holding_period_returns(indices[name], schedule) for name in INSTRUMENTS})


def _switch_factor(cost_per_side: float, traded_fraction) -> float:
    """Equity multiplier for selling ``traded_fraction`` of equity on one leg
    and buying the same amount on the other, each side costing
    ``cost_per_side`` of the traded notional (§6.6, §9.1)."""
    return (1.0 - cost_per_side * traded_fraction) ** 2


def run_switching(targets: pd.Series, returns: pd.DataFrame, cost_per_side: float,
                  initial_holding: str = CASH_LEG) -> pd.DataFrame:
    """The monthly loop of §6.6.  ``targets`` is indexed like ``returns`` (one
    entry per holding period, the target set at that period's execution
    date).  A switch pays ``cost_per_side`` on the sale and on the purchase
    of 100% of equity; no order and no cost when the target equals the
    holding (§6.4)."""
    targets = targets.reindex(returns.index)
    if targets.isna().any():
        raise ValueError("every holding period needs a target")
    holding = initial_holding
    rows = []
    for month, target in targets.items():
        switched = target != holding
        holding = target
        gross = returns.at[month, holding]
        factor = _switch_factor(cost_per_side, 1.0) if switched else 1.0
        rows.append({"holding": holding, "switched": switched, "r_gross": gross,
                     "cost": 1.0 - factor, "r": factor * (1.0 + gross) - 1.0})
    out = pd.DataFrame(rows, index=returns.index)
    out["r_held_minus_other"] = np.where(out["holding"] == DURATION_LEG,
                                         returns[DURATION_LEG] - returns[CASH_LEG],
                                         returns[CASH_LEG] - returns[DURATION_LEG])
    return out


def run_static(weight_ief: float, returns: pd.DataFrame, cost_per_side: float) -> pd.DataFrame:
    """Static mix rebalanced to ``weight_ief`` at every execution date (§9.1).
    The rebalancing trade is the drift of the IEF weight over the previous
    period; both sides pay ``cost_per_side`` on that notional.  With weight 0
    or 1 nothing drifts and nothing is charged, which makes B0 and B1 pure
    buy-and-hold after the initial purchase."""
    w = float(weight_ief)
    r_ief, r_bil = returns[DURATION_LEG].to_numpy(), returns[CASH_LEG].to_numpy()
    gross = w * r_ief + (1.0 - w) * r_bil
    drift = np.empty_like(gross)
    drift[0] = w
    drift[1:] = w * (1.0 + r_ief[:-1]) / (1.0 + gross[:-1])
    traded = np.abs(drift - w)
    factor = _switch_factor(cost_per_side, traded)
    return pd.DataFrame({"weight_ief": w, "traded_fraction": traded, "r_gross": gross,
                         "cost": 1.0 - factor, "r": factor * (1.0 + gross) - 1.0}, index=returns.index)


def benchmarks(returns: pd.DataFrame, weight_b3: float, cost_per_side: float) -> dict[str, pd.DataFrame]:
    """B0 cash, B1 buy-and-hold IEF, B2 50/50, B3 same-exposure static (§9.1)."""
    return {"B0": run_static(0.0, returns, 0.0),
            "B1": run_static(1.0, returns, 0.0),
            "B2": run_static(0.5, returns, cost_per_side),
            "B3": run_static(weight_b3, returns, cost_per_side)}


def exposure_fraction(targets: pd.Series) -> float:
    """Fraction of holding periods in which the rule holds IEF: the frozen
    weight w of benchmark B3 (§9.1), a function of the signal only."""
    return float((targets == DURATION_LEG).mean())


def daily_strategy_index(result: pd.DataFrame, schedule: pd.DataFrame,
                         indices: dict[str, pd.Series]) -> pd.Series:
    """Daily total-return index of a switching result from daily instrument
    indices (for the daily maximum drawdown of §9.3 item 4).  Within each
    holding period the held instrument's daily returns apply; the switch cost
    is charged at the execution-date close."""
    periods = schedule.iloc[:-1]
    pieces = []
    level = 1.0
    for month, row in periods.iterrows():
        held = indices[result.at[month, "holding"]]
        base = held.reindex([row["execution_date"]], method="ffill").iloc[0]
        relative = held.loc[row["execution_date"]:row["period_end"]] / base
        if relative.index[0] == row["execution_date"]:
            relative = relative.iloc[1:]
        level *= 1.0 - result.at[month, "cost"]
        pieces.append(level * relative)
        level = pieces[-1].iloc[-1]
    return pd.concat(pieces).rename("tri")


def stop_touch_count(result: pd.DataFrame, schedule: pd.DataFrame, ief_index: pd.Series,
                     threshold: float = STOP_DESCRIPTIVE_DRAWDOWN) -> int:
    """Number of holding periods in which IEF was held and closed at least 5%
    below its entry close at some point (§11.4 descriptive item, no decision
    weight)."""
    count = 0
    for month, row in schedule.iloc[:-1].iterrows():
        if result.at[month, "holding"] != DURATION_LEG:
            continue
        entry = ief_index.reindex([row["execution_date"]], method="ffill").iloc[0]
        path = ief_index.loc[row["execution_date"]:row["period_end"]]
        if (path / entry - 1.0).min() <= threshold:
            count += 1
    return count
