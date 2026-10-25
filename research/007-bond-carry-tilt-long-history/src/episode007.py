"""Study 007 2019-2026 episode (PREREGISTRATION.md §8.2): once, after the
history note is committed (§14 step 9).  No decision weight; no criterion and
no verdict are computed here.

Actual IEF and BIL from Alpaca (``adjustment='all'``) with the synthetic
series alongside, on the 93 periods from the first execution date of January
2019 to that of October 2026.  The carry and its expanding rank come from FRED
and continue to expand through the episode (no re-estimation); the trend
signal is read from the ETF closes on the actual side and from the synthetic
indices on the synthetic side (§6.3); each trial's B3 is at the weight frozen
by the history run (§8.1, §9.1).  The engine is ``tilt.run_tilt`` as in the
history run.  The five trials' weights at the last signal month are written
for the forward record's starting holdings (§11.2).

    python -m src.episode007    # writes results/episode/ once
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import backtest, report, tilt
from .calendar import build_schedule
from .carry_rank import blend, trend_signal
from .config import CASH_LEG, COST_CASES, DURATION_LEG, SEED, STUDY_DIR
from .config007 import (
    CARRY_FIRST_SIGNAL_MONTH,
    EPISODE_DIR,
    EPISODE_FIRST_SIGNAL_MONTH,
    EPISODE_LAST_SIGNAL_MONTH,
    EPISODE_PERIODS,
    HISTORY_DIR,
    MIN_HISTORY,
    PRIMARY,
    TREND_LAG_ROWS,
    TRIAL_IDS,
)
from .episode import note_committed
from .gate007 import WEIGHT_COLUMNS, index_at_signal_dates, weight_paths
from .history007 import tilt_descriptives
from .synthetic import synthetic_indices

HEADING = "2019–2026 episode (no decision weight)"
KNOWN_WINDOW_NOTE = (
    "For T2 and T3 the trend part of this window is published (Study 003's out-of-sample run, Study 004's "
    "attribution): for them the episode is a recomputation on a known window (§8.2)."
)


def frozen_weights(history_dir: Path = HISTORY_DIR) -> dict[str, float]:
    """Each trial's B3 weight as frozen by the history run (§8.1)."""
    w = json.loads((history_dir / "summary.json").read_text(encoding="utf-8"))["weight_b3"]
    missing = [k for k in TRIAL_IDS if k not in w]
    if missing:
        raise ValueError(f"history summary has no frozen weight for {missing}")
    return {k: float(w[k]) for k in TRIAL_IDS}


def actual_side_weights(paths: pd.DataFrame, full: pd.DataFrame, actual: dict[str, pd.Series],
                        months: pd.Index) -> pd.DataFrame:
    """The weight paths on the actual side for the given months: carry ranks
    as on the synthetic side (FRED only); the trend from the ETF closes read
    at the last bar on or before each signal date, with the twelve earlier
    signal dates taken from the schedule (§6.3)."""
    first = full.index.get_loc(months[0])
    if first < TREND_LAG_ROWS:
        raise ValueError("the schedule has fewer than twelve rows before the episode")
    tail = full.iloc[first - TREND_LAG_ROWS:]
    dates = tail["signal_date"]
    leg = index_at_signal_dates(actual[DURATION_LEG], dates)
    cash = index_at_signal_dates(actual[CASH_LEG], dates)
    h = trend_signal(leg, cash, dates).reindex(months)
    out = pd.DataFrame(index=months)
    for k in MIN_HISTORY:
        out[WEIGHT_COLUMNS[k]] = paths[WEIGHT_COLUMNS[k]].reindex(months)
    out["trend"] = h
    out[WEIGHT_COLUMNS["T2"]] = blend(out[WEIGHT_COLUMNS[PRIMARY]], h)
    out[WEIGHT_COLUMNS["T3"]] = h
    return out


def run_side(label: str, weights: pd.DataFrame, returns: pd.DataFrame, schedule: pd.DataFrame,
             frozen: dict[str, float], out_dir: Path) -> dict:
    """Five trials and their benchmarks on one side (actual or synthetic),
    both cost cases, metrics and monthly files; no criterion."""
    out_dir.mkdir(parents=True, exist_ok=True)
    w = {k: weights[WEIGHT_COLUMNS[k]].reindex(returns.index) for k in TRIAL_IDS}
    for k, series in w.items():
        if series.isna().any():
            raise ValueError(f"{k} has no weight on {int(series.isna().sum())} episode periods")
    summary = {
        "label": label,
        "holding_periods": int(len(returns)),
        "first_execution_date": str(schedule["execution_date"].iloc[0].date()),
        "last_period_end": str(schedule["period_end"].iloc[-2].date()),
        "weight_b3_frozen_from_history": frozen,
        "mean_weight_in_episode": {k: float(w[k].mean()) for k in TRIAL_IDS},
        "cost_cases": {},
    }
    if "days_slipped" in schedule:
        summary["execution_dates_slipped"] = schedule.loc[schedule["days_slipped"] > 0, "days_slipped"].to_dict()
    for case, cost in COST_CASES.items():
        rng = np.random.default_rng(SEED)
        results = {}
        for k in TRIAL_IDS:
            res = backtest.benchmarks(returns, frozen[k], cost)
            res["T"] = tilt.run_tilt(w[k], returns, cost)
            results[k] = res
        desc = {
            k: {
                name: (tilt_descriptives(f, results[k]["B0"]["r"], returns) if name == "T"
                       else report.descriptive_metrics(f, results[k]["B0"]["r"], returns))
                for name, f in results[k].items()
            }
            for k in TRIAL_IDS
        }
        infer = {k: report.inference_metrics(k, results[k]["T"], results[k], rng) for k in TRIAL_IDS}
        summary["cost_cases"][case] = {
            "cost_per_side": cost,
            "descriptive": desc,
            "inference": infer,
            "total_turnover": {k: tilt.total_turnover(results[k]["T"]) for k in TRIAL_IDS},
            "T_minus_B3_mean_annual": {
                k: float((results[k]["T"]["r"] - results[k]["B3"]["r"]).mean()) * 12.0 for k in TRIAL_IDS
            },
        }
        pd.DataFrame({k: desc[k]["T"] for k in TRIAL_IDS}).T.to_csv(out_dir / f"metrics_{case}.csv")
        monthly = pd.concat(
            {**{k: results[k]["T"]["r"] for k in TRIAL_IDS},
             **{f"B3_{k}": results[k]["B3"]["r"] for k in TRIAL_IDS},
             **{b: results[PRIMARY][b]["r"] for b in ("B0", "B1", "B2")}},
            axis=1,
        )
        for k in reversed(TRIAL_IDS):
            monthly.insert(0, f"w_{k}", w[k])
        monthly.insert(0, "period_end", schedule["period_end"].reindex(monthly.index).dt.date)
        monthly.insert(0, "execution_date", schedule["execution_date"].reindex(monthly.index).dt.date)
        monthly.to_csv(out_dir / f"monthly_{case}.csv")
    return summary


def compute(
    fred: dict[str, pd.Series],
    actual: dict[str, pd.Series],
    frozen: dict[str, float],
    carry_first_month: str,
    first_month: str,
    last_month: str,
    out_dir: Path,
    min_history: dict[str, int] = MIN_HISTORY,
    expected_periods: int | None = None,
) -> dict:
    full = build_schedule(fred["DGS10"], fred["DTB3"], carry_first_month, last_month)
    synthetic = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    paths = weight_paths(fred["DGS10"], fred["DGS7"], fred["DTB3"], full, synthetic, min_history)
    schedule = build_schedule(fred["DGS10"], fred["DTB3"], first_month, last_month)
    if expected_periods is not None and len(schedule) - 1 != expected_periods:
        raise ValueError(f"{len(schedule) - 1} episode periods, expected {expected_periods}")
    months = schedule.index[:-1]
    bar_dates = actual[DURATION_LEG].index.intersection(actual[CASH_LEG].index)
    resolved = backtest.resolve_execution_dates(schedule, bar_dates)
    w_actual = actual_side_weights(paths, full, actual, months)
    last_month_weights = actual_side_weights(paths, full, actual, schedule.index[-1:]).iloc[0]
    return {
        "study": "007",
        "section": "PREREGISTRATION.md §8.2",
        "heading": HEADING,
        "known_window_note": KNOWN_WINDOW_NOTE,
        "weight_b3_frozen_from_history": frozen,
        "rank_history_months_at_episode_end": int(len(full)),
        "weights_at_last_signal_month_for_forward_record": {
            "signal_month": str(schedule.index[-1]),
            "signal_date": str(schedule["signal_date"].iloc[-1].date()),
            **{k: round(float(last_month_weights[WEIGHT_COLUMNS[k]]), 4) for k in TRIAL_IDS},
            "carry": round(float(paths["carry"].iloc[-1]), 4),
            "n": int(paths["n"].iloc[-1]),
        },
        "actual": run_side(f"{HEADING}, actual ETFs", w_actual, backtest.instrument_returns(actual, resolved),
                           resolved, frozen, out_dir / "actual"),
        "synthetic": run_side(f"{HEADING}, synthetic instruments", paths, backtest.instrument_returns(synthetic, schedule),
                              schedule, frozen, out_dir / "synthetic"),
    }


def main(
    argv: list[str] | None = None,
    history_dir: Path = HISTORY_DIR,
    out_dir: Path = EPISODE_DIR,
    study_dir: Path = STUDY_DIR,
) -> int:
    argparse.ArgumentParser(description="Study 007 2019-2026 episode (§8.2), once.").parse_args(argv)
    if not (history_dir / "summary.json").exists():
        raise SystemExit("refused: results/history/summary.json is missing; the episode needs the frozen w (§8.2)")
    if not note_committed(study_dir):
        raise SystemExit("refused: README.md (the history note) is not committed with a verdict (§8.2, §14 step 8)")
    if out_dir.exists():
        raise SystemExit(f"refused: {out_dir.name}/ exists; the episode runs once (§8.2)")
    summary = compute(
        report.load_fred(),
        report.actual_indices(),
        frozen_weights(history_dir),
        CARRY_FIRST_SIGNAL_MONTH,
        EPISODE_FIRST_SIGNAL_MONTH,
        EPISODE_LAST_SIGNAL_MONTH,
        out_dir,
        expected_periods=EPISODE_PERIODS,
    )
    summary["run_at_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary["provenance"] = report.provenance()
    report.write_json(out_dir / "summary.json", summary)
    print(f"episode written to {out_dir.relative_to(STUDY_DIR)} under '{HEADING}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
