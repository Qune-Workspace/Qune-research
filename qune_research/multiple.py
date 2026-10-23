"""Multiple-testing inference for a family of trials (the library's §13 list:
White's Reality Check, Hansen's SPA, the minimum track-record length).

Built on 2026-10-23, after Study 004's results and review.  No study's
pre-registration asked for these tests; they describe a finished family of
trials and carry no decision weight anywhere until a later pre-registration
names them.  Every function is pure and takes the data it needs as arrays;
every bootstrap takes an explicit ``numpy.random.Generator``.

Definitions
-----------
Loss differentials.  For trials k = 1..m against one benchmark, the input is
the (n, m) matrix ``d`` with ``d[t, k] = r_trial_k[t] - r_benchmark[t]`` in
the same period t (monthly, non-overlapping).  The null of both tests is
that no trial beats the benchmark in expectation: ``max_k E[d_k] <= 0``.

White (2000) Reality Check.  Statistic ``V = max_k sqrt(n) * mean(d_k)``.
Stationary-bootstrap resamples of the rows give ``V*_b = max_k sqrt(n) *
(mean(d*_bk) - mean(d_k))``; the p-value is the share of ``V*_b >= V``.
Every trial is recentred to a zero mean, the least favourable configuration,
which makes the test conservative when the family holds clearly poor trials.

Hansen (2005) Superior Predictive Ability.  Studentised statistic
``T = max(max_k sqrt(n) * mean(d_k) / w_k, 0)`` with ``w_k`` the bootstrap
standard deviation of ``sqrt(n) * mean(d*_bk)``.  Three recentrings give
three p-values, ``lower <= consistent <= upper``:

  lower       ``Z* = d* - max(mean(d_k), 0)``: a trial with a negative mean
              keeps it in the bootstrap (it is assumed exactly as bad as it
              looks); a trial with a positive mean is recentred to zero;
  consistent  ``Z* = d* - mean(d_k) * 1{sqrt(n) mean(d_k)/w_k > -sqrt(2 log log n)}``:
              trials whose mean is clearly negative (below the threshold)
              keep it, the rest are recentred to zero; the paper's
              recommended p-value;
  upper       ``Z* = d* - mean(d_k)``: every trial recentred, White's
              configuration with a studentised statistic.

``T*_b = max(max_k sqrt(n) * mean(Z*_bk) / w_k, 0)``; p = share of
``T*_b >= T``.  With one trial the consistent SPA p-value is a one-sided
bootstrap test of a zero mean.

Minimum track-record length (Bailey and Lopez de Prado, 2012).  The number
of observations at which the probabilistic Sharpe ratio against a benchmark
``sr_benchmark`` reaches ``confidence``:
``MinTRL = 1 + (1 - g3 SR + (g4 - 1)/4 SR^2) * (z_conf / (SR - SR*))^2``
in the units of the observations (months here), with non-excess kurtosis
``g4``; infinite when ``SR <= SR*``.

References
----------
White, H. (2000). A reality check for data snooping. Econometrica 68(5),
1097–1126. doi:10.1111/1468-0262.00152
Hansen, P. R. (2005). A test for superior predictive ability. Journal of
Business & Economic Statistics 23(4), 365–380. doi:10.1198/073500105000000063
Bailey, D. H. and Lopez de Prado, M. (2012). The Sharpe ratio efficient
frontier. Journal of Risk 15(2), 3–44. doi:10.21314/JOR.2012.255
Politis, D. N. and Romano, J. P. (1994). The stationary bootstrap. JASA
89(428), 1303–1313. doi:10.1080/01621459.1994.10476870
"""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm

from .stats import stationary_bootstrap_indices

BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_BLOCK_MONTHS = 12
BATCH = 1_000


# --- Minimum track-record length ------------------------------------------------

def min_track_record_length(sr: float, skew: float, kurt: float, sr_benchmark: float = 0.0,
                            confidence: float = 0.95) -> float:
    """Observations needed for PSR(sr > sr_benchmark) to reach ``confidence``
    (Bailey and Lopez de Prado, 2012, eq. 13).  ``sr`` in the units of the
    observations (monthly for monthly returns); ``kurt`` non-excess.
    Returns ``inf`` when ``sr <= sr_benchmark``."""
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie strictly between 0 and 1")
    if sr <= sr_benchmark:
        return float("inf")
    z = norm.ppf(confidence)
    variance_term = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2
    if variance_term <= 0.0:
        raise ValueError("the Sharpe-ratio variance term is not positive for these moments")
    return float(1.0 + variance_term * (z / (sr - sr_benchmark)) ** 2)


# --- Reality Check and SPA ---------------------------------------------------------

def _bootstrap_means(d: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """Means of the resampled rows, shape (resamples, m), in batches."""
    out = np.empty((idx.shape[0], d.shape[1]))
    for start in range(0, idx.shape[0], BATCH):
        block = idx[start:start + BATCH]
        out[start:start + BATCH] = d[block].mean(axis=1)
    return out


def _as_matrix(d) -> np.ndarray:
    x = np.asarray(d, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    if x.ndim != 2 or x.shape[0] < 2:
        raise ValueError("d must be an (n, m) matrix of loss differentials with n >= 2")
    if not np.isfinite(x).all():
        raise ValueError("d holds non-finite values")
    return x


def reality_check(d, rng: np.random.Generator, n_resamples: int = BOOTSTRAP_RESAMPLES,
                  expected_block_length: float = BOOTSTRAP_BLOCK_MONTHS) -> dict:
    """White's (2000) Reality Check for ``max_k E[d_k] <= 0``.  Returns the
    statistic, its p-value and the per-trial statistics."""
    x = _as_matrix(d)
    n, m = x.shape
    means = x.mean(axis=0)
    v = float(math.sqrt(n) * means.max())
    idx = stationary_bootstrap_indices(rng, n, n_resamples, expected_block_length)
    star = _bootstrap_means(x, idx)                       # (B, m)
    v_star = math.sqrt(n) * (star - means[None, :]).max(axis=1)
    p = float((v_star >= v).mean())
    return {"statistic": v, "p_value": p, "n": int(n), "trials": int(m),
            "best_trial": int(means.argmax()), "trial_means": means.tolist(),
            "resamples": int(n_resamples), "expected_block": expected_block_length}


def spa_test(d, rng: np.random.Generator, n_resamples: int = BOOTSTRAP_RESAMPLES,
             expected_block_length: float = BOOTSTRAP_BLOCK_MONTHS) -> dict:
    """Hansen's (2005) SPA test for ``max_k E[d_k] <= 0`` with the lower,
    consistent and upper p-values from one set of stationary-bootstrap
    resamples.  ``w_k`` is the bootstrap standard deviation of
    ``sqrt(n) * mean(d*_k)`` (the paper's eq. 7 estimated from the
    resamples themselves)."""
    x = _as_matrix(d)
    n, m = x.shape
    means = x.mean(axis=0)
    idx = stationary_bootstrap_indices(rng, n, n_resamples, expected_block_length)
    star = _bootstrap_means(x, idx)                       # (B, m)
    scaled = math.sqrt(n) * star                          # sqrt(n) * mean(d*_k)
    w = scaled.std(axis=0, ddof=1)
    if (w <= 0.0).any():
        raise ValueError("a trial has zero bootstrap variance; its differential is constant")
    t_k = math.sqrt(n) * means / w
    t_spa = float(max(t_k.max(), 0.0))
    threshold = -math.sqrt(2.0 * math.log(math.log(n))) if n > math.e else -math.inf
    centre = {
        "lower": np.maximum(means, 0.0),
        "consistent": np.where(t_k > threshold, means, 0.0),
        "upper": means,
    }
    p_values = {}
    for name, mu in centre.items():
        z_star = math.sqrt(n) * (star - mu[None, :]) / w[None, :]
        t_star = np.maximum(z_star.max(axis=1), 0.0)
        p_values[name] = float((t_star >= t_spa).mean())
    # one-sided bootstrap p-value of each trial on its own, for the reader
    z_own = math.sqrt(n) * (star - means[None, :]) / w[None, :]
    p_own = (z_own >= t_k[None, :]).mean(axis=0)
    return {"statistic": t_spa, "p_lower": p_values["lower"], "p_consistent": p_values["consistent"],
            "p_upper": p_values["upper"], "n": int(n), "trials": int(m),
            "best_trial": int(t_k.argmax()), "trial_t": t_k.tolist(), "trial_means": means.tolist(),
            "trial_p_individual": p_own.tolist(),
            "trials_kept_negative_consistent": int((t_k <= threshold).sum()),
            "threshold_consistent": float(threshold),
            "resamples": int(n_resamples), "expected_block": expected_block_length}
