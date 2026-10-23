"""Validation of the synthetic series against the actual ETF (§5.3).

A data check, not a performance test: instrument returns only, no rule
applied.  Two windows, one run (§5.3.5):

* window 1 (§5.3.3, required), 2016-01-04 to 2018-12-31: IEF and BIL from
  Alpaca (``adjustment='all'``); checks A1-A4 on the duration leg, B1-B2 on
  the cash leg, and the descriptive year-by-year gap D1;
* window 2 (§5.3.4, conditional), 2003-01-02 to 2015-12-31: IEF from the
  second vendor (split- and distribution-adjusted close); checks A1-A3 at the
  same thresholds and A4 in its own band; no cash check.  It runs only if the
  decision file written by ``overlap_check`` before any validation says the
  window is accepted; if the file says excluded, the reason is recorded here.

Daily comparison on the trading days present in the ETF series, with the
synthetic index compounded onto the same calendar intervals.  The ex-ante
central estimate of §5.3.1 is printed next to the observed A4 so that the
reader can see which component was wrong, whatever the outcome.  If any
threshold fails on either window the study halts permanently (§5.3.5).

Run only through ``reproduce.sh --validate``.
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
from .config import (
    A4_CENTRAL_ESTIMATE,
    CASH_LEG,
    DURATION_LEG,
    RESULTS_DIR,
    ROLLDOWN_ESTIMATE_BY_YEAR,
    VALIDATION_END,
    VALIDATION_START,
    VALIDATION_THRESHOLDS,
    WINDOW2_DECISION_PATH,
    WINDOW2_END,
    WINDOW2_START,
)
from .fred import load_series
from .synthetic import crosscheck_mean_abs_error, duration_returns, synthetic_indices
from .tiingo_bars import load_prices

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402  (backend must be chosen first)
import matplotlib.pyplot as plt  # noqa: E402

TRADING_DAYS_PER_YEAR = 252
VENDOR_SYMBOL = "IEF"


def interval_returns(index: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    """Returns of a total-return index between consecutive ``dates``, the
    index taken as of each date (compounds synthetic FRED-day returns onto
    the ETF's trading-day intervals, §5.3)."""
    return index.reindex(dates, method="ffill").pct_change().dropna()


def comparison_statistics(etf: pd.Series, synthetic: pd.Series) -> dict:
    """Correlation, OLS slope, annualised tracking error and annualised mean
    difference (ETF minus synthetic) of two aligned daily return series, plus
    the annualised mean difference in each calendar year (D1, descriptive)."""
    frame = pd.concat([etf.rename("etf"), synthetic.rename("syn")], axis=1).dropna()
    diff = frame["etf"] - frame["syn"]
    slope, _ = np.polyfit(frame["syn"], frame["etf"], 1)
    return {"days": int(len(frame)),
            "first_return_date": frame.index[0].strftime("%Y-%m-%d"),
            "last_return_date": frame.index[-1].strftime("%Y-%m-%d"),
            "correlation": float(frame["etf"].corr(frame["syn"])),
            "ols_slope": float(slope),
            "tracking_error_annual": float(diff.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)),
            "mean_diff_annual": float(diff.mean() * TRADING_DAYS_PER_YEAR),
            "mean_diff_annual_by_year": {str(y): float(g.mean() * TRADING_DAYS_PER_YEAR)
                                         for y, g in diff.groupby(diff.index.year)}}


def _check(value: float, threshold: str, passed: bool) -> dict:
    return {"value": float(value), "threshold": threshold, "pass": bool(passed)}


def evaluate_duration(stats: dict, window: str) -> dict[str, dict]:
    """Checks A1-A4 against the §5.3.3 / §5.3.4 thresholds; ``window`` is
    ``"window1"`` or ``"window2"`` and selects the A4 band."""
    th = VALIDATION_THRESHOLDS
    lo, hi = th[f"A4_mean_diff_min_{window}"], th[f"A4_mean_diff_max_{window}"]
    a4 = _check(stats["mean_diff_annual"], f"in [{lo}, {hi}]", lo <= stats["mean_diff_annual"] <= hi)
    a4["exante_central_estimate"] = A4_CENTRAL_ESTIMATE[window]
    return {
        "A1": _check(stats["correlation"], f">= {th['A1_corr_min']}", stats["correlation"] >= th["A1_corr_min"]),
        "A2": _check(stats["ols_slope"], f"in [{th['A2_slope_min']}, {th['A2_slope_max']}]",
                     th["A2_slope_min"] <= stats["ols_slope"] <= th["A2_slope_max"]),
        "A3": _check(stats["tracking_error_annual"], f"<= {th['A3_tracking_error_max']}",
                     stats["tracking_error_annual"] <= th["A3_tracking_error_max"]),
        "A4": a4,
    }


def evaluate_cash(stats: dict) -> dict[str, dict]:
    """Checks B1-B2 (window 1 only)."""
    th = VALIDATION_THRESHOLDS
    return {
        "B1": _check(stats["mean_diff_annual"], f"within +/-{th['B1_mean_diff_abs_max']}",
                     abs(stats["mean_diff_annual"]) <= th["B1_mean_diff_abs_max"]),
        "B2": _check(stats["tracking_error_annual"], f"<= {th['B2_tracking_error_max']}",
                     stats["tracking_error_annual"] <= th["B2_tracking_error_max"]),
    }


def window2_decision(path: Path = WINDOW2_DECISION_PATH) -> dict:
    """The pre-committed §5.3.4 decision.  A missing file means the decision
    step was never run, which is an error: validation may not choose."""
    if not path.exists():
        raise FileNotFoundError(f"{path.name} missing: §5.3.4 steps 1-2 must be run and committed before validation")
    return json.loads(path.read_text(encoding="utf-8"))["decision"]


def plot(panels: list[tuple[pd.Series, pd.Series, str]], out_path: Path, title: str) -> None:
    """One scatter of daily returns for the duration leg and one cumulative
    panel per instrument."""
    fig, axes = plt.subplots(1, 1 + len(panels), figsize=(5 * (1 + len(panels)), 4.5))
    etf, syn, label = panels[0]
    axes[0].scatter(syn * 1e4, etf * 1e4, s=6, alpha=0.5, color="#1f4e79")
    axes[0].set_xlabel("synthetic 8.5-year ageing par bond, daily return (bp)")
    axes[0].set_ylabel(f"{label} daily return (bp)")
    axes[0].set_title(f"{title}: A1-A2 daily returns (data check)")
    for ax, (a, b, label) in zip(axes[1:], panels):
        ax.plot((1 + a).cumprod(), label=label, color="#1f4e79")
        ax.plot((1 + b).cumprod(), label="synthetic", color="#c0504d", linestyle="--")
        ax.set_title(f"{title}: cumulative, {label} vs synthetic")
        ax.legend(frameon=False)
        ax.xaxis.set_major_locator(mdates.YearLocator(2 if len(a) > 1500 else 1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _write(out_dir: Path, report: dict, lines: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out_dir / "validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _table(checks: dict[str, dict]) -> list[str]:
    lines = ["| Check | Value | Threshold | Pass |", "|---|---|---|---|"]
    for k, c in checks.items():
        extra = f" (ex-ante central estimate {c['exante_central_estimate']:+.4f})" if "exante_central_estimate" in c else ""
        lines.append(f"| {k} | {c['value']:.5f}{extra} | {c['threshold']} | {'yes' if c['pass'] else 'NO'} |")
    return lines


def run_window1(fred: dict[str, pd.Series], synthetic: dict[str, pd.Series],
                start: str, end: str, out_dir: Path) -> dict:
    """§5.3.3: Alpaca IEF and BIL against the synthetic legs."""
    crosscheck = crosscheck_mean_abs_error(duration_returns(fred["DGS10"], fred["DGS7"]).loc[start:end])
    stats, series = {}, {}
    for name in (DURATION_LEG, CASH_LEG):
        bars = load_bars(name).loc[start:end]
        etf_r = etf_total_return_index(bars).pct_change().dropna()
        syn_r = interval_returns(synthetic[name], bars.index)
        stats[name] = comparison_statistics(etf_r, syn_r)
        series[name] = (etf_r, syn_r, name)
    checks = evaluate_duration(stats[DURATION_LEG], "window1") | evaluate_cash(stats[CASH_LEG])
    d1 = {year: {"observed_mean_diff_annual": stats[DURATION_LEG]["mean_diff_annual_by_year"].get(year),
                 "rolldown_estimate_annual": est}
          for year, est in ROLLDOWN_ESTIMATE_BY_YEAR.items()}
    passed = all(c["pass"] for c in checks.values())
    report = {"window": {"name": "window1", "start": start, "end": end,
                         "etf_source": "Alpaca bars, adjustment='all' (Study 001 fetch, reused)"},
              "statistics": stats, "checks": checks, "D1_by_year_descriptive": d1,
              "duration_convexity_crosscheck_mean_abs_error": crosscheck, "all_pass": passed}
    lines = ["# Validation window 1 (§5.3.3)", "",
             f"Window {start} to {end}; IEF and BIL from Alpaca. Instrument returns only; no rule applied.", ""]
    lines += _table(checks)
    lines += ["", "D1 (descriptive, no decision weight): IEF minus synthetic by calendar year, % p.a., "
              "against the roll-down the construction earns that year (§5.3.3):", "",
              "| Year | Observed gap | Roll-down estimate |", "|---|---|---|"]
    lines += [f"| {y} | {v['observed_mean_diff_annual'] * 100:+.3f}% | {v['rolldown_estimate_annual'] * 100:.3f}% |"
              for y, v in d1.items() if v["observed_mean_diff_annual"] is not None]
    lines += ["", f"Duration/convexity cross-check, mean absolute daily error: {crosscheck * 1e4:.3f} bp "
              "(acceptance 0.5 bp, §5.2).", "",
              f"Result: {'all window-1 thresholds met' if passed else 'FAILED on window 1'}."]
    _write(out_dir, report, lines)
    plot([series[DURATION_LEG], series[CASH_LEG]], out_dir / "validation.png", "window 1")
    print("\n".join(lines))
    return report


def run_window2(fred: dict[str, pd.Series], synthetic: dict[str, pd.Series],
                start: str, end: str, out_dir: Path) -> dict:
    """§5.3.4 step 3: second-vendor IEF against the synthetic duration leg."""
    crosscheck = crosscheck_mean_abs_error(duration_returns(fred["DGS10"], fred["DGS7"]).loc[start:end])
    close = load_prices(VENDOR_SYMBOL)["adjClose"].astype(float).dropna().loc[start:end]
    etf_r = (close / close.shift(1) - 1.0).dropna()
    syn_r = interval_returns(synthetic[DURATION_LEG], close.index)
    stats = comparison_statistics(etf_r, syn_r)
    checks = evaluate_duration(stats, "window2")
    passed = all(c["pass"] for c in checks.values())
    report = {"window": {"name": "window2", "start": start, "end": end,
                         "etf_source": "second vendor (Tiingo), split- and distribution-adjusted close"},
              "statistics": {DURATION_LEG: stats}, "checks": checks,
              "duration_convexity_crosscheck_mean_abs_error": crosscheck, "all_pass": passed}
    lines = ["# Validation window 2 (§5.3.4 step 3)", "",
             f"Window {start} to {end}; IEF from the second vendor. Instrument returns only; no rule applied; "
             "no cash check on this window.", ""]
    lines += _table(checks)
    lines += ["", "Descriptive: IEF minus synthetic by calendar year, % p.a.: "
              + ", ".join(f"{y} {v * 100:+.2f}" for y, v in stats["mean_diff_annual_by_year"].items()), "",
              f"Duration/convexity cross-check, mean absolute daily error: {crosscheck * 1e4:.3f} bp "
              "(acceptance 0.5 bp, §5.2).", "",
              f"Result: {'all window-2 thresholds met' if passed else 'FAILED on window 2'}."]
    _write(out_dir, report, lines)
    plot([(etf_r, syn_r, DURATION_LEG)], out_dir / "validation.png", "window 2")
    print("\n".join(lines))
    return report


def run(out_dir: Path = RESULTS_DIR / "validation",
        window1: tuple[str, str] = (VALIDATION_START, VALIDATION_END),
        window2: tuple[str, str] = (WINDOW2_START, WINDOW2_END),
        decision: dict | None = None) -> bool:
    """Both windows, one summary.  Returns True only if every threshold on
    every included window passes."""
    out_dir.mkdir(parents=True, exist_ok=True)
    decision = decision if decision is not None else window2_decision()
    fred = {name: load_series(name) for name in ("DGS10", "DTB3", "DGS7")}
    synthetic = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    w1 = run_window1(fred, synthetic, *window1, out_dir / "window1")
    included = decision.get("window2") == "accepted"
    w2 = run_window2(fred, synthetic, *window2, out_dir / "window2") if included else None
    passed = w1["all_pass"] and (w2["all_pass"] if included else True)
    summary = {"window1": {"all_pass": w1["all_pass"], "checks": w1["checks"]},
               "window2": ({"included": True, "all_pass": w2["all_pass"], "checks": w2["checks"]} if included
                           else {"included": False, "decision": decision}),
               "all_pass": passed}
    lines = ["# Validation of the synthetic series (§5.3), single run", "",
             f"Window 1: {'pass' if w1['all_pass'] else 'FAIL'} (`window1/validation.md`).",
             (f"Window 2: {'pass' if w2['all_pass'] else 'FAIL'} (`window2/validation.md`)." if included else
              f"Window 2: not included; decision `{decision.get('window2')}`: {decision.get('reason', '')}."), "",
             f"Result: {'all thresholds met; the study proceeds' if passed else 'FAILED; the study halts permanently (§5.3.5)'}."]
    _write(out_dir, summary, lines)
    print("\n".join(lines))
    return passed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="§5.3 validation of the synthetic series, both windows, one run.")
    parser.parse_args(argv)
    return 0 if run() else 1


if __name__ == "__main__":
    raise SystemExit(main())
