"""Study 007 §13 tests (1), (6), (7) and (8) for the gate and the volatility
check: import graph, G1 for a fractional weight on constructed series, the
decision rule of §5.3.3, the G2 reproduction check, the volatility output's
keys, and no look-ahead on every weight path.  Constructed data only; no
file in data/raw/ is read."""

import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from src import gate007, volcheck007
from src.calendar import build_schedule
from src.config import STUDY_DIR
from src.config007 import G1_MAX_007, G2_OBSERVED_006_FULL, MIN_HISTORY, TRIAL_IDS, VOL_BAR_007
from src.synthetic import synthetic_indices

SRC = STUDY_DIR / "src"


def _imports_of(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module.lstrip("."))
    return names


def _reachable(module: str, seen: set[str] | None = None) -> set[str]:
    seen = set() if seen is None else seen
    path = SRC / f"{module}.py"
    if module in seen or not path.exists():
        return seen
    seen.add(module)
    for name in _imports_of(path):
        local = name.split(".")[-1]
        if (SRC / f"{local}.py").exists():
            _reachable(local, seen)
    return seen


# --- test 1: the gate and the volatility check cannot see a rule return ------------------


@pytest.mark.parametrize("module", ["gate007", "volcheck007", "carry_rank"])
def test_gate_modules_never_reach_the_engines(module):
    reached = _reachable(module)
    assert not {"backtest", "tilt", "report", "stats"} & reached, reached


def test_gate_reaches_the_signal_modules():
    assert {"carry_rank", "signal", "synthetic", "calendar", "gate"} <= _reachable("gate007")


# --- test 6: G1 for a fractional w ----------------------------------------------------------


def test_constant_gap_gives_zero_bias_for_a_fractional_weight():
    rng = np.random.default_rng(70)
    w = rng.random(192)
    x_etf = rng.normal(0.002, 0.018, 192)
    s = gate007.fractional_gate(w, x_etf + 0.0004, x_etf)
    assert abs(s["mean_e_annual_signed"]) < 1e-15 and s["G1_pass"]
    assert s["mean_g_annual"] == pytest.approx(0.0048)
    assert "switches" not in s and s["turnover_one_way"] == pytest.approx(np.abs(np.diff(w)).sum())


def test_fractional_gate_known_answer_and_failure():
    w = np.array([0.25, 0.75, 1.0, 0.0])  # mean 0.5
    x_etf = np.array([0.01, -0.01, 0.02, -0.02])
    g = np.array([0.001, 0.003, -0.002, 0.0])
    s = gate007.fractional_gate(w, x_etf + g, x_etf)
    e = (w - 0.5) * g
    assert s["w_o"] == 0.5 and s["periods"] == 4
    assert s["G1_bias_annual"] == pytest.approx(abs(e.mean()) * 12)
    assert s["turnover_one_way"] == pytest.approx(0.5 + 0.25 + 1.0)
    rng = np.random.default_rng(71)
    w = rng.random(192)
    x_etf = rng.normal(0.0, 0.018, 192)
    bad = gate007.fractional_gate(w, x_etf + 0.003 * (w - 0.5), x_etf)  # gap that moves with the weight
    assert bad["G1_bias_annual"] > G1_MAX_007 and not bad["G1_pass"]
    with pytest.raises(ValueError):
        gate007.fractional_gate(np.array([0.5, np.nan]), x_etf[:2], x_etf[:2])


# --- §5.3.3: the decision rule --------------------------------------------------------------


def _stats(passes: dict[str, bool]) -> dict[str, dict]:
    return {k: {"G1_pass": passes.get(k, True)} for k in TRIAL_IDS}


def test_decision_passes_and_drops_failed_companions_and_secondaries():
    d = gate007.decide(_stats({}))
    assert d["outcome"] == "PASS" and d["dropped_trials"] == {} and d["proceeding_trials"] == list(TRIAL_IDS)
    d = gate007.decide(_stats({"T1a": False, "T3": False}))
    assert d["outcome"] == "PASS"
    assert d["dropped_trials"] == {"T1a": "inconclusive (gate)", "T3": "inconclusive (gate)"}
    assert d["proceeding_trials"] == ["T1", "T1b", "T2"]
    assert d["roles"] == {"T1": "primary", "T1a": "companion", "T1b": "companion", "T2": "secondary", "T3": "secondary"}


def test_decision_halts_when_the_primary_fails():
    d = gate007.decide(_stats({"T1": False}))
    assert d["outcome"].startswith("HALT") and "T1" in d["dropped_trials"] and d["outcome"] != "PASS"
    assert d["proceeding_trials"] == ["T1a", "T1b", "T2", "T3"]  # listed, but §5.3.3 halts the study before any run


# --- §5.3.2: G2 is inherited and must be reproduced -------------------------------------------


def test_g2_reproduction_check():
    ok = gate007.check_g2_reproduced(G2_OBSERVED_006_FULL)
    assert ok["abs_difference"] == 0.0 and ok["G2_pass"]
    assert gate007.check_g2_reproduced(G2_OBSERVED_006_FULL + 1e-13)["abs_difference"] < 1e-12
    with pytest.raises(ValueError, match="data step is wrong"):
        gate007.check_g2_reproduced(0.131)  # three decimals are not the committed precision
    with pytest.raises(ValueError):
        gate007.check_g2_reproduced(G2_OBSERVED_006_FULL + 1e-9)


# --- weight paths on constructed FRED series (§6, §5.5) ----------------------------------------


@pytest.fixture(scope="module")
def constructed():
    days = pd.bdate_range("1969-07-01", "1977-12-31")
    rng = np.random.default_rng(72)
    dgs10 = pd.Series(np.clip(6.0 + np.cumsum(rng.normal(0, 0.03, len(days))), 1.0, 15.0), index=days)
    dgs7 = (dgs10 - 0.2 + rng.normal(0, 0.05, len(days))).clip(lower=0.5)
    dtb3 = pd.Series(np.clip(5.0 + np.cumsum(rng.normal(0, 0.04, len(days))), 0.1, 15.0), index=days)
    schedule = build_schedule(dgs10, dtb3, "1969-07", "1977-11")
    indices = synthetic_indices(dgs10, dtb3, dgs7)
    return dgs10, dgs7, dtb3, schedule, indices


def test_weight_paths_shape_and_first_weights(constructed):
    dgs10, dgs7, dtb3, schedule, indices = constructed
    paths = gate007.weight_paths(dgs10, dgs7, dtb3, schedule, indices)
    assert paths.index.equals(schedule.index) and list(paths["n"]) == list(range(1, len(schedule) + 1))
    for trial, m in MIN_HISTORY.items():
        w = paths[f"w_{trial}"]
        assert w.iloc[: m - 1].isna().all()
        if m <= len(schedule):
            assert w.iloc[m - 1 :].notna().all() and ((w.dropna() >= 0) & (w.dropna() <= 1)).all()
    assert paths["w_T1"].first_valid_index() == schedule.index[59]
    assert paths["w_T1a"].first_valid_index() == schedule.index[35]
    assert paths["trend"].iloc[:12].isna().all() and paths["trend"].iloc[12:].isin([0.0, 1.0]).all()
    assert paths["w_T3"].equals(paths["trend"])
    valid = paths.dropna(subset=["w_T1", "trend"])
    assert np.allclose(valid["w_T2"], 0.5 * valid["w_T1"] + 0.5 * valid["trend"])


def test_rank_is_the_carry_percentile_on_the_same_row(constructed):
    dgs10, dgs7, dtb3, schedule, indices = constructed
    paths = gate007.weight_paths(dgs10, dgs7, dtb3, schedule, indices)
    c = paths["carry"].to_numpy()
    i = 70
    seen = c[: i + 1]
    expected = (np.count_nonzero(seen < c[i]) + 0.5 * np.count_nonzero(seen[:i] == c[i])) / i
    assert paths["w_T1"].iloc[i] == pytest.approx(expected)


def test_weight_paths_refuse_a_carry_gap(constructed):
    dgs10, dgs7, dtb3, schedule, indices = constructed
    broken = dgs7.copy()
    broken.loc[schedule["signal_date"].iloc[5]] = np.nan  # DGS7 missing on a later signal date: the frozen signal code refuses
    with pytest.raises(ValueError, match="undefined on signal dates"):
        gate007.weight_paths(dgs10, broken, dtb3, schedule, indices)
    late = dgs7.loc[schedule["signal_date"].iloc[0] + pd.Timedelta(days=1) :]  # no carry on the first row: it would be
    with pytest.raises(ValueError, match="m-th carry"):  # dropped silently by signal.t3, so the row count check fires
        gate007.weight_paths(dgs10, late, dtb3, schedule, indices)


def test_index_at_signal_dates_uses_the_last_value_on_or_before(constructed):
    *_, schedule, indices = constructed
    tri = indices["IEF"]
    on = gate007.index_at_signal_dates(tri, schedule["signal_date"])
    d = schedule["signal_date"].iloc[20]
    assert on.loc[d] == tri.loc[:d].iloc[-1]
    thinned = tri.drop(d)  # no observation on the signal date itself: the previous one is used
    assert gate007.index_at_signal_dates(thinned, schedule["signal_date"]).loc[d] == tri.loc[:d].iloc[-2]
    with pytest.raises(ValueError):
        gate007.index_at_signal_dates(tri.loc[schedule["signal_date"].iloc[3] :], schedule["signal_date"])


# --- test 8: no weight path uses anything after its signal date ----------------------------------


def test_no_weight_path_looks_ahead(constructed):
    dgs10, dgs7, dtb3, schedule, indices = constructed
    base = gate007.weight_paths(dgs10, dgs7, dtb3, schedule, indices)
    for i in (40, 65, 80):
        d = schedule["signal_date"].iloc[i]
        p10, p7, p3 = dgs10.copy(), dgs7.copy(), dtb3.copy()
        p10.loc[p10.index > d] = 12.0
        p7.loc[p7.index > d] = 3.0
        p3.loc[p3.index > d] = 0.5
        perturbed = gate007.weight_paths(p10, p7, p3, schedule, synthetic_indices(p10, p3, p7))
        cols = [f"w_{k}" for k in TRIAL_IDS] + ["carry", "trend"]
        pd.testing.assert_frame_equal(perturbed[cols].iloc[: i + 1], base[cols].iloc[: i + 1])


# --- test 7: the volatility check writes sigma, the count and the MDE only ----------------------


def test_volatility_check_output_keys_and_label(tmp_path):
    x = np.tile([0.02, -0.02], 300)[:534]
    v = volcheck007.volatility(x)
    assert v["periods"] == 534 and v["mde_annual"] == pytest.approx(0.02 * v["sigma_annual"] / VOL_BAR_007)
    out = tmp_path / "volcheck"
    volcheck007.write(v, out)
    written = json.loads((out / "volcheck.json").read_text())
    assert tuple(written) == volcheck007.OUTPUT_KEYS
    assert "Study 007" in (out / "volcheck.md").read_text()
    with pytest.raises(SystemExit):
        volcheck007.write(v, out)


def test_volatility_check_refuses_without_a_passed_gate(tmp_path):
    with pytest.raises(SystemExit, match="passed gate"):
        volcheck007.main([], gate_dir=tmp_path / "gate", out_dir=tmp_path / "volcheck")
    (tmp_path / "gate").mkdir()
    (tmp_path / "gate" / "gate.json").write_text(json.dumps(gate007.decide(_stats({"T1": False}))))
    with pytest.raises(SystemExit, match="passed gate"):
        volcheck007.main([], gate_dir=tmp_path / "gate", out_dir=tmp_path / "volcheck")
    assert not (tmp_path / "volcheck").exists()
