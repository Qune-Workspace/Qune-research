"""Study 008 gate (PREREGISTRATION.md §5.3) and overlap check (§5.6), in one
run: Study 007's fractional G1 with each trial's real-yield weight path in
place of the carry weight, computed once for each of the three registered
paths on Study 006's 192 overlap periods; G2 inherited as observed from Study
006 and reproduced on the copied files to 1e-12; then, over T1's test-window
periods, the correlation of each weight path with Study 007's T1 weight and
with Study 006's T1 holding, read from their committed history files (weight
and holding columns only, files hash-recorded).

The weight paths come from FRED yields and the two CPI files only, through
``real_yield`` (§6.1-§6.2, with the §16 clarifications).  Nothing here
multiplies a weight by a return of a rule: e_t = (w_t - mean w) * g_t is the
only product, and this module cannot import ``backtest`` or ``tilt``
(tests/test_gate008.py checks the import graph).

    python -m src.gate008     # §14 step 5; writes results/gate/ once
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .calendar import build_schedule, holding_periods
from .config006 import BIL_VENDORS, IEF_VENDORS, OVERLAP_SPLIT_YEAR
from .config008 import (
    COMPANIONS,
    CPI_AVAILABILITY_PATH,
    CPI_SERIES,
    FIRST_WEIGHT_MONTH,
    G1_MAX_008,
    G2_MAX_008,
    GATE_DIR,
    OVERLAP_FIRST_SIGNAL_MONTH,
    OVERLAP_FLAG,
    OVERLAP_LAST_SIGNAL_MONTH,
    OVERLAP_LEG_LABEL_006,
    OVERLAP_PERIODS,
    OVERLAP_SOURCES,
    PRIMARY,
    RANK_KIND,
    RANK_N,
    REAL_YIELD_FIRST_SIGNAL_MONTH,
    TEST_FIRST_SIGNAL_MONTH,
    TEST_LAST_SIGNAL_MONTH,
    TEST_PERIODS,
    TRIAL_IDS,
)
from .fred import load_series
from .gate import _commit, choose_vendor, etf_indices, etf_leg_returns, period_returns
from .gate007 import check_g2_reproduced, fractional_gate
from .real_yield import inflation_12m, k_months, monthly, rank_defined, real_yield
from .synthetic import synthetic_indices

WEIGHT_COLUMNS = {k: f"w_{k}" for k in TRIAL_IDS}


def weight_paths(
    dgs10: pd.Series,
    cpi: dict[str, pd.Series],
    availability: pd.DataFrame,
    schedule: pd.DataFrame,
) -> pd.DataFrame:
    """One row per signal month of ``schedule`` (which must start at the first
    real-yield month, §5.5): k, π and r for each CPI series and the weight of
    each trial (NaN before its minimum history or window, and on a month whose
    r is undefined).  ``cpi`` maps series id to the raw FRED file's series.
    Signals only; no return of any rule."""
    months = schedule.index
    av_months = pd.PeriodIndex(availability["signal_month"], freq="M")
    if not months.isin(av_months).all():
        raise ValueError("a signal month has no row in the CPI availability table (§6.1)")
    av = availability.set_index(av_months).loc[months].reset_index(drop=True)
    out = pd.DataFrame(index=months)
    r_by_series: dict[str, pd.Series] = {}
    for series_id in sorted(set(CPI_SERIES.values())):
        k = k_months(av, series_id)
        pi = inflation_12m(monthly(cpi[series_id]), k)
        r = real_yield(dgs10, schedule["signal_date"], pi)
        out[f"k_{series_id}"] = [str(p) for p in k.to_numpy()]
        out[f"pi_{series_id}"] = pi.to_numpy()
        out[f"r_{series_id}"] = r.to_numpy()
        r_by_series[series_id] = r
    for trial in TRIAL_IDS:
        w = rank_defined(r_by_series[CPI_SERIES[trial]], RANK_KIND[trial], RANK_N[trial])
        out[WEIGHT_COLUMNS[trial]] = w.to_numpy()
    return out


def check_first_weights(paths: pd.DataFrame) -> dict[str, str]:
    """The first signal month with a weight must be the one the data step fixed
    (results/data_step.json), or the windows of §7/§8.1 are not the registered ones."""
    first = {k: str(paths[WEIGHT_COLUMNS[k]].first_valid_index()) for k in TRIAL_IDS}
    if first != FIRST_WEIGHT_MONTH:
        raise ValueError(f"first weight months {first} differ from the data step's {FIRST_WEIGHT_MONTH}")
    return first


def decide(gate_by_trial: dict[str, dict]) -> dict:
    """§5.3: a trial whose G1 fails is dropped ('inconclusive (gate)'); if T1's
    fails the study halts permanently.  ``outcome`` is exactly 'PASS' when T1
    passes, so that the volatility check's refusal gate reads it."""
    failed = [k for k in TRIAL_IDS if not gate_by_trial[k]["G1_pass"]]
    if PRIMARY in failed:
        outcome = f"HALT: {PRIMARY}'s G1 fails; the study halts permanently as inconclusive (gate) (§5.3)"
    else:
        outcome = "PASS"
    return {
        "outcome": outcome,
        "proceeding_trials": [k for k in TRIAL_IDS if k not in failed],
        "dropped_trials": {k: "inconclusive (gate)" for k in failed},
        "roles": {PRIMARY: "primary", **dict.fromkeys(COMPANIONS, "companion")},
    }


def read_overlap_column(path: Path, column: str) -> tuple[pd.Series, dict]:
    """§5.6: read only the month column and one weight or holding column of a
    committed history file (``usecols``: no return column is parsed), with the
    file's SHA-256 for the record."""
    raw = path.read_bytes()
    frame = pd.read_csv(path, usecols=["month", column], dtype={"month": str})
    s = frame.set_index(pd.PeriodIndex(frame["month"], freq="M"))[column]
    return s, {"file": str(path.relative_to(path.parents[3])), "sha256": hashlib.sha256(raw).hexdigest(),
               "column_read": column, "rows": int(len(s))}


def overlap_correlations(w: pd.DataFrame, w007: pd.Series, h006: pd.Series, months: pd.PeriodIndex) -> dict:
    """corr(w^k, w^{007 T1}) and corr(w^k, 1[h^{006 T1} = leg]) over ``months``
    (T1's test-window periods) for every trial with a weight on all of them;
    T1b, whose window is shorter, is correlated on the months where it has one,
    and the count is reported.  The flag of §5.6 reads T1 only."""
    a007 = w007.reindex(months)
    a006 = h006.reindex(months)
    if a007.isna().any() or a006.isna().any():
        raise ValueError("a test-window month is missing from Study 006's or 007's history file (§5.6)")
    if not set(a006.unique()) <= {OVERLAP_LEG_LABEL_006, "BIL"}:
        raise ValueError(f"unexpected Study 006 holding labels {sorted(set(a006.unique()))}")
    in_leg = (a006 == OVERLAP_LEG_LABEL_006).astype(float)
    out: dict = {}
    for k in TRIAL_IDS:
        wk = w[WEIGHT_COLUMNS[k]].reindex(months)
        ok = wk.notna().to_numpy()
        x = wk.to_numpy(dtype=float)[ok]
        out[k] = {
            "periods": int(ok.sum()),
            "corr_with_007_T1_weight": float(np.corrcoef(x, a007.to_numpy(dtype=float)[ok])[0, 1]),
            "corr_with_006_T1_in_leg": float(np.corrcoef(x, in_leg.to_numpy()[ok])[0, 1]),
        }
    t1 = out[PRIMARY]
    flagged = [s for s, c in (("007", t1["corr_with_007_T1_weight"]), ("006", t1["corr_with_006_T1_in_leg"]))
               if c > OVERLAP_FLAG]
    return {"by_trial": out, "flag_threshold": OVERLAP_FLAG, "flagged_studies_for_T1": flagged,
            "headline_states_not_independent": bool(flagged)}


def compute() -> dict:
    dgs10, dtb3, dgs7 = load_series("DGS10"), load_series("DTB3"), load_series("DGS7")
    cpi = {s: load_series(s) for s in sorted(set(CPI_SERIES.values()))}
    availability = pd.read_csv(CPI_AVAILABILITY_PATH, dtype=str, keep_default_na=False)
    synthetic = synthetic_indices(dgs10, dtb3, dgs7)

    # Signal paths from the first real-yield month, so that n counts every defined real yield (§5.5, §6.1).
    full = build_schedule(dgs10, dtb3, REAL_YIELD_FIRST_SIGNAL_MONTH, OVERLAP_LAST_SIGNAL_MONTH)
    paths = weight_paths(dgs10, cpi, availability, full)
    first_weights = check_first_weights(paths)

    schedule = build_schedule(dgs10, dtb3, OVERLAP_FIRST_SIGNAL_MONTH, OVERLAP_LAST_SIGNAL_MONTH)
    periods = holding_periods(schedule)
    if len(periods) != OVERLAP_PERIODS:
        raise ValueError(f"{len(periods)} overlap periods, expected {OVERLAP_PERIODS}")
    starts, ends = periods["execution_date"], periods["period_end"]
    months = periods.index

    d_syn = period_returns(synthetic["IEF"], starts, ends)
    c_syn = period_returns(synthetic["BIL"], starts, ends)
    x_syn = d_syn - c_syn

    etf = etf_indices()
    dates = {(s, v): idx.index for (s, v), idx in etf.items()}
    ief_vendor = choose_vendor(starts, ends, {v: dates[("IEF", v)] for v in IEF_VENDORS}, IEF_VENDORS)
    bil_vendor = choose_vendor(starts, ends, {v: dates[("BIL", v)] for v in BIL_VENDORS}, BIL_VENDORS)
    if any(v is None for v in ief_vendor):
        raise ValueError("an overlap period has no IEF bar at both ends (§5.3)")
    first_bil = next(i for i, v in enumerate(bil_vendor) if v is not None)
    if any(v is None for v in bil_vendor[first_bil:]):
        raise ValueError("BIL missing after its first covered period (§5.3)")
    ief = etf_leg_returns({v: etf[("IEF", v)] for v in IEF_VENDORS}, ief_vendor, starts, ends)
    bil = etf_leg_returns({v: etf[("BIL", v)] for v in BIL_VENDORS}, bil_vendor, starts, ends)
    bil = np.where(np.isnan(bil), c_syn, bil)  # synthetic cash on both sides before BIL (Study 006 §5.3.1)
    x_etf = ief - bil

    w = {k: paths[WEIGHT_COLUMNS[k]].reindex(months).to_numpy(dtype=float) for k in TRIAL_IDS}
    gate_by_trial = {k: fractional_gate(w[k], x_syn, x_etf) for k in TRIAL_IDS}
    g2 = check_g2_reproduced(gate_by_trial[PRIMARY]["G2_noise_ratio"])
    decision = decide(gate_by_trial)

    years = pd.DatetimeIndex(starts).year.to_numpy()
    early, late = years < OVERLAP_SPLIT_YEAR, years >= OVERLAP_SPLIT_YEAR
    splits = {
        k: {
            f"{OVERLAP_FIRST_SIGNAL_MONTH[:4]}-{OVERLAP_SPLIT_YEAR - 1}": fractional_gate(w[k][early], x_syn[early], x_etf[early]),
            f"{OVERLAP_SPLIT_YEAR}-{OVERLAP_LAST_SIGNAL_MONTH[:4]}": fractional_gate(w[k][late], x_syn[late], x_etf[late]),
        }
        for k in TRIAL_IDS
    }

    # §5.6, same run: over T1's test-window periods, signal paths only.
    test = holding_periods(build_schedule(dgs10, dtb3, TEST_FIRST_SIGNAL_MONTH, TEST_LAST_SIGNAL_MONTH))
    if len(test) != TEST_PERIODS:
        raise ValueError(f"{len(test)} test-window periods, expected {TEST_PERIODS}")
    w007, src007 = read_overlap_column(*OVERLAP_SOURCES["007"])
    h006, src006 = read_overlap_column(*OVERLAP_SOURCES["006"])
    overlap = overlap_correlations(paths, w007, h006, test.index)
    overlap["sources"] = {"007": src007, "006": src006}

    frame = pd.DataFrame(
        {
            "month": [str(m) for m in months],
            "execution_date": pd.DatetimeIndex(starts).strftime("%Y-%m-%d"),
            "period_end": pd.DatetimeIndex(ends).strftime("%Y-%m-%d"),
            **{WEIGHT_COLUMNS[k]: w[k] for k in TRIAL_IDS},
            "ief_vendor": ief_vendor,
            "bil_vendor": [v or "synthetic cash" for v in bil_vendor],
            "g": x_syn - x_etf,
            "e_T1": (w[PRIMARY] - gate_by_trial[PRIMARY]["w_o"]) * (x_syn - x_etf),
        }
    )
    signals = paths.reset_index(names="month")
    signals["month"] = signals["month"].astype(str)
    return {
        "study": "008",
        "section": "PREREGISTRATION.md §5.3 and §5.6",
        **decision,
        "bounds": {"G1_max_annual": G1_MAX_008, "G2_max": G2_MAX_008},
        "G2_inherited": g2,
        "gate_by_trial": gate_by_trial,
        "descriptive_no_decision_weight": {"splits_by_execution_year": splits},
        "descriptive_note": (
            "Each split uses its own mean weight on that subset. Turnover is the one-way sum of |w_t - w_{t-1}| "
            "inside the subset, without drift (Study 006 §5.3.4). The gate never forms w·x on either series."
        ),
        "overlap_with_006_007": overlap,
        "signal_history": {
            "first_real_yield_month": str(full.index[0]),
            "months_to_overlap_end": int(len(full)),
            "months_without_signal": int(full.attrs.get("months_without_signal", 0)),
            "first_weight_month": first_weights,
            "undefined_real_yield_months": {
                s: [str(m) for m in paths.index[paths[f"r_{s}"].isna()]] for s in sorted(set(CPI_SERIES.values()))
            },
        },
        "overlap": {
            "first_execution": str(pd.Timestamp(starts.iloc[0]).date()),
            "last_period_end": str(pd.Timestamp(ends.iloc[-1]).date()),
            "ief_vendor_counts": pd.Series(ief_vendor).value_counts().to_dict(),
            "bil_vendor_counts": pd.Series([v or "synthetic cash" for v in bil_vendor]).value_counts().to_dict(),
            "first_bil_execution": str(pd.Timestamp(starts.iloc[first_bil]).date()),
        },
        "periods": frame,
        "signals": signals,
    }


def write(result: dict, out_dir: Path = GATE_DIR) -> None:
    if out_dir.exists():
        raise SystemExit(f"refused: {out_dir.name}/ exists; the gate runs once (§5.3, §15)")
    out_dir.mkdir(parents=True)
    result.pop("periods").to_csv(out_dir / "periods.csv", index=False)
    result.pop("signals").to_csv(out_dir / "signals.csv", index=False)
    result["run_at_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    result["code_commit"] = _commit()
    (out_dir / "gate.json").write_text(json.dumps(result, indent=2) + "\n")

    def pct(v: float) -> str:
        return f"{v * 100:.3f}%"

    g2 = result["G2_inherited"]
    ov = result["overlap_with_006_007"]
    lines = [
        "# Study 008 gate (§5.3) and overlap check (§5.6), run once",
        "",
        f"**{result['outcome']}**",
        "",
        "| Trial | Role | Periods | mean w | Turnover | G1, \\|mean(e)\\| × 12 | Bound | G1 pass |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for k in TRIAL_IDS:
        s = result["gate_by_trial"][k]
        lines.append(
            f"| {k} | {result['roles'][k]} | {s['periods']} | {s['w_o']:.3f} | {s['turnover_one_way']:.2f} | "
            f"{pct(s['G1_bias_annual'])} a year | ≤ {pct(G1_MAX_008)} | {s['G1_pass']} |"
        )
    lines += [
        "",
        f"G2, sd(g) / sd(x_ETF): inherited as observed from Study 006 ({g2['inherited_as_observed']}); reproduced here "
        f"{g2['reproduced_here']:.6f} (|diff| {g2['abs_difference']:.1e} ≤ {g2['tolerance']:g}); bound ≤ {G2_MAX_008:.2f}; "
        f"pass {g2['G2_pass']}.",
        "",
        f"Dropped before any return: {result['dropped_trials'] or 'none'}. Proceeding: {', '.join(result['proceeding_trials'])}.",
        "",
        "Overlap with Studies 006 and 007 (§5.6), signal paths over T1's test-window periods:",
        "",
        "| Trial | Periods | corr(w, 007 T1 weight) | corr(w, 006 T1 in IEF) |",
        "|---|---|---|---|",
    ]
    for k in TRIAL_IDS:
        s = ov["by_trial"][k]
        lines.append(f"| {k} | {s['periods']} | {s['corr_with_007_T1_weight']:.3f} | {s['corr_with_006_T1_in_leg']:.3f} |")
    lines += [
        "",
        f"Flag (> {ov['flag_threshold']} for T1): {', '.join(ov['flagged_studies_for_T1']) or 'none'}; "
        f"the note's headline states non-independence: {ov['headline_states_not_independent']}.",
        "",
        "Descriptive, no decision weight, by the execution year of the period:",
        "",
        "| Trial | Split | Periods | mean w | Turnover | G1 |",
        "|---|---|---|---|---|---|",
    ]
    for k in TRIAL_IDS:
        for name, s in result["descriptive_no_decision_weight"]["splits_by_execution_year"][k].items():
            lines.append(
                f"| {k} | {name} | {s['periods']} | {s['w_o']:.3f} | {s['turnover_one_way']:.2f} | {pct(s['G1_bias_annual'])} |"
            )
    t1 = result["gate_by_trial"][PRIMARY]
    sh = result["signal_history"]
    lines += [
        "",
        f"Level gap mean(g) × 12 {pct(t1['mean_g_annual'])} (cancels in e); corr(g, x_ETF) {t1['corr_g_x_etf']:.3f}. "
        f"Real yields from {sh['first_real_yield_month']}; first weight month {sh['first_weight_month']}; "
        f"undefined real-yield months to {OVERLAP_LAST_SIGNAL_MONTH}: {sh['undefined_real_yield_months']}.",
        "",
        f"Run {result['run_at_utc']}, code {result['code_commit'][:7]}. No rule or benchmark return computed.",
        "",
    ]
    (out_dir / "gate.md").write_text("\n".join(lines))
    print("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Study 008 gate (§5.3) and overlap check (§5.6), run once.").parse_args(argv)
    result = compute()
    write(result)
    return 0 if result["outcome"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
