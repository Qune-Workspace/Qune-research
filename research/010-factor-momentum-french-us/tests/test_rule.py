"""Study 010 engine on synthetic factor series only (PREREGISTRATION.md §6.4)."""
import numpy as np
import pandas as pd
import pytest
from src.rule import COST_BASE, TRIALS, Trial, formation_return, run, sign_position, static_exposure, window

H_END = "2026-08"
STARTS = {"SMB": "1926-07", "HML": "1926-07", "ST_Rev": "1926-02", "LT_Rev": "1931-01"}


def synthetic(seed: int = 7) -> pd.DataFrame:
    idx = pd.period_range("1926-02", H_END, freq="M")
    rng = np.random.default_rng(seed)
    f = pd.DataFrame(np.round(rng.normal(0.3, 3.0, (len(idx), 4)), 2), index=idx, columns=list(STARTS))
    for k, s in STARTS.items():
        f.loc[f.index < pd.Period(s, "M"), k] = np.nan
    return f


def test_formation_no_skip_and_window():
    f = synthetic()["SMB"]
    r = formation_return(f, 12)
    t = pd.Period("1950-06", "M")
    months = pd.period_range(t - 12, t - 1, freq="M")
    assert r[t] == pytest.approx(np.prod(1 + f[months] / 100) - 1, abs=1e-15)
    g = f.copy()
    g[t] += 50.0  # f_t itself is not in R_t
    g[t - 13] += 50.0  # nor is t − 13
    assert formation_return(g, 12)[t] == r[t]
    g[t - 1] += 1.0  # t − 1 is
    assert formation_return(g, 12)[t] != r[t]
    assert r[pd.Period("1927-06", "M")] != r[pd.Period("1927-06", "M")]  # NaN: needs 1926-06, not in the file
    assert not np.isnan(r[pd.Period("1927-07", "M")])


def test_tie_takes_minus_one_and_is_counted():
    r = pd.Series([0.0, 5e-13, -1e-13, 2e-12, -0.3, np.nan])
    assert sign_position(r).tolist()[:5] == [-1.0, -1.0, -1.0, 1.0, -1.0]
    assert np.isnan(sign_position(r).iloc[5])
    f = synthetic()
    t = pd.Period("1940-01", "M")
    f.loc[pd.period_range(t - 12, t - 1, freq="M"), "HML"] = 0.0
    out = run(f, TRIALS["T1a"], H_END, COST_BASE)
    assert out["ties"]["HML"] >= 1 and out["h"].loc[t, "HML"] == -1.0


def test_entry_dates_and_K():
    f = synthetic()
    k1 = run(f, TRIALS["T1"], H_END, COST_BASE)["frame"]["K"]
    assert k1.index[0] == pd.Period("1927-07", "M") and k1.index[-1] == pd.Period(H_END, "M") and len(k1) == 1190
    assert (k1[k1.index < pd.Period("1932-01", "M")] == 3).all() and (k1[k1.index >= pd.Period("1932-01", "M")] == 4).all()
    assert (k1 == 3).sum() == 54
    assert (run(f, TRIALS["T1a"], H_END, COST_BASE)["frame"]["K"] == 2).all()
    kb = run(f, TRIALS["T1b"], H_END, COST_BASE)["frame"]["K"]
    assert (kb[kb.index < pd.Period("1931-07", "M")] == 3).all() and (kb[kb.index >= pd.Period("1931-07", "M")] == 4).all()


def test_undefined_formation_in_a_held_month_raises():
    f = synthetic()
    bad = Trial("X", 12, {"LT_Rev": "1931-06"})  # formation would need 1930-06
    with pytest.raises(ValueError):
        run(f, bad, H_END, COST_BASE)


def test_cost_per_flip_and_entry():
    idx = pd.period_range("1926-02", "1935-12", freq="M")
    f = pd.DataFrame(1.0, index=idx, columns=list(STARTS))
    for k, s in STARTS.items():
        f.loc[f.index < pd.Period(s, "M"), k] = np.nan
    # SMB falls for a year so its sign flips to −1 in 1929-01 and back to +1 later
    f.loc[pd.period_range("1928-01", "1928-12", freq="M"), "SMB"] = -2.0
    out = run(f, TRIALS["T1"], "1935-12", 0.10)
    fr, h = out["frame"], out["h"]
    first = pd.Period("1927-07", "M")
    assert fr.loc[first, "cost"] == pytest.approx(0.10 * 3 * 2 / 3)  # three entries at 2c, averaged over K = 3
    flips = h["SMB"].diff().abs().fillna(0) == 2
    assert flips.sum() == 2
    for t in h.index[flips.to_numpy()]:
        assert fr.loc[t, "cost"] == pytest.approx(0.10 * 4 / fr.loc[t, "K"])  # 4c per flip over K
    lt = pd.Period("1932-01", "M")
    assert h.loc[lt, "LT_Rev"] == 1.0 and fr.loc[lt, "cost"] == pytest.approx(0.10 * 2 / 4)  # LT_Rev enters, nothing else trades
    quiet = ~flips & (h.index != first) & (h.index != lt)
    assert (fr.loc[quiet, "cost"] == 0).all()
    assert fr["T"].equals(fr["T_gross"] - fr["cost"])
    assert fr["d"].equals(fr["T"] - fr["B3"])


def test_pm1_versus_long_flat_identity_gross():
    f = synthetic(11)
    for t in TRIALS.values():
        pm = run(f, t, H_END, 0.0)["frame"]["d"]
        lf = run(f, t, H_END, 0.0, mapping="long_flat")["frame"]["d"]
        assert np.allclose(pm, 2 * lf, atol=1e-12)
        assert pm.mean() / pm.std() == pytest.approx(lf.mean() / lf.std(), rel=1e-10)
        # with costs the identity does not hold
        assert not np.allclose(run(f, t, H_END, COST_BASE)["frame"]["d"], 2 * run(f, t, H_END, COST_BASE, mapping="long_flat")["frame"]["d"])


def test_benchmarks_and_frozen_hbar():
    f = synthetic(3)
    out = run(f, TRIALS["T1"], H_END, COST_BASE)
    fr, h, hbar = out["frame"], out["h"], out["hbar"]
    for k in h:
        assert hbar[k] == pytest.approx(h[k].dropna().mean())
    held = h.notna()
    fh = f.reindex(fr.index)[h.columns]
    assert np.allclose(fr["B1"], fh.where(held).sum(axis=1) / fr["K"])
    assert np.allclose(fr["B3"], (fh * hbar).where(held).sum(axis=1) / fr["K"])
    # a window reads rows only: B3 in P1 is the H frame's B3, not re-estimated on P1
    p1 = window(fr, "P1")
    assert p1["B3"].equals(fr.loc[p1.index, "B3"])
    # B1 and B3 pay no cost: unchanged at stress
    st = run(f, TRIALS["T1"], H_END, 0.50)["frame"]
    assert st["B1"].equals(fr["B1"]) and st["B3"].equals(fr["B3"]) and (st["cost"] >= fr["cost"]).all()


def test_static_exposure_zero_when_K_constant():
    f = synthetic(5)
    out = run(f, TRIALS["T1a"], H_END, COST_BASE)
    assert np.allclose(static_exposure(out["h"], out["hbar"]), 0.0, atol=1e-12)
    o1 = run(f, TRIALS["T1"], H_END, COST_BASE)
    se = static_exposure(o1["h"], o1["hbar"])
    h, hb = o1["h"], o1["hbar"]
    for k in h:  # the §9.1 formula written out month by month
        manual = sum((h.loc[t, k] - hb[k]) / h.loc[t].notna().sum() for t in h.index if not np.isnan(h.loc[t, k])) / len(h)
        assert se[k] == pytest.approx(manual, abs=1e-12)


def test_window_counts():
    fr = run(synthetic(), TRIALS["T1"], H_END, COST_BASE)["frame"]
    counts = {w: len(window(fr, w)) for w in ("H", "P1", "L", "P2", "P")}
    assert counts == {"H": 1190, "P1": 432, "L": 630, "P2": 128, "P": 560}


def test_missing_factor_return_in_a_held_month_raises():
    f = synthetic()
    f.loc[pd.Period(H_END, "M"), "HML"] = np.nan  # H's last month: its formation (to 2026-07) is still defined
    with pytest.raises(ValueError, match="factor return is missing"):
        run(f, TRIALS["T1a"], H_END, COST_BASE)
