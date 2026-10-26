"""Power first for industry momentum [MG99] on the French US industry portfolios.

Descriptive power calculation, written 2026-10-26 from 14:2xZ before any question is fixed.
No return is read: the inputs are month counts from the paper's stated sample and the
library's detail pages, plus the anchors already committed in tools/power_mined.txt.

Paper sample, read on 2026-10-26 from the published article's text layer (JSTOR scan of
J. Finance 54(4):1249-1290, a course copy archived by the Internet Archive on 2015-10-27,
web.archive.org/web/20151027131302/http://www-stat.wharton.upenn.edu/~steele/Courses/956/
Resource/Momentum/MoskowitzGrinblatt99.pdf, SHA-256
df0570fc30692b3ecc9a37ccec82860dc3b2adc07c4a55463b658b801e8721d9; text extracted with
the standard library only, nothing redistributed):
- "Using the CRSP and COMPUSTAT data files, 20 value-weighted industry portfolios are formed
  for every month from July 1963 to July 1995. Two-digit Standard Industrial Classification
  (SIC) codes are used to form industry portfolios".
- "The raw return profits correspond to the July 1963 to July 1995 time period". (Table II's
  "July 1963 through July 1995 (i.e., T = 383)" is Panel A, individual equities, not the
  industry strategy; first draft attributed it to the industry window, corrected after the
  separate-session check, tools/power_industry_recompute.md.)
- The headline strategy: industries "sorted on their past six-month raw returns", "long the
  three highest past return industries and short the three lowest, holding the positions
  constant for six months, and recomputing the strategy monthly": 0.43 percent a month.
  Its t-statistic sits in Tables II/III, JBIG2 images with no text layer here: UNREAD, so no
  Sharpe anchor from the paper is used. (The text's equal-weighted variant, 0.0081 a month,
  t 7.71, is a different portfolio and is not used either.)
The publisher's copy (doi:10.1111/0022-1082.00146) returned HTTP 403 to a plain fetch and
sits behind a browser check; it was not bypassed.

Library (Kenneth French Data Library, detail pages for the 10, 12, 17, 30, 38, 48 and 49
industry portfolios read 2026-10-26 14:1xZ, no return read): monthly returns July 1926 -
August 2026 for every one of them; industries by four-digit SIC at the end of June (Compustat
codes for fiscal year t-1, else CRSP codes for June of t). That is not MG99's 20 two-digit
CRSP groups, so any test on the library is a variant, not a replication. Whether some
industries in the finer sets have missing months early is a data-step question.

Method as tools/power_mined.py: S_MDE = K * nw / sqrt(N / 12), K = 2.842 (NW t >= 2.0 at
80% power), nw at 1.00 and at the largest ratio observed in the programme (1.108). A six-month
holding period built from six overlapping cohorts can carry a larger nw than any series seen
so far, so 1.108 is the largest observed, not a bound. A six-month formation period uses the
first six library months and six overlapping six-month cohorts are all held only from
1927-06, so return months are counted from 1927-06 (1927-01..05 would carry one to five
cohorts; the first draft counted them, corrected after the separate-session check).
Formation months may come from the paper's window (I2's first six return months are ranked
on the paper's months), but only return months outside it count as unused.

Run from the repository root: ``python tools/power_industry.py > tools/power_industry.txt``
"""

from __future__ import annotations

import math

K = 2.842
NW_LARGEST = 1.108  # largest Newey-West ratio observed in the programme (tools/power_offduration.txt)
POOL = 0.321  # pool of Studies 006-008, Sharpe of d (tools/power_offduration.txt), an anchor only
LIB_FIRST = "1926-07"
LIB_LAST = "2026-08"
FIRST_FULL = "1927-06"  # first month all six overlapping cohorts are held
PAPER_FIRST, PAPER_LAST = "1963-07", "1995-07"


def months(first: str, last: str) -> int:
    y0, m0 = map(int, first.split("-"))
    y1, m1 = map(int, last.split("-"))
    return (y1 - y0) * 12 + (m1 - m0) + 1


def s_mde(n: float, nw: float) -> float:
    return K * nw / math.sqrt(n / 12)


def main() -> None:
    print("Power first for industry momentum [MG99] on the library's industry portfolios (tools/power_industry.py)")
    print(f"K = {K} (t >= 2.0 at 80% power); nw 1.00 / largest observed {NW_LARGEST}; library {LIB_FIRST}..{LIB_LAST}")
    print("no return read; months from the paper's stated sample and the library's detail pages only")
    print()
    print("Check first: 128 months reproduce tools/power_mined.txt (0.870 / 0.964)")
    print(f"  S_MDE(128) = {s_mde(128, 1.0):.3f} / {s_mde(128, NW_LARGEST):.3f}")
    print(f"Paper's window {PAPER_FIRST}..{PAPER_LAST} (raw industry profits): {months(PAPER_FIRST, PAPER_LAST)} calendar months, all counted as used")
    print()
    full = months(FIRST_FULL, LIB_LAST)
    i1 = months(FIRST_FULL, "1963-06")
    i2 = months("1995-08", LIB_LAST)
    rows = [
        ("I1", "before the paper's sample (return months)", f"{FIRST_FULL}..1963-06", i1),
        ("I2", "after the paper's sample", f"1995-08..{LIB_LAST}", i2),
        ("I1+I2", "all months outside the paper's sample", "both", i1 + i2),
        ("full", "whole library history (mined in part)", f"{FIRST_FULL}..{LIB_LAST}", full),
    ]
    print("  id     window                                      months             N    S_MDE          x pool 0.321")
    for rid, q, span, n in rows:
        a, b = s_mde(n, 1.0), s_mde(n, NW_LARGEST)
        print(f"  {rid:<6} {q:<43} {span:<17} {n:5d}  {a:.3f} / {b:.3f}  {a / POOL:.2f}x / {b / POOL:.2f}x")
    print()
    print("Comparison with the rows already decided (committed outputs):")
    print("  Study 010 outside its paper's window, 560 months: 0.416 / 0.461 (tools/power_study010.txt)")
    print("  vol-managed / dynamic momentum after their samples, 128-161 months: 0.776-0.964 (tools/power_mined.txt);")
    print("  not fixed (RESEARCH_AGENDA.md, dated addition 2026-10-26 13:2xZ)")
    print()
    print("Months needed to see the pool's Sharpe(d) 0.321 (nw 1.00 / largest observed):")
    print(f"  {12 * (K / POOL) ** 2:5.0f} / {12 * (K * NW_LARGEST / POOL) ** 2:5.0f}")


if __name__ == "__main__":
    main()
