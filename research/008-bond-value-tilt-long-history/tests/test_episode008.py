"""Study 008 2019-2026 episode (PREREGISTRATION.md §8.2, §6.1, §6.4, §11.2) on
constructed data only; no file in data/raw/ is read.  A constructed CPI gap
puts two undefined real-yield months inside the toy episode, so the hold rule
is exercised end to end."""

import json
import subprocess

import numpy as np
import pandas as pd
import pytest
from src import episode008
from src.config008 import TRIAL_IDS
from src.synthetic import synthetic_indices

from tests.test_history008 import TOY_RANK_N, _toy_cpi_and_availability
from tests.toy import toy_yields

FROZEN = {"T1": 0.6, "T1a": 0.55, "T1b": 0.65}
TOY_EPISODE = ("2000-01", "2004-01", "2005-10")
GAP = "2004-03"  # CPI(2004-03) missing: signal months 2004-04 (k) and 2005-04 (k - 12) are undefined
UNDEFINED = ["2004-04", "2005-04"]


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"})


@pytest.fixture(scope="module")
def toy_episode(tmp_path_factory):
    fred = toy_yields()
    cpi, availability = _toy_cpi_and_availability(fred)
    cpi = {s: v.copy() for s, v in cpi.items()}
    for v in cpi.values():
        v.loc[pd.Timestamp(f"{GAP}-01")] = np.nan
    synthetic = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    actual = {k: v * (1 + 1e-4) for k, v in synthetic.items()}  # stand-in bars, constructed
    out = tmp_path_factory.mktemp("episode") / "episode"
    summary = episode008.compute(fred, cpi, availability, actual, FROZEN, *TOY_EPISODE, out, rank_n=TOY_RANK_N)
    return out, summary


def test_episode_runs_both_sides_at_the_frozen_weights_without_a_verdict(toy_episode):
    out, s = toy_episode
    assert s["heading"] == episode008.HEADING and "known_window_note" in s
    assert "criteria" not in s and "verdict" not in s
    for side in ("actual", "synthetic"):
        side_summary = s[side]
        assert side_summary["weight_b3_frozen_from_history"] == FROZEN  # frozen, never recomputed
        base = side_summary["cost_cases"]["base"]
        for k in TRIAL_IDS:
            assert base["descriptive"][k]["B3"]["fraction_in_ief"] == pytest.approx(FROZEN[k])
            assert base["descriptive"][k]["T"]["periods"] == side_summary["holding_periods"]
        assert (out / side / "monthly_base.csv").exists() and (out / side / "metrics_stress.csv").exists()
    assert s["actual"]["holding_periods"] == s["synthetic"]["holding_periods"]


def test_undefined_months_hold_on_both_sides(toy_episode):
    out, s = toy_episode
    assert s["undefined_real_yield_months_in_episode"] == {"CPIAUCNS": UNDEFINED, "CPILFENS": UNDEFINED}
    for side in ("actual", "synthetic"):
        assert s[side]["hold_periods"] == dict.fromkeys(TRIAL_IDS, UNDEFINED)
        m = pd.read_csv(out / side / "monthly_stress.csv", index_col=0)
        for k in TRIAL_IDS:
            held = m[m[f"hold_{k}"]]
            assert list(held.index) == UNDEFINED
            assert (m[f"w_{k}"].between(0, 1)).all() and m[f"w_{k}"].notna().all()


def test_signal_weights_are_the_same_on_both_sides(toy_episode):
    """The weights come from FRED and the CPI files only; on the hold months
    the drifted weights differ with the legs, elsewhere they are identical."""
    out, _ = toy_episode
    a = pd.read_csv(out / "actual" / "monthly_base.csv", index_col=0)
    b = pd.read_csv(out / "synthetic" / "monthly_base.csv", index_col=0)
    signal = ~a["hold_T1"]
    for k in TRIAL_IDS:
        pd.testing.assert_series_equal(a.loc[signal, f"w_{k}"], b.loc[signal, f"w_{k}"], check_names=False)


def test_rank_keeps_expanding_and_last_month_weights_are_written(toy_episode):
    _, s = toy_episode
    assert s["rank_history_months_at_episode_end"] == 70  # 2000-01 to 2005-10 on the toy calendar
    last = s["weights_at_last_signal_month_for_forward_record"]
    assert last["signal_month"] == "2005-10"
    assert last["n_defined_CPIAUCNS"] == last["n_defined_CPILFENS"] == 70 - len(UNDEFINED)
    for k in TRIAL_IDS:
        assert 0.0 <= last[k] <= 1.0 and last[k] == round(last[k], 4)
    assert np.isfinite(last["r_CPIAUCNS"]) and np.isfinite(last["r_CPILFENS"])


def test_forward_start_reports_none_on_an_undefined_month():
    months = pd.period_range("2005-01", periods=3, freq="M")
    paths = pd.DataFrame({"w_T1": [0.1, 0.2, np.nan], "w_T1a": [0.3, 0.4, np.nan], "w_T1b": [0.5, 0.6, np.nan],
                          "r_CPIAUCNS": [0.01, 0.02, np.nan], "r_CPILFENS": [0.01, 0.02, np.nan]}, index=months)
    out = episode008.forward_start(paths, months[-1], pd.Timestamp("2005-03-31"))
    assert out["T1"] is None and out["r_CPIAUCNS"] is None and out["n_defined_CPIAUCNS"] == 2


def test_frozen_weights_need_every_trial(tmp_path):
    (tmp_path / "summary.json").write_text(json.dumps({"weight_b3": {"T1": 0.5}}))
    with pytest.raises(ValueError, match="no frozen weight"):
        episode008.frozen_weights(tmp_path)
    (tmp_path / "summary.json").write_text(json.dumps({"weight_b3": FROZEN}))
    assert episode008.frozen_weights(tmp_path) == FROZEN


def test_main_needs_history_and_the_committed_note_and_runs_once(tmp_path):
    study, hist, out = tmp_path / "study", tmp_path / "history", tmp_path / "episode"
    study.mkdir()
    with pytest.raises(SystemExit, match="frozen w"):
        episode008.main([], hist, out, study)
    hist.mkdir()
    (hist / "summary.json").write_text(json.dumps({"weight_b3": FROZEN}))
    with pytest.raises(SystemExit, match="not committed"):
        episode008.main([], hist, out, study)
    _git(study, "init", "-q")
    (study / "README.md").write_text("# Study 008\n\n## Verdict\n")
    _git(study, "add", "README.md")
    _git(study, "commit", "-q", "-m", "note")
    out.mkdir()
    with pytest.raises(SystemExit, match="once"):
        episode008.main([], hist, out, study)


def test_frozen_weights_follow_the_gates_dropped_trials(tmp_path):
    """After the separate code review (2026-10-25): a trial dropped at the gate
    has no frozen weight and no episode return; a weight for it is refused."""
    two = {"T1": 0.6, "T1b": 0.65}
    (tmp_path / "summary.json").write_text(json.dumps({"weight_b3": two, "dropped_at_gate": ["T1a"]}))
    assert episode008.frozen_weights(tmp_path) == two
    (tmp_path / "summary.json").write_text(json.dumps({"weight_b3": FROZEN, "dropped_at_gate": ["T1a"]}))
    with pytest.raises(ValueError, match="dropped at the gate"):
        episode008.frozen_weights(tmp_path)


def test_run_side_runs_only_the_trials_with_a_frozen_weight(tmp_path):
    fred = toy_yields()
    cpi, availability = _toy_cpi_and_availability(fred)
    synthetic = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    s = episode008.compute(fred, cpi, availability, synthetic, {"T1": 0.6, "T1b": 0.65}, *TOY_EPISODE,
                           tmp_path / "e", rank_n=TOY_RANK_N)
    for side in ("actual", "synthetic"):
        assert s[side]["trials_run"] == ["T1", "T1b"]
        assert "T1a" not in s[side]["cost_cases"]["base"]["descriptive"]
