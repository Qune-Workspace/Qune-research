"""The desk view's Brier line against the record (predictions/POST_MORTEMS.md, "A Brier
figure rounded twice", 2026-11-11).  The 6 November view printed "baseline 0.046",
rounded by hand from SKILL.md's 0.0455, where the record's 0.04549689 is 0.045 at
three decimals; nothing read the line back.  These tests hold the clause renderer,
the gate on constructed lines, and the committed page against the committed records
through their gates."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "predictions"))

import baseline as bl  # noqa: E402

VIEW = HERE.parent / "DESK_VIEW.md"
SUMMARY = {"scored_with_baseline": 1, "hits": 0, "brier_desk": 0.49,
           "brier_baseline": 0.04549689, "skill_vs_baseline": -0.44450311}
LEAD = bl.VIEW_BRIER_LEAD
CLEAN = f"{LEAD} (SKILL.md): 1 scored call; desk 0.490, baseline 0.045, skill −0.445; descriptive."


def test_the_clause_is_rendered_from_the_unrounded_figures_not_from_skill_md_text():
    # SKILL.md prints 0.0455; a round of that text gives 0.046, the record gives 0.045.
    assert bl.view_brier_clause(SUMMARY) == "1 scored call; desk 0.490, baseline 0.045, skill −0.445"
    assert bl.view_brier_clause(SUMMARY, decimals=4) == "1 scored call; desk 0.4900, baseline 0.0455, skill −0.4445"
    assert bl.view_brier_clause({**SUMMARY, "scored_with_baseline": 2}).startswith("2 scored calls;")
    assert bl.view_brier_clause({"scored_with_baseline": 0}) == "no scored call with a baseline yet"


def test_the_6_november_line_is_refused_by_name_and_the_record_line_admitted():
    published = CLEAN.replace("baseline 0.045", "baseline 0.046")
    (only,) = bl.view_brier_violations(published, SUMMARY)
    assert only.startswith("baseline: the view prints 0.046") and "0.045 at 3 decimals" in only
    assert bl.view_brier_violations(CLEAN, SUMMARY) == []
    assert bl.view_brier_violations(CLEAN.replace("−", "-"), SUMMARY) == []


@pytest.mark.parametrize("alteration, names", [
    (lambda t: t.replace("1 scored call", "2 scored calls"), ["count: the view prints 2"]),
    (lambda t: t.replace("0.490", "0.489"), ["desk: the view prints 0.489"]),
    (lambda t: t.replace("−0.445", "−0.444"), ["skill: the view prints −0.444"]),
    (lambda t: t.replace("−0.445", "0.445"), ["skill: the view prints 0.445"]),
    (lambda t: t.replace("0.490", "0.49"), ["decimals: the three figures"]),
    (lambda t: t.replace("1 scored call; ", ""), ["does not carry"]),
    (lambda t: t.replace(LEAD, "Brier"), ["carries no line"]),
    (lambda t: t + "\n" + t, ["2 lines"]),
])
def test_each_alteration_of_the_line_is_refused_by_name(alteration, names):
    got = bl.view_brier_violations(alteration(CLEAN), SUMMARY)
    assert len(got) == len(names)
    for name in names:
        assert any(name in g for g in got), got


def test_two_decimals_throughout_are_held_to_the_record_at_two_decimals():
    two = CLEAN.replace("0.490", "0.49").replace("0.045", "0.05").replace("−0.445", "−0.44")
    assert bl.view_brier_violations(two, SUMMARY) == []
    assert bl.view_brier_violations(two.replace("0.05", "0.04"), SUMMARY) == ["baseline: the view prints 0.04, the record's 0.04549689 is 0.05 at 2 decimals"]


def test_a_view_with_no_scored_call_carries_no_figure():
    assert bl.view_brier_violations("no Brier line at all", {"scored_with_baseline": 0}) == []
    assert bl.view_brier_violations(f"{LEAD}: no scored call with a baseline yet.", {"scored_with_baseline": 0}) == []
    (only,) = bl.view_brier_violations(CLEAN, {"scored_with_baseline": 0})
    assert "record has no scored call" in only


def test_the_committed_view_carries_the_committed_records_brier_line():
    summary = bl.record_summary()
    assert summary["scored_with_baseline"] >= 1  # V1 was scored on 2026-10-29
    assert bl.view_brier_violations(VIEW.read_text(encoding="utf-8"), summary) == []
