"""Post-hoc, descriptive breakdown of the window-2 validation by calendar year
(written after the single validation run; used for the halt note only).

Reads the same files the validation read and prints, for each year of window
2 and for window 1 as a whole: annualised tracking error, correlation, OLS
slope, and the annualised daily volatility of the ETF and of the synthetic
series.  Nothing here is a threshold and nothing here changes any result.
Run from the study folder: ``python posthoc_by_year.py``; output committed as
``results/validation/window2/posthoc_by_year.md``.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from src.alpaca_bars import load_bars
from src.config import VALIDATION_END, VALIDATION_START, WINDOW2_END, WINDOW2_START
from src.fred import load_series
from src.synthetic import synthetic_indices
from src.tiingo_bars import load_prices
from src.validate import interval_returns

OUT = Path("results/validation/window2/posthoc_by_year.md")
ANN = math.sqrt(252)


def row(label: str, g: pd.DataFrame) -> str:
    d = g["etf"] - g["syn"]
    return (f"| {label} | {len(g)} | {d.std(ddof=1) * ANN * 100:.2f}% | {g['etf'].corr(g['syn']):.3f} | "
            f"{np.polyfit(g['syn'], g['etf'], 1)[0]:.3f} | {g['etf'].std() * ANN * 100:.1f}% | "
            f"{g['syn'].std() * ANN * 100:.1f}% | {d.std(ddof=1) / g['etf'].std():.2f} |")


def main() -> None:
    fred = {n: load_series(n) for n in ("DGS10", "DTB3", "DGS7")}
    syn = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])["IEF"]
    close = load_prices("IEF")["adjClose"].astype(float).dropna().loc[WINDOW2_START:WINDOW2_END]
    w2 = pd.concat([(close / close.shift(1) - 1).dropna().rename("etf"),
                    interval_returns(syn, close.index).rename("syn")], axis=1).dropna()
    bars = load_bars("IEF").loc[VALIDATION_START:VALIDATION_END]
    w1 = pd.concat([(bars["close"] / bars["close"].shift(1) - 1).dropna().rename("etf"),
                    interval_returns(syn, bars.index).rename("syn")], axis=1).dropna()
    lines = ["# Window 2 by calendar year (post hoc, descriptive; written after the single validation run)", "",
             "IEF minus synthetic, daily, on the ETF's trading days. Not pre-registered; no decision weight; "
             "nothing here changes the halt.", "",
             "| Period | Days | Tracking error (A3) | Correlation (A1) | Slope (A2) | IEF volatility | Synthetic volatility | TE / IEF vol |",
             "|---|---|---|---|---|---|---|---|"]
    for year, g in w2.groupby(w2.index.year):
        lines.append(row(str(year), g))
    lines.append(row("Window 2, all", w2))
    lines.append(row("Window 2 without 2008-2009", w2[(w2.index.year < 2008) | (w2.index.year > 2009)]))
    lines.append(row("Window 1 (2016-2018), for comparison", w1))
    d = (w2["etf"] - w2["syn"]).abs()
    lines += ["", f"Days with an absolute daily gap over 50 bp: {int((d > 0.005).sum())}; over 100 bp: {int((d > 0.01).sum())}. "
              "Largest: " + ", ".join(f"{t.date()} ({v * 1e4:.0f} bp)" for t, v in d.sort_values(ascending=False).head(6).items()) + "."]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
