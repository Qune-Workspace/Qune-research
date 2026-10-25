"""Paper-trading decision step and order plan (§11.2, §11.5).

This module produces the monthly decision record: it fetches DGS10 and DTB3
from FRED, confirms that the observation for the intended signal date t is
present (§6.3), computes the spread and the target, and writes one JSON
record to ``paper-log/``.  It also turns a target into whole-share order
intents for the fixed 4 500 USD sleeve (§11.1, §6.2).

It does not submit orders.  Under RISK_FRAMEWORK.md orders exist only when
the desk's runner executes a strategy that Independent Risk has cleared, so
submission, the engine stop and the drawdown halt (§11.4, §12) belong to that
runner, which consumes the decision record written here.  Nothing here runs
before the publication date of the study note (§8.4).

Usage (from the study folder): ``python -m src.paper_trade --signal-month 2026-10``.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .bey import discount_to_bey
from .calendar import build_schedule
from .config import CASH_LEG, DURATION_LEG, PAPER_LOG_DIR
from .fred import fetch_series
from .signal import target_from_value

SLEEVE_USD = 4_500.0            # §11.1
MAX_FRED_RECHECKS = 3           # NYSE days to wait for FRED to contain date t (§11.2)
ORDER_SIZE_TOLERANCE = 0.02     # §12 item 7


def decision_record(dgs10: pd.Series, dtb3: pd.Series, signal_month: str, holding_before: str) -> dict:
    """§11.5 decision fields for the signal date of ``signal_month``, from
    the series as currently published.  Raises if the month has no valid
    observation yet, so that the caller re-checks on the next NYSE day."""
    schedule = build_schedule(dgs10, dtb3, signal_month, signal_month)
    if schedule.empty:
        raise LookupError(f"FRED has no observation with both DGS10 and DTB3 in {signal_month}")
    t = schedule["signal_date"].iloc[0]
    dgs10_t, dtb3_t = float(dgs10.loc[t]), float(dtb3.loc[t])
    bey_t = float(discount_to_bey(dtb3_t / 100.0))
    spread = dgs10_t / 100.0 - bey_t
    target = str(target_from_value(pd.Series([spread])).iloc[0])
    return {"signal_date": t.strftime("%Y-%m-%d"),
            "execution_date": schedule["execution_date"].iloc[0].strftime("%Y-%m-%d"),
            "dgs10": dgs10_t, "dtb3": dtb3_t, "bey": bey_t, "spread": spread, "target": target,
            "holding_before": holding_before, "orders": [], "equity_close": None, "peak_equity": None,
            "drawdown": None, "notes": "decision only; orders are placed by the cleared runner (§11)",
            "recorded_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}


def order_plan(target: str, holding_before: str, holding_qty: int, prices: dict[str, float],
               sleeve_usd: float = SLEEVE_USD) -> list[dict]:
    """Whole-share order intents for a switch (§6.2, §11.2): sell the whole
    holding, then buy the target with the proceeds capped at the sleeve.
    Empty when the target equals the holding (§6.4)."""
    if target == holding_before:
        return []
    proceeds = min(holding_qty * prices[holding_before], sleeve_usd)
    buy_qty = math.floor(proceeds / prices[target])
    orders = [{"symbol": holding_before, "side": "sell", "qty": holding_qty}] if holding_qty else []
    if buy_qty:
        orders.append({"symbol": target, "side": "buy", "qty": buy_qty})
    for order in orders:
        notional = order["qty"] * prices[order["symbol"]]
        order["within_size_tolerance"] = abs(notional - proceeds) <= ORDER_SIZE_TOLERANCE * proceeds
    return orders


def write_record(record: dict, log_dir: Path = PAPER_LOG_DIR) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"decision_{record['signal_date']}.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monthly paper-trading decision record (§11.2).")
    parser.add_argument("--signal-month", required=True, help="YYYY-MM of the signal date")
    parser.add_argument("--holding", default=CASH_LEG, choices=(DURATION_LEG, CASH_LEG))
    args = parser.parse_args(argv)
    dgs10, dtb3 = fetch_series("DGS10"), fetch_series("DTB3")
    try:
        record = decision_record(dgs10, dtb3, args.signal_month, args.holding)
    except LookupError as exc:
        print(f"signal unavailable: {exc}; re-check next NYSE day (up to {MAX_FRED_RECHECKS})")
        return 1
    path = write_record(record)
    print(f"target {record['target']} for execution on {record['execution_date']}; record {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
