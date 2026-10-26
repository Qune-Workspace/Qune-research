"""Study 010: signal, positions, timing costs, benchmarks and the decision difference.

PREREGISTRATION.md §6.1–§6.3, §7 and §9.1, as written there:

- formation return R_k,t = Π_{j=1..L} (1 + f_k,t−j / 100) − 1 over months
  t − L to t − 1, no skipped month; defined only when all L months exist;
- position h_k,t = +1 if R_k,t > 10⁻¹², −1 otherwise (|R| ≤ 10⁻¹² is a tie
  and takes −1; ties are counted);
- a factor is held from its trial's entry month (§6.2, fixed by the document)
  to H's end; K_t = number held; T_t = (1/K_t) Σ h_k,t f_k,t (percent a month,
  no cash return: each factor is a zero-investment long-short return);
- timing cost c × (1/K_t) Σ_k 2 |h_k,t − h_k,t−1|, with h = 0 before a
  factor's first month in the window (entry 2c, flip 4c); base c = 0.10 and
  stress c = 0.50 in percent units; reweighting when K_t changes is not
  charged; B1 and B3 pay nothing;
- B1_t = (1/K_t) Σ f_k,t over the same factors held; B3_t = (1/K_t) Σ h̄_k f_k,t
  with h̄_k the unweighted mean of h_k,t over factor k's months in H, frozen;
- d = T − B3 at base and at stress costs.

``mapping="long_flat"`` replaces h by (h + 1) / 2 (and h̄ accordingly); it
exists only to test the identity of QUESTION.md §1 (gross d exactly halves)
and is never used by a registered trial.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

TIE_TOL = 1e-12
COST_BASE = 0.10  # 10 bp of notional per dollar traded, one way, in percent units
COST_STRESS = 0.50
H_START = "1927-07"
WINDOWS = {"P1": ("1927-07", "1963-06"), "L": ("1963-07", "2015-12"), "P2": ("2016-01", None)}


@dataclass(frozen=True)
class Trial:
    trial_id: str
    formation: int
    entry: dict[str, str] = field(default_factory=dict)

    @property
    def factors(self) -> list[str]:
        return list(self.entry)


TRIALS = {
    "T1": Trial("T1", 12, {"SMB": "1927-07", "HML": "1927-07", "ST_Rev": "1927-07", "LT_Rev": "1932-01"}),
    "T1a": Trial("T1a", 12, {"SMB": "1927-07", "HML": "1927-07"}),
    "T1b": Trial("T1b", 6, {"SMB": "1927-07", "HML": "1927-07", "ST_Rev": "1927-07", "LT_Rev": "1931-07"}),
}


def _check_monthly(f: pd.DataFrame) -> None:
    if not isinstance(f.index, pd.PeriodIndex) or f.index.freqstr != "M":
        raise ValueError("factor frame needs a monthly PeriodIndex")
    if len(f.index) > 1 and not (np.diff(f.index.asi8) == 1).all():
        raise ValueError("factor frame has a month gap or is unsorted")


def formation_return(f: pd.Series, months: int) -> pd.Series:
    """R_t from f_{t−months} .. f_{t−1}; NaN unless all of them exist."""
    gross = (1.0 + f / 100.0).shift(1)
    return gross.rolling(months, min_periods=months).apply(np.prod, raw=True) - 1.0


def sign_position(r: pd.Series) -> pd.Series:
    h = pd.Series(np.where(r > TIE_TOL, 1.0, -1.0), index=r.index)
    return h.where(r.notna())


def run(f: pd.DataFrame, trial: Trial, h_end: str, cost: float, mapping: str = "pm1") -> dict:
    """Monthly series of one trial on H (1927-07 to h_end) at one cost level.

    Returns a dict with ``frame`` (columns T_gross, cost, T, B1, B3, d, K),
    ``h`` (positions held, NaN where not held), ``hbar`` (per factor) and
    ``ties`` (per factor, months in H whose formation return is a tie).
    """
    _check_monthly(f)
    start, end = pd.Period(H_START, "M"), pd.Period(h_end, "M")
    idx = pd.period_range(start, end, freq="M")
    h = pd.DataFrame(index=idx, columns=trial.factors, dtype=float)
    ties = {}
    for k, entry in trial.entry.items():
        r = formation_return(f[k], trial.formation).reindex(idx)
        held = idx >= pd.Period(entry, "M")
        if r[held].isna().any():
            raise ValueError(f"{trial.trial_id} {k}: formation return undefined in a held month")
        pos = sign_position(r).where(held)
        ties[k] = int(((r.abs() <= TIE_TOL) & held).sum())
        h[k] = pos
    if mapping == "long_flat":
        h = (h + 1.0) / 2.0
    elif mapping != "pm1":
        raise ValueError(mapping)
    fh = f.reindex(idx)[trial.factors]
    held = h.notna()
    if fh.where(held).notna().sum().sum() != held.sum().sum():
        raise ValueError(f"{trial.trial_id}: a factor return is missing in a held month (§6.5 stops the study)")
    K = held.sum(axis=1).astype(float)
    if (K == 0).any():
        raise ValueError("a month in H holds no factor")
    t_gross = (h * fh).sum(axis=1) / K
    prev = h.shift(1).where(h.shift(1).notna(), 0.0)  # 0 before a factor's first month in the window
    traded = (2.0 * (h - prev).abs()).where(held, 0.0).sum(axis=1) / K
    cost_t = cost * traded
    hbar = h.mean(axis=0)  # unweighted over each factor's held months in H (NaN skipped)
    b3 = (fh * hbar).where(held).sum(axis=1) / K
    b1 = fh.where(held).sum(axis=1) / K
    t_net = t_gross - cost_t
    frame = pd.DataFrame(
        {"T_gross": t_gross, "cost": cost_t, "T": t_net, "B1": b1, "B3": b3, "d": t_net - b3, "K": K}
    )
    return {"frame": frame, "h": h, "hbar": hbar, "ties": ties}


def static_exposure(h: pd.DataFrame, hbar: pd.Series) -> pd.Series:
    """§9.1: per factor, Σ over H of (h_k,t − h̄_k) / K_t, divided by H's month count."""
    K = h.notna().sum(axis=1)
    return ((h - hbar).div(K, axis=0)).sum(axis=0) / len(h)


def window(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    """Rows of P1, L, P2 or P (P1 and P2 together); H is the whole frame."""
    if name == "H":
        return frame
    if name == "P":
        return pd.concat([window(frame, "P1"), window(frame, "P2")])
    a, b = WINDOWS[name]
    lo = pd.Period(a, "M")
    hi = frame.index[-1] if b is None else pd.Period(b, "M")
    return frame[(frame.index >= lo) & (frame.index <= hi)]
