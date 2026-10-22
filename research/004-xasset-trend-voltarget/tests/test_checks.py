"""§5.3.1–§5.3.2 branches on constructed series (no network, no raw file):
the single retry, branch X on fetch failure and on coverage, the overlap gate,
the single-vendor skip, the halt rule, the §8.1 entry date, the stage order
and the ``reproduce.sh`` gates."""
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from qune_research.nyse import nyse_trading_days
from src import checks
from src.config import CASH_ETF, STUDY_DIR, SYMBOLS

DAYS = nyse_trading_days("2002-07-01", "2026-09-30")


def _frame(index: pd.DatetimeIndex, drift: float = 0.0, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(drift / 252, 0.01, len(index))))
    return pd.DataFrame({"close": close, "adjClose": close}, index=index)


def _vendor_factory(frames: dict, failures: dict | None = None):
    """``get_vendor(symbol, refetch)``: raises ``failures[symbol]`` times first."""
    left = dict(failures or {})
    calls = []

    def get_vendor(symbol, refetch=False):
        calls.append((symbol, refetch))
        if left.get(symbol, 0) > 0:
            left[symbol] -= 1
            raise RuntimeError("vendor unreachable")
        return frames[symbol]
    get_vendor.calls = calls
    return get_vendor


def test_entry_signal_date_follows_the_lookback_and_63_returns():
    full = DAYS
    assert checks.entry_signal_date(full) == "2003-12-31"
    late = DAYS[DAYS >= "2007-04-11"]                        # HYG-like: first bar 2007-04-11
    assert checks.entry_signal_date(late) == "2008-04-30"
    gld = DAYS[DAYS >= "2004-11-18"]
    assert checks.entry_signal_date(gld) == "2005-11-30"
    assert checks.entry_signal_date(DAYS[DAYS >= "2026-01-02"]) is None


def test_d0_passes_confirms_inception_and_entry():
    frames = {s: _frame(DAYS) for s in SYMBOLS + (CASH_ETF,)}
    frames["HYG"] = _frame(DAYS[DAYS >= "2007-04-11"])
    frames["GLD"] = _frame(DAYS[DAYS >= "2004-11-18"])
    d0 = checks.run_d0(_vendor_factory(frames))
    r = d0["symbols"]
    assert all(v["status"] == "pass" for v in r.values())
    assert r["HYG"]["inception"]["verdict"] == "confirmed" and r["HYG"]["entry"]["as_expected"]
    assert r["GLD"]["entry"]["signal_date"] == "2005-11-30" and r["GLD"]["entry"]["as_expected"]
    assert r["SPY"]["inception"]["verdict"].startswith("file starts at the fetch start")
    assert r["EEM"]["inception"]["verdict"] == "corrected to 2002-07" and not r["EEM"]["entry"]["as_expected"]
    assert r[CASH_ETF]["class"] == "cash" and "entry" not in r[CASH_ETF]
    assert r["SPY"]["attempts"] == [{"attempt": 1, "outcome": "coverage pass"}]


def test_d0_retries_once_then_excludes_on_fetch_failure():
    frames = {s: _frame(DAYS) for s in SYMBOLS + (CASH_ETF,)}
    get = _vendor_factory(frames, {"EEM": 1, "DBC": 2})
    d0 = checks.run_d0(get)
    assert d0["symbols"]["EEM"]["status"] == "pass" and len(d0["symbols"]["EEM"]["attempts"]) == 2
    assert ("EEM", True) in get.calls                          # the retry re-fetched
    assert d0["symbols"]["DBC"]["status"] == "excluded" and "fetch failed" in d0["symbols"]["DBC"]["reason"]
    assert len(d0["symbols"]["DBC"]["attempts"]) == 2


def test_d0_excludes_on_coverage_after_one_refetch():
    frames = {s: _frame(DAYS) for s in SYMBOLS + (CASH_ETF,)}
    gap = DAYS.drop(DAYS[(DAYS >= "2010-06-01") & (DAYS <= "2010-06-08")])   # six consecutive trading days
    frames["VNQ"] = _frame(gap)
    d0 = checks.run_d0(_vendor_factory(frames))
    v = d0["symbols"]["VNQ"]
    assert v["status"] == "excluded" and "coverage fail" in v["reason"]
    assert [a["outcome"] for a in v["attempts"]] == ["coverage fail", "coverage fail"]
    assert v["coverage"]["max_consecutive_missing_days"] == 6
    three = DAYS.drop(DAYS[(DAYS >= "2010-06-01") & (DAYS <= "2010-06-03")])
    frames["VNQ"] = _frame(three)
    assert checks.run_d0(_vendor_factory(frames))["symbols"]["VNQ"]["status"] == "pass"


def _d0_all_pass():
    frames = {s: _frame(DAYS) for s in SYMBOLS + (CASH_ETF,)}
    return checks.run_d0(_vendor_factory(frames)), frames


def test_d1_gate_skip_and_exclusion():
    d0, frames = _d0_all_pass()
    broker = {s: frames[s] for s in SYMBOLS}
    window = DAYS[(DAYS >= "2015-12-31") & (DAYS <= "2018-12-31")]
    drift = np.exp(0.003 / 252 * np.arange(len(window)))     # +0.30% p.a. on LQD: outside the gate
    broker["LQD"] = pd.DataFrame({"close": frames["LQD"].loc[window, "close"].to_numpy() / drift}, index=window)
    small = np.exp(0.0015 / 252 * np.arange(len(window)))    # +0.15% p.a. on HYG: passes, outside ex-ante
    broker["HYG"] = pd.DataFrame({"close": frames["HYG"].loc[window, "close"].to_numpy() / small}, index=window)
    broker_calls = []

    def get_broker(symbol):
        broker_calls.append(symbol)
        if symbol == "DBC":
            raise RuntimeError("no credentials")
        return broker[symbol]
    d1 = checks.run_d1(d0, lambda s: frames[s]["adjClose"], get_broker)
    r = d1["symbols"]
    assert r["SPY"]["status"] == "pass" and r["SPY"]["check"]["within_exante_expectation"]
    assert r["LQD"]["status"] == "excluded" and r["LQD"]["check"]["mean_diff_annual_vendor_minus_broker"] == pytest.approx(0.003, rel=0.05)
    assert r["HYG"]["status"] == "pass" and not r["HYG"]["check"]["within_exante_expectation"]
    assert r["DBC"]["status"] == "unchecked" and broker_calls.count("DBC") == 2
    assert CASH_ETF not in r
    ev = checks.evaluate(d0, d1)
    assert ev["excluded"] == {"LQD": r["LQD"]["reason"]} and ev["universe_size"] == 11
    assert ev["single_vendor_unchecked"] == ["DBC"]
    assert ev["per_class"]["credit"] == ["HYG"]                 # one credit instrument left -> halt (§5.3.5)
    assert ev["halt"] and "class credit" in ev["halt_reasons"][0]


def test_halt_on_more_than_three_exclusions_and_proceed_otherwise():
    d0, frames = _d0_all_pass()
    for s in ("SPY", "IWM", "SHY", "GLD"):
        d0["symbols"][s] = {"symbol": s, "class": "x", "status": "excluded", "reason": "branch X: test", "attempts": []}
    d1 = checks.run_d1(d0, lambda s: frames[s]["adjClose"], lambda s: frames[s])
    assert set(d1["symbols"]) == set(SYMBOLS) - {"SPY", "IWM", "SHY", "GLD"}
    ev = checks.evaluate(d0, d1)
    assert ev["halt"] and "4 symbols excluded" in ev["halt_reasons"][0]
    d0["symbols"]["GLD"]["status"] = "pass"
    d1 = checks.run_d1(d0, lambda s: frames[s]["adjClose"], lambda s: frames[s])
    ev = checks.evaluate(d0, d1)
    assert not ev["halt"] and ev["universe_size"] == 9 and ev["outcome"] == "proceed with 9 instruments"


def test_stages_write_files_in_order(tmp_path):
    frames = {s: _frame(DAYS) for s in SYMBOLS + (CASH_ETF,)}
    with pytest.raises(FileNotFoundError):
        checks.stage_d1(tmp_path, lambda s: frames[s]["adjClose"], lambda s: frames[s])
    d0 = checks.stage_d0(tmp_path, _vendor_factory(frames))
    assert json.loads((tmp_path / "d0.json").read_text())["symbols"]["SPY"]["status"] == "pass"
    report = checks.stage_d1(tmp_path, lambda s: frames[s]["adjClose"], lambda s: frames[s])
    assert report["D0"]["run_at_utc"] == d0["run_at_utc"] and not report["evaluation"]["halt"]
    text = (tmp_path / "data_checks.md").read_text()
    assert "proceed with 12 instruments" in text and "| SPY |" in text
    assert json.loads((tmp_path / "data_checks.json").read_text())["evaluation"]["universe_size"] == 12


@pytest.mark.parametrize("flag", ["--check", "--insample", "--oos"])
def test_reproduce_refuses_without_approval(flag, tmp_path):
    copy = tmp_path / "study"
    copy.mkdir()
    (copy / "reproduce.sh").write_text((STUDY_DIR / "reproduce.sh").read_text())
    proc = subprocess.run(["bash", "reproduce.sh", flag], cwd=copy, capture_output=True, text=True,
                          env={"PATH": os.environ["PATH"]})
    assert proc.returncode != 0 and "APPROVED" in proc.stdout + proc.stderr


def test_reproduce_refuses_a_second_oos_run_and_runs_nothing_without_checks(tmp_path):
    copy = tmp_path / "study"
    copy.mkdir()
    (copy / "reproduce.sh").write_text((STUDY_DIR / "reproduce.sh").read_text())
    (copy / "APPROVED").write_text("2099-01-01 test fixture, not an approval\n")
    (copy / "results" / "oos").mkdir(parents=True)
    proc = subprocess.run(["bash", "reproduce.sh", "--oos"], cwd=copy, capture_output=True, text=True)
    assert proc.returncode != 0 and "results/oos" in proc.stdout + proc.stderr
    # --insample is built but must not compute anything without the data-check evaluation
    # (the universe comes only from results/checks/data_checks.json)
    (copy / "src").mkdir()
    for name in ("__init__.py", "config.py", "data.py", "cash.py", "run.py"):
        (copy / "src" / name).write_text((STUDY_DIR / "src" / name).read_text())
    proc = subprocess.run(["bash", "reproduce.sh", "--insample"], cwd=copy, capture_output=True, text=True,
                          env={**os.environ, "PYTHON": sys.executable, "PYTHONPATH": str(STUDY_DIR.parent.parent)})
    assert proc.returncode != 0 and "data_checks.json" in proc.stdout + proc.stderr
    assert not (copy / "results" / "insample").exists()
