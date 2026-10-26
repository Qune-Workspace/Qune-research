"""Study 011 charts in the house style (PREREGISTRATION.md §9.6), drawn from
the committed history files.

Adapted from Study 010's charts/make_charts.py (with the fixes of its Tester
chart check).  Reads results/history/monthly.csv and summary.json (the history
run, once, 2026-10-26T16:17:35Z, code 5c40e1b, outputs 468c5bd).  Computes
nothing the study did not already publish beyond presentation: the running sum
of the published monthly d of M1 (base costs).  The window rows, the decade
means and the verdict are read from summary.json as published.  Writes SVG + 2x
PNG into this folder with a manifest of the input hashes and every number that
appears in a title.  No result file is written.

The three registered charts (§9.6): cumulative d of M1 with I1/M/I2 marked;
d by decade; the three trials on I1/I2/O.

Every phrase in a title is chosen by this script from the numbers it reads,
never typed, so a title cannot overstate a result.

Run from the repository root:
  .venv/bin/python research/011-industry-momentum-french-us/charts/make_charts.py
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

STUDY_ID = "Study 011"
SOURCE = ("Kenneth R. French Data Library, 17 and 30 US industry portfolios, value-weighted, monthly, "
          "release 202608 (one snapshot)")
PERIOD = "Jun 1927 to Aug 2026, 1,191 holding months (M1b from Dec 1927)"
WINDOWS = [("I1", "1927-06", "1963-06", "I1 1927–63\nbefore the paper"),
           ("M", "1963-07", "1995-07", "M 1963–95\nthe paper's sample"),
           ("I2", "1995-08", "2026-08", "I2 1995–2026\nafter the paper")]
TRIALS = ("M1", "M1a", "M1b")
NAMES = {"M1": "M1 17 industries, 3 a side", "M1a": "M1a 30 industries, 5 a side",
         "M1b": "M1b 12-month formation"}
EDGE = "The industry momentum long-short (M1)"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def num(x: float, decimals: int = 2) -> str:
    return f"{x:.{decimals}f}".replace("-", "−")


def spct(x_pct: float, decimals: int = 1) -> str:
    """A figure already in per cent (the study's unit), signed: 2.57 -> '+2.6%'."""
    return ("+" if x_pct > 0 else "") + style.pct(x_pct / 100.0, decimals)


def load() -> tuple[pd.DataFrame, dict, dict[str, str]]:
    d = STUDY / "results" / "history"
    paths = (d / "monthly.csv", d / "summary.json")
    monthly = pd.read_csv(paths[0])
    monthly["date"] = pd.PeriodIndex(monthly["month"], freq="M").to_timestamp(how="end").normalize()
    summary = json.loads(paths[1].read_text(encoding="utf-8"))
    return monthly, summary, {str(p.relative_to(ROOT)): sha256(p) for p in paths}


def trial(summary: dict, t: str) -> dict:
    return summary["cost_cases"]["base"]["trials"][t]


def verdict_clause(summary: dict) -> str:
    """The pre-registered verdict for M1 with the criterion that fixed it, from summary.json."""
    crit = summary["criteria"]["M1"]
    failed = [c for c in ("C1", "C2", "C3", "C4") if not crit[c]]
    v = summary["verdict"]["M1"]
    dsr = float(trial(summary, "M1")["dsr"]["N3"]["dsr"])
    if "C3" in failed:
        return f"{v}: deflated Sharpe {num(dsr, 3)} against 0.95 at N = 3"
    return v + (f" ({', '.join(failed)} failed)" if failed else "")


def verdict_note(summary: dict) -> str:
    return f"Verdict for M1: {verdict_clause(summary)} (section 9.5); decided on O = I1 and I2 only."


def cumulative_chart(monthly: pd.DataFrame, summary: dict, numbers: dict) -> None:
    cum = monthly.set_index("date")["M1_d_base"].cumsum()
    end = float(cum.iloc[-1])
    win = trial(summary, "M1")["windows"]
    o = trial(summary, "M1")["O"]
    numbers.update(cumulative_d_end_pp=end,
                   window_mean_d_pct_a_year={k: float(win[k]["mean_pct_a_year"]) for k in ("I1", "M", "I2")},
                   window_nw_t={k: float(win[k]["nw_t"]) for k in ("I1", "M", "I2")},
                   O_mean_d_pct_a_year=float(o["mean_pct_a_year"]), O_nw_t=float(o["nw_t"]),
                   dsr_N3=float(trial(summary, "M1")["dsr"]["N3"]["dsr"]))
    st = float(summary["cost_cases"]["stress"]["trials"]["M1"]["O"]["mean_pct_a_year"])
    numbers["O_mean_d_stress_pct_a_year"] = st
    # Lead with the decision row after costs and at stress, then the verdict (Tester chart check of 011, should-fix).
    verb = "made" if float(o["mean_pct_a_year"]) > 0 else "lost"
    finding = (f"Outside the paper's 1963–95 sample {EDGE[0].lower()}{EDGE[1:]} {verb} "
               f"{spct(o['mean_pct_a_year'], 2)} a year after base costs ({spct(win['I1']['mean_pct_a_year'], 2)} "
               f"before, {spct(win['I2']['mean_pct_a_year'], 2)} after), {spct(st, 2)} at 50 bp; "
               f"{verdict_clause(summary)}")
    fig, ax = style.figure(width=8.0, height=5.0)
    fig.subplots_adjust(bottom=0.2)
    style.title(fig, finding, "Running sum of M1's monthly d (the long-short's return after base costs, 10 bp per "
                              "unit of netted weight traded), percentage points, Jun 1927 to Aug 2026. Shaded: M, "
                              "Moskowitz and Grinblatt's 1963–95 sample, outside the decision row.")
    lo, hi = pd.Timestamp("1963-07-01"), pd.Timestamp("1995-07-31")
    style.shade(ax, lo, hi)
    ax.axhline(0.0, color=style.GREY, lw=0.8)
    ax.plot(cum.index, cum.values, color=style.ACCENT, lw=1.5)
    ax.set_xlim(monthly["date"].iloc[0] - pd.offsets.MonthEnd(1), cum.index[-1])
    ax.set_ylim(min(0.0, float(cum.min())) - 10.0, float(cum.max()) * 1.25)
    ax.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:,.0f}"))
    for key, a, b, _lab in WINDOWS:
        mid = pd.Timestamp(a) + (pd.Timestamp(b) - pd.Timestamp(a)) / 2
        ax.text(mid, 1.0, f"{key} {spct(win[key]['mean_pct_a_year'], 2)} a year", transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=style.LABEL_SIZE,
                color=style.TEXT_MUTED if key == "M" else style.TEXT)
    style.despine(ax)
    style.label_line_ends(ax, [style.EndLabel(f"M1 d {end:,.0f} pp", end, style.ACCENT)], min_gap=0.07)
    style.source(fig, SOURCE, PERIOD, STUDY_ID,
                 note=f"Run once; results/history/monthly.csv (M1_d_base), plotted at the end of each return month; "
                      f"window means from summary.json. O ({o['months']} months): {spct(o['mean_pct_a_year'], 2)} a "
                      f"year, Newey–West t {num(o['nw_t'])}. {verdict_note(summary)}")
    style.save(fig, HERE / "history_cumulative_d")


def decade_chart(summary: dict, numbers: dict) -> None:
    dec = summary["descriptive_M1"]["d_by_decade"]
    labels = list(dec)
    means = {k: float(dec[k]["mean_pct_a_year"]) for k in labels}
    months = {k: int(dec[k]["months"]) for k in labels}
    tstats = {k: float(dec[k]["nw_t"]) for k in labels}
    total = int(trial(summary, "M1")["windows"]["full"]["months"])
    assert sum(months.values()) == total
    numbers.update(decade_mean_d_pct_a_year=means, decade_months=months, decade_nw_t=tstats)
    neg = [k for k in labels if means[k] <= 0]
    numbers["decade_negative"] = neg
    head = f"{EDGE} was positive in {len(labels) - len(neg)} of {len(labels)} calendar decades"
    if neg:
        head += (", negative in the " + " and ".join(neg) + " ("
                 + " and ".join(spct(means[k]) for k in neg) + " a year)")
    # No C2 bar applied to the descriptive decade t's and no split chosen by them (Tester chart check of 011,
    # must-fix 1): the t's go to the subtitle with the mean each full decade needed for t 2 (2 x its NW s.e.).
    full = [k for k in labels if months[k] == 120]
    need = {k: 2.0 * float(dec[k]["nw_se_pct_a_year"]) for k in full}
    numbers["full_decade_mean_needed_for_t2_pct_a_year"] = need
    t_lo, t_hi = min(tstats.values()), max(tstats.values())
    fig, ax = style.figure(width=8.6, height=5.4)
    fig.subplots_adjust(bottom=0.24)
    style.title(fig, head, f"Mean monthly d of M1, annualised (× 12), %, base costs, by calendar decade of the "
                           "return month, Jun 1927 to Aug 2026, including the paper's sample (Jul 1963 to Jul "
                           f"1995, inside the 1960s to 1990s bars). Newey–West t by decade {num(t_lo)} to {num(t_hi)}; a full "
                           f"decade needed {spct(min(need.values()))} to {spct(max(need.values()))} a year to reach t 2, "
                           "so each bar is a weak test. Descriptive, no decision weight.")
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
    lo = min(means.values())
    ax.set_ylim(min(lo * 1.6, -2.0), max(means.values()) * 1.25)
    ax.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:.0f}%".replace("-", "−")))
    style.despine(ax, keep=())  # one baseline: the zero line drawn above
    style.source(fig, SOURCE, PERIOD, STUDY_ID,
                 note=f"Bars in time order (decades are ordered, not ranked); {len(full)} full decades of 120 months, "
                      f"the 1920s from Jun 1927 and the 2020s to Aug 2026 are partial. The 1960s and 1990s are split "
                      f"between M and O. Run once; results/history/summary.json (descriptive_M1.d_by_decade). "
                      f"{verdict_note(summary)}")
    style.save(fig, HERE / "history_d_by_decade")


def window_chart(summary: dict, numbers: dict) -> None:
    keys = ["I1", "I2", "O"]
    labels = {"I1": "I1 1927–63\nbefore the paper", "I2": "I2 1995–2026\nafter the paper",
              "O": "O = I1 and I2\nthe decision row"}

    def row(t: str, k: str) -> dict:
        return trial(summary, t)["O"] if k == "O" else trial(summary, t)["windows"][k]

    vals = {t: {k: float(row(t, k)["mean_pct_a_year"]) for k in keys} for t in TRIALS}
    tst = {t: {k: float(row(t, k)["nw_t"]) for k in keys} for t in TRIALS}
    nper = {t: {k: int(row(t, k)["months"]) for k in keys} for t in TRIALS}
    dsr = {t: float(trial(summary, t)["dsr"]["N3"]["dsr"]) for t in TRIALS}
    numbers.update(window_trials_mean_d_pct_a_year=vals, window_trials_nw_t=tst, window_trials_months=nper,
                   window_trials_dsr_N3=dsr)
    all_pos = all(v > 0 for t in TRIALS for v in vals[t].values())
    numbers["window_trials_all_positive"] = all_pos
    head = ("All three trials made more than zero before and after the paper's sample"
            if all_pos else "The three trials did not all make more than zero in I1, I2 and O")
    head += (f"; the headline M1, which alone decides, is {summary['verdict']['M1']} ({spct(vals['M1']['O'], 2)} a "
             f"year on O, deflated Sharpe {num(dsr['M1'], 3)} against 0.95); the companions are fragility checks, "
             f"not alternatives")
    fig, ax = style.figure(width=9.4, height=6.2)
    fig.subplots_adjust(bottom=0.34)
    style.title(fig, head, "Mean monthly d of each trial, annualised (× 12), %, base costs, by registered row (§8): "
                           "I1 and I2 the stretches outside Moskowitz and Grinblatt's 1963–95 sample, O both together "
                           "(the decision row). M1 in accent, the two companions in greys, Jun 1927 (M1b Dec "
                           "1927) to Aug 2026 without Jul 1963 to Jul 1995. Companions cannot lift the headline (§9.5).")
    x = np.arange(len(keys), dtype=float)
    width = 0.26
    colors = {"M1": style.ACCENT, "M1a": style.GREY, "M1b": style.GREY_LIGHT}
    for j, t in enumerate(TRIALS):
        hs = [vals[t][k] for k in keys]
        bars = ax.bar(x + (j - 1) * width, hs, width=width * 0.92, color=colors[t])
        for bar, h in zip(bars, hs, strict=True):
            ax.annotate(spct(h, 2), (bar.get_x() + bar.get_width() / 2, h), xytext=(0, -3 if h < 0 else 3),
                        textcoords="offset points", ha="center", va="top" if h < 0 else "bottom",
                        fontsize=style.LABEL_SIZE, color=style.TEXT if t == "M1" else style.TEXT_MUTED)
    for t, xk in zip(TRIALS, (0.0, 0.35, 0.70), strict=True):
        ax.annotate("■", (xk, -0.27), xycoords="axes fraction", ha="left", va="top",
                    fontsize=style.LABEL_SIZE, color=colors[t], annotation_clip=False)
        ax.annotate(NAMES[t], (xk + 0.025, -0.27), xycoords="axes fraction", ha="left", va="top",
                    fontsize=style.LABEL_SIZE, color=style.TEXT if t == "M1" else style.TEXT_MUTED,
                    annotation_clip=False)
    ax.axhline(0.0, color=style.GREY, lw=0.8)
    ax.set_xticks(x, [f"{labels[k]}\n{nper['M1'][k]:,} months" for k in keys])
    ax.tick_params(axis="x", length=0)
    allv = [v for t in TRIALS for v in vals[t].values()]
    ax.set_ylim(min(min(allv) * 1.6, -0.5), max(allv) * 1.2)
    ax.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:.0f}%".replace("-", "−")))
    style.despine(ax, keep=())  # one baseline: the zero line drawn above
    p = summary["window_row_M1"]
    mde = float(summary["verdict"]["mde_80_M1_pct_a_year"])
    numbers["mde_80_M1_pct_a_year"] = mde
    style.source(fig, SOURCE, PERIOD, STUDY_ID,
                 note=f"Rows in time order, then the decision row (not ranked). M1b has {nper['M1b']['I1']} months in "
                      f"I1 and {nper['M1b']['O']} in O (12-month formation). Newey–West t on O: M1 {num(tst['M1']['O'])}, M1a "
                      f"{num(tst['M1a']['O'])}, M1b {num(tst['M1b']['O'])}; deflated Sharpe at N = 3: "
                      f"{num(dsr['M1'], 3)}, {num(dsr['M1a'], 3)}, {num(dsr['M1b'], 3)} (bar 0.95; M1a and M1b meet C1–C4 in Sharpe units, the 2%-a-year bar not "
                      f"met, §9.5). The registered "
                      f"window rule for M1 ({p['rule']}): {'pass' if p['pass'] else 'fail'}. O can detect a mean d "
                      f"of about {num(mde, 1)}% a year at 80% power. Run once; results/history/summary.json. "
                      f"{verdict_note(summary)}")
    style.save(fig, HERE / "history_trials_by_window")


def main() -> int:
    style.apply()
    monthly, summary, hashes = load()
    numbers: dict = {}
    cumulative_chart(monthly, summary, numbers)
    decade_chart(summary, numbers)
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
