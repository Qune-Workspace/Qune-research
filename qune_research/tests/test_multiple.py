"""Tests for qune_research.multiple on constructed data."""
from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.stats import norm

from qune_research.multiple import min_track_record_length, reality_check, spa_test
from qune_research.stats import probabilistic_sharpe

# --- MinTRL ---------------------------------------------------------------------

def test_mintrl_closed_form_under_normality():
    sr, z = 0.25, norm.ppf(0.95)
    expected = 1.0 + (1.0 + 0.5 * sr ** 2) * (z / sr) ** 2
    assert min_track_record_length(sr, 0.0, 3.0, 0.0, 0.95) == pytest.approx(expected)


def test_mintrl_is_where_psr_reaches_the_confidence():
    sr, skew, kurt, bench, conf = 0.2, -0.4, 5.0, 0.05, 0.9
    n = min_track_record_length(sr, skew, kurt, bench, conf)
    assert probabilistic_sharpe(sr, n, skew, kurt, bench) == pytest.approx(conf, abs=1e-9)


def test_mintrl_orderings():
    assert math.isinf(min_track_record_length(0.1, 0.0, 3.0, 0.1))
    assert math.isinf(min_track_record_length(0.1, 0.0, 3.0, 0.2))
    assert min_track_record_length(0.2, 0.0, 3.0, 0.0, 0.99) > min_track_record_length(0.2, 0.0, 3.0, 0.0, 0.95)
    assert min_track_record_length(0.4, 0.0, 3.0) < min_track_record_length(0.2, 0.0, 3.0)
    # fatter tails lengthen the record needed
    assert min_track_record_length(0.2, 0.0, 9.0) > min_track_record_length(0.2, 0.0, 3.0)
    with pytest.raises(ValueError):
        min_track_record_length(0.2, 0.0, 3.0, 0.0, 1.0)


# --- Reality Check and SPA ----------------------------------------------------------

def _noise(rng, n, m, scale=0.02):
    return rng.normal(0.0, scale, size=(n, m))


def test_statistics_match_their_definitions():
    rng = np.random.default_rng(1)
    d = _noise(rng, 120, 3) + np.array([0.002, -0.001, 0.0])
    rc = reality_check(d, np.random.default_rng(2), n_resamples=500)
    assert rc["statistic"] == pytest.approx(math.sqrt(120) * d.mean(axis=0).max())
    assert rc["best_trial"] == 0
    spa = spa_test(d, np.random.default_rng(2), n_resamples=500)
    assert spa["statistic"] == pytest.approx(max(max(spa["trial_t"]), 0.0))
    assert spa["trials"] == 3 and spa["n"] == 120


def test_strong_trial_rejects_and_noise_does_not():
    rng = np.random.default_rng(3)
    strong = _noise(rng, 180, 4)
    strong[:, 2] += 0.01                                   # t of about 6.7
    s = spa_test(strong, np.random.default_rng(4), n_resamples=2000)
    assert s["p_consistent"] < 0.01 and s["p_upper"] < 0.01 and s["best_trial"] == 2
    assert reality_check(strong, np.random.default_rng(4), n_resamples=2000)["p_value"] < 0.01
    noise = _noise(np.random.default_rng(5), 180, 4)
    s0 = spa_test(noise, np.random.default_rng(6), n_resamples=2000)
    assert s0["p_consistent"] > 0.05


def test_p_values_are_ordered_lower_consistent_upper():
    for seed in range(5):
        d = _noise(np.random.default_rng(seed), 90, 5) + np.linspace(-0.004, 0.002, 5)
        s = spa_test(d, np.random.default_rng(100 + seed), n_resamples=1000)
        assert s["p_lower"] <= s["p_consistent"] <= s["p_upper"]
        assert s["trial_p_individual"][s["best_trial"]] <= s["p_consistent"] + 1e-12


def test_a_clearly_poor_trial_moves_the_upper_but_not_the_consistent_p_value():
    """Hansen's point against the Reality Check: a trial that is plainly
    bad should not make the family look better by being recentred."""
    rng = np.random.default_rng(7)
    base = _noise(rng, 150, 3) + np.array([0.0015, 0.0, -0.0005])
    bad = np.concatenate([base, (rng.normal(0.0, 0.02, 150) - 0.03)[:, None]], axis=1)
    s_base = spa_test(base, np.random.default_rng(8), n_resamples=3000)
    s_bad = spa_test(bad, np.random.default_rng(8), n_resamples=3000)
    assert s_bad["trials_kept_negative_consistent"] == 1
    assert s_bad["p_consistent"] == pytest.approx(s_base["p_consistent"], abs=0.01)
    assert s_bad["p_upper"] >= s_base["p_upper"] - 1e-12
    rc_base = reality_check(base, np.random.default_rng(8), n_resamples=3000)["p_value"]
    rc_bad = reality_check(bad, np.random.default_rng(8), n_resamples=3000)["p_value"]
    assert rc_bad >= rc_base - 1e-12


def test_one_trial_and_input_validation():
    d = _noise(np.random.default_rng(9), 60, 1).ravel() + 0.001
    s = spa_test(d, np.random.default_rng(10), n_resamples=500)
    assert s["trials"] == 1 and s["p_lower"] <= s["p_upper"]
    with pytest.raises(ValueError):
        spa_test(np.zeros((60, 2)), np.random.default_rng(0), n_resamples=100)
    with pytest.raises(ValueError):
        reality_check(np.array([[1.0, np.nan]] * 5), np.random.default_rng(0), n_resamples=10)
    with pytest.raises(ValueError):
        reality_check(np.ones((1, 2)), np.random.default_rng(0), n_resamples=10)


def test_same_seed_same_answer():
    d = _noise(np.random.default_rng(11), 100, 3)
    a = spa_test(d, np.random.default_rng(12), n_resamples=400)
    b = spa_test(d, np.random.default_rng(12), n_resamples=400)
    assert a == b
