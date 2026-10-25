"""Study 008 charts in the house style (PREREGISTRATION.md §9.6), drawn from
the committed history files.

Adapted from Study 007's charts/make_charts.py (with the fixes of its Tester
chart check, CHART_REVIEW.md fourth section).  Reads
results/history/monthly_base.csv, metrics_base.csv and summary.json (the
history run, once, 2026-10-25T21:19:39Z, code 031c134).  Computes nothing the
study did not already publish beyond presentation: the holding-period return
index of each book, its drawdown from the running high, the mean of the
published monthly differential T1 − B3 grouped by the decade of each period's
execution date (descriptive, no decision weight), and counts of T1's weight
and the real yield in ranges.  Writes SVG + 2x PNG into this folder with a
manifest of the input hashes and every number that appears in a title.  No
result file is written.

The four registered charts (§9.6): the real yield with T1's weight path; T1
against B1 and B3, growth and drawdown (two figures); the differential by
decade; the three trials by sub-window (with the rate eras beside them).

Every phrase in a title is chosen by this script from the numbers it
computes, never typed, so a title cannot overstate a result.

Run from the repository root:
  .venv/bin/python research/008-bond-value-tilt-long-history/charts/make_charts.py
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
from matplotlib.ticker import FixedLocator, MultipleLocator

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))

from qune_research import style  # noqa: E402

sys.path.insert(0, str(STUDY))
from src.stats import newey_west_mean  # noqa: E402  (the study's own Newey-West, 6 lags)

STUDY_ID = "Study 008"
SOURCE = ("FRED DGS10, DGS7, DTB3, CPIAUCNS (ALFRED release dates); synthetic 8.5-year par bond and bill legs "
          "(Study 002's construction, frozen)")
PERIOD = "Jul 1974 to Dec 2018, 534 monthly holding periods (T1b from Jul 1979, 474)"
VERDICT = "Verdict: not supported (section 9.5)."
DECADES = [("1974–79", 1974, 1979), ("1980s", 1980, 1989), ("1990s", 1990, 1999),
           ("2000s", 2000, 2009), ("2010–18", 2010, 2018)]
BEFORE, OVERLAP = "1974-07 to 2002-12 (before any ETF)", "2003-01 to 2018-12 (the gate's overlap)"
WINDOWS = [(BEFORE, "1974–2002\nbefore ETFs"),
           (OVERLAP, "2003–18\nETF overlap"),
           ("1974-07 to 1985-12 (complement of the era window)", "1974–85\nbefore 1986"),
           ("1974-07 to 1981-12", "1974–81\nrising rates"),
           ("1982-01 to 2008-12", "1982–2008\ndisinflation"),
           ("2009-01 to 2018-12", "2009–18\nzero bound")]
TRIALS = ("T1", "T1a", "T1b")


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


def real_yield_chart(monthly: pd.DataFrame, numbers: dict) -> None:
    ry = monthly.set_index("execution_date")["r_CPIAUCNS"]
    w = monthly.set_index("execution_date")["w_T1"]
    n = int(len(w))
    hi, lo = int((w >= 0.9).sum()), int((w < 0.3).sum())
    n_neg = int((ry <= 0).sum())
    hi_dates = w.index[w >= 0.9]
    lo_2000 = int(((w < 0.3) & (w.index.year >= 2000)).sum())
    ry_peak = ry.idxmax()
    numbers.update(real_yield_month_ends=n, real_yield_le_zero=n_neg, weight_ge_0_9=hi, weight_lt_0_3=lo,
                   weight_lt_0_3_from_2000=lo_2000, weight_ge_0_9_first=hi_dates.min().strftime("%Y-%m"),
                   weight_ge_0_9_last=hi_dates.max().strftime("%Y-%m"), weight_mean=float(w.mean()),
                   weight_sd=float(w.std(ddof=0)), real_yield_min=float(ry.min()), real_yield_max=float(ry.max()),
                   real_yield_max_month=ry_peak.strftime("%Y-%m"))
    peak = (f", when the real yield peaked at {style.pct(float(ry.max()))}"
            if hi_dates.min() <= ry_peak <= hi_dates.max() else "")
    finding = (f"The value tilt held 0.9 or more of the bond only between {hi_dates.min():%B %Y} and "
               f"{hi_dates.max():%B %Y}{peak}, and less than 0.3 in {lo} of {n} months, {lo_2000} of them from 2000")
    fig, (ax1, ax2) = style.figure(width=8.0, height=5.6, nrows=2, sharex=True,
                                   gridspec_kw={"height_ratios": [1.0, 1.0], "hspace": 0.18})
    style.title(fig, finding, "Top: real yield at each signal date (10-year yield less trailing 12-month headline "
                              "CPI inflation to the latest month published by then), % a year. Bottom: T1's weight in the bond "
                              "(expanding percentile rank, 0 to 1), Jul 1974 to Dec 2018.")
    ax1.axhline(0.0, color=style.GREY, lw=0.8)
    ax1.plot(ry.index, ry.values, color=style.GREY_DARK, lw=1.1)
    style.percent_axis(ax1, decimals=0)
    ax1.yaxis.set_major_locator(MultipleLocator(0.02))  # whole-percent ticks, so no label is rounded
    ax2.fill_between(w.index, w.values, 0.0, color=style.ACCENT, alpha=0.25, lw=0, step="post")
    ax2.step(w.index, w.values, where="post", color=style.ACCENT, lw=1.0)
    ax2.set_ylim(0.0, 1.0)
    ax2.yaxis.set_major_locator(FixedLocator([0.0, 0.5, 1.0]))
    ax2.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:.1f}"))
    ax2.set_xlim(monthly["execution_date"].iloc[0], monthly["period_end"].iloc[-1])
    for ax in (ax1, ax2):
        style.despine(ax)
    style.label_line_ends(ax1, [style.EndLabel("Real yield", float(ry.iloc[-1]), style.GREY_DARK)], min_gap=0.07)
    style.label_line_ends(ax2, [style.EndLabel("T1 weight", float(w.iloc[-1]), style.ACCENT)], min_gap=0.07)
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note=f"Run once; results/history/monthly_base.csv (r_CPIAUCNS, "
                                                     f"w_T1), plotted at each period's execution date; the real "
                                                     f"yield was at or below zero at {n_neg} of {n} month ends. "
                                                     f"{VERDICT}")
    style.save(fig, HERE / "history_real_yield_and_weight")


def growth_chart(monthly: pd.DataFrame, metrics: pd.DataFrame, numbers: dict) -> None:
    idx, _dd = index_and_drawdown(monthly, {"T1": "T1", "B1": "B1", "B3": "B3_T1"})
    sr = float(metrics.loc["T1", "sharpe_annual"])
    sr_b = numbers["_benchmark_sharpe"]
    w_b3 = numbers["_weight_b3"]
    last = idx.iloc[-1]
    numbers.update(growth_sharpe_annual={"T1": sr, **sr_b}, growth_final={k: float(v) for k, v in last.items()},
                   growth_B3_weight=w_b3)
    p_lw = numbers["_lw_p_vs_B3"]
    numbers["growth_ledoit_wolf_p_vs_B3"] = p_lw
    numbers["growth_ledoit_wolf_p_vs_B1"] = numbers["_lw_p_vs_B1"]
    same = (f"{num(sr_b['B1'])} for the bond and the same-exposure mix" if num(sr_b["B1"]) == num(sr_b["B3"])
            else f"{num(sr_b['B1'])} for the bond and {num(sr_b['B3'])} for the same-exposure mix")
    ends = ("but it ended below the bond" if last["T1"] < last["B1"] and sr > sr_b["B1"]
            else ("and it ended below the bond" if last["T1"] < last["B1"] else "and it ended above the bond"))
    # The Sharpe gap with its test, never a verb that reads as "beat" (Tester chart check of 007).
    finding = (f"Over 1974–2018 the value tilt's Sharpe was {num(sr)} against {same} "
               f"(p = {num(p_lw)}), {ends}; verdict not supported")
    fig, ax = style.figure(width=8.0, height=5.0)
    fig.subplots_adjust(bottom=0.2)
    style.title(fig, finding, "Growth of 1 unit, log scale, Jul 1974 to Dec 2018: the value tilt (T1), holding the "
                              "bond (B1), the same average exposure held throughout (B3, w "
                              f"{w_b3:.3f}). Sharpe over bills, annualised; 2 bp per side on the traded fraction.")
    ax.set_yscale("log")
    ax.plot(idx.index, idx["B3"], color=style.GREY, lw=1.2)
    ax.plot(idx.index, idx["B1"], color=style.GREY_DARK, lw=1.3)
    ax.plot(idx.index, idx["T1"], color=style.ACCENT, lw=1.7)
    ax.yaxis.set_major_locator(FixedLocator([1, 2, 5, 10, 20]))
    ax.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:,.0f}"))
    ax.yaxis.set_minor_formatter(style.FuncFormatter(lambda v, _p: ""))
    ax.tick_params(axis="y", which="minor", length=0)
    ax.set_xlim(idx.index[0], idx.index[-1])
    log_end_labels(ax, [
        style.EndLabel(f"T1 {last['T1']:.1f}", float(last["T1"]), style.ACCENT),
        style.EndLabel(f"B1 {last['B1']:.1f}", float(last["B1"]), style.GREY_DARK),
        style.EndLabel(f"B3 {last['B3']:.1f}", float(last["B3"]), style.GREY),
    ], min_gap=0.075)
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note=f"Run once; results/history/monthly_base.csv, metrics_base.csv, "
                                                     f"summary.json (Ledoit–Wolf test vs B3). {VERDICT}")
    style.save(fig, HERE / "history_growth")


def drawdown_chart(monthly: pd.DataFrame, numbers: dict) -> None:
    _idx, dd = index_and_drawdown(monthly, {"T1": "T1", "B1": "B1", "B3": "B3_T1"})
    worst = dd.min()
    numbers["drawdown_monthly_max"] = {k: float(v) for k, v in worst.items()}
    troughs = {}
    for k in ("T1", "B3", "B1"):
        t = dd[k].idxmin()
        troughs[k] = monthly.loc[monthly["period_end"] == t, "execution_date"].iloc[0]
    numbers["drawdown_trough_holding_period"] = {k: v.strftime("%Y-%m") for k, v in troughs.items()}
    vs_mix = "deeper than" if worst["T1"] < worst["B3"] else "no deeper than"
    vs_bond = ("less than half the bond's" if abs(worst["T1"]) < 0.5 * abs(worst["B1"])
               else ("less than the bond's" if worst["T1"] > worst["B1"] else "as deep as the bond's or deeper:"))
    finding = (f"The tilt's deepest drawdown was {style.pct(worst['T1'])}, {vs_mix} the same-exposure mix's "
               f"{style.pct(worst['B3'])} but {vs_bond} {style.pct(worst['B1'])} (month-end marks)")
    when = ", ".join(f"{k} with the {v.strftime('%B %Y')} holding period" for k, v in troughs.items())
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
                                                     f"only; deepest points: {when}. {VERDICT}")
    style.save(fig, HERE / "history_drawdown")


def decade_chart(monthly: pd.DataFrame, numbers: dict) -> None:
    d = monthly["T1"] - monthly["B3_T1"]
    year = monthly["execution_date"].dt.year
    means, counts, tstats = {}, {}, {}
    for label, lo, hi in DECADES:
        mask = (year >= lo) & (year <= hi)
        means[label], counts[label] = float(d[mask].mean() * 12.0), int(mask.sum())
        tstats[label] = float(newey_west_mean(d[mask].reset_index(drop=True))["t"])
    assert sum(counts.values()) == len(monthly)
    numbers.update(decade_mean_d_annual=means, decade_periods=counts, decade_nw_t=tstats)
    era = numbers["_era_row"]

    def name(k: str) -> str:
        return f"the {k}" if k.endswith("s") else k

    t_lo, t_hi = min(tstats.values()), max(tstats.values())
    sig_k = [k for k in tstats if abs(tstats[k]) >= 2.0]
    numbers["decade_abs_t_ge_2"] = sig_k
    if not sig_k:
        qual = f"; none alone significant (t {num(t_lo, 1)} to {num(t_hi, 1)})"
    else:
        qual = ("; only " + " and ".join(f"{name(k)} (t {num(tstats[k], 1)})" for k in sig_k)
                + " alone significant")
    pos = [k for k in means if means[k] > 0]
    top = max(means, key=means.get)
    low = min(means, key=means.get)

    order = [k for k, _lo, _hi in DECADES]
    neg = [k for k in order if means[k] <= 0]
    numbers["decade_title_form"] = "sign change" if pos and neg and order[:len(pos)] == pos else "count"
    if numbers["decade_title_form"] == "sign change":
        # The message is the change of sign (Tester chart check of 008, should-fix 3), not one decade's t.
        last_pos = dict((k, hi) for k, _lo, hi in DECADES)[pos[-1]]
        pos_rng = (f"{signed_pct(min(means[k] for k in pos))} to {signed_pct(max(means[k] for k in pos))}"
                   if len(pos) > 1 else signed_pct(means[pos[0]]))
        words = {1: "one", 2: "two", 3: "three", 4: "four"}
        finding = (f"The tilt's edge over the same-exposure mix was positive in the {words[len(pos)]} decades to "
                   f"{last_pos} ({pos_rng} a year) and negative in " + " and ".join(name(k) for k in neg) + " ("
                   + " and ".join(signed_pct(means[k]) for k in neg) + ")")  # the t range is in the subtitle
    else:
        count = "every decade" if len(pos) == len(means) else f"{len(pos)} of {len(means)} decades"
        finding = (f"The tilt's edge over the same-exposure mix was positive in {count} ({signed_pct(means[low])} a "
                   f"year in {name(low)} to {signed_pct(means[top])} in {name(top)}){qual}")
    fig, ax = style.figure(width=8.0, height=5.4)
    fig.subplots_adjust(bottom=0.25)
    style.title(fig, finding, "Mean monthly difference T1 − B3, annualised (× 12), %, by decade of the execution "
                              "date, Jul 1974 to Dec 2018; Newey–West t from "
                              f"{num(t_lo, 1)} to {num(t_hi, 1)}. Descriptive, no decision weight.")
    labels = [k for k, _lo, _hi in DECADES]
    colors = [style.ACCENT if means[k] > 0 else style.GREY_LIGHT for k in labels]
    bars = ax.bar(labels, [means[k] for k in labels], color=colors, width=0.62)
    ax.axhline(0.0, color=style.GREY, lw=0.8)
    for bar, k in zip(bars, labels, strict=True):
        below = means[k] < 0
        ax.annotate(f"{signed_pct(means[k])} ({counts[k]} mo)", (bar.get_x() + bar.get_width() / 2, means[k]),
                    xytext=(0, -4 if below else 4), textcoords="offset points", ha="center",
                    va="top" if below else "bottom", fontsize=style.LABEL_SIZE, color=style.TEXT)
    floor = 0.0 if min(means.values()) > 0 else min(means.values()) * 1.6
    ax.tick_params(axis="x", length=0, pad=8)
    ax.set_ylim(floor, max(means.values()) * 1.2)
    style.percent_axis(ax, decimals=1)
    style.despine(ax, keep=())  # one baseline: the zero line drawn above
    era_txt = (f"The registered era row (execution months 1986-01 to 2018-12, {era['periods']} periods): "
               f"{signed_pct(era['mean_d_annual'], 2)} a year, {'pass' if era['pass'] else 'fail'}. ")
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note="Bars in time order (decades are ordered, not ranked). "
                                                     f"{era_txt}Run once; results/history/monthly_base.csv, "
                                                     f"summary.json. {VERDICT}")
    style.save(fig, HERE / "history_differential_by_decade")


def window_chart(summary: dict, numbers: dict) -> None:
    base = summary["cost_cases"]["base"]
    vals: dict[str, dict[str, float]] = {t: {} for t in TRIALS}
    tstat: dict[str, dict[str, float]] = {t: {} for t in TRIALS}
    nper: dict[str, dict[str, int]] = {t: {} for t in TRIALS}
    for t in TRIALS:
        for key, _short in WINDOWS:
            src = base["sub_windows"][t] if key in base["sub_windows"][t] else base["rate_eras"][t]
            vals[t][key] = float(src[key]["T_minus_B3"]["mean"]) * 12.0
            tstat[t][key] = float(src[key]["T_minus_B3"]["t"])
            nper[t][key] = int(src[key]["T_minus_B3"]["n"])
    numbers.update(window_mean_d_annual=vals, window_nw_t=tstat, window_periods=nper)
    keys = [k for k, _s in WINDOWS]

    def side(x: float) -> str:
        return "ahead of" if x > 0 else "behind"

    b, o = vals["T1"][BEFORE], vals["T1"][OVERLAP]
    agree = [t for t in TRIALS[1:] if np.sign(vals[t][BEFORE]) == np.sign(b) and np.sign(vals[t][OVERLAP]) == np.sign(o)]
    comp = ("T1a and T1b alike" if len(agree) == 2
            else (f"of the companions only {agree[0]} alike" if agree else "neither companion alike"))
    numbers["window_companions_same_signs_before_and_overlap"] = agree
    t_all = numbers["_t_vs_B3"]
    numbers["window_title_whole_window_nw_t"] = t_all
    finding = (f"The value tilt was {side(b)} the same-exposure mix before 2003 ({signed_pct(b, 2)} a year) and "
               f"{side(o)} it over 2003–18 ({signed_pct(o, 2)}), {comp}; whole period not supported "
               f"(t {num(t_all)})")
    fig, ax = style.figure(width=8.6, height=6.0)
    fig.subplots_adjust(bottom=0.29)
    style.title(fig, finding, "Mean monthly difference to each trial's own B3, annualised (× 12), %, by sub-window "
                              "(registered) and rate era (by execution month). Value tilt T1 on headline CPI "
                              "(accent), T1a on core CPI and T1b on a trailing 120-month rank (greys), Jul 1974 to "
                              "Dec 2018 (T1b from Jul 1979). Descriptive, no decision weight.")
    x = np.array([0.0, 1.0, 2.0, 3.6, 4.6, 5.6])  # a gap between the two splits of the same months
    width = 0.26
    colors = {"T1": style.ACCENT, "T1a": style.GREY, "T1b": style.GREY_LIGHT}
    for j, t in enumerate(TRIALS):
        heights = [vals[t][k] for k in keys]
        ax.bar(x + (j - 1) * width, heights, width=width * 0.92, color=colors[t])
    # One key under the axis for both groups (three bars per window are too narrow for their names;
    # Tester chart check of 008: a key under one group's heading reads as that group's only).
    names = {"T1": "T1 headline CPI", "T1a": "T1a core CPI", "T1b": "T1b 120-month rank"}
    for t, xk in zip(TRIALS, (0.0, 0.3, 0.57), strict=True):
        ax.annotate("■", (xk, -0.2), xycoords="axes fraction", ha="left", va="top",
                    fontsize=style.LABEL_SIZE, color=colors[t], annotation_clip=False)
        ax.annotate(names[t], (xk + 0.025, -0.2), xycoords="axes fraction", ha="left", va="top",
                    fontsize=style.LABEL_SIZE, color=style.TEXT if t == "T1" else style.TEXT_MUTED,
                    annotation_clip=False)
    ax.axhline(0.0, color=style.GREY, lw=0.8)
    ax.axvline(2.8, color=style.GREY_FAINT, lw=0.8)
    for xc, cap in ((1.0, "Registered sub-windows"), (4.6, "Rate eras")):
        ax.text(xc, 1.0, cap, transform=ax.get_xaxis_transform(), ha="center", va="bottom",
                fontsize=style.LABEL_SIZE, color=style.TEXT_MUTED)
    ax.set_xticks(x, [s for _k, s in WINDOWS])
    ax.tick_params(axis="x", length=0)
    style.percent_axis(ax, decimals=1)
    allv = [v for t in TRIALS for v in vals[t].values()]
    ax.set_ylim(min(allv) * 1.3 if min(allv) < 0 else 0.0, max(allv) * 1.2)
    style.despine(ax, keep=())  # one baseline: the zero line drawn above
    short = {k: n for k, n in nper["T1b"].items() if n != nper["T1"][k]}
    t1b_note = ("T1b starts in Jul 1979, so it has fewer months in "
                + ", ".join(f"{k[:18]} ({short[k]} against {nper['T1'][k]})" for k in short) + ". ") if short else ""
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note="Windows in time order within each group (not ranked); the two "
                                                     "groups are two splits of the same months. "
                                                     f"{t1b_note}Run once; results/history/summary.json. {VERDICT}")
    style.save(fig, HERE / "history_trials_by_window")


def main() -> int:
    style.apply()
    monthly, metrics, summary, hashes = load()
    base = summary["cost_cases"]["base"]
    desc = base["descriptive"]["T1"]
    lw = base["inference"]["T1"]["vs_B3"]["ledoit_wolf"]["p_value"]
    era = base["era_row_T1"]
    numbers: dict = {"_benchmark_sharpe": {"B1": float(desc["B1"]["sharpe_annual"]),
                                           "B3": float(desc["B3"]["sharpe_annual"])},
                     "_lw_p_vs_B3": float(lw),
                     "_t_vs_B3": float(base["inference"]["T1"]["vs_B3"]["newey_west"]["t"]),
                     "_lw_p_vs_B1": float(base["inference"]["T1"]["vs_B1"]["ledoit_wolf"]["p_value"]),
                     "_weight_b3": float(summary["weight_b3"]["T1"]),
                     "_era_row": {"periods": int(era["periods"]), "mean_d_annual": float(era["mean_d_annual"]),
                                  "pass": bool(era["pass"])}}
    real_yield_chart(monthly, numbers)
    growth_chart(monthly, metrics, numbers)
    drawdown_chart(monthly, numbers)
    decade_chart(monthly, numbers)
    window_chart(summary, numbers)
    numbers["era_row_T1"] = numbers.pop("_era_row")
    for k in ("_benchmark_sharpe", "_lw_p_vs_B3", "_lw_p_vs_B1", "_t_vs_B3", "_weight_b3"):
        numbers.pop(k)
    outputs = sorted(str(p.relative_to(ROOT)) for p in HERE.glob("history_*.*"))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    manifest = {"made_at_utc": datetime.now(UTC).isoformat(timespec="seconds"), "repository_commit_at_run": commit,
                "inputs_sha256": hashes, "outputs": outputs, "numbers_in_titles": numbers}
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(numbers, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
