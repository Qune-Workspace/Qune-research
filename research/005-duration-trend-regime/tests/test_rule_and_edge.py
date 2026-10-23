"""§5.3.5 (i), (vi), (vii), (viii): the conditional rule against the frozen
engine, the B3 weight, the edge statistics on constructed data, and the
stopping rule.  Test (i)'s second half needs Study 003's raw files on disk
and skips in CI."""
import json

import numpy as np
import pandas as pd
import pytest

from qune_research.data import sha256_of
from src import edge, forward, pipeline
from src.config import (COST_CASES, DURATION_LEG, INSAMPLE_FIRST_SIGNAL_MONTH, INSAMPLE_LAST_SIGNAL_MONTH,
                        MIN_EDGE_PER_MONTH, STUDY_003_DIR, STUDY_003_INSAMPLE_MONTHLY)
from tests.toy import toy_world


@pytest.fixture(scope="module")
def toy():
    world = toy_world()
    schedule, month_ends = pipeline.window_schedule(pipeline.window_bars(world["indices"], etf_cash=False),
                                                    "2001-01", "2007-11")
    signal = pipeline.trend_frame(world["indices"], month_ends, schedule)
    targets = pipeline.period_targets(signal, schedule)
    return dict(world, schedule=schedule, month_ends=month_ends, signal=signal, targets=targets)


def test_i_forced_regimes_collapse_to_b2_and_b1(toy):
    always = pd.Series(True, index=toy["targets"].index)
    never = pd.Series(False, index=toy["targets"].index)
    for cost in COST_CASES.values():
        pos = pipeline.window_paths(toy["indices"], toy["schedule"], toy["targets"], always, cost)
        neg = pipeline.window_paths(toy["indices"], toy["schedule"], toy["targets"], never, cost)
        assert np.array_equal(pos["results"]["T1"]["r"].to_numpy(), pos["results"]["B2"]["r"].to_numpy())
        assert (pos["results"]["T1"]["holding"] == pos["results"]["B2"]["holding"]).all()
        # never positive: IEF held throughout after the initial purchase from BIL
        assert (neg["targets_T1"] == DURATION_LEG).all()
        assert neg["results"]["T1"]["switched"].sum() == 1          # the first period's purchase
        assert np.allclose(neg["results"]["T1"]["r"].to_numpy()[1:], neg["results"]["B1"]["r"].to_numpy()[1:],
                           atol=1e-15)
        assert neg["results"]["T1"]["r"].iloc[0] == pytest.approx(
            (1 - cost) ** 2 * (1 + neg["results"]["B1"]["r"].iloc[0]) - 1, abs=1e-15)
    assert toy["targets"].nunique() == 2, "the toy trend signal must switch for the test to mean anything"


def _study_003_raw_files_present() -> bool:
    manifest = STUDY_003_DIR / "results" / "data_manifest.json"
    raw = STUDY_003_DIR / "data" / "raw"
    if not (manifest.exists() and (raw / "tiingo_IEF_daily.csv").exists() and (raw / "fred_DTB3.csv").exists()):
        return False
    recorded = json.loads(manifest.read_text(encoding="utf-8"))
    return all(sha256_of(raw / n) == recorded[n]["sha256"] for n in ("tiingo_IEF_daily.csv", "fred_DTB3.csv"))


@pytest.mark.skipif(not _study_003_raw_files_present(), reason="Study 003's raw files are not on this machine (CI)")
def test_i_b2_reproduces_study_003_insample_to_1e10():
    """(i): the ported unconditional rule on Study 003's own files reproduces
    its committed in-sample T1 column (and B0, B1, B3) to 1e-10.  Reads the
    hash-checked files in place; writes nothing."""
    from qune_research.data import load_fred, load_tiingo
    raw = STUDY_003_DIR / "data" / "raw"
    indices = pipeline.insample_indices(load_tiingo("IEF", raw)["adjClose"], load_fred("DTB3", raw))
    schedule, month_ends = pipeline.window_schedule(pipeline.window_bars(indices, etf_cash=False),
                                                    INSAMPLE_FIRST_SIGNAL_MONTH, INSAMPLE_LAST_SIGNAL_MONTH)
    signal = pipeline.trend_frame(indices, month_ends, schedule)
    targets = pipeline.period_targets(signal, schedule)
    committed = pd.read_csv(STUDY_003_INSAMPLE_MONTHLY, index_col="month")
    assert len(targets) == len(committed) == 185
    always = pd.Series(True, index=targets.index)
    paths = pipeline.window_paths(indices, schedule, targets, always, COST_CASES["base"],
                                  weight_b3=float(json.loads((STUDY_003_DIR / "results" / "insample" / "summary.json")
                                                             .read_text(encoding="utf-8"))["weight_b3"]))
    for ours, theirs in (("B2", "T1"), ("B0", "B0"), ("B1", "B1"), ("B3", "B3"), ("T1", "T1")):
        diff = np.abs(paths["results"][ours]["r"].to_numpy() - committed[theirs].to_numpy())
        assert diff.max() < 1e-10, f"{ours} vs Study 003 {theirs}: max abs diff {diff.max():.3e}"
    assert (paths["results"]["B2"]["holding"].to_numpy() == committed["T1_holding"].to_numpy()).all()
    assert np.abs(signal["value"].reindex(committed.index).to_numpy() - committed["mom_at_signal"].to_numpy()).max() < 1e-10


def test_vi_b3_weight_is_t1_ief_fraction(toy):
    rng = np.random.default_rng(1)
    positive = pd.Series(rng.random(len(toy["targets"])) < 0.5, index=toy["targets"].index)
    paths = pipeline.window_paths(toy["indices"], toy["schedule"], toy["targets"], positive, COST_CASES["base"])
    assert paths["weight_b3"] == pytest.approx((paths["targets_T1"] == DURATION_LEG).mean())
    assert paths["results"]["B3"]["weight_ief"].iloc[0] == paths["weight_b3"]
    # d_t is zero whenever B2 held IEF (B2 and B1 earn the same gross return, no switch)
    held = paths["results"]["B2"]["holding"] == DURATION_LEG
    unswitched = held & ~paths["results"]["B2"]["switched"]
    assert np.allclose(paths["d"][unswitched].to_numpy(), 0.0, atol=1e-15)


def test_vii_edge_statistics_match_hand_computation():
    """(vii): on constructed d and flags with known group means, Δ and the
    half-means are exact, the Newey–West t matches statsmodels on the same
    regression, and the bootstrap interval covers the known Δ."""
    rng = np.random.default_rng(7)
    n = 180
    positive = pd.Series(np.repeat([True, False, False, True, False], 36))
    d = pd.Series(np.where(positive, 0.004, -0.002) + rng.normal(0, 0.008, n))
    out = edge.conditional_edge(d, positive, np.random.default_rng(2005), n_resamples=2000)
    assert out["n_pos"] == 72 and out["n_neg"] == 108
    assert out["mean_positive"] == pytest.approx(d[positive].mean(), abs=1e-15)
    assert out["mean_negative"] == pytest.approx(d[~positive].mean(), abs=1e-15)
    assert out["delta"] == pytest.approx(d[positive].mean() - d[~positive].mean(), abs=1e-15)
    assert out["newey_west"]["delta"] == pytest.approx(out["delta"], abs=1e-12)
    assert out["newey_west"]["intercept_mean_negative"] == pytest.approx(out["mean_negative"], abs=1e-12)
    import statsmodels.api as sm
    fit = sm.OLS(d.to_numpy(), sm.add_constant(positive.to_numpy().astype(float))).fit(
        cov_type="HAC", cov_kwds={"maxlags": 6, "use_correction": False})
    assert out["newey_west"]["t"] == pytest.approx(float(fit.tvalues[1]), abs=1e-12)
    lo, hi = out["bootstrap"]["delta"]["ci_low"], out["bootstrap"]["delta"]["ci_high"]
    assert lo < 0.006 < hi and lo > 0.0
    for half in ("mean_positive", "mean_negative"):      # each half-mean's interval covers its sample value
        assert out["bootstrap"][half]["ci_low"] < out[half] < out["bootstrap"][half]["ci_high"]
    assert out["bootstrap"]["resamples_dropped_one_regime"] == 0


def test_vii_bootstrap_is_seeded_and_joint():
    rng = np.random.default_rng(11)
    positive = pd.Series(rng.random(120) < 0.3)
    d = pd.Series(rng.normal(0, 0.01, 120))
    a = edge.conditional_edge(d, positive, np.random.default_rng(2005), n_resamples=500)
    b = edge.conditional_edge(d, positive, np.random.default_rng(2005), n_resamples=500)
    assert a["bootstrap"] == b["bootstrap"]
    # joint resampling: with every d in the positive regime equal to +1 and every negative to −1, Δ = 2 in every resample
    const = pd.Series(np.where(positive, 1.0, -1.0))
    c = edge.conditional_edge(const, positive, np.random.default_rng(2005), n_resamples=500)
    assert c["bootstrap"]["delta"] == {"ci_low": 2.0, "ci_high": 2.0}


def test_insample_rows_precedence_and_switch_off():
    base = {"n_pos": 30, "delta": 0.002, "mean_positive": 0.001, "mean_negative": -0.001,
            "bootstrap": {"delta": {"ci_low": -0.001, "ci_high": 0.005}}}
    assert edge.insample_row(base) == edge.ROW_SIGN_CONSISTENT
    assert edge.insample_row(dict(base, n_pos=11)) == edge.ROW_NOT_INFORMATIVE
    refuted = dict(base, bootstrap={"delta": {"ci_low": -0.002, "ci_high": MIN_EDGE_PER_MONTH - 1e-9}})
    assert edge.insample_row(refuted) == edge.ROW_REFUTED           # refuted beats sign consistent
    assert edge.insample_row(dict(base, mean_negative=0.0005)) == edge.ROW_INCONCLUSIVE
    assert edge.insample_row(dict(base, delta=-0.001, mean_positive=-0.002)) == edge.ROW_INCONCLUSIVE


def test_mde_formula_matches_the_preregistration_table():
    """§9.6: σ_d = 1.0% a month, 185 months; the table's 10/20/30% rows were
    evaluated at the unrounded share × 185 (18.5, 37, 55.5 months), which is
    why the 10% row reads 7.3% where the integer count 19 gives 7.2% (§16,
    2026-10-23)."""
    for share, per_year in ((0.10, 7.3), (0.20, 5.5), (0.30, 4.8)):
        out = edge.minimum_detectable_effect(0.010, share * 185, (1 - share) * 185)
        assert out["per_year"] * 100 == pytest.approx(per_year, abs=0.05), share   # the table is in percent
    assert edge.minimum_detectable_effect(0.010, 19, 166)["per_year"] * 100 == pytest.approx(7.23, abs=0.01)
    assert np.isnan(edge.minimum_detectable_effect(0.01, 0, 185)["per_year"])


def test_viii_stopping_rule_fires_at_first_qualifying_month():
    flags = [True] * 23 + [False] * 10 + [True]
    assert forward.stopping_month(flags) == 34               # the 24th positive month
    assert forward.stopping_month(flags[:-1]) is None        # not before
    assert forward.stopping_month([False] * 59) is None
    assert forward.stopping_month([False] * 60) == 60        # 60 periods without 24 positives
    assert forward.stopping_month([True] * 24) == 24
    assert forward.stopping_month([True] * 23 + [False] * 37) == 60


def test_forward_verdict_rows():
    good = {"delta": 0.003, "mean_positive": 0.002, "mean_negative": -0.001,
            "newey_west": {"t": 2.1}, "bootstrap": {"delta": {"ci_low": 0.0005, "ci_high": 0.006}}}
    assert forward.forward_verdict(good) == forward.VERDICT_SUPPORTED
    assert forward.forward_verdict(dict(good, newey_west={"t": 1.9})) == forward.VERDICT_INCONCLUSIVE
    assert forward.forward_verdict(dict(good, mean_negative=0.0001)) == forward.VERDICT_INCONCLUSIVE
    assert forward.forward_verdict(dict(good, newey_west={"t": -2.0})) == forward.VERDICT_REFUTED
    tight = dict(good, bootstrap={"delta": {"ci_low": 0.0001, "ci_high": 0.0005}})
    assert forward.forward_verdict(tight) == forward.VERDICT_REFUTED      # refuted tested first
    assert forward.forward_verdict({"delta": 0.0, "newey_west": None, "bootstrap": None}) == forward.VERDICT_INCONCLUSIVE
