"""Tests for the paper decision record (paper/decide.py; PREREGISTRATION.md §11.2, §11.5).

Synthetic bars only (tests/toy.py); no network, no credentials."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from paper.decide import STRATEGY_ID, decision_record, earliest_write_utc, write_record
from src.calendar import month_end_bars

from tests.toy import toy_bars, toy_ief

BARS = toy_bars("2020-01-02", years=4)
IEF = pd.DataFrame({"close": toy_ief(BARS).to_numpy()}, index=BARS)
BIL = pd.DataFrame({"close": np.exp(np.arange(len(BARS)) * 0.0001) * 91.0}, index=BARS)
TRADING_DAYS = BARS                 # the synthetic exchange calendar is the bar calendar itself
MONTH_ENDS = month_end_bars(BARS)
T = MONTH_ENDS.iloc[-3]              # a month-end bar with later bars in the frames
MONTH = T.to_period("M")


def _hand_mom(t: pd.Timestamp) -> float:
    m = t.to_period("M")
    t12 = MONTH_ENDS.loc[m - 12]
    return (IEF.loc[t, "close"] / IEF.loc[t12, "close"]) - (BIL.loc[t, "close"] / BIL.loc[t12, "close"])


def test_record_matches_hand_computation_and_fields():
    rec = decision_record(IEF, BIL, T.strftime("%Y-%m-%d"), "BIL", TRADING_DAYS, run_at_utc="2020-01-01T00:00:00Z")
    assert rec["status"] == "ok" and rec["strategy_id"] == STRATEGY_ID
    assert rec["mom"] == pytest.approx(_hand_mom(T), abs=1e-12)
    assert rec["target"] == ("IEF" if rec["mom"] > 0 else "BIL")
    assert rec["switch"] == (rec["target"] != "BIL")
    assert rec["t12_date"] == MONTH_ENDS.loc[MONTH - 12].strftime("%Y-%m-%d")
    assert rec["tri_ief_t"] / rec["tri_ief_t12"] == pytest.approx(IEF.loc[T, "close"] / IEF.loc[MONTH_ENDS.loc[MONTH - 12], "close"])
    for key in ("signal_date", "execution_date", "tri_cash_t", "tri_cash_t12", "orders", "equity_close", "notes"):
        assert key in rec


def test_execution_date_is_first_trading_day_after_signal():
    rec = decision_record(IEF, BIL, T.strftime("%Y-%m-%d"), "IEF", TRADING_DAYS)
    execution = pd.Timestamp(rec["execution_date"])
    assert execution > T
    assert TRADING_DAYS[TRADING_DAYS > T][0] == execution


def test_later_bars_do_not_change_the_record():
    """No look-ahead (§6.3): truncating the frames at t gives the same record."""
    full = decision_record(IEF, BIL, T.strftime("%Y-%m-%d"), "BIL", TRADING_DAYS, run_at_utc="x")
    cut = decision_record(IEF.loc[:T], BIL.loc[:T], T.strftime("%Y-%m-%d"), "BIL", TRADING_DAYS, run_at_utc="x")
    assert full == cut


def test_missing_signal_bar_is_signal_unavailable():
    without = IEF.drop(index=T)
    rec = decision_record(without, BIL, T.strftime("%Y-%m-%d"), "BIL", TRADING_DAYS)
    assert rec["status"] == "signal unavailable" and rec["target"] is None and rec["execution_date"] is None
    assert "IEF" in rec["notes"]


def test_non_month_end_date_is_refused():
    mid = BARS[BARS.get_loc(T) - 5]            # a bar earlier in the same month
    assert mid.to_period("M") == MONTH
    rec = decision_record(IEF, BIL, mid.strftime("%Y-%m-%d"), "BIL", TRADING_DAYS)
    assert rec["status"] == "signal unavailable" and "not the last NYSE trading day" in rec["notes"]


def test_short_history_is_signal_unavailable():
    early = MONTH_ENDS.iloc[6]
    rec = decision_record(IEF, BIL, early.strftime("%Y-%m-%d"), "BIL", TRADING_DAYS)
    assert rec["status"] == "signal unavailable" and "lookback" in rec["notes"]


def test_bad_holding_rejected():
    with pytest.raises(ValueError):
        decision_record(IEF, BIL, T.strftime("%Y-%m-%d"), "TLT", TRADING_DAYS)


def test_write_record_never_overwrites(tmp_path):
    rec = decision_record(IEF, BIL, T.strftime("%Y-%m-%d"), "BIL", TRADING_DAYS, run_at_utc="x")
    path = write_record(rec, tmp_path)
    assert json.loads(path.read_text()) == rec
    with pytest.raises(FileExistsError):
        write_record(rec, tmp_path)


# --- §11.2 clock gate (added 2026-10-24, before the first record) ---------------

def test_earliest_write_is_1700_new_york_under_edt_and_est():
    # 2026-10-30 is EDT (UTC-4): 17:00 New York = 21:00Z; 2026-11-30 is EST (UTC-5): 22:00Z
    assert earliest_write_utc("2026-10-30") == pd.Timestamp("2026-10-30T21:00:00Z")
    assert earliest_write_utc("2026-11-30") == pd.Timestamp("2026-11-30T22:00:00Z")


def test_write_record_refuses_before_1700_new_york(tmp_path):
    rec = decision_record(IEF, BIL, T.strftime("%Y-%m-%d"), "BIL", TRADING_DAYS, run_at_utc="x")
    early = earliest_write_utc(rec["signal_date"]) - pd.Timedelta(minutes=1)
    with pytest.raises(RuntimeError, match="too early"):
        write_record(rec, tmp_path, now_utc=early)
    assert list(tmp_path.iterdir()) == []            # a refused write leaves nothing on disk
    # the same minute, and a later day (the §11.2 re-check), are accepted
    path = write_record(rec, tmp_path, now_utc=earliest_write_utc(rec["signal_date"]))
    assert path.exists()
    later = decision_record(IEF, BIL, MONTH_ENDS.iloc[-4].strftime("%Y-%m-%d"), "BIL", TRADING_DAYS, run_at_utc="x")
    assert write_record(later, tmp_path, now_utc=earliest_write_utc(later["signal_date"]) + pd.Timedelta(days=1)).exists()


def test_write_record_gate_accepts_naive_and_string_clocks(tmp_path):
    rec = decision_record(IEF, BIL, T.strftime("%Y-%m-%d"), "BIL", TRADING_DAYS, run_at_utc="x")
    naive = earliest_write_utc(rec["signal_date"]).tz_localize(None) - pd.Timedelta(minutes=1)
    with pytest.raises(RuntimeError, match="too early"):
        write_record(rec, tmp_path, now_utc=naive)                      # naive = UTC
    with pytest.raises(RuntimeError, match="too early"):
        write_record(rec, tmp_path, now_utc=str(naive))                 # ISO string, naive = UTC
    assert write_record(rec, tmp_path, now_utc=str(naive + pd.Timedelta(minutes=1))).exists()
