"""End-to-end smoke tests of the run orchestration (§9) on toy data only.
They check that every table, test, figure and criterion is produced and
internally consistent; they say nothing about any real instrument."""
import json

import pandas as pd
import pytest
from src import backtest, report
from src.calendar import build_schedule, month_end_bars
from src.config import CASH_LEG, COST_CASES, DURATION_LEG, POWER_MIN_SWITCHES, SUBPERIODS, TRIAL_IDS

from tests.toy import toy_world


@pytest.fixture(scope="module")
def toy_run(tmp_path_factory):
    w = toy_world()
    schedule = backtest.resolve_execution_dates(build_schedule(w["bars"], "2001-01", "2007-10"), w["bars"])
    out = tmp_path_factory.mktemp("insample")
    summary = report.run_window("toy", w["indices"], month_end_bars(w["bars"]), schedule, None, out,
                                with_subperiods=True, with_daily=True)
    return w, schedule, out, summary


def test_run_window_writes_every_artifact(toy_run):
    _, schedule, out, summary = toy_run
    for case in COST_CASES:
        assert (out / f"metrics_{case}.csv").exists() and (out / f"monthly_{case}.csv").exists()
    assert (out / "main_chart.png").stat().st_size > 10_000
    assert summary["holding_periods"] == len(schedule) - 1
    assert 0.0 < summary["weight_b3"] < 1.0
    report.write_json(out / "summary.json", summary)        # everything must be serialisable
    assert json.loads((out / "summary.json").read_text())["weight_b3"] == summary["weight_b3"]
    monthly = pd.read_csv(out / "monthly_base.csv")
    assert {"mom_at_signal", "T1_holding", "execution_date", "period_end"} <= set(monthly.columns)


def test_metrics_cover_all_strategies_and_are_consistent(toy_run):
    _, _, _, summary = toy_run
    base = summary["cost_cases"]["base"]
    assert set(base["descriptive"]) == set(TRIAL_IDS) | set(report.BENCHMARK_IDS)
    d = base["descriptive"]
    assert d["B0"]["sharpe_annual"] != d["B0"]["sharpe_annual"]        # cash excess is identically zero: NaN
    assert d["B1"]["fraction_in_ief"] == 1.0 and d["B0"]["fraction_in_ief"] == 0.0
    assert d["B3"]["fraction_in_ief"] == pytest.approx(summary["weight_b3"])
    assert d["T1"]["fraction_in_ief"] == pytest.approx(summary["weight_b3"])
    assert d["T1"]["switches"] > 0 and d["T1"]["switches_per_year"] > 0
    for t in TRIAL_IDS:
        for n in ("N3", "N10"):
            assert 0.0 <= base["deflated_sharpe"][t][n]["dsr"] <= 1.0
        assert base["inference"][t]["vs_B3"]["newey_west"]["lags"] == 6
        assert base["inference"][t]["vs_B1"]["ledoit_wolf"]["resamples"] == 10_000
        assert base["mechanism_check"][t]["months"] > 0
    assert base["max_drawdown_daily"]["T1"] <= d["T1"]["max_drawdown_monthly"] + 1e-12
    p = base["power_statement"]
    assert p["switches"] == d["T1"]["switches"]
    assert p["share_of_months_in_cash"] == pytest.approx(1.0 - summary["weight_b3"])
    assert p["label"] == ("low-powered" if p["switches"] < POWER_MIN_SWITCHES else "as registered")


def test_subperiods_are_sliced_by_execution_month(toy_run):
    _, schedule, _, summary = toy_run
    sub = summary["cost_cases"]["base"]["subperiods"]
    assert set(sub) == set(SUBPERIODS)
    # the toy window (2001-2007) only overlaps the first registered sub-period
    first = sub["2003-08 to 2008-12 (hiking cycle and crisis)"]
    start_month = schedule["execution_date"].iloc[:-1].dt.to_period("M")   # the last row starts no period
    expected = int(((start_month >= pd.Period("2003-08", "M")) & (start_month <= pd.Period("2008-12", "M"))).sum())
    assert first["T1"]["periods"] == expected
    assert all(not v for k, v in sub.items() if k != "2003-08 to 2008-12 (hiking cycle and crisis)")


def test_stress_costs_lower_returns_of_everything_that_trades(toy_run):
    _, _, _, summary = toy_run
    base, stress = summary["cost_cases"]["base"]["descriptive"], summary["cost_cases"]["stress"]["descriptive"]
    for name in TRIAL_IDS + ("B2", "B3"):
        assert stress[name]["ann_geometric_return"] < base[name]["ann_geometric_return"]
    for name in ("B0", "B1"):
        assert stress[name]["ann_geometric_return"] == base[name]["ann_geometric_return"]


def test_criteria_and_verdict_logic(toy_run):
    _, _, _, summary = toy_run
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


def test_mechanism_check_counts_the_months_in_cash(toy_run):
    w, schedule, _, summary = toy_run
    signals = report.trial_signals(w["indices"], month_end_bars(w["bars"]), schedule)
    returns = backtest.instrument_returns(w["indices"], schedule)
    m = report.mechanism_check(signals["T1"], schedule, returns)
    in_cash = (signals["T1"]["value"].reindex(schedule.index[:-1]) <= 0)
    assert m["months"] == int(in_cash.sum())
    assert m["months"] == pytest.approx((1 - summary["weight_b3"]) * (len(schedule) - 1))
    assert 0.0 <= m["fraction_bil_beats_ief"] <= 1.0
    assert CASH_LEG != DURATION_LEG
