"""§5.2 bond maths and the ageing par-bond construction on toy yields; §5.1
BEY conversion.  The five tests the pre-registration requires before
validation are marked ``§5.2 (i)``-``(v)`` in their docstrings."""
import numpy as np
import pandas as pd
import pytest
from src import bey, synthetic
from src.config import BIL_EXPENSE_RATIO, BOND_PERIODS, BOND_YEARS, DC_CROSSCHECK_TOLERANCE, IEF_EXPENSE_RATIO

from tests.toy import toy_yields


def _explicit_price(coupon: float, y: float, n: int) -> float:
    """Study 001's par-bond price as an explicit cash-flow sum over integer
    periods: sum of c/2 * 100 * v^k for k = 1..n plus 100 * v^n."""
    v = 1.0 / (1.0 + y / 2.0)
    return sum(coupon / 2.0 * 100.0 * v ** k for k in range(1, n + 1)) + 100.0 * v ** n


# --- (i) and (ii): the price formula --------------------------------------------

@pytest.mark.parametrize("y", [0.0, 0.0125, 0.05, 0.0875, 0.15])
@pytest.mark.parametrize("m", [17, 16.99, 16.5, 1])
def test_i_par_bond_prices_at_100_for_non_integer_periods(y, m):
    """§5.2 (i): P(c, c, m) = 100 for m in {17, 16.99, 16.5, 1}."""
    assert bey.par_bond_price(y, y, m) == pytest.approx(100.0, abs=1e-10)


@pytest.mark.parametrize("c,y", [(0.05, 0.06), (0.05, 0.04), (0.02, 0.02), (0.0, 0.03), (0.08, 0.0)])
def test_ii_seventeen_period_price_equals_study_001_integer_formula(c, y):
    """§5.2 (ii): P(c, y, 17) equals the integer-period par-bond price of
    Study 001, written out as a cash-flow sum."""
    assert bey.par_bond_price(c, y, BOND_PERIODS) == pytest.approx(_explicit_price(c, y, BOND_PERIODS), rel=1e-12)
    assert bey.par_bond_price(c, y, 20) == pytest.approx(_explicit_price(c, y, 20), rel=1e-12)


def test_price_accepts_an_array_of_periods():
    prices = bey.par_bond_price(np.array([0.05, 0.05]), np.array([0.06, 0.04]), np.array([17.0, 16.98]))
    assert prices[0] < 100.0 < prices[1]
    assert prices[0] == pytest.approx(_explicit_price(0.05, 0.06, 17), rel=1e-12)


def test_price_falls_when_yield_rises():
    assert bey.par_bond_price(0.05, 0.06) < 100.0 < bey.par_bond_price(0.05, 0.04)


# --- Study 001 checks that still apply ----------------------------------------------

def test_discount_to_bey_hand_computed():
    # d = 5%: 365 * 0.05 / (360 - 91 * 0.05) = 18.25 / 355.45
    assert bey.discount_to_bey(0.05) == pytest.approx(18.25 / 355.45, rel=1e-12)
    assert bey.discount_to_bey(0.05) == pytest.approx(0.0513433, abs=1e-7)
    assert bey.discount_to_bey(0.0) == 0.0
    assert np.all(bey.discount_to_bey(np.array([0.01, 0.02])) > np.array([0.01, 0.02]))


def test_par_modified_duration_matches_closed_form_and_finite_difference():
    y = 0.05
    closed_form = (1 - (1 + y / 2) ** -BOND_PERIODS) / y          # (1 - v^n) / i, in years
    assert bey.par_modified_duration(y, BOND_PERIODS) == pytest.approx(closed_form, rel=1e-12)
    h = 1e-6
    numeric = -(bey.par_bond_price(y, y + h, BOND_PERIODS) - bey.par_bond_price(y, y - h, BOND_PERIODS)) / (2 * h) / 100.0
    assert bey.par_modified_duration(y, BOND_PERIODS) == pytest.approx(numeric, rel=1e-6)
    assert bey.par_modified_duration(0.0, BOND_PERIODS) == pytest.approx(BOND_YEARS)


def test_convexity_matches_second_finite_difference():
    y, h = 0.04, 1e-4
    _, convexity = bey.duration_convexity(y, y, BOND_PERIODS)
    numeric = (bey.par_bond_price(y, y + h, BOND_PERIODS) - 2 * 100.0
               + bey.par_bond_price(y, y - h, BOND_PERIODS)) / h ** 2 / 100.0
    assert convexity == pytest.approx(numeric, rel=1e-5)


def test_interpolated_par_yield_is_linear_between_7_and_10_years():
    assert synthetic.interpolated_par_yield(0.02, 0.05, 7.0) == pytest.approx(0.02)
    assert synthetic.interpolated_par_yield(0.02, 0.05, 10.0) == pytest.approx(0.05)
    assert synthetic.interpolated_par_yield(0.02, 0.05, 8.5) == pytest.approx(0.035)
    assert synthetic.interpolated_par_yield(0.02, 0.05, 8.5 - 1 / 365) == pytest.approx(0.035 - 0.03 / 3 / 365)


# --- (iii), (iv), (v): the construction ----------------------------------------------

def test_iii_flat_curve_earns_carry_minus_fee_and_no_rolldown():
    """§5.2 (iii): with DGS7 = DGS10 constant the bond is repriced at par, so
    r_t is exactly carry minus the fee over 1 and 5 calendar days."""
    dates = pd.to_datetime(["2001-01-02", "2001-01-03", "2001-01-08"])   # 1 and 5 calendar days
    flat = pd.Series([5.0, 5.0, 5.0], index=dates)
    out = synthetic.ageing_bond_returns(flat, flat)
    expected = (0.05 - IEF_EXPENSE_RATIO) * np.array([1, 5]) / 365
    assert out["r_exact"].to_numpy() == pytest.approx(expected, abs=1e-15)
    assert out["r_dc"].to_numpy() == pytest.approx(expected, abs=1e-15)
    assert out["days"].tolist() == [1.0, 5.0]


def test_iv_constant_upward_sloping_curve_earns_rolldown():
    """§5.2 (iv): with yields unchanged over time and DGS10 > DGS7, r_t exceeds
    carry minus fee by approximately D_mod x (y10 - y7)/3 x dt."""
    dates = pd.to_datetime(["2001-01-02", "2001-01-03", "2001-01-08"])
    y7, y10 = 4.6, 5.2
    out = synthetic.ageing_bond_returns(pd.Series(y7, index=dates), pd.Series(y10, index=dates))
    y85 = (y7 + y10) / 2 / 100
    d_mod = bey.par_modified_duration(y85, BOND_PERIODS)
    for dt, r in zip(np.array([1, 5]) / 365, out["r_exact"].to_numpy()):
        carry = (y85 - IEF_EXPENSE_RATIO) * dt
        rolldown = d_mod * (y10 - y7) / 100 / 3 * dt
        assert r > carry
        # "approximately": the exact figure differs from D_mod x slope/3 x dt by
        # the second-order terms and by the bond being 2*dt periods shorter
        assert r - carry == pytest.approx(rolldown, rel=5e-3)
    # the roll-down is a yield effect: the sale yield sits below the purchase yield
    assert (out["y"] < out["y_prev"]).all()
    # an inverted 7-10 segment gives negative roll-down
    inverted = synthetic.ageing_bond_returns(pd.Series(y10, index=dates), pd.Series(y7, index=dates))
    assert (inverted["r_exact"] < (y85 - IEF_EXPENSE_RATIO) * np.array([1, 5]) / 365).all()


def test_v_shifting_all_yields_by_one_day_moves_dates_only():
    """§5.2 (v): shifting every observation forward by one day moves every
    return date by one day and changes no return."""
    toy = toy_yields()
    base = synthetic.ageing_bond_returns(toy["DGS7"], toy["DGS10"])
    shifted = synthetic.ageing_bond_returns(
        pd.Series(toy["DGS7"].values, index=toy["DGS7"].index + pd.Timedelta(days=1)),
        pd.Series(toy["DGS10"].values, index=toy["DGS10"].index + pd.Timedelta(days=1)))
    assert ((shifted.index - base.index) == pd.Timedelta(days=1)).all()
    for col in ("r_exact", "r_dc", "y_prev", "y", "days"):
        assert shifted[col].to_numpy() == pytest.approx(base[col].to_numpy(), abs=0)


# --- Other properties ---------------------------------------------------------------

def test_missing_values_are_skipped_and_days_accrue():
    dates = pd.bdate_range("2001-01-01", periods=5)
    dgs10 = pd.Series([5.0, np.nan, 5.1, np.nan, 5.0], index=dates)
    dgs7 = pd.Series([4.8, 4.8, 4.9, 4.9, 4.8], index=dates)
    out = synthetic.ageing_bond_returns(dgs7, dgs10)
    assert list(out.index) == [dates[2], dates[4]]
    assert out["days"].tolist() == [2.0, 2.0]
    assert out["r_exact"].iloc[0] < 0 < out["r_exact"].iloc[1]
    # a day missing in one series only is skipped as well
    dgs7_gap = dgs7.copy()
    dgs7_gap.iloc[2] = np.nan
    out2 = synthetic.ageing_bond_returns(dgs7_gap, dgs10)
    assert list(out2.index) == [dates[4]] and out2["days"].tolist() == [4.0]


def test_exact_repricing_agrees_with_duration_convexity_on_toy_yields():
    toy = toy_yields()
    out = synthetic.ageing_bond_returns(toy["DGS7"], toy["DGS10"])
    assert synthetic.crosscheck_mean_abs_error(out) <= DC_CROSSCHECK_TOLERANCE
    assert synthetic.crosscheck_passes(out)
    # the approximation error is third order in the yield change plus the
    # tiny effect of ageing on an off-par bond; the toy yields jump by up to
    # about 15 bp a day, far more than the real series, and still stay under
    # 0.2 bp on the worst day
    assert (out["r_exact"] - out["r_dc"]).abs().max() < 2e-5


def test_duration_returns_matches_ageing_bond_with_dgs10_first():
    toy = toy_yields()
    a = synthetic.duration_returns(toy["DGS10"], toy["DGS7"])
    b = synthetic.ageing_bond_returns(toy["DGS7"], toy["DGS10"])
    pd.testing.assert_frame_equal(a, b)


def test_cash_leg_unchanged_yield_earns_carry_minus_expense():
    dates = pd.to_datetime(["2001-01-02", "2001-01-03", "2001-01-08"])
    cash = synthetic.cash_returns(pd.Series([4.0, 4.0, 4.0], index=dates))
    bey_4 = 365 * 0.04 / (360 - 91 * 0.04)
    assert cash["r"].to_numpy() == pytest.approx((bey_4 - BIL_EXPENSE_RATIO) * np.array([1, 5]) / 365)


def test_synthetic_indices_start_at_one_on_the_first_common_observation():
    toy = toy_yields()
    indices = synthetic.synthetic_indices(toy["DGS10"], toy["DTB3"], toy["DGS7"])
    both = pd.concat([toy["DGS7"], toy["DGS10"]], axis=1).dropna()
    assert indices["IEF"].index[0] == both.index[0] and indices["IEF"].iloc[0] == 1.0
    out = synthetic.ageing_bond_returns(toy["DGS7"], toy["DGS10"])
    assert indices["IEF"].iloc[-1] == pytest.approx(np.prod(1 + out["r_exact"]))
    assert indices["BIL"].index[0] == toy["DTB3"].dropna().index[0] and indices["BIL"].iloc[0] == 1.0
    # DGS7 starting later than DGS10 moves the duration index's start, not the cash index's
    late7 = toy["DGS7"].copy()
    late7.iloc[:40] = np.nan
    late = synthetic.synthetic_indices(toy["DGS10"], toy["DTB3"], late7)
    assert late["IEF"].index[0] == late7.dropna().index[0]
    assert late["BIL"].index[0] == indices["BIL"].index[0]


def test_total_return_index_starts_at_one_on_the_base_date():
    r = pd.Series([0.01, -0.02], index=pd.to_datetime(["2001-01-03", "2001-01-04"]))
    tri = synthetic.total_return_index(r, pd.Timestamp("2001-01-02"))
    assert tri.iloc[0] == 1.0 and tri.index[0] == pd.Timestamp("2001-01-02")
    assert tri.iloc[-1] == pytest.approx(1.01 * 0.98)
