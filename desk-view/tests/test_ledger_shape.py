"""The shape of one ledger row is held against its test kind (predictions/score.py,
rule added 2026-11-09 after "A band with one side scored as a result" in
predictions/POST_MORTEMS.md).  No tool writes a rates call, so the gate a hand-typed
row meets is ``score.validate_ledger``: at scoring time through ``read_ledger`` and on
the committed file through this suite.  The column search below alters each column
of a clean row in turn and asks the gate once; a new column fails the search until
it is classified here."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "predictions"))

import baseline  # noqa: E402
import score  # noqa: E402

CLEAN = {"id": "T2-2026-11-09", "made_on": "2026-11-09", "series": "DGS10",
         "statement": "The 10-year yield on 2026-12-31 is between 4.60% and 5.30%.", "test": "between_on_due",
         "threshold_low": "4.60", "threshold_high": "5.30", "due_on": "2026-12-31", "confidence": "0.65",
         "basis": "a stated reason"}

# One bad value per column, and the word the refusal must carry.  Every LEDGER_COLUMNS
# column appears here: the search is the checklist.
ALTERED = {
    "id": ("", "id"),
    "made_on": ("09/11/2026", "made_on"),
    "series": ("NOSUCHSERIES", "series"),
    "statement": ("", "statement"),
    "test": ("beats_market", "test"),
    "threshold_low": ("four", "threshold_low"),
    "threshold_high": ("", "threshold_high"),
    "due_on": ("2026-10-01", "due_on"),
    "confidence": ("0.9", "confidence"),
    "basis": ("  ", "basis"),
}


def row(**kw) -> dict:
    out = dict(CLEAN)
    out.update(kw)
    return out


def test_the_clean_row_passes_the_shape_gate():
    assert score.row_shape_violations(row()) == []
    score.validate_ledger(pd.DataFrame([row()]))


def test_every_column_is_held_by_the_shape_gate_and_names_itself():
    assert set(ALTERED) == set(score.LEDGER_COLUMNS), "classify the new column in ALTERED"
    for col, (bad, word) in ALTERED.items():
        problems = score.row_shape_violations(row(**{col: bad}))
        assert problems, f"{col} altered to {bad!r} was admitted"
        assert any(word in p for p in problems), f"{col}: refusal does not name the column: {problems}"
        with pytest.raises(ValueError, match=word):
            score.validate_ledger(pd.DataFrame([row(**{col: bad})]))


def test_a_repeated_id_is_refused_by_name():
    with pytest.raises(ValueError, match="repeated id"):
        score.validate_ledger(pd.DataFrame([row(), row()]))


@pytest.mark.parametrize("kind", sorted(score.TESTS))
def test_threshold_shape_follows_the_test_kind(kind):
    two_sided = kind in score.TWO_SIDED
    good = row(test=kind, threshold_low="4.60", threshold_high="5.30" if two_sided else "")
    assert score.row_shape_violations(good) == []
    wrong = row(test=kind, threshold_low="4.60", threshold_high="" if two_sided else "5.30")
    assert any("threshold_high" in p for p in score.row_shape_violations(wrong))
    if two_sided:
        inverted = row(test=kind, threshold_low="5.30", threshold_high="4.60")
        assert any("not below" in p for p in score.row_shape_violations(inverted))
        flat = row(test=kind, threshold_low="4.60", threshold_high="4.60")
        assert any("not below" in p for p in score.row_shape_violations(flat))


def test_the_kinds_partition():
    assert score.TWO_SIDED | score.ONE_SIDED == score.TESTS and not score.TWO_SIDED & score.ONE_SIDED


def test_scorable_series_are_exactly_those_the_baseline_can_price():
    assert set(score.SCORABLE_SERIES) == set(baseline.SERIES_SPEC)
    assert set(score.DERIVED) <= set(score.SCORABLE_SERIES)


def _series(value: float) -> pd.Series:
    idx = pd.bdate_range("2026-11-10", "2026-12-31")
    return pd.Series(np.full(len(idx), value), idx)


def test_evaluate_refuses_a_band_it_cannot_read_instead_of_scoring_it():
    # Before 2026-11-09 these scored: miss, miss, hit, hit (observed on b441d1e with a scratch script).
    s = _series(4.9)
    assert score.evaluate(pd.Series(row()), s)["result"] == "hit"
    with pytest.raises(ValueError, match="needs threshold_high"):
        score.evaluate(pd.Series(row(threshold_high="")), s)
    with pytest.raises(ValueError, match="not below"):
        score.evaluate(pd.Series(row(threshold_low="5.30", threshold_high="4.60")), s)
    with pytest.raises(ValueError, match="needs threshold_high"):
        score.evaluate(pd.Series(row(test="within_every_day_until_due", threshold_high="")), s)
    with pytest.raises(ValueError, match="takes no threshold_high"):
        score.evaluate(pd.Series(row(test="below_on_due", threshold_low="5.0", threshold_high="1.0")), s)
    with pytest.raises(ValueError, match="unknown test"):
        score.evaluate(pd.Series(row(test="beats_market")), s)


def test_every_committed_row_passes_the_shape_gate():
    ledger_path = HERE.parent.parent / "predictions" / "ledger.csv"
    if not ledger_path.exists():
        pytest.skip("no ledger yet")
    ledger = pd.read_csv(ledger_path, dtype=str, keep_default_na=False)
    for _, r in ledger.iterrows():
        assert score.row_shape_violations(r.to_dict()) == [], r["id"]
