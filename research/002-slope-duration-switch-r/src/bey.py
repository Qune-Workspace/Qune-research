"""Yield conventions and par-bond analytics.

Implements the discount-to-bond-equivalent conversion of §5.1, the exact
par-bond repricing of §5.2 and the modified duration / convexity used by the
§5.2 cross-check and by trial T3 (§7).  All yields are decimals (0.05 for 5%).
"""
from __future__ import annotations

import numpy as np

BILL_DAYS = 91           # tenor of the 3-month bill in the FRBNY convention (§5.1)
PERIODS_PER_YEAR = 2     # semi-annual coupons (§5.2)
TEN_YEAR_PERIODS = 20    # exactly 10 years to maturity (§5.2)


def discount_to_bey(discount_yield):
    """Bond-equivalent yield from a discount yield, both as decimals (§5.1).

    ``bey = 365 * d / (360 - 91 * d)``.
    """
    d = np.asarray(discount_yield, dtype=float)
    return 365.0 * d / (360.0 - BILL_DAYS * d)


def par_bond_price(coupon, yield_, n_periods=TEN_YEAR_PERIODS):
    """Price per 100 of a bond with annual coupon ``coupon`` paid semi-annually,
    ``n_periods`` semi-annual periods to maturity, discounted at ``yield_``
    with semi-annual compounding (§5.2).

    ``P = (c/2) * 100 * (1 - (1 + y/2)^-n) / (y/2) + 100 * (1 + y/2)^-n``;
    at ``y = 0`` the annuity factor is ``n``.

    Study 002 change: ``n_periods`` may be non-integer and may be an array
    aligned with the yields (the ageing bond of §5.2 has ``2 * (8.5 - dt)``
    periods left).  For integer ``n_periods`` the value is identical to
    Study 001's.
    """
    c = np.asarray(coupon, dtype=float) / PERIODS_PER_YEAR * 100.0
    i = np.asarray(yield_, dtype=float) / PERIODS_PER_YEAR
    n = np.asarray(n_periods, dtype=float)
    discount = (1.0 + i) ** -n
    i_safe = np.where(i == 0.0, 1.0, i)
    annuity = np.where(i == 0.0, n, (1.0 - discount) / i_safe)
    return c * annuity + 100.0 * discount


def duration_convexity(coupon, yield_, n_periods: int = TEN_YEAR_PERIODS):
    """Modified duration (years) and convexity (years squared) of the bond
    priced by :func:`par_bond_price`, from the cash-flow sums.

    With periodic yield ``i = y/2``, discount factor ``v = 1/(1+i)``, cash
    flows ``CF_k`` at periods ``k = 1..n`` and price ``P``:
    ``D_mod = sum(k CF_k v^(k+1)) / P / 2`` and
    ``C = sum(k (k+1) CF_k v^(k+2)) / P / 4``, so that
    ``dP/P ~ -D_mod dy + C/2 dy^2``.
    """
    c = np.asarray(coupon, dtype=float)[..., None] / PERIODS_PER_YEAR * 100.0
    i = np.asarray(yield_, dtype=float)[..., None] / PERIODS_PER_YEAR
    k = np.arange(1, n_periods + 1, dtype=float)
    cashflows = np.broadcast_to(c, c.shape[:-1] + (n_periods,)).copy()
    cashflows[..., -1] += 100.0
    v = 1.0 / (1.0 + i)
    price = np.sum(cashflows * v ** k, axis=-1)
    d_mod = np.sum(k * cashflows * v ** (k + 1), axis=-1) / price / PERIODS_PER_YEAR
    convexity = (np.sum(k * (k + 1) * cashflows * v ** (k + 2), axis=-1)
                 / price / PERIODS_PER_YEAR ** 2)
    return d_mod, convexity


def par_modified_duration(yield_, n_periods: int = TEN_YEAR_PERIODS):
    """Modified duration in years of a par bond at ``yield_`` (used by T3, §7)."""
    d_mod, _ = duration_convexity(yield_, yield_, n_periods)
    return d_mod
