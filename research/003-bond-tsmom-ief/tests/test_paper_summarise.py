"""Tests for the monthly paper summary (paper/summarise.py; PREREGISTRATION.md §11.5).

Synthetic bars and hand-made runner records only (tests/toy.py); no network,
no credentials, nothing written outside pytest's temporary folders."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from paper.decide import decision_record
from paper.summarise import (
    BASE_COST,
    COLUMNS,
    append_new,
    read_decisions,
    read_executions,
    summary_rows,
)
from src.calendar import month_end_bars

from tests.toy import toy_bars, toy_ief

BARS = toy_bars("2020-01-02", years=4)
IEF = pd.DataFrame({"close": toy_ief(BARS).to_numpy()}, index=BARS)
BIL = pd.DataFrame({"close": np.exp(np.arange(len(BARS)) * 0.0001) * 91.0}, index=BARS)
MONTH_ENDS = month_end_bars(BARS)
W = 0.69
STAMP = "2020-01-01T00:00:00Z"


def _records(n: int = 5, first: int = -8) -> list[dict]:
    """``n`` consecutive month-end decision records, the holding carried forward."""
    out, holding = [], "BIL"
    for t in MONTH_ENDS.iloc[first:first + n]:
        rec = decision_record(IEF, BIL, t.strftime("%Y-%m-%d"), holding, BARS, run_at_utc=STAMP)
        out.append(rec)
        holding = rec["target"] or holding
    return out


def _ret(frame: pd.DataFrame, start: str, end: str) -> float:
    return frame.loc[pd.Timestamp(end), "close"] / frame.loc[pd.Timestamp(start), "close"] - 1.0


def test_rule_and_benchmarks_match_hand_computation():
    recs = _records()
    rows = summary_rows(recs, {}, IEF, BIL, W, STAMP)
    assert list(rows.columns) == COLUMNS and len(rows) == len(recs) - 1
    holding = "BIL"
    for i, row in rows.iterrows():
        start, end = recs[i]["execution_date"], recs[i + 1]["execution_date"]
        assert (row["execution_date"], row["period_end"]) == (start, end)
        r_ief, r_bil = _ret(IEF, start, end), _ret(BIL, start, end)
        target = recs[i]["target"]
        gross = r_ief if target == "IEF" else r_bil
        factor = (1 - BASE_COST) ** 2 if target != holding else 1.0
        assert row["rule_holding"] == target and row["rule_switched"] == (target != holding)
        assert row["rule_return"] == pytest.approx(factor * (1 + gross) - 1, abs=1e-14)
        assert row["B0"] == pytest.approx(r_bil, abs=1e-14) and row["B1"] == pytest.approx(r_ief, abs=1e-14)
        holding = target
    first = rows.iloc[0]
    assert first["B3"] == pytest.approx(W * first["B1"] + (1 - W) * first["B0"], abs=1e-14)


def test_rule_switches_at_least_once_in_the_toy_window():
    """Guard for the test above: the toy data must exercise the switch cost."""
    rows = summary_rows(_records(n=12, first=-14), {}, IEF, BIL, W, STAMP)
    assert rows["rule_switched"].any() and (~rows["rule_switched"]).any()


def test_period_without_its_end_bar_is_not_written():
    recs = _records()
    end = pd.Timestamp(recs[-1]["execution_date"])
    rows = summary_rows(recs, {}, IEF.drop(index=end), BIL, W, STAMP)
    assert len(rows) == len(recs) - 2
    assert summary_rows(recs[:1], {}, IEF, BIL, W, STAMP).empty


def test_signal_unavailable_record_is_noted_not_a_boundary():
    recs = _records()
    missing = dict(recs[2], status="signal unavailable", target=None, execution_date=None)
    rows = summary_rows([recs[0], recs[1], missing, recs[3], recs[4]], {}, IEF, BIL, W, STAMP)
    assert len(rows) == 3
    assert rows.iloc[1]["period_end"] == recs[3]["execution_date"]
    assert f"{recs[2]['signal_date']}: signal unavailable" in rows.iloc[1]["notes"]


def test_sleeve_columns_empty_without_execution_records():
    rows = summary_rows(_records(), {}, IEF, BIL, W, STAMP)
    assert rows["sleeve_action"].eq("").all() and rows["sleeve_equity_start_usd"].isna().all()
    assert rows["cum_slippage_usd_vs_mid"].isna().all()


def test_sleeve_columns_from_runner_records():
    recs = _records(n=3)
    s0, s1 = recs[0]["signal_date"], recs[1]["signal_date"]
    executions = {
        s0: {"action": "initial-buy", "holding_before": "BIL", "sleeve_equity_before_usd": 2250.0,
             "orders": [{"side": "buy", "symbol": "IEF", "filled_qty": 23, "filled_avg_price": 95.02, "mid_at_order": 95.00}]},
        s1: {"action": "switch", "holding_before": "IEF", "sleeve_equity_before_usd": 2272.5,
             "orders": [{"side": "sell", "symbol": "IEF", "filled_qty": 23, "filled_avg_price": 96.00, "mid_at_order": 96.01},
                        {"side": "buy", "symbol": "BIL", "filled_qty": 24, "filled_avg_price": 91.50, "mid_at_order": 91.51}]},
    }
    rows = summary_rows(recs, executions, IEF, BIL, W, STAMP)
    a, b = rows.iloc[0], rows.iloc[1]
    assert a["sleeve_holding"] == "IEF" and b["sleeve_holding"] == "BIL"
    assert a["sleeve_return"] == pytest.approx(2272.5 / 2250.0 - 1)
    assert np.isnan(b["sleeve_equity_end_usd"])             # no execution record for the next date yet
    assert a["slippage_usd_vs_mid"] == pytest.approx(0.46)    # bought 0.02 above mid on 23 shares: adverse
    assert b["slippage_usd_vs_mid"] == pytest.approx(0.23 - 0.24)  # sold 0.01 below mid; bought 0.01 below mid
    assert b["cum_slippage_usd_vs_mid"] == pytest.approx(0.46 + 0.23 - 0.24)


def test_hold_and_unfilled_actions():
    recs = _records(n=3)
    executions = {recs[0]["signal_date"]: {"action": "hold", "holding_before": "IEF", "sleeve_equity_before_usd": 2250.0, "orders": []},
                  recs[1]["signal_date"]: {"action": "buy-unconfirmed", "holding_before": "IEF", "sleeve_equity_before_usd": 2240.0,
                                           "orders": [{"side": "buy", "symbol": "BIL", "filled_qty": None}]}}
    rows = summary_rows(recs, executions, IEF, BIL, W, STAMP)
    assert rows.iloc[0]["sleeve_holding"] == "IEF" and rows.iloc[1]["sleeve_holding"] == "none filled"


def test_read_executions_takes_last_retry_and_ignores_check_files(tmp_path):
    for name, action in (("2026-11-30.json", "no-order"), ("2026-11-30-retry2.json", "switch"),
                         ("2026-11-30-retry1.json", "no-order"), ("2026-11-30-check-202612011545.json", "check-ok"),
                         ("2026-10-30.json", "initial-buy")):
        (tmp_path / name).write_text(json.dumps({"action": action}))
    got = read_executions(tmp_path)
    assert list(got) == ["2026-10-30", "2026-11-30"]
    assert got["2026-11-30"]["action"] == "switch" and got["2026-10-30"]["action"] == "initial-buy"
    assert read_executions(tmp_path / "absent") == {} and read_decisions(tmp_path / "absent") == []


def test_append_only_never_rewrites_stored_rows():
    recs = _records()
    full = summary_rows(recs, {}, IEF, BIL, W, "later")
    stored = summary_rows(recs[:3], {}, IEF, BIL, W, STAMP)
    out, new, diff = append_new(stored, full)
    assert len(out) == len(full) and len(new) == len(full) - len(stored)
    pd.testing.assert_frame_equal(out.iloc[: len(stored)], stored)   # stamps and values exactly as stored
    assert (new["written_at_utc"] == "later").all() and diff < 1e-15
    again, none, _ = append_new(out, full)
    assert none.empty and len(again) == len(out)


def test_append_refuses_when_stored_rows_do_not_match_the_records():
    recs = _records()
    stored = summary_rows(recs[1:4], {}, IEF, BIL, W, STAMP)
    with pytest.raises(ValueError, match="never rewritten"):
        append_new(stored, summary_rows(recs, {}, IEF, BIL, W, STAMP))


def test_round_trip_through_csv_keeps_the_check_exact(tmp_path):
    recs = _records()
    rows = summary_rows(recs[:3], {}, IEF, BIL, W, STAMP)
    path = tmp_path / "summary.csv"
    rows.to_csv(path, index=False)
    _, new, diff = append_new(pd.read_csv(path), summary_rows(recs, {}, IEF, BIL, W, "later"))
    assert len(new) == 2 and diff < 1e-15
