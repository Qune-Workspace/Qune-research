"""Study 006 charts in the house style (PREREGISTRATION.md §9.6), drawn from
the committed history files.

Reads results/history/monthly_base.csv and metrics_base.csv (the history run,
once, 662630c).  Computes nothing the study did not already publish beyond
presentation: the holding-period return index of each book, its drawdown from
the running high, and the mean of the published monthly differential T1 − B3
grouped by the decade of each period's execution date (descriptive, no
decision weight).  Writes SVG + 2x PNG into this folder with a manifest of the
input hashes and every number that appears in a title.  No result file is
written; the engine's main_chart.png in results/ stays as it was.

Every phrase in a title is chosen by this script from the numbers it
computes, never typed, so a title cannot overstate a result.

Run from the repository root:
  .venv/bin/python research/006-term-spread-switch-long-history/charts/make_charts.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))

from qune_research import style  # noqa: E402

STUDY_ID = "Study 006"
SOURCE = "FRED DGS10, DGS7, DTB3; synthetic 8.5-year par bond and bill legs (Study 002's construction)"
PERIOD = "Aug 1969 to Dec 2018, 593 monthly holding periods"
VERDICT = "Verdict: inconclusive (fragile) (section 9.5)."
DECADES = [("1969–79", 1969, 1979), ("1980s", 1980, 1989), ("1990s", 1990, 1999),
           ("2000s", 2000, 2009), ("2010–18", 2010, 2018)]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def num(x: float, decimals: int = 2) -> str:
    return f"{x:.{decimals}f}".replace("-", "−")


def signed_pct(x: float, decimals: int = 1) -> str:
    return ("+" if x > 0 else "") + style.pct(x, decimals)


def load() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    d = STUDY / "results" / "history"
    monthly_path, metrics_path = d / "monthly_base.csv", d / "metrics_base.csv"
    monthly = pd.read_csv(monthly_path, parse_dates=["execution_date", "period_end"])
    metrics = pd.read_csv(metrics_path, index_col=0)
    return monthly, metrics, {str(p.relative_to(ROOT)): sha256(p) for p in (monthly_path, metrics_path)}


def index_and_drawdown(monthly: pd.DataFrame, books: tuple[str, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    start = monthly["execution_date"].iloc[0]
    growth = (1.0 + monthly[list(books)]).cumprod()
    growth.index = monthly["period_end"]
    idx = pd.concat([pd.DataFrame([pd.Series({b: 1.0 for b in books}, name=start)]), growth])
    return idx, idx / idx.cummax() - 1.0


def shade_bills(ax, monthly: pd.DataFrame) -> int:
    cash = monthly[monthly["T1_holding"] == "BIL"]
    for _, row in cash.iterrows():
        ax.axvspan(row["execution_date"], row["period_end"], color=style.SHADE, lw=0, zorder=0)
    return int(len(cash))


def spread_chart(monthly: pd.DataFrame, numbers: dict) -> None:
    spread = monthly.set_index("execution_date")["spread_at_signal"]
    inverted = spread[spread <= 0]
    n, n_inv = int(len(spread)), int(len(inverted))
    before_1982 = int((inverted.index.year < 1982).sum())
    last_inv = inverted.index.max()
    numbers.update(spread_month_ends=n, spread_inverted_month_ends=n_inv,
                   spread_inverted_before_1982=before_1982, spread_last_inverted_execution=str(last_inv.date()))
    if before_1982 * 2 > n_inv:
        lead = f"most of them ({before_1982}) before 1982"
    else:
        lead = f"{before_1982} of them before 1982"
    finding = (f"The curve was inverted at {n_inv} of {n} month ends, {lead}; "
               f"after {last_inv.strftime('%B %Y')} the rule never left the bond")
    fig, ax = style.figure(width=8.0, height=4.6)
    style.title(fig, finding, "10-year yield minus the bond-equivalent 3-month bill yield at each signal date, "
                              "percentage points, Aug 1969 to Dec 2018. Shaded: months the rule (T1) held bills.")
    shade_bills(ax, monthly)
    ax.axhline(0.0, color=style.GREY, lw=0.8)
    ax.plot(spread.index, spread.values, color=style.ACCENT, lw=1.3)
    ax.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v * 100:.0f}".replace("-", "−")))
    ax.set_xlim(monthly["execution_date"].iloc[0], monthly["period_end"].iloc[-1])
    style.source(fig, SOURCE, PERIOD, STUDY_ID,
                 note=f"Run once; results/history/monthly_base.csv (spread_at_signal, T1_holding). {VERDICT}")
    style.save(fig, HERE / "history_spread_and_holdings")


def growth_chart(monthly: pd.DataFrame, metrics: pd.DataFrame, numbers: dict) -> None:
    idx, _dd = index_and_drawdown(monthly, ("T1", "B1", "B3"))
    sr = metrics.loc[["T1", "B1", "B3"], "sharpe_annual"].astype(float)
    last = idx.iloc[-1]
    numbers.update(growth_sharpe_annual={k: float(v) for k, v in sr.items()},
                   growth_final={k: float(v) for k, v in last.items()})
    gap = sr["T1"] - max(sr["B1"], sr["B3"])
    verb = "beat" if gap >= 0.05 else ("matched" if gap > -0.05 else "lagged")
    finding = (f"Over 1969–2018 the spread switch {verb} holding the bond: Sharpe {num(sr['T1'])} against "
               f"{num(sr['B1'])}, and {num(sr['B3'])} for the same average exposure")
    fig, ax = style.figure(width=8.0, height=4.6)
    style.title(fig, finding, "Growth of 1 unit, log scale, Aug 1969 to Dec 2018: the spread switch (T1), holding the "
                              "bond (B1), the same-exposure mix (B3). Sharpe over bills, annualised; 2 bp per side.")
    ax.set_yscale("log")
    ax.plot(idx.index, idx["B3"], color=style.GREY, lw=1.2)
    ax.plot(idx.index, idx["B1"], color=style.GREY_DARK, lw=1.3)
    ax.plot(idx.index, idx["T1"], color=style.ACCENT, lw=1.7)
    ax.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:,.0f}"))
    ax.yaxis.set_minor_formatter(style.FuncFormatter(lambda v, _p: ""))
    ax.set_xlim(idx.index[0], idx.index[-1])
    style.label_line_ends(ax, [
        style.EndLabel(f"T1 {last['T1']:.1f}", float(last["T1"]), style.ACCENT),
        style.EndLabel(f"B1 {last['B1']:.1f}", float(last["B1"]), style.GREY_DARK),
        style.EndLabel(f"B3 {last['B3']:.1f}", float(last["B3"]), style.GREY),
    ], min_gap=0.11)
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note=f"Run once; results/history/monthly_base.csv, metrics_base.csv. "
                                                     f"{VERDICT}")
    style.save(fig, HERE / "history_growth")


def drawdown_chart(monthly: pd.DataFrame, numbers: dict) -> None:
    _idx, dd = index_and_drawdown(monthly, ("T1", "B1", "B3"))
    worst = dd.min()
    numbers["drawdown_monthly_max"] = {k: float(v) for k, v in worst.items()}
    trough = dd["B1"].idxmin()
    numbers["drawdown_B1_trough"] = str(trough.date())
    cut = 1.0 - worst["T1"] / worst["B1"]
    numbers["drawdown_cut_share_vs_B1"] = float(cut)
    if cut >= 0.2:
        finding = (f"The switch cut the deepest monthly drawdown from {style.pct(worst['B1'])} to "
                   f"{style.pct(worst['T1'])}; holding the bond bottomed in {trough.strftime('%B %Y')}")
    else:
        finding = (f"The switch barely changed the deepest monthly drawdown: {style.pct(worst['T1'])} against "
                   f"{style.pct(worst['B1'])} for holding the bond")
    fig, ax = style.figure(width=8.0, height=4.6)
    style.title(fig, finding, "Drawdown from the running high of the holding-period return index, monthly, %, "
                              "Aug 1969 to Dec 2018. Shaded: months the rule held bills. 2 bp per side.")
    shade_bills(ax, monthly)
    ax.fill_between(dd.index, dd["B1"], 0.0, color=style.GREY_LIGHT, lw=0, zorder=1)
    ax.plot(dd.index, dd["T1"], color=style.ACCENT, lw=1.2, zorder=2)
    style.percent_axis(ax, decimals=0)
    ax.set_ylim(worst.min() * 1.15, 0.005)
    ax.set_xlim(dd.index[0], dd.index[-1])
    style.label_line_ends(ax, [
        style.EndLabel("Spread switch (T1)", float(dd["T1"].iloc[-1]), style.ACCENT),
        style.EndLabel("Hold the bond (B1)", float(dd["B1"].iloc[-1]) - 0.03, style.GREY_DARK),
    ], min_gap=0.07)
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note=f"Run once; results/history/monthly_base.csv. Monthly marks "
                                                     f"only. Same-exposure mix (B3): deepest {style.pct(worst['B3'])}. {VERDICT}")
    style.save(fig, HERE / "history_drawdown")


def decade_chart(monthly: pd.DataFrame, numbers: dict) -> None:
    d = monthly["T1"] - monthly["B3"]
    year = monthly["execution_date"].dt.year
    means, counts = {}, {}
    for label, lo, hi in DECADES:
        mask = (year >= lo) & (year <= hi)
        means[label], counts[label] = float(d[mask].mean() * 12.0), int(mask.sum())
    assert sum(counts.values()) == len(monthly)
    numbers.update(decade_mean_d_annual=means, decade_periods=counts)
    no_timing = [k for k, lo, hi in DECADES
                 if (monthly.loc[(year >= lo) & (year <= hi), "T1_holding"] == "IEF").all()]
    numbers["decade_without_a_bill_month"] = no_timing
    best = max(means, key=means.get)
    timing_others = [k for k, _lo, _hi in DECADES if k != best and k not in no_timing]
    # Only decades in which the rule held bills at least once carry a timing decision; the title
    # compares the best decade with those, never with the exposure-only ones.
    def name(k: str) -> str:
        return f"the {k}" if k.endswith("s") else k
    others = " and ".join(f"{signed_pct(means[k])} in {name(k)}" for k in timing_others)
    finding = (f"The switch's edge over the same-exposure mix came from {name(best)}, {signed_pct(means[best])} a "
               f"year; in the other decades with a bill month it was {others}" if timing_others else
               f"The switch's edge over the same-exposure mix came from {name(best)}, {signed_pct(means[best])} a year")
    fig, ax = style.figure(width=8.0, height=5.2)
    style.title(fig, finding, "Mean monthly difference T1 − B3, annualised (× 12), %, by decade of the execution "
                              "date, Aug 1969 to Dec 2018. Descriptive, no decision weight.")
    labels = [k for k, _lo, _hi in DECADES]
    colors = [style.ACCENT if k == best else style.GREY_LIGHT for k in labels]
    bars = ax.bar(labels, [means[k] for k in labels], color=colors, width=0.62)
    ax.axhline(0.0, color=style.GREY, lw=0.8)
    for bar, k in zip(bars, labels, strict=True):
        v = means[k]
        ax.annotate(f"{signed_pct(v)} ({counts[k]} mo)", (bar.get_x() + bar.get_width() / 2, max(v, 0.0)),
                    xytext=(0, 4), textcoords="offset points", ha="center",
                    fontsize=style.TICK_SIZE, color=style.TEXT)
    ax.set_ylim(min(min(means.values()) * 1.6, -0.002), max(means.values()) * 1.15)
    style.percent_axis(ax, decimals=1)
    exposure = (f" In {' and '.join(name(k) for k in no_timing)} the rule never held bills, so {'those bars are' if len(no_timing) > 1 else 'that bar is'} the exposure gap "
                f"(1 − w)(bond − bill), not timing." if no_timing else "")
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note="Bars in time order (decades are ordered, not ranked)."
                                                     f"{exposure} Run once; results/history/monthly_base.csv. "
                                                     f"{VERDICT}")
    style.save(fig, HERE / "history_differential_by_decade")


def main() -> int:
    style.apply()
    monthly, metrics, hashes = load()
    numbers: dict = {}
    spread_chart(monthly, numbers)
    growth_chart(monthly, metrics, numbers)
    drawdown_chart(monthly, numbers)
    decade_chart(monthly, numbers)
    outputs = sorted(str(p.relative_to(ROOT)) for p in HERE.glob("history_*.*"))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    manifest = {"made_at_utc": datetime.now(UTC).isoformat(timespec="seconds"), "repository_commit_at_run": commit,
                "inputs_sha256": hashes, "outputs": outputs, "numbers_in_titles": numbers}
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(numbers, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
