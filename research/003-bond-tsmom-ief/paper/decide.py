"""Month-end decision record for the paper sleeve (PREREGISTRATION.md §11.2, §11.5).

On the last NYSE trading day of the month, after the close, the paper path
fetches Alpaca daily bars (``adjustment='all'``) for IEF and BIL into the
paper log's own raw directory (never the study's ``data/raw/``, whose hashes
are frozen in ``results/data_manifest.json``), confirms the bar for the
signal date ``t`` is present, computes

    mom_t = TRI_IEF(t) / TRI_IEF(t_12) - TRI_BIL(t) / TRI_BIL(t_12)

with the study's own ``signal.excess_momentum`` (the same function the
backtest called), sets ``target = IEF if mom_t > 0 else BIL``, and writes one
JSON record.  The order leg reads that record on the next NYSE trading day;
this module places no order and holds no credential beyond the environment
variables ``src.alpaca_bars`` reads.

A record is written whatever the outcome: a missing or stale month-end bar
produces ``status = "signal unavailable"`` with ``target = None`` (§11.2:
hold, re-check for up to three NYSE days, then alert).  The record carries
``run_at_utc`` so the commit history shows it was written after the signal
date, never before and never backdated.

Usage (from the study folder, after the close on the signal date):

    python -m paper.decide --signal-date 2026-10-30 --holding BIL [--fetch]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.alpaca_bars import fetch_bars, load_bars, total_return_index
from src.calendar import execution_dates, month_end_bars, nyse_trading_days
from src.config import CASH_LEG, DURATION_LEG, MOMENTUM_LOOKBACK_MONTHS, PAPER_LOG_DIR, SYMBOLS
from src.signal import excess_momentum, month_end_levels

PAPER_RAW_DIR = PAPER_LOG_DIR / "raw"             # git-ignored, separate from the study's data/raw/
PAPER_MANIFEST = PAPER_LOG_DIR / "manifest.json"  # provenance of every paper fetch (hashes, not data)
DECISIONS_DIR = PAPER_LOG_DIR / "decisions"
STRATEGY_ID = "study003-tsmom-ief-bil"
STRATEGY_VERSION = "1"
# Bars are fetched from this date so that the 12-month lookback and the T3
# comparison always have more history than they need.
PAPER_BARS_START = "2024-01-02"


def decision_record(ief_bars: pd.DataFrame, bil_bars: pd.DataFrame, signal_date: str,
                    holding_before: str, trading_days: pd.DatetimeIndex | None = None,
                    run_at_utc: str | None = None) -> dict:
    """The §11.5 record for signal date ``signal_date`` from the two bar
    frames.  Only bars on or before ``signal_date`` are used (§6.3); the
    frames may contain later bars and they are ignored."""
    if holding_before not in SYMBOLS:
        raise ValueError(f"holding_before must be one of {SYMBOLS}, got {holding_before!r}")
    t = pd.Timestamp(signal_date).normalize()
    month_last_day = t.to_period("M").to_timestamp(how="end").normalize()
    if trading_days is None:
        trading_days = nyse_trading_days(t, month_last_day + pd.Timedelta(days=10))
    later_in_month = trading_days[(trading_days > t) & (trading_days <= month_last_day)]
    ief = ief_bars.loc[ief_bars.index <= t]
    bil = bil_bars.loc[bil_bars.index <= t]
    base = {
        "strategy_id": STRATEGY_ID, "strategy_version": STRATEGY_VERSION,
        "signal_date": t.strftime("%Y-%m-%d"), "holding_before": holding_before,
        "run_at_utc": run_at_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "orders": [], "equity_close": None, "peak_equity": None, "drawdown": None, "notes": "",
    }
    if len(later_in_month):
        return {**base, "status": "signal unavailable", "target": None, "execution_date": None,
                "notes": f"{t.date()} is not the last NYSE trading day of its month "
                         f"({later_in_month[-1].date()} is); no signal on other days (§11.2)"}
    for name, frame in ((DURATION_LEG, ief), (CASH_LEG, bil)):
        if frame.empty or frame.index[-1] != t:
            last = frame.index[-1].strftime("%Y-%m-%d") if not frame.empty else None
            return {**base, "status": "signal unavailable", "target": None, "execution_date": None,
                    "notes": f"no {name} bar for the signal date (last bar {last}); hold and re-check (§11.2)"}
    month_ends = month_end_bars(ief.index)
    tri_ief, tri_bil = total_return_index(ief), total_return_index(bil)
    mom = excess_momentum(tri_ief, tri_bil, month_ends, lookback=MOMENTUM_LOOKBACK_MONTHS)
    month = t.to_period("M")
    if month not in mom.index:
        return {**base, "status": "signal unavailable", "target": None, "execution_date": None,
                "notes": f"lookback of {MOMENTUM_LOOKBACK_MONTHS} months not covered by the fetched bars"}
    value = float(mom.loc[month])
    lv_ief, lv_bil = month_end_levels(tri_ief, month_ends), month_end_levels(tri_bil, month_ends)
    t12 = month - MOMENTUM_LOOKBACK_MONTHS
    execution = execution_dates(pd.Series([t], index=[month]), trading_days).iloc[0]
    target = DURATION_LEG if value > 0 else CASH_LEG
    return {
        **base, "status": "ok", "execution_date": execution.strftime("%Y-%m-%d"),
        "tri_ief_t": float(lv_ief.loc[month]), "tri_ief_t12": float(lv_ief.loc[t12]),
        "tri_cash_t": float(lv_bil.loc[month]), "tri_cash_t12": float(lv_bil.loc[t12]),
        "t12_date": month_ends.loc[t12].strftime("%Y-%m-%d"),
        "mom": value, "target": target, "switch": target != holding_before,
    }


def write_record(record: dict, directory: Path = DECISIONS_DIR) -> Path:
    """One file per signal date; refuses to overwrite (a record is never
    rewritten; a correction is a new, later record with a note)."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record['signal_date']}.json"
    if path.exists():
        raise FileExistsError(f"{path} exists: decision records are never overwritten")
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--signal-date", required=True, help="YYYY-MM-DD, the last NYSE trading day of the month")
    parser.add_argument("--holding", required=True, choices=SYMBOLS, help="the sleeve's current holding")
    parser.add_argument("--fetch", action="store_true", help="fetch fresh Alpaca bars into paper-log/raw/ first")
    parser.add_argument("--dry-run", action="store_true", help="print the record, write nothing")
    args = parser.parse_args(argv)
    if args.fetch:
        for symbol in SYMBOLS:
            fetch_bars(symbol, start=PAPER_BARS_START, raw_dir=PAPER_RAW_DIR, manifest_path=PAPER_MANIFEST)
    record = decision_record(load_bars(DURATION_LEG, PAPER_RAW_DIR), load_bars(CASH_LEG, PAPER_RAW_DIR),
                             args.signal_date, args.holding)
    print(json.dumps(record, indent=2, sort_keys=True))
    if not args.dry_run:
        print(f"written: {write_record(record)}")
    return 0 if record["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
