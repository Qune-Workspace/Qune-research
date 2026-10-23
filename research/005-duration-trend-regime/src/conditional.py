"""The conditional rule (§6.2) and the quantity on trial (§9.2).

    unconditional target (B2, Study 003's T1):  IEF if mom_t > 0 else BIL
    conditional target (T1):                     B2's target if the regime is positive, else IEF

``d_t = r(B2)_t − r(B1)_t`` per holding period, B2 at the case's switching
cost, B1 (hold IEF) without cost (§9.2).
"""
from __future__ import annotations

import pandas as pd

from .config import DURATION_LEG


def conditional_targets(trend_targets: pd.Series, positive: pd.Series) -> pd.Series:
    """§6.2 on the months both inputs cover: the trend target where the
    regime is positive, IEF otherwise.  Raises if a trend month has no
    regime flag (the regime window must be defined wherever the signal is)."""
    positive = positive.reindex(trend_targets.index)
    if positive.isna().any():
        raise ValueError(f"no regime flag on months {[str(m) for m in positive.index[positive.isna()]]}")
    out = trend_targets.astype("string").where(positive.astype(bool), DURATION_LEG)
    return out.rename("target")


def trend_minus_hold(r_b2: pd.Series, r_b1: pd.Series) -> pd.Series:
    """``d_t`` of §9.2 on B2's holding periods."""
    return (r_b2 - r_b1.reindex(r_b2.index)).rename("d")
