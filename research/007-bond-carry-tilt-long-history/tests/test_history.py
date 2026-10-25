"""Study 006 history run and episode (PREREGISTRATION.md §8, §9.4-9.6).
Constructed data only; no file in data/raw/ is read."""

import json
import subprocess

import numpy as np
import pandas as pd
import pytest
from src import episode, history, report
from src.config import COST_CASES, N_TRIALS_REGISTERED, TRIAL_IDS
from src.config006 import PROGRAMME_FAMILY, SUB_WINDOWS, TEST_FIRST_SIGNAL_MONTH, TEST_LAST_SIGNAL_MONTH, VOL_BAR
from src.synthetic import synthetic_indices

from tests.toy import toy_yields

PASS = {"C1": True, "C2": True, "C3": True, "C4": True}


def _fail(key):
    return {**PASS, key: False}


@pytest.fixture(scope="module")
def toy_history(tmp_path_factory):
    fred = toy_yields()
    out = tmp_path_factory.mktemp("history") / "history"
    summary = history.compute(fred, "2000-02", "2005-10", 0.05, out)
    return fred, out, summary


# --- §9.5 verdict table and labels ----------------------------------------------------------


def test_verdict_rows_and_precedence():
    ok = {"T2": PASS, "T3": PASS}
    v = history.history_verdict
    assert v(False, PASS, ok, 0.01) == "inconclusive (gate)"
    for key in PASS:
        assert v(True, _fail(key), ok, 0.01) == "not supported"
        assert v(True, _fail(key), {"T2": _fail(key), "T3": PASS}, 0.50) == "not supported"
        assert v(True, PASS, {"T2": PASS, "T3": _fail(key)}, 0.01) == "inconclusive (fragile)"
        assert v(True, PASS, {"T2": _fail(key), "T3": PASS}, 0.50) == "inconclusive (fragile)"
    assert v(True, PASS, ok, VOL_BAR + 1e-12) == "consistent with an edge, not detectable at the 2% bar"
    assert v(True, PASS, ok, VOL_BAR) == "supported in history; forward record pending"  # at the bar: stands


def test_labels():
    assert history.labels(VOL_BAR, 8) == [history.GATE_LABEL]
    assert history.labels(VOL_BAR + 0.01, 8) == [history.GATE_LABEL, "low-power check"]
    assert history.labels(0.05, 7) == [history.GATE_LABEL, "low-powered"]


# --- §5.4 / §9.6: observed Newey-West to i.i.d. ratio ---------------------------------------


def test_nw_iid_ratio_known_answer_at_zero_lags():
    rng = np.random.default_rng(1)
    x = pd.Series(rng.normal(0, 0.01, 400))
    r = history.nw_iid_ratio(x, lags=0)
    # HAC with no lags is the White standard error, sd(ddof 0) / sqrt(n)
    assert r["ratio"] == pytest.approx(np.sqrt((len(x) - 1) / len(x)), rel=1e-10)
    assert r["assumed"] == 0.972


def test_nw_iid_ratio_exceeds_one_under_positive_autocorrelation():
    rng = np.random.default_rng(2)
    e = rng.normal(0, 0.01, 2000)
    ar = np.zeros_like(e)
    for i in range(1, len(e)):
        ar[i] = 0.5 * ar[i - 1] + e[i]
    assert history.nw_iid_ratio(pd.Series(ar))["ratio"] > 1.3


# --- §9.4: programme-level family count -----------------------------------------------------


def test_programme_family_is_this_studys_three_trials():
    assert history.family_count() == 3
    assert PROGRAMME_FAMILY[-1][3] == 3


def test_family_dsr_equals_the_decision_dsr_when_the_counts_agree(toy_history):
    _, _, summary = toy_history
    base = summary["cost_cases"]["base"]
    fam = base["deflated_sharpe_programme_family"]
    assert fam["n_family"] == N_TRIALS_REGISTERED and fam["no_decision_weight"]
    for t in TRIAL_IDS:
        assert fam["dsr"][t]["dsr"] == pytest.approx(
            base["deflated_sharpe"][t][f"N{N_TRIALS_REGISTERED}"]["dsr"], abs=1e-15
        )


# --- the wrapper agrees with Study 002's engine ---------------------------------------------


def test_strategy_results_match_run_window_period_by_period(toy_history):
    fred, out, summary = toy_history
    from src.calendar import build_schedule

    schedule = build_schedule(fred["DGS10"], fred["DTB3"], "2000-02", "2005-10")
    indices = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    for case, cost in COST_CASES.items():
        results, _ = history.strategy_results(indices, fred, schedule, summary["weight_b3"], cost)
        monthly = pd.read_csv(out / f"monthly_{case}.csv", index_col=0)
        for name, frame in results.items():
            assert frame["r"].to_numpy() == pytest.approx(monthly[name].dropna().to_numpy(), abs=1e-15)


def test_history_summary_is_complete_and_serialisable(toy_history):
    _, out, summary = toy_history
    assert set(summary["criteria"]) == {"C1", "C2", "C3", "C4"}
    assert set(summary["criteria_T2_T3"]) == {"T2", "T3"}
    assert summary["verdict_T1"] in {
        "not supported",
        "inconclusive (fragile)",
        "consistent with an edge, not detectable at the 2% bar",
        "supported in history; forward record pending",
    }
    assert history.GATE_LABEL in summary["labels"]
    for case in COST_CASES:
        c = summary["cost_cases"][case]
        assert set(c["sub_windows"]) <= set(SUB_WINDOWS)
        assert c["subperiods"] is not None  # the engine's own, by signal month (§16)
        assert "subperiods_by_execution_month" in c
        for t in TRIAL_IDS:
            assert c["nw_iid_ratio_vs_B3"][t]["ratio"] > 0
    summary = {**summary, "run_at_utc": "2099-01-01T00:00:00Z", "provenance": {"git_commit": "toy"}}
    report.write_json(out / "summary.json", summary)
    history.write_verdict(summary, out)
    assert "Verdict for T1" in (out / "verdict.md").read_text()


def test_sub_windows_partition_the_test_window():
    first = pd.Period(TEST_FIRST_SIGNAL_MONTH, "M") + 1  # first execution month
    last = pd.Period(TEST_LAST_SIGNAL_MONTH, "M")  # the last period starts in December 2018
    spans = sorted((pd.Period(a, "M"), pd.Period(b, "M")) for a, b in SUB_WINDOWS.values())
    assert spans[0][0] == first and spans[-1][1] == last
    assert spans[1][0] == spans[0][1] + 1
    assert sum((b - a).n + 1 for a, b in spans) == 593


def test_sub_windows_count_periods_by_execution_month(toy_history):
    fred, _, _ = toy_history
    from src.calendar import build_schedule

    schedule = build_schedule(fred["DGS10"], fred["DTB3"], "2000-02", "2005-10")
    indices = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    results, returns = history.strategy_results(indices, fred, schedule, 0.5, 2e-4)
    windows = {"a": ("2000-03", "2002-12"), "b": ("2003-01", "2005-10")}
    out = history.subwindow_metrics(results, returns, schedule, windows)
    start = schedule["execution_date"].iloc[:-1].dt.to_period("M")
    for name, (lo, hi) in windows.items():
        expected = int(((start >= pd.Period(lo, "M")) & (start <= pd.Period(hi, "M"))).sum())
        assert out[name]["B1"]["periods"] == expected
    assert out["a"]["B1"]["periods"] + out["b"]["B1"]["periods"] == len(schedule) - 1


def test_compute_checks_the_period_count(tmp_path):
    with pytest.raises(ValueError, match="expected"):
        history.compute(toy_yields(), "2000-02", "2005-10", 0.05, tmp_path / "h", expected_periods=593)


# --- refusals ------------------------------------------------------------------------------


def test_history_refuses_without_gate_or_volcheck_and_runs_once(tmp_path):
    gate_dir, vol_dir, out = tmp_path / "gate", tmp_path / "volcheck", tmp_path / "history"
    with pytest.raises(SystemExit, match="passed gate"):
        history.main([], gate_dir, vol_dir, out)
    gate_dir.mkdir()
    (gate_dir / "gate.json").write_text(json.dumps({"outcome": "FAIL: study halts as inconclusive (§5.3.6)"}))
    with pytest.raises(SystemExit, match="passed gate"):
        history.main([], gate_dir, vol_dir, out)
    (gate_dir / "gate.json").write_text(json.dumps({"outcome": "PASS"}))
    with pytest.raises(SystemExit, match="volcheck"):
        history.main([], gate_dir, vol_dir, out)
    vol_dir.mkdir()
    (vol_dir / "volcheck.json").write_text(json.dumps({"sigma_annual": 0.05}))
    out.mkdir()
    with pytest.raises(SystemExit, match="once"):
        history.main([], gate_dir, vol_dir, out)


def _git(cwd, *args):
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
            "HOME": str(cwd),
            "PATH": "/usr/bin:/bin",
        },
    )


def test_episode_needs_the_committed_note_and_runs_once(tmp_path):
    study, hist, out = tmp_path / "study", tmp_path / "history", tmp_path / "episode"
    study.mkdir()
    with pytest.raises(SystemExit, match="frozen w"):
        episode.main([], hist, out, study)
    hist.mkdir()
    (hist / "summary.json").write_text(json.dumps({"weight_b3": 0.75}))
    assert episode.frozen_weight(hist) == 0.75
    with pytest.raises(SystemExit, match="not committed"):
        episode.main([], hist, out, study)
    _git(study, "init", "-q")
    (study / "README.md").write_text("# Study 006\n\n## Verdict\n")
    with pytest.raises(SystemExit, match="not committed"):  # written, not committed
        episode.main([], hist, out, study)
    _git(study, "add", "README.md")
    _git(study, "commit", "-q", "-m", "note")
    assert episode.note_committed(study)
    (study / "README.md").write_text("# Study 006\n\n## Verdict\nedited\n")
    assert not episode.note_committed(study)  # changed since the commit
    _git(study, "checkout", "README.md")
    out.mkdir()
    with pytest.raises(SystemExit, match="once"):
        episode.main([], hist, out, study)


def test_episode_compute_on_toy_bars(tmp_path):
    fred = toy_yields()
    synthetic = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    actual = {k: v * (1 + 1e-4) for k, v in synthetic.items()}  # stand-in bars, constructed
    summary = episode.compute(fred, actual, 0.6, "2003-01", "2005-10", tmp_path / "episode")
    assert summary["heading"] == episode.HEADING
    for side in ("actual", "synthetic"):
        assert summary[side]["weight_b3"] == 0.6  # frozen, never recomputed
        assert (tmp_path / "episode" / side / "monthly_base.csv").exists()
    assert "criteria" not in summary and "verdict_T1" not in summary
