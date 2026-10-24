#!/usr/bin/env python3
"""Minimum detectable timing edge for candidate 6 (RESEARCH_AGENDA.md), committed
before its question is fixed, from dispersions already published in this repository.

Usage: python3 tools/power_candidate6.py [--out tools/power_candidate6.txt]

Added 2026-10-25 under the power-first rule of 2026-10-24 (RESEARCH_AGENDA.md,
status paragraph, step 1). Candidate 6 is a monthly duration-timing rule on a
constant-maturity Treasury history from 1969-08 (Study 001's in-sample start,
593 holding periods to 2018-12), tested against an exposure-matched static mix
with the C2 bar (Newey-West t of the mean monthly differential >= 2.0, 6 lags).

The rule forbids using the new question's data, so nothing here reads a
constant-maturity series. Inputs are Study 003's committed in-sample monthly
file only (ETF era, 185 periods):

1. It recomputes the published C2 t (0.37) and stops unless it matches to 0.005.
2. Approximation used below: for a switch between a duration leg and cash, the
   differential T1 - B3 = (h_t - w) * x_t, with h_t in {0, 1}, w its mean and
   x_t the duration leg's monthly excess return over cash (B1 - B0); so
   sd(T1 - B3) ~ sqrt(w(1 - w)) * rms(x). The script reports how close that is
   on the 003 file, and the ratio of the Newey-West to the i.i.d. standard error.
3. It scales the 003 figure to 593 months at the same dispersion, then inverts
   the formula: the largest annualised excess-return volatility of the duration
   leg at which the C2-bar MDE stays at or below 2% (and 1%) a year, with
   w = 0.5 (the worst case, the signal is unknown) and with the 003 w.

That volatility is the committed bar: the candidate-6 pre-registration must
measure the constructed series' excess-return volatility at its data-check step,
before any rule return, and if it exceeds the 2% bar the study runs only as a
low-power check, labelled as such in its title (rule, step 2). Standard library
only; descriptive, no decision weight for any finished study.
"""
import argparse
import csv
import math
import sys
from pathlib import Path

from power_first import C2_BAR, LAGS, Z_POWER_80, newey_west_se

ROOT = Path(__file__).resolve().parent.parent
FILE = "research/003-bond-tsmom-ief/results/insample/monthly_base.csv"
PUBLISHED_T, PUBLISHED_W = 0.37, 0.692
N_CANDIDATE = 593  # 1969-08 to 2018-12, Study 001 README / execution_calendar.csv
TARGETS = (0.02, 0.01)


def sd(x):
    m = sum(x) / len(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / len(x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args()
    rows = list(csv.DictReader((ROOT / FILE).open()))
    n = len(rows)
    d = [float(r["T1"]) - float(r["B3"]) for r in rows]
    x = [float(r["B1"]) - float(r["B0"]) for r in rows]
    h = [1.0 if r["T1_holding"] == "IEF" else 0.0 for r in rows]
    w = sum(h) / n
    se_nw = newey_west_se(d, LAGS)
    t = (sum(d) / n) / se_nw
    if abs(t - PUBLISHED_T) > 0.005 or abs(w - PUBLISHED_W) > 0.0005:
        sys.exit(f"recomputed t {t:.4f} / w {w:.4f} do not match the published {PUBLISHED_T} / {PUBLISHED_W}")
    sd_d = sd(d)
    rms_x = math.sqrt(sum(v * v for v in x) / n)
    approx = math.sqrt(w * (1 - w)) * rms_x
    nw_factor = se_nw / (sd_d / math.sqrt(n))
    k = (C2_BAR + Z_POWER_80) * 12  # MDE (annual) = k * monthly standard error
    mde_003 = k * se_nw
    mde_593 = mde_003 * math.sqrt(n / N_CANDIDATE)
    vol_x_etf = sd(x) * math.sqrt(12)

    def vol_bar(target, w_assumed):
        # target = k * nw_factor * sqrt(w(1-w)) * sigma_x_monthly / sqrt(N); solve for sigma_x, annualise
        sigma_m = target * math.sqrt(N_CANDIDATE) / (k * nw_factor * math.sqrt(w_assumed * (1 - w_assumed)))
        return sigma_m * math.sqrt(12)

    out = [
        "Candidate 6: minimum detectable timing edge of the C2 test, committed before the question is fixed",
        "(inputs: Study 003's committed in-sample file only; no constant-maturity data read)",
        "",
        f"Study 003 in-sample check: {n} months, NW t {t:.2f} (published {PUBLISHED_T}), w {w:.3f} (published {PUBLISHED_W})",
        f"  sd(T1 - B3) {sd_d * 100:.3f}% a month; sqrt(w(1-w)) x rms(B1 - B0) {approx * 100:.3f}% "
        f"(approximation / actual {approx / sd_d:.3f})",
        f"  NW / i.i.d. standard error {nw_factor:.3f}; IEF excess-return volatility {vol_x_etf:.2%} a year",
        f"  C2-bar MDE at {n} months: {mde_003:.2%} a year",
        "",
        f"Same dispersion and autocorrelation at {N_CANDIDATE} months (1969-08 to 2018-12): MDE {mde_593:.2%} a year",
        "",
        "Largest annualised excess-return volatility of the duration leg at which the C2-bar MDE stays at or below:",
        "  target    w = 0.5 (worst case)    w = 0.692 (003's)",
    ]
    for target in TARGETS:
        out.append(f"  {target:.0%}/yr    {vol_bar(target, 0.5):>10.2%}             {vol_bar(target, w):>10.2%}")
    calib = approx / sd_d
    out += [
        "",
        f"The product form overstates the 003 dispersion by a factor of {calib:.3f}, so the bars above are conservative.",
        f"Calibrated to 003 (divide the dispersion by {calib:.3f}), the 2% bar would be "
        f"{vol_bar(0.02, 0.5) * calib:.2%} (w = 0.5) / {vol_bar(0.02, w) * calib:.2%} (w = 0.692).",
        f"Committed bar (chosen before any candidate-6 data are read): the conservative w = 0.5 figure, "
        f"{vol_bar(0.02, 0.5):.2%} a year for 2%/yr.",
    ]
    out += [
        "",
        "MDE = (2.0 + 0.842) x 12 x NW standard error of the mean monthly differential (C2 bar, 80% power).",
        "Assumptions (stated before any candidate-6 data are read): the NW/i.i.d. factor and the product form of the",
        "differential carry over from the ETF era; the duration leg's excess-return volatility is the only quantity",
        "expected to change. Inferred, not measured: 1969-2018 rates were more volatile than 2003-2018, so the leg's",
        "volatility will be higher than the ETF-era figure; whether it stays under the 2% bar is checked at the",
        "candidate-6 data step, before any rule return. Under the committed (conservative) form the 1% bar needs a",
        "leg calmer than IEF was in 2003-2018, so candidate 6 cannot claim to see an edge of 1% a year or less.",
    ]
    text = "\n".join(out) + "\n"
    sys.stdout.write(text)
    if args.out:
        (ROOT / args.out).write_text(text)


if __name__ == "__main__":
    main()
