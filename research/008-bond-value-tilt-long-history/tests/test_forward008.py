"""Study 008 forward record (§11): the CPI reading on t (in the file, not yet
in the file, never published, k - 12 never published), the rank history (the
episode's real yields to 2026-09, then one per forward month, earlier months
from their own records), holds, records, the shadow line through the hold
engine and the benchmarks, interim and scoring.  Constructed data, plus one
check against the episode's committed starting weights when the study's raw
files are present."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from src import backtest, tilt
from src import forward008 as fw
from src.carry_rank import expanding_rank
from src.config import CASH_LEG, DURATION_LEG, RAW_DIR, STUDY_DIR
from src.config008 import TRIAL_IDS
from src.real_yield import trailing_rank

START = {"T1": 0.5241, "T1a": 0.654, "T1b": 0.9916}
HEAD, CORE = "CPIAUCNS", "CPILFENS"


def _fred(end: str = "2026-10-30", seed: int = 7) -> dict[str, pd.Series]:
    days = pd.bdate_range("2026-01-02", end)
    rng = np.random.default_rng(seed)
    ten = pd.Series(4.2 + np.cumsum(rng.normal(0, 0.03, len(days))), index=days)
    return {"DGS10": ten, "DTB3": ten - 0.4, "DGS7": ten - 0.15}


def _bars(end: str = "2026-10-30") -> dict[str, pd.Series]:
    days = pd.bdate_range("2026-09-01", end)
    return {DURATION_LEG: pd.Series(100 * np.cumprod(np.full(len(days), 1.0003)), index=days),
            CASH_LEG: pd.Series(90 * np.cumprod(np.full(len(days), 1.00015)), index=days)}


def _cpi(last: str = "2026-09", gap: str | None = "2025-10", trailing_empty: int = 0) -> dict[str, pd.Series]:
    """A FRED monthly file to ``last`` (first-of-month dates), the October
    2025 row empty, optionally empty rows after ``last``."""
    months = pd.period_range("2023-01", pd.Period(last, "M") + trailing_empty, freq="M")
    out = {}
    for name, step in ((HEAD, 0.0025), (CORE, 0.0022)):
        v = pd.Series(300.0 * (1 + step) ** np.arange(len(months)), index=months.to_timestamp(), name=name)
        if gap:
            v.loc[pd.Period(gap, "M").to_timestamp()] = np.nan
        if trailing_empty:
            v.iloc[-trailing_empty:] = np.nan
        out[name] = v
    return out


def _episode_r(n: int = 686, seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    months = pd.period_range(end="2026-09", periods=n, freq="M")
    return pd.DataFrame({HEAD: rng.normal(0.02, 0.025, n), CORE: rng.normal(0.025, 0.02, n)}, index=months)


EP = _episode_r()
T = pd.Timestamp("2026-10-30")


def test_cpi_reading_in_file_not_yet_and_never_published():
    cpi = _cpi()[HEAD]
    r = fw.cpi_reading(cpi, "2026-10")
    assert (r["k"], r["k_minus_12"], r["status_k"], r["status_k_minus_12"]) == ("2026-09", "2025-09", fw.IN_FILE, fw.IN_FILE)
    assert r["pi"] == pytest.approx(1.0025 ** 12 - 1, abs=1e-14)
    late = fw.cpi_reading(_cpi(last="2026-08")[HEAD], "2026-10")  # September not yet in the file on t
    assert late["status_m_minus_1"] == fw.NOT_YET and late["k"] == "2026-08" and late["pi"] is not None
    blank_tail = fw.cpi_reading(_cpi(last="2026-08", trailing_empty=1)[HEAD], "2026-10")  # an empty row after the last value
    assert blank_tail["status_m_minus_1"] == fw.NOT_YET and blank_tail["k"] == "2026-08"
    never = fw.cpi_reading(_cpi(gap="2026-09", last="2026-10")[HEAD], "2026-10")  # m - 1 empty before the last value
    assert never["status_m_minus_1"] == fw.NEVER and never["pi"] is None
    nov = fw.cpi_reading(_cpi(last="2026-10")[HEAD], "2026-11")  # k - 12 = 2025-10, never published
    assert (nov["k"], nov["k_minus_12"], nov["status_k_minus_12"], nov["pi"]) == ("2026-10", "2025-10", fw.NEVER, None)
    # the index of month m itself is never used, even if a file held it
    assert fw.cpi_reading(_cpi(last="2026-10")[HEAD], "2026-10")["k"] == "2026-09"


def test_weights_match_the_direct_rank_on_episode_then_forward_real_yields():
    fred, cpi = _fred(), _cpi()
    w = fw.weights_at(EP, fred, cpi, T, "2026-10")
    y = float(fred["DGS10"].loc[T]) / 100.0
    for k, s, step in (("T1", HEAD, 0.0025), ("T1a", CORE, 0.0022), ("T1b", HEAD, 0.0025)):
        r = y - ((1 + step) ** 12 - 1)
        assert w["real_yield"][s] == pytest.approx(r, abs=1e-15)
        hist = pd.concat([EP[s], pd.Series([w["real_yield"][s]], index=pd.PeriodIndex(["2026-10"], freq="M"))])
        direct = expanding_rank(hist, 60).iloc[-1] if k != "T1b" else trailing_rank(hist, 120).iloc[-1]
        assert w["weights"][k] == round(float(direct), 4)
        assert w["n"][s] == 687
    assert w["cpi"][HEAD]["k"] == "2026-09" and w["cpi"][CORE]["k_minus_12"] == "2025-09"


def test_signal_month_2026_11_holds_on_the_october_2025_gap_and_is_left_out_after():
    fred, bars = _fred("2026-12-31"), _bars("2026-12-31")
    nov = fw.weights_at(EP, fred, _cpi(last="2026-10"), pd.Timestamp("2026-11-30"), "2026-11")
    assert nov["weights"] == {k: None for k in TRIAL_IDS}
    assert all("2025-10" in n and "never published" in n for n in nov["notes"] if n.startswith("T1"))
    dec = fw.weights_at(EP, fred, _cpi(last="2026-11"), pd.Timestamp("2026-12-31"), "2026-12")
    assert all(v is not None for v in dec["weights"].values())
    assert dec["forward_real_yields"][HEAD]["2026-11"] is None and dec["n"][HEAD] == 686 + 2
    assert fw.signal_status(fred, bars, "2026-11")[0] == "final"


def test_earlier_forward_months_come_from_their_own_records():
    oct_ok = {"status": "ok", "signal_month": "2026-10", "real_yield": {HEAD: 0.5, CORE: 0.5}}  # an extreme value
    fred, cpi = _fred("2026-12-31"), _cpi(last="2026-11")
    t_dec = pd.Timestamp("2026-12-31")
    from_record = fw.weights_at(EP, fred, cpi, t_dec, "2026-12", [oct_ok])
    recomputed = fw.weights_at(EP, fred, cpi, t_dec, "2026-12", [])
    assert from_record["forward_real_yields"][HEAD]["2026-10"] == 0.5
    assert recomputed["forward_real_yields"][HEAD]["2026-10"] == pytest.approx(
        float(fred["DGS10"].loc["2026-10-30"]) / 100.0 - (1.0025 ** 12 - 1), abs=1e-15)
    assert any("2026-10: no ok record" in n for n in recomputed["notes"])
    assert not any("2026-10: no ok record" in n for n in from_record["notes"])
    # the recorded 0.5 sits in the history: December's T1 is the direct rank over it
    r_dec = from_record["real_yield"][HEAD]
    hist = pd.concat([EP[HEAD], pd.Series([0.5, r_dec], index=pd.PeriodIndex(["2026-10", "2026-12"], freq="M"))])
    assert from_record["weights"]["T1"] == round(float(expanding_rank(hist, 60).iloc[-1]), 4)


def test_no_look_ahead_in_fred_or_cpi():
    base = fw.weights_at(EP, _fred(), _cpi(), T, "2026-10")
    later = {k: pd.concat([v, pd.Series(0.1, index=pd.bdate_range("2026-11-02", "2026-12-31"))]) for k, v in _fred().items()}
    assert fw.weights_at(EP, later, _cpi(), T, "2026-10") == base
    # a file that already held October's index (published after the deadline) changes nothing
    # (only the descriptive last_month_in_file differs)
    held = fw.weights_at(EP, _fred(), _cpi(last="2026-10"), T, "2026-10")
    assert (held["weights"], held["real_yield"], held["n"]) == (base["weights"], base["real_yield"], base["n"])
    assert held["cpi"][HEAD]["last_month_in_file"] == "2026-10"


def test_decision_record_waits_then_ok_then_unavailable():
    early = _fred("2026-10-29")
    assert fw.decision_record(EP, early, _cpi(), _bars(), "2026-10", START, START, [], "2026-10-30T21:20:00Z") is None
    ok = fw.decision_record(EP, _fred(), _cpi(), _bars(), "2026-10", START, START, [], "2026-10-31T09:00:00Z")
    assert ok["status"] == "ok" and ok["execution_date"] == "2026-11-02" and ok["paper_order"] is False
    assert ok["starting_weights"]["signal_month"] == "2026-09" and ok["starting_weights"]["T1"] == 0.5241
    assert set(ok["weights_after"]) == set(TRIAL_IDS) and "scoring" not in ok
    assert set(ok["inputs_on_signal_date"]) == {"DGS10", "DTB3", "DGS7"}
    for s in (HEAD, CORE):
        assert {"k", "k_minus_12", "status_k", "status_k_minus_12", "pi"} <= set(ok["cpi"][s])
        assert isinstance(ok["real_yield"][s], float) and ok["rank_history_n"][s] == 687
    late = fw.decision_record(EP, early, _cpi(), _bars(), "2026-10", START, START, [], "2026-11-05T09:00:00Z")
    assert late["status"] == "signal unavailable" and late["weights_after"] == START
    sixty = [{"status": "ok", "signal_month": f"x{i}"} for i in range(60)]
    later = fw.decision_record(EP, _fred(), _cpi(), _bars(), "2026-10", START, START, sixty, "2026-10-31T09:00:00Z")
    assert "starting_weights" not in later and later["scoring"]["block"] == 1


def test_records_never_rewritten(tmp_path):
    record = fw.decision_record(EP, _fred(), _cpi(), _bars(), "2026-10", START, START, [], "2026-10-31T09:00:00Z")
    fw.write_record(record, tmp_path)
    with pytest.raises(FileExistsError):
        fw.write_record(record, tmp_path)


def _ok(month: str, execution: str, w: dict) -> dict:
    return {"status": "ok", "signal_month": month, "signal_date": f"{month}-28", "execution_date": execution,
            "weights_after": w}


def test_shadow_line_equals_the_engine_and_benchmarks(tmp_path):
    days = pd.bdate_range("2026-10-01", "2027-03-31")
    rng = np.random.default_rng(6)
    indices = {DURATION_LEG: pd.Series(np.cumprod(1 + rng.normal(0, 0.004, len(days))), index=days),
               CASH_LEG: pd.Series(np.cumprod(np.full(len(days), 1.0002)), index=days)}
    ws = [dict(zip(TRIAL_IDS, v)) for v in ([0.7, 0.8, 0.6], [None, None, None], [0.5, 0.5, 0.5], [0.9, 0.9, 0.9])]
    execs = ["2026-11-02", "2026-12-01", "2027-01-04", "2027-02-01"]
    months = ["2026-10", "2026-11", "2026-12", "2027-01"]
    records = [_ok(m, e, w) for m, e, w in zip(months, execs, ws)]
    frozen = {"T1": 0.4662, "T1a": 0.4483, "T1b": 0.4008}
    path = tmp_path / "shadow.csv"
    for k in range(2, len(records) + 1):
        fw.append_shadow(fw.shadow_line(indices, records[:k], fw.read_shadow(path), START, frozen, now_utc="x"), path)
    shadow = fw.read_shadow(path)
    assert len(shadow) == 3
    returns = pd.DataFrame({DURATION_LEG: shadow["r_IEF"], CASH_LEG: shadow["r_BIL"]})
    r_ief = returns[DURATION_LEG].to_numpy()
    for k in TRIAL_IDS:
        path_w = [r["weights_after"][k] for r in records[:-1]]
        gross0 = path_w[0] * r_ief[0] + (1 - path_w[0]) * returns[CASH_LEG].iloc[0]
        path_w[1] = path_w[0] * (1 + r_ief[0]) / (1 + gross0)  # the 2026-11 hold: drifted, by hand
        expected = tilt.run_tilt(pd.Series(path_w, index=returns.index), returns, 2e-4, START[k])
        np.testing.assert_allclose(shadow[k], expected["r"], rtol=0, atol=1e-15)
        np.testing.assert_allclose(shadow[f"B3_{k}"], backtest.run_static(frozen[k], returns, 2e-4)["r"], rtol=0, atol=1e-15)
        assert shadow[f"traded_{k}"].iloc[1] == 0.0
    np.testing.assert_allclose(shadow["B1"], backtest.run_static(1.0, returns, 0.0)["r"], rtol=0, atol=1e-15)
    np.testing.assert_allclose(shadow["B2"], backtest.run_static(0.5, returns, 2e-4)["r"], rtol=0, atol=1e-15)
    assert shadow["traded_T1"].iloc[0] == pytest.approx(0.7 - 0.5241, abs=1e-12)
    np.testing.assert_allclose(shadow["d"], shadow["T1"] - shadow["B3_T1"], rtol=0, atol=1e-15)
    with pytest.raises(FileExistsError):
        fw.append_shadow(shadow.iloc[0].to_dict() | {"execution_date": str(shadow["execution_date"].iloc[0])}, path)
    with pytest.raises(ValueError):
        fw.shadow_line(indices, records[:3], fw.read_shadow(path), START, frozen)
    with pytest.raises(ValueError):
        fw.append_shadow(shadow.iloc[0].to_dict() | {"execution_date": "2027-03-01"}, path)


def test_interim_has_no_statistic_and_scoring_refuses_early():
    shadow = pd.DataFrame({c: [0.01, 0.02] for c in fw.SHADOW_COLUMNS})
    out = fw.interim(shadow, "x")
    assert out["heading"] == "Not yet scored" and out["periods_to_scoring"] == 58 and "t" not in out
    assert set(out["cumulative"]) == {"B1", "B2", "B3_T1", "B3_T1a", "B3_T1b", "T1", "T1a", "T1b"}
    with pytest.raises(RuntimeError):
        fw.score(shadow, [])
    full = pd.DataFrame({c: [0.01] * 60 for c in fw.SHADOW_COLUMNS})
    ok = [{"status": "ok", "weights_after": {"T1": 0.5}} for _ in range(61)]
    with pytest.raises(RuntimeError):  # the 61st record carries no scoring date
        fw.score(full, ok)


def test_forward_verdict_rows():
    rng = np.random.default_rng(1)
    flat = fw.forward_verdict(pd.Series(rng.normal(0, 0.01, 60)), pd.Series([0.5] * 60), 0.0)
    assert flat["verdict"] == "not testable" and flat["labels"] == ["low-powered"]
    up = fw.forward_verdict(pd.Series(0.004 + rng.normal(0, 0.002, 60)), pd.Series(rng.uniform(0, 1, 60)), 12.0)
    assert up["verdict"] == "supported (forward)" and up["labels"] == []
    down = fw.forward_verdict(pd.Series(-0.004 + rng.normal(0, 0.002, 60)), pd.Series(rng.uniform(0, 1, 60)), 12.0)
    assert down["verdict"] == "refuted (forward)"
    held = fw.forward_verdict(pd.Series(rng.normal(0, 0.01, 60)), pd.Series([None] * 60, dtype=float), 0.0)
    assert held["verdict"] == "not testable"


def test_main_refuses_and_writes_nothing(tmp_path, monkeypatch):
    for name in ("DECISIONS_DIR", "FORWARD_RAW_DIR", "SHADOW_CSV", "WAITS_CSV", "INTERIM_JSON", "FORWARD_MANIFEST"):
        monkeypatch.setattr(fw, name, tmp_path / name)
    monkeypatch.setattr(fw, "utc_now", lambda: "2026-10-25T14:00:00Z")
    assert fw.main(["decide", "--signal-month", "2026-10", "--fetch"]) == 1
    assert fw.main(["decide", "--signal-month", "2026-09"]) == 1
    assert fw.main(["shadow", "--signal-month", "2026-10"]) == 1
    assert fw.main(["interim", "--dry-run"]) == 0
    assert list(tmp_path.iterdir()) == []


def test_label_carries_the_committed_history_verdict():
    summary = json.loads((STUDY_DIR / "results" / "history" / "summary.json").read_text())
    assert fw.HISTORY_VERDICT == summary["verdict"]["T1"] == "not supported"
    assert fw.LABEL.endswith("history verdict: not supported")


@pytest.mark.skipif(not (RAW_DIR / "fred_CPIAUCNS.csv").exists(), reason="study raw files not present")
def test_rank_history_reproduces_the_episode_starting_weights():
    """The rank history the forward record extends is the episode's: 686
    defined real yields per series to 2026-09, r and the three weights there
    exactly as results/episode/summary.json wrote them."""
    episode_r = fw.load_episode_real_yields()
    start = json.loads((STUDY_DIR / "results" / "episode" / "summary.json").read_text())[
        "weights_at_last_signal_month_for_forward_record"]
    assert fw.starting_weights() == {k: start[k] for k in TRIAL_IDS} == START
    for s in (HEAD, CORE):
        assert int(episode_r[s].notna().sum()) == start[f"n_defined_{s}"] == 686
        assert float(episode_r[s].iloc[-1]) == start[f"r_{s}"]
    assert round(float(expanding_rank(episode_r[HEAD].dropna(), 60).iloc[-1]), 4) == START["T1"]
    assert round(float(expanding_rank(episode_r[CORE].dropna(), 60).iloc[-1]), 4) == START["T1a"]
    assert round(float(trailing_rank(episode_r[HEAD].dropna(), 120).iloc[-1]), 4) == START["T1b"]
