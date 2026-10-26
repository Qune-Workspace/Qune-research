"""Power of a pooled forward record (second cold read, 2026-10-26, point 2).

Question this answers, before any forward record exists (first signal date
2026-10-30): could one test pooled across the forward records see the edges
the histories showed (+0.56% to +0.90% a year over B3; average +0.70%), or
the agenda's 2% a year bar, within 60 holding periods?

Reads committed files only (Study 003 ``results/insample/monthly_base.csv``,
Studies 006-008 ``results/history/monthly_base.csv``); fetches nothing and
computes no forward figure. Pools are the forward records whose scored series
is the same object, d_t = T1 - B3 on IEF and BIL: 003, 006, 007, 008. Study
004 (a twelve-ETF book against its own benchmark) and Study 005 (a
regime-conditioned difference scored after 24 positive-regime months) are a
different object and are not pooled.

For each pool: the equal-weight average of the members' monthly d on their
common execution months, its Newey-West standard error (Bartlett, 6 lags, as
every C2), scaled to 60 months by sqrt(n/60); MDE = K x se x 12 with
K = 2.842 (t >= 2.0 at 80% power, Study 007 section 11.4). Two dispersion
windows: the long history (1974-07 to 2018-12, 006-008 only) and the ETF era
overlap (from 2003-08, all four), which is nearer the forward conditions.

Before printing, it checks that the published t-statistics are reproduced
(003 0.37, 006 2.06, 007 2.10, 008 1.38) and stops otherwise.

Run from the repository root: ``python tools/power_pooled.py > tools/power_pooled.txt``
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qune_research.stats import newey_west_mean  # noqa: E402

STUDIES = {
    "003": ("research/003-bond-tsmom-ief/results/insample/monthly_base.csv", "B3", 0.37),
    "006": ("research/006-term-spread-switch-long-history/results/history/monthly_base.csv", "B3", 2.06),
    "007": ("research/007-bond-carry-tilt-long-history/results/history/monthly_base.csv", "B3_T1", 2.10),
    "008": ("research/008-bond-value-tilt-long-history/results/history/monthly_base.csv", "B3_T1", 1.38),
}
POOLS = {
    "006+007+008": ["006", "007", "008"],
    "007+008": ["007", "008"],
    "003+006+007+008": ["003", "006", "007", "008"],
    "003+007+008": ["003", "007", "008"],
}
LAGS = 6
K = 2.842
FORWARD_N = 60
ETF_START = "2003-08"
HISTORY_EDGE = 0.0070  # equal-weight average of 006-008 over B3, tools/effect_lines.txt


def load(study: str) -> pd.Series:
    path, bench, _ = STUDIES[study]
    df = pd.read_csv(ROOT / path, dtype={"month": str})
    diff = (df["T1"] - df[bench]).astype(float)
    diff.index = pd.Index(df["execution_date"].str[:7], name="execution_month")
    return diff.dropna()


def months_for(se_annual: float, n: int, edge: float) -> int:
    return round(n * (K * se_annual / edge) ** 2)


def main() -> None:
    diffs = {s: load(s) for s in STUDIES}
    print("Power of a pooled forward record (descriptive power calculation; tools/power_pooled.py)")
    print(f"d = T1 - B3 by execution month; Newey-West Bartlett {LAGS} lags; MDE = {K} x se x 12; "
          f"forward horizon {FORWARD_N} months")
    print()
    print("Anchors reproduced before anything is reported")
    for s, d in diffs.items():
        nw = newey_west_mean(d, lags=LAGS)
        if round(nw["t"], 2) != STUDIES[s][2]:
            raise SystemExit(f"{s}: t {nw['t']:.3f} does not reproduce the published {STUDIES[s][2]}")
        print(f"  {s}: {nw['n']} months {d.index[0]} to {d.index[-1]}, NW t {nw['t']:.2f} (published {STUDIES[s][2]})")
    print()
    print("Single records, 60-month MDE at each window's dispersion")
    print("  study  window              n    MDE 60 m   months to 2%   months to 1%")
    for s, d in diffs.items():
        for label, sub in (("own window", d), ("ETF era (2003-08+)", d[d.index >= ETF_START])):
            nw = newey_west_mean(sub, lags=LAGS)
            se = nw["se"] * 12
            mde = K * se * (nw["n"] / FORWARD_N) ** 0.5
            print(f"  {s}    {label:18s}  {nw['n']:3d}   {mde:6.2%}     {months_for(se, nw['n'], 0.02):6d}        "
                  f"{months_for(se, nw['n'], 0.01):6d}")
    print()
    print("Pools (equal-weight average of the members' d on their common months)")
    print("  pool              window              n    MDE 60 m   months to 2%   months to 1%   months to +0.70%")
    for name, members in POOLS.items():
        common = pd.concat({s: diffs[s] for s in members}, axis=1, join="inner")
        windows = [("ETF era (2003-08+)", common[common.index >= ETF_START])]
        if "003" not in members:
            windows.insert(0, (f"{common.index[0]} to {common.index[-1]}", common))
        for label, sub in windows:
            avg = sub.mean(axis=1)
            nw = newey_west_mean(avg, lags=LAGS)
            se = nw["se"] * 12
            mde = K * se * (nw["n"] / FORWARD_N) ** 0.5
            print(f"  {name:16s}  {label:18s}  {nw['n']:3d}   {mde:6.2%}     {months_for(se, nw['n'], 0.02):6d}        "
                  f"{months_for(se, nw['n'], 0.01):6d}         {months_for(se, nw['n'], HISTORY_EDGE):6d}")
    print()
    etf = pd.concat(diffs, axis=1, join="inner")
    etf = etf[etf.index >= ETF_START]
    print(f"Correlation of d, ETF era common months ({etf.index[0]} to {etf.index[-1]}, n = {len(etf)}):")
    print(etf.corr().round(3).to_string())


if __name__ == "__main__":
    main()
