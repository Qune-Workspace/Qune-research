"""Separate-session recomputation for REVIEW.md (Study 010, time-series factor
momentum on four US equity factors, 1927-2026).

Written by the reviewer (Tester, a separate agent session that did not write
the code, the pre-registration or the note), adapted in structure from Study
008's review script.  It imports nothing from the study's ``src/`` or from
``qune_research``: every number is re-derived with numpy, pandas and scipy
only, from

  * the three raw zips in ``data/raw/`` (git-ignored; present on disk at review
    time), hash-checked against ``results/data_manifest.json``;
  * the committed outputs under ``results/`` and the numbers typed in
    trials.md (data-step, re-count and history outcome rows) and README.md.

Conventions taken from the code, not chosen here: formation by the product of
(1 + f/100) over t-L..t-1 in date order; tie |R| <= 1e-12 -> -1; timing cost
c * (1/K_t) * sum_k 2|h_k,t - h_k,t-1| with h = 0 before a factor's first held
month (so 2c/K_t on entry, 4c/K_t per flip); h-bar the unweighted mean over a
factor's held months in H; Newey-West Bartlett 6 lags without small-sample
correction; DSR variance = population variance (ddof 0) of the three trials'
monthly Sharpe ratios of T at the same cost case, floored at (0.05/sqrt 12)^2;
bootstrap draws in the committed order (per cost case a fresh
default_rng(20261021); per trial: stationary-bootstrap CI of T, of B1, of B3,
then Ledoit-Wolf vs B1, vs B3).

Run from the study folder:  ../../.venv/bin/python review_recompute.py
Prints one row per check; exit status 1 if any row mismatches.  Nothing is
written to disk.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
RES = STUDY / "results"
RAW = STUDY / "data" / "raw"
SQ12 = math.sqrt(12.0)
LAGS = 6
COSTS = {"base": 0.10, "stress": 0.50}
SEED, NRES, BLOCK = 20261021, 10_000, 12
FLOOR = (0.05 / SQ12) ** 2
TIE = 1e-12
FACTORS = ["SMB", "HML", "ST_Rev", "LT_Rev"]
TRIALS = {
    "T1": (12, {"SMB": "1927-07", "HML": "1927-07", "ST_Rev": "1927-07", "LT_Rev": "1932-01"}),
    "T1a": (12, {"SMB": "1927-07", "HML": "1927-07"}),
    "T1b": (6, {"SMB": "1927-07", "HML": "1927-07", "ST_Rev": "1927-07", "LT_Rev": "1931-07"}),
}
FILES = {"F-F_Research_Data_Factors_CSV.zip": ["SMB", "HML"], "F-F_ST_Reversal_Factor_CSV.zip": ["ST_Rev"],
         "F-F_LT_Reversal_Factor_CSV.zip": ["LT_Rev"]}
WIN = {"P1": [("1927-07", "1963-06")], "L": [("1963-07", "2015-12")], "P2": [("2016-01", "2026-08")],
       "P": [("1927-07", "1963-06"), ("2016-01", "2026-08")]}
EPIS = {"1929-09 to 1932-12": ("1929-09", "1932-12"), "2008-09 to 2009-12": ("2008-09", "2009-12")}

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
    rel = max(1.0, abs(p))
    ok = abs(p - r) <= tol * rel
    rows.append((claim, fmt.format(p), fmt.format(r), ("yes" if ok else "NO") + sfx))


def typed(claim, value, rec, dec, src="trials.md"):
    """A number printed with ``dec`` decimals (rounding tolerance)."""
    ok = abs(float(value) - float(rec)) <= 0.5 * 10 ** (-dec) + 1e-9
    rows.append((f"[{src}] {claim}", f"{value:.{dec}f}", f"{rec:.{dec + 3}f}", "yes" if ok else "NO"))


def series_row(claim, pub, rec, tol=1e-12):
    a, b = np.asarray(pub, float), np.asarray(rec, float)
    if a.shape != b.shape or not np.array_equal(np.isnan(a), np.isnan(b)):
        md = float("inf")
    else:
        dd = np.abs(a - b)
        dd[np.isnan(a)] = 0.0
        md = float(dd.max()) if len(dd) else 0.0
    rows.append((claim + " (max abs diff)", "0", f"{md:.2e}", "yes" if md <= tol else "NO"))


# ----------------------------------------------------------------------------- statistics
def srm(x):
    x = np.asarray(x, float)
    return float(x.mean() / x.std(ddof=1))


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


def drow(d):
    d = np.asarray(d, float)
    m, se, t = nw(d)
    sd = d.std(ddof=1)
    return {"months": len(d), "mean_pct_a_year": m * 12, "nw_t": t, "nw_se_pct_a_year": se * 12,
            "iid_t": m / (sd / math.sqrt(len(d))), "sharpe_annual": m / sd * SQ12}


def smetrics(r):
    x = np.asarray(r, float) / 100
    lv = np.cumprod(1 + x)
    sk, ku = skku(x)
    return {"months": len(x), "mean_pct_a_year": float(np.mean(r) * 12),
            "geometric_pct_a_year": (float(np.prod(1 + x)) ** (12 / len(x)) - 1) * 100,
            "vol_pct_a_year": float(x.std(ddof=1) * SQ12 * 100), "sharpe_annual": srm(x) * SQ12,
            "sharpe_monthly": srm(x), "max_drawdown": float(np.min(lv / np.maximum.accumulate(lv) - 1)),
            "positive_month_share": float((x > 0).mean()), "skewness": sk, "kurtosis_non_excess": ku,
            "excess_kurtosis": ku - 3}


def dsr(sr, n, sk, ku, ntr, var):
    g = 0.5772156649015329
    srs = math.sqrt(var) * ((1 - g) * norm.ppf(1 - 1 / ntr) + g * norm.ppf(1 - 1 / (ntr * math.e)))
    den = math.sqrt(1 - sk * sr + (ku - 1) / 4 * sr ** 2)
    return {"sr_star_monthly": srs, "psr": float(norm.cdf(sr * math.sqrt(n - 1) / den)),
            "dsr": float(norm.cdf((sr - srs) * math.sqrt(n - 1) / den))}


def sb_ci(x, rng):
    n = len(x)
    restart = rng.random(size=(NRES, n)) < 1 / BLOCK
    fresh = rng.integers(0, n, size=(NRES, n))
    idx = np.empty((NRES, n), dtype=np.int64)
    idx[:, 0] = fresh[:, 0]
    for t in range(1, n):
        idx[:, t] = np.where(restart[:, t], fresh[:, t], (idx[:, t - 1] + 1) % n)
    s = np.asarray(x, float)[idx]
    sr = s.mean(axis=1) / s.std(axis=1, ddof=1) * SQ12
    return np.quantile(sr, [0.025, 0.975])


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
    n = len(x1)
    d0, s0 = lw_core(x1[None], x2[None])
    t0 = float(d0[0] / s0[0])
    nb = -(-n // BLOCK)
    st = rng.integers(0, n, size=(NRES, nb))
    idx = ((st[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(NRES, -1)[:, :n]) % n
    ext = 0
    for s in range(0, NRES, 500):
        b = idx[s:s + 500]
        d, se = lw_core(x1[b], x2[b])
        ext += int((np.abs((d - d0[0]) / se) >= abs(t0)).sum())
    return float(d0[0]) * SQ12, ext / NRES


# ----------------------------------------------------------------------------- data and engine
def sha(b):
    return hashlib.sha256(b).hexdigest()


def parse_monthly(text):
    """Own parser: the first block of lines whose first field is six digits, header the line above."""
    lines = text.splitlines()
    out, cols, started = {}, None, False
    for i, ln in enumerate(lines):
        f = [x.strip() for x in ln.split(",")]
        if re.fullmatch(r"\d{6}", f[0]):
            if not started:
                cols = [c.strip() for c in lines[i - 1].split(",")[1:]]
                started = True
            out[f"{f[0][:4]}-{f[0][4:]}"] = [float(v) for v in f[1:]]
        elif started:
            break
    return pd.DataFrame.from_dict(out, orient="index", columns=cols)


def months(a, b):
    return [str(p) for p in pd.period_range(a, b, freq="M")]


def engine(F, trial, cost):
    L, entry = TRIALS[trial]
    H = months("1927-07", "2026-08")
    allm = list(F.index)
    pos = {m: i for i, m in enumerate(allm)}
    h = pd.DataFrame(np.nan, index=H, columns=list(entry))
    ties = {}
    for k, e in entry.items():
        v = F[k].to_numpy()
        ties[k] = 0
        for m in H:
            if m < e:
                continue
            i = pos[m]
            w = v[i - L:i]
            assert i - L >= 0 and not np.isnan(w).any(), (trial, k, m)
            R = float(np.prod(1 + w / 100) - 1)
            h.loc[m, k] = 1.0 if R > TIE else -1.0
            ties[k] += int(abs(R) <= TIE)
    fh = F.loc[H, list(entry)]
    held = h.notna()
    K = held.sum(axis=1).astype(float)
    tg = (h.fillna(0) * fh.fillna(0)).sum(axis=1) / K
    prev = h.shift(1).fillna(0.0)
    traded = (2 * (h - prev).abs()).where(held, 0.0).sum(axis=1) / K
    hbar = h.mean(axis=0)
    b3 = (fh * hbar).where(held, 0.0).sum(axis=1) / K
    b1 = fh.where(held, 0.0).sum(axis=1) / K
    T = tg - cost * traded
    fr = pd.DataFrame({"T_gross": tg, "cost": cost * traded, "T": T, "B1": b1, "B3": b3, "d": T - b3, "K": K})
    return fr, h, hbar, ties, fh


def sl(s, spans):
    return pd.concat([s[(s.index >= a) & (s.index <= b)] for a, b in spans])


def git(*a):
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, check=True).stdout


def cmp_dict(prefix, pub, rec, tol=1e-9):
    for k, v in rec.items():
        if isinstance(v, dict):
            cmp_dict(f"{prefix}.{k}", pub[k], v, tol)
        else:
            add(f"{prefix}.{k}", pub[k], v, tol)


def main() -> int:
    man = json.loads((RES / "data_manifest.json").read_text())["files"]
    step = json.loads((RES / "data_step.json").read_text())
    summ = json.loads((RES / "history" / "summary.json").read_text().replace("NaN", "null"))
    hist = {c: pd.read_csv(RES / "history" / f"monthly_{c}.csv", index_col=0, float_precision="round_trip") for c in COSTS}
    trials_md = (STUDY / "trials.md").read_text()
    readme = (STUDY / "README.md").read_text() if (STUDY / "README.md").exists() else None

    # (e) hashes; (a) parse
    parts = []
    for name, cols in FILES.items():
        p = RAW / name
        if not p.exists():
            print(f"raw file {name} missing: hash and recompute rows skipped")
            return 2
        b = p.read_bytes()
        add(f"sha256 {name} = manifest", man[name]["sha256"], sha(b))
        add(f"bytes {name} = manifest", man[name]["bytes"], len(b), 0)
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            mem = [n for n in z.namelist() if not n.endswith("/")]
            add(f"zip {name}: one member = manifest csv_member", man[name]["csv_member"], ",".join(mem))
            cb = z.read(mem[0])
        add(f"csv sha256 {name} = manifest", man[name]["csv_sha256"], sha(cb))
        add(f"csv bytes {name} = manifest", man[name]["csv_bytes"], len(cb), 0)
        txt = cb.decode("latin-1")
        add(f"header release line {name} names 202608", True, "202608 CRSP database" in txt)
        mf = parse_monthly(txt)
        st = step["files"][name]
        add(f"{name} first month = data_step", st["first_month"], mf.index[0])
        add(f"{name} last month = data_step", st["last_month"], mf.index[-1])
        add(f"{name} rows = data_step", st["rows"], len(mf), 0)
        add(f"{name} no month gap", True, list(mf.index) == months(mf.index[0], mf.index[-1]))
        add(f"{name} no -99.99/-999 marker", True, not mf.isin([-99.99, -999.0]).any().any())
        parts.append(mf[cols])
    F = pd.concat(parts, axis=1).sort_index()
    F = F.reindex(months(F.index[0], F.index[-1]))
    H = months("1927-07", "2026-08")
    hb = hist["base"]
    add("H months = monthly_base rows", 1190, len(hb), 0)
    add("H index = 1927-07..2026-08", True, list(hb.index) == H)
    for k in FACTORS:
        series_row(f"factor {k} in monthly csv = raw", hb[f"f_{k}"], F.loc[H, k], 0)
    for w, n in {"P1": 432, "L": 630, "P2": 128, "P": 560}.items():
        add(f"months {w}", n, sum(len(months(a, b)) for a, b in WIN[w]), 0)

    # (b) engine, (c)-(d) statistics
    rec = {}
    for case, c in COSTS.items():
        hc = hist[case]
        rng = np.random.default_rng(SEED)
        res = {t: engine(F, t, c) for t in TRIALS}
        srs = [srm(res[t][0]["T"] / 100) for t in TRIALS]
        var = float(np.var(srs, ddof=0))
        floored = var < FLOOR
        var = FLOOR if floored else var
        blk = summ["cost_cases"][case]
        add(f"{case} DSR variance across trials (ddof 0)", blk["variance_across_trials"], var)
        add(f"{case} floor applied", blk["floor_applied"], floored)
        rec[case] = {}
        for t in TRIALS:
            fr, h, hbar, ties, fh = res[t]
            for col in ["T_gross", "cost", "T", "B1", "B3", "d", "K"]:
                series_row(f"{case} {t} {col}", hc[f"{t}_{col}"], fr[col], 1e-12)
            for k in h:
                series_row(f"{case} {t} h_{k}", hc[f"{t}_h_{k}"], h[k], 0)
            pub = blk["trials"][t]
            m = {"T": smetrics(fr["T"]), "T_gross": smetrics(fr["T_gross"]), "B1": smetrics(fr["B1"]),
                 "B3": smetrics(fr["B3"]), "d": drow(fr["d"]), "T_minus_B1": drow(fr["T"] - fr["B1"]),
                 "cost_pct_a_year": float(fr["cost"].mean() * 12)}
            add(f"{case} {t} B3 identically zero", pub["B3_identically_zero"], bool((hbar == 0).all()))
            cmp_dict(f"{case} {t}", pub, m)
            # bootstrap CIs and Ledoit-Wolf in the committed draw order
            for s in ("T", "B1", "B3"):
                lo, hi = sb_ci(fr[s].to_numpy() / 100, rng)
                add(f"{case} {t} {s} Sharpe CI low", pub[s]["sharpe_ci"]["ci_low"], lo, 1e-9)
                add(f"{case} {t} {s} Sharpe CI high", pub[s]["sharpe_ci"]["ci_high"], hi, 1e-9)
            for s in ("B1", "B3"):
                da, pv = lw_p(fr["T"].to_numpy() / 100, fr[s].to_numpy() / 100, rng)
                add(f"{case} {t} LW diff_annual vs {s}", pub[f"sharpe_test_vs_{s}"]["diff_annual"], da, 1e-9)
                add(f"{case} {t} LW p vs {s}", pub[f"sharpe_test_vs_{s}"]["p_value"], pv, 0)
            x = fr["T"].to_numpy() / 100
            sk, ku = skku(x)
            for n in (3, 10, 31, 595):
                cmp_dict(f"{case} {t} DSR N{n}", pub["dsr"][f"N{n}"], dsr(srm(x), len(x), sk, ku, n, var))
            for w, spans in WIN.items():
                cmp_dict(f"{case} {t} window {w}", pub["windows"][w], drow(sl(fr["d"], spans)))
            prev = h.shift(1).fillna(0.0)
            hits = held = 0
            tot_flips = 0
            for k in h:
                hk, fk, Kt = h[k], fh[k], fr["K"]
                on = hk.notna()
                flips = int((hk.diff().abs() == 2).sum())
                tot_flips += flips
                contrib = ((hk - hbar[k]) * fk / Kt).where(on, 0.0)
                net = contrib - (c * 2 * (hk - prev[k]).abs() / Kt).where(on, 0.0)
                hit = (np.sign(hk[on]) == np.sign(fk[on])) & (fk[on] != 0)
                se_k = float(((hk - hbar[k]) / Kt).fillna(0).sum() / len(hk))
                pf = {"hbar": float(hbar[k]), "months_held": int(on.sum()), "flips": flips,
                      "flips_per_year": flips / on.sum() * 12, "ties": ties[k],
                      "long_share": float((hk[on] > 0).mean()), "hit_rate": float(hit.mean()),
                      "contribution_to_mean_d_gross_pct_a_year": float(contrib.mean() * 12),
                      "contribution_gross_nw_t": nw(contrib)[2],
                      "contribution_to_mean_d_net_pct_a_year": float(net.mean() * 12),
                      "contribution_net_nw_t": nw(net)[2], "hits": int(hit.sum()), "static_exposure": se_k}
                cmp_dict(f"{case} {t} factor {k}", pub["per_factor"][k], pf)
                hits += int(hit.sum())
                held += int(on.sum())
                rec[case].setdefault(t, {})[k] = pf
            add(f"{case} {t} net contributions sum to mean d",
                sum(v["contribution_to_mean_d_net_pct_a_year"] for v in rec[case][t].values()),
                m["d"]["mean_pct_a_year"], 1e-12)
            add(f"{case} {t} flips total per year", pub["flips_total_per_year"], tot_flips / len(fr) * 12)
            add(f"{case} {t} hit rate pooled", pub["hit_rate_pooled"], hits / held)
            d = fr["d"].to_numpy()
            _, se, _ = nw(d)
            iid = d.std(ddof=1) / math.sqrt(len(d))
            sda = d.std(ddof=1) * SQ12
            pw = {"nw_over_iid_se": se / iid, "sd_d_pct_a_year": sda, "mde_t2_pct_a_year": 2 * se * 12,
                  "mde_80_pct_a_year": 2.842 * se * 12, "mde_t2_sharpe_d": 2 * se * 12 / sda,
                  "mde_80_sharpe_d": 2.842 * se * 12 / sda}
            cmp_dict(f"{case} {t} power", pub["power_realised"], pw)
            rec[case][t]["_m"] = m
            rec[case][t]["_fr"] = fr
            rec[case][t]["_dsr3"] = dsr(srm(x), len(x), sk, ku, 3, var)["dsr"]

    # (c) criteria and verdict by the reviewer's own reading of §9.5
    own = {}
    for t in TRIALS:
        mb, ms = rec["base"][t]["_m"], rec["stress"][t]["_m"]
        c1 = mb["T"]["sharpe_annual"] >= mb["B1"]["sharpe_annual"] + 0.10 and \
            mb["T"]["sharpe_annual"] >= mb["B3"]["sharpe_annual"] + 0.10
        c2 = mb["d"]["nw_t"] >= 2.0
        c3 = rec["base"][t]["_dsr3"] >= 0.95
        c4 = np.sign(ms["d"]["mean_pct_a_year"]) == np.sign(mb["d"]["mean_pct_a_year"])
        for name, v in zip(("C1", "C2", "C3", "C4"), (c1, c2, c3, c4)):
            add(f"criterion {t} {name}", summ["criteria"][t][name], bool(v))
        own[t] = "meets C1-C4" if (c1 and c2 and c3 and c4) else "not supported"
    win = drow(sl(rec["base"]["T1"]["_fr"]["d"], WIN["P"]))
    add("window row P mean d", summ["window_row_T1"]["mean_pct_a_year"], win["mean_pct_a_year"])
    add("window row P pass", summ["window_row_T1"]["pass"], win["mean_pct_a_year"] > 0)
    if own["T1"] == "not supported":
        v = "not supported"
    elif win["mean_pct_a_year"] <= 0:
        v = "inconclusive (paper's window only)"
    elif "not supported" in (own["T1a"], own["T1b"]):
        v = "inconclusive (fragile)"
    else:
        v = "supported in history; forward record pending"
    d1 = rec["base"]["T1"]["_fr"]["d"]
    mde80 = 2.842 * nw(d1)[1] * 12
    lab = mde80 > 2.0
    add("verdict T1 (reviewer's precedence)", summ["verdict"]["T1"], v)
    for t in ("T1a", "T1b"):
        add(f"verdict {t}", summ["verdict"][t].replace("–", "-"), own[t])
    add("return-unit label needed", summ["verdict"]["return_unit_bar_not_met"], lab)
    mb = rec["base"]["T1"]["_m"]
    add("T1 C1 shortfall vs B1 (info)", None, mb["T"]["sharpe_annual"] - mb["B1"]["sharpe_annual"] - 0.10)
    add("T1 C1 shortfall vs B3 (info)", None, mb["T"]["sharpe_annual"] - mb["B3"]["sharpe_annual"] - 0.10)

    # (d) T1 descriptives
    desc = summ["descriptive_T1"]
    yr = pd.Series(d1.index.str[:4].astype(int) // 10 * 10, index=d1.index)
    for dec, grp in d1.groupby(yr):
        cmp_dict(f"decade {dec}s", desc["d_by_decade"][f"{dec}s"], drow(grp))
    worst = d1.sort_values(kind="stable").iloc[:12]
    add("twelve worst months (dates)", ",".join(x["month"] for x in desc["twelve_worst_months_d"]),
        ",".join(worst.index))
    series_row("twelve worst months (values)", [x["d_pct"] for x in desc["twelve_worst_months_d"]], worst.values)
    for name, (a, b) in EPIS.items():
        s = sl(d1, [(a, b)])
        cmp_dict(f"episode {name}", desc["episodes_d"][name],
                 {"months": len(s), "sum_pct": float(s.sum()), "mean_pct_a_year": float(s.mean() * 12)})
    t1 = rec["base"]["T1"]["_fr"]
    for lab_, span in {"paper_strategy_months": ("1964-07", "2015-12"), "H": ("1927-07", "2026-08")}.items():
        for col, key in (("T_gross", "T1_gross"), ("T", "T1_base"), ("B1", "B1")):
            cmp_dict(f"paper comparison {lab_} {key}", desc["paper_comparison"][lab_][key], drow(sl(t1[col], [span])))

    # programme count (public part only)
    pc = json.loads((RES / "programme_count.json").read_text())
    tot = 0
    for p in sorted((ROOT / "research").glob("*/trials.md")):
        txt = git("show", f"eef348e:research/{p.parent.name}/trials.md")
        ids, inside = [], False
        for ln in txt.splitlines():
            if ln.startswith("| ID |"):
                inside = True
                continue
            if inside and not ln.startswith("|"):
                break
            if inside and not set(ln.split("|")[1].strip()) <= set("-: "):
                ids.append(ln.split("|")[1].strip())
        add(f"public count {p.parent.name}", pc["public_by_study"][p.parent.name], len(ids), 0)
        tot += len(ids)
    add("public count total", pc["public_trials_md"], tot, 0)
    add("desk registry part (595 - 31)", None, pc["with_desk_registry"] - pc["public_trials_md"], fmt="{:.0f}",
        note="not checkable: private registry outside the repository")

    # (f) typed numbers
    b, s = (lambda t: rec["base"][t]["_m"]), (lambda t: rec["stress"][t]["_m"])
    pf = rec["base"]["T1"]
    dsr_b = summ["cost_cases"]["base"]["trials"]["T1"]["dsr"]
    w = {k: drow(sl(t1["d"], WIN[k])) for k in WIN}
    common = [  # (claim, printed value, recomputed, decimals)
        ("T1 Sharpe T", 0.575, b("T1")["T"]["sharpe_annual"], 3),
        ("T1 Sharpe B1", 0.554, b("T1")["B1"]["sharpe_annual"], 3),
        ("T1 Sharpe B3", 0.697, b("T1")["B3"]["sharpe_annual"], 3),
        ("T1 B3 vol % a year", 1.96, b("T1")["B3"]["vol_pct_a_year"], 2),
        ("T1 mean d", 2.57, b("T1")["d"]["mean_pct_a_year"], 2), ("T1 NW t d", 3.78, b("T1")["d"]["nw_t"], 2),
        ("T1 DSR N=10", 0.9999, dsr_b["N10"]["dsr"], 4), ("T1 DSR N=31", 0.9989, dsr_b["N31"]["dsr"], 4),
        ("T1 DSR N=595", 0.9403, dsr_b["N595"]["dsr"], 4),
        ("T1 stress mean d", 0.74, s("T1")["d"]["mean_pct_a_year"], 2), ("T1 stress t", 1.03, s("T1")["d"]["nw_t"], 2),
        ("T1 T-B1", -0.36, b("T1")["T_minus_B1"]["mean_pct_a_year"], 2),
        ("T1 T-B1 t", -0.43, b("T1")["T_minus_B1"]["nw_t"], 2),
        ("window P mean", 3.18, w["P"]["mean_pct_a_year"], 2), ("window P t", 2.76, w["P"]["nw_t"], 2),
        ("P1 mean", 4.01, w["P1"]["mean_pct_a_year"], 2), ("P1 t", 2.97, w["P1"]["nw_t"], 2),
        ("L mean", 2.03, w["L"]["mean_pct_a_year"], 2), ("L t", 2.64, w["L"]["nw_t"], 2),
        ("P2 mean", 0.36, w["P2"]["mean_pct_a_year"], 2), ("P2 t", 0.18, w["P2"]["nw_t"], 2),
        ("T1a Sharpe T", 0.330, b("T1a")["T"]["sharpe_annual"], 3),
        ("T1a Sharpe B1", 0.355, b("T1a")["B1"]["sharpe_annual"], 3),
        ("T1a Sharpe B3", 0.361, b("T1a")["B3"]["sharpe_annual"], 3),
        ("T1a mean d", 2.48, b("T1a")["d"]["mean_pct_a_year"], 2), ("T1a t", 2.82, b("T1a")["d"]["nw_t"], 2),
        ("T1b Sharpe T", 0.249, b("T1b")["T"]["sharpe_annual"], 3),
        ("T1b Sharpe B1", 0.551, b("T1b")["B1"]["sharpe_annual"], 3),
        ("T1b Sharpe B3", 0.699, b("T1b")["B3"]["sharpe_annual"], 3),
        ("T1b mean d", 0.59, b("T1b")["d"]["mean_pct_a_year"], 2), ("T1b t", 0.84, b("T1b")["d"]["nw_t"], 2),
        ("MDE 80% % a year", 1.93, mde80, 2),
        ("hbar SMB", 0.059, pf["SMB"]["hbar"], 3), ("hbar HML", 0.224, pf["HML"]["hbar"], 3),
        ("hbar ST_Rev", 0.511, pf["ST_Rev"]["hbar"], 3), ("hbar LT_Rev", 0.120, pf["LT_Rev"]["hbar"], 3),
    ]
    tm = [("T1 B3 mean % a year", 1.36, b("T1")["B3"]["mean_pct_a_year"], 2),
          ("T1 DSR N=3", 1.000, rec["base"]["T1"]["_dsr3"], 3),
          ("data step H months", 1190, 1190, 0), ("3-factor rows", 1202, len(F["SMB"].dropna()), 0),
          ("ST_Rev rows", 1207, len(F["ST_Rev"].dropna()), 0), ("LT_Rev rows", 1148, len(F["LT_Rev"].dropna()), 0),
          ("T1 LT_Rev months held", 1136, pf["LT_Rev"]["months_held"], 0),
          ("T1b LT_Rev months held", 1142, rec["base"]["T1b"]["LT_Rev"]["months_held"], 0),
          ("public count", 31, tot, 0)]
    for cl, v, r, dd in common + tm:
        typed(cl, v, r, dd)
    for t in TRIALS:
        add(f"[trials.md] row says {t} not supported", True,
            ("not supported" in trials_md) and summ["verdict"][t] == "not supported")

    if readme is not None:
        add("README.md sha256 at review (info)", None, sha(readme.encode()))
        sub = {t: {k: drow(sl(rec["base"][t]["_fr"]["d"], WIN[k])) for k in ("P1", "L", "P2")} for t in TRIALS}
        dec = {k: v for k, v in summ["descriptive_T1"]["d_by_decade"].items()}
        hr = [pf[k]["hit_rate"] * 100 for k in FACTORS]
        fl = [pf[k]["flips"] for k in FACTORS]
        wst = list(worst.items())
        pc_ = desc["paper_comparison"]["paper_strategy_months"]
        lwb = summ["cost_cases"]["base"]["trials"]["T1"]
        rd = common + [
            ("T1 vol % a year", 6.84, b("T1")["T"]["vol_pct_a_year"], 2),
            ("T1a T-B1", -0.10, b("T1a")["T_minus_B1"]["mean_pct_a_year"], 2),
            ("T1b T-B1", -2.60, b("T1b")["T_minus_B1"]["mean_pct_a_year"], 2),
            ("DSR N=3 T1", 1.000, rec["base"]["T1"]["_dsr3"], 3),
            ("DSR N=3 T1a", 0.984, rec["base"]["T1a"]["_dsr3"], 3),
            ("DSR N=3 T1b", 0.895, rec["base"]["T1b"]["_dsr3"], 3),
            ("LW diff vs B1", 0.02, lwb["sharpe_test_vs_B1"]["diff_annual"], 2),
            ("LW p vs B1", 0.87, lwb["sharpe_test_vs_B1"]["p_value"], 2),
            ("LW diff vs B3", -0.12, lwb["sharpe_test_vs_B3"]["diff_annual"], 2),
            ("LW p vs B3", 0.31, lwb["sharpe_test_vs_B3"]["p_value"], 2),
            ("T1 cost base % a year", 0.46, b("T1")["cost_pct_a_year"], 2),
            ("T1 cost stress % a year", 2.28, s("T1")["cost_pct_a_year"], 2),
            ("T1 flips a year total", 4.50, lwb["flips_total_per_year"], 2),
            ("T1 Sharpe of d", 0.37, b("T1")["d"]["sharpe_annual"], 2),
            ("P2 power ratio low (0.870 / Sharpe d)", 2.4, 0.870 / b("T1")["d"]["sharpe_annual"], 1),
            ("P2 power ratio high (0.964 / Sharpe d)", 2.6, 0.964 / b("T1")["d"]["sharpe_annual"], 1),
            ("hbar SMB (2 dp)", 0.06, pf["SMB"]["hbar"], 2), ("hbar ST_Rev (2 dp)", 0.51, pf["ST_Rev"]["hbar"], 2),
            ("flips min", 103, min(fl), 0), ("flips max", 123, max(fl), 0),
            ("hit rate min %", 53, min(hr), 0), ("hit rate max %", 57, max(hr), 0),
            ("hit rate pooled %", 55.3, lwb["hit_rate_pooled"] * 100, 1),
            ("static exposure max abs", 0.0035, max(abs(pf[k]["static_exposure"]) for k in FACTORS), 4),
            ("episode 1929-32 sum", 11.0, desc["episodes_d"]["1929-09 to 1932-12"]["sum_pct"], 1),
            ("episode 2008-09 sum", -5.9, desc["episodes_d"]["2008-09 to 2009-12"]["sum_pct"], 1),
            ("worst month value", -13.8, wst[0][1], 1), ("12th worst value", -5.4, wst[-1][1], 1),
            ("paper T1 gross", 3.57, pc_["T1_gross"]["mean_pct_a_year"], 2),
            ("paper T1 gross t", 4.56, pc_["T1_gross"]["nw_t"], 2),
            ("paper T1 base", 3.08, pc_["T1_base"]["mean_pct_a_year"], 2),
            ("paper T1 base t", 3.88, pc_["T1_base"]["nw_t"], 2),
            ("paper B1", 3.97, pc_["B1"]["mean_pct_a_year"], 2), ("paper B1 t", 4.40, pc_["B1"]["nw_t"], 2),
            ("paper months", 618, pc_["B1"]["months"], 0),
            ("sd(d)", 6.94, d1.std(ddof=1) * SQ12, 2),
            ("NW/iid", 0.975, nw(d1)[1] / (d1.std(ddof=1) / math.sqrt(len(d1))), 3),
            ("MDE t=2", 1.36, 2 * nw(d1)[1] * 12, 2),
            ("MDE Sharpe t=2", 0.20, 2 * nw(d1)[1] * 12 / (d1.std(ddof=1) * SQ12), 2),
            ("MDE Sharpe 80%", 0.28, 2.842 * nw(d1)[1] * 12 / (d1.std(ddof=1) * SQ12), 2),
            ("stress T-B1", -2.18, s("T1")["T_minus_B1"]["mean_pct_a_year"], 2),
            ("stress T-B1 t", -2.54, s("T1")["T_minus_B1"]["nw_t"], 2),
            ("T1b stress d", -2.33, s("T1b")["d"]["mean_pct_a_year"], 2),
        ]
        for t, vals in {"T1": [(4.01, 2.97), (2.03, 2.64), (0.36, 0.18)], "T1a": [(3.30, 1.91), (2.31, 2.25),
                        (0.57, 0.22)], "T1b": [(-0.53, -0.36), (1.19, 1.55), (1.43, 0.76)]}.items():
            for wn, (mv, tv) in zip(("P1", "L", "P2"), vals):
                rd += [(f"sub-window {t} {wn} mean", mv, sub[t][wn]["mean_pct_a_year"], 2),
                       (f"sub-window {t} {wn} t", tv, sub[t][wn]["nw_t"], 2)]
        for dk, (mv, tv) in {"1920s": (10.56, 1.92), "1930s": (5.34, 1.36), "1940s": (4.95, 2.46),
                             "1950s": (1.09, 0.98), "1960s": (2.80, 2.38), "1970s": (5.13, 3.30),
                             "1980s": (1.55, 1.05), "1990s": (2.76, 1.37), "2000s": (-0.87, -0.44),
                             "2010s": (-0.22, -0.15), "2020s": (0.49, 0.18)}.items():
            rd += [(f"decade {dk} mean", mv, dec[dk]["mean_pct_a_year"], 2), (f"decade {dk} t", tv, dec[dk]["nw_t"], 2)]
        for k, (nv, nt, gv) in {"SMB": (0.69, 2.41, 0.81), "HML": (0.61, 1.95, 0.72), "ST_Rev": (0.37, 1.24, 0.49),
                                "LT_Rev": (0.91, 2.96, 1.01)}.items():
            rd += [(f"contribution net {k}", nv, pf[k]["contribution_to_mean_d_net_pct_a_year"], 2),
                   (f"contribution net t {k}", nt, pf[k]["contribution_net_nw_t"], 2),
                   (f"contribution gross {k}", gv, pf[k]["contribution_to_mean_d_gross_pct_a_year"], 2)]
        for cl, v_, r, dd in rd:
            typed(cl, v_, r, dd, "README")
        add("[README] decade 1920s months 30, 2020s months 80", "30,80",
            f"{dec['1920s']['months']},{dec['2020s']['months']}")
        add("[README] worst month dates 1939-09 and 2022-07", "1939-09,2022-07", f"{wst[0][0]},{wst[-1][0]}")
        yrs = [m_[:4] for m_, _ in wst]
        add("[README] worst months in 2000-2001 and 2008", 5, sum(y in ("2000", "2001", "2008") for y in yrs), 0)
        add("[README] worst months in 2020-2023", 3, sum("2020" <= y <= "2023" for y in yrs), 0)
        add("[README] decades 1920s-1990s all positive", True,
            all(dec[f"{y}s"]["mean_pct_a_year"] > 0 for y in range(1920, 2000, 10)))
        add("[README] first paragraph has §2.4 disclosure and 'only N = 3'", True,
            "§2.4" in readme.split("\n\n")[1] and "only N = 3" in readme.split("\n\n")[1])
        add("[README] disclosure names the 1929-32 fall (QUESTION.md §3.1 list)", True,
            "1929" in readme.split("\n\n")[1], note="should-fix if NO")

    # (g) commit chain
    chain = ["e699ac3", "9cfd47f", "d9648af", "cb8866c", "a2e97b3", "e98c874", "1839e5a", "55aa9e3", "2f29086",
             "eef348e", "1748602", "d9ac7da"]
    ts = {c: pd.Timestamp(git("show", "-s", "--format=%cI", c).strip()) for c in chain}
    add("chain strictly increasing in committer time", True,
        all(ts[a] < ts[b_] for a, b_ in zip(chain, chain[1:])))
    anc = all(subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", a, b_]).returncode == 0
              for a, b_ in zip(chain, chain[1:]))
    add("chain is an ancestry line", True, anc)
    ds = pd.Timestamp(step["run_at_utc"])
    hr_ = pd.Timestamp(summ["run_at_utc"])
    add("data step run after cb8866c and before a2e97b3", True, ts["cb8866c"] < ds < ts["a2e97b3"])
    add("count time before eef348e", True, pd.Timestamp(pc["counted_at_utc"]) < ts["eef348e"])
    add("history run after eef348e and before 1748602", True, ts["eef348e"] < hr_ < ts["1748602"])
    add("APPROVED added in 2f29086", "2f29086",
        git("log", "--diff-filter=A", "--format=%h", "--", "research/010-factor-momentum-french-us/APPROVED").strip())
    row = "| History run (§14 step 6), logged before it runs"
    add("history-run row absent at 2f29086, present at eef348e", True,
        row not in git("show", "2f29086:research/010-factor-momentum-french-us/trials.md")
        and row in git("show", "eef348e:research/010-factor-momentum-french-us/trials.md"))
    drow_ = "| Data step (§14 step 2), logged before it runs"
    add("data-step row absent at 9dbaa96, present at cb8866c", True,
        drow_ not in git("show", "9dbaa96:research/010-factor-momentum-french-us/trials.md")
        and drow_ in git("show", "cb8866c:research/010-factor-momentum-french-us/trials.md"))
    add("results/history committed only in 1748602", "1748602",
        git("log", "--format=%h", "--", "research/010-factor-momentum-french-us/results/history").strip())
    add("results/ unchanged in the working tree", "",
        git("status", "--porcelain", "--", "research/010-factor-momentum-french-us/results").strip())
    add("src/ and reproduce.sh unchanged 55aa9e3 -> HEAD", "",
        git("diff", "--stat", "55aa9e3", "HEAD", "--", "research/010-factor-momentum-french-us/src",
            "research/010-factor-momentum-french-us/reproduce.sh").strip())
    for f_, base in (("PREREGISTRATION.md", "d9648af"), ("trials.md", "d9648af"), ("QUESTION.md", "e699ac3")):
        ns = git("diff", "--numstat", base, "HEAD", "--", f"research/010-factor-momentum-french-us/{f_}").split()
        add(f"no line removed from {f_} since {base}", 0, int(ns[1]) if ns else 0, 0)
    refl = git("reflog", "show", "--date=iso-strict", "--format=%h %gd", "origin/main")
    push = {ln.split()[0]: pd.Timestamp(re.search(r"@\{(.*)\}", ln).group(1)) for ln in refl.splitlines() if "@{" in ln}
    add("cb8866c pushed before the data step ran", True, "cb8866c" in push and push["cb8866c"] < pd.Timestamp(
        json.loads((RES / "data_manifest.json").read_text())["library_page"]["read_at_utc"]))
    add("eef348e pushed before the history run", True, "eef348e" in push and push["eef348e"] < hr_)
    add("pre-registration (9dbaa96 push contains d9648af) pushed before cb8866c", True,
        "9dbaa96" in push and push["9dbaa96"] < ts["cb8866c"])

    w0 = max(len(r[0]) for r in rows)
    bad = 0
    for cl, p, r, ok in rows:
        print(f"{cl:<{w0}}  {p:>22}  {r:>22}  {ok}")
        bad += ok.startswith("NO")
    n_yes = sum(r[3].startswith("yes") for r in rows)
    n_info = sum(r[3].startswith("info") for r in rows)
    print(f"\n{len(rows)} rows: {n_yes} match, {bad} mismatch, {n_info} informational")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
