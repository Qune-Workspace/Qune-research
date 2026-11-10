"""The two tool-written records of the rates desk, ``outcomes.csv`` and ``baselines.csv``,
are held against the ledger row they score or price (predictions/score.py and
predictions/baseline.py, rule added 2026-11-10 after "A result spelled another way was a
miss" in predictions/POST_MORTEMS.md).  The readers (``read_outcomes``, ``read_baselines``),
the writers (``append_outcome``, ``append_baseline``) and this suite apply one list of
sentences per record.  The column searches below alter each column of a clean row in turn
and ask the gate once; a new column fails the search until it is classified here."""
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
PRED = HERE.parent.parent / "predictions"
sys.path.insert(0, str(PRED))

import baseline  # noqa: E402
import score  # noqa: E402

HASH = "ab" * 32
CALL = {"id": "T2-2026-11-09", "made_on": "2026-11-09", "series": "DGS10",
        "statement": "The 10-year yield on 2026-12-31 is between 4.60% and 5.30%.", "test": "between_on_due",
        "threshold_low": "4.60", "threshold_high": "5.30", "due_on": "2026-12-31", "confidence": "0.65",
        "basis": "a stated reason"}
OUTCOME = {"id": "T2-2026-11-09", "scored_on": "2026-12-31", "observed_on": "2026-12-31", "observed_value": "4.9",
           "result": "hit", "note": "value on the due date", "raw_sha256": HASH}
BASELINE = {"id": "T2-2026-11-09", "computed_on": "2026-11-09", "asof": "2026-11-06", "method": "forward_normal",
            "baseline_probability": "0.6580", "desk_confidence": "0.65", "inputs": '{"h_business_days": 38}',
            "note": "forward centre; realised width", "raw_sha256": f"{HASH};{HASH}"}

# One bad value per column, and the word the refusal must carry.  Every column of each
# record appears here: the search is the checklist.
OUTCOME_ALTERED = {
    "id": ("T9-2026-11-09", "not a call in the ledger"),
    "scored_on": ("2026-12-30", "scored_on"),          # before due_on
    "observed_on": ("31/12/2026", "observed_on"),
    "observed_value": ("n/a", "observed_value"),
    "result": ("Hit", "result"),
    "note": ("", "note"),
    "raw_sha256": ("x", "raw_sha256"),
}
BASELINE_ALTERED = {
    "id": ("", "id"),
    "computed_on": ("2026-11-05", "computed_on"),      # before asof
    "asof": ("2026-11-10", "asof"),                     # after made_on
    "method": ("forward_normal_barrier", "method"),     # not the frozen method for DGS10 between_on_due
    "baseline_probability": ("1.5000", "baseline_probability"),
    "desk_confidence": ("0.90", "desk_confidence"),     # not the ledger's 0.65
    "inputs": ("[]", "inputs"),
    "note": ("  ", "note"),
    "raw_sha256": (f"{HASH};", "raw_sha256"),
}


def ledger(**kw) -> pd.DataFrame:
    return pd.DataFrame([{**CALL, **kw}])


def outcome(**kw) -> dict:
    return {**OUTCOME, **kw}


def baseline_row(**kw) -> dict:
    return {**BASELINE, **kw}


def test_the_clean_rows_pass_their_gates():
    assert score.outcome_row_violations(outcome(), CALL) == []
    assert baseline.baseline_row_violations(baseline_row(), CALL) == []
    score.validate_outcomes(pd.DataFrame([outcome()]), ledger())
    baseline.validate_baselines(pd.DataFrame([baseline_row()]), ledger())


def test_every_outcome_column_is_held_and_names_itself():
    assert set(OUTCOME_ALTERED) == set(score.OUTCOME_COLUMNS), "classify the new column in OUTCOME_ALTERED"
    calls = score.ledger_rows_by_id(ledger())
    for col, (bad, word) in OUTCOME_ALTERED.items():
        row = outcome(**{col: bad})
        problems = score.outcome_row_violations(row, calls.get(row["id"]))
        assert problems, f"{col} altered to {bad!r} was admitted"
        assert any(word in p for p in problems), f"{col}: refusal does not name the column: {problems}"
        with pytest.raises(ValueError, match=re.escape(word)):
            score.validate_outcomes(pd.DataFrame([row]), ledger())


def test_every_baseline_column_is_held_and_names_itself():
    assert set(BASELINE_ALTERED) == set(baseline.BASELINE_COLUMNS), "classify the new column in BASELINE_ALTERED"
    calls = score.ledger_rows_by_id(ledger())
    for col, (bad, word) in BASELINE_ALTERED.items():
        row = baseline_row(**{col: bad})
        problems = baseline.baseline_row_violations(row, calls.get(row["id"]))
        assert problems, f"{col} altered to {bad!r} was admitted"
        assert any(word in p for p in problems), f"{col}: refusal does not name the column: {problems}"
        with pytest.raises(ValueError, match=re.escape(word)):
            baseline.validate_baselines(pd.DataFrame([row]), ledger())


def test_an_outcome_is_held_against_its_call_not_its_types_alone():
    # Each of these is a well-typed row; only the ledger row says it is wrong.
    assert any("before due_on" in p for p in score.outcome_row_violations(outcome(scored_on="2026-12-30"), CALL))
    assert any("after due_on" in p for p in
               score.outcome_row_violations(outcome(observed_on="2027-01-04", scored_on="2027-01-04"), CALL))
    assert any("before the call was made" in p for p in
               score.outcome_row_violations(outcome(observed_on="2026-11-08"), CALL))
    assert any("is before observed_on" in p for p in
               score.outcome_row_violations(outcome(observed_on="2027-01-02", scored_on="2027-01-01"), CALL))
    assert any("not a call in the ledger" in p for p in score.outcome_row_violations(outcome(), None))
    # the day's print was empty: the last valid observation before the due date is named and passes
    assert score.outcome_row_violations(outcome(observed_on="2026-12-30", note="last observation before the due date (2026-12-30)"), CALL) == []
    # the id written another way than the ledger writes it (a trailing space) is refused by name
    assert any("not a call in the ledger" in p for p in
               score.outcome_row_violations(outcome(id="T2-2026-11-09 "), score.ledger_rows_by_id(ledger()).get("T2-2026-11-09 ")))


def test_a_baseline_is_held_against_its_call_not_its_types_alone():
    assert any("not the ledger's confidence" in p for p in baseline.baseline_row_violations(baseline_row(), {**CALL, "confidence": "0.70"}))
    assert any("after the call was made" in p for p in baseline.baseline_row_violations(baseline_row(asof="2026-11-10", computed_on="2026-11-10"), CALL))
    assert any("not the frozen method" in p for p in
               baseline.baseline_row_violations(baseline_row(method="persistence_base_rate"), CALL))
    assert any("not a call in the ledger" in p for p in baseline.baseline_row_violations(baseline_row(), None))
    assert baseline.baseline_row_violations(baseline_row(baseline_probability="1.0000"), CALL) == []  # closed interval
    assert baseline.baseline_row_violations(baseline_row(baseline_probability="0.0000"), CALL) == []
    assert any("4 decimals" in p for p in baseline.baseline_row_violations(baseline_row(baseline_probability="0.658"), CALL))


@pytest.mark.parametrize("series,test,method", [
    ("DFEDTARU", "eq_on_due", "bill_implied_hike"),
    ("DGS10", "between_on_due", "forward_normal"),
    ("T10Y2Y", "below_on_due", "forward_normal"),
    ("T10YIE", "within_every_day_until_due", "forward_normal_barrier"),
    ("SBCORR63", "above_on_due", "persistence_base_rate"),
])
def test_expected_method_is_the_one_compute_baseline_names(series, test, method):
    assert baseline.expected_method(series, test) == method
    assert method in baseline.METHODS


def test_methods_are_exactly_those_compute_baseline_can_return():
    source = (PRED / "baseline.py").read_text(encoding="utf-8")
    body = source[source.index("def compute_baseline"):source.index("# --- files")]
    assert set(re.findall(r'"method": "(\w+)"', body)) == set(baseline.METHODS)
    for series, test in [("DFEDTARU", "between_on_due"), ("SBCORR63", "eq_on_due"), ("NOSUCH", "eq_on_due")]:
        with pytest.raises(ValueError):
            baseline.expected_method(series, test)


def test_repeated_and_stray_ids_are_refused_by_name():
    with pytest.raises(ValueError, match="repeated id"):
        score.validate_outcomes(pd.DataFrame([outcome(), outcome(result="miss")]), ledger())
    with pytest.raises(ValueError, match="repeated id"):
        baseline.validate_baselines(pd.DataFrame([baseline_row(), baseline_row()]), ledger())
    led = ledger()
    with pytest.raises(ValueError, match="outcomes: id not in the ledger"):
        baseline.skill_table(led, pd.DataFrame([baseline_row()]), pd.DataFrame([outcome(id="T2-2026-11-09 ")]))
    with pytest.raises(ValueError, match="baselines: repeated id"):
        baseline.skill_table(led, pd.DataFrame([baseline_row(), baseline_row()]), pd.DataFrame([outcome()]))


def test_skill_summary_refuses_what_it_used_to_count_as_a_miss():
    # Before 2026-11-10 'Hit' and 'pending' each counted as a scored miss (observed on 3ce9276 with a scratch
    # script: Brier desk 0.49 either way); a baseline probability of 1.5 gave a Brier of 2.25 in silence.
    led = ledger()
    base = pd.DataFrame([baseline_row()])
    table = baseline.skill_table(led, base, pd.DataFrame([outcome()]))
    assert baseline.skill_summary(table)["hits"] == 1
    for word in ("Hit", "pending", "HIT", "miss "):
        with pytest.raises(ValueError, match="not hit or miss"):
            baseline.skill_summary(baseline.skill_table(led, base, pd.DataFrame([outcome(result=word)])))
    bad_base = pd.DataFrame([baseline_row(baseline_probability="1.5000")])
    with pytest.raises(ValueError, match="baseline_probability outside"):
        baseline.skill_summary(baseline.skill_table(led, bad_base, pd.DataFrame([outcome()])))
    empty = baseline.skill_table(led, base, pd.DataFrame(columns=score.OUTCOME_COLUMNS))
    assert baseline.skill_summary(empty) == {"scored_with_baseline": 0}


def test_the_writers_refuse_at_admission_and_write_nothing(tmp_path):
    led = ledger()
    out = tmp_path / "outcomes.csv"
    with pytest.raises(ValueError, match="result"):
        score.append_outcome(out, outcome(result="Hit"), led)
    with pytest.raises(ValueError, match="not a call in the ledger"):
        score.append_outcome(out, outcome(id="T2-2026-11-09 "), led)
    assert not out.exists()
    score.append_outcome(out, outcome(), led)
    with pytest.raises(ValueError, match="already scored"):
        score.append_outcome(out, outcome(result="miss"), led)
    assert len(score.read_outcomes(led, out)) == 1
    base = tmp_path / "baselines.csv"
    with pytest.raises(ValueError, match="desk_confidence"):
        baseline.append_baseline(base, baseline_row(desk_confidence="0.90"), led)
    assert not base.exists()
    baseline.append_baseline(base, baseline_row(), led)
    assert len(baseline.read_baselines(led, base)) == 1
    # a row edited on disk after it was written is refused when read
    base.write_text(base.read_text(encoding="utf-8").replace("forward_normal", "nosuch"), encoding="utf-8")
    with pytest.raises(ValueError, match="method"):
        baseline.read_baselines(led, base)


def test_every_committed_row_passes_against_the_committed_ledger():
    ledger_path = PRED / "ledger.csv"
    if not ledger_path.exists():
        pytest.skip("no ledger yet")
    led = score.read_ledger(ledger_path)
    outcomes = score.read_outcomes(led, PRED / "outcomes.csv")
    baselines = baseline.read_baselines(led, PRED / "baselines.csv")
    table = baseline.skill_table(led, baselines, outcomes)
    summary = baseline.skill_summary(table)
    assert summary["scored_with_baseline"] == len(outcomes)
