"""Data checks D0 and D2 (§5.3.1, §5.3.3), one run, no rule applied.

* **D0, coverage of the in-sample IEF series**: the vendor file must have a
  bar on every NYSE trading day from 2002-07-31 to 2018-12-31 with at most
  three consecutive missing days anywhere, and its first bar must be on or
  before 2002-07-31.  Dates only: no IEF price or return is read.
* **D2, cash-leg level check**: annualised mean daily return difference,
  BIL minus ``TRI_cash`` (§5.2), on the common trading days of the window the
  committed §5.3.2 decision selects (2007-06-01 to 2018-12-31 on the vendor
  BIL series when the vendor was accepted; 2016-01-04 to 2018-12-31 on Alpaca
  under branch F).  **B1 within +/-0.30% p.a. is the only gate.**  B2, the
  annualised tracking error of the same difference, is reported against its
  historical reference (0.50% p.a.) and its 2016-2018 reading (0.288%) with no
  decision weight, together with the mean gap in each calendar year, for the
  reason written in §2.5 before any run.

If D0 or D2 fails the study halts permanently before any rule is tested
(§5.3.5); every statistic is published whatever the outcome, with the ex-ante
component estimate of §5.3.3 next to the observed value.  The comparison
machinery (interval returns compounded onto the ETF's trading days,
correlation/tracking-error/mean-difference statistics) follows Study 002's
``validate.py`` (commit 2dfbdd5).

Run only through ``reproduce.sh --check``.
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
from .calendar import nyse_trading_days
from .cash import cash_index
from .config import (B2_READING_2016_2018, B2_REFERENCE_TRACKING_ERROR, CASH_CHECK_THRESHOLDS, CASH_GAP_EXANTE,
                     CASH_LEG, COVERAGE_END, COVERAGE_START, DURATION_LEG, FIRST_BAR_REQUIRED_ON_OR_BEFORE,
                     MAX_MISSING_BARS, RESULTS_DIR, VENDOR_DECISION_PATH)
from .fred import load_series
from .tiingo_bars import load_prices

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402  (backend must be chosen first)
import matplotlib.pyplot as plt  # noqa: E402

TRADING_DAYS_PER_YEAR = 252


# --- D0 -------------------------------------------------------------------------------

def _longest_run(flags: np.ndarray) -> int:
    longest = current = 0
    for flag in flags:
        current = current + 1 if flag else 0
        longest = max(longest, current)
    return int(longest)


def coverage_check(bar_index: pd.DatetimeIndex, start: str = COVERAGE_START, end: str = COVERAGE_END,
                   first_bar_required: str = FIRST_BAR_REQUIRED_ON_OR_BEFORE,
                   max_consecutive_missing: int = MAX_MISSING_BARS) -> dict:
    """D0 on a bar index against the rule-based NYSE calendar (§5.3.1).
    ``extra_bars`` lists bars on days the rule calendar says the exchange was
    closed (a calendar error, reported, not a failure)."""
    bars = pd.DatetimeIndex(bar_index).sort_values()
    trading = nyse_trading_days(start, end)
    present = trading.isin(bars)
    missing = trading[~present]
    inside = bars[(bars >= pd.Timestamp(start)) & (bars <= pd.Timestamp(end))]
    extra = inside[~inside.isin(trading)]
    first_bar = bars[0]
    longest = _longest_run(~present)
    checks = {
        "first_bar": {"value": first_bar.strftime("%Y-%m-%d"), "threshold": f"on or before {first_bar_required}",
                      "pass": bool(first_bar <= pd.Timestamp(first_bar_required))},
        "max_consecutive_missing_days": {"value": longest, "threshold": f"<= {max_consecutive_missing}",
                                         "pass": bool(longest <= max_consecutive_missing)},
    }
    return {"window": {"start": start, "end": end}, "nyse_trading_days": int(len(trading)),
            "bars_present": int(present.sum()), "missing_days": [d.strftime("%Y-%m-%d") for d in missing],
            "extra_bars_on_rule_calendar_closures": [d.strftime("%Y-%m-%d") for d in extra],
            "checks": checks, "all_pass": all(c["pass"] for c in checks.values())}


# --- D2 -------------------------------------------------------------------------------

def interval_returns(index: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    """Returns of a total-return index between consecutive ``dates``, the
    index taken as of each date (compounds FRED-day accrual returns onto the
    ETF's trading-day intervals)."""
    return index.reindex(dates, method="ffill").pct_change().dropna()


def comparison_statistics(etf: pd.Series, modelled: pd.Series) -> dict:
    """Correlation, annualised tracking error and annualised mean difference
    (ETF minus modelled) of two aligned daily return series, plus the
    annualised mean difference and tracking error in each calendar year."""
    frame = pd.concat([etf.rename("etf"), modelled.rename("model")], axis=1).dropna()
    diff = frame["etf"] - frame["model"]
    by_year = diff.groupby(diff.index.year)
    return {"days": int(len(frame)),
            "first_return_date": frame.index[0].strftime("%Y-%m-%d"),
            "last_return_date": frame.index[-1].strftime("%Y-%m-%d"),
            "correlation": float(frame["etf"].corr(frame["model"])),
            "tracking_error_annual": float(diff.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)),
            "mean_diff_annual": float(diff.mean() * TRADING_DAYS_PER_YEAR),
            "max_abs_daily_diff": float(diff.abs().max()),
            "mean_diff_annual_by_year": {str(y): float(g.mean() * TRADING_DAYS_PER_YEAR) for y, g in by_year},
            "tracking_error_annual_by_year": {str(y): float(g.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))
                                              for y, g in by_year if len(g) > 1}}


def evaluate_cash(stats: dict) -> dict[str, dict]:
    """B1 (gate) and B2 (descriptive) of §5.3.3."""
    limit = CASH_CHECK_THRESHOLDS["B1_mean_diff_abs_max"]
    return {
        "B1": {"value": stats["mean_diff_annual"], "threshold": f"within +/-{limit}",
               "pass": bool(abs(stats["mean_diff_annual"]) <= limit),
               "exante_central_estimate": CASH_GAP_EXANTE["central_estimate"],
               "exante_sum_of_ranges": CASH_GAP_EXANTE["sum_of_absolute_ranges"],
               "within_exante_ranges": bool(abs(stats["mean_diff_annual"] - CASH_GAP_EXANTE["central_estimate"])
                                            <= CASH_GAP_EXANTE["sum_of_absolute_ranges"])},
        "B2": {"value": stats["tracking_error_annual"], "descriptive": True, "pass": None,
               "historical_reference": B2_REFERENCE_TRACKING_ERROR, "reading_2016_2018": B2_READING_2016_2018,
               "below_historical_reference": bool(stats["tracking_error_annual"] <= B2_REFERENCE_TRACKING_ERROR)},
    }


def vendor_decision(path: Path = VENDOR_DECISION_PATH) -> dict:
    """The committed §5.3.2 outcome.  A missing file means step 2 was never
    run, which is an error: the check may not choose its own window."""
    if not path.exists():
        raise FileNotFoundError(f"{path.name} missing: §5.3.2 steps 1-2 must be run and committed before --check")
    return json.loads(path.read_text(encoding="utf-8"))["decision"]


def bil_close_for(decision: dict) -> pd.Series:
    """The BIL series the decision selects: vendor adjusted close when the
    vendor was accepted, Alpaca ``adjustment='all'`` close under branch F."""
    series = decision["cash_check_window"]["series"]
    if series.startswith("Tiingo"):
        return load_prices(CASH_LEG)["adjClose"].astype(float).dropna()
    return load_bars(CASH_LEG)["close"].astype(float).dropna()


def cash_level_check(bil_close: pd.Series, tri_cash: pd.Series, start: str, end: str) -> dict:
    """D2 statistics and checks on [start, end]."""
    close = bil_close.loc[start:end]
    etf_r = (close / close.shift(1) - 1.0).dropna()
    model_r = interval_returns(tri_cash, close.index)
    stats = comparison_statistics(etf_r, model_r)
    return {"statistics": stats, "checks": evaluate_cash(stats), "all_pass": evaluate_cash(stats)["B1"]["pass"],
            "series": (etf_r, model_r)}


# --- Output ----------------------------------------------------------------------------

def plot(etf_r: pd.Series, model_r: pd.Series, out_path: Path, title: str) -> None:
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.5))
    gap = (etf_r - model_r).groupby(etf_r.index.to_period("M")).sum() * 1e4
    left.bar(gap.index.to_timestamp(), gap.to_numpy(), width=25, color="#1f4e79")
    left.axhline(0, color="black", linewidth=0.6)
    left.set_ylabel("BIL minus cash accrual, monthly (bp)")
    left.set_title(f"{title}: monthly gap (data check)")
    right.plot((1 + etf_r).cumprod(), label=CASH_LEG, color="#1f4e79")
    right.plot((1 + model_r).cumprod(), label="cash accrual (§5.2)", color="#c0504d", linestyle="--")
    right.set_title(f"{title}: cumulative")
    right.legend(frameon=False)
    for ax in (left, right):
        ax.xaxis.set_major_locator(mdates.YearLocator(2 if len(etf_r) > 1500 else 1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _exante_table() -> list[str]:
    lines = ["| Component | Ex-ante estimate (% p.a.) | Range (+/-) |", "|---|---|---|"]
    for name, c in CASH_GAP_EXANTE["components"].items():
        lines.append(f"| {name} | {c['estimate'] * 100:+.2f} | {c['range'] * 100:.2f} |")
    lines.append(f"| **Central estimate / sum of ranges** | **{CASH_GAP_EXANTE['central_estimate'] * 100:+.2f}** | "
                 f"**{CASH_GAP_EXANTE['sum_of_absolute_ranges'] * 100:.2f}** |")
    return lines


def write_report(report: dict, out_dir: Path) -> None:
    d0, d2, dec = report["D0"], report["D2"], report["decision"]
    b1, b2 = d2["checks"]["B1"], d2["checks"]["B2"]
    s = d2["statistics"]
    lines = ["# Data checks D0 and D2 (§5.3.1, §5.3.3), single run", "",
             f"Run at {report['run_at_utc']} (UTC). Instrument and cash-accrual returns only; no rule applied; "
             "no IEF return read (D0 uses dates only).", "",
             "## D0: coverage of the in-sample IEF series", "",
             f"Vendor IEF bars against the rule-based NYSE calendar, {d0['window']['start']} to {d0['window']['end']}: "
             f"{d0['bars_present']} of {d0['nyse_trading_days']} trading days present; "
             f"first bar {d0['checks']['first_bar']['value']} (required {d0['checks']['first_bar']['threshold']}); "
             f"longest run of missing trading days {d0['checks']['max_consecutive_missing_days']['value']} "
             f"(allowed {d0['checks']['max_consecutive_missing_days']['threshold']}). "
             f"**{'Pass' if d0['all_pass'] else 'FAIL'}.**", ""]
    if d0["missing_days"]:
        lines += [f"Missing trading days: {', '.join(d0['missing_days'])}.", ""]
    if d0["extra_bars_on_rule_calendar_closures"]:
        lines += ["Bars on days the rule calendar lists as closures (calendar error, reported only): "
                  f"{', '.join(d0['extra_bars_on_rule_calendar_closures'])}.", ""]
    lines += ["## D2: cash-leg level check", "",
              f"Window {dec['cash_check_window']['start']} to {dec['cash_check_window']['end']} on "
              f"{dec['cash_check_window']['series']} (selected by the committed §5.3.2 decision: {dec['outcome']}). "
              f"{s['days']} common return days, {s['first_return_date']} to {s['last_return_date']}.", "",
              "| Check | Value | Threshold | Pass |", "|---|---|---|---|",
              f"| B1 annualised mean difference, BIL minus accrual | {b1['value'] * 100:+.4f}% p.a. "
              f"(ex-ante {b1['exante_central_estimate'] * 100:+.2f} +/- {b1['exante_sum_of_ranges'] * 100:.2f}) | "
              f"{b1['threshold']} | {'yes' if b1['pass'] else 'NO'} |",
              f"| B2 annualised tracking error (descriptive) | {b2['value'] * 100:.4f}% p.a. | "
              f"reference {b2['historical_reference'] * 100:.2f}%; 2016-2018 reading {b2['reading_2016_2018'] * 100:.3f}% | "
              f"descriptive ({'below' if b2['below_historical_reference'] else 'above'} the reference) |", "",
              f"Observed gap {'inside' if b1['within_exante_ranges'] else 'outside'} the ex-ante component ranges. "
              f"Correlation of daily returns {s['correlation']:.4f} (descriptive); largest absolute daily difference "
              f"{s['max_abs_daily_diff'] * 1e4:.1f} bp.", "",
              "Ex-ante component estimate (§5.3.3, written before the run):", ""] + _exante_table()
    lines += ["", "By calendar year (descriptive): mean gap and tracking error, % p.a.", "",
              "| Year | Mean gap | Tracking error |", "|---|---|---|"]
    for year, gap in s["mean_diff_annual_by_year"].items():
        te = s["tracking_error_annual_by_year"].get(year)
        lines.append(f"| {year} | {gap * 100:+.3f} | {te * 100:.3f} |" if te is not None else f"| {year} | {gap * 100:+.3f} | n/a |")
    lines += ["", f"**Result: {'D0 and D2 pass; the study proceeds to the registered trials' if report['all_pass'] else 'FAILED; the study halts permanently before any rule is tested (§5.3.5)'}.**"]
    (out_dir / "data_checks.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def run(out_dir: Path = RESULTS_DIR / "checks", decision: dict | None = None,
        ief_bar_index: pd.DatetimeIndex | None = None, bil_close: pd.Series | None = None,
        dtb3: pd.Series | None = None) -> bool:
    """D0 then D2; returns True only if both pass.  The optional arguments
    exist for the tests; the real run reads the committed decision and the
    files in ``data/raw/``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    decision = decision if decision is not None else vendor_decision()
    if ief_bar_index is None:
        ief_bar_index = load_prices(DURATION_LEG).index          # dates only
    if bil_close is None:
        bil_close = bil_close_for(decision)
    if dtb3 is None:
        dtb3 = load_series("DTB3")
    d0 = coverage_check(pd.DatetimeIndex(ief_bar_index))
    window = decision["cash_check_window"]
    d2 = cash_level_check(bil_close, cash_index(dtb3), window["start"], window["end"])
    etf_r, model_r = d2.pop("series")
    report = {"run_at_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
              "decision": decision, "D0": d0, "D2": d2, "exante": CASH_GAP_EXANTE,
              "all_pass": bool(d0["all_pass"] and d2["all_pass"])}
    (out_dir / "data_checks.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    plot(etf_r, model_r, out_dir / "cash_check.png", "D2")
    write_report(report, out_dir)
    return report["all_pass"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="§5.3 data checks D0 and D2, one run.")
    parser.parse_args(argv)
    return 0 if run() else 1


if __name__ == "__main__":
    raise SystemExit(main())
