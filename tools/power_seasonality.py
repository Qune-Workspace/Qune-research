"""Power first for industry return seasonality [KLN14] on the French US industry portfolios.

Descriptive power calculation, written 2026-10-26 from 23:1xZ by the clock, before any question
is fixed. No return is read: the inputs are month counts from the paper's stated sample and the
library's detail pages (as read for tools/power_industry.py), the paper's own reported average
and t-value, and anchors already committed in this repository.

Paper read on 2026-10-26 23:1xZ from the NBER working paper (Keloharju, Linnainmaa, Nyberg,
"Common Factors in Return Seasonalities", NBER Working Paper 20815, December 2014,
nber.org/system/files/working_papers/w20815/w20815.pdf, SHA-256
a273963eeaf32b3acdd15bb0ddfd9d74cc91c7138f8f81956a7d9072d518fc65; text layer extracted with the
standard library only, nothing redistributed). The published version (J. Finance 71(4), 2016,
"Return Seasonalities", doi:10.1111/jofi.12398) is closed access and was not read; its abstract
(OpenAlex) states the same headline. Quoted from the working paper:
- Table 1 note: "17 portfolios for Fama-French industries"; "The same-month portfolio sorts rank
  individual stocks and portfolios by their average return in the same calendar month over the
  prior 20 years"; the industry strategy trades "the top two and bottom two portfolios"; "We use
  monthly data from January 1963 through December 2011".
- Text: "the industry strategy earns 0.70% (t-value = 3.79)" (all months, same-month sort).
- Data section: "right-hand-side returns we use monthly returns going back to January 1943".
  So the paper read 1943-1962 returns as ranking inputs, though it scored no strategy return
  before 1963-01: those months are seen, not clean.
- The text does not say whether the t-values are Newey-West ("Newey" does not occur); the
  implied Sharpe and volatility below assume a plain t and are labelled as such.

Library: the 17-industry portfolios run July 1926 - August 2026 (detail pages read 2026-10-26
14:1xZ for tools/power_industry.py; no return read). A 20-year same-calendar-month average
first exists for return month 1946-07 (Julys 1926-1945) and for every month after it; earlier
months lack their 1926 calendar month, so the first scorable return month is 1946-07. Every
scored month 1946-07..1962-12 lies inside the paper's 1943-1962 ranking inputs (read by the
paper); most of their own ranking inputs (1926-07..1942-12) were not. Table 1's portfolios are
value-weighted, so a study would use the library's value-weighted 17-industry file. Industry definitions are the library's four-digit SIC sets,
which the paper names as "Fama-French industries"; whether its vintage matches today's library
file is unknown, so a test on the library is a variant until shown otherwise.

Method as tools/power_industry.py: S_MDE = K * nw / sqrt(N / 12), K = 2.842 (t >= 2.0 at 80%
power), nw at 1.00 and at the largest ratio observed in the programme (1.108; not a bound).

Run from the repository root: ``python tools/power_seasonality.py > tools/power_seasonality.txt``
"""

from __future__ import annotations

import math

K = 2.842
NW_LARGEST = 1.108  # largest Newey-West ratio observed in the programme (tools/power_offduration.txt)
POOL = 0.321  # pool of Studies 006-008, Sharpe of d (tools/power_offduration.txt), an anchor only
STUDY011_SHARPE = 0.237  # Study 011 history, 806 months outside [MG99]'s sample (root README), observed
LIB_FIRST, LIB_LAST = "1926-07", "2026-08"
FIRST_SCORABLE = "1946-07"  # first month with 20 prior same-calendar-month returns in the library
PAPER_FIRST, PAPER_LAST = "1963-01", "2011-12"
PAPER_SIGNAL_FIRST = "1943-01"  # earliest ranking-input month the paper read
PAPER_MEAN_PM, PAPER_T = 0.70, 3.79  # industry same-month strategy, % a month, t-value (Table 1)


def months(first: str, last: str) -> int:
    y0, m0 = map(int, first.split("-"))
    y1, m1 = map(int, last.split("-"))
    return (y1 - y0) * 12 + (m1 - m0) + 1


def s_mde(n: float, nw: float) -> float:
    return K * nw / math.sqrt(n / 12)


def main() -> None:
    print("Power first for industry return seasonality [KLN14] on the library's 17 industries (tools/power_seasonality.py)")
    print(f"K = {K} (t >= 2.0 at 80% power); nw 1.00 / largest observed {NW_LARGEST}; library {LIB_FIRST}..{LIB_LAST}")
    print("no return read; months from the paper's stated sample and the library's detail pages only")
    print()
    print("Check first: 806 months reproduce tools/power_industry.txt (0.347 / 0.384)")
    print(f"  S_MDE(806) = {s_mde(806, 1.0):.3f} / {s_mde(806, NW_LARGEST):.3f}")
    n_paper = months(PAPER_FIRST, PAPER_LAST)
    sr_m = PAPER_T / math.sqrt(n_paper)
    sr_a = sr_m * math.sqrt(12)
    sd_m = PAPER_MEAN_PM / sr_m
    sd_a = sd_m * math.sqrt(12)
    print()
    print(f"Paper's scored window {PAPER_FIRST}..{PAPER_LAST}: {n_paper} months, all counted as used")
    print(f"Paper's ranking inputs from {PAPER_SIGNAL_FIRST}: {months(PAPER_SIGNAL_FIRST, '1962-12')} months before its window were read, not scored")
    print(f"Paper's industry rule, implied if the t is a plain t (not stated): Sharpe {sr_a:.3f} a year;")
    print(f"  sd {sd_m:.2f}% a month = {sd_a:.1f}% a year; mean {PAPER_MEAN_PM * 12:.1f}% a year")
    print()
    pre = months(FIRST_SCORABLE, "1962-12")
    post = months("2012-01", LIB_LAST)
    clean_pre = months(FIRST_SCORABLE, "1942-12")
    rows = [
        ("S1", "before the window (scored months read by paper)", f"{FIRST_SCORABLE}..1962-12", pre),
        ("S1c", "before any month the paper read", f"{FIRST_SCORABLE}..1942-12", clean_pre),
        ("S2", "after the paper's window", f"2012-01..{LIB_LAST}", post),
        ("S1+S2", "all scorable outside the window (S1 seen)", "both", pre + post),
    ]
    print("  id     window                                          months             N    S_MDE          x pool 0.321   x 011 0.237   x paper     MDE %/yr at paper sd (plain t)")
    for rid, q, span, n in rows:
        if n <= 0:
            print(f"  {rid:<6} {q:<47} {span:<17} {0:5d}  none: first scorable 1946-07 is after 1943-01")
            continue
        a, b = s_mde(n, 1.0), s_mde(n, NW_LARGEST)
        print(
            f"  {rid:<6} {q:<47} {span:<17} {n:5d}  {a:.3f} / {b:.3f}  {a / POOL:.2f}x / {b / POOL:.2f}x"
            f"  {a / STUDY011_SHARPE:.2f}x / {b / STUDY011_SHARPE:.2f}x  {a / sr_a:.2f} / {b / sr_a:.2f}"
            f"  {a * sd_a:.1f} / {b * sd_a:.1f}"
        )
    print()
    print("only S2 (176 months) has outcomes the paper never read.")
    print("Reading: x paper = the MDE as a multiple of the paper's own in-sample Sharpe (implied from a plain t);")
    print("  above 1 means even the full published edge is below the MDE. A rule that kept less than that multiple")
    print("  of its published edge out of sample would have less than 80% power to be seen; it would be missed")
    print("  more often than not only below about 0.70 of that multiple (2.0 / 2.842).")
    print("MDE %/yr uses the paper's implied 15.5% a year volatility (plain t assumed); the library variant's is unknown.")
    print()
    print("Comparison with rows already decided (committed outputs):")
    print("  Study 011 outside [MG99]'s window, 806 months: 0.347 / 0.384 (tools/power_industry.txt); observed 0.237")
    print("  Study 010 outside [EL19]'s window, 560 months: 0.416 / 0.461 (tools/power_study010.txt)")
    print("  vol-managed / dynamic momentum after their samples, 128-161 months: 0.776-0.964 (tools/power_mined.txt); not fixed")
    print()
    print("Months needed to see (nw 1.00 / largest observed):")
    for label, s in (("the pool's 0.321", POOL), ("Study 011's 0.237", STUDY011_SHARPE), (f"the paper's {sr_a:.3f}", sr_a)):
        print(f"  {label:<20} {12 * (K / s) ** 2:5.0f} / {12 * (K * NW_LARGEST / s) ** 2:5.0f}")


if __name__ == "__main__":
    main()
