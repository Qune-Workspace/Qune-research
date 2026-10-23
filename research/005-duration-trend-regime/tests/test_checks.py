"""§5.3 on constructed series: D0 coverage and the halt flags, D1 sign
agreement, D3 flags on the window's holding-period dates, the switch-off of
the in-sample rows and the MDE at the actual counts.  No raw file, no network."""
import numpy as np
import pandas as pd
import pytest

from qune_research.nyse import nyse_trading_days
from src import checks
from src.config import MIN_POSITIVE_MONTHS, TIINGO_COVERAGE
from tests.toy import toy_closes, toy_cpi


def _closes(start, end, seed=3):
    bars = nyse_trading_days(start, end)
    return toy_closes(bars, seed=seed)


def test_d0_coverage_and_halt_flags():
    tiingo = _closes("2002-07-01", "2019-01-31")
    alpaca = _closes("2018-08-01", "2026-10-02", seed=4)
    out = checks.d0({"IEF": tiingo["IEF"], "SPY": tiingo["SPY"]},
                    {"SPY": alpaca["SPY"], "IEF": alpaca["IEF"], "BIL": alpaca["IEF"]})
    assert out["pass"] and not out["halt_ief"]
    assert out["files"]["tiingo_IEF"]["window"] == {"start": TIINGO_COVERAGE[0], "end": TIINGO_COVERAGE[1]}
    # four missing days in a row in Tiingo SPY: regime unavailable in-sample, IEF untouched
    spy = tiingo["SPY"].drop(tiingo["SPY"].index[1000:1004])
    out = checks.d0({"IEF": tiingo["IEF"], "SPY": spy}, {"SPY": alpaca["SPY"], "IEF": alpaca["IEF"], "BIL": alpaca["IEF"]})
    assert out["regime_unavailable_insample"] and not out["halt_ief"] and not out["pass"]
    # IEF starting after 2002-07-31 is a halt ground
    late = tiingo["IEF"].loc["2002-08-05":]
    out = checks.d0({"IEF": late, "SPY": tiingo["SPY"]}, {"SPY": alpaca["SPY"], "IEF": alpaca["IEF"], "BIL": alpaca["IEF"]})
    assert out["halt_ief"]


def test_d1_sign_agreement_is_one_for_identical_closes_and_lower_for_noisy_ones():
    tiingo = _closes("2015-06-01", "2018-12-31")
    out = checks.d1({"IEF": tiingo["IEF"], "SPY": tiingo["SPY"]}, tiingo["SPY"], tiingo["IEF"])
    assert out["sign_agreement_share"] == 1.0 and out["max_abs_difference"] == 0.0
    assert out["days_compared"] == len(nyse_trading_days("2016-01-04", "2018-12-31"))
    rng = np.random.default_rng(9)
    noisy = tiingo["SPY"] * np.exp(np.cumsum(rng.normal(0, 0.003, len(tiingo["SPY"]))))
    out = checks.d1({"IEF": tiingo["IEF"], "SPY": tiingo["SPY"]}, noisy, tiingo["IEF"])
    assert 0.5 < out["sign_agreement_share"] < 1.0 and out["max_abs_difference"] > 0
    assert out["gate"].startswith("none")


def test_d3_flags_on_holding_period_dates_and_rows_switch():
    tiingo = _closes("2002-07-01", "2019-01-31")
    bars = tiingo["IEF"].index
    flags = checks.regime_flags_for_window(tiingo["SPY"], tiingo["IEF"], toy_cpi("2001-01", "2019-12"), bars,
                                           "2003-07", "2018-12")
    assert len(flags) == 185 and str(flags.index[0]) == "2003-07" and str(flags.index[-1]) == "2018-11"
    assert set(flags.columns) >= {"signal_date", "rho_T1", "positive_T1", "rho_T2", "positive_T2", "positive_T3"}
    assert flags["positive_T1"].notna().all() and flags["positive_T2"].notna().all()
    sigma = {"sigma_d_per_month": 0.01, "months": 185, "share_months_d_nonzero": 0.3}
    out = checks.d3(flags, None, sigma)
    t1 = out["insample"]["T1"]
    assert t1["months"] == 185 and t1["positive_months"] + (185 - t1["positive_months"]) == 185
    assert t1["mde"]["per_year"] == pytest.approx(
        (1.645 + 0.842) * 0.01 * (1 / t1["positive_months"] + 1 / (185 - t1["positive_months"])) ** 0.5 * 12)
    assert t1["insample_rows_apply"] == (t1["positive_months"] >= MIN_POSITIVE_MONTHS)
    # fewer than twelve positive months switches the rows off
    few = flags.copy()
    few["positive_T1"] = False
    few.loc[few.index[:11], "positive_T1"] = True
    out = checks.d3(few, None, sigma)
    assert out["insample"]["T1"]["positive_months"] == 11 and not out["insample_rows_apply_T1"]
    # a missing T3 column is reported, not an error
    out = checks.d3(flags.drop(columns=["positive_T3", "cpi_12m_change_T3"]), None, sigma)
    assert out["insample"]["T3"] == {"status": "not run: series unavailable"}
