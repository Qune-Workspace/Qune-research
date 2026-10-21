"""In-sample and out-of-sample runs: tables, tests, decision criteria and
figures into ``results/`` (§8, §9).

``python -m src.report --insample`` writes ``results/insample/`` and freezes
the B3 weight; ``python -m src.report --oos`` reads that weight, runs the
out-of-sample window once on actual ETF bars (and on the synthetic series
alongside) and writes ``results/oos/``.  Both are invoked only through
``reproduce.sh`` after approval.  The same engine, costs and statistics are
used for every strategy and both windows.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from . import backtest, stats
from .alpaca_bars import load_bars
from .alpaca_bars import total_return_index as etf_total_return_index
from .calendar import build_schedule
from .config import (C1_SHARPE_MARGIN, C2_T_MIN, C3_DSR_MIN, CASH_LEG, COST_CASES, DURATION_LEG,
                     INSAMPLE_FIRST_SIGNAL_MONTH, INSAMPLE_LAST_SIGNAL_MONTH, MANIFEST_PATH,
                     N_TRIALS_REGISTERED, N_TRIALS_SENSITIVITY, NOT_SUPPORTED_T_MAX,
                     OOS_FIRST_SIGNAL_MONTH, OOS_LAST_SIGNAL_MONTH, RESULTS_DIR, SEED, STUDY_DIR,
                     SUBPERIODS, SYMBOLS, T3_FIRST_SIGNAL_MONTH, TRIAL_IDS)
from .fred import load_series
from .signal import daily_spread, t1, t2, t3
from .synthetic import synthetic_indices

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (backend must be chosen first)

BENCHMARK_IDS = ("B0", "B1", "B2", "B3")


# --- Inputs ----------------------------------------------------------------------

def load_fred() -> dict[str, pd.Series]:
    return {name: load_series(name) for name in ("DGS10", "DTB3", "DGS7")}


def actual_indices() -> dict[str, pd.Series]:
    return {name: etf_total_return_index(load_bars(name)) for name in SYMBOLS}


def trial_signals(fred: dict[str, pd.Series], schedule: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Signal frames of T1, T2, T3 on the schedule's signal dates (§7).  T3 is
    defined from 1969-07 (DGS7); T2 needs 21 daily spreads.  A trial whose
    signal starts later than the schedule simply has fewer holding periods."""
    dates = schedule["signal_date"]
    t3_dates = dates[dates.index >= pd.Period(T3_FIRST_SIGNAL_MONTH, "M")]
    return {"T1": t1(fred["DGS10"], fred["DTB3"], dates),
            "T2": t2(fred["DGS10"], fred["DTB3"], dates),
            "T3": t3(fred["DGS10"], fred["DGS7"], fred["DTB3"], t3_dates)}


def targets_for_periods(signal_frame: pd.DataFrame, schedule: pd.DataFrame) -> pd.Series:
    """Targets of the holding periods (every schedule row but the last)."""
    return signal_frame["target"].reindex(schedule.index[:-1]).dropna()


# --- Metrics -----------------------------------------------------------------------

def descriptive_metrics(frame: pd.DataFrame, r_cash: pd.Series, returns: pd.DataFrame) -> dict[str, float]:
    """§9.3 items 1-6 and 11 for one strategy result."""
    r = frame["r"]
    excess = r - r_cash.reindex(r.index)
    years = len(r) / stats.MONTHS_PER_YEAR
    out = {"periods": int(len(r)),
           "first_period": str(r.index[0]), "last_period": str(r.index[-1]),
           "ann_geometric_return": stats.annualised_geometric_return(r),
           "ann_volatility": stats.annualised_volatility(r),
           "sharpe_annual": stats.sharpe_annual(excess),
           "sharpe_monthly": stats.sharpe_monthly(excess),
           "max_drawdown_monthly": stats.max_drawdown(stats.total_return_index(r)),
           "mean_excess_monthly": float(excess.mean()),
           "hit_rate_positive_excess": float((excess > 0).mean()),
           "skewness_excess": stats.skewness(excess),
           "kurtosis_excess": stats.kurtosis(excess)}
    if "switched" in frame:
        out["switches_per_year"] = float(frame["switched"].sum() / years)
        out["fraction_in_ief"] = float((frame["holding"] == DURATION_LEG).mean())
        out["hit_rate_held_vs_other"] = float((frame["r_held_minus_other"] > 0).mean())
    else:
        w = float(frame["weight_ief"].iloc[0])
        out["switches_per_year"] = 0.0
        out["fraction_in_ief"] = w
        ief_better = returns[DURATION_LEG].reindex(r.index) > returns[CASH_LEG].reindex(r.index)
        if w == 1.0:
            out["hit_rate_held_vs_other"] = float(ief_better.mean())
        elif w == 0.0:
            out["hit_rate_held_vs_other"] = float((~ief_better).mean())
        else:
            out["hit_rate_held_vs_other"] = float("nan")  # a mix holds both instruments
    return out


def inference_metrics(name: str, frame: pd.DataFrame, results: dict[str, pd.DataFrame],
                      rng: np.random.Generator) -> dict:
    """§9.3 items 7-9 for a trial against B1 and B3 on the trial's own periods."""
    r = frame["r"]
    r_cash = results["B0"]["r"].reindex(r.index)
    out = {"sharpe_ci": stats.sharpe_ci_stationary_bootstrap(r - r_cash, rng)}
    for bench in ("B1", "B3"):
        rb = results[bench]["r"].reindex(r.index)
        out[f"vs_{bench}"] = {"newey_west": stats.newey_west_mean(r - rb),
                              "ledoit_wolf": stats.ledoit_wolf_sharpe_test(r - r_cash, rb - r_cash, rng)}
    return out


def deflation(descriptives: dict[str, dict]) -> tuple[dict[str, dict], dict]:
    """DSR for every trial with N = 3 and N = 10 (§9.4); V is the variance of
    the monthly Sharpe ratios across the three registered trials."""
    sharpes = [descriptives[t]["sharpe_monthly"] for t in TRIAL_IDS]
    variance, floored = stats.trial_variance(sharpes)
    out = {}
    for t in TRIAL_IDS:
        d = descriptives[t]
        out[t] = {f"N{n}": stats.deflated_sharpe(d["sharpe_monthly"], d["periods"], d["skewness_excess"],
                                                 d["kurtosis_excess"], n, variance)
                  for n in (N_TRIALS_REGISTERED, N_TRIALS_SENSITIVITY)}
    return out, {"variance_across_trials": variance, "floor_applied": floored}


def mechanism_check(signal_frame: pd.DataFrame, schedule: pd.DataFrame,
                    returns: pd.DataFrame) -> dict:
    """§9.6: months with a non-positive signal, episode lengths and realised
    IEF versus BIL return in those months."""
    value = signal_frame["value"].reindex(schedule.index[:-1])
    inverted = value <= 0
    out = stats.inverted_episodes(inverted)
    sub = returns.loc[inverted[inverted].index]
    out.update({"mean_r_ief": float(sub[DURATION_LEG].mean()) if len(sub) else float("nan"),
                "mean_r_bil": float(sub[CASH_LEG].mean()) if len(sub) else float("nan"),
                "fraction_bil_beats_ief": float((sub[CASH_LEG] > sub[DURATION_LEG]).mean()) if len(sub) else float("nan")})
    return out


# --- Decision criteria (§9.5) ------------------------------------------------------

def insample_criteria(desc: dict, infer: dict, dsr: dict, desc_stress: dict, infer_stress: dict,
                      trial: str = "T1") -> dict[str, bool]:
    nw_b3 = infer[trial]["vs_B3"]["newey_west"]
    return {"C1": bool(desc[trial]["sharpe_annual"] >= desc["B1"]["sharpe_annual"] + C1_SHARPE_MARGIN
                       and desc[trial]["sharpe_annual"] >= desc["B3"]["sharpe_annual"] + C1_SHARPE_MARGIN),
            "C2": bool(nw_b3["t"] >= C2_T_MIN),
            "C3": bool(dsr[trial][f"N{N_TRIALS_REGISTERED}"]["dsr"] >= C3_DSR_MIN),
            "C4": bool(np.sign(nw_b3["mean"]) == np.sign(infer_stress[trial]["vs_B3"]["newey_west"]["mean"]))}


def oos_criteria(desc: dict, infer: dict, trial: str = "T1") -> dict[str, bool]:
    return {"O1": bool(infer[trial]["vs_B3"]["newey_west"]["mean"] > 0),
            "O2": bool(desc[trial]["sharpe_annual"] > desc["B1"]["sharpe_annual"])}


def verdict(c: dict[str, bool], o: dict[str, bool], oos_t_vs_b3: float,
            oos_mdd_t1: float, oos_mdd_b1: float) -> str:
    """§9.5 verdict table for T1.  The "not supported" conditions are tested
    first: the drawdown clause can hold together with every criterion of
    "supported", and a failing condition is read as dominating.  The T2/T3
    fragility downgrade is applied by the author in the note, where it must
    be stated prominently."""
    c_all = all(c.values())
    if not c_all or (not o["O1"] and oos_t_vs_b3 <= NOT_SUPPORTED_T_MAX) or oos_mdd_t1 < oos_mdd_b1:
        return "not supported"
    if o["O1"] and o["O2"]:
        return "supported"
    return "inconclusive"


# --- Figures -----------------------------------------------------------------------

def main_chart(spread: pd.Series, schedule: pd.DataFrame, t1_result: pd.DataFrame,
               b1_result: pd.DataFrame, out_path: Path, title: str) -> None:
    """Spread with the holding shaded, and the drawdown of T1 versus B1 (§9.6)."""
    periods = schedule.iloc[:-1]
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                                      gridspec_kw={"height_ratios": [3, 2]})
    window = spread.loc[periods["execution_date"].iloc[0]:periods["period_end"].iloc[-1]]
    top.plot(window.index, window * 100, color="#1f4e79", linewidth=0.8)
    top.axhline(0, color="black", linewidth=0.6)
    for month, row in periods.iterrows():
        if t1_result.at[month, "holding"] == DURATION_LEG:
            top.axvspan(row["execution_date"], row["period_end"], color="#1f4e79", alpha=0.08, linewidth=0)
    top.set_ylabel("10y minus 3m spread (pp)")
    top.set_title(f"{title}: spread; shaded where T1 holds {DURATION_LEG}")
    for result, label, colour in ((t1_result, "T1", "#1f4e79"), (b1_result, f"B1 ({DURATION_LEG})", "#c0504d")):
        tri = stats.total_return_index(result["r"])
        dd = (tri / tri.cummax() - 1.0) * 100
        bottom.plot(periods["period_end"].values, dd.values, label=label, color=colour, linewidth=0.9)
    bottom.set_ylabel("drawdown (%)")
    bottom.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# --- Run ---------------------------------------------------------------------------

def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=STUDY_DIR, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _json_default(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, (pd.Timestamp, pd.Period)):
        return str(value)
    raise TypeError(f"not serialisable: {type(value)}")


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n", encoding="utf-8")


def run_window(label: str, indices: dict[str, pd.Series], fred: dict[str, pd.Series],
               schedule: pd.DataFrame, weight_b3: float | None, out_dir: Path,
               with_subperiods: bool, with_daily: bool) -> dict:
    """Everything §9.3 asks for, for one window and one instrument source."""
    out_dir.mkdir(parents=True, exist_ok=True)
    signals = trial_signals(fred, schedule)
    returns = backtest.instrument_returns(indices, schedule)
    targets = {t: targets_for_periods(f, schedule) for t, f in signals.items()}
    if weight_b3 is None:
        weight_b3 = backtest.exposure_fraction(targets["T1"])
    summary = {"label": label, "weight_b3": weight_b3, "holding_periods": int(len(returns)),
               "first_execution_date": str(schedule["execution_date"].iloc[0].date()),
               "last_period_end": str(schedule["period_end"].iloc[-2].date()),
               "months_without_signal": schedule.attrs.get("months_without_signal", 0),
               "terminal_target": {t: str(f["target"].iloc[-1]) for t, f in signals.items()},
               "cost_cases": {}}
    if "days_slipped" in schedule:
        summary["execution_dates_slipped"] = schedule.loc[schedule["days_slipped"] > 0, "days_slipped"].to_dict()
    spread = daily_spread(fred["DGS10"], fred["DTB3"])
    for case, cost in COST_CASES.items():
        rng = np.random.default_rng(SEED)
        results = backtest.benchmarks(returns, weight_b3, cost)
        for t in TRIAL_IDS:
            results[t] = backtest.run_switching(targets[t], returns.loc[targets[t].index], cost)
        desc = {name: descriptive_metrics(f, results["B0"]["r"], returns) for name, f in results.items()}
        infer = {t: inference_metrics(t, results[t], results, rng) for t in TRIAL_IDS}
        dsr, dsr_inputs = deflation(desc)
        mechanism = {t: mechanism_check(signals[t], schedule, returns) for t in TRIAL_IDS}
        stops = {t: backtest.stop_touch_count(results[t], schedule, indices[DURATION_LEG]) for t in TRIAL_IDS}
        case_summary = {"cost_per_side": cost, "descriptive": desc, "inference": infer,
                        "deflated_sharpe": dsr, "deflation_inputs": dsr_inputs,
                        "mechanism_check": mechanism, "ief_stop_touch_periods": stops}
        if with_daily:
            case_summary["max_drawdown_daily"] = {
                t: stats.max_drawdown(backtest.daily_strategy_index(results[t], schedule, indices))
                for t in TRIAL_IDS} | {"B1": stats.max_drawdown(indices[DURATION_LEG].loc[
                    schedule["execution_date"].iloc[0]:schedule["period_end"].iloc[-2]])}
        if with_subperiods:
            case_summary["subperiods"] = subperiod_metrics(results, returns)
        summary["cost_cases"][case] = case_summary
        pd.DataFrame(desc).T.to_csv(out_dir / f"metrics_{case}.csv")
        monthly = pd.concat({name: f["r"] for name, f in results.items()}, axis=1)
        monthly.insert(0, "T1_holding", results["T1"]["holding"])
        monthly.insert(0, "spread_at_signal", signals["T1"]["value"].reindex(monthly.index))
        monthly.insert(0, "period_end", schedule["period_end"].reindex(monthly.index).dt.date)
        monthly.insert(0, "execution_date", schedule["execution_date"].reindex(monthly.index).dt.date)
        monthly.to_csv(out_dir / f"monthly_{case}.csv")
        if case == "base":
            main_chart(spread, schedule, results["T1"], results["B1"], out_dir / "main_chart.png", label)
    return summary


def subperiod_metrics(results: dict[str, pd.DataFrame], returns: pd.DataFrame) -> dict:
    """§9.6 sub-period descriptives (items 1-6) for every strategy."""
    out = {}
    for name, (first, last) in SUBPERIODS.items():
        lo, hi = pd.Period(first, "M"), pd.Period(last, "M")
        sliced = {k: f[(f.index >= lo) & (f.index <= hi)] for k, f in results.items()}
        out[name] = {k: descriptive_metrics(f, sliced["B0"]["r"], returns) for k, f in sliced.items() if len(f) > 1}
    return out


def provenance() -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
    return {"git_commit": git_commit(), "seed": SEED,
            "data": {k: {"sha256": v.get("sha256"), "downloaded_at_utc": v.get("downloaded_at_utc")}
                     for k, v in manifest.items()}}


def run_insample(out_dir: Path = RESULTS_DIR / "insample") -> None:
    fred = load_fred()
    schedule = build_schedule(fred["DGS10"], fred["DTB3"], INSAMPLE_FIRST_SIGNAL_MONTH, INSAMPLE_LAST_SIGNAL_MONTH)
    indices = synthetic_indices(fred["DGS10"], fred["DTB3"])
    summary = run_window("in-sample, synthetic instruments", indices, fred, schedule, None, out_dir,
                         with_subperiods=True, with_daily=False)
    base, stress = summary["cost_cases"]["base"], summary["cost_cases"]["stress"]
    summary["criteria"] = insample_criteria(base["descriptive"], base["inference"], base["deflated_sharpe"],
                                            stress["descriptive"], stress["inference"])
    summary["criteria_T2_T3"] = {t: insample_criteria(base["descriptive"], base["inference"],
                                                      base["deflated_sharpe"], stress["descriptive"],
                                                      stress["inference"], t) for t in ("T2", "T3")}
    summary["provenance"] = provenance()
    write_json(out_dir / "summary.json", summary)
    print(f"in-sample written to {out_dir.relative_to(STUDY_DIR)}; criteria {summary['criteria']}")


def run_oos(out_dir: Path = RESULTS_DIR / "oos") -> None:
    if out_dir.exists():
        raise SystemExit("results/oos/ exists: the out-of-sample run is executed exactly once (§8.2)")
    insample = json.loads((RESULTS_DIR / "insample" / "summary.json").read_text(encoding="utf-8"))
    weight_b3 = float(insample["weight_b3"])
    fred = load_fred()
    schedule = build_schedule(fred["DGS10"], fred["DTB3"], OOS_FIRST_SIGNAL_MONTH, OOS_LAST_SIGNAL_MONTH)
    actual = actual_indices()
    bar_dates = actual[DURATION_LEG].index.intersection(actual[CASH_LEG].index)
    resolved = backtest.resolve_execution_dates(schedule, bar_dates)
    summary = {"actual": run_window("out-of-sample, actual ETFs", actual, fred, resolved, weight_b3,
                                    out_dir / "actual", with_subperiods=False, with_daily=True),
               "synthetic": run_window("out-of-sample, synthetic instruments",
                                       synthetic_indices(fred["DGS10"], fred["DTB3"]), fred, schedule,
                                       weight_b3, out_dir / "synthetic", with_subperiods=False, with_daily=False)}
    base = summary["actual"]["cost_cases"]["base"]
    o = oos_criteria(base["descriptive"], base["inference"])
    t_vs_b3 = base["inference"]["T1"]["vs_B3"]["newey_west"]["t"]
    summary["criteria"] = o
    summary["verdict_T1"] = verdict(insample["criteria"], o, t_vs_b3,
                                    base["max_drawdown_daily"]["T1"], base["max_drawdown_daily"]["B1"])
    summary["criteria_T2_T3"] = {t: oos_criteria(base["descriptive"], base["inference"], t) for t in ("T2", "T3")}
    summary["weight_b3_frozen_from_insample"] = weight_b3
    summary["provenance"] = provenance()
    write_json(out_dir / "summary.json", summary)
    print(f"out-of-sample written to {out_dir.relative_to(STUDY_DIR)}; verdict for T1: {summary['verdict_T1']}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Study 001 runs (§8, §9). Invoke through reproduce.sh.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--insample", action="store_true")
    group.add_argument("--oos", action="store_true")
    args = parser.parse_args(argv)
    if args.insample:
        run_insample()
    else:
        run_oos()


if __name__ == "__main__":
    main()
