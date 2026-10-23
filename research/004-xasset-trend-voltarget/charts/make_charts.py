"""Study 004 charts in the house style, drawn from the committed results files.

Reads results/{insample,oos}/daily_index_10assets.csv and metrics_10assets_base.csv,
computes nothing the study did not already publish (daily drawdown from the
running high; the growth of one unit), and writes SVG + 2x PNG into this
folder with a manifest of the input hashes and every number that appears in a
title.  The original charts in results/ are the run's own output and stay as
they were; these are the same numbers presented to the chart standard of
2026-10-23 (qune_research/style.py).  No result file is written.

Run from the repository root:  .venv/bin/python research/004-xasset-trend-voltarget/charts/make_charts.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))

from qune_research import style  # noqa: E402

STUDY_ID = "Study 004"
SOURCE = "Alpaca and Tiingo daily ETF bars, BIL as cash"
WINDOWS = {
    "insample": ("2004-01 to 2018-12", "in-sample", "In-sample"),
    "oos": ("2019-01 to 2026-09", "out of sample", "Out of sample"),
}
# What each series is, for the subtitles and end labels.
SERIES = {
    "T1": "Trend rule (T1)",
    "B4": "Same book held throughout, matched exposure (B4)",
    "B3": "Same book, fully invested (B3)",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(window: str) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    d = STUDY / "results" / window
    idx_path = d / "daily_index_10assets.csv"
    met_path = d / "metrics_10assets_base.csv"
    idx = pd.read_csv(idx_path, index_col=0, parse_dates=True)
    met = pd.read_csv(met_path, index_col=0)
    return idx, met, {str(idx_path.relative_to(ROOT)): sha256(idx_path),
                      str(met_path.relative_to(ROOT)): sha256(met_path)}


def drawdown_chart(window: str, idx: pd.DataFrame, numbers: dict) -> Path:
    period, where, where_cap = WINDOWS[window]
    dd = idx[["T1", "B3", "B4"]] / idx[["T1", "B3", "B4"]].cummax() - 1.0
    worst = dd.min()
    numbers[f"{window}_daily_max_drawdown"] = {k: float(v) for k, v in worst.items()}
    trough_year = int(dd["B4"].idxmin().year)
    numbers[f"{window}_B4_trough_year"] = trough_year
    t1_trough = dd["T1"].idxmin()
    numbers[f"{window}_T1_trough_date"] = str(t1_trough.date())
    # The two books bottom in different years; naming only B4's year read as the rule's (Tester chart
    # review, 2026-10-23), so the sentence names both unless they coincide.
    if int(t1_trough.year) == trough_year:
        trough_clause = f"the trough came in {trough_year}"
    else:
        trough_clause = (f"the matched book's trough came in {trough_year}, the rule's in "
                         f"{t1_trough.strftime('%B %Y')}")
    cut = 1.0 - worst["T1"] / worst["B4"]
    numbers[f"{window}_drawdown_cut_share"] = float(cut)
    fig, ax = style.figure(width=8.0, height=4.6)
    # The wording follows the size of the cut, so the title cannot overstate it.
    if cut >= 0.33:
        verb = "cut the deepest daily drawdown"
    elif cut >= 0.05:
        verb = "trimmed the deepest daily drawdown only"
    else:
        verb = "left the deepest daily drawdown about where it was,"
    finding = (f"{where_cap}, trend timing {verb} from {style.pct(worst['B4'])} to "
               f"{style.pct(worst['T1'])}; {trough_clause}")
    style.title(fig, finding,
                f"Drawdown from the running high, daily, %, {period}. Ten ETFs, 10% volatility target, "
                f"no leverage, after costs.")
    for name, colour, lw in (("B3", style.GREY_LIGHT, 1.2), ("B4", style.GREY_DARK, 1.3), ("T1", style.ACCENT, 1.7)):
        ax.plot(dd.index, dd[name], color=colour, lw=lw)
    if window == "oos":
        style.shade(ax, pd.Timestamp("2022-01-03"), pd.Timestamp("2022-12-30"), label="2022")
    else:
        style.shade(ax, pd.Timestamp("2007-12-03"), pd.Timestamp("2009-06-30"), label="2008 crisis")
    style.percent_axis(ax, decimals=0)
    ax.set_ylim(min(worst.min() * 1.15, -0.05), 0.012)  # headroom for the shade label above the 0% lines
    ax.set_xlim(dd.index[0], dd.index[-1])
    style.label_line_ends(ax, [
        style.EndLabel("Trend rule (T1)", float(dd["T1"].iloc[-1]), style.ACCENT),
        style.EndLabel("Matched exposure (B4)", float(dd["B4"].iloc[-1]), style.GREY_DARK),
        style.EndLabel("Fully invested (B3)", float(dd["B3"].iloc[-1]), style.GREY_LIGHT),
    ], min_gap=0.07)
    style.source(fig, SOURCE, period, STUDY_ID,
                 note="Run once; results/" + window + "/daily_index_10assets.csv. Verdict: not supported (section 9.5).")
    svg, _png = style.save(fig, HERE / f"{window}_drawdown_10assets")
    return svg


def growth_chart(window: str, idx: pd.DataFrame, met: pd.DataFrame, numbers: dict) -> Path:
    period, where, where_cap = WINDOWS[window]
    sr = met.loc[["T1", "B4", "B3"], "sharpe_annual"].astype(float)
    numbers[f"{window}_sharpe_annual"] = {k: float(v) for k, v in sr.items()}
    growth = idx[["T1", "B3", "B4"]] / idx[["T1", "B3", "B4"]].iloc[0]
    numbers[f"{window}_final_growth"] = {k: float(v) for k, v in growth.iloc[-1].items()}
    # Calendar-year returns from the daily index: where did the rule's gap over B4 come from?
    yearly = growth.groupby(growth.index.year).apply(lambda g: g.iloc[-1] / g.iloc[0] - 1.0)
    gap = (yearly["T1"] - yearly["B4"])
    best_year = int(gap.idxmax())
    numbers[f"{window}_year_of_largest_gap_over_B4"] = {
        "year": best_year, "T1": float(yearly.loc[best_year, "T1"]), "B4": float(yearly.loc[best_year, "B4"]),
        "gap_share_of_summed_yearly_gaps": float(gap.loc[best_year] / gap.sum()) if gap.sum() != 0 else None}
    ended = "above" if growth["T1"].iloc[-1] > growth["B3"].iloc[-1] else "below"
    fig, ax = style.figure(width=8.0, height=4.6)
    if abs(sr["T1"] - sr["B4"]) < 0.05:
        finding = (f"{where_cap}, the trend signal added nothing on top of volatility scaling: "
                   f"Sharpe {sr['T1']:.2f} against {sr['B4']:.2f}, ending {ended} the fully invested book")
    else:
        finding = (f"{where_cap}, the rule's Sharpe ratio was {sr['T1']:.2f} against {sr['B4']:.2f}; "
                   f"the largest gap came in {best_year} ({style.pct(yearly.loc[best_year, 'T1'])} against "
                   f"{style.pct(yearly.loc[best_year, 'B4'])})")
    style.title(fig, finding,
                f"Growth of 1 unit, {period}. Ten ETFs, 10% volatility target, no leverage, after costs; "
                f"Sharpe ratios annualised.")
    for name, colour, lw in (("B3", style.GREY_LIGHT, 1.2), ("B4", style.GREY_DARK, 1.3), ("T1", style.ACCENT, 1.7)):
        ax.plot(growth.index, growth[name], color=colour, lw=lw)
    ax.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:,.2f}"))  # 0.05 steps need two decimals
    ax.set_xlim(growth.index[0], growth.index[-1])
    last = growth.iloc[-1]
    style.label_line_ends(ax, [
        style.EndLabel(f"Trend rule (T1) {last['T1']:.2f}", float(last["T1"]), style.ACCENT),
        style.EndLabel(f"Matched (B4) {last['B4']:.2f}", float(last["B4"]), style.GREY_DARK),
        style.EndLabel(f"Fully invested (B3) {last['B3']:.2f}", float(last["B3"]), style.GREY_LIGHT),
    ], min_gap=0.07)
    style.source(fig, SOURCE, period, STUDY_ID,
                 note="Run once; results/" + window + "/daily_index_10assets.csv and metrics_10assets_base.csv.")
    svg, _png = style.save(fig, HERE / f"{window}_growth_10assets")
    return svg


def main() -> None:
    numbers: dict = {}
    inputs: dict[str, str] = {}
    outputs: list[str] = []
    for window in ("insample", "oos"):
        idx, met, hashes = load(window)
        inputs.update(hashes)
        for p in (drawdown_chart(window, idx, numbers), growth_chart(window, idx, met, numbers)):
            outputs.append(str(p.relative_to(ROOT)))
            outputs.append(str(p.with_suffix(".png").relative_to(ROOT)))
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.strip()
    except Exception:  # pragma: no cover
        commit = "unknown"
    manifest = {
        "made_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repository_commit_at_run": commit,
        "inputs_sha256": inputs,
        "outputs": outputs,
        "numbers_in_titles": numbers,
        "note": "Presentation only. Every number is recomputed from the committed results files; "
                "no result file is written. Style: qune_research/style.py (chart standard of 2026-10-23).",
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(numbers, indent=2))


if __name__ == "__main__":
    main()
