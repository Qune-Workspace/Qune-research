"""Study 011: Newey-West mean test on the two-stretch decision row O (PREREGISTRATION.md §9.3).

Bartlett kernel, 6 lags. The series is demeaned by O's overall mean; the
autocovariance at lag j sums only over pairs of months in the same stretch,
divided by O's total month count. On a single stretch it equals the shared
library's ``newey_west_mean`` (statsmodels HAC, no small-sample correction),
which the tests check.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

LAGS = 6


def newey_west_stretches(parts: list[pd.Series], lags: int = LAGS) -> dict[str, float]:
    arrays = [np.asarray(p, dtype=float) for p in parts if len(p)]
    allv = np.concatenate(arrays)
    N = len(allv)
    mu = float(allv.mean())
    us = [a - mu for a in arrays]
    s = sum(float(u @ u) for u in us) / N
    for j in range(1, lags + 1):
        wj = 1.0 - j / (lags + 1.0)
        gj = sum(float(u[j:] @ u[:-j]) for u in us if len(u) > j) / N
        s += 2.0 * wj * gj
    se = math.sqrt(s / N)
    return {"mean": mu, "se": se, "t": mu / se if se > 0 else float("nan"), "n": N, "lags": lags}
