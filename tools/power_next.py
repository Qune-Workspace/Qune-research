#!/usr/bin/env python3
"""Minimum detectable timing edge for agenda questions 2 (bond carry, carry plus
trend in Treasuries) and 5 (the curve switch on ETF history), computed before
either question is fixed, from dispersions already published in this repository.

Usage: python3 tools/power_next.py [--out tools/power_next.txt]

Added 2026-10-25 under the power-first rule of 2026-10-24 (RESEARCH_AGENDA.md,
status paragraph, step 1), after candidate 6 became Study 006. The rule forbids
using a new question's data, so nothing here fetches anything or reads a yield
series. Inputs are committed result files only:

  Study 003  results/insample/monthly_base.csv         IEF-era differential T1 - B3, 185 months
  Study 004  results/insample/signal_vol_10assets.csv  per-asset trailing volatility at each
                                                       signal date (SHY, IEF, TLT), 181 rows
  Study 006  results/history/monthly_base.csv          the term-spread switch's holdings 1969-2018
             results/volcheck/volcheck.json            sigma of the synthetic 7-10y leg, 593 months

Before reporting anything it reproduces published figures and stops on a miss:
003's C2 t (0.37) and w (0.692); 006's 593 periods, 77 bill months, w (0.8702)
and sigma (7.75%). The same product form as tools/power_candidate6.py is used:
for a switch between a leg and cash, T1 - B3 = (h - w) x, so
sd(T1 - B3) ~ sqrt(w(1 - w)) rms(x), with the Newey-West to i.i.d. factor and
the conservative/calibrated distinction carried over from the 003 file.

Volatility proxies for SHY and TLT: no committed file holds their monthly
returns. Study 004's signal_vol file holds the close-to-close trailing
volatility the sizing used at every signal date (an ex-ante estimate, not a
realised monthly-return volatility). Its root-mean-square over the window is
calibrated to 003's realised IEF excess-return volatility by the IEF ratio and
labelled as a proxy. Standard library only; descriptive, no decision weight.
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

from power_first import C2_BAR, LAGS, Z_POWER_80, newey_west_se

ROOT = Path(__file__).resolve().parent.parent
F003 = "research/003-bond-tsmom-ief/results/insample/monthly_base.csv"
F004 = "research/004-xasset-trend-voltarget/results/insample/signal_vol_10assets.csv"
F006 = "research/006-term-spread-switch-long-history/results/history/monthly_base.csv"
F006V = "research/006-term-spread-switch-long-history/results/volcheck/volcheck.json"
PUB_003 = {"t": 0.37, "w": 0.692}
PUB_006 = {"periods": 593, "bill_months": 77, "w": 0.8702, "sigma": 0.0775}
ETF_ERA = ("2003-07", "2018-11")  # 003's 185 in-sample signal months
K = (C2_BAR + Z_POWER_80) * 12  # annual MDE = K x monthly standard error of the mean differential
TARGETS = (0.02, 0.01)


def sd(x):
    m = sum(x) / len(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / len(x))


def rms(x):
    return math.sqrt(sum(v * v for v in x) / len(x))


def mde(sigma_annual, w, n, nw_factor):
    """Annual C2-bar MDE under the product form: K x nw x sqrt(w(1-w)) x sigma_monthly / sqrt(n)."""
    return K * nw_factor * math.sqrt(w * (1 - w)) * (sigma_annual / math.sqrt(12)) / math.sqrt(n)


def months_for(target, sigma_annual, w, nw_factor):
    return (K * nw_factor * math.sqrt(w * (1 - w)) * (sigma_annual / math.sqrt(12)) / target) ** 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args()

    # --- Study 003: reproduce, then take the dispersion constants ---
    r003 = list(csv.DictReader((ROOT / F003).open()))
    n003 = len(r003)
    d = [float(r["T1"]) - float(r["B3"]) for r in r003]
    x = [float(r["B1"]) - float(r["B0"]) for r in r003]
    w003 = sum(1.0 for r in r003 if r["T1_holding"] == "IEF") / n003
    se_nw = newey_west_se(d, LAGS)
    t003 = (sum(d) / n003) / se_nw
    if abs(t003 - PUB_003["t"]) > 0.005 or abs(w003 - PUB_003["w"]) > 0.0005:
        sys.exit(f"003: recomputed t {t003:.4f} / w {w003:.4f} do not match the published {PUB_003}")
    nw_factor = se_nw / (sd(d) / math.sqrt(n003))
    calib = math.sqrt(w003 * (1 - w003)) * rms(x) / sd(d)  # product form / actual, > 1 means conservative
    sigma_ief = sd(x) * math.sqrt(12)

    # --- Study 006: reproduce, then the spread rule's ETF-era holdings and the long-history sigma ---
    r006 = list(csv.DictReader((ROOT / F006).open()))
    bill = sum(1 for r in r006 if r["T1_holding"] == "BIL")
    w006 = 1 - bill / len(r006)
    vol006 = json.loads((ROOT / F006V).read_text())
    sigma006, mde006 = vol006["sigma_annual"], vol006["mde_annual"]
    if (len(r006), bill) != (PUB_006["periods"], PUB_006["bill_months"]) or abs(w006 - PUB_006["w"]) > 0.0005 \
            or abs(sigma006 - PUB_006["sigma"]) > 0.0005:
        sys.exit(f"006: recomputed {len(r006)} periods / {bill} bill months / w {w006:.4f} / sigma {sigma006:.4f} "
                 f"do not match the published {PUB_006}")
    era = [r for r in r006 if ETF_ERA[0] <= r["month"] <= ETF_ERA[1]]
    era_bill = [r["month"] for r in era if r["T1_holding"] == "BIL"]
    if len(era) != n003:
        sys.exit(f"006 ETF-era rows {len(era)} differ from 003's {n003} months")
    w_q5 = 1 - len(era_bill) / len(era)

    # --- Study 004: per-asset trailing volatility, calibrated to 003's realised IEF figure ---
    r004 = list(csv.DictReader((ROOT / F004).open()))
    sig = {}
    for a in ("SHY", "IEF", "TLT"):
        v = [float(r[a]) for r in r004 if r[a]]
        sig[a] = (rms(v), len(v))
    ief_ratio = sigma_ief / sig["IEF"][0]
    proxy = {a: sig[a][0] * ief_ratio for a in sig}

    out = [
        "Agenda questions 2 and 5: minimum detectable timing edge of the C2 test, committed before either question is fixed",
        "(inputs: committed result files of Studies 003, 004 and 006 only; nothing fetched, no yield series read)",
        "",
        "Anchors reproduced before anything is reported",
        f"  003 in-sample: {n003} months, NW t {t003:.2f} (published {PUB_003['t']}), w {w003:.3f} (published {PUB_003['w']});"
        f" NW / i.i.d. {nw_factor:.3f}; product form / actual {calib:.3f}; IEF excess-return volatility {sigma_ief:.2%} a year",
        f"  006 history: {len(r006)} periods, {bill} bill months, w {w006:.4f} (published {PUB_006['w']}), synthetic 7-10y leg sigma {sigma006:.2%}"
        f" (published {PUB_006['sigma']:.2%})",
        f"  004 signal_vol (trailing close-to-close, ex-ante, rms over {sig['IEF'][1]} signal dates): SHY {sig['SHY'][0]:.2%}, IEF {sig['IEF'][0]:.2%}, TLT {sig['TLT'][0]:.2%}",
        f"  calibration: 003 realised IEF / 004 ex-ante IEF = {ief_ratio:.3f}; proxies used below: SHY {proxy['SHY']:.2%}, IEF {proxy['IEF']:.2%}, TLT {proxy['TLT']:.2%} a year",
        "",
        f"MDE = ({C2_BAR} + {Z_POWER_80}) x 12 x NW standard error of the mean monthly differential (C2 bar, 80% power), product form",
        "sd(T1 - B3) = sqrt(w(1-w)) x sigma_leg; 'conservative' keeps the product form, 'calibrated' divides by the 003 factor.",
        "",
        "Question 5: the term-spread switch on IEF, 2003-07 to 2018-11 (the 185 months Study 003 used)",
        f"  Signal path already published (Study 006, results/history/monthly_base.csv): {len(era_bill)} bill months of {len(era)}, w {w_q5:.3f}",
        f"  bill months: {', '.join(era_bill)}",
        f"  C2-bar MDE at that w and 185 months: conservative {mde(sigma_ief, w_q5, n003, nw_factor):.2%}, calibrated {mde(sigma_ief, w_q5, n003, nw_factor) / calib:.2%} a year",
        f"  Upper bound on the timing part of the mean differential, |(1/N) sum over bill months of x|, at the ETF-era rms(x) {rms(x):.3%} a month:"
        f" {len(era_bill) / n003 * rms(x) * 12:.2%} a year",
        "  Reading: the MDE clears the 2% bar only because the rule hardly ever leaves the bond; the largest edge twelve bill months",
        "  could carry is about the same size as the MDE, so the test could at best just see a perfect call. Study 006 has already",
        "  published this window on synthetic legs that passed a fidelity gate against IEF over these same months (G1 bias 0.008% a",
        "  year): the 2000s decade bar is -0.1% a year and 2010-2018 is exposure only. Not computed here: the differential on actual",
        "  IEF over the twelve months, which would be question 5's result.",
        "",
        "Question 2: bond carry, and carry plus trend, in Treasuries (SHY, IEF, TLT against bills)",
        "  Leg against bills, worst case w = 0.5, ETF era (185 months) and the long history (593 months) at the same leg volatility:",
        "  leg     sigma (proxy)   MDE 185 cons.   MDE 185 calib.   MDE 593 cons.   months for 2%/yr (cons.)   months for 1%/yr (cons.)",
    ]
    for a in ("SHY", "IEF", "TLT"):
        s = proxy[a]
        out.append(
            f"  {a:<6}  {s:>8.2%}        {mde(s, 0.5, n003, nw_factor):>6.2%}          {mde(s, 0.5, n003, nw_factor) / calib:>6.2%}"
            f"           {mde(s, 0.5, PUB_006['periods'], nw_factor):>6.2%}          {months_for(0.02, s, 0.5, nw_factor):>8.0f}"
            f"                   {months_for(0.01, s, 0.5, nw_factor):>8.0f}"
        )
    s6 = sigma006
    out += [
        f"  006 synthetic 7-10y leg, sigma {s6:.2%}, 593 months, w = 0.5: MDE {mde(s6, 0.5, PUB_006['periods'], nw_factor):.2%} a year"
        f" (006's volcheck.json committed {mde006:.2%} at its data step)",
        "  Switch between maturities (TLT against SHY, duration timing inside Treasuries), w = 0.5, 185 months, conservative:",
        f"    sigma(TLT - SHY) lies between {proxy['TLT'] - proxy['SHY']:.2%} and {proxy['TLT'] + proxy['SHY']:.2%} (no committed correlation),"
        f" so the MDE lies between {mde(proxy['TLT'] - proxy['SHY'], 0.5, n003, nw_factor):.2%} and {mde(proxy['TLT'] + proxy['SHY'], 0.5, n003, nw_factor):.2%} a year",
        "",
        "The bar in return units is leg-independent in Sharpe units: MDE / sigma_leg = K x nw x sqrt(w(1-w)) / sqrt(12 N):",
        f"  185 months, w = 0.5: {K * nw_factor * 0.5 / math.sqrt(12 * n003):.3f}; 593 months, w = 0.5: {K * nw_factor * 0.5 / math.sqrt(12 * PUB_006['periods']):.3f}",
        "  so the 2% a year bar is weak for a low-volatility leg (SHY passes it with an edge the leg can hardly carry) and strict",
        "  for TLT. A Sharpe-unit statement belongs beside the return-unit one in any pre-registration that follows.",
        "",
        "Reading for question 2: on the ETF era alone no carry design on IEF or TLT clears the 2% a year bar under the committed",
        f"conservative form at w = 0.5 (IEF {mde(proxy['IEF'], 0.5, n003, nw_factor):.2%}, TLT {mde(proxy['TLT'], 0.5, n003, nw_factor):.2%});"
        f" IEF's calibrated figure ({mde(proxy['IEF'], 0.5, n003, nw_factor) / calib:.2%}) does. A powered version needs the",
        "long constant-maturity history: carry (yield over bills plus roll-down) read from the same FRED curve Study 006 already",
        f"holds, on 006's frozen synthetic 7-10y leg over 1969-2018, MDE {mde(s6, 0.5, PUB_006['periods'], nw_factor):.2%} a year at w = 0.5. That window is not untouched for",
        "the instrument (006's three trend/spread trials ran on it; programme family count would rise from 3), and the 2019-2026",
        "IEF/BIL window is spent (METHODS section 2.5), so the test would be the long history plus a forward record, as for 006.",
        "Precision (same run): a carry-SIGN switch on that leg is already published as Study 006's trial T3 (Study 001's",
        "'carry including roll-down' rule; Sharpe 0.468, NW t 1.91 vs B3, C2 fail), so the powered form of question 2 must be a",
        "different rule (a carry tilt by level, carry across maturities, or carry combined with the unseen long-history trend).",
        "Assumptions stated now: the NW/i.i.d. factor (0.972) and the product form carry over; SHY and TLT volatilities are",
        "ex-ante proxies calibrated on IEF, not realised monthly-return volatilities; a carry rule's w is unknown, 0.5 is the worst case.",
    ]
    text = "\n".join(out) + "\n"
    sys.stdout.write(text)
    if args.out:
        (ROOT / args.out).write_text(text)


if __name__ == "__main__":
    main()
