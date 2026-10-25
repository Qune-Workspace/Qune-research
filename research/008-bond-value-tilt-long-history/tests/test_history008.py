"""Study 008 history run (PREREGISTRATION.md §6.4, §8.1, §9.4-§9.6) on
constructed data only; no file in data/raw/ is read.  §13 tests (4) (the hold
period in the engine) and (8) (the era row and the verdict precedence on
constructed differentials), plus the toy run's structure.  Toy windows and
short minimum histories stand in for the registered ones, which ``main``
checks (534 / 474 / 396 periods)."""

import json

import numpy as np
import pandas as pd
import pytest
from src import backtest, history008, tilt
from src.calendar import build_schedule
from src.config import CASH_LEG, COST_CASES, DURATION_LEG
from src.config008 import FAMILY_COUNT_AT_REGISTRATION, TRIAL_IDS, VOL_BAR_008
from src.synthetic import synthetic_indices

from tests.toy import toy_yields

PASS = {"C1": True, "C2": True, "C3": True, "C4": True}
MEETS = {"T1a": "meets C1-C4", "T1b": "meets C1-C4"}
TOY_RANK_N = {"T1": 12, "T1a": 12, "T1b": 24}
TOY = dict(real_yield_first_month="2000-01", test_first_month="2001-01", t1b_first_month="2002-01",
           last_month="2005-10")
TOY_ERA = ("2003-01", "2005-10")


def _fail(key):
    return {**PASS, key: False}


def _toy_returns(n: int = 24, seed: int = 8) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.period_range("2001-01", periods=n, freq="M")
    return pd.DataFrame({DURATION_LEG: rng.normal(0.004, 0.02, n), CASH_LEG: rng.normal(0.002, 0.0005, n)}, index=idx)


# --- §13 test (4): the hold period in the engine --------------------------------------------------


def test_hold_wrapper_equals_the_copied_engine_without_a_hold():
    returns = _toy_returns()
    w = pd.Series(np.linspace(0.1, 0.9, len(returns)), index=returns.index)
    ours = history008.run_tilt_hold(w, returns, COST_CASES["base"])
    theirs = tilt.run_tilt(w, returns, COST_CASES["base"])
    pd.testing.assert_frame_equal(ours.drop(columns="hold"), theirs)
    assert not ours["hold"].any()


def test_hold_period_passes_the_drifted_weight_with_zero_trade():
    returns = _toy_returns()
    w = pd.Series(np.linspace(0.1, 0.9, len(returns)), index=returns.index)
    gaps = [5, 6, 17]  # two consecutive holds and one alone
    w_gap = w.copy()
    w_gap.iloc[gaps] = np.nan
    cost = COST_CASES["stress"]
    out = history008.run_tilt_hold(w_gap, returns, cost)
    assert out["hold"].iloc[gaps].all() and out["hold"].sum() == len(gaps)
    for i in gaps:
        assert out["traded_fraction"].iloc[i] == 0.0
        assert out["cost"].iloc[i] == 0.0
        assert out["weight"].iloc[i] == out["drifted_from"].iloc[i]
        prev = out.iloc[i - 1]
        drift = prev["weight"] * (1 + returns[DURATION_LEG].iloc[i - 1]) / (1 + prev["r_gross"])
        assert out["weight"].iloc[i] == pytest.approx(drift, abs=1e-15)
    # Every other period: the copied engine on the filled path, unchanged; the
    # period after a hold trades from the drifted hold weight.
    pd.testing.assert_frame_equal(out.drop(columns="hold"), tilt.run_tilt(out["weight"], returns, cost))
    assert out["traded_fraction"].iloc[7] == pytest.approx(abs(w.iloc[7] - out["drifted_from"].iloc[7]))


def test_hold_wrapper_refuses_a_first_period_without_weight_and_bad_weights():
    returns = _toy_returns()
    w = pd.Series(0.5, index=returns.index)
    w.iloc[0] = np.nan
    with pytest.raises(ValueError, match="no position to hold"):
        history008.run_tilt_hold(w, returns, 0.0)
    w.iloc[0] = 1.5
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        history008.run_tilt_hold(w, returns, 0.0)


def test_b3_mean_weight_leaves_hold_months_out():
    returns = _toy_returns(12)
    w = pd.Series([0.2] * 6 + [np.nan] + [0.8] * 5, index=returns.index)
    res = history008.run_trial(w, returns, COST_CASES["base"])
    assert tilt.mean_weight(w) == pytest.approx((0.2 * 6 + 0.8 * 5) / 11)
    pd.testing.assert_frame_equal(res["B3"], backtest.run_static(tilt.mean_weight(w), returns, COST_CASES["base"]))
    assert res["T"]["hold"].sum() == 1


# --- §13 test (8): era row and verdict precedence on constructed differentials --------------------


def test_era_row_sign_only_with_t_reported():
    idx = pd.period_range("1974-06", periods=40, freq="M")
    exec_dates = pd.Series(pd.DatetimeIndex([p.to_timestamp() + pd.offsets.BDay(1) for p in idx + 1]), index=idx)
    schedule = pd.DataFrame({"execution_date": exec_dates})
    mask = history008.era_months(schedule, idx, "1975-07", "1976-12")
    assert mask.sum() == 18
    d = pd.Series(np.where(mask, 1e-5, 0.05), index=idx)  # tiny positive inside the era, large outside
    row = history008.era_row(d, mask, expected_periods=18)
    assert row["pass"] and row["periods"] == 18
    assert row["mean_d_annual"] == pytest.approx(12e-5)
    assert "nw_t_reported_not_tested" in row
    neg = history008.era_row(pd.Series(np.where(mask, -1e-5, 0.05), index=idx), mask)
    assert not neg["pass"]  # the full-window mean is positive; only the era's sign decides
    with pytest.raises(ValueError, match="expected 17"):
        history008.era_row(d, mask, expected_periods=17)


def test_primary_verdict_precedence():
    v = history008.primary_verdict
    assert v(False, _fail("C1"), False, {"T1a": "not supported"}, 0.5) == "inconclusive (gate)"
    for key in PASS:
        assert v(True, _fail(key), False, {"T1a": "not supported", "T1b": "not supported"}, 0.5) == "not supported"
    assert v(True, PASS, False, {"T1a": "not supported", "T1b": "meets C1-C4"}, 0.5) == "inconclusive (one era)"
    assert v(True, PASS, True, {"T1a": "not supported", "T1b": "meets C1-C4"}, 0.5) == "inconclusive (fragile)"
    assert v(True, PASS, True, {"T1a": "meets C1-C4", "T1b": "not supported"}, 0.01) == "inconclusive (fragile)"
    # A companion dropped at the gate is not "not supported": the clause does not fire.
    assert v(True, PASS, True, {"T1a": "inconclusive (gate)", "T1b": "meets C1-C4"}, 0.01) == (
        "supported in history; forward record pending")
    assert v(True, PASS, True, MEETS, VOL_BAR_008 + 1e-9) == "consistent with an edge, not detectable at the 2% bar"
    assert v(True, PASS, True, MEETS, VOL_BAR_008) == "supported in history; forward record pending"


def test_companion_rows_have_no_era_row_and_no_clause():
    v = history008.companion_verdict
    assert v(False, PASS) == "inconclusive (gate)"
    assert v(True, PASS) == "meets C1-C4"
    for key in PASS:
        assert v(True, _fail(key)) == "not supported"


def test_criteria_known_answer():
    desc = {"T": {"sharpe_annual": 0.60}, "B1": {"sharpe_annual": 0.50}, "B3": {"sharpe_annual": 0.49}}
    infer = {"vs_B3": {"newey_west": {"t": 2.0, "mean": 1e-4}}}
    stress = {"vs_B3": {"newey_west": {"mean": 5e-5}}}
    assert history008.criteria(desc, infer, {"dsr": 0.95}, stress) == PASS
    c = history008.criteria({**desc, "B1": {"sharpe_annual": 0.51}}, infer, {"dsr": 0.9499}, {"vs_B3": {"newey_west": {"mean": -1e-6}}})
    assert c == {"C1": False, "C2": True, "C3": False, "C4": False}


def test_family_count_is_the_registered_seventeen():
    assert history008.family_count() == FAMILY_COUNT_AT_REGISTRATION == 17


def test_realised_power_and_mde():
    rng = np.random.default_rng(3)
    d = pd.Series(rng.normal(0.0005, 0.01, 240))
    w = pd.Series(rng.uniform(0, 1, 240))
    p = history008.realised_power(d, w)
    assert p["mde_annual_at_t2"] == pytest.approx(2.0 * p["nw_se"] * 12)
    assert p["mde_annual_at_80pct_power"] == pytest.approx(2.842 * p["nw_se"] * 12)
    assert p["sd_w_minus_wbar"] == pytest.approx(float(w.std(ddof=0)))
    assert p["assumed"] == 0.972


# --- the toy run ---------------------------------------------------------------------------------


def _toy_cpi_and_availability(fred):
    rng = np.random.default_rng(81)
    first = pd.date_range("1998-01-01", "2005-12-01", freq="MS")
    head = pd.Series(100.0 * np.exp(np.cumsum(rng.normal(0.002, 0.003, len(first)))), index=first, name="CPIAUCNS")
    core = pd.Series(100.0 * np.exp(np.cumsum(rng.normal(0.002, 0.002, len(first)))), index=first, name="CPILFENS")
    schedule = build_schedule(fred["DGS10"], fred["DTB3"], TOY["real_yield_first_month"], TOY["last_month"])
    months = schedule.index
    availability = pd.DataFrame(
        {
            "signal_month": [str(m) for m in months],
            "signal_date": schedule["signal_date"].dt.strftime("%Y-%m-%d").to_numpy(),
            "CPIAUCNS_m1_published_by_t": "1",
            "CPIAUCNS_k": [str(m - 1) for m in months],
            "CPIAUCNS_branch": "release_date_read",
            "CPILFENS_m1_published_by_t": "",
            "CPILFENS_k": [str(m - 1) for m in months],
            "CPILFENS_branch": "assumed_known",
        }
    )
    return {"CPIAUCNS": head, "CPILFENS": core}, availability


@pytest.fixture(scope="module")
def toy_history(tmp_path_factory):
    fred = toy_yields()
    cpi, availability = _toy_cpi_and_availability(fred)
    indices = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    sched = build_schedule(fred["DGS10"], fred["DTB3"], TOY["test_first_month"], TOY["last_month"])
    ret = backtest.instrument_returns(indices, sched)
    rng = np.random.default_rng(7)
    monthly_007 = pd.DataFrame({"T1": ret[DURATION_LEG] + rng.normal(0, 1e-3, len(ret)), "B3_T1": ret[CASH_LEG]},
                               index=ret.index)
    out = tmp_path_factory.mktemp("history") / "history"
    summary = history008.compute(fred, cpi, availability, sigma=0.05, out_dir=out, rank_n=TOY_RANK_N,
                                 era=TOY_ERA, monthly_007=monthly_007, **TOY)
    return fred, out, summary


def test_summary_structure_and_files(toy_history):
    _, out, s = toy_history
    assert set(s["cost_cases"]) == set(COST_CASES)
    assert s["holding_periods"]["T1b"] < s["holding_periods"]["T1"] == s["holding_periods"]["T1a"]
    assert set(s["verdict"]) == set(TRIAL_IDS) and set(s["criteria"]) == set(TRIAL_IDS)
    allowed = {"inconclusive (gate)", "not supported", "inconclusive (one era)", "inconclusive (fragile)",
               "consistent with an edge, not detectable at the 2% bar", "supported in history; forward record pending"}
    assert s["verdict"]["T1"] in allowed
    assert {s["verdict"][k] for k in ("T1a", "T1b")} <= {"inconclusive (gate)", "not supported", "meets C1-C4"}
    base = s["cost_cases"]["base"]
    for k in TRIAL_IDS:
        assert set(base["deflated_sharpe"][k]) == {"N17", "N3", "N10"}
        assert set(base["descriptive"][k]) == {"T", "B0", "B1", "B2", "B3"}
        assert base["descriptive"][k]["B3"]["fraction_in_ief"] == pytest.approx(s["weight_b3"][k])
        assert s["hold_periods"][k] == []
    for case in COST_CASES:
        assert (out / f"metrics_{case}.csv").exists() and (out / f"monthly_{case}.csv").exists()
    monthly = pd.read_csv(out / "monthly_base.csv", index_col=0)
    assert monthly.index.name == "month" and len(monthly) == s["holding_periods"]["T1"]
    assert {"w_T1", "w_T1a", "w_T1b", "T1", "B3_T1", "B3_T1b", "B0", "B1", "B2", "r_CPIAUCNS", "r_CPILFENS"} <= set(monthly.columns)
    assert monthly["T1b"].notna().sum() == s["holding_periods"]["T1b"]


def test_era_row_in_the_run_uses_t1s_own_b3(toy_history):
    _, out, s = toy_history
    monthly = pd.read_csv(out / "monthly_base.csv", index_col=0, parse_dates=["execution_date"])
    m = monthly["execution_date"].dt.to_period("M")
    sel = monthly[(m >= pd.Period(TOY_ERA[0], "M")) & (m <= pd.Period(TOY_ERA[1], "M"))]
    era = s["cost_cases"]["base"]["era_row_T1"]
    assert era["periods"] == len(sel) == s["era_periods"]
    assert era["mean_d_monthly"] == pytest.approx(float((sel["T1"] - sel["B3_T1"]).mean()), abs=1e-15)
    assert era["pass"] == bool((sel["T1"] - sel["B3_T1"]).mean() > 0)


def test_descriptives_cover_every_period(toy_history):
    _, _, s = toy_history
    base = s["cost_cases"]["base"]
    q = base["mechanism"]["by_T1_weight_quintile"]
    assert list(q) == ["Q1", "Q2", "Q3", "Q4", "Q5"]
    assert sum(v["periods"] for v in q.values()) == s["holding_periods"]["T1"]
    sign = base["mechanism"]["by_real_yield_sign"]
    assert sign["r_le_0"]["periods"] + sign["r_gt_0"]["periods"] == s["holding_periods"]["T1"]
    t1b = base["T1_on_T1b_window_descriptive"]
    assert t1b["periods"] == s["holding_periods"]["T1b"] and np.isfinite(t1b["T_minus_own_B3"]["t"])
    ov = base["overlap_after_the_fact"]
    assert ov["periods"] == s["holding_periods"]["T1"] and -1.0 <= ov["corr_d_T1_008_vs_007"] <= 1.0
    av = s["availability"]["T1"]
    assert av["CPIAUCNS"]["branch_counts"] == {"release_date_read": s["holding_periods"]["T1"]}
    assert av["CPILFENS"]["k_not_m_minus_1"] == 0 and av["CPIAUCNS"]["undefined_real_yield_months"] == []
    for k in TRIAL_IDS:
        assert set(base["sub_windows"][k]) and set(base["rate_eras"][k])


def test_write_verdict_and_json(toy_history, tmp_path):
    _, _, s = toy_history
    s = {**s, "run_at_utc": "2026-01-01T00:00:00Z", "provenance": {"git_commit": "0000000"}}
    history008.report.write_json(tmp_path / "summary.json", s)
    history008.write_verdict(s, tmp_path)
    text = (tmp_path / "verdict.md").read_text()
    assert "Verdict for T1" in text and "Family count 17 decides C3" in text and "Era row" in text
    assert json.loads((tmp_path / "summary.json").read_text())["family"]["n_family"] == 17


def test_registered_period_check_refuses_other_windows(tmp_path):
    fred = toy_yields()
    cpi, availability = _toy_cpi_and_availability(fred)
    with pytest.raises(ValueError, match="expected"):
        history008.compute(fred, cpi, availability, sigma=0.05, out_dir=tmp_path / "h", rank_n=TOY_RANK_N,
                           era=TOY_ERA, expected_periods=(534, 474, 396), **TOY)


# --- refusals ----------------------------------------------------------------------------------------


def test_main_refuses_without_gate_volcheck_or_with_existing_output(tmp_path):
    gate, vol, out = tmp_path / "gate", tmp_path / "volcheck", tmp_path / "history"
    with pytest.raises(SystemExit, match="passed gate"):
        history008.main([], gate_dir=gate, volcheck_dir=vol, out_dir=out)
    gate.mkdir()
    (gate / "gate.json").write_text(json.dumps({"outcome": "PASS"}))
    with pytest.raises(SystemExit, match="volcheck.json is missing"):
        history008.main([], gate_dir=gate, volcheck_dir=vol, out_dir=out)
    vol.mkdir()
    (vol / "volcheck.json").write_text(json.dumps({"sigma_annual": 0.07}))
    out.mkdir()
    with pytest.raises(SystemExit, match="executed once"):
        history008.main([], gate_dir=gate, volcheck_dir=vol, out_dir=out)


# --- after the separate code review (2026-10-25): gate-dropped trials, C3 wiring, column reads -------


def test_c3_is_decided_at_the_family_count_in_the_run(toy_history):
    _, _, s = toy_history
    dsr = s["cost_cases"]["base"]["deflated_sharpe"]
    for k in TRIAL_IDS:
        assert s["criteria"][k]["C3"] == (dsr[k]["N17"]["dsr"] >= 0.95)


def test_t1_on_t1b_periods_uses_t1s_own_b3(toy_history):
    _, out, s = toy_history
    monthly = pd.read_csv(out / "monthly_base.csv", index_col=0)
    on = monthly[monthly["T1b"].notna()]
    got = s["cost_cases"]["base"]["T1_on_T1b_window_descriptive"]
    assert got["B3_used"].startswith("T1's own B3")
    assert got["T_minus_own_B3"]["mean"] == pytest.approx(float((on["T1"] - on["B3_T1"]).mean()), abs=1e-15)
    assert got["T_minus_own_B3"]["n"] == s["holding_periods"]["T1b"]


def test_a_companion_dropped_at_the_gate_has_no_return_and_no_clause(tmp_path):
    fred = toy_yields()
    cpi, availability = _toy_cpi_and_availability(fred)
    s = history008.compute(fred, cpi, availability, sigma=0.05, out_dir=tmp_path / "h", rank_n=TOY_RANK_N,
                           era=TOY_ERA, dropped=("T1a",), **TOY)
    assert s["trials_run"] == ["T1", "T1b"] and s["dropped_at_gate"] == ["T1a"]
    assert "T1a" not in s["criteria"] and "T1a" not in s["weight_b3"]
    assert "T1a" not in s["cost_cases"]["base"]["descriptive"]
    assert s["verdict"]["T1a"] == s["verdict_rows_on_own_criteria"]["T1a"] == "inconclusive (gate)"
    assert s["verdict"]["T1"] != "inconclusive (fragile)" or s["verdict"]["T1b"] == "not supported"
    monthly = pd.read_csv(tmp_path / "h" / "monthly_base.csv", index_col=0)
    assert "T1a" not in monthly.columns and "w_T1a" not in monthly.columns
    s = {**s, "run_at_utc": "2026-01-01T00:00:00Z", "provenance": {"git_commit": "0000000"}}
    history008.write_verdict(s, tmp_path)
    assert "dropped at the gate" in (tmp_path / "verdict.md").read_text()
    with pytest.raises(ValueError, match="only companions"):
        history008.compute(fred, cpi, availability, sigma=0.05, out_dir=tmp_path / "x", rank_n=TOY_RANK_N,
                           era=TOY_ERA, dropped=("T1",), **TOY)


def test_main_passes_the_gates_dropped_trials_to_the_run(tmp_path, monkeypatch):
    gate, vol, out = tmp_path / "gate", tmp_path / "volcheck", tmp_path / "history"
    gate.mkdir()
    vol.mkdir()
    (gate / "gate.json").write_text(json.dumps({"outcome": "PASS", "dropped_trials": {"T1a": "inconclusive (gate)"}}))
    (vol / "volcheck.json").write_text(json.dumps({"sigma_annual": 0.07}))
    seen = {}

    class Stop(Exception):
        pass

    def fake_compute(*args, **kwargs):
        seen.update(kwargs)
        raise Stop

    for name in ("load_fred",):
        monkeypatch.setattr(history008.report, name, lambda: {})
    monkeypatch.setattr(history008, "load_series", lambda s: None)
    monkeypatch.setattr(history008.pd, "read_csv", lambda *a, **k: None)
    monkeypatch.setattr(history008, "read_007_differential", lambda: None)
    monkeypatch.setattr(history008, "compute", fake_compute)
    with pytest.raises(Stop):
        history008.main([], gate_dir=gate, volcheck_dir=vol, out_dir=out)
    assert seen["dropped"] == ("T1a",)


def test_read_007_differential_reads_only_month_t1_and_its_b3(tmp_path, monkeypatch):
    path = tmp_path / "monthly_base.csv"
    path.write_text("month,execution_date,w_T1,T1,B3_T1,B1\n1974-06,1974-07-01,0.25,0.01,0.005,x\n")
    calls = []
    real = pd.read_csv

    def spy(*args, **kwargs):
        calls.append(kwargs.get("usecols"))
        return real(*args, **kwargs)

    monkeypatch.setattr(history008.pd, "read_csv", spy)
    frame = history008.read_007_differential(path)
    assert calls == [["month", "T1", "B3_T1"]]
    assert list(frame.columns) == ["T1", "B3_T1"] and frame.index[0] == pd.Period("1974-06", "M")


def test_c3_reads_the_family_count_column_not_n3_or_n10(tmp_path, monkeypatch):
    """The toy DSRs lie on the same side of 0.95 at every N, so the test above
    cannot tell N17 from N3; here the DSR is pinned to depend on N only."""
    monkeypatch.setattr(history008.stats, "deflated_sharpe",
                        lambda sr, n_obs, skew, kurt, n, variance: {"dsr": 1.0 if n == 17 else 0.0})
    fred = toy_yields()
    cpi, availability = _toy_cpi_and_availability(fred)
    s = history008.compute(fred, cpi, availability, sigma=0.05, out_dir=tmp_path / "h", rank_n=TOY_RANK_N,
                           era=TOY_ERA, **TOY)
    assert all(s["criteria"][k]["C3"] for k in TRIAL_IDS)
    monkeypatch.setattr(history008.stats, "deflated_sharpe",
                        lambda sr, n_obs, skew, kurt, n, variance: {"dsr": 0.0 if n == 17 else 1.0})
    s = history008.compute(fred, cpi, availability, sigma=0.05, out_dir=tmp_path / "h2", rank_n=TOY_RANK_N,
                           era=TOY_ERA, **TOY)
    assert not any(s["criteria"][k]["C3"] for k in TRIAL_IDS)
