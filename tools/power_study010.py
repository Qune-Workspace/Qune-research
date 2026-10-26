"""Power of each row of Study 010's question note, before any return is read.

Arithmetic on month counts only (RESEARCH_AGENDA, dated addition 2026-10-26 06:2xZ: the
question note "names the source paper and its rule, the family count, the in-sample and
post-sample rows and their power, and the vintage plan, written before any return is read").
Reads nothing and fetches nothing. Month counts come from the Kenneth French Data Library
detail pages (US 3 factors from July 1926, read 2026-10-26 06:1xZ; short-term reversal from
February 1926 and long-term reversal from January 1931, read 07:20Z; all to August 2026) and
from the source paper's stated sample (Ehsani and
Linnainmaa, NBER Working Paper 25551, February 2019: US factor data from July 1963,
strategies from July 1964 to December 2015). The data step fixes the last month from the
snapshot; a later last month lengthens the full and post-sample rows only.

Method as tools/power_offduration.py: S_MDE(N) = K x nw / sqrt(N / 12), K = 2.842 (a
Newey-West t >= 2.0 seen with 80% power), nw = Newey-West over iid standard error, shown at
1.00 and at 1.108, the largest ratio observed among the programme's committed d series (not a
bound). Compared with the pool of Studies 006-008, Sharpe(d) 0.321 (an in-sample anchor,
standard error about 0.15; tools/power_offduration.txt), and with the 2%-a-year bar through
sd(d) <= 2% / S_MDE.

Run from the repository root: ``python tools/power_study010.py > tools/power_study010.txt``
"""

from __future__ import annotations

import math

K = 2.842
NW = (1.00, 1.108)
POOL = 0.321


def months(start: tuple[int, int], end: tuple[int, int]) -> int:
    """Holding months from start to end inclusive, (year, month) pairs."""
    return (end[0] - start[0]) * 12 + (end[1] - start[1]) + 1


# First holding month 1927-07: SMB and HML have their first 12-month formation return then
# (ST_Rev earlier); LT_Rev joins in 1932-01, as the paper adds factors when they start.
ROWS = [
    ("H  full history (decision row)", (1927, 7), (2026, 8)),
    ("P1 before the paper's data (pre-1963-07)", (1927, 7), (1963, 6)),
    ("L  the paper's US data window", (1963, 7), (2015, 12)),
    ("P2 after the paper's sample end", (2016, 1), (2026, 8)),
]


def s_mde(n: int, nw: float) -> float:
    return K * nw / math.sqrt(n / 12)


def main() -> None:
    print("Study 010 question note: power of each row (arithmetic on month counts; no return read)")
    print(f"K = {K}; nw shown at {NW[0]:.2f} / {NW[1]:.3f}; pool anchor Sharpe(d) {POOL}")
    print()
    hdr = (
        f"  {'row':44s} {'first':>8s} {'last':>8s} {'N':>5s}   {'S_MDE':>13s}   {'x pool':>13s}   2% bar needs sd(d) <="
    )
    print(hdr)
    rows = [(lab, a, b, months(a, b)) for lab, a, b in ROWS]
    p1, p2 = rows[1][3], rows[3][3]
    rows.append(("P  outside the paper's window (P1 + P2)", None, None, p1 + p2))
    for lab, a, b, n in rows:
        s = [s_mde(n, nw) for nw in NW]
        first = f"{a[0]}-{a[1]:02d}" if a else "-"
        last = f"{b[0]}-{b[1]:02d}" if b else "-"
        print(
            f"  {lab:44s} {first:>8s} {last:>8s} {n:5d}   {s[0]:.3f} / {s[1]:.3f}"
            f"   {s[0] / POOL:.2f}x / {s[1] / POOL:.2f}x   {2 / s[0]:.2f}% / {2 / s[1]:.2f}%"
        )
    print()
    print("  check: H = P1 + L + P2:", rows[0][3] == rows[1][3] + rows[2][3] + rows[3][3])
    print("  months to see Sharpe(d) 0.321 at nw 1.00:", round((K / POOL) ** 2 * 12))


if __name__ == "__main__":
    main()
