"""Study 011: signal, cohorts, rule return and costs (PREREGISTRATION.md §6).

Input: industry returns in percent a month as printed (rows: monthly
``pd.Period``; columns: industries in the file's order; NaN where a value is
missing, §6.5). Nothing here reads a file.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HOLD = 6  # six overlapping six-month cohorts, 1/6 each (§6.2)
TIE_DECIMALS = 10  # sort key rounds R to ten decimals (§6.1)
TIE_TOL = 1e-12  # boundary near-ties counted (§6.1)
COST_BASE = 0.10  # 10 bp one way, in percent (§6.3)
COST_STRESS = 0.50


def formation_returns(r: pd.DataFrame, F: int) -> pd.DataFrame:
    """R_i,m: compounded return over months m-F+1..m; NaN unless all F values exist (§6.1)."""
    g = 1.0 + r / 100.0
    return g.rolling(F, min_periods=F).apply(np.prod, raw=True) - 1.0


def rank_cohort(R_m: pd.Series, n: int) -> tuple[list[str], list[str], int]:
    """W(m), L(m) and the count of boundary near-ties at ranking month m.

    Sort key (-round(R, 10), column index): highest first, ties to ten
    decimals ordered by column, earlier first. Raises if fewer than 2n
    industries are eligible (the §5.4 floors keep it far above that).
    """
    elig = [(c, i, float(R_m[c])) for i, c in enumerate(R_m.index) if pd.notna(R_m[c])]
    if len(elig) < 2 * n:
        raise ValueError(f"{len(elig)} eligible industries, fewer than 2n = {2 * n}")
    order = sorted(elig, key=lambda e: (-round(e[2], TIE_DECIMALS), e[1]))
    winners = [e[0] for e in order[:n]]
    losers = [e[0] for e in order[-n:]]
    ties = 0
    for k in (n - 1, len(order) - n - 1):  # pairs (n-th, n+1-th) from the top and from the bottom
        if abs(order[k][2] - order[k + 1][2]) <= TIE_TOL:
            ties += 1
    return winners, losers, ties


def run(r: pd.DataFrame, F: int, n: int, first_holding: pd.Period) -> pd.DataFrame:
    """Monthly rule series from ``first_holding`` to the last month of ``r``.

    Columns: d_gross (percent a month), turnover (sum |w_t - w_{t-1}|),
    d_base, d_stress (after 10 / 50 bp one-way costs), winners_leg and
    losers_leg (mean over the cohorts of each leg's return) and ew (equal-weight
    mean over industries with a value), each minus nothing; empty_legs (count of
    cohort legs with no member holding a value in t), ties (boundary near-ties
    of the cohort ranked at t-1).
    """
    R = formation_returns(r, F)
    cols = list(r.columns)
    months = list(r.index)
    pos = {m: i for i, m in enumerate(months)}
    if first_holding not in pos or pos[first_holding] < HOLD:
        raise ValueError("first holding month needs six earlier ranking months inside the data")
    cohorts: dict[pd.Period, tuple[list[str], list[str]]] = {}
    ties_at: dict[pd.Period, int] = {}
    for m in months[pos[first_holding] - HOLD : -1]:
        w, lo, ties = rank_cohort(R.loc[m], n)
        cohorts[m] = (w, lo)
        ties_at[m] = ties
    rows = []
    w_prev = pd.Series(0.0, index=cols)
    for t in months[pos[first_holding] :]:
        rt = r.loc[t]
        w_t = pd.Series(0.0, index=cols)
        legs_w, legs_l, contrib, empty = [], [], [], 0
        for j in range(1, HOLD + 1):
            m = t - j
            W, L = cohorts[m]
            w_t[W] += 1.0 / (HOLD * n)
            w_t[L] -= 1.0 / (HOLD * n)
            rw, rl = rt[W].dropna(), rt[L].dropna()
            if rw.empty or rl.empty:
                empty += int(rw.empty) + int(rl.empty)
                contrib.append(0.0)  # §6.5: the cohort contributes zero in t
                continue
            legs_w.append(rw.mean())
            legs_l.append(rl.mean())
            contrib.append(rw.mean() - rl.mean())
        d = float(np.mean(contrib))
        turnover = float((w_t - w_prev).abs().sum())
        rows.append(
            {
                "month": t,
                "d_gross": d,
                "turnover": turnover,
                "d_base": d - COST_BASE * turnover,
                "d_stress": d - COST_STRESS * turnover,
                "winners_leg": float(np.mean(legs_w)) if legs_w else np.nan,
                "losers_leg": float(np.mean(legs_l)) if legs_l else np.nan,
                "ew": float(rt.dropna().mean()),
                "empty_legs": empty,
                "ties": ties_at[t - 1],
            }
        )
        w_prev = w_t
    out = pd.DataFrame(rows).set_index("month")
    out.index = pd.PeriodIndex(out.index, freq="M")
    return out


def cohort_table(r: pd.DataFrame, F: int, n: int, first_rank: pd.Period) -> dict[str, tuple[list[str], list[str], int]]:
    """W(m), L(m) and the boundary near-ties of every ranking month from ``first_rank``
    (for the per-industry shares and the tie count of §9.6)."""
    R = formation_returns(r, F)
    return {str(m): rank_cohort(R.loc[m], n) for m in R.index if m >= first_rank}
