"""Build the desk view's numbers and charts from public FRED series.

Usage (from this folder, repository virtualenv active):

    python build_view.py --asof 2026-10-23               # fetch, write data/ and charts/
    python build_view.py --asof 2026-10-23 --offline     # reuse data/raw/, no network
    python build_view.py --asof 2026-10-23 --charts-only # redraw charts/ from data/raw/ only

Every raw file is fetched with the shared library's FRED adapter and recorded in
``data/manifest.json`` with its hash and download time; the raw files are not
committed (they are re-fetched).  The derived snapshot (``data/snapshot_<asof>.csv``,
``data/numbers_<asof>.json``) and the charts are committed, and the note
``DESK_VIEW.md`` quotes only numbers that appear in the json.  Nothing here is
a forecast: the calls are a human-readable judgement written in the note and
logged in ``../predictions/ledger.csv`` before the outcome.

Charts follow the chart standard of 2026-10-23 (``qune_research/style.py``):
the title states the finding, and every phrase in it is chosen by the pure
functions in ``view_lib`` from the numbers this script computes, never typed,
so a title cannot overstate a reading.  ``charts/manifest.json`` records the
hash of every raw file read and every number that appears in a title.

``--charts-only`` is for redrawing a published view: it hash-checks the raw
files on disk against ``data/manifest.json``, recomputes the numbers, refuses
to draw if any of them differs from the committed ``data/numbers_<asof>.json``,
and writes nothing under ``data/``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import view_lib as vl  # noqa: E402

from qune_research import data as qdata  # noqa: E402
from qune_research import style  # noqa: E402

RAW_DIR = HERE / "data" / "raw"
MANIFEST = HERE / "data" / "manifest.json"
CHARTS = HERE / "charts"
STUDY_ID = "desk view"
SOURCE = "FRED, Federal Reserve Bank of St. Louis (public series, no key)"

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

TENORS = {"3m": "DGS3MO", "2y": "DGS2", "10y": "DGS10", "30y": "DGS30"}
LOOKBACKS = {"1m": pd.DateOffset(months=1), "3m": pd.DateOffset(months=3), "1y": pd.DateOffset(years=1)}
CHANGE_SERIES = ("DGS3MO", "DGS2", "DGS10", "DGS30", "DFII10", "T10YIE", "T5YIFR", "THREEFYTP10", "BAMLH0A0HYM2",
                 "VIXCLS")
# Series whose FRED notes forbid reproduction without the owner's permission (tools/intraday_source_check.md).
# From the view of 2026-10-30 their levels are not written to the committed numbers or snapshot files while the
# owner's licence decision is open; they are still read (SP500 feeds the correlation proxy, a derived statistic).
# Views dated before 2026-10-30 keep the files they were published with, so --charts-only still reproduces them.
NO_REPRODUCTION = ("BAMLH0A0HYM2", "SP500")
NO_REPRODUCTION_FROM = pd.Timestamp("2026-10-30")


def change_series(asof: pd.Timestamp) -> tuple[str, ...]:
    if asof < NO_REPRODUCTION_FROM:
        return CHANGE_SERIES
    return tuple(sid for sid in CHANGE_SERIES if sid not in NO_REPRODUCTION)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_all(offline: bool) -> dict[str, pd.Series]:
    out = {}
    for sid in SERIES:
        if offline:
            out[sid] = qdata.load_fred(sid, RAW_DIR)
        else:
            out[sid] = qdata.fetch_fred(sid, RAW_DIR, MANIFEST)
    return out


def verify_raw_against_manifest() -> dict[str, str]:
    """Hash every raw file and refuse if one differs from data/manifest.json.  Returns the hashes."""
    manifest = json.loads(MANIFEST.read_text())
    hashes = {}
    for sid in SERIES:
        name = f"fred_{sid}.csv"
        path = RAW_DIR / name
        if not path.exists():
            raise SystemExit(f"raw file missing: {path}")
        h = sha256(path)
        if manifest.get(name, {}).get("sha256") != h:
            raise SystemExit(f"raw file {name} does not match data/manifest.json; refusing to draw from it")
        hashes[f"desk-view/data/raw/{name}"] = h
    return hashes


def compute_numbers(s: dict[str, pd.Series], asof: pd.Timestamp) -> tuple[dict, pd.Series]:
    """Every number the note quotes, plus the correlation series the chart draws."""
    curve = vl.curve_snapshot({t: s[c] for t, c in TENORS.items()}, asof)
    changes = {sid: vl.change_table(s[sid], asof, LOOKBACKS) for sid in change_series(asof)}
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
    return numbers, corr


def same_numbers(a, b, path: str = "") -> list[str]:
    """Differences between two nested number structures (floats within 1e-9); empty means equal."""
    diffs: list[str] = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                diffs.append(f"{path}/{k}: only on one side")
            else:
                diffs += same_numbers(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append(f"{path}: length {len(a)} vs {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b, strict=True)):
                diffs += same_numbers(x, y, f"{path}[{i}]")
    elif isinstance(a, float) or isinstance(b, float):
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isclose(a, b, abs_tol=1e-9)):
            diffs.append(f"{path}: {a!r} vs {b!r}")
    elif a != b:
        diffs.append(f"{path}: {a!r} vs {b!r}")
    return diffs


# ----------------------------------------------------------------------------
# Charts.  Each returns the numbers that appear in its title, for the manifest.
# ----------------------------------------------------------------------------

def day(d) -> str:
    return pd.Timestamp(d).strftime("%-d %b %Y")


def chart_curve(s: dict[str, pd.Series], asof: pd.Timestamp) -> dict:
    x = [0.25, 2, 10, 30]
    snaps = {label: vl.curve_snapshot({t: s[c] for t, c in TENORS.items()}, when)
             for label, when in (("now", asof), ("3m", asof - pd.DateOffset(months=3)),
                                 ("1y", asof - pd.DateOffset(years=1)))}
    now, year = snaps["now"], snaps["1y"]
    changes = {t: float((now["yield_pct"].iloc[i] - year["yield_pct"].iloc[i]) * vl.BP)
               for i, t in enumerate(TENORS)}
    inverted_then = bool(year.loc[year["tenor"] == "2y", "yield_pct"].iloc[0]
                         < year.loc[year["tenor"] == "3m", "yield_pct"].iloc[0])
    inverted_now = bool(now.loc[now["tenor"] == "2y", "yield_pct"].iloc[0]
                        < now.loc[now["tenor"] == "3m", "yield_pct"].iloc[0])
    finding = vl.curve_finding(changes, inverted_then, inverted_now)
    dates = {k: v["observed_on"].iloc[-1] for k, v in snaps.items()}

    fig, ax = style.figure(width=8.0, height=4.8)
    style.title(fig, finding,
                f"US Treasury constant-maturity yields, %, 3-month bill to 30-year bond, on {day(dates['now'])}, "
                f"{day(dates['3m'])} and {day(dates['1y'])}")
    for label, colour, lw in (("1y", style.GREY_LIGHT, 1.4), ("3m", style.GREY_DARK, 1.4), ("now", style.ACCENT, 2.0)):
        ax.plot(x, snaps[label]["yield_pct"], color=colour, linewidth=lw, marker="o", markersize=4.5)
    ax.set_xscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(["3m", "2y", "10y", "30y"])
    ax.minorticks_off()
    ax.set_xlim(0.2, 36)
    ax.tick_params(axis="x", length=0)
    style.percent_axis(ax, decimals=1, xmax=100)
    lo = min(v["yield_pct"].min() for v in snaps.values())
    hi = max(v["yield_pct"].max() for v in snaps.values())
    ax.set_ylim(math.floor((lo - 0.2) * 2) / 2, math.ceil((hi + 0.2) * 2) / 2)
    style.label_line_ends(ax, [
        style.EndLabel(f"now, {day(dates['now'])}", float(now["yield_pct"].iloc[-1]), style.ACCENT),
        style.EndLabel("3 months ago", float(snaps["3m"]["yield_pct"].iloc[-1]), style.GREY_DARK),
        style.EndLabel("a year ago", float(year["yield_pct"].iloc[-1]), style.GREY),
    ], x=30, min_gap=0.08)
    for i in range(len(TENORS)):
        ax.annotate(f"{now['yield_pct'].iloc[i]:.2f}", (x[i], now["yield_pct"].iloc[i]), xytext=(0, 8),
                    textcoords="offset points", ha="center", va="bottom", fontsize=style.TICK_SIZE, color=style.ACCENT)
    style.source(fig, SOURCE + "; DGS3MO, DGS2, DGS10, DGS30", f"{day(dates['1y'])} to {day(dates['now'])}", STUDY_ID,
                 note="Each date is the last observation on or before the calendar date asked for.")
    style.save(fig, CHARTS / "curve")
    return {"finding": finding, "one_year_change_bp_by_tenor": changes, "front_inverted_a_year_ago": inverted_then,
            "front_inverted_now": inverted_now, "dates": dates,
            "yields_now_pct": {t: float(v) for t, v in zip(TENORS, now["yield_pct"], strict=True)}}


def chart_policy(s: dict[str, pd.Series], start: str, numbers: dict) -> dict:
    path = numbers["market_implied_path"]
    finding = vl.front_end_finding(path["bill_3m_minus_effr_bp"], path["note_2y_minus_effr_bp"])
    series = {sid: s[sid].loc[start:].dropna() for sid in ("EFFR", "DGS3MO", "DGS2")}
    last = max(v.index[-1] for v in series.values())

    fig, ax = style.figure(width=8.0, height=4.6)
    style.title(fig, finding,
                f"Effective federal funds rate, 3-month bill and 2-year note, %, daily, "
                f"{day(start)} to {day(last)}; the gaps are on {day(path['note_2y_on'])}")
    ax.plot(series["EFFR"].index, series["EFFR"].values, color=style.GREY_DARK, linewidth=1.3, drawstyle="steps-post")
    ax.plot(series["DGS3MO"].index, series["DGS3MO"].values, color=style.GREY, linewidth=1.3)
    ax.plot(series["DGS2"].index, series["DGS2"].values, color=style.ACCENT, linewidth=1.8)
    style.percent_axis(ax, decimals=0, xmax=100)
    ax.set_ylim(0, math.ceil(max(v.max() for v in series.values()) + 0.5))
    ax.set_xlim(pd.Timestamp(start), last)
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    style.label_line_ends(ax, [
        style.EndLabel(f"2-year note {path['note_2y_pct']:.2f}%", float(series["DGS2"].iloc[-1]), style.ACCENT),
        style.EndLabel(f"3-month bill {path['bill_3m_pct']:.2f}%", float(series["DGS3MO"].iloc[-1]), style.GREY),
        style.EndLabel(f"funds rate {path['effr_pct']:.2f}%", float(series["EFFR"].iloc[-1]), style.GREY_DARK),
    ], min_gap=0.075)
    style.source(fig, SOURCE + "; EFFR, DGS3MO, DGS2", f"{day(start)} to {day(last)}", STUDY_ID,
                 note="Read off the bill and the 2-year, not futures: the gaps mix expectations with term premia.")
    style.save(fig, CHARTS / "policy_vs_front_end")
    return {"finding": finding, "bill_3m_minus_effr_bp": path["bill_3m_minus_effr_bp"],
            "note_2y_minus_effr_bp": path["note_2y_minus_effr_bp"], "on": path["note_2y_on"]}


def chart_decomposition(s: dict[str, pd.Series], start: str, numbers: dict) -> dict:
    sids = ("DGS10", "DFII10", "T10YIE", "THREEFYTP10")
    one_year = {sid: next(r for r in numbers["changes_bp"][sid] if r["lookback"] == "1y") for sid in sids}
    latest = {sid: next(r for r in numbers["changes_bp"][sid] if r["lookback"] == "now") for sid in sids}
    change = {sid: float(r["change_bp"]) for sid, r in one_year.items()}
    # The breakeven change is taken on the nominal's own date (decomposition_10y.breakeven_pct, the value
    # used in the identity), not on the series' later last print, so that real + breakeven adds up to the
    # nominal change the title states.  Found by the Tester chart review of 2026-10-23.
    bei_on_nominal_date = float(numbers["decomposition_10y"]["breakeven_pct"])
    change["T10YIE"] = (bei_on_nominal_date - float(one_year["T10YIE"]["value_pct"])) * vl.BP
    finding = vl.decomposition_finding(change["DGS10"], change["DFII10"], change["T10YIE"], change["THREEFYTP10"])
    lead = "DFII10" if abs(change["DFII10"]) >= abs(change["T10YIE"]) else "T10YIE"
    names = {"DFII10": "real yield (TIPS)", "T10YIE": "breakeven", "THREEFYTP10": "term premium"}
    colours = {sid: style.ACCENT if sid == lead else (style.GREY_DARK if sid != "THREEFYTP10" else style.GREY)
               for sid in names}
    series = {sid: s[sid].loc[start:].dropna() for sid in names}
    last = max(v.index[-1] for v in series.values())

    fig, ax = style.figure(width=8.0, height=4.8)
    style.title(fig, finding,
                f"The 10-year Treasury yield's parts, %, daily, {day(start)} to {day(last)}. One-year changes from "
                f"{day(one_year['DGS10']['observed_on'])} to {day(latest['DGS10']['observed_on'])} (term premium to "
                f"{day(latest['THREEFYTP10']['observed_on'])}, which FRED publishes with a lag)")
    for sid in ("THREEFYTP10", "T10YIE", "DFII10"):
        ax.plot(series[sid].index, series[sid].values, color=colours[sid], linewidth=1.8 if sid == lead else 1.3)
    ax.axhline(0, color=style.GREY_LIGHT, linewidth=0.8)
    style.percent_axis(ax, decimals=0, xmax=100)
    ax.set_xlim(pd.Timestamp(start), last)
    ax.xaxis.set_major_locator(mdates.YearLocator(3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    style.label_line_ends(ax, [
        style.EndLabel(f"{names[sid]} {series[sid].iloc[-1]:.2f}%", float(series[sid].iloc[-1]), colours[sid])
        for sid in names
    ], min_gap=0.075)
    style.source(fig, SOURCE + "; DFII10, T10YIE, THREEFYTP10", f"{day(start)} to {day(last)}", STUDY_ID,
                 note="The term premium is a model estimate published with a lag and revised; it overlaps the other two.")
    style.save(fig, CHARTS / "decomposition_10y")
    change_to = {sid: r["observed_on"] for sid, r in latest.items()}
    change_to["T10YIE"] = numbers["decomposition_10y"]["dates_used"]["breakeven"]
    return {"finding": finding, "one_year_change_bp": change, "accent_series": lead,
            "change_from": {sid: r["observed_on"] for sid, r in one_year.items()}, "change_to": change_to,
            "breakeven_pct_on_nominal_date": bei_on_nominal_date}


def chart_stock_bond(corr: pd.Series, numbers: dict) -> dict:
    sb = numbers["stock_bond_corr_63d"]
    # The series starts 63 trading days into FRED's ten-year S&P 500 history, so the "before" period is
    # labelled from its first actual year (2017), not from the numbers file's key.  Tester review, 2026-10-23.
    first_year = int(corr.loc[:"2021"].index[0].year)
    finding = vl.correlation_finding(sb["now"], sb["share_of_days_positive_since_2022"],
                                     sb["share_of_days_positive_2016_2021"], before_label=f"in {first_year}–2021")
    fig, ax = style.figure(width=8.0, height=4.2)
    style.title(fig, finding,
                f"63-day correlation of daily S&P 500 returns with the daily fall in the 10-year yield "
                f"(a bond-price proxy; positive = moved together as prices), {day(corr.index[0])} to {day(corr.index[-1])}")
    style.shade(ax, pd.Timestamp("2022-01-01"), corr.index[-1],
                label=f"2022 onward: positive on {100 * sb['share_of_days_positive_since_2022']:.0f}% of days")
    ax.plot(corr.index, corr.values, color=style.ACCENT, linewidth=1.5)
    ax.axhline(0, color=style.GREY_DARK, linewidth=0.8)
    ax.set_ylim(-1, 1)
    ax.set_yticks([-1, -0.5, 0, 0.5, 1])
    ax.set_yticklabels(["−1.0", "−0.5", "0", "+0.5", "+1.0"])
    ax.set_xlim(corr.index[0], corr.index[-1])
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    style.label_line_ends(ax, [style.EndLabel(f"{sb['now']:+.2f} on {day(sb['on'])}".replace("-", vl.MINUS),
                                              float(corr.iloc[-1]), style.ACCENT)])
    style.source(fig, SOURCE + "; SP500, DGS10", f"{day(corr.index[0])} to {day(corr.index[-1])}", STUDY_ID,
                 note="FRED carries ten years of the S&P 500. Duration-free by construction (yield change, not a bond index).")
    style.save(fig, CHARTS / "stock_bond_corr")
    return {"finding": finding, "now": sb["now"], "on": sb["on"],
            "share_of_days_positive_since_2022": sb["share_of_days_positive_since_2022"],
            "share_of_days_positive_before_2022": sb["share_of_days_positive_2016_2021"],
            "before_period_first_day": str(corr.index[0].date()), "before_period_last_year": 2021}


def draw_charts(s: dict[str, pd.Series], asof: pd.Timestamp, numbers: dict, corr: pd.Series,
                raw_hashes: dict[str, str]) -> None:
    CHARTS.mkdir(exist_ok=True)
    titles = {
        "curve": chart_curve(s, asof),
        "policy_vs_front_end": chart_policy(s, "2022-01-01", numbers),
        "decomposition_10y": chart_decomposition(s, "2003-01-01", numbers),
        "stock_bond_corr": chart_stock_bond(corr, numbers),
    }
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                                check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    manifest = {
        "made_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "repository_commit_at_run": commit,
        "asof": str(asof.date()),
        "inputs_sha256": raw_hashes,
        "style": "qune_research/style.py (chart standard of 2026-10-23); SVG and 2x PNG per chart",
        "title_wording": "chosen by view_lib.curve_finding, front_end_finding, decomposition_finding, "
                         "correlation_finding from the numbers below; never typed",
        "charts": titles,
    }
    (CHARTS / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asof", required=True, help="view date, YYYY-MM-DD (data up to this date)")
    parser.add_argument("--offline", action="store_true", help="reuse data/raw/ instead of fetching")
    parser.add_argument("--charts-only", action="store_true",
                        help="redraw charts/ from data/raw/ (hash-checked); refuse if the numbers differ from the "
                             "committed data/numbers_<asof>.json; write nothing under data/")
    args = parser.parse_args()
    asof = pd.Timestamp(args.asof)
    offline = args.offline or args.charts_only
    s = load_all(offline)
    raw_hashes = (verify_raw_against_manifest() if offline
                  else {f"desk-view/data/raw/{k}": v["sha256"] for k, v in json.loads(MANIFEST.read_text()).items()})
    numbers, corr = compute_numbers(s, asof)

    numbers_path = HERE / "data" / f"numbers_{asof.date()}.json"
    if args.charts_only:
        committed = json.loads(numbers_path.read_text())
        diffs = same_numbers(numbers, committed)
        if diffs:
            print("recomputed numbers differ from the committed json; not drawing:", file=sys.stderr)
            for d in diffs:
                print("  " + d, file=sys.stderr)
            return 2
        raw_hashes["desk-view/data/" + numbers_path.name] = sha256(numbers_path)
        draw_charts(s, asof, committed, corr, raw_hashes)
        print(json.dumps({k: v["finding"] for k, v in json.loads((CHARTS / "manifest.json").read_text())["charts"].items()},
                         indent=2, ensure_ascii=False))
        return 0

    rows = []
    for sid in SERIES:
        d, v = vl.last_valid_on_or_before(s[sid], asof)
        if sid in NO_REPRODUCTION and asof >= NO_REPRODUCTION_FROM:
            v = None  # level withheld; see NO_REPRODUCTION
        rows.append({"series": sid, "observed_on": str(d.date()), "value": v, "what": SERIES[sid]})
    pd.DataFrame(rows).to_csv(HERE / "data" / f"snapshot_{asof.date()}.csv", index=False)
    numbers_path.write_text(json.dumps(numbers, indent=2) + "\n")
    raw_hashes["desk-view/data/" + numbers_path.name] = sha256(numbers_path)
    draw_charts(s, asof, numbers, corr, raw_hashes)
    print(json.dumps({k: numbers[k] for k in ("asof", "decomposition_10y", "market_implied_path", "target_range",
                                                "slope_2s10s_bp", "slope_3m10y_bp", "stock_bond_corr_63d",
                                                "dgs10_high_since_2007", "term_premium_percentile_since_1990")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
