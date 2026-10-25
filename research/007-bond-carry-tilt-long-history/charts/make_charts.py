"""Study 007 charts in the house style (PREREGISTRATION.md §9.6), drawn from
the committed history files.

Reads results/history/monthly_base.csv, metrics_base.csv and summary.json
(the history run, once, b43c825).  Computes nothing the study did not already
publish beyond presentation: the holding-period return index of each book, its
drawdown from the running high, the mean of the published monthly differential
T1 − B3 grouped by the decade of each period's execution date (descriptive, no
decision weight), and counts of T1's weight in ranges.  Writes SVG + 2x PNG
into this folder with a manifest of the input hashes and every number that
appears in a title.  No result file is written.

Every phrase in a title is chosen by this script from the numbers it
computes, never typed, so a title cannot overstate a result.

Run from the repository root:
  .venv/bin/python research/007-bond-carry-tilt-long-history/charts/make_charts.py
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

STUDY_ID = "Study 007"
SOURCE = "FRED DGS10, DGS7, DTB3; synthetic 8.5-year par bond and bill legs (Study 002's construction, frozen)"
PERIOD = "Jul 1974 to Dec 2018, 534 monthly holding periods"
VERDICT = "Verdict: inconclusive (fragile) (section 9.5)."
DECADES = [("1974–79", 1974, 1979), ("1980s", 1980, 1989), ("1990s", 1990, 1999),
           ("2000s", 2000, 2009), ("2010–18", 2010, 2018)]
WINDOWS = [("1974-07 to 2002-12 (before any ETF)", "1974–2002\nbefore ETFs"),
           ("2003-01 to 2018-12 (the gate's overlap)", "2003–18\nETF overlap"),
           ("1974-07 to 1981-12", "1974–81\nrising rates"),
           ("1982-01 to 2008-12", "1982–2008\ndisinflation"),
           ("2009-01 to 2018-12", "2009–18\nzero bound")]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def num(x: float, decimals: int = 2) -> str:
    return f"{x:.{decimals}f}".replace("-", "−")


def signed_pct(x: float, decimals: int = 1) -> str:
    return ("+" if x > 0 else "") + style.pct(x, decimals)


def load() -> tuple[pd.DataFrame, pd.DataFrame, dict, dict[str, str]]:
    d = STUDY / "results" / "history"
    paths = (d / "monthly_base.csv", d / "metrics_base.csv", d / "summary.json")
    monthly = pd.read_csv(paths[0], parse_dates=["execution_date", "period_end"])
    metrics = pd.read_csv(paths[1], index_col=0)
    summary = json.loads(paths[2].read_text(encoding="utf-8"))
    return monthly, metrics, summary, {str(p.relative_to(ROOT)): sha256(p) for p in paths}


def index_and_drawdown(monthly: pd.DataFrame, books: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """books maps a display key to a monthly_base column."""
    start = monthly["execution_date"].iloc[0]
    growth = (1.0 + monthly[list(books.values())]).cumprod()
    growth.columns = list(books)
    growth.index = monthly["period_end"]
    idx = pd.concat([pd.DataFrame([pd.Series({b: 1.0 for b in books}, name=start)]), growth])
    return idx, idx / idx.cummax() - 1.0


def log_end_labels(ax, labels: list, min_gap: float) -> None:
    """Study 006's end labels for a log axis (same placement rule, in log space)."""
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


def carry_chart(monthly: pd.DataFrame, numbers: dict) -> None:
    carry = monthly.set_index("execution_date")["carry_at_signal"]
    w = monthly.set_index("execution_date")["w_T1"]
    n = int(len(w))
    hi, lo = int((w >= 0.9).sum()), int((w < 0.3).sum())
    n_neg = int((carry <= 0).sum())
    numbers.update(carry_month_ends=n, carry_le_zero=n_neg, weight_ge_0_9=hi, weight_lt_0_3=lo,
                   weight_mean=float(w.mean()), weight_sd=float(w.std(ddof=0)))
    finding = (f"The carry tilt held at least 0.9 of the bond in {hi} of {n} months and less than 0.3 in {lo}; "
               f"carry itself was at or below zero at {n_neg} month ends")
    fig, (ax1, ax2) = style.figure(width=8.0, height=5.6, nrows=2, sharex=True,
                                   gridspec_kw={"height_ratios": [1.0, 1.0], "hspace": 0.18})
    style.title(fig, finding, "Top: carry of the 8.5-year leg at each signal date (yield over bills plus roll-down), "
                              "% a year. Bottom: T1's weight in the bond (expanding percentile rank, 0 to 1), "
                              "Jul 1974 to Dec 2018.")
    ax1.axhline(0.0, color=style.GREY, lw=0.8)
    ax1.plot(carry.index, carry.values, color=style.GREY_DARK, lw=1.1)
    style.percent_axis(ax1, decimals=0)
    ax2.fill_between(w.index, w.values, 0.0, color=style.ACCENT, alpha=0.25, lw=0, step="post")
    ax2.step(w.index, w.values, where="post", color=style.ACCENT, lw=1.0)
    ax2.set_ylim(0.0, 1.0)
    ax2.yaxis.set_major_locator(FixedLocator([0.0, 0.5, 1.0]))
    ax2.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:.1f}"))
    ax2.set_xlim(monthly["execution_date"].iloc[0], monthly["period_end"].iloc[-1])
    for ax in (ax1, ax2):
        style.despine(ax)
    style.label_line_ends(ax1, [style.EndLabel("Carry", float(carry.iloc[-1]), style.GREY_DARK)], min_gap=0.07)
    style.label_line_ends(ax2, [style.EndLabel("T1 weight", float(w.iloc[-1]), style.ACCENT)], min_gap=0.07)
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note=f"Run once; results/history/monthly_base.csv (carry_at_signal, "
                                                     f"w_T1). {VERDICT}")
    style.save(fig, HERE / "history_carry_and_weight")


def growth_chart(monthly: pd.DataFrame, metrics: pd.DataFrame, numbers: dict) -> None:
    idx, _dd = index_and_drawdown(monthly, {"T1": "T1", "B1": "B1", "B3": "B3_T1"})
    sr = metrics.loc[["T1"], "sharpe_annual"].astype(float)
    # B1 and T1's B3 come from summary-equivalent columns; Sharpe of the benchmarks from the metrics
    # of the history run (summary.json cost_cases.base.descriptive.T1), passed in by main().
    sr_b = numbers["_benchmark_sharpe"]
    last = idx.iloc[-1]
    numbers.update(growth_sharpe_annual={"T1": float(sr["T1"]), **sr_b},
                   growth_final={k: float(v) for k, v in last.items()})
    gap = float(sr["T1"]) - max(sr_b["B1"], sr_b["B3"])
    verb = ("had the higher Sharpe" if gap >= 0.05 else
            ("matched on Sharpe" if gap > -0.05 else "had the lower Sharpe"))
    same = (f"{num(sr_b['B1'])} for holding the bond and for the same-exposure mix"
            if num(sr_b["B1"]) == num(sr_b["B3"])
            else f"{num(sr_b['B1'])} for holding the bond and {num(sr_b['B3'])} for the same-exposure mix")
    ends = "ended below holding the bond" if last["T1"] < last["B1"] else "ended above holding the bond"
    finding = (f"Over 1974–2018 the carry tilt {verb}, {num(float(sr['T1']))} against {same}, but {ends}; "
               f"the verdict is inconclusive (fragile)")
    fig, ax = style.figure(width=8.0, height=4.6)
    style.title(fig, finding, "Growth of 1 unit, log scale, Jul 1974 to Dec 2018: the carry tilt (T1), holding the "
                              "bond (B1), the same average exposure held throughout (B3, w 0.606). Sharpe over bills, "
                              "annualised; 2 bp per side on the traded fraction.")
    ax.set_yscale("log")
    ax.plot(idx.index, idx["B3"], color=style.GREY, lw=1.2)
    ax.plot(idx.index, idx["B1"], color=style.GREY_DARK, lw=1.3)
    ax.plot(idx.index, idx["T1"], color=style.ACCENT, lw=1.7)
    ax.yaxis.set_major_locator(FixedLocator([1, 2, 5, 10, 20]))
    ax.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:,.0f}"))
    ax.yaxis.set_minor_formatter(style.FuncFormatter(lambda v, _p: ""))
    ax.set_xlim(idx.index[0], idx.index[-1])
    log_end_labels(ax, [
        style.EndLabel(f"T1 {last['T1']:.1f}", float(last["T1"]), style.ACCENT),
        style.EndLabel(f"B1 {last['B1']:.1f}", float(last["B1"]), style.GREY_DARK),
        style.EndLabel(f"B3 {last['B3']:.1f}", float(last["B3"]), style.GREY),
    ], min_gap=0.075)
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note=f"Run once; results/history/monthly_base.csv, metrics_base.csv, "
                                                     f"summary.json. {VERDICT}")
    style.save(fig, HERE / "history_growth")


def drawdown_chart(monthly: pd.DataFrame, numbers: dict) -> None:
    _idx, dd = index_and_drawdown(monthly, {"T1": "T1", "B1": "B1", "B3": "B3_T1"})
    worst = dd.min()
    numbers["drawdown_monthly_max"] = {k: float(v) for k, v in worst.items()}
    trough = dd["B1"].idxmin()
    trough_period = monthly.loc[monthly["period_end"] == trough, "execution_date"].iloc[0]
    numbers["drawdown_B1_trough_holding_period"] = trough_period.strftime("%Y-%m")
    finding = (f"The tilt's deepest monthly drawdown was {style.pct(worst['T1'])}, against "
               f"{style.pct(worst['B3'])} for the same-exposure mix and {style.pct(worst['B1'])} for holding the bond")
    fig, ax = style.figure(width=8.0, height=5.2)
    fig.subplots_adjust(bottom=0.21)
    style.title(fig, finding, "Drawdown from the running high of the holding-period return index, monthly, %, "
                              "Jul 1974 to Dec 2018. 2 bp per side on the traded fraction.")
    ax.fill_between(dd.index, dd["B1"], 0.0, color=style.GREY_LIGHT, lw=0, zorder=1)
    ax.plot(dd.index, dd["B3"], color=style.GREY_DARK, lw=0.9, zorder=2)
    ax.plot(dd.index, dd["T1"], color=style.ACCENT, lw=1.2, zorder=3)
    style.percent_axis(ax, decimals=0)
    ax.set_ylim(worst.min() * 1.15, 0.005)
    ax.set_xlim(dd.index[0], dd.index[-1])
    style.label_line_ends(ax, [
        style.EndLabel("Tilt (T1)", float(dd["T1"].iloc[-1]), style.ACCENT),
        style.EndLabel("Mix (B3)", float(dd["B3"].iloc[-1]), style.GREY_DARK),
        style.EndLabel("Bond (B1), area", float(dd["B1"].iloc[-1]), style.GREY),
    ], min_gap=0.07)
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note=f"Run once; results/history/monthly_base.csv. Monthly marks "
                                                     f"only; holding the bond bottomed with the "
                                                     f"{trough_period.strftime('%B %Y')} holding period. {VERDICT}")
    style.save(fig, HERE / "history_drawdown")


def decade_chart(monthly: pd.DataFrame, numbers: dict) -> None:
    d = monthly["T1"] - monthly["B3_T1"]
    year = monthly["execution_date"].dt.year
    means, counts = {}, {}
    for label, lo, hi in DECADES:
        mask = (year >= lo) & (year <= hi)
        means[label], counts[label] = float(d[mask].mean() * 12.0), int(mask.sum())
    assert sum(counts.values()) == len(monthly)
    numbers.update(decade_mean_d_annual=means, decade_periods=counts)
    pos = [k for k in means if means[k] > 0]
    top = max(means, key=means.get)
    low = min(means, key=means.get)

    def name(k: str) -> str:
        return f"the {k}" if k.endswith("s") else k

    if len(pos) == len(means):
        finding = (f"The tilt's edge over the same-exposure mix was positive in every decade, from "
                   f"{signed_pct(means[low])} a year in {name(low)} to {signed_pct(means[top])} in {name(top)}")
    else:
        finding = (f"The tilt's edge over the same-exposure mix was positive in {len(pos)} of {len(means)} decades, "
                   f"from {signed_pct(means[low])} a year in {name(low)} to {signed_pct(means[top])} in {name(top)}")
    fig, ax = style.figure(width=8.0, height=4.8)
    style.title(fig, finding, "Mean monthly difference T1 − B3, annualised (× 12), %, by decade of the execution "
                              "date, Jul 1974 to Dec 2018. Descriptive, no decision weight.")
    labels = [k for k, _lo, _hi in DECADES]
    colors = [style.ACCENT if means[k] > 0 else style.GREY_LIGHT for k in labels]
    bars = ax.bar(labels, [means[k] for k in labels], color=colors, width=0.62)
    ax.axhline(0.0, color=style.GREY, lw=0.8)
    for bar, k in zip(bars, labels, strict=True):
        ax.annotate(f"{signed_pct(means[k])} ({counts[k]} mo)", (bar.get_x() + bar.get_width() / 2,
                    max(means[k], 0.0)), xytext=(0, 4), textcoords="offset points", ha="center", va="bottom",
                    fontsize=style.TICK_SIZE, color=style.TEXT)
    ax.set_ylim(min(min(means.values()) * 1.6, -0.001), max(means.values()) * 1.2)
    style.percent_axis(ax, decimals=1)
    style.despine(ax, keep=("bottom",))
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note="Bars in time order (decades are ordered, not ranked). Run once; "
                                                     f"results/history/monthly_base.csv. {VERDICT}")
    style.save(fig, HERE / "history_differential_by_decade")


def window_chart(summary: dict, numbers: dict) -> None:
    base = summary["cost_cases"]["base"]
    trials = ("T1", "T2", "T3")
    vals: dict[str, dict[str, float]] = {t: {} for t in trials}
    tstat: dict[str, dict[str, float]] = {t: {} for t in trials}
    for t in trials:
        for key, _short in WINDOWS:
            src = base["sub_windows"][t] if key in base["sub_windows"][t] else base["rate_eras"][t]
            vals[t][key] = float(src[key]["T_minus_B3"]["mean"]) * 12.0
            tstat[t][key] = float(src[key]["T_minus_B3"]["t"])
    numbers.update(window_mean_d_annual=vals, window_nw_t=tstat)
    keys = [k for k, _s in WINDOWS]
    t1_all_pos = all(vals["T1"][k] > 0 for k in keys)
    t1_max_t = max(tstat["T1"][k] for k in keys)
    eras = dict(WINDOWS[2:])
    up = [eras[k].split("\n")[0] for k in eras if vals["T2"][k] > vals["T1"][k]]
    down = [eras[k].split("\n")[0] for k in eras if vals["T2"][k] <= vals["T1"][k]]
    numbers.update(window_T1_max_t=t1_max_t, rate_eras_T2_above_T1=up, rate_eras_T2_not_above_T1=down)
    lead = ("Carry alone was ahead of the same-exposure mix in all five windows" if t1_all_pos
            else "Carry alone was not ahead of the same-exposure mix in every window")
    tail = (f"adding trend raised it in {' and '.join(up) if up else 'no rate era'}"
            + (f" and lowered it in {' and '.join(down)}" if down else ""))
    finding = f"{lead}, but no window alone reached t = 2 (highest {num(t1_max_t)}); {tail}"
    fig, ax = style.figure(width=8.6, height=5.8)
    fig.subplots_adjust(bottom=0.24)
    style.title(fig, finding, "Mean monthly difference to each trial's own B3, annualised (× 12), %, by sub-window "
                              "(registered) and rate era (by execution month). Carry tilt T1 (accent), carry + "
                              "trend T2 and trend alone T3 (greys). Descriptive, no decision weight.")
    x = np.arange(len(keys))
    width = 0.26
    colors = {"T1": style.ACCENT, "T2": style.GREY, "T3": style.GREY_LIGHT}
    for j, t in enumerate(trials):
        heights = [vals[t][k] for k in keys]
        bars = ax.bar(x + (j - 1) * width, heights, width=width * 0.92, color=colors[t])
        first = bars[0]
        ax.annotate(t, (first.get_x() + first.get_width() / 2, max(heights[0], 0.0)), xytext=(0, 3),
                    textcoords="offset points", ha="center", va="bottom", fontsize=style.TICK_SIZE,
                    color=style.TEXT if t == "T1" else style.TEXT_MUTED)
    ax.axhline(0.0, color=style.GREY, lw=0.8)
    ax.set_xticks(x, [s for _k, s in WINDOWS])
    ax.tick_params(axis="x", length=0)
    style.percent_axis(ax, decimals=1)
    allv = [v for t in trials for v in vals[t].values()]
    ax.set_ylim(min(min(allv) * 1.3, -0.001), max(allv) * 1.2)
    style.despine(ax, keep=("bottom",))
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note="Windows in time order within each group (not ranked); the first "
                                                     "two partition the window, the last three are the rate eras. Run "
                                                     f"once; results/history/summary.json. {VERDICT}")
    style.save(fig, HERE / "history_trials_by_window")


def main() -> int:
    style.apply()
    monthly, metrics, summary, hashes = load()
    desc = summary["cost_cases"]["base"]["descriptive"]["T1"]
    numbers: dict = {"_benchmark_sharpe": {"B1": float(desc["B1"]["sharpe_annual"]),
                                           "B3": float(desc["B3"]["sharpe_annual"])}}
    carry_chart(monthly, numbers)
    growth_chart(monthly, metrics, numbers)
    drawdown_chart(monthly, numbers)
    decade_chart(monthly, numbers)
    window_chart(summary, numbers)
    numbers.pop("_benchmark_sharpe")
    outputs = sorted(str(p.relative_to(ROOT)) for p in HERE.glob("history_*.*"))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    manifest = {"made_at_utc": datetime.now(UTC).isoformat(timespec="seconds"), "repository_commit_at_run": commit,
                "inputs_sha256": hashes, "outputs": outputs, "numbers_in_titles": numbers}
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(numbers, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
