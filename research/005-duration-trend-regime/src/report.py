"""The in-sample run and the hypothesis-generating episode: tables, the
conditional edge, the §9.5 row and the §9.7 descriptives into ``results/``
(§8, §9).

``python -m src.report --insample`` writes ``results/insample/`` once and
freezes the B3 weight at T1's in-sample IEF fraction (§5.3.5 (vi), §9.1);
``python -m src.report --episode`` reads that weight, runs 2019–2026 once on
the broker's bars under the label of §8.2 and writes ``results/episode/``.
Both refuse if their folder exists and are invoked only through
``reproduce.sh`` after approval.  The same frozen engine, costs and
statistics are used for every trial, benchmark and window.

The descriptive-metric, deflation and sub-period functions are adapted from
Study 003's ``report.py`` (commit 987b161) with the library's statistics in
place of the study's copy.  New here: the regime inputs, the conditional
paths of T1–T3 through ``pipeline.window_paths``, the edge statistics of
``edge.py``, the §9.5 row and the §9.7 positive-regime episode table.
Charts (§9.7) are drawn from the committed results by ``charts.py`` in a
later step, not by this module, so that every published number exists in a
results file before any picture of it.

Layout decisions fixed here before any run (recorded in §16): a descriptive
trial (T2, T3) runs on the holding periods on which its regime variable is
defined, which can start later than T1's (the 252-day window and the lagged
CPI change need history that the broker's SPY file, fetched from 2018-09-01,
does not reach for the first episode months); its tables name its own first
period.  T1 must be defined on every period of the window, else the run
stops.  ``d_t`` is the same series for every trial of a window (B2 − B1 does
not depend on the regime); each trial's edge is computed on its own months.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from qune_research import stats

from . import data, regime
from .config import (
    CASH_LEG,
    COST_CASES,
    DURATION_LEG,
    EPISODE_FIRST_SIGNAL_MONTH,
    EPISODE_LAST_SIGNAL_MONTH,
    INSAMPLE_FIRST_SIGNAL_MONTH,
    INSAMPLE_LAST_SIGNAL_MONTH,
    MANIFEST_PATH,
    N_TRIALS_REGISTERED,
    N_TRIALS_SENSITIVITY,
    RESULTS_DIR,
    SEED,
    STUDY_DIR,
    SUBPERIODS,
    TRIAL_IDS,
)
from .edge import conditional_edge, insample_row, regime_descriptives
from .pipeline import (
    etf_indices,
    insample_indices,
    period_targets,
    trend_frame,
    window_bars,
    window_paths,
    window_schedule,
)

BENCHMARK_IDS = ("B0", "B1", "B2", "B3")
EPISODE_LABEL = "hypothesis-generating episode (no decision weight)"


# --- Regimes on a window -------------------------------------------------------------

def regime_frames(close_spy: pd.Series, close_ief: pd.Series, cpi: pd.Series | None,
                  schedule: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """T1, T2 (and T3 when the CPI series exists) regime frames on the
    schedule's signal dates (§6.1, §7)."""
    dates = schedule["signal_date"]
    returns = regime.common_returns(close_spy, close_ief)
    frames = {t: regime.correlation_regime(returns, dates, t) for t in ("T1", "T2")}
    if cpi is not None:
        frames["T3"] = regime.cpi_regime(cpi, dates)
    return frames


# --- Metrics (Study 003 §9.3 items 1-6 and 11, inherited by §9.4) -----------------------

def descriptive_metrics(frame: pd.DataFrame, r_cash: pd.Series, returns: pd.DataFrame) -> dict[str, float]:
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
        out["switches"] = int(frame["switched"].sum())
        out["switches_per_year"] = float(frame["switched"].sum() / years)
        out["fraction_in_ief"] = float((frame["holding"] == DURATION_LEG).mean())
        out["hit_rate_held_vs_other"] = float((frame["r_held_minus_other"] > 0).mean())
    else:
        w = float(frame["weight_ief"].iloc[0])
        out["switches"] = 0
        out["switches_per_year"] = 0.0
        out["fraction_in_ief"] = w
        ief_better = returns[DURATION_LEG].reindex(r.index) > returns[CASH_LEG].reindex(r.index)
        if w == 1.0:
            out["hit_rate_held_vs_other"] = float(ief_better.mean())
        elif w == 0.0:
            out["hit_rate_held_vs_other"] = float((~ief_better).mean())
        else:
            out["hit_rate_held_vs_other"] = float("nan")
    return out


def deflation(descriptives: dict[str, dict], trials: tuple[str, ...]) -> tuple[dict[str, dict], dict]:
    """DSR for every trial that ran, N = 3 and N = 10, reported without
    decision weight (§9.4); V from the monthly Sharpe ratios across the
    trials that ran."""
    sharpes = [descriptives[t]["sharpe_monthly"] for t in trials]
    variance, floored = stats.trial_variance(sharpes)
    out = {}
    for t in trials:
        d = descriptives[t]
        out[t] = {f"N{n}": stats.deflated_sharpe(d["sharpe_monthly"], d["periods"], d["skewness_excess"],
                                                 d["kurtosis_excess"], n, variance)
                  for n in (N_TRIALS_REGISTERED, N_TRIALS_SENSITIVITY)}
    return out, {"variance_across_trials": variance, "floor_applied": floored, "trials_in_variance": list(trials)}


def subperiod_edges(d: pd.Series, positive: pd.Series, schedule: pd.DataFrame) -> dict:
    """§9.7: d_t by regime within Study 003's sub-periods, sliced by the
    calendar month of the holding period's execution date; means and counts
    only (no interval: the slices are too short for one)."""
    start_month = schedule["execution_date"].dt.to_period("M")
    positive = positive.reindex(d.index).astype(bool)
    out = {}
    for name, (first, last) in SUBPERIODS.items():
        lo, hi = pd.Period(first, "M"), pd.Period(last, "M")
        months = start_month[(start_month >= lo) & (start_month <= hi)].index.intersection(d.index)
        ds, ps = d.loc[months], positive.loc[months]
        n_pos, n_neg = int(ps.sum()), int((~ps).sum())
        out[name] = {"months": int(len(ds)), "n_pos": n_pos, "n_neg": n_neg,
                     "mean_positive": float(ds[ps].mean()) if n_pos else float("nan"),
                     "mean_negative": float(ds[~ps].mean()) if n_neg else float("nan")}
        out[name]["delta"] = out[name]["mean_positive"] - out[name]["mean_negative"]
    return out


def positive_episode_table(positive: pd.Series, schedule: pd.DataFrame, b2_holding: pd.Series,
                           ief_excess: pd.Series) -> pd.DataFrame:
    """§9.7: every positive-regime episode with its first and last signal
    date, length, the share of its months B2 held bills and IEF's mean
    excess return over cash in it."""
    flags = positive.astype(bool)
    rows, start = [], None
    months = list(flags.index)
    for i, m in enumerate(months):
        if flags.iloc[i] and start is None:
            start = i
        last = i == len(months) - 1
        if start is not None and (not flags.iloc[i] or last):
            end = i if (flags.iloc[i] and last) else i - 1
            span = months[start:end + 1]
            rows.append({"first_month": str(span[0]), "last_month": str(span[-1]),
                         "first_signal_date": str(schedule.loc[span[0], "signal_date"].date()),
                         "last_signal_date": str(schedule.loc[span[-1], "signal_date"].date()),
                         "months": len(span),
                         "share_b2_in_bills": float((b2_holding.reindex(span) == CASH_LEG).mean()),
                         "mean_ief_excess": float(ief_excess.reindex(span).mean()),
                         "sum_ief_excess": float(ief_excess.reindex(span).sum())})
            start = None
    return pd.DataFrame(rows)


# --- One window ------------------------------------------------------------------------

def run_window(label: str, indices: dict[str, pd.Series], close_spy: pd.Series, close_ief: pd.Series,
               cpi: pd.Series | None, bars: pd.DatetimeIndex, first_month: str, last_month: str,
               weight_b3: float | None, out_dir: Path, decision_weight: bool) -> dict:
    """Every table of §9.2–9.4 and §9.7 for one window: T1–T3 on their
    regime variables, B0–B3, both cost cases."""
    out_dir.mkdir(parents=True, exist_ok=True)
    schedule, month_ends = window_schedule(bars, first_month, last_month)
    trend = trend_frame(indices, month_ends, schedule)
    trend_targets = period_targets(trend, schedule)
    regimes = regime_frames(close_spy, close_ief, cpi, schedule)
    trials = tuple(t for t in TRIAL_IDS if t in regimes)
    positives = {t: regimes[t]["positive"].reindex(trend_targets.index) for t in trials}
    if positives["T1"].isna().any():
        raise SystemExit("T1's regime is undefined on a holding period of the window; the run stops (§5.3.6)")
    trial_months = {t: positives[t].dropna().index for t in trials}
    summary = {"label": label, "decision_weight": decision_weight, "holding_periods": int(len(trend_targets)),
               "first_execution_date": str(schedule["execution_date"].iloc[0].date()),
               "last_period_end": str(schedule["period_end"].iloc[-2].date()),
               "months_without_signal": schedule.attrs.get("months_without_signal", 0),
               "trials_run": list(trials),
               "trials_not_run": [t for t in TRIAL_IDS if t not in trials],
               "trial_first_period": {t: str(trial_months[t][0]) for t in trials},
               "trial_periods": {t: int(len(trial_months[t])) for t in trials},
               "terminal_trend_target": str(trend["target"].iloc[-1]),
               "terminal_trend_value": float(trend["value"].iloc[-1]),
               "terminal_regime": {t: {"signal_date": str(regimes[t]["signal_date"].iloc[-1].date()),
                                       "positive": bool(regimes[t]["positive"].iloc[-1]),
                                       **({"rho": float(regimes[t]["rho"].iloc[-1])} if "rho" in regimes[t] else
                                          {"cpi_12m_change": float(regimes[t]["cpi_12m_change"].iloc[-1]),
                                           "cpi_month": str(regimes[t]["cpi_month"].iloc[-1])})}
                                   for t in trials},
               "regime_descriptives": {t: regime.regime_episodes(positives[t].dropna()) for t in trials},
               "cost_cases": {}}
    if "days_slipped" in schedule:
        summary["execution_dates_slipped"] = {str(k): int(v) for k, v in
                                              schedule.loc[schedule["days_slipped"] > 0, "days_slipped"].items()}
    frozen_weight = weight_b3
    for case, cost in COST_CASES.items():
        rng = np.random.default_rng(SEED)
        primary = window_paths(indices, schedule, trend_targets, positives["T1"], cost, frozen_weight)
        if frozen_weight is None:
            frozen_weight = primary["weight_b3"]
            summary["weight_b3"] = frozen_weight
        results = {b: primary["results"][b] for b in BENCHMARK_IDS}
        results["T1"] = primary["results"]["T1"]
        for t in trials:
            if t == "T1":
                continue
            own = window_paths(indices, schedule, trend_targets.loc[trial_months[t]], positives[t].loc[trial_months[t]],
                               cost, frozen_weight)
            results[t] = own["results"]["T1"]
        returns, d = primary["returns"], primary["d"]
        desc = {name: descriptive_metrics(f, results["B0"]["r"], returns) for name, f in results.items()}
        edges, companions, versus = {}, {}, {}
        for t in trials:
            pos = positives[t].loc[trial_months[t]]
            edges[t] = conditional_edge(d.loc[trial_months[t]], pos, rng)
            companions[t] = regime_descriptives(d.loc[trial_months[t]], pos, primary["b2_in_bills"],
                                                primary["ief_excess"])
            rt = results[t]["r"]
            versus[t] = {f"vs_{b}": stats.newey_west_mean(rt - results[b]["r"].reindex(rt.index))
                         for b in ("B2", "B3")}
            versus[t]["switches_T_vs_B2"] = {"trial": int(results[t]["switched"].sum()),
                                             "B2_same_months": int(results["B2"]["switched"].reindex(rt.index).sum())}
        sharpe_ci = {t: stats.sharpe_ci_stationary_bootstrap(results[t]["r"] - results["B0"]["r"].reindex(results[t].index),
                                                             rng) for t in trials}
        dsr, dsr_inputs = deflation(desc, trials)
        case_summary = {"cost_per_side": cost, "descriptive": desc, "edge": edges, "edge_companions": companions,
                        "versus_benchmarks": versus, "sharpe_ci": sharpe_ci, "deflated_sharpe": dsr,
                        "deflation_inputs": dsr_inputs,
                        "subperiods_d_by_regime": {t: subperiod_edges(d.loc[trial_months[t]], positives[t], schedule)
                                                   for t in trials}}
        if case == "base":
            case_summary["rows_9_5"] = {t: insample_row(edges[t]) for t in trials}
            case_summary["rows_9_5_note"] = ("T1's row is the study's in-sample check; T2 and T3 rows are descriptive "
                                             "(§7)") if decision_weight else \
                "no row applies: the window is the hypothesis-generating episode (§8.2)"
        summary["cost_cases"][case] = case_summary
        pd.DataFrame(desc).T.to_csv(out_dir / f"metrics_{case}.csv")
        monthly = pd.concat({name: f["r"] for name, f in results.items()}, axis=1)
        monthly["d"] = d.reindex(monthly.index)
        for t in trials:
            monthly[f"{t}_holding"] = results[t]["holding"].reindex(monthly.index)
            monthly[f"positive_{t}"] = positives[t].reindex(monthly.index)
        monthly.insert(0, "B2_holding", results["B2"]["holding"])
        monthly.insert(0, "mom_at_signal", trend["value"].reindex(monthly.index))
        for t in ("T1", "T2"):
            if t in regimes:
                monthly.insert(0, f"rho_{t}", regimes[t]["rho"].reindex(monthly.index))
        if "T3" in regimes:
            monthly.insert(0, "cpi_12m_change_T3", regimes["T3"]["cpi_12m_change"].reindex(monthly.index))
        monthly.insert(0, "period_end", schedule["period_end"].reindex(monthly.index).dt.date)
        monthly.insert(0, "execution_date", schedule["execution_date"].reindex(monthly.index).dt.date)
        monthly.insert(0, "signal_date", schedule["signal_date"].reindex(monthly.index).dt.date)
        monthly.to_csv(out_dir / f"monthly_{case}.csv")
        if case == "base":
            for t in trials:
                table = positive_episode_table(positives[t].loc[trial_months[t]], schedule,
                                               results["B2"]["holding"], primary["ief_excess"])
                table.to_csv(out_dir / f"positive_episodes_{t}.csv", index=False)
    return summary


# --- Provenance and entry points ------------------------------------------------------------

def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=STUDY_DIR, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _json_default(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, pd.Period)):
        return str(value)
    raise TypeError(f"not serialisable: {type(value)}")


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n", encoding="utf-8")


def provenance() -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
    return {"git_commit": git_commit(), "seed": SEED,
            "data": {k: {"sha256": v.get("sha256"), "downloaded_at_utc": v.get("downloaded_at_utc")}
                     for k, v in manifest.items()}}


def _cpi_or_none() -> pd.Series | None:
    """The CPIAUCNS file if §5.3.3 step 2 fetched and recorded it; None
    otherwise (T3 then reads "not run: series unavailable").  A run never
    fetches: fetches happen under step 3, logged first."""
    from qune_research import data as lib

    from .config import CPI_SERIES, RAW_DIR
    path = lib.fred_path(CPI_SERIES, RAW_DIR)
    if path.exists() and path.name in lib.read_manifest(MANIFEST_PATH):
        return lib.load_fred(CPI_SERIES, RAW_DIR)
    return None


def run_insample(out_dir: Path = RESULTS_DIR / "insample") -> None:
    if out_dir.exists():
        raise SystemExit("results/insample/ exists: the in-sample run is executed once (§14 step 6)")
    tiingo = data.insample_closes()
    indices = insample_indices(tiingo[DURATION_LEG], data.dtb3_series())
    bars = window_bars(indices, etf_cash=False)
    summary = run_window("in-sample, vendor IEF and SPY history and the cash accrual", indices,
                         tiingo["SPY"], tiingo[DURATION_LEG], _cpi_or_none(), bars,
                         INSAMPLE_FIRST_SIGNAL_MONTH, INSAMPLE_LAST_SIGNAL_MONTH, None, out_dir, decision_weight=True)
    base = summary["cost_cases"]["base"]
    summary["row_9_5_T1"] = base["rows_9_5"]["T1"]
    summary["provenance"] = provenance()
    write_json(out_dir / "summary.json", summary)
    print(f"in-sample written to {out_dir.relative_to(STUDY_DIR)}; §9.5 row for T1: {summary['row_9_5_T1']}; "
          f"rows T2/T3 (descriptive): {[base['rows_9_5'].get(t) for t in ('T2', 'T3')]}")


def run_episode(out_dir: Path = RESULTS_DIR / "episode") -> None:
    if out_dir.exists():
        raise SystemExit("results/episode/ exists: the episode is run exactly once (§8.2, §14 step 8)")
    insample_summary = RESULTS_DIR / "insample" / "summary.json"
    if not insample_summary.exists():
        raise SystemExit("results/insample/summary.json missing: the episode runs after the in-sample results are "
                         "committed (§8.2, §14 step 8)")
    weight_b3 = float(json.loads(insample_summary.read_text(encoding="utf-8"))["weight_b3"])
    closes = data.episode_closes()
    indices = etf_indices(closes)
    bars = window_bars(indices, etf_cash=True)
    summary = run_window(EPISODE_LABEL, indices, closes["SPY"], closes[DURATION_LEG], _cpi_or_none(), bars,
                         EPISODE_FIRST_SIGNAL_MONTH, EPISODE_LAST_SIGNAL_MONTH, weight_b3, out_dir,
                         decision_weight=False)
    summary["weight_b3_frozen_from_insample"] = weight_b3
    summary["provenance"] = provenance()
    write_json(out_dir / "summary.json", summary)
    print(f"episode written to {out_dir.relative_to(STUDY_DIR)} under the label '{EPISODE_LABEL}'; "
          f"no verdict row (§8.2)")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Study 005 runs (§8, §9). Invoke through reproduce.sh.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--insample", action="store_true")
    group.add_argument("--episode", action="store_true")
    args = parser.parse_args(argv)
    if args.insample:
        run_insample()
    else:
        run_episode()


if __name__ == "__main__":
    main()
