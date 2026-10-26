"""Cold-read point 3: fidelity of the synthetic 7-10-year leg before 2003.

Compares the synthetic bond leg (B1, buy and hold, in each long-history study's
committed results/history/monthly_base.csv) with an independent series built
from Treasury Bulletin bond prices, not from FRED yields:

    Stocker, A.J. (2025), "Database of US Treasury prices and returns 1942-1982",
    Mendeley Data, v1, doi:10.17632/j4c325yrgg.1, CC BY 4.0.
    Method: Stocker (2025), SSRN, doi:10.2139/ssrn.5422914.

Primary sector, chosen from the file names before any return was read: 5-10
years, AllTax (returns_05_10.csv; 8.5 years lies inside it). Secondary,
descriptive: 3-10 years. The comparison was specified in COLD_READ.md (dated
addition 2026-10-26, point 3) and committed before the files were fetched.

It carries no decision weight and changes no verdict. It reports, over the
overlap (execution months 1969-08 for 006, 1974-07 for 007/008, to the last
Stocker month):
  * the gap g_t = synthetic B1 - Stocker return, its mean x 12, sd x sqrt(12),
    and its correlation with the Stocker return;
  * G2-style ratio sd(g) / sd(x), x = Stocker - B0 (the study's synthetic bill);
  * G1-style |mean((h_t - w) g_t)| x 12 for each study's T1, h_t its weight in
    the bond, w its mean weight over the comparison months (the gates' own
    convention for sub-windows); bounds 0.18% a year and 0.32 from the gates;
  * calendar-year returns of both by execution year.
Period alignment: a study period runs from the first NYSE day of month M to the
first NYSE day of M+1; Stocker month M runs from the end of M-1 to the end of M.
They are matched on M, a one-trading-day offset that lowers the monthly
correlation and barely moves the annual figures.

Usage: python tools/fidelity_stocker.py [--fetch]   (writes tools/fidelity_stocker.txt)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import math
import statistics as st
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "tools" / "data" / "raw" / "stocker"
OUT = ROOT / "tools" / "fidelity_stocker.txt"
API = "https://data.mendeley.com/public-files/datasets/j4c325yrgg/files/{fid}/file_downloaded"
# File ids and sha256 from the public file listing (folder MonthlyData, v1), read 2026-10-26.
FILES = {
    "returns_05_10.csv": ("11aa2d75-f8e1-4ab0-83c8-90055cd609ab",
                          "0bb2e94ee5df82dc4c42e95d04965f55c3ee98f3c2e9c19bb56033a7061b44ad"),
    "returns_03_10.csv": ("5ee7f382-696e-48e2-a4a3-f1908d78ca12",
                          "987a7a1e3e85158708227665b9e17d858fbd6071f74ce4a0b560c8ba3314a748"),
}
STUDIES = {
    "006": "research/006-term-spread-switch-long-history",
    "007": "research/007-bond-carry-tilt-long-history",
    "008": "research/008-bond-value-tilt-long-history",
}
G1_BOUND, G2_BOUND = 0.0018, 0.32


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, (fid, digest) in FILES.items():
        dest = RAW / name
        if not dest.exists():
            with urllib.request.urlopen(API.format(fid=fid), timeout=60) as r:
                dest.write_bytes(r.read())
        if sha256(dest) != digest:
            sys.exit(f"hash mismatch for {name}: {sha256(dest)} != {digest}")


def parse_month(text: str) -> str:
    """Return YYYY-MM from the file's month field (accepts YYYY-MM[-DD] or a decimal year)."""
    text = text.strip()
    if len(text) >= 7 and text[4] in "-/":
        return f"{text[:4]}-{int(text[5:7]):02d}"
    raise ValueError(f"unrecognised month field: {text!r}")


def read_stocker(path: Path) -> dict[str, dict[str, float]]:
    """Columns by position, as the dataset's ReadMe lists them: month, total return (%),
    time to maturity (years), modified duration, yield to maturity (%), number of bonds.
    Lines whose first field is not a month (a header, if any) are skipped."""
    names = ["ret", "maturity", "duration", "ytm", "nbonds"]
    rows: dict[str, dict[str, float]] = {}
    with path.open(newline="") as f:
        for rec in csv.reader(f, delimiter="\t"):
            if not rec or not rec[0].strip():
                continue
            try:
                m = parse_month(rec[0])
            except ValueError:
                continue
            vals = {}
            for h, v in zip(names, rec[1:]):
                try:
                    vals[h] = float(v)
                except ValueError:
                    vals[h] = float("nan")
            rows[m] = vals
    return rows


def read_study(sid: str) -> list[dict[str, str]]:
    with (ROOT / STUDIES[sid] / "results/history/monthly_base.csv").open(newline="") as f:
        return list(csv.DictReader(f))


def weight(sid: str, row: dict[str, str]) -> float:
    if sid == "006":
        return 1.0 if row["T1_holding"] == "IEF" else 0.0
    return float(row["w_T1"])


def corr(a: list[float], b: list[float]) -> float:
    return st.correlation(a, b)


def compare(sid: str, rows: list[dict[str, str]], stk: dict[str, dict[str, float]], ret_col: str) -> dict:
    g, x, s_list, e_parts, years = [], [], [], [], defaultdict(lambda: [1.0, 1.0, 0])
    months = []
    for r in rows:
        m = r["execution_date"][:7]
        if m not in stk or math.isnan(stk[m][ret_col]):
            continue
        s = stk[m][ret_col] / 100.0
        b1, b0 = float(r["B1"]), float(r["B0"])
        months.append(m)
        g.append(b1 - s)
        x.append(s - b0)
        s_list.append(s)
        e_parts.append((weight(sid, r), b1 - s))
        y = years[m[:4]]
        y[0] *= 1 + b1
        y[1] *= 1 + s
        y[2] += 1
    w = sum(h for h, _ in e_parts) / len(e_parts)
    e = [(h - w) * gg for h, gg in e_parts]
    return {
        "first": months[0], "last": months[-1], "n": len(months), "w": w,
        "mean_g_ann": st.mean(g) * 12, "sd_g_ann": st.stdev(g) * math.sqrt(12),
        "corr_g_s": corr(g, s_list), "corr_b1_s": corr([gg + ss for gg, ss in zip(g, s_list)], s_list),
        "g2": st.stdev(g) / st.stdev(x), "g1": abs(st.mean(e)) * 12, "years": dict(years),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    args = ap.parse_args()
    if args.fetch:
        fetch()
    lines = ["Cold-read point 3: synthetic leg (B1) vs Stocker (2025) Treasury Bulletin sector returns",
             "Source: doi:10.17632/j4c325yrgg.1 (CC BY 4.0); no decision weight; verdicts unchanged.", ""]
    for name in FILES:
        path = RAW / name
        lines.append(f"{name} sha256 {sha256(path)}")
        stk = read_stocker(path)
        ret_col, dur_col = "ret", "duration"
        lines.append(f"  months parsed: {len(stk)} ({min(stk)}..{max(stk)})")
        for sid in STUDIES:
            c = compare(sid, read_study(sid), stk, ret_col)
            durs = [stk[m][dur_col] for m in stk if c["first"] <= m <= c["last"]]
            lines.append(
                f"  {sid}: {c['first']}..{c['last']} n={c['n']}  mean(g)x12 {c['mean_g_ann']:+.3%}  "
                f"sd(g)xsqrt12 {c['sd_g_ann']:.3%}  corr(B1,S) {c['corr_b1_s']:.3f}  corr(g,S) {c['corr_g_s']:+.3f}  "
                f"G2-style {c['g2']:.3f} (bound {G2_BOUND})  G1-style {c['g1']:.3%} (bound {G1_BOUND:.2%}, w {c['w']:.4f})  "
                f"Stocker mod. duration mean {st.mean(durs):.2f}")
        c = compare("006", read_study("006"), stk, ret_col)
        lines.append("  calendar years by execution month (006 window; partial years marked *):")
        lines.append("    year  months  synthetic   Stocker     gap")
        for y, (a, b, n) in sorted(c["years"].items()):
            lines.append(f"    {y}  {n:>6}{'*' if n < 12 else ' '} {a - 1:+9.2%} {b - 1:+9.2%} {(a - 1) - (b - 1):+8.2%}")
        lines.append("")
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
