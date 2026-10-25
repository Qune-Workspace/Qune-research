"""Study 006 gate and volatility check (PREREGISTRATION.md §5.3, §5.4, §13
tests 1-6).  Constructed data only; no file in data/raw/ is read."""

import ast
import json
import os
import subprocess

import numpy as np
import pandas as pd
import pytest
from src import backtest, gate, volcheck
from src.config import STUDY_DIR
from src.config006 import G1_MAX, G2_MAX, VOL_BAR

SRC = STUDY_DIR / "src"


def _local_imports(module: str) -> set[str]:
    tree = ast.parse((SRC / f"{module}.py").read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            if node.module:
                found.add(node.module)
            else:
                found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            found.update(a.name.split(".")[1] for a in node.names if a.name.startswith("src."))
    return found


def _reachable(module: str) -> set[str]:
    seen, todo = set(), [module]
    while todo:
        m = todo.pop()
        if m in seen:
            continue
        seen.add(m)
        todo.extend(_local_imports(m))
    return seen


# --- test 1: the gate and the volatility check cannot see a rule return ------------


@pytest.mark.parametrize("module", ["gate", "volcheck"])
def test_gate_modules_never_reach_the_backtest(module):
    reachable = _reachable(module)
    assert "backtest" not in reachable and "report" not in reachable and "stats" not in reachable
    assert {"signal", "synthetic", "calendar"} <= _reachable("gate")


def test_import_graph_walker_sees_the_backtest_where_it_is():
    assert "backtest" in _reachable("report")


# --- test 2: a constant gap cancels ---------------------------------------------------


def test_constant_gap_gives_zero_bias():
    rng = np.random.default_rng(6)
    h = (rng.random(192) > 0.3).astype(float)
    x_etf = rng.normal(0.002, 0.018, 192)
    s = gate.gate_statistics(h, x_etf + 0.0004, x_etf)
    assert abs(s["mean_e_annual_signed"]) < 1e-15 and s["G1_pass"]
    assert s["mean_g_annual"] == pytest.approx(0.0048)


# --- test 3: known answers ------------------------------------------------------------


def test_gate_statistics_known_answer():
    h = np.array([1, 1, 0, 0], dtype=float)  # w_o = 0.5
    x_etf = np.array([0.01, -0.01, 0.02, -0.02])
    g = np.array([0.001, 0.003, -0.002, 0.0])
    s = gate.gate_statistics(h, x_etf + g, x_etf)
    e = (h - 0.5) * g  # 0.0005, 0.0015, 0.001, 0
    assert s["w_o"] == 0.5 and s["switches"] == 1
    assert s["G1_bias_annual"] == pytest.approx(abs(e.mean()) * 12)
    assert s["G2_noise_ratio"] == pytest.approx(np.std(g, ddof=1) / np.std(x_etf, ddof=1))


def test_gate_fails_on_a_gap_that_coincides_with_the_holdings():
    rng = np.random.default_rng(7)
    h = (rng.random(192) > 0.5).astype(float)
    x_etf = rng.normal(0.0, 0.018, 192)
    s = gate.gate_statistics(h, x_etf + 0.0012 * h, x_etf)  # 1.44%/yr gap in held months: G1 = w(1-w) x 1.44% ~ 0.36%
    assert s["G1_bias_annual"] > G1_MAX and not s["G1_pass"] and s["G2_pass"]
    noisy = gate.gate_statistics(h, x_etf + rng.normal(0, 0.01, 192), x_etf)
    assert noisy["G2_noise_ratio"] > G2_MAX and not noisy["G2_pass"]


def test_bil_absent_branch_uses_synthetic_cash_on_both_sides():
    vendors = [None, None, "tiingo"]
    starts = pd.Series(pd.to_datetime(["2007-04-02", "2007-05-01", "2007-06-01"]))
    ends = pd.Series(pd.to_datetime(["2007-05-01", "2007-06-01", "2007-07-02"]))
    tri = pd.Series([1.0, 1.01], index=pd.to_datetime(["2007-06-01", "2007-07-02"]))
    bil = gate.etf_leg_returns({"tiingo": tri}, vendors, starts, ends)
    c_syn = np.array([0.004, 0.0041, 0.0042])
    filled = np.where(np.isnan(bil), c_syn, bil)
    assert filled[0] == 0.004 and filled[1] == 0.0041 and filled[2] == pytest.approx(0.01)
    # with synthetic cash on both sides, g is the duration-leg gap alone
    d_syn, ief = np.array([0.01, 0.02, 0.0]), np.array([0.011, 0.018, 0.0])
    g = (d_syn - c_syn) - (ief - filled)
    assert g[:2] == pytest.approx(d_syn[:2] - ief[:2])


# --- test 4: vendor per holding period ---------------------------------------------------


def test_vendor_rule_prefers_alpaca_only_when_it_covers_both_ends():
    alpaca = pd.DatetimeIndex(pd.bdate_range("2016-01-04", "2016-03-31"))
    tiingo = pd.DatetimeIndex(pd.bdate_range("2015-11-02", "2016-03-31"))
    starts = pd.Series(pd.to_datetime(["2015-11-02", "2015-12-01", "2016-01-04", "2016-02-01"]))
    ends = pd.Series(pd.to_datetime(["2015-12-01", "2016-01-04", "2016-02-01", "2016-03-01"]))
    chosen = gate.choose_vendor(starts, ends, {"alpaca": alpaca, "tiingo": tiingo}, ("alpaca", "tiingo"))
    assert chosen == ["tiingo", "tiingo", "alpaca", "alpaca"]  # December 2015 stays with one vendor
    none = gate.choose_vendor(starts[:1], ends[:1], {"alpaca": alpaca, "tiingo": alpaca}, ("alpaca", "tiingo"))
    assert none == [None]


# --- test 5: the volatility check writes sigma and the MDE only --------------------------


def test_volatility_check_keys_and_mde(tmp_path):
    x = np.tile([0.02, -0.02], 300)[:593]
    v = volcheck.volatility(x)
    assert v["sigma_annual"] == pytest.approx(np.std(x, ddof=1) * np.sqrt(12))
    assert v["mde_annual"] == pytest.approx(0.02 * v["sigma_annual"] / VOL_BAR)
    assert ("low-power" in v["consequence"]) == (v["sigma_annual"] > VOL_BAR)
    out = tmp_path / "volcheck"
    volcheck.write(v, out)
    written = json.loads((out / "volcheck.json").read_text())
    assert tuple(written) == volcheck.OUTPUT_KEYS
    with pytest.raises(SystemExit):
        volcheck.write(v, out)  # once only


def test_volatility_check_refuses_without_a_passed_gate(tmp_path):
    assert not volcheck.gate_passed(tmp_path)
    (tmp_path / "gate.json").write_text(json.dumps({"outcome": "FAIL: study halts as inconclusive (§5.3.6)"}))
    assert not volcheck.gate_passed(tmp_path)
    (tmp_path / "gate.json").write_text(json.dumps({"outcome": "PASS"}))
    assert volcheck.gate_passed(tmp_path)


# --- test 6: h uses nothing after the signal date ----------------------------------------


def test_holdings_ignore_data_after_the_signal_date():
    from src import signal

    days = pd.bdate_range("2003-01-01", "2003-06-30")
    rng = np.random.default_rng(8)
    dgs10 = pd.Series(4.0 + rng.normal(0, 0.3, len(days)), index=days)
    dtb3 = pd.Series(4.0 + rng.normal(0, 0.3, len(days)), index=days)
    signal_dates = dgs10.groupby(days.to_period("M")).apply(lambda s: s.index[-1])
    months = signal_dates.index[:-1]
    h = gate.holdings(signal.t1(dgs10, dtb3, signal_dates), months)
    for i, d in enumerate(signal_dates.iloc[:-1]):
        perturbed = dgs10.copy()
        perturbed.loc[perturbed.index > d] = -5.0
        h_p = gate.holdings(signal.t1(perturbed, dtb3, signal_dates), months)
        assert (h_p[: i + 1] == h[: i + 1]).all()


# --- the gate's period returns follow the engine's convention ----------------------------


def test_period_returns_match_the_engine():
    days = pd.bdate_range("2003-01-01", "2003-12-31")
    tri = pd.Series(np.cumprod(1 + np.random.default_rng(9).normal(0.0002, 0.003, len(days))), index=days)
    schedule = pd.DataFrame(
        {"execution_date": pd.to_datetime(["2003-01-02", "2003-02-03", "2003-03-03", "2003-04-01"])},
        index=pd.period_range("2002-12", "2003-03", freq="M"),
    )
    schedule["period_end"] = schedule["execution_date"].shift(-1)
    periods = schedule.iloc[:-1]
    ours = gate.period_returns(tri, periods["execution_date"], periods["period_end"])
    assert ours == pytest.approx(backtest.holding_period_returns(tri, schedule).to_numpy(), abs=0, rel=1e-15)


# --- reproduce.sh gates (replace Study 002's four tests of its own script) ----------------


@pytest.mark.parametrize("flag", ["--gate", "--volcheck", "--history", "--episode"])
def test_reproduce_refuses_without_approval(flag, tmp_path):
    copy = tmp_path / "study"
    copy.mkdir()
    (copy / "reproduce.sh").write_text((STUDY_DIR / "reproduce.sh").read_text())
    proc = subprocess.run(
        ["bash", "reproduce.sh", flag],
        cwd=copy,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": os.environ["PATH"]},
    )
    assert proc.returncode != 0 and "APPROVED" in proc.stdout + proc.stderr


@pytest.mark.parametrize(
    "flag,folder", [("--gate", "gate"), ("--volcheck", "volcheck"), ("--history", "history"), ("--episode", "episode")]
)
def test_reproduce_refuses_a_second_run(flag, folder, tmp_path):
    copy = tmp_path / "study"
    copy.mkdir()
    (copy / "reproduce.sh").write_text((STUDY_DIR / "reproduce.sh").read_text())
    (copy / "APPROVED").write_text("2099-01-01 test fixture, not an approval\n")
    (copy / "results" / folder).mkdir(parents=True)
    proc = subprocess.run(["bash", "reproduce.sh", flag], cwd=copy, capture_output=True, text=True)
    assert proc.returncode != 0 and f"results/{folder}" in proc.stdout + proc.stderr
