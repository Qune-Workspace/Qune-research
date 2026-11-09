"""Discipline rules on the committed prediction files, adopted 2026-10-30 after the
V1 miss (predictions/POST_MORTEMS.md).  They apply to calls made on or after that
date; the five calls of 2026-10-23 are exempt and the exemption is stated here
because their baselines were computed two days after the calls (disclosed in
predictions/README.md).

Rules checked:
1. Baseline before confidence: every call has a baselines.csv row computed on or
   before the day the call was made, so the desk knew the market's number when it
   wrote its own.
2. A departure needs a reason: when the desk's confidence is more than 0.20 from the
   baseline probability, the basis names the baseline and what the market is missing
   (the word 'baseline' must appear in the basis).
3. Confidence is a probability in (0, 1), written with two decimals, so that it can be
   Brier-scored.  Since 2026-11-09 this is one sentence of ``score.row_shape_violations``,
   the gate that holds every column of a row against its test kind (test_ledger_shape.py);
   the test below applies that gate to the committed file instead of a copy of the rule.
"""
import csv
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PRED = HERE.parent.parent / "predictions"
sys.path.insert(0, str(PRED))

import score  # noqa: E402

RULES_FROM = "2026-10-30"
DEPARTURE = 0.20


def read(name: str) -> list[dict]:
    path = PRED / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def governed_calls() -> list[dict]:
    return [r for r in read("ledger.csv") if r["made_on"] >= RULES_FROM]


def baselines_by_id() -> dict[str, dict]:
    return {r["id"]: r for r in read("baselines.csv")}


def test_every_governed_call_has_a_baseline_computed_before_or_on_the_day_it_was_made():
    baselines = baselines_by_id()
    for call in governed_calls():
        assert call["id"] in baselines, f"{call['id']}: no baseline row; run baseline.py before writing the confidence"
        computed_on = baselines[call["id"]]["computed_on"]
        assert computed_on <= call["made_on"], (
            f"{call['id']}: baseline computed on {computed_on}, after the call was made on {call['made_on']}")


def test_a_departure_from_the_baseline_names_the_baseline_in_the_basis():
    baselines = baselines_by_id()
    for call in governed_calls():
        if call["id"] not in baselines:
            continue  # the first test reports this
        gap = abs(float(call["confidence"]) - float(baselines[call["id"]]["baseline_probability"]))
        if gap > DEPARTURE:
            assert "baseline" in call["basis"].lower(), (
                f"{call['id']}: confidence is {gap:.2f} from the baseline; the basis must say what the market is missing")


def test_every_committed_row_meets_the_shape_gate_confidence_included():
    for call in read("ledger.csv"):
        assert score.row_shape_violations(call) == [], call["id"]


def test_exempt_calls_are_exactly_the_five_of_2026_10_23():
    exempt = [r["id"] for r in read("ledger.csv") if r["made_on"] < RULES_FROM]
    assert exempt == [f"V{i}-2026-10-23" for i in range(1, 6)]


@pytest.mark.parametrize("name", ["ledger.csv", "baselines.csv"])
def test_ids_are_unique(name: str):
    ids = [r["id"] for r in read(name)]
    assert len(ids) == len(set(ids)), f"{name}: duplicate id"
