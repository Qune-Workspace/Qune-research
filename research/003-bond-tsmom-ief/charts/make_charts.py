"""Study 003 charts in the house style, drawn from the committed results files.

Reads results/{insample,oos}/monthly_base.csv and metrics_base.csv, the daily
drawdown figures already published in results/{window}/summary.json, and the
by-year cash-check statistics in results/checks/data_checks.json.  Computes
nothing the study did not already publish (the holding-period return index of
each book, its drawdown from the running high, calendar-year returns from the
same monthly rows) and writes SVG + 2x PNG into this folder with a manifest of
the input hashes and every number that appears in a title.  The run's own
charts in results/ stay as they were; these are the same numbers presented to
the chart standard of 2026-10-23 (qune_research/style.py).  No result file is
written.

Every phrase in a title is chosen by this script from the numbers it computes,
never typed, so a title cannot overstate a result.

Run from the repository root:
  .venv/bin/python research/003-bond-tsmom-ief/charts/make_charts.py
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

STUDY_ID = "Study 003"
SOURCE = "Alpaca and Tiingo daily ETF bars (IEF, BIL), FRED DTB3 for the in-sample cash accrual"
WINDOWS = {
    "insample": ("2003-08 to 2018-12", "In-sample"),
    "oos": ("2019-01 to 2026-09", "Out of sample"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def num(x: float, decimals: int = 2) -> str:
    """A plain number with the typographic minus the percent labels use."""
    return f"{x:.{decimals}f}".replace("-", "\u2212")


def load(window: str) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict[str, str]]:
    d = STUDY / "results" / window
    monthly_path = d / "monthly_base.csv"
    metrics_path = d / "metrics_base.csv"
    summary_path = d / "summary.json"
    monthly = pd.read_csv(monthly_path, parse_dates=["execution_date", "period_end"])
    metrics = pd.read_csv(metrics_path, index_col=0)
    summary = json.loads(summary_path.read_text())
    hashes = {str(p.relative_to(ROOT)): sha256(p) for p in (monthly_path, metrics_path, summary_path)}
    return monthly, metrics, summary, hashes


def index_and_drawdown(monthly: pd.DataFrame, books: tuple[str, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Holding-period return index (1 at the first execution date) and drawdown from its running high,
    both indexed by period end, with the starting point prepended at the first execution date."""
    start = monthly["execution_date"].iloc[0]
    rows = [pd.Series({b: 1.0 for b in books}, name=start)]
    growth = (1.0 + monthly[list(books)]).cumprod()
    growth.index = monthly["period_end"]
    idx = pd.concat([pd.DataFrame(rows), growth])
    dd = idx / idx.cummax() - 1.0
    return idx, dd


def shade_cash_months(ax, monthly: pd.DataFrame) -> int:
    """Shade the holding periods in which T1 held bills.  Returns the number of such months."""
    cash = monthly[monthly["T1_holding"] == "BIL"]
    for _, row in cash.iterrows():
        ax.axvspan(row["execution_date"], row["period_end"], color=style.SHADE, lw=0, zorder=0)
    return int(len(cash))


def drawdown_chart(window: str, monthly: pd.DataFrame, summary: dict, numbers: dict) -> Path:
    period, where_cap = WINDOWS[window]
    idx, dd = index_and_drawdown(monthly, ("T1", "B1", "B0"))
    worst = dd[["T1", "B1"]].min()
    daily = summary["cost_cases"]["base"]["max_drawdown_daily"]
    numbers[f"{window}_monthly_max_drawdown"] = {k: float(v) for k, v in worst.items()}
    numbers[f"{window}_daily_max_drawdown_from_summary"] = {k: float(daily[k]) for k in ("T1", "B1")}
    cut = 1.0 - worst["T1"] / worst["B1"]
    numbers[f"{window}_drawdown_cut_share"] = float(cut)
    trough_year = int(dd["B1"].idxmin().year)
    numbers[f"{window}_B1_trough_year"] = trough_year
    in_bills_all_trough_year = bool((monthly.loc[monthly["period_end"].dt.year == trough_year, "T1_holding"] == "BIL").all())
    numbers[f"{window}_T1_in_bills_every_month_of_trough_year"] = in_bills_all_trough_year
    # The wording follows the size of the cut and the holdings, so the title cannot overstate it.
    if cut >= 0.33 and in_bills_all_trough_year:
        finding = (f"{where_cap}, trend timing cut the deepest monthly drawdown from {style.pct(worst['B1'])} "
                   f"to {style.pct(worst['T1'])} by sitting in bills through {trough_year}")
    elif cut >= 0.33:
        finding = (f"{where_cap}, trend timing cut the deepest monthly drawdown from {style.pct(worst['B1'])} "
                   f"to {style.pct(worst['T1'])}; the trough came in {trough_year}")
    elif cut >= 0.05:
        finding = (f"{where_cap}, trend timing trimmed the deepest monthly drawdown only from "
                   f"{style.pct(worst['B1'])} to {style.pct(worst['T1'])}; the trough came in {trough_year}")
    else:
        finding = (f"{where_cap}, trend timing did not reduce the deepest monthly drawdown: "
                   f"{style.pct(worst['T1'])} against {style.pct(worst['B1'])} for holding IEF throughout")
    fig, ax = style.figure(width=8.0, height=4.6)
    style.title(fig, finding,
                f"Drawdown from the running high of the holding-period return index, monthly, %, {period}. "
                f"Shaded: months the rule held bills. 2 bp per side.")
    n_cash = shade_cash_months(ax, monthly)
    numbers[f"{window}_months_in_bills"] = n_cash
    ax.plot(dd.index, dd["B1"], color=style.GREY_DARK, lw=1.3)
    ax.plot(dd.index, dd["T1"], color=style.ACCENT, lw=1.7)
    style.percent_axis(ax, decimals=0)
    ax.set_ylim(min(worst.min() * 1.15, -0.05), 0.005)
    ax.set_xlim(dd.index[0], dd.index[-1])
    style.label_line_ends(ax, [
        style.EndLabel("Trend rule (T1)", float(dd["T1"].iloc[-1]), style.ACCENT),
        style.EndLabel("Hold IEF (B1)", float(dd["B1"].iloc[-1]), style.GREY_DARK),
    ], min_gap=0.07)
    style.source(fig, SOURCE, period, STUDY_ID,
                 note=f"Run once; results/{window}/monthly_base.csv. Daily drawdown inside the holding periods: "
                      f"T1 {style.pct(daily['T1'])}, B1 {style.pct(daily['B1'])} (summary.json). "
                      f"Verdict: not supported (section 9.5).")
    svg, _png = style.save(fig, HERE / f"{window}_drawdown")
    return svg


def growth_chart(window: str, monthly: pd.DataFrame, metrics: pd.DataFrame, numbers: dict) -> Path:
    period, where_cap = WINDOWS[window]
    idx, _dd = index_and_drawdown(monthly, ("T1", "B1", "B0"))
    sr = metrics.loc[["T1", "B1"], "sharpe_annual"].astype(float)
    switches = int(metrics.loc["T1", "switches"])
    numbers[f"{window}_sharpe_annual"] = {k: float(v) for k, v in sr.items()}
    numbers[f"{window}_T1_switches"] = switches
    numbers[f"{window}_final_growth"] = {k: float(v) for k, v in idx.iloc[-1].items()}
    # Calendar-year returns by period end: where did the gap between the rule and IEF come from?
    # Each year's return is the index at its last period end over the index at the previous year's last
    # period end (the start value for the first year), so the partial first and last years are counted as such.
    year_end = idx.groupby(idx.index.year).last()
    yearly = (year_end / year_end.shift(1).fillna(idx.iloc[0]) - 1.0).iloc[1:] \
        if (idx.index.year == idx.index[0].year).sum() == 1 else (year_end / year_end.shift(1).fillna(idx.iloc[0]) - 1.0)
    gap = yearly["T1"] - yearly["B1"]
    year_max = int(gap.abs().idxmax())
    numbers[f"{window}_year_of_largest_gap_vs_B1"] = {
        "year": year_max, "T1": float(yearly.loc[year_max, "T1"]), "B1": float(yearly.loc[year_max, "B1"])}
    diff = sr["T1"] - sr["B1"]
    if diff <= -0.05:
        finding = (f"{where_cap}, the trend rule lagged holding IEF throughout: Sharpe {num(sr['T1'])} against "
                   f"{num(sr['B1'])}, after {switches} switches")
    elif diff >= 0.05:
        finding = (f"{where_cap}, the trend rule beat holding IEF: Sharpe {num(sr['T1'])} against {num(sr['B1'])}; "
                   f"the largest yearly gap came in {year_max} ({style.pct(yearly.loc[year_max, 'T1'])} against "
                   f"{style.pct(yearly.loc[year_max, 'B1'])})")
    else:
        finding = (f"{where_cap}, the trend rule matched holding IEF: Sharpe {num(sr['T1'])} against {num(sr['B1'])}")
    fig, ax = style.figure(width=8.0, height=4.6)
    style.title(fig, finding,
                f"Growth of 1 unit over the monthly holding periods, {period}. Sharpe ratios of returns in excess "
                f"of bills, annualised; 2 bp per side.")
    ax.plot(idx.index, idx["B0"], color=style.GREY_LIGHT, lw=1.2)
    ax.plot(idx.index, idx["B1"], color=style.GREY_DARK, lw=1.3)
    ax.plot(idx.index, idx["T1"], color=style.ACCENT, lw=1.7)
    ax.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:,.2f}"))
    ax.set_xlim(idx.index[0], idx.index[-1])
    last = idx.iloc[-1]
    style.label_line_ends(ax, [
        style.EndLabel(f"Trend rule (T1) {last['T1']:.2f}", float(last["T1"]), style.ACCENT),
        style.EndLabel(f"Hold IEF (B1) {last['B1']:.2f}", float(last["B1"]), style.GREY_DARK),
        style.EndLabel(f"Bills (B0) {last['B0']:.2f}", float(last["B0"]), style.GREY_LIGHT),
    ], min_gap=0.07)
    style.source(fig, SOURCE, period, STUDY_ID,
                 note=f"Run once; results/{window}/monthly_base.csv and metrics_base.csv.")
    svg, _png = style.save(fig, HERE / f"{window}_growth")
    return svg


def cash_check_chart(numbers: dict) -> tuple[Path, dict[str, str]]:
    path = STUDY / "results" / "checks" / "data_checks.json"
    checks = json.loads(path.read_text())
    stats = checks["D2"]["statistics"]
    by_year = {int(k): float(v) for k, v in stats["mean_diff_annual_by_year"].items()}
    mean_all = float(stats["mean_diff_annual"])
    gate = 0.003
    exante = 0.002
    first, last = stats["first_return_date"][:4], stats["last_return_date"][:4]
    outside = sorted(y for y, v in by_year.items() if abs(v) > exante)
    numbers["cash_check_mean_diff_annual"] = mean_all
    numbers["cash_check_years_outside_exante_band"] = outside
    numbers["cash_check_by_year"] = by_year
    if outside:
        span = f"{outside[0]}" if len(outside) == 1 else f"{outside[0]} to {outside[-1]}" \
            if outside == list(range(outside[0], outside[-1] + 1)) else ", ".join(map(str, outside))
        finding = (f"BIL tracked the cash-accrual model to within {style.pct(abs(mean_all), 2)} a year over "
                   f"{first} to {last}; only {span} sat outside the ±{style.pct(exante, 1)} band written down beforehand")
    else:
        finding = (f"BIL tracked the cash-accrual model to within {style.pct(abs(mean_all), 2)} a year over "
                   f"{first} to {last}, every year inside the ±{style.pct(exante, 1)} band written down beforehand")
    fig, ax = style.figure(width=8.0, height=4.6)
    style.title(fig, finding,
                f"Annualised mean daily difference, BIL total return minus the bill-yield cash accrual, by calendar "
                f"year, % p.a. Gate for the full-window mean: ±{style.pct(gate, 1)} (passed at "
                f"{'+' if mean_all >= 0 else ''}{style.pct(mean_all, 3)}).")
    years = list(by_year)
    vals = [by_year[y] for y in years]
    colours = [style.ACCENT if y in outside else style.GREY_LIGHT for y in years]
    ax.bar(years, vals, color=colours, width=0.7)
    ax.axhspan(-exante, exante, color=style.SHADE, lw=0, zorder=0)
    ax.axhline(0.0, color=style.GREY, lw=0.8)
    ax.axhline(mean_all, color=style.GREY_DARK, lw=1.0, ls=(0, (4, 3)))
    ax.annotate(f"mean {'+' if mean_all >= 0 else ''}{style.pct(mean_all, 3)}", xy=(years[-1] + 0.45, mean_all),
                xytext=(6, 0), textcoords="offset points", ha="left", va="center", fontsize=style.LABEL_SIZE,
                color=style.GREY_DARK, annotation_clip=False)
    ax.annotate(f"ex-ante band ±{style.pct(exante, 1)}", xy=(years[-1] + 0.45, exante), xytext=(6, 0),
                textcoords="offset points", ha="left", va="center", fontsize=style.LABEL_SIZE, color=style.TEXT_MUTED,
                annotation_clip=False)
    style.despine(ax, keep=("bottom",))
    ax.tick_params(axis="y", length=0)
    style.percent_axis(ax, decimals=1)
    ax.set_xticks(years)
    ax.set_xticklabels([str(y) for y in years], rotation=0)
    ax.set_xlim(years[0] - 0.6, years[-1] + 0.6)
    style.source(fig, "Tiingo BIL adjusted close; FRED DTB3", f"{stats['first_return_date']} to {stats['last_return_date']}",
                 STUDY_ID, note="Data check D2 (section 5.3), not a performance test; results/checks/data_checks.json. "
                                "Bars in calendar order, not sorted, because the message is the regime pattern.")
    svg, _png = style.save(fig, HERE / "cash_check_by_year")
    return svg, {str(path.relative_to(ROOT)): sha256(path)}


def main() -> None:
    numbers: dict = {}
    inputs: dict[str, str] = {}
    outputs: list[str] = []
    for window in ("insample", "oos"):
        monthly, metrics, summary, hashes = load(window)
        inputs.update(hashes)
        for p in (drawdown_chart(window, monthly, summary, numbers), growth_chart(window, monthly, metrics, numbers)):
            outputs.append(str(p.relative_to(ROOT)))
            outputs.append(str(p.with_suffix(".png").relative_to(ROOT)))
    p, h = cash_check_chart(numbers)
    inputs.update(h)
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
