"""End-to-end smoke tests of the run orchestration (§9) and of the two-window
validation script (§5.3) on toy data only.  They check that every table,
test, figure and criterion is produced and internally consistent; they say
nothing about any real instrument."""
import json

import numpy as np
import pandas as pd
import pytest

from src import report, validate
from src.calendar import build_schedule
from src.config import CASH_LEG, COST_CASES, DURATION_LEG, TRIAL_IDS
from src.synthetic import synthetic_indices
from tests.toy import toy_yields


@pytest.fixture(scope="module")
def toy_run(tmp_path_factory):
    fred = toy_yields()
    schedule = build_schedule(fred["DGS10"], fred["DTB3"], "2000-02", "2005-10")
    indices = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    out = tmp_path_factory.mktemp("insample")
    summary = report.run_window("toy", indices, fred, schedule, None, out,
                                with_subperiods=False, with_daily=True)
    return fred, schedule, indices, out, summary


def test_run_window_writes_every_artifact(toy_run):
    _, schedule, _, out, summary = toy_run
    for case in COST_CASES:
        assert (out / f"metrics_{case}.csv").exists() and (out / f"monthly_{case}.csv").exists()
    assert (out / "main_chart.png").stat().st_size > 10_000
    assert summary["holding_periods"] == len(schedule) - 1
    assert 0.0 < summary["weight_b3"] < 1.0
    report.write_json(out / "summary.json", summary)        # everything must be serialisable
    assert json.loads((out / "summary.json").read_text())["weight_b3"] == summary["weight_b3"]


def test_metrics_cover_all_strategies_and_are_consistent(toy_run):
    _, _, _, _, summary = toy_run
    base = summary["cost_cases"]["base"]
    assert set(base["descriptive"]) == set(TRIAL_IDS) | set(report.BENCHMARK_IDS)
    d = base["descriptive"]
    assert d["B0"]["sharpe_annual"] != d["B0"]["sharpe_annual"]        # cash excess is identically zero: NaN
    assert d["B1"]["fraction_in_ief"] == 1.0 and d["B0"]["fraction_in_ief"] == 0.0
    assert d["B3"]["fraction_in_ief"] == pytest.approx(summary["weight_b3"])
    assert d["T1"]["fraction_in_ief"] == pytest.approx(summary["weight_b3"])
    assert d["T1"]["switches_per_year"] > 0
    for t in TRIAL_IDS:
        for n in ("N3", "N10"):
            assert 0.0 <= base["deflated_sharpe"][t][n]["dsr"] <= 1.0
        assert base["inference"][t]["vs_B3"]["newey_west"]["lags"] == 6
        assert base["inference"][t]["vs_B1"]["ledoit_wolf"]["resamples"] == 10_000
        assert base["mechanism_check"][t]["months"] > 0
    assert base["max_drawdown_daily"]["T1"] <= d["T1"]["max_drawdown_monthly"] + 1e-12


def test_stress_costs_lower_returns_of_everything_that_trades(toy_run):
    _, _, _, _, summary = toy_run
    base, stress = summary["cost_cases"]["base"]["descriptive"], summary["cost_cases"]["stress"]["descriptive"]
    for name in TRIAL_IDS + ("B2", "B3"):
        assert stress[name]["ann_geometric_return"] < base[name]["ann_geometric_return"]
    for name in ("B0", "B1"):
        assert stress[name]["ann_geometric_return"] == base[name]["ann_geometric_return"]


def test_criteria_and_verdict_logic(toy_run):
    _, _, _, _, summary = toy_run
    base, stress = summary["cost_cases"]["base"], summary["cost_cases"]["stress"]
    c = report.insample_criteria(base["descriptive"], base["inference"], base["deflated_sharpe"],
                                 stress["descriptive"], stress["inference"])
    assert set(c) == {"C1", "C2", "C3", "C4"} and all(isinstance(v, bool) for v in c.values())
    o = report.oos_criteria(base["descriptive"], base["inference"])
    assert set(o) == {"O1", "O2"}
    all_c = {k: True for k in c}
    assert report.verdict(all_c, {"O1": True, "O2": True}, 1.0, -0.1, -0.2) == "supported"
    assert report.verdict(dict(all_c, C3=False), {"O1": True, "O2": True}, 1.0, -0.1, -0.2) == "not supported"
    assert report.verdict(all_c, {"O1": False, "O2": True}, -1.5, -0.1, -0.2) == "not supported"
    assert report.verdict(all_c, {"O1": True, "O2": True}, 1.0, -0.3, -0.2) == "not supported"
    assert report.verdict(all_c, {"O1": False, "O2": True}, -0.5, -0.1, -0.2) == "inconclusive"
    assert report.verdict(all_c, {"O1": True, "O2": False}, 0.5, -0.1, -0.2) == "inconclusive"


# --- §5.3 validation plumbing on toy data ------------------------------------------

W1 = ("2003-01-02", "2005-06-30")   # toy "window 1": Alpaca-style bars for IEF and BIL
W2 = ("2000-07-03", "2002-12-31")   # toy "window 2": vendor-style adjusted closes for IEF


def _toy_sources(monkeypatch, fred, indices, noise_scale=1e-4):
    rng = np.random.default_rng(7)
    days = pd.bdate_range("2000-01-04", "2005-12-30").drop(pd.Timestamp("2002-07-04"))

    def noisy(name, scale):
        tri = indices[name].reindex(days, method="ffill")
        return tri.to_numpy() * 100 * np.exp(rng.normal(0, scale, len(days)).cumsum())

    closes = {DURATION_LEG: noisy(DURATION_LEG, noise_scale), CASH_LEG: noisy(CASH_LEG, 1e-6)}
    monkeypatch.setattr(validate, "load_bars", lambda name: pd.DataFrame({"close": closes[name]}, index=days))
    monkeypatch.setattr(validate, "load_prices", lambda name: pd.DataFrame({"adjClose": closes[name]}, index=days))
    monkeypatch.setattr(validate, "load_series", lambda name: fred[name])
    return days


def test_validate_runs_both_windows_and_summarises(monkeypatch, tmp_path):
    fred = toy_yields()
    indices = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    days = _toy_sources(monkeypatch, fred, indices)
    decision = {"window2": "accepted", "reason": "toy"}
    passed = validate.run(tmp_path, W1, W2, decision)
    summary = json.loads((tmp_path / "validation.json").read_text())
    w1 = json.loads((tmp_path / "window1" / "validation.json").read_text())
    w2 = json.loads((tmp_path / "window2" / "validation.json").read_text())
    assert set(w1["checks"]) == {"A1", "A2", "A3", "A4", "B1", "B2"}
    assert set(w2["checks"]) == {"A1", "A2", "A3", "A4"}
    assert w1["checks"]["A4"]["threshold"] == "in [-0.0025, 0.0035]"
    assert w2["checks"]["A4"]["threshold"] == "in [-0.0045, 0.0035]"
    assert w1["checks"]["A4"]["exante_central_estimate"] == 0.0005
    assert w2["checks"]["A4"]["exante_central_estimate"] == -0.0005
    assert w1["checks"]["A1"]["pass"] and w1["checks"]["A2"]["pass"] and w2["checks"]["A1"]["pass"]
    assert summary["window2"]["included"] is True
    assert passed == (w1["all_pass"] and w2["all_pass"]) == summary["all_pass"]
    for folder in ("window1", "window2"):
        assert (tmp_path / folder / "validation.png").exists() and (tmp_path / folder / "validation.md").exists()
    assert w1["statistics"][CASH_LEG]["days"] == len(days[(days >= W1[0]) & (days <= W1[1])]) - 1
    assert set(w1["D1_by_year_descriptive"]) == {"2016", "2017", "2018"}   # the real window's years, by design
    assert set(w2["statistics"][DURATION_LEG]["mean_diff_annual_by_year"]) == {"2000", "2001", "2002"}


def test_validate_skips_window_2_when_the_committed_decision_excludes_it(monkeypatch, tmp_path):
    fred = toy_yields()
    indices = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    _toy_sources(monkeypatch, fred, indices)
    decision = {"window2": "excluded_unavailable", "reason": "toy: vendor series starts too late"}
    passed = validate.run(tmp_path, W1, W2, decision)
    summary = json.loads((tmp_path / "validation.json").read_text())
    assert summary["window2"] == {"included": False, "decision": decision}
    assert not (tmp_path / "window2").exists()
    assert passed == summary["window1"]["all_pass"] == summary["all_pass"]


def test_validate_fails_on_a_level_gap_outside_the_band(monkeypatch, tmp_path):
    """A toy ETF that earns 1% p.a. more than the synthetic series must fail
    A4 on both windows and nothing else of A1-A3."""
    fred = toy_yields()
    indices = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    days = _toy_sources(monkeypatch, fred, indices, noise_scale=1e-5)
    drift = np.exp(0.01 / 252 * np.arange(len(days)))
    ief = validate.load_bars(DURATION_LEG)["close"].to_numpy() * drift
    original_bars = validate.load_bars
    monkeypatch.setattr(validate, "load_bars", lambda name: pd.DataFrame({"close": ief}, index=days)
                        if name == DURATION_LEG else original_bars(name))
    monkeypatch.setattr(validate, "load_prices", lambda name: pd.DataFrame({"adjClose": ief}, index=days))
    assert not validate.run(tmp_path, W1, W2, {"window2": "accepted"})
    for folder in ("window1", "window2"):
        checks = json.loads((tmp_path / folder / "validation.json").read_text())["checks"]
        assert not checks["A4"]["pass"] and checks["A4"]["value"] > 0.0035
        assert checks["A1"]["pass"] and checks["A2"]["pass"] and checks["A3"]["pass"]


def test_validate_refuses_without_the_committed_decision_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        validate.window2_decision(tmp_path / "missing.json")
