"""Study 011 rule, costs and Newey-West on synthetic series only."""
import numpy as np
import pandas as pd
import pytest
from src.rule import COST_BASE, formation_returns, rank_cohort, run
from src.stats011 import newey_west_stretches

from qune_research.stats import newey_west_mean

P = pd.Period


def _frame(n_months: int, cols: list[str], seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.period_range("1926-07", periods=n_months, freq="M")
    return pd.DataFrame(rng.normal(1.0, 5.0, size=(n_months, len(cols))).round(2), index=idx, columns=cols)


def test_formation_no_skip_and_missing():
    r = pd.DataFrame({"A": [0.0, 0.0, 10.0], "B": [1.0, np.nan, 1.0]}, index=pd.period_range("1926-07", periods=3, freq="M"))
    R = formation_returns(r, 2)
    assert R.loc[P("1926-09", "M"), "A"] == pytest.approx(0.10)  # includes month m itself (t-1 for t = m+1)
    assert np.isnan(R.loc[P("1926-09", "M"), "B"])  # a missing formation month makes B ineligible


def test_rank_order_and_ties():
    R = pd.Series({"A": 0.05, "B": 0.05, "C": -0.01, "D": 0.20, "E": -0.30})
    w, lo, ties = rank_cohort(R, 2)
    assert w == ["D", "A"]  # A before B: equal to ten decimals, earlier column first
    assert lo == ["C", "E"]
    assert ties == 1  # A/B straddle the n/n+1 boundary at the top
    with pytest.raises(ValueError):
        rank_cohort(pd.Series({"A": 0.1, "B": np.nan, "C": 0.2}), 2)


def test_constant_ranking_costs_and_d():
    idx = pd.period_range("1926-07", periods=24, freq="M")
    r = pd.DataFrame({"A": 3.0, "B": 1.0, "C": 0.5, "D": -2.0}, index=idx)
    out = run(r, F=6, n=1, first_holding=P("1927-06", "M"))
    assert out.index[0] == P("1927-06", "M")
    assert out["d_gross"].iloc[0] == pytest.approx(5.0)  # A minus D every month
    assert out["turnover"].iloc[0] == pytest.approx(2.0)  # entry from zero: 1 long + 1 short
    assert (out["turnover"].iloc[1:] == 0).all()
    assert out["d_base"].iloc[0] == pytest.approx(5.0 - COST_BASE * 2.0)
    assert out["ew"].iloc[0] == pytest.approx(np.mean([3.0, 1.0, 0.5, -2.0]))


def test_one_replacement_adds_2_over_6n():
    idx = pd.period_range("1926-07", periods=30, freq="M")
    base = {"A": 3.0, "B": 1.0, "C": 0.5, "D": 0.0, "E": -2.0}
    r = pd.DataFrame(base, index=idx)
    # month 1927-07: B jumps so that over 1927-02..07 B leads A for the cohort ranked at 1927-07 only
    r.loc[P("1927-07", "M"), "B"] = 40.0
    out = run(r, F=6, n=1, first_holding=P("1927-06", "M"))
    t = P("1927-08", "M")  # first month holding the cohort ranked at 1927-07
    assert out.loc[t, "turnover"] == pytest.approx(2.0 / 6.0)


def test_d_equals_weights_times_returns_without_missing():
    cols = [f"I{i}" for i in range(17)]
    r = _frame(60, cols, seed=1)
    out = run(r, F=6, n=3, first_holding=P("1927-06", "M"))
    assert len(out) == 60 - 11
    assert out["empty_legs"].sum() == 0
    assert np.isfinite(out["d_gross"]).all()


def test_empty_leg_contributes_zero():
    idx = pd.period_range("1926-07", periods=20, freq="M")
    r = pd.DataFrame({"A": 3.0, "B": 1.0, "C": -2.0}, index=idx)
    t = P("1927-08", "M")
    r.loc[t, "C"] = np.nan  # the loser has no value in t: every cohort's short leg is empty
    out = run(r, F=6, n=1, first_holding=P("1927-06", "M"))
    assert out.loc[t, "d_gross"] == 0.0
    assert out.loc[t, "empty_legs"] == 6


def test_first_holding_needs_formation():
    r = _frame(30, list("ABCDEFGH"))
    with pytest.raises(ValueError):
        run(r, F=12, n=3, first_holding=P("1927-06", "M"))  # ranking at 1926-12 has no 12-month formation
    out = run(r, F=12, n=3, first_holding=P("1927-12", "M"))
    assert out.index[0] == P("1927-12", "M")


def test_nw_single_stretch_matches_shared_library():
    x = pd.Series(np.random.default_rng(3).normal(0.2, 2.0, 300))
    a = newey_west_stretches([x])
    b = newey_west_mean(x, lags=6)
    assert a["mean"] == pytest.approx(b["mean"])
    assert a["se"] == pytest.approx(b["se"], rel=1e-10)


def test_nw_two_stretches_drop_cross_gap_pairs():
    rng = np.random.default_rng(4)
    p1, p2 = pd.Series(rng.normal(0, 1, 50)), pd.Series(rng.normal(0, 1, 40))
    two = newey_west_stretches([p1, p2])
    joined = newey_west_stretches([pd.concat([p1, p2], ignore_index=True)])
    assert two["mean"] == pytest.approx(joined["mean"])
    assert two["se"] != pytest.approx(joined["se"], rel=1e-12)
    # by hand: the difference is the six cross-gap lag terms only
    allv = np.concatenate([p1, p2])
    u = allv - allv.mean()
    N = len(u)
    cross = sum(2 * (1 - j / 7) * sum(u[50 + k] * u[50 + k - j] for k in range(j)) / N for j in range(1, 7))
    assert two["se"] ** 2 * N == pytest.approx(joined["se"] ** 2 * N - cross)
