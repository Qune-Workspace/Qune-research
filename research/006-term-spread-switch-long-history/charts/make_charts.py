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

import numpy as np
import pandas as pd
from matplotlib.ticker import FixedLocator

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
        ax.axvspan(row["execution_date"], row["period_end"], color=style.GREY_FAINT, lw=0, zorder=0)
    return int(len(cash))


def log_end_labels(ax, labels: list, min_gap: float) -> None:
    """End labels for a log-scale axis: style.label_line_ends spaces labels in linear data units,
    which on a log axis lets close lines' labels touch.  Same placement rule, in log space."""
    y0, y1 = (np.log10(v) for v in ax.get_ylim())
    order = sorted(range(len(labels)), key=lambda i: labels[i].y)
    frac = [(np.log10(labels[i].y) - y0) / (y1 - y0) for i in order]
    for k in range(1, len(frac)):
        frac[k] = max(frac[k], frac[k - 1] + min_gap)
    over = frac[-1] - 0.99
    frac = [f - over for f in frac] if over > 0 else frac
    for k, i in enumerate(order):
        ax.annotate(labels[i].text, xy=(1.0, frac[k]), xycoords="axes fraction", xytext=(6.0, 0),
                    textcoords="offset points", ha="left", va="center", fontsize=style.LABEL_SIZE,
                    color=labels[i].color, annotation_clip=False)


def spread_chart(monthly: pd.DataFrame, numbers: dict) -> None:
    spread = monthly.set_index("execution_date")["spread_at_signal"]
    inverted = spread[spread <= 0]
    n, n_inv = int(len(spread)), int(len(inverted))
    before_1982 = int((inverted.index.year < 1982).sum())
    last_inv = inverted.index.max()
    later = spread.index[spread.index > last_inv]
    numbers.update(spread_month_ends=n, spread_inverted_month_ends=n_inv,
                   spread_inverted_before_1982=before_1982, spread_last_inverted_execution=str(last_inv.date()))
    # The curve inverted again after the window ends, so the title bounds the bond-only stretch by the window.
    tail = (f"; from {later[0].strftime('%B %Y')} to {monthly['execution_date'].iloc[-1].strftime('%B %Y')} "
            f"the rule held the bond" if len(later) else "")
    if len(later):
        numbers["spread_bond_only_from_execution"] = str(later[0].date())
    finding = f"The curve inverted at {n_inv} of {n} month ends, {before_1982} before 1982{tail}"
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
    # "Higher Sharpe", not "beat": the verdict is inconclusive (fragile), so the title states the
    # measured gap and the verdict side by side (Tester chart check, 2026-10-25).
    verb = ("had the higher Sharpe" if gap >= 0.05 else
            ("matched on Sharpe" if gap > -0.05 else "had the lower Sharpe"))
    same = (f"{num(sr['B1'])} for holding the bond and for the same-exposure mix" if num(sr["B1"]) == num(sr["B3"])
            else f"{num(sr['B1'])} for holding the bond and {num(sr['B3'])} for the same-exposure mix")
    finding = (f"Over 1969–2018 the spread switch {verb}, {num(sr['T1'])} against {same}; "
               f"the verdict is inconclusive (fragile)")
    fig, ax = style.figure(width=8.0, height=4.6)
    style.title(fig, finding, "Growth of 1 unit, log scale, Aug 1969 to Dec 2018: the spread switch (T1), holding the "
                              "bond (B1), the same-exposure mix (B3). Sharpe over bills, annualised; 2 bp per side.")
    ax.set_yscale("log")
    ax.plot(idx.index, idx["B3"], color=style.GREY, lw=1.2)
    ax.plot(idx.index, idx["B1"], color=style.GREY_DARK, lw=1.3)
    ax.plot(idx.index, idx["T1"], color=style.ACCENT, lw=1.7)
    ax.yaxis.set_major_locator(FixedLocator([1, 2, 5, 10, 20, 50]))
    ax.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:,.0f}"))
    ax.yaxis.set_minor_formatter(style.FuncFormatter(lambda v, _p: ""))
    ax.set_xlim(idx.index[0], idx.index[-1])
    log_end_labels(ax, [
        style.EndLabel(f"T1 {last['T1']:.1f}", float(last["T1"]), style.ACCENT),
        style.EndLabel(f"B1 {last['B1']:.1f}", float(last["B1"]), style.GREY_DARK),
        style.EndLabel(f"B3 {last['B3']:.1f}", float(last["B3"]), style.GREY),
    ], min_gap=0.055)
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note=f"Run once; results/history/monthly_base.csv, metrics_base.csv. "
                                                     f"{VERDICT}")
    style.save(fig, HERE / "history_growth")


def drawdown_chart(monthly: pd.DataFrame, numbers: dict) -> None:
    _idx, dd = index_and_drawdown(monthly, ("T1", "B1", "B3"))
    worst = dd.min()
    numbers["drawdown_monthly_max"] = {k: float(v) for k, v in worst.items()}
    # Each index point is a period-end mark; the holding period it closes is named by its execution
    # month (as the tear-sheets date rows), so the B1 trough at 1980-03-03 is the February 1980 period.
    trough = dd["B1"].idxmin()
    trough_period = monthly.loc[monthly["period_end"] == trough, "execution_date"].iloc[0]
    numbers["drawdown_B1_trough"] = str(trough.date())
    numbers["drawdown_B1_trough_holding_period"] = trough_period.strftime("%Y-%m")
    numbers["drawdown_cut_share_vs_B1"] = float(1.0 - worst["T1"] / worst["B1"])
    numbers["drawdown_cut_share_vs_B3"] = float(1.0 - worst["T1"] / worst["B3"])
    # Against both benchmarks, as the pre-registration asks; the title states the three depths and
    # never a single "cut" share measured against the weaker benchmark (Tester chart check, 2026-10-25).
    finding = (f"The switch's deepest monthly drawdown was {style.pct(worst['T1'])}, against "
               f"{style.pct(worst['B3'])} for the same-exposure mix and {style.pct(worst['B1'])} for holding the bond")
    fig, ax = style.figure(width=8.0, height=4.6)
    style.title(fig, finding, "Drawdown from the running high of the holding-period return index, monthly, %, "
                              "Aug 1969 to Dec 2018. Pale vertical bands: months the rule held bills. 2 bp per side.")
    shade_bills(ax, monthly)
    ax.fill_between(dd.index, dd["B1"], 0.0, color=style.GREY_LIGHT, lw=0, zorder=1)
    ax.plot(dd.index, dd["B3"], color=style.GREY_DARK, lw=0.9, zorder=2)
    ax.plot(dd.index, dd["T1"], color=style.ACCENT, lw=1.2, zorder=3)
    style.percent_axis(ax, decimals=0)
    ax.set_ylim(worst.min() * 1.15, 0.005)
    ax.set_xlim(dd.index[0], dd.index[-1])
    style.label_line_ends(ax, [
        style.EndLabel("Switch (T1)", float(dd["T1"].iloc[-1]), style.ACCENT),
        style.EndLabel("Mix (B3)", float(dd["B3"].iloc[-1]), style.GREY_DARK),
        style.EndLabel("Bond (B1), area", float(dd["B1"].iloc[-1]), style.GREY),
    ], min_gap=0.07)
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note=f"Run once; results/history/monthly_base.csv. Monthly marks "
                                                     f"only; holding the bond bottomed with the "
                                                     f"{trough_period.strftime('%B %Y')} holding period. {VERDICT}")
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
    # Only decades in which the rule held bills at least once carry a timing decision; the title names
    # every such decade with a positive edge (not only the largest: 1969–79 alone was under half of the
    # summed edge, Tester chart check 2026-10-25) and compares them with the other timing decades, never
    # with the exposure-only ones.
    timing = [k for k, _lo, _hi in DECADES if k not in no_timing]
    ahead = [k for k in timing if means[k] > 0]
    behind = [k for k in timing if means[k] <= 0]
    total = sum(means[k] * counts[k] for k in means)
    numbers["decade_share_of_summed_edge"] = {k: float(means[k] * counts[k] / total) for k in means}

    def name(k: str) -> str:
        return f"the {k}" if k.endswith("s") else k

    bounds = {k: (lo, hi) for k, lo, hi in DECADES}
    pos = [i for i, (k, _lo, _hi) in enumerate(DECADES) if k in ahead]
    if len(ahead) > 1 and pos == list(range(pos[0], pos[0] + len(pos))):
        where = f"{bounds[ahead[0]][0]}–{str(bounds[ahead[-1]][1])[2:]}"
    else:
        where = " and ".join(name(k) for k in ahead)
    gains = " and ".join(signed_pct(means[k]) for k in ahead)
    if behind:
        which = "the only later decade with bill months" if len(behind) == 1 else "the later decades with bill months"
        rest = f"; in {' and '.join(name(k) for k in behind)}, {which}, it was " + \
            " and ".join(signed_pct(means[k]) for k in behind)
    else:
        rest = ""
    finding = (f"The switch's edge over the same-exposure mix came from {where}, {gains} a year{rest}"
               if ahead else f"The switch had no positive edge over the same-exposure mix in any decade with bill "
                             f"months{rest}")
    fig, ax = style.figure(width=8.0, height=5.2)
    style.title(fig, finding, "Mean monthly difference T1 − B3, annualised (× 12), %, by decade of the execution "
                              "date, Aug 1969 to Dec 2018. Descriptive, no decision weight.")
    labels = [k for k, _lo, _hi in DECADES]
    colors = [style.ACCENT if k in ahead else (style.GREY_LIGHT if k in behind else style.GREY_FAINT) for k in labels]
    bars = ax.bar(labels, [means[k] for k in labels], color=colors, width=0.62)
    for bar, k in zip(bars, labels, strict=True):
        if k in no_timing:
            bar.set_hatch("///")
            bar.set_edgecolor(style.GREY_LIGHT)
            bar.set_linewidth(0)
    ax.axhline(0.0, color=style.GREY, lw=0.8)
    for bar, k in zip(bars, labels, strict=True):
        v = means[k]
        tag = f"{signed_pct(v)} ({counts[k]} mo)" + ("\nno bill month:\nexposure only" if k in no_timing else "")
        ax.annotate(tag, (bar.get_x() + bar.get_width() / 2, max(v, 0.0)),
                    xytext=(0, 4), textcoords="offset points", ha="center", va="bottom",
                    fontsize=style.TICK_SIZE, color=style.TEXT_MUTED if k in no_timing else style.TEXT)
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
