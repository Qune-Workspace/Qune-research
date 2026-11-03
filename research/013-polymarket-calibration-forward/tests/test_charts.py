"""Tests of the Study 013 chart step (PREREGISTRATION.md §9.6, §14 step 12) on a synthetic scoring summary.

The chart script reads results/score/summary.json only; here a summary with the keys the scoring run writes
is built in memory, the two charts are drawn into tmp_path and checked against the mechanical part of the
house standard (style.save is strict), and the no-scoring-run path is shown to write nothing.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parents[1]


def load_module():
    spec = importlib.util.spec_from_file_location("make_charts_013", STUDY_DIR / "charts" / "make_charts.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def row(b: float, n: int = 1000, g: int = 400, se: float = 0.05, boot: bool = True) -> dict:
    r = {"n": n, "G": g, "a": 0.01, "b": b, "converged": True, "separated": False, "se_cl": se, "se_ordinary": se * 0.9,
         "t_cl": (b - 1.0) / se, "wald_low": b - 1.96 * se, "wald_high": b + 1.96 * se, "loglik": -600.0, "loglik_calibrated": -610.0}
    if boot:
        r["bootstrap"] = {"low": b - 0.09, "high": b + 0.11, "resamples": 2000, "dropped": 0, "available": True}
    return r


def reliability() -> list[dict]:
    edges = (0.01, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.99)
    out = []
    for k in range(10):
        mid = (edges[k] + edges[k + 1]) / 2
        share = min(0.99, max(0.01, mid + 0.03 * (mid - 0.5)))
        out.append({"bin_low": edges[k], "bin_high": edges[k + 1], "n": 100.0, "clusters": 60.0, "mean_p": mid, "outcome_share": share,
                    "diff_pp": 100 * (share - mid), "ci_low_pp": 100 * (share - mid) - 4.0, "ci_high_pp": 100 * (share - mid) + 4.0})
    return out


def summary(b: float = 1.07) -> dict:
    splits = {"early": row(1.12, 300, 150, 0.09, boot=False), "not early": row(1.05, 700, 300, 0.06, boot=False),
              "tag:Politics": row(1.03, 520, 200, 0.07, boot=False), "tag:Sports": row(1.10, 400, 160, 0.08, boot=False),
              "tag:other": row(1.0, 80, 50, 0.2, boot=False), "liquidity:low tercile": row(1.0, 333, 150, 0.1, boot=False)}
    return {
        "run_at_utc": "2027-01-22T09:00:00Z", "code_commit": "abc1234", "headline_verdict": "not supported", "low_power_label": False,
        "verdicts": {"C1": "not supported; h = 24 h; floor 10,000 USDC and spread <= 0.10 at the horizon; Sports share 0.400 of the scored sample; n = 1000, G = 400"},
        "trials": {"C1": {"rows": {"W": row(b)}, "reliability": reliability(), "splits": splits},
                   "C1a": {"rows": {"W": row(1.04, 600, 240)}}, "C1b": {"rows": {"W": row(1.11, 700, 300)}}},
    }


def test_two_charts_pass_the_house_check_and_the_manifest_records_the_titles(tmp_path: Path):
    mod = load_module()
    score_dir = tmp_path / "score"
    score_dir.mkdir()
    (score_dir / "summary.json").write_text(json.dumps(summary()), encoding="utf-8")
    out = tmp_path / "charts"
    written = mod.draw_if_scored(score_dir, out)
    names = sorted(p.name for p in written)
    assert names == ["manifest.json", "reliability_c1.png", "reliability_c1.svg", "slopes.png", "slopes.svg"]
    assert all(p.is_file() and p.stat().st_size > 0 for p in written)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["titles"]["reliability_c1"]["b"] == 1.07 and "1.07" in manifest["titles"]["reliability_c1"]["title"]
    assert "not supported" in manifest["titles"]["reliability_c1"]["title"]
    # the slope chart lists the three trials, the tag families and the early split; the liquidity split is not on it
    assert manifest["titles"]["slopes"]["rows"] == 3 + 3 + 2
    svg = (out / "slopes.svg").read_text(encoding="utf-8")
    assert "C1a: without Sports" in svg and "liquidity" not in svg
    assert len(manifest["input"]["summary.json"]) == 64


def test_no_fit_and_a_missing_bootstrap_still_draw(tmp_path: Path):
    mod = load_module()
    s = summary()
    w = s["trials"]["C1"]["rows"]["W"]
    w.update({"converged": False, "a": math.nan, "b": math.nan, "t_cl": math.nan, "wald_low": math.nan, "wald_high": math.nan})
    w["bootstrap"]["available"] = False
    s["headline_verdict"] = "not supported"
    score_dir = tmp_path / "score"
    score_dir.mkdir()
    (score_dir / "summary.json").write_text(json.dumps(s), encoding="utf-8")
    written = mod.draw_if_scored(score_dir, tmp_path / "charts")
    assert len(written) == 5
    manifest = json.loads((tmp_path / "charts" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["titles"]["reliability_c1"]["title"].startswith("No slope could be fitted")


def test_before_the_scoring_run_nothing_is_drawn(tmp_path: Path, capsys):
    mod = load_module()
    assert mod.draw_if_scored(tmp_path / "score", tmp_path / "charts") == []
    assert "nothing to draw" in capsys.readouterr().out
    assert not (tmp_path / "charts").exists()
