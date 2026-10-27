"""Power first for a risk-property question on the ETF era: volatility-forecast accuracy.

Descriptive power calculation, written 2026-10-27 from 00:2xZ by the clock, before any question
is fixed. The 2026-10-26 06:2xZ addition to RESEARCH_AGENDA.md named the one thing that reopens
the ETF era: "a question whose expected effect is a risk property rather than a return edge, for
example volatility forecastability, judged in its own units with its own power statement". This
script makes that power statement for the forecasts the desk already uses.

Inputs: Study 004's committed post-hoc risk files only (research/004-xasset-trend-voltarget/risk/
forecasts_insample.csv and forecasts_oos.csv, written 2026-10-23 by risk/risk_report.py). Nothing
is fetched and no vendor file is read. Both windows were already read for this property by that
post-hoc report (no decision weight), so neither window is a clean sample for a test of it: the
only unread months are forward months, and the rows below say what a forward record could see.

Per signal date t the files hold four ex-ante annualised volatility forecasts of Study 004's T1
book (diagonal with the study's 63-day vols; full EWMA covariance, 42-day half-life; the same
shrunk toward constant correlation; equal-weighted 252-day sample covariance) and the realised
annualised volatility of the book's daily net index over the holding period that followed
(about 19-21 daily returns). Months with no position or too short a history are dropped.

Loss: QLIKE, L = r2/f2 - ln(r2/f2) - 1, with r the realised and f the forecast volatility.
QLIKE ranks forecasts consistently when the variance proxy r2 is noisy but conditionally unbiased
(Patton 2011, J. Econometrics 160(1):246-256, doi:10.1016/j.jeconom.2010.03.034); MSE on variance,
also robust in that sense, is shown beside it as a second loss. Here r2 is the squared sample
standard deviation of about 19 daily returns, annualised: approximately unbiased for the period's
variance. In the 2019-2026 file nine flat months (2018-12-31, and 2022-07 to 2023-03 except
2023-01-31) are dropped, so its 84 months are not contiguous; the 6-lag HAC treats them as if
they were. Loss differential d_t = L(other) - L(candidate), so d > 0 means the
candidate forecast was better. The test of a forward record would be a Diebold-Mariano test,
mean(d) / its Newey-West standard error, at t >= 2.0.

Power as in the other power tools, in units of the monthly Sharpe of d (mean / sd, one month):
S_MDE = K * nw / sqrt(N), K = 2.842 (t >= 2.0 at 80% power), with nw the Newey-West ratio
(HAC standard error over the iid one; qune_research.stats.newey_west_mean, 6 lags) observed in
each window. Months needed to see an observed monthly Sharpe s: (K * nw / s)^2.

Run from the repository root: ``python tools/power_riskforecast.py > tools/power_riskforecast.txt``
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from qune_research.stats import newey_west_mean  # noqa: E402

K = 2.842
RISK = ROOT / "research" / "004-xasset-trend-voltarget" / "risk"
FILES = {"in-sample 2004-2018": RISK / "forecasts_insample.csv", "2019-2026 (seen)": RISK / "forecasts_oos.csv"}
FORWARD = (60, 120)  # forward months: the programme's 60-month record, and a decade
# (id, candidate, other, question)
PAIRS = [
    ("R1", "vol_ewma", "vol_sample", "EWMA (42-day half-life) beats the 252-day sample covariance"),
    ("R2", "vol_shrunk", "vol_ewma", "Ledoit-Wolf shrinkage improves on plain EWMA"),
    ("R3", "vol_shrunk", "vol_diagonal", "full covariance beats the diagonal forecast the study used"),
]


def qlike(realised: pd.Series, forecast: pd.Series) -> pd.Series:
    q = realised ** 2 / forecast ** 2
    return q - np.log(q) - 1.0


def mse_var(realised: pd.Series, forecast: pd.Series) -> pd.Series:
    return (realised ** 2 - forecast ** 2) ** 2


def describe(d: pd.Series) -> dict[str, float]:
    n = len(d)
    sd = float(d.std(ddof=1))
    nw = newey_west_mean(d)
    iid_se = sd / math.sqrt(n)
    return {"n": n, "mean": float(d.mean()), "sd": sd, "s": float(d.mean()) / sd, "t_iid": float(d.mean()) / iid_se,
            "t_nw": nw["t"], "nw": nw["se"] / iid_se, "wins": int((d > 0).sum())}


def main() -> None:
    print("Power first for volatility-forecast accuracy on Study 004's T1 book (tools/power_riskforecast.py)")
    print(f"K = {K} (t >= 2.0 at 80% power); monthly Sharpe of the loss differential d; Newey-West 6 lags")
    print("inputs: research/004-xasset-trend-voltarget/risk/forecasts_{insample,oos}.csv (committed); nothing fetched")
    print("both windows were already read for this property (post-hoc risk report, 2026-10-23): seen, not clean")
    print()
    frames = {}
    for label, path in FILES.items():
        df = pd.read_csv(path)
        df = df.dropna(subset=["realised_period", "vol_diagonal", "vol_ewma", "vol_shrunk", "vol_sample"])
        frames[label] = df
        print(f"{label}: {len(df)} months with a position and all four forecasts "
              f"({df['signal_date'].iloc[0]} .. {df['signal_date'].iloc[-1]}); "
              f"realised vol median {df['realised_period'].median():.4f}")
    print()
    hdr = (f"  {'id':4} {'window':20} {'loss':6} {'n':>4} {'mean d':>10} {'sd d':>10} {'s/month':>8} "
           f"{'t iid':>6} {'t NW':>6} {'nw':>6} {'d>0':>8} {'months to see s':>16}")
    for pid, cand, other, question in PAIRS:
        print(f"{pid}: {question} (d = L({other}) - L({cand}); d > 0 favours {cand})")
        print(hdr)
        for label, df in frames.items():
            for lname, lf in (("QLIKE", qlike), ("MSEvar", mse_var)):
                d = lf(df["realised_period"], df[other]) - lf(df["realised_period"], df[cand])
                r = describe(d.reset_index(drop=True))
                need = f"{(K * r['nw'] / r['s']) ** 2:,.0f}" if r["s"] > 0 else "never (s <= 0)"
                print(f"  {pid:4} {label:20} {lname:6} {r['n']:>4} {r['mean']:>10.3e} {r['sd']:>10.3e} {r['s']:>8.3f} "
                      f"{r['t_iid']:>6.2f} {r['t_nw']:>6.2f} {r['nw']:>6.3f} {r['wins']:>4}/{r['n']:<3} {need:>16}")
        print()
    print("Forward record: detectable monthly Sharpe of d, S_MDE = K * nw / sqrt(N)")
    nws = []
    for _pid, cand, other, _ in PAIRS:
        for df in frames.values():
            d = qlike(df["realised_period"], df[other]) - qlike(df["realised_period"], df[cand])
            nws.append(describe(d.reset_index(drop=True))["nw"])
    lo, hi = 1.0, max(nws)
    print(f"  nw bracket 1.00 / largest observed here {hi:.3f} (QLIKE rows; not a bound)")
    for n in FORWARD:
        print(f"  N = {n:>3} months: S_MDE = {K * lo / math.sqrt(n):.3f} / {K * hi / math.sqrt(n):.3f}")
    print()
    print("Reading: compare each row's s/month with S_MDE. A forward record can see a comparison only if its")
    print("monthly Sharpe of d out of sample is at least S_MDE. The in-sample s is an anchor, not a target; the")
    print("2019-2026 s shows whether that size held in a later window. Both windows were seen by the author and")
    print("read for this property by the post-hoc risk report, so only forward months are a clean sample.")


if __name__ == "__main__":
    main()
