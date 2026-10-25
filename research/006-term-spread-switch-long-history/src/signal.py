"""Signals T1, T2 and T3 (§6.1, §7).

Each function returns, for the given signal dates, a frame with the signal
``value`` (decimal, annualised) and the ``target`` instrument: IEF when the
value is strictly positive, BIL otherwise.  The threshold is exactly zero and
no observation dated after the signal date is used (§6.3).
"""
from __future__ import annotations

import pandas as pd

from .bey import discount_to_bey, par_modified_duration
from .config import CASH_LEG, DURATION_LEG, T2_WINDOW


def daily_spread(dgs10_pct: pd.Series, dtb3_pct: pd.Series) -> pd.Series:
    """10-year yield minus the bond-equivalent 3-month bill yield, decimal,
    on every date where both are observed (§6.1)."""
    both = pd.concat([dgs10_pct.rename("dgs10"), dtb3_pct.rename("dtb3")], axis=1, sort=True).dropna()
    spread = both["dgs10"] / 100.0 - discount_to_bey(both["dtb3"].values / 100.0)
    return spread.rename("spread")


def target_from_value(value: pd.Series) -> pd.Series:
    """``IEF if value > 0 else BIL`` (§6.1)."""
    return pd.Series(pd.NA, index=value.index, dtype="string").mask(
        value > 0, DURATION_LEG).mask(value <= 0, CASH_LEG).rename("target")


def _at_signal_dates(values: pd.Series, signal_dates: pd.Series, name: str) -> pd.DataFrame:
    """Signal values on the signal dates.  Signal dates before the first
    defined value are dropped (a trial whose input starts later simply has
    fewer holding periods); any later gap is an error, because a signal date
    is by construction a date on which the inputs are observed."""
    signal_dates = signal_dates[signal_dates >= values.index[0]]
    missing = signal_dates[~signal_dates.isin(values.index)]
    if len(missing):
        raise ValueError(f"{name} undefined on signal dates {list(missing.dt.date)}")
    value = pd.Series(values.loc[signal_dates.values].values, index=signal_dates.index, name="value")
    return pd.DataFrame({"signal_date": signal_dates, "value": value,
                         "target": target_from_value(value)})


def t1(dgs10_pct: pd.Series, dtb3_pct: pd.Series, signal_dates: pd.Series) -> pd.DataFrame:
    """T1: sign of the spread on the signal date (§6.1)."""
    return _at_signal_dates(daily_spread(dgs10_pct, dtb3_pct), signal_dates, "T1")


def t2(dgs10_pct: pd.Series, dtb3_pct: pd.Series, signal_dates: pd.Series,
       window: int = T2_WINDOW) -> pd.DataFrame:
    """T2: mean of the last ``window`` valid daily spreads ending on the
    signal date (§7).  Undefined until ``window`` observations exist."""
    smoothed = daily_spread(dgs10_pct, dtb3_pct).rolling(window, min_periods=window).mean().dropna()
    return _at_signal_dates(smoothed, signal_dates, "T2")


def carry(dgs10_pct: pd.Series, dgs7_pct: pd.Series, dtb3_pct: pd.Series) -> pd.Series:
    """Carry including roll-down (§7, after Koijen et al., 2018):
    ``spread + D_mod(DGS10) * (DGS10 - DGS7) / 3`` with every yield as a
    decimal and D_mod the modified duration of a 10-year par bond at DGS10."""
    spread = daily_spread(dgs10_pct, dtb3_pct)
    both = pd.concat([dgs10_pct.rename("dgs10"), dgs7_pct.rename("dgs7")], axis=1, sort=True).dropna() / 100.0
    rolldown = par_modified_duration(both["dgs10"].values) * (both["dgs10"] - both["dgs7"]) / 3.0
    return (spread + rolldown).dropna().rename("carry")


def t3(dgs10_pct: pd.Series, dgs7_pct: pd.Series, dtb3_pct: pd.Series,
       signal_dates: pd.Series) -> pd.DataFrame:
    """T3: sign of carry including roll-down on the signal date (§7)."""
    return _at_signal_dates(carry(dgs10_pct, dgs7_pct, dtb3_pct), signal_dates, "T3")
