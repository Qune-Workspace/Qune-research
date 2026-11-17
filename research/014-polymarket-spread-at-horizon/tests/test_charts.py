"""Tests of the Study 014 chart step (PREREGISTRATION.md §9.6, §14 step 9).

The chart script reads results/run/summary.json only. The summary here is the one the engine itself writes on the
synthetic folders of test_run.py (not a dict typed to the chart's shape, so a key the run renames fails here), the two
charts are drawn into tmp_path and checked against the mechanical part of the house standard (style.save is strict),
and the no-run and halted paths are shown to write nothing. Study 013's chart review items are run as a checklist:
the verdict phrase comes from the run's own §9.5 sentence with the low-power label travelling with it (should-fix 11);
a cell or split under ten markets shows its count only (should-fix 12); a title stays within three lines.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

from src import analysis as an

from tests.test_run import _build_013, _build_014, _markets, _run

STUDY_DIR = Path(__file__).resolve().parents[1]


def load_module():
    spec = importlib.util.spec_from_file_location("make_charts_014", STUDY_DIR / "charts" / "make_charts.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _summary_from_the_engine(root: Path, markets=None) -> tuple[Path, dict]:
    """Run the engine on a synthetic folder and return results/run/ and the summary it wrote."""
    ms = markets if markets is not None else _markets()
    s13 = _build_013(root, ms)
    s14 = _build_014(root)
    _run(root, s14, s13, resamples=50)
    run_dir = s14 / "results" / "run"
    return run_dir, json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))


def _rewrite(run_dir: Path, summary: dict) -> None:
    (run_dir / "summary.json").write_text(json.dumps(summary, allow_nan=True), encoding="utf-8")


def test_two_charts_from_the_engine_summary_pass_the_house_check(tmp_path: Path):
    mod = load_module()
    run_dir, s = _summary_from_the_engine(tmp_path)
    out = tmp_path / "charts"
    written = mod.draw_if_run(run_dir, out)
    assert sorted(p.name for p in written) == ["deciles_median_s.png", "deciles_median_s.svg", "deltas.png", "deltas.svg", "manifest.json"]
    assert all(p.is_file() and p.stat().st_size > 0 for p in written)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["input"]["summary.json"]) == 64 and manifest["input"]["programme_count"] == 40
    m1 = s["fits"]["M1"]["W"]
    d = manifest["titles"]["deltas"]
    assert d["M1"] == m1["delta"] and f"{m1['delta']:.2f}" in d["title"] and "against the bar 0.59" in d["title"]
    # the verdict phrase is the run's own §9.5 sentence (013 review, should-fix 11)
    assert s["verdict"]["M1"].split(" (low-power")[0] in d["title"]
    assert d["rows"] == 5 and d["intervals"][0] == "clustered bootstrap" and d["intervals"][3] == "clustered Wald"
    svg = (out / "deltas.svg").read_text(encoding="utf-8")
    assert "M1a: without Sports" in svg and "M1 early closes" in svg and "the bar" in svg
    # the decile chart: the synthetic sample fills the lowest decile and the two central ones; the rest are counts only
    dc = manifest["titles"]["deciles_median_s"]
    assert dc["low_decile"] == "0.01–0.10" and dc["low_n"] == 220 and dc["central_decile"] in ("0.40–0.50", "0.50–0.60")
    assert dc["ratio"] == dc["low_median_s"] / dc["central_median_s"] and "times the" in dc["title"]
    assert "0.20–0.30" in dc["deciles_counts_only"] and len(dc["deciles_counts_only"]) + dc["deciles_with_value"] == 10
    dsvg = (out / "deciles_median_s.svg").read_text(encoding="utf-8")
    assert "only" in dsvg and "· count" in dsvg and "[DU26] 0.04, central" in dsvg
    # a four-line title was a should-fix three times in CHART_REVIEW.md
    assert dc["title_lines"] <= mod.TITLE_LINES_MAX and d["title_lines"] <= mod.TITLE_LINES_MAX


def test_counts_only_cells_and_splits_draw_no_value(tmp_path: Path):
    """013 review should-fix 12: fewer than ten markets is a count, not a value, on both charts."""
    mod = load_module()
    run_dir, s = _summary_from_the_engine(tmp_path)
    # M1a's W fit published as counts only, as run.publishable writes it
    w = s["fits"]["M1a"]["W"]
    s["fits"]["M1a"]["W"] = {k: w[k] for k in ("n", "n_longshot", "n_central", "G", "G_longshot", "G_central", "fitted", "no_fit_reason")}
    s["fits"]["M1a"]["W"].update({"n": 7, "suppressed": True, "delta_sign": 1})
    _rewrite(run_dir, s)
    out = tmp_path / "charts"
    mod.draw_if_run(run_dir, out)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    d = manifest["titles"]["deltas"]
    assert d["intervals"][1] == "counts only" and "n/a without Sports" in d["title"]
    assert "n = 7: counts only" in (out / "deltas.svg").read_text(encoding="utf-8")
    # every suppressed decile carries no median in the manifest's numbers and the chart names it as a count
    for c in s["deciles_M1"]:
        if c["suppressed"]:
            assert math.isnan(c["median_s"]) and c["n"] < an.MIN_CELL
    assert manifest["titles"]["deciles_median_s"]["deciles_counts_only"]


def test_low_power_label_travels_and_no_fit_is_said(tmp_path: Path):
    mod = load_module()
    run_dir, s = _summary_from_the_engine(tmp_path)
    s["low_power"] = True
    for t in s["verdict"]:
        s["verdict"][t] = f"{s['verdict'][t]} {an.LOW_POWER_LABEL}"
    _rewrite(run_dir, s)
    mod.draw_if_run(run_dir, tmp_path / "one")
    d = json.loads((tmp_path / "one" / "manifest.json").read_text(encoding="utf-8"))["titles"]["deltas"]
    assert d["low_power"] and d["title"].endswith("(low-power check)") and an.LOW_POWER_LABEL in d["verdict_M1"]
    # no fit for M1: the title says so and names the reason; nothing is drawn as a value for that row
    m1 = s["fits"]["M1"]["W"]
    m1.update({"fitted": False, "no_fit_reason": "SE_cl is 0", "delta": math.nan, "boot_available": False,
               "wald_low": math.nan, "wald_high": math.nan})
    s["verdict"]["M1"] = "not supported (no fit)"
    _rewrite(run_dir, s)
    mod.draw_if_run(run_dir, tmp_path / "two")
    d2 = json.loads((tmp_path / "two" / "manifest.json").read_text(encoding="utf-8"))["titles"]["deltas"]
    assert d2["title"].startswith("No Δ̂ could be fitted for M1: SE_cl is 0") and d2["intervals"][0] == "no fit"


def test_every_decile_a_count_only_still_draws_with_a_counts_only_title(tmp_path: Path):
    mod = load_module()
    run_dir, s = _summary_from_the_engine(tmp_path)
    for c in s["deciles_M1"]:
        c.update({"n": 3, "G": 3, "suppressed": True, "median_s": math.nan, "median_half_points": math.nan,
                  "floored_share": math.nan, "median_liquidity": math.nan, "fees_enabled_share": math.nan})
    _rewrite(run_dir, s)
    written = mod.draw_if_run(run_dir, tmp_path / "charts")
    assert len(written) == 5
    dc = json.loads((tmp_path / "charts" / "manifest.json").read_text(encoding="utf-8"))["titles"]["deciles_median_s"]
    assert dc["title"].startswith("No decile of the mid holds 10 markets") and dc["deciles_with_value"] == 0


def test_a_halted_run_draws_nothing(tmp_path: Path, capsys):
    mod = load_module()
    s13 = _build_013(tmp_path, _markets(), price_pass=False)
    s14 = _build_014(tmp_path)
    s = _run(tmp_path, s14, s13)
    assert s["halted"]
    assert mod.draw_if_run(s14 / "results" / "run", tmp_path / "charts") == []
    assert "halted" in capsys.readouterr().out and not (tmp_path / "charts").exists()


def test_before_the_analysis_run_nothing_is_drawn(tmp_path: Path, capsys):
    mod = load_module()
    assert mod.draw_if_run(tmp_path / "run", tmp_path / "charts") == []
    assert "nothing to draw" in capsys.readouterr().out
    assert not (tmp_path / "charts").exists()


def test_main_on_the_real_folder_writes_nothing_before_the_run(capsys):
    """The study's results/run/ does not exist before 2027-01-20; `make charts` must pass with nothing written."""
    mod = load_module()
    assert not (STUDY_DIR / "results" / "run").exists()
    before = sorted(p.name for p in (STUDY_DIR / "charts").iterdir())
    assert mod.main() == 0
    assert "nothing to draw" in capsys.readouterr().out
    assert sorted(p.name for p in (STUDY_DIR / "charts").iterdir()) == before
