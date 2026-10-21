"""§5.3.4 step 2: overlap check of the Tiingo IEF series against Alpaca.

A data check, not a threshold on the construction.  Over 2016-01-04 to
2018-12-31 the vendor's daily returns (from ``adjClose``) are compared with
Alpaca's ``adjustment='all'`` returns on the trading days common to both.
Acceptance (fixed in the pre-registration before this module was written):
Pearson correlation >= 0.999 and annualised mean difference, vendor minus
Alpaca, within +/-0.05% p.a. (mean daily difference x 252, the convention of
Study 001 §5.3).  If either fails, window 2 is excluded for data quality and
these statistics are published anyway.

The Alpaca bars are the ones fetched under Study 001 (its manifest records
the download); this module verifies the file's SHA-256 against that manifest,
copies it into this study's ``data/raw/`` and records the reuse in this
study's manifest.  No credential is needed and nothing is re-downloaded.

Only returns inside the overlap window are touched.  Nothing before 2016 is
read beyond the row count and first/last dates already in the manifest.

Usage (from the study folder): ``python -m src.overlap_check``.
"""
from __future__ import annotations

import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .tiingo_bars import MANIFEST_PATH, RAW_DIR, STUDY_DIR, load_prices, sha256_of, update_manifest

STUDY_001_DIR = STUDY_DIR.parent / "001-slope-duration-switch"
STUDY_001_MANIFEST = STUDY_001_DIR / "results" / "data_manifest.json"
ALPACA_FILE = "alpaca_IEF_1Day_all.csv"
RESULTS_PATH = STUDY_DIR / "results" / "validation" / "window2_data_decision.json"
REPORT_PATH = STUDY_DIR / "results" / "validation" / "window2_data_decision.md"

OVERLAP_START = "2016-01-04"
OVERLAP_END = "2018-12-31"
WINDOW2_START = "2003-01-02"
CORR_MIN = 0.999
MEAN_DIFF_ABS_MAX = 0.0005
TRADING_DAYS_PER_YEAR = 252
LARGE_DIFF = 0.0010  # 10 bp, descriptive count only


def reuse_study_001_bars(raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH) -> Path:
    """Copy Study 001's Alpaca IEF bars into this study after verifying that
    the bytes match the SHA-256 recorded in Study 001's manifest."""
    source = STUDY_001_DIR / "data" / "raw" / ALPACA_FILE
    recorded = json.loads(STUDY_001_MANIFEST.read_text(encoding="utf-8"))[ALPACA_FILE]
    actual = sha256_of(source)
    if actual != recorded["sha256"]:
        raise RuntimeError(f"{ALPACA_FILE}: SHA-256 differs from Study 001's manifest; not reusing")
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / ALPACA_FILE
    shutil.copyfile(source, target)
    update_manifest(ALPACA_FILE, dict(recorded, reused_from="Study 001 data/raw (same bytes; SHA-256 verified against Study 001 results/data_manifest.json)",
                                      reused_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")), manifest_path)
    return target


def daily_returns(close: pd.Series) -> pd.Series:
    close = close.astype(float).dropna()
    return (close / close.shift(1) - 1.0).dropna()


def overlap_statistics(vendor: pd.Series, alpaca: pd.Series,
                       start: str = OVERLAP_START, end: str = OVERLAP_END) -> dict:
    """Statistics of vendor-minus-Alpaca daily returns on common dates inside
    [start, end], plus the trading days each series has that the other lacks."""
    r_v = daily_returns(vendor).loc[start:end]
    r_a = daily_returns(alpaca).loc[start:end]
    common = r_v.index.intersection(r_a.index)
    only_vendor = r_v.index.difference(r_a.index)
    only_alpaca = r_a.index.difference(r_v.index)
    v, a = r_v.loc[common], r_a.loc[common]
    diff = v - a
    by_year = {str(year): float(group.mean() * TRADING_DAYS_PER_YEAR) for year, group in diff.groupby(diff.index.year)}
    corr = float(v.corr(a))
    mean_diff_annual = float(diff.mean() * TRADING_DAYS_PER_YEAR)
    return {
        "window": {"start": start, "end": end},
        "common_return_days": int(len(common)),
        "first_common_return_date": common[0].strftime("%Y-%m-%d") if len(common) else None,
        "last_common_return_date": common[-1].strftime("%Y-%m-%d") if len(common) else None,
        "days_only_in_vendor": [d.strftime("%Y-%m-%d") for d in only_vendor],
        "days_only_in_alpaca": [d.strftime("%Y-%m-%d") for d in only_alpaca],
        "correlation": corr,
        "mean_diff_annual_vendor_minus_alpaca": mean_diff_annual,
        "tracking_error_annual": float(diff.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)),
        "max_abs_daily_diff": float(diff.abs().max()),
        "days_abs_diff_over_10bp": int((diff.abs() > LARGE_DIFF).sum()),
        "mean_diff_annual_by_year": by_year,
        "checks": {
            "correlation": {"value": corr, "threshold": f">= {CORR_MIN}", "pass": bool(corr >= CORR_MIN)},
            "mean_diff_annual": {"value": mean_diff_annual, "threshold": f"within +/-{MEAN_DIFF_ABS_MAX}",
                                 "pass": bool(abs(mean_diff_annual) <= MEAN_DIFF_ABS_MAX)},
        },
    }


def decide(stats: dict, vendor_first_bar: str) -> dict:
    starts_in_time = vendor_first_bar <= WINDOW2_START
    passed = all(check["pass"] for check in stats["checks"].values())
    if not starts_in_time:
        decision, reason = "excluded_unavailable", f"vendor series starts {vendor_first_bar}, after {WINDOW2_START}"
    elif passed:
        decision, reason = "accepted", "vendor series starts in time and both overlap checks pass"
    else:
        failed = [name for name, check in stats["checks"].items() if not check["pass"]]
        decision, reason = "excluded_data_quality", "overlap check failed: " + ", ".join(failed)
    return {"window2": decision, "reason": reason, "vendor_first_bar": vendor_first_bar,
            "required_start": WINDOW2_START}


def write_report(result: dict, path: Path = REPORT_PATH) -> None:
    s, d = result["overlap"], result["decision"]
    lines = [
        "# Window-2 data decision (§5.3.4 steps 1-2)",
        "",
        f"Run at {result['run_at_utc']} (UTC). Data check only; no synthetic series, no rule, no return outside "
        f"{s['window']['start']} to {s['window']['end']} was computed.",
        "",
        f"**Decision: window 2 {d['window2'].replace('_', ' ')}.** {d['reason']}.",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| Vendor series (Tiingo IEF, adjClose) | {result['vendor']['rows']} rows, {result['vendor']['first_bar']} to {result['vendor']['last_bar']} |",
        f"| Alpaca series (Study 001 bars, adjustment='all') | {result['alpaca']['rows']} rows, {result['alpaca']['first_bar']} to {result['alpaca']['last_bar']} |",
        f"| Common return days in window | {s['common_return_days']} ({s['first_common_return_date']} to {s['last_common_return_date']}) |",
        f"| Days only in vendor / only in Alpaca | {len(s['days_only_in_vendor'])} / {len(s['days_only_in_alpaca'])} |",
        f"| Correlation of daily returns | {s['correlation']:.6f} (threshold >= {CORR_MIN}) -> {'pass' if s['checks']['correlation']['pass'] else 'FAIL'} |",
        f"| Annualised mean difference, vendor - Alpaca | {s['mean_diff_annual_vendor_minus_alpaca'] * 100:+.4f}% p.a. (threshold within +/-{MEAN_DIFF_ABS_MAX * 100:.2f}%) -> {'pass' if s['checks']['mean_diff_annual']['pass'] else 'FAIL'} |",
        f"| Annualised tracking error (descriptive) | {s['tracking_error_annual'] * 100:.4f}% p.a. |",
        f"| Largest absolute daily difference (descriptive) | {s['max_abs_daily_diff'] * 1e4:.2f} bp |",
        f"| Days with absolute difference over 10 bp (descriptive) | {s['days_abs_diff_over_10bp']} |",
        f"| Mean difference by year (descriptive, % p.a.) | " + ", ".join(f"{y}: {v * 100:+.4f}" for y, v in s['mean_diff_annual_by_year'].items()) + " |",
        "",
        "Full statistics in `window2_data_decision.json`.",
    ]
    if s["days_only_in_vendor"] or s["days_only_in_alpaca"]:
        lines += ["", f"Days only in vendor: {', '.join(s['days_only_in_vendor']) or 'none'}.",
                  f"Days only in Alpaca: {', '.join(s['days_only_in_alpaca']) or 'none'}."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    vendor_entry = manifest["tiingo_IEF_daily.csv"]
    alpaca_path = reuse_study_001_bars()
    alpaca_entry = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))[ALPACA_FILE]
    vendor = load_prices("IEF")["adjClose"]
    alpaca = pd.read_csv(alpaca_path, index_col="date", parse_dates=["date"])["close"]
    stats = overlap_statistics(vendor, alpaca)
    result = {
        "run_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vendor": {k: vendor_entry[k] for k in ("source", "rows", "first_bar", "last_bar", "sha256", "downloaded_at_utc")},
        "alpaca": {k: alpaca_entry[k] for k in ("source", "rows", "first_bar", "last_bar", "sha256", "downloaded_at_utc")},
        "overlap": stats,
        "decision": decide(stats, vendor_entry["first_bar"]),
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write_report(result)
    return result


def main() -> int:
    result = run()
    s, d = result["overlap"], result["decision"]
    print(f"common return days {s['common_return_days']}, corr {s['correlation']:.6f}, "
          f"mean diff {s['mean_diff_annual_vendor_minus_alpaca'] * 100:+.4f}% p.a., "
          f"TE {s['tracking_error_annual'] * 100:.4f}%, max |diff| {s['max_abs_daily_diff'] * 1e4:.2f} bp, "
          f">10bp days {s['days_abs_diff_over_10bp']}, only-vendor {len(s['days_only_in_vendor'])}, only-alpaca {len(s['days_only_in_alpaca'])}")
    print(f"decision: window 2 {d['window2']} ({d['reason']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
