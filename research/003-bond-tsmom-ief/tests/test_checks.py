"""§5.2 cash accrual and §5.3 data checks D0 and D2 on toy data only."""
import json

import numpy as np
import pandas as pd
import pytest

from src import checks
from src.bey import discount_to_bey
from src.calendar import nyse_trading_days
from src.cash import cash_index, cash_returns
from src.config import BIL_EXPENSE_RATIO, CASH_GAP_EXANTE
from tests.toy import toy_bars, toy_bil, toy_dtb3


def test_cash_accrual_formula_over_a_weekend_and_a_gap():
    dtb3 = pd.Series([2.0, np.nan, 2.4, 2.2],
                     index=pd.to_datetime(["2010-01-04", "2010-01-05", "2010-01-06", "2010-01-11"]))
    out = cash_returns(dtb3)
    assert out.index.tolist() == list(pd.to_datetime(["2010-01-06", "2010-01-11"]))
    bey = discount_to_bey(0.02)
    assert out["r"].iloc[0] == pytest.approx(bey * 2 / 365 - BIL_EXPENSE_RATIO * 2 / 365)
    assert out["r"].iloc[1] == pytest.approx(discount_to_bey(0.024) * 5 / 365 - BIL_EXPENSE_RATIO * 5 / 365)
    tri = cash_index(dtb3)
    assert tri.index[0] == pd.Timestamp("2010-01-04") and tri.iloc[0] == 1.0
    assert tri.iloc[-1] == pytest.approx((1 + out["r"].iloc[0]) * (1 + out["r"].iloc[1]))
    assert discount_to_bey(0.05) == pytest.approx(365 * 0.05 / (360 - 91 * 0.05))


def test_coverage_check_passes_on_a_complete_series_and_counts_gaps():
    trading = nyse_trading_days("2002-07-31", "2003-12-31")
    full = trading.insert(0, pd.Timestamp("2002-07-26"))
    d0 = checks.coverage_check(full, "2002-07-31", "2003-12-31")
    assert d0["all_pass"] and d0["missing_days"] == [] and d0["bars_present"] == d0["nyse_trading_days"]
    gappy = full.drop(trading[10:13])                                 # three consecutive missing: allowed
    assert checks.coverage_check(gappy, "2002-07-31", "2003-12-31")["checks"]["max_consecutive_missing_days"] == \
        {"value": 3, "threshold": "<= 3", "pass": True}
    broken = full.drop(trading[10:14])                                # four: a halt ground
    d0 = checks.coverage_check(broken, "2002-07-31", "2003-12-31")
    assert not d0["all_pass"] and len(d0["missing_days"]) == 4
    late = trading[1:]                                                # first bar after 2002-07-31
    assert not checks.coverage_check(late, "2002-07-31", "2003-12-31")["checks"]["first_bar"]["pass"]
    extra = full.insert(5, pd.Timestamp("2002-12-25"))                # a bar on Christmas
    assert checks.coverage_check(extra, "2002-07-31", "2003-12-31")["extra_bars_on_rule_calendar_closures"] == ["2002-12-25"]


def test_cash_level_check_passes_a_faithful_toy_bill_fund_and_fails_a_drifting_one():
    bars = toy_bars()
    dtb3 = toy_dtb3()
    tri = cash_index(dtb3)
    faithful = checks.cash_level_check(toy_bil(bars, dtb3), tri, "2001-01-02", "2007-12-31")
    b1 = faithful["checks"]["B1"]
    assert b1["pass"] and abs(b1["value"]) < 0.0030 and faithful["all_pass"]
    assert b1["exante_central_estimate"] == CASH_GAP_EXANTE["central_estimate"]
    assert faithful["checks"]["B2"]["pass"] is None                   # descriptive, never a gate
    drifting = checks.cash_level_check(toy_bil(bars, dtb3, drift_annual=0.005), tri, "2001-01-02", "2007-12-31")
    assert not drifting["checks"]["B1"]["pass"] and drifting["checks"]["B1"]["value"] == pytest.approx(0.005, rel=0.1)
    assert not drifting["all_pass"]
    s = faithful["statistics"]
    assert set(s["mean_diff_annual_by_year"]) == {str(y) for y in range(2001, 2008)}
    assert s["days"] == len(bars[(bars >= "2001-01-02") & (bars <= "2007-12-31")]) - 1


def test_run_writes_every_artifact_and_respects_the_committed_decision(tmp_path):
    bars = toy_bars()
    dtb3 = toy_dtb3()
    decision = {"outcome": "vendor_accepted", "reason": "toy",
                "cash_check_window": {"start": "2001-01-02", "end": "2007-12-31", "series": "Tiingo BIL adjClose"}}
    ief_bars = nyse_trading_days("2002-07-26", "2018-12-31")
    passed = checks.run(tmp_path, decision, ief_bar_index=ief_bars, bil_close=toy_bil(bars, dtb3), dtb3=dtb3)
    report = json.loads((tmp_path / "data_checks.json").read_text())
    assert passed and report["all_pass"] and report["D0"]["all_pass"] and report["D2"]["all_pass"]
    assert report["D2"]["statistics"]["first_return_date"] >= "2001-01-03"
    assert report["decision"] == decision and report["exante"] == CASH_GAP_EXANTE
    assert (tmp_path / "data_checks.md").exists() and (tmp_path / "cash_check.png").stat().st_size > 10_000
    failing = checks.run(tmp_path / "fail", decision, ief_bar_index=ief_bars[5:],
                         bil_close=toy_bil(bars, dtb3), dtb3=dtb3)
    assert not failing
    assert "halts permanently" in (tmp_path / "fail" / "data_checks.md").read_text()


def test_run_refuses_without_the_committed_decision_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        checks.vendor_decision(tmp_path / "missing.json")
