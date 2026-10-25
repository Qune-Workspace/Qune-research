"""Separate-session recomputation for REVIEW.md (Study 008, bond value tilt by
the real yield on the 1974-2018 history).

Written by the reviewer (Tester, a separate agent session that did not write
the code, the pre-registration or the note), adapted from Study 007's review
script.  It imports nothing from the study's ``src/`` or from
``qune_research``: every number is re-derived with numpy, pandas and scipy
only, from

  * the raw files in ``data/raw/`` (git-ignored; present on disk at review
    time): FRED DGS7, DGS10, DTB3, CPIAUCNS, CPILFENS; the ALFRED vintage
    cache ``data/raw/alfred/``; Tiingo ``adjClose`` and the broker's
    ``adjustment='all'`` closes for IEF and BIL;
  * the committed outputs under ``results/`` and the typed numbers of
    README.md and trials.md.

What is rebuilt from raw data: the signal dates (last date of each month on
which DGS10, DGS7 and DTB3 all exist); **k for each signal month from the
ALFRED cache itself** (m - 1 if the vintage dated on the signal date holds a
value for m - 1, else the latest month it holds; a 404 marker means no
vintage: CPILFENS then follows the CPIAUCNS vintage for the same date, §16 (a);
an index missing from the current file makes r undefined, §16 (b)) and
compared with ``results/cpi_availability.csv``; pi, the real yield, the
expanding (min 60) and trailing-120 average-rank weights over defined values;
the synthetic 8.5-year leg and bill leg (Study 002 §5.2, Study 001 §5.2,
formulas as in Study 007's review script); the leg returns on the committed
execution dates; the gate gap g from the ETF closes; the episode's actual ETF
returns.  Execution dates are taken from the committed files and cross-checked
against Study 007's committed history.

Statistics (twelve metrics, Newey-West t with Bartlett 6 lags, stationary
bootstrap Sharpe interval, Ledoit-Wolf p, DSR, §9.5 rows with the era row and
precedence) are the reviewer's own code.  Random draws reproduce the
committed order: per cost case a fresh ``numpy.random.default_rng(20261021)``;
for T1, T1a, T1b in turn, the Sharpe interval, Ledoit-Wolf vs B1, vs B3.

Run from the study folder:  ../../.venv/bin/python review_recompute.py
Prints one row per check; exit status 1 if any row mismatches.  Nothing is
written to disk.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

STUDY = Path(__file__).resolve().parent
RES = STUDY / "results"
RAW = STUDY / "data" / "raw"
ALF = RAW / "alfred"
S006 = STUDY.parent / "006-term-spread-switch-long-history"
S007 = STUDY.parent / "007-bond-carry-tilt-long-history"
SQ12 = math.sqrt(12.0)
LAGS = 6
IEF_EXP, BIL_EXP = 0.0015, 0.001356
COSTS = {"base": 2e-4, "stress": 4e-4}
SEED, NRES, BLOCK = 20261021, 10_000, 12
FLOOR = (0.05 / SQ12) ** 2
TRIALS = ("T1", "T1a", "T1b")
CPI_OF = {"T1": "CPIAUCNS", "T1a": "CPILFENS", "T1b": "CPIAUCNS"}
NFAM = 17
SUBW = {"1974-07 to 2002-12": ("1974-07", "2002-12"), "2003-01 to 2018-12": ("2003-01", "2018-12"),
        "1974-07 to 1985-12": ("1974-07", "1985-12")}
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
    if not np.array_equal(np.isnan(a), np.isnan(b)):
        return float("inf")
    d = np.abs(a - b)
    d[np.isnan(a)] = 0.0
    return float(d.max()) if len(d) else 0.0


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
    """Fractional engine from cash; a NaN weight holds the drifted weight (traded 0)."""
    n = len(w)
    out, traded, used, prev = np.empty(n), np.empty(n), np.empty(n), w0
    for i in range(n):
        wi = prev if np.isnan(w[i]) else w[i]
        used[i] = wi
        traded[i] = abs(wi - prev)
        gross = wi * rl[i] + (1 - wi) * rc[i]
        out[i] = (1 - cost * traded[i]) ** 2 * (1 + gross) - 1
        prev = wi * (1 + rl[i]) / (1 + gross)
    return out, traded, used


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


def cpi_monthly(path):
    """Monthly CPI from a FRED/ALFRED csv, indexed 'YYYY-MM'; empty values kept as NaN."""
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    v = pd.to_numeric(raw.iloc[:, 1].str.strip().replace({"": np.nan, ".": np.nan}), errors="coerce")
    return pd.Series(v.to_numpy(float), index=raw.iloc[:, 0].str[:7].to_numpy())


def bey(d):
    return 365.0 * d / (360.0 - 91.0 * d)


def bond_price(c, y, m):
    i = np.asarray(y, float) / 2
    disc = (1 + i) ** -np.asarray(m, float)
    ann = np.where(i == 0, m, (1 - disc) / np.where(i == 0, 1, i))
    return 100 * (np.asarray(c, float) / 2 * ann + disc)


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


def prev_month(m, k=1):
    return str(pd.Period(m, "M") - k)


def expanding_rank(v, m):
    """§6.2 over defined values v (no NaN): (#{s<=i: v_s<v_i} + 0.5 #{s<i: v_s=v_i}) / (n-1), n >= m."""
    out = np.full(len(v), np.nan)
    for i in range(len(v)):
        n = i + 1
        if n >= m:
            out[i] = (np.sum(v[:n] < v[i]) + 0.5 * np.sum(v[:i] == v[i])) / (n - 1)
    return out


def trailing_rank(v, win=120):
    out = np.full(len(v), np.nan)
    for i in range(win - 1, len(v)):
        s = v[i - win + 1:i + 1]
        out[i] = (np.sum(s < v[i]) + 0.5 * np.sum(s[:-1] == v[i])) / (win - 1)
    return out


def on_defined(r, fn):
    ok = ~np.isnan(r.values)
    out = np.full(len(r), np.nan)
    out[ok] = fn(r.values[ok])
    return pd.Series(out, index=r.index)


def main() -> int:
    hist = {c: pd.read_csv(RES / "history" / f"monthly_{c}.csv") for c in COSTS}
    hb = hist["base"]
    summ = json.loads((RES / "history" / "summary.json").read_text().replace("NaN", "null"))
    gate = json.loads((RES / "gate" / "gate.json").read_text())
    per = pd.read_csv(RES / "gate" / "periods.csv")
    sig = pd.read_csv(RES / "gate" / "signals.csv").set_index("month")
    volc = json.loads((RES / "volcheck" / "volcheck.json").read_text())
    epi = json.loads((RES / "episode" / "summary.json").read_text().replace("NaN", "null"))
    ep = {(s, c): pd.read_csv(RES / "episode" / s / f"monthly_{c}.csv") for s in ("actual", "synthetic") for c in COSTS}
    avail = pd.read_csv(RES / "cpi_availability.csv", dtype=str, keep_default_na=False).set_index("signal_month")
    vchk = json.loads((RES / "vintage_check.json").read_text())

    # ------------------------------------------------------------- (g) raw hashes
    dman = json.loads((RES / "data_manifest.json").read_text())
    have_raw = RAW.exists() and all((RAW / f).exists() for f in dman)
    for f, meta in sorted(dman.items()):
        add(f"SHA-256 data/raw/{f} = data_manifest.json", meta["sha256"], sha(RAW / f) if (RAW / f).exists() else "missing")
    for f, meta in sorted(summ["provenance"]["data"].items()):
        add(f"history provenance hash {f} = data_manifest.json", dman[f]["sha256"], meta["sha256"])
    for src, rel in (("007", S007 / "results/history/monthly_base.csv"), ("006", S006 / "results/history/monthly_base.csv")):
        add(f"gate overlap source hash, Study {src} monthly_base.csv = committed file",
            gate["overlap_with_006_007"]["sources"][src]["sha256"], sha(rel))
    if not have_raw:
        add("raw files present", True, False, note="raw-data rows not checked")
        return report()
    acm = pd.read_csv(RES / "alfred_cache_manifest.csv", dtype=str, keep_default_na=False)
    bad = sum(1 for _, rw in acm.iterrows() if not (ALF / rw["file"]).exists() or sha(ALF / rw["file"]) != rw["sha256"])
    add("ALFRED cache: files whose SHA-256 differs from alfred_cache_manifest.csv (of %d)" % len(acm), 0, bad, 0, "{:.0f}")
    add("ALFRED cache: outcomes 200 / 404", "1045/329",
        f"{(acm.outcome == '200').sum()}/{(acm.outcome == '404').sum()}")

    # ------------------------------------------------------------- (a) signal dates, k, pi, r, ranks
    d10, d7, d3 = fred("DGS10"), fred("DGS7"), fred("DTB3")
    three = pd.concat([d10.rename("y10"), d7.rename("y7"), d3.rename("d3")], axis=1).dropna()
    sigd = pd.Series(three.index, index=three.index).groupby(three.index.to_period("M")).last()
    sigd = sigd.loc[pd.Period("1969-07", "M"):pd.Period("2026-09", "M")]
    sigd.index = sigd.index.astype(str)
    months = list(sigd.index)
    add("signal months 1969-07..2026-09 rebuilt (count)", 687, len(months), 0, "{:.0f}")
    add("signal dates = cpi_availability.csv signal_date", True,
        bool((avail.loc[months, "signal_date"].values == sigd.dt.strftime("%Y-%m-%d").values).all()))
    cpi = {s: cpi_monthly(RAW / f"fred_{s}.csv") for s in ("CPIAUCNS", "CPILFENS")}
    add("current CPI files: months with an empty value", "2025-10/2025-10",
        "/".join(",".join(cpi[s].index[cpi[s].isna()]) for s in ("CPIAUCNS", "CPILFENS")))

    def vintage_k(series, m, d):
        f = ALF / f"{series}_{d}.csv"
        if not f.exists():
            return None  # 404: no vintage at t
        v = cpi_monthly(f).dropna()
        v = v[v.index <= prev_month(m)]
        if prev_month(m) in v.index:
            return prev_month(m), 1
        return (v.index[-1] if len(v) else None), 0
    K = {"CPIAUCNS": {}, "CPILFENS": {}}
    pubflag = {"CPIAUCNS": {}, "CPILFENS": {}}
    for m in months:
        d = sigd[m].strftime("%Y-%m-%d")
        kh = vintage_k("CPIAUCNS", m, d)
        K["CPIAUCNS"][m] = kh[0] if kh else prev_month(m)
        pubflag["CPIAUCNS"][m] = kh[1] if kh else None
        kc = vintage_k("CPILFENS", m, d)
        pubflag["CPILFENS"][m] = kc[1] if kc else None
        K["CPILFENS"][m] = kc[0] if kc else K["CPIAUCNS"][m]  # §16 (a): core follows the headline release
    for s in ("CPIAUCNS", "CPILFENS"):
        csv_k = avail.loc[months, f"{s}_k"].values
        mine = np.array([K[s][m] for m in months])
        diff = [m for m, a, b in zip(months, csv_k, mine) if a != b]
        add(f"k_{s} rebuilt from ALFRED cache vs cpi_availability.csv: months that differ", "" if s == "CPIAUCNS" else "1996-01",
            ",".join(diff), note="1996-01 is the §16 (a) change; the csv predates it" if s == "CPILFENS" else "")
        late = [m for m in months if pubflag[s][m] == 0]
        add(f"{s}: m-1 not published by t (rebuilt)", ",".join(x["signal_month"] for x in vchk["series"][s]["m1_not_published_by_t"]),
            ",".join(late))
        csv_flag = avail.loc[months, f"{s}_m1_published_by_t"].values
        add(f"{s}: published-by-t flag rebuilt = csv", True,
            bool(all((str(pubflag[s][m]) if pubflag[s][m] is not None else "") == f for m, f in zip(months, csv_flag))))
    for s in ("CPIAUCNS", "CPILFENS"):  # §5.1 (a): December vintages vs the current file
        rc_ = vchk["series"][s]["revision_check"]
        nmon, ndiff = 0, 0
        for ym in rc_:
            v = cpi_monthly(ALF / f"{s}_{sigd[ym].strftime('%Y-%m-%d')}.csv").dropna()
            cur = cpi[s].reindex(v.index)
            ok = cur.notna().values
            nmon += int(ok.sum())
            ndiff += int((np.abs(cur.values[ok] - v.values[ok]) > 1e-9).sum())
        add(f"{s} revision check: December vintages compared (count)", len(rc_), len(rc_), 0, "{:.0f}")
        add(f"{s} revision check: months compared, all vintages", sum(x["months_compared"] for x in rc_.values()), nmon, 0, "{:.0f}")
        add(f"{s} revision check: months differing from the current file", 0, ndiff, 0, "{:.0f}")
    add("CPILFENS signal months without an ALFRED vintage (404)", 329, sum(pubflag["CPILFENS"][m] is None for m in months), 0, "{:.0f}")
    add("CPILFENS first month with a vintage", "1996-12", next(m for m in months if pubflag["CPILFENS"][m] is not None))

    R, PI = {}, {}
    for s in ("CPIAUCNS", "CPILFENS"):
        c = cpi[s]
        pi = []
        for m in months:
            k = K[s][m]
            a, b = c.get(k, np.nan), c.get(prev_month(k, 12), np.nan)
            v = a / b - 1
            if np.isnan(c.get(prev_month(m), np.nan)):  # §16 (b): never published -> undefined, hold
                v = np.nan
            pi.append(v)
        PI[s] = pd.Series(pi, index=months)
        y = d10.reindex(pd.DatetimeIndex(sigd.values)).to_numpy() / 100
        R[s] = pd.Series(y - PI[s].values, index=months)
        add(f"undefined real-yield months {s} (rebuilt)", "2025-11", ",".join(R[s].index[R[s].isna()]))
        series_row(f"k_{s} rebuilt = gate signals.csv (to 2018-12), as month index", 0 * np.arange(len(sig)),
                   np.array([0 if K[s][m] == sig.loc[m, f"k_{s}"] else 1 for m in sig.index]), 0)
        series_row(f"pi_{s} rebuilt = signals.csv", sig[f"pi_{s}"], PI[s].loc[sig.index].values, 1e-15)
        series_row(f"r_{s} rebuilt = signals.csv", sig[f"r_{s}"], R[s].loc[sig.index].values, 1e-15)
    hm = hb["month"].astype(str)
    for s in ("CPIAUCNS", "CPILFENS"):
        series_row(f"r_{s} rebuilt = history monthly_base (534)", hb[f"r_{s}"], R[s].loc[hm].values, 1e-15)
    W = {"T1": on_defined(R["CPIAUCNS"], lambda v: expanding_rank(v, 60)),
         "T1a": on_defined(R["CPILFENS"], lambda v: expanding_rank(v, 60)),
         "T1b": on_defined(R["CPIAUCNS"], trailing_rank)}
    for k in TRIALS:
        add(f"first weight month {k}", gate["signal_history"]["first_weight_month"][k], W[k].first_valid_index())
        series_row(f"w_{k} rebuilt = gate signals.csv (594 months)", sig[f"w_{k}"], W[k].loc[sig.index].values, 1e-15)
        series_row(f"w_{k} rebuilt = history monthly_base", hb[f"w_{k}"], W[k].loc[hm].values, 1e-15)
    add("T1 first weight at 1974-06 (n = 60)", None, W["T1"].loc["1974-06"], fmt="{:.4f}")
    add("T1b periods (defined w_T1b in history)", 474, int(hb["w_T1b"].notna().sum()), 0, "{:.0f}")
    add("T1a rank differs from T1 on the test window (periods with w_T1a != w_T1)", None,
        int((W["T1"].loc[hm].values != W["T1a"].loc[hm].values).sum()), fmt="{:.0f}")
    # what the csv's own CPILFENS k (pre-§16 (a)) would have given T1a at 1996-01: informational
    kc = avail.loc["1996-01", "CPILFENS_k"]
    alt = cpi["CPILFENS"][kc] / cpi["CPILFENS"][str(pd.Period(kc, "M") - 12)] - 1
    add("T1a 1996-01: r with the csv's k = 1995-12 (pre-§16 (a)) vs used", None,
        f"{(d10.reindex([sigd['1996-01']]).iloc[0] / 100 - alt):.6f} vs {R['CPILFENS'].loc['1996-01']:.6f}")

    # ------------------------------------------------------------- legs and engine
    leg, cash = duration_leg(d7, d10), cash_leg(d3)
    exe, end = pd.to_datetime(hb["execution_date"]), pd.to_datetime(hb["period_end"])
    sdt = pd.DatetimeIndex(sigd.loc[hm].values)
    add("every execution date 1-7 days after the rebuilt signal date", True,
        bool(((exe.values > sdt.values) & (exe.values - sdt.values <= np.timedelta64(7, "D"))).all()))
    s7 = pd.read_csv(S007 / "results/history/monthly_base.csv")
    add("execution dates and months = Study 007 committed history (534)", True,
        bool((s7["execution_date"].values == hb["execution_date"].values).all() and (s7["month"].values == hm.values).all()))
    rl, rc = pret(leg, exe, end), pret(cash, exe, end)
    series_row("B1 (synthetic leg) rebuilt from FRED", hb["B1"], rl, 1e-13)
    series_row("B0 (synthetic cash) rebuilt from FRED", hb["B0"], rc, 1e-13)
    series_row("B1, B0 = Study 007 committed history", np.r_[s7["B1"].values, s7["B0"].values], np.r_[hb["B1"].values, hb["B0"].values], 1e-15)

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
            add(f"B3 weight {k} = mean signal weight on own window", summ["weight_b3"][k], wb, 1e-15)
            t, traded, used = run_tilt(wts[k][sel], B1[sel], B0[sel], cost)
            b3 = run_static(wb, B1[sel], B0[sel], cost)
            series_row(f"{k} {case} tilt engine (from cash, drift, cost on traded fraction)", df[k].values[sel], t, 1e-15)
            series_row(f"B3_{k} {case} static", df[f"B3_{k}"].values[sel], b3, 1e-15)
            res[case][k] = dict(sel=sel, T=t, B3=b3, B1=B1[sel], B0=B0[sel], B2=run_static(0.5, B1[sel], B0[sel], cost),
                                traded=traded, wb=wb, w=wts[k][sel])
            if case == "base":
                add(f"total one-way turnover {k}", summ["total_turnover"][k], traded.sum(), 1e-10)
    add("hold periods in the test window (all trials)", "[]", str([m for k in TRIALS for m in summ["hold_periods"][k]]))

    # ------------------------------------------------------------- (c) statistics, DSR, §9.5
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
            add(f"{case} {k} sd_weight", mcsv.loc[k, "sd_weight"], np.std(r["w"], ddof=0), 1e-12, note="ddof 0")
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
            for n in (NFAM, 3, 10):
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
                c3 = dsr(s["sharpe_monthly"], len(r["T"]), s["skewness_excess"], s["kurtosis_excess"], NFAM, var)[2] >= 0.95
                crit[k] = dict(C1=c1, C2=c2, C3=c3, margins=(s["sharpe_annual"] - s1 - 0.1, s["sharpe_annual"] - s3 - 0.1))
    for k in TRIALS:
        rb, rs = res["base"][k], res["stress"][k]
        crit[k]["C4"] = np.sign(np.mean(rb["T"] - rb["B3"])) == np.sign(np.mean(rs["T"] - rs["B3"]))
        for c in ("C1", "C2", "C3", "C4"):
            add(f"§9.5 {k} {c}", summ["criteria"][k][c], bool(crit[k][c]))
        add(f"C1 margins {k} (vs B1+0.10, vs B3+0.10)", None, "%.4f / %.4f" % crit[k]["margins"])
    sigma = vol(hb["B1"].values - hb["B0"].values)
    # era row
    exm = exe.dt.to_period("M").values
    era = (exm >= pd.Period("1986-01", "M")) & (exm <= pd.Period("2018-12", "M"))
    d1 = res["base"]["T1"]["T"] - res["base"]["T1"]["B3"]
    pe_ = summ["cost_cases"]["base"]["era_row_T1"]
    add("era row periods", pe_["periods"], int(era.sum()), 0, "{:.0f}")
    add("era row mean(T1 - B3) a year", pe_["mean_d_annual"], d1[era].mean() * 12, 1e-14)
    add("era row NW t (reported)", pe_["nw_t_reported_not_tested"], nw(d1[era])[2], 1e-9)
    era_pass = bool(d1[era].mean() > 0)
    add("era row pass (sign only)", pe_["pass"], era_pass)

    def own_row(k):
        if not all(crit[k][c] for c in ("C1", "C2", "C3", "C4")):
            return "not supported"
        return "meets C1-C4"
    own = {k: own_row(k) for k in TRIALS}
    gate_t1 = gate["gate_by_trial"]["T1"]["G1_pass"]
    if not gate_t1:
        v1 = "inconclusive (gate)"
    elif own["T1"] == "not supported":
        v1 = "not supported"
    elif not era_pass:
        v1 = "inconclusive (one era)"
    elif "not supported" in (own["T1a"], own["T1b"]):
        v1 = "inconclusive (fragile)"
    elif sigma > 0.1018:
        v1 = "consistent with an edge, not detectable at the 2% bar"
    else:
        v1 = "supported in history; forward record pending"
    add("§9.5 T1 headline verdict by reviewer's precedence", summ["verdict"]["T1"], v1)
    for k in ("T1a", "T1b"):
        add(f"§9.5 {k} row on own criteria", summ["verdict_rows_on_own_criteria"][k], own[k])
    for k in TRIALS:
        add(f"turnover label {k} (none if >= 8)", "None", "None" if res["base"][k]["traded"].sum() >= 8 else "low-powered")
    # counterfactual: would the era row alone have decided?  (informational)
    add("C1-C4 failures for T1 (reviewer)", None, ",".join(c for c in ("C1", "C2", "C3", "C4") if not crit["T1"][c]))

    # ------------------------------------------------------------- (d) sub-windows, eras, mechanism, power
    cb = summ["cost_cases"]["base"]
    for k in TRIALS:
        r = res["base"][k]
        em = exm[r["sel"]]
        for grp, wins in (("sub_windows", SUBW), ("rate_eras", ERAS)):
            for name, (a, z) in wins.items():
                key = [x for x in cb[grp][k] if x.startswith(name)][0]
                msk = (em >= pd.Period(a, "M")) & (em <= pd.Period(z, "M"))
                pub = cb[grp][k][key]
                if "T" not in pub:
                    add(f"{grp} {k} {name} periods (too few)", pub["periods"], int(msk.sum()), 0, "{:.0f}")
                    continue
                add(f"{grp} {k} {name} periods", pub["T"]["periods"], int(msk.sum()), 0, "{:.0f}")
                for bn in ("T", "B1", "B3"):
                    add(f"{grp} {k} {name} {bn} Sharpe", pub[bn]["sharpe_annual"], metrics(r[bn][msk], r["B0"][msk])["sharpe_annual"], 1e-10)
                mu, se, t = nw(r["T"][msk] - r["B3"][msk])
                add(f"{grp} {k} {name} mean T-B3", pub["T_minus_B3"]["mean_monthly"], mu, 1e-14)
                add(f"{grp} {k} {name} NW t T-B3", pub["T_minus_B3"]["t"], t, 1e-9)
                add(f"{grp} {k} {name} mean weight", pub["T"]["mean_weight"], r["w"][msk].mean(), 1e-12)
    xs = hb["B1"].values - hb["B0"].values
    w1 = wts["T1"]
    grp = pd.qcut(pd.Series(w1).rank(method="first"), 5, labels=[f"Q{i}" for i in range(1, 6)]).values
    for q in [f"Q{i}" for i in range(1, 6)]:
        pq, sel = cb["mechanism"]["by_T1_weight_quintile"][q], grp == q
        add(f"mechanism {q} periods", pq["periods"], int(sel.sum()), 0, "{:.0f}")
        add(f"mechanism {q} weight min / max", f"{pq['weight_min']:.12f}/{pq['weight_max']:.12f}",
            f"{w1[sel].min():.12f}/{w1[sel].max():.12f}")
        add(f"mechanism {q} leg excess annual", pq["mean_excess_annual"], xs[sel].mean() * 12, 1e-13)
        add(f"mechanism {q} hit rate", pq["hit_rate_leg_beats_cash"], (xs[sel] > 0).mean(), 1e-13)
    rneg = R["CPIAUCNS"].loc[hm].values <= 0
    for nm, sel in (("r_le_0", rneg), ("r_gt_0", ~rneg)):
        add(f"mechanism {nm} periods", cb["mechanism"]["by_real_yield_sign"][nm]["periods"], int(sel.sum()), 0, "{:.0f}")
        add(f"mechanism {nm} leg excess annual", cb["mechanism"]["by_real_yield_sign"][nm]["mean_excess_annual"], xs[sel].mean() * 12, 1e-13)
    for k in TRIALS:
        d = res["base"][k]["T"] - res["base"][k]["B3"]
        se_nw = nw(d)[1]
        pw = cb["power_realised"][k]
        add(f"NW/iid ratio {k}", pw["ratio"], se_nw / (np.std(d, ddof=1) / math.sqrt(len(d))), 1e-12)
        add(f"sd(w - wbar) {k}", pw["sd_w_minus_wbar"], np.std(res["base"][k]["w"], ddof=0), 1e-12, note="ddof 0")
        add(f"MDE at t = 2 {k}", pw["mde_annual_at_t2"], 2 * se_nw * 12, 1e-14)
        add(f"MDE at K = 2.842 {k}", pw["mde_annual_at_80pct_power"], 2.842 * se_nw * 12, 1e-14)
    d7_ = s7["T1"].values - s7["B3_T1"].values
    add("corr(d T1 008, d T1 007)", cb["overlap_after_the_fact"]["corr_d_T1_008_vs_007"], np.corrcoef(d1, d7_)[0, 1], 1e-12)
    r1 = res["base"]["T1"]
    win = res["base"]["T1b"]["sel"]
    m1b = metrics(r1["T"][win], r1["B0"][win])
    p1b = cb["T1_on_T1b_window_descriptive"]
    add("T1 on T1b's 474 periods Sharpe (descriptive)", p1b["sharpe_annual"], m1b["sharpe_annual"], 1e-10)
    add("T1 on T1b's 474 periods NW t vs T1's own B3", p1b["T_minus_own_B3"]["t"], nw(d1[win])[2], 1e-9)
    add("T1 on T1b's window: mean d a year", None, d1[win].mean() * 12, fmt="{:.5f}")
    for k in TRIALS:
        for s in ("CPIAUCNS", "CPILFENS"):
            av = summ["availability"][k][s]
            ks = res["base"][k]["sel"]
            ms = hm.values[ks]
            add(f"availability {k} {s}: k != m-1 count", av["k_not_m_minus_1"], int(sum(K[s][m] != prev_month(m) for m in ms)), 0, "{:.0f}")

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
    add("gate vendor rule: IEF alpaca iff execution >= 2016-01-04", True, bool(((per.ief_vendor == "alpaca") == (pe >= "2016-01-04")).all()))
    add("gate BIL synthetic cash iff signal month < 2007-05", True, bool(((per.bil_vendor == "synthetic cash") == (per.month < "2007-05")).all()))
    series_row("gate g rebuilt from FRED legs and ETF closes", per["g"], g, 1e-13)
    pm = per["month"].astype(str)
    for k in TRIALS:
        series_row(f"gate w_{k} on overlap = rebuilt", per[f"w_{k}"], W[k].loc[pm].values, 1e-15)
    G2 = float(np.std(g, ddof=1) / np.std(xetf, ddof=1))
    add("G2 sd(g)/sd(x_ETF)", gate["G2_inherited"]["committed_full_precision_006"], G2, 1e-12)
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
        sp = gate["descriptive_no_decision_weight"]["splits_by_execution_year"][k]
        ey = pe.dt.year.values
        for key, msk in (("2002-2007", ey <= 2007), ("2008-2018", ey >= 2008)):
            ws = w[msk]
            add(f"gate split {k} {key} (execution years) G1", sp[key]["G1_bias_annual"], abs(((ws - ws.mean()) * g[msk]).mean()) * 12, 1e-14)
    add("mean(g) x 12", gate["gate_by_trial"]["T1"]["mean_g_annual"], g.mean() * 12, 1e-14)
    add("corr(g, x_ETF)", gate["gate_by_trial"]["T1"]["corr_g_x_etf"], np.corrcoef(g, xetf)[0, 1], 1e-12)
    s6 = pd.read_csv(S006 / "results/history/monthly_base.csv").set_index("month")
    ov = gate["overlap_with_006_007"]["by_trial"]
    for k in TRIALS:
        ms = hm.values[res["base"][k]["sel"]]
        wk = W[k].loc[ms].values
        add(f"overlap corr(w_{k}, 007 w_T1)", ov[k]["corr_with_007_T1_weight"],
            np.corrcoef(wk, s7.set_index("month").loc[ms, "w_T1"].values)[0, 1], 1e-12)
        add(f"overlap corr(w_{k}, 1[006 T1 in IEF])", ov[k]["corr_with_006_T1_in_leg"],
            np.corrcoef(wk, (s6.loc[ms, "T1_holding"] == "IEF").astype(float).values)[0, 1], 1e-12)
    add("overlap flag for T1 (> 0.8)", str(gate["overlap_with_006_007"]["flagged_studies_for_T1"]),
        str([s for s, c in (("007", ov["T1"]["corr_with_007_T1_weight"]), ("006", ov["T1"]["corr_with_006_T1_in_leg"])) if abs(c) > 0.8]))

    # ------------------------------------------------------------- volatility check
    add("volcheck sigma over 534 periods (rebuilt legs)", volc["sigma_annual"], vol(rl - rc), 1e-12)
    add("volcheck sigma = Study 007 committed figure", json.loads((S007 / "results/volcheck/volcheck.json").read_text())["sigma_annual"],
        volc["sigma_annual"], 1e-12)
    add("volcheck MDE = 2% sigma / 10.18%", volc["mde_annual"], 0.02 * sigma / 0.1018, 1e-14)
    add("sigma <= 10.18% (no 'consistent' row)", summ["low_power_check"], bool(sigma > 0.1018))

    # ------------------------------------------------------------- (e) episode
    ea = ep[("actual", "base")]
    eexe, eend = pd.to_datetime(ea["execution_date"]), pd.to_datetime(ea["period_end"])
    em_ = ea["month"].astype(str)
    add("episode periods / first / last", "93/2018-12/2026-08", f"{len(ea)}/{em_.iloc[0]}/{em_.iloc[-1]}")
    series_row("episode actual B1 = Alpaca IEF close returns", ea["B1"], pret(al["IEF"], eexe, eend), 1e-13)
    series_row("episode actual B0 = Alpaca BIL close returns", ea["B0"], pret(al["BIL"], eexe, eend), 1e-13)
    es = ep[("synthetic", "base")]
    series_row("episode synthetic B1 / B0 rebuilt from FRED", np.r_[es["B1"].values, es["B0"].values],
               np.r_[pret(leg, eexe, eend), pret(cash, eexe, eend)], 1e-13)
    for k in TRIALS:
        wsig = W[k].loc[em_].values
        add(f"episode hold months {k} (signal weight undefined)", ",".join(epi["actual"]["hold_periods"][k]),
            ",".join(em_[np.isnan(wsig)]))
        held = ea[f"hold_{k}"].astype(str).values == "True"
        series_row(f"episode w_{k} on non-hold months (rank still expanding/trailing)", ea[f"w_{k}"].values[~held], wsig[~held], 1e-15)
        add(f"episode mean signal weight {k}", epi["actual"]["mean_signal_weight_in_episode"][k], np.nanmean(wsig), 1e-12)
    fw = epi["weights_at_last_signal_month_for_forward_record"]
    for k in TRIALS:
        add(f"forward start: {k} weight at 2026-09 (4 dp)", fw[k], round(W[k].loc["2026-09"], 4), 1e-12)
    add("forward start: r_CPIAUCNS at 2026-09", fw["r_CPIAUCNS"], R["CPIAUCNS"].loc["2026-09"], 1e-15)
    add("forward start: r_CPILFENS at 2026-09", fw["r_CPILFENS"], R["CPILFENS"].loc["2026-09"], 1e-15)
    add("forward start: defined real yields to 2026-09", fw["n_defined_CPIAUCNS"], int(R["CPIAUCNS"].notna().sum()), 0, "{:.0f}")
    add("rank history months at episode end", epi["rank_history_months_at_episode_end"], len(months), 0, "{:.0f}")
    epres = {}
    for side in ("actual", "synthetic"):
        for case, cost in COSTS.items():
            df = ep[(side, case)]
            B1, B0 = df["B1"].values, df["B0"].values
            for k in TRIALS:
                wb = summ["weight_b3"][k]
                t, tr, used = run_tilt(W[k].loc[em_].values, B1, B0, cost)
                b3 = run_static(wb, B1, B0, cost)
                series_row(f"episode {side} {case} {k}, B3_{k} and held weight", np.r_[df[k].values, df[f"B3_{k}"].values, df[f"w_{k}"].values],
                           np.r_[t, b3, used], 1e-15)
                mu, se, tt = nw(t - b3)
                pub = epi[side]["cost_cases"][case]["inference"][k]["vs_B3"]["newey_west"]
                add(f"episode {side} {case} {k} NW t vs B3", pub["t"], tt, 1e-9)
                epres[(side, case, k)] = dict(T=t, B3=b3, B1=B1, B0=B0, w=used, d=mu, t=tt)
            series_row(f"episode {side} {case} B2", df["B2"], run_static(0.5, B1, B0, cost), 1e-15)
    emc = pd.read_csv(RES / "episode/actual/metrics_base.csv", index_col=0)
    for k in TRIALS:
        e = epres[("actual", "base", k)]
        m = metrics(e["T"], e["B0"])
        for key in ("ann_geometric_return", "ann_volatility", "sharpe_annual", "max_drawdown_monthly"):
            add(f"episode actual base {k} {key}", emc.loc[k, key], m[key], 1e-10)
        add(f"episode actual base {k} mean weight (incl. held drift)", emc.loc[k, "mean_weight"], e["w"].mean(), 1e-12)

    # ------------------------------------------------------------- (f) README and trial-log typed numbers
    b = res["base"]
    M = {k: metrics(b[k]["T"], b[k]["B0"]) for k in TRIALS}
    MB1 = {k: metrics(b[k]["B1"], b[k]["B0"]) for k in TRIALS}
    MB3 = {k: metrics(b[k]["B3"], b[k]["B0"]) for k in TRIALS}
    MB2 = metrics(b["T1"]["B2"], b["T1"]["B0"])
    T = {k: nw(b[k]["T"] - b[k]["B3"]) for k in TRIALS}
    TB1 = {k: nw(b[k]["T"] - b[k]["B1"]) for k in TRIALS}
    TS = {k: nw(res["stress"][k]["T"] - res["stress"][k]["B3"]) for k in TRIALS}
    DS = {k: {n: cb["deflated_sharpe"][k][f"N{n}"]["dsr"] for n in (17, 3, 10)} for k in TRIALS}
    for src in ("README", "trials.md"):
        typed("T1 Sharpe", 0.415, M["T1"]["sharpe_annual"], 3, src=src)
        typed("B1 Sharpe", 0.382, MB1["T1"]["sharpe_annual"], 3, src=src)
        typed("B3 Sharpe", 0.381, MB3["T1"]["sharpe_annual"], 3, src=src)
        typed("T1 mean d %/yr", 0.56, T["T1"][0] * 12, 2, 0.01, src=src)
        typed("T1 NW t", 1.38, T["T1"][2], 2, src=src)
        typed("T1a NW t", 1.78, T["T1a"][2], 2, src=src)
        typed("T1b NW t", 0.91, T["T1b"][2], 2, src=src)
        typed("era row %/yr", -0.06, d1[era].mean() * 12, 2, 0.01, src=src)
        typed("era row t", -0.18, nw(d1[era])[2], 2, src=src)
        typed("T1 stress t", 1.33, TS["T1"][2], 2, src=src)
        typed("corr(d T1, d 007 T1)", 0.193, np.corrcoef(d1, d7_)[0, 1], 3, src=src)
        typed("sd(w - wbar) T1", 0.270, np.std(w1, ddof=0), 3, src=src)
        typed("MDE t=2 %/yr", 0.82, 2 * T["T1"][1] * 12, 2, 0.01, src=src)
        typed("NW/iid T1", 1.095, cb["power_realised"]["T1"]["ratio"], 3, src=src)
        for k, v in (("T1", 0.70), ("T1a", 0.43), ("T1b", 0.87)):
            typed(f"Ledoit-Wolf p vs B3 {k}", v, cb["inference"][k]["vs_B3"]["ledoit_wolf"]["p_value"], 2, src=src)
        for k, v in (("T1", 23.8), ("T1a", 21.9), ("T1b", 32.7)):
            typed(f"turnover {k}", v, b[k]["traded"].sum(), 1, src=src)
        for k, v in (("T1", 0.988), ):
            typed("T1 DSR 17", v, DS["T1"][17], 3, src=src)
        typed("T1 DSR 3", 0.996, DS["T1"][3], 3, src=src)
        typed("T1 DSR 10", 0.991, DS["T1"][10], 3, src=src)
        for q, v in (("Q1", 0.84), ("Q2", 1.27), ("Q3", 2.08), ("Q4", 3.83), ("Q5", 6.88)):
            typed(f"mechanism {q} %/yr", v, xs[grp == q].mean() * 12, 2, 0.01, src=src)
    typed("T1a Sharpe", 0.448, M["T1a"]["sharpe_annual"], 3, src="trials.md")
    typed("T1a mean d %/yr", 0.72, T["T1a"][0] * 12, 2, 0.01, src="trials.md")
    typed("T1b Sharpe", 0.388, M["T1b"]["sharpe_annual"], 3, src="trials.md")
    typed("T1b B1 Sharpe", 0.406, MB1["T1b"]["sharpe_annual"], 3, src="trials.md")
    typed("T1b B3 Sharpe", 0.405, MB3["T1b"]["sharpe_annual"], 3, src="trials.md")
    typed("T1b mean d %/yr", 0.44, T["T1b"][0] * 12, 2, 0.01, src="trials.md")
    typed("w-bar T1", 0.4662, b["T1"]["wb"], 4, src="trials.md")
    for nm, (a, z), dv, tv in (("1974-81", ERAS["1974-07 to 1981-12"], 1.14, 1.16), ("1982-2008", ERAS["1982-01 to 2008-12"], 0.87, 1.54),
                               ("2009-18", ERAS["2009-01 to 2018-12"], -0.68, -1.20)):
        msk = (exm >= pd.Period(a, "M")) & (exm <= pd.Period(z, "M"))
        typed(f"rate era {nm} T1-B3 %/yr", dv, d1[msk].mean() * 12, 2, 0.01, src="trials.md")
        typed(f"rate era {nm} t", tv, nw(d1[msk])[2], 2, src="trials.md")
    # README results table
    for k, v in (("T1", (534, 6.66, 4.85, 0.415, -6.3, 0.56, 1.38, -1.03, -1.53, 1.33, 0.466)),
                 ("T1a", (534, 6.77, 4.72, 0.448, -6.4, 0.72, 1.78, -0.93, -1.38, 1.73, 0.448)),
                 ("T1b", (474, 6.21, 4.67, 0.388, -6.2, 0.44, 0.91, -1.53, -1.82, 0.85, 0.401))):
        add(f"[README] table {k} months", v[0], len(b[k]["T"]), 0, "{:.0f}")
        typed(f"table {k} annual return %", v[1], M[k]["ann_geometric_return"], 2, 0.01)
        typed(f"table {k} volatility %", v[2], M[k]["ann_volatility"], 2, 0.01)
        typed(f"table {k} Sharpe", v[3], M[k]["sharpe_annual"], 3)
        typed(f"table {k} drawdown %", v[4], M[k]["max_drawdown_monthly"], 1, 0.01)
        typed(f"table {k} mean d %/yr", v[5], T[k][0] * 12, 2, 0.01)
        typed(f"table {k} NW t vs B3", v[6], T[k][2], 2)
        typed(f"table {k} mean d vs B1 %/yr", v[7], TB1[k][0] * 12, 2, 0.01)
        typed(f"table {k} NW t vs B1", v[8], TB1[k][2], 2)
        typed(f"table {k} stress t", v[9], TS[k][2], 2)
        typed(f"table {k} B3 weight", v[10], b[k]["wb"], 3)
    for k, v in (("T1a", (0.994, 0.998, 0.996)), ("T1b", (0.976, 0.989, 0.980))):
        for n, val in zip((17, 3, 10), v):
            typed(f"table {k} DSR N={n}", val, DS[k][n], 3)
    for k, s1, s3 in (("T1", 0.382, 0.381), ("T1a", 0.382, 0.381), ("T1b", 0.406, 0.405)):
        typed(f"table {k} same-window B1 Sharpe", s1, MB1[k]["sharpe_annual"], 3)
        typed(f"table {k} same-window B3 Sharpe", s3, MB3[k]["sharpe_annual"], 3)
    for nm, met, val, dec in (("B1 annual return %", MB1["T1"]["ann_geometric_return"], 7.56, 2), ("B3 annual return %", MB3["T1"]["ann_geometric_return"], 6.11, 2),
                              ("B2 annual return %", MB2["ann_geometric_return"], 6.21, 2), ("B1 vol %", MB1["T1"]["ann_volatility"], 7.82, 2),
                              ("B3 vol %", MB3["T1"]["ann_volatility"], 3.73, 2), ("B2 vol %", MB2["ann_volatility"], 3.99, 2),
                              ("B1 drawdown %", MB1["T1"]["max_drawdown_monthly"], -15.2, 1), ("B3 drawdown %", MB3["T1"]["max_drawdown_monthly"], -3.8, 1),
                              ("B2 drawdown %", MB2["max_drawdown_monthly"], -4.3, 1)):
        typed(nm, val, met, dec, 0.01)
    typed("B2 Sharpe", 0.381, MB2["sharpe_annual"], 3)
    inf1 = cb["inference"]["T1"]
    typed("T1 bootstrap CI low", 0.14, inf1["sharpe_ci"]["ci_low"], 2)
    typed("T1 bootstrap CI high", 0.68, inf1["sharpe_ci"]["ci_high"], 2)
    for k in TRIALS:
        add(f"[README] {k} criteria C1/C2/C3/C4 = fail/fail/pass/pass", "False/False/True/True",
            "/".join(str(bool(crit[k][c])) for c in ("C1", "C2", "C3", "C4")))
    add("[README] era months", 396, int(era.sum()), 0, "{:.0f}")
    add("[README] months before 2003 (of 534)", 342, int((exm < pd.Period("2003-01", "M")).sum()), 0, "{:.0f}")
    # sub-window table
    swt = [("1974-07 to 2002-12", 342, 0.468, 0.333, 0.332, 1.36, 2.47, 0.584),
           ("2003-01 to 2018-12", 192, 0.346, 0.499, 0.499, -0.85, -1.81, 0.257),
           ("1974-07 to 1985-12", 138, 0.401, 0.113, 0.112, 2.34, 1.92, 0.581),
           ("1974-07 to 1981-12", 90, -0.099, -0.364, -0.365, 1.14, 1.16, 0.385),
           ("1982-01 to 2008-12", 324, 0.600, 0.629, 0.629, 0.87, 1.54, 0.563),
           ("2009-01 to 2018-12", 120, 0.289, 0.452, 0.452, -0.68, -1.20, 0.267)]
    for nm, n, s1, sb1, sb3, dd, tt, mw in swt:
        a, z = nm.split(" to ")
        msk = (exm >= pd.Period(a, "M")) & (exm <= pd.Period(z, "M"))
        add(f"[README] window {nm} months", n, int(msk.sum()), 0, "{:.0f}")
        typed(f"window {nm} T1 Sharpe", s1, metrics(b["T1"]["T"][msk], b["T1"]["B0"][msk])["sharpe_annual"], 3)
        typed(f"window {nm} B1 Sharpe", sb1, metrics(b["T1"]["B1"][msk], b["T1"]["B0"][msk])["sharpe_annual"], 3)
        typed(f"window {nm} B3 Sharpe", sb3, metrics(b["T1"]["B3"][msk], b["T1"]["B0"][msk])["sharpe_annual"], 3)
        typed(f"window {nm} T1-B3 %/yr", dd, d1[msk].mean() * 12, 2, 0.01)
        typed(f"window {nm} T1-B3 t", tt, nw(d1[msk])[2], 2)
        typed(f"window {nm} T1 mean weight", mw, w1[msk].mean(), 3)
    msk = exm >= pd.Period("2003-01", "M")
    typed("after 2002 mean weight 0.26", 0.26, w1[msk].mean(), 2)
    for q, lo_, hi_, n, ex, hr in (("Q1", 0.000, 0.190, 107, 0.84, 50.5), ("Q2", 0.190, 0.349, 107, 1.27, 54.2),
                                   ("Q3", 0.353, 0.556, 106, 2.08, 53.8), ("Q4", 0.558, 0.702, 107, 3.83, 58.9),
                                   ("Q5", 0.702, 1.000, 107, 6.88, 53.3)):
        sel = grp == q
        add(f"[README] mechanism {q} months", n, int(sel.sum()), 0, "{:.0f}")
        typed(f"mechanism {q} weight min", lo_, w1[sel].min(), 3)
        typed(f"mechanism {q} weight max", hi_, w1[sel].max(), 3)
        typed(f"mechanism {q} leg beat bills %", hr, (xs[sel] > 0).mean(), 1, 0.01)
    typed("r <= 0 leg excess %/yr", 1.30, xs[rneg].mean() * 12, 2, 0.01)
    typed("r > 0 leg excess %/yr", 3.26, xs[~rneg].mean() * 12, 2, 0.01)
    add("[README] r <= 0 / r > 0 months", "76/458", f"{int(rneg.sum())}/{int((~rneg).sum())}")
    typed("1/sqrt(12)", 0.289, 1 / SQ12, 3)
    typed("MDE 80% power %/yr", 1.16, 2.842 * T["T1"][1] * 12, 2, 0.01)
    typed("volcheck MDE %/yr ('about 1.5')", 1.5, 0.02 * sigma / 0.1018, 1, 0.01)
    typed("sigma %", 7.81, sigma, 2, 0.01)
    typed("sigma % (4 dp)", 7.8124, sigma, 4, 0.01, src="trials.md")
    typed("volcheck MDE %/yr", 1.53, 0.02 * sigma / 0.1018, 2, 0.01, src="trials.md")
    # gate typed
    for k, v, wo, to in (("T1", 0.021, 0.257, 8.99), ("T1a", 0.024, 0.228, 6.44), ("T1b", 0.062, 0.326, 14.69)):
        typed(f"G1 {k} %/yr", v, gate["gate_by_trial"][k]["G1_bias_annual"], 3, 0.01)
        typed(f"gate overlap mean w {k}", wo, gate["gate_by_trial"][k]["w_o"], 3, src="trials.md")
        typed(f"gate overlap turnover {k}", to, gate["gate_by_trial"][k]["turnover_one_way"], 2, src="trials.md")
    typed("G2", 0.131, G2, 3)
    typed("G2 (6 dp)", 0.131409, G2, 6, src="trials.md")
    for k, a, z in (("T1", 0.115, 0.161), ("T1a", -0.014, 0.115), ("T1b", 0.085, 0.088)):
        typed(f"overlap corr {k} vs 007", a, ov[k]["corr_with_007_T1_weight"], 3)
        typed(f"overlap corr {k} vs 006", z, ov[k]["corr_with_006_T1_in_leg"], 3)
    add("[README] ALFRED vintages read", "1,045", f"{(acm.outcome == '200').sum():,}")
    # episode typed
    E = {k: epres[("actual", "base", k)] for k in TRIALS}
    ME = {k: metrics(E[k]["T"], E[k]["B0"]) for k in TRIALS}
    MEB1, MEB3 = metrics(E["T1"]["B1"], E["T1"]["B0"]), metrics(E["T1"]["B3"], E["T1"]["B0"])
    for k, v in (("T1", (0.218, 2.53, 1.80, -1.5, 0.78, 0.85)), ("T1a", (0.167, 2.53, 1.45, -1.8, 0.74, 0.77)),
                 ("T1b", (0.446, 2.15, 3.76, -4.5, 0.34, 0.40))):
        typed(f"episode {k} mean weight (monthly w column, held drift included)", v[0], E[k]["w"].mean(), 3)
        add(f"[README] episode {k} mean weight, signal months only (hold excluded)", None, float(np.nanmean(W[k].loc[em_].values)), fmt="{:.4f}")
        typed(f"episode {k} annual return %", v[1], ME[k]["ann_geometric_return"], 2, 0.01)
        typed(f"episode {k} volatility %", v[2], ME[k]["ann_volatility"], 2, 0.01)
        typed(f"episode {k} drawdown %", v[3], ME[k]["max_drawdown_monthly"], 1, 0.01)
        typed(f"episode {k} mean T - B3 %/yr", v[4], E[k]["d"] * 12, 2, 0.01)
        typed(f"episode {k} NW t vs B3", v[5], E[k]["t"], 2)
    for src in ("README", "trials.md"):
        typed("episode T1 mean weight", 0.218, E["T1"]["w"].mean(), 3, src=src)
        typed("episode B1 annual return %", 0.45, MEB1["ann_geometric_return"], 2, 0.01, src=src)
        typed("episode B3 annual return %", 1.69, MEB3["ann_geometric_return"], 2, 0.01, src=src)
        typed("episode bills annual return %", 2.66, geo(E["T1"]["B0"]), 2, 0.01, src=src)
        typed("episode B1 drawdown %", -22.2, MEB1["max_drawdown_monthly"], 1, 0.01, src=src)
        typed("episode B3 drawdown %", -10.1, MEB3["max_drawdown_monthly"], 1, 0.01, src=src)
        typed("episode T1 Sharpe", -0.065, ME["T1"]["sharpe_annual"], 3, src=src)
        typed("episode B1 Sharpe", -0.259, MEB1["sharpe_annual"], 3, src=src)
        typed("episode B3 Sharpe", -0.259, MEB3["sharpe_annual"], 3, src=src)
        typed("episode T1 synthetic t", 0.84, epres[("synthetic", "base", "T1")]["t"], 2, src=src)
    typed("episode B1 vol %", 7.39, MEB1["ann_volatility"], 2, 0.01)
    typed("episode B3 vol %", 3.49, MEB3["ann_volatility"], 2, 0.01)
    typed("episode bills vol %", 0.59, vol(E["T1"]["B0"]), 2, 0.01)
    typed("episode bills drawdown %", -0.2, mdd(E["T1"]["B0"]), 1, 0.01)
    typed("episode T1 t vs B1", 0.82, nw(E["T1"]["T"] - E["T1"]["B1"])[2], 2, src="trials.md")
    typed("episode T1 stress t", 0.83, epres[("actual", "stress", "T1")]["t"], 2, src="trials.md")
    for k, v in (("T1a", (0.74, 0.77)), ("T1b", (0.34, 0.40))):
        typed(f"episode {k} mean d %/yr", v[0], E[k]["d"] * 12, 2, 0.01, src="trials.md")
        typed(f"episode {k} t", v[1], E[k]["t"], 2, src="trials.md")
    for k, v4, v3 in (("T1", 0.5241, 0.524), ("T1a", 0.6540, 0.654), ("T1b", 0.9916, 0.992)):
        typed(f"forward start {k} weight", v3, W[k].loc["2026-09"], 3)
        typed(f"forward start {k} weight (4 dp)", v4, W[k].loc["2026-09"], 4, src="trials.md")
    for k, v in (("T1", 0.466), ("T1a", 0.448), ("T1b", 0.401)):
        typed(f"episode pre-run row frozen B3 weight {k}", v, summ["weight_b3"][k], 3, src="trials.md")
    # weight by execution year (README: computed from actual/monthly_base.csv, column w_T1)
    ey = eexe.dt.year.values
    wcol = ea["w_T1"].values
    for yr, v in ((2019, 0.19), (2020, 0.12), (2021, 0.06), (2022, 0.01), (2023, 0.20), (2024, 0.38), (2025, 0.45), (2026, 0.39)):
        typed(f"episode T1 mean weight in execution year {yr}", v, wcol[ey == yr].mean(), 2)
    typed("episode T1 max weight in execution year 2022", 0.033, wcol[ey == 2022].max(), 3)
    add("[README] episode hold period", "2025-11", ",".join(em_[ea["hold_T1"].astype(str) == "True"]))

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
    seq = ["1d1daeb", "ca2432a", "be162c1", "d76c22a", "ac42f2d", "245613c", "dcf5cd1", "0dec256", "2c76deb", "d8b29f6",
           "67efe67", "fc250a5", "cf5b64f", "7d7dc03", "e9169dd", "172c456", "fe94ff7", "2902e22", "031c134", "ef7f4bd",
           "b111b0e", "798d487", "a90f048", "ebc80e1", "eb39f49", "cea7187", "b13efd2"]
    t = {c: ctime(c) for c in seq}
    if any(v is None for v in t.values()):
        add("git chain", True, False, note="git not available; not checked")
        return
    add(f"commit chain of {len(seq)} commits strictly increasing in committer time", True, all(t[a] < t[b] for a, b in zip(seq, seq[1:])))
    ds = json.loads((RES / "data_step.json").read_text()).get("run_at_utc")
    vc = json.loads((RES / "vintage_check.json").read_text())
    for name, run, before, after, code in (
            ("data step (2nd attempt)", ds, "ca2432a", "be162c1", None),
            ("vintage check (2nd attempt; start)", vc["started_utc"], "ac42f2d", "245613c", None),
            ("gate", gate["run_at_utc"], "e9169dd", "172c456", gate.get("code_commit") or gate.get("provenance", {}).get("git_commit")),
            ("volcheck", volc["run_at_utc"], "fe94ff7", "2902e22", volc["code_commit"]),
            ("history", summ["run_at_utc"], "031c134", "ef7f4bd", summ["provenance"]["git_commit"]),
            ("episode", epi["run_at_utc"], "ebc80e1", "eb39f49", epi["provenance"].get("git_commit"))):
        r = pd.Timestamp(run)
        add(f"{name} run {run} after rule/row commit {before} ({t[before].strftime('%H:%M:%S')}) and before output commit "
            f"{after} ({t[after].strftime('%H:%M:%S')})", True, bool(t[before] < r < t[after]))
        if code:
            add(f"{name} code commit = governing commit {before}", True, code.startswith(before))
    add("§16 (a)/(b) clarifications dcf5cd1 after vintage outputs 245613c and before code 0dec256", True,
        t["245613c"] < t["dcf5cd1"] < t["0dec256"])
    add("note a90f048 before episode row ebc80e1", True, t["a90f048"] < t["ebc80e1"])
    for f, c in (("results/gate", "172c456"), ("results/volcheck", "2902e22"), ("results/history", "ef7f4bd"),
                 ("results/episode", "eb39f49"), ("results/cpi_availability.csv", "245613c")):
        out = subprocess.run(["git", "log", "--format=%h", "--", f], cwd=STUDY, capture_output=True, text=True).stdout.split()
        add(f"{f} committed once ({c})", c, ",".join(out))
    for a, z in (("7d7dc03", "ef7f4bd"), ("ef7f4bd", "eb39f49")):
        for f in ("src", "tests", "reproduce.sh"):
            out = subprocess.run(["git", "diff", "-U0", a, z, "--", f], cwd=STUDY, capture_output=True, text=True).stdout
            code = [ln for ln in out.splitlines() if ln[:1] in "+-" and ln[:3] not in ("+++", "---") and not ln[1:].lstrip().startswith("#")]
            add(f"{f}: non-comment lines changed {a}..{z}", 0, len(code), 0, "{:.0f}")
    for f in ("PREREGISTRATION.md", "trials.md", "QUESTION.md"):
        out = subprocess.run(["git", "diff", "ca2432a", "HEAD", "--", f], cwd=STUDY, capture_output=True, text=True).stdout
        removed = [ln for ln in out.splitlines() if ln.startswith("-") and not ln.startswith("---")]
        add(f"{f} since ca2432a: lines removed", 0, len(removed), 0, "{:.0f}")
    add("§16 series-ID amendment and data-step pre-run row: commit time (data step ran 17:25:07Z)", None,
        t["be162c1"].strftime("%H:%M:%S"))


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
