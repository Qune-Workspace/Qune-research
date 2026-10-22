"""Independent recomputation for REVIEW.md (Study 001, term-spread duration switch, halted at §5.3).

Written by the reviewer (Tester, a separate agent session that did not write the
code).  It imports nothing from the study's ``src/``: both synthetic constructions
(the original 10-year par bond of §5.2 and the 7/10-year blend of the §16 decision),
the cash leg, the duration/convexity cross-check and the §5.3 statistics A1-A4 and
B1-B2 are re-derived with numpy and pandas only from the git-ignored raw files in
``data/raw/`` (``fred_DGS10.csv``, ``fred_DGS7.csv``, ``fred_DTB3.csv``,
``alpaca_IEF_1Day_all.csv``, ``alpaca_BIL_1Day_all.csv``), whose SHA-256 are checked
against ``results/data_manifest.json`` first.

It prints a comparison table (claim | published | recomputed | match).  Published
values are read from ``results/validation/run1-ten-year-only/validation.json`` (run 1)
and ``results/validation/validation.json`` (run 2) at full precision; numbers that
exist only in README.md are typed in below and marked README.  Nothing is written
to disk.  No return of any rule or benchmark is computed; nothing after 2018-12-31
is read except the row count of the dates-only execution calendar.

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
START, END = "2016-01-04", "2018-12-31"
IEF_FEE, BIL_FEE = 0.0015, 0.001356
TH = {"A1": 0.95, "A2": (0.80, 1.05), "A3": 0.015, "A4": 0.0040, "B1": 0.0030, "B2": 0.0050}   # §5.3

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
    return v.dropna() / 100.0          # decimal yields, valid observations only


def alpaca(symbol: str) -> pd.Series:
    df = pd.read_csv(RAW / f"alpaca_{symbol}_1Day_all.csv", parse_dates=["date"]).set_index("date").sort_index()
    return df["close"].astype(float)


# ----------------------------------------------------------------------------- bond arithmetic (reviewer's own)
def par_price(c: np.ndarray, y: np.ndarray, m: int) -> np.ndarray:
    """Price per 100 of a bond with annual coupon c paid semi-annually, m periods, yield y (§5.2)."""
    i = y / 2.0
    disc = (1.0 + i) ** (-m)
    ann = np.where(i == 0, float(m), (1.0 - disc) / np.where(i == 0, 1.0, i))
    return 100.0 * (c / 2.0) * ann + 100.0 * disc


def dmod_conv(y: np.ndarray, m: int) -> tuple[np.ndarray, np.ndarray]:
    """Modified duration (years) and convexity (years^2) of a par bond at yield y from the cash flows."""
    i = y[:, None] / 2.0
    k = np.arange(1, m + 1, dtype=float)[None, :]
    cf = np.full((len(y), m), 1.0) * (y[:, None] / 2.0 * 100.0)
    cf[:, -1] += 100.0
    v = 1.0 / (1.0 + i)
    p = (cf * v ** k).sum(axis=1)
    d = (k * cf * v ** (k + 1)).sum(axis=1) / p / 2.0
    c = (k * (k + 1) * cf * v ** (k + 2)).sum(axis=1) / p / 4.0
    return d, c


def par_bond_leg(y: pd.Series, m: int, fee: float) -> pd.DataFrame:
    """§5.2 duration leg on the valid observations of one yield series: exact repricing of a
    par bond bought at y_s, sold at y_t after `days` calendar days, plus carry, minus fee."""
    ys, yt = y.values[:-1], y.values[1:]
    days = np.diff(y.index.values).astype("timedelta64[D]").astype(float)
    carry = (ys - fee) * days / 365.0
    exact = par_price(ys, yt, m) / 100.0 - 1.0 + carry
    d, c = dmod_conv(ys, m)
    dy = yt - ys
    dc = carry - d * dy + 0.5 * c * dy ** 2
    return pd.DataFrame({"exact": exact, "dc": dc}, index=y.index[1:])


def cash_leg(dtb3: pd.Series) -> pd.Series:
    d = dtb3.values[:-1]
    bey = 365.0 * d / (360.0 - 91.0 * d)
    days = np.diff(dtb3.index.values).astype("timedelta64[D]").astype(float)
    return pd.Series((bey - BIL_FEE) * days / 365.0, index=dtb3.index[1:])


def tri(returns: pd.Series, base_date) -> pd.Series:
    out = (1.0 + returns).cumprod()
    return pd.concat([pd.Series([1.0], index=pd.DatetimeIndex([base_date])), out])


def stats(etf_r: pd.Series, syn_r: pd.Series) -> dict:
    f = pd.concat([etf_r.rename("e"), syn_r.rename("s")], axis=1).dropna()
    diff = f["e"] - f["s"]
    slope = np.cov(f["s"], f["e"], ddof=1)[0, 1] / np.var(f["s"], ddof=1)
    return {"days": len(f), "corr": float(f["e"].corr(f["s"])), "slope": float(slope),
            "te": float(diff.std(ddof=1) * math.sqrt(252)), "mean": float(diff.mean() * 252),
            "by_year": {str(y): float(g.mean() * 252) for y, g in diff.groupby(diff.index.year)}, "diff": diff}


def onto(index: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    """Synthetic index taken as of each ETF date (last observation on or before), then simple returns."""
    return index.reindex(dates, method="ffill").pct_change().dropna()


# ----------------------------------------------------------------------------- main
def main() -> int:
    manifest = json.loads((RES / "data_manifest.json").read_text(encoding="utf-8"))
    for name, entry in manifest.items():
        p = RAW / name
        if not p.exists():
            rows.append((f"manifest SHA-256 {name}", entry["sha256"][:12], "absent", "not checked (file missing)"))
            continue
        add(f"manifest SHA-256 {name}", entry["sha256"], sha256(p))
        if "rows" in entry:
            n = sum(1 for _ in open(p, "rb")) - 1
            add(f"manifest row count {name}", entry["rows"], n, 0, "{:d}")

    dgs10, dgs7, dtb3 = fred("DGS10"), fred("DGS7"), fred("DTB3")
    both = pd.concat([dgs7.rename("y7"), dgs10.rename("y10")], axis=1).dropna()
    both = both.loc[both.index >= "1969-07-01"]
    add("DGS7 and DGS10 observed on the same dates from 1969-07-01 (README note 7)", True,
        bool(len(both) == len(dgs7) and len(dgs10.loc["1969-07-01":]) == len(both)))

    # construction 1: 10-year par bond alone (§5.2 as pre-registered) -> run 1
    ten = par_bond_leg(dgs10, 20, IEF_FEE)
    # construction 2: equal-weight 7/10-year blend on the common calendar (§16 decision) -> run 2
    seven_b = par_bond_leg(both["y7"], 14, IEF_FEE)
    ten_b = par_bond_leg(both["y10"], 20, IEF_FEE)
    blend = pd.DataFrame({"exact": 0.5 * seven_b["exact"] + 0.5 * ten_b["exact"],
                          "dc": 0.5 * seven_b["dc"] + 0.5 * ten_b["dc"]})
    cash = cash_leg(dtb3)
    idx = {"run1": tri(ten["exact"], dgs10.index[0]), "run2": tri(blend["exact"], both.index[0]),
           "cash": tri(cash, dtb3.index[0])}

    ief, bil = alpaca("IEF").loc[START:END], alpaca("BIL").loc[START:END]
    ief_r, bil_r = ief.pct_change().dropna(), bil.pct_change().dropna()
    published = {"run1": json.loads((RES / "validation" / "run1-ten-year-only" / "validation.json").read_text()),
                 "run2": json.loads((RES / "validation" / "validation.json").read_text())}
    readme = {"run1": {"A1": 0.966, "A2": 0.821, "A3": 0.01540, "A4": 0.00455, "B1": -0.00110, "B2": 0.00288},
              "run2": {"A1": 0.970, "A2": 0.946, "A3": 0.01145, "A4": 0.00451, "B1": -0.00110, "B2": 0.00288}}
    out = {}
    for run, label, series in (("run1", "run 1 (10-year alone)", ten), ("run2", "run 2 (7/10 blend)", blend)):
        pub = published[run]
        s_ief = stats(ief_r, onto(idx[run], ief.index))
        s_bil = stats(bil_r, onto(idx["cash"], bil.index))
        out[run] = s_ief
        add(f"{label}: window start/end", f"{pub['window']['start']}..{pub['window']['end']}", f"{START}..{END}")
        add(f"{label}: common return days IEF", pub["statistics"]["IEF"]["days"], s_ief["days"], 0, "{:d}")
        add(f"{label}: A1 correlation", pub["checks"]["A1"]["value"], s_ief["corr"], 1e-9, "{:.6f}")
        add(f"{label}: A2 OLS slope", pub["checks"]["A2"]["value"], s_ief["slope"], 1e-9, "{:.6f}")
        add(f"{label}: A3 tracking error p.a.", pub["checks"]["A3"]["value"], s_ief["te"], 1e-9, "{:.6%}")
        add(f"{label}: A4 mean difference p.a.", pub["checks"]["A4"]["value"], s_ief["mean"], 1e-9, "{:+.6%}")
        add(f"{label}: B1 mean difference p.a. (BIL - cash)", pub["checks"]["B1"]["value"], s_bil["mean"], 1e-9, "{:+.6%}")
        add(f"{label}: B2 tracking error p.a. (BIL vs cash)", pub["checks"]["B2"]["value"], s_bil["te"], 1e-9, "{:.6%}")
        cc = float((series["exact"] - series["dc"]).abs().loc[START:END].mean())
        add(f"{label}: duration/convexity cross-check mean abs error", pub["duration_convexity_crosscheck_mean_abs_error"], cc, 1e-12, "{:.3e}")
        # pass/fail flags applied by the reviewer from the §5.3 thresholds
        flags = {"A1": s_ief["corr"] >= TH["A1"], "A2": TH["A2"][0] <= s_ief["slope"] <= TH["A2"][1],
                 "A3": s_ief["te"] <= TH["A3"], "A4": abs(s_ief["mean"]) <= TH["A4"],
                 "B1": abs(s_bil["mean"]) <= TH["B1"], "B2": s_bil["te"] <= TH["B2"]}
        for k, v in flags.items():
            add(f"{label}: {k} pass flag", pub["checks"][k]["pass"], bool(v))
        add(f"{label}: all_pass", pub["all_pass"], all(flags.values()))
        add(f"{label}: cross-check within 0.5 bp", True, bool(cc <= 5e-5))
        # README table (rounded)
        r = readme[run]
        add(f"{label}: README A1", r["A1"], s_ief["corr"], 5e-4, "{:.3f}")
        add(f"{label}: README A2", r["A2"], s_ief["slope"], 5e-4, "{:.3f}")
        add(f"{label}: README A3", r["A3"], s_ief["te"], 5e-6, "{:.3%}")
        add(f"{label}: README A4", r["A4"], s_ief["mean"], 5e-6, "{:+.3%}")
        add(f"{label}: README B1", r["B1"], s_bil["mean"], 5e-6, "{:+.3%}")
        add(f"{label}: README B2", r["B2"], s_bil["te"], 5e-6, "{:.3%}")
    # README reading-of-the-failure numbers (run 2 by year; roll-down back-of-envelope)
    for y, v in (("2016", 0.0047), ("2017", 0.0050), ("2018", 0.0038)):
        add(f"README: run 2 IEF - synthetic in {y} (% p.a.)", v, out["run2"]["by_year"][y], 5e-5, "{:+.4%}")
    add("README: A2 run 1 passed by 0.02", 0.02, out["run1"]["slope"] - 0.80, 5e-3, "{:.3f}")
    w = both.loc[START:END]
    spread = (w["y10"] - w["y7"]).mean()
    add("README: mean 10y-7y spread over the window (14 bp)", 0.0014, spread, 5e-5, "{:.2%}")
    d10 = dmod_conv(np.array([w["y10"].mean()]), 20)[0][0]
    d7 = dmod_conv(np.array([w["y7"].mean()]), 14)[0][0]
    add("README: roll-down estimate 10-year leg D_mod x spread/3 (0.43% p.a.)", 0.0043, d10 * spread / 3, 5e-4, "{:.2%}", note="README's rounding; reviewer at mean yields")
    add("README: roll-down estimate 7-year leg (0.31% p.a.)", 0.0031, d7 * spread / 3, 5e-4, "{:.2%}")
    add("README: roll-down estimate blend (0.37% p.a.)", 0.0037, 0.5 * (d10 + d7) * spread / 3, 5e-4, "{:.2%}")
    # dates-only execution calendar (no return): holding-period counts quoted in the README
    cal = pd.read_csv(RES / "execution_calendar.csv")
    hp = cal["period_end"].notna()      # the last signal row of each window starts no holding period inside it
    add("README: execution calendar in-sample holding periods (593, from the 1969-07 signal month)", 593, int(((cal["window"] == "insample") & hp).sum()), 0, "{:d}")
    add("README: execution calendar out-of-sample holding periods (93)", 93, int(((cal["window"] == "oos") & hp).sum()), 0, "{:d}")
    add("execution calendar first in-sample signal month is 1969-07 (§16 decision)", "1969-07", str(cal.loc[cal["window"] == "insample", "month"].iloc[0]))
    add("execution calendar last out-of-sample signal month is 2026-09 (§8.2)", "2026-09", str(cal.loc[cal["window"] == "oos", "month"].iloc[-1]))

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
