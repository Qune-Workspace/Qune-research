"""Tests on constructed series for the desk view's functions and the prediction
scorer.  No network, no files beyond a temporary directory."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "predictions"))

import view_lib as vl  # noqa: E402
import score  # noqa: E402


def days(start: str, n: int) -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=n)


# --- view_lib ------------------------------------------------------------------------------

def test_last_valid_skips_missing_and_reports_the_date_used():
    s = pd.Series([1.0, np.nan, np.nan], index=days("2026-01-05", 3))
    date, value = vl.last_valid_on_or_before(s, pd.Timestamp("2026-01-07"))
    assert value == 1.0 and date == pd.Timestamp("2026-01-05")
    with pytest.raises(ValueError):
        vl.last_valid_on_or_before(s, pd.Timestamp("2026-01-02"))


def test_curve_snapshot_one_row_per_tenor_in_order():
    idx = days("2026-01-05", 2)
    snap = vl.curve_snapshot({"3m": pd.Series([4.0, 4.1], idx), "10y": pd.Series([5.0, 5.2], idx)},
                             pd.Timestamp("2026-01-06"))
    assert list(snap["tenor"]) == ["3m", "10y"]
    assert list(snap["yield_pct"]) == [4.1, 5.2]


def test_spread_in_basis_points_on_common_dates_only():
    idx = days("2026-01-05", 3)
    long = pd.Series([5.0, 5.1, 5.2], idx)
    short = pd.Series([4.0, np.nan, 4.9], idx)
    spread = vl.spread_bp(long, short)
    assert list(spread.index) == [idx[0], idx[2]]
    assert np.allclose(spread.values, [100.0, 30.0])


def test_decomposition_identity_and_expected_short_rate():
    d = vl.decomposition(nominal=5.13, real=2.76, breakeven=2.37, term_premium=0.99)
    assert abs(d["identity_gap_pct"]) < 1e-9
    assert d["expected_short_rate_pct"] == pytest.approx(4.14)


def test_stock_bond_corr_sign_convention():
    # Stocks up exactly when yields fall (bond prices up): prices move together -> +1.
    idx = days("2024-01-01", 200)
    rng = np.random.default_rng(0)
    shocks = rng.normal(size=200)
    stock = pd.Series(100 * np.exp(np.cumsum(shocks * 0.01)), idx)
    yld = pd.Series(4.0 - np.cumsum(shocks * 0.02), idx)  # yield falls when stocks rise
    corr = vl.rolling_stock_bond_corr(stock, yld, window=63)
    assert corr.iloc[-1] > 0.95
    # Yields rising when stocks rise (bonds fall): prices move apart -> -1.
    corr2 = vl.rolling_stock_bond_corr(stock, 4.0 + np.cumsum(shocks * 0.02) + 0 * yld, window=63)
    assert corr2.iloc[-1] < -0.95
    assert len(corr) == 200 - 1 - 62  # first return is NaN, then the window fills


def test_market_implied_path_in_bp_with_dates():
    idx = days("2026-10-19", 3)
    out = vl.market_implied_path(pd.Series([3.88, 3.88, 3.88], idx), pd.Series([4.25, 4.26, np.nan], idx),
                                 pd.Series([4.77, 4.79, 4.81], idx), pd.Timestamp("2026-10-21"))
    assert out["bill_3m_minus_effr_bp"] == pytest.approx(38.0)
    assert out["bill_3m_on"] == "2026-10-20"  # the missing day falls back to the day before
    assert out["note_2y_minus_effr_bp"] == pytest.approx(93.0)


def test_change_table_uses_last_valid_before_each_lookback():
    idx = pd.to_datetime(["2026-07-21", "2026-07-22", "2026-10-21"])
    s = pd.Series([4.75, 4.80, 5.13], idx)
    tbl = vl.change_table(s, pd.Timestamp("2026-10-21"), {"3m": pd.DateOffset(months=3)})
    assert tbl.loc[1, "observed_on"] == "2026-07-21"
    assert tbl.loc[1, "change_bp"] == pytest.approx(38.0)


# --- predictions/score.py ------------------------------------------------------------------

def row(**kw) -> pd.Series:
    base = {"id": "T", "made_on": "2026-10-23", "series": "X", "statement": "s", "test": "between_on_due",
            "threshold_low": "4.6", "threshold_high": "5.3", "due_on": "2026-12-31", "confidence": "0.65", "basis": "b"}
    base.update(kw)
    return pd.Series(base)


def test_scorer_point_tests_hit_and_miss():
    idx = pd.to_datetime(["2026-12-30", "2026-12-31"])
    s = pd.Series([5.0, 5.4], idx)
    assert score.evaluate(row(), s)["result"] == "miss"
    assert score.evaluate(row(threshold_high="5.5"), s)["result"] == "hit"
    assert score.evaluate(row(test="below_on_due", threshold_low="5.5", threshold_high=""), s)["result"] == "hit"
    assert score.evaluate(row(test="above_on_due", threshold_low="5.5", threshold_high=""), s)["result"] == "miss"
    assert score.evaluate(row(test="eq_on_due", threshold_low="5.4", threshold_high=""), s)["result"] == "hit"


def test_scorer_uses_last_observation_before_due_and_says_so():
    s = pd.Series([4.25], pd.to_datetime(["2026-10-28"]))
    out = score.evaluate(row(test="eq_on_due", threshold_low="4.25", threshold_high="", due_on="2026-10-29"), s)
    assert out["result"] == "hit" and out["observed_on"] == "2026-10-28" and "before the due date" in out["note"]


def test_scorer_within_every_day_fails_on_one_excursion():
    idx = days("2026-10-23", 10)
    vals = np.full(10, 2.3)
    s = pd.Series(vals, idx)
    r = row(test="within_every_day_until_due", threshold_low="2.1", threshold_high="2.6", due_on="2026-11-04")
    assert score.evaluate(r, s)["result"] == "hit"
    vals2 = vals.copy()
    vals2[5] = 2.7
    out = score.evaluate(r, pd.Series(vals2, idx))
    assert out["result"] == "miss" and out["observed_on"] == str(idx[5].date())
    # The day the call was made is excluded from the window.
    vals3 = vals.copy()
    vals3[0] = 9.9
    assert score.evaluate(r, pd.Series(vals3, idx))["result"] == "hit"


def test_ledger_validation_rejects_duplicates_and_due_before_made():
    good = pd.DataFrame([row().to_dict(), row(id="U").to_dict()])
    score.validate_ledger(good)
    with pytest.raises(ValueError):
        score.validate_ledger(pd.DataFrame([row().to_dict(), row().to_dict()]))
    with pytest.raises(ValueError):
        score.validate_ledger(pd.DataFrame([row(due_on="2026-10-23").to_dict()]))
    with pytest.raises(ValueError):
        score.validate_ledger(pd.DataFrame([row(test="guess").to_dict()]))


def test_due_unscored_excludes_scored_and_future(tmp_path):
    ledger = pd.DataFrame([row(id="A", due_on="2026-10-29").to_dict(), row(id="B", due_on="2026-12-31").to_dict()])
    outcomes = pd.DataFrame(columns=score.OUTCOME_COLUMNS)
    assert list(score.due_unscored(ledger, outcomes, pd.Timestamp("2026-10-30"))["id"]) == ["A"]
    score.append_outcome(tmp_path / "o.csv", {"id": "A", "scored_on": "2026-10-30", "observed_on": "2026-10-29",
                                              "observed_value": 4.25, "result": "hit", "note": "", "raw_sha256": "x"})
    outcomes = score.read_outcomes(tmp_path / "o.csv")
    assert score.due_unscored(ledger, outcomes, pd.Timestamp("2026-10-30")).empty
    assert list(score.due_unscored(ledger, outcomes, pd.Timestamp("2027-01-01"))["id"]) == ["B"]


def test_derived_series_built_from_fetched_inputs():
    idx = days("2024-01-01", 120)
    rng = np.random.default_rng(1)
    shocks = rng.normal(size=120)
    inputs = {"SP500": pd.Series(100 * np.exp(np.cumsum(shocks * 0.01)), idx),
              "DGS10": pd.Series(4.0 - np.cumsum(shocks * 0.02), idx)}
    asked = []

    def fetch(sid):
        asked.append(sid)
        return inputs[sid]

    corr = score.load_series("SBCORR63", fetch)
    assert asked == ["SP500", "DGS10"] and corr.iloc[-1] > 0.95
    assert score.load_series("DGS10", fetch).equals(inputs["DGS10"])


def test_committed_ledger_is_valid():
    ledger_path = HERE.parent.parent / "predictions" / "ledger.csv"
    if not ledger_path.exists():
        pytest.skip("no ledger yet")
    score.read_ledger(ledger_path)
