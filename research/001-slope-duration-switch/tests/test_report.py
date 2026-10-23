"""End-to-end smoke tests of the run orchestration (§9) and of the validation
script (§5.3) on toy data only.  They check that every table, test, figure
and criterion is produced and internally consistent; they say nothing about
any real instrument."""
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


def test_validate_on_toy_bars(monkeypatch, tmp_path):
    """The §5.3 statistics on a toy ETF built from the synthetic index with
    noise: the plumbing runs and the thresholds are evaluated."""
    fred = toy_yields()
    indices = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    rng = np.random.default_rng(7)
    nyse = pd.bdate_range("2001-01-02", "2003-12-31").drop(pd.Timestamp("2002-07-04"))

    def toy_bars(name):
        tri = indices[name].reindex(nyse, method="ffill")
        noise = rng.normal(0, 1e-4 if name == DURATION_LEG else 1e-6, len(nyse)).cumsum()
        return pd.DataFrame({"close": tri.to_numpy() * 100 * np.exp(noise)}, index=nyse)

    monkeypatch.setattr(validate, "load_bars", toy_bars)
    monkeypatch.setattr(validate, "load_series", lambda name: fred[name])
    passed = validate.run("2001-01-02", "2003-12-31", tmp_path)
    out = json.loads((tmp_path / "validation.json").read_text())
    assert set(out["checks"]) == {"A1", "A2", "A3", "A4", "B1", "B2"}
    assert out["checks"]["A1"]["pass"] and out["checks"]["A2"]["pass"]
    assert passed == all(c["pass"] for c in out["checks"].values())
    assert (tmp_path / "validation.png").exists() and (tmp_path / "validation.md").exists()
    assert out["statistics"][CASH_LEG]["days"] == len(nyse) - 1
