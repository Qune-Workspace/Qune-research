#!/usr/bin/env python3
"""Minimum detectable edge for the agenda refresh of 2026-10-25 (backlog item 7):
new candidate questions on Study 006's frozen 7-10-year leg, each with its
detectable edge committed before any of them is fixed.

Usage: python3 tools/power_refresh.py [--out tools/power_refresh.txt]

The agenda's five questions are exhausted (1 and 3 run as Studies 004 and 005,
2 as Study 007, 5 retired, 4 not fixed; RESEARCH_AGENDA.md dated additions).
The only window inside the 2% a year bar is the long constant-maturity history
on Study 006's gated synthetic leg (tools/power_next.txt), so every candidate
here is a duration-timing rule on that leg and joins the same family. Nothing is
fetched, no new series is read and no signal path is computed: a candidate's
holding weight is unknown, so the worst case sd(w) = 0.5 binds, with the uniform
rank weight (sd 0.2887) beside it for the tilt designs, as Study 007 did.

Inputs are committed result files only, reproduced before anything is reported:

  Study 003  results/insample/monthly_base.csv   NW / i.i.d. factor and the product-form calibration
  Study 006  results/volcheck/volcheck.json      the leg's whole-history excess-return volatility
  Study 007  QUESTION.md section 2.3             1.6% a year / 0.207 Sharpe at sd 0.5 over 534 months

Standard library only; descriptive, no decision weight.
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

from power_first import LAGS, newey_west_se
from power_next import F003, F006V, PUB_003, PUB_006, K, rms, sd

ROOT = Path(__file__).resolve().parent.parent
PUB_007 = {"n": 534, "mde": 0.016, "sharpe": 0.207}  # Study 007 QUESTION.md section 2.3
SD_WORST = 0.5
SD_UNIFORM = math.sqrt(1 / 12)  # a weight spread evenly over [0, 1]
BAR = 0.02
FAMILY_NOW = 14  # Study 007 PREREGISTRATION section 9.4, re-counted at 14 before its history run: 003's 3, 005's 3, 006's 3, 007's 5
FORWARD_N = 60  # the forward records of 006 and 007 are scored once at 60 months

# name, design, first decision month (by construction of its inputs, stated now), periods to 2018-12, own trials, tilt?
CANDIDATES = [
    ("V", "bond value tilt: weight = expanding rank (min 60 months) of the real yield, DGS10 less trailing 12-month CPI inflation",
     "1974-07", 534, 3, True),
    ("F", "forward-rate factor: sign of an expanding-window (min 60 months) forecast of the leg's 12-month excess return from the curve's forward rates",
     "1975-07", 522, 2, False),
    ("P", "policy-cycle switch: hold the leg unless the 3-month bill yield rose over the past 6 months",
     "1969-08", 593, 1, False),
    ("I", "inflation-trend switch: hold the leg unless trailing 12-month CPI inflation is above its level 12 months earlier",
     "1969-08", 593, 1, False),
]


def mde_sd(sigma_annual, sd_w, n, nw_factor):
    """Annual C2-bar MDE with the weight's sd given directly (sqrt(w(1-w)) for a switch)."""
    return K * nw_factor * sd_w * (sigma_annual / math.sqrt(12)) / math.sqrt(n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args()

    # --- Study 003: reproduce, then the NW factor and the product-form calibration ---
    r003 = list(csv.DictReader((ROOT / F003).open()))
    n003 = len(r003)
    d = [float(r["T1"]) - float(r["B3"]) for r in r003]
    x = [float(r["B1"]) - float(r["B0"]) for r in r003]
    w003 = sum(1.0 for r in r003 if r["T1_holding"] == "IEF") / n003
    se_nw = newey_west_se(d, LAGS)
    t003 = (sum(d) / n003) / se_nw
    if abs(t003 - PUB_003["t"]) > 0.005 or abs(w003 - PUB_003["w"]) > 0.0005:
        sys.exit(f"003: recomputed t {t003:.4f} / w {w003:.4f} do not match the published {PUB_003}")
    nw = se_nw / (sd(d) / math.sqrt(n003))
    calib = math.sqrt(w003 * (1 - w003)) * rms(x) / sd(d)

    # --- Study 006: the leg's volatility; Study 007: its committed MDE at 534 months ---
    sigma = json.loads((ROOT / F006V).read_text())["sigma_annual"]
    if abs(sigma - PUB_006["sigma"]) > 0.0005:
        sys.exit(f"006: sigma {sigma:.4f} does not match the published {PUB_006['sigma']}")
    m007 = mde_sd(sigma, SD_WORST, PUB_007["n"], nw)
    s007 = K * nw * SD_WORST / math.sqrt(12 * PUB_007["n"])
    if abs(m007 - PUB_007["mde"]) > 0.0005 or abs(s007 - PUB_007["sharpe"]) > 0.0005:
        sys.exit(f"007: recomputed {m007:.4f} / {s007:.4f} do not match the published {PUB_007}")

    out = [
        "Agenda refresh, 2026-10-25: minimum detectable edge of each new candidate, committed before any is fixed",
        "(inputs: committed result files of Studies 003, 006 and 007 only; nothing fetched, no new series read, no signal path computed)",
        "",
        "Anchors reproduced before anything is reported",
        f"  003 in-sample: {n003} months, NW t {t003:.2f} (published {PUB_003['t']}), w {w003:.3f} (published {PUB_003['w']});"
        f" NW / i.i.d. {nw:.3f}; product form / actual {calib:.3f}",
        f"  006 synthetic 7-10y leg, whole-history excess-return volatility {sigma:.2%} a year (published {PUB_006['sigma']:.2%})",
        f"  007 C2-bar MDE at sd 0.5 over {PUB_007['n']} months: {m007:.2%} a year, {s007:.3f} Sharpe (published 1.6%, 0.207)",
        "",
        "Test for every candidate: T = w_t x leg + (1 - w_t) x bills against B3 = w-bar x leg held throughout, on the leg Study 006",
        "gated (1969-08 to 2018-12); C2 bar (NW t >= 2.0) at 80% power; MDE = K x nw x sd(w) x sigma / sqrt(12 N).",
        "The first decision month follows from each design's own inputs and burn-in, stated before any value is computed.",
        "",
        "  id  first   N    own trials  family after   MDE sd 0.5 cons. (Sharpe)   calib.   MDE uniform rank (Sharpe)   forward 60 m, sd 0.5",
    ]
    for cid, _, first, n, k, tilt in CANDIDATES:
        m = mde_sd(sigma, SD_WORST, n, nw)
        sh = K * nw * SD_WORST / math.sqrt(12 * n)
        u = f"{mde_sd(sigma, SD_UNIFORM, n, nw):.2%} ({K * nw * SD_UNIFORM / math.sqrt(12 * n):.3f})" if tilt else "n/a (switch)"
        out.append(
            f"  {cid:<3} {first}  {n:>3}  {k:>6}      {FAMILY_NOW + k:>6}          {m:.2%} ({sh:.3f})"
            f"              {m / calib:.2%}   {u:<26}  {mde_sd(sigma, SD_WORST, FORWARD_N, nw):.2%}"
        )
    sd_bar = SD_WORST * BAR / mde_sd(sigma, SD_WORST, min(c[3] for c in CANDIDATES), nw)
    out += [
        "",
        "Designs (fixed only by a later question note; listed so the figures above can be checked against them):",
    ]
    out += [f"  {cid}  {desc}" for cid, desc, *_ in CANDIDATES]
    out += [
        "",
        "Reading (inferred from the figures above; no candidate's return or signal computed):",
        f"  - All four clear the 2% a year bar at the worst case (largest {max(mde_sd(sigma, SD_WORST, c[3], nw) for c in CANDIDATES):.2%});"
        f" the bar is reached only at sd(w) {sd_bar:.3f},",
        "    above the 0.5 that any weight in [0, 1] can have, so every design on this leg clears it whatever its weight and the",
        "    bar does not separate them. None reaches 1% a year at the worst case; a rank tilt does at the uniform sd.",
        "  - The bar cannot separate candidates on one leg and one window; what separates them is independence from the",
        "    three signals already run there (spread, carry, 12-month trend), the evidence behind each, and how few trials each adds.",
        f"  - Every candidate joins the same family (now {FAMILY_NOW}); the window is in-sample for the family, as for Study 007.",
        f"  - Each forward record alone is low-powered ({mde_sd(sigma, SD_WORST, FORWARD_N, nw):.2%} a year at 60 months, sd 0.5).",
        "Assumptions stated now: the NW/i.i.d. factor and the product form carry over from Study 003; the leg's volatility over",
        "each shorter window equals its 593-month figure until a data step measures it; the family count is Study 007's",
        "(PREREGISTRATION section 9.4: 003, 005 and 006 three each, 007 five) and is re-counted before any run; any addition raises it.",
    ]
    text = "\n".join(out) + "\n"
    sys.stdout.write(text)
    if args.out:
        (ROOT / args.out).write_text(text)


if __name__ == "__main__":
    main()
