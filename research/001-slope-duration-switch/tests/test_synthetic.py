"""§5.2 bond maths and synthetic series on toy yields; §5.1 BEY conversion."""
import numpy as np
import pandas as pd
import pytest
from src import bey, synthetic
from src.config import BIL_EXPENSE_RATIO, DC_CROSSCHECK_TOLERANCE, IEF_EXPENSE_RATIO

from tests.toy import toy_yields


@pytest.mark.parametrize("y", [0.0, 0.0125, 0.05, 0.0875, 0.15])
def test_par_bond_prices_at_100(y):
    assert bey.par_bond_price(y, y) == pytest.approx(100.0, abs=1e-10)


def test_price_falls_when_yield_rises():
    assert bey.par_bond_price(0.05, 0.06) < 100.0 < bey.par_bond_price(0.05, 0.04)


def test_discount_to_bey_hand_computed():
    # d = 5%: 365 * 0.05 / (360 - 91 * 0.05) = 18.25 / 355.45
    assert bey.discount_to_bey(0.05) == pytest.approx(18.25 / 355.45, rel=1e-12)
    assert bey.discount_to_bey(0.05) == pytest.approx(0.0513433, abs=1e-7)
    assert bey.discount_to_bey(0.0) == 0.0
    assert np.all(bey.discount_to_bey(np.array([0.01, 0.02])) > np.array([0.01, 0.02]))


def test_par_modified_duration_matches_closed_form_and_finite_difference():
    y = 0.05
    closed_form = (1 - (1 + y / 2) ** -20) / y          # (1 - v^n) / i, in years
    assert bey.par_modified_duration(y) == pytest.approx(closed_form, rel=1e-12)
    h = 1e-6
    numeric = -(bey.par_bond_price(y, y + h) - bey.par_bond_price(y, y - h)) / (2 * h) / 100.0
    assert bey.par_modified_duration(y) == pytest.approx(numeric, rel=1e-6)
    assert bey.par_modified_duration(0.0) == pytest.approx(10.0)


def test_convexity_matches_second_finite_difference():
    y, h = 0.04, 1e-4
    _, convexity = bey.duration_convexity(y, y)
    numeric = (bey.par_bond_price(y, y + h) - 2 * 100.0 + bey.par_bond_price(y, y - h)) / h ** 2 / 100.0
    assert convexity == pytest.approx(numeric, rel=1e-5)


def test_unchanged_yield_earns_carry_minus_expense():
    dates = pd.to_datetime(["2001-01-02", "2001-01-03", "2001-01-08"])   # 1 and 5 calendar days
    ten = synthetic.ten_year_returns(pd.Series([5.0, 5.0, 5.0], index=dates))
    expected = (0.05 - IEF_EXPENSE_RATIO) * np.array([1, 5]) / 365
    assert ten["r_exact"].to_numpy() == pytest.approx(expected, abs=1e-15)
    assert ten["r_dc"].to_numpy() == pytest.approx(expected, abs=1e-15)
    cash = synthetic.cash_returns(pd.Series([4.0, 4.0, 4.0], index=dates))
    bey_4 = 365 * 0.04 / (360 - 91 * 0.04)
    assert cash["r"].to_numpy() == pytest.approx((bey_4 - BIL_EXPENSE_RATIO) * np.array([1, 5]) / 365)


def test_missing_values_are_skipped_and_days_accrue():
    dates = pd.bdate_range("2001-01-01", periods=5)
    ten = synthetic.ten_year_returns(pd.Series([5.0, np.nan, 5.1, np.nan, 5.0], index=dates))
    assert list(ten.index) == [dates[2], dates[4]]
    assert ten["days"].tolist() == [2.0, 2.0]
    assert ten["r_exact"].iloc[0] < 0 < ten["r_exact"].iloc[1]


def test_exact_repricing_agrees_with_duration_convexity_on_toy_yields():
    ten = synthetic.ten_year_returns(toy_yields()["DGS10"])
    assert synthetic.crosscheck_mean_abs_error(ten) <= DC_CROSSCHECK_TOLERANCE
    assert synthetic.crosscheck_passes(ten)
    # the approximation error is third order in the yield change
    assert (ten["r_exact"] - ten["r_dc"]).abs().max() < 1e-5


def test_blend_with_flat_yields_earns_average_carry_minus_expense():
    """§16 blend: with unchanged yields each leg earns its own carry at the
    purchase yield and the blend pays the whole expense ratio once."""
    dates = pd.to_datetime(["2001-01-02", "2001-01-03", "2001-01-08"])
    dgs10 = pd.Series([5.0, 5.0, 5.0], index=dates)
    dgs7 = pd.Series([4.6, 4.6, 4.6], index=dates)
    blend = synthetic.blend_returns(dgs10, dgs7, blend_start="2000-01-01")
    expected = (0.5 * 0.046 + 0.5 * 0.05 - IEF_EXPENSE_RATIO) * np.array([1, 5]) / 365
    assert blend["r_exact"].to_numpy() == pytest.approx(expected, abs=1e-15)
    assert blend["r_dc"].to_numpy() == pytest.approx(expected, abs=1e-15)
    assert blend["blended"].all()


def test_blend_is_the_equal_weight_average_of_exactly_repriced_legs():
    toy = toy_yields()
    blend = synthetic.blend_returns(toy["DGS10"], toy["DGS7"], blend_start="2000-01-01")
    both = pd.concat([toy["DGS10"], toy["DGS7"]], axis=1).dropna()
    seven = synthetic.par_bond_returns(both["DGS7"], 14, IEF_EXPENSE_RATIO)
    ten = synthetic.par_bond_returns(both["DGS10"], 20, IEF_EXPENSE_RATIO)
    assert blend["r_exact"].to_numpy() == pytest.approx(
        (0.5 * seven["r_exact"] + 0.5 * ten["r_exact"]).to_numpy(), abs=1e-15)
    assert list(blend.index) == list(both.index[1:])
    assert synthetic.crosscheck_passes(blend)
    # a 7-year par bond has less duration than a 10-year one, so for the same
    # parallel yield rise the blend loses less than the 10-year leg alone
    dates = pd.to_datetime(["2001-01-02", "2001-01-03"])
    up10 = synthetic.blend_returns(pd.Series([5.0, 5.5], index=dates), pd.Series([5.0, 5.5], index=dates),
                                   blend_start="2000-01-01")["r_exact"].iloc[0]
    only10 = synthetic.ten_year_returns(pd.Series([5.0, 5.5], index=dates))["r_exact"].iloc[0]
    assert only10 < up10 < 0


def test_blend_uses_the_ten_year_alone_before_dgs7_starts():
    """Before BLEND_START the 10-year par bond alone; the return into the
    first blend-era observation is the bridge (10-year alone); every later
    return is the blend.  No date is covered twice and none is dropped."""
    dates = pd.bdate_range("2001-01-01", periods=8)
    rng = np.random.default_rng(3)
    dgs10 = pd.Series(5.0 + np.cumsum(rng.normal(0, 0.05, 8)), index=dates)
    dgs7 = pd.Series(np.nan, index=dates)
    dgs7.iloc[4:] = dgs10.iloc[4:] - 0.2
    start = str(dates[4].date())
    blend = synthetic.blend_returns(dgs10, dgs7, blend_start=start)
    ten = synthetic.ten_year_returns(dgs10)
    assert list(blend.index) == list(dates[1:])
    assert blend["blended"].tolist() == [False] * 4 + [True] * 3
    assert blend.loc[dates[1:5], "r_exact"].to_numpy() == pytest.approx(ten.loc[dates[1:5], "r_exact"].to_numpy(), abs=1e-15)
    assert (blend.loc[dates[5:], "r_exact"].to_numpy() != ten.loc[dates[5:], "r_exact"].to_numpy()).all()
    tri = synthetic.total_return_index(blend["r_exact"], dates[0])
    assert tri.index[0] == dates[0] and tri.iloc[0] == 1.0
    assert tri.iloc[-1] == pytest.approx(np.prod(1 + blend["r_exact"]))
    # with the default BLEND_START (1969) every toy date is in the blend era
    indices = synthetic.synthetic_indices(dgs10, pd.Series(4.0, index=dates), dgs7.ffill().bfill())
    full = synthetic.blend_returns(dgs10, dgs7.ffill().bfill())
    assert full["blended"].all()
    assert indices["IEF"].iloc[-1] == pytest.approx(np.prod(1 + full["r_exact"]))


def test_total_return_index_starts_at_one_on_the_base_date():
    r = pd.Series([0.01, -0.02], index=pd.to_datetime(["2001-01-03", "2001-01-04"]))
    tri = synthetic.total_return_index(r, pd.Timestamp("2001-01-02"))
    assert tri.iloc[0] == 1.0 and tri.index[0] == pd.Timestamp("2001-01-02")
    assert tri.iloc[-1] == pytest.approx(1.01 * 0.98)
