"""Study 008 §13 tests (1), (5) and (7) for the gate and overlap module: import
graph; weight paths from constructed yields and CPI files (first weights, the
rank on the same row, the CPI series of each trial, the availability rule, an
undefined month holding and leaving the rank history, no look-ahead); the
decision rule of §5.3; the overlap correlations reading only the month and one
weight or holding column.  Constructed data only; no file in data/raw/ is read."""

import numpy as np
import pandas as pd
import pytest
from src import gate008
from src.calendar import build_schedule
from src.config008 import FIRST_WEIGHT_MONTH, TRIAL_IDS

from tests.test_carry_rank import _reachable

# --- test 1: the gate cannot see a rule return ------------------------------------------------


def test_gate008_never_reaches_the_engines():
    reached = _reachable("gate008")
    assert not {"backtest", "tilt", "report", "stats"} & reached, reached
    assert {"real_yield", "carry_rank", "calendar", "gate", "gate007"} <= reached


# --- constructed yields, CPI files and availability table ---------------------------------------


@pytest.fixture(scope="module")
def constructed():
    days = pd.bdate_range("1969-07-01", "1983-12-31")
    rng = np.random.default_rng(80)
    dgs10 = pd.Series(np.clip(6.0 + np.cumsum(rng.normal(0, 0.03, len(days))), 1.0, 15.0), index=days)
    dtb3 = pd.Series(np.clip(5.0 + np.cumsum(rng.normal(0, 0.04, len(days))), 0.1, 15.0), index=days)
    schedule = build_schedule(dgs10, dtb3, "1969-07", "1983-11")
    first = pd.date_range("1967-01-01", "1983-12-01", freq="MS")
    head = pd.Series(30.0 * np.exp(np.cumsum(rng.normal(0.004, 0.003, len(first)))), index=first, name="CPIAUCNS")
    core = pd.Series(30.0 * np.exp(np.cumsum(rng.normal(0.004, 0.002, len(first)))), index=first, name="CPILFENS")
    months = schedule.index
    availability = pd.DataFrame(
        {
            "signal_month": [str(m) for m in months],
            "signal_date": schedule["signal_date"].dt.strftime("%Y-%m-%d").to_numpy(),
            "CPIAUCNS_m1_published_by_t": "1",
            "CPIAUCNS_k": [str(m - 1) for m in months],
            "CPIAUCNS_branch": "release_date_read",
            "CPILFENS_m1_published_by_t": "",
            "CPILFENS_k": [str(m - 1) for m in months],
            "CPILFENS_branch": "assumed_known",
        }
    )
    return dgs10, dtb3, schedule, {"CPIAUCNS": head, "CPILFENS": core}, availability


def _percentile(values: np.ndarray, i: int) -> float:
    seen = values[: i + 1]
    return (np.count_nonzero(seen < values[i]) + 0.5 * np.count_nonzero(seen[:i] == values[i])) / i


def test_weight_paths_first_weights_and_bounds(constructed):
    dgs10, _, schedule, cpi, availability = constructed
    paths = gate008.weight_paths(dgs10, cpi, availability, schedule)
    assert paths.index.equals(schedule.index)
    assert paths["w_T1"].first_valid_index() == schedule.index[59]
    assert paths["w_T1a"].first_valid_index() == schedule.index[59]
    assert paths["w_T1b"].first_valid_index() == schedule.index[119]
    for k in TRIAL_IDS:
        w = paths[f"w_{k}"].dropna()
        assert ((w >= 0) & (w <= 1)).all()


def test_weights_are_the_real_yield_percentiles_of_their_own_cpi_series(constructed):
    dgs10, _, schedule, cpi, availability = constructed
    paths = gate008.weight_paths(dgs10, cpi, availability, schedule)
    i = 130
    r_head, r_core = paths["r_CPIAUCNS"].to_numpy(), paths["r_CPILFENS"].to_numpy()
    assert paths["w_T1"].iloc[i] == pytest.approx(_percentile(r_head, i))
    assert paths["w_T1a"].iloc[i] == pytest.approx(_percentile(r_core, i))
    window = r_head[i - 119 : i + 1]
    expected_b = (np.count_nonzero(window < r_head[i]) + 0.5 * np.count_nonzero(window[:-1] == r_head[i])) / 119
    assert paths["w_T1b"].iloc[i] == pytest.approx(expected_b)
    # r = DGS10_t / 100 - (CPI(m-1) / CPI(m-13) - 1), at the signal date of the row
    m, t = schedule.index[i], schedule["signal_date"].iloc[i]
    head = cpi["CPIAUCNS"]
    pi = head.loc[(m - 1).to_timestamp()] / head.loc[(m - 13).to_timestamp()] - 1
    assert r_head[i] == pytest.approx(dgs10.loc[t] / 100 - pi)


def test_late_release_switches_k_and_core_follows_the_headline(constructed):
    dgs10, _, schedule, cpi, availability = constructed
    late = availability.copy()
    j = 70
    late.loc[j, "CPIAUCNS_k"] = str(schedule.index[j] - 2)  # CPI(m-1) published after t (§6.1)
    paths = gate008.weight_paths(dgs10, cpi, late, schedule)
    assert paths["k_CPIAUCNS"].iloc[j] == str(schedule.index[j] - 2)
    assert paths["k_CPILFENS"].iloc[j] == str(schedule.index[j] - 2)  # §16 (a): no core vintage -> headline's release
    assert paths["k_CPIAUCNS"].iloc[j + 1] == str(schedule.index[j + 1] - 1)


def test_missing_index_makes_the_month_undefined_and_leaves_the_rank_history(constructed):
    dgs10, _, schedule, cpi, availability = constructed
    j = 100
    gap = {s: c.copy() for s, c in cpi.items()}
    gap["CPIAUCNS"].loc[(schedule.index[j] - 1).to_timestamp()] = np.nan  # never published (§16 (b))
    paths = gate008.weight_paths(dgs10, gap, availability, schedule)
    assert np.isnan(paths["r_CPIAUCNS"].iloc[j]) and np.isnan(paths["w_T1"].iloc[j])
    assert np.isnan(paths["w_T1b"].iloc[j])
    assert not np.isnan(paths["w_T1a"].iloc[j])  # the core series is unaffected
    # the next month ranks over the defined values only: n counts defined real yields
    r = paths["r_CPIAUCNS"].to_numpy()
    defined = r[~np.isnan(r)]
    pos = int(np.count_nonzero(~np.isnan(r[: j + 2]))) - 1
    assert paths["w_T1"].iloc[j + 1] == pytest.approx(_percentile(defined, pos))


def test_weight_paths_refuse_a_month_missing_from_the_availability_table(constructed):
    dgs10, _, schedule, cpi, availability = constructed
    with pytest.raises(ValueError, match="availability table"):
        gate008.weight_paths(dgs10, cpi, availability.drop(index=12), schedule)


def test_no_weight_path_looks_ahead(constructed):
    dgs10, _, schedule, cpi, availability = constructed
    base = gate008.weight_paths(dgs10, cpi, availability, schedule)
    cols = [f"w_{k}" for k in TRIAL_IDS] + ["r_CPIAUCNS", "r_CPILFENS"]
    for i in (65, 125, 150):
        m, d = schedule.index[i], schedule["signal_date"].iloc[i]
        p10 = dgs10.copy()
        p10.loc[p10.index > d] = 14.0
        pc = {s: c.copy() for s, c in cpi.items()}
        for c in pc.values():
            c.loc[c.index >= m.to_timestamp()] *= 3.0  # the index for month m and later is never used at m
        perturbed = gate008.weight_paths(p10, pc, availability, schedule)
        pd.testing.assert_frame_equal(perturbed[cols].iloc[: i + 1], base[cols].iloc[: i + 1])


def test_check_first_weights(constructed):
    dgs10, _, schedule, cpi, availability = constructed
    paths = gate008.weight_paths(dgs10, cpi, availability, schedule)
    # constructed real yields start in 1969-07 as the real ones do: 60th in 1974-06, 120th in 1979-06
    assert gate008.check_first_weights(paths) == FIRST_WEIGHT_MONTH
    shifted = paths.copy()
    shifted.index = shifted.index + 1
    with pytest.raises(ValueError, match="data step"):
        gate008.check_first_weights(shifted)


# --- §5.3 decision ------------------------------------------------------------------------------


def _g(passes: dict[str, bool]) -> dict:
    return {k: {"G1_pass": v} for k, v in passes.items()}


def test_decision_passes_and_drops_failed_companions():
    d = gate008.decide(_g({"T1": True, "T1a": False, "T1b": True}))
    assert d["outcome"] == "PASS" and d["proceeding_trials"] == ["T1", "T1b"]
    assert d["dropped_trials"] == {"T1a": "inconclusive (gate)"}


def test_decision_halts_when_t1_fails():
    d = gate008.decide(_g({"T1": False, "T1a": True, "T1b": True}))
    assert d["outcome"].startswith("HALT") and "T1" in d["dropped_trials"]


# --- test 5: the overlap check reads only the weight and holding columns ------------------------


def test_read_overlap_column_reads_only_month_and_one_column(tmp_path):
    path = tmp_path / "research" / "007-x" / "results" / "history" / "monthly_base.csv"
    path.parent.mkdir(parents=True)
    path.write_text("month,execution_date,w_T1,T1,B1\n1974-06,1974-07-01,0.25,not-a-number,x\n1974-07,1974-08-01,0.5,y,z\n")
    s, meta = gate008.read_overlap_column(path, "w_T1")
    assert list(s) == [0.25, 0.5] and s.index.equals(pd.period_range("1974-06", periods=2, freq="M"))
    assert meta["column_read"] == "w_T1" and meta["rows"] == 2 and len(meta["sha256"]) == 64
    assert meta["file"] == "007-x/results/history/monthly_base.csv"


def test_overlap_correlations_known_answers_and_flag():
    months = pd.period_range("1974-06", periods=200, freq="M")
    rng = np.random.default_rng(5)
    w007 = pd.Series(rng.uniform(0, 1, 200), index=months)
    h006 = pd.Series(np.where(rng.uniform(0, 1, 200) > 0.3, "IEF", "BIL"), index=months)
    in_leg = (h006 == "IEF").astype(float)
    w = pd.DataFrame({"w_T1": w007, "w_T1a": 1 - w007, "w_T1b": in_leg}, index=months)
    w.iloc[:60, 2] = np.nan  # T1b's shorter window
    out = gate008.overlap_correlations(w, w007, h006, months)
    assert out["by_trial"]["T1"]["corr_with_007_T1_weight"] == pytest.approx(1.0)
    assert out["by_trial"]["T1a"]["corr_with_007_T1_weight"] == pytest.approx(-1.0)
    assert out["by_trial"]["T1b"]["corr_with_006_T1_in_leg"] == pytest.approx(1.0)
    assert out["by_trial"]["T1b"]["periods"] == 140 and out["by_trial"]["T1"]["periods"] == 200
    assert out["flagged_studies_for_T1"] == ["007"] and out["headline_states_not_independent"]
    quiet = gate008.overlap_correlations(w.assign(w_T1=rng.uniform(0, 1, 200)), w007, h006, months)
    assert quiet["flagged_studies_for_T1"] == [] and not quiet["headline_states_not_independent"]


def test_overlap_correlations_refuse_gaps_and_unknown_labels():
    months = pd.period_range("1974-06", periods=10, freq="M")
    w = pd.DataFrame({f"w_{k}": np.linspace(0, 1, 10) for k in TRIAL_IDS}, index=months)
    w007 = pd.Series(np.linspace(1, 0, 10), index=months)
    with pytest.raises(ValueError, match="missing"):
        gate008.overlap_correlations(w, w007.iloc[1:], pd.Series(["IEF"] * 10, index=months), months)
    with pytest.raises(ValueError, match="labels"):
        gate008.overlap_correlations(w, w007, pd.Series(["IEF"] * 9 + ["SPY"], index=months), months)


def test_read_overlap_column_passes_usecols_to_the_reader(tmp_path, monkeypatch):
    """After the separate code review (2026-10-25): the test above passes even
    without ``usecols``; this one fails unless only the month and the one
    column are requested from the reader."""
    path = tmp_path / "research" / "007-x" / "results" / "history" / "monthly_base.csv"
    path.parent.mkdir(parents=True)
    path.write_text("month,w_T1,T1\n1974-06,0.25,0.01\n")
    calls = []
    real = pd.read_csv

    def spy(*args, **kwargs):
        calls.append(kwargs.get("usecols"))
        return real(*args, **kwargs)

    monkeypatch.setattr(gate008.pd, "read_csv", spy)
    gate008.read_overlap_column(path, "w_T1")
    assert calls == [["month", "w_T1"]]
