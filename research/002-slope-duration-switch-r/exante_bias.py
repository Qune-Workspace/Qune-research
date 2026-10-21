"""Ex-ante bias components of the Study 002 synthetic duration leg (§5.3).

Reads FRED yields only (DGS7, DGS10).  Computes no return of any ETF, rule
or benchmark.  Run from this folder:

    python exante_bias.py <fred_DGS7.csv> <fred_DGS10.csv>

The output is pasted into PREREGISTRATION.md §5.3 so that every number used
to set a fidelity threshold is reproducible from public data.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

PERIODS = 17            # 8.5 years, semi-annual coupons
WINDOWS = {
    "W1 2016-01-04..2018-12-31": ("2016-01-04", "2018-12-31"),
    "W2 2003-01-02..2015-12-31": ("2003-01-02", "2015-12-31"),
    "IS 1969-07-01..2018-12-31": ("1969-07-01", "2018-12-31"),
}


def load(path: str) -> pd.Series:
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    dcol = [c for c in df.columns if "date" in c][0]
    vcol = [c for c in df.columns if c != dcol][0]
    v = pd.to_numeric(df[vcol].replace(".", np.nan), errors="coerce")
    v.index = pd.to_datetime(df[dcol])
    return v.dropna()


def par_mod_duration(y: np.ndarray, n: int = PERIODS) -> np.ndarray:
    """Modified duration (years) of a par bond at decimal yield ``y`` with
    ``n`` semi-annual periods, from the cash-flow sum."""
    i = y[..., None] / 2.0
    k = np.arange(1, n + 1, dtype=float)
    cf = np.broadcast_to(y[..., None] / 2.0 * 100.0, y.shape + (n,)).copy()
    cf[..., -1] += 100.0
    v = 1.0 / (1.0 + i)
    price = np.sum(cf * v ** k, axis=-1)
    return np.sum(k * cf * v ** (k + 1), axis=-1) / price / 2.0


def main(p7: str, p10: str) -> None:
    y7, y10 = load(p7), load(p10)
    both = pd.concat([y7.rename("y7"), y10.rename("y10")], axis=1, sort=True).dropna()
    print("series: DGS7 first %s, DGS10 first %s, last common %s" % (
        y7.index[0].date(), y10.index[0].date(), both.index[-1].date()))
    for name, (a, b) in WINDOWS.items():
        w = both.loc[a:b]
        y85 = (w.y7 + w.y10) / 2.0 / 100.0
        d = par_mod_duration(y85.values)
        slope_py = ((w.y10 - w.y7) / 3.0 / 100.0).values   # per year of maturity
        roll = (d * slope_py).mean()
        years = (w.index[-1] - w.index[0]).days / 365.0
        dy_py = (y85.iloc[-1] - y85.iloc[0]) / years
        print("\n%s  (%d obs, %.1f years)" % (name, len(w), years))
        print("  mean yields: 7y %.3f%%  10y %.3f%%  8.5y %.3f%%" % (
            w.y7.mean(), w.y10.mean(), y85.mean() * 100))
        print("  10y-7y spread: mean %.1f bp, min %.0f, max %.0f, share negative %.3f" % (
            (w.y10 - w.y7).mean() * 100, (w.y10 - w.y7).min() * 100,
            (w.y10 - w.y7).max() * 100, ((w.y10 - w.y7) < 0).mean()))
        print("  8.5y par bond: mean D_mod %.2f years" % d.mean())
        print("  roll-down estimate (D_mod x spread/3, daily, averaged): %.3f%% p.a." % (roll * 100))
        print("  8.5y yield change: %.2f%% -> %.2f%%, i.e. %+.1f bp per year" % (
            y85.iloc[0] * 100, y85.iloc[-1] * 100, dy_py * 1e4))
        print("  duration-mismatch term for a 0.40-year shorter instrument: %+.3f%% p.a." % (
            0.40 * dy_py * 100))
        if name.startswith("W1"):
            for yr in ("2016", "2017", "2018"):
                ww = w.loc[yr]
                yy = ((ww.y7 + ww.y10) / 2.0 / 100.0).values
                r = (par_mod_duration(yy) * ((ww.y10 - ww.y7) / 3.0 / 100.0).values).mean()
                print("    %s: spread %.1f bp, roll-down %.3f%% p.a." % (
                    yr, (ww.y10 - ww.y7).mean() * 100, r * 100))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
