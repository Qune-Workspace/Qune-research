#!/usr/bin/env python3
"""Minimum detectable edge for agenda question 4 (volatility-managed against
unmanaged exposure on the approved ETFs), computed before the question is fixed
or retired, from dispersions already published in this repository.

Usage: python3 tools/power_q4.py [--out tools/power_q4.txt]

Added 2026-10-25 under the power-first rule of 2026-10-24 (RESEARCH_AGENDA.md,
status paragraph, step 1), after question 2 became Study 007. Nothing is fetched
and no return of a volatility-managed book is computed. Inputs are committed
result files only:

  Study 003  results/insample/monthly_base.csv         NW / i.i.d. factor and the IEF calibration
  Study 004  results/insample/signal_vol_10assets.csv  per-asset trailing volatility at each signal
                                                       date (the question's IWM, IEF and TLT)

The test the agenda describes, in this programme's form: a long-only book that
holds w_t of one ETF and 1 - w_t in bills, with w_t set from trailing volatility
and 0 <= w_t <= 1 (the desk uses no margin), against B3 = the same ETF held at the
average weight w-bar throughout. T - B3 = (w_t - w-bar) x, so under the product
form sd(T - B3) ~ sd(w) x sigma_leg, and sd(w) <= 0.5 for any weight in [0, 1]
(the worst case, reached only by a 0/1 switch held half the time). The same
constants as tools/power_next.py are used, and its anchors are reproduced first.

SPY, QQQ and DIA, which the agenda also names, have no committed volatility
series (SPY was excluded from Study 004 at its data gate; QQQ and DIA were never
in a study). Standard library only; descriptive, no decision weight.
"""
import argparse
import csv
import math
import sys
from pathlib import Path

from power_first import LAGS, newey_west_se
from power_next import F003, F004, PUB_003, K, mde, months_for, rms, sd

ROOT = Path(__file__).resolve().parent.parent
FIRST_SIGNAL = "2003-12-31"  # Study 004's signal file: 181 rows to 2018-12-31; rms over all of them, as power_next.py
N_004 = 180
PUB_NEXT = {"SHY": 0.0137, "IEF": 0.0651, "TLT": 0.1345}  # tools/power_next.txt, 004 signal_vol rms
LEGS = ("IWM", "IEF", "TLT")
BAR = 0.02


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args()

    # --- Study 003: reproduce, then the NW factor, the product-form calibration and IEF's realised volatility ---
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
    calib = math.sqrt(w003 * (1 - w003)) * rms(x) / sd(d)
    sigma_ief = sd(x) * math.sqrt(12)

    # --- Study 004: reproduce power_next's three rms figures, then the question's legs ---
    r004 = list(csv.DictReader((ROOT / F004).open()))
    sig = {}
    for a in ("SHY", "IEF", "TLT", "IWM"):
        v = [float(r[a]) for r in r004 if r[a]]
        sig[a] = (rms(v), len(v), min(v), max(v))
    for a, pub in PUB_NEXT.items():
        if abs(sig[a][0] - pub) > 0.00005:
            sys.exit(f"004: recomputed rms {a} {sig[a][0]:.4%} does not match power_next's {pub:.2%}")
    dates = [r["signal_date"] for r in r004]
    if dates[0] != FIRST_SIGNAL or len(r004) != N_004 + 1:
        sys.exit(f"004 signal file: first date {dates[0]}, {len(r004)} rows; expected {FIRST_SIGNAL} and {N_004 + 1}")
    ratio = sigma_ief / sig["IEF"][0]
    proxy = {a: sig[a][0] * ratio for a in LEGS}

    sharpe_mde = K * nw_factor * 0.5 / math.sqrt(12 * N_004)
    out = [
        "Agenda question 4: minimum detectable edge of volatility management on the approved ETFs, committed before the",
        "question is fixed or retired (inputs: committed result files of Studies 003 and 004 only; nothing fetched, no managed",
        "book computed)",
        "",
        "Anchors reproduced before anything is reported",
        f"  003 in-sample: {n003} months, NW t {t003:.2f} (published {PUB_003['t']}), w {w003:.3f} (published {PUB_003['w']});"
        f" NW / i.i.d. {nw_factor:.3f}; product form / actual {calib:.3f}; IEF excess-return volatility {sigma_ief:.2%} a year",
        f"  004 signal_vol rms (power_next.txt): SHY {sig['SHY'][0]:.2%}, IEF {sig['IEF'][0]:.2%}, TLT {sig['TLT'][0]:.2%}"
        f" (published {PUB_NEXT['SHY']:.2%}, {PUB_NEXT['IEF']:.2%}, {PUB_NEXT['TLT']:.2%})",
        f"  calibration: 003 realised IEF / 004 ex-ante IEF = {ratio:.3f}",
        "",
        "Test: long-only book w_t x leg + (1 - w_t) x bills, 0 <= w_t <= 1, against B3 = w-bar x leg held throughout;",
        f"C2 bar (NW t >= 2.0) at 80% power over Study 004's {N_004} in-sample months; MDE = K x nw x sd(w) x sigma_leg / sqrt(12 N).",
        "",
        f"In Sharpe units of the leg (leg-independent), worst case sd(w) = 0.5: {sharpe_mde:.3f}",
        "",
        "  leg   trailing vol (004, rms; min-max)   proxy sigma   MDE sd 0.5 cons.   calib.   sd(w) for 2%/yr   months for 2%/yr at sd 0.5",
    ]
    for a in LEGS:
        s = proxy[a]
        m = mde(s, 0.5, N_004, nw_factor)
        sd_bar = 0.5 * BAR / m
        out.append(
            f"  {a:<4}  {sig[a][0]:>6.2%} ({sig[a][2]:.1%}-{sig[a][3]:.1%}, n {sig[a][1]})       {s:>6.2%}"
            f"        {m:>6.2%}          {m / calib:>6.2%}        {sd_bar:>5.3f}              {months_for(BAR, s, 0.5, nw_factor):>6.0f}"
        )
    m_iwm = mde(proxy["IWM"], 0.5, N_004, nw_factor)
    out += [
        "",
        "Reading (inferred from the figures above; no managed return computed):",
        f"  - Equities: at the worst-case dispersion the C2 test on IWM can see about {m_iwm:.2%} a year, far above the 2% bar;",
        f"    it clears the bar only if the weight's sd stays below {0.5 * BAR / m_iwm:.3f}, and a weight that moves that little can",
        "    carry only a proportionally small edge, so in Sharpe units the test is no stronger (the 007 caveat). SPY's volatility is",
        "    not committed; it is lower than a small-cap ETF's (inferred), which would lower the return figure, not the Sharpe one.",
        f"  - Treasuries: IEF {mde(proxy['IEF'], 0.5, N_004, nw_factor):.2%} and TLT {mde(proxy['TLT'], 0.5, N_004, nw_factor):.2%}"
        " a year at sd 0.5 (power_next.txt gave 2.20% and 4.55% over 185 months); neither clears the bar",
        f"    at the worst case under the conservative form. IEF clears it at sd(w) <= {0.5 * BAR / mde(proxy['IEF'], 0.5, N_004, nw_factor):.3f}"
        f" and on the calibrated figure ({mde(proxy['IEF'], 0.5, N_004, nw_factor) / calib:.2%}), so a",
        "    volatility-managed IEF is the one form of the question inside the bar; its only window, IEF 2003-2018, is the one",
        "    Studies 003 and 005 already tested trend exits on (and Study 006's gate compared its synthetic leg with).",
        "  - No untouched window: 2019-2026 is spent for IWM, IEF and TLT (Study 004's out-of-sample run, METHODS section 2.5).",
        "    A long equity history needs index data outside the approved ETF universe, and long US market histories are the kind",
        "    of sample the papers it tests used [MM17, COWY20], so a run there would largely re-measure published work (inferred).",
        "  - The desk's no-margin rule caps w at 1, so a managed book can only de-risk below full exposure; the scaling up in calm",
        "    months that the published volatility-managed portfolios allow is not available here (inferred from their design).",
        "Assumptions stated now: the NW/i.i.d. factor and the product form carry over from Study 003 (for a weight set from",
        "trailing volatility, w and the leg's variance are not independent, so the product form may misstate the dispersion in",
        "either direction; not measured); leg volatilities are ex-ante proxies calibrated on IEF, not realised monthly figures.",
    ]
    text = "\n".join(out) + "\n"
    sys.stdout.write(text)
    if args.out:
        (ROOT / args.out).write_text(text)


if __name__ == "__main__":
    main()
