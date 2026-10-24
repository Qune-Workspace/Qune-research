#!/usr/bin/env python3
"""Deflated Sharpe ratios of Studies 003-005 at the programme-level trial count
of their signal family (post hoc, descriptive, no decision weight).

Usage: python3 tools/tsmom_family_dsr.py [--out tools/tsmom_family_dsr.txt]

Added 2026-10-24 after the cold read (COLD_READ.md, point 5): each study reset N
to its own registered trials, although the desk had tried the same 12-month
time-series momentum signal before. This script counts every trial of that
family whose return was seen, in the desk's internal registry and in the public
studies, up to and including each study, and recomputes the study's deflated
Sharpe ratio at that N.

Inputs are the committed `results/*/summary.json` files only. For each study,
trial and window the file stores the monthly Sharpe ratio SR, the probabilistic
Sharpe ratio PSR against zero, and the variance V across the registered trials
(after the study's variance floor). Because PSR = Phi(SR * c) and
DSR(N) = Phi((SR - SR*(N)) * c) with the same c, DSR(N) = Phi(Phi^-1(PSR) *
(1 - SR*(N) / SR)), where SR*(N) is the Bailey and Lopez de Prado expected
maximum used by every study. The script first reproduces every committed DSR
(at the study's N and at N = 10) from those three numbers and stops if any
differs by more than 1e-9; only then does it compute the family-N figures.

V stays each study's own: the family's other trials ran on other assets and
windows, so their Sharpe spread is not measured on a common sample. A larger
spread would raise SR* and lower every figure below. Standard library only.
"""
import argparse
import json
import math
import sys
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parent.parent
EULER_GAMMA = 0.5772156649015329
PHI = NormalDist()

# Trials whose return was seen, in time order. "narrow": the signal is the sign
# of an asset's own trailing 12-month return, used alone (incl. the 12-1 skip
# and Study 005's regime-conditioned use of Study 003's T1). "broad": any
# time-series trend timing rule on an asset's own past (any lookback, moving
# average, blend). Internal ids are rows of the desk's private trial registry
# (trials.jsonl); they are not in this repository.
FAMILY = [
    # (when, where, ids, count, narrow?)
    ("2026-10-18", "desk TRD-11 round 2, crypto daily TSMOM, 480-bar lookback", "TR-00506", 1, False),
    ("2026-10-19", "desk EQ-03, 12-month TSMOM on SPY, QQQ, IWM, DIA and their portfolio, 2017-2026", "TR-00480..00484", 5, True),
    ("2026-10-20", "desk TRD-46, the same five, 1994-2015", "TR-00508..00512", 5, True),
    ("2026-10-22", "Study 003 T1 (12-month) and T2 (12-1)", "trials.md", 2, True),
    ("2026-10-22", "Study 003 T3 (10-month moving average)", "trials.md", 1, False),
    ("2026-10-22", "Study 004 T1 (12-month, vol-scaled)", "trials.md", 1, True),
    ("2026-10-22", "Study 004 T2-T4 (6-month, 3-month, blend)", "trials.md", 3, False),
    ("2026-10-23", "Study 005 T1-T3 (Study 003's T1 exit, three regime variables)", "trials.md", 3, True),
]
NOT_COUNTED = ("Channel-breakout rules on crypto 1-hour and 4-hour bars (desk registry: 18 rows "
               "'donchian-trend-1h', TR-00505, TR-00507) are trend-following in spirit but a "
               "different signal; adding their 20 rows to the broad family would raise it further. "
               "Correction and audit rows marked NON-TRIAL in the registry are not trials.")

# Cumulative family count up to and including each study (index into FAMILY).
STUDIES = {
    "003": ("research/003-bond-tsmom-ief", 5, [("insample", ("cost_cases", "base")), ("oos", ("cost_cases", "base"))]),
    "004": ("research/004-xasset-trend-voltarget", 7, [("insample", ("runs", "ten", "cost_cases", "base")),
                                                       ("oos", ("runs", "ten", "cost_cases", "base"))]),
    "005": ("research/005-duration-trend-regime", 8, [("insample", ("cost_cases", "base"))]),
}


def expected_max_sharpe(n, v):
    return math.sqrt(v) * ((1.0 - EULER_GAMMA) * PHI.inv_cdf(1.0 - 1.0 / n)
                           + EULER_GAMMA * PHI.inv_cdf(1.0 - 1.0 / (n * math.e)))


def dsr_at(sr, psr, v, n):
    return PHI.cdf(PHI.inv_cdf(psr) * (1.0 - expected_max_sharpe(n, v) / sr))


def counts(upto):
    rows = FAMILY[:upto]
    return sum(r[3] for r in rows if r[4]), sum(r[3] for r in rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args()
    out, checked = [], 0
    out.append("Deflated Sharpe at the programme-level family count (post hoc, descriptive, no decision weight)")
    out.append("")
    out.append("Family trials whose return was seen, in time order:")
    for when, where, ids, n, narrow in FAMILY:
        out.append(f"  {when}  {n:>2}  {'narrow+broad' if narrow else 'broad only  '}  {where} [{ids}]")
    out.append("  " + NOT_COUNTED)
    out.append("")
    out.append("study window    trial  N_study  DSR(N_study)  DSR(10)  N_narrow  DSR(narrow)  N_broad  DSR(broad)  PSR")
    for sid, (folder, upto, windows) in STUDIES.items():
        n_narrow, n_broad = counts(upto)
        for window, path in windows:
            node = json.loads((ROOT / folder / "results" / window / "summary.json").read_text())
            for key in path:
                node = node[key]
            for trial, by_n in node["deflated_sharpe"].items():
                for rec in by_n.values():
                    got = dsr_at(rec["sr_monthly"], rec["psr"], rec["variance_across_trials"], rec["n_trials"])
                    if abs(got - rec["dsr"]) > 1e-9:
                        sys.exit(f"{sid} {window} {trial} N={rec['n_trials']}: recomputed {got!r} != committed {rec['dsr']!r}")
                    checked += 1
                n_study = min(int(k[1:]) for k in by_n)
                own, ten = by_n[f"N{n_study}"], by_n["N10"]
                sr, psr, v = own["sr_monthly"], own["psr"], own["variance_across_trials"]
                out.append(f"{sid}   {window:<9} {trial:<5}  {n_study:>7}  {own['dsr']:>12.3f}  {ten['dsr']:>7.3f}"
                           f"  {n_narrow:>8}  {dsr_at(sr, psr, v, n_narrow):>11.3f}  {n_broad:>7}"
                           f"  {dsr_at(sr, psr, v, n_broad):>10.3f}  {psr:.3f}")
    out.append("")
    out.append(f"Check: {checked} committed DSR values reproduced from (SR, PSR, V, N) to within 1e-9 before any family figure was computed.")
    out.append("Reading: at these N the expected maximum SR* stays small against the trials' own SR, so the DSR stays close "
               "to the PSR, which tests whether the rule's own Sharpe ratio is above zero (largely the asset's premium), "
               "not whether the timing beats a benchmark. Reported descriptively; no verdict depends on it.")
    text = "\n".join(out) + "\n"
    sys.stdout.write(text)
    if args.out:
        (ROOT / args.out).write_text(text)


if __name__ == "__main__":
    main()
