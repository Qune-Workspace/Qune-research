"""Independent recomputation for REVIEW.md (Study 005, trend exits from
duration conditional on the stock-bond correlation regime).

Written by the reviewer (Tester, a separate agent session that did not write
the code).  It imports nothing from the study's ``src/`` or from the shared
library ``qune_research``: every number below is re-derived with numpy,
pandas and scipy only, from

  * the committed outputs under ``results/insample/``, ``results/episode/``
    and ``results/checks/`` (``monthly_*.csv``, ``metrics_*.csv``,
    ``positive_episodes_*.csv``, ``summary.json``, ``d0/d1/d3.json``,
    ``regime_flags_*.csv``), ``results/data_manifest.json``, and Study 003's
    committed ``results/insample/monthly_base.csv`` and ``results/oos/``;
  * the raw vendor files in ``data/raw/`` (git-ignored; present on disk at
    review time): Tiingo ``adjClose`` for IEF and SPY, FRED DTB3 and
    CPIAUCNS, the broker's ``adjustment='all'`` bars for IEF, BIL and SPY and
    the 2016-2018 broker SPY file under ``data/raw/overlap/``.

With the raw files the reviewer rebuilds the schedule, the trend signal, the
three regime variables, B0-B3, T1-T3 and d_t for both windows with an engine
of their own and compares to the committed monthly files; every published
statistic (edge, Newey-West t, stationary-bootstrap intervals with the
pre-registered seed, metrics, DSR, sub-periods, episodes, MDE, D1, D3) is
recomputed from the committed files.  "Published" values are read from
``summary.json`` and the CSVs at full precision; numbers that exist only in
README.md or PREREGISTRATION.md section 16 are typed in below, marked README,
and compared at the README's rounding.  Nothing is written to disk.

Run from the study folder:  ../../.venv/bin/python review_recompute.py
Exit status is 1 if any row mismatches.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

STUDY = Path(__file__).resolve().parent
RES = STUDY / "results"
RAW = STUDY / "data" / "raw"
S003 = STUDY.parent / "003-bond-tsmom-ief" / "results"
SQ12 = math.sqrt(12.0)
NW_LAGS = 6
BIL_EXPENSE = 0.001356                      # §5.2 (Study 001 §4)
COSTS = {"base": 2e-4, "stress": 4e-4}      # per side (Study 001 §9.2)
SEED, RESAMPLES, BLOCK = 2005, 10_000, 12.0  # §9.3 item 2
MIN_EDGE = 0.01 / 12                        # §9.5
POWER_Z = 1.645 + 0.842                     # §9.6
DSR_FLOOR = (0.05 / SQ12) ** 2              # Study 001 §9.4
WINDOWS = {"T1": 63, "T2": 252}
CPI_THRESHOLD, CPI_LAG = 0.03, 2
STRATS = ("B0", "B1", "B2", "B3", "T1", "T2", "T3")
TRIALS = ("T1", "T2", "T3")
SUBPERIODS = {"2003-08 to 2008-12": ("2003-08", "2008-12"), "2009-01 to 2015-12": ("2009-01", "2015-12"),
              "2016-01 to 2018-12": ("2016-01", "2018-12")}

rows: list[tuple[str, str, str, str]] = []


def add(claim, published, recomputed, tol=0.0, fmt="{:.4f}", note=""):
    """Append one comparison row; match when |published - recomputed| <= tol."""
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


def add_readme(claim, readme_value, recomputed, decimals, scale=1.0, src="README"):
    """A typed value printed with ``decimals`` digits after dividing by ``scale`` (100 for %)."""
    add(f"{claim} [{src}]", readme_value, recomputed / scale, 0.5 * 10 ** (-decimals) + 1e-12, "{:." + str(decimals) + "f}")


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


def hac_ols(y, X, lags=NW_LAGS):
    """OLS with a Bartlett-kernel HAC covariance (``lags`` lags, no small-sample
    factor), hand-coded: returns (beta, se)."""
    y, X = np.asarray(y, dtype=float), np.asarray(X, dtype=float)
    n = len(y)
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    u = y - X @ beta
    g = X * u[:, None]
    s = g.T @ g
    for j in range(1, lags + 1):
        gj = g[j:].T @ g[:-j]
        s += (1.0 - j / (lags + 1.0)) * (gj + gj.T)
    cov = xtx_inv @ s @ xtx_inv
    return beta, np.sqrt(np.diag(cov))


def nw_mean(x):
    b, se = hac_ols(x, np.ones((len(x), 1)))
    return float(b[0]), float(se[0]), float(b[0] / se[0])


def nw_delta(d, pos):
    X = np.column_stack([np.ones(len(d)), pos.astype(float)])
    b, se = hac_ols(d, X)
    return float(b[1]), float(se[1]), float(b[1] / se[1]), float(b[0])


def sb_indices(rng, n, n_resamples=RESAMPLES, block=BLOCK):
    """Stationary-bootstrap indices (Politis-Romano): geometric block lengths
    with mean ``block``, circular wrap; the reviewer's own loop."""
    restart = rng.random(size=(n_resamples, n)) < 1.0 / block
    fresh = rng.integers(0, n, size=(n_resamples, n))
    idx = np.empty((n_resamples, n), dtype=np.int64)
    idx[:, 0] = fresh[:, 0]
    for t in range(1, n):
        idx[:, t] = np.where(restart[:, t], fresh[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def boot_edge(d, pos, rng):
    idx = sb_indices(rng, len(d))
    ds, ps = d[idx], pos[idx]
    npos, nneg = ps.sum(axis=1), (~ps).sum(axis=1)
    keep = (npos > 0) & (nneg > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        mp = np.where(ps, ds, 0.0).sum(axis=1) / np.where(npos > 0, npos, np.nan)
        mn = np.where(~ps, ds, 0.0).sum(axis=1) / np.where(nneg > 0, nneg, np.nan)
    q = [0.025, 0.975]
    out = {"delta": np.quantile((mp - mn)[keep], q), "mean_positive": np.quantile(mp[keep], q),
           "mean_negative": np.quantile(mn[keep], q), "dropped": int((~keep).sum())}
    return out


def boot_sharpe(x, rng):
    idx = sb_indices(rng, len(x))
    s = x[idx]
    sd = s.std(axis=1, ddof=1)
    keep = sd > 0
    sr = s[keep].mean(axis=1) / sd[keep] * SQ12
    return np.quantile(sr, [0.025, 0.975]), int((~keep).sum())


def dsr(sr, n_obs, skew, kurt, n_trials, var_trials):
    g = 0.5772156649015329
    sr_star = math.sqrt(var_trials) * ((1 - g) * norm.ppf(1 - 1 / n_trials) + g * norm.ppf(1 - 1 / (n_trials * math.e)))
    den = math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr ** 2)
    psr = float(norm.cdf(sr * math.sqrt(n_obs - 1) / den))
    return sr_star, psr, float(norm.cdf((sr - sr_star) * math.sqrt(n_obs - 1) / den))


def episodes(flags):
    """Count, share, regime changes, number / mean / longest positive episode."""
    f = np.asarray(flags, dtype=bool)
    changes = int((f[1:] != f[:-1]).sum())
    lengths, run = [], 0
    for v in f:
        if v:
            run += 1
        elif run:
            lengths.append(run)
            run = 0
    if run:
        lengths.append(run)
    return {"months": len(f), "positive_months": int(f.sum()), "positive_share": float(f.mean()),
            "regime_changes": changes, "positive_episodes": len(lengths),
            "mean_positive_episode_months": float(np.mean(lengths)) if lengths else float("nan"),
            "longest_positive_episode_months": int(max(lengths)) if lengths else 0}


def mde(sigma, n_pos, n_neg):
    return POWER_Z * sigma * math.sqrt(1.0 / n_pos + 1.0 / n_neg)


# ----------------------------------------------------------------------------- reviewer's own engine
def tiingo_close(symbol):
    df = pd.read_csv(RAW / f"tiingo_{symbol}_daily.csv", parse_dates=["date"]).set_index("date").sort_index()
    return df["adjClose"].astype(float).dropna()


def alpaca_close(symbol, sub=""):
    df = pd.read_csv(RAW / sub / f"alpaca_{symbol}_1Day_all.csv", parse_dates=["date"]).set_index("date").sort_index()
    return df["close"].astype(float).dropna()


def fred(series):
    raw = pd.read_csv(RAW / f"fred_{series}.csv", dtype=str, keep_default_na=False)
    v = pd.to_numeric(raw.iloc[:, 1].str.strip().replace({"": np.nan, ".": np.nan}), errors="coerce")
    return pd.Series(v.to_numpy(dtype=float), index=pd.to_datetime(raw.iloc[:, 0]))


def cash_index_dtb3(dtb3_pct):
    """§5.2: bey_s = 365 d/(360 - 91 d) at the previous valid observation, r_t = (bey - expense) days/365."""
    v = dtb3_pct.dropna() / 100.0
    d_prev = v.to_numpy()[:-1]
    bey = 365.0 * d_prev / (360.0 - 91.0 * d_prev)
    days = np.diff(v.index.to_numpy()).astype("timedelta64[D]").astype(float)
    r = (bey - BIL_EXPENSE) * days / 365.0
    return pd.Series(np.concatenate([[1.0], np.cumprod(1.0 + r)]), index=v.index)


def month_end_bars(bars):
    s = pd.Series(bars, index=bars)
    return s.groupby(bars.to_period("M")).last()


def schedule(bars, first, last):
    """Signal date = last bar of each month; execution = first bar strictly after it."""
    me = month_end_bars(bars)
    sig = me.loc[pd.Period(first, "M"):pd.Period(last, "M")]
    pos = bars.searchsorted(sig.to_numpy(), side="right")
    exe = pd.Series(pd.DatetimeIndex(bars[pos]), index=sig.index)
    out = pd.DataFrame({"signal_date": sig, "execution_date": exe})
    out["period_end"] = out["execution_date"].shift(-1)
    return out.iloc[:-1], me


def level_at(tri, dates):
    return tri.reindex(pd.DatetimeIndex(dates), method="ffill").to_numpy()


def period_returns(tri, sched):
    return pd.Series(level_at(tri, sched["period_end"]) / level_at(tri, sched["execution_date"]) - 1.0, index=sched.index)


def momentum(tri_ief, tri_cash, me, months):
    out = {}
    for m in months:
        t, t12 = me.loc[m], me.loc[m - 12]
        ief = level_at(tri_ief, [t12, t])
        cash = level_at(tri_cash, [t12, t])
        out[m] = ief[1] / ief[0] - cash[1] / cash[0]
    return pd.Series(out)


def daily_returns(close):
    return (close / close.shift(1) - 1.0).dropna()


def common_returns(c_spy, c_ief):
    r1, r2 = daily_returns(c_spy), daily_returns(c_ief)
    common = r1.index.intersection(r2.index).sort_values()
    return pd.DataFrame({"SPY": r1.loc[common].to_numpy(), "IEF": r2.loc[common].to_numpy()}, index=common)


def trailing_corr(returns, dates, window):
    out = {}
    for k, t in dates.items():
        upto = returns.loc[:t]
        if len(upto) < window:
            out[k] = np.nan
            continue
        tail = upto.iloc[-window:]
        out[k] = float(np.corrcoef(tail["SPY"].to_numpy(), tail["IEF"].to_numpy())[0, 1])
    return pd.Series(out, dtype=float)


def cpi_regime(cpi, months):
    """T3: twelve-month change of CPIAUCNS for month m-2, or the latest defined
    change for an earlier month (§16 amendment); returns (change, month read, filled)."""
    lv = cpi.copy()
    lv.index = lv.index.to_period("M")
    lv = lv.reindex(pd.period_range(lv.index[0], lv.index[-1], freq="M"))
    ch = (lv / lv.shift(12) - 1.0).dropna()
    out = {}
    for m in months:
        lag = m - CPI_LAG
        avail = ch.loc[:lag]
        out[m] = (float(avail.iloc[-1]), avail.index[-1], avail.index[-1] != lag)
    return pd.DataFrame(out, index=["change", "month", "filled"]).T


def run_switching(targets, r_ief, r_bil, cost, initial="BIL"):
    holding, out, sw = initial, [], []
    for m in targets.index:
        tgt = targets.loc[m]
        switched = tgt != holding
        holding = tgt
        gross = r_ief.loc[m] if holding == "IEF" else r_bil.loc[m]
        factor = (1.0 - cost) ** 2 if switched else 1.0
        out.append(factor * (1.0 + gross) - 1.0)
        sw.append(switched)
    return pd.Series(out, index=targets.index), pd.Series(sw, index=targets.index)


def run_static(w, r_ief, r_bil, cost):
    ri, rb = r_ief.to_numpy(), r_bil.to_numpy()
    gross = w * ri + (1 - w) * rb
    drift = np.empty_like(gross)
    drift[0] = w
    drift[1:] = w * (1 + ri[:-1]) / (1 + gross[:-1])
    factor = (1.0 - cost * np.abs(drift - w)) ** 2
    return pd.Series(factor * (1 + gross) - 1, index=r_ief.index)


def rebuild(window, tri_ief, tri_cash, bars, c_spy, c_ief, cpi, first, last, weight_b3=None):
    """Every strategy of one window from raw data; returns dict of frames per cost case plus inputs."""
    sched, me = schedule(bars, first, last)
    months = sched.index
    r_ief, r_bil = period_returns(tri_ief, sched), period_returns(tri_cash, sched)
    mom = momentum(tri_ief, tri_cash, me, months)
    trend = pd.Series(np.where(mom > 0, "IEF", "BIL"), index=months)
    rets = common_returns(c_spy, c_ief)
    rho = {t: trailing_corr(rets, sched["signal_date"], WINDOWS[t]) for t in ("T1", "T2")}
    pos = {t: (rho[t] > 0).where(rho[t].notna()) for t in ("T1", "T2")}
    cp = cpi_regime(cpi, months)
    pos["T3"] = (cp["change"].astype(float) > CPI_THRESHOLD)
    out = {"sched": sched, "mom": mom, "trend": trend, "rho": rho, "pos": pos, "cpi": cp, "r_ief": r_ief, "r_bil": r_bil}
    cases = {}
    for case, c in COSTS.items():
        res = {"B0": r_bil.copy(), "B1": r_ief.copy()}
        res["B2"], sw_b2 = run_switching(trend, r_ief, r_bil, c)
        tg = {}
        sw = {"B2": sw_b2}
        for t in TRIALS:
            p = pos[t].dropna().astype(bool)
            tg[t] = trend.loc[p.index].where(p, "IEF")
            res[t], sw[t] = run_switching(tg[t], r_ief.loc[p.index], r_bil.loc[p.index], c)
        w = weight_b3 if weight_b3 is not None else float((tg["T1"] == "IEF").mean())
        res["B3"] = run_static(w, r_ief, r_bil, c)
        cases[case] = {"res": res, "sw": sw, "targets": tg, "w": w, "d": res["B2"] - res["B1"]}
    out["cases"] = cases
    return out


# ----------------------------------------------------------------------------- committed files
def load(window):
    f = {}
    for case in COSTS:
        m = pd.read_csv(RES / window / f"monthly_{case}.csv", index_col=0)
        m.index = pd.PeriodIndex(m.index, freq="M")
        for c in ("signal_date", "execution_date", "period_end"):
            m[c] = pd.to_datetime(m[c])
        f[f"monthly_{case}"] = m
        f[f"met_{case}"] = pd.read_csv(RES / window / f"metrics_{case}.csv", index_col=0)
    f["summ"] = json.loads((RES / window / "summary.json").read_text(encoding="utf-8"))
    f["epi"] = {t: pd.read_csv(RES / window / f"positive_episodes_{t}.csv") for t in TRIALS}
    return f


def check_window(window, label, f, raw):
    summ = f["summ"]
    mb = f["monthly_base"]
    n = len(mb)
    add(f"{label} holding periods", summ["holding_periods"], n, 0, "{:d}")
    add(f"{label} first execution date", summ["first_execution_date"], str(mb["execution_date"].iloc[0].date()))
    add(f"{label} last period end", summ["last_period_end"], str(mb["period_end"].iloc[-1].date()))
    add(f"{label} period_end equals the next row's execution_date", True,
        bool((mb["period_end"].iloc[:-1].to_numpy() == mb["execution_date"].iloc[1:].to_numpy()).all()))
    add(f"{label} signal date < execution date every period", True, bool((mb["signal_date"] < mb["execution_date"]).all()))
    add(f"{label} execution dates slipped (summary)", 0, len(summ.get("execution_dates_slipped", {})), 0, "{:d}")
    add(f"{label} d = B2 - B1 in the monthly file (max abs diff)", 0.0, float((mb["d"] - (mb["B2"] - mb["B1"])).abs().max()), 1e-15, "{:.1e}")
    add(f"{label} B2 holding = IEF iff mom_at_signal > 0", True,
        bool(((mb["mom_at_signal"] > 0) == (mb["B2_holding"] == "IEF")).all()))
    for t in TRIALS:
        hold = mb[f"{t}_holding"].dropna()
        p = mb[f"positive_{t}"].dropna().astype(bool)
        expect = mb.loc[hold.index, "B2_holding"].where(p.loc[hold.index], "IEF")
        add(f"{label} {t} holding = B2's target in positive months, IEF otherwise", True, bool((hold == expect).all()))
        add(f"{label} {t} periods", summ["trial_periods"][t], len(hold), 0, "{:d}")
        add(f"{label} {t} first period", summ["trial_first_period"][t], str(hold.index[0]))
    for t in ("T1", "T2"):
        p = mb[f"positive_{t}"].dropna().astype(bool)
        add(f"{label} positive_{t} = rho_{t} > 0", True, bool(((mb[f"rho_{t}"] > 0).loc[p.index] == p).all()))
    add(f"{label} positive_T3 = cpi_12m_change_T3 > 3%", True,
        bool(((mb["cpi_12m_change_T3"] > CPI_THRESHOLD) == mb["positive_T3"].astype(bool)).all()))
    # regime descriptives from the monthly flags
    for t in TRIALS:
        e = episodes(mb[f"positive_{t}"].dropna().astype(bool))
        pub = summ["regime_descriptives"][t]
        for k in e:
            add(f"{label} {t} regime descriptive {k}", pub[k], e[k], 1e-12, "{:.4f}")
    # D3 regime flags file equals the run's flags
    flags = pd.read_csv(RES / "checks" / f"regime_flags_{window}.csv", index_col=0)
    flags.index = pd.PeriodIndex(flags.index, freq="M")
    same = True
    for t in TRIALS:
        a, b = flags[f"positive_{t}"].dropna().astype(bool), mb[f"positive_{t}"].dropna().astype(bool)
        same = same and a.index.equals(b.index) and (a == b).all()
    add(f"{label} regime flags in results/checks equal the run's flags (T1, T2, T3)", True, bool(same))
    add(f"{label} rho_T1 in checks equals rho_T1 in the monthly file (max abs diff)", 0.0,
        float((flags["rho_T1"] - mb["rho_T1"]).abs().max()), 1e-15, "{:.1e}")

    # descriptive metrics and inference per cost case
    srs = {}
    for case in COSTS:
        m, met = f[f"monthly_{case}"], f[f"met_{case}"]
        base = summ["cost_cases"][case]
        cl = f"{label} {case}"
        b0 = m["B0"]
        for s in STRATS:
            r = m[s].dropna()
            ex = (r - b0.loc[r.index]).to_numpy()
            r = r.to_numpy()
            dsc = base["descriptive"][s]
            add(f"{cl} {s} periods", met.at[s, "periods"], len(r), 0, "{:d}")
            add(f"{cl} {s} ann. geometric return", met.at[s, "ann_geometric_return"], geo_annual(r), 1e-12, "{:.4%}")
            add(f"{cl} {s} ann. volatility", met.at[s, "ann_volatility"], vol_annual(r), 1e-12, "{:.4%}")
            add(f"{cl} {s} Sharpe annual (excess over B0)", met.at[s, "sharpe_annual"], sharpe_m(ex) * SQ12, 1e-10, "{:.4f}")
            add(f"{cl} {s} max drawdown (monthly)", met.at[s, "max_drawdown_monthly"], max_dd(r), 1e-12, "{:.2%}")
            add(f"{cl} {s} mean excess monthly", met.at[s, "mean_excess_monthly"], float(ex.mean()), 1e-15, "{:+.6f}")
            add(f"{cl} {s} hit rate (excess > 0)", met.at[s, "hit_rate_positive_excess"], float((ex > 0).mean()), 1e-12)
            if s != "B0":
                sk, ku = skew_kurt(ex)
                add(f"{cl} {s} skewness of excess", met.at[s, "skewness_excess"], sk, 1e-10, "{:.3f}")
                add(f"{cl} {s} kurtosis of excess (non-excess)", met.at[s, "kurtosis_excess"], ku, 1e-10, "{:.3f}")
            add(f"{cl} {s} summary.json descriptive equals metrics CSV (Sharpe)", dsc["sharpe_annual"], met.at[s, "sharpe_annual"], 1e-12, "{:.6f}")
            if s in ("B2",) + TRIALS:
                hold = m[f"{s}_holding" if s != "B2" else "B2_holding"].dropna()
                add(f"{cl} {s} switches (from the holding column, start in BIL)", met.at[s, "switches"],
                    int((hold != hold.shift(1).fillna("BIL")).sum()), 0, "{:d}")
                add(f"{cl} {s} share of months in IEF", met.at[s, "fraction_in_ief"], float((hold == "IEF").mean()), 1e-12)
                add(f"{cl} {s} switches per year", met.at[s, "switches_per_year"], float(met.at[s, "switches"] / (len(hold) / 12)), 1e-12)
            srs[(case, s)] = {"ex": ex, "sr_m": sharpe_m(ex)}
        add(f"{cl} B3 fraction_in_ief is the frozen weight", met.at["B3", "fraction_in_ief"],
            summ.get("weight_b3", summ.get("weight_b3_frozen_from_insample")), 1e-15)
        if window == "insample":
            add(f"{cl} B3 weight = T1's in-sample IEF share", summ["weight_b3"], float((m["T1_holding"] == "IEF").mean()), 1e-15)
        # B3 reproduces from B1 and B0 (drift-rebalanced static mix with the case's cost)
        b3 = run_static(float(met.at["B3", "fraction_in_ief"]), m["B1"], m["B0"], COSTS[case])
        add(f"{cl} B3 rebuilt from B1 and B0 with the drift-rebalancing cost (max abs diff)", 0.0,
            float((b3 - m["B3"]).abs().max()), 1e-15, "{:.1e}")
        # the conditional rule's return rebuilt from B1 (IEF), B0 (cash) and the flags with the switching cost
        for t in TRIALS:
            p = m[f"positive_{t}"].dropna().astype(bool)
            tg = m.loc[p.index, "B2_holding"].where(p, "IEF")
            r_t, _ = run_switching(tg, m["B1"].loc[p.index], m["B0"].loc[p.index], COSTS[case])
            add(f"{cl} {t} monthly return rebuilt from B1, B0, B2's target and the regime flag (max abs diff)", 0.0,
                float((r_t - m[t].loc[p.index]).abs().max()), 1e-15, "{:.1e}")
        r_b2, _ = run_switching(m["B2_holding"], m["B1"], m["B0"], COSTS[case])
        add(f"{cl} B2 monthly return rebuilt from B1, B0 and its holding (max abs diff)", 0.0,
            float((r_b2 - m["B2"]).abs().max()), 1e-15, "{:.1e}")
        # edge statistics; the bootstrap follows the run's draw order: edges T1, T2, T3 then Sharpe CIs T1, T2, T3
        rng = np.random.default_rng(SEED)
        d_all = m["d"]
        for t in TRIALS:
            p = m[f"positive_{t}"].dropna().astype(bool)
            d = d_all.loc[p.index].to_numpy()
            pv = p.to_numpy()
            pub = base["edge"][t]
            add(f"{cl} {t} n / n_pos / n_neg", f"{pub['n']}/{pub['n_pos']}/{pub['n_neg']}", f"{len(d)}/{int(pv.sum())}/{int((~pv).sum())}")
            mp, mn = float(d[pv].mean()), float(d[~pv].mean())
            add(f"{cl} {t} mean(d | positive)", pub["mean_positive"], mp, 1e-15, "{:+.6f}")
            add(f"{cl} {t} mean(d | negative)", pub["mean_negative"], mn, 1e-15, "{:+.6f}")
            add(f"{cl} {t} delta", pub["delta"], mp - mn, 1e-15, "{:+.6f}")
            dl, se, tt, a = nw_delta(d, pv)
            add(f"{cl} {t} Newey-West lags", 6, pub["newey_west"]["lags"], 0, "{:d}")
            add(f"{cl} {t} Newey-West delta (regression slope)", pub["newey_west"]["delta"], dl, 1e-12, "{:+.6f}")
            add(f"{cl} {t} Newey-West se (Bartlett, 6 lags, no small-sample factor, hand-coded)", pub["newey_west"]["se"], se, 1e-12, "{:.6f}")
            add(f"{cl} {t} Newey-West t", pub["newey_west"]["t"], tt, 1e-8, "{:.4f}")
            add(f"{cl} {t} regression intercept = mean(d | negative)", pub["newey_west"]["intercept_mean_negative"], a, 1e-12, "{:+.6f}")
            bt = boot_edge(d, pv, rng)
            pb = pub["bootstrap"]
            for key in ("delta", "mean_positive", "mean_negative"):
                add(f"{cl} {t} bootstrap 95% interval for {key}, low (seed 2005, block 12, 10,000, reviewer's generator)",
                    pb[key]["ci_low"], bt[key][0], 1e-12, "{:+.6f}")
                add(f"{cl} {t} bootstrap 95% interval for {key}, high", pb[key]["ci_high"], bt[key][1], 1e-12, "{:+.6f}")
            add(f"{cl} {t} bootstrap resamples dropped (one regime only)", pb["resamples_dropped_one_regime"], bt["dropped"], 0, "{:d}")
            add(f"{cl} {t} bootstrap settings (resamples/block/level)", f"{pb['resamples']}/{pb['expected_block']}/{pb['level']}", f"{RESAMPLES}/{int(BLOCK)}/0.95")
            # companions
            comp = base["edge_companions"][t]
            bills = (m["B2_holding"] == "BIL")
            ief_ex = m["B1"] - m["B0"]
            for lab, mask in (("positive", p), ("negative", ~p)):
                idx = p.index[mask.to_numpy()]
                add(f"{cl} {t} {lab} months", comp[lab]["months"], len(idx), 0, "{:d}")
                add(f"{cl} {t} {lab} share B2 in bills", comp[lab]["share_b2_in_bills"], float(bills.loc[idx].mean()), 1e-12)
                add(f"{cl} {t} {lab} mean IEF excess over cash", comp[lab]["mean_ief_excess"], float(ief_ex.loc[idx].mean()), 1e-15, "{:+.6f}")
            # versus benchmarks
            rt = m[t].dropna()
            for b in ("B2", "B3"):
                mean, se2, t2 = nw_mean((rt - m[b].loc[rt.index]).to_numpy())
                pv2 = base["versus_benchmarks"][t][f"vs_{b}"]
                add(f"{cl} mean({t}-{b})", pv2["mean"], mean, 1e-15, "{:+.6f}")
                add(f"{cl} Newey-West t of {t}-{b}", pv2["t"], t2, 1e-8, "{:.4f}")
            sv = base["versus_benchmarks"][t]["switches_T_vs_B2"]
            hold_b2 = m["B2_holding"].loc[rt.index]
            prev = m["B2_holding"].shift(1).fillna("BIL").loc[rt.index]
            add(f"{cl} {t} switches vs B2's in the same months", f"{sv['trial']}/{sv['B2_same_months']}",
                f"{int(met.at[t, 'switches'])}/{int((hold_b2 != prev).sum())}")
            # §9.5 row as written, with refuted tested first
            row = ("refuted in-sample" if bt["delta"][1] < MIN_EDGE else
                   "sign consistent, forward record decides" if (mp - mn > 0 and mp > 0 and mn < 0) else
                   "inconclusive, forward record decides") if int(pv.sum()) >= 12 else "not informative"
            if case == "base":
                add(f"{cl} {t} §9.5 row (reviewer's application; episode rows carry no weight)", base["rows_9_5"][t], row)
        for t in TRIALS:
            x = srs[(case, t)]["ex"]
            ci, dropped = boot_sharpe(x, rng)
            pc = base["sharpe_ci"][t]
            add(f"{cl} {t} Sharpe bootstrap interval low", pc["ci_low"], ci[0], 1e-12, "{:+.4f}")
            add(f"{cl} {t} Sharpe bootstrap interval high", pc["ci_high"], ci[1], 1e-12, "{:+.4f}")
            add(f"{cl} {t} Sharpe bootstrap degenerate resamples", pc["resamples_dropped_degenerate"], dropped, 0, "{:d}")
        # deflated Sharpe
        v = float(np.var([srs[(case, t)]["sr_m"] for t in TRIALS], ddof=0))
        floored = v < DSR_FLOOR
        v_used = DSR_FLOOR if floored else v
        add(f"{cl} variance of monthly Sharpe across T1-T3 (floor {DSR_FLOOR:.6f} if below)", base["deflation_inputs"]["variance_across_trials"], v_used, 1e-15, "{:.8f}")
        add(f"{cl} DSR floor applied", base["deflation_inputs"]["floor_applied"], bool(floored))
        for t in TRIALS:
            sk, ku = skew_kurt(srs[(case, t)]["ex"])
            n_t = len(srs[(case, t)]["ex"])
            for N in (3, 10):
                sr_star, psr, dd = dsr(srs[(case, t)]["sr_m"], n_t, sk, ku, N, v_used)
                pub = base["deflated_sharpe"][t][f"N{N}"]
                add(f"{cl} {t} SR* monthly N={N}", pub["sr_star_monthly"], sr_star, 1e-12, "{:.6f}")
                add(f"{cl} {t} DSR N={N}", pub["dsr"], dd, 1e-10)
            add(f"{cl} {t} PSR", base["deflated_sharpe"][t]["N3"]["psr"], psr, 1e-10)
        # sub-periods by execution month
        em = m["execution_date"].dt.to_period("M")
        for t in TRIALS:
            p = m[f"positive_{t}"].dropna().astype(bool)
            for name, (a, b) in SUBPERIODS.items():
                mask = (em >= pd.Period(a, "M")) & (em <= pd.Period(b, "M"))
                idx = p.index.intersection(em.index[mask])
                pub = base["subperiods_d_by_regime"][t][name]
                ds, ps = d_all.loc[idx], p.loc[idx]
                mp = float(ds[ps].mean()) if ps.sum() else float("nan")
                mn = float(ds[~ps].mean()) if (~ps).sum() else float("nan")
                add(f"{cl} {t} sub-period {name} months/n_pos/n_neg", f"{pub['months']}/{pub['n_pos']}/{pub['n_neg']}",
                    f"{len(idx)}/{int(ps.sum())}/{int((~ps).sum())}")
                add(f"{cl} {t} sub-period {name} delta", pub["delta"], mp - mn, 1e-15, "{:+.6f}")
        # stress - base edge shift
        if case == "stress":
            shift = max(abs(summ["cost_cases"]["stress"]["edge"][t]["delta"] - summ["cost_cases"]["base"]["edge"][t]["delta"]) for t in TRIALS)
            add(f"{label} largest |delta stress - delta base| over T1-T3", None, shift, fmt="{:.6f}")
    # positive-episode tables from the monthly file
    for t in TRIALS:
        p = f["monthly_base"][f"positive_{t}"].dropna().astype(bool)
        bills = (f["monthly_base"]["B2_holding"] == "BIL")
        ief_ex = f["monthly_base"]["B1"] - f["monthly_base"]["B0"]
        recs, start = [], None
        idx = list(p.index)
        for i, mth in enumerate(idx):
            if p.iloc[i] and start is None:
                start = i
            if start is not None and (not p.iloc[i] or i == len(idx) - 1):
                end = i if p.iloc[i] else i - 1
                span = idx[start:end + 1]
                recs.append((str(span[0]), str(span[-1]), len(span), float(bills.loc[span].mean()),
                             float(ief_ex.loc[span].mean()), float(ief_ex.loc[span].sum())))
                start = None
        pub = f["epi"][t]
        add(f"{label} {t} positive-episode table rows", len(pub), len(recs), 0, "{:d}")
        ok = len(pub) == len(recs) and all(
            pub.loc[i, "first_month"] == r[0] and pub.loc[i, "last_month"] == r[1] and pub.loc[i, "months"] == r[2]
            and abs(pub.loc[i, "share_b2_in_bills"] - r[3]) < 1e-12 and abs(pub.loc[i, "mean_ief_excess"] - r[4]) < 1e-15
            and abs(pub.loc[i, "sum_ief_excess"] - r[5]) < 1e-15 for i, r in enumerate(recs))
        add(f"{label} {t} positive-episode table (dates, lengths, B2 bill share, IEF excess) recomputed", True, bool(ok))
    return srs


def raw_rebuild(window, label, f, rb):
    """Compare the reviewer's raw-data rebuild to the committed monthly files."""
    mb = f["monthly_base"]
    s = rb["sched"]
    add(f"{label} schedule rebuilt from raw bars equals committed (signal, execution, period-end dates)", True,
        bool(s.index.equals(mb.index) and (s["signal_date"].to_numpy() == mb["signal_date"].to_numpy()).all()
             and (s["execution_date"].to_numpy() == mb["execution_date"].to_numpy()).all()
             and (s["period_end"].to_numpy() == mb["period_end"].to_numpy()).all()))
    add(f"{label} mom_at_signal rebuilt from raw bars (max abs diff)", 0.0, float((rb["mom"] - mb["mom_at_signal"]).abs().max()), 1e-12, "{:.1e}")
    for t in ("T1", "T2"):
        a, b = rb["rho"][t], mb[f"rho_{t}"]
        add(f"{label} rho_{t} rebuilt from raw daily closes, {WINDOWS[t]} common return days (max abs diff; NaN pattern equal)",
            0.0, float(np.nanmax((a - b).abs().to_numpy())) if (a.isna() == b.isna()).all() else float("nan"), 1e-12, "{:.1e}")
    cp = rb["cpi"]
    add(f"{label} T3 CPI change rebuilt from the FRED file with the m-2 lag and the filled rule (max abs diff)", 0.0,
        float((cp["change"].astype(float) - mb["cpi_12m_change_T3"]).abs().max()), 1e-15, "{:.1e}")
    flags = pd.read_csv(RES / "checks" / f"regime_flags_{window}.csv", index_col=0)
    flags.index = pd.PeriodIndex(flags.index, freq="M")
    add(f"{label} T3 month read equals checks file", True, bool((cp["month"].astype(str) == flags["cpi_month_T3"]).all()))
    add(f"{label} T3 filled months", int(flags["cpi_month_filled_T3"].sum()), int(cp["filled"].sum()), 0, "{:d}")
    for t in TRIALS:
        a, b = rb["pos"][t].dropna().astype(bool), mb[f"positive_{t}"].dropna().astype(bool)
        add(f"{label} positive_{t} flags rebuilt from raw data equal committed (all {len(b)} months)", True,
            bool(a.index.equals(b.index) and (a == b).all()))
    for case in COSTS:
        m = f[f"monthly_{case}"]
        for s_ in STRATS:
            r = rb["cases"][case]["res"][s_]
            add(f"{label} {case} {s_} monthly return rebuilt from raw data with the reviewer's engine (max abs diff)", 0.0,
                float((r - m[s_].loc[r.index]).abs().max()), 1e-13, "{:.1e}")
    if window == "insample":
        add(f"{label} B3 weight from the rebuilt T1 targets", f["summ"]["weight_b3"], rb["cases"]["base"]["w"], 1e-15)


def main() -> int:
    manifest = json.loads((RES / "data_manifest.json").read_text(encoding="utf-8"))
    have_raw = all((RAW / k).exists() for k in manifest)
    if have_raw:
        for k, v in sorted(manifest.items()):
            add(f"SHA-256 of data/raw/{k} equals the manifest", v["sha256"], hashlib.sha256((RAW / k).read_bytes()).hexdigest())
        for k in ("alpaca_SPY_1Day_all.csv", "fred_CPIAUCNS.csv"):
            n_rows = len(pd.read_csv(RAW / k))
            add(f"manifest row count of {k}", manifest[k]["rows"], n_rows, 0, "{:d}")
        add("manifest: Alpaca SPY first / last bar", "2018-09-04/2026-09-30", f"{manifest['alpaca_SPY_1Day_all.csv']['first_bar']}/{manifest['alpaca_SPY_1Day_all.csv']['last_bar']}")
        add_readme("Alpaca SPY bars", 2029, manifest["alpaca_SPY_1Day_all.csv"]["rows"], 0)
        add_readme("CPIAUCNS monthly rows", 1365, manifest["fred_CPIAUCNS.csv"]["rows"], 0)
    else:
        rows.append(("Raw vendor files", "n/a", "absent", "not checked (data/raw/ incomplete)"))

    f_is, f_ep = load("insample"), load("episode")
    d3 = json.loads((RES / "checks" / "d3.json").read_text(encoding="utf-8"))
    d1 = json.loads((RES / "checks" / "d1.json").read_text(encoding="utf-8"))
    d0 = json.loads((RES / "checks" / "d0.json").read_text(encoding="utf-8"))

    # ---------------- Study 003 cross-checks (committed files only)
    s3_is = pd.read_csv(S003 / "insample" / "monthly_base.csv", index_col=0)
    s3_is.index = pd.PeriodIndex(s3_is.index, freq="M")
    for ours, theirs in (("B0", "B0"), ("B1", "B1"), ("B2", "T1")):
        add(f"IS {ours} equals Study 003's committed in-sample {theirs} (max abs diff)", 0.0,
            float((f_is["monthly_base"][ours] - s3_is[theirs]).abs().max()), 1e-10, "{:.1e}")
    add("IS B2 holding equals Study 003's T1_holding", True, bool((f_is["monthly_base"]["B2_holding"] == s3_is["T1_holding"]).all()))
    add("IS mom_at_signal equals Study 003's (max abs diff)", 0.0, float((f_is["monthly_base"]["mom_at_signal"] - s3_is["mom_at_signal"]).abs().max()), 1e-10, "{:.1e}")
    s3_oos_m = pd.read_csv(S003 / "oos" / "monthly_base.csv", index_col=0)
    s3_oos_m.index = pd.PeriodIndex(s3_oos_m.index, freq="M")
    for ours, theirs in (("B0", "B0"), ("B1", "B1"), ("B2", "T1")):
        add(f"EP {ours} equals Study 003's committed out-of-sample {theirs} monthly (max abs diff)", 0.0,
            float((f_ep["monthly_base"][ours] - s3_oos_m[theirs]).abs().max()), 0.0, "{:.1e}")
    s3_oos = pd.read_csv(S003 / "oos" / "metrics_base.csv", index_col=0)
    num = [c for c in s3_oos.columns if c not in ("first_period", "last_period")]
    add("EP metrics_base numeric columns compared with Study 003 (README says fourteen; periods included)", 14, len(num), 0, "{:d}")
    for ours, theirs in (("B0", "B0"), ("B1", "B1"), ("B2", "T1")):
        a, b = f_ep["met_base"].loc[ours, num].astype(float), s3_oos.loc[theirs, num].astype(float)
        diff = float(np.nanmax(np.abs(a.to_numpy() - b.to_numpy()))) if not (a.isna() == b.isna()).all() is False else float("nan")
        add(f"EP {ours} metrics equal Study 003's out-of-sample {theirs} row exactly (max abs diff over numeric columns)", 0.0, diff, 0.0, "{:.1e}")
    # sigma_d and MDE (D3)
    d_003 = (s3_is["T1"] - s3_is["B1"]).to_numpy()
    sigma = float(np.std(d_003, ddof=1))
    add("D3 sigma_d from Study 003's committed in-sample file (T1 - B1, ddof 1)", d3["sigma_d"]["sigma_d_per_month"], sigma, 1e-15, "{:.6%}")
    add("D3 share of months with d != 0", d3["sigma_d"]["share_months_d_nonzero"], float((d_003 != 0).mean()), 1e-15)
    add_readme("sigma_d per month (%)", 0.692, sigma, 3, 0.01)
    for t in TRIALS:
        e = d3["insample"][t]
        n_pos, n_neg = e["positive_months"], e["months"] - e["positive_months"]
        add(f"D3 {t} MDE per month at the actual counts", e["mde"]["per_month"], mde(sigma, n_pos, n_neg), 1e-15, "{:.6%}")
        add(f"D3 {t} MDE per year", e["mde"]["per_year"], 12 * mde(sigma, n_pos, n_neg), 1e-15, "{:.4%}")
        add(f"D3 {t} in-sample rows apply (n_pos >= 12)", e["insample_rows_apply"], bool(n_pos >= 12))
    add_readme("MDE T1 per month (%)", 0.364, 100 * mde(sigma, 26, 159), 3)
    add_readme("MDE T1 per year (%)", 4.37, 1200 * mde(sigma, 26, 159), 2)
    add_readme("MDE T2 per year (%)", 6.16, 1200 * mde(sigma, 12, 173), 2, src="§16")
    add_readme("MDE T3 per year (%)", 3.59, 1200 * mde(sigma, 43, 142), 2, src="§16")
    # §9.6 registration table at sigma 1.0% and unrounded shares
    for share, per_m, per_y in ((0.10, 0.61, 7.3), (0.20, 0.46, 5.5), (0.30, 0.40, 4.8)):
        v = mde(0.01, share * 185, (1 - share) * 185)
        add_readme(f"§9.6 table MDE per month at share {share:.0%} (sigma 1.0%)", per_m, 100 * v, 2, src="§9.6")
        add_readme(f"§9.6 table MDE a year at share {share:.0%}", per_y, 1200 * v, 1, src="§9.6")
    add_readme("§16 note: 10% row at the integer count 19 reads 7.2%", 7.2, 1200 * mde(0.01, 19, 166), 1, src="§16")
    # D3 descriptives equal the summaries' regime descriptives
    for t in TRIALS:
        for k in ("months", "positive_months", "regime_changes", "positive_episodes", "longest_positive_episode_months"):
            add(f"D3 in-sample {t} {k} equals summary", d3["insample"][t][k], f_is["summ"]["regime_descriptives"][t][k], 0, "{:d}")
            add(f"D3 episode {t} {k} equals summary", d3["episode_no_decision_weight"][t][k], f_ep["summ"]["regime_descriptives"][t][k], 0, "{:d}")

    # ---------------- committed-file checks per window
    srs_is = check_window("insample", "IS", f_is, None)
    srs_ep = check_window("episode", "EP", f_ep, None)

    # ---------------- raw rebuild
    if have_raw:
        c_ief_t, c_spy_t = tiingo_close("IEF"), tiingo_close("SPY")
        dtb3, cpi = fred("DTB3"), fred("CPIAUCNS")
        tri_ief = c_ief_t / c_ief_t.iloc[0]
        cash = cash_index_dtb3(dtb3)
        rb_is = rebuild("insample", tri_ief, cash, c_ief_t.index, c_spy_t, c_ief_t, cpi, "2003-07", "2018-12")
        raw_rebuild("insample", "IS", f_is, rb_is)
        a_ief, a_bil, a_spy = alpaca_close("IEF"), alpaca_close("BIL"), alpaca_close("SPY")
        bars = a_ief.index.intersection(a_bil.index)
        rb_ep = rebuild("episode", a_ief / a_ief.iloc[0], a_bil / a_bil.iloc[0], bars, a_spy, a_ief, cpi, "2018-12", "2026-09",
                        weight_b3=f_is["summ"]["weight_b3"])
        raw_rebuild("episode", "EP", f_ep, rb_ep)
        # terminal regime and trend at 2026-09-30 (summary / README)
        rets_ep = common_returns(a_spy, a_ief)
        last = pd.Series([pd.Timestamp("2026-09-30")], index=[pd.Period("2026-09", "M")])
        for t in ("T1", "T2"):
            rho_last = float(trailing_corr(rets_ep, last, WINDOWS[t]).iloc[0])
            add(f"EP terminal rho {t} at 2026-09-30", f_ep["summ"]["terminal_regime"][t]["rho"], rho_last, 1e-12, "{:.4f}")
        add_readme("rho_63 at the last signal date", 0.55, float(trailing_corr(rets_ep, last, 63).iloc[0]), 2)
        me_ep = month_end_bars(bars)
        mom_last = momentum(a_ief / a_ief.iloc[0], a_bil / a_bil.iloc[0], me_ep, [pd.Period("2026-09", "M")]).iloc[0]
        add("EP terminal trend value", f_ep["summ"]["terminal_trend_value"], mom_last, 1e-12, "{:+.6f}")
        add_readme("trend signal at the last signal date (%)", -7.4, 100 * mom_last, 1)
        cp_last = cpi_regime(cpi, [pd.Period("2026-09", "M")])
        add("EP terminal T3 month read / change", f"{f_ep['summ']['terminal_regime']['T3']['cpi_month']}/{f_ep['summ']['terminal_regime']['T3']['cpi_12m_change']:.6f}",
            f"{cp_last['month'].iloc[0]}/{float(cp_last['change'].iloc[0]):.6f}")
        # T3 filled reading at 2025-12
        cp_dec = cpi_regime(cpi, [pd.Period("2025-12", "M")])
        add("T3 2025-12 signal month reads 2025-09 (filled)", "2025-09/True", f"{cp_dec['month'].iloc[0]}/{bool(cp_dec['filled'].iloc[0])}")
        add_readme("T3 filled reading, 2025-09 twelve-month change (%)", 3.01, 100 * float(cp_dec["change"].iloc[0]), 2, src="§16")
        add("CPIAUCNS has no value for 2025-10", True, bool(np.isnan(cpi.loc["2025-10-01"])))
        # D0 bar counts and D1 sign agreement from raw files
        add("D0 Tiingo IEF bars 2003-04-01..2018-12-31", d0["files"]["tiingo_IEF"]["bars_present"], int(((c_ief_t.index >= "2003-04-01") & (c_ief_t.index <= "2018-12-31")).sum()), 0, "{:d}")
        add("D0 Tiingo SPY bars 2003-04-01..2018-12-31", d0["files"]["tiingo_SPY"]["bars_present"], int(((c_spy_t.index >= "2003-04-01") & (c_spy_t.index <= "2018-12-31")).sum()), 0, "{:d}")
        for sym, ser in (("SPY", a_spy), ("IEF", a_ief), ("BIL", a_bil)):
            add(f"D0 Alpaca {sym} bars 2018-09-04..2026-09-30", d0["files"][f"alpaca_{sym}"]["bars_present"], int(((ser.index >= "2018-09-04") & (ser.index <= "2026-09-30")).sum()), 0, "{:d}")
        add("D0 Tiingo IEF first bar", d0["files"]["tiingo_IEF"]["first_bar"], str(c_ief_t.index[0].date()))
        ov = alpaca_close("SPY", "overlap")
        days = c_ief_t.index[(c_ief_t.index >= "2016-01-04") & (c_ief_t.index <= "2018-12-31")]
        dates = pd.Series(days, index=days)
        rv = trailing_corr(common_returns(c_spy_t, c_ief_t), dates, 63)
        rbk = trailing_corr(common_returns(ov, a_ief), dates, 63)
        both = pd.concat([rv.rename("v"), rbk.rename("b")], axis=1).dropna()
        add("D1 trading days in the overlap window (bar count)", 754, len(days), 0, "{:d}")
        add("D1 days compared", d1["days_compared"], len(both), 0, "{:d}")
        add("D1 days undefined broker", d1["days_undefined_broker"], int(rbk.isna().sum()), 0, "{:d}")
        add("D1 sign agreement share", d1["sign_agreement_share"], float((np.sign(both["v"]) == np.sign(both["b"])).mean()), 1e-15)
        diff = (both["v"] - both["b"]).abs()
        add("D1 mean abs difference", d1["mean_abs_difference"], float(diff.mean()), 1e-12, "{:.6f}")
        add("D1 max abs difference / date", f"{d1['max_abs_difference']:.6f}/{d1['max_abs_difference_date']}", f"{float(diff.max()):.6f}/{diff.idxmax().date()}")
        add("D1 share of days vendor correlation positive", d1["share_days_vendor_positive"], float((both["v"] > 0).mean()), 1e-15)

    # ---------------- README figures, in-sample
    mb, sj = f_is["monthly_base"], f_is["summ"]["cost_cases"]["base"]
    e = sj["edge"]
    for t, vals in {"T1": (26, 159, -0.325, -0.029, -0.296, -2.31, -0.519, 0.027),
                    "T2": (12, 173, -0.625, -0.032, -0.593, -3.11, -2.110, -0.108),
                    "T3": (43, 142, 0.007, -0.094, 0.101, 0.81, -0.125, 0.302)}.items():
        add_readme(f"IS {t} n_pos", vals[0], e[t]["n_pos"], 0)
        add_readme(f"IS {t} n_neg", vals[1], e[t]["n_neg"], 0)
        add_readme(f"IS {t} mean(d|pos) %", vals[2], 100 * e[t]["mean_positive"], 3)
        add_readme(f"IS {t} mean(d|neg) %", vals[3], 100 * e[t]["mean_negative"], 3)
        add_readme(f"IS {t} delta %", vals[4], 100 * e[t]["delta"], 3)
        add_readme(f"IS {t} NW t", vals[5], e[t]["newey_west"]["t"], 2)
        add_readme(f"IS {t} CI low %", vals[6], 100 * e[t]["bootstrap"]["delta"]["ci_low"], 3)
        add_readme(f"IS {t} CI high %", vals[7], 100 * e[t]["bootstrap"]["delta"]["ci_high"], 3)
    add_readme("IS T1 delta % (first paragraph, 2 dp)", -0.30, 100 * e["T1"]["delta"], 2)
    add_readme("IS T1 mean(d|pos) % (first paragraph)", -0.32, 100 * e["T1"]["mean_positive"], 2)
    add_readme("IS T1 mean(d|neg) % (first paragraph)", -0.03, 100 * e["T1"]["mean_negative"], 2)
    add_readme("IS T1 CI [-0.52, +0.03] % (first paragraph) low", -0.52, 100 * e["T1"]["bootstrap"]["delta"]["ci_low"], 2)
    add_readme("IS T1 CI high (first paragraph)", 0.03, 100 * e["T1"]["bootstrap"]["delta"]["ci_high"], 2)
    add("IS T1 CI upper bound < 0.083%/month (refuted row)", True, bool(e["T1"]["bootstrap"]["delta"]["ci_high"] < MIN_EDGE))
    add_readme("IS stress moves delta by at most (%)", 0.007, 100 * max(abs(f_is["summ"]["cost_cases"]["stress"]["edge"][t]["delta"] - e[t]["delta"]) for t in TRIALS), 3)
    add("IS stress changes no §9.5 row", True, bool(all(
        (f_is["summ"]["cost_cases"]["stress"]["edge"][t]["bootstrap"]["delta"]["ci_high"] < MIN_EDGE) == (sj["rows_9_5"][t] == "refuted in-sample") for t in ("T1", "T2"))))
    add_readme("IS T2 resamples dropped", 480, e["T2"]["bootstrap"]["resamples_dropped_one_regime"], 0)
    add_readme("IS T1 half-mean pos CI low %", -0.51, 100 * e["T1"]["bootstrap"]["mean_positive"]["ci_low"], 2)
    add_readme("IS T1 half-mean pos CI high %", -0.04, 100 * e["T1"]["bootstrap"]["mean_positive"]["ci_high"], 2)
    add_readme("IS T1 half-mean neg CI low %", -0.12, 100 * e["T1"]["bootstrap"]["mean_negative"]["ci_low"], 2)
    add_readme("IS T1 half-mean neg CI high %", 0.07, 100 * e["T1"]["bootstrap"]["mean_negative"]["ci_high"], 2)
    comp = sj["edge_companions"]["T1"]
    add_readme("IS B2 in bills in positive months (%)", 62, 100 * comp["positive"]["share_b2_in_bills"], 0)
    add_readme("IS B2 in bills in negative months (%)", 26, 100 * comp["negative"]["share_b2_in_bills"], 0)
    add_readme("IS IEF mean excess in positive months (%/month)", 0.22, 100 * comp["positive"]["mean_ief_excess"], 2)
    ep1 = f_is["epi"]["T1"]
    add_readme("IS T1 positive episodes", 9, len(ep1), 0)
    add_readme("IS episodes with IEF excess positive", 6, int((ep1["sum_ief_excess"] > 0).sum()), 0)
    longest = ep1.loc[ep1["months"].idxmax()]
    add("IS longest episode 2006-04..2006-10, 7 months, B2 in bills throughout", "2006-04/2006-10/7/1.0",
        f"{longest['first_month']}/{longest['last_month']}/{int(longest['months'])}/{longest['share_b2_in_bills']}")
    add_readme("IS longest episode IEF excess (%)", 4.5, 100 * longest["sum_ief_excess"], 1)
    falling = ep1[ep1["sum_ief_excess"] < 0]
    add("IS falling episodes: 2005-07..08, 2015-05, 2016-09..10", "2005-07,2015-05,2016-09", ",".join(falling["first_month"]))
    add_readme("IS falling episodes months together", 5, int(falling["months"].sum()), 0)
    add("IS falling episodes all with B2 holding IEF (bill share 0)", True, bool((falling["share_b2_in_bills"] == 0).all()))
    pos_t1 = mb["positive_T1"].astype(bool)
    yrs = pd.Series([m.year for m in mb.index], index=mb.index)
    add_readme("IS positive T1 months in 2004-2006", 16, int((pos_t1 & yrs.between(2004, 2006)).sum()), 0)
    sp = sj["subperiods_d_by_regime"]["T1"]
    for name, (n_pos, dl) in {"2003-08 to 2008-12": (19, -0.48), "2009-01 to 2015-12": (5, -0.11), "2016-01 to 2018-12": (2, 0.13)}.items():
        add_readme(f"IS sub-period {name} n_pos", n_pos, sp[name]["n_pos"], 0)
        add_readme(f"IS sub-period {name} delta %", dl, 100 * sp[name]["delta"], 2)
    ep2 = f_is["epi"]["T2"]
    add("IS T2: 12 positive months, 10 in one episode 2006-05..2007-02", "12/10/2006-05/2007-02",
        f"{int(ep2['months'].sum())}/{int(ep2['months'].max())}/{ep2.loc[ep2['months'].idxmax(), 'first_month']}/{ep2.loc[ep2['months'].idxmax(), 'last_month']}")
    met = f_is["met_base"]
    table = {"T1": (3.93, 6.17, 0.471, -8.3, 9, 91.4), "T2": (3.99, 6.19, 0.479, -8.1, 9, 94.6), "T3": (4.53, 6.19, 0.565, -8.1, 5, 91.9),
             "B0": (1.14, 0.47, None, -0.4, 0, 0.0), "B1": (4.51, 6.27, 0.555, -8.1, 0, 100.0), "B2": (3.66, 5.82, 0.452, -8.6, 18, 69.2),
             "B3": (4.23, 5.73, 0.555, -7.4, 0, 91.4)}
    for s, (ret, vol, sh, dd, sw, share) in table.items():
        add_readme(f"IS table {s} ann. return %", ret, 100 * met.at[s, "ann_geometric_return"], 2)
        add_readme(f"IS table {s} ann. vol %", vol, 100 * met.at[s, "ann_volatility"], 2)
        if sh is not None:
            add_readme(f"IS table {s} Sharpe", sh, met.at[s, "sharpe_annual"], 3)
        add_readme(f"IS table {s} max DD %", dd, 100 * met.at[s, "max_drawdown_monthly"], 1)
        add_readme(f"IS table {s} switches", sw, met.at[s, "switches"], 0)
        add_readme(f"IS table {s} share in IEF %", share, 100 * met.at[s, "fraction_in_ief"], 1)
    add_readme("IS B3 weight w", 0.914, f_is["summ"]["weight_b3"], 3)
    vb = sj["versus_benchmarks"]["T1"]
    add_readme("IS T1-B2 mean %", 0.024, 100 * vb["vs_B2"]["mean"], 3)
    add_readme("IS T1-B2 NW t", 0.51, vb["vs_B2"]["t"], 2)
    add_readme("IS T1-B3 mean %", -0.022, 100 * vb["vs_B3"]["mean"], 3)
    add_readme("IS T1-B3 NW t", -0.79, vb["vs_B3"]["t"], 2)
    add_readme("IS T1 Sharpe CI low", 0.00, sj["sharpe_ci"]["T1"]["ci_low"], 2)
    add_readme("IS T1 Sharpe CI high", 0.89, sj["sharpe_ci"]["T1"]["ci_high"], 2)
    add_readme("IS T1 DSR N=3", 0.959, sj["deflated_sharpe"]["T1"]["N3"]["dsr"], 3)
    add_readme("IS T1 DSR N=10", 0.945, sj["deflated_sharpe"]["T1"]["N10"]["dsr"], 3)
    add_readme("IS T1 Sharpe 0.47 (text)", 0.47, met.at["T1", "sharpe_annual"], 2)
    rd = f_is["summ"]["regime_descriptives"]
    add("IS D3 text: T1 9 episodes, mean 2.9, longest 7; T2 12 in 3; T3 43 in 6, longest 14; 18 changes",
        "9/2.9/7/12/3/43/6/14/18", f"{rd['T1']['positive_episodes']}/{rd['T1']['mean_positive_episode_months']:.1f}/{rd['T1']['longest_positive_episode_months']}/"
        f"{rd['T2']['positive_months']}/{rd['T2']['positive_episodes']}/{rd['T3']['positive_months']}/{rd['T3']['positive_episodes']}/{rd['T3']['longest_positive_episode_months']}/{rd['T1']['regime_changes']}")
    add_readme("IS positive share T1 (%)", 14.1, 100 * rd["T1"]["positive_share"], 1)
    add_readme("D1 sign agreement", 1.0000, d1["sign_agreement_share"], 4)
    add_readme("D1 days", 691, d1["days_compared"], 0)
    add_readme("D1 mean abs difference", 0.0060, d1["mean_abs_difference"], 4)
    add_readme("D1 max abs difference", 0.0190, d1["max_abs_difference"], 4)

    # ---------------- README figures, episode
    me_, se_ = f_ep["monthly_base"], f_ep["summ"]["cost_cases"]["base"]
    e = se_["edge"]
    for t, vals in {"T1": (38, 55, 0.072, 0.304, -0.232, -0.72, -0.878, 0.439),
                    "T2": (38, 46, 0.016, 0.405, -0.389, -1.05, -1.300, 0.408),
                    "T3": (44, 49, 0.429, 0.012, 0.417, 1.35, -0.207, 0.969)}.items():
        add_readme(f"EP {t} n_pos", vals[0], e[t]["n_pos"], 0)
        add_readme(f"EP {t} n_neg", vals[1], e[t]["n_neg"], 0)
        add_readme(f"EP {t} mean(d|pos) %", vals[2], 100 * e[t]["mean_positive"], 3)
        add_readme(f"EP {t} mean(d|neg) %", vals[3], 100 * e[t]["mean_negative"], 3)
        add_readme(f"EP {t} delta %", vals[4], 100 * e[t]["delta"], 3)
        add_readme(f"EP {t} NW t", vals[5], e[t]["newey_west"]["t"], 2)
        add_readme(f"EP {t} CI low %", vals[6], 100 * e[t]["bootstrap"]["delta"]["ci_low"], 3)
        add_readme(f"EP {t} CI high %", vals[7], 100 * e[t]["bootstrap"]["delta"]["ci_high"], 3)
    add_readme("EP T1 delta % (first paragraph, 2 dp)", -0.23, 100 * e["T1"]["delta"], 2)
    add_readme("EP stress moves delta by at most (%)", 0.005, 100 * max(abs(f_ep["summ"]["cost_cases"]["stress"]["edge"][t]["delta"] - e[t]["delta"]) for t in TRIALS), 3)
    add("EP stress changes no sign of delta", True, bool(all(np.sign(f_ep["summ"]["cost_cases"]["stress"]["edge"][t]["delta"]) == np.sign(e[t]["delta"]) for t in TRIALS)))
    add_readme("EP T3 resamples dropped", 1, e["T3"]["bootstrap"]["resamples_dropped_one_regime"], 0)
    add_readme("EP T1, T2 resamples dropped", 0, e["T1"]["bootstrap"]["resamples_dropped_one_regime"] + e["T2"]["bootstrap"]["resamples_dropped_one_regime"], 0)
    pos = me_["positive_T1"].astype(bool)
    bills = me_["B2_holding"] == "BIL"
    ief_ex = me_["B1"] - me_["B0"]
    d = me_["d"]
    add_readme("EP positive months", 38, int(pos.sum()), 0)
    add_readme("EP positive share (%)", 41, 100 * pos.mean(), 0)
    add_readme("EP positive months with B2 in bills", 36, int((pos & bills).sum()), 0)
    add_readme("EP IEF excess over the 38 positive months (%/month)", -0.03, 100 * ief_ex[pos].mean(), 2)
    add_readme("EP IEF excess over the 36 positive bill months (%/month)", -0.08, 100 * ief_ex[pos & bills].mean(), 2)
    add_readme("EP d summed over the positive months (points)", 2.8, 100 * d[pos].sum(), 1)
    add("EP d summed over the 36 positive bill months (points; reviewer's variant)", None, 100 * d[pos & bills].sum(), fmt="{:+.2f}")
    neg_bills = (~pos) & bills
    add_readme("EP negative-regime months with B2 in bills", 19, int(neg_bills.sum()), 0)
    add_readme("EP d summed over those 19 months (points)", 16.9, 100 * d[neg_bills].sum(), 1)
    jan_may = [pd.Period(f"2022-{k:02d}", "M") for k in range(1, 6)]
    exe_jan_may = [pd.Period("2021-12", "M")] + jan_may[:-1]
    add_readme("EP d summed over the five holding periods executed January to May 2022 (signal months 2021-12..2022-04, points)", 9.7, 100 * d.loc[exe_jan_may].sum(), 1)
    add("EP d summed over signal months 2022-01..05 (points; the other naming convention)", None, 100 * d.loc[jan_may].sum(), fmt="{:+.1f}")
    add("EP those five periods are negative-regime bill months", True, bool(neg_bills.loc[exe_jan_may].all()))
    add_readme("EP d in the February and March 2022 signal months (points)", 9.9, 100 * d.loc[[pd.Period("2022-02", "M"), pd.Period("2022-03", "M")]].sum(), 1)
    add("EP d in the periods executed in February and March 2022 (signal 2022-01..02; points)", None, 100 * d.loc[jan_may[:2]].sum(), fmt="{:+.1f}")
    first_pos_2022 = pos.loc[pd.Period("2022-01", "M"):].idxmax()
    add("EP correlation turned positive at the 2022-06 signal month (2022-06-30)", "2022-06/2022-06-30",
        f"{first_pos_2022}/{me_.loc[first_pos_2022, 'signal_date'].date()}")
    add("EP B2 in bills from the 2021-02 signal through 2022-12", True, bool(bills.loc[pd.Period("2021-02", "M"):pd.Period("2022-12", "M")].all()))
    add("EP B2 held IEF at the 2021-01 signal", True, bool(not bills.loc[pd.Period("2021-01", "M")]))
    cal22 = [pd.Period(f"2022-{k:02d}", "M") for k in range(1, 13)]
    exe22 = [pd.Period("2021-12", "M")] + cal22[:-1]
    for s, val in (("B1", -13.7), ("B2", 1.4), ("T1", -7.6)):
        add_readme(f"EP calendar 2022, the twelve periods executed in 2022 (signal months 2021-12..2022-11) {s} cumulative %", val,
                   100 * (np.prod(1 + me_.loc[exe22, s]) - 1), 1)
    add("EP calendar 2022 by signal month (2022-01..12) B1/B2/T1 % (the other naming convention)", None,
        "/".join(f"{100 * (np.prod(1 + me_.loc[cal22, s]) - 1):+.1f}" for s in ("B1", "B2", "T1")))
    t1_ief_b2_bills = (me_["T1_holding"] == "IEF") & bills
    add_readme("EP months T1 held IEF while B2 held bills", 19, int(t1_ief_b2_bills.sum()), 0)
    listed = ([pd.Period("2018-12", "M")] + list(pd.period_range("2021-07", "2022-05", freq="M")) + list(pd.period_range("2023-03", "2023-06", freq="M")))
    actual = list(me_.index[t1_ief_b2_bills])
    others = [m for m in actual if m not in listed]
    add("EP those months are 2018-12, 2021-07..2022-05, 2023-03..2023-06 and three 2025 signal months", True,
        bool(all(m in actual for m in listed) and len(others) == 3 and all(m.year == 2025 for m in others)))
    add("EP the three 2025 months (informational)", None, ", ".join(str(m) for m in others))
    add_readme("EP T1 switches", 14, f_ep["met_base"].at["T1", "switches"], 0)
    add_readme("EP B2 switches", 10, f_ep["met_base"].at["B2", "switches"], 0)
    cum = {s: 100 * (np.prod(1 + me_[s].dropna()) - 1) for s in STRATS}
    for s, val in (("B2", 27.7), ("T3", 26.5), ("B0", 22.5), ("T1", 7.3), ("B3", 5.2), ("B1", 3.6), ("T2", -4.4)):
        add_readme(f"EP cumulative {s} over its months (%)", val, cum[s], 1)
    add_readme("EP T3 ends behind B2 by (points; README 'about a point', commit message 1.25)", 1.25, cum["B2"] - cum["T3"], 2)
    vb = se_["versus_benchmarks"]["T1"]
    add_readme("EP T1-B2 mean %", -0.18, 100 * vb["vs_B2"]["mean"], 2)
    add_readme("EP T1-B2 NW t", -1.69, vb["vs_B2"]["t"], 2)
    add_readme("EP T1-B3 mean %", 0.01, 100 * vb["vs_B3"]["mean"], 2)
    add_readme("EP T1-B3 NW t", 0.11, vb["vs_B3"]["t"], 2)
    pos3 = me_["positive_T3"].astype(bool)
    run3 = list(pd.period_range("2021-06", "2023-07", freq="M"))
    add("EP T3 positive for the 26 months 2021-06..2023-07 and not in 2021-05 or 2023-08", True,
        bool(pos3.loc[run3].all() and len(run3) == 26 and not pos3.loc[pd.Period("2021-05", "M")] and not pos3.loc[pd.Period("2023-08", "M")]))
    add("EP B2 in bills throughout those 26 months", True, bool(bills.loc[run3].all()))
    add_readme("EP IEF excess in those 26 months (%/month)", -0.76, 100 * ief_ex.loc[run3].mean(), 2)
    add_readme("EP IEF excess in those 26 months, total (points)", -19.7, 100 * ief_ex.loc[run3].sum(), 1)
    met = f_ep["met_base"]
    table = {"T1": (0.91, 4.96, -0.325, -17.8, 14, 61.3), "T2": (-0.64, 5.36, -0.602, -22.2, 12, 60.7), "T3": (3.08, 4.33, 0.115, -7.1, 8, 55.9),
             "B0": (2.66, 0.59, None, -0.2, 0, 0.0), "B1": (0.45, 7.39, -0.259, -22.2, 0, 100.0), "B2": (3.21, 3.89, 0.157, -5.5, 10, 40.9),
             "B3": (0.66, 6.76, -0.259, -20.1, 0, 91.4)}
    for s, (ret, vol, sh, dd, sw, share) in table.items():
        add_readme(f"EP table {s} ann. return %", ret, 100 * met.at[s, "ann_geometric_return"], 2)
        add_readme(f"EP table {s} ann. vol %", vol, 100 * met.at[s, "ann_volatility"], 2)
        if sh is not None:
            add_readme(f"EP table {s} Sharpe", sh, met.at[s, "sharpe_annual"], 3)
        add_readme(f"EP table {s} max DD %", dd, 100 * met.at[s, "max_drawdown_monthly"], 1)
        add_readme(f"EP table {s} switches", sw, met.at[s, "switches"], 0)
        add_readme(f"EP table {s} share in IEF %", share, 100 * met.at[s, "fraction_in_ief"], 1)
    add_readme("EP T1 Sharpe CI low", -1.23, se_["sharpe_ci"]["T1"]["ci_low"], 2)
    add_readme("EP T1 Sharpe CI high", 0.63, se_["sharpe_ci"]["T1"]["ci_high"], 2)
    ep1 = f_ep["epi"]["T1"]
    longest = ep1.loc[ep1["months"].idxmax()]
    add("EP longest T1 episode 2023-07..2024-07, 13 months, B2 in bills throughout", "2023-07/2024-07/13/1.0",
        f"{longest['first_month']}/{longest['last_month']}/{int(longest['months'])}/{longest['share_b2_in_bills']}")
    add_readme("EP longest episode IEF excess total (points)", 0.9, 100 * longest["sum_ief_excess"], 1)
    add("EP all three regimes positive at the last signal date", True, bool(all(f_ep["summ"]["terminal_regime"][t]["positive"] for t in TRIALS)))
    add("EP terminal trend target BIL", "BIL", f_ep["summ"]["terminal_trend_target"])
    rd = f_ep["summ"]["regime_descriptives"]
    add("EP D3 text: T1 38/93, 13 changes, 7 episodes, longest 13; T2 38 of 84; T3 44 of 93, longest 26",
        "38/93/13/7/13/38/84/44/93/26", f"{rd['T1']['positive_months']}/{rd['T1']['months']}/{rd['T1']['regime_changes']}/{rd['T1']['positive_episodes']}/"
        f"{rd['T1']['longest_positive_episode_months']}/{rd['T2']['positive_months']}/{rd['T2']['months']}/{rd['T3']['positive_months']}/{rd['T3']['months']}/{rd['T3']['longest_positive_episode_months']}")
    add("EP summary carries no decision weight and the no-row note", "False/no row applies",
        f"{f_ep['summ']['decision_weight']}/{'no row applies' if f_ep['summ']['cost_cases']['base']['rows_9_5_note'].startswith('no row applies') else 'other'}")
    add("EP summary rows_9_5 values present despite the no-row note (informational)", None,
        json.dumps(f_ep["summ"]["cost_cases"]["base"]["rows_9_5"]))
    add("IS summary row_9_5_T1", "refuted in-sample", f_is["summ"]["row_9_5_T1"])
    add("IS and EP provenance seed", "2005/2005", f"{f_is['summ']['provenance']['seed']}/{f_ep['summ']['provenance']['seed']}")
    add("EP B3 weight frozen from the in-sample summary", f_is["summ"]["weight_b3"], f_ep["summ"]["weight_b3_frozen_from_insample"], 0.0, "{:.10f}")

    # ---------------- print
    width = max(len(r[0]) for r in rows)
    print(f"{'claim':<{width}}  {'published':>22}  {'recomputed':>22}  match")
    for c, p, r, ok in rows:
        print(f"{c:<{width}}  {p:>22}  {r:>22}  {ok}")
    n_yes = sum(1 for r in rows if r[3].startswith("yes"))
    n_no = sum(1 for r in rows if r[3].startswith("NO"))
    n_info = sum(1 for r in rows if r[3].startswith("informational"))
    n_nc = sum(1 for r in rows if r[3].startswith("not checked"))
    print(f"\n{len(rows)} rows: {n_yes} match, {n_no} mismatch, {n_info} informational, {n_nc} not checked")
    if n_no:
        print("\nMISMATCHES:")
        for c, p, r, ok in rows:
            if ok.startswith("NO"):
                print(f"  {c}: published {p}, recomputed {r}")
    return 1 if n_no else 0


if __name__ == "__main__":
    sys.exit(main())
