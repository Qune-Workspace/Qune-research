"""Post-hoc tear-sheets for Studies 003, 004 and 005 from their committed monthly files.

Descriptive only.  This script reads results/<window>/monthly_*.csv exactly as
committed, builds one tear-sheet per window with the shared library
(``qune_research.report``) and writes SVG + 2x PNG + JSON + CSV into
``tearsheets/``.  It re-runs nothing, fetches nothing, carries no decision
weight and changes no result file.  Each study's verdict was fixed by its own
pre-registered rules before this script existed.

Self-check: the sheet's annualised return, volatility, Sharpe ratio and
maximum drawdown for every series are compared with the study's committed
``metrics_*.csv`` (the figures the independent reviewers recomputed); the
script exits 1 on any difference above 1e-9.  The manifest records the
SHA-256 of every input and the git commit it ran at.

Run from the repository root:  .venv/bin/python tools/make_tearsheets.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from matplotlib import pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qune_research import report  # noqa: E402

OUT = ROOT / "tearsheets"

# One entry per published window: the monthly file, the metrics file the
# numbers are checked against, the strategy, the benchmarks in the order the
# sheet shows them (the first drives the title and the difference row), the
# cash column, the labels from the pre-registration and the chart subtitle.
SHEETS = [
    {
        "stem": "003_insample", "study": "Study 003", "window": "In-sample 2004-2018",
        "monthly": "research/003-bond-tsmom-ief/results/insample/monthly_base.csv",
        "metrics": "research/003-bond-tsmom-ief/results/insample/metrics_base.csv",
        "date_col": "execution_date", "strategy": "T1", "benchmarks": ["B3", "B1", "B2"], "cash": "B0",
        "labels": {"T1": "Trend rule T1", "B3": "Constant mix B3", "B1": "Hold IEF B1", "B2": "50/50 B2",
                   "B0": "cash (B0)"},
        "source": "Alpaca and Tiingo daily IEF bars, FRED DTB3 cash leg in-sample",
    },
    {
        "stem": "003_oos", "study": "Study 003", "window": "Out of sample 2019-2026",
        "monthly": "research/003-bond-tsmom-ief/results/oos/monthly_base.csv",
        "metrics": "research/003-bond-tsmom-ief/results/oos/metrics_base.csv",
        "date_col": "execution_date", "strategy": "T1", "benchmarks": ["B3", "B1", "B2"], "cash": "B0",
        "labels": {"T1": "Trend rule T1", "B3": "Constant mix B3", "B1": "Hold IEF B1", "B2": "50/50 B2",
                   "B0": "cash (B0)"},
        "source": "Alpaca and Tiingo daily IEF and BIL bars",
    },
    {
        "stem": "004_insample", "study": "Study 004", "window": "In-sample 2004-2018, ten ETFs",
        "monthly": "research/004-xasset-trend-voltarget/results/insample/monthly_10assets_base.csv",
        "metrics": "research/004-xasset-trend-voltarget/results/insample/metrics_10assets_base.csv",
        "date_col": "execution_date", "strategy": "T1", "benchmarks": ["B4", "B3", "B1"], "cash": "B0",
        "labels": {"T1": "Trend rule T1", "B4": "Matched exposure B4", "B3": "Vol-scaled long B3",
                   "B1": "Equal weight B1", "B0": "cash (B0)"},
        "source": "Alpaca and Tiingo daily ETF bars, FRED DTB3 cash leg in-sample",
    },
    {
        "stem": "004_oos", "study": "Study 004", "window": "Out of sample 2019-2026, ten ETFs",
        "monthly": "research/004-xasset-trend-voltarget/results/oos/monthly_10assets_base.csv",
        "metrics": "research/004-xasset-trend-voltarget/results/oos/metrics_10assets_base.csv",
        "date_col": "execution_date", "strategy": "T1", "benchmarks": ["B4", "B3", "B1"], "cash": "B0",
        "labels": {"T1": "Trend rule T1", "B4": "Matched exposure B4", "B3": "Vol-scaled long B3",
                   "B1": "Equal weight B1", "B0": "cash (B0)"},
        "source": "Alpaca and Tiingo daily ETF bars, BIL as cash",
    },
    {
        "stem": "005_insample", "study": "Study 005", "window": "In-sample 2004-2018",
        "monthly": "research/005-duration-trend-regime/results/insample/monthly_base.csv",
        "metrics": "research/005-duration-trend-regime/results/insample/metrics_base.csv",
        "date_col": "execution_date", "strategy": "T1", "benchmarks": ["B2", "B1", "B3"], "cash": "B0",
        "labels": {"T1": "Regime-gated exit T1", "B2": "Unconditional trend B2", "B1": "Hold IEF B1",
                   "B3": "Constant mix B3", "B0": "cash (B0)"},
        "source": "Alpaca and Tiingo daily IEF and SPY bars, FRED DTB3 cash leg in-sample",
    },
    {
        "stem": "005_episode", "study": "Study 005", "window": "Episode 2019-2026 (no decision weight)",
        "monthly": "research/005-duration-trend-regime/results/episode/monthly_base.csv",
        "metrics": "research/005-duration-trend-regime/results/episode/metrics_base.csv",
        "date_col": "execution_date", "strategy": "T1", "benchmarks": ["B2", "B1", "B3"], "cash": "B0",
        "labels": {"T1": "Regime-gated exit T1", "B2": "Unconditional trend B2", "B1": "Hold IEF B1",
                   "B3": "Constant mix B3", "B0": "cash (B0)"},
        "source": "Alpaca and Tiingo daily IEF, SPY and BIL bars",
    },
]

# Committed metric name -> tear-sheet metric name.  The committed drawdown is
# of the monthly total-return index, as the sheet's is.
CHECKED = {"ann_geometric_return": "ann_return", "ann_volatility": "ann_volatility",
           "sharpe_annual": "sharpe", "max_drawdown_monthly": "max_drawdown", "periods": "months"}
TOL = 1e-9


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def load_monthly(spec: dict) -> pd.DataFrame:
    """The monthly returns indexed by holding month.

    Every study's rows are holding periods from one execution date to the
    next; the period's month is that of its execution date (the ``month``
    column of 003 and 005 is the signal month before it, ``period_end`` is
    the next period's execution date).  Indexing by ``period_end``, as the
    first version of this script did, booked every December holding period
    to the following year; the Tester's review of 2026-10-23 found it.
    """
    raw = pd.read_csv(ROOT / spec["monthly"])
    cols = [spec["strategy"]] + spec["benchmarks"] + [spec["cash"]]
    monthly = raw[cols].astype(float)
    holding = pd.to_datetime(raw[spec["date_col"]]).dt.to_period("M").dt.to_timestamp("M")
    monthly.index = pd.DatetimeIndex(holding)
    monthly.index.name = "holding_month"
    return monthly


def check_against_committed(spec: dict, sheet: report.TearSheet) -> list[dict]:
    """Every checked metric for every series on the sheet against the study's metrics file."""
    committed = pd.read_csv(ROOT / spec["metrics"], index_col=0)
    rows = []
    for series in sheet.series:
        for theirs, ours in CHECKED.items():
            a = float(committed.loc[series, theirs]) if theirs in committed.columns else float("nan")
            b = float(sheet.metrics.loc[ours, series])
            both_nan = pd.isna(a) and pd.isna(b)
            match = both_nan or (not pd.isna(a) and not pd.isna(b) and abs(a - b) <= TOL)
            rows.append({"series": series, "metric": theirs, "committed": None if pd.isna(a) else a,
                         "tearsheet": None if pd.isna(b) else b, "match": bool(match)})
    return rows


def main() -> int:
    OUT.mkdir(exist_ok=True)
    manifest: dict = {"generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "commit": git_head(),
                      "tolerance": TOL, "sheets": []}
    failures = 0
    for spec in SHEETS:
        monthly = load_monthly(spec)
        inputs = {spec["monthly"]: sha256(ROOT / spec["monthly"]), spec["metrics"]: sha256(ROOT / spec["metrics"])}
        sheet = report.build(monthly, spec["strategy"], spec["benchmarks"], cash=spec["cash"],
                             labels=spec["labels"], inputs=inputs)
        cash_label = spec["labels"][spec["cash"]]
        subtitle = (f"{spec['window']}; monthly net returns for the holding periods {sheet.period}, each from one execution "
                    f"date to the next; Sharpe ratio of the excess over {cash_label}, annualised; drawdown from the "
                    f"running high of the monthly total-return index")
        fig = report.draw(sheet, spec["source"], spec["study"], subtitle=subtitle,
                          note="Post hoc, no decision weight; drawn from the committed result files.")
        paths = report.write(sheet, fig, OUT, spec["stem"])
        plt.close(fig)
        checks = check_against_committed(spec, sheet)
        n_bad = sum(1 for c in checks if not c["match"])
        failures += n_bad
        manifest["sheets"].append({
            "stem": spec["stem"], "study": spec["study"], "window": spec["window"], "period": sheet.period,
            "months": int(sheet.metrics.loc["months", spec["strategy"]]), "headline": sheet.headline,
            "inputs": inputs, "outputs": {k: str(p.relative_to(ROOT)) for k, p in paths.items()},
            "checks_against_committed_metrics": {"rows": len(checks), "mismatches": n_bad, "detail": checks},
        })
        print(f"{spec['stem']}: {sheet.headline}")
        print(f"    checked {len(checks)} metrics against {spec['metrics']}: {n_bad} mismatches")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\n{len(SHEETS)} sheets; {failures} mismatches against the committed metrics files; manifest written.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
