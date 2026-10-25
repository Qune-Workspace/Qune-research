"""Study 008 history run (PREREGISTRATION.md §8.1, §9): once, after a passed
gate (§5.3) and a written volatility check (§5.4); §14 step 7.

Three real-yield weight paths (``gate008.weight_paths``, signals only) run
through the fractional-weight engine with the §6.4 hold addition
(``run_tilt_hold`` below, around the copied ``tilt.run_tilt``) on the test
window, T1b on its own window; each trial against its own exposure-matched B3
at its frozen mean weight (``backtest.run_static``), B0-B2 common; Study 002's
metrics and tests (``report``, ``stats``) unchanged; the DSR at the
programme-level family count decides C3 (§9.4) with N = 3 and N = 10 beside
it; the era row (T1 only, §9.5); the §9.5 verdict table with its precedence,
the companion clause for T1 and the turnover label; the §9.6 descriptives
(sub-windows and rate eras by execution month, T1 on T1b's periods with its t,
mechanism by weight quintile and by the sign of the real yield, the
differential correlation with Study 007's T1, the realised power figures, the
§6.1 branch counts and undefined months per window).  Charts are made at the
note step from the committed monthly files, not here.

    python -m src.history008    # writes results/history/ once
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
    SEED,
    STUDY_DIR,
)
from .config006 import ASSUMED_NW_IID_RATIO
from .config008 import (
    COMPANIONS,
    CPI_AVAILABILITY_PATH,
    CPI_SERIES,
    DSR_ALSO_AT,
    ERA_FIRST_EXECUTION_MONTH,
    ERA_LAST_EXECUTION_MONTH,
    ERA_PERIODS,
    GATE_DIR,
    HISTORY_DIR,
    PRIMARY,
    PROGRAMME_FAMILY,
    RANK_KIND,
    RANK_N,
    RATE_ERAS_008,
    REAL_YIELD_FIRST_SIGNAL_MONTH,
    STUDY007_DIR,
    SUB_WINDOWS,
    T1B_FIRST_SIGNAL_MONTH,
    T1B_PERIODS,
    TEST_FIRST_SIGNAL_MONTH,
    TEST_LAST_SIGNAL_MONTH,
    TEST_PERIODS,
    TRIAL_IDS,
    VOL_BAR_008,
    VOLCHECK_DIR,
    WINDOW_OF,
)
from .fred import load_series
from .gate008 import WEIGHT_COLUMNS, weight_paths
from .history import nw_iid_ratio
from .history007 import tilt_descriptives, turnover_label
from .real_yield import rank_defined
from .synthetic import synthetic_indices
from .volcheck import gate_passed

N_STUDY = len(TRIAL_IDS)
POWER_K_80 = 2.842  # §9.6 / Study 007 §11.4: 2.0 + 0.842, the 80%-power multiple of the NW standard error
DISPERSION_REFERENCES = {"sd_0.5_design": 0.5, "uniform_rank_1_over_sqrt12": 1.0 / np.sqrt(12.0)}
STUDY007_MONTHLY = STUDY007_DIR / "results" / "history" / "monthly_base.csv"
STUDY007_D_COLUMNS = ("T1", "B3_T1")  # §9.6 overlap after the fact: Study 007's T1 and its own B3


def family_count(family: tuple = PROGRAMME_FAMILY) -> int:
    return int(sum(row[3] for row in family))


# --- §6.4: the engine with a hold period -------------------------------------------------------


def run_tilt_hold(weights: pd.Series, returns: pd.DataFrame, cost_per_side: float) -> pd.DataFrame:
    """``tilt.run_tilt`` with §6.4's one addition: a period whose weight is
    undefined (NaN: the month's real yield is undefined, §6.1) **holds**: its
    target is the previous weight drifted with the two legs over the period
    just ended, so the traded fraction is exactly zero and no cost is paid.
    The copied engine is called unchanged; each hold target is the drift it
    computes itself.  A first period without a weight is refused (no position
    exists to hold; the first period starts from cash, §6.3).  The output adds
    a boolean ``hold`` column."""
    w = weights.reindex(returns.index).astype(float).copy()
    hold = w.isna()
    if len(w) and bool(hold.iloc[0]):
        raise ValueError("the first holding period has no weight; there is no position to hold (§6.3, §6.4)")
    for i in np.flatnonzero(hold.to_numpy()):
        prefix = tilt.run_tilt(w.iloc[:i], returns.iloc[:i], cost_per_side)
        last = prefix.iloc[-1]
        r_leg = float(returns[DURATION_LEG].iloc[i - 1])
        w.iloc[i] = float(last["weight"]) * (1.0 + r_leg) / (1.0 + float(last["r_gross"]))
    out = tilt.run_tilt(w, returns, cost_per_side)
    out["hold"] = hold.to_numpy()
    return out


# --- one trial, the criteria and the verdicts --------------------------------------------------


def run_trial(weights: pd.Series, returns: pd.DataFrame, cost: float) -> dict[str, pd.DataFrame]:
    """One trial with its own B3 at its frozen mean weight (signals only: hold
    months, which have no signal weight, are not in the mean); B0-B2 common (§9.1)."""
    w_bar = tilt.mean_weight(weights)
    results = backtest.benchmarks(returns, w_bar, cost)
    results["T"] = run_tilt_hold(weights, returns, cost)
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


def era_months(schedule: pd.DataFrame, index: pd.Index,
               first: str = ERA_FIRST_EXECUTION_MONTH, last: str = ERA_LAST_EXECUTION_MONTH) -> np.ndarray:
    """Boolean mask over ``index`` (holding periods) for the era window, by the
    calendar month of each period's execution date (§8.1)."""
    m = schedule["execution_date"].dt.to_period("M").reindex(index)
    return ((m >= pd.Period(first, "M")) & (m <= pd.Period(last, "M"))).to_numpy()


def era_row(d: pd.Series, mask: np.ndarray, expected_periods: int | None = None) -> dict:
    """§9.5 era row for T1: mean(T1 - B3^{T1}) over the era window > 0 at base
    costs, with B3 at T1's full-window w̄ (``d`` is already formed against it).
    Pass/fail on the sign only; the Newey-West t is reported, not tested."""
    sel = d[mask]
    if expected_periods is not None and len(sel) != expected_periods:
        raise ValueError(f"era window has {len(sel)} periods, expected {expected_periods} (§8.1)")
    nw = stats.newey_west_mean(sel)
    return {
        "periods": int(len(sel)),
        "mean_d_monthly": float(sel.mean()),
        "mean_d_annual": float(sel.mean()) * 12.0,
        "nw_t_reported_not_tested": nw["t"],
        "nw_se": nw["se"],
        "pass": bool(sel.mean() > 0),
    }


def companion_verdict(gate_ok: bool, c: dict[str, bool]) -> str:
    """A companion's own row (§9.5): 'not supported', 'inconclusive (gate)' or
    'meets C1-C4'; no era row and no companion clause for it."""
    if not gate_ok:
        return "inconclusive (gate)"
    if not all(c.values()):
        return "not supported"
    return "meets C1-C4"


def primary_verdict(gate_ok: bool, c_t1: dict[str, bool], era_pass: bool,
                    companion_verdicts: dict[str, str], sigma: float) -> str:
    """T1's row (§9.5).  Precedence: not supported > inconclusive (gate) >
    inconclusive (one era) > inconclusive (fragile) > consistent > supported.
    'Not supported' outranks the gate only in the table's order; a failed gate
    computes no return, so no criterion exists to fail."""
    if not gate_ok:
        return "inconclusive (gate)"
    if not all(c_t1.values()):
        return "not supported"
    if not era_pass:
        return "inconclusive (one era)"
    if any(v == "not supported" for v in companion_verdicts.values()):
        return "inconclusive (fragile)"
    if sigma > VOL_BAR_008:
        return "consistent with an edge, not detectable at the 2% bar"
    return "supported in history; forward record pending"


# --- §9.6 descriptives -------------------------------------------------------------------------


def subwindow_metrics(results: dict[str, pd.DataFrame], returns: pd.DataFrame, schedule: pd.DataFrame,
                      windows: dict[str, tuple[str, str]]) -> dict:
    """Metrics 1-7 by the calendar month of each period's execution date (§8.1)."""
    out = {}
    for name, (first, last) in windows.items():
        mask = era_months(schedule, results["T"].index, first, last)
        sliced = {k: f[mask] for k, f in results.items()}
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


def mechanism(weights: pd.Series, r_real: pd.Series, returns: pd.DataFrame) -> dict:
    """§9.6: the leg's mean excess return over cash a year by equal-count
    quintile of T1's weight (ties by order, Study 007's rule; five rows, in
    full), and in the periods with r_m <= 0 against the others."""
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
    r = r_real.reindex(weights.index)
    neg, pos = x[r <= 0], x[r > 0]
    return {
        "by_T1_weight_quintile": quintiles,
        "by_real_yield_sign": {
            "r_le_0": {"periods": int(len(neg)), "mean_excess_annual": float(neg.mean()) * 12.0 if len(neg) else float("nan")},
            "r_gt_0": {"periods": int(len(pos)), "mean_excess_annual": float(pos.mean()) * 12.0 if len(pos) else float("nan")},
        },
    }


def realised_power(d: pd.Series, weights: pd.Series) -> dict:
    """§9.6 power, realised: the observed NW/iid ratio of d beside the assumed
    0.972; sd(w - w̄) beside 0.5 and 1/sqrt(12); the minimum detectable mean
    difference at t = 2 and at 80% power (K = 2.842) from the observed NW
    standard error of d, a year."""
    ratio = nw_iid_ratio(d)
    se_annual = ratio["nw_se"] * 12.0
    return {
        **ratio,
        "sd_w_minus_wbar": float(weights.std(ddof=0)),
        **DISPERSION_REFERENCES,
        "mde_annual_at_t2": C2_T_MIN * se_annual,
        "mde_annual_at_80pct_power": POWER_K_80 * se_annual,
        "k_80": POWER_K_80,
    }


def differential_correlation_with_007(d: pd.Series, monthly_007: pd.DataFrame) -> dict:
    """§9.6 overlap after the fact: corr(d^{008 T1}, d^{007 T1}) over the
    common periods, each against its own B3.  ``monthly_007`` carries Study
    007's ``T1`` and ``B3_T1`` columns indexed by signal month."""
    d007 = (monthly_007["T1"] - monthly_007["B3_T1"]).reindex(d.index)
    if d007.isna().any():
        raise ValueError("a period is missing from Study 007's history file (§9.6)")
    return {"periods": int(len(d)), "corr_d_T1_008_vs_007": float(np.corrcoef(d.to_numpy(), d007.to_numpy())[0, 1])}


def read_007_differential(path: Path = STUDY007_MONTHLY) -> pd.DataFrame:
    frame = pd.read_csv(path, usecols=["month", *STUDY007_D_COLUMNS], dtype={"month": str})
    return frame.set_index(pd.PeriodIndex(frame["month"], freq="M"))[list(STUDY007_D_COLUMNS)]


def availability_counts(availability: pd.DataFrame, paths: pd.DataFrame, months: pd.Index) -> dict:
    """§9.6: counts by §6.1's availability branch (as the data step read them),
    the months whose k is not m - 1 (as used, after §16 (a)), and the months
    whose r is undefined, for the signal months of one window, per CPI series."""
    av = availability.set_index(pd.PeriodIndex(availability["signal_month"], freq="M")).reindex(months)
    out = {}
    for s in sorted(set(CPI_SERIES.values())):
        branch = av[f"{s}_branch"]
        k_used = paths[f"k_{s}"].reindex(months)  # the k each signal month used (core follows headline, §16 (a))
        late = int((k_used != pd.Series([str(m - 1) for m in months], index=months)).sum())
        out[s] = {
            "branch_counts": {str(k): int(v) for k, v in branch.value_counts().items()},
            "k_not_m_minus_1": late,
            "undefined_real_yield_months": [str(m) for m in months[paths[f"r_{s}"].reindex(months).isna().to_numpy()]],
        }
    return out


# --- the run ---------------------------------------------------------------------------------


def compute(
    fred: dict[str, pd.Series],
    cpi: dict[str, pd.Series],
    availability: pd.DataFrame,
    real_yield_first_month: str,
    test_first_month: str,
    t1b_first_month: str,
    last_month: str,
    sigma: float,
    out_dir: Path,
    gate_ok: bool = True,
    rank_n: dict[str, int] = RANK_N,
    era: tuple[str, str] = (ERA_FIRST_EXECUTION_MONTH, ERA_LAST_EXECUTION_MONTH),
    expected_periods: tuple[int, int, int] | None = None,
    n_family: int | None = None,
    monthly_007: pd.DataFrame | None = None,
    dropped: tuple[str, ...] = (),
) -> dict:
    """The history run on the given windows (the registered ones from
    ``main``; toy windows from the tests).  ``expected_periods`` is (test,
    T1b, era); ``monthly_007`` feeds the after-the-fact overlap row.
    ``dropped`` lists the trials the gate dropped (§5.3, gate.json
    ``dropped_trials``): no return of theirs is computed, their own row is
    'inconclusive (gate)', and the companion clause does not fire on them."""
    if PRIMARY in dropped or not set(dropped) <= set(COMPANIONS):
        raise ValueError(f"only companions can be dropped at a passed gate (§5.3), got {sorted(dropped)}")
    trials = tuple(k for k in TRIAL_IDS if k not in dropped)
    out_dir.mkdir(parents=True, exist_ok=True)
    indices = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    full = build_schedule(fred["DGS10"], fred["DTB3"], real_yield_first_month, last_month)
    paths = weight_paths(fred["DGS10"], cpi, availability, full)
    if dict(rank_n) != dict(RANK_N):  # toy minimum histories from the tests only
        for k in TRIAL_IDS:
            paths[WEIGHT_COLUMNS[k]] = rank_defined(paths[f"r_{CPI_SERIES[k]}"], RANK_KIND[k], rank_n[k]).to_numpy()
    first_of = {"test": test_first_month, "t1b": t1b_first_month}
    schedules = {k: build_schedule(fred["DGS10"], fred["DTB3"], first_of[WINDOW_OF[k]], last_month) for k in TRIAL_IDS}
    returns = {k: backtest.instrument_returns(indices, s) for k, s in schedules.items()}
    era_mask = era_months(schedules[PRIMARY], returns[PRIMARY].index, *era)
    if expected_periods is not None:
        got = (len(returns[PRIMARY]), len(returns["T1b"]), int(era_mask.sum()))
        if got != tuple(expected_periods):
            raise ValueError(f"periods {got}, expected {tuple(expected_periods)}")
    weights = {}
    for k in trials:
        w = paths[WEIGHT_COLUMNS[k]].reindex(returns[k].index)
        if pd.isna(w.iloc[0]):
            raise ValueError(f"{k} has no weight on the first period of its window (§7, data step)")
        weights[k] = w
    n_family = family_count() if n_family is None else int(n_family)
    dsr_ns = (n_family, *DSR_ALSO_AT)
    r_head = paths[f"r_{CPI_SERIES[PRIMARY]}"]

    summary = {
        "study": "008",
        "section": "PREREGISTRATION.md §8.1, §9",
        "label": "1974-2018 test window, synthetic instruments (T1b from 1979-07)",
        "holding_periods": {k: int(len(returns[k])) for k in TRIAL_IDS},
        "era_periods": int(era_mask.sum()),
        "first_execution_date": {k: str(schedules[k]["execution_date"].iloc[0].date()) for k in TRIAL_IDS},
        "last_period_end": str(schedules[PRIMARY]["period_end"].iloc[-2].date()),
        "months_without_signal": int(full.attrs.get("months_without_signal", 0)),
        "trials_run": list(trials),
        "dropped_at_gate": list(dropped),
        "hold_periods": {k: [str(m) for m in weights[k].index[weights[k].isna().to_numpy()]] for k in trials},
        "availability": {k: availability_counts(availability, paths, returns[k].index) for k in TRIAL_IDS},
        "weight_b3": {},
        "family": {"n_family": n_family, "rows": [list(r) for r in PROGRAMME_FAMILY], "decides_C3": True},
        "cost_cases": {},
    }
    for case, cost in COST_CASES.items():
        rng = np.random.default_rng(SEED)
        results = {k: run_trial(weights[k], returns[k], cost) for k in trials}
        desc = {
            k: {
                name: (tilt_descriptives(f, results[k]["B0"]["r"], returns[k]) if name == "T"
                       else report.descriptive_metrics(f, results[k]["B0"]["r"], returns[k]))
                for name, f in results[k].items()
            }
            for k in trials
        }
        infer = {k: report.inference_metrics(k, results[k]["T"], results[k], rng) for k in trials}
        variance, floored = stats.trial_variance([desc[k]["T"]["sharpe_monthly"] for k in trials])
        dsr = {
            k: {
                f"N{n}": stats.deflated_sharpe(
                    desc[k]["T"]["sharpe_monthly"], desc[k]["T"]["periods"], desc[k]["T"]["skewness_excess"],
                    desc[k]["T"]["kurtosis_excess"], n, variance,
                )
                for n in dsr_ns
            }
            for k in trials
        }
        d = {k: results[k]["T"]["r"] - results[k]["B3"]["r"] for k in trials}
        # T1 on T1b's periods, descriptive (§2.5, §9.6): T1's own path and T1's own B3 (at T1's
        # full-window w̄), restricted to those periods; cash is B0 on the same periods.
        t1_on_t1b = results[PRIMARY]["T"].reindex(returns["T1b"].index)
        cash_t1b = backtest.run_static(0.0, returns["T1b"], 0.0)["r"]
        d_t1_on_t1b = d[PRIMARY].reindex(returns["T1b"].index)
        summary["cost_cases"][case] = {
            "cost_per_side": cost,
            "descriptive": desc,
            "inference": infer,
            "deflated_sharpe": dsr,
            "deflation_inputs": {"variance_across_trials": variance, "floor_applied": floored, "n_family": n_family},
            "era_row_T1": era_row(d[PRIMARY], era_mask),
            "sub_windows": {k: subwindow_metrics(results[k], returns[k], schedules[k], SUB_WINDOWS) for k in trials},
            "rate_eras": {k: subwindow_metrics(results[k], returns[k], schedules[k], RATE_ERAS_008) for k in trials},
            "mechanism": mechanism(weights[PRIMARY], r_head, returns[PRIMARY]),
            "power_realised": {k: realised_power(d[k], weights[k]) for k in trials},
            "T1_on_T1b_window_descriptive": {
                "B3_used": "T1's own B3 at T1's full-window mean weight",
                **tilt_descriptives(t1_on_t1b, cash_t1b, returns["T1b"]),
                "T_minus_own_B3": {"mean_monthly": float(d_t1_on_t1b.mean()), **stats.newey_west_mean(d_t1_on_t1b)},
            },
            "overlap_after_the_fact": (differential_correlation_with_007(d[PRIMARY], monthly_007)
                                       if monthly_007 is not None else None),
        }
        if case == "base":
            summary["weight_b3"] = {k: tilt.mean_weight(weights[k]) for k in trials}
            summary["total_turnover"] = {k: tilt.total_turnover(results[k]["T"]) for k in trials}
        pd.DataFrame({k: desc[k]["T"] for k in trials}).T.to_csv(out_dir / f"metrics_{case}.csv")
        monthly = pd.concat(
            {**{k: results[k]["T"]["r"] for k in trials},
             **{f"B3_{k}": results[k]["B3"]["r"] for k in trials},
             **{b: results[PRIMARY][b]["r"] for b in ("B0", "B1", "B2")}},
            axis=1,
        )
        for k in reversed(trials):
            monthly.insert(0, f"w_{k}", results[k]["T"]["weight"])
        for s in sorted(set(CPI_SERIES.values()), reverse=True):
            monthly.insert(0, f"r_{s}", paths[f"r_{s}"].reindex(monthly.index))
        sched = schedules[PRIMARY]
        monthly.insert(0, "period_end", sched["period_end"].reindex(monthly.index).dt.date)
        monthly.insert(0, "execution_date", sched["execution_date"].reindex(monthly.index).dt.date)
        monthly.index.name = "month"
        monthly.to_csv(out_dir / f"monthly_{case}.csv")

    base, stress = summary["cost_cases"]["base"], summary["cost_cases"]["stress"]
    crit = {
        k: criteria(base["descriptive"][k], base["inference"][k], base["deflated_sharpe"][k][f"N{n_family}"],
                    stress["inference"][k])
        for k in trials
    }
    own = {k: (companion_verdict(gate_ok, crit[k]) if k in trials else "inconclusive (gate)") for k in TRIAL_IDS}
    verdicts = {PRIMARY: primary_verdict(gate_ok, crit[PRIMARY], base["era_row_T1"]["pass"],
                                         {c: own[c] for c in COMPANIONS}, sigma)}
    verdicts.update({k: own[k] for k in COMPANIONS})
    labels = {k: turnover_label(summary["total_turnover"][k]) for k in trials}
    summary.update(
        {
            "criteria": crit,
            "verdict": verdicts,
            "verdict_rows_on_own_criteria": own,
            "turnover_labels": labels,
            "sigma_from_volcheck": sigma,
            "low_power_check": bool(sigma > VOL_BAR_008),
            "roles": {PRIMARY: "primary", **dict.fromkeys(COMPANIONS, "companion")},
            "n_trials_study": N_STUDY,
        }
    )
    return summary


def write_verdict(summary: dict, out_dir: Path) -> None:
    base = summary["cost_cases"]["base"]
    n_family = summary["family"]["n_family"]
    n_a, n_b = DSR_ALSO_AT
    lines = [
        "# Study 008 history run (§8.1, §9), run once",
        "",
        f"**Verdict for T1 (the headline): {summary['verdict']['T1']}**"
        + (f" ({summary['turnover_labels']['T1']})" if summary["turnover_labels"]["T1"] else "")
        + (" (low-power check)" if summary["low_power_check"] else "")
        + ".",
        "",
        f"| Trial | Role | Own row | C1 | C2 | C3 (N={n_family}) | C4 | Sharpe | B1 | B3 | NW t vs B3 | "
        f"DSR N={n_family} | N={n_a} | N={n_b} | w̄ | Turnover |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for k in TRIAL_IDS:
        if k not in summary["criteria"]:
            lines.append(f"| {k} | {summary['roles'][k]} | {summary['verdict_rows_on_own_criteria'][k]} (dropped at the gate; "
                         "no return computed) |" + " – |" * 13)
            continue
        c, d, i = summary["criteria"][k], base["descriptive"][k], base["inference"][k]
        dsr = base["deflated_sharpe"][k]
        label = f" ({summary['turnover_labels'][k]})" if summary["turnover_labels"][k] else ""
        lines.append(
            f"| {k} | {summary['roles'][k]} | {summary['verdict_rows_on_own_criteria'][k]}{label} | {c['C1']} | {c['C2']} | "
            f"{c['C3']} | {c['C4']} | {d['T']['sharpe_annual']:.3f} | {d['B1']['sharpe_annual']:.3f} | "
            f"{d['B3']['sharpe_annual']:.3f} | {i['vs_B3']['newey_west']['t']:.2f} | {dsr[f'N{n_family}']['dsr']:.3f} | "
            f"{dsr[f'N{n_a}']['dsr']:.3f} | {dsr[f'N{n_b}']['dsr']:.3f} | {summary['weight_b3'][k]:.4f} | "
            f"{summary['total_turnover'][k]:.2f} |"
        )
    era = base["era_row_T1"]
    t1b = base["T1_on_T1b_window_descriptive"]["T_minus_own_B3"]
    pw = base["power_realised"][PRIMARY]
    ov = base["overlap_after_the_fact"]
    lines += [
        "",
        f"Era row (T1, execution months {ERA_FIRST_EXECUTION_MONTH} to {ERA_LAST_EXECUTION_MONTH}, {era['periods']} periods): "
        f"mean(T1 − B3) {era['mean_d_annual']:.2%} a year, pass {era['pass']} (sign only; NW t {era['nw_t_reported_not_tested']:.2f}, "
        "reported, not tested).",
        "",
        f"Periods: {summary['holding_periods']}. sigma {summary['sigma_from_volcheck']:.2%} (bar {VOL_BAR_008:.2%}). "
        f"Family count {n_family} decides C3 (§9.4). Hold periods: {summary['hold_periods']}.",
        "",
        f"T1 on T1b's periods (descriptive): mean(T1 − B3) {t1b['mean'] * 12:.2%} a year, NW t {t1b['t']:.2f}.",
        "",
        "Mechanism, leg excess return a year by quintile of T1's weight: "
        + "; ".join(f"{q} {v['mean_excess_annual']:.2%} (n {v['periods']})"
                    for q, v in base["mechanism"]["by_T1_weight_quintile"].items())
        + "; by the sign of the real yield: "
        + "; ".join(f"{s} {v['mean_excess_annual']:.2%} (n {v['periods']})"
                    for s, v in base["mechanism"]["by_real_yield_sign"].items())
        + ".",
        "",
        f"Power, realised (T1): NW/iid ratio {pw['ratio']:.3f} (assumed {ASSUMED_NW_IID_RATIO}); sd(w − w̄) "
        f"{pw['sd_w_minus_wbar']:.3f} (design 0.5, uniform rank {1 / np.sqrt(12):.3f}); MDE {pw['mde_annual_at_t2']:.2%} "
        f"a year at t = 2, {pw['mde_annual_at_80pct_power']:.2%} at 80% power (K {POWER_K_80}).",
        "",
        ("Overlap after the fact: " + (f"corr(d T1, d Study 007 T1) {ov['corr_d_T1_008_vs_007']:.3f} over {ov['periods']} periods."
                                       if ov else "not computed (no Study 007 file passed).")),
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
    argparse.ArgumentParser(description="Study 008 history run (§8.1, §9), once.").parse_args(argv)
    if not gate_passed(gate_dir):
        raise SystemExit("refused: results/gate/gate.json does not record a passed gate (§5.3, §14 step 7)")
    vol_path = volcheck_dir / "volcheck.json"
    if not vol_path.exists():
        raise SystemExit("refused: results/volcheck/volcheck.json is missing (§5.4 runs before any rule return)")
    if out_dir.exists():
        raise SystemExit(f"refused: {out_dir.name}/ exists; the history run is executed once (§8.1)")
    sigma = float(json.loads(vol_path.read_text())["sigma_annual"])
    dropped = tuple(sorted(json.loads((gate_dir / "gate.json").read_text()).get("dropped_trials", {})))
    summary = compute(
        report.load_fred(),
        {s: load_series(s) for s in sorted(set(CPI_SERIES.values()))},
        pd.read_csv(CPI_AVAILABILITY_PATH, dtype=str, keep_default_na=False),
        REAL_YIELD_FIRST_SIGNAL_MONTH,
        TEST_FIRST_SIGNAL_MONTH,
        T1B_FIRST_SIGNAL_MONTH,
        TEST_LAST_SIGNAL_MONTH,
        sigma,
        out_dir,
        expected_periods=(TEST_PERIODS, T1B_PERIODS, ERA_PERIODS),
        monthly_007=read_007_differential(),
        dropped=dropped,
    )
    summary["run_at_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary["provenance"] = report.provenance()
    report.write_json(out_dir / "summary.json", summary)
    write_verdict(summary, out_dir)
    print(f"history written to {out_dir.relative_to(STUDY_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
