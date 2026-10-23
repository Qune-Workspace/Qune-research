"""Post-hoc, descriptive: why T1's out-of-sample bootstrap confidence intervals
are NaN in ``results/oos/summary.json``, and what they are once the degenerate
resamples are dropped.  Written after the single out-of-sample run; nothing in
``results/`` is changed by this script and nothing here has decision weight.

Cause: out-of-sample, T1 held BIL in 55 of 93 months, in one run of 42 months
(2021-02 to 2024-07).  Its excess return over B0 (actual BIL) is exactly zero
in those months.  A bootstrap resample drawn only from zero-excess months has
zero variance and an undefined Sharpe ratio; ``numpy.quantile`` of a vector
containing NaN is NaN, so the stationary-bootstrap interval (§9.3 item 8) and
the Ledoit-Wolf interval (item 9) came out NaN for T1 while the point
estimates, t-statistics and p-values (which count finite extremes only) are
unaffected.  The §9.3 statistics were designed for strategies whose excess
return is never identically zero; a strategy that is mostly in the cash
benchmark breaks that assumption.  This is a limitation of the inherited
statistic, disclosed here, not a correction of a result.

Usage (from the study folder): ``python posthoc_bootstrap_nan.py``.  Writes
``results/oos/posthoc_bootstrap_nan.{json,md}``.
"""
from __future__ import annotations

import json
import math
import warnings

import numpy as np
import pandas as pd
from src import stats
from src.config import BOOTSTRAP_BLOCK_MONTHS, BOOTSTRAP_RESAMPLES, NEWEY_WEST_LAGS, RESULTS_DIR, SEED

OOS_DIR = RESULTS_DIR / "oos"


def sharpe_ci_dropping_degenerate(excess: np.ndarray, rng: np.random.Generator) -> dict:
    idx = stats.stationary_bootstrap_indices(rng, len(excess), BOOTSTRAP_RESAMPLES, BOOTSTRAP_BLOCK_MONTHS)
    samples = excess[idx]
    sd = samples.std(axis=1, ddof=1)
    finite = sd > 0
    sr = samples[finite].mean(axis=1) / sd[finite] * math.sqrt(stats.MONTHS_PER_YEAR)
    lo, hi = np.quantile(sr, [0.025, 0.975])
    return {"degenerate_resamples": int((~finite).sum()), "resamples": BOOTSTRAP_RESAMPLES,
            "ci_low": float(lo), "ci_high": float(hi)}


def ledoit_wolf_dropping_degenerate(r1: np.ndarray, r2: np.ndarray, rng: np.random.Generator) -> dict:
    n = len(r1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        diff, se = stats._sharpe_difference_and_se(r1[None, :], r2[None, :], NEWEY_WEST_LAGS)
        diff, se = float(diff[0]), float(se[0])
        idx = stats.circular_block_indices(rng, n, BOOTSTRAP_RESAMPLES, BOOTSTRAP_BLOCK_MONTHS)
        d_star, se_star = stats._sharpe_difference_and_se(r1[idx], r2[idx], NEWEY_WEST_LAGS)
    t_star = (d_star - diff) / se_star
    finite = np.isfinite(t_star)
    lo, hi = np.quantile(t_star[finite], [0.025, 0.975])
    root = math.sqrt(stats.MONTHS_PER_YEAR)
    return {"degenerate_resamples": int((~finite).sum()), "resamples": BOOTSTRAP_RESAMPLES,
            "diff_annual": diff * root, "ci_low_annual": (diff - hi * se) * root, "ci_high_annual": (diff - lo * se) * root,
            "p_value_finite_only": float((np.abs(t_star[finite]) >= abs(diff / se)).mean())}


def main() -> None:
    monthly = pd.read_csv(OOS_DIR / "monthly_base.csv", index_col=0)
    summary = json.loads((OOS_DIR / "summary.json").read_text(encoding="utf-8"))
    excess = (monthly["T1"] - monthly["B0"]).to_numpy()
    zero_months = int((excess == 0).sum())
    out = {"T1_excess_exactly_zero_months": zero_months, "months": int(len(excess)),
           "sharpe_ci_as_published": summary["cost_cases"]["base"]["inference"]["T1"]["sharpe_ci"],
           "ledoit_wolf_vs_B3_as_published": summary["cost_cases"]["base"]["inference"]["T1"]["vs_B3"]["ledoit_wolf"]}
    # The run drew one generator per cost case and consumed it in the order
    # sharpe_ci(T1), LW(T1 vs B1), LW(T1 vs B3), then T2, T3.  The same order
    # is replayed here so that the resamples are the ones the run used.
    rng = np.random.default_rng(SEED)
    out["sharpe_ci_finite_resamples"] = sharpe_ci_dropping_degenerate(excess, rng)
    b1 = (monthly["B1"] - monthly["B0"]).to_numpy()
    b3 = (monthly["B3"] - monthly["B0"]).to_numpy()
    out["ledoit_wolf_vs_B1_finite_resamples"] = ledoit_wolf_dropping_degenerate(excess, b1, rng)
    out["ledoit_wolf_vs_B3_finite_resamples"] = ledoit_wolf_dropping_degenerate(excess, b3, rng)
    (OOS_DIR / "posthoc_bootstrap_nan.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    ci, lw = out["sharpe_ci_finite_resamples"], out["ledoit_wolf_vs_B3_finite_resamples"]
    lines = ["# Post-hoc: NaN bootstrap intervals for T1 out-of-sample (descriptive, no decision weight)", "",
             f"T1's excess return over B0 is exactly zero in {zero_months} of {len(excess)} out-of-sample months "
             "(the months it held BIL, which is B0). Resamples drawn only from those months have zero variance and an "
             "undefined Sharpe ratio, and a quantile over a vector containing NaN is NaN. The point estimates, "
             "t-statistics and p-values in `summary.json` are unaffected.", "",
             "| Statistic | As published | Dropping degenerate resamples |", "|---|---|---|",
             f"| Stationary-bootstrap 95% CI of T1's annualised Sharpe | NaN, NaN | [{ci['ci_low']:.3f}, {ci['ci_high']:.3f}] "
             f"({ci['degenerate_resamples']} of {ci['resamples']} resamples dropped) |",
             f"| Ledoit-Wolf 95% CI of the annualised Sharpe difference, T1 - B3 | NaN, NaN | "
             f"[{lw['ci_low_annual']:.3f}, {lw['ci_high_annual']:.3f}] ({lw['degenerate_resamples']} dropped; "
             f"p = {lw['p_value_finite_only']:.3f} on finite resamples, {out['ledoit_wolf_vs_B3_as_published']['p_value']:.3f} as published) |",
             "", "Nothing in `results/oos/summary.json` or the CSVs was changed. A successor study should define the "
             "Sharpe ratio of a resample with zero variance (or exclude such resamples by a rule) before running."]
    (OOS_DIR / "posthoc_bootstrap_nan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
