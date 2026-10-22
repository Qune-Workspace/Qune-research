"""Independent recomputation for REVIEW.md (Study 002, roll-down-aware re-test, halted at §5.3).

Written by the reviewer (Tester, a separate agent session that did not write the
code).  It imports nothing from the study's ``src/`` or ``exante_bias.py``: the §5.2
ageing 8.5-year par bond, the cash leg, the duration/convexity cross-check, the §5.3
statistics on both windows (A1-A4, B1-B2, D1), the §5.3.4 step-2 vendor overlap check,
the §5.3.1 ex-ante yield-only quantities and threshold derivation, and the post-hoc
year-by-year table are re-derived with numpy and pandas only from the git-ignored raw
files in ``data/raw/`` (``fred_DGS10.csv``, ``fred_DGS7.csv``, ``fred_DTB3.csv``,
``alpaca_IEF_1Day_all.csv``, ``alpaca_BIL_1Day_all.csv``, ``tiingo_IEF_daily.csv``),
whose SHA-256 are checked against ``results/data_manifest.json`` first.

It prints a comparison table (claim | published | recomputed | match).  Published
values are read from the committed json files at full precision; numbers that exist
only in PREREGISTRATION.md §5.3.5, README.md or ``posthoc_by_year.md`` are typed in
below and marked as such.  Nothing is written to disk.  No return of any rule or
benchmark is computed; no ETF return after 2018-12-31 is read.

Run from the study folder:  ../../.venv/bin/python review_recompute.py
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

STUDY = Path(__file__).resolve().parent
RAW = STUDY / "data" / "raw"
RES = STUDY / "results"
VAL = RES / "validation"
W1 = ("2016-01-04", "2018-12-31")
W2 = ("2003-01-02", "2015-12-31")
IEF_FEE, BIL_FEE = 0.0015, 0.001356
N_YEARS, M0 = 8.5, 17

rows: list[tuple[str, str, str, str]] = []


def add(claim, published, recomputed, tol=None, fmt="{:.6f}", note=""):
    if published is None:
        rows.append((claim, "n/a", fmt.format(recomputed), "informational" + (f" ({note})" if note else "")))
        return
    if isinstance(published, (str, bool, np.bool_)) or isinstance(recomputed, (str, bool, np.bool_)):
        ok = str(published) == str(recomputed)
        rows.append((claim, str(published), str(recomputed), "yes" if ok else "NO"))
        return
    ok = abs(float(published) - float(recomputed)) <= (tol if tol is not None else 0.0)
    rows.append((claim, fmt.format(published), fmt.format(recomputed), ("yes" if ok else "NO") + (f" ({note})" if note else "")))


# ----------------------------------------------------------------------------- raw data
def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fred(name: str) -> pd.Series:
    df = pd.read_csv(RAW / f"fred_{name}.csv")
    v = pd.to_numeric(df.iloc[:, 1].replace(".", np.nan), errors="coerce")
    v.index = pd.to_datetime(df.iloc[:, 0])
    return v.dropna() / 100.0


def alpaca(symbol: str) -> pd.Series:
    df = pd.read_csv(RAW / f"alpaca_{symbol}_1Day_all.csv", parse_dates=["date"]).set_index("date").sort_index()
    return df["close"].astype(float)


def tiingo() -> pd.Series:
    df = pd.read_csv(RAW / "tiingo_IEF_daily.csv", parse_dates=["date"]).set_index("date").sort_index()
    return df["adjClose"].astype(float).dropna()


# ----------------------------------------------------------------------------- bond arithmetic (reviewer's own)
def price(c, y, m):
    """§5.2 P(c, y, m) for non-integer m: 100 [ (c/y)(1 - (1+y/2)^-m) + (1+y/2)^-m ]; at y = 0, 100 c m / 2 + 100."""
    disc = (1.0 + y / 2.0) ** (-m)
    first = np.where(y == 0, 100.0 * c * m / 2.0, 100.0 * (c / np.where(y == 0, 1.0, y)) * (1.0 - disc))
    return first + 100.0 * disc


def dmod_conv(y: np.ndarray, m: int) -> tuple[np.ndarray, np.ndarray]:
    i = y[:, None] / 2.0
    k = np.arange(1, m + 1, dtype=float)[None, :]
    cf = np.full((len(y), m), 1.0) * (y[:, None] / 2.0 * 100.0)
    cf[:, -1] += 100.0
    v = 1.0 / (1.0 + i)
    p = (cf * v ** k).sum(axis=1)
    return (k * cf * v ** (k + 1)).sum(axis=1) / p / 2.0, (k * (k + 1) * cf * v ** (k + 2)).sum(axis=1) / p / 4.0


def ageing_bond(both: pd.DataFrame) -> pd.DataFrame:
    """§5.2 on the dates where DGS7 and DGS10 are both observed (decimals)."""
    y7s, y7t = both["y7"].values[:-1], both["y7"].values[1:]
    y10s, y10t = both["y10"].values[:-1], both["y10"].values[1:]
    days = np.diff(both.index.values).astype("timedelta64[D]").astype(float)
    dt = days / 365.0
    ys = (y7s + y10s) / 2.0
    yt = y7t + (y10t - y7t) * (N_YEARS - dt - 7.0) / 3.0
    mt = 2.0 * (N_YEARS - dt)
    carry = ys * dt - IEF_FEE * dt
    exact = price(ys, yt, mt) / 100.0 - 1.0 + carry
    d, c = dmod_conv(ys, M0)
    dy = yt - ys
    dc = carry - d * dy + 0.5 * c * dy ** 2
    return pd.DataFrame({"exact": exact, "dc": dc}, index=both.index[1:])


def cash_leg(dtb3: pd.Series) -> pd.Series:
    d = dtb3.values[:-1]
    bey = 365.0 * d / (360.0 - 91.0 * d)
    days = np.diff(dtb3.index.values).astype("timedelta64[D]").astype(float)
    return pd.Series((bey - BIL_FEE) * days / 365.0, index=dtb3.index[1:])


def tri(returns: pd.Series, base_date) -> pd.Series:
    return pd.concat([pd.Series([1.0], index=pd.DatetimeIndex([base_date])), (1.0 + returns).cumprod()])


def onto(index: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    return index.reindex(dates, method="ffill").pct_change().dropna()


def stats(etf_r: pd.Series, syn_r: pd.Series) -> dict:
    f = pd.concat([etf_r.rename("e"), syn_r.rename("s")], axis=1).dropna()
    diff = f["e"] - f["s"]
    slope = np.cov(f["s"], f["e"], ddof=1)[0, 1] / np.var(f["s"], ddof=1)
    return {"days": len(f), "first": f.index[0].strftime("%Y-%m-%d"), "last": f.index[-1].strftime("%Y-%m-%d"),
            "corr": float(f["e"].corr(f["s"])), "slope": float(slope),
            "te": float(diff.std(ddof=1) * math.sqrt(252)), "mean": float(diff.mean() * 252),
            "vol_e": float(f["e"].std(ddof=1) * math.sqrt(252)), "vol_s": float(f["s"].std(ddof=1) * math.sqrt(252)),
            "by_year": {str(y): float(g.mean() * 252) for y, g in diff.groupby(diff.index.year)}, "frame": f, "diff": diff}


# ----------------------------------------------------------------------------- main
def main() -> int:
    manifest = json.loads((RES / "data_manifest.json").read_text(encoding="utf-8"))
    for name, entry in manifest.items():
        p = RAW / name
        if not p.exists():
            rows.append((f"manifest SHA-256 {name}", entry["sha256"][:12], "absent", "not checked (file missing)"))
            continue
        add(f"manifest SHA-256 {name}", entry["sha256"], sha256(p))
        add(f"manifest row count {name}", entry["rows"], sum(1 for _ in open(p, "rb")) - 1, 0, "{:d}")
    study1 = STUDY.parent / "001-slope-duration-switch" / "results" / "data_manifest.json"
    if study1.exists():
        m1 = json.loads(study1.read_text(encoding="utf-8"))
        for name in m1:
            add(f"manifest SHA-256 {name} equals Study 001's (reuse claim)", m1[name]["sha256"], manifest[name]["sha256"])

    dgs10, dgs7, dtb3 = fred("DGS10"), fred("DGS7"), fred("DTB3")
    both = pd.concat([dgs7.rename("y7"), dgs10.rename("y10")], axis=1).dropna()
    bond = ageing_bond(both)
    cash = cash_leg(dtb3)
    syn = tri(bond["exact"], both.index[0])
    syn_cash = tri(cash, dtb3.index[0])

    # ---- §5.3.4 step 2: vendor overlap check (Tiingo adjClose vs Alpaca close, 2016-01-04..2018-12-31)
    dec = json.loads((VAL / "window2_data_decision.json").read_text(encoding="utf-8"))
    tii = tiingo()
    v_r = tii.pct_change().dropna().loc[W1[0]:W1[1]]          # the vendor's 2016-01-04 return exists (prior close 2015-12-31)
    a_r = alpaca("IEF").pct_change().dropna().loc[W1[0]:W1[1]]   # Alpaca's first bar is 2016-01-04, so its first return is 2016-01-05
    f = pd.concat([v_r.rename("v"), a_r.rename("a")], axis=1).dropna()
    d = f["v"] - f["a"]
    o = dec["overlap"]
    add("overlap: vendor first bar", dec["vendor"]["first_bar"], tii.index[0].strftime("%Y-%m-%d"))
    add("overlap: vendor rows", dec["vendor"]["rows"], len(tii), 0, "{:d}")
    add("overlap: common return days", o["common_return_days"], len(f), 0, "{:d}")
    add("overlap: first/last common return date", f"{o['first_common_return_date']}..{o['last_common_return_date']}",
        f"{f.index[0]:%Y-%m-%d}..{f.index[-1]:%Y-%m-%d}")
    add("overlap: days only in vendor", ",".join(o["days_only_in_vendor"]), ",".join(x.strftime("%Y-%m-%d") for x in v_r.index.difference(a_r.index)))
    add("overlap: days only in Alpaca", ",".join(o["days_only_in_alpaca"]), ",".join(x.strftime("%Y-%m-%d") for x in a_r.index.difference(v_r.index)))
    add("overlap: correlation", o["correlation"], float(f["v"].corr(f["a"])), 1e-9, "{:.6f}")
    add("overlap: mean difference p.a. vendor - Alpaca", o["mean_diff_annual_vendor_minus_alpaca"], float(d.mean() * 252), 1e-9, "{:+.6%}")
    add("overlap: tracking error p.a.", o["tracking_error_annual"], float(d.std(ddof=1) * math.sqrt(252)), 1e-9, "{:.6%}")
    add("overlap: max abs daily difference", o["max_abs_daily_diff"], float(d.abs().max()), 1e-9, "{:.6%}")
    add("overlap: days with |diff| > 10 bp", o["days_abs_diff_over_10bp"], int((d.abs() > 0.001).sum()), 0, "{:d}")
    add("overlap: date of the largest difference (README/§16: 2016-08-01)", "2016-08-01", d.abs().idxmax().strftime("%Y-%m-%d"))
    for y in ("2016", "2017", "2018"):
        add(f"overlap: mean difference {y} p.a.", o["mean_diff_annual_by_year"][y], float(d.loc[y].mean() * 252), 1e-9, "{:+.6%}")
    md = float(d.mean() * 252)
    add("overlap: correlation pass flag (>= 0.999)", o["checks"]["correlation"]["pass"], bool(f["v"].corr(f["a"]) >= 0.999))
    add("overlap: mean-difference pass flag (within +/-0.05%)", o["checks"]["mean_diff_annual"]["pass"], bool(abs(md) <= 0.0005))
    add("overlap: decision", dec["decision"]["window2"], "accepted" if (f["v"].corr(f["a"]) >= 0.999 and abs(md) <= 0.0005 and tii.index[0] <= pd.Timestamp("2003-01-02")) else "excluded")
    add("README/§16/trials: 'pass by 0.6 bp' margin to the +/-0.05% threshold, in bp", 0.6, (0.0005 - abs(md)) * 1e4, 0.05, "{:.3f}", note="1 bp = 0.01% p.a.")

    # ---- window 1 (§5.3.3)
    w1 = json.loads((VAL / "window1" / "validation.json").read_text(encoding="utf-8"))
    ief = alpaca("IEF").loc[W1[0]:W1[1]]
    bil = alpaca("BIL").loc[W1[0]:W1[1]]
    s1 = stats(ief.pct_change().dropna(), onto(syn, ief.index))
    b1 = stats(bil.pct_change().dropna(), onto(syn_cash, bil.index))
    cc1 = float((bond["exact"] - bond["dc"]).abs().loc[W1[0]:W1[1]].mean())
    chk = w1["checks"]
    add("W1: days", w1["statistics"]["IEF"]["days"], s1["days"], 0, "{:d}")
    add("W1: first/last return date", f"{w1['statistics']['IEF']['first_return_date']}..{w1['statistics']['IEF']['last_return_date']}", f"{s1['first']}..{s1['last']}")
    add("W1: A1 correlation", chk["A1"]["value"], s1["corr"], 1e-9, "{:.6f}")
    add("W1: A2 OLS slope", chk["A2"]["value"], s1["slope"], 1e-9, "{:.6f}")
    add("W1: A3 tracking error p.a.", chk["A3"]["value"], s1["te"], 1e-9, "{:.6%}")
    add("W1: A4 mean difference p.a.", chk["A4"]["value"], s1["mean"], 1e-9, "{:+.6%}")
    add("W1: B1 mean difference p.a. (BIL - cash)", chk["B1"]["value"], b1["mean"], 1e-9, "{:+.6%}")
    add("W1: B2 tracking error p.a. (BIL vs cash)", chk["B2"]["value"], b1["te"], 1e-9, "{:.6%}")
    add("W1: cross-check mean abs error", w1["duration_convexity_crosscheck_mean_abs_error"], cc1, 1e-12, "{:.3e}")
    for y in ("2016", "2017", "2018"):
        add(f"W1: D1 observed gap {y} p.a.", w1["D1_by_year_descriptive"][y]["observed_mean_diff_annual"], s1["by_year"][y], 1e-9, "{:+.6%}")
    flags1 = {"A1": s1["corr"] >= 0.95, "A2": 0.80 <= s1["slope"] <= 1.05, "A3": s1["te"] <= 0.015,
              "A4": -0.0025 <= s1["mean"] <= 0.0035, "B1": abs(b1["mean"]) <= 0.003, "B2": b1["te"] <= 0.005}
    for k, v in flags1.items():
        add(f"W1: {k} pass flag", chk[k]["pass"], bool(v))
    add("W1: all_pass", w1["all_pass"], all(flags1.values()))

    # ---- window 2 (§5.3.4 step 3)
    w2 = json.loads((VAL / "window2" / "validation.json").read_text(encoding="utf-8"))
    close = tii.loc[W2[0]:W2[1]]
    s2 = stats(close.pct_change().dropna(), onto(syn, close.index))
    cc2 = float((bond["exact"] - bond["dc"]).abs().loc[W2[0]:W2[1]].mean())
    chk = w2["checks"]
    add("W2: days", w2["statistics"]["IEF"]["days"], s2["days"], 0, "{:d}")
    add("W2: first/last return date", f"{w2['statistics']['IEF']['first_return_date']}..{w2['statistics']['IEF']['last_return_date']}", f"{s2['first']}..{s2['last']}")
    add("W2: A1 correlation", chk["A1"]["value"], s2["corr"], 1e-9, "{:.6f}")
    add("W2: A2 OLS slope", chk["A2"]["value"], s2["slope"], 1e-9, "{:.6f}")
    add("W2: A3 tracking error p.a.", chk["A3"]["value"], s2["te"], 1e-9, "{:.6%}")
    add("W2: A4 mean difference p.a.", chk["A4"]["value"], s2["mean"], 1e-9, "{:+.6%}")
    add("W2: cross-check mean abs error", w2["duration_convexity_crosscheck_mean_abs_error"], cc2, 1e-12, "{:.3e}")
    for y, v in w2["statistics"]["IEF"]["mean_diff_annual_by_year"].items():
        add(f"W2: mean difference {y} p.a.", v, s2["by_year"][y], 1e-9, "{:+.6%}")
    flags2 = {"A1": s2["corr"] >= 0.95, "A2": 0.80 <= s2["slope"] <= 1.05, "A3": s2["te"] <= 0.015, "A4": -0.0045 <= s2["mean"] <= 0.0035}
    for k, v in flags2.items():
        add(f"W2: {k} pass flag", chk[k]["pass"], bool(v))
    add("W2: all_pass", w2["all_pass"], all(flags2.values()))
    summ = json.loads((VAL / "validation.json").read_text(encoding="utf-8"))
    add("summary: all_pass", summ["all_pass"], all(flags1.values()) and all(flags2.values()))
    add("summary: window2 included", summ["window2"]["included"], True)
    add("cross-checks within 0.5 bp (both windows)", True, bool(cc1 <= 5e-5 and cc2 <= 5e-5))

    # ---- README rounded table and prose
    R = [("README W1 A1", 0.970, s1["corr"], 5e-4, "{:.3f}"), ("README W1 A2", 0.940, s1["slope"], 5e-4, "{:.3f}"),
         ("README W1 A3", 0.01159, s1["te"], 5e-6, "{:.3%}"), ("README W1 A4", 0.00100, s1["mean"], 5e-6, "{:+.3%}"),
         ("README W1 B1", -0.00110, b1["mean"], 5e-6, "{:+.3%}"), ("README W1 B2", 0.00288, b1["te"], 5e-6, "{:.3%}"),
         ("README W1 D1 2016 (-0.06%)", -0.0006, s1["by_year"]["2016"], 5e-5, "{:+.2%}"),
         ("README W1 D1 2017 (+0.15%)", 0.0015, s1["by_year"]["2017"], 5e-5, "{:+.2%}"),
         ("README W1 D1 2018 (+0.22%)", 0.0022, s1["by_year"]["2018"], 5e-5, "{:+.2%}"),
         ("README W2 A1", 0.960, s2["corr"], 5e-4, "{:.3f}"), ("README W2 A2", 0.926, s2["slope"], 5e-4, "{:.3f}"),
         ("README W2 A3", 0.02016, s2["te"], 5e-6, "{:.3%}"), ("README W2 A4", -0.00008, s2["mean"], 5e-6, "{:+.3%}"),
         ("README cross-check W1 (0.010 bp)", 0.010, cc1 * 1e4, 5e-4, "{:.3f}"), ("README cross-check W2 (0.013 bp)", 0.013, cc2 * 1e4, 5e-4, "{:.3f}"),
         ("README: vendors' tracking error 0.13% p.a.", 0.0013, float(d.std(ddof=1) * math.sqrt(252)), 5e-5, "{:.2%}")]
    for claim, pub, rec, tol, fmt in R:
        add(claim, pub, rec, tol, fmt)

    # ---- post-hoc by-year table (descriptive; posthoc_by_year.md) from the same window-2 series
    ph = {"2003": (251, 0.0202, 0.967, 0.904, 0.074, 0.079), "2004": (252, 0.0163, 0.969, 0.948, 0.065, 0.066),
          "2005": (252, 0.0137, 0.964, 0.947, 0.050, 0.051), "2006": (251, 0.0142, 0.944, 0.953, 0.043, 0.042),
          "2007": (251, 0.0223, 0.934, 0.897, 0.060, 0.062), "2008": (253, 0.0356, 0.945, 0.859, 0.098, 0.108),
          "2009": (252, 0.0250, 0.972, 0.889, 0.095, 0.103), "2010": (252, 0.0160, 0.979, 0.957, 0.077, 0.078),
          "2011": (252, 0.0281, 0.940, 0.983, 0.082, 0.078), "2012": (250, 0.0136, 0.970, 0.971, 0.056, 0.055),
          "2013": (252, 0.0151, 0.970, 0.994, 0.062, 0.060), "2014": (252, 0.0136, 0.962, 0.982, 0.049, 0.048),
          "2015": (252, 0.0142, 0.977, 0.970, 0.066, 0.067)}
    fr = s2["frame"]
    for y, (n, te, corr, slope, ve, vs) in ph.items():
        g = stats(fr.loc[y, "e"], fr.loc[y, "s"])
        ok = (g["days"] == n and abs(g["te"] - te) <= 5e-5 and abs(g["corr"] - corr) <= 5e-4 and abs(g["slope"] - slope) <= 5e-4
              and abs(g["vol_e"] - ve) <= 5e-4 and abs(g["vol_s"] - vs) <= 5e-4)
        rows.append((f"posthoc {y}: days, TE, corr, slope, IEF vol, syn vol", f"{n}, {te:.2%}, {corr:.3f}, {slope:.3f}, {ve:.1%}, {vs:.1%}",
                     f"{g['days']}, {g['te']:.2%}, {g['corr']:.3f}, {g['slope']:.3f}, {g['vol_e']:.1%}, {g['vol_s']:.1%}", "yes" if ok else "NO"))
    ex = fr[~fr.index.year.isin([2008, 2009])]
    g = stats(ex["e"], ex["s"])
    add("posthoc: window 2 without 2008-2009, days", 2767, g["days"], 0, "{:d}")
    add("posthoc: window 2 without 2008-2009, tracking error (1.76%)", 0.0176, g["te"], 5e-5, "{:.2%}")
    add("posthoc: window 2 without 2008-2009, correlation (0.962)", 0.962, g["corr"], 5e-4, "{:.3f}")
    add("posthoc: W2 IEF vol / synthetic vol (6.9% / 7.2%)", "6.9%/7.2%", f"{s2['vol_e']:.1%}/{s2['vol_s']:.1%}")
    add("posthoc: W1 IEF vol / synthetic vol (4.6% / 4.7%)", "4.6%/4.7%", f"{s1['vol_e']:.1%}/{s1['vol_s']:.1%}")
    add("posthoc: days with |gap| > 50 bp (17)", 17, int((s2["diff"].abs() > 0.005).sum()), 0, "{:d}")
    add("posthoc: days with |gap| > 100 bp (3)", 3, int((s2["diff"].abs() > 0.01).sum()), 0, "{:d}")
    top = s2["diff"].abs().nlargest(6)
    add("posthoc: six largest gaps (dates)", "2011-08-10,2011-08-09,2011-10-10,2009-02-26,2008-10-10,2008-10-14", ",".join(x.strftime("%Y-%m-%d") for x in top.index))
    add("posthoc: six largest gaps (bp)", "116,107,105,97,93,92", ",".join(f"{v * 1e4:.0f}" for v in top.values))
    oct08 = s2["diff"].loc["2008-10"].abs().nlargest(4)
    rows.append(("README: 'three days in October 2008' among the ~90-115 bp gaps; four largest October 2008 gaps (bp)", "3 days of 90-115 bp",
                 ", ".join(f"{d_:%Y-%m-%d} {v * 1e4:.0f}" for d_, v in oct08.items()), "informational (README wording)"))

    # ---- §5.3.1 ex-ante yield-only quantities (exante_bias.py output as printed in §5.3.5), reviewer's own code
    printed = {"W1": ("2016-01-04", "2018-12-31", 749, 2.214, 2.359, 2.286, 14.4, 2, 28, 0.000, 7.69, 0.373, 2.15, 2.64, 16.4, 0.066),
               "W2": ("2003-01-02", "2015-12-31", 3254, 2.967, 3.366, 3.166, 40.0, -2, 82, 0.004, 7.41, 1.002, 3.85, 2.18, -12.8, -0.051),
               "IS": ("1969-07-01", "2018-12-31", 12364, 6.255, 6.413, 6.334, 15.8, -52, 82, 0.210, 6.57, 0.383, 6.81, 2.64, -8.4, None)}
    for name, (a, b, nobs, m7, m10, m85, sp, spmin, spmax, neg, dm, roll, y0, y1, dy, mism) in printed.items():
        w = both.loc[a:b]
        y85 = (w["y7"] + w["y10"]) / 2.0
        dmod = dmod_conv(y85.values, M0)[0]
        spread = w["y10"] - w["y7"]
        years = (w.index[-1] - w.index[0]).days / 365.0
        dy_py = (y85.iloc[-1] - y85.iloc[0]) / years
        add(f"ex-ante {name}: observations", nobs, len(w), 0, "{:d}")
        add(f"ex-ante {name}: mean 7y / 10y / 8.5y yields (%)", f"{m7:.3f}/{m10:.3f}/{m85:.3f}", f"{w['y7'].mean() * 100:.3f}/{w['y10'].mean() * 100:.3f}/{y85.mean() * 100:.3f}")
        add(f"ex-ante {name}: 10y-7y spread mean / min / max (bp), share negative", f"{sp:.1f}/{spmin:.0f}/{spmax:.0f}, {neg:.3f}",
            f"{spread.mean() * 1e4:.1f}/{spread.min() * 1e4:.0f}/{spread.max() * 1e4:.0f}, {(spread < 0).mean():.3f}")
        add(f"ex-ante {name}: mean D_mod of the 8.5y par bond (years)", dm, float(dmod.mean()), 5e-3, "{:.2f}")
        add(f"ex-ante {name}: roll-down estimate D_mod x spread/3 (% p.a.)", roll, float((dmod * spread.values / 3.0).mean() * 100), 5e-4, "{:.3f}")
        add(f"ex-ante {name}: 8.5y yield at the start (%)", y0, float(y85.iloc[0] * 100), 5.1e-3, "{:.3f}", note="printed to 2 d.p.; W2 and IS start on an exact .xx5")
        add(f"ex-ante {name}: 8.5y yield at the end (%)", y1, float(y85.iloc[-1] * 100), 5.1e-3, "{:.3f}")
        add(f"ex-ante {name}: 8.5y yield change (bp per year)", dy, float(dy_py * 1e4), 0.051, "{:+.2f}")
        if mism is not None:
            add(f"ex-ante {name}: duration-mismatch term 0.40 x dy (% p.a.)", mism, float(0.40 * dy_py * 100), 5e-4, "{:+.3f}")
        if name == "W1":
            for yr, (spy, ry) in {"2016": (20.3, 0.533), "2017": (17.1, 0.438), "2018": (5.9, 0.147)}.items():
                ww = w.loc[yr]
                yy = ((ww["y7"] + ww["y10"]) / 2.0).values
                add(f"ex-ante W1 {yr}: spread (bp), roll-down (% p.a.)", f"{spy:.1f}, {ry:.3f}",
                    f"{(ww['y10'] - ww['y7']).mean() * 1e4:.1f}, {(dmod_conv(yy, M0)[0] * (ww['y10'] - ww['y7']).values / 3.0).mean() * 100:.3f}")
    # threshold rule (§5.3.2) applied by the reviewer to the §5.3.1 table as written
    comp = {"W1": {"signed": [0, 0, 0.07, 0, 0.02, 0, -0.03, 0, 0], "ranges": [0, 0.06, 0.03, 0.01, 0.025, 0.05, 0.03, 0.05, 0.03]},
            "W2": {"signed": [0, 0, -0.05, 0, 0.02, 0, -0.03, 0, 0], "ranges": [0, 0.15, 0.03, 0.01, 0.025, 0.08, 0.03, 0.02, 0.03]}}
    for name, (centre, width, lo, hi) in {"W1": (0.06, 0.285, -0.0025, 0.0035), "W2": (-0.06, 0.375, -0.0045, 0.0035)}.items():
        c, s = sum(comp[name]["signed"]), sum(comp[name]["ranges"])
        add(f"§5.3.1 {name}: central estimate, sum of signed terms (table: {centre:+.2f})", centre, c, 1e-9, "{:+.3f}")
        add(f"§5.3.1 {name}: sum of absolute ranges (table prints {round(width + 1e-9, 2):.2f}; component 5 '0 to +0.05' read as +/-0.025)", width, s, 1e-9, "{:.3f}")
        cr = round(c * 20) / 20                     # 'rounded to 0.05' as the table states
        wr = math.ceil(s * 20 - 1e-9) / 20          # 'rounded up to 0.05'
        add(f"§5.3.2 {name}: A4 band = centre +/- width after rounding", f"[{lo:+.4f}, {hi:+.4f}]", f"[{(cr - wr) / 100:+.4f}, {(cr + wr) / 100:+.4f}]")
    add("§5.3.2: A1-A3 and B1-B2 thresholds equal Study 001's (0.95; [0.80, 1.05]; 1.5%; 0.30%; 0.50%)", True,
        bool(w1["checks"]["A1"]["threshold"] == ">= 0.95" and w1["checks"]["A2"]["threshold"] == "in [0.8, 1.05]"
             and w1["checks"]["A3"]["threshold"] == "<= 0.015" and w1["checks"]["B1"]["threshold"] == "within +/-0.003"
             and w1["checks"]["B2"]["threshold"] == "<= 0.005" and w2["checks"]["A3"]["threshold"] == "<= 0.015"))

    print("| # | Claim | Published | Recomputed | Match |")
    print("|---|---|---|---|---|")
    for i, (c, p, r, m) in enumerate(rows, 1):
        print(f"| {i} | {c} | {p} | {r} | {m} |")
    n_yes = sum(1 for r in rows if r[3].startswith("yes"))
    n_no = sum(1 for r in rows if r[3].startswith("NO"))
    print(f"\nRows: {len(rows)}; match: {n_yes}; mismatch: {n_no}; informational/not checked: {len(rows) - n_yes - n_no}")
    return 1 if n_no else 0


if __name__ == "__main__":
    sys.exit(main())
