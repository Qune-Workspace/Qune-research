"""Post-hoc multiple-testing report for Study 004's four trials
(library ``qune_research.multiple``).

Built on 2026-10-23, after the study's results and its independent review,
so it carries no decision weight and changes nothing in ``results/``: it
reads the committed monthly holding-period returns and metrics and asks
one question the pre-registration did not: taking the four trials T1–T4 as
a family, does the best of them beat the decisive benchmark B4 (and B3)
once the search over four lookbacks is accounted for, by White's (2000)
Reality Check and Hansen's (2005) SPA test with the stationary bootstrap?
Beside it, the minimum track-record length (Bailey and Lopez de Prado,
2012): how many months of T1's record would be needed to be 95 percent
confident that its Sharpe ratio exceeds zero, and exceeds B4's.

Settings, chosen once before the run and not varied: 10,000 stationary-
bootstrap resamples with a 12-month expected block (the study's own §9.3
values), seed 20261023 drawn once per test call in a fixed order.

Run from the study folder: ``python multiple/spa_report.py``.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

STUDY_DIR = Path(__file__).resolve().parents[1]
ROOT = STUDY_DIR.parents[1]
sys.path.insert(0, str(ROOT))

from qune_research import multiple as mt  # noqa: E402

OUT = STUDY_DIR / "multiple"
SEED = 20261023
RESAMPLES = 10_000
BLOCK = 12
TRIALS = ["T1", "T2", "T3", "T4"]
BENCHMARKS = ["B4", "B3"]
CASES = [("insample", "10assets"), ("insample", "9assets"), ("oos", "10assets"), ("oos", "9assets")]


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                              cwd=STUDY_DIR).stdout.strip()
    except Exception:  # pragma: no cover
        return "unknown"


def main() -> None:
    rng = np.random.default_rng(SEED)
    report = {"built": pd.Timestamp.now(tz="Europe/London").isoformat(timespec="minutes"),
              "commit_before_run": git_commit(), "seed": SEED, "resamples": RESAMPLES,
              "expected_block_months": BLOCK, "trials": TRIALS, "cases": {}}
    rows = []
    for window, universe in CASES:
        monthly = pd.read_csv(STUDY_DIR / "results" / window / f"monthly_{universe}_base.csv")
        metrics = pd.read_csv(STUDY_DIR / "results" / window / f"metrics_{universe}_base.csv", index_col=0)
        case = {"periods": int(len(monthly)), "first_period": monthly["signal_date"].iloc[0],
                "last_period": monthly["signal_date"].iloc[-1], "tests": {}}
        for bench in BENCHMARKS:
            d = monthly[TRIALS].to_numpy() - monthly[[bench]].to_numpy()
            spa = mt.spa_test(d, rng, n_resamples=RESAMPLES, expected_block_length=BLOCK)
            rc = mt.reality_check(d, rng, n_resamples=RESAMPLES, expected_block_length=BLOCK)
            case["tests"][bench] = {"spa": spa, "reality_check": rc}
            rows.append({"window": window, "universe": universe, "benchmark": bench,
                         "best_trial": TRIALS[spa["best_trial"]], "spa_statistic": spa["statistic"],
                         "p_lower": spa["p_lower"], "p_consistent": spa["p_consistent"], "p_upper": spa["p_upper"],
                         "rc_p": rc["p_value"], "kept_negative": spa["trials_kept_negative_consistent"],
                         **{f"t_{k}": t for k, t in zip(TRIALS, spa["trial_t"])},
                         **{f"p_own_{k}": p for k, p in zip(TRIALS, spa["trial_p_individual"])}})
        t1 = metrics.loc["T1"]
        b4 = metrics.loc["B4"]
        case["min_track_record_months"] = {
            "T1_sharpe_monthly": float(t1["sharpe_monthly"]), "B4_sharpe_monthly": float(b4["sharpe_monthly"]),
            "T1_skew": float(t1["skewness_excess"]), "T1_kurtosis": float(t1["kurtosis_excess"]),
            "vs_zero_95": mt.min_track_record_length(float(t1["sharpe_monthly"]), float(t1["skewness_excess"]),
                                                     float(t1["kurtosis_excess"]), 0.0, 0.95),
            "vs_B4_95": mt.min_track_record_length(float(t1["sharpe_monthly"]), float(t1["skewness_excess"]),
                                                   float(t1["kurtosis_excess"]), float(b4["sharpe_monthly"]), 0.95),
            "months_available": int(len(monthly))}
        report["cases"][f"{window}_{universe}"] = case
    pd.DataFrame(rows).to_csv(OUT / "family_tests.csv", index=False)
    (OUT / "report.json").write_text(json.dumps(report, indent=2, default=float) + "\n")
    print(pd.DataFrame(rows)[["window", "universe", "benchmark", "best_trial", "spa_statistic",
                              "p_lower", "p_consistent", "p_upper", "rc_p", "kept_negative"]].to_string(index=False))
    for key, case in report["cases"].items():
        print(key, "MinTRL months:", {k: round(v, 1) if isinstance(v, float) else v
                                       for k, v in case["min_track_record_months"].items()})


if __name__ == "__main__":
    main()
