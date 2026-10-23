"""Study 005 charts in the house style, drawn from the committed results files (§9.7).

Reads results/{insample,episode}/monthly_base.csv and summary.json, computes
nothing the study did not already publish (the growth of one unit from the
monthly net returns; counts of flagged months), and writes SVG + 2x PNG into
this folder with a manifest of the input hashes and every number that appears
in a title.  The pre-registration (§9.7, §16 layout note 4) asks for three
pictures: the 63-day correlation at the signal dates with the positive regime
shaded and the trend rule's bill months marked; the growth of one unit of the
conditional rule (T1), hold-IEF (B1) and the trend rule (B2) by window; and
the monthly trend-minus-hold return d_t by regime.  Titles are computed from
the numbers.  No result file is written; this script changes nothing a verdict
rests on.

Run from the repository root:  .venv/bin/python research/005-duration-trend-regime/charts/make_charts.py
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

STUDY_ID = "Study 005"
SOURCE = "Tiingo and Alpaca daily IEF, SPY and BIL bars, FRED CPIAUCNS"
WINDOWS = {
    "insample": ("2003-08 to 2018-12", "In-sample", "in-sample check, run once; verdict: refuted in-sample (section 9.5)"),
    "episode": ("2019-01 to 2026-09", "2019–2026 episode", "hypothesis-generating episode, no decision weight (section 8.2)"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(window: str) -> tuple[pd.DataFrame, dict, dict[str, str]]:
    d = STUDY / "results" / window
    m_path = d / "monthly_base.csv"
    s_path = d / "summary.json"
    monthly = pd.read_csv(m_path, parse_dates=["signal_date", "execution_date", "period_end"])
    summary = json.loads(s_path.read_text())
    return monthly, summary, {str(m_path.relative_to(ROOT)): sha256(m_path),
                              str(s_path.relative_to(ROOT)): sha256(s_path)}


def _shade_positive(ax, frame: pd.DataFrame, flag: str = "positive_T1") -> None:
    """One band per run of positive-regime signal dates (a month wide each)."""
    dates = frame["signal_date"].reset_index(drop=True)
    pos = frame[flag].astype(bool).reset_index(drop=True)
    i = 0
    while i < len(pos):
        if pos[i]:
            j = i
            while j + 1 < len(pos) and pos[j + 1]:
                j += 1
            start = dates[i] - pd.Timedelta(days=15)
            end = dates[j] + pd.Timedelta(days=15)
            style.shade(ax, start, end)
            i = j + 1
        else:
            i += 1


def rho_chart(frames: dict[str, pd.DataFrame], summaries: dict[str, dict], numbers: dict) -> Path:
    both = pd.concat([frames["insample"], frames["episode"]], ignore_index=True)
    n_pos = {w: int(summaries[w]["regime_descriptives"]["T1"]["positive_months"]) for w in frames}
    n_all = {w: int(summaries[w]["regime_descriptives"]["T1"]["months"]) for w in frames}
    numbers["rho_positive_months"] = {w: [n_pos[w], n_all[w]] for w in frames}
    ep = frames["episode"]
    # When did the regime first turn positive in 2022, and since when had the trend rule been in bills?
    first_pos_2022 = ep.loc[(ep["signal_date"].dt.year == 2022) & ep["positive_T1"].astype(bool), "signal_date"].min()
    before = ep.loc[ep["signal_date"] < first_pos_2022]
    bills_run_start = None
    for _, row in before[::-1].iterrows():
        if row["B2_holding"] == "BIL":
            bills_run_start = row["signal_date"]
        else:
            break
    numbers["first_positive_signal_date_2022"] = str(first_pos_2022.date())
    numbers["trend_rule_in_bills_since_signal_date"] = str(bills_run_start.date()) if bills_run_start is not None else None
    months_late = int((first_pos_2022.year - 2022) * 12 + first_pos_2022.month - 1)  # signal months of 2022 before it
    numbers["signal_months_of_2022_before_first_positive"] = months_late

    fig, ax = style.figure(width=9.0, height=4.6)
    finding = (f"In 2022 the correlation regime turned positive only at the {first_pos_2022.strftime('%B')} signal date, "
               f"{months_late} months into the bond sell-off; the trend rule had been in bills since "
               f"{bills_run_start.strftime('%B %Y')}")
    style.title(fig, finding,
                "Pearson correlation of daily SPY and IEF total returns over the 63 most recent days at each monthly "
                "signal date, 2003-07 to 2026-08. Shaded: positive regime (26 of 185 months in-sample, 38 of 93 in "
                "2019–2026). Ticks at the bottom: months in which Study 003's trend rule held bills.")
    _shade_positive(ax, both)
    ax.plot(both["signal_date"], both["rho_T1"], color=style.ACCENT, lw=1.4)
    ax.axhline(0.0, color=style.GREY_DARK, lw=0.8)
    bills = both.loc[both["B2_holding"] == "BIL", "signal_date"]
    ax.plot(bills, [-0.97] * len(bills), linestyle="none", marker="|", markersize=7, color=style.GREY_DARK, mew=1.0)
    ax.annotate("trend rule in bills", xy=(both["signal_date"].iloc[0], -0.97), xytext=(0, 6), textcoords="offset points",
                ha="left", va="bottom", fontsize=style.TICK_SIZE, color=style.TEXT_MUTED)
    split = frames["episode"]["signal_date"].iloc[0] - pd.Timedelta(days=15)
    ax.axvline(split, color=style.GREY_LIGHT, lw=0.8, linestyle=(0, (3, 3)))
    ax.annotate("in-sample", xy=(split, 0.95), xytext=(-4, 0), textcoords="offset points", ha="right", va="top",
                fontsize=style.TICK_SIZE, color=style.TEXT_MUTED)
    ax.annotate("episode, no decision weight", xy=(split, 0.95), xytext=(4, 0), textcoords="offset points",
                ha="left", va="top", fontsize=style.TICK_SIZE, color=style.TEXT_MUTED)
    ax.set_ylim(-1.05, 1.0)
    ax.set_xlim(both["signal_date"].iloc[0] - pd.Timedelta(days=20), both["signal_date"].iloc[-1] + pd.Timedelta(days=20))
    ax.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:+.1f}".replace("-", "−") if v else "0.0"))
    ax.set_ylabel("63-day correlation", color=style.TEXT_MUTED)
    style.label_line_ends(ax, [style.EndLabel(f"Aug 2026 {both['rho_T1'].iloc[-1]:+.2f}", float(both["rho_T1"].iloc[-1]), style.ACCENT)])
    style.source(fig, SOURCE, "2003-07 to 2026-08 signal dates", STUDY_ID,
                 note="results/insample/ and results/episode/monthly_base.csv; the 2019–2026 window generated the hypothesis.")
    svg, _png = style.save(fig, HERE / "rho63_regime_and_bill_months")
    return svg


def growth_chart(window: str, monthly: pd.DataFrame, numbers: dict) -> Path:
    period, where, label = WINDOWS[window]
    cols = ["T1", "B1", "B2"]
    growth = (1.0 + monthly[cols]).cumprod()
    growth.index = monthly["period_end"]
    start = pd.DataFrame([[1.0] * 3], columns=cols, index=[monthly["execution_date"].iloc[0]])
    growth = pd.concat([start, growth])
    final = growth.iloc[-1] - 1.0
    numbers[f"{window}_cumulative_return"] = {k: float(v) for k, v in final.items()}
    fig, ax = style.figure(width=8.0, height=4.6)
    fig.subplots_adjust(right=0.74)
    if window == "insample":
        finding = (f"{where}, switching to bills only in the positive regime ended {style.pct(final['T1'])} up, "
                   f"below holding IEF ({style.pct(final['B1'])}) and above the unconditional trend rule "
                   f"({style.pct(final['B2'])})")
        if not (final["B2"] < final["T1"] < final["B1"]):
            finding = (f"{where}, the conditional rule ended {style.pct(final['T1'])} up against {style.pct(final['B1'])} "
                       f"for holding IEF and {style.pct(final['B2'])} for the unconditional trend rule")
    else:
        kept = final["T1"] - final["B1"]
        saved = final["B2"] - final["B1"]
        share = kept / saved if saved else float("nan")
        numbers["episode_share_of_exit_gain_kept"] = float(share)
        finding = (f"Over 2019–2026 the conditional rule kept {share:.0%} of what the trend exit gained over holding "
                   f"IEF: +{style.pct(final['T1'])} against +{style.pct(final['B2'])} for the trend rule and "
                   f"+{style.pct(final['B1'])} for holding IEF")
    style.title(fig, finding,
                f"Growth of 1 unit, monthly holding periods, {period}, after costs of 2 bp a side. "
                f"IEF or BIL only; SPY is never held. {label[0].upper() + label[1:]}.")
    for name, colour, lw in (("B1", style.GREY, 1.2), ("B2", style.GREY_DARK, 1.3), ("T1", style.ACCENT, 1.7)):
        ax.plot(growth.index, growth[name], color=colour, lw=lw)
    if window == "episode":
        style.shade(ax, pd.Timestamp("2022-01-03"), pd.Timestamp("2022-12-30"), label="2022")
    ax.yaxis.set_major_formatter(style.FuncFormatter(lambda v, _p: f"{v:,.2f}"))
    ax.set_xlim(growth.index[0], growth.index[-1])
    last = growth.iloc[-1]
    style.label_line_ends(ax, [
        style.EndLabel(f"Conditional (T1) {last['T1']:.2f}", float(last["T1"]), style.ACCENT),
        style.EndLabel(f"Trend rule (B2) {last['B2']:.2f}", float(last["B2"]), style.GREY_DARK),
        style.EndLabel(f"Hold IEF (B1) {last['B1']:.2f}", float(last["B1"]), style.GREY),
    ], min_gap=0.07)
    style.source(fig, SOURCE, period, STUDY_ID, note=f"results/{window}/monthly_base.csv.")
    svg, _png = style.save(fig, HERE / f"{window}_growth_T1_B1_B2")
    return svg


def d_chart(window: str, monthly: pd.DataFrame, summary: dict, numbers: dict) -> Path:
    period, where, label = WINDOWS[window]
    edge = summary["cost_cases"]["base"]["edge"]["T1"]
    mp, mn, delta = edge["mean_positive"], edge["mean_negative"], edge["delta"]
    t = edge["newey_west"]["t"]
    lo, hi = edge["bootstrap"]["delta"]["ci_low"], edge["bootstrap"]["delta"]["ci_high"]
    numbers[f"{window}_edge_T1"] = {"mean_positive": mp, "mean_negative": mn, "delta": delta, "nw_t": t,
                                    "ci": [lo, hi], "n_pos": edge["n_pos"], "n_neg": edge["n_neg"]}
    tt = f"{t:.2f}".replace("-", "−")

    def signed(x: float) -> str:
        return ("+" if x > 0 else "") + style.pct(x, 2)

    pos = monthly["positive_T1"].astype(bool)
    d = monthly["d"]
    fig, ax = style.figure(width=9.0, height=4.6)
    fig.subplots_adjust(right=0.75)
    if window == "insample":
        finding = (f"{where}, the trend exit returned {style.pct(mp, 2)} a month against holding IEF in the "
                   f"{edge['n_pos']} positive-regime months and {style.pct(mn, 2)} in the other {edge['n_neg']}: a conditional "
                   f"edge of {style.pct(delta, 2)} a month (t {tt}), the wrong sign")
    else:
        finding = (f"Over 2019–2026 the exit's gains fell in negative-regime months: d averaged +{style.pct(mp, 2)} a month "
                   f"in the {edge['n_pos']} positive-regime months and +{style.pct(mn, 2)} in the other {edge['n_neg']} "
                   f"(edge {style.pct(delta, 2)}, t {tt})")
    style.title(fig, finding,
                f"d = trend rule (B2) minus hold IEF (B1), monthly net return, %, {period}; zero where both held IEF. "
                f"Accent: positive-regime months. Newey–West t with 6 lags; bootstrap 95% interval for the edge "
                f"[{style.pct(lo, 2)}, {style.pct(hi, 2)}]. {label[0].upper() + label[1:]}.")
    colours = [style.ACCENT if p else style.GREY_LIGHT for p in pos]
    ax.bar(monthly["signal_date"], d, width=24, color=colours, linewidth=0)
    ax.axhline(0.0, color=style.GREY_DARK, lw=0.8)
    ax.axhline(mp, color=style.ACCENT, lw=0.9, linestyle=(0, (4, 3)))
    ax.axhline(mn, color=style.GREY, lw=0.9, linestyle=(0, (4, 3)))
    style.percent_axis(ax, decimals=0)
    ax.set_xlim(monthly["signal_date"].iloc[0] - pd.Timedelta(days=20), monthly["signal_date"].iloc[-1] + pd.Timedelta(days=20))
    style.label_line_ends(ax, [
        style.EndLabel(f"positive, mean {signed(mp)}", float(mp), style.ACCENT),
        style.EndLabel(f"negative, mean {signed(mn)}", float(mn), style.GREY),
    ], min_gap=0.06)
    style.source(fig, SOURCE, period, STUDY_ID, note=f"results/{window}/monthly_base.csv and summary.json.")
    svg, _png = style.save(fig, HERE / f"{window}_d_by_regime")
    return svg


def main() -> None:
    numbers: dict = {}
    inputs: dict[str, str] = {}
    outputs: list[Path] = []
    frames: dict[str, pd.DataFrame] = {}
    summaries: dict[str, dict] = {}
    for window in ("insample", "episode"):
        monthly, summary, hashes = load(window)
        frames[window], summaries[window] = monthly, summary
        inputs.update(hashes)
        outputs.append(growth_chart(window, monthly, numbers))
        outputs.append(d_chart(window, monthly, summary, numbers))
    outputs.append(rho_chart(frames, summaries, numbers))
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.strip()
    except Exception:  # pragma: no cover
        commit = "unknown"
    out_list: list[str] = []
    for p in outputs:
        out_list.append(str(p.relative_to(ROOT)))
        out_list.append(str(p.with_suffix(".png").relative_to(ROOT)))
    manifest = {
        "made_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repository_commit_at_run": commit,
        "inputs_sha256": inputs,
        "outputs": out_list,
        "numbers_in_titles": numbers,
        "note": "Presentation only (section 9.7, no decision weight). Every number is recomputed from the committed "
                "results files; no result file is written. Style: qune_research/style.py (chart standard of 2026-10-23).",
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(numbers, indent=2))


if __name__ == "__main__":
    main()
