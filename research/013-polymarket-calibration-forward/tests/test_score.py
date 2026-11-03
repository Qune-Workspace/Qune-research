"""Tests of the Study 013 scoring run (PREREGISTRATION.md §6.6), on a synthetic study folder built under tmp_path.

No network and no real file: the sample, the fetch's two files, the manifests, the approval, the programme
count and the trial log are all written here, in the shape the earlier steps write them. The checks §6.6
names for this step: the scoring run refusing without `APPROVED` and refusing to run twice; plus every other
refusal in order, the outcome rule applied per kind, the recovered slope on a known model, the verdict
sentences, the low-power label, the multiplicity bars, the pooling of small tag families, and that no output
holds a per-market row.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from src import fit, outcome, score
from src.data_step import Refusal

UTC = dt.UTC
STUDY_DIR = Path(__file__).resolve().parents[1]
NOW = dt.datetime(2027, 1, 22, 9, 0, tzinfo=UTC)
RESAMPLES = 40  # lowered for the tests only; the command line never changes the §9.3 count


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class World:
    """A study folder: sample, the fetch's two files with their provenance line, manifests, approval, count, log."""

    def __init__(self, root: Path, n: int = 3000, clusters: int = 1000, b_true: float = 1.15, a_true: float = 0.0,
                 seed: int = 7, ratio_c1: float = 0.30):
        self.root = root
        self.results = root / "results"
        self.res = root / "data" / "raw" / "resolution"
        self.paper = root / "paper-log"
        for d in (self.results, self.res, self.paper):
            d.mkdir(parents=True, exist_ok=True)
        rng = np.random.default_rng(seed)
        p = rng.uniform(0.03, 0.97, size=n)
        x = fit.logit(p)
        y = (rng.uniform(size=n) < 1.0 / (1.0 + np.exp(-(a_true + b_true * x)))).astype(int)
        vol = rng.uniform(10_000.0, 1_000_000.0, size=n)
        fam = ["Politics", "Crypto", "Politics", "Crypto"]  # about 1,000 each; every 50th non-Sports market is a small family, pooled
        self.n, self.y = n, y
        sample_rows: list[dict] = []
        status_lines: list[str] = []
        outcome_lines: list[str] = []
        for i in range(n):
            tok = [f"tok-{i}-a", f"tok-{i}-b"]
            sports = i % 3 == 0
            base = {
                "market": str(i), "cluster": str(5000 + i % clusters), "price": float(p[i]), "snapshot": "2026-11-20",
                "realised_horizon_hours": 24.0 + float(rng.uniform(0, 40)), "early": i % 5 == 0,
                "half": "W1" if i % 2 else "W2", "sports": sports, "first_label_yes": i % 7 != 0,
                "volume_at_horizon": float(vol[i]),
                "tag_family": "Sports" if sports else ("Culture" if i % 50 == 1 else fam[(i // 3) % 4]), "first_token": tok[0],
            }
            sample_rows.append({"trial": "C1", **base})
            if not sports:
                sample_rows.append({"trial": "C1a", **base})
            if i % 10 < 7:
                sample_rows.append({"trial": "C1b", **base, "realised_horizon_hours": 168.0 + float(rng.uniform(0, 40))})
            # the excluded kinds of §6.5, five or ten markets each, then the resolved rest
            if 20 <= i < 23:
                status_lines.append(json.dumps({"id": str(i), "conditionId": "0x0", "fetch_failed": True, "reason": "request"}))
                continue
            if 23 <= i < 25:
                continue  # missing from both files
            uma = "proposed" if i < 10 else "resolved"
            status_lines.append(json.dumps({"id": str(i), "conditionId": f"0x{i:x}", "closedTime": "2026-11-21T12:00:00Z", "closed": True,
                                            "umaResolutionStatus": uma, "endDate": "2026-12-31T12:00:00Z", "volumeNum": float(vol[i]),
                                            "eventIds": [str(5000 + i % clusters)], "tagLabels": ["Sports"] if sports else [],
                                            "outcomeLabels": '["Yes", "No"]', "clobTokenIds": json.dumps(tok), "fetch_failed": False}))
            won = bool(y[i])
            if 10 <= i < 15:
                prices = ["0.5", "0.5"]
            else:
                prices = ["1", "0"] if won else ["0", "1"]
            w_first, w_other = (won, not won) if not (15 <= i < 20) else (not won, won)  # 15-19: flags disagree with the prices
            outcome_lines.append(json.dumps({"id": str(i), "outcomePrices": json.dumps(prices),
                                             "tokens": [{"token_id": tok[0], "winner": w_first}, {"token_id": tok[1], "winner": w_other}]}))
        self.sample = self.results / "sample.jsonl"
        self.sample.write_text("".join(json.dumps(r) + "\n" for r in sample_rows), encoding="utf-8")
        self.status = self.res / "status.jsonl"
        self.outcome = self.res / "outcome.jsonl"
        self.status.write_text("\n".join(status_lines) + "\n", encoding="utf-8")
        self.outcome.write_text("\n".join(outcome_lines) + "\n", encoding="utf-8")
        self.manifest = self.results / "data_manifest.json"
        self.manifest.write_text(json.dumps({"sample_jsonl_sha256": sha(self.sample), "status_jsonl_sha256": sha(self.status)}), encoding="utf-8")
        self.fetch_log = self.paper / "resolution_fetch.csv"
        with open(self.fetch_log, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["started_utc", "finished_utc", "candidates", "fetched", "failed", "status_sha256", "outcome_sha256", "manifest_sha256"], lineterminator="\n")
            w.writeheader()
            w.writerow({"started_utc": "2027-01-20T00:10:00Z", "finished_utc": "2027-01-20T03:00:00Z", "candidates": n, "fetched": n - 5,
                        "failed": 3, "status_sha256": sha(self.status), "outcome_sha256": sha(self.outcome), "manifest_sha256": "c" * 64})
        self.data_step = self.results / "data_step.json"
        self.set_data_step(ratio_c1=ratio_c1)
        self.count = self.results / "programme_count.json"
        self.count.write_text(json.dumps({"public_trials_md": 40, "with_desk_registry": 70, "method": "counted as written"}), encoding="utf-8")
        self.trials_md = root / "trials.md"
        self.trials_md.write_text("| Step | Date | Outcome |\n|---|---|---|\n" + score.SCORING_ROW + " | 2027-01-22 | logged before the run |\n", encoding="utf-8")
        self.approved = root / "APPROVED"
        self.approved.write_text("approved by the orchestrator under the owner's delegation of 2026-10-21, 2026-11-xx\n", encoding="utf-8")
        self.out = self.results / "score"

    def set_data_step(self, *, ratio_c1: float = 0.30, halted: bool = False, stopped: bool = False, amendment: str | None = None) -> None:
        self.data_step.write_text(json.dumps({"run_at_utc": "2027-01-21T10:00:00Z", "halted": halted, "stopped_for_amendment": stopped,
                                              "amendment": amendment, "trials": {"C1": {"power": {"ratio": ratio_c1}}}}), encoding="utf-8")

    def run(self, **over) -> dict:
        kw = dict(approved=self.approved, trials_md=self.trials_md, data_step_json=self.data_step, data_manifest_json=self.manifest,
                  sample_jsonl=self.sample, programme_count_json=self.count, status_jsonl=self.status, outcome_jsonl=self.outcome,
                  fetch_log_csv=self.fetch_log, out_dir=self.out, now=NOW, resamples=RESAMPLES)
        kw.update(over)
        return score.run_score(**kw)


def test_end_to_end_counts_slope_outputs_and_no_per_market_row(tmp_path: Path):
    w = World(tmp_path)
    s = w.run()
    c1 = s["trials"]["C1"]
    # the outcome rule by kind, in the order of §6.5: 10 not resolved, 5 not binary, 5 disagreeing, 5 unfetched (3 failed, 2 missing)
    assert c1["sampled"] == w.n and c1["scored"] == w.n - 25
    assert c1["excluded_at_scoring"] == {outcome.NOT_RESOLVED: 10, outcome.NOT_BINARY_SETTLEMENT: 5, outcome.DISAGREEMENT: 5, outcome.UNFETCHED: 5}
    # the slope recovers the model it was drawn from (b = 1.15; SE about 0.04)
    wrow = c1["rows"]["W"]
    assert wrow["converged"] and wrow["b"] == pytest.approx(1.15, abs=0.15)
    assert wrow["G"] == 1000 and wrow["n"] == w.n - 25 and np.isfinite(wrow["se_cl"]) and np.isfinite(wrow["se_ordinary"])
    assert wrow["bootstrap"]["resamples"] == RESAMPLES and wrow["bootstrap"]["low"] <= wrow["b"] <= wrow["bootstrap"]["high"]
    assert c1["rows"]["W1"]["n"] + c1["rows"]["W2"]["n"] == wrow["n"]
    # C1a holds no Sports market; C1b is the 168 h subset
    assert s["trials"]["C1a"]["sports_share"] == 0.0 and s["trials"]["C1a"]["sampled"] == sum(1 for i in range(w.n) if i % 3)
    assert s["trials"]["C1b"]["sampled"] == sum(1 for i in range(w.n) if i % 10 < 7)
    # reliability: ten bins, every scored market in one of them; scores present
    assert len(c1["reliability"]) == 10 and sum(int(b["n"]) for b in c1["reliability"]) == wrow["n"]
    assert 0 < c1["scores"]["brier"] < 0.25 and "brier_skill" in c1["scores"]
    # the splits listed in §9.6, each with a clustered Wald interval
    keys = set(c1["splits"])
    assert {"early", "not early", "liquidity:low tercile", "liquidity:middle tercile", "liquidity:high tercile",
            "horizon:below median", "horizon:at or above median"} <= keys
    # the small "Culture" family (about 40 markets) is pooled into "other" (§9.6: fewer than 500)
    assert {k for k in keys if k.startswith("tag:")} == {"tag:Crypto", "tag:Politics", "tag:Sports", "tag:other"}
    assert 0 < c1["splits"]["tag:other"]["n"] < score.MIN_FAMILY
    assert c1["splits"]["early"]["n"] + c1["splits"]["not early"]["n"] == wrow["n"]
    assert c1["splits"]["early"]["wald_low"] < c1["splits"]["early"]["b"] < c1["splits"]["early"]["wald_high"]
    # verdict sentences carry the horizon, the floor and the Sports share (§9.5); the bars of §9.4
    for name, v in s["verdicts"].items():
        assert f"h = {s['trials'][name]['horizon_hours']} h" in v and "floor 10,000 USDC" in v and "Sports share" in v
    assert "b-hat(168 h) > b-hat(24 h)" in s["verdicts"]["C1b"]
    assert s["multiplicity_bars"]["C1"]["N=3 (decides C3; the pre-registered 2.128)"]["z"] == fit.C3_T  # one C3 bar
    assert s["multiplicity_bars"]["C1"]["N=12 (one per study)"]["z"] == pytest.approx(2.638, abs=5e-4)
    assert "N=40 (public trials.md rows)" in s["multiplicity_bars"]["C1"] and "N=70 (with the desk registry)" in s["multiplicity_bars"]["C1"]
    assert not s["low_power_label"]
    # the four outputs, aggregates only: no token id and no per-market line count anywhere
    names = {p.name for p in w.out.iterdir()}
    # started.txt is written before the outcome file is opened, so a crashed run leaves a trace (review should-fix 7)
    assert names == {"started.txt", "summary.json", "verdict.md", "slopes.csv", "reliability.csv"}
    assert (w.out / "started.txt").read_text(encoding="utf-8").startswith("scoring run started 2027-01-22")
    for p in w.out.iterdir():
        text = p.read_text(encoding="utf-8")
        assert "tok-" not in text and len(text.splitlines()) < w.n  # aggregates: never a line per market
    with open(w.out / "slopes.csv", newline="", encoding="utf-8") as f:
        slopes = list(csv.DictReader(f))
    assert {(r["trial"], r["row"]) for r in slopes} >= {("C1", "W"), ("C1", "W1"), ("C1", "W2"), ("C1a", "W"), ("C1b", "W"), ("C1", "early")}
    with open(w.out / "reliability.csv", newline="", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 30
    md = (w.out / "verdict.md").read_text(encoding="utf-8")
    assert "| C1 |" in md and "Excluded at scoring" in md and s["headline_verdict"] in md
    assert s["inputs_sha256"]["outcome_jsonl"] == sha(w.outcome)


def test_a_strong_slope_is_supported_in_one_forward_window_with_the_window_dates(tmp_path: Path):
    w = World(tmp_path, b_true=1.4, seed=11)
    s = w.run()
    assert s["headline_verdict"] == "supported in one forward window"
    assert s["verdicts"]["C1"].startswith("supported in one forward window (" + score.WINDOW_TEXT + ")")
    assert s["trials"]["C1"]["criteria"]["all"] and s["verdicts"]["C1a"].startswith("meets C1–C4")


def test_a_calibrated_market_is_not_supported_and_the_low_power_label_is_read_from_the_data_step(tmp_path: Path):
    w = World(tmp_path, b_true=1.0, seed=3, ratio_c1=0.62)
    s = w.run()
    c1 = s["trials"]["C1"]
    assert c1["rows"]["W"]["b"] == pytest.approx(1.0, abs=0.15)
    # with b near 1 the C1 margin (0.02) or the t bar fails; the verdict follows the criteria dict, never a typed string
    assert s["headline_verdict"] == fit.headline_verdict(c1["criteria"]["all"], c1["rows"]["W"]["converged"],
                                                         not s["trials"]["C1a"]["criteria"]["all"], False)
    assert s["low_power_label"] and all(v.endswith(score.LOW_POWER_LABEL) or score.LOW_POWER_LABEL in v for v in s["verdicts"].values())


def test_refusals_in_order_and_nothing_written(tmp_path: Path):
    w = World(tmp_path, n=300, clusters=100)
    w.approved.write_text("", encoding="utf-8")
    with pytest.raises(Refusal, match="APPROVED"):
        w.run()
    w.approved.write_text("approved\n", encoding="utf-8")
    w.out.mkdir()
    with pytest.raises(Refusal, match="once"):
        w.run()
    w.out.rmdir()
    w.data_step.unlink()
    with pytest.raises(Refusal, match="data step has not run"):
        w.run()
    w.set_data_step(halted=True)
    with pytest.raises(Refusal, match="halted"):
        w.run()
    w.set_data_step(stopped=True)
    with pytest.raises(Refusal, match="amendment"):
        w.run()
    w.set_data_step(stopped=True, amendment="§16 2026-12-xx")  # a re-run after the amendment: allowed
    count_text = w.count.read_text(encoding="utf-8")
    w.count.unlink()
    with pytest.raises(Refusal, match="programme_count"):
        w.run()
    w.count.write_text(json.dumps({"public_trials_md": 1, "with_desk_registry": 70, "method": "x"}), encoding="utf-8")
    with pytest.raises(Refusal, match="integer >= 2"):
        w.run()
    w.count.write_text(json.dumps({"public_trials_md": 40, "with_desk_registry": 70}), encoding="utf-8")
    with pytest.raises(Refusal, match="method"):
        w.run()
    w.count.write_text(count_text, encoding="utf-8")
    log_text = w.trials_md.read_text(encoding="utf-8")
    w.trials_md.write_text("| Step |\n", encoding="utf-8")
    with pytest.raises(Refusal, match="scoring-run row"):
        w.run()
    w.trials_md.write_text(log_text, encoding="utf-8")
    # an edited input: the sample, then the outcome file, then the status file
    with open(w.sample, "a", encoding="utf-8") as f:
        f.write(json.dumps({"trial": "C1", "market": "x"}) + "\n")
    with pytest.raises(Refusal, match="sample.jsonl"):
        w.run()
    sample_lines = w.sample.read_text(encoding="utf-8").splitlines()
    w.sample.write_text("\n".join(sample_lines[:-1]) + "\n", encoding="utf-8")
    outcome_text = w.outcome.read_text(encoding="utf-8")
    w.outcome.write_text(outcome_text + '{"id": "zzz"}\n', encoding="utf-8")
    with pytest.raises(Refusal, match="outcome.jsonl"):
        w.run()
    w.outcome.write_text(outcome_text, encoding="utf-8")
    status_text = w.status.read_text(encoding="utf-8")
    w.status.write_text(status_text + '{"id": "zzz"}\n', encoding="utf-8")
    with pytest.raises(Refusal, match="status.jsonl"):
        w.run()
    w.status.write_text(status_text, encoding="utf-8")
    assert not w.out.exists()
    s = w.run()  # everything restored: the run proceeds, and a second run refuses
    assert s["trials"]["C1"]["scored"] == 300 - 25
    with pytest.raises(Refusal, match="once"):
        w.run()


def test_small_tag_families_pool_into_other():
    rows = [{"tag_family": "Sports"} for _ in range(600)] + [{"tag_family": "Crypto"} for _ in range(20)] + [{"tag_family": "other"} for _ in range(5)]
    groups = score.tag_family_groups(rows)
    assert list(groups) == ["Sports", "other"] and len(groups["other"]) == 25


def test_fit_subset_on_one_outcome_only_on_a_small_cell_and_on_nothing():
    assert score.fit_subset([])["n"] == 0
    r = score.fit_subset([{"price": 0.3 + 0.02 * i, "y": 1, "cluster": str(i)} for i in range(12)])
    assert r["n"] == 12 and r.get("one_outcome_only") and not r["converged"] and not np.isfinite(r["b"])
    # a cell below MIN_CELL reports its count only (code review of 2026-11-03: a cell of two is a per-market row)
    s = score.fit_subset([{"price": 0.3, "y": 1, "cluster": "a"}, {"price": 0.6, "y": 0, "cluster": "b"}])
    assert s["n"] == 2 and s.get("suppressed") and not s.get("one_outcome_only") and not np.isfinite(s["b"])


def test_bonferroni_bars():
    assert score.bonferroni_bar(3) == pytest.approx(2.128, abs=5e-4)
    assert score.bonferroni_bar(12) == pytest.approx(2.638, abs=5e-4)
    assert score.bonferroni_bar(1) == pytest.approx(1.645, abs=5e-4)


def test_only_the_scoring_module_names_the_outcome_file():
    src = STUDY_DIR / "src"
    assert "outcome.jsonl" in (src / "score.py").read_text(encoding="utf-8")
    for name in ("data_step.py", "snapshots.py", "fit.py", "outcome.py"):
        assert "outcome.jsonl" not in (src / name).read_text(encoding="utf-8"), name


def test_main_refuses_on_an_empty_study_folder_and_writes_nothing(tmp_path: Path, capsys):
    assert score.main(["--study-dir", str(tmp_path)]) == 1
    assert "refused: no APPROVED" in capsys.readouterr().out
    assert not (tmp_path / "results").exists()


def test_programme_count_reads_this_study_and_the_programme(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("programme_count_013", STUDY_DIR / "programme_count.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.registered_rows(STUDY_DIR / "trials.md") == ["C1", "C1a", "C1b"]
    public = mod.count_public()
    assert public["013-polymarket-calibration-forward"] == ["C1", "C1a", "C1b"] and len(public) >= 10
    reg = tmp_path / "trials.jsonl"
    reg.write_text('{"id": "TRD-1", "family": "polymarket calibration"}\n{"id": "TRD-2", "corrects": "TRD-1"}\n', encoding="utf-8")
    desk = mod.count_desk(reg)
    assert desk == {"rows": 2, "correction_rows": 1, "family_keyword_hits": 1}
    out = mod.build(public, desk)
    assert out["with_desk_registry"] == out["public_trials_md"] + 2 and "N = 3" in out["method"]
    score.check_programme_count(out)
