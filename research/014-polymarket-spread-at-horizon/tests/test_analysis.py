"""§6.5 tests of the pure analysis on synthetic rows: the tick floor, the bins, the fit, its clustered error,
the bootstrap, the no-fit rule, the power and the verdict texts."""

import math

import numpy as np
import pytest
from src import analysis as an

# --- §6.2: spread, mid, the tick floor -------------------------------------------------------------------------

def test_locked_book_reads_tick_over_mid_and_is_counted():
    q = an.quote_variables(0.05, 0.05, 0.01)
    assert q.locked and q.floored and not q.tick_null
    assert q.s == pytest.approx(0.01 / 0.05)
    assert q.half_points == 0.0


def test_null_tick_reads_0_001_and_is_counted():
    q = an.quote_variables(0.05, 0.05, None)
    assert q.tick_null and q.tick == 0.001 and q.s == pytest.approx(0.001 / 0.05)
    q2 = an.quote_variables(0.05, 0.05, None, null_tick=an.ALT_NULL_TICK)
    assert q2.tick == 0.01 and q2.s == pytest.approx(0.01 / 0.05)


def test_tick_below_0_001_is_kept_and_counted():
    q = an.quote_variables(0.05, 0.05, 0.0001)
    assert q.tick_below and q.tick == 0.0001 and q.s == pytest.approx(0.0001 / 0.05)


def test_quote_below_tick_is_floored_and_a_normal_quote_is_not():
    below = an.quote_variables(0.500, 0.505, 0.01)
    assert below.floored and not below.locked and below.s == pytest.approx(0.01 / 0.5025)
    assert below.half_points == pytest.approx(0.25)  # q / 2 in points, not floored
    normal = an.quote_variables(0.50, 0.52, 0.01)
    assert not normal.floored and normal.s == pytest.approx(0.02 / 0.51) and normal.ln_s == pytest.approx(math.log(0.02 / 0.51))


@pytest.mark.parametrize("bid,ask,tick", [(0.05, 0.06, 0.01), (0.02, 0.03, 0.01), (0.07, 0.08, 0.01), (0.050, 0.051, 0.001),
                                          (0.49, 0.50, 0.01), (0.1, 0.2, 0.1)])
def test_a_quote_exactly_one_tick_wide_is_not_floored(bid, ask, tick):
    # 0.06 - 0.05 = 0.009999999999999995 in floats; the flag is decided on q and the tick rounded to nine places
    # (code review 2026-11-17, must-fix 3: with q < tick on floats, 18 of 98 one-tick quotes on the 0.01 grid read floored)
    q = an.quote_variables(bid, ask, tick)
    assert not q.floored and not q.locked
    assert q.s == pytest.approx(tick / q.mid)  # s is max(q, tick) / mid, equal to tick / mid to 1e-15 here
    assert an.quote_variables(bid, ask, tick + 1e-9).floored  # a tick a hair above q: floored on the rounded comparison


def test_one_tick_quotes_on_the_grid_are_never_floored():
    grid = [round(i * 0.01, 2) for i in range(1, 100)]
    flagged = [b for b in grid[:-1] if an.quote_variables(b, round(b + 0.01, 2), 0.01).floored]
    assert flagged == []
    grid3 = [round(i * 0.001, 3) for i in range(1, 1000)]
    assert [b for b in grid3[:-1] if an.quote_variables(b, round(b + 0.001, 3), 0.001).floored] == []


def test_row_as_recorded_rule():
    assert an.row_as_recorded(0.55, 0.65, 0.6)
    assert not an.row_as_recorded(0.65, 0.55, 0.6)  # bid above ask
    assert not an.row_as_recorded(0.0, 0.1, 0.05)  # bid not in (0, 1)
    assert not an.row_as_recorded("0.5", 0.6, 0.55)  # not a number on the row
    assert not an.row_as_recorded(0.55, 0.65, 0.61)  # mid off Study 013's p
    assert an.row_as_recorded(0.55, 0.65, 0.6 + 5e-10)
    assert not an.row_as_recorded(0.55, 0.65, 0.6 + 2e-9)  # the 1e-9 tolerance of §6.2, not a looser one


# --- §6.3: bins at every boundary and on the two float pairs ----------------------------------------------------

@pytest.mark.parametrize("mid,expected", [
    (0.01, an.LONGSHOT), (0.0099999, None), (0.10, None), (0.099999999, an.LONGSHOT),
    (0.40, an.CENTRAL), (0.399999999, None), (0.60, an.CENTRAL), (0.600000001, None),
    (0.90, None), (0.900000001, an.HIGH), (0.99, an.HIGH), (0.990000001, None), (0.25, None),
    # a tenth place beyond the nine the rule rounds on is absorbed by the rounding (§6.3): the edge is on the rounded mid
    (0.0999999999, None), (0.3999999999, an.CENTRAL), (0.6000000001, an.CENTRAL), (0.9000000001, None), (0.9900000001, an.HIGH),
])
def test_bin_boundaries(mid, expected):
    assert an.assign_bin(mid) == expected


def test_the_two_float_pairs_of_section_6_3():
    assert (0.55 + 0.65) / 2 == 0.6000000000000001  # the float the document names
    assert an.assign_bin((0.55 + 0.65) / 2) == an.CENTRAL
    assert (0.051 + 0.149) / 2 == 0.09999999999999999
    # the quotes' true mid is 0.100, which the longshot bin excludes; without the rounding the float would fall inside
    assert an.assign_bin((0.051 + 0.149) / 2) is None
    assert 0.01 <= (0.051 + 0.149) / 2 < 0.10  # the unrounded float would have passed the rule's text
    assert an.assign_bin(0.10) is None and an.assign_bin(0.6) == an.CENTRAL


def test_deciles_cover_the_unit_interval_with_the_last_closed():
    assert [an.decile(x) for x in (0.0, 0.05, 0.1, 0.55, 0.9, 0.99, 1.0)] == [0, 0, 1, 5, 9, 9, 9]
    assert an.decile((0.051 + 0.149) / 2) == 1  # a true mid of 0.100 sits in the second decile, as the rounded mid says
    # the labels are the document's: [0.01, 0.10) first, [0.90, 0.99] last (Study 013's p lies in [0.01, 0.99])
    assert an.DECILE_EDGES[0] == 0.01 and an.DECILE_EDGES[-1] == 0.99 and len(an.DECILE_EDGES) == 11


# --- §9.1, §9.3: the fit ---------------------------------------------------------------------------------------

def _synthetic(n1=40, n0=40, seed=3, clusters_per_bin=10):
    rng = np.random.default_rng(seed)
    y1 = rng.normal(-1.0, 0.5, n1)
    y0 = rng.normal(-3.0, 0.4, n0)
    y = np.concatenate([y1, y0])
    L = np.concatenate([np.ones(n1), np.zeros(n0)])
    g = np.concatenate([np.arange(n1) % clusters_per_bin, 100 + np.arange(n0) % clusters_per_bin]).astype(str)
    return y, L, g


def test_delta_hat_is_the_difference_of_the_two_bin_means_to_1e_12():
    y, L, g = _synthetic()
    f = an.fit_delta(y, L, g)
    assert f.fitted
    assert abs(f.delta - (y[L == 1].mean() - y[L == 0].mean())) < 1e-12
    assert abs(f.alpha - y[L == 0].mean()) < 1e-12
    assert f.n == 80 and f.n_longshot == 40 and f.n_central == 40 and f.G == 20
    assert f.G_longshot == 10 and f.G_central == 10  # §9.6: G in each decision bin
    assert f.t_cl == pytest.approx(f.delta / f.se_cl)
    lo, hi = an.wald(f)
    assert lo == pytest.approx(f.delta - 1.96 * f.se_cl) and hi == pytest.approx(f.delta + 1.96 * f.se_cl)


def test_three_cluster_sandwich_by_hand():
    # A: (L=1, y=1), (L=0, y=0); B: (1, 2), (1, 4); C: (0, 1), (0, 3): Delta-hat = 1, alpha-hat = 4/3,
    # scores (-8/3, -4/3), (4/3, 4/3), (4/3, 0); V = 3/2 * 32/81 = 16/27; SE_cl = 4 / sqrt(27)
    y = np.array([1.0, 0.0, 2.0, 4.0, 1.0, 3.0])
    L = np.array([1.0, 0.0, 1.0, 1.0, 0.0, 0.0])
    g = np.array(["A", "A", "B", "B", "C", "C"])
    f = an.fit_delta(y, L, g)
    assert f.delta == pytest.approx(1.0, abs=1e-12) and f.alpha == pytest.approx(4 / 3, abs=1e-12)
    assert f.se_cl == pytest.approx(4 / math.sqrt(27), abs=1e-12)
    assert f.se_ordinary == pytest.approx(math.sqrt((84 / 9) / 4 * 2 / 3), abs=1e-12)
    assert f.G == 3 and f.G_longshot == 2 and f.G_central == 2


def test_clustered_se_equals_hc0_times_n_over_n_minus_1_with_one_row_per_cluster():
    y, L, _ = _synthetic(n1=25, n0=35)
    g = np.arange(y.size).astype(str)
    f = an.fit_delta(y, L, g)
    hc0 = an.hc0_se_delta(y, L)
    n = y.size
    assert f.se_cl == pytest.approx(hc0 * math.sqrt(n / (n - 1)), rel=1e-12)
    assert f.se_ordinary > 0 and f.se_ordinary != f.se_cl


def test_no_fit_on_an_empty_bin_one_cluster_and_zero_se():
    y, L, g = _synthetic()
    empty = an.fit_delta(y[L == 1], L[L == 1], g[L == 1])
    assert not empty.fitted and empty.no_fit_reason == "empty decision bin"
    one = an.fit_delta(y, L, np.array(["c"] * y.size))
    assert not one.fitted and one.no_fit_reason == "fewer than two clusters"
    # two clusters, each a bin with every row at one value: residuals are 0, so the sandwich is 0
    yy = np.array([-1.0, -1.0, -3.0, -3.0])
    LL = np.array([1.0, 1.0, 0.0, 0.0])
    gg = np.array(["a", "a", "b", "b"])
    zero = an.fit_delta(yy, LL, gg)
    assert not zero.fitted and zero.no_fit_reason == "SE_cl is 0"
    assert math.isnan(zero.delta) and math.isnan(zero.t_cl)
    # a sandwich that is zero in exact arithmetic but about 1e-16 in floats (should-fix 1): still "no fit", never t ~ 1e13
    v1, v0 = math.log(0.001 / 0.05), math.log(0.01 / 0.5)
    y2 = np.array([v1, v1, v0, v0])
    near = an.fit_delta(y2, LL, gg)
    assert not near.fitted and near.no_fit_reason == "SE_cl is 0"
    with_rows = an.fit_delta(np.array([v1, v1, v1, v0, v0, v0]), np.array([1.0, 1.0, 1.0, 0.0, 0.0, 0.0]),
                             np.array(["a", "a", "b", "c", "c", "d"]))
    assert not with_rows.fitted


def test_bootstrap_is_seeded_and_drops_resamples_with_an_empty_bin():
    y, L, g = _synthetic()
    a = an.cluster_bootstrap(y, L, g, resamples=200)
    b = an.cluster_bootstrap(y, L, g, resamples=200)
    assert (a.low, a.high, a.dropped) == (b.low, b.high, b.dropped) and a.available
    c = an.cluster_bootstrap(y, L, g, resamples=200, seed=an.BOOTSTRAP_SEED + 1)
    assert (c.low, c.high) != (a.low, a.high)
    assert a.low < y[L == 1].mean() - y[L == 0].mean() < a.high
    # one cluster per bin: half of the resamples draw one cluster twice, so a bin is empty and the resample is dropped
    g2 = np.where(L == 1, "l", "c")
    d = an.cluster_bootstrap(y, L, g2, resamples=200)
    assert d.dropped > 2 and not d.available and math.isnan(d.low)
    assert an.BOOTSTRAP_SEED == 14 and an.BOOTSTRAP_RESAMPLES == 2000


def test_bootstrap_availability_boundary_is_exactly_one_percent():
    assert an.bootstrap_available(20, 2000, 1980)  # exactly 1 percent is not "more than"
    assert not an.bootstrap_available(21, 2000, 1979)
    assert an.bootstrap_available(1, 100, 99) and not an.bootstrap_available(2, 115, 113)
    assert not an.bootstrap_available(0, 2000, 1)  # percentiles need two kept resamples


# --- §9.4–§9.6: power, criteria, verdict texts ----------------------------------------------------------------

def test_power_figures():
    p = an.power(0.1)
    assert p["mde_2.842"] == pytest.approx(0.2842) and p["mde_2.970"] == pytest.approx(0.297)
    assert p["mde_2.486"] == pytest.approx(0.2486)
    assert p["ratio"] == pytest.approx(0.2842 / 1.18)
    assert an.power(0.59 / 2.842)["ratio"] == pytest.approx(0.50)  # ratio 0.50 is where the MDE equals the bar


def test_low_power_label_boundary():
    assert not an.low_power(0.50) and an.low_power(0.5001) and not an.low_power(0.49)
    assert not an.low_power(float("nan"))


def _fit(delta, t, fitted=True, se=None):
    nan = float("nan")
    if se is None:
        se = delta / t if fitted and t else nan
    return an.Fit(400, 200, 200, 150, 80, 70, fitted, None if fitted else "empty decision bin", -3.0, delta if fitted else nan,
                  se, se, t if fitted else nan, 0.5, 0.4)


def test_criteria_and_headline_precedence():
    strong = _fit(0.8, 3.0)
    half = _fit(0.3, 2.5)
    weak_t = _fit(0.8, 1.5)
    nofit = _fit(0.0, 0.0, fitted=False)
    c_ok = an.criteria(strong, strong, strong)
    assert all(c_ok.values())
    assert an.criteria(strong, strong, nofit)["C4"] is False  # C4 needs both halves fitted
    assert an.criteria(strong, strong, _fit(-0.1, -0.5))["C4"] is False
    assert an.criteria(strong, strong, _fit(0.0, 0.0, se=0.2))["C4"] is False  # C4 is Delta-hat > 0, not >= 0
    assert an.criteria(nofit, strong, strong) == {"C1": False, "C2": False, "C3": False, "C4": False}
    exact = _fit(0.59, 2.128)
    assert an.criteria(exact, exact, exact) == {"C1": True, "C2": True, "C3": True, "C4": True}  # the bars are >=
    assert an.criteria(_fit(0.5899, 2.128), exact, exact)["C1"] is False
    assert an.criteria(_fit(0.59, 2.1279), exact, exact)["C3"] is False
    assert an.criteria(half, half, half)["C1"] is False and an.criteria(weak_t, weak_t, weak_t)["C2"] is False
    assert an.headline(strong, c_ok, "meets C1–C4", False).startswith("supported in one forward window (W: ")
    assert "2026-11-04, 2026-12-30" in an.headline(strong, c_ok, "meets C1–C4", False)
    assert an.headline(strong, c_ok, "not supported", False) == "inconclusive (fragile: Sports)"
    assert an.headline(strong, c_ok, "not supported (no fit)", False) == "inconclusive (fragile: Sports)"
    assert an.headline(half, an.criteria(half, half, half), "meets C1–C4", False).startswith(
        "not supported (a premium below half the published size: Δ̂ = 0.300, t_cl = 2.50)")
    assert an.headline(nofit, an.criteria(nofit, nofit, nofit), "meets C1–C4", False) == "not supported (no fit)"
    assert an.headline(_fit(-0.2, -1.0), an.criteria(_fit(-0.2, -1.0), half, half), "meets C1–C4", False) == "not supported"
    assert an.headline(strong, c_ok, "meets C1–C4", True).endswith(an.LOW_POWER_LABEL)
    assert an.companion_row(nofit, an.criteria(nofit, nofit, nofit)) == "not supported (no fit)"
    assert an.companion_row(strong, c_ok) == "meets C1–C4"


def test_verdict_rows_put_the_low_power_label_on_every_row():
    strong = _fit(0.8, 3.0)
    fits = {"M1": strong, "M1a": strong, "M1b": _fit(0.3, 2.5)}
    crit = {t: an.criteria(f, f, f) for t, f in fits.items()}
    rows = an.verdict_rows(fits, crit, False)
    assert rows["M1"].startswith("supported in one forward window") and rows["M1a"] == "meets C1–C4" and rows["M1b"] == "not supported"
    rows_lp = an.verdict_rows(fits, crit, True)
    assert all(r.endswith(an.LOW_POWER_LABEL) for r in rows_lp.values())
    fits_fragile = dict(fits, M1a=_fit(0.3, 2.5))
    crit_fragile = {t: an.criteria(f, f, f) for t, f in fits_fragile.items()}
    assert an.verdict_rows(fits_fragile, crit_fragile, False)["M1"] == "inconclusive (fragile: Sports)"


def test_wa26_compression_matches_the_documents_figures():
    assert an.wa26_compression_points(0.05) == pytest.approx(1.4, abs=0.1)
    assert an.wa26_compression_points(0.60) == pytest.approx(1.1, abs=0.1)
