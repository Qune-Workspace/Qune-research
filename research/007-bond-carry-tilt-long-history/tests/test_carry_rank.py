"""Study 007 §13 tests (1)-(3) and (5): import graph of the signal module,
the expanding rank on constructed carries, the trend signal on constructed
indices, the blend and the descriptive turnover."""

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from src import carry_rank
from src.config import STUDY_DIR

SRC = STUDY_DIR / "src"
FORBIDDEN = {"src.backtest", "src.tilt", "backtest", "tilt"}


def _imports_of(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module.lstrip("."))  # relative imports inside src/
    return names


def _reachable(module: str, seen: set[str] | None = None) -> set[str]:
    seen = set() if seen is None else seen
    path = SRC / f"{module}.py"
    if module in seen or not path.exists():
        return seen
    seen.add(module)
    for name in _imports_of(path):
        local = name.split(".")[-1]
        if (SRC / f"{local}.py").exists():
            _reachable(local, seen)
    return seen


@pytest.mark.parametrize("module", ["carry_rank", "config007"])
def test_signal_modules_never_reach_the_engines(module):
    reached = _reachable(module)
    assert "backtest" not in reached and "tilt" not in reached, reached


def test_import_walker_sees_the_engine_where_it_is():
    assert "backtest" in _reachable("tilt")


# --- expanding rank (§6.2) --------------------------------------------------------------

def test_rank_is_nan_before_the_minimum_history_and_in_unit_interval_after():
    c = pd.Series(np.arange(10, dtype=float), index=[f"m{i}" for i in range(10)])
    w = carry_rank.expanding_rank(c, min_history=4)
    assert w.iloc[:3].isna().all()
    assert w.iloc[3:].notna().all()
    assert ((w.dropna() >= 0) & (w.dropna() <= 1)).all()


def test_rank_of_a_new_maximum_is_one_and_of_a_new_minimum_zero():
    c = pd.Series([1.0, 2.0, 3.0, 4.0, 0.0, 9.0])
    w = carry_rank.expanding_rank(c, min_history=2)
    assert w.iloc[1] == 1.0 and w.iloc[3] == 1.0  # rising: each new value is the max so far
    assert w.iloc[4] == 0.0  # 0.0 below all five earlier values
    assert w.iloc[5] == 1.0


def test_rank_formula_on_a_hand_computed_case():
    # carries seen so far: 3, 1, 4, 1, 5 -> today's 4: below = {3, 1, 1} = 3, ties before = 1 (the
    # earlier 4), n - 1 = 5 -> (3 + 0.5) / 5
    c = pd.Series([3.0, 1.0, 4.0, 1.0, 5.0, 4.0])
    w = carry_rank.expanding_rank(c, min_history=2)
    assert w.iloc[5] == pytest.approx(3.5 / 5)
    # and with a distinct value in place of the earlier 4, no tie: 3 / 5
    c2 = pd.Series([3.0, 1.0, 4.5, 1.0, 5.0, 4.0])
    assert carry_rank.expanding_rank(c2, min_history=2).iloc[5] == pytest.approx(3 / 5)
    # today's 1 at position 3: below = 0, ties before = 1 (the earlier 1), n - 1 = 3 -> 0.5 / 3
    assert w.iloc[3] == pytest.approx(0.5 / 3)


def test_rank_is_monotone_in_todays_carry_given_the_same_history():
    history = [2.0, -1.0, 0.5, 3.0, 1.0]
    ranks = []
    for today in [-5.0, 0.0, 0.7, 2.5, 10.0]:
        w = carry_rank.expanding_rank(pd.Series(history + [today]), min_history=2)
        ranks.append(w.iloc[-1])
    assert ranks == sorted(ranks) and ranks[0] == 0.0 and ranks[-1] == 1.0


def test_rank_has_no_look_ahead():
    rng = np.random.default_rng(7)
    c = pd.Series(rng.normal(size=80))
    w = carry_rank.expanding_rank(c, min_history=12)
    c2 = c.copy()
    c2.iloc[50:] = 100.0  # the future changes
    w2 = carry_rank.expanding_rank(c2, min_history=12)
    pd.testing.assert_series_equal(w.iloc[:50], w2.iloc[:50])


def test_rank_of_exchangeable_carries_is_about_uniform():
    rng = np.random.default_rng(1)
    c = pd.Series(rng.normal(size=5000))
    w = carry_rank.expanding_rank(c, min_history=60).dropna()
    assert abs(w.mean() - 0.5) < 0.02
    assert abs(w.std() - 1 / np.sqrt(12)) < 0.02  # the §11.4 "uniform-rank dispersion"


def test_rank_refuses_undefined_carry():
    with pytest.raises(ValueError):
        carry_rank.expanding_rank(pd.Series([1.0, np.nan, 2.0]), min_history=2)


# --- trend signal (§6.3) ------------------------------------------------------------------

def _indices_and_dates(leg_monthly: list[float], cash_monthly: list[float]):
    dates = pd.date_range("2000-01-31", periods=len(leg_monthly) + 1, freq="ME")
    leg = pd.Series(np.cumprod([1.0] + [1 + r for r in leg_monthly]), index=dates)
    cash = pd.Series(np.cumprod([1.0] + [1 + r for r in cash_monthly]), index=dates)
    signal_dates = pd.Series(dates, index=[d.strftime("%Y-%m") for d in dates])
    return leg, cash, signal_dates


def test_trend_signal_is_nan_for_twelve_rows_then_follows_the_sign():
    leg = [0.01] * 12 + [-0.02] * 12 + [0.03] * 6
    cash = [0.002] * 30
    leg_i, cash_i, sd = _indices_and_dates(leg, cash)
    h = carry_rank.trend_signal(leg_i, cash_i, sd)
    assert h.iloc[:12].isna().all()
    assert h.iloc[12] == 1.0  # the first twelve months beat cash
    assert h.iloc[24] == 0.0  # twelve months of -2% against +0.2%
    assert h.iloc[30] == 1.0  # six months of +3% then six of -2%: (1.03^6 * 0.98^6 - 1) > 12 x 0.2%


def test_excess_return_12m_matches_a_hand_computation():
    rng = np.random.default_rng(3)
    leg = list(rng.normal(0.004, 0.02, 20))
    cash = list(rng.normal(0.002, 0.001, 20))
    leg_i, cash_i, sd = _indices_and_dates(leg, cash)
    x = carry_rank.excess_return_12m(leg_i, cash_i, sd)
    expected = np.prod([1 + r for r in leg[3:15]]) - np.prod([1 + r for r in cash[3:15]])
    assert x.iloc[15] == pytest.approx(expected)


def test_trend_signal_refuses_an_index_undefined_on_a_signal_date():
    leg_i, cash_i, sd = _indices_and_dates([0.01] * 14, [0.0] * 14)
    with pytest.raises(ValueError):
        carry_rank.trend_signal(leg_i.iloc[:-1], cash_i, sd)


# --- blend and turnover ----------------------------------------------------------------------

def test_blend_is_half_and_half_and_nan_where_either_is():
    w = pd.Series([0.2, 0.8, np.nan, 1.0])
    h = pd.Series([1.0, 0.0, 1.0, np.nan])
    b = carry_rank.blend(w, h)
    assert b.iloc[0] == pytest.approx(0.6) and b.iloc[1] == pytest.approx(0.4)
    assert b.iloc[2:].isna().all()


def test_descriptive_turnover_counts_the_first_purchase():
    assert carry_rank.turnover(pd.Series([1.0, 1.0, 0.0, 1.0])) == pytest.approx(3.0)
    assert carry_rank.turnover(pd.Series([np.nan, 0.5, 0.5, 0.25])) == pytest.approx(0.75)
