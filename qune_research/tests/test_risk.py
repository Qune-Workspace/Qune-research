"""Risk model checks on constructed data: covariance forecasts, portfolio
volatility, Euler contributions, VaR/ES, stress windows, drawdown control
and forecast accuracy.  No vendor data."""
import numpy as np
import pandas as pd
import pytest
from scipy import stats as sps

from qune_research import risk


def _returns(n=2000, seed=1, rho=0.5, vols=(0.16, 0.08, 0.24)):
    rng = np.random.default_rng(seed)
    k = len(vols)
    corr = np.full((k, k), rho)
    np.fill_diagonal(corr, 1.0)
    sd = np.asarray(vols) / np.sqrt(risk.TRADING_DAYS)
    cov = corr * np.outer(sd, sd)
    x = rng.multivariate_normal(np.zeros(k), cov, size=n)
    idx = pd.bdate_range("2010-01-01", periods=n)
    return pd.DataFrame(x, index=idx, columns=list("ABC")[:k]), pd.DataFrame(cov * risk.TRADING_DAYS, index=list("ABC")[:k], columns=list("ABC")[:k])


def test_ewma_with_long_halflife_approaches_sample_covariance():
    r, true = _returns()
    ew = risk.ewma_covariance(r, halflife_days=1e6)
    samp = risk.sample_covariance(r)
    assert np.allclose(ew.to_numpy(), samp.to_numpy(), rtol=0.02, atol=1e-4)
    assert np.allclose(ew.to_numpy(), true.to_numpy(), rtol=0.15, atol=2e-3)


def test_ewma_weights_recent_rows_more():
    idx = pd.bdate_range("2010-01-01", periods=400)
    rng = np.random.default_rng(3)
    quiet = rng.normal(0, 0.005, 300)
    loud = rng.normal(0, 0.02, 100)
    r = pd.DataFrame({"A": np.concatenate([quiet, loud])}, index=idx)
    short = risk.ewma_covariance(r, halflife_days=10).iloc[0, 0]
    long = risk.ewma_covariance(r, halflife_days=400).iloc[0, 0]
    assert short > long
    assert np.sqrt(short) == pytest.approx(0.02 * np.sqrt(252), rel=0.2)


def test_ewma_rejects_bad_inputs():
    r, _ = _returns(n=10)
    with pytest.raises(ValueError):
        risk.ewma_covariance(r, halflife_days=0)
    with pytest.raises(ValueError):
        risk.ewma_covariance(r.iloc[:1], halflife_days=5)


def test_constant_correlation_target_keeps_variances_and_sets_mean_correlation():
    _, true = _returns()
    f = risk.constant_correlation_target(true)
    assert np.allclose(np.diag(f), np.diag(true))
    sd = np.sqrt(np.diag(f.to_numpy()))
    corr = f.to_numpy() / np.outer(sd, sd)
    off = corr[~np.eye(3, dtype=bool)]
    assert np.allclose(off, 0.5)


def _heterogeneous_returns(n, seed=5):
    """Correlations that differ by pair, so the constant-correlation target
    is not the truth and the intensity must fall as the sample grows."""
    rng = np.random.default_rng(seed)
    corr = np.array([[1.0, 0.8, 0.1], [0.8, 1.0, -0.3], [0.1, -0.3, 1.0]])
    sd = np.array([0.16, 0.08, 0.24]) / np.sqrt(risk.TRADING_DAYS)
    x = rng.multivariate_normal(np.zeros(3), corr * np.outer(sd, sd), size=n)
    return pd.DataFrame(x, columns=list("ABC"))


def test_ledoit_wolf_intensity_in_unit_interval_and_shrinks_less_with_more_data():
    d = [risk.ledoit_wolf_intensity(_heterogeneous_returns(n)) for n in (30, 120, 1000, 4000)]
    assert all(0.0 <= x <= 1.0 for x in d)
    assert d[0] > d[1] > d[2] > d[3]
    assert d[3] < 0.01
    assert risk.ledoit_wolf_intensity(_heterogeneous_returns(60)[["A"]]) == 0.0


def test_ledoit_wolf_intensity_is_one_when_the_target_is_the_truth():
    # every pair at the same correlation: the target is the data-generating
    # matrix, so full shrinkage is optimal and the estimate says so
    r, _ = _returns(n=4000, seed=5)
    assert risk.ledoit_wolf_intensity(r) == 1.0


def test_shrink_is_a_convex_combination_and_rejects_bad_intensity():
    _, true = _returns()
    f = risk.constant_correlation_target(true)
    assert np.allclose(risk.shrink(true, 0.0).to_numpy(), true.to_numpy())
    assert np.allclose(risk.shrink(true, 1.0).to_numpy(), f.to_numpy())
    mid = risk.shrink(true, 0.3)
    assert np.allclose(mid.to_numpy(), 0.7 * true.to_numpy() + 0.3 * f.to_numpy())
    with pytest.raises(ValueError):
        risk.shrink(true, 1.5)


def test_shrunk_ewma_is_positive_semidefinite():
    r, _ = _returns(n=300, seed=7)
    cov, delta = risk.shrunk_ewma_covariance(r, halflife_days=42)
    assert 0.0 <= delta <= 1.0
    assert np.all(np.linalg.eigvalsh(cov.to_numpy()) > -1e-12)


def test_diagonal_zeroes_off_diagonal_only():
    _, true = _returns()
    d = risk.diagonal(true)
    assert np.allclose(np.diag(d), np.diag(true))
    assert np.allclose(d.to_numpy() - np.diag(np.diag(d.to_numpy())), 0.0)


def test_portfolio_vol_single_asset_and_uncorrelated_pair():
    cov = pd.DataFrame(np.diag([0.16 ** 2, 0.08 ** 2]), index=["A", "B"], columns=["A", "B"])
    assert risk.portfolio_vol({"A": 1.0}, cov) == pytest.approx(0.16)
    assert risk.portfolio_vol({"A": 0.5, "B": 0.5}, cov) == pytest.approx(np.sqrt(0.25 * 0.16 ** 2 + 0.25 * 0.08 ** 2))
    assert risk.portfolio_vol({}, cov) == 0.0
    with pytest.raises(ValueError):
        risk.portfolio_vol({"Z": 1.0}, cov)


def test_correlation_raises_portfolio_vol_above_diagonal_forecast():
    _, true = _returns()
    w = {"A": 0.3, "B": 0.3, "C": 0.3}
    assert risk.portfolio_vol(w, true) > risk.portfolio_vol(w, risk.diagonal(true))


def test_risk_contributions_sum_to_one_and_are_symmetric():
    _, true = _returns(vols=(0.16, 0.16, 0.16))
    rc = risk.risk_contributions({"A": 0.2, "B": 0.2, "C": 0.2}, true)
    assert rc.sum() == pytest.approx(1.0)
    assert np.allclose(rc.to_numpy(), 1 / 3)
    single = risk.risk_contributions({"A": 0.5}, true)
    assert single["A"] == pytest.approx(1.0) and single["B"] == 0.0
    assert (risk.risk_contributions({}, true) == 0.0).all()


def test_parametric_var_es_match_the_normal_formulas():
    cov = pd.DataFrame([[0.01 ** 2]], index=["A"], columns=["A"])
    out = risk.parametric_var_es({"A": 1.0}, cov, level=0.99, horizon_days=4)
    sigma = 0.02
    z = sps.norm.ppf(0.99)
    assert out["vol_horizon"] == pytest.approx(sigma)
    assert out["var"] == pytest.approx(sigma * z)
    assert out["es"] == pytest.approx(sigma * sps.norm.pdf(z) / 0.01)
    assert out["es"] > out["var"]


def test_historical_var_es_on_known_sample():
    r = pd.Series(np.arange(-100, 100) / 1000.0)
    out = risk.historical_var_es(r, level=0.95)
    assert out["n"] == 200
    assert out["var"] == pytest.approx(-np.quantile(r, 0.05))
    assert out["es"] >= out["var"]
    assert out["n_tail"] == 10


def test_stress_window_returns_are_weighted_leg_sums():
    idx = pd.bdate_range("2020-01-01", periods=60)
    prices = pd.DataFrame({"A": np.linspace(100, 80, 60), "B": np.linspace(50, 55, 60)}, index=idx)
    cash = pd.Series(np.linspace(1.0, 1.01, 60), index=idx)
    win = {"w": (str(idx[9].date()), str(idx[49].date()))}
    out = risk.stress_window_returns(prices, {"A": 0.5, "B": 0.25}, win, cash)
    ra = prices["A"].iloc[49] / prices["A"].iloc[9] - 1
    rb = prices["B"].iloc[49] / prices["B"].iloc[9] - 1
    rc = cash.iloc[49] / cash.iloc[9] - 1
    assert out.loc["w", "leg_A"] == pytest.approx(0.5 * ra)
    assert out.loc["w", "total"] == pytest.approx(0.5 * ra + 0.25 * rb + 0.25 * rc)


def test_stress_window_before_an_asset_exists_is_nan_not_partial():
    idx = pd.bdate_range("2020-01-01", periods=60)
    a = pd.Series(np.linspace(100, 80, 60), index=idx)
    b = a.copy()
    b.iloc[:30] = np.nan
    prices = pd.DataFrame({"A": a, "B": b})
    out = risk.stress_window_returns(prices, {"A": 0.5, "B": 0.5}, {"early": ("2020-01-10", "2020-02-10")})
    assert np.isnan(out.loc["early", "total"])


def test_drawdown_multiplier_is_linear_bounded_and_vectorised():
    assert risk.drawdown_multiplier(0.0, 0.10) == 1.0
    assert risk.drawdown_multiplier(-0.05, 0.10) == pytest.approx(0.5)
    assert risk.drawdown_multiplier(-0.20, 0.10) == 0.0
    assert risk.drawdown_multiplier(-0.20, 0.10, floor=0.25) == 0.25
    idx = pd.Series([1.0, 1.1, 1.0, 0.99, 1.2])
    dd = risk.drawdown_from_high(idx)
    assert dd.iloc[2] == pytest.approx(1.0 / 1.1 - 1)
    m = risk.drawdown_multiplier(dd, 0.20)   # the trough is a 10% drawdown, half the limit
    assert m.iloc[0] == 1.0 and m.iloc[4] == 1.0 and m.iloc[3] == pytest.approx(0.5, abs=1e-6)
    with pytest.raises(ValueError):
        risk.drawdown_multiplier(-0.1, 0.0)


def test_forecast_accuracy_identity_and_scale():
    f = pd.Series([0.1, 0.2, 0.3], index=[1, 2, 3])
    out = risk.forecast_accuracy(f, f)
    assert out["n"] == 3 and out["mean_ratio"] == pytest.approx(1.0)
    assert out["mean_log_ratio"] == pytest.approx(0.0) and out["slope_through_origin"] == pytest.approx(1.0)
    out2 = risk.forecast_accuracy(f, 2.0 * f)
    assert out2["mean_ratio"] == pytest.approx(2.0) and out2["share_over_factor"] == 1.0
    assert risk.forecast_accuracy(f * 0, f)["n"] == 0
