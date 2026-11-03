"""Study 013 scoring estimator (PREREGISTRATION.md §9.1, §9.3, §9.5, §9.6).

Pure functions on arrays; nothing here reads a file, a snapshot or an outcome.
The scoring run (`src/score.py`, §14 step 9) calls these after `APPROVED`; the
tests (tests/test_fit.py) call them on synthetic data only (§6.6).

The test object (§9.1): over a trial's sample, with x = logit(p) and y the
outcome, logit Pr(y = 1) = a + b x, fitted by maximum likelihood with every
market one observation of weight 1.  The decision quantity is b - 1, its sign
and its clustered t-statistic t_cl = (b - 1) / SE_cl.

Estimator (§9.3): Newton-Raphson on the log-likelihood with step halving,
started at (a, b) = (0, 1), stopped when the relative change in the
log-likelihood is below 1e-10 or after 100 iterations.  A fit that does not
converge is reported as such (`converged` False), never raised.

Clustered covariance (§9.3): with pi the fitted probability, z = (1, x)^T,
H = sum_i pi_i (1 - pi_i) z_i z_i^T the observed information and
s_g = sum_{i in g} (y_i - pi_i) z_i the score of cluster g,
    V_cl = G / (G - 1) * H^-1 (sum_g s_g s_g^T) H^-1.
Reported beside it, no decision weight: the ordinary (model-based) standard
error from H^-1, and a clustered bootstrap percentile interval at 95 percent
(2,000 resamples of clusters with replacement, numpy.random.default_rng(13)).

Two precisions found while writing the tests (§16, dated 2026-11-02):

1. With one market per cluster, V_cl equals the unclustered sandwich (the HC0
   form times n / (n - 1)), not the model-based H^-1; the two agree only in
   expectation under a correctly specified model.  §6.6's sentence "the
   clustered standard error equal to the ordinary one when every cluster has
   one member" is read that way, and the tests assert both readings (exact
   equality with the unclustered sandwich; agreement within sampling error
   with H^-1 on a large correctly specified sample).
2. On perfectly separated data the §9.3 stop rule fires (the log-likelihood
   tends to 0 and its relative change falls below 1e-10) and the first draft
   of this module reported a slope of 410 as converged.  A fit is therefore
   `separated` (and not converged) when every observation is fitted to within
   1e-6 of its outcome, or when the observed information is singular; the
   trial's row reads "not supported (no fit)" as §9.3 provides.
3. (Code review of 2026-11-03, should-fix 2.) Quasi-complete separation (the
   outcomes overlap at one x only) passed both tests above: on six points the
   fit returned b = 24.6 as converged with an ordinary standard error of 1.5e5.
   The observed information is then numerically singular, so a condition
   number above SEPARATION_COND also marks the fit as no fit.  A well-posed
   fit on x = logit p with p in [0.01, 0.99] has a condition number in the
   tens or hundreds, never near that bound.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]

# MDE = K * SE (§9.6; tools/power_pm013.py): K_PROGRAMME is t >= 2.0 at 80 percent power (2.0 + 0.842, the
# programme's convention); K_ONESIDED is z(0.95) + z(0.80) = 1.645 + 0.842, reported beside it, no decision weight.
K_PROGRAMME = 2.842
K_ONESIDED = 2.486
PUBLISHED_EFFECT = 0.112  # [WA26] b - 1, the effect the low-power ratio is measured against (§9.6)
C1_MARGIN = 0.02  # §9.5
C2_T = 2.0  # §9.5
C3_T = 2.128  # §9.4, Bonferroni at N = 3, one-sided 0.05 / 3 on the standard normal
LOW_POWER_RATIO = 0.50  # §8, §9.5
BOOTSTRAP_RESAMPLES = 2000  # §9.3
BOOTSTRAP_SEED = 13  # §9.3
BOOTSTRAP_MAX_DROPPED_SHARE = 0.01  # §9.3
BIN_EDGES = (0.01, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.99)  # §9.6, last bin closed
MIN_CELL = 10  # a bin or split with fewer markets reports its count only (Polymarket verdict `derived`: no per-market row)
SEPARATION_COND = 1e8  # condition number of the observed information above which the fit is no fit (quasi-separation)


def logit(p: Array) -> Array:
    p = np.asarray(p, dtype=np.float64)
    return np.log(p) - np.log1p(-p)


def _sigmoid(eta: Array) -> Array:
    """1 / (1 + exp(-eta)) without overflow at large |eta|."""
    out = np.empty_like(eta)
    pos = eta >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-eta[pos]))
    e = np.exp(eta[~pos])
    out[~pos] = e / (1.0 + e)
    return out


def _loglik(a: float, b: float, x: Array, y: Array) -> float:
    eta = a + b * x
    # log(1 + exp(eta)) computed stably; y in {0, 1}
    return float(np.sum(y * eta - np.logaddexp(0.0, eta)))


SEPARATION_TOL = 1e-6  # every observation fitted to within this of its outcome: no finite maximum


@dataclass
class Fit:
    a: float
    b: float
    converged: bool
    separated: bool
    iterations: int
    loglik: float
    loglik_calibrated: float  # at (a, b) = (0, 1), the benchmark of §9.1
    n: int
    se_ordinary_b: float
    hessian_inv: Array = field(repr=False)


def fit_logistic(x: Array, y: Array, tol: float = 1e-10, max_iter: int = 100) -> Fit:
    """Maximum-likelihood fit of logit Pr(y = 1) = a + b x by Newton-Raphson with step halving (§9.3)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.ndim != 1 or x.shape != y.shape:
        raise ValueError("x and y must be one-dimensional arrays of the same length")
    if not np.all((y == 0) | (y == 1)):
        raise ValueError("y must be 0 or 1")
    n = int(x.size)
    z = np.column_stack([np.ones(n), x])
    theta = np.array([0.0, 1.0])
    ll = _loglik(theta[0], theta[1], x, y)
    ll_cal = ll
    converged = False
    it = 0
    h_inv = np.full((2, 2), np.nan)
    for it in range(1, max_iter + 1):
        eta = z @ theta
        pi = _sigmoid(eta)
        w = pi * (1.0 - pi)
        grad = z.T @ (y - pi)
        hess = (z * w[:, None]).T @ z
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            break
        lam = 1.0
        new_ll = -np.inf
        for _ in range(60):
            cand = theta + lam * step
            new_ll = _loglik(cand[0], cand[1], x, y)
            if new_ll >= ll:
                break
            lam *= 0.5
        else:
            break  # no step improves the likelihood: stop, not converged unless the change test below says so
        theta = theta + lam * step
        rel = abs(new_ll - ll) / max(1.0, abs(ll))
        ll = new_ll
        if rel < tol:
            converged = True
            break
    separated = False
    if np.all(np.isfinite(theta)):
        eta = z @ theta
        pi = _sigmoid(eta)
        w = pi * (1.0 - pi)
        hess = (z * w[:, None]).T @ z
        separated = bool(np.max(np.abs(y - pi)) < SEPARATION_TOL)
        try:
            h_inv = np.linalg.inv(hess)
            if np.linalg.cond(hess) > SEPARATION_COND:
                separated = True  # quasi-complete separation: no finite maximum, the information is numerically singular
        except np.linalg.LinAlgError:
            h_inv = np.full((2, 2), np.nan)
            separated = True
    else:
        separated = True
    if separated:
        converged = False
    se_b = float(np.sqrt(h_inv[1, 1])) if np.isfinite(h_inv[1, 1]) and h_inv[1, 1] > 0 else float("nan")
    return Fit(a=float(theta[0]), b=float(theta[1]), converged=converged, separated=separated, iterations=it,
               loglik=ll, loglik_calibrated=ll_cal, n=n, se_ordinary_b=se_b, hessian_inv=h_inv)


def clustered_cov(fit: Fit, x: Array, y: Array, clusters: Array) -> tuple[Array, int]:
    """V_cl = G/(G - 1) H^-1 (sum_g s_g s_g^T) H^-1 (§9.3); returns (V_cl, G)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    clusters = np.asarray(clusters)
    if clusters.shape != x.shape:
        raise ValueError("clusters must align with x")
    n = x.size
    z = np.column_stack([np.ones(n), x])
    pi = _sigmoid(fit.a + fit.b * x)
    resid = (y - pi)[:, None] * z  # per-observation score contributions, n x 2
    _, inv = np.unique(clusters, return_inverse=True)
    g_count = int(inv.max()) + 1
    scores = np.zeros((g_count, 2))
    np.add.at(scores, inv, resid)
    meat = scores.T @ scores
    if g_count < 2:
        return np.full((2, 2), np.nan), g_count
    v = (g_count / (g_count - 1.0)) * fit.hessian_inv @ meat @ fit.hessian_inv
    return v, g_count


def se_clustered_b(fit: Fit, x: Array, y: Array, clusters: Array) -> tuple[float, int]:
    v, g = clustered_cov(fit, x, y, clusters)
    return (float(np.sqrt(v[1, 1])) if np.isfinite(v[1, 1]) and v[1, 1] > 0 else float("nan")), g


@dataclass
class Bootstrap:
    low: float
    high: float
    resamples: int
    dropped: int
    available: bool  # False when more than 1 percent of resamples were dropped (§9.3)


def cluster_bootstrap(x: Array, y: Array, clusters: Array, resamples: int = BOOTSTRAP_RESAMPLES,
                      seed: int = BOOTSTRAP_SEED) -> Bootstrap:
    """Percentile interval for b over resamples of clusters with replacement (§9.3).

    A resample whose fit does not converge, or that holds one outcome only, is dropped and counted."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    labels, inv = np.unique(np.asarray(clusters), return_inverse=True)
    g_count = labels.size
    members = [np.flatnonzero(inv == g) for g in range(g_count)]
    rng = np.random.default_rng(seed)
    bs: list[float] = []
    dropped = 0
    for _ in range(resamples):
        draw = rng.integers(0, g_count, size=g_count)
        idx = np.concatenate([members[g] for g in draw])
        yy = y[idx]
        if yy.min() == yy.max():
            dropped += 1
            continue
        f = fit_logistic(x[idx], yy)
        if not f.converged:
            dropped += 1
            continue
        bs.append(f.b)
    available = dropped <= BOOTSTRAP_MAX_DROPPED_SHARE * resamples and len(bs) > 0
    if bs:
        low, high = (float(v) for v in np.percentile(np.array(bs), [2.5, 97.5]))
    else:
        low = high = float("nan")
    return Bootstrap(low=low, high=high, resamples=resamples, dropped=dropped, available=available)


def criteria(b: float, se_cl: float, b_w1: float, b_w2: float, converged: bool = True,
             w1_converged: bool = True, w2_converged: bool = True) -> dict[str, bool | float]:
    """C1-C4 of §9.5 on the window row, with the two halves' slopes for C4.

    C4 needs both half fits to have converged (code review of 2026-11-03, must-fix 5: a half's slope was
    taken whether or not its fit converged; §9.3 reports a non-converged fit as no fit)."""
    t_cl = (b - 1.0) / se_cl if se_cl and np.isfinite(se_cl) and se_cl > 0 else float("nan")
    c1 = bool(converged and np.isfinite(b) and (b - 1.0) >= C1_MARGIN)
    c2 = bool(converged and np.isfinite(t_cl) and t_cl >= C2_T)
    c3 = bool(converged and np.isfinite(t_cl) and t_cl >= C3_T)
    c4 = bool(converged and w1_converged and w2_converged and np.isfinite(b_w1) and np.isfinite(b_w2)
              and (b_w1 - 1.0) > 0 and (b_w2 - 1.0) > 0)
    return {"t_cl": float(t_cl), "C1": c1, "C2": c2, "C3": c3, "C4": c4, "all": c1 and c2 and c3 and c4}


def headline_verdict(c1_meets: bool, c1_converged: bool, c1a_not_supported: bool, halted: bool) -> str:
    """The verdict table of §9.5 with its precedence: halted > not supported > fragile > supported."""
    if halted:
        return "inconclusive (halted at the data step)"
    if not c1_converged:
        return "not supported (no fit)"  # §9.3
    if not c1_meets:
        return "not supported"
    if c1a_not_supported:
        return "inconclusive (fragile: Sports)"
    return "supported in one forward window"


def power_row(p: Array, g_count: int) -> dict[str, float]:
    """Realised power (§9.6, data step, before any outcome): E-hat, SE under H0, MDEs and the ratio."""
    p = np.asarray(p, dtype=np.float64)
    x = logit(p)
    e_hat = float(np.mean(x * x * p * (1.0 - p)))
    se = 1.0 / np.sqrt(g_count * e_hat) if g_count > 0 and e_hat > 0 else float("nan")
    ratio = float(K_PROGRAMME * se / PUBLISHED_EFFECT)
    return {"n": float(p.size), "G": float(g_count), "E_hat": e_hat, "se_h0": float(se),
            "mde_programme": float(K_PROGRAMME * se), "mde_onesided": float(K_ONESIDED * se),
            "ratio": ratio, "low_power": float(ratio > LOW_POWER_RATIO)}


def reliability_table(p: Array, y: Array, clusters: Array, min_cell: int = MIN_CELL) -> list[dict[str, float]]:
    """Ten bins of p (§9.6): n, mean p, outcome share, difference in percentage points, clustered 95 percent interval.

    The interval is on the mean of (y - p) within the bin, with the sandwich over clusters and the G/(G - 1) factor.
    A bin with fewer than `min_cell` markets reports its count only (`suppressed` 1): a cell of one or two markets
    is a per-market row in effect, which the venue's `derived` verdict does not allow (code review of 2026-11-03)."""
    p = np.asarray(p, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    clusters = np.asarray(clusters)
    rows: list[dict[str, float]] = []
    for k in range(len(BIN_EDGES) - 1):
        lo, hi = BIN_EDGES[k], BIN_EDGES[k + 1]
        last = k == len(BIN_EDGES) - 2
        m = (p >= lo) & ((p <= hi) if last else (p < hi))
        n = int(m.sum())
        row: dict[str, float] = {"bin_low": lo, "bin_high": hi, "n": float(n)}
        if n < min_cell:
            row.update({"mean_p": float("nan"), "outcome_share": float("nan"), "diff_pp": float("nan"),
                        "ci_low_pp": float("nan"), "ci_high_pp": float("nan"),
                        "clusters": float(np.unique(clusters[m]).size) if n else 0.0, "suppressed": float(n > 0)})
            rows.append(row)
            continue
        d = y[m] - p[m]
        diff = float(d.mean())
        _, inv = np.unique(clusters[m], return_inverse=True)
        g_count = int(inv.max()) + 1
        s = np.zeros(g_count)
        np.add.at(s, inv, d - diff)
        se = float(np.sqrt(g_count / (g_count - 1.0) * np.sum(s * s)) / n) if g_count > 1 else float("nan")
        row.update({"mean_p": float(p[m].mean()), "outcome_share": float(y[m].mean()), "diff_pp": 100.0 * diff,
                    "ci_low_pp": 100.0 * (diff - 1.96 * se), "ci_high_pp": 100.0 * (diff + 1.96 * se),
                    "clusters": float(g_count)})
        rows.append(row)
    return rows


def scores(p: Array, y: Array) -> dict[str, float]:
    """Brier score, log-loss and the Brier skill score against the sample's own base rate (§9.6)."""
    p = np.asarray(p, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    brier = float(np.mean((p - y) ** 2))
    base = float(y.mean())
    brier_base = float(np.mean((base - y) ** 2))
    ll = float(-np.mean(y * np.log(p) + (1.0 - y) * np.log1p(-p)))
    bss = 1.0 - brier / brier_base if brier_base > 0 else float("nan")
    return {"brier": brier, "log_loss": ll, "base_rate": base, "brier_base": brier_base, "brier_skill": bss}
