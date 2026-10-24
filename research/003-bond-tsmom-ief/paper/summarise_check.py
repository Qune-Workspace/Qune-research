"""Read-only check of ``paper/summarise.py`` against the committed out-of-sample record.

Builds a decision record with ``paper/decide.decision_record`` for every
month-end of the out-of-sample window (plus the month after the last period,
which closes it) from the study's own Alpaca bars in ``data/raw/``, runs
``paper/summarise.summary_rows`` on them, and compares the result with
``results/oos/monthly_base.csv``: execution dates, period ends, holdings and
the T1, B0, B1 and B3 returns.  It writes nothing and decides nothing; it
checks that the paper summary computes a period exactly as the study's
backtest did.  ``data/raw/`` is git-ignored, so the check needs the files
``reproduce.sh`` fetches and verifies by hash; it is not part of CI.

First run 2026-10-24 (before any paper record): 94 records, all ``ok``;
93 of 93 periods; dates and holdings equal; largest absolute difference
9.9e-17 (T1 and B3), 9.8e-17 (B0), 9.7e-17 (B1).

Usage (from the study folder):  python -m paper.summarise_check
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from src.alpaca_bars import load_bars
from src.calendar import nyse_trading_days
from src.config import RAW_DIR, RESULTS_DIR

from paper.decide import decision_record
from paper.summarise import frozen_b3_weight, summary_rows


def main() -> int:
    ief, bil = load_bars("IEF", RAW_DIR), load_bars("BIL", RAW_DIR)
    committed = pd.read_csv(RESULTS_DIR / "oos" / "monthly_base.csv")
    days = nyse_trading_days("2018-01-01", "2026-12-31")
    months = [*committed["month"], str(pd.Period(committed["month"].iloc[-1]) + 1)]
    records, holding = [], "BIL"
    for month in months:
        period = pd.Period(month)
        t = days[(days >= period.start_time) & (days <= period.end_time)][-1]
        record = decision_record(ief, bil, t.strftime("%Y-%m-%d"), holding, days, run_at_utc="check")
        records.append(record)
        holding = record["target"] or holding
    rows = summary_rows(records, {}, ief, bil, frozen_b3_weight(), "check")
    print(f"records {len(records)}, statuses {sorted({r['status'] for r in records})}, "
          f"periods {len(rows)} of {len(committed)} committed")
    ok = len(rows) == len(committed)
    a, b = rows.reset_index(drop=True), committed.iloc[: len(rows)]
    same = (a["execution_date"].eq(b["execution_date"]).all() and a["period_end"].eq(b["period_end"]).all()
            and a["rule_holding"].eq(b["T1_holding"]).all())
    print(f"dates and holdings equal: {same}")
    ok &= bool(same)
    for col, ref in (("rule_return", "T1"), ("B0", "B0"), ("B1", "B1"), ("B3", "B3")):
        diff = float(np.max(np.abs(a[col].to_numpy(float) - b[ref].to_numpy(float))))
        print(f"{col} vs {ref}: largest absolute difference {diff:.1e}")
        ok &= diff < 1e-12
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
