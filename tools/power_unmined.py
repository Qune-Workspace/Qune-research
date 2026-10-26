"""Power first for the next sample (RESEARCH_AGENDA, dated addition 2026-10-26: the next
question must use a sample the author has not mined; which one is decided by power first).

Question this answers, before any series of a candidate sample is read: could a test of
the three already-fixed duration-timing rules (Studies 006, 007, 008) on an unmined
sample detect the edges their histories showed? The edges are judged in Sharpe units of
d = T1 - B3, because the agenda's 2%-a-year bar is in return units and a calm sample's
low leg volatility would pass that bar without any extra power (power_next.txt, step 2).

Reads committed files only (Studies 006-008 ``results/history/monthly_base.csv`` and
``tools/fidelity_stocker.txt``); fetches nothing. The candidate samples' lengths come from
series metadata (first observation dates on the FRED series pages, read 2026-10-26
05:1xZ; no observation of any series was read):
  US 1953-1969 (unmined: every study so far starts in 1969 or later): GS10, GS5, GS3
    monthly averages from 1953-04; TB3MS from 1934-01; DTB3 daily from 1954-01-04; DGS10,
    DGS5 daily from 1962-01-02; DGS7 daily from 1969-07-01. Leg: Stocker (2025) price-based
    5-10-year sector returns, 1942-01 to 1982-10 (already on disk for the fidelity check;
    no 1942-1968 return has been summarised, printed or used).
  Other countries (OECD MEI on FRED, monthly averages; long = IRLTLT01xxM156N, short =
    IR3TIB01xxM156N): first month with both series GBR 1960-01, DEU 1960-01, CAN 1956-01,
    FRA 1970-01, AUS 1969-07; NLD 1982-01, ITA 1991-03, JPN 2002-04, CHE 1999-07. Legs
    would be synthetic, built from monthly-average yields.

Method. For each study, the NW t of d over its history (reproduced first: 2.06, 2.10,
1.38). The detectable Sharpe of d over N months is S_MDE(N) = K x nw / sqrt(N / 12), with
K = 2.842 (t >= 2.0 at 80% power, Study 007 section 11.4) and nw = the history's Newey-West
standard error over its iid standard error (Bartlett, 6 lags). The months needed to see the
history's own Sharpe at that power are n x (K / t)^2. A pool of C samples whose d are
correlated rho on average is counted as N_eff = sum(N) / (1 + (C - 1) rho); rho across
countries is not observed here and is shown at 0.25, 0.50 and 0.75 (assumed). The
synthetic-leg bias measured against Stocker in 1969/1974-1982 is restated in Sharpe units
of d by dividing by sd(d) a year over the same months (and, for scale, over the whole history).

Run from the repository root: ``python tools/power_unmined.py > tools/power_unmined.txt``
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qune_research.stats import newey_west_mean  # noqa: E402

STUDIES = {
    "006": ("research/006-term-spread-switch-long-history/results/history/monthly_base.csv", "B3", 2.06),
    "007": ("research/007-bond-carry-tilt-long-history/results/history/monthly_base.csv", "B3_T1", 2.10),
    "008": ("research/008-bond-value-tilt-long-history/results/history/monthly_base.csv", "B3_T1", 1.38),
}
LAGS = 6
K = 2.842
RANK_MIN = 60  # 007/008 expanding rank, minimum 60 months before the first weight
LAST_SIGNAL = "2026-09"  # last complete month for the other-country samples
US_LAST_SIGNAL = "1969-06"  # the month before Study 006's first signal month (1969-07)
# First signal month for each form of the US 1953-1969 sample (metadata above).
US_FORMS = {
    "switch, exact daily inputs (DGS10, DTB3 from 1962-01)": "1962-01",
    "switch, monthly-average inputs (GS10, TB3MS from 1953-04)": "1953-04",
    "tilts, monthly-average inputs (GS10/GS5/GS3, TB3MS from 1953-04), after the 60-month rank": None,
}
COUNTRIES = {"GBR": "1960-01", "DEU": "1960-01", "CAN": "1956-01", "FRA": "1970-01", "AUS": "1969-07"}
RHOS = (0.25, 0.50, 0.75)
# Signed G1-style bias of the synthetic leg against Stocker's 5-10-year AllTax sector
# (tools/fidelity_stocker.txt, primary sector, pre-specified rows), % a year, and the
# execution months it was measured over.
STOCKER_BIAS = {"006": ("0.626%", "1969-08"), "007": ("0.570%", "1974-07"), "008": ("0.766%", "1974-07")}
STOCKER_LAST = "1982-10"


def months(first: str, last: str) -> int:
    a, b = pd.Period(first, "M"), pd.Period(last, "M")
    return (b - a).n + 1


def load(study: str) -> pd.Series:
    path, bench, _ = STUDIES[study]
    df = pd.read_csv(ROOT / path, dtype={"month": str})
    diff = (df["T1"] - df[bench]).astype(float)
    diff.index = pd.Index(df["execution_date"].str[:7], name="execution_month")
    return diff.dropna()


def s_mde(n: float, nw: float) -> float:
    return K * nw / math.sqrt(n / 12)


def main() -> None:
    fidelity = (ROOT / "tools" / "fidelity_stocker.txt").read_text(encoding="utf-8")
    print("Power first for an unmined sample (descriptive power calculation; tools/power_unmined.py)")
    print(f"d = T1 - B3 by execution month; Newey-West Bartlett {LAGS} lags; K = {K} (t >= 2.0 at 80% power)")
    print()
    print("Anchors reproduced before anything is reported, and the histories in Sharpe units of d")
    print("  study  n    window             NW t   mean(d) a yr  sd(d) a yr  Sharpe(d)  nw ratio  months to see it")
    hist = {}
    for s in STUDIES:
        d = load(s)
        res = newey_west_mean(d, lags=LAGS)
        if round(res["t"], 2) != STUDIES[s][2]:
            raise SystemExit(f"{s}: t {res['t']:.3f} does not reproduce the published {STUDIES[s][2]}")
        sd_m = float(d.std(ddof=1))
        nw = res["se"] / (sd_m / math.sqrt(res["n"]))
        sharpe = res["mean"] / sd_m * math.sqrt(12)
        need = res["n"] * (K / res["t"]) ** 2
        hist[s] = {"n": res["n"], "t": res["t"], "sd": sd_m * math.sqrt(12), "sharpe": sharpe, "nw": nw}
        print(
            f"  {s}    {res['n']:3d}  {d.index[0]} to {d.index[-1]}  {res['t']:5.2f}  {res['mean'] * 12:+8.2%}     "
            f"{sd_m * math.sqrt(12):7.2%}     {sharpe:6.3f}     {nw:6.3f}    {need:6.0f}"
        )
    common = pd.concat({s: load(s) for s in STUDIES}, axis=1, join="inner")
    avg = common.mean(axis=1)
    res = newey_west_mean(avg, lags=LAGS)
    sd_m = float(avg.std(ddof=1))
    nw_pool = res["se"] / (sd_m / math.sqrt(res["n"]))
    sharpe_pool = res["mean"] / sd_m * math.sqrt(12)
    need_pool = res["n"] * (K / res["t"]) ** 2
    print(
        f"  pool   {res['n']:3d}  {common.index[0]} to {common.index[-1]}  {res['t']:5.2f}  {res['mean'] * 12:+8.2%}     "
        f"{sd_m * math.sqrt(12):7.2%}     {sharpe_pool:6.3f}     {nw_pool:6.3f}    {need_pool:6.0f}"
    )
    print("  (pool = equal-weight average of the three d on their common months; the three d correlate:")
    print(
        "   "
        + "; ".join(
            f"{a}-{b} {common[a].corr(common[b]):.3f}" for a, b in (("006", "007"), ("006", "008"), ("007", "008"))
        )
        + ")"
    )
    print()
    print("Candidate U: US 1953-1969 on Stocker's price-based 5-10-year sector (signal months to 1969-06)")
    print(
        "  form                                                                         N    Sharpe MDE  "
        "x pool's history Sharpe"
    )
    for label, first in US_FORMS.items():
        n = months(first, US_LAST_SIGNAL) if first else months("1953-04", US_LAST_SIGNAL) - RANK_MIN + 1
        mde = s_mde(n, nw_pool)
        print(f"  {label:76s} {n:3d}    {mde:6.3f}      {mde / sharpe_pool:4.1f}x")
    print()
    print("Candidate C: other countries, synthetic legs from monthly-average yields (signal months to 2026-09)")
    n_c = {c: months(first, LAST_SIGNAL) - RANK_MIN + 1 for c, first in COUNTRIES.items()}
    print(
        "  months per country after the 60-month rank (tilt forms): "
        + ", ".join(f"{c} {n}" for c, n in n_c.items())
        + f"; total {sum(n_c.values())}"
    )
    print("  rho (assumed)  N_eff   Sharpe MDE   x pool's history Sharpe")
    for rho in RHOS:
        n_eff = sum(n_c.values()) / (1 + (len(n_c) - 1) * rho)
        mde = s_mde(n_eff, nw_pool)
        print(f"  {rho:4.2f}           {n_eff:5.0f}    {mde:6.3f}       {mde / sharpe_pool:4.1f}x")
    print()
    print("Synthetic-leg bias found against Stocker (1969/1974-1982), in Sharpe units of d")
    for s, (bias, first) in STOCKER_BIAS.items():
        if f"signed mean(e)x12 +{bias}" not in fidelity:
            raise SystemExit(f"{s}: bias {bias} not found in tools/fidelity_stocker.txt")
        b = float(bias.rstrip("%")) / 100
        d = load(s)
        sd_w = float(d[(d.index >= first) & (d.index <= STOCKER_LAST)].std(ddof=1)) * math.sqrt(12)
        print(
            f"  {s}: +{bias} a year / sd(d) {sd_w:.2%} over {first} to {STOCKER_LAST} = {b / sd_w:+.3f} Sharpe "
            f"(over the whole history, sd {hist[s]['sd']:.2%}: {b / hist[s]['sd']:+.3f}); "
            f"the history's Sharpe(d) {hist[s]['sharpe']:.3f}"
        )


if __name__ == "__main__":
    main()
