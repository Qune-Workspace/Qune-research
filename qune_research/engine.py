"""Multi-asset monthly backtest with drift and per-asset costs (Study 004 §6.3–§6.4).

Inputs: total-return indices (one column per asset), a cash index, a
schedule from ``dates.schedule`` and, for each signal date, the target
weights set at that date's execution close.  The holding period runs from
the close of one execution date to the close of the next.  Within a period
weights drift with the assets' returns; at the next execution date the
portfolio is traded back to the new targets and the cost of the month is
``Σ_i |Δw_i| × c_i`` on the pre-trade value, where Δw_i is the change from
the drifted weight.  The initial purchase is charged like any other trade.
An index not observed on an execution date is taken as of the last
observation on or before it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _value_at(tri: pd.Series, date: pd.Timestamp) -> float:
    v = tri.reindex([date], method="ffill").iloc[0]
    if np.isnan(v):
        raise ValueError(f"index does not cover {date.date()}")
    return float(v)


def run(prices: pd.DataFrame, cash_tri: pd.Series, schedule: pd.DataFrame,
        weights: dict[pd.Timestamp, dict[str, float]], costs: dict[str, float]) -> pd.DataFrame:
    """One row per holding period, indexed by the signal date that opened it:
    ``gross`` (before cost), ``cost`` (fraction of pre-trade value),
    ``net`` (the period return), ``gross_exposure`` (Σ w_i at the open),
    ``turnover`` (Σ |Δw_i| at the open), plus one column ``w_<asset>`` per
    asset with the weight set at the open.  The last schedule row starts no
    period and is not returned."""
    periods = schedule.iloc[:-1]
    assets = list(prices.columns)
    drifted = {a: 0.0 for a in assets}          # all cash before the first trade
    rows = []
    for _, row in periods.iterrows():
        t, e, e_next = row["signal_date"], row["execution_date"], row["period_end"]
        target = {a: float(weights.get(t, {}).get(a, 0.0)) for a in assets}
        turnover = sum(abs(target[a] - drifted[a]) for a in assets)
        cost = sum(abs(target[a] - drifted[a]) * costs[a] for a in assets)
        asset_r = {a: _value_at(prices[a], e_next) / _value_at(prices[a], e) - 1.0 for a in assets
                   if target[a] != 0.0}
        cash_r = _value_at(cash_tri, e_next) / _value_at(cash_tri, e) - 1.0
        gross_exposure = sum(target.values())
        if gross_exposure > 1.0 + 1e-12:
            raise ValueError("weights sum to more than one (no leverage, §6.2)")
        gross = sum(target[a] * asset_r[a] for a in asset_r) + (1.0 - gross_exposure) * cash_r
        net = (1.0 - cost) * (1.0 + gross) - 1.0
        # drifted weights at the close of e_next, as fractions of the portfolio's value
        drifted = {a: (target[a] * (1.0 + asset_r[a]) / (1.0 + gross) if a in asset_r else 0.0)
                   for a in assets}
        rec = {"signal_date": t, "execution_date": e, "period_end": e_next, "gross": gross,
               "cost": cost, "net": net, "gross_exposure": gross_exposure, "turnover": turnover}
        rec.update({f"w_{a}": target[a] for a in assets})
        rows.append(rec)
    out = pd.DataFrame(rows).set_index("signal_date")
    return out


def exposure_ratio(t1: pd.DataFrame, b3: pd.DataFrame) -> float:
    """k for benchmark B4 (§9.1): the in-sample mean over months of T1's gross
    exposure divided by B3's.  A function of signals and volatilities only."""
    if not t1.index.equals(b3.index):
        raise ValueError("T1 and B3 must share the same holding periods")
    ratio = t1["gross_exposure"] / b3["gross_exposure"]
    ratio = ratio.replace([np.inf, -np.inf], np.nan).dropna()
    return float(ratio.mean())
