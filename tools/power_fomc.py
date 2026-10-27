"""Power first for the pre-FOMC announcement drift [LM15] after the paper's sample.

Descriptive power calculation, written 2026-10-27 from 21:1xZ by the clock, before any question
is fixed. No return is read: the inputs are the paper's own reported means, standard deviations
and counts, meeting counts from the Federal Reserve's calendar pages, and the house constant K.

Paper read on 2026-10-27 21:1xZ from the Federal Reserve Bank of New York Staff Report 512
(Lucca, Moench, "The Pre-FOMC Announcement Drift", September 2011, revised August 2013,
newyorkfed.org/medialibrary/media/research/staff_reports/sr512.pdf, SHA-256
c7cb0f335c60cb9fc305189935fb7c51e98fa8461c2b33efd51eb5a5c3f2e34b; text layer extracted with the
standard library only, nothing redistributed). The published version (J. Finance 70(1), 2015,
doi:10.1111/jofi.12196) is closed access and was not read. Quoted from the staff report:
- Table 1 note: "The sample period is 1994:09-2011:03 in the top panel"; "SPX-2pm is the
  cum-dividend log excess return on the S&P500 index from 2pm at date t - 1 to 2pm on date t.
  SPX denotes the close-to-close log excess return on the S&P500 index."
- Table 1, post-1994 panel, pre-FOMC column (mean, st.dev., N, in %):
  SPX-2pm .488 1.215 131; SPX .338 1.144 132.
- Text: "for the 131 FOMC observations in the sample, the 24-hour return right before the FOMC
  meeting has on average been 49 basis points, with a t-statistic of more than 4.5 based on
  Huber-White standard errors"; close-to-close "about 33 basis points"; "the close-to-close FOMC
  day return ... yields a considerable annualized Sharpe Ratio of 0.84".

Later work: Kurov, Wolfe, Gilbert, "The disappearing pre-FOMC announcement drift", Finance
Research Letters 40 (2021) 101781, doi:10.1016/j.frl.2020.101781 (Crossref checked 2026-10-27).
Its text and abstract were NOT read (closed access; the SSRN page is behind a browser check, not
bypassed; Crossref and OpenAlex carry no abstract). Only its title is used: it implies a reported
decline of the drift after [LM15]'s sample. Its own sample was not checked, so that it covers the
window below is inferred from the title, not verified. Either way the direction of the prior is
known before any question is fixed.

Meetings after the sample (scheduled meetings held, as in the paper; unscheduled meetings,
conference calls and notation votes excluded), from the Fed's yearly pages: 2011 Apr 26-27,
Jun 21-22, Aug 9, Sep 20-21, Nov 1-2, Dec 13 after the last in-sample one (Mar 15) = 6;
2012-2019 eight a year = 64; 2020 seven (Mar 17-18 "cancelled"; Mar 2 and Mar 15 "unscheduled")
= 7; 2021-2025 eight a year = 40; 2026 Jan, Mar, Apr, Jun, Jul, Sep before October = 6. Total
2011-04..2026-09 = 123. Pages for 2011, 2020 and 2026 read by Qune; 2012-2019 and 2021-2025
counted in the separate-session check (tools/power_fomc_recompute.md). The Oct 27-28 2026
meeting is under way as this is written and is in no window below.

Method as the house tools, per event instead of per month: a one-sided-in-effect test that
reaches |t| >= 2.0 with 80% power needs mean >= K * sd / sqrt(N), K = 2.842. In Sharpe units
(annualised at 8 meetings a year, the paper's own convention for its 0.84): S_MDE = K * nw /
sqrt(N / 8). Event days do not overlap, so nw = 1.00; the programme's largest observed
Newey-West ratio (1.108) is shown as a sensitivity in the Sharpe table only. The post-sample
standard deviation is not read; the paper's is used, with +/-25% as a sensitivity. K is the
normal approximation; with 39 degrees of freedom (forward window) the t quantile would need
slightly more, so the forward figures are, if anything, optimistic.

Not checked, for any later data step: statement release times after 2011 (on some days they may
fall inside a 2pm-to-2pm window). The power figures do not depend on it.

Dated addition, 2026-10-27 from 22:1xZ by the clock (section 6; sections 1-5 unchanged): the
desk's paper market-data feed (Alpaca, SIP feed) was probed for SPY minute bars, counts and
timestamps only, no price read (record: tools/intraday_source_check.md). Minute bars start on
2016-01-04; none on any date probed before it. The 2pm-to-2pm form can therefore be built for
the scheduled meetings of 2016-01..2026-09 only: 2016-2019 eight a year = 32; 2020 seven; 2021-2025
eight a year = 40; 2026 six = 85 (the same counts as the 123 above, minus 2011-04..2015-12 = 38).
SPY is an ETF on the index, not the index the paper used; that is a construction difference for any
later pre-registration, not a power input.

Run from the repository root: ``python tools/power_fomc.py > tools/power_fomc.txt``
"""

from __future__ import annotations

import math

K = 2.842
NW_LARGEST = 1.108  # largest Newey-West ratio observed in the programme (tools/power_offduration.txt)
PER_YEAR = 8
FORMS = {  # form: (mean %, sd %, N) from LM15 Table 1, post-1994 panel, pre-FOMC column
    "2pm-to-2pm (SPX-2pm)": (0.488, 1.215, 131),
    "close-to-close (SPX)": (0.338, 1.144, 132),
}
PAPER_SHARPE_CC = 0.84  # LM15 text, close-to-close, annualised
N_POST = 6 + 8 * 8 + 7 + 5 * 8 + 6  # 2011-04..2026-09 scheduled meetings held (2020: 7)
N_ALPACA = 8 * 4 + 7 + 5 * 8 + 6  # 2016-01..2026-09, the window with SIP minute bars (section 6)
N_FORWARD = 60 // 12 * PER_YEAR  # 60 months of forward record


def mde_mean(sd: float, n: int) -> float:
    return K * sd / math.sqrt(n)


def mde_sharpe(n: int, nw: float = 1.0) -> float:
    return K * nw / math.sqrt(n / PER_YEAR)


def main() -> None:
    print("Power first: pre-FOMC announcement drift [LM15] after its sample (no return read)")
    print(f"K = {K}; annualised at {PER_YEAR} meetings a year; nw 1.00 (sensitivity {NW_LARGEST})")
    print()
    print("1. The paper's own figures, recomputed from Table 1 (plain t, Sharpe)")
    for form, (m, sd, n) in FORMS.items():
        t = m / (sd / math.sqrt(n))
        s = m / sd * math.sqrt(PER_YEAR)
        print(f"   {form:24s} mean {m:.3f}% sd {sd:.3f}% N {n}: plain t {t:.2f}, Sharpe {s:.3f}")
    print(f"   check: close-to-close Sharpe vs the paper's stated {PAPER_SHARPE_CC}")
    print()
    print(f"2. Windows: after the sample 2011-04..2026-09 N = {N_POST}; forward 60 months N = {N_FORWARD}")
    print()
    print("3. Minimum detectable mean (80% power at |t| >= 2.0), paper's sd and +/-25%")
    for form, (m, sd, _n) in FORMS.items():
        for label, n in (("after sample", N_POST), ("forward 60m", N_FORWARD)):
            cells = []
            for f in (0.75, 1.00, 1.25):
                v = mde_mean(sd * f, n)
                cells.append(f"sd x{f:.2f}: {v:.3f}% ({v / m:.2f}x)")
            print(f"   {form:24s} {label:12s} " + "; ".join(cells))
    print("   (x = multiple of the paper's own mean for that form)")
    print()
    print("4. Minimum detectable annualised Sharpe")
    s2 = FORMS["2pm-to-2pm (SPX-2pm)"][0] / FORMS["2pm-to-2pm (SPX-2pm)"][1] * math.sqrt(PER_YEAR)
    for label, n in (("after sample", N_POST), ("forward 60m", N_FORWARD)):
        a, b = mde_sharpe(n), mde_sharpe(n, NW_LARGEST)
        print(f"   {label:12s} N {n:3d}: {a:.3f} (nw {NW_LARGEST}: {b:.3f}); "
              f"vs paper close-to-close {PAPER_SHARPE_CC}: {a / PAPER_SHARPE_CC:.2f}x; "
              f"vs 2pm {s2:.3f}: {a / s2:.2f}x")
    print()
    print("5. Meetings needed to see the paper's own mean (80% power, paper's sd)")
    for form, (m, sd, _n) in FORMS.items():
        need = math.ceil((K * sd / m) ** 2)
        print(f"   {form:24s} {need} meetings = {need / PER_YEAR:.3f} years")
    print()
    print(f"6. 2pm-to-2pm on the window with a checked free minute-bar source (2016-01..2026-09), N = {N_ALPACA}")
    m, sd, _n = FORMS["2pm-to-2pm (SPX-2pm)"]
    cells = []
    for f in (0.75, 1.00, 1.25):
        v = mde_mean(sd * f, N_ALPACA)
        cells.append(f"sd x{f:.2f}: {v:.3f}% ({v / m:.2f}x)")
    print("   mean: " + "; ".join(cells))
    a, b = mde_sharpe(N_ALPACA), mde_sharpe(N_ALPACA, NW_LARGEST)
    print(f"   Sharpe: {a:.3f} (nw {NW_LARGEST}: {b:.3f}); vs 2pm {s2:.3f}: {a / s2:.2f}x (nw: {b / s2:.2f}x)")


if __name__ == "__main__":
    main()
