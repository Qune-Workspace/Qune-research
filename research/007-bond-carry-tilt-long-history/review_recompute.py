"""Separate-session recomputation for REVIEW.md (Study 007, bond carry tilt by
level on the 1974-2018 history).

Written by the reviewer (Tester, a separate agent session that did not write
the code, the pre-registration or the note).  It imports nothing from the
study's ``src/`` or from ``qune_research``: every number is re-derived with
numpy, pandas and scipy only, from

  * the raw files in ``data/raw/`` (git-ignored; present on disk at review
    time): FRED DGS7, DGS10, DTB3; Tiingo ``adjClose`` and the broker's
    ``adjustment='all'`` closes for IEF and BIL;
  * the committed outputs under ``results/`` and ``charts/manifest.json``, the
    five SVG titles, and the typed numbers of README.md and trials.md.

What is rebuilt from raw data: the signal dates (last date of each month on
which DGS10, DGS7 and DTB3 all exist), the carry of §6.1 at each of them, the
expanding average-rank weights of §6.2 for m = 60 / 36 / 120 from 1969-07, the
synthetic 8.5-year leg and bill leg (Study 002 §5.2, Study 001 §5.2; the
formulas follow the Study 006 reviewer's script, itself checked to 1e-13), the
12-month trend signal of §6.3, the leg returns B1 and B0 on the committed
execution dates, the gate gap g from the ETF closes, and the episode's actual
ETF returns and trend.  The execution dates themselves are taken from the
committed files and cross-checked against Study 006's committed history (the
NYSE calendar was verified in Study 006's review).

Statistics (twelve metrics, Newey-West t with Bartlett 6 lags, stationary
bootstrap Sharpe interval, Ledoit-Wolf p, DSR, §9.5 rows) are the reviewer's
own code.  The random draws reproduce the committed order: per cost case a
fresh ``numpy.random.default_rng(20261021)``; for T1, T1a, T1b, T2, T3 in turn,
the Sharpe interval, Ledoit-Wolf vs B1, Ledoit-Wolf vs B3.

Run from the study folder:  ../../.venv/bin/python review_recompute.py
Prints one row per check; exit status 1 if any row mismatches.  Nothing is
written to disk.
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

STUDY = Path(__file__).resolve().parent
RES = STUDY / "results"
RAW = STUDY / "data" / "raw"
S006 = STUDY.parent / "006-term-spread-switch-long-history"
SQ12 = math.sqrt(12.0)
LAGS = 6
IEF_EXP, BIL_EXP = 0.0015, 0.001356
COSTS = {"base": 2e-4, "stress": 4e-4}
SEED, NRES, BLOCK = 20261021, 10_000, 12
FLOOR = (0.05 / SQ12) ** 2
TRIALS = ("T1", "T1a", "T1b", "T2", "T3")
MINHIST = {"T1": 60, "T1a": 36, "T1b": 120}
SUBW = {"1974-07 to 2002-12 (before any ETF)": ("1974-07", "2002-12"),
        "2003-01 to 2018-12 (the gate's overlap)": ("2003-01", "2018-12")}
ERAS = {"1974-07 to 1981-12": ("1974-07", "1981-12"), "1982-01 to 2008-12": ("1982-01", "2008-12"),
        "2009-01 to 2018-12": ("2009-01", "2018-12")}

rows: list[tuple[str, str, str, str]] = []


def add(claim, pub, rec, tol=1e-10, fmt="{:.6g}", note=""):
    sfx = f" ({note})" if note else ""
    if pub is None:
        rows.append((claim, "n/a", fmt.format(rec) if isinstance(rec, (int, float, np.floating)) else str(rec),
                     "info" + sfx))
        return
    if isinstance(pub, (str, bool, np.bool_)) or isinstance(rec, (str, bool, np.bool_)):
        ok = str(pub) == str(rec)
        rows.append((claim, str(pub), str(rec), ("yes" if ok else "NO") + sfx))
        return
    p, r = float(pub), float(rec)
    if math.isnan(p) and math.isnan(r):
        rows.append((claim, "nan", "nan", "yes" + sfx))
        return
    ok = abs(p - r) <= tol
    rows.append((claim, fmt.format(p), fmt.format(r), ("yes" if ok else "NO") + sfx))


def typed(claim, value, rec, dec, scale=1.0, src="README"):
    """A number printed with ``dec`` decimals after dividing by ``scale`` (0.01 for %)."""
    add(f"[{src}] {claim}", value, rec / scale, 0.5 * 10 ** (-dec) + 1e-9, "{:." + str(dec) + "f}")


def maxdiff(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.shape != b.shape:
        return float("inf")
    both_nan = np.isnan(a) & np.isnan(b)
    d = np.abs(a - b)
    d[both_nan] = 0.0
    return float(np.nanmax(d)) if np.isfinite(d).all() else float("inf")


def series_row(claim, pub, rec, tol=1e-12):
    add(claim + " (max abs diff)", 0.0, maxdiff(pub, rec), tol, "{:.2e}")


# ----------------------------------------------------------------------------- statistics
def geo(r):
    return float(np.prod(1 + r) ** (12 / len(r)) - 1)


def vol(r):
    return float(np.std(r, ddof=1) * SQ12)


def srm(x):
    return float(np.mean(x) / np.std(x, ddof=1))


def mdd(r):
    lv = np.cumprod(1 + np.asarray(r, float))
    return float(np.min(lv / np.maximum.accumulate(lv) - 1))


def skku(x):
    x = np.asarray(x, float)
    z = (x - x.mean()) / x.std(ddof=0)
    return float((z ** 3).mean()), float((z ** 4).mean())


def nw(x, lags=LAGS):
    x = np.asarray(x, float)
    n = len(x)
    u = x - x.mean()
    s = float(u @ u)
    for j in range(1, lags + 1):
        s += 2 * (1 - j / (lags + 1)) * float(u[j:] @ u[:-j])
    se = math.sqrt(s) / n
    return float(x.mean()), se, float(x.mean() / se)


def sb_idx(rng, n):
    restart = rng.random(size=(NRES, n)) < 1 / BLOCK
    fresh = rng.integers(0, n, size=(NRES, n))
    idx = np.empty((NRES, n), dtype=np.int64)
    idx[:, 0] = fresh[:, 0]
    for t in range(1, n):
        idx[:, t] = np.where(restart[:, t], fresh[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def boot_ci(x, rng):
    s = np.asarray(x, float)[sb_idx(rng, len(x))]
    sr = s.mean(axis=1) / s.std(axis=1, ddof=1) * SQ12
    return np.quantile(sr, [0.025, 0.975])


def cb_idx(rng, n):
    nb = -(-n // BLOCK)
    st = rng.integers(0, n, size=(NRES, nb))
    return ((st[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(NRES, -1)[:, :n]) % n


def lw_core(r1, r2):
    n = r1.shape[1]
    y = np.stack([r1, r1 ** 2, r2, r2 ** 2], axis=-1)
    a, b, c, d = y.mean(axis=1).T
    v1, v2 = b - a ** 2, d - c ** 2
    diff = a / np.sqrt(v1) - c / np.sqrt(v2)
    g = np.stack([b / v1 ** 1.5, -0.5 * a / v1 ** 1.5, -d / v2 ** 1.5, 0.5 * c / v2 ** 1.5], axis=-1)
    z = y - y.mean(axis=1, keepdims=True)
    cov = np.einsum("bti,btj->bij", z, z) / n
    for k in range(1, LAGS + 1):
        gm = np.einsum("bti,btj->bij", z[:, k:, :], z[:, :-k, :]) / n
        cov += (1 - k / (LAGS + 1)) * (gm + gm.transpose(0, 2, 1))
    return diff, np.sqrt(np.einsum("bi,bij,bj->b", g, cov, g) / n)


def lw_p(x1, x2, rng):
    x1, x2 = np.asarray(x1, float), np.asarray(x2, float)
    d0, s0 = lw_core(x1[None], x2[None])
    t0 = float(d0[0] / s0[0])
    idx = cb_idx(rng, len(x1))
    ext = 0
    with np.errstate(invalid="ignore", divide="ignore"):
        for st in range(0, NRES, 500):
            b = idx[st:st + 500]
            d, s = lw_core(x1[b], x2[b])
            ext += int((np.abs((d - d0[0]) / s) >= abs(t0)).sum())
    return ext / NRES, t0


def dsr(sr, n, sk, ku, ntr, var):
    g = 0.5772156649015329
    srs = math.sqrt(var) * ((1 - g) * norm.ppf(1 - 1 / ntr) + g * norm.ppf(1 - 1 / (ntr * math.e)))
    den = math.sqrt(1 - sk * sr + (ku - 1) / 4 * sr ** 2)
    return srs, float(norm.cdf(sr * math.sqrt(n - 1) / den)), float(norm.cdf((sr - srs) * math.sqrt(n - 1) / den))


def metrics(r, r0):
    ex = np.asarray(r) - np.asarray(r0)
    sk, ku = skku(ex)
    return {"ann_geometric_return": geo(r), "ann_volatility": vol(r), "sharpe_annual": srm(ex) * SQ12,
            "sharpe_monthly": srm(ex), "max_drawdown_monthly": mdd(r), "mean_excess_monthly": float(ex.mean()),
            "hit_rate_positive_excess": float((ex > 1e-15).mean()), "skewness_excess": sk, "kurtosis_excess": ku}


# ----------------------------------------------------------------------------- engines
def run_tilt(w, rl, rc, cost, w0=0.0):
    out, traded, prev = np.empty(len(w)), np.empty(len(w)), w0
    for i in range(len(w)):
        traded[i] = abs(w[i] - prev)
        gross = w[i] * rl[i] + (1 - w[i]) * rc[i]
        out[i] = (1 - cost * traded[i]) ** 2 * (1 + gross) - 1
        prev = w[i] * (1 + rl[i]) / (1 + gross)
    return out, traded


def run_static(w, rl, rc, cost):
    gross = w * rl + (1 - w) * rc
    drift = np.empty_like(gross)
    drift[0] = w
    drift[1:] = w * (1 + rl[:-1]) / (1 + gross[:-1])
    return (1 - cost * np.abs(drift - w)) ** 2 * (1 + gross) - 1


# ----------------------------------------------------------------------------- data
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fred(s):
    raw = pd.read_csv(RAW / f"fred_{s}.csv", dtype=str, keep_default_na=False)
    v = pd.to_numeric(raw.iloc[:, 1].str.strip().replace({"": np.nan, ".": np.nan}), errors="coerce")
    return pd.Series(v.to_numpy(float), index=pd.to_datetime(raw.iloc[:, 0])).dropna()


def bey(d):
    return 365.0 * d / (360.0 - 91.0 * d)


def bond_price(c, y, m):
    i = np.asarray(y, float) / 2
    disc = (1 + i) ** -np.asarray(m, float)
    ann = np.where(i == 0, m, (1 - disc) / np.where(i == 0, 1, i))
    return 100 * (np.asarray(c, float) / 2 * ann + disc)


def par_dmod(y, n=20):
    y = np.asarray(y, float)
    i = y[:, None] / 2
    k = np.arange(1, n + 1, dtype=float)
    cf = np.broadcast_to(y[:, None] / 2 * 100, (len(y), n)).copy()
    cf[:, -1] += 100
    v = 1 / (1 + i)
    return (k * cf * v ** (k + 1)).sum(axis=1) / (cf * v ** k).sum(axis=1) / 2


def duration_leg(d7, d10):
    b = pd.concat([d7.rename("y7"), d10.rename("y10")], axis=1).dropna() / 100
    dt = np.diff(b.index.to_numpy()).astype("timedelta64[D]").astype(float) / 365
    y7s, y10s, y7t, y10t = b.y7.values[:-1], b.y10.values[:-1], b.y7.values[1:], b.y10.values[1:]
    ys = y7s + (y10s - y7s) * 1.5 / 3
    yt = y7t + (y10t - y7t) * (8.5 - dt - 7) / 3
    r = (bond_price(ys, yt, 2 * (8.5 - dt)) / 100 - 1) + ys * dt - IEF_EXP * dt
    return pd.Series(np.concatenate([[1.0], np.cumprod(1 + r)]), index=b.index)


def cash_leg(d3):
    v = d3 / 100
    days = np.diff(v.index.to_numpy()).astype("timedelta64[D]").astype(float)
    r = (bey(v.values[:-1]) - BIL_EXP) * days / 365
    return pd.Series(np.concatenate([[1.0], np.cumprod(1 + r)]), index=v.index)


def at(tri, dates):
    return tri.reindex(pd.DatetimeIndex(dates), method="ffill").to_numpy()


def pret(tri, exe, end):
    return at(tri, end) / at(tri, exe) - 1


def rank_weights(c, m):
    out = np.full(len(c), np.nan)
    for i in range(len(c)):
        n = i + 1
        if n >= m:
            out[i] = (np.sum(c[:n] < c[i]) + 0.5 * np.sum(c[:i] == c[i])) / (n - 1)
    return out


def main() -> int:
    hist = {c: pd.read_csv(RES / "history" / f"monthly_{c}.csv") for c in COSTS}
    hb = hist["base"]
    summ = json.loads((RES / "history" / "summary.json").read_text().replace("NaN", "null"))
    gate = json.loads((RES / "gate" / "gate.json").read_text())
    per = pd.read_csv(RES / "gate" / "periods.csv")
    volc = json.loads((RES / "volcheck" / "volcheck.json").read_text())
    epi = json.loads((RES / "episode" / "summary.json").read_text().replace("NaN", "null"))
    ep = {(s, c): pd.read_csv(RES / "episode" / s / f"monthly_{c}.csv") for s in ("actual", "synthetic") for c in COSTS}
    man = json.loads((STUDY / "charts" / "manifest.json").read_text())
    mt = man["numbers_in_titles"]

    # ------------------------------------------------------------- (g) raw hashes
    dman = json.loads((RES / "data_manifest.json").read_text())
    have_raw = RAW.exists() and all((RAW / f).exists() for f in dman)
    for f, meta in sorted(dman.items()):
        add(f"SHA-256 data/raw/{f} = data_manifest.json", meta["sha256"], sha(RAW / f) if (RAW / f).exists() else "missing")
    repo = STUDY.parent.parent
    for rel, h in man["inputs_sha256"].items():
        add(f"chart manifest input hash {rel.split('/')[-1]} = committed file", h, sha(repo / rel))
    if not have_raw:
        add("raw files present", True, False, note="raw-data rows not checked")
        return report()

    # ------------------------------------------------------------- (a) carry, ranks, trend from raw FRED
    d10, d7, d3 = fred("DGS10"), fred("DGS7"), fred("DTB3")
    three = pd.concat([d10.rename("y10"), d7.rename("y7"), d3.rename("d3")], axis=1).dropna() / 100
    carry_daily = (three.y10 - bey(three.d3)) + par_dmod(three.y10.values) * (three.y10 - three.y7) / 3
    sigd = pd.Series(three.index, index=three.index).groupby(three.index.to_period("M")).last()
    sigd = sigd.loc[pd.Period("1969-07", "M"):pd.Period("2026-09", "M")]
    carry = pd.Series(carry_daily.loc[sigd.values].values, index=sigd.index.astype(str))
    add("signal months 1969-07..2026-09 rebuilt (count)", 687, len(carry), 0, "{:.0f}")
    add("rank history months at 2018-11 (gate: carry months to overlap end 594 incl. 2018-12)",
        gate["signal_history"]["carry_months_to_overlap_end"], len(carry.loc[:"2018-12"]), 0, "{:.0f}")
    hm = hb["month"].astype(str)
    series_row("carry_at_signal, history 534 periods, rebuilt from FRED", hb["carry_at_signal"], carry.loc[hm].values, 1e-15)
    cv = carry.values
    W = {k: pd.Series(rank_weights(cv, m), index=carry.index) for k, m in MINHIST.items()}
    for k in MINHIST:
        add(f"first weight month {k} (m = {MINHIST[k]})", gate["signal_history"]["first_weight_month"][k],
            W[k].first_valid_index())
        series_row(f"w_{k} history, rebuilt from FRED carry", hb[f"w_{k}"], W[k].loc[hm].values, 1e-15)
    add("w_T1 == w_T1a on every test period (design miss, disclosed)", True,
        bool(np.array_equal(W["T1"].loc[hm].values, W["T1a"].loc[hm].values)))
    t1b_m = hb.loc[hb["w_T1b"].notna(), "month"].astype(str)
    add("w_T1 == w_T1b on T1b's 474 periods (disclosed)", True,
        bool(np.array_equal(W["T1"].loc[t1b_m].values, W["T1b"].loc[t1b_m].values)))
    add("T1b periods", 474, len(t1b_m), 0, "{:.0f}")
    add("first weight w_T1 at 1974-06 = 7/59 (n = 60, denominator n - 1)", 7 / 59, W["T1"].loc["1974-06"], 1e-15)

    leg, cash = duration_leg(d7, d10), cash_leg(d3)
    sdates = pd.DatetimeIndex(sigd.values)
    D, C = at(leg, sdates), at(cash, sdates)
    x12 = np.full(len(D), np.nan)
    x12[12:] = D[12:] / D[:-12] - C[12:] / C[:-12]
    h = pd.Series(np.where(np.isnan(x12), np.nan, (x12 > 0).astype(float)), index=carry.index)
    add("first trend month (12 rows after 1969-07)", gate["signal_history"]["first_weight_month"]["T3"],
        h.first_valid_index())
    series_row("w_T3 history (12-month trend on rebuilt synthetic indices)", hb["w_T3"], h.loc[hm].values, 0)
    series_row("w_T2 history = 1/2 w_T1 + 1/2 h", hb["w_T2"], 0.5 * W["T1"].loc[hm].values + 0.5 * h.loc[hm].values, 1e-15)
    add("min |12m excess| over test signals (distance from the sign boundary)", None,
        float(np.nanmin(np.abs(pd.Series(x12, index=carry.index).loc[hm].values))), fmt="{:.2e}")

    # leg returns on committed execution dates; cross-check dates against Study 006
    exe, end = pd.to_datetime(hb["execution_date"]), pd.to_datetime(hb["period_end"])
    add("every execution date strictly after the rebuilt signal date and within 7 days", True,
        bool(((exe.values > sigd.loc[hm.values].values) &
              (exe.values - sigd.loc[hm.values].values <= np.timedelta64(7, "D"))).all()))
    rl, rc = pret(leg, exe, end), pret(cash, exe, end)
    series_row("B1 (synthetic leg) history, rebuilt from FRED", hb["B1"], rl, 1e-13)
    series_row("B0 (synthetic cash) history, rebuilt from FRED", hb["B0"], rc, 1e-13)
    if (S006 / "results/history/monthly_base.csv").exists():
        s6 = pd.read_csv(S006 / "results/history/monthly_base.csv").set_index("month")
        s6 = s6.loc[s6.index.isin(hm)]
        add("execution dates = Study 006 committed history, same 534 months", True,
            bool((s6["execution_date"].values == hb["execution_date"].values).all() and len(s6) == 534))
        series_row("B1, B0 = Study 006 committed history", np.r_[s6["B1"].values, s6["B0"].values],
                   np.r_[hb["B1"].values, hb["B0"].values], 1e-15)

    # ------------------------------------------------------------- (b) engines at both costs
    wts = {k: hb[f"w_{k}"].values for k in TRIALS}
    res = {}
    for case, cost in COSTS.items():
        df = hist[case]
        B1, B0 = df["B1"].values, df["B0"].values
        series_row(f"B2 {case} = 50/50 static with drift cost", df["B2"], run_static(0.5, B1, B0, cost), 1e-15)
        res[case] = {}
        for k in TRIALS:
            sel = ~np.isnan(wts[k])
            wb = float(np.mean(wts[k][sel]))
            add(f"B3 weight {k} = mean weight on own window", summ["weight_b3"][k], wb, 1e-15)
            t, traded = run_tilt(wts[k][sel], B1[sel], B0[sel], cost)
            b3 = run_static(wb, B1[sel], B0[sel], cost)
            series_row(f"{k} {case} tilt engine (from cash, drift, cost on traded fraction)", df[k].values[sel], t, 1e-15)
            series_row(f"B3_{k} {case} static", df[f"B3_{k}"].values[sel], b3, 1e-15)
            res[case][k] = dict(sel=sel, T=t, B3=b3, B1=B1[sel], B0=B0[sel], B2=run_static(0.5, B1[sel], B0[sel], cost),
                                traded=traded, wb=wb, w=wts[k][sel])
            if case == "base":
                add(f"total one-way turnover {k}", summ["total_turnover"][k], traded.sum(), 1e-10)

    # ------------------------------------------------------------- (c) statistics, DSR, §9.5
    nfam = 14
    crit = {}
    for case in COSTS:
        cc = summ["cost_cases"][case]
        mcsv = pd.read_csv(RES / "history" / f"metrics_{case}.csv", index_col=0)
        rng = np.random.default_rng(SEED)
        for k in TRIALS:
            r = res[case][k]
            m = metrics(r["T"], r["B0"])
            for key, val in m.items():
                add(f"{case} {k} {key} vs metrics_{case}.csv", mcsv.loc[k, key], val, 1e-10)
            add(f"{case} {k} sd_weight", mcsv.loc[k, "sd_weight"], np.std(r["w"], ddof=0), 1e-12, note="population sd, ddof 0")
            for bname in ("B1", "B3", "B2"):
                mb = metrics(r[bname], r["B0"])
                pd_ = cc["descriptive"][k][bname]
                for key in ("ann_geometric_return", "ann_volatility", "sharpe_annual", "max_drawdown_monthly"):
                    add(f"{case} {k} window {bname} {key}", pd_[key], mb[key], 1e-10)
            inf = cc["inference"][k]
            lo, hi = boot_ci(r["T"] - r["B0"], rng)
            add(f"{case} {k} Sharpe bootstrap CI low", inf["sharpe_ci"]["ci_low"], lo, 1e-10)
            add(f"{case} {k} Sharpe bootstrap CI high", inf["sharpe_ci"]["ci_high"], hi, 1e-10)
            for bname in ("B1", "B3"):
                mu, se, t = nw(r["T"] - r[bname])
                add(f"{case} {k} NW mean T-{bname}", inf[f"vs_{bname}"]["newey_west"]["mean"], mu, 1e-14)
                add(f"{case} {k} NW se T-{bname}", inf[f"vs_{bname}"]["newey_west"]["se"], se, 1e-14)
                add(f"{case} {k} NW t T-{bname}", inf[f"vs_{bname}"]["newey_west"]["t"], t, 1e-9)
                p, t0 = lw_p(r["T"] - r["B0"], r[bname] - r["B0"], rng)
                add(f"{case} {k} Ledoit-Wolf t vs {bname}", inf[f"vs_{bname}"]["ledoit_wolf"]["t"], t0, 1e-9)
                add(f"{case} {k} Ledoit-Wolf p vs {bname}", inf[f"vs_{bname}"]["ledoit_wolf"]["p_value"], p, 1.01e-4)
        srs = {k: metrics(res[case][k]["T"], res[case][k]["B0"]) for k in TRIALS}
        var_raw = float(np.var([srs[k]["sharpe_monthly"] for k in TRIALS], ddof=1))
        var = max(var_raw, FLOOR)
        add(f"{case} DSR variance floor applied (raw var {var_raw:.2e} < floor {FLOOR:.2e})",
            cc["deflation_inputs"]["floor_applied"], var_raw < FLOOR)
        for k in TRIALS:
            s = srs[k]
            for n in (nfam, 5, 10):
                star, psr, dd = dsr(s["sharpe_monthly"], len(res[case][k]["T"]), s["skewness_excess"], s["kurtosis_excess"], n, var)
                add(f"{case} {k} DSR N={n}", cc["deflated_sharpe"][k][f"N{n}"]["dsr"], dd, 1e-10)
                add(f"{case} {k} SR* N={n}", cc["deflated_sharpe"][k][f"N{n}"]["sr_star_monthly"], star, 1e-12)
        if case == "base":
            for k in TRIALS:
                r, s = res[case][k], srs[k]
                s1 = metrics(r["B1"], r["B0"])["sharpe_annual"]
                s3 = metrics(r["B3"], r["B0"])["sharpe_annual"]
                c1 = s["sharpe_annual"] >= s1 + 0.10 and s["sharpe_annual"] >= s3 + 0.10
                c2 = nw(r["T"] - r["B3"])[2] >= 2.0
                c3 = dsr(s["sharpe_monthly"], len(r["T"]), s["skewness_excess"], s["kurtosis_excess"], nfam, var)[2] >= 0.95
                crit[k] = dict(C1=c1, C2=c2, C3=c3, margins=(s["sharpe_annual"] - s1 - 0.1, s["sharpe_annual"] - s3 - 0.1))
            # break-even family variance for C3 (T1): the DSR at 14 falls to 0.95 when sqrt(V) reaches this
            s = srs["T1"]
            den = math.sqrt(1 - s["skewness_excess"] * s["sharpe_monthly"] + (s["kurtosis_excess"] - 1) / 4 * s["sharpe_monthly"] ** 2)
            zfac = (1 - 0.5772156649015329) * norm.ppf(1 - 1 / 14) + 0.5772156649015329 * norm.ppf(1 - 1 / (14 * math.e))
            sd_be = (s["sharpe_monthly"] - norm.ppf(0.95) * den / math.sqrt(len(res[case]["T1"]["T"]) - 1)) / zfac
            add("C3 break-even: annual sd of family Sharpes at which T1's DSR(14) = 0.95", None, sd_be * SQ12, fmt="{:.3f}")
    for k in TRIALS:
        rb, rs = res["base"][k], res["stress"][k]
        crit[k]["C4"] = np.sign(np.mean(rb["T"] - rb["B3"])) == np.sign(np.mean(rs["T"] - rs["B3"]))
        for c in ("C1", "C2", "C3", "C4"):
            add(f"§9.5 {k} {c}", summ["criteria"][k][c], bool(crit[k][c]))
    add("C1 margins T1 (vs B1+0.10, vs B3+0.10)", None, "%.4f / %.4f" % crit["T1"]["margins"])
    add("C1 margins T2", None, "%.4f / %.4f" % crit["T2"]["margins"])
    add("C1 margins T1b", None, "%.4f / %.4f" % crit["T1b"]["margins"])
    sigma = vol(hb["B1"].values - hb["B0"].values)

    def own_row(k):
        if not all(crit[k][c] for c in ("C1", "C2", "C3", "C4")):
            return "not supported"
        return "consistent with an edge, not detectable at the 2% bar" if sigma > 0.1018 else \
            "supported in history; forward record pending"
    own = {k: own_row(k) for k in TRIALS}
    v1 = own["T1"]
    if v1 != "not supported" and ("not supported" in (own["T1a"], own["T1b"])):
        v1 = "inconclusive (fragile)"
    add("§9.5 T1 headline verdict by reviewer's precedence and companion clause", summ["verdict"]["T1"], v1)
    for k in ("T1b", "T2", "T3"):
        add(f"§9.5 {k} verdict on own criteria", summ["verdict_rows_on_own_criteria"][k], own[k])
    for k in TRIALS:
        add(f"turnover label {k} (none if >= 8)", "None", "None" if res["base"][k]["traded"].sum() >= 8 else "low-powered")
    add("gate row not reached: G1(T1) passes", gate["gate_by_trial"]["T1"]["G1_pass"], True)

    # ------------------------------------------------------------- (d) sub-windows, eras, attribution, mechanism
    cb = summ["cost_cases"]["base"]
    for k in ("T1", "T2", "T3"):
        r = res["base"][k]
        em = pd.to_datetime(hb["execution_date"]).dt.to_period("M").values[r["sel"]]
        for grp, wins in (("sub_windows", SUBW), ("rate_eras", ERAS)):
            pubk = list(cb[grp][k].keys())
            for name, (a, b) in wins.items():
                key = [x for x in pubk if x.startswith(name[:18])][0]
                msk = (em >= pd.Period(a, "M")) & (em <= pd.Period(b, "M"))
                pub = cb[grp][k][key]
                add(f"{grp} {k} {name} periods", pub["T"]["periods"], int(msk.sum()), 0, "{:.0f}")
                for bn in ("T", "B1", "B3"):
                    add(f"{grp} {k} {name} {bn} Sharpe", pub[bn]["sharpe_annual"], metrics(r[bn][msk], r["B0"][msk])["sharpe_annual"], 1e-10)
                mu, se, t = nw(r["T"][msk] - r["B3"][msk])
                add(f"{grp} {k} {name} mean T-B3", pub["T_minus_B3"]["mean_monthly"], mu, 1e-14)
                add(f"{grp} {k} {name} NW t T-B3", pub["T_minus_B3"]["t"], t, 1e-9)
                add(f"{grp} {k} {name} mean weight", pub["T"]["mean_weight"], r["w"][msk].mean(), 1e-12)
    for k in ("T1", "T2", "T3"):
        mu, se, t = nw(res["base"][k]["T"] - res["base"][k]["B3"])
        add(f"attribution {k} mean d annual", cb["attribution"][k]["mean_d_annual"], mu * 12, 1e-13)
        add(f"attribution {k} t", cb["attribution"][k]["t"], t, 1e-9)
    add("corr(w_T1, w_T3)", cb["attribution"]["corr_weight_T1_T3"], np.corrcoef(wts["T1"], wts["T3"])[0, 1], 1e-12)
    xs = hb["B1"].values - hb["B0"].values
    grp = pd.qcut(pd.Series(wts["T1"]).rank(method="first"), 5, labels=[f"Q{i}" for i in range(1, 6)]).values
    for q in [f"Q{i}" for i in range(1, 6)]:
        pq, sel = cb["mechanism"]["by_T1_weight_quintile"][q], grp == q
        add(f"mechanism {q} periods", pq["periods"], int(sel.sum()), 0, "{:.0f}")
        add(f"mechanism {q} weight min / max", f"{pq['weight_min']:.12f}/{pq['weight_max']:.12f}",
            f"{wts['T1'][sel].min():.12f}/{wts['T1'][sel].max():.12f}")
        add(f"mechanism {q} leg excess annual", pq["mean_excess_annual"], xs[sel].mean() * 12, 1e-13)
        add(f"mechanism {q} hit rate", pq["hit_rate_leg_beats_cash"], (xs[sel] > 0).mean(), 1e-13)
    cneg = hb["carry_at_signal"].values <= 0
    for nm, sel in (("carry_le_0", cneg), ("carry_gt_0", ~cneg)):
        add(f"mechanism {nm} periods", cb["mechanism"]["by_carry_sign"][nm]["periods"], int(sel.sum()), 0, "{:.0f}")
        add(f"mechanism {nm} leg excess annual", cb["mechanism"]["by_carry_sign"][nm]["mean_excess_annual"], xs[sel].mean() * 12, 1e-13)
    for k in TRIALS:
        d = res["base"][k]["T"] - res["base"][k]["B3"]
        ratio = nw(d)[1] / (np.std(d, ddof=1) / math.sqrt(len(d)))
        add(f"NW/iid ratio {k}", cb["nw_iid_ratio_vs_B3"][k]["ratio"], ratio, 1e-12)
        add(f"sd(w - wbar) {k}", cb["weight_dispersion"][k]["sd_w_minus_wbar"], np.std(res["base"][k]["w"], ddof=0), 1e-12, note="ddof 0")
    r1 = res["base"]["T1"]
    win = res["base"]["T1b"]["sel"][r1["sel"]]
    m1b = metrics(r1["T"][win], r1["B0"][win])
    add("T1 on T1b's 474 periods Sharpe (descriptive)", cb["T1_on_T1b_window_descriptive"]["sharpe_annual"], m1b["sharpe_annual"], 1e-10)
    t1_on_b = nw(r1["T"][win] - res["base"]["T1b"]["B3"])
    add("T1 (carried-in holdings) on T1b's window vs B3_T1b: NW t", None, t1_on_b[2], fmt="{:.4f}")
    pre = ~win
    add("T1 - B3 annual on 1974-07..1979-06 (60 months)", None, (r1["T"][pre] - r1["B3"][pre]).mean() * 12, fmt="{:.5f}")
    ex79 = pd.to_datetime(hb["execution_date"]).dt.to_period("M").values
    l79 = (ex79 >= pd.Period("1979-07", "M")) & (ex79 <= pd.Period("1979-12", "M"))
    add("T1 - B3 annualised over the six periods executed 1979-07..1979-12", None, (r1["T"][l79] - r1["B3"][l79]).mean() * 12, fmt="{:.4f}")

    # ------------------------------------------------------------- gate from raw ETF files
    ti = {s: pd.read_csv(RAW / f"tiingo_{s}_daily.csv", parse_dates=["date"]).set_index("date")["adjClose"] for s in ("IEF", "BIL")}
    al = {s: pd.read_csv(RAW / f"alpaca_{s}_1Day_all.csv", parse_dates=["date"]).set_index("date")["close"] for s in ("IEF", "BIL")}
    pe, pn = pd.to_datetime(per["execution_date"]), pd.to_datetime(per["period_end"])
    syn_x = pret(leg, pe, pn) - pret(cash, pe, pn)
    ief = np.where(per["ief_vendor"] == "alpaca", pret(al["IEF"], pe, pn), pret(ti["IEF"], pe, pn))
    bilr = np.where(per["bil_vendor"] == "alpaca", pret(al["BIL"], pe, pn),
                    np.where(per["bil_vendor"] == "tiingo", pret(ti["BIL"], pe, pn), pret(cash, pe, pn)))
    xetf = ief - bilr
    g = syn_x - xetf
    add("gate periods", 192, len(per), 0, "{:.0f}")
    add("gate vendor counts IEF tiingo/alpaca", "156/36", f"{(per.ief_vendor == 'tiingo').sum()}/{(per.ief_vendor == 'alpaca').sum()}")
    add("gate vendor rule: IEF alpaca iff execution >= 2016-01-04", True, bool(((per.ief_vendor == "alpaca") == (pe >= "2016-01-04")).all()))
    add("gate BIL synthetic cash iff signal month < 2007-05", True, bool(((per.bil_vendor == "synthetic cash") == (per.month < "2007-05")).all()))
    series_row("gate g rebuilt from FRED legs and ETF closes", per["g"], g, 1e-13)
    pm = per["month"].astype(str)
    for k in TRIALS:
        series_row(f"gate w_{k} on overlap", per[f"w_{k}"], (0.5 * W["T1"] + 0.5 * h if k == "T2" else h if k == "T3" else W[k]).loc[pm].values, 1e-15)
    G2 = float(np.std(g, ddof=1) / np.std(xetf, ddof=1))
    add("G2 sd(g)/sd(x_ETF)", gate["G2_inherited"]["committed_full_precision_006"], G2, 1e-12)
    add("G2 <= 0.32", True, G2 <= 0.32)
    for k in TRIALS:
        w = per[f"w_{k}"].values
        wo = w.mean()
        e = (w - wo) * g
        pk = gate["gate_by_trial"][k]
        add(f"G1 {k} |mean e| x 12", pk["G1_bias_annual"], abs(e.mean()) * 12, 1e-14)
        add(f"G1 {k} <= 0.18%", pk["G1_pass"], abs(e.mean()) * 12 <= 0.0018)
        add(f"gate w_o {k}", pk["w_o"], wo, 1e-14)
        add(f"gate turnover {k} (sum |dw|, no drift)", pk["turnover_one_way"], np.abs(np.diff(w)).sum(), 1e-12)
        if k == "T1":
            series_row("gate e_T1 column", per["e_T1"], e, 1e-15)
            add("T1 weight = 1 on overlap periods (count)", 2, int((w == 1).sum()), 0, "{:.0f}")
            add("T1 weight range on overlap", "0.103-1.000", f"{w.min():.3f}-{w.max():.3f}")
        sp = gate["descriptive_no_decision_weight"]["splits_by_execution_year"][k]
        ey = pe.dt.year.values
        for key, msk in (("2002-2007", ey <= 2007), ("2008-2018", ey >= 2008)):
            ws = w[msk]
            add(f"gate split {k} {key} (execution years) G1", sp[key]["G1_bias_annual"], abs(((ws - ws.mean()) * g[msk]).mean()) * 12, 1e-14)
            add(f"gate split {k} {key} w_o", sp[key]["w_o"], ws.mean(), 1e-14)
    add("mean(g) x 12", gate["gate_by_trial"]["T1"]["mean_g_annual"], g.mean() * 12, 1e-14)
    add("corr(g, x_ETF)", gate["gate_by_trial"]["T1"]["corr_g_x_etf"], np.corrcoef(g, xetf)[0, 1], 1e-12)

    # ------------------------------------------------------------- volatility check
    add("volcheck sigma over 534 periods (rebuilt legs)", volc["sigma_annual"], vol(rl - rc), 1e-12)
    add("volcheck sigma (committed B1 - B0)", volc["sigma_annual"], sigma, 1e-13)
    add("volcheck MDE = 2% sigma / 10.18%", volc["mde_annual"], 0.02 * sigma / 0.1018, 1e-14)
    add("volcheck periods", volc["periods"], 534, 0, "{:.0f}")
    add("sigma <= 10.18% (no low-power label)", summ["low_power_check"], bool(sigma > 0.1018))

    # ------------------------------------------------------------- (e) episode
    ea = ep[("actual", "base")]
    eexe, eend = pd.to_datetime(ea["execution_date"]), pd.to_datetime(ea["period_end"])
    em_ = ea["month"].astype(str)
    series_row("episode actual B1 = Alpaca IEF close returns", ea["B1"], pret(al["IEF"], eexe, eend), 1e-13)
    series_row("episode actual B0 = Alpaca BIL close returns", ea["B0"], pret(al["BIL"], eexe, eend), 1e-13)
    es = ep[("synthetic", "base")]
    series_row("episode synthetic B1 / B0 rebuilt from FRED", np.r_[es["B1"].values, es["B0"].values],
               np.r_[pret(leg, eexe, eend), pret(cash, eexe, eend)], 1e-13)
    for k in MINHIST:
        series_row(f"episode w_{k} (rank still expanding)", ea[f"w_{k}"], W[k].loc[em_].values, 1e-15)
    series_row("episode synthetic w_T3 (synthetic trend)", es["w_T3"], h.loc[em_].values, 0)
    sd_all = pd.DatetimeIndex(sigd.values)
    Ia, Ba = at(al["IEF"], sd_all), at(al["BIL"], sd_all)
    xa = pd.Series(np.r_[np.full(12, np.nan), Ia[12:] / Ia[:-12] - Ba[12:] / Ba[:-12]], index=carry.index)
    series_row("episode actual w_T3 (trend from Alpaca closes, last bar on or before signal date)", ea["w_T3"],
               (xa.loc[em_] > 0).astype(float).values, 0)
    fw = epi["weights_at_last_signal_month_for_forward_record"]
    add("forward start: T1 weight at 2026-09 (4 dp)", fw["T1"], round(W["T1"].loc["2026-09"], 4), 1e-12)
    add("forward start: carry at 2026-09 (4 dp)", fw["carry"], round(carry.loc["2026-09"], 4), 1e-12)
    add("forward start: T3 at 2026-09 (actual trend)", fw["T3"], float(xa.loc["2026-09"] > 0), 0)
    add("forward start: T2 = 1/2 T1 + 1/2 T3 (4 dp)", fw["T2"], round(0.5 * W["T1"].loc["2026-09"] + 0.5 * float(xa.loc["2026-09"] > 0), 4), 1e-12)
    add("rank history months at episode end", epi["rank_history_months_at_episode_end"], len(carry), 0, "{:.0f}")
    epres = {}
    for side in ("actual", "synthetic"):
        for case, cost in COSTS.items():
            df = ep[(side, case)]
            B1, B0 = df["B1"].values, df["B0"].values
            for k in TRIALS:
                wb = summ["weight_b3"][k]
                t, tr = run_tilt(df[f"w_{k}"].values, B1, B0, cost)
                b3 = run_static(wb, B1, B0, cost)
                series_row(f"episode {side} {case} {k} and B3_{k} engine", np.r_[df[k].values, df[f"B3_{k}"].values], np.r_[t, b3], 1e-15)
                mu, se, tt = nw(t - b3)
                pub = epi[side]["cost_cases"][case]["inference"][k]["vs_B3"]["newey_west"]
                add(f"episode {side} {case} {k} NW t vs B3", pub["t"], tt, 1e-9)
                epres[(side, case, k)] = dict(T=t, B3=b3, B1=B1, B0=B0, w=df[f"w_{k}"].values, d=mu, t=tt)
            series_row(f"episode {side} {case} B2", df["B2"], run_static(0.5, B1, B0, cost), 1e-15)
    emc = pd.read_csv(RES / "episode/actual/metrics_base.csv", index_col=0)
    for k in TRIALS:
        e = epres[("actual", "base", k)]
        m = metrics(e["T"], e["B0"])
        for key in ("ann_geometric_return", "sharpe_annual", "max_drawdown_monthly"):
            add(f"episode actual base {k} {key}", emc.loc[k, key], m[key], 1e-10)
        add(f"episode actual base {k} mean weight", emc.loc[k, "mean_weight"], e["w"].mean(), 1e-12)

    # ------------------------------------------------------------- (f) README and trial-log typed numbers
    b = res["base"]
    M = {k: metrics(b[k]["T"], b[k]["B0"]) for k in TRIALS}
    MB1 = {k: metrics(b[k]["B1"], b[k]["B0"]) for k in TRIALS}
    MB3 = {k: metrics(b[k]["B3"], b[k]["B0"]) for k in TRIALS}
    MB2 = metrics(b["T1"]["B2"], b["T1"]["B0"])
    T = {k: nw(b[k]["T"] - b[k]["B3"]) for k in TRIALS}
    TB1 = {k: nw(b[k]["T"] - b[k]["B1"]) for k in TRIALS}
    TS = {k: nw(res["stress"][k]["T"] - res["stress"][k]["B3"]) for k in TRIALS}
    typed("T1 Sharpe", 0.493, M["T1"]["sharpe_annual"], 3)
    typed("B1 Sharpe", 0.382, MB1["T1"]["sharpe_annual"], 3)
    typed("B3 Sharpe", 0.381, MB3["T1"]["sharpe_annual"], 3)
    typed("B2 Sharpe", 0.381, MB2["sharpe_annual"], 3)
    typed("w-bar T1", 0.606, b["T1"]["wb"], 3)
    typed("T1 NW t vs B3", 2.10, T["T1"][2], 2)
    typed("T1 mean d %/month", 0.070, T["T1"][0], 3, 0.01)
    typed("T1 mean d %/yr", 0.85, T["T1"][0] * 12, 2, 0.01)
    typed("T1 stress t", 2.04, TS["T1"][2], 2)
    typed("T1b t", 1.95, T["T1b"][2], 2)
    typed("T1b misses C2 by", 0.05, 2.0 - T["T1b"][2], 2)
    typed("T1 clears C2 by", 0.10, T["T1"][2] - 2.0, 2)
    typed("sigma %", 7.81, sigma, 2, 0.01)
    typed("T1 t vs B1", -0.54, TB1["T1"][2], 2)
    for k, v in (("T1", (7.37, 5.43, 0.493, -7.6, 0.85, 2.10, -0.54, 2.04, 0.606, 29.8)),
                 ("T1b", (7.34, 5.60, 0.516, -7.6, 0.88, 1.95, -0.62, 1.90, 0.604, 25.2)),
                 ("T2", (7.39, 5.50, 0.493, -8.2, 0.86, 2.10, -0.51, 2.02, 0.609, 36.1)),
                 ("T3", (7.38, 6.08, 0.449, -8.9, 0.88, 1.60, -0.41, 1.52, 0.612, 46.0))):
        typed(f"table {k} annual return %", v[0], M[k]["ann_geometric_return"], 2, 0.01)
        typed(f"table {k} volatility %", v[1], M[k]["ann_volatility"], 2, 0.01)
        typed(f"table {k} Sharpe", v[2], M[k]["sharpe_annual"], 3)
        typed(f"table {k} drawdown %", v[3], M[k]["max_drawdown_monthly"], 1, 0.01)
        typed(f"table {k} mean d %/yr", v[4], T[k][0] * 12, 2, 0.01)
        typed(f"table {k} NW t vs B3", v[5], T[k][2], 2)
        typed(f"table {k} NW t vs B1", v[6], TB1[k][2], 2)
        typed(f"table {k} stress t", v[7], TS[k][2], 2)
        typed(f"table {k} B3 weight", v[8], b[k]["wb"], 3)
        typed(f"table {k} turnover", v[9], b[k]["traded"].sum(), 1)
    typed("table T1b same-window B1 Sharpe", 0.406, MB1["T1b"]["sharpe_annual"], 3)
    typed("table T1b same-window B3 Sharpe", 0.405, MB3["T1b"]["sharpe_annual"], 3)
    for k in ("T1", "T2", "T3"):
        typed(f"table {k} same-window B1 / B3 Sharpe", 0.382, MB1[k]["sharpe_annual"], 3)
        typed(f"table {k} same-window B3 Sharpe", 0.381, MB3[k]["sharpe_annual"], 3)
    for k, v in (("T1", (0.998, 0.999, 0.998)), ("T1b", (0.997, 0.999, 0.998)), ("T2", (0.997, 0.999, 0.998)), ("T3", (0.993, 0.996, 0.994))):
        for n, val in zip((14, 5, 10), v):
            typed(f"table {k} DSR N={n}", val, summ["cost_cases"]["base"]["deflated_sharpe"][k][f"N{n}"]["dsr"], 3)
    typed("B1 annual return %", 7.56, MB1["T1"]["ann_geometric_return"], 2, 0.01)
    typed("B3 annual return %", 6.50, MB3["T1"]["ann_geometric_return"], 2, 0.01)
    typed("B2 annual return %", 6.21, MB2["ann_geometric_return"], 2, 0.01)
    typed("B1 vol %", 7.82, MB1["T1"]["ann_volatility"], 2, 0.01)
    typed("B3 vol %", 4.79, MB3["T1"]["ann_volatility"], 2, 0.01)
    typed("B2 vol %", 3.99, MB2["ann_volatility"], 2, 0.01)
    typed("B1 drawdown %", -15.2, MB1["T1"]["max_drawdown_monthly"], 1, 0.01)
    typed("B3 drawdown %", -6.5, MB3["T1"]["max_drawdown_monthly"], 1, 0.01)
    typed("B2 drawdown %", -4.3, MB2["max_drawdown_monthly"], 1, 0.01)
    inf1 = summ["cost_cases"]["base"]["inference"]["T1"]
    typed("T1 bootstrap CI low", 0.22, inf1["sharpe_ci"]["ci_low"], 2)
    typed("T1 bootstrap CI high", 0.74, inf1["sharpe_ci"]["ci_high"], 2)
    typed("T1 Ledoit-Wolf p vs B3", 0.15, inf1["vs_B3"]["ledoit_wolf"]["p_value"], 2)
    for k, v in (("T1", 0.15), ("T1b", 0.19), ("T2", 0.20), ("T3", 0.52)):
        typed(f"Ledoit-Wolf p vs B3 {k}", v, summ["cost_cases"]["base"]["inference"][k]["vs_B3"]["ledoit_wolf"]["p_value"], 2, src="trials.md")
    typed("T1 per-year turnover", 0.67, b["T1"]["traded"].sum() / (534 / 12), 2)
    typed("T1 on T1b window Sharpe", 0.516, m1b["sharpe_annual"], 3)
    typed("T1 - B3 1974-07..1979-06 %/yr", 0.62, (r1["T"][pre] - r1["B3"][pre]).mean() * 12, 2, 0.01)
    em = pd.to_datetime(hb["execution_date"])
    yr = em.dt.year.values
    dec = {"1974–79": yr <= 1979, "1980s": (yr >= 1980) & (yr <= 1989), "1990s": (yr >= 1990) & (yr <= 1999),
           "2000s": (yr >= 2000) & (yr <= 2009), "2010–18": yr >= 2010}
    d1 = b["T1"]["T"] - b["T1"]["B3"]
    for (nm, msk), val, n in zip(dec.items(), (1.50, 1.12, 0.43, 0.29, 1.22), (66, 120, 120, 120, 108)):
        typed(f"decade {nm} T1-B3 %/yr", val, d1[msk].mean() * 12, 2, 0.01)
        add(f"[README] decade {nm} months", n, int(msk.sum()), 0, "{:.0f}")
        add(f"[CHART manifest] decade {nm} mean", mt["decade_mean_d_annual"][nm], d1[msk].mean() * 12, 1e-13)
        add(f"[CHART manifest] decade {nm} NW t", mt["decade_nw_t"][nm], nw(d1[msk])[2], 1e-9)
    # sub-window table
    swt = [("T1", "1974-07 to 2002-12", 342, 0.469, 0.333, 0.332, 0.79, 1.40, 0.568),
           ("T1", "2003-01 to 2018-12", 192, 0.533, 0.499, 0.499, 0.95, 1.91, 0.672),
           ("T1", "1974-07 to 1981-12", 90, -0.099, -0.364, -0.365, 1.72, 1.24, 0.492),
           ("T1", "1982-01 to 2008-12", 324, 0.612, 0.629, 0.629, 0.58, 1.18, 0.596),
           ("T1", "2009-01 to 2018-12", 120, 0.513, 0.452, 0.452, 0.92, 1.51, 0.716)]
    other = {"T2": (0.93, 1.61, 0.75, 1.51, 2.13, 1.40, 0.62, 1.32, 0.57, 0.90),
             "T3": (1.06, 1.38, 0.55, 0.82, 2.53, 1.36, 0.66, 1.00, 0.22, 0.26)}
    exm = em.dt.to_period("M").values
    for i, (k, nm, n, s1, sb1, sb3, dd, tt, mw) in enumerate(swt):
        a, z = nm.split(" to ")
        msk = (exm >= pd.Period(a, "M")) & (exm <= pd.Period(z, "M"))
        add(f"[README] window {nm} months", n, int(msk.sum()), 0, "{:.0f}")
        typed(f"window {nm} T1 Sharpe", s1, metrics(b["T1"]["T"][msk], b["T1"]["B0"][msk])["sharpe_annual"], 3)
        typed(f"window {nm} B1 Sharpe", sb1, metrics(b["T1"]["B1"][msk], b["T1"]["B0"][msk])["sharpe_annual"], 3)
        typed(f"window {nm} B3 Sharpe", sb3, metrics(b["T1"]["B3"][msk], b["T1"]["B0"][msk])["sharpe_annual"], 3)
        typed(f"window {nm} T1-B3 %/yr", dd, d1[msk].mean() * 12, 2, 0.01)
        typed(f"window {nm} T1-B3 t", tt, nw(d1[msk])[2], 2)
        typed(f"window {nm} T1 mean weight", mw, b["T1"]["w"][msk].mean(), 3)
        for k2 in ("T2", "T3"):
            dk = b[k2]["T"][msk] - b[k2]["B3"][msk]
            typed(f"window {nm} {k2}-B3 %/yr", other[k2][2 * i], dk.mean() * 12, 2, 0.01)
            typed(f"window {nm} {k2}-B3 t", other[k2][2 * i + 1], nw(dk)[2], 2)
        for k2 in ("T1", "T2", "T3"):
            dk = b[k2]["T"][msk] - b[k2]["B3"][msk]
            key = [x for x in mt["window_mean_d_annual"][k2] if x.startswith(nm)][0]
            add(f"[CHART manifest] window {k2} {nm} mean", mt["window_mean_d_annual"][k2][key], dk.mean() * 12, 1e-13)
            add(f"[CHART manifest] window {k2} {nm} t", mt["window_nw_t"][k2][key], nw(dk)[2], 1e-9)
    typed("attribution T2 mean %/yr", 0.86, T["T2"][0] * 12, 2, 0.01)
    typed("attribution T3 mean %/yr", 0.88, T["T3"][0] * 12, 2, 0.01)
    typed("attribution T2 t", 2.10, T["T2"][2], 2)
    typed("attribution T3 t", 1.60, T["T3"][2], 2)
    typed("corr(w_T1, w_T3)", 0.325, np.corrcoef(wts["T1"], wts["T3"])[0, 1], 3)
    typed("sd(w) T3 (ddof 0)", 0.487, np.std(wts["T3"], ddof=0), 3)
    typed("sd(w) T1 (ddof 0)", 0.303, np.std(wts["T1"], ddof=0), 3)
    typed("trials.md corr of T1 and T2 monthly returns", 0.950, np.corrcoef(b["T1"]["T"], b["T2"]["T"])[0, 1], 3, src="trials.md")
    for q, lo_, hi_, n, ex, hr in (("Q1", 0.000, 0.288, 107, -0.93, 47.7), ("Q2", 0.289, 0.492, 107, 2.59, 53.3),
                                   ("Q3", 0.495, 0.788, 106, 3.10, 57.5), ("Q4", 0.789, 0.933, 107, -2.29, 46.7),
                                   ("Q5", 0.936, 1.000, 107, 12.45, 65.4)):
        sel = grp == q
        typed(f"mechanism {q} weight min", lo_, wts["T1"][sel].min(), 3)
        typed(f"mechanism {q} weight max", hi_, wts["T1"][sel].max(), 3)
        typed(f"mechanism {q} leg excess %/yr", ex, xs[sel].mean() * 12, 2, 0.01)
        typed(f"mechanism {q} leg beat bills %", hr, (xs[sel] > 0).mean(), 1, 0.01)
    typed("carry <= 0 months leg excess %/yr", -3.9, xs[cneg].mean() * 12, 1, 0.01)
    typed("carry > 0 months leg excess %/yr", 3.9, xs[~cneg].mean() * 12, 1, 0.01)
    add("[README] carry <= 0 months", 61, int(cneg.sum()), 0, "{:.0f}")
    # Power, after the fact
    se1 = T["T1"][1]
    typed("NW se of T1 - B3, %/month", 0.0335, se1, 4, 0.01)
    typed("NW se of T1 - B3, %/yr", 0.40, se1 * 12, 2, 0.01)
    typed("C2 bar t = 2 in %/yr", 0.80, 2 * se1 * 12, 2, 0.01)
    typed("MDE at K = 2.842 in %/yr", 1.14, 2.842 * se1 * 12, 2, 0.01)
    typed("NW/iid T1", 0.981, cb["nw_iid_ratio_vs_B3"]["T1"]["ratio"], 3)
    typed("NW/iid T1b", 0.999, cb["nw_iid_ratio_vs_B3"]["T1b"]["ratio"], 3)
    typed("NW/iid T2", 0.960, cb["nw_iid_ratio_vs_B3"]["T2"]["ratio"], 3)
    typed("NW/iid T3", 0.950, cb["nw_iid_ratio_vs_B3"]["T3"]["ratio"], 3)
    typed("1/sqrt(12)", 0.289, 1 / SQ12, 3)
    s775 = 0.0775 / SQ12

    def mde(sdw, n):
        return 2.842 * s775 * sdw * 0.972 / math.sqrt(n) * 12
    typed("registered MDE at sd 0.5, 534 periods, %/yr", 1.6, mde(0.5, 534), 1, 0.01, src="PREREG/README")
    typed("registered uniform-rank MDE, %/yr", 0.93, mde(1 / SQ12, 534), 2, 0.01, src="README")
    typed("registered uniform-rank MDE, Sharpe", 0.120, mde(1 / SQ12, 534) / 0.0775, 3, src="README")
    typed("forward MDE 60 periods sd 0.5, %/yr", 4.8, mde(0.5, 60), 1, 0.01, src="PREREG §11.4")
    typed("forward MDE 60 periods sd 0.5, Sharpe", 0.62, mde(0.5, 60) / 0.0775, 2, src="PREREG §11.4")
    typed("forward MDE 60 periods uniform, %/yr", 2.8, mde(1 / SQ12, 60), 1, 0.01, src="README/PREREG")
    typed("forward MDE 60 periods uniform, Sharpe", 0.36, mde(1 / SQ12, 60) / 0.0775, 2, src="README/PREREG")
    typed("volcheck MDE %/yr", 1.53, 0.02 * sigma / 0.1018, 2, 0.01, src="trials.md")
    # gate typed
    for k, v in (("T1", 0.019), ("T1a", 0.019), ("T1b", 0.019), ("T2", 0.021), ("T3", 0.061)):
        typed(f"G1 {k} %/yr", v, gate["gate_by_trial"][k]["G1_bias_annual"], 3, 0.01)
    typed("G2", 0.131, G2, 3)
    for k, v in (("T1", 0.672), ("T2", 0.685), ("T3", 0.698)):
        typed(f"gate overlap mean w {k}", v, gate["gate_by_trial"][k]["w_o"], 3, src="trials.md")
    for k, v in (("T1", 7.00), ("T2", 11.53), ("T3", 17.00)):
        typed(f"gate overlap turnover {k}", v, gate["gate_by_trial"][k]["turnover_one_way"], 2, src="trials.md")
    sp1 = gate["descriptive_no_decision_weight"]["splits_by_execution_year"]
    for k, a, z in (("T1", 0.032, 0.003), ("T2", 0.037, 0.026), ("T3", 0.106, 0.050)):
        typed(f"gate split {k} 2003-07 G1 %", a, sp1[k]["2002-2007"]["G1_bias_annual"], 3, 0.01, src="trials.md")
        typed(f"gate split {k} 2008-18 G1 %", z, sp1[k]["2008-2018"]["G1_bias_annual"], 3, 0.01, src="trials.md")
    typed("level gap mean(g) x 12 %", 0.002, g.mean() * 12, 3, 0.01, src="trials.md")
    typed("corr(g, x_ETF)", 0.223, np.corrcoef(g, xetf)[0, 1], 3, src="trials.md")
    # episode typed
    E = {k: epres[("actual", "base", k)] for k in TRIALS}
    ME = {k: metrics(E[k]["T"], E[k]["B0"]) for k in TRIALS}
    MEB1, MEB3 = metrics(E["T1"]["B1"], E["T1"]["B0"]), metrics(E["T1"]["B3"], E["T1"]["B0"])
    for k, v in (("T1", (0.256, 2.03, -6.5, 0.56, 0.59)), ("T2", (0.332, 2.63, -6.0, 1.17, 1.22)), ("T3", (0.409, 3.21, -5.5, 1.78, 1.28))):
        typed(f"episode {k} mean weight", v[0], E[k]["w"].mean(), 3)
        typed(f"episode {k} annual return %", v[1], ME[k]["ann_geometric_return"], 2, 0.01)
        typed(f"episode {k} drawdown %", v[2], ME[k]["max_drawdown_monthly"], 1, 0.01)
        typed(f"episode {k} mean T - B3 %/yr", v[3], E[k]["d"] * 12, 2, 0.01)
        typed(f"episode {k} NW t vs B3", v[4], E[k]["t"], 2)
    typed("episode B1 annual return %", 0.45, MEB1["ann_geometric_return"], 2, 0.01)
    typed("episode B3 annual return %", 1.38, MEB3["ann_geometric_return"], 2, 0.01)
    typed("episode bills annual return %", 2.66, geo(E["T1"]["B0"]), 2, 0.01)
    typed("episode B1 drawdown %", -22.2, MEB1["max_drawdown_monthly"], 1, 0.01)
    typed("episode B3 drawdown %", -13.1, MEB3["max_drawdown_monthly"], 1, 0.01)
    typed("episode T1 Sharpe", -0.33, ME["T1"]["sharpe_annual"], 2)
    typed("episode B1 Sharpe", -0.26, MEB1["sharpe_annual"], 2)
    typed("episode B3 Sharpe (trials.md: 'for both')", -0.259, MEB3["sharpe_annual"], 3, src="trials.md")
    typed("episode T1 mean d %/month", 0.047, E["T1"]["d"], 3, 0.01, src="trials.md")
    typed("episode T1 t vs B1", 0.69, nw(E["T1"]["T"] - E["T1"]["B1"])[2], 2, src="trials.md")
    typed("episode T1 stress t", 0.57, epres[("actual", "stress", "T1")]["t"], 2, src="trials.md")
    typed("episode T1 synthetic t", 0.52, epres[("synthetic", "base", "T1")]["t"], 2)
    typed("forward start T1 weight", 0.411, W["T1"].loc["2026-09"], 3)
    typed("forward start carry %", 1.42, carry.loc["2026-09"], 2, 0.01)
    typed("forward start T2 weight", 0.206, fw["T2"], 3)
    typed("forward start T2 weight, from full-precision T1", 0.206, 0.5 * W["T1"].loc["2026-09"] + 0.5 * fw["T3"], 3)
    eam = ea["month"].astype(str).values
    wE = E["T1"]["w"]
    back = eam[(eam > "2022-07") & (wE >= 0.2)]
    add("[README] episode T1 weight below 0.2 from the 2022-07 signal on", True, bool((wE[eam >= "2022-07"] < 0.2).all()),
        note=f"below 0.2 from 2022-07 to 2024-11 only; >= 0.2 again from {back[0]}, max {wE[eam >= '2022-07'].max():.3f} at 2026-07")
    add("[README] episode T1 weight going into 2022 (2021-12 signal) about 0.4", None, float(wE[eam == "2021-12"][0]), fmt="{:.3f}")
    w10 = (eam >= "2021-12") & (eam <= "2022-09")
    add("[README] ten holding periods signalled 2021-12..2022-09", 10, int(w10.sum()), 0, "{:.0f}")
    typed("episode T1 cumulative 2021-12..2022-09 %", -3.6, np.prod(1 + E["T1"]["T"][w10]) - 1, 1, 0.01)
    typed("episode IEF cumulative 2021-12..2022-09 %", -16.1, np.prod(1 + E["T1"]["B1"][w10]) - 1, 1, 0.01)

    # ------------------------------------------------------------- chart titles (SVG text) vs recomputed
    alts = dict((p, a) for a, p in re.findall(r"!\[([^\]]*)\]\((charts/[^)]*)\.png\)", (STUDY / "README.md").read_text()))
    w1 = wts["T1"]
    lv = {k: np.prod(1 + v) for k, v in (("T1", b["T1"]["T"]), ("B1", b["T1"]["B1"]), ("B3", b["T1"]["B3"]))}
    expect = {
        "history_carry_and_weight": f"The carry tilt held at least 0.9 of the bond in {int((w1 >= 0.9).sum())} of {len(w1)} months "
                                    f"and less than 0.3 in {int((w1 < 0.3).sum())}; carry itself was at or below zero at {int(cneg.sum())} month ends",
        "history_growth": f"Over 1974–2018 the carry tilt's Sharpe was {M['T1']['sharpe_annual']:.2f} against {MB1['T1']['sharpe_annual']:.2f} "
                          f"for the bond and the same-exposure mix (p = {inf1['vs_B3']['ledoit_wolf']['p_value']:.2f}), but it ended "
                          f"{'below' if lv['T1'] < lv['B1'] else 'above'} the bond; verdict {v1}",
        "history_drawdown": f"The tilt's deepest monthly drawdown was {M['T1']['max_drawdown_monthly'] * 100:.1f}%, against ".replace("-", "−") +
                            f"{MB3['T1']['max_drawdown_monthly'] * 100:.1f}% for the same-exposure mix and ".replace("-", "−", 1) +
                            f"{MB1['T1']['max_drawdown_monthly'] * 100:.1f}% for holding the bond".replace("-", "−"),
        "history_differential_by_decade": "The tilt's edge over the same-exposure mix was positive in every decade, from "
                                          f"+{min(d1[m].mean() for m in dec.values()) * 1200:.1f}% a year in the 2000s to +{d1[dec['1974–79']].mean() * 1200:.1f}% in 1974–79; "
                                          f"none alone significant (t {min(nw(d1[m])[2] for m in dec.values()):.1f} to {max(nw(d1[m])[2] for m in dec.values()):.1f})",
        "history_trials_by_window": "Carry alone was ahead of the same-exposure mix in both registered sub-windows and all three rate eras, "
                                    f"but none alone reached t = 2 (highest {max(cb[g_][ 'T1'][x]['T_minus_B3']['t'] for g_ in ('sub_windows', 'rate_eras') for x in cb[g_]['T1']):.2f}); "
                                    f"over the whole window adding trend changed little (+{T['T2'][0] * 1200:.2f}% against +{T['T1'][0] * 1200:.2f}% a year, both t {T['T1'][2]:.2f})",
    }
    for name, title in expect.items():
        svg = (STUDY / "charts" / f"{name}.svg").read_text()
        txt = re.sub(r"\s+", " ", " ".join(html.unescape(re.sub("<[^>]+>", "", x)).strip()
                                         for x in re.findall(r"<text[^>]*>(.*?)</text>", svg, re.S)))
        add(f"[CHART] {name}: title recomputed = SVG text", True, title in txt)
        add(f"[CHART] {name}: README alt text = recomputed title", alts.get(f"charts/{name}", ""), title)
    add("[CHART] decade edge positive in every decade", True, bool(all(d1[m].mean() > 0 for m in dec.values())))
    add("[CHART] T1 ahead of B3 in all 5 windows", True, bool(all(cb[g_]["T1"][x]["T_minus_B3"]["mean_monthly"] > 0
                                                               for g_ in ("sub_windows", "rate_eras") for x in cb[g_]["T1"])))
    for k, v in (("carry_month_ends", len(w1)), ("carry_le_zero", int(cneg.sum())), ("weight_ge_0_9", int((w1 >= 0.9).sum())),
                 ("weight_lt_0_3", int((w1 < 0.3).sum())), ("weight_mean", w1.mean()), ("weight_sd", np.std(w1, ddof=0))):
        add(f"[CHART manifest] {k}", mt[k], v, 1e-12)
    for k in ("T1", "B1", "B3"):
        add(f"[CHART manifest] growth_final {k}", mt["growth_final"][k], lv[k], 1e-9)
    add("[CHART manifest] drawdown T1 / B1 / B3", "%.10f/%.10f/%.10f" % tuple(mt["drawdown_monthly_max"][k] for k in ("T1", "B1", "B3")),
        "%.10f/%.10f/%.10f" % (M["T1"]["max_drawdown_monthly"], MB1["T1"]["max_drawdown_monthly"], MB3["T1"]["max_drawdown_monthly"]))
    lvl1 = np.cumprod(1 + b["T1"]["B1"])
    add("[CHART manifest] B1 drawdown trough holding period", mt["drawdown_B1_trough_holding_period"],
        str(pd.Timestamp(hb["execution_date"].values[int(np.argmin(lvl1 / np.maximum.accumulate(lvl1)))]).to_period("M")))

    # ------------------------------------------------------------- (h) git chain
    chain(summ, gate, volc, epi)
    return report()


def chain(summ, gate, volc, epi):
    def ctime(c):
        try:
            return pd.Timestamp(subprocess.run(["git", "show", "-s", "--format=%cI", c], cwd=STUDY, capture_output=True,
                                               text=True, check=True).stdout.strip())
        except Exception:
            return None
    seq = ["6cc65fb", "7692356", "e4c21e5", "1cb9b28", "b529994", "c9a27f3", "8a304e4", "96af276", "4b2b7fd",
           "ae0cfa7", "04c77e0", "4af5b84", "b43c825", "6cbfa6c", "4c19353", "5dc2d38", "5b7632b", "ab0f01a",
           "9d2d317", "91367d8", "a82006a"]
    t = {c: ctime(c) for c in seq}
    if any(v is None for v in t.values()):
        add("git chain", True, False, note="git not available; not checked")
        return
    add("commit chain strictly increasing in committer time", True, all(t[a] < t[b] for a, b in zip(seq, seq[1:])))
    ds = json.loads((RES / "data_step.json").read_text()).get("run_at_utc")
    for name, run, before, after, code in (
            ("data step", ds, "e4c21e5", "1cb9b28", None),
            ("gate", gate["run_at_utc"], "96af276", "4b2b7fd", gate["code_commit"]),
            ("volcheck", volc["run_at_utc"], "ae0cfa7", "04c77e0", volc["code_commit"]),
            ("history", summ["run_at_utc"], "4af5b84", "b43c825", summ["provenance"]["git_commit"]),
            ("episode", epi["run_at_utc"], "5dc2d38", "5b7632b", epi["provenance"].get("git_commit"))):
        r = pd.Timestamp(run)
        add(f"{name} run {run} after rule/row commit {before} ({t[before].strftime('%H:%M:%S')}) and before output commit "
            f"{after} ({t[after].strftime('%H:%M:%S')})", True, bool(t[before] < r < t[after]))
        if code:
            add(f"{name} code commit = governing commit {before}", True, code.startswith(before))
    add("note 6cbfa6c before episode row 5dc2d38", True, t["6cbfa6c"] < t["5dc2d38"])
    for f, c in (("results/history", "b43c825"), ("results/episode", "5b7632b"), ("results/gate", "4b2b7fd"), ("results/volcheck", "04c77e0")):
        out = subprocess.run(["git", "log", "--format=%h", "--", f], cwd=STUDY, capture_output=True, text=True).stdout.split()
        add(f"{f} committed once ({c})", c, ",".join(out))
    for f, base in (("src", "8a304e4"), ("tests", "8a304e4"), ("reproduce.sh", "8a304e4")):
        out = subprocess.run(["git", "diff", "-U0", base, "b43c825", "--", f], cwd=STUDY, capture_output=True, text=True).stdout
        code = [ln for ln in out.splitlines() if ln[:1] in "+-" and ln[:3] not in ("+++", "---") and not ln[1:].lstrip().startswith("#")]
        add(f"{f}: non-comment lines changed from {base} to the history output b43c825", 0, len(code), 0, "{:.0f}",
            note="config007.py gains one comment line, the family re-count" if f == "src" else "")
    pre = subprocess.run(["git", "diff", "e4c21e5", "HEAD", "--", "PREREGISTRATION.md"], cwd=STUDY, capture_output=True, text=True).stdout
    removed = [ln for ln in pre.splitlines() if ln.startswith("-") and not ln.startswith("---")]
    add("PREREGISTRATION.md since e4c21e5: lines removed", 0, len(removed), 0, "{:.0f}")
    trl = subprocess.run(["git", "diff", "e4c21e5", "HEAD", "--", "trials.md"], cwd=STUDY, capture_output=True, text=True).stdout
    removed = [ln for ln in trl.splitlines() if ln.startswith("-") and not ln.startswith("---")]
    add("trials.md since e4c21e5: lines removed (rewritten rows)", None, len(removed), fmt="{:.0f}")
    for c, label in (("c9a27f3", "trials.md 'Implementation, part 2' row labelled 12:4x GMT"),
                     ("8a304e4", "trials.md 'Implementation, part 3' row labelled 12:3x GMT")):
        add(f"{label}: commit time", None, t[c].strftime("%H:%M:%S"))


def report() -> int:
    w = max(len(r[0]) for r in rows)
    print(f"{'claim':<{w}} | published | recomputed | match")
    for r in rows:
        print(f"{r[0]:<{w}} | {r[1]} | {r[2]} | {r[3]}")
    n_yes = sum(r[3].startswith("yes") for r in rows)
    n_no = sum(r[3].startswith("NO") for r in rows)
    n_info = sum(r[3].startswith("info") for r in rows)
    print(f"\n{len(rows)} rows: {n_yes} match, {n_no} mismatch, {n_info} informational")
    return 1 if n_no else 0


if __name__ == "__main__":
    sys.exit(main())
