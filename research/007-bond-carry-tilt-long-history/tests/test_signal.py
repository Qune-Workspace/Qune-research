"""§6.1 and §7 signal definitions on hand-built inputs."""
import numpy as np
import pandas as pd
import pytest
from src import signal
from src.bey import discount_to_bey, par_modified_duration
from src.config import CASH_LEG, DURATION_LEG


def _series(values, start="2001-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


def test_daily_spread_uses_bey_and_drops_missing():
    dgs10 = _series([5.0, 5.0, np.nan, 5.0])
    dtb3 = _series([4.8, np.nan, 4.8, 5.2])
    spread = signal.daily_spread(dgs10, dtb3)
    assert list(spread.index) == [dgs10.index[0], dgs10.index[3]]
    assert spread.iloc[0] == pytest.approx(0.05 - discount_to_bey(0.048))
    assert spread.iloc[1] == pytest.approx(0.05 - discount_to_bey(0.052))


def test_threshold_is_exactly_zero():
    value = pd.Series([1e-12, 0.0, -1e-12])
    assert signal.target_from_value(value).tolist() == [DURATION_LEG, CASH_LEG, CASH_LEG]


def test_t1_picks_the_value_on_the_signal_date():
    dgs10 = _series(np.linspace(4.0, 6.0, 30))
    dtb3 = _series(np.full(30, 5.0))
    dates = pd.Series(dgs10.index[[5, 29]], index=pd.PeriodIndex(["2001-01", "2001-02"], freq="M"))
    out = signal.t1(dgs10, dtb3, dates)
    assert out["value"].iloc[0] == pytest.approx(dgs10.iloc[5] / 100 - discount_to_bey(0.05))
    assert out["target"].tolist() == [CASH_LEG, DURATION_LEG]


def test_t2_is_the_mean_of_the_last_21_valid_spreads():
    dgs10 = _series(np.arange(40, dtype=float) / 10 + 3.0)
    dtb3 = _series(np.full(40, 3.0))
    dgs10.iloc[30] = np.nan                                   # a holiday inside the window
    spread = signal.daily_spread(dgs10, dtb3)
    dates = pd.Series([dgs10.index[39]], index=pd.PeriodIndex(["2001-02"], freq="M"))
    out = signal.t2(dgs10, dtb3, dates)
    assert out["value"].iloc[0] == pytest.approx(spread.iloc[-21:].mean())
    early = pd.Series([dgs10.index[10]], index=pd.PeriodIndex(["2001-01"], freq="M"))
    assert signal.t2(dgs10, dtb3, early).empty          # fewer than 21 observations: undefined


def test_t3_carry_formula():
    dgs10, dgs7, dtb3 = _series([5.0]), _series([4.7]), _series([4.0])
    dates = pd.Series([dgs10.index[0]], index=pd.PeriodIndex(["2001-01"], freq="M"))
    out = signal.t3(dgs10, dgs7, dtb3, dates)
    expected = (0.05 - discount_to_bey(0.04)) + par_modified_duration(0.05) * (0.05 - 0.047) / 3
    assert out["value"].iloc[0] == pytest.approx(expected, rel=1e-12)
    assert out["target"].iloc[0] == DURATION_LEG


def test_gap_after_first_defined_value_is_an_error():
    dgs10 = _series([5.0, 5.0, 5.0])
    dtb3 = _series([4.0, np.nan, 4.0])
    dates = pd.Series([dgs10.index[1]], index=pd.PeriodIndex(["2001-01"], freq="M"))
    with pytest.raises(ValueError):
        signal.t1(dgs10, dtb3, dates)
