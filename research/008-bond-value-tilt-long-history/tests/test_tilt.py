"""Study 007 §13 test (4) and (5): the fractional-weight engine equals the
frozen switching engine on a 0/1 path and the frozen static benchmark on a
constant path (from the second period), with and without costs; the turnover
statistic; the mean weight."""

import numpy as np
import pandas as pd
import pytest
from src import tilt
from src.backtest import run_static, run_switching
from src.config import CASH_LEG, DURATION_LEG


def _returns(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.period_range("1974-07", periods=n, freq="M").astype(str)
    return pd.DataFrame({DURATION_LEG: rng.normal(0.004, 0.02, n), CASH_LEG: rng.normal(0.004, 0.001, n)}, index=idx)


@pytest.mark.parametrize("cost", [0.0, 0.0002, 0.0004])
def test_zero_one_path_reproduces_the_switching_engine(cost):
    returns = _returns(120, seed=11)
    rng = np.random.default_rng(5)
    path = rng.integers(0, 2, size=120).astype(float)
    weights = pd.Series(path, index=returns.index)
    targets = pd.Series(np.where(path == 1.0, DURATION_LEG, CASH_LEG), index=returns.index)
    ours = tilt.run_tilt(weights, returns, cost)
    frozen = run_switching(targets, returns, cost)
    np.testing.assert_allclose(ours["r"].to_numpy(), frozen["r"].to_numpy(), rtol=0, atol=1e-15)
    np.testing.assert_allclose(ours["r_gross"].to_numpy(), frozen["r_gross"].to_numpy(), rtol=0, atol=1e-15)
    np.testing.assert_allclose(ours["cost"].to_numpy(), frozen["cost"].to_numpy(), rtol=0, atol=1e-15)
    assert (ours["traded_fraction"] == frozen["switched"].astype(float)).all()


@pytest.mark.parametrize("cost", [0.0, 0.0002])
@pytest.mark.parametrize("w", [0.0, 0.3, 0.8702, 1.0])
def test_constant_path_reproduces_the_static_benchmark_from_the_second_period(w, cost):
    returns = _returns(96, seed=2)
    ours = tilt.run_tilt(pd.Series(w, index=returns.index), returns, cost)
    frozen = run_static(w, returns, cost)
    np.testing.assert_allclose(ours["r"].to_numpy()[1:], frozen["r"].to_numpy()[1:], rtol=0, atol=1e-15)
    np.testing.assert_allclose(ours["traded_fraction"].to_numpy()[1:], frozen["traded_fraction"].to_numpy()[1:],
                               rtol=0, atol=1e-15)
    # the first period: the static benchmark charges nothing, the engine pays the first purchase (§6.5)
    assert ours["traded_fraction"].iloc[0] == w and frozen["traded_fraction"].iloc[0] == 0.0
    assert ours["r_gross"].iloc[0] == pytest.approx(frozen["r_gross"].iloc[0])


def test_drift_moves_the_weight_with_the_legs_relative_return():
    returns = pd.DataFrame({DURATION_LEG: [0.10, 0.0], CASH_LEG: [0.0, 0.0]}, index=["a", "b"])
    out = tilt.run_tilt(pd.Series([0.5, 0.5], index=returns.index), returns, 0.0)
    # after +10% on the leg and 0 on cash, half-and-half drifts to 0.55/1.05
    assert out["drifted_from"].iloc[1] == pytest.approx(0.55 / 1.05)
    assert out["traded_fraction"].iloc[1] == pytest.approx(abs(0.5 - 0.55 / 1.05))


def test_costs_are_charged_on_the_traded_fraction_only():
    returns = pd.DataFrame({DURATION_LEG: [0.0, 0.0, 0.0], CASH_LEG: [0.0, 0.0, 0.0]}, index=list("abc"))
    out = tilt.run_tilt(pd.Series([0.25, 0.25, 1.0], index=returns.index), returns, 0.01)
    assert out["cost"].iloc[0] == pytest.approx(1 - (1 - 0.01 * 0.25) ** 2)
    assert out["cost"].iloc[1] == 0.0
    assert out["cost"].iloc[2] == pytest.approx(1 - (1 - 0.01 * 0.75) ** 2)
    assert tilt.total_turnover(out) == pytest.approx(1.0)


def test_engine_refuses_missing_or_out_of_range_weights():
    returns = _returns(3, seed=1)
    with pytest.raises(ValueError):
        tilt.run_tilt(pd.Series([0.5, np.nan, 0.5], index=returns.index), returns, 0.0)
    with pytest.raises(ValueError):
        tilt.run_tilt(pd.Series([0.5, 1.5, 0.5], index=returns.index), returns, 0.0)


def test_mean_weight_ignores_undefined_months():
    assert tilt.mean_weight(pd.Series([np.nan, 0.2, 0.6])) == pytest.approx(0.4)
    with pytest.raises(ValueError):
        tilt.mean_weight(pd.Series([np.nan]))
