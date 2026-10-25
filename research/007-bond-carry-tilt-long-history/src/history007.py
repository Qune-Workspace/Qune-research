"""Study 007 history run (PREREGISTRATION.md §8.1, §9): once, after a passed
gate (§5.3) and a written volatility check (§5.4); §14 step 7.

Five weight paths (``gate007.weight_paths``, signals only) run through the
fractional-weight engine (``tilt.run_tilt``) on the test window, T1b on its own
window; each trial against its own exposure-matched B3 at its frozen mean
weight (``backtest.run_static``), B0-B2 common; Study 002's metrics and tests
(``report``, ``stats``) unchanged; the DSR at the programme-level family count
decides C3 (§9.4) with N = 5 and N = 10 beside it; the §9.5 verdict table with
the companion clause for T1 and the turnover label; the §9.6 descriptives
(sub-windows and rate eras by execution month, attribution, mechanism by weight
quintile and by the sign of carry, the observed Newey-West to i.i.d. ratio,
the realised sd of the weight).  Charts (§9.6) are made at the note step from
the committed monthly files, not here.

    python -m src.history007    # writes results/history/ once
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import backtest, report, stats, tilt
from .calendar import build_schedule
from .config import (
    C1_SHARPE_MARGIN,
    C2_T_MIN,
    C3_DSR_MIN,
    CASH_LEG,
    COST_CASES,
    DURATION_LEG,
    N_TRIALS_SENSITIVITY,
    SEED,
    STUDY_DIR,
)
from .config006 import ASSUMED_NW_IID_RATIO
from .config007 import (
    CARRY_FIRST_SIGNAL_MONTH,
    COMPANIONS,
    GATE_DIR,
    HISTORY_DIR,
    LOW_POWERED_TURNOVER,
    MIN_HISTORY,
    PRIMARY,
    PROGRAMME_FAMILY,
    RATE_ERAS,
    SECONDARY,
    SUB_WINDOWS,
    T1B_FIRST_SIGNAL_MONTH,
    T1B_PERIODS,
    TEST_FIRST_SIGNAL_MONTH,
    TEST_LAST_SIGNAL_MONTH,
    TEST_PERIODS,
    TRIAL_IDS,
    VOL_BAR_007,
    VOLCHECK_DIR,
)
from .gate007 import WEIGHT_COLUMNS, weight_paths
from .history import nw_iid_ratio
from .synthetic import synthetic_indices
from .volcheck import gate_passed

N_STUDY = len(TRIAL_IDS)
DISPERSION_REFERENCES = {"sd_0.5_design": 0.5, "uniform_rank_1_over_sqrt12": 1.0 / np.sqrt(12.0)}


def family_count(family: tuple = PROGRAMME_FAMILY) -> int:
    return int(sum(row[3] for row in family))


# --- metrics for a fractional path ------------------------------------------------------------


def tilt_descriptives(frame: pd.DataFrame, r_cash: pd.Series, returns: pd.DataFrame) -> dict:
    """Study 002's twelve metrics on a ``tilt.run_tilt`` frame: the static
    branch of ``report.descriptive_metrics`` at the path's mean weight, then
    the fractional path's own figures (turnover, mean and sd of the weight) in
    place of the switch count, which has no meaning for it (§8.1)."""
    w = frame["weight"]
    out = report.descriptive_metrics(frame.assign(weight_ief=float(w.mean())), r_cash, returns)
    out.pop("switches_per_year")
    out["mean_weight"] = float(w.mean())
    out["sd_weight"] = float(w.std(ddof=0))
    out["turnover_one_way_total"] = tilt.total_turnover(frame)
    out["turnover_per_year"] = out["turnover_one_way_total"] / (len(frame) / stats.MONTHS_PER_YEAR)
    out["fraction_in_ief"] = out["mean_weight"]
    return out


def run_trial(weights: pd.Series, returns: pd.DataFrame, cost: float) -> dict[str, pd.DataFrame]:
    """One trial with its own B3 at its frozen mean weight; B0-B2 common (§9.1)."""
    w_bar = tilt.mean_weight(weights)
    results = backtest.benchmarks(returns, w_bar, cost)
    results["T"] = tilt.run_tilt(weights, returns, cost)
    return results


def criteria(desc: dict, infer: dict, dsr_family: dict, infer_stress: dict) -> dict[str, bool]:
    """C1-C4 of §9.5 for one trial against B1 and its own B3; C3 at the family count."""
    nw = infer["vs_B3"]["newey_west"]
    return {
        "C1": bool(
            desc["T"]["sharpe_annual"] >= desc["B1"]["sharpe_annual"] + C1_SHARPE_MARGIN
            and desc["T"]["sharpe_annual"] >= desc["B3"]["sharpe_annual"] + C1_SHARPE_MARGIN
        ),
        "C2": bool(nw["t"] >= C2_T_MIN),
        "C3": bool(dsr_family["dsr"] >= C3_DSR_MIN),
        "C4": bool(np.sign(nw["mean"]) == np.sign(infer_stress["vs_B3"]["newey_west"]["mean"])),
    }


# --- §9.5 verdicts -----------------------------------------------------------------------------


def secondary_verdict(gate_ok: bool, c: dict[str, bool], sigma: float) -> str:
    """A row without the companion clause (T2, T3, and each companion on its own criteria)."""
    if not gate_ok:
        return "inconclusive (gate)"
    if not all(c.values()):
        return "not supported"
    if sigma > VOL_BAR_007:
        return "consistent with an edge, not detectable at the 2% bar"
    return "supported in history; forward record pending"


def primary_verdict(gate_ok: bool, c_t1: dict[str, bool], companion_verdicts: dict[str, str], sigma: float) -> str:
    """T1's row (§9.5): precedence not supported > inconclusive (either kind) > consistent > supported."""
    if not gate_ok:
        return "inconclusive (gate)"
    if not all(c_t1.values()):
        return "not supported"
    if any(v == "not supported" for v in companion_verdicts.values()):
        return "inconclusive (fragile)"
    if sigma > VOL_BAR_007:
        return "consistent with an edge, not detectable at the 2% bar"
    return "supported in history; forward record pending"


def turnover_label(total_turnover: float) -> str | None:
    return "low-powered" if total_turnover < LOW_POWERED_TURNOVER else None


# --- §9.6 descriptives -------------------------------------------------------------------------


def subwindow_metrics(results: dict[str, pd.DataFrame], returns: pd.DataFrame, schedule: pd.DataFrame,
                      windows: dict[str, tuple[str, str]]) -> dict:
    """Metrics 1-7 by the calendar month of each period's execution date (§8.1)."""
    start_month = schedule["execution_date"].dt.to_period("M")
    out = {}
    for name, (first, last) in windows.items():
        lo, hi = pd.Period(first, "M"), pd.Period(last, "M")
        sliced = {}
        for k, f in results.items():
            m = start_month.reindex(f.index)
            sliced[k] = f[((m >= lo) & (m <= hi)).to_numpy()]
        if len(sliced["T"]) < 2:
            out[name] = {"periods": int(len(sliced["T"])), "note": "fewer than two periods in the window"}
            continue
        out[name] = {
            k: (tilt_descriptives(f, sliced["B0"]["r"], returns) if k == "T"
                else report.descriptive_metrics(f, sliced["B0"]["r"], returns))
            for k, f in sliced.items()
        }
        d = sliced["T"]["r"] - sliced["B3"]["r"]
        out[name]["T_minus_B3"] = {"mean_monthly": float(d.mean()), **stats.newey_west_mean(d)}
    return out


def mechanism_by_weight_quintile(weights: pd.Series, carry: pd.Series, returns: pd.DataFrame) -> dict:
    """The leg's mean excess return over cash by the quintile of T1's weight
    (five equal-count groups by the rank of the weight, ties broken by order,
    so that long runs of w = 1 still split; reported in full) and in the
    periods with c_t <= 0 against the others (§9.6)."""
    x = (returns[DURATION_LEG] - returns[CASH_LEG]).reindex(weights.index)
    groups = pd.qcut(weights.rank(method="first"), 5, labels=[f"Q{i}" for i in range(1, 6)])
    quintiles = {}
    for q in [f"Q{i}" for i in range(1, 6)]:
        sel = x[groups == q]
        quintiles[q] = {
            "periods": int(len(sel)),
            "weight_min": float(weights[groups == q].min()),
            "weight_max": float(weights[groups == q].max()),
            "mean_excess_monthly": float(sel.mean()),
            "mean_excess_annual": float(sel.mean()) * 12.0,
            "hit_rate_leg_beats_cash": float((sel > 0).mean()),
        }
    c = carry.reindex(weights.index)
    neg, pos = x[c <= 0], x[c > 0]
    return {
        "by_T1_weight_quintile": quintiles,
        "by_carry_sign": {
            "carry_le_0": {"periods": int(len(neg)), "mean_excess_annual": float(neg.mean()) * 12.0 if len(neg) else float("nan")},
            "carry_gt_0": {"periods": int(len(pos)), "mean_excess_annual": float(pos.mean()) * 12.0 if len(pos) else float("nan")},
        },
    }


def attribution(results: dict[str, dict[str, pd.DataFrame]], paths: pd.DataFrame, months: pd.Index) -> dict:
    """mean(d) and its t for T2 beside T1 and T3 on the common window, and the
    correlation of T1's and T3's weight paths (§9.6)."""
    out = {}
    for k in (PRIMARY, "T2", "T3"):
        d = results[k]["T"]["r"] - results[k]["B3"]["r"]
        out[k] = {"mean_d_monthly": float(d.mean()), "mean_d_annual": float(d.mean()) * 12.0, **stats.newey_west_mean(d)}
    w1 = paths[WEIGHT_COLUMNS[PRIMARY]].reindex(months)
    w3 = paths[WEIGHT_COLUMNS["T3"]].reindex(months)
    out["corr_weight_T1_T3"] = float(np.corrcoef(w1.to_numpy(dtype=float), w3.to_numpy(dtype=float))[0, 1])
    return out


# --- the run ---------------------------------------------------------------------------------


def compute(
    fred: dict[str, pd.Series],
    carry_first_month: str,
    test_first_month: str,
    t1b_first_month: str,
    last_month: str,
    sigma: float,
    out_dir: Path,
    gate_ok: bool = True,
    min_history: dict[str, int] = MIN_HISTORY,
    expected_periods: tuple[int, int] | None = None,
    n_family: int | None = None,
) -> dict:
    """The history run on the given windows (the registered ones from
    ``main``; toy windows from the tests)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    indices = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    full = build_schedule(fred["DGS10"], fred["DTB3"], carry_first_month, last_month)
    paths = weight_paths(fred["DGS10"], fred["DGS7"], fred["DTB3"], full, indices, min_history)
    schedules = {
        k: build_schedule(fred["DGS10"], fred["DTB3"], t1b_first_month if k == "T1b" else test_first_month, last_month)
        for k in TRIAL_IDS
    }
    if expected_periods is not None:
        got = (len(schedules[PRIMARY]) - 1, len(schedules["T1b"]) - 1)
        if got != tuple(expected_periods):
            raise ValueError(f"periods {got}, expected {tuple(expected_periods)}")
    returns = {k: backtest.instrument_returns(indices, s) for k, s in schedules.items()}
    weights = {}
    for k in TRIAL_IDS:
        w = paths[WEIGHT_COLUMNS[k]].reindex(returns[k].index)
        if w.isna().any():
            raise ValueError(f"{k} has no weight on {int(w.isna().sum())} periods of its window (§5.5)")
        weights[k] = w
    n_family = family_count() if n_family is None else int(n_family)

    summary = {
        "study": "007",
        "section": "PREREGISTRATION.md §8.1, §9",
        "label": "1974-2018 test window, synthetic instruments (T1b from 1979-07)",
        "holding_periods": {k: int(len(returns[k])) for k in TRIAL_IDS},
        "first_execution_date": {k: str(schedules[k]["execution_date"].iloc[0].date()) for k in TRIAL_IDS},
        "last_period_end": str(schedules[PRIMARY]["period_end"].iloc[-2].date()),
        "months_without_signal": int(full.attrs.get("months_without_signal", 0)),
        "weight_b3": {},
        "family": {"n_family": n_family, "rows": [list(r) for r in PROGRAMME_FAMILY], "decides_C3": True},
        "cost_cases": {},
    }
    for case, cost in COST_CASES.items():
        rng = np.random.default_rng(SEED)
        results = {k: run_trial(weights[k], returns[k], cost) for k in TRIAL_IDS}
        desc = {
            k: {
                name: (tilt_descriptives(f, results[k]["B0"]["r"], returns[k]) if name == "T"
                       else report.descriptive_metrics(f, results[k]["B0"]["r"], returns[k]))
                for name, f in results[k].items()
            }
            for k in TRIAL_IDS
        }
        infer = {k: report.inference_metrics(k, results[k]["T"], results[k], rng) for k in TRIAL_IDS}
        variance, floored = stats.trial_variance([desc[k]["T"]["sharpe_monthly"] for k in TRIAL_IDS])
        dsr = {
            k: {
                f"N{n}": stats.deflated_sharpe(
                    desc[k]["T"]["sharpe_monthly"], desc[k]["T"]["periods"], desc[k]["T"]["skewness_excess"],
                    desc[k]["T"]["kurtosis_excess"], n, variance,
                )
                for n in (n_family, N_STUDY, N_TRIALS_SENSITIVITY)
            }
            for k in TRIAL_IDS
        }
        summary["cost_cases"][case] = {
            "cost_per_side": cost,
            "descriptive": desc,
            "inference": infer,
            "deflated_sharpe": dsr,
            "deflation_inputs": {"variance_across_trials": variance, "floor_applied": floored, "n_family": n_family},
            "sub_windows": {k: subwindow_metrics(results[k], returns[k], schedules[k], SUB_WINDOWS) for k in TRIAL_IDS},
            "rate_eras": {k: subwindow_metrics(results[k], returns[k], schedules[k], RATE_ERAS) for k in TRIAL_IDS},
            "nw_iid_ratio_vs_B3": {k: nw_iid_ratio(results[k]["T"]["r"] - results[k]["B3"]["r"]) for k in TRIAL_IDS},
            "attribution": attribution(results, paths, returns[PRIMARY].index),
            "mechanism": mechanism_by_weight_quintile(weights[PRIMARY], paths["carry"], returns[PRIMARY]),
            "weight_dispersion": {
                k: {"sd_w_minus_wbar": desc[k]["T"]["sd_weight"], **DISPERSION_REFERENCES} for k in TRIAL_IDS
            },
            "T1_on_T1b_window_descriptive": tilt_descriptives(
                results[PRIMARY]["T"].reindex(returns["T1b"].index), results["T1b"]["B0"]["r"], returns["T1b"]
            ),
        }
        if case == "base":
            summary["weight_b3"] = {k: tilt.mean_weight(weights[k]) for k in TRIAL_IDS}
            summary["total_turnover"] = {k: tilt.total_turnover(results[k]["T"]) for k in TRIAL_IDS}
        pd.DataFrame({k: desc[k]["T"] for k in TRIAL_IDS}).T.to_csv(out_dir / f"metrics_{case}.csv")
        monthly = pd.concat(
            {**{k: results[k]["T"]["r"] for k in TRIAL_IDS},
             **{f"B3_{k}": results[k]["B3"]["r"] for k in TRIAL_IDS},
             **{b: results[PRIMARY][b]["r"] for b in ("B0", "B1", "B2")}},
            axis=1,
        )
        for k in reversed(TRIAL_IDS):
            monthly.insert(0, f"w_{k}", weights[k])
        monthly.insert(0, "carry_at_signal", paths["carry"].reindex(monthly.index))
        sched = schedules[PRIMARY]
        monthly.insert(0, "period_end", sched["period_end"].reindex(monthly.index).dt.date)
        monthly.insert(0, "execution_date", sched["execution_date"].reindex(monthly.index).dt.date)
        monthly.to_csv(out_dir / f"monthly_{case}.csv")

    base, stress = summary["cost_cases"]["base"], summary["cost_cases"]["stress"]
    crit = {
        k: criteria(base["descriptive"][k], base["inference"][k], base["deflated_sharpe"][k][f"N{n_family}"],
                    stress["inference"][k])
        for k in TRIAL_IDS
    }
    own = {k: secondary_verdict(gate_ok, crit[k], sigma) for k in TRIAL_IDS}
    verdicts = {PRIMARY: primary_verdict(gate_ok, crit[PRIMARY], {c: own[c] for c in COMPANIONS}, sigma)}
    verdicts.update({k: own[k] for k in COMPANIONS + SECONDARY})
    labels = {k: turnover_label(summary["total_turnover"][k]) for k in TRIAL_IDS}
    summary.update(
        {
            "criteria": crit,
            "verdict": verdicts,
            "verdict_rows_on_own_criteria": own,
            "turnover_labels": labels,
            "sigma_from_volcheck": sigma,
            "low_power_check": bool(sigma > VOL_BAR_007),
            "roles": {PRIMARY: "primary", **dict.fromkeys(COMPANIONS, "companion"), **dict.fromkeys(SECONDARY, "secondary")},
            "n_trials_study": N_STUDY,
        }
    )
    return summary


def write_verdict(summary: dict, out_dir: Path) -> None:
    base = summary["cost_cases"]["base"]
    n_family = summary["family"]["n_family"]
    lines = [
        "# Study 007 history run (§8.1, §9), run once",
        "",
        f"**Verdict for T1 (the headline): {summary['verdict']['T1']}**"
        + (f" ({summary['turnover_labels']['T1']})" if summary["turnover_labels"]["T1"] else "")
        + (" (low-power check)" if summary["low_power_check"] else "")
        + ".",
        "",
        f"| Trial | Role | Verdict (own criteria) | C1 | C2 | C3 (N={n_family}) | C4 | Sharpe | B1 | B3 | NW t vs B3 | "
        f"DSR N={n_family} | N=5 | N=10 | w̄ | Turnover |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for k in TRIAL_IDS:
        c, d, i = summary["criteria"][k], base["descriptive"][k], base["inference"][k]
        dsr = base["deflated_sharpe"][k]
        label = f" ({summary['turnover_labels'][k]})" if summary["turnover_labels"][k] else ""
        lines.append(
            f"| {k} | {summary['roles'][k]} | {summary['verdict_rows_on_own_criteria'][k]}{label} | {c['C1']} | {c['C2']} | "
            f"{c['C3']} | {c['C4']} | {d['T']['sharpe_annual']:.3f} | {d['B1']['sharpe_annual']:.3f} | "
            f"{d['B3']['sharpe_annual']:.3f} | {i['vs_B3']['newey_west']['t']:.2f} | {dsr[f'N{n_family}']['dsr']:.3f} | "
            f"{dsr['N5']['dsr']:.3f} | {dsr['N10']['dsr']:.3f} | {summary['weight_b3'][k]:.4f} | "
            f"{summary['total_turnover'][k]:.2f} |"
        )
    a = base["attribution"]
    lines += [
        "",
        f"Periods: {summary['holding_periods']}. sigma {summary['sigma_from_volcheck']:.2%} (bar {VOL_BAR_007:.2%}). "
        f"Family count {n_family} decides C3 (§9.4).",
        "",
        "Attribution (§9.6): mean(d) a year and NW t: "
        + "; ".join(f"{k} {a[k]['mean_d_annual']:.2%} (t {a[k]['t']:.2f})" for k in (PRIMARY, "T2", "T3"))
        + f"; corr(w_T1, w_T3) {a['corr_weight_T1_T3']:.3f}.",
        "",
        "Mechanism, leg excess return a year by quintile of T1's weight: "
        + "; ".join(f"{q} {v['mean_excess_annual']:.2%} (n {v['periods']})"
                    for q, v in base["mechanism"]["by_T1_weight_quintile"].items())
        + ".",
        "",
        f"Observed NW/iid ratio for T1 − B3: {base['nw_iid_ratio_vs_B3']['T1']['ratio']:.3f} (assumed {ASSUMED_NW_IID_RATIO}); "
        f"realised sd(w − w̄) for T1 {base['weight_dispersion']['T1']['sd_w_minus_wbar']:.3f} "
        f"(design 0.5, uniform rank {1 / np.sqrt(12):.3f}).",
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
    argparse.ArgumentParser(description="Study 007 history run (§8.1, §9), once.").parse_args(argv)
    if not gate_passed(gate_dir):
        raise SystemExit("refused: results/gate/gate.json does not record a passed gate (§5.3.3, §14 step 7)")
    vol_path = volcheck_dir / "volcheck.json"
    if not vol_path.exists():
        raise SystemExit("refused: results/volcheck/volcheck.json is missing (§5.4 runs before any rule return)")
    if out_dir.exists():
        raise SystemExit(f"refused: {out_dir.name}/ exists; the history run is executed once (§8.1)")
    sigma = float(json.loads(vol_path.read_text())["sigma_annual"])
    summary = compute(
        report.load_fred(),
        CARRY_FIRST_SIGNAL_MONTH,
        TEST_FIRST_SIGNAL_MONTH,
        T1B_FIRST_SIGNAL_MONTH,
        TEST_LAST_SIGNAL_MONTH,
        sigma,
        out_dir,
        expected_periods=(TEST_PERIODS, T1B_PERIODS),
    )
    summary["run_at_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary["provenance"] = report.provenance()
    report.write_json(out_dir / "summary.json", summary)
    write_verdict(summary, out_dir)
    print(f"history written to {out_dir.relative_to(STUDY_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
