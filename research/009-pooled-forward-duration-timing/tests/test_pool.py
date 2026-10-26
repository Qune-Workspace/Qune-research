"""Study 009 scoring (src/pool.py) on constructed data only: no forward
record of any member exists when these tests are written (2026-10-26)."""

import json

import numpy as np
import pandas as pd
import pytest
from src import pool

TRIALS_OK = "| Step | Date | Outcome |\n|---|---|---|\n| Scoring date (P1) | 2031-12-01 | written before any statistic |\n"
DATES = {m: "2031-11-03" for m in pool.MEMBERS}


def _dates(n):
    """n monthly periods: signal on the 28th, execution on the 2nd of the next month."""
    sig = pd.date_range("2026-10-28", periods=n + 1, freq="MS") + pd.Timedelta(days=27)
    exe = pd.date_range("2026-11-02", periods=n + 1, freq="MS") + pd.Timedelta(days=1)
    return [str(d.date()) for d in sig], [str(d.date()) for d in exe]


def shadow(d, holdings=None):
    n = len(d)
    sig, exe = _dates(n)
    frame = pd.DataFrame({"signal_date": sig[:n], "execution_date": exe[:n], "period_end": exe[1:n + 1],
                          "d": [repr(float(x)) for x in d]})
    if holdings is not None:
        frame["T1_holding"] = holdings
    return frame.astype(str)


def members(d6, d7, d8, hold6=None):
    hold6 = hold6 if hold6 is not None else ["IEF", "BIL"] * (len(d6) // 2) + ["IEF"] * (len(d6) % 2)
    return {"006": shadow(d6, hold6), "007": shadow(d7), "008": shadow(d8)}


def verdicts(v6="inconclusive (forward)", v7="inconclusive (forward)", v8="inconclusive (forward)"):
    return {m: {"verdict": v, "scoring_date": DATES[m]} for m, v in zip(pool.MEMBERS, (v6, v7, v8))}


rng = np.random.default_rng(9)
NOISE = {m: rng.normal(0.0, 0.004, 66) for m in pool.MEMBERS}


def test_pooled_series_is_the_equal_weight_mean_and_the_t_is_newey_west_6_lags():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    out = pool.score(s, verdicts(), TRIALS_OK)
    p = (NOISE["006"][:60] + NOISE["007"][:60] + NOISE["008"][:60]) / 3
    nw = pool.newey_west_mean(pd.Series(p), lags=6)
    assert out["n"] == 60 and out["newey_west"]["lags"] == 6
    assert out["newey_west"]["t"] == pytest.approx(nw["t"], rel=1e-12)
    assert out["mean_P_per_year"] == pytest.approx(12 * p.mean(), rel=1e-12)
    assert out["detectable_per_year"] == pytest.approx(2.842 * nw["se"] * 12, rel=1e-12)
    assert out["label"] == "low-power check" and out["left_out"] == []


def test_rows_after_each_members_first_60_never_enter():
    a = members(NOISE["006"], NOISE["007"], NOISE["008"])
    b = members(NOISE["006"][:60], NOISE["007"][:60], NOISE["008"][:60])
    late = {m: np.r_[NOISE[m][:60], np.full(6, 0.5)] for m in pool.MEMBERS}
    c = members(late["006"], late["007"], late["008"])
    ta, tb, tc = (pool.score(x, verdicts(), TRIALS_OK)["newey_west"]["t"] for x in (a, b, c))
    assert ta == tb == tc


@pytest.mark.parametrize("shift, expected", [(0.01, pool.VERDICT_SUPPORTED), (-0.01, pool.VERDICT_REFUTED),
                                             (0.0, pool.VERDICT_INCONCLUSIVE)])
def test_verdict_rows_on_constructed_edges(shift, expected):
    s = members(NOISE["006"] + shift, NOISE["007"] + shift, NOISE["008"] + shift)
    assert pool.score(s, verdicts(), TRIALS_OK)["verdict"] == expected


@pytest.mark.parametrize("mean, t, expected", [
    (0.001, 2.0, pool.VERDICT_SUPPORTED), (0.001, 1.999, pool.VERDICT_INCONCLUSIVE),
    (-0.001, 2.5, pool.VERDICT_INCONCLUSIVE),  # t >= 2 with a negative mean cannot occur, but the row needs both
    (-0.001, -2.0, pool.VERDICT_REFUTED), (-0.001, -1.999, pool.VERDICT_INCONCLUSIVE)])
def test_verdict_boundaries(monkeypatch, mean, t, expected):
    seen = {}

    def fake(x, lags):
        seen["lags"] = lags
        return {"mean": mean, "se": 0.001, "t": t, "n": len(x), "lags": lags}

    monkeypatch.setattr(pool, "newey_west_mean", fake)
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    assert pool.score(s, verdicts(), TRIALS_OK)["verdict"] == expected and seen["lags"] == 6


def test_a_missed_month_in_one_member_drops_both_months_and_is_listed():
    """007 writes no row for signal month 6; its next row spans two months
    (the members' codes).  Neither month enters P; 007's block then reaches
    one month further than the others', and that row is left out too."""
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    s7 = s["007"].drop(index=6).reset_index(drop=True)
    s7.loc[5, "period_end"] = s["007"].loc[6, "period_end"]
    s["007"] = s7
    out = pool.score(s, verdicts(), TRIALS_OK)
    assert out["n"] == 58
    sig = s["006"]["signal_date"]
    assert {r["signal_date"] for r in out["periods"]}.isdisjoint({sig[5], sig[6], sig[60]})
    reasons = {(r["member"], r["signal_date"]): r["reason"] for r in out["left_out"]}
    assert "same signal date" in reasons[("006", sig[5])]
    assert "007: no block-1 row with this signal date" in reasons[("006", sig[6])]
    assert ("007", sig[60]) in reasons and "no block-1 row" in reasons[("007", sig[60])]
    p = [(NOISE["006"][i] + NOISE["007"][i] + NOISE["008"][i]) / 3 for i in range(60) if i not in (5, 6)]
    assert out["mean_P_per_year"] == pytest.approx(12 * np.mean(p), rel=1e-12)


def test_a_slipped_execution_date_in_one_member_is_left_out_not_matched_by_signal_month():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    s["008"].loc[10, "execution_date"] = "2099-01-01"
    out = pool.score(s, verdicts(), TRIALS_OK)
    assert out["n"] == 59
    assert sum(r["signal_date"] == s["006"].loc[10, "signal_date"] for r in out["left_out"]) == 3


def test_006_not_testable_is_dropped_and_p_is_the_mean_of_007_and_008():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"], hold6=["IEF"] * 66)
    out = pool.score(s, verdicts(v6="not testable"), TRIALS_OK)
    p = (NOISE["007"][:60] + NOISE["008"][:60]) / 2
    assert out["dropped"] == ["006"] and out["remaining"] == ["007", "008"]
    assert out["mean_P_per_year"] == pytest.approx(12 * p.mean(), rel=1e-12)


def test_006_holding_one_asset_only_after_its_block_is_still_testable():
    hold = ["IEF", "BIL"] + ["IEF"] * 64
    s = members(NOISE["006"], NOISE["007"], NOISE["008"], hold6=hold)
    assert pool.score(s, verdicts(), TRIALS_OK)["remaining"] == ["006", "007", "008"]
    s = members(NOISE["006"], NOISE["007"], NOISE["008"], hold6=["IEF"] * 60 + ["BIL"] * 6)
    with pytest.raises(ValueError, match="disagrees"):
        pool.score(s, verdicts(), TRIALS_OK)


def test_a_stated_006_verdict_that_contradicts_its_file_is_refused():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    with pytest.raises(ValueError, match="disagrees"):
        pool.score(s, verdicts(v6="not testable"), TRIALS_OK)


def test_every_member_dropped_is_not_testable_with_no_statistic():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"], hold6=["IEF"] * 66)
    out = pool.score(s, verdicts("not testable", "not testable", "not testable"), TRIALS_OK)
    assert out["verdict"] == pool.VERDICT_NOT_TESTABLE and out["newey_west"] is None and out["n"] == 0


def test_no_scoring_date_row_means_no_statistic(monkeypatch):
    called = []
    monkeypatch.setattr(pool, "newey_west_mean", lambda *a, **k: called.append(1))
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    with pytest.raises(RuntimeError, match="no 'Scoring date"):
        pool.score(s, verdicts(), "| Step | Date | Outcome |\n")
    assert called == []


def test_a_scoring_date_before_a_members_block_scoring_is_refused():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    v = verdicts()
    v["008"]["scoring_date"] = "2031-12-02"
    with pytest.raises(RuntimeError, match="precedes"):
        pool.score(s, v, TRIALS_OK)


def test_two_scoring_date_rows_are_refused():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    with pytest.raises(ValueError, match="more than one"):
        pool.score(s, verdicts(), TRIALS_OK + "| Scoring date (P1), again | 2032-01-01 | x |\n")


def test_a_member_short_of_60_periods_is_not_scored():
    s = members(NOISE["006"], NOISE["007"][:59], NOISE["008"])
    with pytest.raises(RuntimeError, match="59 periods"):
        pool.score(s, verdicts(), TRIALS_OK)


@pytest.mark.parametrize("bad", ["supported", "", None, "Not testable"])
def test_member_verdicts_must_be_the_members_own_strings(bad):
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    with pytest.raises(ValueError, match="unknown member verdict"):
        pool.score(s, verdicts(v7=bad), TRIALS_OK)


def test_members_are_fixed():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    s["003"] = s["006"]
    with pytest.raises(ValueError, match="members are fixed"):
        pool.score(s, verdicts(), TRIALS_OK)


def test_duplicate_signal_dates_and_empty_d_are_refused():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    s["007"].loc[3, "signal_date"] = s["007"].loc[2, "signal_date"]
    with pytest.raises(ValueError, match="twice"):
        pool.score(s, verdicts(), TRIALS_OK)
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    s["008"].loc[4, "d"] = "nan"
    with pytest.raises(ValueError, match="non-finite"):
        pool.score(s, verdicts(), TRIALS_OK)


def test_fewer_than_two_common_periods_is_an_unregistered_case():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    s["008"]["execution_date"] = "2099-01-01"
    with pytest.raises(RuntimeError, match="dated decision"):
        pool.score(s, verdicts(), TRIALS_OK)


def test_main_refuses_on_the_real_repository_today_and_writes_nothing(tmp_path, capsys):
    f = tmp_path / "v.json"
    f.write_text(json.dumps(verdicts()), encoding="utf-8")
    existed = pool.RESULT_JSON.exists()
    assert pool.main(["score", "--member-verdicts", str(f)]) == 1
    assert "refused" in capsys.readouterr().out
    assert pool.RESULT_JSON.exists() == existed


def test_main_scores_once(tmp_path, monkeypatch, capsys):
    paths = {}
    for m, frame in members(NOISE["006"], NOISE["007"], NOISE["008"]).items():
        paths[m] = tmp_path / f"{m}.csv"
        frame.to_csv(paths[m], index=False)
    trials = tmp_path / "trials.md"
    trials.write_text(TRIALS_OK, encoding="utf-8")
    monkeypatch.setattr(pool, "MEMBERS", paths)
    monkeypatch.setattr(pool, "TRIALS_MD", trials)
    monkeypatch.setattr(pool, "STUDY_DIR", tmp_path)
    monkeypatch.setattr(pool, "RESULT_JSON", tmp_path / "results" / "score.json")
    monkeypatch.setattr(pool.read_shadows, "__defaults__", (paths,))
    f = tmp_path / "v.json"
    f.write_text(json.dumps(verdicts()), encoding="utf-8")
    assert pool.main(["score", "--member-verdicts", str(f)]) == 0
    assert json.loads((tmp_path / "results" / "score.json").read_text())["n"] == 60
    assert pool.main(["score", "--member-verdicts", str(f)]) == 1
    assert "scored once" in capsys.readouterr().out
