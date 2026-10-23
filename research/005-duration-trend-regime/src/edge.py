"""The conditional edge and its statistics (§9.2–9.3), the in-sample decision
rows (§9.5) and the power statement (§9.6).

    Δ = mean(d | positive) − mean(d | negative)

* Newey–West t of Δ from the regression ``d_t = a + Δ·1[positive_t] + ε_t``
  (Bartlett kernel, 6 lags, the programme's convention; small-sample
  correction off, as the library's ``newey_west_mean``).
* Stationary-bootstrap 95% interval for Δ and for each half-mean (expected
  block 12 months, 10,000 resamples, seed fixed by the caller), resampling
  the (d, regime) pairs jointly so that regime persistence is kept; a
  resample with no month in one regime has no Δ and is dropped and counted.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from qune_research.stats import stationary_bootstrap_indices

from .config import (BOOTSTRAP_BLOCK_MONTHS, BOOTSTRAP_RESAMPLES, MIN_EDGE_PER_MONTH, MIN_POSITIVE_MONTHS,
                     NEWEY_WEST_LAGS, POWER_Z)


def newey_west_delta(d: np.ndarray, positive: np.ndarray, lags: int = NEWEY_WEST_LAGS) -> dict[str, float]:
    """Δ and its HAC t from the one-regressor regression of §9.3 item 1."""
    x = sm.add_constant(positive.astype(float), has_constant="add")
    fit = sm.OLS(d, x).fit(cov_type="HAC", cov_kwds={"maxlags": lags, "use_correction": False})
    return {"delta": float(fit.params[1]), "se": float(fit.bse[1]), "t": float(fit.tvalues[1]),
            "intercept_mean_negative": float(fit.params[0]), "lags": lags}


def bootstrap_edge(d: np.ndarray, positive: np.ndarray, rng: np.random.Generator,
                   n_resamples: int = BOOTSTRAP_RESAMPLES, block: float = BOOTSTRAP_BLOCK_MONTHS,
                   level: float = 0.95) -> dict:
    """§9.3 item 2: percentile intervals for Δ and both half-means from
    jointly resampled (d, regime) pairs."""
    idx = stationary_bootstrap_indices(rng, len(d), n_resamples, block)
    ds, ps = d[idx], positive[idx].astype(bool)
    n_pos = ps.sum(axis=1)
    n_neg = (~ps).sum(axis=1)
    keep = (n_pos > 0) & (n_neg > 0)
    if keep.sum() < 2:
        raise ValueError("fewer than two bootstrap resamples contain both regimes")
    with np.errstate(invalid="ignore", divide="ignore"):
        mean_pos = np.where(ps, ds, 0.0).sum(axis=1) / np.where(n_pos > 0, n_pos, np.nan)
        mean_neg = np.where(~ps, ds, 0.0).sum(axis=1) / np.where(n_neg > 0, n_neg, np.nan)
    delta = (mean_pos - mean_neg)[keep]
    q = [(1 - level) / 2, 1 - (1 - level) / 2]

    def interval(x: np.ndarray) -> dict[str, float]:
        lo, hi = np.quantile(x[~np.isnan(x)], q)
        return {"ci_low": float(lo), "ci_high": float(hi)}

    return {"delta": interval(delta), "mean_positive": interval(mean_pos[keep]), "mean_negative": interval(mean_neg[keep]),
            "level": level, "resamples": n_resamples, "resamples_dropped_one_regime": int((~keep).sum()),
            "expected_block": block}


def conditional_edge(d: pd.Series, positive: pd.Series, rng: np.random.Generator, **bootstrap_kwargs) -> dict:
    """Everything §9.2–9.3 report for one window and one cost case."""
    positive = positive.reindex(d.index)
    if positive.isna().any():
        raise ValueError("every d_t needs a regime flag")
    dv, pv = d.to_numpy(dtype=float), positive.to_numpy(dtype=bool)
    n_pos, n_neg = int(pv.sum()), int((~pv).sum())
    out = {"n": int(len(dv)), "n_pos": n_pos, "n_neg": n_neg,
           "mean_positive": float(dv[pv].mean()) if n_pos else float("nan"),
           "mean_negative": float(dv[~pv].mean()) if n_neg else float("nan")}
    out["delta"] = out["mean_positive"] - out["mean_negative"]
    if n_pos and n_neg:
        out["newey_west"] = newey_west_delta(dv, pv)
        out["bootstrap"] = bootstrap_edge(dv, pv, rng, **bootstrap_kwargs)
    else:
        out["newey_west"] = None
        out["bootstrap"] = None
    return out


def regime_descriptives(d: pd.Series, positive: pd.Series, b2_in_bills: pd.Series,
                        ief_excess: pd.Series) -> dict:
    """§9.2's companions by regime: the share of months B2 held bills and
    IEF's mean excess return over cash."""
    positive = positive.reindex(d.index).astype(bool)
    out = {}
    for label, mask in (("positive", positive), ("negative", ~positive)):
        months = d.index[mask.to_numpy()]
        out[label] = {"months": int(len(months)),
                      "share_b2_in_bills": float(b2_in_bills.reindex(months).astype(bool).mean()) if len(months) else float("nan"),
                      "mean_ief_excess": float(ief_excess.reindex(months).mean()) if len(months) else float("nan")}
    return out


# --- §9.5 in-sample rows ------------------------------------------------------------

ROW_NOT_INFORMATIVE = "not informative (fewer than 12 positive-regime months; no row applies)"
ROW_REFUTED = "refuted in-sample"
ROW_SIGN_CONSISTENT = "sign consistent, forward record decides"
ROW_INCONCLUSIVE = "inconclusive, forward record decides"


def insample_row(edge: dict, min_edge: float = MIN_EDGE_PER_MONTH, min_pos: int = MIN_POSITIVE_MONTHS) -> str:
    """The §9.5 row for the base-cost in-sample edge; precedence refuted >
    inconclusive > sign consistent (so a result that meets the refuted
    condition is never read as sign consistent)."""
    if edge["n_pos"] < min_pos:
        return ROW_NOT_INFORMATIVE
    upper = edge["bootstrap"]["delta"]["ci_high"]
    if upper < min_edge:
        return ROW_REFUTED
    if edge["delta"] > 0 and edge["mean_positive"] > 0 and edge["mean_negative"] < 0:
        return ROW_SIGN_CONSISTENT
    return ROW_INCONCLUSIVE


# --- §9.6 power ---------------------------------------------------------------------

def minimum_detectable_effect(sigma_d: float, n_pos: int, n_neg: int, z: float = POWER_Z) -> dict[str, float]:
    """``MDE = z · σ_d · sqrt(1/n_pos + 1/n_neg)`` per month and ×12 a year."""
    if n_pos <= 0 or n_neg <= 0:
        return {"per_month": float("nan"), "per_year": float("nan")}
    per_month = z * sigma_d * (1.0 / n_pos + 1.0 / n_neg) ** 0.5
    return {"per_month": float(per_month), "per_year": float(per_month * 12)}


def sigma_d_from_study_003(monthly_base_csv) -> dict:
    """σ_d from Study 003's committed in-sample ``monthly_base.csv``
    (d = T1 − B1 there; already public), as §5.3.4 and §9.6 require."""
    frame = pd.read_csv(monthly_base_csv, index_col="month")
    d = frame["T1"].astype(float) - frame["B1"].astype(float)
    return {"sigma_d_per_month": float(d.std(ddof=1)), "months": int(len(d)),
            "share_months_d_nonzero": float((d != 0).mean())}
