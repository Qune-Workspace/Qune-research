"""Tests on constructed series for predictions/baseline.py.  No network, no files
beyond a temporary directory."""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent / "predictions"))

import baseline as bl  # noqa: E402


def row(**kw) -> pd.Series:
    base = {"id": "T", "made_on": "2026-10-23", "series": "DGS10", "statement": "s", "test": "between_on_due",
            "threshold_low": "4.6", "threshold_high": "5.3", "due_on": "2026-12-31", "confidence": "0.65", "basis": "b"}
    base.update(kw)
    return pd.Series(base)


def walk(start: str, n: int, level: float, sd: float, seed: int = 1) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    return pd.Series(level + np.cumsum(rng.normal(0, sd, n)), index=idx)


def test_horizon_counts_weekdays_after_asof_to_due_inclusive():
    assert bl.business_days_between(pd.Timestamp("2026-10-21"), pd.Timestamp("2026-10-28")) == 5
    with pytest.raises(ValueError):
        bl.business_days_between(pd.Timestamp("2026-10-21"), pd.Timestamp("2026-10-21"))


def test_forward_yield_flat_curve_is_spot_and_upward_curve_is_above_spot():
    assert bl.forward_yield(4.0, 10.0, 4.0, 0.2) == pytest.approx(4.0)
    assert bl.forward_yield(5.13, 10.0, 4.25, 0.2) > 5.13
    with pytest.raises(ValueError):
        bl.forward_yield(5.0, 2.0, 4.0, 2.5)


def test_normal_point_probabilities_add_up():
    centre, scale = 5.0, 0.3
    below = bl.probability_on_due("below_on_due", 4.6, float("nan"), centre, scale)
    between = bl.probability_on_due("between_on_due", 4.6, 5.3, centre, scale)
    above = bl.probability_on_due("above_on_due", 5.3, float("nan"), centre, scale)
    assert below + between + above == pytest.approx(1.0)
    assert bl.probability_on_due("below_on_due", 5.0, float("nan"), centre, scale) == pytest.approx(0.5)
    assert bl.probability_on_due("between_on_due", 4.7, 5.3, centre, scale) == pytest.approx(
        math.erf(1 / math.sqrt(2)), abs=1e-12)


def test_barrier_probability_limits_and_monotone_in_width():
    wide = bl.barrier_probability(2.3, -1e9, 1e9, 40, 0.02, paths=20_000)
    narrow = bl.barrier_probability(2.3, 2.29, 2.31, 40, 0.02, paths=20_000)
    middle = bl.barrier_probability(2.3, 2.0, 2.6, 40, 0.02, paths=20_000)
    assert wide == 1.0
    assert narrow < middle < wide
    assert bl.barrier_probability(2.7, 2.0, 2.6, 40, 0.02, paths=1000) == 0.0
    assert bl.barrier_probability(2.3, 2.0, 2.6, 40, 0.02, paths=20_000) == middle  # seeded


def test_bill_implied_hike_probability_scales_and_clips():
    assert bl.bill_implied_hike_probability(3.88, 3.88, 28, 7) == 0.0
    # spread exactly one step over the post-meeting part of the bill's life
    spread = 0.25 * (28 - 7) / 28
    assert bl.bill_implied_hike_probability(3.88 + spread, 3.88, 28, 7) == pytest.approx(1.0)
    assert bl.bill_implied_hike_probability(3.88 + spread / 2, 3.88, 28, 7) == pytest.approx(0.5)
    assert bl.bill_implied_hike_probability(5.0, 3.88, 28, 7) == 1.0
    with pytest.raises(ValueError):
        bl.bill_implied_hike_probability(4.0, 3.88, 28, 30)


def test_persistence_base_rate_on_constructed_regimes():
    # 100 days positive, 100 negative, repeated: ten steps ahead stays on the same side 90% of the time
    values = np.tile(np.r_[np.ones(100), -np.ones(100)], 3)
    s = pd.Series(values, index=pd.bdate_range("2020-01-01", periods=len(values)))
    assert bl.persistence_base_rate(s, 0.0, True, 10) == pytest.approx(0.9)
    # the closing negative block has no future for its last ten days: 20 flips in 290 negative days
    assert bl.persistence_base_rate(s, 0.0, False, 10) == pytest.approx(20 / 290)
    with pytest.raises(ValueError):
        bl.persistence_base_rate(s, 5.0, True, 10)


def test_compute_baseline_level_spread_and_breakeven_use_only_data_to_asof():
    asof = pd.Timestamp("2026-10-21")
    series = {
        "DGS10": walk("2024-01-01", 800, 5.0, 0.05),
        "DGS2": walk("2024-01-01", 800, 4.5, 0.04, seed=2),
        "DGS3MO": walk("2024-01-01", 800, 4.2, 0.01, seed=3),
        "T10YIE": walk("2024-01-01", 800, 2.3, 0.02, seed=4),
    }
    loaded: list[str] = []

    def load(sid):
        loaded.append(sid)
        return series[sid]

    out = bl.compute_baseline(row(), load, asof)
    assert out["method"] == "forward_normal"
    assert 0.0 <= out["baseline_probability"] <= 1.0
    assert out["inputs"]["spot_on"] == "2026-10-21"
    assert out["inputs"]["spot"] == pytest.approx(float(series["DGS10"].loc[:asof].iloc[-1]))
    assert out["inputs"]["h_business_days"] == bl.business_days_between(asof, pd.Timestamp("2026-12-31"))

    spread = bl.compute_baseline(row(series="T10Y2Y", test="below_on_due", threshold_low="0.32", threshold_high=""),
                                 load, asof)
    s10, s2 = (float(series[k].loc[:asof].iloc[-1]) for k in ("DGS10", "DGS2"))
    assert spread["inputs"]["spot"] == pytest.approx(s10 - s2)
    assert spread["method"] == "forward_normal"

    band = bl.compute_baseline(row(series="T10YIE", test="within_every_day_until_due", threshold_low="2.05",
                                   threshold_high="2.65"), load, asof)
    assert band["method"] == "forward_normal_barrier"
    assert band["inputs"]["forward_centre"] == band["inputs"]["spot"]
    assert "DGS3MO" not in band["inputs"]


def test_compute_baseline_policy_uses_bill_and_funds_to_asof():
    asof = pd.Timestamp("2026-10-21")
    idx = pd.bdate_range("2026-09-01", periods=60)
    series = {"DTB4WK": pd.Series(4.05, index=idx), "EFFR": pd.Series(3.88, index=idx)}
    out = bl.compute_baseline(row(series="DFEDTARU", test="eq_on_due", threshold_low="4.25", threshold_high="",
                                  due_on="2026-10-29"), lambda sid: series[sid], asof)
    assert out["method"] == "bill_implied_hike"
    assert out["inputs"]["meeting_on"] == "2026-10-28"
    assert out["inputs"]["days_to_meeting"] == 7
    assert out["baseline_probability"] == pytest.approx(min(1.0, 0.17 * 28 / 21 / 0.25))


def test_append_refuses_duplicate_and_summary_brier(tmp_path):
    path = tmp_path / "baselines.csv"
    rec = {c: "" for c in bl.BASELINE_COLUMNS}
    rec.update({"id": "A", "baseline_probability": "0.5000", "method": "forward_normal", "asof": "2026-10-21"})
    bl.append_baseline(path, rec)
    with pytest.raises(ValueError):
        bl.append_baseline(path, rec)
    ledger = pd.DataFrame([{"id": "A", "made_on": "2026-10-23", "series": "DGS10", "test": "between_on_due",
                            "due_on": "2026-12-31", "confidence": "0.8"},
                           {"id": "B", "made_on": "2026-10-23", "series": "DGS2", "test": "below_on_due",
                            "due_on": "2026-12-31", "confidence": "0.6"}])
    outcomes = pd.DataFrame([{"id": "A", "result": "hit", "observed_value": "5.0"}])
    table = bl.skill_table(ledger, bl.read_baselines(path), outcomes)
    assert list(table["id"]) == ["A", "B"]
    assert table.loc[1, "method"] == ""
    summary = bl.skill_summary(table)
    assert summary["scored_with_baseline"] == 1
    assert summary["brier_desk"] == pytest.approx(0.04)
    assert summary["brier_baseline"] == pytest.approx(0.25)
    assert summary["skill_vs_baseline"] == pytest.approx(0.21)
    text = bl.render_skill(table, summary, pd.Timestamp("2026-10-25"))
    assert "| A |" in text and "not yet due" in text and "+0.2100" in text
