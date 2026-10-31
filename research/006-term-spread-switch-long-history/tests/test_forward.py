"""Forward record (§11): gates, signal-date finality, records, shadow line
through the frozen engine, interim and scoring.  Constructed data only."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from src import backtest, forward
from src.config import CASH_LEG, DURATION_LEG


def _fred(end: str, start: str = "2026-06-01", inverted: bool = False) -> dict[str, pd.Series]:
    """Weekday rows; DGS10 above (or below) the bill, DGS7 a little under DGS10."""
    days = pd.bdate_range(start, end)
    ten = pd.Series(4.5 + 0.001 * np.arange(len(days)), index=days)
    bill = ten + (0.5 if inverted else -0.5)
    return {"DGS10": ten, "DTB3": bill, "DGS7": ten - 0.1}


START = {"T1": "IEF", "T2": "IEF", "T3": "IEF"}


def test_signal_waits_until_every_later_weekday_has_a_row():
    state, t, why = forward.signal_status(_fred("2026-10-29"), "2026-10")
    assert state == "wait" and t == pd.Timestamp("2026-10-29") and "2026-10-30" in why
    state, t, _ = forward.signal_status(_fred("2026-10-30"), "2026-10")
    assert state == "final" and t == pd.Timestamp("2026-10-30")


def test_missing_value_on_last_weekday_moves_t_back_once_the_row_exists():
    fred = _fred("2026-10-30")
    fred["DGS10"].loc["2026-10-30"] = np.nan  # an empty FRED row (a bond-market holiday)
    state, t, _ = forward.signal_status(fred, "2026-10")
    assert state == "final" and t == pd.Timestamp("2026-10-29")


def test_last_weekday_t_waits_for_its_own_dgs7_row():
    # Found by the code review of Study 007's forward007.py (2026-10-25): with t on the last weekday
    # there are no later days to check, so a DGS7 not yet posted would have held T3 for good.
    fred = _fred("2026-10-30")
    fred["DGS7"] = fred["DGS7"].loc[:"2026-10-29"]
    state, t, why = forward.signal_status(fred, "2026-10")
    assert state == "wait" and t == pd.Timestamp("2026-10-30") and "DGS7" in why


def test_periods_to_scoring_is_zero_at_a_full_block():
    shadow = pd.DataFrame({c: [0.0] * 60 for c in forward.SHADOW_COLUMNS})
    shadow["T1_switched"] = False
    assert forward.interim(shadow, "x")["periods_to_scoring"] == 0


def test_nyse_holiday_after_t_needs_no_row():
    # 2027-05-31 is Memorial Day (NYSE closed); FRED shows no value that day.
    state, t, _ = forward.signal_status(_fred("2027-05-28", start="2027-03-01"), "2027-05")
    assert state == "final" and t == pd.Timestamp("2027-05-28")


def test_targets_use_nothing_after_t():
    fred = _fred("2026-10-30")
    later = _fred("2026-12-31", inverted=True)
    joined = {k: pd.concat([fred[k], later[k].loc["2026-11-02":]]) for k in fred}
    t = pd.Timestamp("2026-10-30")
    assert forward.targets_at(fred, t) == forward.targets_at(joined, t)
    assert {v["target"] for v in forward.targets_at(fred, t).values()} == {DURATION_LEG}
    assert {v["target"] for v in forward.targets_at(_fred("2026-10-30", inverted=True), t).values()} == {CASH_LEG}


def test_close_is_16_new_york_under_edt_and_est():
    assert forward.close_utc("2026-10-30") == pd.Timestamp("2026-10-30 20:00", tz="UTC")
    assert forward.close_utc("2026-11-02") == pd.Timestamp("2026-11-02 21:00", tz="UTC")


def test_execution_slips_up_to_three_nyse_days_then_none():
    t = pd.Timestamp("2026-10-30")
    assert forward.execution_for(t, "2026-10-30T21:15:00Z")[:2] == (pd.Timestamp("2026-11-02"), 0)
    assert forward.execution_for(t, "2026-11-02T21:01:00Z")[:2] == (pd.Timestamp("2026-11-03"), 1)
    assert forward.execution_for(t, "2026-11-04T20:59:00Z")[:2] == (pd.Timestamp("2026-11-04"), 2)
    assert forward.execution_for(t, "2026-11-04T21:00:00Z")[0] is None


def test_refusal_gates():
    assert "before the first forward month" in forward.refusal("2026-09", "2026-10-30T22:00:00Z")
    assert "H.15" in forward.refusal("2026-10", "2026-10-30T21:14:00Z")
    assert forward.refusal("2026-10", "2026-10-30T21:15:00Z") is None


def test_decision_record_waits_then_ok_then_unavailable():
    early = _fred("2026-10-29")
    assert forward.decision_record(early, "2026-10", START, 0, "2026-10-30T21:20:00Z") is None
    ok = forward.decision_record(_fred("2026-10-30", inverted=True), "2026-10", START, 0, "2026-10-31T09:00:00Z")
    assert ok["status"] == "ok" and ok["execution_date"] == "2026-11-02" and ok["days_slipped"] == 0
    assert ok["holding_after"] == {"T1": CASH_LEG, "T2": CASH_LEG, "T3": CASH_LEG}
    assert all(ok["switch"].values()) and ok["paper_order"] is False and "scoring" not in ok
    late = forward.decision_record(early, "2026-10", START, 0, "2026-11-05T09:00:00Z")
    assert late["status"] == "signal unavailable" and late["holding_after"] == START


def test_t3_undefined_holds_its_position():
    fred = _fred("2026-10-30", inverted=True)
    fred["DGS7"].loc["2026-10-30"] = np.nan  # an empty row on t (a row not yet posted waits: test above)
    record = forward.decision_record(fred, "2026-10", START, 0, "2026-10-31T09:00:00Z")
    assert record["targets"]["T3"]["target"] is None and record["holding_after"]["T3"] == "IEF"
    assert record["switch"]["T3"] is False


def test_scoring_date_written_in_the_record_that_ends_the_block():
    record = forward.decision_record(_fred("2026-10-30"), "2026-10", START, 60, "2026-10-31T09:00:00Z")
    assert record["scoring"] == {"block": 1, "periods": 60, "scoring_date": "2026-11-02",
                                 "rule": record["scoring"]["rule"]}


def test_records_never_rewritten(tmp_path):
    record = forward.decision_record(_fred("2026-10-30"), "2026-10", START, 0, "2026-10-31T09:00:00Z")
    forward.write_record(record, tmp_path)
    with pytest.raises(FileExistsError):
        forward.write_record(record, tmp_path)
    assert forward.load_records(tmp_path)[0]["signal_month"] == "2026-10"


def _ok(month: str, execution: str, held: dict) -> dict:
    return {"status": "ok", "signal_month": month, "signal_date": f"{month}-28", "execution_date": execution,
            "holding_after": held}


def test_shadow_line_equals_the_frozen_engine(tmp_path):
    days = pd.bdate_range("2026-10-01", "2027-03-31")
    rng = np.random.default_rng(6)
    indices = {DURATION_LEG: pd.Series(np.cumprod(1 + rng.normal(0, 0.004, len(days))), index=days),
               CASH_LEG: pd.Series(np.cumprod(np.full(len(days), 1.0002)), index=days)}
    holds = [{"T1": "BIL", "T2": "IEF", "T3": "IEF"}, {"T1": "IEF", "T2": "IEF", "T3": "BIL"},
             {"T1": "IEF", "T2": "BIL", "T3": "BIL"}, {"T1": "BIL", "T2": "BIL", "T3": "BIL"}]
    execs = ["2026-11-02", "2026-12-01", "2027-01-04", "2027-02-01"]
    records = [_ok(f"2026-{10 + i:02d}" if i < 3 else "2027-01", e, h) for i, (e, h) in enumerate(zip(execs, holds))]
    path = tmp_path / "shadow.csv"
    for k in range(2, len(records) + 1):
        line = forward.shadow_line(indices, records[:k], forward.read_shadow(path), START, 0.87, now_utc="x")
        forward.append_shadow(line, path)
    shadow = forward.read_shadow(path)
    assert len(shadow) == 3
    returns = pd.DataFrame({DURATION_LEG: shadow["r_IEF"], CASH_LEG: shadow["r_BIL"]})
    for trial in forward.TRIALS:
        targets = pd.Series([r["holding_after"][trial] for r in records[:-1]], index=returns.index)
        expected = backtest.run_switching(targets, returns, 2e-4, initial_holding="IEF")["r"]
        assert np.allclose(shadow[trial], expected, rtol=0, atol=1e-15)
    b3 = backtest.run_static(0.87, returns, 2e-4)["r"]
    assert np.allclose(shadow["B3"], b3, atol=1e-15) and shadow["B3"].iloc[0] == pytest.approx(
        0.87 * shadow["r_IEF"].iloc[0] + 0.13 * shadow["r_BIL"].iloc[0], abs=1e-15)
    assert np.allclose(shadow["d"], shadow["T1"] - shadow["B3"], atol=1e-15)
    assert shadow["T1_switched"].tolist() == [True, True, False]
    r0 = indices[DURATION_LEG].loc["2026-12-01"] / indices[DURATION_LEG].loc["2026-11-02"] - 1
    assert shadow["r_IEF"].iloc[0] == pytest.approx(r0, abs=1e-15)


def test_shadow_refuses_duplicates_and_gaps(tmp_path):
    path = tmp_path / "shadow.csv"
    line = {c: 0.0 for c in forward.SHADOW_COLUMNS}
    line.update(execution_date="2026-11-02", period_end="2026-12-01")
    forward.append_shadow(line, path)
    with pytest.raises(FileExistsError):
        forward.append_shadow(line, path)
    with pytest.raises(ValueError):
        forward.append_shadow({**line, "execution_date": "2027-01-04", "period_end": "2027-02-01"}, path)


def test_interim_has_no_statistic():
    shadow = pd.DataFrame({c: [0.01, -0.01] for c in forward.STRATEGIES} | {"d": [0.001, 0.002],
                          "T1_switched": [True, False]})
    out = forward.interim(shadow, "now")
    assert out["heading"] == "Not yet scored" and out["periods_to_scoring"] == 58 and out["T1_switches"] == 1
    assert "verdict" not in out and "t" not in out


def test_forward_verdict_rows():
    rng = np.random.default_rng(1)
    mixed = pd.Series(["IEF", "BIL"] * 30)
    assert forward.forward_verdict(pd.Series(rng.normal(0, 0.01, 60)), pd.Series(["IEF"] * 60), 0)["verdict"] \
        == forward.VERDICT_NOT_TESTABLE
    up = forward.forward_verdict(pd.Series(0.01 + rng.normal(0, 0.002, 60)), mixed, 10)
    assert up["verdict"] == forward.VERDICT_SUPPORTED and up["labels"] == []
    down = forward.forward_verdict(pd.Series(-0.01 + rng.normal(0, 0.002, 60)), mixed, 3)
    assert down["verdict"] == forward.VERDICT_REFUTED and down["labels"] == ["low-powered"]
    assert forward.forward_verdict(pd.Series(rng.normal(0, 0.01, 60) * 0 + np.r_[[0.01, -0.01] * 30]), mixed,
                                   9)["verdict"] == forward.VERDICT_INCONCLUSIVE


def test_score_refuses_early_and_without_a_scoring_date():
    shadow = pd.DataFrame({"d": [0.0] * 60, "T1_holding": ["IEF"] * 60, "T1_switched": [False] * 60})
    with pytest.raises(RuntimeError):
        forward.score(shadow.iloc[:59], [])
    records = [{"status": "ok"} for _ in range(61)]
    with pytest.raises(RuntimeError):
        forward.score(shadow, records)
    records[60]["scoring"] = {"block": 1, "scoring_date": "2031-11-03"}
    out = forward.score(shadow, records)
    assert out["verdict"] == forward.VERDICT_NOT_TESTABLE and out["scoring_date"] == "2031-11-03"


def test_dry_run_without_inputs_refuses_and_writes_nothing(tmp_path, monkeypatch):
    """Found by the 2026-10-31 pre-flight: a missing forward input was a traceback, not a refusal
    (Study 008 had refused cleanly since its code review of 2026-10-25; 006 and 007 were never back-ported)."""
    for name in ("DECISIONS_DIR", "FORWARD_RAW_DIR", "SHADOW_CSV", "WAITS_CSV", "INTERIM_JSON", "FORWARD_MANIFEST"):
        monkeypatch.setattr(forward, name, tmp_path / name)
    monkeypatch.setattr(forward, "utc_now", lambda: "2026-10-31T09:00:00Z")
    assert forward.main(["decide", "--signal-month", "2026-10", "--fetch", "--dry-run"]) == 1
    assert forward.main(["decide", "--signal-month", "2026-10", "--dry-run"]) == 1
    assert list(tmp_path.iterdir()) == []


def test_missing_frozen_input_refuses(tmp_path, monkeypatch, capsys):
    """The starting holdings come from the study's data/raw/ (git-ignored); a fresh checkout refuses, never crashes."""
    for name in ("DECISIONS_DIR", "FORWARD_RAW_DIR", "SHADOW_CSV", "WAITS_CSV", "INTERIM_JSON", "FORWARD_MANIFEST"):
        monkeypatch.setattr(forward, name, tmp_path / name)
    monkeypatch.setattr(forward, "RAW_DIR", tmp_path / "no-such-raw")
    monkeypatch.setattr(forward, "utc_now", lambda: "2026-10-31T09:00:00Z")
    assert forward.main(["decide", "--signal-month", "2026-10", "--dry-run"]) == 1
    assert "refused: a frozen input is not in data/raw/" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []
