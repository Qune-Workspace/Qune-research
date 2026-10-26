"""Power first for volatility-managed and dynamic-momentum questions on the French US history.

Descriptive power calculation, written 2026-10-26 before any question is fixed. No return is read:
the inputs are month counts from the source papers' stated samples and the library's last month
(release 202608, Study 010's snapshot), plus two anchors already committed or reported.

The programme's rule since the second cold read (RESEARCH_AGENDA, 2026-10-26) is that the next study
runs on a sample its source paper did not use. This tool asks how many such months each candidate has
and what Sharpe of d the decision test could see over them with 80% power
(S_MDE = K * nw / sqrt(N / 12), K = 2.842, as tools/power_offduration.py).

Paper samples, as read on 2026-10-26 from the NBER working papers (text extracted from the PDFs):
- [MM17] Moreira and Muir, NBER WP 22208 (2016): "the sample is 1926-2015 for Mkt, SMB, HML, and Mom";
  for the market "an alpha of 4.9%, an Appraisal ratio of 0.33" (a footnote gives 0.34 for the same ratio).
  The window is stated in years; its regressions have N = 1,065 (Mkt, SMB, HML) and 1,060 (Mom) against
  1,074 / 1,068 calendar months, so at most about 9 months are unused, unstated where; 2016-01 as the first
  unused month is assumed from "1926-2015".
- [DM16] Daniel and Moskowitz, NBER WP 20439 (2014): "full sample period 1927:01 to 2013:03"; the paper
  cites Israel and Moskowitz (2013) for momentum "from 1927 to 1965 and from 1990 to 2012". DM16 builds its
  own CRSP winner-minus-loser deciles, not the library's Mom, so row V3a counts calendar months, not the
  same series; its dynamic-strategy regression starts 1927:07 (six months used as burn-in).

The anchor 0.33 is MM17's appraisal ratio: alpha over residual sd against the unmanaged market (beta 0.61).
It is not the Sharpe of d. d (managed minus unmanaged) also carries -0.39 of the market premium, so the
Sharpe of d is likely below 0.33 and this anchor flatters detectability. A second-session check found
this label wrong in the first draft (tools/power_mined_recompute.md).
"""

from __future__ import annotations

import math

K = 2.842
NW_LARGEST = 1.108  # largest Newey-West ratio observed in the programme (tools/power_offduration.txt)
POOL = 0.321  # pool of Studies 006-008, Sharpe of d (tools/power_offduration.txt), an anchor only
MM17_MKT_AR = 0.33  # reported appraisal ratio of the managed market, 1926-2015; NOT the Sharpe of d
LIB_LAST = "2026-08"


def months(first: str, last: str) -> int:
    y0, m0 = map(int, first.split("-"))
    y1, m1 = map(int, last.split("-"))
    return (y1 - y0) * 12 + (m1 - m0) + 1


def s_mde(n: float, nw: float) -> float:
    return K * nw / math.sqrt(n / 12)


ROWS = [
    # id, question, months not in the source paper's sample (first unused month, library's last month), paper(s)
    ("V1", "volatility-managed market (Mkt-RF)", "2016-01", "MM17 1926-2015"),
    ("V2", "volatility-managed SMB, HML", "2016-01", "MM17 1926-2015"),
    ("V3", "volatility-managed momentum (Mom)", "2016-01", "MM17 1926-2015; DM16 1927:01-2013:03"),
    ("V3a", "dynamic momentum, DM16's sample only", "2013-04", "DM16 1927:01-2013:03"),
]


def main() -> None:
    print("Power first on mined samples (descriptive power calculation; tools/power_mined.py)")
    print(f"K = {K} (t >= 2.0 at 80% power); nw 1.00 / largest observed {NW_LARGEST}; library last month {LIB_LAST}")
    print("no return read; months from the papers' stated samples only")
    print()
    print("Check first: 128 months reproduce Study 010's P2 row (0.870 / 0.964 in tools/power_study010.txt)")
    print(f"  months 2016-01..2026-08 = {months('2016-01', LIB_LAST)}; S_MDE = {s_mde(128, 1.0):.3f} / {s_mde(128, NW_LARGEST):.3f}")
    print()
    print("  id    question                                 unused months    N    S_MDE          x pool 0.321    x MM17 mkt AR 0.33 (not Sharpe d)  paper sample")
    for rid, q, first, paper in ROWS:
        n = months(first, LIB_LAST)
        a, b = s_mde(n, 1.0), s_mde(n, NW_LARGEST)
        print(f"  {rid:<5} {q:<40} {first}..{LIB_LAST}  {n:4d}  {a:.3f} / {b:.3f}  {a / POOL:.2f}x / {b / POOL:.2f}x   {a / MM17_MKT_AR:.2f}x / {b / MM17_MKT_AR:.2f}x                       {paper}")
    print()
    print("Months before the papers' samples: no usable window. The library's 3 factors start 1926-07 and Mom 1927-01")
    print("(1,202 and 1,196 months to 2026-08, tools/power_offduration.txt rows F3/F2); MM17 starts in 1926 and DM16")
    print("in 1927:01, leaving at most ~9 unused months, unstated where and needed as volatility burn-in anyway")
    print("(Study 010 had 432 months before its paper's sample).")
    print()
    print("Months needed to see the anchors (nw 1.00 / largest observed nw):")
    for s, label in ((POOL, "Sharpe(d) 0.321 (pool of 006-008)"),
                     (MM17_MKT_AR, "MM17 market appraisal ratio 0.33 (alpha/residual sd vs unmanaged, beta 0.61; not Sharpe of d)")):
        n1, n2 = 12 * (K / s) ** 2, 12 * (K * NW_LARGEST / s) ** 2
        print(f"  {label}: {n1:5.0f} / {n2:5.0f} months")


if __name__ == "__main__":
    main()
