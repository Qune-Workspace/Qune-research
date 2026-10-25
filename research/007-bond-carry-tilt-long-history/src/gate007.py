"""Study 007 gate (PREREGISTRATION.md §5.3): Study 006's G1 with each trial's
weight path w_t in place of the 0/1 holding h_t, computed once for each of the
five registered weight paths on the 192 overlap periods; G2 inherited as
observed from Study 006 and reproduced as a consistency check on the copied
files, not re-run as if new.

The weight paths come from FRED yields and the synthetic indices only (§6.1 to
§6.3, through ``carry_rank``); the gap g_t = x_t(synthetic) - x_t(ETF) and the
vendor rule are Study 006's ``gate`` functions, copied unchanged.  Nothing here
multiplies a weight by a return of a rule: e_t = (w_t - mean w) * g_t is the
only product, and this module cannot import ``backtest`` or ``tilt``
(tests/test_gate007.py checks the import graph).

    python -m src.gate007     # §14 step 5; writes results/gate/ once
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .calendar import build_schedule, holding_periods
from .carry_rank import blend, carry_at_signal_dates, expanding_rank, trend_signal
from .config006 import BIL_VENDORS, IEF_VENDORS, OVERLAP_SPLIT_YEAR
from .config007 import (
    CARRY_FIRST_SIGNAL_MONTH,
    COMPANIONS,
    G1_MAX_007,
    G2_MAX_007,
    G2_OBSERVED_006,
    G2_OBSERVED_006_FULL,
    G2_REPRODUCTION_TOLERANCE,
    GATE_DIR,
    MIN_HISTORY,
    OVERLAP_FIRST_SIGNAL_MONTH,
    OVERLAP_LAST_SIGNAL_MONTH,
    OVERLAP_PERIODS,
    PRIMARY,
    SECONDARY,
    TRIAL_IDS,
)
from .fred import load_series
from .gate import _commit, choose_vendor, etf_indices, etf_leg_returns, gate_statistics, period_returns
from .synthetic import synthetic_indices

WEIGHT_COLUMNS = {k: f"w_{k}" for k in TRIAL_IDS}


def index_at_signal_dates(tri: pd.Series, signal_dates: pd.Series) -> pd.Series:
    """The index value on the last date on or before each signal date (the
    engine's convention, ``gate.period_returns``), re-indexed by the signal
    date so that ``carry_rank`` reads it exactly there (§6.3)."""
    dates = pd.DatetimeIndex(signal_dates.values)
    values = tri.sort_index().reindex(dates, method="ffill")
    if values.isna().any():
        raise ValueError("a synthetic index starts after a signal date")
    return pd.Series(values.to_numpy(dtype=float), index=dates, name=tri.name)


def weight_paths(
    dgs10: pd.Series,
    dgs7: pd.Series,
    dtb3: pd.Series,
    schedule: pd.DataFrame,
    indices: dict[str, pd.Series],
    min_history: dict[str, int] = MIN_HISTORY,
) -> pd.DataFrame:
    """One row per signal month of ``schedule`` (which must start at the first
    carry month, §5.5): the carry c_t, the history length n_t, the weight of
    each trial (NaN before its minimum history or, for T2 and T3, before the
    trend's twelfth row).  Signals only; no return of any rule."""
    signal_dates = schedule["signal_date"]
    carry = carry_at_signal_dates(dgs10, dgs7, dtb3, signal_dates)
    if len(carry) != len(schedule) or not carry.index.equals(schedule.index):
        raise ValueError("carry undefined on a signal date: the m-th carry would not be the m-th row (§5.5)")
    out = pd.DataFrame({"carry": carry, "n": np.arange(1, len(carry) + 1)}, index=schedule.index)
    for trial, m in min_history.items():
        out[WEIGHT_COLUMNS[trial]] = expanding_rank(carry, m).to_numpy()
    leg = index_at_signal_dates(indices["IEF"], signal_dates)
    cash = index_at_signal_dates(indices["BIL"], signal_dates)
    h = trend_signal(leg, cash, signal_dates)
    out["trend"] = h.to_numpy()
    out[WEIGHT_COLUMNS["T2"]] = blend(out[WEIGHT_COLUMNS[PRIMARY]], out["trend"]).to_numpy()
    out[WEIGHT_COLUMNS["T3"]] = out["trend"]
    return out


def fractional_gate(w: np.ndarray, x_syn: np.ndarray, x_etf: np.ndarray) -> dict:
    """Study 006's statistics with a fractional w; the integer switch count is
    replaced by the one-way turnover of the path on the subset (§5.3.4)."""
    w = np.asarray(w, dtype=float)
    if np.isnan(w).any():
        raise ValueError("a weight is missing on an overlap period")
    s = gate_statistics(w, x_syn, x_etf)
    del s["switches"]
    s["turnover_one_way"] = float(np.abs(np.diff(w)).sum())
    return s


def check_g2_reproduced(g2: float) -> dict:
    """§5.3.2: G2 does not depend on the rule and is inherited as observed;
    the copied files must give Study 006's figure to the committed precision,
    or the data step is wrong and the study stops before any weight is used."""
    diff = abs(float(g2) - G2_OBSERVED_006_FULL)
    if diff > G2_REPRODUCTION_TOLERANCE:
        raise ValueError(
            f"G2 {g2!r} does not reproduce Study 006's committed {G2_OBSERVED_006_FULL!r} "
            f"(|diff| {diff:.3g} > {G2_REPRODUCTION_TOLERANCE:g}): the data step is wrong (§5.3.2)"
        )
    return {
        "inherited_as_observed": G2_OBSERVED_006,
        "committed_full_precision_006": G2_OBSERVED_006_FULL,
        "reproduced_here": float(g2),
        "abs_difference": diff,
        "tolerance": G2_REPRODUCTION_TOLERANCE,
        "G2_pass": bool(g2 <= G2_MAX_007),
    }


def decide(gate_by_trial: dict[str, dict]) -> dict:
    """§5.3.3: a trial whose G1 fails is dropped ('inconclusive (gate)'); if the
    primary's fails the study halts.  ``outcome`` is exactly 'PASS' when the
    primary passes, so that the volatility check's refusal gate reads it."""
    failed = [k for k in TRIAL_IDS if not gate_by_trial[k]["G1_pass"]]
    if PRIMARY in failed:
        outcome = f"HALT: {PRIMARY}'s G1 fails; the study halts permanently as inconclusive (§5.3.3)"
    else:
        outcome = "PASS"
    return {
        "outcome": outcome,
        "proceeding_trials": [k for k in TRIAL_IDS if k not in failed],
        "dropped_trials": {k: "inconclusive (gate)" for k in failed},
        "roles": {PRIMARY: "primary", **dict.fromkeys(COMPANIONS, "companion"), **dict.fromkeys(SECONDARY, "secondary")},
    }


def compute() -> dict:
    dgs10, dtb3, dgs7 = load_series("DGS10"), load_series("DTB3"), load_series("DGS7")
    synthetic = synthetic_indices(dgs10, dtb3, dgs7)

    # Signal paths from the first carry month, so that n_t counts every month-end carry (§5.5).
    full = build_schedule(dgs10, dtb3, CARRY_FIRST_SIGNAL_MONTH, OVERLAP_LAST_SIGNAL_MONTH)
    paths = weight_paths(dgs10, dgs7, dtb3, full, synthetic)

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
        raise ValueError("an overlap period has no IEF bar at both ends (§5.3.2)")
    first_bil = next(i for i, v in enumerate(bil_vendor) if v is not None)
    if any(v is None for v in bil_vendor[first_bil:]):
        raise ValueError("BIL missing after its first covered period (§5.3.2)")
    ief = etf_leg_returns({v: etf[("IEF", v)] for v in IEF_VENDORS}, ief_vendor, starts, ends)
    bil = etf_leg_returns({v: etf[("BIL", v)] for v in BIL_VENDORS}, bil_vendor, starts, ends)
    bil = np.where(np.isnan(bil), c_syn, bil)  # synthetic cash on both sides before BIL (§5.3.1)
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
    return {
        "study": "007",
        "section": "PREREGISTRATION.md §5.3",
        **decision,
        "bounds": {"G1_max_annual": G1_MAX_007, "G2_max": G2_MAX_007},
        "G2_inherited": g2,
        "gate_by_trial": gate_by_trial,
        "descriptive_no_decision_weight": {"splits_by_execution_year": splits},
        "descriptive_note": (
            "Each split uses its own mean weight on that subset. Turnover is the one-way sum of |w_t - w_{t-1}| "
            "inside the subset, without drift (§5.3.4). The gate never forms w·x on either series."
        ),
        "signal_history": {
            "first_carry_month": str(full.index[0]),
            "carry_months_to_overlap_end": int(len(full)),
            "months_without_signal": int(full.attrs.get("months_without_signal", 0)),
            "first_weight_month": {k: str(paths[WEIGHT_COLUMNS[k]].first_valid_index()) for k in TRIAL_IDS},
        },
        "overlap": {
            "first_execution": str(pd.Timestamp(starts.iloc[0]).date()),
            "last_period_end": str(pd.Timestamp(ends.iloc[-1]).date()),
            "ief_vendor_counts": pd.Series(ief_vendor).value_counts().to_dict(),
            "bil_vendor_counts": pd.Series([v or "synthetic cash" for v in bil_vendor]).value_counts().to_dict(),
            "first_bil_execution": str(pd.Timestamp(starts.iloc[first_bil]).date()),
        },
        "periods": frame,
    }


def write(result: dict, out_dir: Path = GATE_DIR) -> None:
    if out_dir.exists():
        raise SystemExit(f"refused: {out_dir.name}/ exists; the gate runs once (§5.3.3)")
    out_dir.mkdir(parents=True)
    periods = result.pop("periods")
    periods.to_csv(out_dir / "periods.csv", index=False)
    result["run_at_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    result["code_commit"] = _commit()
    (out_dir / "gate.json").write_text(json.dumps(result, indent=2) + "\n")

    def pct(v: float) -> str:
        return f"{v * 100:.3f}%"

    g2 = result["G2_inherited"]
    lines = [
        "# Study 007 gate (§5.3), run once",
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
            f"{pct(s['G1_bias_annual'])} a year | ≤ {pct(G1_MAX_007)} | {s['G1_pass']} |"
        )
    lines += [
        "",
        f"G2, sd(g) / sd(x_ETF): inherited as observed from Study 006 ({g2['inherited_as_observed']}); reproduced here "
        f"{g2['reproduced_here']:.6f} (|diff| {g2['abs_difference']:.1e} ≤ {g2['tolerance']:g}); bound ≤ {G2_MAX_007:.2f}; "
        f"pass {g2['G2_pass']}.",
        "",
        f"Dropped before any return: {result['dropped_trials'] or 'none'}. Proceeding: {', '.join(result['proceeding_trials'])}.",
        "",
        "Descriptive, no decision weight (§5.3.4), by the execution year of the period:",
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
    lines += [
        "",
        f"Level gap mean(g) × 12 {pct(t1['mean_g_annual'])} (cancels in e); corr(g, x_ETF) {t1['corr_g_x_etf']:.3f}. "
        f"Carry history from {result['signal_history']['first_carry_month']}; first weight month "
        f"{result['signal_history']['first_weight_month']}.",
        "",
        f"Run {result['run_at_utc']}, code {result['code_commit'][:7]}. No rule or benchmark return computed.",
        "",
    ]
    (out_dir / "gate.md").write_text("\n".join(lines))
    print("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Study 007 gate (§5.3), run once.").parse_args(argv)
    result = compute()
    write(result)
    return 0 if result["outcome"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
