"""Study 014 charts in the house style (PREREGISTRATION.md §9.6; §14 step 9),
drawn from the committed analysis-run outputs only.

Reads results/run/summary.json (the analysis run, once, §14 step 6) and draws
the two registered charts: the median spread in units of mid by decile of the
mid, with [DU26]'s full-quoted-spread figures drawn as reference lines, and
Delta-hat with its interval for M1, M1a, M1b and the early split. Computes
nothing the run did not publish beyond presentation (the ratio of two published
medians in a title; a line between published points). Writes SVG + 2x PNG into
this folder with a manifest of the input hash and every number that appears in
a title. No result file is written.

Before the analysis run there is nothing to draw: the script says so and exits 0
with nothing written, so `make charts` passes while Study 013 collects. After a
halt (§5.4) no Delta is estimated (§9.5) and the decile table is empty: the
script says so and draws nothing.

A decile cell or a split with fewer than ten markets is published as a count
only (§9.6, last bullet; Polymarket's `derived` verdict): the chart writes its
count where its value would be and draws no value.

Every phrase in a title is chosen by this script from the numbers it reads,
never typed, so a title cannot overstate a result; the verdict phrase is the
run's own §9.5 sentence, so a "supported" title carries the window's dates and
the low-power label travels with it (Study 013's chart review, should-fix 11).

Run from the repository root:
  .venv/bin/python research/014-polymarket-spread-at-horizon/charts/make_charts.py
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from matplotlib.axes import Axes
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qune_research import style  # noqa: E402

STUDY_ID = "Study 014"
SOURCE = ("Polymarket public Gamma and CLOB endpoints, Study 013's daily snapshots of record "
          "(derived aggregates only; no per-market row published)")
PERIOD = ("markets closing 4 Nov to 29 Dec 2026; the quote is the snapshot of record at least 24 h before close "
          "(M1b: 168 h); Study 013's floor 10,000 USDC and spread ≤ 0.10 at the horizon")
TRIAL_NAMES = {"M1": "M1: every market, 24 h", "M1a": "M1a: without Sports, 24 h", "M1b": "M1b: every market, 168 h"}
# [DU26]'s full quoted spread in units of mid (§9.6): 400 bps central, 1,300 to 1,800 bps below a mid of 0.10
DU26_CENTRAL = 0.04
DU26_LONGSHOT = (0.13, 0.18)
C1_BAR = 0.59  # §9.5: half the smaller published premium ln(1300 / 400) = 1.18
PUBLISHED_PREMIUM = 1.18
MIN_CELL = 10  # §9.6: a cell or split under this publishes its count only
LOW_POWER_MARK = "(low-power check"
TITLE_LINES_MAX = 3  # CHART_REVIEW.md: a four-line title was a should-fix three times
LOG_TICKS = (0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def num(x: float | None, decimals: int = 2) -> str:
    """A number for a title, with the typographic minus the axes use; n/a when there is none."""
    return "n/a" if x is None or not math.isfinite(x) else f"{x:.{decimals}f}".replace("-", "−")


def title_lines(fig, finding: str) -> int:
    return len(style._wrap(finding, fig, style.TITLE_SIZE, 0.02, em=0.66))


def decile_label(cell: dict) -> str:
    return f"{cell['decile_low']:.2f}–{cell['decile_high']:.2f}"


def decile_finding(deciles: list[dict]) -> tuple[str, dict]:
    """The title of the decile chart from the published medians: the lowest decile with a value against the
    decile with a value whose midpoint is nearest 0.50; a count-only sentence when either is missing."""
    with_value = [c for c in deciles if not c.get("suppressed") and math.isfinite(float(c.get("median_s", math.nan)))]
    counts_only = [c for c in deciles if c not in with_value]
    info: dict = {"deciles_with_value": len(with_value), "deciles_counts_only": [decile_label(c) for c in counts_only]}
    if not with_value:
        return f"No decile of the mid holds {MIN_CELL} markets: counts only, no median spread published", info
    low = with_value[0]
    central = min(with_value, key=lambda c: abs((c["decile_low"] + c["decile_high"]) / 2 - 0.5))
    info.update({"low_decile": decile_label(low), "low_median_s": low["median_s"], "low_n": low["n"],
                 "central_decile": decile_label(central), "central_median_s": central["median_s"], "central_n": central["n"]})
    if low is central:
        return (f"One decile of the mid holds {MIN_CELL} or more markets: median spread {num(low['median_s'])} of the mid "
                f"in the {decile_label(low)} decile ({low['n']:,} markets); every other decile is a count only"), info
    ratio = low["median_s"] / central["median_s"] if central["median_s"] > 0 else math.nan
    info["ratio"] = ratio
    if not math.isfinite(ratio):
        rel = "against a central median of 0"
    elif ratio > 1.0:
        rel = f"{num(ratio, 1)} times the {decile_label(central)} decile's {num(central['median_s'])}"
    elif ratio < 1.0:
        rel = f"below the {decile_label(central)} decile's {num(central['median_s'])} ({num(ratio, 2)} of it)"
    else:
        rel = f"equal to the {decile_label(central)} decile's"
    return (f"Median spread in the {decile_label(low)} decile of the mid is {num(low['median_s'])} of the mid, {rel}; "
            f"[DU26] reported 0.13–0.18 below 0.10 and 0.04 centrally"), info


def deciles_chart(summary: dict, out_dir: Path) -> tuple[Path, dict]:
    deciles = summary["deciles_M1"]
    finding, info = decile_finding(deciles)
    fig, ax = style.figure(8.4, 6.2)
    assert isinstance(ax, Axes)
    fig.subplots_adjust(bottom=0.24)  # two-line tick labels and the axis label above the source line
    ax.set_yscale("log")
    xs = list(range(len(deciles)))
    values = [(k, float(c["median_s"])) for k, c in enumerate(deciles)
              if not c.get("suppressed") and math.isfinite(float(c.get("median_s", math.nan)))]
    # a line joins adjacent deciles with a value only; a gap stays a gap
    for (k0, v0), (k1, v1) in zip(values, values[1:]):
        if k1 == k0 + 1:
            ax.plot([k0, k1], [v0, v1], color=style.ACCENT, lw=1.4)
    if values:
        ax.plot([k for k, _ in values], [v for _, v in values], "o", color=style.ACCENT, ms=5.5)
    for k, c in enumerate(deciles):
        if (k, float(c.get("median_s", math.nan))) not in values:
            ax.annotate("count\nonly", xy=(k, 0.04), xycoords=("data", "axes fraction"), ha="center",
                        va="bottom", fontsize=style.TICK_SIZE, color=style.TEXT_MUTED)
    ax.axhline(DU26_CENTRAL, color=style.GREY_DARK, lw=1.0, ls="--")
    for ref in DU26_LONGSHOT:
        ax.axhline(ref, color=style.GREY, lw=1.0, ls=":")
    drawn = [v for _, v in values] + [DU26_CENTRAL, *DU26_LONGSHOT]
    lo, hi = min(drawn) / 1.8, max(drawn) * 1.8
    ax.set_ylim(lo, hi)
    ax.set_xlim(-0.5, len(deciles) - 0.5)
    ticks = [t for t in LOG_TICKS if lo <= t <= hi]
    ax.yaxis.set_major_locator(FixedLocator(ticks))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:g}"))
    labels = []
    for k, c in enumerate(deciles):
        if (k, float(c.get("median_s", math.nan))) in values:
            labels.append(f"{decile_label(c)}\n{c['n']:,} · {style.pct(c['floored_share'], 0)}")
        else:
            labels.append(f"{decile_label(c)}\n{c['n']:,} · count")
    ax.set_xticks(xs, labels, fontsize=style.TICK_SIZE - 1)
    ax.set_xlabel("decile of the mid at the snapshot of record; under it: markets · share of quotes one tick wide")
    ax.set_ylabel("median s = (ask − bid) / mid, log scale")
    style.label_line_ends(ax, [style.EndLabel("[DU26] 0.04, central", DU26_CENTRAL, style.GREY_DARK),
                               style.EndLabel("[DU26] 0.13, below 0.10", DU26_LONGSHOT[0], style.GREY),
                               style.EndLabel("[DU26] 0.18, below 0.10", DU26_LONGSHOT[1], style.GREY)])
    subtitle = ("M1 rows, median by decile of the mid. The reference lines are [DU26]'s full quoted spread in units of mid "
                "(400 bps centrally, 1,300 to 1,800 bps below 0.10), not the half-spread its introduction quotes at about "
                f"200 bps. A decile with fewer than {MIN_CELL} markets shows its count only (§9.6); the sample's spread cap of "
                "0.10 truncates s at 10 in the lowest decile (§10 item 2)")
    style.title(fig, finding, subtitle)
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note="Drawn once from results/run/summary.json after the analysis run (§14 step 9).")
    info["title_lines"] = title_lines(fig, finding)
    svg, _ = style.save(fig, out_dir / "deciles_median_s")
    return svg, {"title": finding, **info}


def _interval(f: dict) -> tuple[float, float, str]:
    if f.get("boot_available"):
        return float(f["boot_low"]), float(f["boot_high"]), "clustered bootstrap"
    return float(f.get("wald_low", math.nan)), float(f.get("wald_high", math.nan)), "clustered Wald"


def delta_rows(summary: dict) -> list[dict]:
    """The rows of the Delta chart: the three trials' W fits, then M1's early split (§9.6: descriptive)."""
    rows: list[dict] = []
    for t in ("M1", "M1a", "M1b"):
        rows.append({"label": TRIAL_NAMES[t], "fit": summary["fits"][t]["W"], "colour": style.ACCENT if t == "M1" else style.GREY_DARK})
    early = summary.get("early_split_M1", {})
    for key, label in (("early", "M1 early closes"), ("not_early", "M1 other closes")):
        if key in early:
            rows.append({"label": label, "fit": early[key], "colour": style.GREY})
    return rows


def delta_finding(summary: dict) -> tuple[str, dict]:
    m1 = summary["fits"]["M1"]["W"]
    verdict = str(summary["verdict"]["M1"])
    low_power = LOW_POWER_MARK in verdict
    phrase = verdict.split(LOW_POWER_MARK)[0].strip() + (" (low-power check)" if low_power else "")
    info = {"verdict_M1": verdict, "low_power": low_power}
    if m1.get("suppressed"):
        return f"Δ̂ is not published: M1 holds {m1['n']:,} markets, fewer than {MIN_CELL} (counts only)", info
    if not m1.get("fitted"):
        return f"No Δ̂ could be fitted for M1: {m1.get('no_fit_reason') or 'no fit'}; {phrase}", info
    parts = [f"Δ̂ = {num(m1['delta'])} over every market"]
    for t, words in (("M1a", "without Sports"), ("M1b", "at 168 h")):
        f = summary["fits"][t]["W"]
        parts.append(f"{num(f['delta']) if f.get('fitted') and not f.get('suppressed') else 'n/a'} {words}")
    info.update({"M1": m1["delta"], "M1a": summary["fits"]["M1a"]["W"].get("delta"), "M1b": summary["fits"]["M1b"]["W"].get("delta")})
    return f"{', '.join(parts[:2])} and {parts[2]}, against the bar {C1_BAR}: {phrase}", info


def deltas_chart(summary: dict, out_dir: Path) -> tuple[Path, dict]:
    rows = delta_rows(summary)
    finding, info = delta_finding(summary)
    fig, ax = style.figure(8.0, 0.6 * len(rows) + 3.1)
    assert isinstance(ax, Axes)
    fig.subplots_adjust(left=0.28, bottom=0.21)  # room for the row labels and for the axis label above the source line
    ys = np.arange(len(rows))
    ax.axvline(0.0, color=style.GREY, lw=1.0)
    ax.axvline(C1_BAR, color=style.GREY_DARK, lw=1.0, ls="--")
    ax.axvline(PUBLISHED_PREMIUM, color=style.GREY_FAINT, lw=1.0, ls=":")
    drawn: list[float] = [0.0, C1_BAR, PUBLISHED_PREMIUM]
    kinds: list[str] = []
    for y, r in zip(ys, rows):
        f, colour = r["fit"], r["colour"]
        if f.get("suppressed"):
            ax.annotate(f"n = {f['n']:,}: counts only", xy=(0.0, y), xytext=(6, 0), textcoords="offset points", ha="left",
                        va="center", fontsize=style.TICK_SIZE, color=style.TEXT_MUTED)
            kinds.append("counts only")
            continue
        if not f.get("fitted"):
            ax.annotate(f"no fit: {f.get('no_fit_reason') or 'not fitted'}", xy=(0.0, y), xytext=(6, 0), textcoords="offset points",
                        ha="left", va="center", fontsize=style.TICK_SIZE, color=style.TEXT_MUTED)
            kinds.append("no fit")
            continue
        lo, hi, kind = _interval(f)
        kinds.append(kind)
        if math.isfinite(lo) and math.isfinite(hi):
            ax.hlines(y, lo, hi, color=colour, lw=1.6)
            drawn += [lo, hi]
        d = float(f["delta"])
        drawn.append(d)
        ax.plot([d], [y], "o", color=colour, ms=5.5)
        ax.annotate(num(d), xy=(d, y), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=style.TICK_SIZE, color=colour)
    ax.set_yticks(ys, [r["label"] for r in rows])
    ax.invert_yaxis()
    span = max(drawn) - min(drawn)
    ax.set_xlim(min(drawn) - 0.08 * span, max(drawn) + 0.08 * span)
    ax.grid(False, axis="x")
    ax.grid(False, axis="y")
    ax.tick_params(axis="y", length=0)
    style.despine(ax, keep=("bottom",))
    ax.set_xlabel("Δ̂: mean ln s in the longshot bin [0.01, 0.10) minus the central bin [0.40, 0.60]")
    # the three line labels sit on two sides of their lines so that they cannot run into each other
    for x, text, ha, dx in ((0.0, "no premium", "right", -3), (C1_BAR, f"bar {C1_BAR}", "left", 3),
                            (PUBLISHED_PREMIUM, f"[DU26] {PUBLISHED_PREMIUM}", "left", 3)):
        ax.annotate(text, xy=(x, 1.0), xycoords=("data", "axes fraction"), xytext=(dx, 2), textcoords="offset points",
                    ha=ha, va="bottom", fontsize=style.TICK_SIZE, color=style.TEXT_MUTED)
    m1 = summary["fits"]["M1"]["W"]
    floored = (f"tick-floored share longshot {num(m1.get('floored_share_longshot'), 3)}, central {num(m1.get('floored_share_central'), 3)}; "
               if m1.get("fitted") and not m1.get("suppressed") else "")
    sports = summary.get("sports_share", {}).get("M1")
    subtitle = ("95% intervals: clustered bootstrap for the three trials (clustered Wald when it is not available), clustered Wald "
                f"for the early split, which is descriptive and moves no verdict (§9.6). {floored}Sports share "
                f"{num(sports, 3)}; §9.5 verdict for M1: {summary['verdict']['M1']}")
    style.title(fig, finding, subtitle)
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note="Drawn once from results/run/summary.json after the analysis run (§14 step 9).")
    info.update({"rows": len(rows), "intervals": kinds, "title_lines": title_lines(fig, finding)})
    svg, _ = style.save(fig, out_dir / "deltas")
    return svg, {"title": finding, **info}


def draw_if_run(run_dir: Path, out_dir: Path) -> list[Path]:
    """Draw both charts from `run_dir`/summary.json; an empty list, nothing written, before the analysis run or after a halt."""
    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        print("nothing to draw: the analysis run has not happened (§14 step 9); no file written")
        return []
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("halted") or "fits" not in summary:
        reasons = "; ".join(str(r) for r in summary.get("halt_reasons", [])) or "no fits in the summary"
        print(f"nothing to draw: the analysis run halted ({reasons}); no Δ is estimated (§9.5); no file written")
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    titles: dict[str, dict] = {}
    for fn in (deciles_chart, deltas_chart):
        svg, info = fn(summary, out_dir)
        written += [svg, svg.with_suffix(".png")]
        titles[svg.stem] = info
    manifest = {
        "drawn_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input": {"summary.json": sha256(summary_path), "run_date": summary.get("run_date"),
                  "programme_count": summary.get("programme_count")},
        "titles": titles,
        "standard": "qune_research.style; style.save refused any figure failing the mechanical check; "
                    f"titles at most {TITLE_LINES_MAX} lines (title_lines above)",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=True) + "\n", encoding="utf-8")
    written.append(out_dir / "manifest.json")
    for p in written:
        print(f"  wrote {p.relative_to(STUDY) if p.is_relative_to(STUDY) else p}")
    return written


def main() -> int:
    draw_if_run(STUDY / "results" / "run", HERE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
