"""Study 007 history run (PREREGISTRATION.md §8.1, §9.4-§9.6) on constructed
data only; no file in data/raw/ is read.  Toy windows and short minimum
histories stand in for the registered ones, which are checked by ``main``."""

import json

import numpy as np
import pandas as pd
import pytest
from src import backtest, history007, tilt
from src.config import CASH_LEG, COST_CASES, DURATION_LEG
from src.config007 import FAMILY_COUNT_AT_REGISTRATION, TRIAL_IDS, VOL_BAR_007

from tests.toy import toy_yields

PASS = {"C1": True, "C2": True, "C3": True, "C4": True}
TOY_MIN_HISTORY = {"T1": 12, "T1a": 6, "T1b": 24}
TOY = dict(carry_first_month="2000-01", test_first_month="2001-01", t1b_first_month="2002-01", last_month="2005-10")


def _fail(key):
    return {**PASS, key: False}


@pytest.fixture(scope="module")
def toy_history(tmp_path_factory):
    fred = toy_yields()
    out = tmp_path_factory.mktemp("history") / "history"
    summary = history007.compute(fred, sigma=0.05, out_dir=out, min_history=TOY_MIN_HISTORY, **TOY)
    return fred, out, summary


# --- §9.5 verdicts --------------------------------------------------------------------------------


def test_primary_verdict_precedence():
    ok = {"T1a": "supported in history; forward record pending", "T1b": "supported in history; forward record pending"}
    v = history007.primary_verdict
    assert v(False, PASS, ok, 0.01) == "inconclusive (gate)"
    for key in PASS:
        assert v(True, _fail(key), ok, 0.01) == "not supported"
        assert v(True, _fail(key), {**ok, "T1a": "not supported"}, 0.5) == "not supported"
    assert v(True, PASS, {**ok, "T1b": "not supported"}, 0.01) == "inconclusive (fragile)"
    assert v(True, PASS, {**ok, "T1a": "inconclusive (gate)"}, 0.01) == "supported in history; forward record pending"
    assert v(True, PASS, ok, VOL_BAR_007 + 1e-12) == "consistent with an edge, not detectable at the 2% bar"
    assert v(True, PASS, ok, VOL_BAR_007) == "supported in history; forward record pending"


def test_secondary_verdict_has_no_companion_clause():
    v = history007.secondary_verdict
    assert v(False, PASS, 0.01) == "inconclusive (gate)"
    assert v(True, _fail("C3"), 0.01) == "not supported"
    assert v(True, PASS, 0.2) == "consistent with an edge, not detectable at the 2% bar"
    assert v(True, PASS, 0.05) == "supported in history; forward record pending"


def test_turnover_label():
    assert history007.turnover_label(7.999) == "low-powered" and history007.turnover_label(8.0) is None


def test_criteria_known_answer():
    desc = {"T": {"sharpe_annual": 0.50}, "B1": {"sharpe_annual": 0.40}, "B3": {"sharpe_annual": 0.35}}
    infer = {"vs_B3": {"newey_west": {"t": 2.0, "mean": 0.001}}}
    stress = {"vs_B3": {"newey_west": {"t": 1.5, "mean": 0.0005}}}
    assert history007.criteria(desc, infer, {"dsr": 0.95}, stress) == PASS
    assert not history007.criteria({**desc, "B3": {"sharpe_annual": 0.41}}, infer, {"dsr": 0.95}, stress)["C1"]
    assert not history007.criteria(desc, infer, {"dsr": 0.949}, stress)["C3"]
    flipped = {"vs_B3": {"newey_west": {"t": -0.1, "mean": -0.0001}}}
    assert not history007.criteria(desc, infer, {"dsr": 0.95}, flipped)["C4"]


def test_family_count_is_the_registered_fourteen():
    assert history007.family_count() == FAMILY_COUNT_AT_REGISTRATION == 14


# --- the run on toy data ----------------------------------------------------------------------------


def test_summary_structure_and_files(toy_history):
    _, out, s = toy_history
    assert set(s["cost_cases"]) == set(COST_CASES)
    assert s["holding_periods"]["T1b"] < s["holding_periods"]["T1"] == s["holding_periods"]["T3"]
    assert set(s["verdict"]) == set(TRIAL_IDS) and set(s["criteria"]) == set(TRIAL_IDS)
    allowed = {"inconclusive (gate)", "not supported", "inconclusive (fragile)",
               "consistent with an edge, not detectable at the 2% bar", "supported in history; forward record pending"}
    assert set(s["verdict"].values()) <= allowed
    base = s["cost_cases"]["base"]
    for k in TRIAL_IDS:
        assert set(base["deflated_sharpe"][k]) == {"N14", "N5", "N10"}
        assert set(base["descriptive"][k]) == {"T", "B0", "B1", "B2", "B3"}
        assert base["descriptive"][k]["B3"]["fraction_in_ief"] == pytest.approx(s["weight_b3"][k])
    for case in COST_CASES:
        assert (out / f"metrics_{case}.csv").exists() and (out / f"monthly_{case}.csv").exists()
    monthly = pd.read_csv(out / "monthly_base.csv", index_col=0)
    assert len(monthly) == s["holding_periods"]["T1"]
    assert {"w_T1", "w_T1b", "T1", "B3_T1", "B3_T1b", "B0", "B1", "B2", "carry_at_signal"} <= set(monthly.columns)
    assert monthly["T1b"].notna().sum() == s["holding_periods"]["T1b"]  # T1b only on its own window


def test_each_trial_has_its_own_b3_at_its_mean_weight(toy_history):
    _, _, s = toy_history
    base = s["cost_cases"]["base"]
    assert s["weight_b3"]["T3"] == pytest.approx(base["descriptive"]["T3"]["T"]["mean_weight"])
    assert 0.0 < s["weight_b3"]["T1"] < 1.0
    assert base["descriptive"]["T1"]["B3"]["periods"] == s["holding_periods"]["T1"]
    assert base["descriptive"]["T1b"]["B3"]["periods"] == s["holding_periods"]["T1b"]


def test_t3_equals_the_switching_engine_on_its_zero_one_path(toy_history):
    fred, _, s = toy_history
    from src.calendar import build_schedule
    from src.gate007 import weight_paths
    from src.synthetic import synthetic_indices

    indices = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    full = build_schedule(fred["DGS10"], fred["DTB3"], TOY["carry_first_month"], TOY["last_month"])
    paths = weight_paths(fred["DGS10"], fred["DGS7"], fred["DTB3"], full, indices, TOY_MIN_HISTORY)
    schedule = build_schedule(fred["DGS10"], fred["DTB3"], TOY["test_first_month"], TOY["last_month"])
    returns = backtest.instrument_returns(indices, schedule)
    w3 = paths["w_T3"].reindex(returns.index)
    cost = COST_CASES["base"]
    ours = tilt.run_tilt(w3, returns, cost)
    targets = pd.Series(np.where(w3 == 1.0, DURATION_LEG, CASH_LEG), index=returns.index)
    theirs = backtest.run_switching(targets, returns, cost)
    np.testing.assert_allclose(ours["r"].to_numpy(), theirs["r"].to_numpy(), rtol=0, atol=1e-15)
    assert s["cost_cases"]["base"]["descriptive"]["T3"]["T"]["sharpe_annual"] == pytest.approx(
        history007.report.descriptive_metrics(theirs, backtest.run_static(0.0, returns, 0.0)["r"], returns)["sharpe_annual"]
    )


def test_mechanism_and_attribution_cover_every_period(toy_history):
    _, _, s = toy_history
    base = s["cost_cases"]["base"]
    q = base["mechanism"]["by_T1_weight_quintile"]
    assert list(q) == ["Q1", "Q2", "Q3", "Q4", "Q5"]
    assert sum(v["periods"] for v in q.values()) == s["holding_periods"]["T1"]
    assert q["Q1"]["weight_max"] <= q["Q5"]["weight_min"]
    sign = base["mechanism"]["by_carry_sign"]
    assert sign["carry_le_0"]["periods"] + sign["carry_gt_0"]["periods"] == s["holding_periods"]["T1"]
    a = base["attribution"]
    assert set(a) == {"T1", "T2", "T3", "corr_weight_T1_T3"} and -1.0 <= a["corr_weight_T1_T3"] <= 1.0
    assert a["T1"]["mean_d_annual"] == pytest.approx(a["T1"]["mean_d_monthly"] * 12)


def test_subwindows_by_execution_month_and_dispersion(toy_history):
    _, _, s = toy_history
    base = s["cost_cases"]["base"]
    for k in TRIAL_IDS:
        for name, block in base["sub_windows"][k].items():
            assert "periods" in block or "T" in block
        d = base["weight_dispersion"][k]
        assert d["sd_w_minus_wbar"] == pytest.approx(base["descriptive"][k]["T"]["sd_weight"])
        assert d["uniform_rank_1_over_sqrt12"] == pytest.approx(1 / np.sqrt(12))
    assert base["T1_on_T1b_window_descriptive"]["periods"] == s["holding_periods"]["T1b"]
    assert "ratio" in base["nw_iid_ratio_vs_B3"]["T1"]


def test_write_verdict_and_json(toy_history, tmp_path):
    _, _, s = toy_history
    s = {**s, "run_at_utc": "2026-01-01T00:00:00Z", "provenance": {"git_commit": "0000000"}}
    history007.report.write_json(tmp_path / "summary.json", s)
    history007.write_verdict(s, tmp_path)
    text = (tmp_path / "verdict.md").read_text()
    assert "Verdict for T1" in text and "Family count 14 decides C3" in text
    assert json.loads((tmp_path / "summary.json").read_text())["family"]["n_family"] == 14


# --- refusals ----------------------------------------------------------------------------------------


def test_main_refuses_without_gate_volcheck_or_with_existing_output(tmp_path):
    gate, vol, out = tmp_path / "gate", tmp_path / "volcheck", tmp_path / "history"
    with pytest.raises(SystemExit, match="passed gate"):
        history007.main([], gate_dir=gate, volcheck_dir=vol, out_dir=out)
    gate.mkdir()
    (gate / "gate.json").write_text(json.dumps({"outcome": "PASS"}))
    with pytest.raises(SystemExit, match="volcheck.json is missing"):
        history007.main([], gate_dir=gate, volcheck_dir=vol, out_dir=out)
    vol.mkdir()
    (vol / "volcheck.json").write_text(json.dumps({"sigma_annual": 0.07}))
    out.mkdir()
    with pytest.raises(SystemExit, match="executed once"):
        history007.main([], gate_dir=gate, volcheck_dir=vol, out_dir=out)
