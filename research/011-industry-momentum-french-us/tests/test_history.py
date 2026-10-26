"""Study 011 history code on synthetic industries only (no library file)."""
import json

import numpy as np
import pandas as pd
import pytest
from src import history
from src.data import vw_monthly

PROG = {"public_trials_md": 40, "with_desk_registry": 60, "method": "synthetic"}


def _ind(n: int, seed: int, months: int = 1202) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.period_range("1926-07", periods=months, freq="M")
    return pd.DataFrame(rng.normal(0.8, 5.0, (months, n)).round(2), index=idx, columns=[f"I{i}" for i in range(n)])


@pytest.fixture(scope="module")
def result():
    history.N_RESAMPLES = 50
    ind = {17: _ind(17, 1), 30: _ind(30, 2)}
    return history.compute(ind, "2026-08", PROG), ind


def test_windows_and_counts(result):
    (summary, frames, cohorts), _ = result
    b = summary["cost_cases"]["base"]["trials"]
    assert b["M1"]["O"]["months"] == 806 and b["M1a"]["O"]["months"] == 806 and b["M1b"]["O"]["months"] == 800
    assert b["M1"]["windows"]["I1"]["months"] == 433 and b["M1"]["windows"]["I2"]["months"] == 373
    assert b["M1"]["windows"]["M"]["months"] == 385 and b["M1"]["windows"]["full"]["months"] == 1191
    assert b["M1b"]["windows"]["full"]["months"] == 1185
    assert frames["M1"].index[0] == pd.Period("1927-06", "M")
    assert str(frames["M1b"].index[0]) == "1927-12"
    assert "1926-12" in cohorts["M1"] and "1927-06" in cohorts["M1b"] and "1927-05" not in cohorts["M1b"]


def test_summary_structure(result):
    (summary, _, _), _ = result
    assert summary["verdict"]["M1"].startswith("not supported") or summary["criteria"]["M1"]["all"] is not False
    assert set(summary["criteria"]["M1"]) == {"C1", "C2", "C3", "C4", "all"}
    assert f"N{history.N_FAMILY}" in summary["cost_cases"]["base"]["trials"]["M1"]["dsr"]


def test_planted_momentum_is_found():
    history.N_RESAMPLES = 50
    rng = np.random.default_rng(7)
    months, n = 1202, 17
    idx = pd.period_range("1926-07", periods=months, freq="M")
    # persistent industry means that drift slowly: past winners keep winning
    mu = np.cumsum(rng.normal(0, 0.15, (months, n)), axis=0)
    r = pd.DataFrame((mu + rng.normal(0, 2.0, (months, n))).round(2), index=idx, columns=[f"I{i}" for i in range(n)])
    r30 = pd.DataFrame(np.repeat(r.values, 2, axis=1)[:, :30], index=idx, columns=[f"J{i}" for i in range(30)])
    summary, _, _ = history.compute({17: r, 30: r30}, "2026-08", PROG)
    assert summary["criteria"]["M1"]["C2"]
    assert summary["cost_cases"]["base"]["trials"]["M1"]["O"]["mean_pct_a_year"] > 0


def test_verdict_precedence():
    ok = {"C1": True, "C2": True, "C3": True, "C4": True, "all": True}
    bad = {**ok, "C2": False, "all": False}
    v = history.verdict({"M1": ok, "M1a": ok, "M1b": ok}, True, 1.0)
    assert v["M1"] == "supported in history; forward record pending"
    v = history.verdict({"M1": ok, "M1a": bad, "M1b": ok}, False, 1.0)
    assert v["M1"] == "inconclusive (one side of the paper's sample only)"
    v = history.verdict({"M1": ok, "M1a": bad, "M1b": ok}, True, 3.0)
    assert v["M1"] == "inconclusive (fragile) (Sharpe units; the 2%-a-year bar not met)"
    assert v["M1a"] == "not supported"
    v = history.verdict({"M1": bad, "M1a": ok, "M1b": ok}, True, 3.0)
    assert v["M1"] == "not supported"


def test_refusals(tmp_path):
    with pytest.raises(SystemExit, match="APPROVED"):
        history.main([], here=tmp_path)
    (tmp_path / "APPROVED").write_text("ok\n")
    (tmp_path / "results" / "history").mkdir(parents=True)
    with pytest.raises(SystemExit, match="exists"):
        history.main([], here=tmp_path)
    (tmp_path / "results" / "history").rmdir()
    with pytest.raises(SystemExit, match="programme_count"):
        history.main([], here=tmp_path)
    (tmp_path / "results" / "programme_count.json").write_text(json.dumps(PROG))
    (tmp_path / "trials.md").write_text("no row\n")
    with pytest.raises(SystemExit, match="history-run row"):
        history.main([], here=tmp_path)


def test_loader_reads_vw_monthly_only():
    text = ("x\n\n  Average Value Weighted Returns -- Monthly\n,A,B\n192607,  1.50, -99.99\n192608,  2.00,  3.00\n\n"
            "  Average Equal Weighted Returns -- Monthly\n,A,B\n192607,  9.00,  9.00\n")
    f = vw_monthly(text)
    assert list(f.columns) == ["A", "B"] and len(f) == 2
    assert f.iloc[0, 0] == 1.5 and np.isnan(f.iloc[0, 1])
