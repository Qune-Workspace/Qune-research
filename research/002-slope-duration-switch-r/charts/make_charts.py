"""Study 002 charts in the house style, drawn from the committed validation files.

Reads results/validation/window1/validation.json and window2/validation.json
(the pre-registered checks and the by-year gaps), the post-hoc by-year table
results/validation/window2/posthoc_by_year.md (descriptive, no decision
weight) and, for one reference line, Study 001's results/validation/validation.json.
Computes nothing the study did not already publish and writes SVG + 2x PNG into
this folder with a manifest of the input hashes and every number that appears
in a title.  The run's own figures in results/validation/ stay as they were;
this is the same check presented to the chart standard of 2026-10-23
(qune_research/style.py).  No result file is written.  Nothing is re-run.

Run from the repository root:  .venv/bin/python research/002-slope-duration-switch-r/charts/make_charts.py
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(ROOT))

from qune_research import style  # noqa: E402

STUDY_ID = "Study 002"
SOURCE = "Synthetic ageing bond from FRED Treasury yields; IEF from Alpaca (2016-18) and Tiingo (2003-15) daily bars"
W1 = STUDY / "results" / "validation" / "window1" / "validation.json"
W2 = STUDY / "results" / "validation" / "window2" / "validation.json"
POSTHOC = STUDY / "results" / "validation" / "window2" / "posthoc_by_year.md"
STUDY_001 = ROOT / "research" / "001-slope-duration-switch" / "results" / "validation" / "validation.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def band(threshold: str) -> tuple[float, float]:
    """The two numbers of a threshold such as 'in [-0.0045, 0.0035]'."""
    nums = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", threshold)]
    if len(nums) != 2:
        raise ValueError(f"expected two numbers in threshold {threshold!r}")
    return nums[0], nums[1]


def one_number(threshold: str) -> float:
    """The one unsigned number of a threshold such as '<= 0.015' or 'within +/-0.004'."""
    nums = re.findall(r"\d*\.\d+|\d+", threshold)
    if len(nums) != 1:
        raise ValueError(f"expected one number in threshold {threshold!r}")
    return float(nums[0])


def signed_pct(x: float, decimals: int = 2) -> str:
    return ("+" if x > 0 else "") + style.pct(x, decimals)


def year_span(years: list[int]) -> str:
    return f"{years[0]}–{str(years[-1])[2:]}"


def level_gap_chart(w1: dict, w2: dict, s001: dict, numbers: dict) -> Path:
    """The level check (A4) the rebuilt series passed, by calendar year and window, against Study 001's miss."""
    windows = []
    for name, d in (("window2", w2), ("window1", w1)):
        by_year = {int(y): float(v) for y, v in d["statistics"]["IEF"]["mean_diff_annual_by_year"].items()}
        lo, hi = band(d["checks"]["A4"]["threshold"])
        windows.append({
            "name": name, "years": sorted(by_year), "by_year": by_year,
            "mean": float(d["checks"]["A4"]["value"]), "pass": bool(d["checks"]["A4"]["pass"]),
            "band": (lo, hi), "exante": float(d["checks"]["A4"]["exante_central_estimate"]),
        })
    gap_001 = float(s001["checks"]["A4"]["value"])
    band_001 = one_number(s001["checks"]["A4"]["threshold"])
    w2i, w1i = windows
    numbers["level_gap"] = {
        w["name"]: {"mean": w["mean"], "pass": w["pass"], "band": w["band"], "exante_central": w["exante"],
                    "years": f"{w['years'][0]}-{w['years'][-1]}", "by_year": w["by_year"]} for w in windows}
    numbers["study_001_mean_gap_2016_2018"] = gap_001
    numbers["study_001_band"] = band_001

    both_pass = w1i["pass"] and w2i["pass"]
    if both_pass:
        finding = (f"The rebuilt bond matched IEF's return level: a gap of {signed_pct(w2i['mean'])} a year over "
                   f"{year_span(w2i['years'])} and {signed_pct(w1i['mean'])} over {year_span(w1i['years'])}, inside "
                   f"the bands set beforehand; Study 001's bond had missed by {signed_pct(gap_001)}")
    else:
        failed = [w for w in windows if not w["pass"]]
        finding = (f"The rebuilt bond missed IEF's return level on {' and '.join(year_span(w['years']) for w in failed)}: "
                   + ", ".join(f"{signed_pct(w['mean'])} against [{signed_pct(w['band'][0])}, {signed_pct(w['band'][1])}]"
                               for w in failed))
    numbers["level_gap_title"] = finding

    fig, ax = style.figure(width=8.0, height=4.6)
    style.title(fig, finding,
                "Annualised mean daily difference, IEF total return minus the synthetic bond, by calendar year, % p.a. "
                "Shaded: each window's pre-registered acceptance band for the window mean (check A4); the check is on "
                "the mean, not on single years.")
    fig.subplots_adjust(right=0.76)
    all_years = w2i["years"] + w1i["years"]
    vals = [w2i["by_year"][y] for y in w2i["years"]] + [w1i["by_year"][y] for y in w1i["years"]]
    ax.bar(all_years, vals, color=style.GREY_LIGHT, width=0.7)
    ax.axhline(0.0, color=style.GREY, lw=0.8)
    for w in windows:
        x0, x1 = w["years"][0] - 0.5, w["years"][-1] + 0.5
        ax.fill_between([x0, x1], [w["band"][0]] * 2, [w["band"][1]] * 2, color=style.SHADE, lw=0, zorder=0)
        ax.hlines(w["mean"], x0, x1, color=style.ACCENT, lw=2.0)
    # Study 001's series on the same 2016-2018 window, for the reference the title makes.
    x0, x1 = w1i["years"][0] - 0.5, w1i["years"][-1] + 0.5
    ax.hlines(gap_001, x0, x1, color=style.GREY_DARK, lw=1.2, ls=(0, (4, 3)))
    xr = all_years[-1] + 0.55
    ax.annotate(f"Study 001's bond {signed_pct(gap_001)}", xy=(xr, gap_001), xytext=(6, 0), textcoords="offset points",
                ha="left", va="center", fontsize=style.LABEL_SIZE, color=style.GREY_DARK, annotation_clip=False)
    ax.annotate(f"mean {signed_pct(w1i['mean'])}", xy=(xr, w1i["mean"]), xytext=(6, 0), textcoords="offset points",
                ha="left", va="center", fontsize=style.LABEL_SIZE, color=style.ACCENT, annotation_clip=False)
    # Below the line at the window's right end: above it the label ran across the 2014 bar (chart review, 2026-10-23).
    ax.annotate(f"mean {signed_pct(w2i['mean'])}", xy=(w2i["years"][-1] + 0.5, w2i["mean"]), xytext=(-4, -5),
                textcoords="offset points", ha="right", va="top", fontsize=style.LABEL_SIZE, color=style.ACCENT)
    for w, label in ((w2i, "window 2, thirteen years never seen"), (w1i, "window 1")):
        ax.annotate(label, xy=((w["years"][0] + w["years"][-1]) / 2.0, 1.0), xycoords=("data", "axes fraction"),
                    xytext=(0, -2), textcoords="offset points", ha="center", va="top", fontsize=style.TICK_SIZE,
                    color=style.TEXT_MUTED)
    style.despine(ax, keep=("bottom",))
    ax.tick_params(axis="y", length=0)
    style.percent_axis(ax, decimals=1)
    ax.set_xticks(all_years)
    ax.set_xticklabels([str(y) if i % 2 == 0 else "" for i, y in enumerate(all_years)])
    ax.set_xlim(all_years[0] - 0.6, all_years[-1] + 0.6)
    ymin = min(min(vals), min(w["band"][0] for w in windows)) * 1.25
    ymax = max(max(vals), gap_001) * 1.35
    ax.set_ylim(ymin, ymax)
    style.source(fig, SOURCE, f"{w2i['years'][0]} to {w1i['years'][-1]}", STUDY_ID,
                 note="Data check A4 (section 5.3), not a performance test; no rule was run. results/validation/window*/validation.json; "
                      "Study 001's gap from its results/validation/validation.json. Bars in calendar order, not sorted.")
    svg, _png = style.save(fig, HERE / "level_gap_by_year")
    return svg


def parse_posthoc(path: Path) -> tuple[dict[int, dict[str, float]], dict[str, dict[str, float]]]:
    """Rows of the post-hoc by-year table: year rows and the summary rows."""
    years: dict[int, dict[str, float]] = {}
    summary: dict[str, dict[str, float]] = {}
    for line in path.read_text().splitlines():
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| Period"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 8:
            continue
        row = {"days": float(cells[1]), "te": float(cells[2].rstrip("%")) / 100.0, "corr": float(cells[3]),
               "slope": float(cells[4]), "ief_vol": float(cells[5].rstrip("%")) / 100.0,
               "syn_vol": float(cells[6].rstrip("%")) / 100.0, "ratio": float(cells[7])}
        if re.fullmatch(r"\d{4}", cells[0]):
            years[int(cells[0])] = row
        else:
            summary[cells[0]] = row
    if len(years) < 10 or not summary:
        raise ValueError(f"could not parse the by-year table in {path}")
    return years, summary


def tracking_error_chart(w2: dict, w1: dict, numbers: dict) -> Path:
    """The check that failed (A3), by year against IEF's volatility: post hoc, descriptive."""
    years, summary = parse_posthoc(POSTHOC)
    te_limit = one_number(w2["checks"]["A3"]["threshold"])
    te_w2 = float(w2["checks"]["A3"]["value"])
    te_w1 = float(w1["checks"]["A3"]["value"])
    w1_row = next(v for k, v in summary.items() if k.startswith("Window 1"))
    all_row = next(v for k, v in summary.items() if k.startswith("Window 2, all"))
    above = sorted(y for y, r in years.items() if r["te"] > te_limit)
    ratios = [r["ratio"] for r in years.values()]
    numbers["tracking_error"] = {
        "window2": te_w2, "window1": te_w1, "limit": te_limit, "window2_pass": bool(w2["checks"]["A3"]["pass"]),
        "years_above_limit": above, "n_years": len(years), "ratio_min": min(ratios), "ratio_max": max(ratios),
        "window2_ratio": all_row["ratio"], "window1_ratio": w1_row["ratio"],
        "ief_vol_window2": all_row["ief_vol"], "ief_vol_window1": w1_row["ief_vol"],
        "by_year": {y: {"te": r["te"], "ief_vol": r["ief_vol"], "ratio": r["ratio"]} for y, r in years.items()},
    }
    finding = (f"Tracking error rose with IEF's volatility, {min(ratios):.2f} to {max(ratios):.2f} of it in every year, so a "
               f"fixed {style.pct(te_limit, 1)} limit set when volatility was {style.pct(w1_row['ief_vol'], 1)} was breached "
               f"in {len(above)} of {len(years)} years and on the whole window ({style.pct(te_w2, 2)})")
    numbers["tracking_error_title"] = finding

    fig, ax = style.figure(width=8.0, height=5.4)
    top = style.title(fig, finding,
                      "Each point is one calendar year of 2003–2015: annualised tracking error of IEF against the "
                      "synthetic bond (vertical) and IEF's realised volatility (horizontal), % p.a. Check A3 is scored on "
                      "the whole window.")
    # Room for the axis label above the three-line source.
    fig.subplots_adjust(right=0.95, top=top, bottom=0.22)
    xs = [years[y]["ief_vol"] for y in sorted(years)]
    xmax = max(xs + [w1_row["ief_vol"]]) * 1.12
    xline = [0.0, xmax]
    ax.plot(xline, [all_row["ratio"] * x for x in xline], color=style.GREY_LIGHT, lw=1.0, ls=(0, (4, 3)), zorder=1)
    # The ratio label goes under the empty lower-left stretch of the line, clear of every point.
    x_lab = 0.025
    ax.annotate(f"{all_row['ratio']:.2f} × volatility (window-2 ratio)", xy=(x_lab, all_row["ratio"] * x_lab),
                xytext=(0, -5), textcoords="offset points", ha="left", va="top", fontsize=style.TICK_SIZE,
                color=style.GREY)
    ax.axhline(te_limit, color=style.GREY_DARK, lw=1.0, ls=(0, (4, 3)), zorder=1)
    ax.annotate(f"limit {style.pct(te_limit, 1)} (A3)", xy=(0.0, te_limit), xycoords=("axes fraction", "data"),
                xytext=(4, 3), textcoords="offset points", ha="left", va="bottom", fontsize=style.TICK_SIZE,
                color=style.GREY_DARK)
    # Years over the limit are labelled up and to the right; the years under it cluster just below the line,
    # so their labels go beneath the points in two alternating rows.
    below_row = 1  # the first (lowest-volatility) sub-limit year takes the lower row, clear of window 1's leader
    for y in sorted(years, key=lambda k: years[k]["ief_vol"]):
        r = years[y]
        if y in above:
            ax.scatter([r["ief_vol"]], [r["te"]], s=28, color=style.ACCENT, zorder=3, linewidths=0)
            # 2013 sits just left of and below 2004, so its label goes below-left; up-right it covered the 2004
            # marker (chart review, 2026-10-23).
            if y == 2013:
                ax.annotate(str(y), xy=(r["ief_vol"], r["te"]), xytext=(-4, -10), textcoords="offset points",
                            ha="right", fontsize=style.TICK_SIZE - 1, color=style.ACCENT)
            else:
                ax.annotate(str(y), xy=(r["ief_vol"], r["te"]), xytext=(4, 3), textcoords="offset points",
                            fontsize=style.TICK_SIZE - 1, color=style.ACCENT)
        else:
            ax.scatter([r["ief_vol"]], [r["te"]], s=28, color=style.GREY, zorder=3, linewidths=0)
            ax.annotate(str(y), xy=(r["ief_vol"], r["te"]), xytext=(0, -4 - 10 * (below_row % 2)),
                        textcoords="offset points", ha="center", va="top", fontsize=style.TICK_SIZE - 1,
                        color=style.GREY)
            below_row += 1
    ax.scatter([w1_row["ief_vol"]], [w1_row["te"]], s=40, facecolors="white", edgecolors=style.GREY_DARK,
               linewidths=1.2, zorder=3)
    # Window 1's point sits under the cluster of sub-limit years, so its label goes in the empty space to the
    # left, between the ratio line and the limit, with a thin leader.
    ax.annotate(f"window 1, 2016–18 ({style.pct(w1_row['te'], 2)})", xy=(w1_row["ief_vol"], w1_row["te"]),
                xytext=(0.003, 0.012), textcoords="data", ha="left", va="center", fontsize=style.TICK_SIZE,
                color=style.GREY_DARK,
                arrowprops={"arrowstyle": "-", "color": style.GREY_LIGHT, "lw": 0.8, "shrinkA": 2, "shrinkB": 5})
    style.percent_axis(ax, decimals=0, axis="x")
    style.percent_axis(ax, decimals=1)
    ax.set_xlim(0.0, xmax)
    ax.set_ylim(0.0, max(r["te"] for r in years.values()) * 1.15)
    ax.set_xlabel("IEF realised volatility, % p.a.")
    ax.set_ylabel("Tracking error, % p.a.")
    style.source(fig, "Tiingo IEF adjusted close; synthetic bond from FRED yields", "2003-01-02 to 2015-12-31", STUDY_ID,
                 note="Post hoc and descriptive, no decision weight (results/validation/window2/posthoc_by_year.md); "
                      "the pre-registered check failed on the full-window figure, 2.02% against 1.5%.")
    svg, _png = style.save(fig, HERE / "tracking_error_vs_volatility")
    return svg


def main() -> None:
    inputs = {str(p.relative_to(ROOT)): sha256(p) for p in (W1, W2, POSTHOC, STUDY_001)}
    w1 = json.loads(W1.read_text())
    w2 = json.loads(W2.read_text())
    s001 = json.loads(STUDY_001.read_text())
    numbers: dict = {}
    outputs: list[str] = []
    for p in (level_gap_chart(w1, w2, s001, numbers), tracking_error_chart(w2, w1, numbers)):
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
        "note": "Presentation only. Every number is read from the committed validation files (the by-year tracking "
                "errors from the post-hoc table, which carries no decision weight); no result file is written. "
                "Style: qune_research/style.py (chart standard of 2026-10-23).",
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(numbers, indent=2, default=str))


if __name__ == "__main__":
    main()
