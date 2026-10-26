"""Power first for the next question outside duration timing (RESEARCH_AGENDA, dated
addition 2026-10-26 05:2xZ: "the next question leaves duration timing. It is chosen by the
same power-first rule, with the Sharpe-unit statement beside the return-unit one, and
recorded here before any question note").

Question this answers, before any question is fixed and before any return of a candidate
sample is read: how large an edge, in Sharpe units of the decision difference d (rule minus
its benchmark), can each sample the desk can read without purchase or sign-up detect, and
how does that compare with the edges this programme has actually observed?

Reads committed files only (Studies 003, 004 in-sample and 006-008 history monthly files);
fetches nothing. Candidate sample lengths come from metadata only:
  ETF era: Study 004's in-sample window, 2004-01 to 2018-12 (180 holding periods, its
    committed metrics file), and the same plus the held-back window to 2026-09 (273), which
    is spent or seen for every ETF the programme has used (METHODS section 2.5).
  Kenneth French Data Library (free, no sign-up; detail pages read 2026-10-26 06:1xZ, no
    return read): US Fama/French 3 factors July 1926 - August 2026; momentum factor January
    1927 - August 2026; Developed 3 factors July 1990 - August 2026.

Method. S_MDE(N) = K x nw / sqrt(N / 12): the Sharpe ratio of d a year that a NW t >= 2.0
test sees with 80% power over N months (K = 2.842, Study 007 section 11.4; nw = Newey-West
over iid standard error, Bartlett 6 lags). nw is not known for a question not yet fixed, so
it is shown at 1.00 and at the largest ratio observed among the committed d series below
(the largest observed, not a bound: a slower or overlapping signal could have a larger one). The
return-unit statement beside it: the 2%-a-year bar holds only if sd(d) <= 2% / S_MDE, and
the return MDE at an assumed sd(d) is S_MDE x sd(d) (assumed values, labelled so).

Run from the repository root: ``python tools/power_offduration.py > tools/power_offduration.txt``
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qune_research.stats import newey_west_mean  # noqa: E402

LAGS = 6
K = 2.842
# Committed d series: (file, rule column, benchmark column, published NW t, label).
SERIES = {
    "003": ("research/003-bond-tsmom-ief/results/insample/monthly_base.csv", "T1", "B3", 0.37,
            "IEF 12-month trend vs B3, 2003-2018"),
    "004": ("research/004-xasset-trend-voltarget/results/insample/monthly_10assets_base.csv", "T1", "B4", 0.65,
            "ten-ETF trend vs exposure-matched B4, 2004-2018"),
    "006": ("research/006-term-spread-switch-long-history/results/history/monthly_base.csv", "T1", "B3", 2.06,
            "term-spread switch vs B3, 1969-2018"),
    "007": ("research/007-bond-carry-tilt-long-history/results/history/monthly_base.csv", "T1", "B3_T1", 2.10,
            "carry tilt vs B3, 1974-2018"),
    "008": ("research/008-bond-value-tilt-long-history/results/history/monthly_base.csv", "T1", "B3_T1", 1.38,
            "value tilt vs B3, 1974-2018"),
}
POOL = ("006", "007", "008")
PUB_POOL_SHARPE = 0.321  # tools/power_unmined.txt
SAMPLES = {
    "E1 ETF era in-sample (Study 004 window)": ("2004-01", "2018-12"),
    "E2 ETF era incl. the spent/seen 2019-2026 window": ("2004-01", "2026-09"),
    "F1 French Developed 3 factors": ("1990-07", "2026-08"),
    "F2 French US momentum factor": ("1927-01", "2026-08"),
    "F3 French US 3 factors": ("1926-07", "2026-08"),
}
ASSUMED_SD = (0.05, 0.10, 0.15)


def months(first: str, last: str) -> int:
    return (pd.Period(last, "M") - pd.Period(first, "M")).n + 1


def load(key: str) -> pd.Series:
    path, rule, bench, _, _ = SERIES[key]
    df = pd.read_csv(ROOT / path, dtype=str)
    d = df[rule].astype(float) - df[bench].astype(float)
    month = df["execution_date"] if "execution_date" in df else df[df.columns[0]]
    d.index = pd.Index(month.str[:7], name="month")
    return d.dropna()


def s_mde(n: float, nw: float) -> float:
    return K * nw / math.sqrt(n / 12)


def main() -> None:
    print("Power first outside duration timing (descriptive power calculation; tools/power_offduration.py)")
    print(f"Newey-West Bartlett {LAGS} lags; K = {K} (t >= 2.0 at 80% power)")
    print()
    print("1. Edges observed in this programme, in Sharpe units of d (anchors reproduced first)")
    print("  study  n    NW t   Sharpe(d)  sd(d) a yr  nw ratio  series")
    nws = {}
    for key, (_, _, _, pub_t, label) in SERIES.items():
        d = load(key)
        res = newey_west_mean(d, lags=LAGS)
        if round(res["t"], 2) != pub_t:
            raise SystemExit(f"{key}: t {res['t']:.3f} does not reproduce the published {pub_t}")
        sd_m = float(d.std(ddof=1))
        nws[key] = res["se"] / (sd_m / math.sqrt(res["n"]))
        sharpe = res["mean"] / sd_m * math.sqrt(12)
        print(
            f"  {key}    {res['n']:3d}  {res['t']:5.2f}   {sharpe:6.3f}     {sd_m * math.sqrt(12):6.2%}     "
            f"{nws[key]:5.3f}    {label}"
        )
    common = pd.concat({k: load(k) for k in POOL}, axis=1, join="inner").mean(axis=1)
    res = newey_west_mean(common, lags=LAGS)
    sd_m = float(common.std(ddof=1))
    pool_sharpe = res["mean"] / sd_m * math.sqrt(12)
    if round(pool_sharpe, 3) != PUB_POOL_SHARPE:
        raise SystemExit(f"pool Sharpe {pool_sharpe:.4f} does not reproduce tools/power_unmined.txt {PUB_POOL_SHARPE}")
    nws["pool"] = res["se"] / (sd_m / math.sqrt(res["n"]))
    print(f"  pool   {res['n']:3d}  {res['t']:5.2f}   {pool_sharpe:6.3f}     {sd_m * math.sqrt(12):6.2%}     "
          f"{nws['pool']:5.3f}    equal-weight 006-008 (as tools/power_unmined.txt)")
    nw_hi = max(nws.values())
    print(f"  largest nw ratio observed above: {nw_hi:.3f} (shown below beside nw 1.00; not a bound)")
    print("  the pool's 0.321 is an in-sample point estimate (standard error about 0.15 over 44.5 years): an anchor")
    print("  for the size of edge this programme has measured, not a target edge")
    print()
    print("2. Detectable Sharpe of d by sample (months from metadata only; no return read)")
    print("  each pair is nw 1.00 / largest observed nw; return MDE at an assumed sd(d), nw 1.00")
    print("  sample                                              N     S_MDE           x pool 0.321    "
          "2% bar needs sd(d) <=  return MDE at sd(d) 5% / 10% / 15%")
    for label, (first, last) in SAMPLES.items():
        n = months(first, last)
        lo, hi = s_mde(n, 1.0), s_mde(n, nw_hi)
        rets = " / ".join(f"{lo * s:5.2%}" for s in ASSUMED_SD)
        print(f"  {label:50s} {n:5d}   {lo:5.3f} / {hi:5.3f}   {lo / pool_sharpe:4.2f}x / {hi / pool_sharpe:4.2f}x   "
              f"{0.02 / lo:5.2%} / {0.02 / hi:5.2%}       {rets}")
    print()
    print("3. Months needed to see a given Sharpe of d (nw 1.00 / largest observed nw)")
    for s in (0.20, 0.321, 0.50, 0.75):
        print(f"  Sharpe(d) {s:5.3f}: {12 * (K / s) ** 2:6.0f} / {12 * (K * nw_hi / s) ** 2:6.0f} months")


if __name__ == "__main__":
    main()
