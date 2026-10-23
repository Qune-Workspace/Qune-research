"""Study 001 chart in the house style, drawn from the committed validation files.

Reads results/validation/run1-ten-year-only/validation.json (run 1, the 10-year
par bond alone) and results/validation/validation.json (run 2, the 7/10-year
blend), computes nothing the study did not already publish, and writes SVG + 2x
PNG into this folder with a manifest of the input hashes and every number that
appears in a title.  The run's own figures in results/validation/ stay as they
were; this is the same check presented to the chart standard of 2026-10-23
(qune_research/style.py).  No result file is written.  Nothing is re-run.

Run from the repository root:  .venv/bin/python research/001-slope-duration-switch/charts/make_charts.py
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

STUDY_ID = "Study 001"
SOURCE = "Synthetic par bond from FRED Treasury yields; IEF from Alpaca daily bars"
RUNS = (
    ("run1", STUDY / "results" / "validation" / "run1-ten-year-only" / "validation.json", "Run 1\n10-year bond alone"),
    ("run2", STUDY / "results" / "validation" / "validation.json", "Run 2\n7/10-year blend"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def limit(threshold: str) -> float:
    """The one number in a threshold string such as '<= 0.015' or 'within +/-0.004'."""
    nums = re.findall(r"\d*\.\d+|\d+", threshold)
    if len(nums) != 1:
        raise ValueError(f"expected one number in threshold {threshold!r}")
    return float(nums[0])


def signed_pct(x: float, decimals: int = 3) -> str:
    return ("+" if x > 0 else "") + style.pct(x, decimals)


def panel(ax, name: str, values: dict[str, float], fails: dict[str, bool], band: float | None,
          limit_value: float, heading: str, limit_text: str) -> None:
    labels = [RUNS[0][2], RUNS[1][2]]
    vals = [values["run1"], values["run2"]]
    colours = [style.ACCENT if fails[r] else style.GREY_LIGHT for r in ("run1", "run2")]
    ax.bar(labels, vals, color=colours, width=0.55)
    if band is not None:
        ax.axhspan(-band, band, color=style.SHADE, lw=0, zorder=0)
        ax.axhline(0.0, color=style.GREY, lw=0.8)
    ax.axhline(limit_value, color=style.GREY_DARK, lw=1.0, ls=(0, (4, 3)))
    # The limit label sits between the two bars, just under the line, where no bar or value label can reach it.
    ax.annotate(limit_text, xy=(0.5, limit_value), xytext=(0, -3), textcoords="offset points",
                ha="center", va="top", fontsize=style.TICK_SIZE, color=style.GREY_DARK)
    for x, v, r in zip(labels, vals, ("run1", "run2")):
        text = signed_pct(v) if band is not None else style.pct(v, 3)
        ax.annotate(text + (" fail" if fails[r] else " pass"), xy=(x, v), xytext=(0, 4),
                    textcoords="offset points", ha="center", va="bottom", fontsize=style.LABEL_SIZE,
                    color=style.ACCENT if fails[r] else style.GREY_DARK)
    ax.annotate(heading, xy=(0.0, 1.0), xycoords="axes fraction", xytext=(0, 8), textcoords="offset points",
                ha="left", va="bottom", fontsize=style.LABEL_SIZE, color=style.TEXT)
    style.despine(ax, keep=("bottom",))
    ax.tick_params(axis="y", length=0)
    style.percent_axis(ax, decimals=1)
    top = max(max(vals), limit_value) * 1.25
    ax.set_ylim(min(0.0, -band * 1.15) if band is not None else 0.0, top)


def main() -> None:
    inputs: dict[str, str] = {}
    data: dict[str, dict] = {}
    for key, path, _label in RUNS:
        data[key] = json.loads(path.read_text())
        inputs[str(path.relative_to(ROOT))] = sha256(path)
    checks = {k: v["checks"] for k, v in data.items()}
    te = {k: float(checks[k]["A3"]["value"]) for k in checks}
    gap = {k: float(checks[k]["A4"]["value"]) for k in checks}
    te_fail = {k: not checks[k]["A3"]["pass"] for k in checks}
    gap_fail = {k: not checks[k]["A4"]["pass"] for k in checks}
    te_limit = limit(checks["run2"]["A3"]["threshold"])
    gap_band = limit(checks["run2"]["A4"]["threshold"])
    if limit(checks["run1"]["A3"]["threshold"]) != te_limit or limit(checks["run1"]["A4"]["threshold"]) != gap_band:
        raise ValueError("the two runs were scored against different thresholds")
    others = [c for c in checks["run1"] if c not in ("A3", "A4")]
    others_passed_both = all(checks[r][c]["pass"] for r in checks for c in others)
    days = {k: int(data[k]["statistics"]["IEF"]["days"]) for k in data}
    window = data["run2"]["window"]
    numbers = {
        "tracking_error_annual": te, "mean_diff_annual": gap,
        "tracking_error_limit": te_limit, "mean_diff_band": gap_band,
        "A3_fail": te_fail, "A4_fail": gap_fail,
        "other_checks": others, "other_checks_passed_in_both_runs": others_passed_both,
        "days": days, "window": window,
    }

    # The title's verbs follow from the pass/fail pattern; nothing here is typed from memory.
    if te_fail["run1"] and not te_fail["run2"]:
        te_phrase = f"fixed the tracking error ({style.pct(te['run1'], 3)} to {style.pct(te['run2'], 3)} a year)"
    elif not te_fail["run1"] and not te_fail["run2"]:
        te_phrase = f"left the tracking error inside the limit ({style.pct(te['run1'], 3)} to {style.pct(te['run2'], 3)})"
    else:
        te_phrase = f"did not fix the tracking error ({style.pct(te['run1'], 3)} to {style.pct(te['run2'], 3)})"
    if gap_fail["run1"] and gap_fail["run2"]:
        gap_phrase = (f"but not the return gap: {signed_pct(gap['run1'])} then {signed_pct(gap['run2'])} a year "
                      f"against ±{style.pct(gap_band, 2)}, so the study halted")
        joiner = " "
    elif gap_fail["run1"] and not gap_fail["run2"]:
        gap_phrase = f"and brought the return gap inside the band ({signed_pct(gap['run1'])} to {signed_pct(gap['run2'])})"
        joiner = " "
    else:
        gap_phrase = f"with the return gap at {signed_pct(gap['run1'])} then {signed_pct(gap['run2'])} a year"
        joiner = ", "
    finding = f"Blending in the 7-year bond {te_phrase}{joiner}{gap_phrase}"
    numbers["title"] = finding

    fig, axes = style.figure(width=8.0, height=5.2, ncols=2)
    top = style.title(fig, finding,
                      f"Daily returns of IEF against the synthetic bond, {window['start']} to {window['end']} "
                      f"({days['run2']:,} days), annualised, % p.a. Checks A3 and A4 of the six pre-registered; "
                      + ("the other four passed in both runs." if others_passed_both else "see the note for the other four."))
    # Room above each panel for its heading and below for the two-line run labels over the source line.
    fig.subplots_adjust(left=0.08, right=0.97, wspace=0.35, top=top - 0.06, bottom=0.25)
    panel(axes[0], "A3", te, te_fail, None, te_limit, "Tracking error (A3)", f"limit {style.pct(te_limit, 1)}")
    panel(axes[1], "A4", gap, gap_fail, gap_band, gap_band, "Mean return gap, IEF minus synthetic (A4)",
          f"band ±{style.pct(gap_band, 2)}")
    style.source(fig, SOURCE, f"{window['start']} to {window['end']}", STUDY_ID,
                 note="Data check (section 5.3), not a performance test; no rule was run. results/validation/*/validation.json. "
                      "Bars in run order, not sorted: run 2 was the one correction the halt rule allowed.")
    svg, png = style.save(fig, HERE / "validation_checks")

    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.strip()
    except Exception:  # pragma: no cover
        commit = "unknown"
    manifest = {
        "made_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repository_commit_at_run": commit,
        "inputs_sha256": inputs,
        "outputs": [str(svg.relative_to(ROOT)), str(png.relative_to(ROOT))],
        "numbers_in_titles": numbers,
        "note": "Presentation only. Every number is read from the committed validation files; "
                "no result file is written. Style: qune_research/style.py (chart standard of 2026-10-23).",
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(numbers, indent=2))


if __name__ == "__main__":
    main()
