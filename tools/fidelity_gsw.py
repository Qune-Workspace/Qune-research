"""Cold-read point 3, 1983-2002: the synthetic 7-10-year leg against an independent curve.

No readable independent total-return series covers 1983-2002 (COLD_READ.md,
point 3). This check reprices the same instrument, an ageing 8.5-year par bond
bought fresh on every observation day, on a curve the leg does not use:

    Federal Reserve Board, nominal yield curve, feds200628.csv (Svensson /
    Nelson-Siegel parameters, daily from 1961). Gurkaynak, R.S., Sack, B. and
    Wright, J.H. (2007), "The U.S. Treasury yield curve: 1961 to the present",
    Journal of Monetary Economics 54, 2291-2304. Public domain per the Board's
    website notice; cited as the Board asks.

The Board fits it to off-the-run Treasury notes and bonds only (no bills, no
on-the-run or first-off-the-run issues), while the leg interpolates FRED's
constant-maturity DGS7 and DGS10. So this measures the leg's YIELD INPUTS AND
INTERPOLATION against an independent curve. It does not measure the leg's
construction (one constant-maturity par bond versus a basket of real issues);
the calibration block says how much of the 1969-1982 failure against
Stocker (2025) that leaves out. Specified in COLD_READ.md (dated addition
2026-10-28, point 3) and committed before the file was fetched.

Twin construction (daily, between consecutive valid days s and t, yf = calendar
days / 365): at s, par coupon c with semi-annual payments at 0.5k years, k = 1..17,
c = 2 (1 - D_s(8.5)) / sum_k D_s(0.5k); at t the same cash flows, now 0.5k - yf
years away, are priced on D_t: P_t = c/2 sum_k D_t(0.5k - yf) + D_t(8.5 - yf);
r = P_t - 1 - 0.0015 yf (the leg's IEF expense ratio). D(n) = exp(-z(n) n), z the
Svensson zero yield (continuously compounded), BETA3 = 0 on Nelson-Siegel days.
A day is valid only when the Board reports SVENY09 (so 8.5 years lies inside the
fitted maturities). A study period's twin return is I(P) / I(E) - 1 with E, P
its execution_date and period_end, each read at the last valid day on or before.

Reported, for 006, 007, 008 (no decision weight; no verdict changes either way):
  A. calibration, first valid month to 1982-10: twin vs Stocker 5-10y and leg vs
     Stocker over the identical months (mean gap x 12, signed G1-style);
     share = signed G1(twin vs Stocker) / signed G1(leg vs Stocker).
  B. PRIMARY, execution months 1983-01..2002-12: g = B1 - twin; mean x 12,
     sd x sqrt(12), corr(B1, twin), G2-style sd(g) / sd(twin - B0),
     G1-style |mean((h - w) g)| x 12 (bounds 0.32 and 0.18% from the gates).
  C. descriptive, 2003-01 to each study's last month: the same figures where
     the gates already validated the leg against IEF (the noise scale).
  Calendar-year returns, 006, 1983-2002.

Usage: python tools/fidelity_gsw.py [--fetch]   (writes tools/fidelity_gsw.txt)
"""
from __future__ import annotations

import argparse
import bisect
import csv
import datetime as dt
import hashlib
import math
import statistics as st
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fidelity_stocker as fs  # noqa: E402  (same folder; reuses the Stocker reader and study files)

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "tools" / "data" / "raw" / "gsw"
FILE = RAW / "feds200628.csv"
URL = "https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv"
OUT = ROOT / "tools" / "fidelity_gsw.txt"
EXPENSE = 0.0015          # IEF expense ratio used by the leg (006 src/config.py)
BOND_YEARS, N_COUPONS = 8.5, 17
WINDOW_B = ("1983-01", "2002-12")
WINDOW_C_START = "2003-01"
STOCKER_LAST = "1982-10"
SHARE_RULE = 0.5


def fetch() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    if not FILE.exists():
        req = urllib.request.Request(URL, headers={"User-Agent": "qune-research/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            FILE.write_bytes(r.read())


def num(text: str) -> float:
    try:
        return float(text)
    except ValueError:
        return float("nan")


def read_gsw(path: Path) -> list[tuple[dt.date, tuple[float, ...]]]:
    """Rows (date, (b0, b1, b2, b3, tau1, tau2)) on valid days, sorted. The file opens
    with a text preamble; the data header is the first line that starts with 'Date'."""
    lines = path.read_text().splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("Date"))
    reader = csv.DictReader(lines[start:])
    out = []
    for r in reader:
        if math.isnan(num(r.get("SVENY09", ""))):
            continue
        b0, b1, b2, b3 = (num(r[k]) for k in ("BETA0", "BETA1", "BETA2", "BETA3"))
        t1, t2 = num(r["TAU1"]), num(r["TAU2"])
        if any(math.isnan(v) for v in (b0, b1, b2, t1)):
            continue
        if math.isnan(b3) or math.isnan(t2):
            b3, t2 = 0.0, 1.0          # Nelson-Siegel day
        out.append((dt.date.fromisoformat(r["Date"]), (b0, b1, b2, b3, t1, t2)))
    out.sort()
    return out


def discount(p: tuple[float, ...], n: float) -> float:
    b0, b1, b2, b3, t1, t2 = p
    a1, a2 = n / t1, n / t2
    f1 = (1 - math.exp(-a1)) / a1
    f2 = (1 - math.exp(-a2)) / a2
    z = b0 + b1 * f1 + b2 * (f1 - math.exp(-a1)) + b3 * (f2 - math.exp(-a2))
    return math.exp(-z / 100.0 * n)


def twin_index(rows) -> tuple[list[dt.date], list[float]]:
    dates, idx = [rows[0][0]], [1.0]
    times = [0.5 * k for k in range(1, N_COUPONS + 1)]
    for (s, ps), (t, pt) in zip(rows[:-1], rows[1:], strict=True):
        yf = (t - s).days / 365.0
        c = 2 * (1 - discount(ps, BOND_YEARS)) / sum(discount(ps, x) for x in times)
        price = c / 2 * sum(discount(pt, x - yf) for x in times) + discount(pt, BOND_YEARS - yf)
        dates.append(t)
        idx.append(idx[-1] * (price - EXPENSE * yf))
    return dates, idx


def at(dates, idx, day: dt.date) -> float | None:
    i = bisect.bisect_right(dates, day) - 1
    return idx[i] if i >= 0 else None


def twin_periods(sid: str, dates, idx) -> dict[str, tuple[float, dict[str, str]]]:
    out = {}
    for r in fs.read_study(sid):
        e, p = dt.date.fromisoformat(r["execution_date"]), dt.date.fromisoformat(r["period_end"])
        if e < dates[0]:
            continue
        ie, ip = at(dates, idx, e), at(dates, idx, p)
        out[r["execution_date"][:7]] = (ip / ie - 1, r)
    return out


def stats(sid: str, items: list[tuple[float, float, float, dict[str, str]]], n_full: int) -> dict:
    """items: (leg return, comparison return, bill return, study row)."""
    g = [a - b for a, b, _, _ in items]
    x = [b - c for _, b, c, _ in items]
    hs = [fs.weight(sid, r) for *_, r in items]
    w = sum(hs) / len(hs)
    e = [(h - w) * gg for h, gg in zip(hs, g, strict=True)]
    return {"n": len(items), "w": w, "mean_g": st.mean(g) * 12, "sd_g": st.stdev(g) * math.sqrt(12),
            "corr": st.correlation([a for a, *_ in items], [b for _, b, *_ in items]),
            "g2": st.stdev(g) / st.stdev(x), "g1": abs(st.mean(e)) * 12, "e": st.mean(e) * 12,
            "full": st.mean(e) * 12 * len(e) / n_full}


def fmt(c: dict) -> str:
    return (f"n={c['n']}  mean(g)x12 {c['mean_g']:+.3%}  sd(g)xsqrt12 {c['sd_g']:.3%}  corr {c['corr']:.3f}  "
            f"G2-style {c['g2']:.3f} (bound {fs.G2_BOUND})  G1-style {c['g1']:.3%} (bound {fs.G1_BOUND:.2%}, "
            f"w {c['w']:.4f}; signed {c['e']:+.3%}, + = the leg flatters T1 - B3; over the full window "
            f"{c['full']:+.3%} a year if the other periods had none)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    args = ap.parse_args()
    if args.fetch:
        fetch()
    rows = read_gsw(FILE)
    dates, idx = twin_index(rows)
    stk = fs.read_stocker(fs.RAW / "returns_05_10.csv")
    lines = ["Cold-read point 3, 1983-2002: synthetic leg (B1) vs a twin repriced on the Board's off-the-run curve",
             "Source: Federal Reserve Board, feds200628.csv (Gurkaynak, Sack and Wright 2007); public domain, cited.",
             "Measures yield inputs and interpolation only, not the constant-maturity construction. No decision weight.",
             "", f"feds200628.csv sha256 {hashlib.sha256(FILE.read_bytes()).hexdigest()}",
             f"valid days (SVENY09 reported): {len(rows)} ({rows[0][0]}..{rows[-1][0]})", ""]
    lines.append("A. Calibration against Stocker (2025) 5-10y, first twin month to 1982-10 "
                 f"(rule fixed in advance: share >= {SHARE_RULE} -> the twin shares most of the leg's error "
                 "against real issues, so B speaks to yield inputs only)")
    tw_all = {}
    for sid in fs.STUDIES:
        tw = twin_periods(sid, dates, idx)
        tw_all[sid] = tw
        n_full = len(fs.read_study(sid))
        months = [m for m in tw if m <= STOCKER_LAST and m in stk and not math.isnan(stk[m]["ret"])]
        legs = [(float(tw[m][1]["B1"]), stk[m]["ret"] / 100, float(tw[m][1]["B0"]), tw[m][1]) for m in months]
        twins = [(tw[m][0], stk[m]["ret"] / 100, float(tw[m][1]["B0"]), tw[m][1]) for m in months]
        a, b = stats(sid, legs, n_full), stats(sid, twins, n_full)
        share = b["e"] / a["e"] if a["e"] else float("nan")
        lines.append(f"  {sid} {months[0]}..{months[-1]}")
        lines.append(f"    leg  vs Stocker: {fmt(a)}")
        lines.append(f"    twin vs Stocker: {fmt(b)}")
        lines.append(f"    share {share:+.2f} -> {'shares most of the error' if share >= SHARE_RULE else 'does not share most of the error'}")
    for label, lo, hi in (("B. PRIMARY 1983-2002", *WINDOW_B), ("C. descriptive, ETF era (gates validated vs IEF)", WINDOW_C_START, "9999-12")):
        lines.append("")
        lines.append(f"{label}: g = B1 - twin")
        for sid in fs.STUDIES:
            tw = tw_all[sid]
            ms = [m for m in tw if lo <= m <= hi]
            items = [(float(tw[m][1]["B1"]), tw[m][0], float(tw[m][1]["B0"]), tw[m][1]) for m in ms]
            c = stats(sid, items, len(fs.read_study(sid)))
            verdict = "within both bounds" if c["g1"] <= fs.G1_BOUND and c["g2"] <= fs.G2_BOUND else "outside a bound"
            lines.append(f"  {sid} {ms[0]}..{ms[-1]} {fmt(c)} -> {verdict}")
    lines.append("")
    lines.append("Calendar years, 006 periods by execution month, 1983-2002:")
    lines.append("  year  leg        twin       gap")
    years = defaultdict(lambda: [1.0, 1.0])
    for m, (r_tw, r) in tw_all["006"].items():
        if WINDOW_B[0] <= m <= WINDOW_B[1]:
            years[m[:4]][0] *= 1 + float(r["B1"])
            years[m[:4]][1] *= 1 + r_tw
    for y, (a, b) in sorted(years.items()):
        lines.append(f"  {y} {a - 1:+9.2%} {b - 1:+9.2%} {a - b:+8.2%}")
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
