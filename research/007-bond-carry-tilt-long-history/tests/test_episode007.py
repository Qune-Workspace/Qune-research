"""Study 007 2019-2026 episode (PREREGISTRATION.md §8.2) on constructed data
only; no file in data/raw/ is read."""

import json
import subprocess

import pytest
from src import episode007
from src.config007 import TRIAL_IDS
from src.synthetic import synthetic_indices

from tests.toy import toy_yields

TOY_MIN_HISTORY = {"T1": 12, "T1a": 6, "T1b": 24}
FROZEN = {"T1": 0.6, "T1a": 0.55, "T1b": 0.65, "T2": 0.7, "T3": 0.8}


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"})


@pytest.fixture(scope="module")
def toy_episode(tmp_path_factory):
    fred = toy_yields()
    synthetic = synthetic_indices(fred["DGS10"], fred["DTB3"], fred["DGS7"])
    actual = {k: v * (1 + 1e-4) for k, v in synthetic.items()}  # stand-in bars, constructed
    out = tmp_path_factory.mktemp("episode") / "episode"
    summary = episode007.compute(fred, actual, FROZEN, "2000-01", "2004-01", "2005-10", out,
                                 min_history=TOY_MIN_HISTORY)
    return out, summary


def test_episode_runs_both_sides_at_the_frozen_weights_without_a_verdict(toy_episode):
    out, s = toy_episode
    assert s["heading"] == episode007.HEADING and "known_window_note" in s
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


def test_rank_keeps_expanding_and_last_month_weights_are_written(toy_episode):
    _, s = toy_episode
    assert s["rank_history_months_at_episode_end"] == 70  # 2000-01 to 2005-10 on the toy calendar
    last = s["weights_at_last_signal_month_for_forward_record"]
    assert last["signal_month"] == "2005-10" and last["n"] == 70
    for k in TRIAL_IDS:
        assert 0.0 <= last[k] <= 1.0 and last[k] == round(last[k], 4)
    assert last["T3"] in (0.0, 1.0) and last["T2"] == pytest.approx(0.5 * last["T1"] + 0.5 * last["T3"], abs=1e-4)


def test_actual_side_trend_uses_the_etf_closes(toy_episode):
    """On the constructed data the actual bars are the synthetic indices scaled
    by a constant, so the trend signals agree; the weights must then agree too."""
    out, _ = toy_episode
    import pandas as pd

    a = pd.read_csv(out / "actual" / "monthly_base.csv", index_col=0)
    b = pd.read_csv(out / "synthetic" / "monthly_base.csv", index_col=0)
    for k in TRIAL_IDS:
        pd.testing.assert_series_equal(a[f"w_{k}"], b[f"w_{k}"], check_names=False)


def test_frozen_weights_need_every_trial(tmp_path):
    (tmp_path / "summary.json").write_text(json.dumps({"weight_b3": {"T1": 0.5}}))
    with pytest.raises(ValueError, match="no frozen weight"):
        episode007.frozen_weights(tmp_path)
    (tmp_path / "summary.json").write_text(json.dumps({"weight_b3": FROZEN}))
    assert episode007.frozen_weights(tmp_path) == FROZEN


def test_main_needs_history_and_the_committed_note_and_runs_once(tmp_path):
    study, hist, out = tmp_path / "study", tmp_path / "history", tmp_path / "episode"
    study.mkdir()
    with pytest.raises(SystemExit, match="frozen w"):
        episode007.main([], hist, out, study)
    hist.mkdir()
    (hist / "summary.json").write_text(json.dumps({"weight_b3": FROZEN}))
    with pytest.raises(SystemExit, match="not committed"):
        episode007.main([], hist, out, study)
    _git(study, "init", "-q")
    (study / "README.md").write_text("# Study 007\n\n## Verdict\n")
    _git(study, "add", "README.md")
    _git(study, "commit", "-q", "-m", "note")
    out.mkdir()
    with pytest.raises(SystemExit, match="once"):
        episode007.main([], hist, out, study)
