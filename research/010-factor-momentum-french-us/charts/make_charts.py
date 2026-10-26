"""Study 010 charts in the house style (PREREGISTRATION.md §9.6), drawn from
the committed history files.

Adapted from Study 008's charts/make_charts.py (with the fixes of its Tester
chart check).  Reads results/history/monthly_base.csv and summary.json (the
history run, once, 2026-10-26T10:19:49Z, commit 1748602).  Computes nothing
the study did not already publish beyond presentation: the running sum of the
published monthly differential d of T1 (base costs).  The decade means, the per-factor contributions and
the window rows are read from summary.json as published.  Writes SVG + 2x PNG
into this folder with a manifest of the input hashes and every number that
appears in a title.  No result file is written.

The four registered charts (§9.6): cumulative d of T1 with P1/L/P2 marked;
d by decade; per-factor contributions; the three trials on P1/L/P2.

Every phrase in a title is chosen by this script from the numbers it reads,
never typed, so a title cannot overstate a result.

Run from the repository root:
  .venv/bin/python research/010-factor-momentum-french-us/charts/make_charts.py
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

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))

from qune_research import style  # noqa: E402

STUDY_ID = "Study 010"
SOURCE = ("Kenneth R. French Data Library, US research factors SMB, HML, short-term and long-term reversal, "
          "monthly, release 202608 (one snapshot)")
PERIOD = "Jul 1927 to Aug 2026, 1,190 months (LT_Rev held by T1 from Jan 1932)"
VERDICT = "Verdict: not supported (section 9.5); the rule did not beat holding the four factors (C1)."
WINDOWS = [("P1", "1927-07", "1963-06", "P1 1927–63\nbefore the paper"),
           ("L", "1963-07", "2015-12", "L 1963–2015\nthe paper's window"),
           ("P2", "2016-01", "2026-08", "P2 2016–26\nafter the paper")]
TRIALS = ("T1", "T1a", "T1b")
NAMES = {"T1": "T1 four factors, 12 months", "T1a": "T1a SMB and HML only", "T1b": "T1b four factors, 6 months"}
EDGE = "T1's edge over its own average positions"
FACTOR_NAMES = {"SMB": "Size (SMB)", "HML": "Value (HML)", "ST_Rev": "Short-term reversal",
                "LT_Rev": "Long-term reversal"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def num(x: float, decimals: int = 2) -> str:
    return f"{x:.{decimals}f}".replace("-", "−")


def spct(x_pct: float, decimals: int = 1) -> str:
    """A figure already in per cent (the study's unit), signed: 2.57 -> '+2.6%'."""
    return ("+" if x_pct > 0 else "") + style.pct(x_pct / 100.0, decimals)


def load() -> tuple[pd.DataFrame, dict, dict[str, str]]:
    d = STUDY / "results" / "history"
    paths = (d / "monthly_base.csv", d / "summary.json")
    monthly = pd.read_csv(paths[0])
    monthly["date"] = pd.PeriodIndex(monthly["month"], freq="M").to_timestamp(how="end").normalize()
    summary = json.loads(paths[1].read_text(encoding="utf-8"))
    return monthly, summary, {str(p.relative_to(ROOT)): sha256(p) for p in paths}


def trial(summary: dict, t: str) -> dict:
    return summary["cost_cases"]["base"]["trials"][t]


def cumulative_chart(monthly: pd.DataFrame, summary: dict, numbers: dict) -> None:
    cum = monthly.set_index("date")["T1_d"].cumsum()
    peak, end = float(cum.max()), float(cum.iloc[-1])
    win = trial(summary, "T1")["windows"]
    t_b1 = float(trial(summary, "T1")["T_minus_B1"]["mean_pct_a_year"])
    numbers.update(cumulative_d_end_pp=end, cumulative_T_minus_B1_pct_a_year=t_b1,
                   window_mean_d_pct_a_year={k: float(win[k]["mean_pct_a_year"]) for k in ("P1", "L", "P2")},
                   window_nw_t={k: float(win[k]["nw_t"]) for k in ("P1", "L", "P2")})
    # No descriptive t and no peak in the title (Tester chart check of 010, must-fix 1): the verdict instead.
    vs_b1 = "yet the rule trailed" if t_b1 < 0 else "and the rule was ahead of"
    finding = (f"{EDGE} was {spct(win['P1']['mean_pct_a_year'])} a year before 1963, "
               f"{spct(win['L']['mean_pct_a_year'])} in the paper's window and {spct(win['P2']['mean_pct_a_year'])} "
               f"after it, {vs_b1} holding the four factors ({spct(t_b1, 2)} a year; not supported)")
    fig, ax = style.figure(width=8.0, height=5.0)
    fig.subplots_adjust(bottom=0.2)
    style.title(fig, finding, "Running sum of T1's monthly d (rule return less B3, the same factors held at the "
                              "rule's own average positions), percentage points, base costs (10 bp per dollar "
                              "traded, so one flip costs 40 bp on that factor's share), Jul 1927 to Aug 2026. Shaded: L, the source paper's US data window.")
    lo, hi = pd.Timestamp("1963-07-01"), pd.Timestamp("2015-12-31")
    style.shade(ax, lo, hi)
    ax.axhline(0.0, color=style.GREY, lw=0.8)
    ax.plot(cum.index, cum.values, color=style.ACCENT, lw=1.5)
    ax.set_xlim(monthly["date"].iloc[0] - pd.offsets.MonthEnd(1), cum.index[-1])
    ax.set_ylim(min(0.0, float(cum.min())) - 10.0, peak * 1.25)
    ax.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:,.0f}"))
    for key, a, b, _lab in WINDOWS:
        mid = pd.Timestamp(a) + (pd.Timestamp(b) - pd.Timestamp(a)) / 2
        ax.text(mid, 1.0, f"{key} {spct(win[key]['mean_pct_a_year'])} a year", transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=style.LABEL_SIZE,
                color=style.TEXT if key == "L" else style.TEXT_MUTED)
    style.despine(ax)
    style.label_line_ends(ax, [style.EndLabel(f"T1 d {end:,.0f}", end, style.ACCENT)], min_gap=0.07)
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note="Run once; results/history/monthly_base.csv (T1_d), plotted at "
                                                     "the end of each return month; window means from summary.json. "
                                                     f"{VERDICT}")
    style.save(fig, HERE / "history_cumulative_d")


def decade_chart(summary: dict, numbers: dict) -> None:
    dec = summary["descriptive_T1"]["d_by_decade"]
    labels = list(dec)
    means = {k: float(dec[k]["mean_pct_a_year"]) for k in labels}
    months = {k: int(dec[k]["months"]) for k in labels}
    tstats = {k: float(dec[k]["nw_t"]) for k in labels}
    assert sum(months.values()) == trial(summary, "T1")["d"]["months"]
    numbers.update(decade_mean_d_pct_a_year=means, decade_months=months, decade_nw_t=tstats)
    neg = [k for k in labels if means[k] <= 0]
    pos = [k for k in labels if means[k] > 0]
    numbers["decade_negative"] = neg
    full = [k for k in labels if months[k] == 120]
    lead = labels[:labels.index(neg[0])] if neg else labels
    if neg and lead == pos[:len(lead)] and all(k in pos for k in lead):
        finding = (f"{EDGE} was positive in every decade from the {lead[0]} to the {lead[-1]} and negative "
                   f"in the " + " and ".join(neg) + " (" + " and ".join(spct(means[k]) for k in neg) + " a year)")
        rest = [k for k in pos if k not in lead]
        if rest:
            finding += "; " + ", ".join(f"{spct(means[k])} in the {k} so far ({months[k]} months)" for k in rest)
    else:
        finding = f"{EDGE} was positive in {len(pos)} of {len(labels)} decades"
    fig, ax = style.figure(width=8.6, height=5.4)
    fig.subplots_adjust(bottom=0.24)
    t_lo, t_hi = min(tstats.values()), max(tstats.values())
    style.title(fig, finding, "Mean monthly d of T1, annualised (× 12), %, by calendar decade of the return month, "
                              f"Jul 1927 to Aug 2026; Newey–West t from {num(t_lo, 1)} to {num(t_hi, 1)}. "
                              "Descriptive, no decision weight.")
    colors = [style.ACCENT if means[k] > 0 else style.GREY_LIGHT for k in labels]
    bars = ax.bar(labels, [means[k] for k in labels], color=colors, width=0.62)
    ax.axhline(0.0, color=style.GREY, lw=0.8)
    for bar, k in zip(bars, labels, strict=True):
        below = means[k] < 0
        txt = spct(means[k]) + (f"\n{months[k]} mo" if months[k] != 120 else "")
        ax.annotate(txt, (bar.get_x() + bar.get_width() / 2, means[k]), xytext=(0, -4 if below else 4),
                    textcoords="offset points", ha="center", va="top" if below else "bottom",
                    fontsize=style.LABEL_SIZE, color=style.TEXT)
    ax.tick_params(axis="x", length=0, pad=8)
    ax.set_ylim(min(means.values()) * 2.2, max(means.values()) * 1.25)
    ax.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:.0f}%".replace("-", "−")))
    style.despine(ax, keep=())  # one baseline: the zero line drawn above
    style.source(fig, SOURCE, PERIOD, STUDY_ID,
                 note=f"Bars in time order (decades are ordered, not ranked); {len(full)} full decades of 120 months, "
                      f"the 1920s from Jul 1927 and the 2020s to Aug 2026 are partial. Run once; "
                      f"results/history/summary.json (descriptive_T1.d_by_decade). {VERDICT}")
    style.save(fig, HERE / "history_d_by_decade")


def factor_chart(summary: dict, numbers: dict) -> None:
    pf = trial(summary, "T1")["per_factor"]
    net = {k: float(v["contribution_to_mean_d_net_pct_a_year"]) for k, v in pf.items()}
    tnet = {k: float(v["contribution_net_nw_t"]) for k, v in pf.items()}
    mean_d = float(trial(summary, "T1")["d"]["mean_pct_a_year"])
    assert abs(sum(net.values()) - mean_d) < 1e-9
    numbers.update(factor_contribution_net_pct_a_year=net, factor_contribution_net_nw_t=tnet,
                   factor_contributions_sum_pct_a_year=sum(net.values()))
    top, low = max(net, key=net.get), min(net, key=net.get)
    t_b1 = float(trial(summary, "T1")["T_minus_B1"]["mean_pct_a_year"])
    numbers["factor_T_minus_B1_pct_a_year"] = t_b1
    # The accent marks the factor the title names, not a t threshold (Tester chart check of 010, must-fix 2).
    vs_b1 = "but the rule trailed" if t_b1 < 0 else "and the rule was ahead of"
    finding = (f"{FACTOR_NAMES[top]} added most to {EDGE} ({spct(net[top], 2)} a year) and "
               f"{FACTOR_NAMES[low].lower()} least ({spct(net[low], 2)}); the four sum to {spct(mean_d, 2)}, {vs_b1} "
               f"holding the factors ({spct(t_b1, 2)} a year)")
    fig, ax = style.figure(width=8.0, height=5.2)
    fig.subplots_adjust(bottom=0.3, left=0.24)
    style.title(fig, finding, "Each factor's contribution to T1's mean d, % a year, after base costs, Jul 1927 to "
                              f"Aug 2026; the four sum to the {spct(mean_d, 2)} a year of the decision row. Accent: "
                              "the largest. Newey–West t on the bars, descriptive, no decision weight.")
    names = style.sorted_bars(ax, {FACTOR_NAMES[k]: net[k] for k in net},
                              highlight=[FACTOR_NAMES[top]])
    inv = {v: k for k, v in FACTOR_NAMES.items()}
    for i, n in enumerate(names):
        k = inv[n]
        ax.annotate(f"{spct(net[k], 2)} (t {num(tnet[k])})", (net[k], i), xytext=(4, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=style.LABEL_SIZE, color=style.TEXT)
    ax.set_xlim(0.0, max(net.values()) * 1.45)
    ax.xaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:.1f}%"))
    style.source(fig, SOURCE, PERIOD, STUDY_ID,
                 note=f"Bars sorted by value. Contributions are to d, the gain over the rule's own average positions, "
                      f"not to the rule's return over holding the factors (T − B1 {spct(t_b1, 2)} a year). LT_Rev held "
                      f"in {int(pf['LT_Rev']['months_held']):,} of the 1,190 months (its file starts in Jan 1931). Run once; results/history/summary.json "
                      f"(per_factor). {VERDICT}")
    style.save(fig, HERE / "history_factor_contributions")


def window_chart(summary: dict, numbers: dict) -> None:
    keys = [k for k, *_ in WINDOWS]
    vals = {t: {k: float(trial(summary, t)["windows"][k]["mean_pct_a_year"]) for k in keys} for t in TRIALS}
    tst = {t: {k: float(trial(summary, t)["windows"][k]["nw_t"]) for k in keys} for t in TRIALS}
    nper = {t: {k: int(trial(summary, t)["windows"][k]["months"]) for k in keys} for t in TRIALS}
    numbers.update(window_trials_mean_d_pct_a_year=vals, window_trials_nw_t=tst, window_trials_months=nper)

    def falls(t: str) -> bool:
        return vals[t]["P1"] > vals[t]["L"] > vals[t]["P2"]

    def rises(t: str) -> bool:
        return vals[t]["P1"] < vals[t]["L"] < vals[t]["P2"]

    t1 = vals["T1"]
    head = (f"{EDGE} fell from {spct(t1['P1'])} a year before 1963 to {spct(t1['L'])} in the paper's window and "
            f"{spct(t1['P2'])} after it" if falls("T1")
            else f"{EDGE} was {spct(t1['P1'])}, {spct(t1['L'])} and {spct(t1['P2'])} a year in P1, L and P2")
    same = [t for t in TRIALS[1:] if falls(t)]
    numbers["window_companions_falling_in_order"] = same
    other = [t for t in TRIALS[1:] if t not in same]
    tail = ""
    if same:
        tail += "; " + " and ".join(same) + " fell the same way"
    for t in other:
        if rises(t):
            tail += (f"; {t}'s rose ({spct(vals[t]['P1'])}, {spct(vals[t]['L'])}, {spct(vals[t]['P2'])})")
        elif vals[t]["P1"] < 0:
            tail += f"; {t} was negative before 1963 ({spct(vals[t]['P1'])} a year)"
        else:
            tail += f"; {t} did not fall in that order"
    finding = head + tail
    fig, ax = style.figure(width=8.6, height=6.2)
    fig.subplots_adjust(bottom=0.34)
    style.title(fig, finding, "Mean monthly d of each trial, annualised (× 12), %, base costs, by registered window "
                              "(§8): P1 before the source paper's data, L its US data window, P2 after its sample. "
                              "T1 in accent, the two companions in greys, Jul 1927 to Aug 2026. Descriptive, no "
                              "decision weight.")
    x = np.arange(len(keys), dtype=float)
    width = 0.26
    colors = {"T1": style.ACCENT, "T1a": style.GREY, "T1b": style.GREY_LIGHT}
    for j, t in enumerate(TRIALS):
        hs = [vals[t][k] for k in keys]
        bars = ax.bar(x + (j - 1) * width, hs, width=width * 0.92, color=colors[t])
        for bar, h, k in zip(bars, hs, keys, strict=True):
            ax.annotate(spct(h), (bar.get_x() + bar.get_width() / 2, h), xytext=(0, -3 if h < 0 else 3),
                        textcoords="offset points", ha="center", va="top" if h < 0 else "bottom",
                        fontsize=style.LABEL_SIZE, color=style.TEXT if t == "T1" else style.TEXT_MUTED)
    for t, xk in zip(TRIALS, (0.0, 0.36, 0.69), strict=True):
        ax.annotate("■", (xk, -0.27), xycoords="axes fraction", ha="left", va="top",
                    fontsize=style.LABEL_SIZE, color=colors[t], annotation_clip=False)
        ax.annotate(NAMES[t], (xk + 0.025, -0.27), xycoords="axes fraction", ha="left", va="top",
                    fontsize=style.LABEL_SIZE, color=style.TEXT if t == "T1" else style.TEXT_MUTED,
                    annotation_clip=False)
    ax.axhline(0.0, color=style.GREY, lw=0.8)
    ax.set_xticks(x, [f"{lab}\n{nper['T1'][k]:,} months" for k, *_, lab in WINDOWS])
    ax.tick_params(axis="x", length=0)
    allv = [v for t in TRIALS for v in vals[t].values()]
    ax.set_ylim(min(min(allv) * 1.6, -0.5), max(allv) * 1.2)
    ax.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:.0f}%".replace("-", "−")))
    style.despine(ax, keep=())  # one baseline: the zero line drawn above
    p = summary["window_row_T1"]
    style.source(fig, SOURCE, PERIOD, STUDY_ID,
                 note=f"Windows in time order (not ranked). The registered window rule uses "
                      f"P = P1 and P2 together for T1 only: {spct(p['mean_pct_a_year'], 2)} a year, t "
                      f"{num(p['nw_t'])}, {p['months']} months, {'pass' if p['pass'] else 'fail'}. P2 can detect only "
                      f"a Sharpe of d of about 0.87 at 80% power, so its figure is a weak test. Run once; "
                      f"results/history/summary.json. {VERDICT}")
    style.save(fig, HERE / "history_trials_by_window")


def main() -> int:
    style.apply()
    monthly, summary, hashes = load()
    numbers: dict = {}
    cumulative_chart(monthly, summary, numbers)
    decade_chart(summary, numbers)
    factor_chart(summary, numbers)
    window_chart(summary, numbers)
    outputs = sorted(str(p.relative_to(ROOT)) for p in HERE.glob("history_*.*"))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    manifest = {"made_at_utc": datetime.now(UTC).isoformat(timespec="seconds"), "repository_commit_at_run": commit,
                "inputs_sha256": hashes, "outputs": outputs, "numbers_in_titles": numbers}
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(numbers, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
