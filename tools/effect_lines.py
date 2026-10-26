"""Post-hoc effect lines for Studies 006-008 (second cold read, 2026-10-26, points 1 and 4).

Descriptive only, no decision weight: reads the committed history files
(``results/history/monthly_base.csv``), fetches nothing, re-runs nothing.
For each study's primary rule T1: the mean monthly difference T1 - B3 (its
exposure-matched benchmark) a year, the Newey-West t (Bartlett, 6 lags, as
each pre-registration's C2), a normal 95% interval from the same standard
error, and the share of the summed difference earned in execution months up
to 1985-12. Then the three studies' differences side by side on their common
months: correlations and the equal-weight average, as one estimate for the
one sample the three studies share. The window is spent for duration timing
(RESEARCH_AGENDA.md, 2026-10-26): none of this is a test.

Before printing, it checks that the published t-statistics are reproduced
(006 2.06, 007 2.10, 008 1.38) and stops otherwise.

Run from the repository root: ``python tools/effect_lines.py > tools/effect_lines.txt``
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qune_research.stats import newey_west_mean  # noqa: E402

STUDIES = {
    "006": ("research/006-term-spread-switch-long-history", "B3", 2.06),
    "007": ("research/007-bond-carry-tilt-long-history", "B3_T1", 2.10),
    "008": ("research/008-bond-value-tilt-long-history", "B3_T1", 1.38),
}
EARLY_END = "1985-12"
LAGS = 6


def load(study: str) -> pd.Series:
    folder, bench, _ = STUDIES[study]
    df = pd.read_csv(ROOT / folder / "results/history/monthly_base.csv", dtype={"month": str})
    diff = (df["T1"] - df[bench]).astype(float)
    diff.index = pd.Index(df["execution_date"].str[:7], name="execution_month")
    return diff.dropna()


def main() -> None:
    diffs = {s: load(s) for s in STUDIES}
    print("Post-hoc effect lines, Studies 006-008 (descriptive, no decision weight; tools/effect_lines.py)")
    print(f"T1 - B3 by execution month; Newey-West Bartlett {LAGS} lags; 95% interval = mean +/- 1.96 se; x12 a year")
    print()
    print("study  months  first    last     edge/yr   95% interval        NW t   share to 1985-12  months to 1985-12")
    for s, d in diffs.items():
        nw = newey_west_mean(d, lags=LAGS)
        published = STUDIES[s][2]
        if round(nw["t"], 2) != published:
            raise SystemExit(f"{s}: t {nw['t']:.3f} does not reproduce the published {published}")
        early = d[d.index <= EARLY_END]
        share = early.sum() / d.sum()
        lo, hi = (nw["mean"] - 1.96 * nw["se"]) * 12, (nw["mean"] + 1.96 * nw["se"]) * 12
        print(f"{s}    {nw['n']:5d}   {d.index[0]}  {d.index[-1]}  {nw['mean'] * 12:+7.2%}   "
              f"[{lo:+.2%}, {hi:+.2%}]   {nw['t']:5.2f}   {share:7.0%}           {len(early)}")
    print()
    common = pd.concat(diffs, axis=1, join="inner")
    print(f"Common execution months: {common.index[0]} to {common.index[-1]}, n = {len(common)}")
    print("Correlation of the monthly differences:")
    print(common.corr().round(3).to_string())
    avg = common.mean(axis=1)
    nw = newey_west_mean(avg, lags=LAGS)
    early = avg[avg.index <= EARLY_END]
    lo, hi = (nw["mean"] - 1.96 * nw["se"]) * 12, (nw["mean"] + 1.96 * nw["se"]) * 12
    print()
    print("Equal-weight average of the three differences (one estimate for one sample):")
    print(f"  edge {nw['mean'] * 12:+.2%} a year, 95% interval [{lo:+.2%}, {hi:+.2%}], NW t {nw['t']:.2f}, "
          f"share to 1985-12 {early.sum() / avg.sum():.0%}")
    late = avg[avg.index > EARLY_END]
    nw_late = newey_west_mean(late, lags=LAGS)
    print(f"  from 1986-01 only: edge {nw_late['mean'] * 12:+.2%} a year, NW t {nw_late['t']:.2f}, n = {nw_late['n']}")


if __name__ == "__main__":
    main()
