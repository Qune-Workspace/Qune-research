"""Ex-ante risk model: covariance forecasts, portfolio volatility, risk
contributions, value at risk and expected shortfall, historical stress
windows and a drawdown-control multiplier.

Every function is pure and takes only the data it is given, so a forecast
made at a date uses nothing after it when the caller passes returns ending
at that date.  Nothing here changes a study's rule: the module describes
the risk of a weight vector, it does not size it.  The first use is the
post-hoc risk report of Study 004 (``research/004-.../risk/``), where the
study's own diagonal forecast was found to understate realised volatility
by 1.6× in-sample and 1.8× out of sample because it ignores correlations.

Conventions: daily simple returns in columns, one column per asset;
covariances are annualised with ``TRADING_DAYS`` only where the function
says so; weights are fractions of portfolio value (long-only or flat in the
studies, but nothing here assumes it).

References
----------
RiskMetrics Technical Document (J.P. Morgan/Reuters, 1996): exponentially
  weighted, zero-mean covariance.
Ledoit, O. and Wolf, M. (2004), "Honey, I shrunk the sample covariance
  matrix", Journal of Portfolio Management 30(4), 110-119,
  doi:10.3905/jpm.2004.110: constant-correlation shrinkage target and the
  analytical shrinkage intensity.
Euler decomposition of portfolio volatility: Litterman (1996), "Hot spots
  and hedges", Goldman Sachs Risk Management Series.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sps

TRADING_DAYS = 252


# --- Covariance forecasts --------------------------------------------------------------

def ewma_covariance(returns: pd.DataFrame, halflife_days: float, annualise: bool = True) -> pd.DataFrame:
    """Exponentially weighted covariance of daily returns about zero
    (RiskMetrics), the most recent row weighted most.  ``halflife_days``
    is the lag at which a row's weight has halved; weights are normalised
    over the rows present, so a short history is used in full rather than
    padded.  Rows with any NaN are dropped.  Annualised by ``TRADING_DAYS``
    when ``annualise`` is set."""
    if halflife_days <= 0:
        raise ValueError("halflife_days must be positive")
    x = returns.dropna(how="any")
    if len(x) < 2:
        raise ValueError("need at least two complete rows")
    lam = 0.5 ** (1.0 / halflife_days)
    n = len(x)
    w = lam ** np.arange(n - 1, -1, -1)
    w = w / w.sum()
    a = x.to_numpy(dtype=float)
    cov = (a * w[:, None]).T @ a
    if annualise:
        cov = cov * TRADING_DAYS
    return pd.DataFrame(cov, index=x.columns, columns=x.columns)


def sample_covariance(returns: pd.DataFrame, annualise: bool = True) -> pd.DataFrame:
    """Equal-weighted sample covariance (ddof = 1) of the complete rows."""
    x = returns.dropna(how="any")
    if len(x) < 2:
        raise ValueError("need at least two complete rows")
    cov = x.cov(ddof=1)
    return cov * TRADING_DAYS if annualise else cov


def constant_correlation_target(cov: pd.DataFrame) -> pd.DataFrame:
    """Ledoit-Wolf (2004) target: every variance kept, every correlation
    replaced by the mean off-diagonal correlation of ``cov``."""
    c = cov.to_numpy(dtype=float)
    sd = np.sqrt(np.diag(c))
    corr = c / np.outer(sd, sd)
    n = len(sd)
    if n == 1:
        return cov.copy()
    off = corr[~np.eye(n, dtype=bool)]
    r_bar = float(off.mean())
    f = r_bar * np.outer(sd, sd)
    np.fill_diagonal(f, sd ** 2)
    return pd.DataFrame(f, index=cov.index, columns=cov.columns)


def ledoit_wolf_intensity(returns: pd.DataFrame) -> float:
    """The analytical shrinkage intensity δ of Ledoit and Wolf (2004) for
    the constant-correlation target, estimated on the equal-weighted sample
    of the complete rows (their equations in the appendix), clipped to
    [0, 1].  Independent of annualisation."""
    x = returns.dropna(how="any").to_numpy(dtype=float)
    t, n = x.shape
    if t < 2:
        raise ValueError("need at least two complete rows")
    if n == 1:
        return 0.0
    x = x - x.mean(axis=0)
    s = (x.T @ x) / t
    sd = np.sqrt(np.diag(s))
    corr = s / np.outer(sd, sd)
    r_bar = float(corr[~np.eye(n, dtype=bool)].mean())
    f = r_bar * np.outer(sd, sd)
    np.fill_diagonal(f, sd ** 2)
    # pi: sum over i,j of the asymptotic variances of the sample covariances
    y = x ** 2
    pi_mat = (y.T @ y) / t - s ** 2
    pi_hat = float(pi_mat.sum())
    # rho: diagonal part plus the off-diagonal covariances with the target
    theta_ii = ((x ** 3).T @ x) / t - sd[:, None] ** 2 * s      # theta_{ii,ij}
    theta_jj = theta_ii.T                                          # theta_{jj,ij}
    ratio = np.sqrt(np.outer(1.0 / sd ** 2, sd ** 2))              # sqrt(s_jj / s_ii)
    rho_off = (r_bar / 2.0) * (ratio * theta_ii + ratio.T * theta_jj)
    np.fill_diagonal(rho_off, 0.0)
    rho_hat = float(np.trace(pi_mat) + rho_off.sum())
    gamma_hat = float(((f - s) ** 2).sum())
    if gamma_hat <= 0:
        return 0.0
    kappa = (pi_hat - rho_hat) / gamma_hat
    return float(min(1.0, max(0.0, kappa / t)))


def shrink(cov: pd.DataFrame, intensity: float) -> pd.DataFrame:
    """``(1 − δ) Σ + δ F`` with F the constant-correlation target of Σ."""
    if not 0.0 <= intensity <= 1.0:
        raise ValueError("intensity must lie in [0, 1]")
    f = constant_correlation_target(cov)
    return (1.0 - intensity) * cov + intensity * f


def shrunk_ewma_covariance(returns: pd.DataFrame, halflife_days: float,
                           annualise: bool = True) -> tuple[pd.DataFrame, float]:
    """EWMA covariance shrunk toward its own constant-correlation target with
    the Ledoit-Wolf intensity estimated on the same rows, equal-weighted.
    A pragmatic hybrid, not a theorem: the intensity is derived for the
    equal-weighted estimator and is applied here to the exponentially
    weighted one.  Returns the covariance and the intensity used."""
    delta = ledoit_wolf_intensity(returns)
    return shrink(ewma_covariance(returns, halflife_days, annualise), delta), delta


def diagonal(cov: pd.DataFrame) -> pd.DataFrame:
    """The covariance with every off-diagonal element set to zero: the
    forecast a study makes when it sizes each leg by its own volatility."""
    return pd.DataFrame(np.diag(np.diag(cov.to_numpy(dtype=float))), index=cov.index, columns=cov.columns)


# --- Portfolio risk --------------------------------------------------------------------

def _align(weights: pd.Series | dict[str, float], cov: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    w = pd.Series(weights, dtype=float).reindex(cov.index).fillna(0.0)
    return w.to_numpy(), cov.to_numpy(dtype=float)


def portfolio_variance(weights: pd.Series | dict[str, float], cov: pd.DataFrame) -> float:
    """``w' Σ w`` over the assets of ``cov``; weights absent from ``cov`` are
    an error, assets without a weight are held at zero."""
    extra = set(pd.Series(weights, dtype=float).index) - set(cov.index)
    if extra:
        raise ValueError(f"weights for assets not in the covariance: {sorted(extra)}")
    w, c = _align(weights, cov)
    return float(w @ c @ w)


def portfolio_vol(weights: pd.Series | dict[str, float], cov: pd.DataFrame) -> float:
    """``sqrt(w' Σ w)``, in the units of ``cov`` (annualised if it is)."""
    return float(np.sqrt(max(portfolio_variance(weights, cov), 0.0)))


def risk_contributions(weights: pd.Series | dict[str, float], cov: pd.DataFrame) -> pd.Series:
    """Euler decomposition of portfolio variance: ``w_i (Σ w)_i / (w' Σ w)``
    per asset, summing to one.  An all-cash book (zero variance) returns
    zeros.  A negative value means the leg hedges the rest of the book."""
    w, c = _align(weights, cov)
    var = float(w @ c @ w)
    marginal = c @ w
    rc = w * marginal / var if var > 0 else np.zeros_like(w)
    return pd.Series(rc, index=cov.index)


def parametric_var_es(weights: pd.Series | dict[str, float], cov_daily: pd.DataFrame,
                      level: float = 0.99, horizon_days: int = 1) -> dict[str, float]:
    """Normal value at risk and expected shortfall of the portfolio as positive
    fractions of its value, from a *daily* (not annualised) covariance and
    a zero mean, scaled by the square root of the horizon.  Returns
    ``{"vol_horizon", "var", "es"}``."""
    if not 0.5 < level < 1.0:
        raise ValueError("level must lie in (0.5, 1)")
    sigma = portfolio_vol(weights, cov_daily) * np.sqrt(horizon_days)
    z = sps.norm.ppf(level)
    es = sigma * sps.norm.pdf(z) / (1.0 - level)
    return {"vol_horizon": float(sigma), "var": float(sigma * z), "es": float(es)}


def historical_var_es(portfolio_returns: pd.Series, level: float = 0.99) -> dict[str, float]:
    """Empirical value at risk (the ``1 − level`` quantile, sign flipped) and
    expected shortfall (mean loss at or beyond it) of realised returns, as
    positive fractions.  ``n`` is the number of returns used; with fewer
    than ``1/(1 − level)`` the tail is one observation and the caller
    should say so."""
    r = pd.Series(portfolio_returns, dtype=float).dropna()
    if len(r) < 2:
        raise ValueError("need at least two returns")
    q = float(np.quantile(r.to_numpy(), 1.0 - level))
    tail = r[r <= q]
    return {"var": float(-q), "es": float(-tail.mean()), "n": int(len(r)), "n_tail": int(len(tail))}


# --- Stress windows --------------------------------------------------------------------

def stress_window_returns(prices: pd.DataFrame, weights: pd.Series | dict[str, float],
                          windows: dict[str, tuple[str, str]],
                          cash_index: pd.Series | None = None) -> pd.DataFrame:
    """The return a book with constant ``weights`` (set at the window's start
    and not rebalanced) would have earned across each historical window,
    with the unallocated part in ``cash_index`` (or at zero if None), plus
    each leg's contribution ``w_i × r_i``.  Window ends are the last price on
    or before the end date, starts the last price on or before the start
    date (so the first day's return is inside the window).  An asset with
    no price at the start of a window makes that window NaN rather than a
    silent partial book: a stress figure that quietly drops a leg is worse
    than none."""
    w = pd.Series(weights, dtype=float)
    w = w[w != 0.0]
    missing = set(w.index) - set(prices.columns)
    if missing:
        raise ValueError(f"no prices for {sorted(missing)}")
    rows = {}
    for label, (start, end) in windows.items():
        s, e = pd.Timestamp(start), pd.Timestamp(end)
        p0 = prices.reindex([s], method="ffill").iloc[0]
        p1 = prices.reindex([e], method="ffill").iloc[0]
        leg = {}
        ok = True
        for a_, wa in w.items():
            a = str(a_)
            if np.isnan(p0[a]) or np.isnan(p1[a]):
                ok = False
                break
            leg[a] = float(wa * (p1[a] / p0[a] - 1.0))
        if not ok:
            rows[label] = {"total": np.nan}
            continue
        cash_part = 0.0
        if cash_index is not None:
            c0 = cash_index.reindex([s], method="ffill").iloc[0]
            c1 = cash_index.reindex([e], method="ffill").iloc[0]
            cash_part = float((1.0 - w.sum()) * (c1 / c0 - 1.0))
        rec = {"total": sum(leg.values()) + cash_part, "cash": cash_part}
        rec.update({f"leg_{a}": v for a, v in leg.items()})
        rows[label] = rec
    return pd.DataFrame(rows).T


# --- Drawdown control ------------------------------------------------------------------

def drawdown_from_high(index: pd.Series) -> pd.Series:
    """Decline from the running peak, zero at a new high, negative below it."""
    s = pd.Series(index, dtype=float)
    return s / s.cummax() - 1.0


def drawdown_multiplier(drawdown: float | pd.Series, limit: float, floor: float = 0.0) -> float | pd.Series:
    """A linear drawdown-control rule: exposure multiplier 1 at no drawdown,
    falling in proportion to the drawdown and reaching ``floor`` once the
    drawdown is at or beyond ``limit``.  ``limit`` is positive (0.10 = ten
    per cent).  Descriptive only: no study applies it unless its
    pre-registration says so."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    if not 0.0 <= floor <= 1.0:
        raise ValueError("floor must lie in [0, 1]")
    dd = -np.minimum(np.asarray(drawdown, dtype=float), 0.0)
    m = 1.0 - (1.0 - floor) * np.clip(dd / limit, 0.0, 1.0)
    if isinstance(drawdown, pd.Series):
        return pd.Series(m, index=drawdown.index)
    return float(m)


# --- Forecast accuracy -----------------------------------------------------------------

def forecast_accuracy(forecast: pd.Series, realised: pd.Series, exceedance_factor: float = 1.5) -> dict[str, float]:
    """How a volatility forecast did against what followed, on the dates both
    are present and the forecast is positive: mean ratio realised/forecast,
    the share of dates realised exceeded the forecast by more than
    ``exceedance_factor``, the mean log ratio (zero if unbiased on a log
    scale) and the slope of realised on forecast through the origin (one if
    unbiased in scale).  ``n`` dates compared."""
    both = pd.DataFrame({"f": forecast, "r": realised}).dropna()
    both = both[both["f"] > 0]
    if len(both) == 0:
        return {"n": 0}
    ratio = both["r"] / both["f"]
    slope = float((both["f"] * both["r"]).sum() / (both["f"] ** 2).sum())
    return {"n": int(len(both)), "mean_forecast": float(both["f"].mean()), "mean_realised": float(both["r"].mean()),
            "mean_ratio": float(ratio.mean()), "median_ratio": float(ratio.median()),
            "share_over_factor": float((ratio > exceedance_factor).mean()),
            "mean_log_ratio": float(np.log(ratio).mean()), "slope_through_origin": slope}
