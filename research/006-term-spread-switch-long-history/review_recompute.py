"""Separate-session recomputation for REVIEW.md (Study 006, term-spread
duration switch on the 1969-2018 history with a decision-tied fidelity gate).

Written by the reviewer (Tester, a separate agent session that did not write
the code, the pre-registration or the note).  It imports nothing from the
study's ``src/`` or from the shared library ``qune_research``: every number is
re-derived with numpy, pandas and scipy only, from

  * the raw files in ``data/raw/`` (git-ignored; present on disk at review
    time): FRED DGS7, DGS10, DTB3; Tiingo ``adjClose`` for IEF and BIL; the
    broker's ``adjustment='all'`` closes for IEF and BIL;
  * the committed outputs: ``results/gate/``, ``results/volcheck/``,
    ``results/history/``, ``results/episode/``, ``results/data_manifest.json``,
    ``charts/manifest.json`` and the four SVG titles.

With the raw files the reviewer rebuilds the synthetic legs (Study 002 §5.2
and Study 001 §5.2 as written), the signal dates, a rule-based NYSE calendar,
the signals of T1-T3, B0-B3 and T1-T3 at both cost levels, the gate quantities
h, x, g and e, the volatility check, the episode on actual and synthetic
instruments, and compares each to the committed files.  Every published
statistic (twelve metrics, Newey-West t, Ledoit-Wolf p, stationary-bootstrap
Sharpe interval with the committed seed, DSR at N = 3 / 10 / family, the §9.5
row, sub-windows, mechanism check, NW/i.i.d. ratio) is recomputed from the
committed monthly files with the reviewer's own statistics code.  Values that
exist only in README.md or in chart titles are typed in below, marked README
or CHART, and compared at their printed rounding.  Nothing is written to disk.

Conventions the pre-registration leaves to the code and that the reviewer
reproduced rather than chose: the first holding starts in cash so a first
target of IEF pays a switch (Study 001 §6.6); B2/B3 pay the per-side cost on
the drift of the IEF weight; the random draws per cost case are, in order,
T1 Sharpe interval, T1 Ledoit-Wolf vs B1, vs B3, then T2 and T3 likewise,
from ``numpy.random.default_rng(20261021)``.

Run from the study folder:  ../../.venv/bin/python review_recompute.py
Exit status is 1 if any row mismatches.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

STUDY = Path(__file__).resolve().parent
RES = STUDY / "results"
RAW = STUDY / "data" / "raw"
SQ12 = math.sqrt(12.0)
NW_LAGS = 6
IEF_EXPENSE, BIL_EXPENSE = 0.0015, 0.001356          # Study 002 §5.2, Study 001 §5.2
COSTS = {"base": 2e-4, "stress": 4e-4}               # Study 001 §9.2
SEED, RESAMPLES, BLOCK = 20261021, 10_000, 12        # Study 002 config / Study 001 §9.3
DSR_FLOOR = (0.05 / SQ12) ** 2                       # Study 001 §9.4
G1_MAX, G2_MAX, VOL_BAR, DESIGN_MDE = 0.0018, 0.32, 0.1018, 0.02   # §5.3.3, §5.4
STRATS = ("B0", "B1", "B2", "B3", "T1", "T2", "T3")
TRIALS = ("T1", "T2", "T3")
SUB_WINDOWS = {"1969-08 to 2002-12 (before any ETF)": ("1969-08", "2002-12"),
               "2003-01 to 2018-12 (the gate's overlap)": ("2003-01", "2018-12")}
SUBPERIODS = {"1969-08 to 1981-12 (rising rates)": ("1969-08", "1981-12"),
              "1982-01 to 2008-12 (disinflation)": ("1982-01", "2008-12"),
              "2009-01 to 2018-12 (zero lower bound and QE)": ("2009-01", "2018-12")}

rows: list[tuple[str, str, str, str]] = []


def add(claim, published, recomputed, tol=0.0, fmt="{:.4f}", note=""):
    suffix = f" ({note})" if note else ""
    if published is None:
        shown = fmt.format(recomputed) if isinstance(recomputed, (int, float, np.floating, np.integer)) else str(recomputed)
        rows.append((claim, "n/a", shown, "informational" + suffix))
        return
    if isinstance(published, (str, bool, np.bool_)) or isinstance(recomputed, (str, bool, np.bool_)):
        ok = str(published) == str(recomputed)
        rows.append((claim, str(published), str(recomputed), ("yes" if ok else "NO") + suffix))
        return
    p, r = float(published), float(recomputed)
    if math.isnan(p) and math.isnan(r):
        rows.append((claim, "nan", "nan", "yes" + suffix))
        return
    ok = abs(p - r) <= tol
    show = (lambda x: fmt.format(int(round(x)))) if "d}" in fmt else (lambda x: fmt.format(x))
    rows.append((claim, show(p), show(r), ("yes" if ok else "NO") + suffix))


def pct(x, decimals=1):
    """Percent with a typographic minus, as the charts print it."""
    return f"{x * 100:.{decimals}f}%".replace("-", "−")


def add_typed(claim, typed, recomputed, decimals, scale=1.0, src="README"):
    """A value printed with ``decimals`` digits after dividing by ``scale`` (0.01 for %)."""
    add(f"{claim} [{src}]", typed, recomputed / scale, 0.5 * 10 ** (-decimals) + 1e-12, "{:." + str(decimals) + "f}")


# ----------------------------------------------------------------------------- statistics (reviewer's own)
def geo_annual(r):
    return float(np.prod(1.0 + r) ** (12.0 / len(r)) - 1.0)


def vol_annual(r):
    return float(np.std(r, ddof=1) * SQ12)


def sharpe_m(x):
    sd = np.std(x, ddof=1)
    return float(np.mean(x) / sd) if sd > 0 else float("nan")


def max_dd(r):
    lv = np.cumprod(1.0 + np.asarray(r, dtype=float))
    return float(np.min(lv / np.maximum.accumulate(lv) - 1.0))


def skew_kurt(x):
    x = np.asarray(x, dtype=float)
    z = (x - x.mean()) / x.std(ddof=0)
    return float((z ** 3).mean()), float((z ** 4).mean())


def nw_mean(x, lags=NW_LAGS):
    """Mean and Bartlett-kernel HAC standard error (``lags`` lags, no small-sample factor), hand-coded."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    u = x - x.mean()
    s = float(u @ u)
    for j in range(1, lags + 1):
        s += 2.0 * (1.0 - j / (lags + 1.0)) * float(u[j:] @ u[:-j])
    se = math.sqrt(s) / n
    return float(x.mean()), se, float(x.mean() / se)


def sb_indices(rng, n, n_resamples=RESAMPLES, block=BLOCK):
    """Stationary bootstrap (Politis-Romano): geometric blocks of mean ``block``, circular wrap."""
    restart = rng.random(size=(n_resamples, n)) < 1.0 / block
    fresh = rng.integers(0, n, size=(n_resamples, n))
    idx = np.empty((n_resamples, n), dtype=np.int64)
    idx[:, 0] = fresh[:, 0]
    for t in range(1, n):
        idx[:, t] = np.where(restart[:, t], fresh[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def boot_sharpe(x, rng):
    s = np.asarray(x, dtype=float)[sb_indices(rng, len(x))]
    sr = s.mean(axis=1) / s.std(axis=1, ddof=1) * SQ12
    return np.quantile(sr, [0.025, 0.975])


def cb_indices(rng, n, n_resamples=RESAMPLES, block=BLOCK):
    """Circular block bootstrap with fixed block length (Ledoit-Wolf 2008)."""
    n_blocks = -(-n // block)
    starts = rng.integers(0, n, size=(n_resamples, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_resamples, -1)
    return idx[:, :n] % n


def lw_diff_se(r1, r2, lags=NW_LAGS):
    """Sharpe difference (monthly, population moments) and its HAC se by the delta method on
    (mu1, E r1^2, mu2, E r2^2), for batches (b, n); Ledoit and Wolf (2008), section 3."""
    n = r1.shape[1]
    y = np.stack([r1, r1 ** 2, r2, r2 ** 2], axis=-1)
    a, b, c, d = y.mean(axis=1).T
    v1, v2 = b - a ** 2, d - c ** 2
    diff = a / np.sqrt(v1) - c / np.sqrt(v2)
    grad = np.stack([b / v1 ** 1.5, -0.5 * a / v1 ** 1.5, -d / v2 ** 1.5, 0.5 * c / v2 ** 1.5], axis=-1)
    z = y - y.mean(axis=1, keepdims=True)
    cov = np.einsum("bti,btj->bij", z, z) / n
    for lag in range(1, lags + 1):
        g = np.einsum("bti,btj->bij", z[:, lag:, :], z[:, :-lag, :]) / n
        cov += (1.0 - lag / (lags + 1.0)) * (g + g.transpose(0, 2, 1))
    se = np.sqrt(np.einsum("bi,bij,bj->b", grad, cov, grad) / n)
    return diff, se


def ledoit_wolf_p(x1, x2, rng):
    """Studentised circular block bootstrap p-value for equal Sharpe ratios."""
    x1, x2 = np.asarray(x1, dtype=float), np.asarray(x2, dtype=float)
    d0, s0 = lw_diff_se(x1[None, :], x2[None, :])
    t0 = float(d0[0] / s0[0])
    idx = cb_indices(rng, len(x1))
    extremes = 0
    with np.errstate(invalid="ignore"):
        for start in range(0, RESAMPLES, 500):
            b = idx[start:start + 500]
            d, s = lw_diff_se(x1[b], x2[b])
            extremes += int((np.abs((d - d0[0]) / s) >= abs(t0)).sum())
    return extremes / RESAMPLES, t0


def dsr(sr, n_obs, skew, kurt, n_trials, var_trials):
    g = 0.5772156649015329
    sr_star = math.sqrt(var_trials) * ((1 - g) * norm.ppf(1 - 1 / n_trials) + g * norm.ppf(1 - 1 / (n_trials * math.e)))
    den = math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr ** 2)
    psr = float(norm.cdf(sr * math.sqrt(n_obs - 1) / den))
    return sr_star, psr, float(norm.cdf((sr - sr_star) * math.sqrt(n_obs - 1) / den))


def episodes(flags):
    f = np.asarray(flags, dtype=bool)
    starts = f & ~np.concatenate([[False], f[:-1]])
    return int(f.sum()), int(starts.sum())


# ----------------------------------------------------------------------------- reviewer's own NYSE calendar
def easter(year):
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def nth_weekday(year, month, weekday, n):
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def last_weekday(year, month, weekday):
    last = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def observed(d):
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


SPECIAL = {"1963-11-25", "1968-02-12", "1968-04-09", "1968-07-05", "1969-02-10", "1969-03-31", "1969-07-21",
           "1972-12-28", "1973-01-25", "1977-07-14", "1985-09-27", "1994-04-27", "2001-09-11", "2001-09-12",
           "2001-09-13", "2001-09-14", "2004-06-11", "2007-01-02", "2012-10-29", "2012-10-30", "2018-12-05",
           "2025-01-09"}


def nyse_closed(year):
    h = set()
    ny = date(year, 1, 1)
    if ny.weekday() == 6:
        h.add(ny + timedelta(days=1))
    elif ny.weekday() < 5:
        h.add(ny)
    if year >= 1998:
        h.add(nth_weekday(year, 1, 0, 3))
    h.add(nth_weekday(year, 2, 0, 3) if year >= 1971 else observed(date(year, 2, 22)))
    h.add(easter(year) - timedelta(days=2))
    h.add(last_weekday(year, 5, 0) if year >= 1971 else observed(date(year, 5, 30)))
    if year >= 2022:
        h.add(observed(date(year, 6, 19)))
    h.add(observed(date(year, 7, 4)))
    h.add(nth_weekday(year, 9, 0, 1))
    if year <= 1968 or year in (1972, 1976, 1980):
        h.add(nth_weekday(year, 11, 0, 1) + timedelta(days=1))
    h.add(nth_weekday(year, 11, 3, 4))
    h.add(observed(date(year, 12, 25)))
    h.update(date.fromisoformat(s) for s in SPECIAL if s.startswith(str(year)))
    if year == 1968:
        w = date(1968, 6, 12)
        while w <= date(1968, 12, 31):
            if w not in (date(1968, 7, 3), date(1968, 9, 4)):
                h.add(w)
            w += timedelta(days=7)
    return {pd.Timestamp(d) for d in h if d.weekday() < 5}


def nyse_days(start, end):
    days = pd.bdate_range(start, end)
    closed = set()
    for y in range(days[0].year, days[-1].year + 1):
        closed |= nyse_closed(y)
    return days[~days.isin(closed)]


# ----------------------------------------------------------------------------- reviewer's own data and legs
def fred(series):
    raw = pd.read_csv(RAW / f"fred_{series}.csv", dtype=str, keep_default_na=False)
    v = pd.to_numeric(raw.iloc[:, 1].str.strip().replace({"": np.nan, ".": np.nan}), errors="coerce")
    return pd.Series(v.to_numpy(dtype=float), index=pd.to_datetime(raw.iloc[:, 0]))


def bey(d):
    return 365.0 * d / (360.0 - 91.0 * d)


def bond_price(c, y, m):
    """Price per 100 of a bond with annual coupon c paid semi-annually, m (non-integer) periods left, yield y."""
    i = np.asarray(y, dtype=float) / 2.0
    m = np.asarray(m, dtype=float)
    disc = (1.0 + i) ** -m
    ann = np.where(i == 0.0, m, (1.0 - disc) / np.where(i == 0.0, 1.0, i))
    return 100.0 * (np.asarray(c, dtype=float) / 2.0 * ann + disc)


def par_dmod(y, n=20):
    """Modified duration of a par bond with n semi-annual periods, from the cash flows (reviewer's own)."""
    y = np.asarray(y, dtype=float)
    i = y[:, None] / 2.0
    k = np.arange(1, n + 1, dtype=float)
    cf = np.broadcast_to(y[:, None] / 2.0 * 100.0, (len(y), n)).copy()
    cf[:, -1] += 100.0
    v = 1.0 / (1.0 + i)
    price = (cf * v ** k).sum(axis=1)
    return (k * cf * v ** (k + 1)).sum(axis=1) / price / 2.0


def duration_leg(dgs7, dgs10):
    """Study 002 §5.2: 8.5-year par bond bought at the interpolated yield at s, repriced at t at the
    interpolated par yield for 8.5 - dt years, plus coupon accrual, minus the expense ratio pro rata."""
    both = pd.concat([dgs7.rename("y7"), dgs10.rename("y10")], axis=1).dropna() / 100.0
    idx = both.index
    days = np.diff(idx.to_numpy()).astype("timedelta64[D]").astype(float)
    dt = days / 365.0
    y7s, y10s = both["y7"].to_numpy()[:-1], both["y10"].to_numpy()[:-1]
    y7t, y10t = both["y7"].to_numpy()[1:], both["y10"].to_numpy()[1:]
    y_s = y7s + (y10s - y7s) * (8.5 - 7.0) / 3.0
    y_t = y7t + (y10t - y7t) * (8.5 - dt - 7.0) / 3.0
    p_t = bond_price(y_s, y_t, 2.0 * (8.5 - dt))
    r = (p_t / 100.0 - 1.0) + y_s * dt - IEF_EXPENSE * dt
    tri = np.concatenate([[1.0], np.cumprod(1.0 + r)])
    return pd.Series(tri, index=idx)


def cash_leg(dtb3):
    v = dtb3.dropna() / 100.0
    days = np.diff(v.index.to_numpy()).astype("timedelta64[D]").astype(float)
    r = (bey(v.to_numpy()[:-1]) - BIL_EXPENSE) * days / 365.0
    return pd.Series(np.concatenate([[1.0], np.cumprod(1.0 + r)]), index=v.index)


def schedule(dgs10, dtb3, first, last):
    both = pd.concat([dgs10, dtb3], axis=1).dropna()
    valid = pd.Series(both.index, index=both.index)
    sig = valid.groupby(valid.index.to_period("M")).last().loc[pd.Period(first, "M"):pd.Period(last, "M")]
    days = nyse_days(sig.iloc[0], sig.iloc[-1] + pd.Timedelta(days=10))
    exe = pd.Series(pd.DatetimeIndex(days[days.searchsorted(sig.to_numpy(), side="right")]), index=sig.index)
    out = pd.DataFrame({"signal_date": sig, "execution_date": exe})
    out["period_end"] = out["execution_date"].shift(-1)
    out.index.name = "month"
    return out.iloc[:-1]


def level_at(tri, dates):
    return tri.reindex(pd.DatetimeIndex(dates), method="ffill").to_numpy()


def period_returns(tri, sched):
    return pd.Series(level_at(tri, sched["period_end"]) / level_at(tri, sched["execution_date"]) - 1.0, index=sched.index)


def signals(dgs10, dgs7, dtb3, sched):
    both = pd.concat([dgs10.rename("y10"), dtb3.rename("d3")], axis=1).dropna()
    spread = both["y10"] / 100.0 - bey(both["d3"] / 100.0)
    t2 = spread.rolling(21, min_periods=21).mean()
    three = pd.concat([dgs10.rename("y10"), dgs7.rename("y7"), dtb3.rename("d3")], axis=1).dropna() / 100.0
    carry = (three["y10"] - bey(three["d3"])) + par_dmod(three["y10"].to_numpy()) * (three["y10"] - three["y7"]) / 3.0
    sd = sched["signal_date"]
    return {"T1": pd.Series(spread.loc[sd].to_numpy(), index=sd.index),
            "T2": pd.Series(t2.loc[sd].to_numpy(), index=sd.index),
            "T3": pd.Series(carry.reindex(sd).to_numpy(), index=sd.index)}


def run_switching(targets, r_ief, r_bil, cost):
    holding, out, sw = "BIL", [], 0
    for m in targets.index:
        switched = targets.loc[m] != holding
        holding = targets.loc[m]
        gross = r_ief.loc[m] if holding == "IEF" else r_bil.loc[m]
        out.append(((1.0 - cost) ** 2 if switched else 1.0) * (1.0 + gross) - 1.0)
        sw += int(switched)
    return pd.Series(out, index=targets.index), sw


def run_static(w, r_ief, r_bil, cost):
    ri, rb = r_ief.to_numpy(), r_bil.to_numpy()
    gross = w * ri + (1 - w) * rb
    drift = np.empty_like(gross)
    drift[0] = w
    drift[1:] = w * (1 + ri[:-1]) / (1 + gross[:-1])
    return pd.Series((1.0 - cost * np.abs(drift - w)) ** 2 * (1 + gross) - 1, index=r_ief.index)


def rebuild(tri, sched, sig, weight=None):
    r_ief, r_bil = period_returns(tri["IEF"], sched), period_returns(tri["BIL"], sched)
    targets = {t: pd.Series(np.where(sig[t] > 0, "IEF", "BIL"), index=sched.index) for t in TRIALS}
    w = weight if weight is not None else float((targets["T1"] == "IEF").mean())
    cases = {}
    for case, c in COSTS.items():
        res = {"B0": r_bil.copy(), "B1": r_ief.copy(), "B2": run_static(0.5, r_ief, r_bil, c),
               "B3": run_static(w, r_ief, r_bil, c)}
        sw = {}
        for t in TRIALS:
            res[t], sw[t] = run_switching(targets[t], r_ief, r_bil, c)
        cases[case] = {"res": res, "switches": sw}
    return {"r_ief": r_ief, "r_bil": r_bil, "targets": targets, "w": w, "cases": cases}


def daily_strategy_mdd(targets, sched, tri, cost, include_start):
    """Daily index of a switching book from the held instrument's daily index; cost at the execution close."""
    holding, level, pieces = "BIL", 1.0, []
    for m, row in sched.iterrows():
        tgt = targets.loc[m]
        if tgt != holding:
            level *= (1.0 - cost) ** 2
        holding = tgt
        held = tri[holding]
        base = held.reindex([row["execution_date"]], method="ffill").iloc[0]
        rel = held.loc[row["execution_date"]:row["period_end"]] / base
        if rel.index[0] == row["execution_date"]:
            rel = rel.iloc[1:]
        pieces.append(level * rel)
        level = pieces[-1].iloc[-1]
    path = pd.concat(pieces)
    if include_start:
        path = pd.concat([pd.Series([1.0], index=[sched["execution_date"].iloc[0]]), path])
    return float((path / path.cummax() - 1.0).min())


# ----------------------------------------------------------------------------- committed files
def load(folder):
    f = {}
    for case in COSTS:
        m = pd.read_csv(RES / folder / f"monthly_{case}.csv", index_col=0)
        m.index = pd.PeriodIndex(m.index, freq="M")
        for c in ("execution_date", "period_end"):
            m[c] = pd.to_datetime(m[c])
        f[f"monthly_{case}"] = m
        f[f"met_{case}"] = pd.read_csv(RES / folder / f"metrics_{case}.csv", index_col=0)
    return f


def check_window(label, f, summ, weight_frozen=None, with_daily=False):
    """Everything published for one window, from its committed monthly files."""
    mb = f["monthly_base"]
    n = len(mb)
    add(f"{label} holding periods", summ["holding_periods"], n, 0, "{:d}")
    add(f"{label} first execution date", summ["first_execution_date"], str(mb["execution_date"].iloc[0].date()))
    add(f"{label} last period end", summ["last_period_end"], str(mb["period_end"].iloc[-1].date()))
    add(f"{label} period_end equals the next execution date", True,
        bool((mb["period_end"].iloc[:-1].to_numpy() == mb["execution_date"].iloc[1:].to_numpy()).all()))
    add(f"{label} T1_holding = IEF iff spread_at_signal > 0", True, bool(((mb["spread_at_signal"] > 0) == (mb["T1_holding"] == "IEF")).all()))
    add(f"{label} months without signal", 0, summ["months_without_signal"], 0, "{:d}")
    out = {}
    for case in COSTS:
        m, met, base = f[f"monthly_{case}"], f[f"met_{case}"], summ["cost_cases"][case]
        cl = f"{label} {case}"
        add(f"{cl} cost per side", COSTS[case], base["cost_per_side"], 1e-15, "{:.4f}")
        b0 = m["B0"]
        ex = {}
        for s in STRATS:
            r = m[s].to_numpy()
            e = (m[s] - b0).to_numpy()
            ex[s] = e
            d = base["descriptive"][s]
            add(f"{cl} {s} periods", met.at[s, "periods"], len(r), 0, "{:d}")
            add(f"{cl} {s} ann. geometric return", met.at[s, "ann_geometric_return"], geo_annual(r), 1e-12, "{:.4%}")
            add(f"{cl} {s} ann. volatility", met.at[s, "ann_volatility"], vol_annual(r), 1e-12, "{:.4%}")
            add(f"{cl} {s} Sharpe annual", met.at[s, "sharpe_annual"], sharpe_m(e) * SQ12, 1e-10, "{:.4f}")
            add(f"{cl} {s} Sharpe monthly", met.at[s, "sharpe_monthly"], sharpe_m(e), 1e-10, "{:.6f}")
            add(f"{cl} {s} max drawdown (monthly)", met.at[s, "max_drawdown_monthly"], max_dd(r), 1e-12, "{:.3%}")
            add(f"{cl} {s} mean excess monthly", met.at[s, "mean_excess_monthly"], float(e.mean()), 1e-15, "{:+.6f}")
            add(f"{cl} {s} hit rate (excess > 0)", met.at[s, "hit_rate_positive_excess"], float((e > 0).mean()), 1e-12)
            if s != "B0":
                sk, ku = skew_kurt(e)
                add(f"{cl} {s} skewness of excess", met.at[s, "skewness_excess"], sk, 1e-10, "{:.4f}")
                add(f"{cl} {s} kurtosis of excess", met.at[s, "kurtosis_excess"], ku, 1e-10, "{:.4f}")
            add(f"{cl} {s} summary descriptive Sharpe = metrics CSV", d["sharpe_annual"], met.at[s, "sharpe_annual"], 1e-12, "{:.6f}")
            ief_better = m["B1"] > m["B0"]
            if s == "B1":
                add(f"{cl} B1 hit rate held vs other", met.at[s, "hit_rate_held_vs_other"], float(ief_better.mean()), 1e-12)
            if s == "B0":
                add(f"{cl} B0 hit rate held vs other", met.at[s, "hit_rate_held_vs_other"], float((~ief_better).mean()), 1e-12)
        # holdings of T1 from the monthly file; T2/T3 holdings from their returns
        hold = {"T1": m["T1_holding"]}
        for t in ("T2", "T3"):
            hold[t] = pd.Series(np.where(np.isclose(m[t], m["B1"]) | (np.isclose((1 + m[t]) / (1 + m["B1"]), (1 - COSTS[case]) ** 2)), "IEF", "BIL"), index=m.index)
        for t in TRIALS:
            h = hold[t]
            prev = h.shift(1).fillna("BIL")
            sw = int((h != prev).sum())
            add(f"{cl} {t} switches per year", met.at[t, "switches_per_year"], sw / (n / 12), 1e-12)
            add(f"{cl} {t} share of periods in IEF", met.at[t, "fraction_in_ief"], float((h == "IEF").mean()), 1e-12)
            held_minus_other = np.where(h == "IEF", m["B1"] - m["B0"], m["B0"] - m["B1"])
            add(f"{cl} {t} hit rate held vs other", met.at[t, "hit_rate_held_vs_other"], float((held_minus_other > 0).mean()), 1e-12)
            r_t, _ = run_switching(h, m["B1"], m["B0"], COSTS[case])
            add(f"{cl} {t} monthly return rebuilt from B1, B0 and its holdings with the switch cost (max abs diff)", 0.0,
                float((r_t - m[t]).abs().max()), 1e-15, "{:.1e}")
            if case == "base" and t == "T1":
                out["t1_switches"] = sw
        w = float(met.at["B3", "fraction_in_ief"])
        add(f"{cl} B3 weight in metrics = summary weight_b3", summ["weight_b3"], w, 1e-15, "{:.6f}")
        if weight_frozen is None:
            add(f"{cl} B3 weight = T1's share in IEF", w, float((m["T1_holding"] == "IEF").mean()), 1e-15, "{:.6f}")
        else:
            add(f"{cl} B3 weight is the frozen history weight", weight_frozen, w, 1e-15, "{:.6f}")
        for b, wb in (("B2", 0.5), ("B3", w)):
            add(f"{cl} {b} rebuilt from B1 and B0 with the drift-rebalancing cost (max abs diff)", 0.0,
                float((run_static(wb, m["B1"], m["B0"], COSTS[case]) - m[b]).abs().max()), 1e-15, "{:.1e}")
        # inference: same draw order as the engine, one generator per cost case
        rng = np.random.default_rng(SEED)
        for t in TRIALS:
            inf = base["inference"][t]
            lo, hi = boot_sharpe(ex[t], rng)
            add(f"{cl} {t} Sharpe bootstrap 95% low (seed 20261021, stationary, block 12, 10,000)", inf["sharpe_ci"]["ci_low"], lo, 1e-12, "{:+.4f}")
            add(f"{cl} {t} Sharpe bootstrap 95% high", inf["sharpe_ci"]["ci_high"], hi, 1e-12, "{:+.4f}")
            add(f"{cl} {t} bootstrap settings", "10000/12/0.95", f"{inf['sharpe_ci']['resamples']}/{inf['sharpe_ci']['expected_block']}/{inf['sharpe_ci']['level']}")
            for b in ("B1", "B3"):
                diff = (m[t] - m[b]).to_numpy()
                mean, se, tt = nw_mean(diff)
                nw = inf[f"vs_{b}"]["newey_west"]
                add(f"{cl} {t} mean({t} - {b})", nw["mean"], mean, 1e-15, "{:+.6f}")
                add(f"{cl} {t} Newey-West se vs {b} (Bartlett 6 lags, hand-coded)", nw["se"], se, 1e-12, "{:.6f}")
                add(f"{cl} {t} Newey-West t vs {b}", nw["t"], tt, 1e-8, "{:.4f}")
                add(f"{cl} {t} Newey-West lags / n", "6/" + str(n), f"{nw['lags']}/{nw['n']}")
                p, t0 = ledoit_wolf_p(ex[t], ex[b], rng)
                lw = inf[f"vs_{b}"]["ledoit_wolf"]
                add(f"{cl} {t} Ledoit-Wolf t vs {b} (delta method, HAC 6 lags)", lw["t"], t0, 1e-8, "{:.4f}")
                add(f"{cl} {t} Ledoit-Wolf p vs {b} (studentised circular block bootstrap)", lw["p_value"], p, 1.01e-4,
                    note="tolerance one resample in 10,000: a degenerate resample can sit on the |t*| >= |t| boundary")
                if t == "T1" and b == "B3":
                    iid = float(np.std(diff, ddof=1) / math.sqrt(n))
                    if "nw_iid_ratio_vs_B3" in base:
                        add(f"{cl} T1 NW/i.i.d. se ratio vs B3", base["nw_iid_ratio_vs_B3"]["T1"]["ratio"], se / iid, 1e-12)
                        add(f"{cl} T1 i.i.d. se vs B3", base["nw_iid_ratio_vs_B3"]["T1"]["iid_se"], iid, 1e-15, "{:.6e}")
                    out[(case, "nw_iid")] = se / iid
                out[(case, t, b)] = (mean, se, tt)
        # deflated Sharpe
        sr = {t: sharpe_m(ex[t]) for t in TRIALS}
        v = float(np.var([sr[t] for t in TRIALS], ddof=0))
        floored = v < DSR_FLOOR
        v_used = DSR_FLOOR if floored else v
        add(f"{cl} variance of monthly Sharpe across trials (floor if < {DSR_FLOOR:.6f})", base["deflation_inputs"]["variance_across_trials"], v_used, 1e-15, "{:.8f}")
        add(f"{cl} DSR floor applied", base["deflation_inputs"]["floor_applied"], bool(floored))
        add(f"{cl} raw variance across trials (informational)", None, v, fmt="{:.3e}")
        for t in TRIALS:
            sk, ku = skew_kurt(ex[t])
            for N in (3, 10):
                s_star, psr, dd_ = dsr(sr[t], n, sk, ku, N, v_used)
                pub = base["deflated_sharpe"][t][f"N{N}"]
                add(f"{cl} {t} SR* monthly N={N}", pub["sr_star_monthly"], s_star, 1e-12, "{:.6f}")
                add(f"{cl} {t} DSR N={N}", pub["dsr"], dd_, 1e-10, "{:.6f}")
                add(f"{cl} {t} PSR", pub["psr"], psr, 1e-10, "{:.6f}")
            if "deflated_sharpe_programme_family" in base:
                fam = base["deflated_sharpe_programme_family"]
                nf = fam["n_family"]
                add(f"{cl} {t} DSR at programme family N={nf}", fam["dsr"][t]["dsr"], dsr(sr[t], n, sk, ku, nf, v_used)[2], 1e-10, "{:.6f}")
            out[(case, t, "dsr3")] = dsr(sr[t], n, sk, ku, 3, v_used)[2]
        if "deflated_sharpe_programme_family" in base:
            add(f"{cl} programme family count", 3, base["deflated_sharpe_programme_family"]["n_family"], 0, "{:d}")
        # mechanism check for T1 from the monthly file (spread <= 0)
        inv = (m["spread_at_signal"] <= 0).to_numpy()
        mech = base["mechanism_check"]["T1"]
        months, eps = episodes(inv)
        add(f"{cl} T1 mechanism: inverted month ends", mech["months"], months, 0, "{:d}")
        add(f"{cl} T1 mechanism: episodes", mech["episodes"], eps, 0, "{:d}")
        add(f"{cl} T1 mechanism: mean episode length", mech["mean_episode_length"], months / eps, 1e-12)
        add(f"{cl} T1 mechanism: mean duration-leg return in inverted months", mech["mean_r_ief"], float(m["B1"][inv].mean()), 1e-15, "{:.6f}")
        add(f"{cl} T1 mechanism: mean cash return in inverted months", mech["mean_r_bil"], float(m["B0"][inv].mean()), 1e-15, "{:.6f}")
        add(f"{cl} T1 mechanism: share with cash > duration leg", mech["fraction_bil_beats_ief"], float((m["B0"][inv] > m["B1"][inv]).mean()), 1e-12)
        # sub-windows and sub-periods by execution month; Study 002's copied key by signal month
        em = m["execution_date"].dt.to_period("M")
        for key, windows in (("sub_windows", SUB_WINDOWS), ("subperiods_by_execution_month", SUBPERIODS)):
            if key not in base:
                continue
            for name, (a, b) in windows.items():
                mask = ((em >= pd.Period(a, "M")) & (em <= pd.Period(b, "M"))).to_numpy()
                sub = m[mask]
                for s in STRATS:
                    pub = base[key][name][s]
                    r = sub[s].to_numpy()
                    e = (sub[s] - sub["B0"]).to_numpy()
                    add(f"{cl} {key} {name} {s} periods", pub["periods"], len(r), 0, "{:d}")
                    add(f"{cl} {key} {name} {s} Sharpe annual", pub["sharpe_annual"] if pub["sharpe_annual"] is not None else float("nan"), sharpe_m(e) * SQ12, 1e-10)
                    add(f"{cl} {key} {name} {s} ann. geometric return", pub["ann_geometric_return"], geo_annual(r), 1e-12, "{:.4%}")
                    add(f"{cl} {key} {name} {s} ann. volatility", pub["ann_volatility"], vol_annual(r), 1e-12, "{:.4%}")
                    add(f"{cl} {key} {name} {s} max drawdown", pub["max_drawdown_monthly"], max_dd(r), 1e-12, "{:.3%}")
                    add(f"{cl} {key} {name} {s} mean excess", pub["mean_excess_monthly"], float(e.mean()), 1e-15, "{:+.6f}")
                    add(f"{cl} {key} {name} {s} hit rate", pub["hit_rate_positive_excess"], float((e > 0).mean()), 1e-12)
                    if s in TRIALS:
                        add(f"{cl} {key} {name} {s} share in IEF", pub["fraction_in_ief"], float((hold[s][mask] == "IEF").mean()), 1e-12)
                out[(case, key, name, "T1")] = sharpe_m((sub["T1"] - sub["B0"]).to_numpy()) * SQ12
                out[(case, key, name, "B1")] = sharpe_m((sub["B1"] - sub["B0"]).to_numpy()) * SQ12
                out[(case, key, name, "B3")] = sharpe_m((sub["B3"] - sub["B0"]).to_numpy()) * SQ12
                out[(case, key, name, "n")] = int(mask.sum())
                out[(case, key, name, "frac")] = float((hold["T1"][mask] == "IEF").mean())
        if "subperiods" in base:
            sm = m.index
            for name, (a, b) in SUBPERIODS.items():
                mask = ((sm >= pd.Period(a, "M")) & (sm <= pd.Period(b, "M")))
                sub = m[mask]
                for s in ("T1", "B1"):
                    pub = base["subperiods"][name][s]
                    add(f"{cl} subperiods (copied key, by SIGNAL month) {name} {s} periods", pub["periods"], len(sub), 0, "{:d}")
                    add(f"{cl} subperiods (copied key, by SIGNAL month) {name} {s} Sharpe", pub["sharpe_annual"], sharpe_m((sub[s] - sub["B0"]).to_numpy()) * SQ12, 1e-10)
                out[(case, "subperiods", name, "T1")] = sharpe_m((sub["T1"] - sub["B0"]).to_numpy()) * SQ12
                out[(case, "subperiods", name, "B1")] = sharpe_m((sub["B1"] - sub["B0"]).to_numpy()) * SQ12
        out[(case, "ex")] = ex
    return out


def check_criteria(summ, h):
    """§9.5 applied by the reviewer from the recomputed numbers (base costs, T1; T2/T3 for fragility)."""
    base = summ["cost_cases"]["base"]
    sr = {s: float(base["descriptive"][s]["sharpe_annual"]) for s in STRATS if s != "B0"}
    crit = {}
    for t in TRIALS:
        c1 = sr[t] >= sr["B1"] + 0.10 and sr[t] >= sr["B3"] + 0.10
        c2 = h[("base", t, "B3")][2] >= 2.0
        c3 = h[("base", t, "dsr3")] >= 0.95
        c4 = np.sign(h[("base", t, "B3")][0]) == np.sign(h[("stress", t, "B3")][0])
        crit[t] = {"C1": bool(c1), "C2": bool(c2), "C3": bool(c3), "C4": bool(c4)}
        pub = summ["criteria"] if t == "T1" else summ["criteria_T2_T3"][t]
        add(f"§9.5 criteria for {t} (reviewer's application)", json.dumps(pub), json.dumps(crit[t]))
    gate_ok = json.loads((RES / "gate" / "gate.json").read_text())["outcome"] == "PASS"
    sigma = float(json.loads((RES / "volcheck" / "volcheck.json").read_text())["sigma_annual"])
    if not gate_ok:
        row = "inconclusive (gate)"
    elif not all(crit["T1"].values()):
        row = "not supported"
    elif not all(all(crit[t].values()) for t in ("T2", "T3")):
        row = "inconclusive (fragile)"
    elif sigma > VOL_BAR:
        row = "consistent with an edge, not detectable at the 2% bar"
    else:
        row = "supported in history; forward record pending"
    add("§9.5 verdict row for T1 (precedence not supported > inconclusive > consistent > supported)", summ["verdict_T1"], row)
    add("sigma carried into the history summary equals volcheck.json", summ["sigma_from_volcheck"], sigma, 0.0, "{:.6f}")
    add("first-paragraph labels (gate label only: sigma <= bar, switches >= 8)",
        json.dumps(summ["labels"]), json.dumps(["gate redesigned after Study 002's halt (cold read, point 7)"] + (["low-power check"] if sigma > VOL_BAR else []) + (["low-powered"] if h["t1_switches"] < 8 else [])))
    add("C1 margin T1 - B1 Sharpe (informational)", None, sr["T1"] - sr["B1"], fmt="{:.4f}")
    add("C1 margin T1 - B3 Sharpe (informational)", None, sr["T1"] - sr["B3"], fmt="{:.4f}")
    return crit


def main() -> int:
    manifest = json.loads((RES / "data_manifest.json").read_text(encoding="utf-8"))
    have_raw = all((RAW / k).exists() for k in manifest)
    if have_raw:
        for k, v in sorted(manifest.items()):
            add(f"SHA-256 of data/raw/{k} equals the manifest", v["sha256"], hashlib.sha256((RAW / k).read_bytes()).hexdigest())
    else:
        rows.append(("Raw vendor files", "n/a", "absent", "not checked (data/raw/ incomplete)"))

    hist = json.loads((RES / "history" / "summary.json").read_text(encoding="utf-8"))
    epi = json.loads((RES / "episode" / "summary.json").read_text(encoding="utf-8"))
    gate = json.loads((RES / "gate" / "gate.json").read_text(encoding="utf-8"))
    vol = json.loads((RES / "volcheck" / "volcheck.json").read_text(encoding="utf-8"))
    f_hist = load("history")
    f_act, f_syn = load("episode/actual"), load("episode/synthetic")

    # ---------------- committed-file recomputation
    h = check_window("HIST", f_hist, hist)
    check_criteria(hist, h)
    a = check_window("EP actual", f_act, epi["actual"], weight_frozen=hist["weight_b3"], with_daily=True)
    s = check_window("EP synthetic", f_syn, epi["synthetic"], weight_frozen=hist["weight_b3"])
    add("EP frozen weight = history weight_b3", hist["weight_b3"], epi["weight_b3_frozen_from_history"], 0.0, "{:.10f}")
    add("EP actual execution dates slipped", 0, len(epi["actual"].get("execution_dates_slipped") or {}), 0, "{:d}")
    add("EP summary carries no criteria or verdict key", True, not any(k in epi for k in ("criteria", "verdict_T1", "criteria_T2_T3")))

    # ---------------- gate from periods.csv
    per = pd.read_csv(RES / "gate" / "periods.csv")
    hT1, g = per["h_T1"].to_numpy(dtype=float), per["g"].to_numpy()
    w_o = hT1.mean()
    e = (hT1 - w_o) * g
    gt = gate["gate_T1"]
    add("gate periods", 192, len(per), 0, "{:d}")
    add("gate w_o from periods.csv", gt["w_o"], w_o, 1e-15, "{:.6f}")
    add("gate e_T1 column = (h - w_o) g", 0.0, float(np.abs(e - per["e_T1"].to_numpy()).max()), 1e-15, "{:.1e}")
    add("gate G1 |mean(e)| x 12 from periods.csv", gt["G1_bias_annual"], abs(e.mean()) * 12, 1e-15, "{:.6e}")
    add("gate G1 pass at full precision", gt["G1_pass"], bool(abs(e.mean()) * 12 <= G1_MAX))
    add("gate level gap mean(g) x 12", gt["mean_g_annual"], g.mean() * 12, 1e-15, "{:.6e}")
    add("gate switches of h", gt["switches"], int(np.abs(np.diff(hT1)).sum()), 0, "{:d}")
    yr = pd.to_datetime(per["execution_date"]).dt.year.to_numpy()
    early = yr < 2008
    add("gate 2003-2007 periods / cash periods", "60/12", f"{int(early.sum())}/{int((hT1[early] == 0).sum())}")
    add("gate T1 held the duration leg in every 2008-2018 period", True, bool((hT1[~early] == 1).all()))
    e_early = (hT1[early] - hT1[early].mean()) * g[early]
    add("gate split 2003-2007 G1", gate["descriptive_no_decision_weight"]["split_2003_2007"]["G1_bias_annual"], abs(e_early.mean()) * 12, 1e-15, "{:.6e}")
    add("gate split 2008-2018 G1", gate["descriptive_no_decision_weight"]["split_2008_2018"]["G1_bias_annual"], 0.0, 1e-18, "{:.1e}")
    add("gate vendor counts IEF tiingo/alpaca", "156/36", f"{int((per['ief_vendor'] == 'tiingo').sum())}/{int((per['ief_vendor'] == 'alpaca').sum())}")
    add("gate vendor counts BIL tiingo/synthetic/alpaca", "103/53/36", "/".join(str(int((per["bil_vendor"] == v).sum())) for v in ("tiingo", "synthetic cash", "alpaca")))
    add("gate first BIL execution", gate["overlap"]["first_bil_execution"], str(per.loc[per["bil_vendor"] != "synthetic cash", "execution_date"].iloc[0]))
    add("gate bounds as registered", "0.0018/0.32", f"{gate['bounds']['G1_max_annual']}/{gate['bounds']['G2_max']}")
    add("gate outcome", "PASS", gate["outcome"])
    add("G1 bound derivation: 0.25 x 2% / (2.0 + 0.842) (informational, %/yr)", None, 0.25 * DESIGN_MDE / 2.842 * 100, fmt="{:.4f}")
    add("G2 bound derivation: sqrt(1 + 0.32^2) (informational)", None, math.sqrt(1 + 0.32 ** 2), fmt="{:.4f}")
    add("volcheck MDE = 2% x sigma / 10.18%", vol["mde_annual"], DESIGN_MDE * vol["sigma_annual"] / VOL_BAR, 1e-15, "{:.6%}")
    add("volcheck consequence: criteria stand", True, vol["sigma_annual"] <= VOL_BAR)
    add("volcheck keys exactly as registered", True, list(vol) == ["sigma_annual", "mde_annual", "periods", "bar", "consequence", "run_at_utc", "code_commit"])

    # ---------------- raw-data rebuild
    if have_raw:
        dgs7, dgs10, dtb3 = fred("DGS7"), fred("DGS10"), fred("DTB3")
        tri = {"IEF": duration_leg(dgs7, dgs10), "BIL": cash_leg(dtb3)}
        add("synthetic duration index starts 1969-07-01 at 1.0", "1969-07-01", str(tri["IEF"].index[0].date()))
        sched = schedule(dgs10, dtb3, "1969-07", "2018-12")
        mb = f_hist["monthly_base"]
        add("HIST schedule rebuilt (reviewer's NYSE calendar): months, signal, execution and period-end dates equal committed", True,
            bool(sched.index.equals(mb.index) and (sched["execution_date"].to_numpy() == mb["execution_date"].to_numpy()).all()
                 and (sched["period_end"].to_numpy() == mb["period_end"].to_numpy()).all()))
        add("HIST signal date < execution date every period", True, bool((sched["signal_date"] < sched["execution_date"]).all()))
        sig = signals(dgs10, dgs7, dtb3, sched)
        add("HIST spread_at_signal rebuilt from FRED (max abs diff)", 0.0, float(np.abs(sig["T1"].to_numpy() - mb["spread_at_signal"].to_numpy()).max()), 1e-15, "{:.1e}")
        rb = rebuild(tri, sched, sig)
        add("HIST B3 weight from rebuilt T1 targets", hist["weight_b3"], rb["w"], 1e-15, "{:.10f}")
        for t in TRIALS:
            add(f"HIST {t} targets rebuilt from FRED equal the committed holdings/returns", True,
                bool((rb["cases"]["base"]["res"][t] - mb[t]).abs().max() < 1e-13))
        for case in COSTS:
            m = f_hist[f"monthly_{case}"]
            for s_ in STRATS:
                add(f"HIST {case} {s_} monthly return rebuilt from raw FRED with the reviewer's engine (max abs diff)", 0.0,
                    float((rb["cases"][case]["res"][s_] - m[s_]).abs().max()), 1e-13, "{:.1e}")
        add("HIST T1 switches from the rebuilt targets", hist["t1_switches"], rb["cases"]["base"]["switches"]["T1"], 0, "{:d}")
        # volatility check from the rebuilt x
        x = (rb["r_ief"] - rb["r_bil"]).to_numpy()
        add("volcheck sigma from the rebuilt synthetic legs (593 periods)", vol["sigma_annual"], float(np.std(x, ddof=1) * SQ12), 1e-13, "{:.6%}")
        add("volcheck periods", vol["periods"], len(x), 0, "{:d}")
        # gate from raw ETF files
        ov = schedule(dgs10, dtb3, "2002-12", "2018-12")
        add("gate overlap schedule: 192 periods, 2003-01-02 to 2019-01-02", "192/2003-01-02/2019-01-02",
            f"{len(ov)}/{ov['execution_date'].iloc[0].date()}/{ov['period_end'].iloc[-1].date()}")
        add("gate periods.csv dates equal the rebuilt overlap schedule", True,
            bool((pd.to_datetime(per["execution_date"]).to_numpy() == ov["execution_date"].to_numpy()).all()
                 and (pd.to_datetime(per["period_end"]).to_numpy() == ov["period_end"].to_numpy()).all()))
        x_syn = period_returns(tri["IEF"], ov).to_numpy() - period_returns(tri["BIL"], ov).to_numpy()
        tiingo = {s_: pd.read_csv(RAW / f"tiingo_{s_}_daily.csv", parse_dates=["date"]).set_index("date")["adjClose"].astype(float).dropna() for s_ in ("IEF", "BIL")}
        alpaca = {s_: pd.read_csv(RAW / f"alpaca_{s_}_1Day_all.csv", parse_dates=["date"]).set_index("date")["close"].astype(float).dropna() for s_ in ("IEF", "BIL")}
        starts, ends = pd.DatetimeIndex(ov["execution_date"]), pd.DatetimeIndex(ov["period_end"])

        def vendor_returns(symbol):
            out, who = np.full(len(ov), np.nan), []
            for i, (a_, b_) in enumerate(zip(starts, ends)):
                pick = None
                for name, px in (("alpaca", alpaca[symbol]), ("tiingo", tiingo[symbol])):
                    if a_ in px.index and b_ in px.index:
                        pick = name
                        out[i] = px.loc[b_] / px.loc[a_] - 1.0
                        break
                who.append(pick or "synthetic cash")
            return out, who

        ief, ief_v = vendor_returns("IEF")
        bil, bil_v = vendor_returns("BIL")
        add("gate IEF vendor per period equals periods.csv", True, ief_v == list(per["ief_vendor"]))
        add("gate BIL vendor per period equals periods.csv", True, bil_v == list(per["bil_vendor"]))
        c_syn = period_returns(tri["BIL"], ov).to_numpy()
        x_etf = ief - np.where(np.isnan(bil), c_syn, bil)
        g_r = x_syn - x_etf
        add("gate g rebuilt from raw FRED, Tiingo and Alpaca files (max abs diff vs periods.csv)", 0.0, float(np.abs(g_r - g).max()), 1e-14, "{:.1e}")
        hT1_r = (sig_ov := signals(dgs10, dgs7, dtb3, ov))["T1"].to_numpy() > 0
        add("gate h_T1 rebuilt from FRED equals periods.csv", True, bool((hT1_r.astype(float) == hT1).all()))
        e_r = (hT1_r - hT1_r.mean()) * g_r
        add("gate G1 from raw files", gt["G1_bias_annual"], abs(e_r.mean()) * 12, 1e-14, "{:.6e}")
        g2 = float(np.std(g_r, ddof=1) / np.std(x_etf, ddof=1))
        add("gate G2 sd(g)/sd(x_ETF) from raw files", gt["G2_noise_ratio"], g2, 1e-12, "{:.6f}")
        add("gate G2 pass at full precision", gt["G2_pass"], bool(g2 <= G2_MAX))
        add("gate corr(g, x_ETF)", gt["corr_g_x_etf"], float(np.corrcoef(g_r, x_etf)[0, 1]), 1e-12, "{:.6f}")
        for name, mask in (("split_2003_2007", early), ("split_2008_2018", ~early)):
            d_ = gate["descriptive_no_decision_weight"][name]
            add(f"gate {name} G2", d_["G2_noise_ratio"], float(np.std(g_r[mask], ddof=1) / np.std(x_etf[mask], ddof=1)), 1e-12, "{:.6f}")
            add(f"gate {name} w_o", d_["w_o"], float(hT1_r[mask].mean()), 1e-15)
            add(f"gate {name} level gap mean(g) x 12", d_["mean_g_annual"], float(g_r[mask].mean() * 12), 1e-14, "{:.6e}")
        for t in ("T2", "T3"):
            ht = sig_ov[t].to_numpy() > 0
            d_ = gate["descriptive_no_decision_weight"][t]
            add(f"gate {t} G1 (own signal, own w)", d_["G1_bias_annual"], abs(((ht - ht.mean()) * g_r).mean()) * 12, 1e-14, "{:.6e}")
            add(f"gate {t} w_o", d_["w_o"], float(ht.mean()), 1e-15)
            add(f"gate {t} switches", d_["switches"], int(np.abs(np.diff(ht.astype(float))).sum()), 0, "{:d}")
        add("gate G1 as a share of the bound (informational)", None, gt["G1_bias_annual"] / G1_MAX, fmt="{:.3f}")
        # episode: actual Alpaca closes and the synthetic series
        es = schedule(dgs10, dtb3, "2018-12", "2026-09")
        bars = alpaca["IEF"].index.intersection(alpaca["BIL"].index)
        pos = bars.searchsorted(es["execution_date"].to_numpy(), side="left")
        resolved = es.copy()
        resolved["execution_date"] = pd.DatetimeIndex(bars[pos])
        resolved["period_end"] = resolved["execution_date"].shift(-1)
        resolved.loc[resolved.index[-1], "period_end"] = bars[bars.searchsorted(es["period_end"].iloc[-1], side="left")]
        add("EP execution dates fall on Alpaca bars (no slip)", True, bool((resolved["execution_date"].to_numpy() == es["execution_date"].to_numpy()).all()))
        ma = f_act["monthly_base"]
        add("EP actual schedule equals committed (93 periods, 2019-01-02 to 2026-10-01)", True,
            bool(resolved.index.equals(ma.index) and (resolved["execution_date"].to_numpy() == ma["execution_date"].to_numpy()).all()
                 and (resolved["period_end"].to_numpy() == ma["period_end"].to_numpy()).all()))
        act_tri = {k: alpaca[k] / alpaca[k].iloc[0] for k in ("IEF", "BIL")}
        sig_e = signals(dgs10, dgs7, dtb3, resolved)
        add("EP spread_at_signal rebuilt (max abs diff)", 0.0, float(np.abs(sig_e["T1"].to_numpy() - ma["spread_at_signal"].to_numpy()).max()), 1e-15, "{:.1e}")
        rb_a = rebuild(act_tri, resolved, sig_e, weight=hist["weight_b3"])
        rb_s = rebuild(tri, es, sig_e, weight=hist["weight_b3"])
        for lab, rbx, ff in (("EP actual", rb_a, f_act), ("EP synthetic", rb_s, f_syn)):
            for case in COSTS:
                for s_ in STRATS:
                    add(f"{lab} {case} {s_} monthly return rebuilt from raw data with the reviewer's engine (max abs diff)", 0.0,
                        float((rbx["cases"][case]["res"][s_] - ff[f"monthly_{case}"][s_]).abs().max()), 1e-13, "{:.1e}")
        mdd = epi["actual"]["cost_cases"]["base"]["max_drawdown_daily"]
        for t in TRIALS:
            add(f"EP actual {t} daily max drawdown (reviewer's daily path, cost at the execution close)", mdd[t],
                daily_strategy_mdd(rb_a["targets"][t], resolved, act_tri, COSTS["base"], include_start=False), 1e-12, "{:.4%}")
        add("EP actual T1 daily max drawdown with the start point included (informational)", None,
            daily_strategy_mdd(rb_a["targets"]["T1"], resolved, act_tri, COSTS["base"], include_start=True), fmt="{:.4%}")
        ief_path = act_tri["IEF"].loc[resolved["execution_date"].iloc[0]:resolved["period_end"].iloc[-1]]
        add("EP actual B1 daily max drawdown", mdd["B1"], float((ief_path / ief_path.cummax() - 1.0).min()), 1e-12, "{:.4%}")
        add("EP terminal T1 target (2026-09 signal) is IEF", "IEF", str(rb_a["targets"]["T1"].iloc[-1]))
        add("EP 2026-08 spread equals the forward code's starting value 0.008805271872744068 (§16)", 0.008805271872744068,
            float(sig_e["T1"].loc[pd.Period("2026-08", "M")]), 1e-15, "{:.12f}")
    else:
        rows.append(("Raw-data rebuild (legs, schedule, signals, engine, gate, volcheck, episode)", "n/a", "skipped", "not checked (data/raw/ incomplete)"))

    # ---------------- README typed numbers (history)
    hb = hist["cost_cases"]["base"]
    desc = hb["descriptive"]
    for s_, v in (("T1", 7.98), ("T2", 7.94), ("T3", 7.99), ("B1", 7.31), ("B3", 7.03), ("B2", 6.15)):
        add_typed(f"README annual return {s_} (%)", v, desc[s_]["ann_geometric_return"], 2, 0.01)
    for s_, v in (("T1", 0.463), ("T2", 0.463), ("T3", 0.468), ("B1", 0.338), ("B3", 0.338), ("B2", 0.338)):
        add_typed(f"README Sharpe {s_}", v, desc[s_]["sharpe_annual"], 3)
    for s_, v in (("T1", -9.8), ("T2", -9.8), ("T3", -9.8), ("B1", -15.2), ("B3", -12.4), ("B2", -4.3)):
        add_typed(f"README deepest monthly drawdown {s_} (%)", v, desc[s_]["max_drawdown_monthly"], 1, 0.01)
    for t, v in (("T1", 0.075), ("T2", 0.072), ("T3", 0.076)):
        add_typed(f"README mean difference to B3 {t} (%/month)", v, h[("base", t, "B3")][0], 3, 0.01)
    for t, v in (("T1", 2.06), ("T2", 1.97), ("T3", 1.91)):
        add_typed(f"README NW t to B3 {t}", v, h[("base", t, "B3")][2], 2)
    for t, v in (("T1", 1.16), ("T2", 1.09), ("T3", 1.09)):
        add_typed(f"README NW t to B1 {t}", v, h[("base", t, "B1")][2], 2)
    for t in TRIALS:
        add_typed(f"README DSR N=3 {t}", 0.999, h[("base", t, "dsr3")], 3)
    for t, v in (("T1", 2.01), ("T2", 1.94), ("T3", 1.86)):
        add_typed(f"README stress t to B3 {t}", v, h[("stress", t, "B3")][2], 2)
    add_typed("README T1 switches", 27, h["t1_switches"], 0)
    add_typed("README T1 switches a year", 0.55, h["t1_switches"] / (593 / 12), 2)
    add_typed("README T1 share in the bond (%)", 87.0, desc["T1"]["fraction_in_ief"], 1, 0.01)
    add_typed("README B3 weight w", 0.870, hist["weight_b3"], 3)
    add_typed("README T1 Sharpe interval low", 0.21, hb["inference"]["T1"]["sharpe_ci"]["ci_low"], 2)
    add_typed("README T1 Sharpe interval high", 0.71, hb["inference"]["T1"]["sharpe_ci"]["ci_high"], 2)
    add_typed("README Ledoit-Wolf p vs B3", 0.097, hb["inference"]["T1"]["vs_B3"]["ledoit_wolf"]["p_value"], 3)
    add_typed("README DSR N=10 T1", 0.997, hb["deflated_sharpe"]["T1"]["N10"]["dsr"], 3)
    add_typed("README NW/iid ratio T1", 0.963, h[("base", "nw_iid")], 3)
    add_typed("README T1 - B3 about 0.9% a year", 0.9, 12 * h[("base", "T1", "B3")][0], 1, 0.01)
    add_typed("README 'cleared t = 2.0 by 0.06'", 0.06, h[("base", "T1", "B3")][2] - 2.0, 2)
    add_typed("README 'missed by 0.03' (T2)", 0.03, 2.0 - h[("base", "T2", "B3")][2], 2)
    add_typed("README 'missed by 0.09' (T3)", 0.09, 2.0 - h[("base", "T3", "B3")][2], 2)
    add_typed("README sigma (%)", 7.75, vol["sigma_annual"], 2, 0.01)
    add_typed("README MDE about 1.5% (%)", 1.5, vol["mde_annual"], 1, 0.01)
    add_typed("README/trials MDE 1.52% (%)", 1.52, vol["mde_annual"], 2, 0.01)
    add_typed("README gate G1 (%/yr)", 0.008, gt["G1_bias_annual"], 3, 0.01)
    add_typed("README gate G2", 0.131, gt["G2_noise_ratio"], 3)
    add_typed("README level gap (%/yr)", 0.002, gt["mean_g_annual"], 3, 0.01)
    add_typed("README corr(g, x_ETF)", 0.223, gt["corr_g_x_etf"], 3)
    dd_ = gate["descriptive_no_decision_weight"]
    add_typed("README 2003-2007 G1 (%)", 0.064, dd_["split_2003_2007"]["G1_bias_annual"], 3, 0.01)
    add_typed("README 2003-2007 G2", 0.115, dd_["split_2003_2007"]["G2_noise_ratio"], 3)
    add_typed("README 2008-2018 G1 (%)", 0.000, dd_["split_2008_2018"]["G1_bias_annual"], 3, 0.01)
    add_typed("README 2008-2018 G2", 0.138, dd_["split_2008_2018"]["G2_noise_ratio"], 3)
    add_typed("trials w_o", 0.938, gt["w_o"], 3)
    add_typed("trials T2 G1 (%)", 0.009, dd_["T2"]["G1_bias_annual"], 3, 0.01)
    add_typed("trials T3 G1 (%)", 0.014, dd_["T3"]["G1_bias_annual"], 3, 0.01)
    sw_ = "sub_windows"
    for name, n_, t1, b1, b3, frac in (("1969-08 to 2002-12 (before any ETF)", 401, 0.444, 0.279, 0.278, 83.8),
                                        ("2003-01 to 2018-12 (the gate's overlap)", 192, 0.508, 0.499, 0.499, 93.8)):
        add_typed(f"README {name} months", n_, h[("base", sw_, name, "n")], 0)
        add_typed(f"README {name} T1 Sharpe", t1, h[("base", sw_, name, "T1")], 3)
        add_typed(f"README {name} B1 Sharpe", b1, h[("base", sw_, name, "B1")], 3)
        add_typed(f"README {name} B3 Sharpe", b3, h[("base", sw_, name, "B3")], 3)
        add_typed(f"README {name} T1 in the bond (%)", frac, h[("base", sw_, name, "frac")], 1, 0.01)
    sp = "subperiods_by_execution_month"
    for name, n_, t1, b1, b3, frac in (("1969-08 to 1981-12 (rising rates)", 149, 0.105, -0.271, -0.271, 63.8),
                                        ("1982-01 to 2008-12 (disinflation)", 324, 0.599, 0.629, 0.629, 92.9),
                                        ("2009-01 to 2018-12 (zero lower bound and QE)", 120, 0.452, 0.452, 0.452, 100.0)):
        add_typed(f"README {name} months", n_, h[("base", sp, name, "n")], 0)
        add_typed(f"README {name} T1 Sharpe", t1, h[("base", sp, name, "T1")], 3)
        add_typed(f"README {name} B1 Sharpe", b1, h[("base", sp, name, "B1")], 3)
        add_typed(f"README {name} B3 Sharpe", b3, h[("base", sp, name, "B3")], 3)
        add_typed(f"README {name} T1 in the bond (%)", frac, h[("base", sp, name, "frac")], 1, 0.01)
    add_typed("README signal-month rising-rate T1 Sharpe", 0.076, h[("base", "subperiods", "1969-08 to 1981-12 (rising rates)", "T1")], 3)
    add_typed("README signal-month rising-rate B1 Sharpe", -0.274, h[("base", "subperiods", "1969-08 to 1981-12 (rising rates)", "B1")], 3)
    mech = hb["mechanism_check"]["T1"]
    add_typed("README mechanism 77 month ends", 77, mech["months"], 0)
    add_typed("README mechanism 14 episodes", 14, mech["episodes"], 0)
    add_typed("README mechanism mean 5.5 months", 5.5, mech["mean_episode_length"], 1)
    add_typed("README mechanism bond 0.38% a month", 0.38, mech["mean_r_ief"], 2, 0.01)
    add_typed("README mechanism bills 0.76% a month", 0.76, mech["mean_r_bil"], 2, 0.01)
    add_typed("README mechanism bills beat the bond 55%", 55, mech["fraction_bil_beats_ief"], 0, 0.01)
    # README typed numbers (episode)
    eb = epi["actual"]["cost_cases"]["base"]
    add_typed("README EP T1 Sharpe", -0.494, eb["descriptive"]["T1"]["sharpe_annual"], 3)
    add_typed("README EP B1 Sharpe", -0.259, eb["descriptive"]["B1"]["sharpe_annual"], 3)
    add_typed("README EP B3 Sharpe", -0.259, eb["descriptive"]["B3"]["sharpe_annual"], 3)
    add_typed("README EP T1 - B3 (%/month)", -0.065, a[("base", "T1", "B3")][0], 3, 0.01)
    add_typed("README EP T1 - B3 NW t", -0.61, a[("base", "T1", "B3")][2], 2)
    add_typed("README EP T1 daily drawdown (%)", -22.6, eb["max_drawdown_daily"]["T1"], 1, 0.01)
    add_typed("README EP IEF daily drawdown (%)", -23.9, eb["max_drawdown_daily"]["B1"], 1, 0.01)
    add_typed("README EP 37 inverted month ends", 37, eb["mechanism_check"]["T1"]["months"], 0)
    add_typed("README EP 5 episodes", 5, eb["mechanism_check"]["T1"]["episodes"], 0)
    add_typed("README EP IEF 0.46% in inverted months", 0.46, eb["mechanism_check"]["T1"]["mean_r_ief"], 2, 0.01)
    add_typed("README EP bills 0.36% in inverted months", 0.36, eb["mechanism_check"]["T1"]["mean_r_bil"], 2, 0.01)
    add_typed("README EP T2 t", 0.20, a[("base", "T2", "B3")][2], 2)
    add_typed("README EP T3 t", 0.97, a[("base", "T3", "B3")][2], 2)
    add_typed("README EP synthetic T1 - B3 (%/month)", -0.074, s[("base", "T1", "B3")][0], 3, 0.01)
    add_typed("README EP synthetic t", -0.69, s[("base", "T1", "B3")][2], 2)
    add_typed("trials EP T1 in the bond (%)", 60.2, eb["descriptive"]["T1"]["fraction_in_ief"], 1, 0.01)

    # ---------------- charts: manifest inputs, title numbers, title text
    cm = json.loads((STUDY / "charts" / "manifest.json").read_text(encoding="utf-8"))
    for rel, hsh in cm["inputs_sha256"].items():
        p = STUDY.parents[1] / rel
        add(f"charts manifest input hash: {Path(rel).name}", hsh, hashlib.sha256(p.read_bytes()).hexdigest())
    mb = f_hist["monthly_base"]
    inv = mb["spread_at_signal"] <= 0
    nums = cm["numbers_in_titles"]
    add("chart: month ends", nums["spread_month_ends"], len(mb), 0, "{:d}")
    add("chart: inverted month ends", nums["spread_inverted_month_ends"], int(inv.sum()), 0, "{:d}")
    add("chart: inverted before 1982 (execution year)", nums["spread_inverted_before_1982"], int((inv & (mb["execution_date"].dt.year < 1982)).sum()), 0, "{:d}")
    add("chart: inverted before 1982 by signal month (same count)", nums["spread_inverted_before_1982"], int((inv & (mb.index < pd.Period("1982-01", "M"))).sum()), 0, "{:d}")
    last_inv = mb.loc[inv, "execution_date"].max()
    add("chart: last inverted execution", nums["spread_last_inverted_execution"], str(last_inv.date()))
    add("chart: bond-only from execution", nums["spread_bond_only_from_execution"], str(mb.loc[mb["execution_date"] > last_inv, "execution_date"].iloc[0].date()))
    growth = (1.0 + mb[["T1", "B1", "B3"]]).cumprod()
    for k in ("T1", "B1", "B3"):
        add(f"chart: growth final {k}", nums["growth_final"][k], float(growth[k].iloc[-1]), 1e-10, "{:.4f}")
        add(f"chart: Sharpe {k}", nums["growth_sharpe_annual"][k], desc[k]["sharpe_annual"], 1e-12, "{:.6f}")
        add(f"chart: max drawdown {k}", nums["drawdown_monthly_max"][k], max_dd(mb[k].to_numpy()), 1e-12, "{:.4%}")
    dd_b1 = growth["B1"] / growth["B1"].cummax() - 1.0
    tr = mb.loc[dd_b1.idxmin()]
    add("chart: B1 trough period end", nums["drawdown_B1_trough"], str(tr["period_end"].date()))
    add("chart: B1 trough holding period (execution month)", nums["drawdown_B1_trough_holding_period"], tr["execution_date"].strftime("%Y-%m"))
    d = mb["T1"] - mb["B3"]
    yr = mb["execution_date"].dt.year
    means = {}
    for lab, lo, hi in (("1969–79", 1969, 1979), ("1980s", 1980, 1989), ("1990s", 1990, 1999), ("2000s", 2000, 2009), ("2010–18", 2010, 2018)):
        mask = (yr >= lo) & (yr <= hi)
        means[lab] = float(d[mask].mean() * 12)
        add(f"chart: decade {lab} mean d x 12", nums["decade_mean_d_annual"][lab], means[lab], 1e-12, "{:+.4%}")
        add(f"chart: decade {lab} periods", nums["decade_periods"][lab], int(mask.sum()), 0, "{:d}")
        add(f"chart: decade {lab} without a bill month", lab in nums["decade_without_a_bill_month"], bool((mb.loc[mask, "T1_holding"] == "IEF").all()))
    total = sum(means[k] * nums["decade_periods"][k] for k in means)
    for k in means:
        add(f"chart: decade {k} share of summed edge", nums["decade_share_of_summed_edge"][k], means[k] * nums["decade_periods"][k] / total, 1e-12)
    titles = {}
    for name in ("history_spread_and_holdings", "history_growth", "history_drawdown", "history_differential_by_decade"):
        svg = (STUDY / "charts" / f"{name}.svg").read_text(encoding="utf-8")
        texts = [re.sub(r"<[^>]+>", "", m_).strip() for m_ in re.findall(r"<text[^>]*>(.*?)</text>", svg, re.S)]
        titles[name] = " ".join(t for t in texts if t and not re.fullmatch(r"[−\-\d.,% ]+|(19|20)\d\d", t) and not t.startswith("Source"))
    exp = {
        "history_spread_and_holdings": f"The curve inverted at {len(mb)} of {len(mb)} month ends".replace(f"at {len(mb)} of", f"at {int(inv.sum())} of") + f", {int((inv & (yr < 1982)).sum())} before 1982; from {mb.loc[mb['execution_date'] > last_inv, 'execution_date'].iloc[0].strftime('%B %Y')} to {mb['execution_date'].iloc[-1].strftime('%B %Y')} the rule held the bond",
        "history_growth": f"Over 1969–2018 the spread switch had the higher Sharpe, {desc['T1']['sharpe_annual']:.2f} against {desc['B1']['sharpe_annual']:.2f} for holding the bond and for the same-exposure mix; the verdict is inconclusive (fragile)",
        "history_drawdown": f"The switch's deepest monthly drawdown was {pct(max_dd(mb['T1'].to_numpy()))}, against {pct(max_dd(mb['B3'].to_numpy()))} for the same-exposure mix and {pct(max_dd(mb['B1'].to_numpy()))} for holding the bond",
        "history_differential_by_decade": f"The switch's edge over the same-exposure mix came from 1969–89, +{pct(means['1969–79'])} and +{pct(means['1980s'])} a year; in the 2000s, the only later decade with bill months, it was {pct(means['2000s'])}",
    }
    for name, want in exp.items():
        got = titles[name]
        add(f"CHART title text of {name}.svg matches the recomputed title", True, want in got, note=f"SVG: '{got[:160]}…'" if want not in got else "")
    add("chart: growth verb rule (Sharpe gap >= 0.05 -> 'had the higher Sharpe')", True, desc["T1"]["sharpe_annual"] - max(desc["B1"]["sharpe_annual"], desc["B3"]["sharpe_annual"]) >= 0.05)
    add("chart: decade title names 1969-89 because both early decades are positive timing decades and 2000s is the only later one with bill months", True,
        means["1969–79"] > 0 and means["1980s"] > 0 and means["2000s"] <= 0 and set(nums["decade_without_a_bill_month"]) == {"1990s", "2010–18"})
    for k, v in (("1969–79", 1.9), ("1980s", 1.7), ("2000s", -0.1)):
        add_typed(f"CHART decade {k} (%/yr)", v, means[k], 1, 0.01, src="CHART")
    add_typed("README decade 1990s/2010-18 note: 1969-79 share of summed edge (CHART_REVIEW 45%)", 45, nums["decade_share_of_summed_edge"]["1969–79"], 0, 0.01, src="CHART")
    add_typed("CHART 1980s share of summed edge (39%)", 39, nums["decade_share_of_summed_edge"]["1980s"], 0, 0.01, src="CHART")

    # ---------------- print
    width = max(len(r[0]) for r in rows)
    for claim, pub, rec, ok in rows:
        print(f"{claim.ljust(width)} | {pub:>22} | {rec:>22} | {ok}")
    n_yes = sum(r[3].startswith("yes") for r in rows)
    n_no = sum(r[3].startswith("NO") for r in rows)
    n_info = len(rows) - n_yes - n_no
    print(f"\n{len(rows)} rows: {n_yes} match, {n_no} mismatch, {n_info} informational / not checked")
    if n_no:
        print("Mismatches:")
        for r in rows:
            if r[3].startswith("NO"):
                print("  ", r)
    return 1 if n_no else 0


if __name__ == "__main__":
    sys.exit(main())
