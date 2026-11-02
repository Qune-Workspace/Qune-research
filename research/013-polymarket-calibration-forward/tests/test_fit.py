"""Tests of the Study 013 scoring estimator (PREREGISTRATION.md §6.6), on synthetic data only.

No file, snapshot, outcome or network is touched: every sample is drawn here with a fixed seed.
The checks §6.6 names for the estimator: the MLE against a closed-form two-point design; against
an independent implementation (statsmodels) on one synthetic sample to 1e-8; the clustered
standard error with one member per cluster; plus the bootstrap, the criteria, the reliability
bins, the power row and the scores.
"""

from __future__ import annotations

import numpy as np
import pytest
from src import fit

SEED = 20261102


def sample(n: int = 4000, b_true: float = 1.15, a_true: float = 0.0, clusters: int = 800, seed: int = SEED):
    """Markets with p drawn uniform on [0.02, 0.98] and y from the (a, b) model, grouped into clusters."""
    rng = np.random.default_rng(seed)
    p = rng.uniform(0.02, 0.98, size=n)
    x = fit.logit(p)
    pi = 1.0 / (1.0 + np.exp(-(a_true + b_true * x)))
    y = (rng.uniform(size=n) < pi).astype(float)
    g = rng.integers(0, clusters, size=n)
    return p, x, y, g


def test_two_point_design_matches_closed_form():
    # x in {-c, +c}; the saturated model fits the two group frequencies exactly:
    # a + b c = logit(q_plus), a - b c = logit(q_minus).
    c = 1.3
    n_plus, n_minus = 400, 600
    k_plus, k_minus = 300, 150
    x = np.concatenate([np.full(n_plus, c), np.full(n_minus, -c)])
    y = np.concatenate([np.ones(k_plus), np.zeros(n_plus - k_plus), np.ones(k_minus), np.zeros(n_minus - k_minus)])
    f = fit.fit_logistic(x, y)
    q_plus, q_minus = k_plus / n_plus, k_minus / n_minus
    lp, lm = np.log(q_plus / (1 - q_plus)), np.log(q_minus / (1 - q_minus))
    assert f.converged
    assert f.b == pytest.approx((lp - lm) / (2 * c), abs=1e-8)
    assert f.a == pytest.approx((lp + lm) / 2, abs=1e-8)
    # the fitted log-likelihood equals the saturated two-group log-likelihood
    sat = k_plus * np.log(q_plus) + (n_plus - k_plus) * np.log(1 - q_plus) + k_minus * np.log(q_minus) + (n_minus - k_minus) * np.log(1 - q_minus)
    assert f.loglik == pytest.approx(sat, abs=1e-8)


def test_against_independent_implementation_to_1e8():
    sm = pytest.importorskip("statsmodels.api")
    p, x, y, g = sample()
    f = fit.fit_logistic(x, y)
    assert f.converged
    exog = np.column_stack([np.ones(x.size), x])
    res = sm.Logit(y, exog).fit(method="newton", tol=1e-12, maxiter=200, disp=0)
    assert f.a == pytest.approx(res.params[0], abs=1e-8)
    assert f.b == pytest.approx(res.params[1], abs=1e-8)
    assert f.loglik == pytest.approx(res.llf, abs=1e-8)
    assert f.se_ordinary_b == pytest.approx(res.bse[1], rel=1e-6)
    # clustered sandwich: statsmodels' raw cluster covariance (no small-sample factor) times G/(G - 1)
    v, g_count = fit.clustered_cov(f, x, y, g)
    res_cl = sm.Logit(y, exog).fit(method="newton", tol=1e-12, maxiter=200, disp=0,
                                   cov_type="cluster", cov_kwds={"groups": g, "use_correction": False})
    assert g_count == np.unique(g).size
    assert v[1, 1] == pytest.approx(res_cl.cov_params()[1, 1] * g_count / (g_count - 1), rel=1e-6)


def test_singleton_clusters_equal_the_unclustered_sandwich_and_agree_with_ordinary_in_expectation():
    p, x, y, _ = sample(n=20000, clusters=1)
    f = fit.fit_logistic(x, y)
    singles = np.arange(x.size)
    v, g_count = fit.clustered_cov(f, x, y, singles)
    assert g_count == x.size
    # exact: with one member per cluster the meat is sum_i s_i s_i^T (HC0), times n/(n - 1)
    z = np.column_stack([np.ones(x.size), x])
    pi = 1.0 / (1.0 + np.exp(-(f.a + f.b * x)))
    s = (y - pi)[:, None] * z
    hc0 = f.hessian_inv @ (s.T @ s) @ f.hessian_inv
    assert np.allclose(v, hc0 * x.size / (x.size - 1), rtol=1e-12, atol=0)
    # in expectation under the correctly specified model: the robust and the model-based SE agree
    se_cl, _ = fit.se_clustered_b(f, x, y, singles)
    assert se_cl == pytest.approx(f.se_ordinary_b, rel=0.05)
    assert se_cl != f.se_ordinary_b  # and not identically: the pre-registration's §6.6 sentence is read as above


def test_clustering_widens_the_interval_when_outcomes_share_a_cluster_shock():
    rng = np.random.default_rng(SEED + 1)
    n, clusters = 6000, 300
    g = rng.integers(0, clusters, size=n)
    shock = rng.normal(0, 0.6, size=clusters)[g]  # a cluster-level slope shock: logit Pr = x (1 + shock)
    p = rng.uniform(0.05, 0.95, size=n)
    x = fit.logit(p)
    pi = 1.0 / (1.0 + np.exp(-(x * (1.0 + shock))))
    y = (rng.uniform(size=n) < pi).astype(float)
    f = fit.fit_logistic(x, y)
    se_cl, _ = fit.se_clustered_b(f, x, y, g)
    assert se_cl > 1.4 * f.se_ordinary_b


def test_separated_data_is_reported_not_raised():
    # the §9.3 stop rule fires on separated data (the log-likelihood tends to 0), so the separation
    # check is what marks the fit as no fit: found when the first draft reported b = 410 as converged
    x = np.linspace(-3, 3, 50)
    y = (x > 0).astype(float)
    f = fit.fit_logistic(x, y)
    assert f.separated
    assert not f.converged
    assert f.iterations >= 1
    assert f.b > 10
    assert not fit.criteria(b=f.b, se_cl=f.se_ordinary_b, b_w1=2.0, b_w2=2.0, converged=f.converged)["all"]
    # a well-posed sample is not flagged
    _, x2, y2, _ = sample(n=500)
    assert not fit.fit_logistic(x2, y2).separated


def test_input_checks():
    with pytest.raises(ValueError):
        fit.fit_logistic(np.array([0.1, 0.2]), np.array([0.0, 2.0]))
    with pytest.raises(ValueError):
        fit.fit_logistic(np.array([0.1, 0.2]), np.array([0.0]))


def test_bootstrap_is_reproducible_and_brackets_the_estimate():
    p, x, y, g = sample(n=1500, clusters=200)
    f = fit.fit_logistic(x, y)
    one = fit.cluster_bootstrap(x, y, g, resamples=200)
    two = fit.cluster_bootstrap(x, y, g, resamples=200)
    assert (one.low, one.high, one.dropped) == (two.low, two.high, two.dropped)
    assert one.low < f.b < one.high
    assert one.dropped == 0 and one.available
    se_cl, _ = fit.se_clustered_b(f, x, y, g)
    assert (one.high - one.low) / (2 * 1.96 * se_cl) == pytest.approx(1.0, abs=0.35)


def test_bootstrap_counts_dropped_resamples_and_withholds_the_interval():
    # three clusters; the only y = 1 rows sit in cluster 0, so a resample without it holds one outcome only
    x = np.array([-1.0, 1.0, -0.5, 0.5, -1.5, 1.5, -0.2, 0.2])
    y = np.array([1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    g = np.array([0, 0, 1, 1, 2, 2, 1, 2])
    out = fit.cluster_bootstrap(x, y, g, resamples=100, seed=13)
    assert out.dropped > 1  # (2/3)^3 of resamples lack cluster 0; others separate and do not converge
    assert not out.available


def test_criteria_and_verdict_precedence():
    c = fit.criteria(b=1.05, se_cl=0.02, b_w1=1.03, b_w2=1.06)
    assert c["t_cl"] == pytest.approx(2.5)
    assert c["C1"] and c["C2"] and c["C3"] and c["C4"] and c["all"]
    assert not fit.criteria(b=1.019, se_cl=0.001, b_w1=1.1, b_w2=1.1)["C1"]  # margin 0.02
    c = fit.criteria(b=1.04, se_cl=0.019, b_w1=1.1, b_w2=1.1)  # t = 2.105: C2 yes, C3 (2.128) no
    assert c["C2"] and not c["C3"] and not c["all"]
    assert not fit.criteria(b=1.05, se_cl=0.02, b_w1=1.03, b_w2=0.99)["C4"]
    assert not fit.criteria(b=1.05, se_cl=0.02, b_w1=1.03, b_w2=1.06, converged=False)["all"]
    assert fit.headline_verdict(True, True, False, True) == "inconclusive (halted at the data step)"
    assert fit.headline_verdict(False, True, False, False) == "not supported"
    assert fit.headline_verdict(True, False, False, False) == "not supported"
    assert fit.headline_verdict(True, True, True, False) == "inconclusive (fragile: Sports)"
    assert fit.headline_verdict(True, True, False, False) == "supported in one forward window"


def test_power_row_reproduces_the_question_note_decision_row():
    # uniform p on [0.02, 0.98]: E = 0.2159 (QUESTION.md §2); G = 44,694 clusters: MDE 0.0289, ratio 0.26
    grid = np.linspace(0.02, 0.98, 200001)
    row = fit.power_row(grid, 44694)
    assert row["E_hat"] == pytest.approx(0.2159, abs=5e-4)
    assert row["mde_programme"] == pytest.approx(0.0289, abs=2e-4)
    assert row["ratio"] == pytest.approx(0.26, abs=0.005)
    assert row["low_power"] == 0.0
    assert fit.power_row(grid, 2000)["ratio"] == pytest.approx(1.22, abs=0.01)  # §5.4's halt figure
    assert fit.power_row(grid, 2000)["low_power"] == 1.0


def test_reliability_bins_edges_and_interval():
    p = np.array([0.01, 0.099, 0.10, 0.5, 0.899, 0.90, 0.99, 0.95])
    y = np.array([0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0])
    g = np.arange(p.size)
    rows = fit.reliability_table(p, y, g)
    assert len(rows) == 10
    # 0.01 and 0.099 in the first bin; 0.10 opens the second; 0.5 opens the sixth; 0.899 in the ninth;
    # 0.90, 0.95 and 0.99 in the last (closed) bin
    assert [r["n"] for r in rows] == [2, 1, 0, 0, 0, 1, 0, 0, 1, 3]
    last = rows[-1]
    assert last["mean_p"] == pytest.approx((0.90 + 0.99 + 0.95) / 3)
    assert last["outcome_share"] == pytest.approx(2 / 3)
    assert last["diff_pp"] == pytest.approx(100 * (2 / 3 - (0.90 + 0.99 + 0.95) / 3))
    assert last["ci_low_pp"] < last["diff_pp"] < last["ci_high_pp"]
    assert np.isnan(rows[2]["mean_p"])


def test_scores_by_hand():
    p = np.array([0.8, 0.3, 0.6, 0.1])
    y = np.array([1.0, 0.0, 0.0, 0.0])
    s = fit.scores(p, y)
    assert s["brier"] == pytest.approx((0.04 + 0.09 + 0.36 + 0.01) / 4)
    assert s["base_rate"] == 0.25
    assert s["brier_base"] == pytest.approx((0.5625 + 3 * 0.0625) / 4)
    assert s["log_loss"] == pytest.approx(-(np.log(0.8) + np.log(0.7) + np.log(0.4) + np.log(0.9)) / 4)
    assert s["brier_skill"] == pytest.approx(1 - s["brier"] / s["brier_base"])
