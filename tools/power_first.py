#!/usr/bin/env python3
"""Minimum detectable timing edge of the decision test in Studies 003 and 004,
and the sample a powered successor would need (post hoc, descriptive).

Usage: python3 tools/power_first.py [--out tools/power_first.txt]

Added 2026-10-24 after the cold read (COLD_READ.md, point 1). The decision test
of both studies is C2: the Newey-West t of the mean monthly differential
between the rule (T1) and its exposure-matched benchmark (003: B3; 004: B4) must
reach 2.0. This script reads the committed in-sample monthly files, recomputes
that t with the studies' convention (Bartlett weights, 6 lags) and stops unless
it matches the published C2 value to 0.005. It then reports, from the same
standard error, the edge the test would detect with 80% power, both at a
one-sided 5% level and at the C2 bar itself, and how many months a design with
the same dispersion would need to bring that edge down to 2% and 1% a year.

The standard error uses the dispersion of the differential, not its mean, so
the minimum detectable effect does not depend on the result. It is still
computed after the result was seen, which is why it is labelled post hoc: the
rule adopted on 2026-10-24 (RESEARCH_AGENDA.md) is that the next study commits
this figure before its question is fixed. Standard library only.
"""
import argparse
import csv
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
Z_ONE_SIDED_5, Z_POWER_80, C2_BAR = 1.645, 0.842, 2.0
LAGS = 6
CASES = [
    # (label, file, rule, benchmark, published C2 t)
    ("003 in-sample, T1 - B3", "research/003-bond-tsmom-ief/results/insample/monthly_base.csv", "T1", "B3", 0.37),
    ("004 in-sample, T1 - B4", "research/004-xasset-trend-voltarget/results/insample/monthly_10assets_base.csv",
     "T1", "B4", 0.65),
]


def newey_west_se(x, lags):
    n = len(x)
    m = sum(x) / n
    e = [v - m for v in x]
    s = sum(v * v for v in e) / n
    for lag in range(1, lags + 1):
        s += 2.0 * (1.0 - lag / (lags + 1.0)) * sum(e[t] * e[t - lag] for t in range(lag, n)) / n
    return math.sqrt(s / n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args()
    out = ["Minimum detectable timing edge of the C2 test (post hoc, descriptive, no decision weight)", "",
           "case                      months  NW t (published)  MDE 5%/80%  MDE at C2 bar  months for 2%/yr  months for 1%/yr"]
    for label, path, rule, bench, published in CASES:
        rows = list(csv.DictReader((ROOT / path).open()))
        d = [float(r[rule]) - float(r[bench]) for r in rows]
        n = len(d)
        se = newey_west_se(d, LAGS)
        t = (sum(d) / n) / se
        if abs(t - published) > 0.005:
            sys.exit(f"{label}: recomputed NW t {t:.4f} does not match the published {published}")
        mde = (Z_ONE_SIDED_5 + Z_POWER_80) * se * 12
        mde_c2 = (C2_BAR + Z_POWER_80) * se * 12
        # se scales with 1/sqrt(n) at fixed dispersion: months needed for the C2-bar MDE to reach a target
        need = {target: math.ceil(n * (mde_c2 / target) ** 2) for target in (0.02, 0.01)}
        out.append(f"{label:<25} {n:>6}  {t:>6.2f} ({published:.2f})  {mde:>9.2%}  {mde_c2:>12.2%}"
                   f"  {need[0.02]:>16}  {need[0.01]:>16}")
    out += ["",
            "MDE = (z + 0.842) x NW standard error of the mean monthly differential x 12; z = 1.645 (one-sided 5%) or 2.0 (the C2 bar).",
            "Months needed assume the differential keeps the same dispersion and autocorrelation; a longer history is a different sample.",
            "Reading: each test could detect a timing edge of about 1.7% a year over its exposure-matched benchmark with 80% power;",
            "an edge of 1% a year, or less, would usually have been missed. Study 005's in-sample MDE (4.4% a year) is in its own",
            "results/checks/d3.json and is not recomputed here."]
    text = "\n".join(out) + "\n"
    sys.stdout.write(text)
    if args.out:
        (ROOT / args.out).write_text(text)


if __name__ == "__main__":
    main()
