"""Study 007 forward record (§11): finality on all three FRED series and the
ETF bars, the rank history (frozen to 2026-09, then forward), the trend on ETF
closes, holds, records, the shadow line through ``tilt.run_tilt`` and the
benchmarks, interim and scoring.  Constructed data, plus one check against the
episode's committed starting weights when the study's raw files are present."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from src import backtest, tilt
from src import forward007 as fw
from src.calendar import build_schedule
from src.carry_rank import carry_at_signal_dates, expanding_rank
from src.config import CASH_LEG, DURATION_LEG, RAW_DIR, STUDY_DIR
from src.config007 import CARRY_FIRST_SIGNAL_MONTH, TRIAL_IDS

START = {"T1": 0.4111, "T1a": 0.4111, "T1b": 0.4111, "T2": 0.2055, "T3": 0.0}


def _fred(start: str, end: str, seed: int = 7) -> dict[str, pd.Series]:
    """Weekday rows; a wandering 10-year yield, a bill below it, DGS7 under DGS10."""
    days = pd.bdate_range(start, end)
    rng = np.random.default_rng(seed)
    ten = pd.Series(6.0 + np.cumsum(rng.normal(0, 0.03, len(days))), index=days)
    return {"DGS10": ten, "DTB3": ten - 1.0 + 0.3 * np.sin(np.arange(len(days)) / 300), "DGS7": ten - 0.15}


FROZEN = _fred("1969-07-01", "2026-10-19")


def _forward(end: str = "2026-10-30", shift: float = 0.0) -> dict[str, pd.Series]:
    """The 'fetched' files: the frozen ones up to 2026-09, then new rows."""
    new = _fred("2026-10-01", end, seed=11)
    return {k: pd.concat([FROZEN[k].loc[:"2026-09-30"] + shift, new[k] - new[k].iloc[0] + FROZEN[k].loc[:"2026-09-30"].iloc[-1]])
            for k in FROZEN}


def _bars(end: str = "2026-10-30", ief_drift: float = 0.0003) -> dict[str, pd.Series]:
    days = pd.bdate_range("2025-01-02", end)
    return {DURATION_LEG: pd.Series(100 * np.cumprod(np.full(len(days), 1 + ief_drift)), index=days),
            CASH_LEG: pd.Series(90 * np.cumprod(np.full(len(days), 1.00015)), index=days)}


def _direct_carry(fred: dict, month: str) -> pd.Series:
    old = build_schedule(FROZEN["DGS10"], FROZEN["DTB3"], CARRY_FIRST_SIGNAL_MONTH, "2026-09")["signal_date"]
    oc = carry_at_signal_dates(FROZEN["DGS10"], FROZEN["DGS7"], FROZEN["DTB3"], old)
    new = build_schedule(fred["DGS10"], fred["DTB3"], "2026-10", month)["signal_date"]
    return pd.concat([oc, carry_at_signal_dates(fred["DGS10"], fred["DGS7"], fred["DTB3"], new)])


def test_finality_needs_all_three_fred_series_and_the_bars():
    fred = _forward()
    fred["DGS10"].loc["2026-10-30"] = np.nan  # an empty row on the last weekday: t = 10-29
    fred["DGS7"] = fred["DGS7"].loc[:"2026-10-29"]  # DGS7 has no 10-30 row yet
    state, t, why = fw.signal_status(fred, _bars(), "2026-10")
    assert state == "wait" and t == pd.Timestamp("2026-10-29") and "DGS7" in why
    state, _, why = fw.signal_status(_forward(), _bars("2026-10-29"), "2026-10")
    assert state == "wait" and "IEF bar" in why
    assert fw.signal_status(_forward(), _bars(), "2026-10")[0] == "final"


def test_weights_match_the_direct_rank_on_frozen_then_forward_carries():
    t = pd.Timestamp("2026-10-30")
    w = fw.weights_at(FROZEN, _forward(), _bars(), t, "2026-10")
    carry = _direct_carry(_forward(), "2026-10")
    assert w["n"] == len(carry) and w["carry"] == pytest.approx(float(carry.iloc[-1]), abs=0)
    for k, m in {"T1": 60, "T1a": 36, "T1b": 120}.items():
        assert w["weights"][k] == round(float(expanding_rank(carry, m).iloc[-1]), 4)
    assert w["trend"] == 1 and w["weights"]["T3"] == 1.0
    assert w["weights"]["T2"] == round(0.5 * w["weights"]["T1"] + 0.5, 4)


def test_months_to_2026_09_come_from_the_frozen_files_not_the_fetch():
    t = pd.Timestamp("2026-10-30")
    revised = _forward(shift=0.5)  # a fetch that disagrees with the frozen files before 2026-10
    revised = {k: pd.concat([revised[k].loc[:"2026-09-30"], _forward()[k].loc["2026-10-01":]]) for k in revised}
    assert fw.weights_at(FROZEN, revised, _bars(), t, "2026-10") == fw.weights_at(FROZEN, _forward(), _bars(), t, "2026-10")


def test_no_look_ahead_in_fred_or_bars():
    t = pd.Timestamp("2026-10-30")
    base = fw.weights_at(FROZEN, _forward(), _bars(), t, "2026-10")
    later_fred = {k: pd.concat([v, pd.Series(0.1, index=pd.bdate_range("2026-11-02", "2026-12-31"))])
                  for k, v in _forward().items()}
    later_bars = {k: pd.concat([v, pd.Series(1.0, index=pd.bdate_range("2026-11-02", "2026-12-31"))])
                  for k, v in _bars().items()}
    assert fw.weights_at(FROZEN, later_fred, later_bars, t, "2026-10") == base


def test_trend_reads_the_etf_closes_twelve_signal_dates_back():
    t = pd.Timestamp("2026-10-30")
    assert fw.weights_at(FROZEN, _forward(), _bars(ief_drift=0.0), t, "2026-10")["trend"] == 0
    assert fw.weights_at(FROZEN, _forward(), _bars(ief_drift=0.0), t, "2026-10")["weights"]["T3"] == 0.0


def test_dgs7_missing_on_t_holds_the_carry_trials():
    fred = _forward()
    fred["DGS7"].loc["2026-10-30"] = np.nan
    w = fw.weights_at(FROZEN, fred, _bars(), pd.Timestamp("2026-10-30"), "2026-10")
    assert [w["weights"][k] for k in ("T1", "T1a", "T1b", "T2")] == [None] * 4
    assert w["weights"]["T3"] == 1.0 and "DGS7" in w["notes"][0]


def test_decision_record_waits_then_ok_then_unavailable():
    early = _forward("2026-10-29")
    assert fw.decision_record(FROZEN, early, _bars(), "2026-10", START, START, 0, "2026-10-30T21:20:00Z") is None
    ok = fw.decision_record(FROZEN, _forward(), _bars(), "2026-10", START, START, 0, "2026-10-31T09:00:00Z")
    assert ok["status"] == "ok" and ok["execution_date"] == "2026-11-02" and ok["paper_order"] is False
    assert ok["starting_weights"]["signal_month"] == "2026-09" and ok["starting_weights"]["T1"] == 0.4111
    assert set(ok["weights_after"]) == set(TRIAL_IDS) and "scoring" not in ok
    assert set(ok["inputs_on_signal_date"]) == {"DGS10", "DTB3", "DGS7"}
    late = fw.decision_record(FROZEN, early, _bars(), "2026-10", START, START, 0, "2026-11-05T09:00:00Z")
    assert late["status"] == "signal unavailable" and late["weights_after"] == START
    later = fw.decision_record(FROZEN, _forward(), _bars(), "2026-10", START, START, 60, "2026-10-31T09:00:00Z")
    assert "starting_weights" not in later and later["scoring"]["block"] == 1


def test_records_never_rewritten(tmp_path):
    record = fw.decision_record(FROZEN, _forward(), _bars(), "2026-10", START, START, 0, "2026-10-31T09:00:00Z")
    fw.write_record(record, tmp_path)
    with pytest.raises(FileExistsError):
        fw.write_record(record, tmp_path)


def _returns(n: int, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({DURATION_LEG: rng.normal(0.003, 0.02, n), CASH_LEG: np.full(n, 0.003)},
                        index=pd.Index([f"m{i}" for i in range(n)]))


def test_a_hold_trades_nothing_and_drifts():
    returns = _returns(4)
    res = fw.run_with_holds([0.6, None, 0.2, None], returns, 2e-4, 0.4)
    assert res["traded_fraction"].iloc[1] == 0.0 and res["traded_fraction"].iloc[3] == 0.0
    expected_w1 = 0.6 * (1 + returns[DURATION_LEG].iloc[0]) / (1 + res["r_gross"].iloc[0])
    assert res["weight"].iloc[1] == pytest.approx(expected_w1, abs=1e-15)
    plain = tilt.run_tilt(pd.Series([0.6, 0.3, 0.2, 0.9], index=returns.index), returns, 2e-4, 0.4)
    assert np.allclose(fw.run_with_holds([0.6, 0.3, 0.2, 0.9], returns, 2e-4, 0.4)["r"], plain["r"], atol=0)


def _ok(month: str, execution: str, w: dict) -> dict:
    return {"status": "ok", "signal_month": month, "signal_date": f"{month}-28", "execution_date": execution,
            "weights_after": w}


def test_shadow_line_equals_the_engine_and_benchmarks(tmp_path):
    days = pd.bdate_range("2026-10-01", "2027-03-31")
    rng = np.random.default_rng(6)
    indices = {DURATION_LEG: pd.Series(np.cumprod(1 + rng.normal(0, 0.004, len(days))), index=days),
               CASH_LEG: pd.Series(np.cumprod(np.full(len(days), 1.0002)), index=days)}
    ws = [dict(zip(TRIAL_IDS, v)) for v in ([0.7, 0.8, 0.6, 0.85, 1.0], [0.2, None, 0.3, 0.1, 0.0],
                                            [0.5, 0.5, 0.5, 0.75, 1.0], [0.9, 0.9, 0.9, 0.45, 0.0])]
    execs = ["2026-11-02", "2026-12-01", "2027-01-04", "2027-02-01"]
    months = ["2026-10", "2026-11", "2026-12", "2027-01"]
    records = [_ok(m, e, w) for m, e, w in zip(months, execs, ws)]
    frozen = {"T1": 0.6056, "T1a": 0.6056, "T1b": 0.6036, "T2": 0.609, "T3": 0.6124}
    path = tmp_path / "shadow.csv"
    for k in range(2, len(records) + 1):
        fw.append_shadow(fw.shadow_line(indices, records[:k], fw.read_shadow(path), START, frozen, now_utc="x"), path)
    shadow = fw.read_shadow(path)
    assert len(shadow) == 3
    returns = pd.DataFrame({DURATION_LEG: shadow["r_IEF"], CASH_LEG: shadow["r_BIL"]})
    for k in TRIAL_IDS:
        expected = fw.run_with_holds([r["weights_after"][k] for r in records[:-1]], returns, 2e-4, START[k])
        assert np.allclose(shadow[k], expected["r"], atol=1e-15)
        assert np.allclose(shadow[f"B3_{k}"], backtest.run_static(frozen[k], returns, 2e-4)["r"], atol=1e-15)
    assert shadow["traded_T1"].iloc[0] == pytest.approx(0.7 - 0.4111, abs=1e-12)
    assert shadow["traded_T1a"].iloc[1] == 0.0
    assert np.allclose(shadow["d"], shadow["T1"] - shadow["B3_T1"], atol=1e-15)
    with pytest.raises(FileExistsError):
        fw.append_shadow(shadow.iloc[0].to_dict() | {"execution_date": str(shadow["execution_date"].iloc[0])}, path)
    with pytest.raises(ValueError):
        fw.shadow_line(indices, records[:3], fw.read_shadow(path), START, frozen)


def test_interim_has_no_statistic_and_scoring_refuses_early():
    shadow = pd.DataFrame({c: [0.01, 0.02] for c in fw.SHADOW_COLUMNS})
    out = fw.interim(shadow, "x")
    assert out["heading"] == "Not yet scored" and out["periods_to_scoring"] == 58 and "t" not in out
    with pytest.raises(RuntimeError):
        fw.score(shadow, [])


def test_forward_verdict_rows():
    rng = np.random.default_rng(1)
    flat = fw.forward_verdict(pd.Series(rng.normal(0, 0.01, 60)), pd.Series([0.5] * 60), 0.0)
    assert flat["verdict"] == "not testable" and flat["labels"] == ["low-powered"]
    up = fw.forward_verdict(pd.Series(0.004 + rng.normal(0, 0.002, 60)), pd.Series(rng.uniform(0, 1, 60)), 12.0)
    assert up["verdict"] == "supported (forward)" and up["labels"] == []
    down = fw.forward_verdict(pd.Series(-0.004 + rng.normal(0, 0.002, 60)), pd.Series(rng.uniform(0, 1, 60)), 12.0)
    assert down["verdict"] == "refuted (forward)"


def test_starting_weights_are_the_episodes():
    assert fw.starting_weights() == START


@pytest.mark.skipif(not (RAW_DIR / "fred_DGS10.csv").exists(), reason="study raw files not present")
def test_frozen_rank_history_reproduces_the_episode_starting_weights():
    """The rank history the forward record extends is the episode's: 687
    carries to 2026-09 and T1's weight there 0.4111 (results/episode)."""
    from src.fred import load_series
    frozen = {k: load_series(k, RAW_DIR) for k in ("DGS10", "DTB3", "DGS7")}
    old = build_schedule(frozen["DGS10"], frozen["DTB3"], CARRY_FIRST_SIGNAL_MONTH, "2026-09")["signal_date"]
    carry = carry_at_signal_dates(frozen["DGS10"], frozen["DGS7"], frozen["DTB3"], old)
    episode = json.loads((STUDY_DIR / "results" / "episode" / "summary.json").read_text())
    start = episode["weights_at_last_signal_month_for_forward_record"]
    assert len(carry) == start["n"] == 687
    for k, m in {"T1": 60, "T1a": 36, "T1b": 120}.items():
        assert round(float(expanding_rank(carry, m).iloc[-1]), 4) == start[k]
