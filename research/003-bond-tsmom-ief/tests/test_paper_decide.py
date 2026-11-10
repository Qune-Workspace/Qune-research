"""Tests for the paper decision record (paper/decide.py; PREREGISTRATION.md §11.2, §11.5).

Synthetic bars only (tests/toy.py); no network, no credentials.  Since 2026-11-10 the record's gate
(``record_violations``), the chain reader (``holding_in_force``) and the held ``--holding`` argument are
tested here too, with the search that found them kept as parametrised cases against the committed record
(research/POST_MORTEMS.md "A holding passed by hand")."""
from __future__ import annotations

import json
import shutil

import numpy as np
import pandas as pd
import pytest
from paper.decide import (
    DECISIONS_DIR,
    RECORD_STATUSES,
    STARTING_HOLDING,
    STRATEGY_ID,
    decision_record,
    earliest_write_utc,
    holding_in_force,
    load_records,
    main,
    record_violations,
    write_record,
)
from src.alpaca_bars import raw_path
from src.calendar import month_end_bars

from tests.toy import toy_bars, toy_ief

BARS = toy_bars("2020-01-02", years=4)
IEF = pd.DataFrame({"close": toy_ief(BARS).to_numpy()}, index=BARS)
BIL = pd.DataFrame({"close": np.exp(np.arange(len(BARS)) * 0.0001) * 91.0}, index=BARS)
TRADING_DAYS = BARS                 # the synthetic exchange calendar is the bar calendar itself
MONTH_ENDS = month_end_bars(BARS)
T = MONTH_ENDS.iloc[-3]              # a month-end bar with later bars in the frames
MONTH = T.to_period("M")
COMMITTED = DECISIONS_DIR / "2026-10-30.json"   # the first forward record, written 2026-10-31


def _stamp(t) -> str:
    """A run stamp the gate admits: an hour after 17:00 New York on the signal date.  Until 2026-11-10 these
    tests stamped records ``"x"`` and ``"2020-01-01T00:00:00Z"``, records no run writes."""
    return (earliest_write_utc(str(pd.Timestamp(t).date())) + pd.Timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rec(t, holding: str, ief: pd.DataFrame = IEF, **over) -> dict:
    t = pd.Timestamp(t)
    return dict(decision_record(ief, BIL, t.strftime("%Y-%m-%d"), holding, TRADING_DAYS, run_at_utc=_stamp(t)), **over)


def _after(t) -> str:
    return str(earliest_write_utc(str(pd.Timestamp(t).date())) + pd.Timedelta(days=1))


def _hand_mom(t: pd.Timestamp) -> float:
    m = t.to_period("M")
    t12 = MONTH_ENDS.loc[m - 12]
    return (IEF.loc[t, "close"] / IEF.loc[t12, "close"]) - (BIL.loc[t, "close"] / BIL.loc[t12, "close"])


def test_record_matches_hand_computation_and_fields():
    rec = _rec(T, "BIL")
    assert rec["status"] == "ok" and rec["strategy_id"] == STRATEGY_ID
    assert rec["mom"] == pytest.approx(_hand_mom(T), abs=1e-12)
    assert rec["target"] == ("IEF" if rec["mom"] > 0 else "BIL")
    assert rec["switch"] == (rec["target"] != "BIL")
    assert rec["t12_date"] == MONTH_ENDS.loc[MONTH - 12].strftime("%Y-%m-%d")
    assert rec["tri_ief_t"] / rec["tri_ief_t12"] == pytest.approx(IEF.loc[T, "close"] / IEF.loc[MONTH_ENDS.loc[MONTH - 12], "close"])
    for key in ("signal_date", "execution_date", "tri_cash_t", "tri_cash_t12", "orders", "equity_close", "notes"):
        assert key in rec
    assert record_violations(rec, f"{rec['signal_date']}.json") == []   # what the writer writes, the gate admits


def test_execution_date_is_first_trading_day_after_signal():
    rec = decision_record(IEF, BIL, T.strftime("%Y-%m-%d"), "IEF", TRADING_DAYS)
    execution = pd.Timestamp(rec["execution_date"])
    assert execution > T
    assert TRADING_DAYS[TRADING_DAYS > T][0] == execution


def test_later_bars_do_not_change_the_record():
    """No look-ahead (§6.3): truncating the frames at t gives the same record."""
    full = _rec(T, "BIL")
    cut = dict(decision_record(IEF.loc[:T], BIL.loc[:T], T.strftime("%Y-%m-%d"), "BIL", TRADING_DAYS, run_at_utc=_stamp(T)))
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
    rec = _rec(T, "BIL")
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
    rec = _rec(T, "BIL")
    early = earliest_write_utc(rec["signal_date"]) - pd.Timedelta(minutes=1)
    with pytest.raises(RuntimeError, match="too early"):
        write_record(rec, tmp_path, now_utc=early)
    assert list(tmp_path.iterdir()) == []            # a refused write leaves nothing on disk
    # the same minute, and a later day (the §11.2 re-check), are accepted
    path = write_record(rec, tmp_path, now_utc=earliest_write_utc(rec["signal_date"]))
    assert path.exists()
    nxt = MONTH_ENDS.iloc[-2]                        # the next month, its holding the state the record left
    later = _rec(nxt, rec["target"])
    assert write_record(later, tmp_path, now_utc=earliest_write_utc(later["signal_date"]) + pd.Timedelta(days=1)).exists()


def test_write_record_gate_accepts_naive_and_string_clocks(tmp_path):
    rec = _rec(T, "BIL")
    naive = earliest_write_utc(rec["signal_date"]).tz_localize(None) - pd.Timedelta(minutes=1)
    with pytest.raises(RuntimeError, match="too early"):
        write_record(rec, tmp_path, now_utc=naive)                      # naive = UTC
    with pytest.raises(RuntimeError, match="too early"):
        write_record(rec, tmp_path, now_utc=str(naive))                 # ISO string, naive = UTC
    assert write_record(rec, tmp_path, now_utc=str(naive + pd.Timedelta(minutes=1))).exists()


# --- the record's gate and the chain (added 2026-11-10, after the search in research/POST_MORTEMS.md) -------

def test_committed_record_passes_its_own_gate():
    """The first forward record, as committed, through the reader; the holding before the 30 November record
    is its target, read from the record and not from a hand-typed argument."""
    records = load_records(DECISIONS_DIR)
    assert [r["signal_date"] for r in records] == ["2026-10-30"]
    assert record_violations(json.loads(COMMITTED.read_text()), COMMITTED) == []
    assert holding_in_force("2026-10-30", DECISIONS_DIR) == (STARTING_HOLDING, "the pre-registered starting position (paper/README.md)")
    assert holding_in_force("2026-11-30", DECISIONS_DIR) == (records[0]["target"], "decision record 2026-10-30 (target)")


# One field of the committed record at a time, with the word the refusal must carry; the search of 2026-11-10
# (nothing was held before that day) kept as a test.  ``None`` as the value removes the field.
ALTERATIONS = [
    ("status", "OK", "status"), ("status", "done", "status"), ("status", None, "status"),
    ("holding_before", "ief", "holding_before"), ("holding_before", "SPY", "holding_before"),
    ("holding_before", None, "holding_before"),
    ("target", "IEF", "target"), ("target", "spy", "target"), ("target", None, "target"),
    ("switch", True, "switch"),
    ("execution_date", "2026-10-29", "execution_date"), ("execution_date", "2026-10-30", "execution_date"),
    ("execution_date", None, "execution_date"),
    ("signal_date", "30/10/2026", "signal_date"), ("signal_date", "2026-10-31", "signal_date"),
    ("run_at_utc", "soon", "run_at_utc"), ("run_at_utc", "2026-10-30T20:59:59Z", "run_at_utc"),
    ("strategy_id", "study004-xasset", "strategy_id"), ("strategy_version", "2", "strategy_version"),
    ("orders", [{"symbol": "IEF", "qty": 20}], "orders"),
    ("mom", "-0.05", "mom"), ("mom", float("nan"), "mom"), ("mom", 0.05, "target"), ("mom", -0.04, "mom"),
    ("tri_ief_t", None, "tri_ief_t"), ("tri_cash_t12", "x", "tri_cash_t12"), ("tri_ief_t12", -1.0, "tri_ief_t12"),
    ("t12_date", "2025-13-45", "t12_date"), ("t12_date", "2026-10-30", "t12_date"),
    ("equity_close", 1000.0, "equity_close"), ("notes", None, "notes"),
]


def _altered(column: str, value) -> dict:
    record = json.loads(COMMITTED.read_text())
    if value is None:
        record.pop(column, None)
    else:
        record[column] = value
    return record


@pytest.mark.parametrize(("column", "value", "word"), ALTERATIONS, ids=[f"{c}={v!r}" for c, v, _ in ALTERATIONS])
def test_an_altered_column_of_the_committed_record_is_refused_by_name(tmp_path, column, value, word):
    record = _altered(column, value)
    (tmp_path / COMMITTED.name).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    with pytest.raises(ValueError, match=word) as refused:
        load_records(tmp_path)
    assert COMMITTED.name in str(refused.value) and "fix the record, never the reader" in str(refused.value)
    with pytest.raises(ValueError, match=word):
        holding_in_force("2026-11-30", tmp_path)
    if column != "signal_date" or value == "30/10/2026":     # the writer names the file after the record's own date
        empty = tmp_path / "writer"
        with pytest.raises(ValueError, match=word):
            write_record(record, empty, now_utc="2026-11-01T00:00:00Z")
        assert not empty.exists() or list(empty.iterdir()) == []


def test_two_records_for_one_month_are_refused(tmp_path):
    base = json.loads(COMMITTED.read_text())
    (tmp_path / "2026-10-30.json").write_text(json.dumps(base) + "\n")
    second = dict(base, signal_date="2026-10-29", execution_date="2026-10-30", run_at_utc="2026-10-29T22:00:00Z")
    (tmp_path / "2026-10-29.json").write_text(json.dumps(second) + "\n")
    with pytest.raises(ValueError, match="two records in 2026-10"):
        load_records(tmp_path)


@pytest.mark.parametrize(("name", "text", "word"), [
    ("2026-11-30.json", "[1, 2]\n", "does not hold a record"),
    ("2026-11-30.json", "{not json\n", "not JSON"),
    ("record.json", None, "not named after its signal_date"),       # a well-formed record under another name
])
def test_a_file_that_is_not_a_record_is_refused(tmp_path, name, text, word):
    shutil.copy(COMMITTED, tmp_path / COMMITTED.name)
    if text is None:
        text = json.dumps(dict(json.loads(COMMITTED.read_text()), signal_date="2026-11-30", execution_date="2026-12-01",
                               run_at_utc="2026-11-30T22:30:00Z")) + "\n"
    (tmp_path / name).write_text(text)
    with pytest.raises(ValueError, match=word):
        load_records(tmp_path)


def test_holding_in_force_walks_the_chain(tmp_path):
    """Start BIL; each record's holding_before is the state in force before it; an ok record's target is the
    state after it; a signal-unavailable record carries the holding; an edited link is refused, not carried."""
    held = STARTING_HOLDING
    dates = MONTH_ENDS.iloc[-8:-3]
    for i, t in enumerate(dates):
        ief = IEF.drop(index=t) if i == 2 else IEF              # the third month has no signal bar
        rec = _rec(t, held, ief)
        assert holding_in_force(rec["signal_date"], tmp_path)[0] == held
        write_record(rec, tmp_path, now_utc=_after(t))
        if rec["status"] == "ok":
            held = rec["target"]
        else:
            assert rec["status"] == "signal unavailable"
            assert holding_in_force(str(T.date()), tmp_path) == (held, f"decision record {rec['signal_date']} (signal unavailable: {held} held)")
    assert len(load_records(tmp_path)) == 5
    after, source = holding_in_force(str(T.date()), tmp_path)
    assert after == held and source.startswith("decision record ")
    # an edited link: a well-formed record whose holding_before is not the state in force before it
    path = tmp_path / f"{dates.iloc[3].strftime('%Y-%m-%d')}.json"
    record = json.loads(path.read_text())
    other = "IEF" if record["holding_before"] == "BIL" else "BIL"
    record["holding_before"], record["switch"] = other, record["target"] != other
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    assert record_violations(record, path) == []                 # the gate alone would admit it
    with pytest.raises(ValueError, match=f"record for {record['signal_date']} says holding_before {other}"):
        holding_in_force(str(T.date()), tmp_path)
    assert holding_in_force(dates.iloc[3].strftime("%Y-%m-%d"), tmp_path)[0] != other   # the chain before it is intact


def test_write_record_refuses_a_holding_not_in_force(tmp_path):
    first = _rec(MONTH_ENDS.iloc[-4], STARTING_HOLDING)
    write_record(first, tmp_path, now_utc=_after(MONTH_ENDS.iloc[-4]))
    other = "IEF" if first["target"] == "BIL" else "BIL"
    wrong = _rec(T, other)                                       # the hand-typed holding of the old command line
    with pytest.raises(ValueError, match=f"holding_before {other} but the state in force before it is {first['target']}"):
        write_record(wrong, tmp_path, now_utc=_after(T))
    assert sorted(p.name for p in tmp_path.iterdir()) == [f"{first['signal_date']}.json"]
    assert write_record(_rec(T, first["target"]), tmp_path, now_utc=_after(T)).exists()


def test_write_record_refuses_a_backdated_record(tmp_path):
    write_record(_rec(T, STARTING_HOLDING), tmp_path, now_utc=_after(T))
    earlier = _rec(MONTH_ENDS.iloc[-4], STARTING_HOLDING)
    with pytest.raises(ValueError, match="never backdated"):
        write_record(earlier, tmp_path, now_utc=_after(T))
    assert len(list(tmp_path.iterdir())) == 1


def test_write_record_judges_its_own_record(tmp_path):
    rec = _rec(T, "BIL", orders=[{"symbol": "IEF", "qty": 20}])
    with pytest.raises(ValueError, match="orders"):
        write_record(rec, tmp_path, now_utc=_after(T))
    assert not tmp_path.exists() or list(tmp_path.iterdir()) == []


def _toy_raw(raw_dir) -> None:
    raw_dir.mkdir()
    for symbol, frame in (("IEF", IEF), ("BIL", BIL)):
        frame.rename_axis("date").to_csv(raw_path(symbol, raw_dir))


def test_main_holds_the_hand_holding_against_the_record(tmp_path, capsys):
    """``--holding`` is optional; given, it must be the holding in force; the record is written with the
    holding read from the chain.  Paths are passed by name (no module constant is patched)."""
    decisions, raw = tmp_path / "decisions", tmp_path / "raw"
    _toy_raw(raw)
    first = _rec(MONTH_ENDS.iloc[-4], STARTING_HOLDING)
    write_record(first, decisions, now_utc=_after(MONTH_ENDS.iloc[-4]))
    other = "IEF" if first["target"] == "BIL" else "BIL"
    date = T.strftime("%Y-%m-%d")
    assert main(["--signal-date", date, "--holding", other, "--dry-run"], decisions_dir=decisions, raw_dir=raw) == 1
    out = capsys.readouterr().out
    assert f"refused: --holding {other} disagrees with the record" in out and first["target"] in out
    assert sorted(p.name for p in decisions.iterdir()) == [f"{first['signal_date']}.json"]
    rc = main(["--signal-date", date], decisions_dir=decisions, raw_dir=raw)      # the holding read from the chain
    out = capsys.readouterr().out
    written = json.loads((decisions / f"{date}.json").read_text())
    assert written["holding_before"] == first["target"] and written["status"] in RECORD_STATUSES
    assert rc == (0 if written["status"] == "ok" else 1) and "written:" in out
    assert [r["signal_date"] for r in load_records(decisions)] == [first["signal_date"], date]
    # the same holding given by hand agrees; the window is recorded, so the write is refused and nothing changes
    assert main(["--signal-date", date, "--holding", first["target"]], decisions_dir=decisions, raw_dir=raw) == 1
    assert "never overwritten" in capsys.readouterr().out
    assert json.loads((decisions / f"{date}.json").read_text()) == written


def test_main_refuses_when_a_record_on_disk_is_not_as_written(tmp_path, capsys):
    decisions, raw = tmp_path / "decisions", tmp_path / "raw"
    _toy_raw(raw)
    decisions.mkdir()
    (decisions / COMMITTED.name).write_text(json.dumps(_altered("holding_before", "SPY")) + "\n")
    assert main(["--signal-date", "2026-11-30", "--dry-run"], decisions_dir=decisions, raw_dir=raw) == 1
    out = capsys.readouterr().out
    assert "refused:" in out and "holding_before 'SPY'" in out
    assert [p.name for p in decisions.iterdir()] == [COMMITTED.name]
