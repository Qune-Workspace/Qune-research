"""Build the desk view's numbers and charts from public FRED series.

Usage (from this folder, repository virtualenv active):

    python build_view.py --asof 2026-10-23          # fetch, write data/ and charts/
    python build_view.py --asof 2026-10-23 --offline  # reuse data/raw/, no network

Every raw file is fetched with the shared library's FRED adapter and recorded in
``data/manifest.json`` with its hash and download time; the raw files are not
committed (they are re-fetched).  The derived snapshot (``data/snapshot_<asof>.csv``,
``data/numbers_<asof>.json``) and the charts are committed, and the note
``DESK_VIEW.md`` quotes only numbers that appear in the json.  Nothing here is
a forecast: the calls are a human-readable judgement written in the note and
logged in ``../predictions/ledger.csv`` before the outcome.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qune_research import data as qdata  # noqa: E402
import view_lib as vl  # noqa: E402

RAW_DIR = HERE / "data" / "raw"
MANIFEST = HERE / "data" / "manifest.json"
CHARTS = HERE / "charts"

# FRED series, all public, no key.  Each one is named here once with what it is.
SERIES = {
    "DGS3MO": "3-month Treasury bill, constant maturity, percent",
    "DGS2": "2-year Treasury, constant maturity, percent",
    "DGS10": "10-year Treasury, constant maturity, percent",
    "DGS30": "30-year Treasury, constant maturity, percent",
    "DFII10": "10-year TIPS real yield, constant maturity, percent",
    "T10YIE": "10-year breakeven inflation rate, percent",
    "T5YIFR": "5-year, 5-year forward inflation expectation rate, percent",
    "EFFR": "Effective federal funds rate, percent",
    "DFEDTARU": "Federal funds target range, upper limit, percent",
    "DFEDTARL": "Federal funds target range, lower limit, percent",
    "THREEFYTP10": "10-year term premium, Kim-Wright three-factor model, percent",
    "BAMLH0A0HYM2": "ICE BofA US High Yield option-adjusted spread, percent",
    "SP500": "S&P 500 index level (FRED carries the last ten years)",
    "VIXCLS": "CBOE VIX, close",
}

# Chart palette: the dataviz reference instance (categorical slots 1-3, light surface).
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"


def load_all(offline: bool) -> dict[str, pd.Series]:
    out = {}
    for sid in SERIES:
        if offline:
            out[sid] = qdata.load_fred(sid, RAW_DIR)
        else:
            out[sid] = qdata.fetch_fred(sid, RAW_DIR, MANIFEST)
    return out


def style_axes(ax, title: str, ylabel: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=INK, fontsize=11, pad=10)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9)
    ax.tick_params(colors=INK2, labelsize=8.5, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


def end_label(ax, series: pd.Series, text: str, colour: str) -> None:
    ax.annotate(text, (series.index[-1], series.iloc[-1]), xytext=(6, 0), textcoords="offset points",
                va="center", fontsize=8.5, color=INK)
    ax.plot([series.index[-1]], [series.iloc[-1]], marker="o", markersize=4, color=colour)


def chart_curve(s: dict[str, pd.Series], asof: pd.Timestamp, path: Path) -> None:
    tenors = {"3m": "DGS3MO", "2y": "DGS2", "10y": "DGS10", "30y": "DGS30"}
    x = [0.25, 2, 10, 30]
    fig, ax = plt.subplots(figsize=(7.2, 4.2), facecolor=SURFACE)
    for label, when, colour in (("now", asof, S1), ("3 months ago", asof - pd.DateOffset(months=3), S2),
                                ("1 year ago", asof - pd.DateOffset(years=1), S3)):
        snap = vl.curve_snapshot({t: s[c] for t, c in tenors.items()}, when)
        ax.plot(x, snap["yield_pct"], color=colour, linewidth=2, marker="o", markersize=5,
                label=f"{label} ({snap['observed_on'].iloc[-1]})")
        ax.annotate(f"{snap['yield_pct'].iloc[-1]:.2f}", (x[-1], snap["yield_pct"].iloc[-1]),
                    xytext=(6, 0), textcoords="offset points", va="center", fontsize=8.5, color=INK)
    ax.set_xscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(["3m", "2y", "10y", "30y"])
    ax.minorticks_off()
    style_axes(ax, "US Treasury curve: now, three months ago, a year ago", "yield, %")
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)


def chart_decomposition(s: dict[str, pd.Series], start: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.2), facecolor=SURFACE)
    for sid, label, colour in (("DFII10", "10y real yield (TIPS)", S1), ("T10YIE", "10y breakeven inflation", S2),
                               ("THREEFYTP10", "10y term premium (Kim-Wright)", S3)):
        ser = s[sid].loc[start:].dropna()
        ax.plot(ser.index, ser.values, color=colour, linewidth=1.6, label=label)
        end_label(ax, ser, f"{ser.iloc[-1]:.2f}", colour)
    ax.axhline(0, color=GRID, linewidth=1)
    style_axes(ax, "What the 10-year yield is made of, 2003 to date", "%")
    ax.xaxis.set_major_locator(mdates.YearLocator(3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK, loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)


def chart_stock_bond(corr: pd.Series, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 3.6), facecolor=SURFACE)
    ax.plot(corr.index, corr.values, color=S1, linewidth=1.6)
    ax.axhline(0, color=INK2, linewidth=0.8)
    end_label(ax, corr, f"{corr.iloc[-1]:+.2f}", S1)
    style_axes(ax, "Stock-bond correlation proxy: 63-day, S&P 500 returns against the fall in the 10y yield",
               "correlation (+ = prices move together)")
    ax.set_ylim(-1, 1)
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)


def chart_policy(s: dict[str, pd.Series], start: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.0), facecolor=SURFACE)
    for sid, label, colour in (("EFFR", "effective funds rate", S1), ("DGS3MO", "3-month bill", S2),
                               ("DGS2", "2-year note", S3)):
        ser = s[sid].loc[start:].dropna()
        ax.plot(ser.index, ser.values, color=colour, linewidth=1.6, label=label)
        end_label(ax, ser, f"{ser.iloc[-1]:.2f}", colour)
    style_axes(ax, "Policy rate against what the front end prices, 2022 to date", "%")
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK, loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=SURFACE)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asof", required=True, help="view date, YYYY-MM-DD (data up to this date)")
    parser.add_argument("--offline", action="store_true", help="reuse data/raw/ instead of fetching")
    args = parser.parse_args()
    asof = pd.Timestamp(args.asof)
    s = load_all(args.offline)
    CHARTS.mkdir(exist_ok=True)

    tenors = {"3m": "DGS3MO", "2y": "DGS2", "10y": "DGS10", "30y": "DGS30"}
    curve = vl.curve_snapshot({t: s[c] for t, c in tenors.items()}, asof)
    lookbacks = {"1m": pd.DateOffset(months=1), "3m": pd.DateOffset(months=3), "1y": pd.DateOffset(years=1)}
    changes = {sid: vl.change_table(s[sid], asof, lookbacks) for sid in
               ("DGS3MO", "DGS2", "DGS10", "DGS30", "DFII10", "T10YIE", "T5YIFR", "THREEFYTP10", "BAMLH0A0HYM2", "VIXCLS")}
    nominal = vl.last_valid_on_or_before(s["DGS10"], asof)
    real = vl.last_valid_on_or_before(s["DFII10"], nominal[0])
    bei = vl.last_valid_on_or_before(s["T10YIE"], nominal[0])
    tp = vl.last_valid_on_or_before(s["THREEFYTP10"], nominal[0])
    decomp = vl.decomposition(nominal[1], real[1], bei[1], tp[1])
    decomp["dates_used"] = {"nominal": str(nominal[0].date()), "real": str(real[0].date()),
                            "breakeven": str(bei[0].date()), "term_premium": str(tp[0].date())}
    path = vl.market_implied_path(s["EFFR"], s["DGS3MO"], s["DGS2"], asof)
    corr = vl.rolling_stock_bond_corr(s["SP500"], s["DGS10"])
    slope_2s10s = vl.spread_bp(s["DGS10"], s["DGS2"])
    slope_3m10y = vl.spread_bp(s["DGS10"], s["DGS3MO"])
    target = {"upper_pct": vl.last_valid_on_or_before(s["DFEDTARU"], asof)[1],
              "lower_pct": vl.last_valid_on_or_before(s["DFEDTARL"], asof)[1]}
    tp_hist = s["THREEFYTP10"].dropna()
    numbers = {
        "asof": str(asof.date()),
        "curve": curve.to_dict(orient="records"),
        "changes_bp": {sid: tbl.to_dict(orient="records") for sid, tbl in changes.items()},
        "decomposition_10y": decomp,
        "market_implied_path": path,
        "target_range": target,
        "slope_2s10s_bp": {"now": float(slope_2s10s.iloc[-1]), "on": str(slope_2s10s.index[-1].date())},
        "slope_3m10y_bp": {"now": float(slope_3m10y.iloc[-1]), "on": str(slope_3m10y.index[-1].date())},
        "stock_bond_corr_63d": {"now": float(corr.iloc[-1]), "on": str(corr.index[-1].date()),
                                "share_of_days_positive_since_2022": float((corr.loc["2022":] > 0).mean()),
                                "share_of_days_positive_2016_2021": float((corr.loc["2016":"2021"] > 0).mean())},
        "dgs10_high_since_2007": {"value_pct": float(s["DGS10"].loc["2008":asof].max()),
                                  "on": str(s["DGS10"].loc["2008":asof].idxmax().date())},
        "term_premium_percentile_since_1990": float((tp_hist.loc[:asof] <= tp[1]).mean()),
        "series": SERIES,
    }
    out_csv = HERE / "data" / f"snapshot_{asof.date()}.csv"
    rows = []
    for sid in SERIES:
        d, v = vl.last_valid_on_or_before(s[sid], asof)
        rows.append({"series": sid, "observed_on": str(d.date()), "value": v, "what": SERIES[sid]})
    pd.DataFrame(rows).to_csv(out_csv, index=False)
    (HERE / "data" / f"numbers_{asof.date()}.json").write_text(json.dumps(numbers, indent=2) + "\n")

    chart_curve(s, asof, CHARTS / "curve.png")
    chart_decomposition(s, "2003-01-01", CHARTS / "decomposition_10y.png")
    chart_stock_bond(corr, CHARTS / "stock_bond_corr.png")
    chart_policy(s, "2022-01-01", CHARTS / "policy_vs_front_end.png")
    print(json.dumps({k: numbers[k] for k in ("asof", "decomposition_10y", "market_implied_path", "target_range",
                                                "slope_2s10s_bp", "slope_3m10y_bp", "stock_bond_corr_63d",
                                                "dgs10_high_since_2007", "term_premium_percentile_since_1990")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
