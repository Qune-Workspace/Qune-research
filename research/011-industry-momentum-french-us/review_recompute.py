"""Independent recomputation of Study 011 from results/history/ (separate-session review).

Rebuilds the rule from industries_17.csv / industries_30.csv per PREREGISTRATION §6,
without importing the study's src/. Uses qune_research.stats only for DSR and bootstrap
(and its skewness/kurtosis, re-derived here as well).
Run: python -I recompute011.py <repo_root>
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(sys.argv[1])
H = ROOT / "research/011-industry-momentum-french-us/results/history"
sys.path.insert(0, str(ROOT))
from qune_research import stats  # noqa: E402

END = "2026-08"
TRIALS = {"M1": (17, 6, 3, "1927-06"), "M1a": (30, 6, 5, "1927-06"), "M1b": (17, 12, 3, "1927-12")}
out = {}


def load(n):
    df = pd.read_csv(H / f"industries_{n}.csv", dtype={"month": str}).set_index("month")
    df.index = pd.PeriodIndex(df.index, freq="M")
    return df.astype(float)


def build(df, F, n, first):
    r = df.values
    months = df.index
    T, K = r.shape
    g = 1 + r / 100
    W, L = {}, {}
    ties = 0
    for m in range(F - 1, T):
        R = np.prod(g[m - F + 1:m + 1], axis=0) - 1
        order = sorted(range(K), key=lambda i: (-round(R[i], 10), i))
        W[m] = order[:n]
        L[m] = order[-n:]
        Rs = [R[i] for i in order]
        for b in (n - 1, K - n - 1):
            if abs(Rs[b] - Rs[b + 1]) < 1e-12:
                ties += 1
    t0 = list(months).index(pd.Period(first, "M"))
    rows = []
    wprev = np.zeros(K)
    for t in range(t0, T):
        w = np.zeros(K)
        cs, wl, ll = [], [], []
        for j in range(1, 7):
            m = t - j
            w[W[m]] += 1 / (6 * n)
            w[L[m]] -= 1 / (6 * n)
            wm = r[t, W[m]].mean()
            lm = r[t, L[m]].mean()
            cs.append(wm - lm); wl.append(wm); ll.append(lm)
        to = np.abs(w - wprev).sum()
        wprev = w
        dg = np.mean(cs)
        rows.append((months[t], dg, to, dg - 0.10 * to, dg - 0.50 * to, np.mean(wl), np.mean(ll), r[t].mean()))
    f = pd.DataFrame(rows, columns=["month", "d_gross", "turnover", "d_base", "d_stress", "winners_leg",
                                    "losers_leg", "ew"]).set_index("month")
    return f, W, L, ties


def sl(s, a, b):
    return s[(s.index >= pd.Period(a, "M")) & (s.index <= pd.Period(b, "M"))]


def nw_two(parts, lags=6):
    arr = [np.asarray(p, float) for p in parts]
    x = np.concatenate(arr); N = len(x); mu = x.mean()
    us = [a - mu for a in arr]
    s = sum(u @ u for u in us) / N
    for j in range(1, lags + 1):
        s += 2 * (1 - j / (lags + 1)) * sum(u[j:] @ u[:-j] for u in us) / N
    se = math.sqrt(s / N)
    return mu, se, mu / se


def nw(x):
    return nw_two([x])


def row(x):
    mu, se, t = nw(x)
    return dict(n=len(x), mean_a=mu * 12, t=t, sharpe=x.mean() / x.std(ddof=1) * math.sqrt(12))


def sk(x):
    z = (x - x.mean()) / x.std(ddof=0); return float((z ** 3).mean()), float((z ** 4).mean())


mon = pd.read_csv(H / "monthly.csv", dtype={"month": str}).set_index("month")
mon.index = pd.PeriodIndex(mon.index, freq="M")
coh = json.load(open(H / "cohorts.json"))
ind = {17: load(17), 30: load(30)}
frames = {}
for k, (s, F, n, first) in TRIALS.items():
    f, W, L, ties = build(ind[s], F, n, first)
    f = f[f.index <= pd.Period(END, "M")]
    frames[k] = f
    cols = ind[s].columns
    diffs = {}
    for c in ["d_gross", "turnover", "d_base", "d_stress", "winners_leg", "losers_leg", "ew"]:
        theirs = mon[f"{k}_{c}"].dropna()
        assert list(theirs.index) == list(f.index), (k, c)
        diffs[c] = float(np.abs(theirs.values - f[c].values).max())
    # cohorts
    cm = 0; cmis = 0
    for m, (w, l, _) in coh[k].items():
        p = list(ind[s].index).index(pd.Period(m, "M"))
        cm += 1
        if set(w) != set(cols[W[p]]) or set(l) != set(cols[L[p]]):
            cmis += 1
    out[k] = {"maxabs": diffs, "cohorts_checked": cm, "cohort_mismatch": cmis, "ties": ties,
              "empty_legs_csv": int(mon[f"{k}_empty_legs"].sum()), "ties_csv": int(mon[f"{k}_ties"].sum())}

res = {}
for case in ["base", "stress"]:
    srs = {}
    for k, (s, F, n, first) in TRIALS.items():
        d = frames[k][f"d_{case}"]
        i1, i2 = sl(d, first, "1963-06"), sl(d, "1995-08", END)
        o = pd.concat([i1, i2])
        mu, se, t = nw_two([i1, i2])
        sd = o.std(ddof=1)
        g3, g4 = sk(o)
        srs[k] = (o.mean() / sd)
        res[(case, k)] = dict(
            O=dict(n=len(o), nI1=len(i1), nI2=len(i2), mean_a=mu * 12, t=t, sharpe=o.mean() / sd * math.sqrt(12),
                   se_a=se * 12, sd_a=sd * math.sqrt(12), nw_iid=se / (sd / math.sqrt(len(o))),
                   mde2=2 * se * 12, mde80=2.842 * se * 12, mde2_sh=2 * se * 12 / (sd * math.sqrt(12)),
                   mde80_sh=2.842 * se * 12 / (sd * math.sqrt(12)), skew=g3, kurt=g4, pos=float((o > 0).mean()),
                   naive_t_concat=nw(o)[2]),
            I1=row(i1), I2=row(i2), M=row(sl(d, "1963-07", "1995-07")), full=row(d),
            turnover_a=frames[k]["turnover"].mean() * 12,
            turnover_O_a=pd.concat([sl(frames[k]["turnover"], first, "1963-06"),
                                    sl(frames[k]["turnover"], "1995-08", END)]).mean() * 12,
            cost_O_a=(pd.concat([sl(frames[k]["d_gross"], first, "1963-06"), sl(frames[k]["d_gross"], "1995-08", END)])
                      - o).mean() * 12,
            o_series=o)
    v = float(np.var(list(srs.values()), ddof=0))
    floor = (0.05 / math.sqrt(12)) ** 2
    vv = max(v, floor)
    for k in TRIALS:
        o = res[(case, k)]["o_series"] / 100
        g3, g4 = sk(o)
        sr = o.mean() / o.std(ddof=1)
        dsr = {}
        for N in (3, 11, 34, 598):
            from scipy.stats import norm
            emax = math.sqrt(vv) * ((1 - 0.5772156649015329) * norm.ppf(1 - 1 / N)
                                   + 0.5772156649015329 * norm.ppf(1 - 1 / (N * math.e)))
            dsr[N] = float(norm.cdf((sr - emax) * math.sqrt(len(o) - 1) / math.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)))
            lib = stats.deflated_sharpe(stats.sharpe_monthly(o), len(o), stats.skewness(o), stats.kurtosis(o), N, vv)["dsr"]
            assert abs(lib - dsr[N]) < 1e-12
        # DSR without floor, for information
        dsr_nofloor3 = None
        res[(case, k)]["dsr"] = dsr
        res[(case, k)]["var_raw"] = v
        res[(case, k)]["floor_applied"] = v < floor
    # bootstrap in the code's order: rng seeded once per case, trials in order M1, M1a, M1b
    rng = np.random.default_rng(20261021)
    for k in TRIALS:
        res[(case, k)]["ci"] = stats.sharpe_ci_stationary_bootstrap(res[(case, k)]["o_series"] / 100, rng,
                                                                    n_resamples=10_000)

P = print
P("== rule rebuild: max abs diff vs monthly.csv, cohorts")
for k, v in out.items():
    P(k, v)
for case in ["base", "stress"]:
    P(f"== {case}")
    for k in TRIALS:
        r = res[(case, k)]
        O = r["O"]
        P(k, "O n=%d (%d+%d) mean %+.4f t %.4f sh %.4f se_a %.4f sd_a %.4f nwiid %.4f mde2 %.4f mde80 %.4f "
          "mde2sh %.4f mde80sh %.4f skew %.4f kurt %.4f pos %.4f naive-concat-t %.4f" % (
              O["n"], O["nI1"], O["nI2"], O["mean_a"], O["t"], O["sharpe"], O["se_a"], O["sd_a"], O["nw_iid"],
              O["mde2"], O["mde80"], O["mde2_sh"], O["mde80_sh"], O["skew"], O["kurt"], O["pos"],
              O["naive_t_concat"]))
        for w in ["I1", "I2", "M", "full"]:
            P("   ", w, {a: (round(b, 4) if isinstance(b, float) else b) for a, b in r[w].items()})
        P("   DSR", {a: round(b, 4) for a, b in r["dsr"].items()}, "var_raw %.6g floor_applied %s" % (
            r["var_raw"], r["floor_applied"]))
        P("   turnover/yr full %.3f O %.3f cost on O %.3f" % (r["turnover_a"], r["turnover_O_a"], r["cost_O_a"]))
        P("   CI", r["ci"])
# criteria
P("== criteria (base) and verdict")
crit = {}
for k in TRIALS:
    b, s_ = res[("base", k)], res[("stress", k)]
    c = dict(C1=b["O"]["sharpe"] >= 0.10, C2=b["O"]["t"] >= 2.0, C3=b["dsr"][3] >= 0.95,
             C4=np.sign(s_["O"]["mean_a"]) == np.sign(b["O"]["mean_a"]))
    crit[k] = c
    P(k, c)
win = res[("base", "M1")]["I1"]["mean_a"] > 0 and res[("base", "M1")]["I2"]["mean_a"] > 0
P("window row pass", win, "MDE80 M1 %.4f > 2: %s" % (res[("base", "M1")]["O"]["mde80"], res[("base", "M1")]["O"]["mde80"] > 2))

# descriptive, M1
f1 = frames["M1"]; d1 = f1["d_base"]
P("== decades (d_base)")
for dec, g in d1.groupby((d1.index.year // 10) * 10):
    r = row(g); P(dec, r["n"], "%+.2f (%.2f)" % (r["mean_a"], r["t"]))
P("== decades (d_gross, for comparison)")
for dec, g in f1["d_gross"].groupby((f1.index.year // 10) * 10):
    r = row(g); P(dec, r["n"], "%+.2f (%.2f)" % (r["mean_a"], r["t"]))
P("== legs on O (two-stretch)")
for name, s in [("W-EW", f1["winners_leg"] - f1["ew"]), ("L-EW", f1["losers_leg"] - f1["ew"]), ("EW", f1["ew"])]:
    i1, i2 = sl(s, "1927-06", "1963-06"), sl(s, "1995-08", END)
    mu, se, t = nw_two([i1, i2]); P(name, "%+.3f t %.3f" % (mu * 12, t))
# W-L leg identity: winners_leg - losers_leg == d_gross
P("legs identity max diff", float(np.abs(f1["winners_leg"] - f1["losers_leg"] - f1["d_gross"]).max()))
P("== paper comparison: M1 gross over M %% a month %.4f; base %.4f" % (
    sl(f1["d_gross"], "1963-07", "1995-07").mean(), sl(d1, "1963-07", "1995-07").mean()))
P("   M1 gross over M %% a year %.3f" % (sl(f1["d_gross"], "1963-07", "1995-07").mean() * 12))
for a, b in [("1929-09", "1932-12"), ("2008-09", "2009-12")]:
    s = sl(d1, a, b); P("episode", a, b, len(s), "sum %.3f" % s.sum(), "gross sum %.3f" % sl(f1["d_gross"], a, b).sum())
P("== twelve worst (d_base, full history)")
for p, v in d1.nsmallest(12).items():
    P(p, "%.3f" % v)
P("== twelve worst (d_base, O only)")
oo = pd.concat([sl(d1, "1927-06", "1963-06"), sl(d1, "1995-08", END)])
for p, v in oo.nsmallest(12).items():
    P(p, "%.3f" % v)
P("full-history skew/kurt", sk(d1))
P("== industry shares M1 (held ranking months 1926-12..2026-07)")
s17 = ind[17]
_, W, L, _ = build(s17, 6, 3, "1927-06")
idx = list(s17.index)
held = [p for p in W if idx[p] >= pd.Period("1926-12", "M") and idx[p] < pd.Period(END, "M")]
sh = {c: (sum(i in W[p] for p in held) / len(held), sum(i in L[p] for p in held) / len(held))
      for i, c in enumerate(s17.columns)}
for c, (w, l) in sorted(sh.items(), key=lambda kv: kv[1][0]):
    P(c, "W %.4f L %.4f sum %.4f" % (w, l, w + l))
P("held ranking months", len(held))
# decade 1970s-2010s t below 1.1? and 1970s..2020s range

# Sensitivity: DSR at N = 3 without the variance floor (information only)
P("== DSR without the variance floor (base)")
for k in TRIALS:
    o = res[("base", k)]["o_series"] / 100
    raw = res[("base", k)]["var_raw"]
    P(k, {N: round(stats.deflated_sharpe(stats.sharpe_monthly(o), len(o), stats.skewness(o), stats.kurtosis(o), N, raw)["dsr"], 4)
          for N in (3, 11, 34, 598)}, "PSR(0) %.4f" % stats.deflated_sharpe(stats.sharpe_monthly(o), len(o), stats.skewness(o), stats.kurtosis(o), 3, raw)["psr"])
# M gross mean and its se, for the paper comparison
g = sl(f1["d_gross"], "1963-07", "1995-07"); mu, se, t = nw(g)
P("M gross %% a month %.4f se %.4f t %.3f; diff from 0.43 in se units %.2f" % (mu, se, t, (0.43 - mu) / se))
