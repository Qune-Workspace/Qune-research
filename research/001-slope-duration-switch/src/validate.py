"""Validation of the synthetic series against the actual ETFs (§5.3).

A data check, not a performance test: instrument returns only, no rule
applied.  Window 2016-01-04 to 2018-12-31 (inside the in-sample period; the
out-of-sample window is not touched).  Daily comparison on the NYSE trading
days present in the ETF bars, with the synthetic index compounded onto the
same calendar intervals.  If any threshold fails the study halts (§5.3).
The duration leg is the 7/10-year blend of §16 (decision of 2026-10-21);
the thresholds are unchanged.

Run only through ``reproduce.sh --validate`` after approval.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from .alpaca_bars import load_bars
from .alpaca_bars import total_return_index as etf_total_return_index
from .config import CASH_LEG, DURATION_LEG, RESULTS_DIR, VALIDATION_END, VALIDATION_START, VALIDATION_THRESHOLDS
from .fred import load_series
from .synthetic import blend_returns, crosscheck_mean_abs_error, synthetic_indices

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402  (backend must be chosen first)
import matplotlib.pyplot as plt  # noqa: E402

TRADING_DAYS_PER_YEAR = 252


def interval_returns(index: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    """Returns of a total-return index between consecutive ``dates``, the
    index taken as of each date (compounds synthetic FRED-day returns onto
    NYSE intervals, §5.3)."""
    return index.reindex(dates, method="ffill").pct_change().dropna()


def comparison_statistics(etf: pd.Series, synthetic: pd.Series) -> dict[str, float]:
    """Correlation, OLS slope, annualised tracking error and annualised mean
    difference of two aligned daily return series (ETF minus synthetic)."""
    frame = pd.concat([etf.rename("etf"), synthetic.rename("syn")], axis=1).dropna()
    diff = frame["etf"] - frame["syn"]
    slope, _ = np.polyfit(frame["syn"], frame["etf"], 1)
    return {"days": int(len(frame)),
            "correlation": float(frame["etf"].corr(frame["syn"])),
            "ols_slope": float(slope),
            "tracking_error_annual": float(diff.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)),
            "mean_diff_annual": float(diff.mean() * TRADING_DAYS_PER_YEAR)}


def evaluate(ten: dict[str, float], cash: dict[str, float]) -> dict[str, dict]:
    """Checks A1-A4 and B1-B2 against the §5.3 thresholds."""
    th = VALIDATION_THRESHOLDS
    checks = {
        "A1": (ten["correlation"], f">= {th['A1_corr_min']}", ten["correlation"] >= th["A1_corr_min"]),
        "A2": (ten["ols_slope"], f"in [{th['A2_slope_min']}, {th['A2_slope_max']}]",
               th["A2_slope_min"] <= ten["ols_slope"] <= th["A2_slope_max"]),
        "A3": (ten["tracking_error_annual"], f"<= {th['A3_tracking_error_max']}",
               ten["tracking_error_annual"] <= th["A3_tracking_error_max"]),
        "A4": (ten["mean_diff_annual"], f"within +/-{th['A4_mean_diff_abs_max']}",
               abs(ten["mean_diff_annual"]) <= th["A4_mean_diff_abs_max"]),
        "B1": (cash["mean_diff_annual"], f"within +/-{th['B1_mean_diff_abs_max']}",
               abs(cash["mean_diff_annual"]) <= th["B1_mean_diff_abs_max"]),
        "B2": (cash["tracking_error_annual"], f"<= {th['B2_tracking_error_max']}",
               cash["tracking_error_annual"] <= th["B2_tracking_error_max"]),
    }
    return {k: {"value": v, "threshold": t, "pass": bool(p)} for k, (v, t, p) in checks.items()}


def plot(etf_ten: pd.Series, syn_ten: pd.Series, etf_cash: pd.Series, syn_cash: pd.Series,
         out_dir: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    axes[0].scatter(syn_ten * 1e4, etf_ten * 1e4, s=6, alpha=0.5, color="#1f4e79")
    axes[0].set_xlabel("synthetic 7/10-year blend daily return (bp)")
    axes[0].set_ylabel(f"{DURATION_LEG} daily return (bp)")
    axes[0].set_title("A1-A2: daily returns (backtest data check)")
    for ax, (a, b, label) in zip(axes[1:], [(etf_ten, syn_ten, DURATION_LEG), (etf_cash, syn_cash, CASH_LEG)]):
        ax.plot((1 + a).cumprod(), label=label, color="#1f4e79")
        ax.plot((1 + b).cumprod(), label="synthetic", color="#c0504d", linestyle="--")
        ax.set_title(f"cumulative: {label} vs synthetic")
        ax.legend(frameon=False)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    fig.savefig(out_dir / "validation.png", dpi=150)
    plt.close(fig)


def run(start: str = VALIDATION_START, end: str = VALIDATION_END,
        out_dir: Path = RESULTS_DIR / "validation") -> bool:
    out_dir.mkdir(parents=True, exist_ok=True)
    dgs10, dtb3, dgs7 = load_series("DGS10"), load_series("DTB3"), load_series("DGS7")
    synthetic = synthetic_indices(dgs10, dtb3, dgs7)
    crosscheck = crosscheck_mean_abs_error(blend_returns(dgs10, dgs7).loc[start:end])
    results = {}
    series = {}
    for name in (DURATION_LEG, CASH_LEG):
        bars = load_bars(name).loc[start:end]
        etf_r = etf_total_return_index(bars).pct_change().dropna()
        syn_r = interval_returns(synthetic[name], bars.index)
        results[name] = comparison_statistics(etf_r, syn_r)
        series[name] = (etf_r, syn_r)
    checks = evaluate(results[DURATION_LEG], results[CASH_LEG])
    passed = all(c["pass"] for c in checks.values())
    report = {"window": {"start": start, "end": end}, "statistics": results, "checks": checks,
              "duration_convexity_crosscheck_mean_abs_error": crosscheck, "all_pass": passed}
    (out_dir / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Validation of the synthetic series (§5.3)", "",
             f"Window {start} to {end}. Instrument returns only; no rule applied.", "",
             "| Check | Value | Threshold | Pass |", "|---|---|---|---|"]
    lines += [f"| {k} | {c['value']:.5f} | {c['threshold']} | {'yes' if c['pass'] else 'NO'} |"
              for k, c in checks.items()]
    lines += ["", f"Duration/convexity cross-check, mean absolute daily error: {crosscheck * 1e4:.3f} bp "
              "(acceptance 0.5 bp, §5.2).", "",
              f"Result: {'all thresholds met; the study proceeds' if passed else 'FAILED; the study halts (§5.3)'}."]
    (out_dir / "validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    plot(*series[DURATION_LEG], *series[CASH_LEG], out_dir)
    print("\n".join(lines))
    return passed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="§5.3 validation of the synthetic series.")
    parser.add_argument("--start", default=VALIDATION_START)
    parser.add_argument("--end", default=VALIDATION_END)
    args = parser.parse_args(argv)
    return 0 if run(args.start, args.end) else 1


if __name__ == "__main__":
    raise SystemExit(main())
