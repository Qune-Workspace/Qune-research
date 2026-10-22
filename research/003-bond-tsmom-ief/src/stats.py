"""Performance metrics and inference (§9.3, §9.4).

All inputs are monthly, non-overlapping holding-period returns.  Excess
return means strategy return minus the cash benchmark B0 in the same period.
Every bootstrap takes an explicit ``numpy.random.Generator`` so that the
seed fixed in §13 (20261021) is applied by the caller exactly once per run.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm

from .config import BOOTSTRAP_BLOCK_MONTHS, BOOTSTRAP_RESAMPLES, DSR_VARIANCE_FLOOR, NEWEY_WEST_LAGS

MONTHS_PER_YEAR = 12
EULER_GAMMA = 0.5772156649015329
BOOTSTRAP_BATCH = 500


# --- Descriptive metrics (§9.3 items 1-6, 11) --------------------------------

def annualised_geometric_return(r: pd.Series) -> float:
    return float(np.prod(1.0 + r) ** (MONTHS_PER_YEAR / len(r)) - 1.0)


def annualised_volatility(r: pd.Series) -> float:
    return float(r.std(ddof=1) * math.sqrt(MONTHS_PER_YEAR))


def sharpe_monthly(excess: pd.Series) -> float:
    sd = excess.std(ddof=1)
    return float(excess.mean() / sd) if sd > 0 else float("nan")


def sharpe_annual(excess: pd.Series) -> float:
    return sharpe_monthly(excess) * math.sqrt(MONTHS_PER_YEAR)


def total_return_index(r: pd.Series) -> pd.Series:
    return (1.0 + r).cumprod()


def max_drawdown(index: pd.Series) -> float:
    """Most negative peak-to-trough decline of a total-return index."""
    return float((index / index.cummax() - 1.0).min())


def skewness(x: pd.Series) -> float:
    z = (x - x.mean()) / x.std(ddof=0)
    return float((z ** 3).mean())


def kurtosis(x: pd.Series) -> float:
    """Non-excess kurtosis (3 for a normal), the gamma_4 of §9.4."""
    z = (x - x.mean()) / x.std(ddof=0)
    return float((z ** 4).mean())


# --- Newey-West (§9.3 item 7) -------------------------------------------------

def newey_west_mean(diff: pd.Series, lags: int = NEWEY_WEST_LAGS) -> dict[str, float]:
    """Mean of a monthly return difference and its HAC t-statistic (Bartlett
    kernel, ``lags`` lags; statsmodels OLS on a constant with
    ``cov_type='HAC'``)."""
    y = np.asarray(diff, dtype=float)
    fit = sm.OLS(y, np.ones((len(y), 1))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return {"mean": float(fit.params[0]), "se": float(fit.bse[0]), "t": float(fit.tvalues[0]),
            "n": int(len(y)), "lags": int(lags)}


# --- Block bootstraps (§9.3 items 8-9) -----------------------------------------

def circular_block_indices(rng: np.random.Generator, n: int, n_resamples: int,
                           block_length: int) -> np.ndarray:
    """Circular block bootstrap indices of shape (n_resamples, n), fixed
    block length (Ledoit and Wolf, 2008)."""
    n_blocks = -(-n // block_length)
    starts = rng.integers(0, n, size=(n_resamples, n_blocks))
    offsets = np.arange(block_length)
    idx = (starts[:, :, None] + offsets[None, None, :]).reshape(n_resamples, -1)
    return idx[:, :n] % n


def stationary_bootstrap_indices(rng: np.random.Generator, n: int, n_resamples: int,
                                 expected_block_length: float) -> np.ndarray:
    """Stationary bootstrap indices of shape (n_resamples, n) (Politis and
    Romano, 1994): geometric block lengths with mean ``expected_block_length``,
    circular wrap."""
    p = 1.0 / expected_block_length
    restart = rng.random(size=(n_resamples, n)) < p
    fresh = rng.integers(0, n, size=(n_resamples, n))
    idx = np.empty((n_resamples, n), dtype=np.int64)
    idx[:, 0] = fresh[:, 0]
    for t in range(1, n):
        idx[:, t] = np.where(restart[:, t], fresh[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def sharpe_ci_stationary_bootstrap(excess: pd.Series, rng: np.random.Generator,
                                   n_resamples: int = BOOTSTRAP_RESAMPLES,
                                   expected_block_length: float = BOOTSTRAP_BLOCK_MONTHS,
                                   level: float = 0.95) -> dict[str, float]:
    """Percentile confidence interval for the annualised Sharpe ratio."""
    x = np.asarray(excess, dtype=float)
    idx = stationary_bootstrap_indices(rng, len(x), n_resamples, expected_block_length)
    samples = x[idx]
    sr = samples.mean(axis=1) / samples.std(axis=1, ddof=1) * math.sqrt(MONTHS_PER_YEAR)
    lo, hi = np.quantile(sr, [(1 - level) / 2, 1 - (1 - level) / 2])
    return {"sharpe_annual": sharpe_annual(excess), "ci_low": float(lo), "ci_high": float(hi),
            "level": level, "resamples": n_resamples, "expected_block": expected_block_length}


def _hac_covariance(y: np.ndarray, lags: int) -> np.ndarray:
    """Bartlett-kernel long-run covariance of the rows of ``y`` (batch, n, k),
    returned as (batch, k, k); ``y`` is demeaned inside."""
    z = y - y.mean(axis=1, keepdims=True)
    n = z.shape[1]
    cov = np.einsum("bti,btj->bij", z, z) / n
    for lag in range(1, lags + 1):
        gamma = np.einsum("bti,btj->bij", z[:, lag:, :], z[:, :-lag, :]) / n
        cov += (1.0 - lag / (lags + 1.0)) * (gamma + gamma.transpose(0, 2, 1))
    return cov


def _sharpe_difference_and_se(r1: np.ndarray, r2: np.ndarray, lags: int) -> tuple[np.ndarray, np.ndarray]:
    """Monthly Sharpe difference and its HAC standard error by the delta
    method on the moments (mu1, gamma1, mu2, gamma2), gamma = E[r^2], for
    batches of shape (batch, n)."""
    n = r1.shape[1]
    y = np.stack([r1, r1 ** 2, r2, r2 ** 2], axis=-1)
    a, b, c, d = y.mean(axis=1).T
    v1, v2 = b - a ** 2, d - c ** 2
    diff = a / np.sqrt(v1) - c / np.sqrt(v2)
    grad = np.stack([b / v1 ** 1.5, -0.5 * a / v1 ** 1.5, -d / v2 ** 1.5, 0.5 * c / v2 ** 1.5], axis=-1)
    psi = _hac_covariance(y, lags)
    se = np.sqrt(np.einsum("bi,bij,bj->b", grad, psi, grad) / n)
    return diff, se


def ledoit_wolf_sharpe_test(r1: pd.Series, r2: pd.Series, rng: np.random.Generator,
                            n_resamples: int = BOOTSTRAP_RESAMPLES,
                            block_length: int = BOOTSTRAP_BLOCK_MONTHS,
                            hac_lags: int = NEWEY_WEST_LAGS) -> dict[str, float]:
    """Ledoit and Wolf (2008) test of equal Sharpe ratios: studentised
    circular block bootstrap of the paired excess returns.  The difference
    is on monthly units and uses population moments as in the paper (so it
    differs from the ddof=1 Sharpe of the tables by a factor sqrt((n-1)/n));
    ``diff_annual`` scales by sqrt(12).  The HAC standard error uses a
    Bartlett kernel with ``hac_lags`` lags both in the sample and in every
    resample."""
    x1, x2 = np.asarray(r1, dtype=float), np.asarray(r2, dtype=float)
    if x1.shape != x2.shape:
        raise ValueError("series must be paired")
    n = len(x1)
    diff, se = _sharpe_difference_and_se(x1[None, :], x2[None, :], hac_lags)
    diff, se = float(diff[0]), float(se[0])
    t_stat = diff / se
    idx = circular_block_indices(rng, n, n_resamples, block_length)
    extremes = 0
    studentised = []
    for start in range(0, n_resamples, BOOTSTRAP_BATCH):
        batch = idx[start:start + BOOTSTRAP_BATCH]
        d_star, se_star = _sharpe_difference_and_se(x1[batch], x2[batch], hac_lags)
        t_star = (d_star - diff) / se_star
        studentised.append(t_star)
        extremes += int((np.abs(t_star) >= abs(t_stat)).sum())
    t_star = np.concatenate(studentised)
    lo, hi = np.quantile(t_star, [0.025, 0.975])
    return {"diff_monthly": diff, "diff_annual": diff * math.sqrt(MONTHS_PER_YEAR), "se_monthly": se,
            "t": t_stat, "p_value": extremes / n_resamples,
            "ci_low_annual": (diff - hi * se) * math.sqrt(MONTHS_PER_YEAR),
            "ci_high_annual": (diff - lo * se) * math.sqrt(MONTHS_PER_YEAR),
            "resamples": n_resamples, "block_length": block_length, "hac_lags": hac_lags}


# --- Probabilistic and deflated Sharpe ratio (§9.4) ---------------------------

def expected_max_sharpe(n_trials: int, variance_across_trials: float) -> float:
    """``SR* = sqrt(V) * ((1 - gamma_E) Phi^-1(1 - 1/N) + gamma_E Phi^-1(1 - 1/(N e)))``
    (Bailey and Lopez de Prado, 2014).  Requires N >= 2."""
    if n_trials < 2:
        raise ValueError("the expected maximum needs at least two trials")
    return math.sqrt(variance_across_trials) * (
        (1.0 - EULER_GAMMA) * norm.ppf(1.0 - 1.0 / n_trials)
        + EULER_GAMMA * norm.ppf(1.0 - 1.0 / (n_trials * math.e)))


def probabilistic_sharpe(sr: float, n_obs: int, skew: float, kurt: float, sr_benchmark: float = 0.0) -> float:
    """``PSR = Phi((SR - SR*) sqrt(T - 1) / sqrt(1 - gamma_3 SR + (gamma_4 - 1)/4 SR^2))``
    with monthly-unit SR and non-excess kurtosis."""
    denominator = math.sqrt(1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2)
    return float(norm.cdf((sr - sr_benchmark) * math.sqrt(n_obs - 1) / denominator))


def trial_variance(monthly_sharpes: list[float], floor: float = DSR_VARIANCE_FLOOR) -> tuple[float, bool]:
    """Variance of the monthly Sharpe ratios across the registered trials,
    with the §9.4 floor applied when the trials are nearly identical.
    Returns (variance, floor_applied)."""
    v = float(np.var(monthly_sharpes, ddof=0))
    return (floor, True) if v < floor else (v, False)


def deflated_sharpe(sr: float, n_obs: int, skew: float, kurt: float,
                    n_trials: int, variance_across_trials: float) -> dict[str, float]:
    sr_star = expected_max_sharpe(n_trials, variance_across_trials)
    return {"sr_monthly": sr, "sr_star_monthly": sr_star, "n_trials": n_trials,
            "variance_across_trials": variance_across_trials,
            "psr": probabilistic_sharpe(sr, n_obs, skew, kurt, 0.0),
            "dsr": probabilistic_sharpe(sr, n_obs, skew, kurt, sr_star)}


# --- Convenience ----------------------------------------------------------------

def inverted_episodes(inverted: pd.Series) -> dict[str, float]:
    """Count of months with a non-positive signal and the mean length of
    consecutive runs of them (§9.6)."""
    flags = inverted.astype(bool).to_numpy()
    starts = flags & ~np.concatenate([[False], flags[:-1]])
    n_episodes = int(starts.sum())
    return {"months": int(flags.sum()), "episodes": n_episodes,
            "mean_episode_length": float(flags.sum() / n_episodes) if n_episodes else float("nan")}
