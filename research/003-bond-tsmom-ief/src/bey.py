"""Bill yield convention (§5.2): the discount-to-bond-equivalent conversion
only.  Copied from Study 002's ``bey.py`` (commit 2dfbdd5) without the par-bond
analytics, which this study does not use (no synthetic duration series, §15).
All yields are decimals (0.05 for 5%).
"""
from __future__ import annotations

import numpy as np

BILL_DAYS = 91           # tenor of the 3-month bill in the FRBNY convention (Study 001 §5.1)


def discount_to_bey(discount_yield):
    """Bond-equivalent yield from a discount yield, both as decimals.

    ``bey = 365 * d / (360 - 91 * d)``.
    """
    d = np.asarray(discount_yield, dtype=float)
    return 365.0 * d / (360.0 - BILL_DAYS * d)
