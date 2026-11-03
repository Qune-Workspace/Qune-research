"""Study 013 charts in the house style (PREREGISTRATION.md §9.6; §14 step 12),
drawn from the committed scoring outputs only.

Reads results/score/summary.json (the scoring run, once, §14 step 9) and draws
the two registered charts: the reliability diagram of C1 with the fitted curve
and the diagonal, and the slope b with its interval for C1, C1a, C1b, the tag
families and the early split. Computes nothing the scoring run did not publish
beyond presentation (the fitted curve is the published a and b on a grid).
Writes SVG + 2x PNG into this folder with a manifest of the input hash and
every number that appears in a title. No result file is written.

Before the scoring run there is nothing to draw: the script says so and exits 0
with nothing written, so `make charts` passes while the study collects.

Every phrase in a title is chosen by this script from the numbers it reads,
never typed, so a title cannot overstate a result.

Run from the repository root:
  .venv/bin/python research/013-polymarket-calibration-forward/charts/make_charts.py
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qune_research import style  # noqa: E402

STUDY_ID = "Study 013"
SOURCE = "Polymarket public Gamma and CLOB endpoints, daily snapshots and one resolution fetch (derived aggregates only)"
PERIOD = "markets closing 4 Nov to 29 Dec 2026; price from the last daily snapshot at least 24 h before close (realised 24 to 72 h; C1b: 168 h, realised 168 to 216 h)"
TRIAL_NAMES = {"C1": "C1: every market, 24 h", "C1a": "C1a: without Sports, 24 h", "C1b": "C1b: every market, 168 h"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def num(x: float, decimals: int = 2) -> str:
    return "n/a" if x is None or not math.isfinite(x) else f"{x:.{decimals}f}".replace("-", "−")


def _sigmoid(eta: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-eta))


def reliability_chart(summary: dict, out_dir: Path) -> tuple[Path, dict]:
    c1 = summary["trials"]["C1"]
    w = c1["rows"]["W"]
    bins = [b for b in c1["reliability"] if b["n"] > 0 and math.isfinite(b["mean_p"])]
    fig, ax = style.figure(7.2, 5.4)
    ax.plot([0.0, 1.0], [0.0, 1.0], color=style.GREY_LIGHT, lw=1.0, ls="--")
    labels = [style.EndLabel("calibrated market (b = 1)", 1.0, style.GREY)]
    fitted = bool(w["converged"]) and math.isfinite(w["a"]) and math.isfinite(w["b"])
    if fitted:
        grid = np.linspace(0.01, 0.99, 197)
        curve = _sigmoid(w["a"] + w["b"] * (np.log(grid) - np.log1p(-grid)))
        ax.plot(grid, curve, color=style.ACCENT, lw=1.8)
        labels.append(style.EndLabel(f"fitted, b = {num(w['b'])}", float(curve[-1]), style.ACCENT))
    if bins:
        xs = np.array([b["mean_p"] for b in bins])
        ys = np.array([b["outcome_share"] for b in bins])
        err = np.array([max(0.0, (b["ci_high_pp"] - b["diff_pp"]) / 100.0) if math.isfinite(b["ci_high_pp"]) else 0.0 for b in bins])
        ax.errorbar(xs, ys, yerr=err, fmt="o", color=style.GREY_DARK, ecolor=style.GREY, elinewidth=1.0, capsize=2.5, ms=4.5)
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    style.percent_axis(ax, "x")
    style.percent_axis(ax, "y")
    ax.set_xlabel("price of the first listed outcome, 24 h before close (bin mean)")
    ax.set_ylabel("share of markets where it won")
    style.label_line_ends(ax, labels, x=1.0)
    # §9.5: a "supported" sentence carries the window's dates, and the low-power label travels with the verdict
    verdict = str(summary["verdicts"]["C1"]).split(";")[0].strip()
    if summary.get("low_power_label"):
        verdict += " (low-power check)"
    finding = (f"Slope b = {num(w['b'])} against 1.00 for a calibrated market: {verdict}" if fitted
               else f"No slope could be fitted: {verdict}")
    subtitle = (f"Outcome share by price bin with clustered 95% intervals, {w['n']:,} resolved markets in {w['G']:,} events; "
                f"t_cl = {num(w['t_cl'])}, decided at the N = 3 bar 2.128; {summary['verdicts']['C1']}")
    style.title(fig, finding, subtitle)
    style.source(fig, SOURCE, PERIOD, STUDY_ID, note="Scored once after APPROVED (§14 step 9). Low-power label "
                 + ("on." if summary["low_power_label"] else "off."))
    svg, _ = style.save(fig, out_dir / "reliability_c1")
    return svg, {"title": finding, "b": w["b"], "n": w["n"], "G": w["G"], "t_cl": w["t_cl"], "verdict": verdict}


def slopes_chart(summary: dict, out_dir: Path) -> tuple[Path, dict]:
    rows: list[tuple[str, float, float, float, str]] = []  # label, b, low, high, colour
    for name in ("C1", "C1a", "C1b"):
        w = summary["trials"][name]["rows"]["W"]
        bs = w.get("bootstrap") or {}
        if bs.get("available"):
            lo, hi = bs["low"], bs["high"]
        else:
            lo, hi = w["wald_low"], w["wald_high"]
        rows.append((TRIAL_NAMES[name], w["b"], lo, hi, style.ACCENT if name == "C1" else style.GREY_DARK))
    c1_splits = summary["trials"]["C1"]["splits"]
    for key, r in c1_splits.items():
        if key.startswith("tag:") or key in ("early", "not early"):
            label = key.replace("tag:", "C1 tag family: ") if key.startswith("tag:") else f"C1 {key} closes"
            rows.append((label, r["b"], r["wald_low"], r["wald_high"], style.GREY))
    fig, ax = style.figure(7.6, 0.55 * len(rows) + 2.6)
    ys = np.arange(len(rows))
    ax.axvline(1.0, color=style.GREY, lw=1.0)
    ax.axvline(1.0 + 0.02, color=style.GREY_FAINT, lw=1.0, ls=":")
    for y, (label, b, lo, hi, colour) in zip(ys, rows):
        if math.isfinite(lo) and math.isfinite(hi):
            ax.hlines(y, lo, hi, color=colour, lw=1.6)
        if math.isfinite(b):
            ax.plot([b], [y], "o", color=colour, ms=5.5)
            ax.annotate(num(b), xy=(b, y), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=style.TICK_SIZE, color=colour)
    ax.set_yticks(ys, [r[0] for r in rows])
    ax.invert_yaxis()
    ax.grid(False, axis="x")
    ax.grid(False, axis="y")
    ax.tick_params(axis="y", length=0)
    style.despine(ax, keep=("bottom",))
    ax.set_xlabel("slope b of outcome on logit(price); 1.00 = calibrated, 1.02 = the C1 margin")
    ax.annotate("calibrated", xy=(1.0, 1.0), xycoords=("data", "axes fraction"), xytext=(2, 2), textcoords="offset points",
                ha="left", va="bottom", fontsize=style.TICK_SIZE, color=style.TEXT_MUTED)
    c1, c1a, c1b = (summary["trials"][k]["rows"]["W"]["b"] for k in ("C1", "C1a", "C1b"))
    finding = f"Slope b = {num(c1)} over every market, {num(c1a)} without Sports and {num(c1b)} at 168 h, against 1.00"
    subtitle = ("95% intervals: clustered bootstrap for the three trials (clustered Wald when it is not available), clustered Wald for "
                "the C1 splits; the splits are descriptive and move no verdict (§9.6)")
    style.title(fig, finding, subtitle)
    style.source(fig, SOURCE, PERIOD, STUDY_ID)
    svg, _ = style.save(fig, out_dir / "slopes")
    return svg, {"title": finding, "C1": c1, "C1a": c1a, "C1b": c1b, "rows": len(rows)}


def draw_if_scored(score_dir: Path, out_dir: Path) -> list[Path]:
    """Draw both charts from `score_dir`/summary.json; an empty list, nothing written, when the scoring run has not happened."""
    summary_path = score_dir / "summary.json"
    if not summary_path.is_file():
        print("nothing to draw: the scoring run has not happened (§14 step 9); no file written")
        return []
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    titles: dict[str, dict] = {}
    for fn in (reliability_chart, slopes_chart):
        svg, info = fn(summary, out_dir)
        written += [svg, svg.with_suffix(".png")]
        titles[svg.stem] = info
    manifest = {
        "drawn_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input": {"summary.json": sha256(summary_path), "scoring_run_at_utc": summary.get("run_at_utc"), "code_commit": summary.get("code_commit")},
        "titles": titles,
        "standard": "qune_research.style; style.save refused any figure failing the mechanical check",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=True) + "\n", encoding="utf-8")
    written.append(out_dir / "manifest.json")
    for p in written:
        print(f"  wrote {p.relative_to(STUDY) if p.is_relative_to(STUDY) else p}")
    return written


def main() -> int:
    draw_if_scored(STUDY / "results" / "score", HERE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
