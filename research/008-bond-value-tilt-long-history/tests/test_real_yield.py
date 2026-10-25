"""Study 008 §13 tests (1)-(3) for ``real_yield.py``: import graph; π and r on
constructed CPI series (k = m - 1, never m; the availability rule; a missing
index making r undefined; the §16 clarifications); the trailing rank (window
120 including today, denominator 119, ties, no weight before 120 values, no
look-ahead); ranks over defined values only."""

import numpy as np
import pandas as pd
import pytest
from src import real_yield as ry

from tests.test_carry_rank import _reachable


def months(first: str, n: int) -> pd.PeriodIndex:
    return pd.period_range(first, periods=n, freq="M")


def cpi_series(first: str, values) -> pd.Series:
    return pd.Series(np.asarray(values, dtype=float), index=months(first, len(values)))


def availability(rows) -> pd.DataFrame:
    """rows: (signal_month, head_k, head_branch, core_k, core_branch)."""
    return pd.DataFrame(
        [{"signal_month": m, "signal_date": "", "CPIAUCNS_m1_published_by_t": "", "CPIAUCNS_k": hk,
          "CPIAUCNS_branch": hb, "CPILFENS_m1_published_by_t": "", "CPILFENS_k": ck, "CPILFENS_branch": cb}
         for m, hk, hb, ck, cb in rows])


# --- (1) import graph ------------------------------------------------------------------

def test_real_yield_never_reaches_the_engines():
    reached = _reachable("real_yield")
    assert "backtest" not in reached and "tilt" not in reached, reached


# --- (2) k, π and r -----------------------------------------------------------------------

def test_inflation_uses_k_equal_m_minus_one_never_m():
    cpi = cpi_series("2000-01", np.arange(100.0, 130.0))  # 2000-01 .. 2002-06
    m = months("2001-06", 3)
    k = pd.Series(m - 1, index=m)
    pi = ry.inflation_12m(cpi, k)
    expected = [cpi[p - 1] / cpi[p - 13] - 1 for p in m]
    assert np.allclose(pi.to_numpy(), expected)
    # Changing the index for month m itself changes nothing.
    bumped = cpi.copy()
    bumped[m[1]] *= 2.0
    assert np.allclose(ry.inflation_12m(bumped, k).iloc[1], pi.iloc[1])


def test_k_months_refuses_k_equal_to_m():
    with pytest.raises(ValueError):
        ry.k_months(availability([("2001-06", "2001-06", "release_date_read", "2001-05", "release_date_read")]),
                    "CPIAUCNS")


def test_availability_rule_moves_k_to_the_latest_published_month():
    av = availability([
        ("1996-01", "1995-11", "release_date_read", "1995-12", "assumed_known"),
        ("1996-02", "1996-01", "release_date_read", "1996-01", "assumed_known"),
        ("1997-02", "1997-01", "release_date_read", "1996-12", "release_date_read"),
    ])
    k_head = ry.k_months(av, "CPIAUCNS")
    assert list(k_head.astype(str)) == ["1995-11", "1996-01", "1997-01"]
    # §16 (a): core without its own vintage follows the headline release; a core release read is its own.
    k_core = ry.k_months(av, "CPILFENS")
    assert list(k_core.astype(str)) == ["1995-11", "1996-01", "1996-12"]
    cpi = cpi_series("1994-01", np.linspace(150.0, 160.0, 48))
    pi = ry.inflation_12m(cpi, k_head)
    p = pd.Period("1995-11", "M")
    assert pi.iloc[0] == pytest.approx(cpi[p] / cpi[p - 12] - 1)


def test_core_with_no_vintage_and_no_headline_read_assumes_m_minus_one():
    av = availability([("1970-03", "1970-02", "assumed_known", "1970-02", "assumed_known")])
    assert str(ry.k_months(av, "CPILFENS").iloc[0]) == "1970-02"


def test_a_missing_index_makes_pi_and_r_undefined():
    values = np.linspace(200.0, 230.0, 36)  # 2024-01 .. 2026-12
    cpi = cpi_series("2024-01", values)
    cpi[pd.Period("2025-10", "M")] = np.nan  # never published
    # 2025-11: m - 1 missing -> undefined even though the availability table names 2025-09 (§16 (b)).
    # 2026-11: k = 2026-10 exists but k - 12 = 2025-10 is missing -> undefined.
    # 2026-01: everything present -> defined.
    m = pd.PeriodIndex(["2025-11", "2026-01", "2026-11"], freq="M")
    k = pd.Series(pd.PeriodIndex(["2025-09", "2025-12", "2026-10"], freq="M"), index=m)
    pi = ry.inflation_12m(cpi, k)
    assert np.isnan(pi.iloc[0]) and np.isfinite(pi.iloc[1]) and np.isnan(pi.iloc[2])


def test_real_yield_is_the_ten_year_yield_at_the_signal_date_less_pi():
    days = pd.bdate_range("2001-05-01", "2001-07-31")
    dgs10 = pd.Series(np.linspace(5.0, 6.0, len(days)), index=days)
    m = months("2001-05", 3)
    signal = pd.Series([days[days.to_period("M") == p][-1] for p in m], index=m)
    pi = pd.Series([0.02, 0.03, np.nan], index=m)
    r = ry.real_yield(dgs10, signal, pi)
    assert r.iloc[0] == pytest.approx(dgs10[signal.iloc[0]] / 100 - 0.02)
    assert r.iloc[1] == pytest.approx(dgs10[signal.iloc[1]] / 100 - 0.03)
    assert np.isnan(r.iloc[2])


# --- (3) trailing rank -------------------------------------------------------------------

def test_trailing_rank_window_includes_today_and_divides_by_window_minus_one():
    v = pd.Series(np.arange(130, dtype=float))
    w = ry.trailing_rank(v, 120)
    assert w.iloc[:119].isna().all() and w.iloc[119:].notna().all()
    assert w.iloc[119] == 1.0 and w.iloc[129] == 1.0  # a new maximum: 119 below / 119
    v2 = v.copy()
    v2.iloc[129] = 15.0  # inside the window 10..129: values 10..14 are below it, one tie (15) before
    assert ry.trailing_rank(v2, 120).iloc[129] == pytest.approx((5 + 0.5) / 119)


def test_trailing_rank_forgets_values_outside_the_window():
    v = pd.Series(np.r_[np.full(10, -100.0), np.arange(120, dtype=float)])
    w = ry.trailing_rank(v, 120)
    # At the last month the window is the 120 values 0..119: the -100s have left it.
    assert w.iloc[-1] == 1.0
    v_today_low = v.copy()
    v_today_low.iloc[-1] = -50.0
    assert ry.trailing_rank(v_today_low, 120).iloc[-1] == 0.0


def test_trailing_rank_has_no_look_ahead():
    rng = np.random.default_rng(8)
    v = pd.Series(rng.normal(size=200))
    w = ry.trailing_rank(v, 120)
    changed = v.copy()
    changed.iloc[150:] += 10.0
    w2 = ry.trailing_rank(changed, 120)
    assert np.array_equal(w.iloc[:150].to_numpy(), w2.iloc[:150].to_numpy(), equal_nan=True)


def test_trailing_rank_refuses_undefined_values():
    with pytest.raises(ValueError):
        ry.trailing_rank(pd.Series([1.0, np.nan, 2.0]), 2)


def test_ranks_count_defined_values_only_and_leave_undefined_months_empty():
    idx = months("2000-01", 8)
    r = pd.Series([0.01, 0.02, np.nan, 0.03, 0.00, np.nan, 0.05, 0.04], index=idx)
    w = ry.rank_defined(r, "expanding", 3)
    assert w.index.equals(idx)
    assert np.isnan(w.iloc[2]) and np.isnan(w.iloc[5])
    # Third defined value (2000-04, 0.03) is the first with a weight: max of three -> 1.
    assert np.isnan(w.iloc[1]) and w.iloc[3] == 1.0
    assert w.iloc[4] == 0.0  # 0.00 is the lowest of four defined values
    wt = ry.rank_defined(r, "trailing", 3)
    assert np.isnan(wt.iloc[1]) and wt.iloc[3] == 1.0
    assert wt.iloc[7] == pytest.approx(1 / 2)  # window (0.00, 0.05, 0.04): one below / 2
    with pytest.raises(ValueError):
        ry.rank_defined(r, "other", 3)
