"""Study 014 analysis (PREREGISTRATION.md §6.2, §6.3, §9.1, §9.3–§9.6): pure functions on rows and arrays.

Nothing here reads a file. The run (`src/run.py`) calls these after the reader;
the tests (tests/test_analysis.py) call them on synthetic rows.

Test variable (§6.2): mid = (bid + ask) / 2; tick = `orderPriceMinTickSize` as a
decimal, 0.001 when null or unreadable (counted), a value below 0.001 kept and
counted; q = ask - bid; s = max(q, tick) / mid, so a locked book reads tick / mid;
the test variable is ln s; the half-spread in points is q / 2 (not floored).

Bins (§6.3) on the mid rounded to nine places: longshot [0.01, 0.10), central
[0.40, 0.60], high-probability (0.90, 0.99] (reported only).

Test object (§9.1): ln s = a + Delta * L + e by OLS, so Delta-hat is exactly the
difference of the two bin means. SE_cl (§9.3) is the cluster sandwich times
G / (G - 1); SE_ordinary the homoskedastic OLS error; the clustered bootstrap
(2,000 resamples of clusters, `default_rng(14)`) drops a resample with an empty
bin and reports the interval as not available above 1 percent dropped.
No fit (§9.3): an empty decision bin, fewer than two clusters, or SE_cl of 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]

LONGSHOT, CENTRAL, HIGH = "longshot", "central", "high"
DECISION_BINS = (LONGSHOT, CENTRAL)
NULL_TICK = 0.001  # §6.2: a null or unreadable tick (the conservative side for H1; §0 item 4)
ALT_NULL_TICK = 0.01  # §9.6: the alternative floor reported beside the decision figure
MID_TOL = 1e-9  # §6.2: |mid - Study 013's p| above this is "row not as recorded"
ROUND_PLACES = 9  # §6.3
C1_BAR = 0.59  # §9.5: half the smaller published premium ln(1300 / 400) = 1.18
PUBLISHED_PREMIUM = 1.18  # [DU26], the effect the low-power ratio is measured against (§8, §9.6)
C2_T = 2.0
C3_T = 2.128  # §9.4, Bonferroni at N = 3, one-sided 0.05 / 3
K_PROGRAMME = 2.842  # 80 percent power at t >= 2.0
K_C3 = 2.970  # 80 percent power at t >= 2.128
K_ONESIDED = 2.486
LOW_POWER_RATIO = 0.50  # §8, §9.5
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 14
BOOTSTRAP_MAX_DROPPED_SHARE = 0.01
WALD_Z = 1.96
MIN_CELL = 10  # §9.6: a decile cell or split with fewer markets reports its count only (`derived` verdict)
DECILE_EDGES = tuple(i / 10 for i in range(11))  # §9.6: ten bins of mid, the last closed
WA26_SLOPE = 1.112  # [WA26] b, for the compression at a price (§9.6 secondary reading)
CR26_COMPRESSION_POINTS = (5.9, 7.3)  # [CR26] interior bins, probability points
LOW_POWER_LABEL = "(low-power check: the minimum detectable effect exceeds the pass bar, half the published premium)"


def round_mid(mid: float) -> float:
    return round(mid, ROUND_PLACES)


def assign_bin(mid: float) -> str | None:
    """§6.3 on the rounded mid; None outside the three named bins."""
    m = round_mid(mid)
    if 0.01 <= m < 0.10:
        return LONGSHOT
    if 0.40 <= m <= 0.60:
        return CENTRAL
    if 0.90 < m <= 0.99:
        return HIGH
    return None


def decile(mid: float) -> int:
    """0..9: ten bins of the rounded mid, [k/10, (k+1)/10), the last closed at 1.0."""
    m = round_mid(mid)
    k = int(math.floor(m * 10))
    return min(max(k, 0), 9)


@dataclass(frozen=True)
class Quote:
    mid: float
    q: float
    tick: float
    tick_null: bool
    tick_below: bool
    locked: bool  # q == 0
    floored: bool  # s read from the tick, not the quote (q < tick, which includes a locked book)
    s: float
    ln_s: float
    half_points: float  # q / 2 in probability points (x 100), not floored


def quote_variables(bid: float, ask: float, tick_raw: float | None, null_tick: float = NULL_TICK) -> Quote:
    """§6.2 on one row; `tick_raw` None means the field was null or unreadable."""
    mid = (bid + ask) / 2.0
    q = ask - bid
    tick_null = tick_raw is None or not math.isfinite(tick_raw) or tick_raw <= 0
    tick = null_tick if tick_null else float(tick_raw)  # type: ignore[arg-type]
    tick_below = (not tick_null) and tick < NULL_TICK
    floored = q < tick
    s = max(q, tick) / mid
    return Quote(mid=mid, q=q, tick=tick, tick_null=tick_null, tick_below=tick_below, locked=(q == 0.0),
                 floored=floored, s=s, ln_s=math.log(s), half_points=100.0 * q / 2.0)


def row_as_recorded(bid: object, ask: object, price: object) -> bool:
    """§5.4: both quotes decimal numbers in (0, 1), bid <= ask, and the mid within 1e-9 of Study 013's p."""
    if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in (bid, ask, price)):
        return False
    b, a, p = float(bid), float(ask), float(price)  # type: ignore[arg-type]
    if not (math.isfinite(b) and math.isfinite(a) and 0.0 < b < 1.0 and 0.0 < a < 1.0 and b <= a):
        return False
    return abs((a + b) / 2.0 - p) <= MID_TOL


@dataclass
class Fit:
    n: int
    n_longshot: int
    n_central: int
    G: int
    fitted: bool
    no_fit_reason: str | None
    alpha: float
    delta: float
    se_cl: float
    se_ordinary: float
    t_cl: float
    sd_longshot: float
    sd_central: float

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _no_fit(n: int, n1: int, n0: int, g: int, reason: str, sd1: float = float("nan"), sd0: float = float("nan")) -> Fit:
    nan = float("nan")
    return Fit(n, n1, n0, g, False, reason, nan, nan, nan, nan, nan, sd1, sd0)


def _design(L: Array) -> tuple[Array, Array]:
    X = np.column_stack([np.ones_like(L), L])
    xtx_inv = np.linalg.inv(X.T @ X)
    return X, xtx_inv


def fit_delta(ln_s: Array, L: Array, clusters: Array) -> Fit:
    """§9.1 and §9.3 on the rows of the two decision bins (L = 1 longshot, 0 central)."""
    y = np.asarray(ln_s, dtype=np.float64)
    L = np.asarray(L, dtype=np.float64)
    g = np.asarray(clusters)
    n = int(y.size)
    n1, n0 = int(np.sum(L == 1)), int(np.sum(L == 0))
    G = int(np.unique(g).size) if n else 0
    sd1 = float(np.std(y[L == 1], ddof=1)) if n1 > 1 else float("nan")
    sd0 = float(np.std(y[L == 0], ddof=1)) if n0 > 1 else float("nan")
    if n1 == 0 or n0 == 0:
        return _no_fit(n, n1, n0, G, "empty decision bin", sd1, sd0)
    if G < 2:
        return _no_fit(n, n1, n0, G, "fewer than two clusters", sd1, sd0)
    X, xtx_inv = _design(L)
    beta = xtx_inv @ (X.T @ y)
    e = y - X @ beta
    # cluster sandwich with G / (G - 1)
    meat = np.zeros((2, 2))
    for cid in np.unique(g):
        sg = (X[g == cid] * e[g == cid, None]).sum(axis=0)
        meat += np.outer(sg, sg)
    v_cl = (G / (G - 1)) * xtx_inv @ meat @ xtx_inv
    se_cl = float(np.sqrt(v_cl[1, 1])) if v_cl[1, 1] > 0 else 0.0
    if n > 2:
        sigma2 = float(e @ e) / (n - 2)
        se_ord = float(np.sqrt(sigma2 * xtx_inv[1, 1]))
    else:
        se_ord = float("nan")
    if not (se_cl > 0) or not math.isfinite(se_cl):
        return _no_fit(n, n1, n0, G, "SE_cl is 0", sd1, sd0)
    delta = float(beta[1])
    return Fit(n, n1, n0, G, True, None, float(beta[0]), delta, se_cl, se_ord, delta / se_cl, sd1, sd0)


def hc0_se_delta(ln_s: Array, L: Array) -> float:
    """The unclustered HC0 sandwich standard error of Delta (a test reference: with one row per cluster,
    SE_cl^2 = n / (n - 1) times this squared)."""
    y = np.asarray(ln_s, dtype=np.float64)
    L = np.asarray(L, dtype=np.float64)
    X, xtx_inv = _design(L)
    e = y - X @ (xtx_inv @ (X.T @ y))
    meat = (X * e[:, None]).T @ (X * e[:, None])
    v = xtx_inv @ meat @ xtx_inv
    return float(np.sqrt(v[1, 1]))


@dataclass
class Bootstrap:
    low: float
    high: float
    resamples: int
    dropped: int
    available: bool


def cluster_bootstrap(ln_s: Array, L: Array, clusters: Array, resamples: int = BOOTSTRAP_RESAMPLES,
                      seed: int = BOOTSTRAP_SEED) -> Bootstrap:
    """§9.3: percentile interval of Delta over resamples of clusters with replacement; a resample with an empty
    bin is dropped and counted; not available when more than 1 percent were dropped."""
    y = np.asarray(ln_s, dtype=np.float64)
    L = np.asarray(L, dtype=np.float64)
    g = np.asarray(clusters)
    ids = np.unique(g)
    members = {cid: np.flatnonzero(g == cid) for cid in ids}
    rng = np.random.default_rng(seed)
    out: list[float] = []
    dropped = 0
    for _ in range(resamples):
        draw = rng.choice(ids, size=ids.size, replace=True)
        idx = np.concatenate([members[c] for c in draw])
        Ls, ys = L[idx], y[idx]
        if not np.any(Ls == 1) or not np.any(Ls == 0):
            dropped += 1
            continue
        out.append(float(ys[Ls == 1].mean() - ys[Ls == 0].mean()))
    available = dropped <= BOOTSTRAP_MAX_DROPPED_SHARE * resamples and len(out) >= 2
    if not available:
        return Bootstrap(float("nan"), float("nan"), resamples, dropped, False)
    lo, hi = np.percentile(np.array(out), [2.5, 97.5])
    return Bootstrap(float(lo), float(hi), resamples, dropped, True)


def power(se_cl: float) -> dict[str, float]:
    """§9.6: MDE = K * SE at the three K, and the ratio the low-power label reads."""
    return {
        "mde_2.842": K_PROGRAMME * se_cl,
        "mde_2.970": K_C3 * se_cl,
        "mde_2.486": K_ONESIDED * se_cl,
        "ratio": K_PROGRAMME * se_cl / PUBLISHED_PREMIUM,
    }


def wald(fit: Fit) -> tuple[float, float]:
    if not fit.fitted:
        return float("nan"), float("nan")
    return fit.delta - WALD_Z * fit.se_cl, fit.delta + WALD_Z * fit.se_cl


def criteria(w: Fit, w1: Fit, w2: Fit) -> dict[str, bool]:
    """§9.5 C1–C4 for one trial; every criterion False when W has no fit."""
    if not w.fitted:
        return {"C1": False, "C2": False, "C3": False, "C4": False}
    return {
        "C1": w.delta >= C1_BAR,
        "C2": w.t_cl >= C2_T,
        "C3": w.t_cl >= C3_T,
        "C4": w1.fitted and w2.fitted and w1.delta > 0 and w2.delta > 0,
    }


def companion_row(w: Fit, crit: dict[str, bool]) -> str:
    if not w.fitted:
        return "not supported (no fit)"
    return "meets C1–C4" if all(crit.values()) else "not supported"


def headline(m1: Fit, m1_crit: dict[str, bool], m1a_row: str, low_power: bool) -> str:
    """§9.5 verdict for M1 with its precedence (halts are decided before this is called)."""
    if not m1.fitted:
        text = "not supported (no fit)"
    elif not all(m1_crit.values()):
        if 0.0 < m1.delta < C1_BAR:
            text = f"not supported (a premium below half the published size: Δ̂ = {m1.delta:.3f}, t_cl = {m1.t_cl:.2f})"
        else:
            text = "not supported"
    elif m1a_row.startswith("not supported"):
        text = "inconclusive (fragile: Sports)"
    else:
        text = "supported in one forward window (W: resolution time in [2026-11-04, 2026-12-30))"
    return f"{text} {LOW_POWER_LABEL}" if low_power else text


def wa26_compression_points(mid: float) -> float:
    """|p - sigma(b * logit p)| in probability points under [WA26]'s slope: about 1.4 at 0.05, 1.1 at 0.60."""
    x = math.log(mid) - math.log1p(-mid)
    fitted = 1.0 / (1.0 + math.exp(-WA26_SLOPE * x))
    return 100.0 * abs(mid - fitted)


def median_or_nan(values: list[float]) -> float:
    return float(np.median(values)) if values else float("nan")
