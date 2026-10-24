"""Monthly summary of the paper record (PREREGISTRATION.md §11.5; Study 001 §11.5 inherited).

One row per holding period that has ended: from the close of one month-end
decision's execution date to the close of the next.  Each row carries

* the rule at official closes: the holding the decision records set, its
  return from the paper bars (``adjustment='all'``) with the study's own
  ``backtest.run_switching`` at the base cost (2 bp per side on a switch);
* the same-dated benchmarks B0 (BIL), B1 (IEF) and B3 (the static mix at the
  frozen in-sample weight w from ``results/insample/summary.json``), from
  the same bars with the study's own ``backtest.benchmarks``;
* the sleeve as the desk's runner observed it: the action of the execution
  record, the holding it left, the sleeve equity the runner marked before
  trading on this execution date and on the next one, the return between the
  two marks, and the slippage of the period's fills against the mid at order
  time (in USD, adverse positive) with its running total.  Empty until an
  execution record exists; nothing is estimated for a period without one.

The file is append-only: a row, once written, is never rewritten.  A rerun
recomputes every period from the bars on disk, appends only periods not yet
in the file and reports the largest difference between a stored row and its
recomputation (split/dividend adjustment scales both ends of a past period
alike, so the difference should be rounding).  The module fetches nothing,
places no order and changes no record; it reads ``paper-log/decisions/``,
``paper-log/executions/`` and the bars ``paper/decide.py --fetch`` stored in
``paper-log/raw/``.

Two departures from Study 001 §11.5's wording, disclosed in ``paper/README.md``:
slippage is measured against the mid at order time, as the runner records it,
not against the official close (the paper bars are dividend-adjusted, so their
close is not the price a fill can be compared with); and the sleeve equity is
the runner's mark (shares at the quote plus sleeve cash), which credits no
fund distribution to the sleeve, so the sleeve's return understates a total
return by the distributions paid in the period.  The rule column is a total
return; the gap between the two is reported, not hidden.

Built 2026-10-24, before the first decision record (2026-10-30).

Usage (from the study folder):  python -m paper.summarise [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from src import backtest
from src.alpaca_bars import load_bars, total_return_index
from src.config import CASH_LEG, COST_CASES, DURATION_LEG, PAPER_LOG_DIR, RESULTS_DIR

from paper.decide import DECISIONS_DIR, PAPER_RAW_DIR

EXECUTIONS_DIR = PAPER_LOG_DIR / "executions"
SUMMARY_PATH = PAPER_LOG_DIR / "summary.csv"
INSAMPLE_SUMMARY = RESULTS_DIR / "insample" / "summary.json"
BASE_COST = COST_CASES["base"]

COLUMNS = ["signal_date", "execution_date", "period_end", "rule_holding", "rule_switched", "rule_return",
           "B0", "B1", "B3", "sleeve_action", "sleeve_holding", "sleeve_equity_start_usd",
           "sleeve_equity_end_usd", "sleeve_return", "slippage_usd_vs_mid", "cum_slippage_usd_vs_mid",
           "notes", "written_at_utc"]
# Columns recomputed on a rerun and compared with the stored row (never rewritten).
NUMERIC_CHECKED = ["rule_return", "B0", "B1", "B3"]
FILLED_ACTIONS = ("switch", "initial-buy")
_EXEC_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-retry(\d+))?\.json$")   # check-mode files never match


def frozen_b3_weight(path: Path = INSAMPLE_SUMMARY) -> float:
    """The B3 weight w, frozen from the in-sample signals (§9.1, the same w out of sample)."""
    return float(json.loads(Path(path).read_text())["weight_b3"])


def read_decisions(directory: Path = DECISIONS_DIR) -> list[dict]:
    directory = Path(directory)
    return [json.loads(p.read_text()) for p in sorted(directory.glob("*.json"))] if directory.is_dir() else []


def read_executions(directory: Path = EXECUTIONS_DIR) -> dict[str, dict]:
    """The execution record that stands for each signal date: the last retry,
    or the first attempt when there was none.  Check-mode files are ignored."""
    directory = Path(directory)
    chosen: dict[str, tuple[int, dict]] = {}
    if not directory.is_dir():
        return {}
    for path in directory.glob("*.json"):
        match = _EXEC_NAME.match(path.name)
        if not match:
            continue
        retry = int(match.group(2) or 0)
        if match.group(1) not in chosen or retry > chosen[match.group(1)][0]:
            chosen[match.group(1)] = (retry, json.loads(path.read_text()))
    return {date: rec for date, (_, rec) in sorted(chosen.items())}


def _sleeve(exec_now: dict | None, exec_next: dict | None) -> dict:
    """The sleeve columns for one period from the runner's own records."""
    if exec_now is None:
        return {"sleeve_action": "", "sleeve_holding": "", "sleeve_equity_start_usd": np.nan,
                "sleeve_equity_end_usd": np.nan, "sleeve_return": np.nan, "slippage_usd_vs_mid": np.nan}
    action = str(exec_now.get("action") or "")
    orders = exec_now.get("orders") or []
    bought = [o for o in orders if o.get("side") == "buy" and (o.get("filled_qty") or 0) > 0]
    if action == "hold":
        holding = exec_now.get("holding_before") or ""
    elif action in FILLED_ACTIONS and bought:
        holding = bought[-1]["symbol"]
    else:
        holding = "none filled"
    slip = 0.0
    for o in orders:
        qty, fill, mid = o.get("filled_qty"), o.get("filled_avg_price"), o.get("mid_at_order")
        if qty and fill and mid:
            slip += (fill - mid) * qty if o.get("side") == "buy" else (mid - fill) * qty
    start = exec_now.get("sleeve_equity_before_usd")
    end = exec_next.get("sleeve_equity_before_usd") if exec_next else None
    start = float(start) if start is not None else np.nan
    end = float(end) if end is not None else np.nan
    return {"sleeve_action": action, "sleeve_holding": holding, "sleeve_equity_start_usd": start,
            "sleeve_equity_end_usd": end, "sleeve_return": end / start - 1.0 if start > 0 else np.nan,
            "slippage_usd_vs_mid": round(slip, 4)}


def summary_rows(decisions: list[dict], executions: dict[str, dict], ief_bars: pd.DataFrame,
                 bil_bars: pd.DataFrame, weight_b3: float, written_at_utc: str) -> pd.DataFrame:
    """Every holding period that has ended, computed from the records and bars given."""
    ok = [d for d in decisions if d.get("status") == "ok"]
    if len(ok) < 2:
        return pd.DataFrame(columns=COLUMNS)
    common = ief_bars.index.intersection(bil_bars.index)
    schedule = pd.DataFrame({"execution_date": pd.to_datetime([d["execution_date"] for d in ok])},
                            index=pd.PeriodIndex([pd.Timestamp(d["signal_date"]).to_period("M") for d in ok]))
    schedule["period_end"] = schedule["execution_date"].shift(-1)
    # A period has ended when the bar of its end date is on disk for both legs.
    ended = schedule["period_end"].isin(common)
    n = int(ended.to_numpy().argmin()) if not ended.all() else len(schedule)
    n = min(n, len(schedule) - 1)
    if n == 0:
        return pd.DataFrame(columns=COLUMNS)
    schedule = schedule.iloc[: n + 1]
    indices = {DURATION_LEG: total_return_index(ief_bars), CASH_LEG: total_return_index(bil_bars)}
    returns = backtest.instrument_returns(indices, schedule)
    targets = pd.Series([d["target"] for d in ok[:n]], index=returns.index)
    rule = backtest.run_switching(targets, returns, BASE_COST, initial_holding=ok[0]["holding_before"])
    bench = backtest.benchmarks(returns, weight_b3, BASE_COST)
    skipped = [d for d in decisions if d.get("status") != "ok"]
    rows = []
    for i, month in enumerate(returns.index):
        start, end = schedule["execution_date"].iloc[i], schedule["period_end"].iloc[i]
        notes = "; ".join(f"{d['signal_date']}: {d.get('status')}" for d in skipped
                          if start < pd.Timestamp(d["signal_date"]) < end)
        sig = ok[i]["signal_date"]
        nxt = executions.get(ok[i + 1]["signal_date"])
        rows.append({"signal_date": sig, "execution_date": start.strftime("%Y-%m-%d"),
                     "period_end": end.strftime("%Y-%m-%d"), "rule_holding": rule.at[month, "holding"],
                     "rule_switched": bool(rule.at[month, "switched"]), "rule_return": rule.at[month, "r"],
                     **{b: bench[b].at[month, "r"] for b in ("B0", "B1", "B3")},
                     **_sleeve(executions.get(sig), nxt), "notes": notes, "written_at_utc": written_at_utc})
    frame = pd.DataFrame(rows, columns=COLUMNS)
    frame["cum_slippage_usd_vs_mid"] = frame["slippage_usd_vs_mid"].cumsum()
    return frame


def append_new(existing: pd.DataFrame, computed: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    """Stored rows unchanged plus the computed rows for periods not yet stored.
    Returns (full frame, appended rows, largest |stored - recomputed| on the
    checked columns of the stored rows).  Raises if the stored rows are not
    a prefix of the computed periods (a record was removed or reordered)."""
    if existing.empty:
        return computed.copy(), computed.copy(), 0.0
    stored = existing["signal_date"].astype(str).tolist()
    if computed["signal_date"].astype(str).tolist()[: len(stored)] != stored:
        raise ValueError("summary.csv does not match the decision records: rows are never rewritten; "
                         "investigate before writing")
    head = computed.iloc[: len(stored)]
    diff = float(np.nanmax(np.abs(existing[NUMERIC_CHECKED].to_numpy(float) - head[NUMERIC_CHECKED].to_numpy(float))))
    new = computed.iloc[len(stored):].copy()
    if not new.empty:
        # the running total continues from the stored rows
        base = float(existing["cum_slippage_usd_vs_mid"].fillna(0).iloc[-1]) if len(existing) else 0.0
        new["cum_slippage_usd_vs_mid"] = base + new["slippage_usd_vs_mid"].cumsum()
    return pd.concat([existing, new], ignore_index=True), new, diff


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="print the rows, write nothing")
    args = parser.parse_args(argv)
    decisions = read_decisions()
    if len([d for d in decisions if d.get("status") == "ok"]) < 2:
        print(f"{len(decisions)} decision record(s) on disk: no holding period has ended; nothing written")
        return 0
    written = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    computed = summary_rows(decisions, read_executions(), load_bars(DURATION_LEG, PAPER_RAW_DIR),
                            load_bars(CASH_LEG, PAPER_RAW_DIR), frozen_b3_weight(), written)
    existing = pd.read_csv(SUMMARY_PATH) if SUMMARY_PATH.is_file() else pd.DataFrame(columns=COLUMNS)
    full, new, diff = append_new(existing, computed)
    print(new.to_string(index=False) if not new.empty else "no new period has ended")
    print(f"stored rows: {len(existing)}; appended: {len(new)}; largest recomputation difference on stored rows: {diff:.2e}")
    if not args.dry_run and not new.empty:
        full.to_csv(SUMMARY_PATH, index=False)
        print(f"written: {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
