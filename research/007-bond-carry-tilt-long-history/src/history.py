"""Study 006 history run (PREREGISTRATION.md §8.1, §9): once, after a passed
gate (§5.3) and a written volatility check (§5.4); §14 step 7.

The engine is Study 002's ``report.run_window``, copied unchanged: T1-T3 and
B0-B3 on the 593 test periods with the synthetic legs, base and stress costs,
the twelve metrics, Newey-West and Ledoit-Wolf tests, the bootstrap interval,
the DSR at N = 3 and N = 10, the mechanism check and Study 001's sub-periods.
This module adds only what Study 006 changes: the §9.5 verdict table (gate,
fragility and volatility rows), the §8.1 sub-windows, the observed Newey-West
to i.i.d. ratio beside the assumed one (§5.4, §9.6) and the DSR at the
programme-level family count (§9.4, descriptive).

    python -m src.history    # writes results/history/ once
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import backtest, report, stats
from .calendar import build_schedule
from .config import COST_CASES, N_TRIALS_REGISTERED, STUDY_DIR, SUBPERIODS, TRIAL_IDS
from .config006 import (
    ASSUMED_NW_IID_RATIO,
    GATE_DIR,
    HISTORY_DIR,
    LOW_POWERED_SWITCHES,
    PROGRAMME_FAMILY,
    SUB_WINDOWS,
    TEST_FIRST_SIGNAL_MONTH,
    TEST_LAST_SIGNAL_MONTH,
    TEST_PERIODS,
    VOL_BAR,
    VOLCHECK_DIR,
)
from .synthetic import synthetic_indices
from .volcheck import gate_passed

GATE_LABEL = "gate redesigned after Study 002's halt (cold read, point 7)"


def strategy_results(
    indices: dict[str, pd.Series], fred: dict[str, pd.Series], schedule: pd.DataFrame, weight_b3: float, cost: float
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """The same steps as ``report.run_window`` for one cost case, returning the
    frames it keeps internal (tests check the two agree period by period)."""
    signals = report.trial_signals(fred, schedule)
    returns = backtest.instrument_returns(indices, schedule)
    results = backtest.benchmarks(returns, weight_b3, cost)
    for t in TRIAL_IDS:
        targets = report.targets_for_periods(signals[t], schedule)
        results[t] = backtest.run_switching(targets, returns.loc[targets.index], cost)
    return results, returns


def subwindow_metrics(
    results: dict[str, pd.DataFrame],
    returns: pd.DataFrame,
    schedule: pd.DataFrame,
    windows: dict[str, tuple[str, str]],
) -> dict:
    """§8.1 descriptives for every strategy, by the calendar month of each
    period's execution date (the month the holding period starts).  Study
    002's ``report.subperiod_metrics`` compares the schedule's index, which is
    the signal month, one month earlier (§16, 2026-10-25 03:3x); this function
    is used for 006's sub-windows and for Study 001's sub-periods alike."""
    start_month = schedule["execution_date"].dt.to_period("M")
    out = {}
    for name, (first, last) in windows.items():
        lo, hi = pd.Period(first, "M"), pd.Period(last, "M")
        sliced = {}
        for k, f in results.items():
            m = start_month.reindex(f.index)
            sliced[k] = f[((m >= lo) & (m <= hi)).to_numpy()]
        out[name] = {
            k: report.descriptive_metrics(f, sliced["B0"]["r"], returns) for k, f in sliced.items() if len(f) > 1
        }
    return out


def nw_iid_ratio(diff: pd.Series, lags: int | None = None) -> dict[str, float]:
    """Newey-West standard error of the mean over the i.i.d. one (sd / sqrt n,
    ddof 1): the factor the power file assumed to be 0.972 (§5.4)."""
    nw = stats.newey_west_mean(diff) if lags is None else stats.newey_west_mean(diff, lags)
    y = np.asarray(diff, dtype=float)
    iid = float(np.std(y, ddof=1) / np.sqrt(len(y)))
    return {"nw_se": nw["se"], "iid_se": iid, "ratio": nw["se"] / iid, "assumed": ASSUMED_NW_IID_RATIO}


def family_count(family: tuple = PROGRAMME_FAMILY) -> int:
    return int(sum(row[3] for row in family))


def family_dsr(desc: dict, variance: float, n_family: int) -> dict[str, dict]:
    """DSR of each trial at the programme-level family count (§9.4), with the
    study's own variance across trials, as ``tools/tsmom_family_dsr.py``."""
    return {
        t: stats.deflated_sharpe(
            desc[t]["sharpe_monthly"],
            desc[t]["periods"],
            desc[t]["skewness_excess"],
            desc[t]["kurtosis_excess"],
            n_family,
            variance,
        )
        for t in TRIAL_IDS
    }


def history_verdict(gate_ok: bool, c_t1: dict[str, bool], c_others: dict[str, dict[str, bool]], sigma: float) -> str:
    """§9.5, precedence: not supported > inconclusive (either kind) >
    consistent > supported.  A failed gate means no rule return exists, so it
    is checked first; the module refuses to run without a passed gate anyway."""
    if not gate_ok:
        return "inconclusive (gate)"
    if not all(c_t1.values()):
        return "not supported"
    if not all(all(c.values()) for c in c_others.values()):
        return "inconclusive (fragile)"
    if sigma > VOL_BAR:
        return "consistent with an edge, not detectable at the 2% bar"
    return "supported in history; forward record pending"


def labels(sigma: float, t1_switches: int) -> list[str]:
    """First-paragraph labels the note must carry (§5.4, §8.1, §9.5)."""
    out = [GATE_LABEL]
    if sigma > VOL_BAR:
        out.append("low-power check")
    if t1_switches < LOW_POWERED_SWITCHES:
        out.append("low-powered")
    return out


def compute(
    fred: dict[str, pd.Series],
    first_month: str,
    last_month: str,
    sigma: float,
    out_dir: Path,
    expected_periods: int | None = None,
) -> dict:
    """The history run on whatever window is given (the test window from
    ``main``; toy windows from the tests)."""
    schedule = build_schedule(fred["DGS10"], fred["DTB3"], first_month, last_month)
    if expected_periods is not None and len(schedule) - 1 != expected_periods:
        raise ValueError(f"{len(schedule) - 1} test periods, expected {expected_periods}")
    indices = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    summary = report.run_window(
        "1969-2018 test window, synthetic instruments",
        indices,
        fred,
        schedule,
        None,
        out_dir,
        with_subperiods=True,
        with_daily=False,
    )
    weight = summary["weight_b3"]
    cases = summary["cost_cases"]
    base, stress = cases["base"], cases["stress"]
    criteria = {
        t: report.insample_criteria(
            base["descriptive"],
            base["inference"],
            base["deflated_sharpe"],
            stress["descriptive"],
            stress["inference"],
            t,
        )
        for t in TRIAL_IDS
    }
    n_family = family_count()
    t1_switches = None
    for case, cost in COST_CASES.items():
        results, returns = strategy_results(indices, fred, schedule, weight, cost)
        if case == "base":
            t1_switches = int(results["T1"]["switched"].sum())
        cases[case]["sub_windows"] = subwindow_metrics(results, returns, schedule, SUB_WINDOWS)
        cases[case]["subperiods_by_execution_month"] = subwindow_metrics(results, returns, schedule, SUBPERIODS)
        cases[case]["nw_iid_ratio_vs_B3"] = {
            t: nw_iid_ratio(results[t]["r"] - results["B3"]["r"].reindex(results[t].index)) for t in TRIAL_IDS
        }
        cases[case]["deflated_sharpe_programme_family"] = {
            "n_family": n_family,
            "rows": [list(row) for row in PROGRAMME_FAMILY],
            "no_decision_weight": True,
            "dsr": family_dsr(
                cases[case]["descriptive"], cases[case]["deflation_inputs"]["variance_across_trials"], n_family
            ),
        }
    summary.update(
        {
            "study": "006",
            "section": "PREREGISTRATION.md §8.1, §9",
            "criteria": criteria["T1"],
            "criteria_T2_T3": {t: criteria[t] for t in ("T2", "T3")},
            "sigma_from_volcheck": sigma,
            "t1_switches": t1_switches,
            "verdict_T1": history_verdict(True, criteria["T1"], {t: criteria[t] for t in ("T2", "T3")}, sigma),
            "labels": labels(sigma, t1_switches),
            "n_trials_decision": N_TRIALS_REGISTERED,
        }
    )
    return summary


def write_verdict(summary: dict, out_dir: Path) -> None:
    base = summary["cost_cases"]["base"]
    lines = [
        "# Study 006 history run (§8.1, §9), run once",
        "",
        f"**Verdict for T1: {summary['verdict_T1']}** ({'; '.join(summary['labels'])}).",
        "",
        "| Trial | C1 | C2 | C3 | C4 | Sharpe | NW t vs B3 | DSR N=3 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    all_criteria = {"T1": summary["criteria"], **summary["criteria_T2_T3"]}
    for t in TRIAL_IDS:
        c = all_criteria[t]
        lines.append(
            f"| {t} | {c['C1']} | {c['C2']} | {c['C3']} | {c['C4']} | "
            f"{base['descriptive'][t]['sharpe_annual']:.3f} | {base['inference'][t]['vs_B3']['newey_west']['t']:.2f} | "
            f"{base['deflated_sharpe'][t][f'N{N_TRIALS_REGISTERED}']['dsr']:.3f} |"
        )
    lines += [
        "",
        f"B1 Sharpe {base['descriptive']['B1']['sharpe_annual']:.3f}, B3 Sharpe "
        f"{base['descriptive']['B3']['sharpe_annual']:.3f} at frozen w {summary['weight_b3']:.4f}; "
        f"{summary['holding_periods']} periods; T1 switches {summary['t1_switches']}; "
        f"sigma {summary['sigma_from_volcheck']:.2%} (bar {VOL_BAR:.2%}).",
        "",
        f"Observed NW/iid ratio for T1 − B3: {base['nw_iid_ratio_vs_B3']['T1']['ratio']:.3f} "
        f"(assumed {ASSUMED_NW_IID_RATIO}). Programme-level family count "
        f"{base['deflated_sharpe_programme_family']['n_family']} (descriptive).",
        "",
        f"Run {summary['run_at_utc']}, code {summary['provenance']['git_commit'][:7]}.",
        "",
    ]
    (out_dir / "verdict.md").write_text("\n".join(lines))
    print("\n".join(lines))


def main(
    argv: list[str] | None = None,
    gate_dir: Path = GATE_DIR,
    volcheck_dir: Path = VOLCHECK_DIR,
    out_dir: Path = HISTORY_DIR,
) -> int:
    argparse.ArgumentParser(description="Study 006 history run (§8.1, §9), once.").parse_args(argv)
    if not gate_passed(gate_dir):
        raise SystemExit("refused: results/gate/gate.json does not record a passed gate (§5.3.6, §14 step 7)")
    vol_path = volcheck_dir / "volcheck.json"
    if not vol_path.exists():
        raise SystemExit("refused: results/volcheck/volcheck.json is missing (§5.4 runs before any rule return)")
    if out_dir.exists():
        raise SystemExit(f"refused: {out_dir.name}/ exists; the history run is executed once (§8.1)")
    sigma = float(json.loads(vol_path.read_text())["sigma_annual"])
    summary = compute(
        report.load_fred(),
        TEST_FIRST_SIGNAL_MONTH,
        TEST_LAST_SIGNAL_MONTH,
        sigma,
        out_dir,
        expected_periods=TEST_PERIODS,
    )
    summary["run_at_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary["provenance"] = report.provenance()
    report.write_json(out_dir / "summary.json", summary)
    write_verdict(summary, out_dir)
    print(f"history written to {out_dir.relative_to(STUDY_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
