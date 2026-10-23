"""The report module on toy data: every table written, d_t equal to B2 − B1,
T1 identical to the pipeline's conditional path, descriptive trials on their
own months, the §9.5 row present only where the window carries decision
weight, and the refusal when a results folder exists."""
import json

import numpy as np
import pandas as pd
import pytest
from src import pipeline, regime, report
from src.config import COST_CASES

from tests.toy import toy_cpi, toy_world


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    world = toy_world()
    out = tmp_path_factory.mktemp("insample")
    bars = pipeline.window_bars(world["indices"], etf_cash=False)
    summary = report.run_window("toy in-sample", world["indices"], world["closes"]["SPY"], world["closes"]["IEF"],
                                toy_cpi(), bars, "2001-01", "2007-11", None, out, decision_weight=True)
    return dict(world, out=out, summary=summary, bars=bars)


def test_files_and_trials(window):
    out, s = window["out"], window["summary"]
    for case in COST_CASES:
        assert (out / f"metrics_{case}.csv").exists() and (out / f"monthly_{case}.csv").exists()
    assert s["trials_run"] == ["T1", "T2", "T3"] and s["trials_not_run"] == []
    for t in s["trials_run"]:
        assert (out / f"positive_episodes_{t}.csv").exists()
    assert s["trial_periods"]["T1"] == s["holding_periods"]
    assert s["trial_periods"]["T2"] <= s["holding_periods"]          # the 252-day window starts later
    assert "weight_b3" in s and 0.0 < s["weight_b3"] < 1.0


def test_d_is_b2_minus_b1_and_t1_matches_pipeline(window):
    monthly = pd.read_csv(window["out"] / "monthly_base.csv", index_col=0)
    assert np.allclose(monthly["d"], monthly["B2"] - monthly["B1"], atol=1e-15)
    schedule, month_ends = pipeline.window_schedule(window["bars"], "2001-01", "2007-11")
    trend = pipeline.trend_frame(window["indices"], month_ends, schedule)
    targets = pipeline.period_targets(trend, schedule)
    returns = regime.common_returns(window["closes"]["SPY"], window["closes"]["IEF"])
    positive = regime.correlation_regime(returns, schedule["signal_date"], "T1")["positive"].reindex(targets.index)
    paths = pipeline.window_paths(window["indices"], schedule, targets, positive, COST_CASES["base"])
    assert np.allclose(monthly["T1"], paths["results"]["T1"]["r"].to_numpy(), atol=1e-15)
    assert (monthly["T1_holding"].to_numpy() == paths["results"]["T1"]["holding"].to_numpy()).all()
    assert (monthly["positive_T1"].astype(bool).to_numpy() == positive.to_numpy()).all()


def test_edge_and_rows(window):
    base = window["summary"]["cost_cases"]["base"]
    for t in ("T1", "T2", "T3"):
        e = base["edge"][t]
        assert e["n_pos"] + e["n_neg"] == window["summary"]["trial_periods"][t]
        assert e["delta"] == pytest.approx(e["mean_positive"] - e["mean_negative"])
        assert base["rows_9_5"][t] in (report.insample_row.__globals__["ROW_REFUTED"],
                                       report.insample_row.__globals__["ROW_SIGN_CONSISTENT"],
                                       report.insample_row.__globals__["ROW_INCONCLUSIVE"],
                                       report.insample_row.__globals__["ROW_NOT_INFORMATIVE"])
    assert set(base["deflated_sharpe"]) == {"T1", "T2", "T3"}
    assert "vs_B2" in base["versus_benchmarks"]["T1"] and "vs_B3" in base["versus_benchmarks"]["T1"]
    # the stress case has no row: §9.5 applies to base costs only
    assert "rows_9_5" not in window["summary"]["cost_cases"]["stress"]


def test_positive_episode_table_matches_flags(window):
    table = pd.read_csv(window["out"] / "positive_episodes_T1.csv")
    monthly = pd.read_csv(window["out"] / "monthly_base.csv", index_col=0)
    flags = monthly["positive_T1"].astype(bool)
    assert table["months"].sum() == int(flags.sum())
    assert len(table) == window["summary"]["regime_descriptives"]["T1"]["positive_episodes"]


def test_episode_label_has_no_row(tmp_path):
    world = toy_world()
    bars = pipeline.window_bars(world["indices"], etf_cash=False)
    s = report.run_window(report.EPISODE_LABEL, world["indices"], world["closes"]["SPY"], world["closes"]["IEF"],
                          None, bars, "2004-01", "2007-11", 0.5, tmp_path, decision_weight=False)
    assert s["decision_weight"] is False and s["trials_not_run"] == ["T3"]
    assert s["cost_cases"]["base"]["rows_9_5_note"].startswith("no row applies")
    assert "weight_b3" not in s                                       # frozen weight passed in, not re-estimated
    assert pd.read_csv(tmp_path / "metrics_base.csv", index_col=0).loc["B3", "fraction_in_ief"] == 0.5


def test_runs_refuse_when_results_exist(tmp_path, monkeypatch):
    existing = tmp_path / "insample"
    existing.mkdir()
    with pytest.raises(SystemExit):
        report.run_insample(existing)
    with pytest.raises(SystemExit):
        report.run_episode(existing)
    (tmp_path / "episode").mkdir(parents=True)
    with pytest.raises(SystemExit):
        report.run_episode(tmp_path / "episode")


def test_json_default_handles_numpy_and_periods(tmp_path):
    payload = {"a": np.float64(1.5), "b": np.int64(2), "c": np.bool_(True), "d": pd.Period("2003-08", "M")}
    report.write_json(tmp_path / "x.json", payload)
    assert json.loads((tmp_path / "x.json").read_text()) == {"a": 1.5, "b": 2, "c": True, "d": "2003-08"}
