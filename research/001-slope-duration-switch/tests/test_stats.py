"""§9.3 and §9.4 statistics against hand-computed values and known limits."""
import math

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm
from src import stats
from src.config import DSR_VARIANCE_FLOOR, SEED


def test_sharpe_and_volatility_scaling():
    r = pd.Series([0.01, -0.01, 0.02, 0.0, 0.03, -0.02])
    assert stats.sharpe_annual(r) == pytest.approx(stats.sharpe_monthly(r) * math.sqrt(12))
    assert stats.annualised_volatility(r) == pytest.approx(r.std(ddof=1) * math.sqrt(12))
    assert stats.annualised_geometric_return(pd.Series([0.01] * 12)) == pytest.approx(1.01 ** 12 - 1)


def test_max_drawdown_on_a_known_path():
    tri = pd.Series([1.0, 1.2, 0.9, 1.0, 1.3, 1.17])
    assert stats.max_drawdown(tri) == pytest.approx(0.9 / 1.2 - 1)


def test_skewness_and_kurtosis_of_a_symmetric_two_point_distribution():
    x = pd.Series([1.0, -1.0] * 50)
    assert stats.skewness(x) == pytest.approx(0.0)
    assert stats.kurtosis(x) == pytest.approx(1.0)


def test_newey_west_t_matches_plain_t_without_autocorrelation_at_zero_lags():
    rng = np.random.default_rng(SEED)
    x = pd.Series(rng.normal(0.002, 0.01, 300))
    nw = stats.newey_west_mean(x, lags=0)
    plain_se = x.std(ddof=1) / math.sqrt(len(x))
    assert nw["mean"] == pytest.approx(x.mean())
    assert nw["t"] == pytest.approx(x.mean() / plain_se, rel=0.01)   # HAC uses a small-sample factor
    assert stats.newey_west_mean(x, lags=6)["lags"] == 6


def test_expected_max_sharpe_and_dsr_hand_computed():
    # N = 3, V = 0.02^2, gamma_E = 0.5772...
    z1 = norm.ppf(1 - 1 / 3)             # 0.4307
    z2 = norm.ppf(1 - 1 / (3 * math.e))  # 1.1613
    sr_star = 0.02 * ((1 - 0.5772156649) * z1 + 0.5772156649 * z2)
    assert stats.expected_max_sharpe(3, 0.02 ** 2) == pytest.approx(sr_star, rel=1e-9)
    assert sr_star == pytest.approx(0.017056, abs=1e-5)
    # SR = 0.10 monthly, T = 120, skew 0, kurtosis 3
    out = stats.deflated_sharpe(0.10, 120, 0.0, 3.0, 3, 0.02 ** 2)
    expected = norm.cdf((0.10 - sr_star) * math.sqrt(119) / math.sqrt(1 + 0.5 * 0.01))
    assert out["dsr"] == pytest.approx(expected, rel=1e-9)
    assert out["dsr"] == pytest.approx(0.8166, abs=2e-3)
    assert out["psr"] == pytest.approx(norm.cdf(0.10 * math.sqrt(119) / math.sqrt(1.005)), rel=1e-9)
    assert out["dsr"] < out["psr"]


def test_dsr_increases_with_fewer_trials_and_lower_variance():
    a = stats.deflated_sharpe(0.1, 200, 0.0, 3.0, 3, 1e-4)["dsr"]
    b = stats.deflated_sharpe(0.1, 200, 0.0, 3.0, 10, 1e-4)["dsr"]
    c = stats.deflated_sharpe(0.1, 200, 0.0, 3.0, 3, 4e-4)["dsr"]
    assert a > b and a > c


def test_trial_variance_floor():
    assert stats.trial_variance([0.1, 0.1, 0.1]) == (DSR_VARIANCE_FLOOR, True)
    v, floored = stats.trial_variance([0.0, 0.1, 0.2])
    assert v == pytest.approx(np.var([0.0, 0.1, 0.2])) and not floored


def test_bootstrap_indices_shapes_and_blocks():
    rng = np.random.default_rng(SEED)
    idx = stats.circular_block_indices(rng, 100, 7, 12)
    assert idx.shape == (7, 100) and idx.min() >= 0 and idx.max() < 100
    assert ((idx[:, 1:12] - idx[:, :11]) % 100 == 1).all()        # consecutive inside a block
    sb = stats.stationary_bootstrap_indices(rng, 100, 7, 12.0)
    assert sb.shape == (7, 100) and sb.min() >= 0 and sb.max() < 100
    steps = (sb[:, 1:] - sb[:, :-1]) % 100
    assert 0.6 < (steps == 1).mean() < 0.98                        # mostly continuations


def test_bootstraps_are_deterministic_under_the_seed():
    rng_a, rng_b = np.random.default_rng(SEED), np.random.default_rng(SEED)
    x = pd.Series(np.random.default_rng(3).normal(0.003, 0.02, 240))
    y = pd.Series(np.random.default_rng(4).normal(0.002, 0.02, 240))
    ci_a = stats.sharpe_ci_stationary_bootstrap(x, rng_a, n_resamples=500)
    ci_b = stats.sharpe_ci_stationary_bootstrap(x, rng_b, n_resamples=500)
    assert ci_a == ci_b
    assert ci_a["ci_low"] < ci_a["sharpe_annual"] < ci_a["ci_high"]
    lw_a = stats.ledoit_wolf_sharpe_test(x, y, rng_a, n_resamples=1000)
    lw_b = stats.ledoit_wolf_sharpe_test(x, y, rng_b, n_resamples=1000)
    assert lw_a == lw_b
    assert 0.0 <= lw_a["p_value"] <= 1.0
    population_sharpe = lambda s: s.mean() / s.std(ddof=0)   # Ledoit-Wolf use population moments
    assert lw_a["diff_monthly"] == pytest.approx(population_sharpe(x) - population_sharpe(y))
    assert lw_a["diff_annual"] == pytest.approx(lw_a["diff_monthly"] * math.sqrt(12))


def test_ledoit_wolf_identical_series_and_very_different_series():
    rng = np.random.default_rng(SEED)
    x = pd.Series(np.random.default_rng(5).normal(0.0, 0.02, 300))
    lw = stats.ledoit_wolf_sharpe_test(x, x + 0.01, rng, n_resamples=1000)
    assert lw["diff_monthly"] < 0 and lw["p_value"] < 0.01
    with pytest.raises(ValueError):
        stats.ledoit_wolf_sharpe_test(x, x.iloc[:-1], rng)


def test_inverted_episodes():
    flags = pd.Series([False, True, True, False, True, False, False, True, True, True])
    out = stats.inverted_episodes(flags)
    assert out == {"months": 6, "episodes": 3, "mean_episode_length": 2.0}
    assert math.isnan(stats.inverted_episodes(pd.Series([False, False]))["mean_episode_length"])
