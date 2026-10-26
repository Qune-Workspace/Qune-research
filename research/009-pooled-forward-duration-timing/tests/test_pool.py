"""Study 009 scoring (src/pool.py) on constructed data only: no forward
record of any member exists when these tests are written (2026-10-26)."""

import json

import numpy as np
import pandas as pd
import pytest
from src import pool

TRIALS_OK = "| Step | Date | Outcome |\n|---|---|---|\n| Scoring date (P1) | 2032-01-05 | written before any statistic |\n"


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
    else:
        frame["w_T1"] = [repr(0.3 + 0.01 * (i % 7)) for i in range(n)]
    return frame.astype(str)


def members(d6, d7, d8, hold6=None):
    hold6 = hold6 if hold6 is not None else ["IEF", "BIL"] * (len(d6) // 2) + ["IEF"] * (len(d6) % 2)
    return {"006": shadow(d6, hold6), "007": shadow(d7), "008": shadow(d8)}


def verdicts(s=None, v6=None, v7="inconclusive (forward)", v8="inconclusive (forward)"):
    """The members' own verdicts and scoring dates as their score() would
    return them: 006's row recomputed by its rule, each date = period_end of
    shadow row 60."""
    s = s if s is not None else members(NOISE["006"], NOISE["007"], NOISE["008"])
    v6 = v6 if v6 is not None else pool.own_006_verdict(s["006"].iloc[:60].assign(d=lambda f: f["d"].astype(float)))
    return {m: {"verdict": v, "scoring_date": s[m]["period_end"].iloc[59]} for m, v in zip(pool.MEMBERS, (v6, v7, v8))}


rng = np.random.default_rng(9)
NOISE = {m: rng.normal(0.0, 0.004, 66) for m in pool.MEMBERS}


def test_pooled_series_is_the_equal_weight_mean_and_the_t_is_newey_west_6_lags():
    out = pool.score(members(NOISE["006"], NOISE["007"], NOISE["008"]), verdicts(), TRIALS_OK)
    p = (NOISE["006"][:60] + NOISE["007"][:60] + NOISE["008"][:60]) / 3
    nw = pool.newey_west_mean(pd.Series(p), lags=6)
    assert out["n"] == 60 and out["newey_west"]["lags"] == 6
    assert out["newey_west"]["t"] == pytest.approx(nw["t"], rel=1e-12)
    assert out["mean_P_per_year"] == pytest.approx(12 * p.mean(), rel=1e-12)
    assert out["detectable_per_year"] == pytest.approx(2.842 * nw["se"] * 12, rel=1e-12)
    assert out["label"] == "low-power check" and out["row"].endswith(", low-power check")
    assert out["left_out"] == [] and out["periods_longer_than_45_days"] == 0


def test_rows_after_each_members_first_60_never_enter():
    a = members(NOISE["006"], NOISE["007"], NOISE["008"])
    b = members(NOISE["006"][:60], NOISE["007"][:60], NOISE["008"][:60])
    late = {m: np.r_[NOISE[m][:60], np.full(6, 0.5)] for m in pool.MEMBERS}
    c = members(late["006"], late["007"], late["008"])
    ta, tb, tc = (pool.score(x, verdicts(x), TRIALS_OK)["newey_west"]["t"] for x in (a, b, c))
    assert ta == tb == tc


@pytest.mark.parametrize("shift, expected", [(0.01, pool.VERDICT_SUPPORTED), (-0.01, pool.VERDICT_REFUTED),
                                             (0.0, pool.VERDICT_INCONCLUSIVE)])
def test_verdict_rows_on_constructed_edges(shift, expected):
    s = members(NOISE["006"] + shift, NOISE["007"] + shift, NOISE["008"] + shift)
    assert pool.score(s, verdicts(s), TRIALS_OK)["verdict"] == expected


@pytest.mark.parametrize("mean, t, expected", [
    (0.001, 2.0, pool.VERDICT_SUPPORTED), (0.001, 1.999, pool.VERDICT_INCONCLUSIVE),
    (-0.001, 2.5, pool.VERDICT_INCONCLUSIVE),  # t >= 2 with a negative mean cannot occur, but the row needs both
    (-0.001, -2.0, pool.VERDICT_REFUTED), (-0.001, -1.999, pool.VERDICT_INCONCLUSIVE)])
def test_verdict_boundaries(monkeypatch, mean, t, expected):
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    v = verdicts(s)  # computed with the real statistic, before the patch
    seen = {}

    def fake(x, lags):
        seen["lags"] = lags
        return {"mean": mean, "se": 0.001, "t": t, "n": len(x), "lags": lags}

    monkeypatch.setattr(pool, "newey_west_mean", fake)
    monkeypatch.setattr(pool, "own_006_verdict", lambda rows: v["006"]["verdict"])
    assert pool.score(s, v, TRIALS_OK)["verdict"] == expected and seen["lags"] == 6


def test_a_missed_month_in_one_member_drops_both_months_and_is_listed():
    """007 writes no row for signal month 6; its next row spans two months
    (the members' codes).  Neither month enters P; 007's block then reaches
    one month further than the others', and that row is left out too."""
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    s7 = s["007"].drop(index=6).reset_index(drop=True)
    s7.loc[5, "period_end"] = s["007"].loc[6, "period_end"]
    s["007"] = s7
    out = pool.score(s, verdicts(s), TRIALS_OK)
    assert out["n"] == 58
    sig = s["006"]["signal_date"]
    assert {r["signal_date"] for r in out["periods"]}.isdisjoint({sig[5], sig[6], sig[60]})
    reasons = {(r["member"], r["signal_date"]): r["reason"] for r in out["left_out"]}
    assert reasons[("006", sig[5])].startswith("007: same signal date") and "008" not in reasons[("006", sig[5])]
    assert "007: no block-1 row with this signal date" in reasons[("006", sig[6])]
    assert ("007", sig[60]) in reasons and "no block-1 row" in reasons[("007", sig[60])]
    p = [(NOISE["006"][i] + NOISE["007"][i] + NOISE["008"][i]) / 3 for i in range(60) if i not in (5, 6)]
    assert out["mean_P_per_year"] == pytest.approx(12 * np.mean(p), rel=1e-12)


def test_a_slipped_execution_date_in_one_member_is_left_out_not_matched_by_signal_month():
    """As the members write it: a slip moves row 10's execution date and the
    end of row 9 (append_shadow's continuity rule), so two periods drop."""
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    slipped = str((pd.Timestamp(s["008"].loc[10, "execution_date"]) + pd.Timedelta(days=1)).date())
    s["008"].loc[10, "execution_date"] = slipped
    s["008"].loc[9, "period_end"] = slipped
    out = pool.score(s, verdicts(s), TRIALS_OK)
    assert out["n"] == 58
    assert {r["signal_date"] for r in out["left_out"]} == {s["006"].loc[i, "signal_date"] for i in (9, 10)}


def test_the_same_month_missed_by_every_member_stays_in_p_and_is_counted():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    for m in pool.MEMBERS:
        x = s[m].drop(index=6).reset_index(drop=True)
        x.loc[5, "period_end"] = s[m].loc[6, "period_end"]
        s[m] = x
    out = pool.score(s, verdicts(s), TRIALS_OK)
    assert out["n"] == 60 and out["periods_longer_than_45_days"] == 1 and out["left_out"] == []


def test_a_block_out_of_date_order_or_with_a_gap_is_refused():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    s["007"] = s["007"].iloc[[1, 0] + list(range(2, 66))].reset_index(drop=True)
    with pytest.raises(ValueError, match="continuous"):
        pool.score(s, verdicts(s), TRIALS_OK)
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    s["008"] = s["008"].drop(index=20).reset_index(drop=True)
    with pytest.raises(ValueError, match="continuous"):
        pool.score(s, verdicts(s), TRIALS_OK)


def test_006_not_testable_is_dropped_and_p_is_the_mean_of_007_and_008():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"], hold6=["IEF"] * 66)
    out = pool.score(s, verdicts(s), TRIALS_OK)
    p = (NOISE["007"][:60] + NOISE["008"][:60]) / 2
    assert out["dropped"] == ["006"] and out["remaining"] == ["007", "008"]
    assert out["mean_P_per_year"] == pytest.approx(12 * p.mean(), rel=1e-12)


@pytest.mark.parametrize("hold", [["BIL"] + ["IEF"] * 65, ["IEF"] * 59 + ["BIL"] + ["IEF"] * 6])
def test_006_is_testable_when_it_switched_once_anywhere_in_rows_1_to_60(hold):
    s = members(NOISE["006"], NOISE["007"], NOISE["008"], hold6=hold)
    assert pool.score(s, verdicts(s), TRIALS_OK)["remaining"] == ["006", "007", "008"]
    with pytest.raises(ValueError, match="disagrees"):
        pool.score(s, verdicts(s, v6="not testable"), TRIALS_OK)


def test_006_switching_only_after_its_block_is_not_testable():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"], hold6=["IEF"] * 60 + ["BIL"] * 6)
    with pytest.raises(ValueError, match="disagrees"):
        pool.score(s, verdicts(s, v6="inconclusive (forward)"), TRIALS_OK)
    assert pool.score(s, verdicts(s), TRIALS_OK)["dropped"] == ["006"]


def test_a_stated_006_row_other_than_its_own_is_refused():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    assert verdicts(s)["006"]["verdict"] == "inconclusive (forward)"
    for wrong in ("supported (forward)", "refuted (forward)", "not testable"):
        with pytest.raises(ValueError, match="disagrees"):
            pool.score(s, verdicts(s, v6=wrong), TRIALS_OK)


def test_007_or_008_said_testable_with_a_weight_that_never_moved_is_refused():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    s["008"]["w_T1"] = "0.5"
    with pytest.raises(ValueError, match="never moved"):
        pool.score(s, verdicts(s), TRIALS_OK)
    assert pool.score(s, verdicts(s, v8="not testable"), TRIALS_OK)["dropped"] == ["008"]


def test_every_member_dropped_is_not_testable_with_no_statistic():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"], hold6=["IEF"] * 66)
    out = pool.score(s, verdicts(s, "not testable", "not testable", "not testable"), TRIALS_OK)
    assert out["verdict"] == pool.VERDICT_NOT_TESTABLE and out["newey_west"] is None and out["n"] == 0
    assert out["row"] == "not testable, low-power check"


def test_no_scoring_date_row_means_no_statistic(monkeypatch):
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    v = verdicts(s)
    called = []
    monkeypatch.setattr(pool, "newey_west_mean", lambda *a, **k: called.append(1))
    with pytest.raises(RuntimeError, match="no 'Scoring date"):
        pool.score(s, v, "| Step | Date | Outcome |\n")
    assert called == []


def test_a_member_scoring_date_that_is_not_its_files_is_refused():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    v = verdicts(s)
    v["007"]["scoring_date"] = "2026-01-01"
    with pytest.raises(ValueError, match="not the end of its block 1"):
        pool.score(s, v, TRIALS_OK)


def test_the_scoring_date_must_follow_every_members_strictly():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    last = s["006"]["period_end"].iloc[59]
    for when, ok in ((last, False), (str((pd.Timestamp(last) + pd.Timedelta(days=1)).date()), True)):
        trials = f"| Scoring date (P1) | {when} | x |\n"
        if ok:
            assert pool.score(s, verdicts(s), trials)["scoring_date"] == when
        else:
            with pytest.raises(RuntimeError, match="does not follow"):
                pool.score(s, verdicts(s), trials)


@pytest.mark.parametrize("text, found", [
    ("| Scoring date (P1) | 2032-01-05 | x |", "2032-01-05"),
    ("|  Scoring date (P1)  |  2032-01-05 (London) | x |", "2032-01-05"),
    ("| Scoring date (P1) postponed, not fixed | 2032-01-05 | x |", None),
    ("| Scoring date (P1) correction | 2032-02-01 | x |", None),
    ("| Power | 2026-10-26 | Scoring date (P1) | 2032-01-05 |", None),
    ("| **Scoring date (P1)** | 2032-01-05 | x |", None),
    ("Scoring date (P1) | 2032-01-05", None)])
def test_only_an_exact_scoring_date_step_cell_counts(text, found):
    assert pool.logged_scoring_date(text + "\n") == found


def test_two_scoring_date_rows_are_refused():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    with pytest.raises(ValueError, match="more than one"):
        pool.score(s, verdicts(s), TRIALS_OK + "| Scoring date (P1) | 2032-02-01 | x |\n")


@pytest.mark.parametrize("bad", ["2031-99-99", "2031-1-5", "", None])
def test_dates_must_be_iso(bad):
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    v = verdicts(s)
    v["007"]["scoring_date"] = bad
    with pytest.raises(ValueError, match="not an ISO date"):
        pool.score(s, v, TRIALS_OK)
    s["008"].loc[3, "period_end"] = "2031-99-99"
    with pytest.raises(ValueError, match="not an ISO date"):
        pool.score(s, verdicts(s), TRIALS_OK)


def test_a_member_short_of_60_periods_is_not_scored():
    s = members(NOISE["006"], NOISE["007"][:59], NOISE["008"])
    with pytest.raises(RuntimeError, match="59 periods"):
        pool.score(s, verdicts(), TRIALS_OK)


@pytest.mark.parametrize("bad", ["supported", "", None, "Not testable"])
def test_member_verdicts_must_be_the_members_own_strings(bad):
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    with pytest.raises(ValueError, match="unknown member verdict"):
        pool.score(s, verdicts(s, v7=bad), TRIALS_OK)


def test_a_verdict_that_is_not_an_object_is_refused():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    v = verdicts(s)
    v["006"] = "inconclusive (forward)"
    with pytest.raises(ValueError, match="must be"):
        pool.score(s, v, TRIALS_OK)


def test_members_are_fixed():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    s["003"] = s["006"]
    with pytest.raises(ValueError, match="members are fixed"):
        pool.score(s, verdicts(), TRIALS_OK)


def test_duplicate_signal_dates_and_empty_d_are_refused():
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    s["007"].loc[3, "signal_date"] = s["007"].loc[2, "signal_date"]
    with pytest.raises(ValueError, match="twice"):
        pool.score(s, verdicts(s), TRIALS_OK)
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    s["008"].loc[4, "d"] = "nan"
    with pytest.raises(ValueError, match="non-finite"):
        pool.score(s, verdicts(s), TRIALS_OK)


def test_fewer_than_two_common_periods_is_an_unregistered_case():
    """008 one day behind in every period: continuous, but no key in common."""
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    for c in ("execution_date", "period_end"):
        s["008"][c] = [str((pd.Timestamp(x) + pd.Timedelta(days=1)).date()) for x in s["008"][c]]
    trials = "| Scoring date (P1) | 2032-01-05 | x |\n"
    with pytest.raises(RuntimeError, match="dated decision"):
        pool.score(s, verdicts(s), trials)


def _redirect(monkeypatch, tmp_path, shadows, trials_text):
    paths = {}
    for m, frame in shadows.items():
        paths[m] = tmp_path / f"{m}.csv"
        frame.to_csv(paths[m], index=False)
    trials = tmp_path / "trials.md"
    trials.write_text(trials_text, encoding="utf-8")
    monkeypatch.setattr(pool, "MEMBERS", paths)
    monkeypatch.setattr(pool, "TRIALS_MD", trials)
    monkeypatch.setattr(pool, "STUDY_DIR", tmp_path)
    monkeypatch.setattr(pool, "RESULT_JSON", tmp_path / "results" / "score.json")
    monkeypatch.setattr(pool.read_shadows, "__defaults__", (paths,))


class _Clock:
    @staticmethod
    def now(tz):
        return pd.Timestamp("2032-01-10", tz="UTC").to_pydatetime()


def test_main_refuses_on_the_real_repository_today_and_writes_nothing(tmp_path, monkeypatch, capsys):
    """Never writes the real results/score.json (code review, finding 1): the
    result path is redirected, and the test is skipped once any member has a
    forward record."""
    if any(p.exists() for p in pool.MEMBERS.values()):
        pytest.skip("a member has a shadow.csv: this test is for the days before any forward record")
    monkeypatch.setattr(pool, "RESULT_JSON", tmp_path / "score.json")
    f = tmp_path / "v.json"
    f.write_text(json.dumps(verdicts()), encoding="utf-8")
    assert pool.main(["score", "--member-verdicts", str(f)]) == 1
    assert "refused: no shadow.csv yet" in capsys.readouterr().out
    assert not (tmp_path / "score.json").exists()


def test_main_scores_once_and_refuses_a_scoring_date_after_today(tmp_path, monkeypatch, capsys):
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    f = tmp_path / "v.json"
    f.write_text(json.dumps(verdicts(s)), encoding="utf-8")
    _redirect(monkeypatch, tmp_path, s, TRIALS_OK)
    assert pool.main(["score", "--member-verdicts", str(f)]) == 1  # 2032-01-05 is after the real today
    assert "after today" in capsys.readouterr().out
    monkeypatch.setattr(pool, "datetime", _Clock)
    assert pool.main(["score", "--member-verdicts", str(f)]) == 0
    assert json.loads((tmp_path / "results" / "score.json").read_text())["n"] == 60
    assert pool.main(["score", "--member-verdicts", str(f)]) == 1
    assert "scored once" in capsys.readouterr().out


def test_main_refuses_a_malformed_verdicts_file(tmp_path, monkeypatch, capsys):
    s = members(NOISE["006"], NOISE["007"], NOISE["008"])
    _redirect(monkeypatch, tmp_path, s, TRIALS_OK)
    monkeypatch.setattr(pool, "datetime", _Clock)
    f = tmp_path / "v.json"
    for content in ('{"006": "x", "007": "x", "008": "x"}', "not json"):
        f.write_text(content, encoding="utf-8")
        assert pool.main(["score", "--member-verdicts", str(f)]) == 1
        assert "refused" in capsys.readouterr().out
    assert not (tmp_path / "results").exists()
