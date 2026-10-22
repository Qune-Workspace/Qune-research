"""Study 004 §5.3.4 engine checks (i), (ii), (iii), (v), (vi), (viii) on
constructed data.  (iv) and (vii) belong to the signal arithmetic and the
statistics module and are tested where those are built."""
import numpy as np
import pandas as pd
import pytest

from qune_research import dates as cal
from qune_research import engine, sizing


def _bars(start="2004-01-01", end="2006-12-31"):
    return pd.bdate_range(start, end)  # weekdays; holidays are irrelevant to these checks


def _tri(bars, mu, sigma, seed):
    rng = np.random.default_rng(seed)
    r = rng.normal(mu / 252, sigma / np.sqrt(252), len(bars))
    return pd.Series(np.cumprod(1 + r) * 100.0, index=bars)


@pytest.fixture
def world():
    bars = _bars()
    prices = pd.DataFrame({"A": _tri(bars, 0.05, 0.15, 1), "B": _tri(bars, 0.03, 0.06, 2),
                           "C": _tri(bars, 0.0, 0.25, 3)})
    cash = pd.Series(np.cumprod(1 + np.full(len(bars), 0.02 / 252)) * 100.0, index=bars)
    sig = cal.month_end_signal_dates(bars, "2004-12-01", "2006-11-30")
    sched = cal.schedule(bars, sig)
    costs = {"A": 0.0002, "B": 0.0002, "C": 0.0003}
    return bars, prices, cash, sig, sched, costs


def _weights(prices, cash, sig, lookback=12, force=None):
    out = {}
    for t in sig:
        s = {a: (force if force is not None else sizing.trend_signal(prices[a], cash, t, lookback))
             for a in prices.columns}
        v = {a: sizing.realised_vol(prices[a], t) for a in prices.columns}
        out[t] = sizing.target_weights(s, v)
    return out


def test_i_forced_signals_reduce_to_b3_and_cash(world):
    bars, prices, cash, sig, sched, costs = world
    zero = {a: 0.0 for a in costs}
    always_on = engine.run(prices, cash, sched, _weights(prices, cash, sig, force=1.0), zero)
    b3 = engine.run(prices, cash, sched, _weights(prices, cash, sig, force=1.0), zero)
    assert np.allclose(always_on["net"], b3["net"])
    flat = engine.run(prices, cash, sched, _weights(prices, cash, sig, force=0.0), zero)
    e, e_next = sched["execution_date"].iloc[0], sched["period_end"].iloc[0]
    assert flat["net"].iloc[0] == pytest.approx(cash.loc[e_next] / cash.loc[e] - 1.0)
    assert (flat["gross_exposure"] == 0).all()


def test_i_single_asset_full_weight_equals_its_holding_return(world):
    bars, prices, cash, sig, sched, costs = world
    w = {t: {"A": 1.0} for t in sig}
    out = engine.run(prices[["A"]], cash, sched, w, {"A": 0.0})
    e, e_next = sched["execution_date"].iloc[3], sched["period_end"].iloc[3]
    assert out["net"].iloc[3] == pytest.approx(prices["A"].loc[e_next] / prices["A"].loc[e] - 1.0)


def test_ii_relabelling_every_date_moves_the_schedule_and_keeps_every_weight(world):
    """§5.3.4 (ii): dates come from the data, not from anything hard-coded.
    A shift of one trading day would change which bar is the last of a month,
    so the shift used here is one calendar year, which preserves every bar's
    month and ordering (PREREGISTRATION.md §16, 2026-10-22)."""
    bars, prices, cash, sig, sched, costs = world
    w0 = _weights(prices, cash, sig)
    shift = pd.DateOffset(years=1)
    shifted_bars = pd.DatetimeIndex([d + shift for d in bars])
    sp = prices.copy(); sp.index = shifted_bars
    sc = cash.copy(); sc.index = shifted_bars
    ssig = cal.month_end_signal_dates(shifted_bars, "2005-12-01", "2007-11-30")
    assert len(ssig) == len(sig)
    assert all(s == t + shift for s, t in zip(ssig, sig))
    ssched = cal.schedule(shifted_bars, ssig)
    assert all(ssched["execution_date"] == sched["execution_date"] + shift)
    w1 = _weights(sp, sc, ssig)
    for t in sig:
        assert w0[t] == pytest.approx(w1[t + shift])
    out0 = engine.run(prices, cash, sched, w0, costs)
    out1 = engine.run(sp, sc, ssched, w1, costs)
    assert np.allclose(out0["net"].values, out1["net"].values)


def test_iii_no_look_ahead(world):
    bars, prices, cash, sig, sched, costs = world
    t = sig[6]
    before = {a: (sizing.trend_signal(prices[a], cash, t, 12), sizing.realised_vol(prices[a], t))
              for a in prices.columns}
    perturbed = prices.copy()
    perturbed.loc[perturbed.index > t] *= 3.0
    after = {a: (sizing.trend_signal(perturbed[a], cash, t, 12), sizing.realised_vol(perturbed[a], t))
             for a in prices.columns}
    assert before == after


def test_v_weight_identity_cap_and_scale_down():
    sig = {"A": 1.0, "B": 1.0, "C": 1.0, "D": 0.0}
    vols = {"A": 0.15, "B": 0.015, "C": 0.25, "D": 0.10}
    w = sizing.target_weights(sig, vols, sigma_a=0.10, cap=0.25)
    n = 4
    assert w["A"] == pytest.approx(min(0.10 / (n * 0.15), 0.25))
    assert w["B"] == pytest.approx(0.25)          # 0.10/(4*0.015)=1.67 -> capped
    assert w["C"] == pytest.approx(0.10 / (n * 0.25))
    assert w["D"] == 0.0
    assert sum(w.values()) <= 1.0
    # scale-down fires exactly when the raw sum would exceed one
    low = {"A": 0.01, "B": 0.01, "C": 0.01, "D": 0.01}
    w2 = sizing.target_weights({a: 1.0 for a in low}, low, sigma_a=0.10, cap=0.5)
    assert sum(w2.values()) == pytest.approx(1.0)
    assert len(set(round(v, 12) for v in w2.values())) == 1
    w3 = sizing.target_weights({a: 1.0 for a in low}, low, sigma_a=0.10, cap=0.2)
    assert sum(w3.values()) == pytest.approx(0.8)  # 4 × 0.2 < 1: no scale-down
    # an asset with no signal or no vol is absent and does not count in N
    w4 = sizing.target_weights({"A": 1.0, "B": None}, {"A": 0.10, "B": 0.10})
    assert w4 == {"A": pytest.approx(min(0.10 / (1 * 0.10), 0.25))}


def test_vi_cost_equals_turnover_times_rate_and_zero_when_unchanged(world):
    bars, prices, cash, sig, sched, costs = world
    const = {t: {"A": 0.3, "B": 0.2, "C": 0.1} for t in sig}
    out = engine.run(prices, cash, sched, const, costs)
    first = out.iloc[0]
    assert first["turnover"] == pytest.approx(0.6)
    assert first["cost"] == pytest.approx(0.3 * 0.0002 + 0.2 * 0.0002 + 0.1 * 0.0003)
    # later months trade only the drift back to target: cost = Σ|Δw| c, never zero unless no drift
    for i in range(1, len(out)):
        row = out.iloc[i]
        assert row["cost"] <= row["turnover"] * max(costs.values()) + 1e-15
        assert row["cost"] >= row["turnover"] * min(costs.values()) - 1e-15
    # net = (1 − cost)(1 + gross) − 1
    assert np.allclose(out["net"], (1 - out["cost"]) * (1 + out["gross"]) - 1)
    # with every weight zero nothing is traded after the first month and no cost is charged
    flat = engine.run(prices, cash, sched, {t: {} for t in sig}, costs)
    assert (flat["cost"] == 0).all() and (flat["turnover"] == 0).all()


def test_vi_drift_is_tracked(world):
    bars, prices, cash, sig, sched, costs = world
    # hold A at 0.5 for one month; if A doubled while cash was flat the drifted weight is 2/3,
    # so the next month's turnover to 0.5 is 1/6
    bars2 = pd.bdate_range("2004-01-01", "2004-04-30")
    a = pd.Series(100.0, index=bars2); a[a.index > "2004-02-15"] = 200.0
    cash2 = pd.Series(100.0, index=bars2)
    sig2 = cal.month_end_signal_dates(bars2, "2004-01-01", "2004-03-31")
    sched2 = cal.schedule(bars2, sig2)
    out = engine.run(pd.DataFrame({"A": a}), cash2, sched2, {t: {"A": 0.5} for t in sig2}, {"A": 0.0})
    assert out["gross"].iloc[0] == pytest.approx(0.5)
    assert out["turnover"].iloc[1] == pytest.approx(abs(0.5 - 2.0 / 3.0))


def test_viii_exposure_ratio_depends_on_weights_only(world):
    bars, prices, cash, sig, sched, costs = world
    t1 = engine.run(prices, cash, sched, _weights(prices, cash, sig), costs)
    b3 = engine.run(prices, cash, sched, _weights(prices, cash, sig, force=1.0), costs)
    k = engine.exposure_ratio(t1, b3)
    assert 0.0 <= k <= 1.0
    assert k == pytest.approx((t1["gross_exposure"] / b3["gross_exposure"]).mean())
    # changing costs changes no exposure and so not k
    t1b = engine.run(prices, cash, sched, _weights(prices, cash, sig), {a: 0.0 for a in costs})
    assert engine.exposure_ratio(t1b, b3) == pytest.approx(k)


def test_calendar_schedule_and_entry():
    bars = pd.bdate_range("2003-01-01", "2004-03-31")
    sig = cal.month_end_signal_dates(bars, "2003-12-01", "2004-02-29")
    assert list(sig.strftime("%Y-%m-%d")) == ["2003-12-31", "2004-01-30", "2004-02-27"]
    s = cal.schedule(bars, sig)
    assert s["execution_date"].iloc[0] == pd.Timestamp("2004-01-01")
    assert s["period_end"].iloc[0] == s["execution_date"].iloc[1]
    assert pd.isna(s["period_end"].iloc[-1])
    assert cal.months_before(pd.Timestamp("2003-12-31"), 12, bars) is None   # bars start 2003-01
    assert cal.months_before(pd.Timestamp("2004-01-30"), 12, bars) == pd.Timestamp("2003-01-31")
    with pytest.raises(ValueError):
        cal.schedule(bars, cal.month_end_signal_dates(bars, "2004-03-01", "2004-03-31"))


def test_schedule_end_at_last_bar_ends_the_last_period_at_the_last_bar():
    # bars stop on the month-end that is the last signal date (Study 004 §16, 2026-10-22)
    bars = pd.bdate_range("2003-01-01", "2004-02-27")
    sig = cal.month_end_signal_dates(bars, "2003-12-01", "2004-02-29")
    assert list(sig.strftime("%Y-%m-%d")) == ["2003-12-31", "2004-01-30", "2004-02-27"]
    with pytest.raises(ValueError):
        cal.schedule(bars, sig)
    s = cal.schedule(bars, sig, end_at_last_bar=True)
    assert len(s) == 3
    assert s["execution_date"].iloc[0] == pd.Timestamp("2004-01-01")
    assert s["execution_date"].iloc[1] == pd.Timestamp("2004-02-02")
    assert pd.isna(s["execution_date"].iloc[-1])        # the last signal starts no period
    assert s["period_end"].iloc[0] == pd.Timestamp("2004-02-02")
    assert s["period_end"].iloc[1] == pd.Timestamp("2004-02-27")   # one day short of 2004-03-01
    assert pd.isna(s["period_end"].iloc[-1])
    # unchanged when the bars do reach the next execution date
    bars2 = pd.bdate_range("2003-01-01", "2004-03-31")
    s2 = cal.schedule(bars2, sig, end_at_last_bar=True)
    assert s2["period_end"].iloc[1] == pd.Timestamp("2004-03-01")
    assert s2.equals(cal.schedule(bars2, sig))
    # still refuses when more than the last signal has no execution bar
    with pytest.raises(ValueError):
        cal.schedule(bars, pd.DatetimeIndex(["2004-02-27", "2004-03-31"]), end_at_last_bar=True)
