"""Study 008 2019-2026 episode (PREREGISTRATION.md §8.2): once, after the
history note is committed (§14 step 9).  No decision weight; no criterion and
no verdict are computed here.

Actual IEF and BIL from Alpaca (``adjustment='all'``) with the synthetic
series alongside, on the 93 periods from the first execution date of January
2019 to that of October 2026.  The real yields come from FRED's DGS10 and the
two CPI files only (``gate008.weight_paths``), so both sides carry the same
weight path; the expanding rank keeps expanding and T1b's keeps trailing
through the episode (no re-estimation).  A month whose real yield is
undefined (the October 2025 index was never published: signal month 2025-11)
holds (§6.1, §6.4) through ``history008.run_tilt_hold``.  Each trial's B3 is at
the weight frozen by the history run (§8.1, §9.1).  The three trials' weights
at the last signal month are written for the forward record's starting
holdings (§11.2).

    python -m src.episode008    # writes results/episode/ once
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
from .config import CASH_LEG, COST_CASES, DURATION_LEG, SEED, STUDY_DIR
from .config008 import (
    CPI_AVAILABILITY_PATH,
    CPI_SERIES,
    EPISODE_DIR,
    EPISODE_FIRST_SIGNAL_MONTH,
    EPISODE_LAST_SIGNAL_MONTH,
    EPISODE_PERIODS,
    HISTORY_DIR,
    PRIMARY,
    RANK_KIND,
    RANK_N,
    REAL_YIELD_FIRST_SIGNAL_MONTH,
    TRIAL_IDS,
)
from .episode import note_committed
from .fred import load_series
from .gate008 import WEIGHT_COLUMNS, weight_paths
from .history007 import tilt_descriptives
from .history008 import run_tilt_hold
from .real_yield import rank_defined
from .synthetic import synthetic_indices

HEADING = "2019–2026 episode (no decision weight)"
KNOWN_WINDOW_NOTE = (
    "The episode's bond returns are published (Studies 004, 006 and 007 report IEF over 2019-2026), and real yields "
    "over 2019-2026 are general knowledge: the episode is a recomputation on a known window (§8.2), not a test."
)


def frozen_weights(history_dir: Path = HISTORY_DIR) -> dict[str, float]:
    """Each trial's B3 weight as frozen by the history run (§8.1), for every
    trial the gate did not drop (the history summary's ``dropped_at_gate``,
    §5.3: a dropped trial has no return anywhere, the episode included)."""
    summary = json.loads((history_dir / "summary.json").read_text(encoding="utf-8"))
    w, dropped = summary["weight_b3"], set(summary.get("dropped_at_gate", []))
    expected = [k for k in TRIAL_IDS if k not in dropped]
    missing = [k for k in expected if k not in w]
    if missing:
        raise ValueError(f"history summary has no frozen weight for {missing}")
    extra = [k for k in w if k not in expected]
    if extra:
        raise ValueError(f"history summary has a frozen weight for a trial dropped at the gate: {extra}")
    return {k: float(w[k]) for k in expected}


def run_side(label: str, paths: pd.DataFrame, returns: pd.DataFrame, schedule: pd.DataFrame,
             frozen: dict[str, float], out_dir: Path) -> dict:
    """The trials in ``frozen`` (those the gate did not drop) and their
    benchmarks on one side (actual or synthetic), both cost cases, metrics and
    monthly files; no criterion."""
    out_dir.mkdir(parents=True, exist_ok=True)
    trials = tuple(k for k in TRIAL_IDS if k in frozen)
    w = {k: paths[WEIGHT_COLUMNS[k]].reindex(returns.index) for k in trials}
    summary = {
        "label": label,
        "holding_periods": int(len(returns)),
        "first_execution_date": str(schedule["execution_date"].iloc[0].date()),
        "last_period_end": str(schedule["period_end"].iloc[-2].date()),
        "weight_b3_frozen_from_history": frozen,
        "trials_run": list(trials),
        "hold_periods": {k: [str(m) for m in w[k].index[w[k].isna().to_numpy()]] for k in trials},
        "mean_signal_weight_in_episode": {k: float(w[k].mean()) for k in trials},
        "cost_cases": {},
    }
    if "days_slipped" in schedule:
        summary["execution_dates_slipped"] = {
            str(m): int(v) for m, v in schedule.loc[schedule["days_slipped"] > 0, "days_slipped"].items()
        }
    for case, cost in COST_CASES.items():
        rng = np.random.default_rng(SEED)
        results = {}
        for k in trials:
            res = backtest.benchmarks(returns, frozen[k], cost)
            res["T"] = run_tilt_hold(w[k], returns, cost)
            results[k] = res
        desc = {
            k: {
                name: (tilt_descriptives(f, results[k]["B0"]["r"], returns) if name == "T"
                       else report.descriptive_metrics(f, results[k]["B0"]["r"], returns))
                for name, f in results[k].items()
            }
            for k in trials
        }
        infer = {k: report.inference_metrics(k, results[k]["T"], results[k], rng) for k in trials}
        summary["cost_cases"][case] = {
            "cost_per_side": cost,
            "descriptive": desc,
            "inference": infer,
            "total_turnover": {k: tilt.total_turnover(results[k]["T"]) for k in trials},
            "T_minus_B3_mean_annual": {
                k: float((results[k]["T"]["r"] - results[k]["B3"]["r"]).mean()) * 12.0 for k in trials
            },
        }
        pd.DataFrame({k: desc[k]["T"] for k in trials}).T.to_csv(out_dir / f"metrics_{case}.csv")
        monthly = pd.concat(
            {**{k: results[k]["T"]["r"] for k in trials},
             **{f"B3_{k}": results[k]["B3"]["r"] for k in trials},
             **{b: results[PRIMARY][b]["r"] for b in ("B0", "B1", "B2")}},
            axis=1,
        )
        for k in reversed(trials):
            monthly.insert(0, f"hold_{k}", results[k]["T"]["hold"])
            monthly.insert(0, f"w_{k}", results[k]["T"]["weight"])
        monthly.insert(0, "period_end", schedule["period_end"].reindex(monthly.index).dt.date)
        monthly.insert(0, "execution_date", schedule["execution_date"].reindex(monthly.index).dt.date)
        monthly.index.name = "month"
        monthly.to_csv(out_dir / f"monthly_{case}.csv")
    return summary


def forward_start(paths: pd.DataFrame, month: pd.Period, signal_date: pd.Timestamp) -> dict:
    """§11.2: the three trials' weights at the last episode signal month (to
    four decimals), with r and n_m for each CPI series; a trial without a
    weight there (r undefined) is reported as None."""
    row = paths.loc[month]
    out: dict = {"signal_month": str(month), "signal_date": str(signal_date.date())}
    for k in TRIAL_IDS:
        v = row[WEIGHT_COLUMNS[k]]
        out[k] = None if pd.isna(v) else round(float(v), 4)
    for s in sorted(set(CPI_SERIES.values())):
        out[f"r_{s}"] = None if pd.isna(row[f"r_{s}"]) else float(row[f"r_{s}"])
        out[f"n_defined_{s}"] = int(paths[f"r_{s}"].loc[:month].notna().sum())
    return out


def compute(
    fred: dict[str, pd.Series],
    cpi: dict[str, pd.Series],
    availability: pd.DataFrame,
    actual: dict[str, pd.Series],
    frozen: dict[str, float],
    real_yield_first_month: str,
    first_month: str,
    last_month: str,
    out_dir: Path,
    rank_n: dict[str, int] = RANK_N,
    expected_periods: int | None = None,
) -> dict:
    full = build_schedule(fred["DGS10"], fred["DTB3"], real_yield_first_month, last_month)
    paths = weight_paths(fred["DGS10"], cpi, availability, full)
    if dict(rank_n) != dict(RANK_N):  # toy minimum histories from the tests only
        for k in TRIAL_IDS:
            paths[WEIGHT_COLUMNS[k]] = rank_defined(paths[f"r_{CPI_SERIES[k]}"], RANK_KIND[k], rank_n[k]).to_numpy()
    synthetic = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    schedule = build_schedule(fred["DGS10"], fred["DTB3"], first_month, last_month)
    if expected_periods is not None and len(schedule) - 1 != expected_periods:
        raise ValueError(f"{len(schedule) - 1} episode periods, expected {expected_periods}")
    bar_dates = actual[DURATION_LEG].index.intersection(actual[CASH_LEG].index)
    resolved = backtest.resolve_execution_dates(schedule, bar_dates)
    return {
        "study": "008",
        "section": "PREREGISTRATION.md §8.2",
        "heading": HEADING,
        "known_window_note": KNOWN_WINDOW_NOTE,
        "weight_b3_frozen_from_history": frozen,
        "rank_history_months_at_episode_end": int(len(full)),
        "undefined_real_yield_months_in_episode": {
            s: [str(m) for m in schedule.index[:-1][paths[f"r_{s}"].reindex(schedule.index[:-1]).isna().to_numpy()]]
            for s in sorted(set(CPI_SERIES.values()))
        },
        "weights_at_last_signal_month_for_forward_record": forward_start(
            paths, schedule.index[-1], schedule["signal_date"].iloc[-1]
        ),
        "actual": run_side(f"{HEADING}, actual ETFs", paths, backtest.instrument_returns(actual, resolved),
                           resolved, frozen, out_dir / "actual"),
        "synthetic": run_side(f"{HEADING}, synthetic instruments", paths,
                              backtest.instrument_returns(synthetic, schedule), schedule, frozen, out_dir / "synthetic"),
    }


def main(
    argv: list[str] | None = None,
    history_dir: Path = HISTORY_DIR,
    out_dir: Path = EPISODE_DIR,
    study_dir: Path = STUDY_DIR,
) -> int:
    argparse.ArgumentParser(description="Study 008 2019-2026 episode (§8.2), once.").parse_args(argv)
    if not (history_dir / "summary.json").exists():
        raise SystemExit("refused: results/history/summary.json is missing; the episode needs the frozen w (§8.2)")
    if not note_committed(study_dir):
        raise SystemExit("refused: README.md (the history note) is not committed with a verdict (§8.2, §14 step 8)")
    if out_dir.exists():
        raise SystemExit(f"refused: {out_dir.name}/ exists; the episode runs once (§8.2)")
    summary = compute(
        report.load_fred(),
        {s: load_series(s) for s in sorted(set(CPI_SERIES.values()))},
        pd.read_csv(CPI_AVAILABILITY_PATH, dtype=str, keep_default_na=False),
        report.actual_indices(),
        frozen_weights(history_dir),
        REAL_YIELD_FIRST_SIGNAL_MONTH,
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
