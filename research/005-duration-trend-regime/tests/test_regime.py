"""§5.3.5 (ii)–(v) and the regime descriptives on constructed series."""
import numpy as np
import pandas as pd
import pytest
from src import regime
from src.config import CPI_LAG_MONTHS, REGIME_WINDOWS
from src.schedule import build_schedule

from tests.toy import toy_bars, toy_closes, toy_cpi


@pytest.fixture(scope="module")
def world():
    bars = toy_bars()
    closes = toy_closes(bars)
    schedule = build_schedule(bars, "2001-01", "2007-11")
    returns = regime.common_returns(closes["SPY"], closes["IEF"])
    return {"bars": bars, "closes": closes, "schedule": schedule, "returns": returns}


def test_iv_sign_is_recovered_on_constructed_correlation(world):
    """(iv): with a correlation of about ±0.6 by construction, the flag at
    each signal date matches the sign of the block the window sits in, on
    every date whose whole window lies inside one block."""
    frame = regime.correlation_regime(world["returns"], world["schedule"]["signal_date"], "T1")
    sign = world["closes"]["sign"]
    positions = world["bars"].get_indexer(frame["signal_date"])
    checked = 0
    for month, pos in zip(frame.index, positions):
        block_start = (pos // 252) * 252
        if pos - block_start + 1 >= 63 + 1:      # the 63 returns use 64 bars, all inside the block
            assert bool(frame.at[month, "positive"]) == (sign.iloc[pos] > 0), str(month)
            checked += 1
    assert checked > 40


def test_iv_window_is_exactly_n_common_return_days_across_a_gap(world):
    """(iv): the window counts common return days; removing ten SPY bars
    before a signal date lengthens the span and keeps 63 returns."""
    t = world["schedule"]["signal_date"].iloc[40]
    spy = world["closes"]["SPY"].copy()
    pos = spy.index.get_loc(t)
    spy = spy.drop(spy.index[pos - 30:pos - 20])
    returns = regime.common_returns(spy, world["closes"]["IEF"])
    upto = returns.loc[:t]
    tail = upto.iloc[-63:]
    assert len(tail) == 63
    assert tail.index[0] < world["returns"].loc[:t].iloc[-63:].index[0]       # the span grew
    rho = regime.trailing_correlation(returns, world["schedule"]["signal_date"], 63)
    expected = float(np.corrcoef(tail["SPY"], tail["IEF"])[0, 1])
    assert rho.loc[world["schedule"].index[40]] == pytest.approx(expected, abs=1e-15)
    # the gap removed a day from SPY only: IEF's return across the gap is its own, not spliced
    assert returns.loc[:t].index.isin(spy.index).all()


def test_iv_fewer_than_window_days_is_undefined_not_short(world):
    rho = regime.trailing_correlation(world["returns"].iloc[:50], world["schedule"]["signal_date"].iloc[:3], 63)
    assert rho.isna().all()
    with pytest.raises(ValueError):
        regime.regime_from_rho(rho)


def test_ii_shifting_every_series_by_one_day_moves_dates_not_flags(world):
    """(ii): shift both closes forward by one bar; every regime flag is the
    same, every signal date one bar later (the toy bars are NYSE days, so a
    one-bar shift keeps every month-end structure except where the month
    boundary moves; those months are excluded by comparing on dates)."""
    bars = world["bars"]
    shifted = {k: pd.Series(v.to_numpy(), index=bars[1:len(v) + 1] if len(v) < len(bars) else bars, name=k)
               for k, v in world["closes"].items() if k != "sign"}
    # shift by one bar: value on bars[i] moves to bars[i+1]
    shifted = {k: pd.Series(v.to_numpy()[:-1], index=bars[1:], name=k) for k, v in world["closes"].items() if k != "sign"}
    returns_shifted = regime.common_returns(shifted["SPY"], shifted["IEF"])
    base = regime.trailing_correlation(world["returns"], world["schedule"]["signal_date"], 63).dropna()
    # the same 63 returns end one bar later: evaluate the shifted series at the next bar after each signal date
    next_bar = pd.Series(bars[bars.get_indexer(base.index.map(world["schedule"]["signal_date"])) + 1], index=base.index)
    moved = regime.trailing_correlation(returns_shifted, next_bar, 63)
    assert np.allclose(base.to_numpy(), moved.to_numpy(), atol=1e-15)


def test_iii_no_lookahead_in_correlation(world):
    """(iii): perturbing SPY and IEF after a signal date leaves that date's
    correlation unchanged."""
    t = world["schedule"]["signal_date"].iloc[30]
    month = world["schedule"].index[30]
    base = regime.trailing_correlation(world["returns"], world["schedule"]["signal_date"], 63)
    spy, ief = world["closes"]["SPY"].copy(), world["closes"]["IEF"].copy()
    spy.loc[spy.index > t] *= 3.0
    ief.loc[ief.index > t] = ief.loc[ief.index > t].to_numpy()[::-1]
    perturbed = regime.trailing_correlation(regime.common_returns(spy, ief), world["schedule"]["signal_date"], 63)
    assert perturbed.loc[month] == base.loc[month]
    assert (perturbed.loc[:month].dropna() == base.loc[:month].dropna()).all()
    # perturbing the signal-date bar itself does change it (the window ends at t inclusive)
    spy2 = world["closes"]["SPY"].copy()
    spy2.loc[t] *= 1.05
    assert regime.trailing_correlation(regime.common_returns(spy2, world["closes"]["IEF"]),
                                       world["schedule"]["signal_date"], 63).loc[month] != base.loc[month]


def test_t2_uses_252_days(world):
    frame = regime.correlation_regime(world["returns"], world["schedule"]["signal_date"], "T2")
    assert REGIME_WINDOWS["T2"] == 252
    t = frame["signal_date"].iloc[5]
    tail = world["returns"].loc[:t].iloc[-252:]
    assert frame["rho"].iloc[5] == pytest.approx(float(np.corrcoef(tail["SPY"], tail["IEF"])[0, 1]), abs=1e-15)
    early = build_schedule(world["bars"], "2000-02", "2001-12")["signal_date"]
    t1_months = regime.correlation_regime(world["returns"], early, "T1")
    t2_months = regime.correlation_regime(world["returns"], early, "T2")
    assert len(t2_months) < len(t1_months)            # the longer window needs more history before its first flag
    assert t1_months.index[0] == pd.Period("2000-04", "M")   # 63 returns need 64 bars: the April 2000 month-end
    assert t2_months.index[0] == pd.Period("2001-01", "M")


def test_v_cpi_flag_reads_month_m_minus_2_and_no_later(world):
    """(v): the flag at the signal date of month m is the twelve-month change
    for month m − 2 against 3%; changing any later month's level does not
    move it, changing month m − 2's does."""
    cpi = toy_cpi()
    frame = regime.cpi_regime(cpi, world["schedule"]["signal_date"])
    m = frame.index[20]
    lagged = pd.Period(m, "M") - CPI_LAG_MONTHS
    expected = cpi.loc[lagged] / cpi.loc[lagged - 12] - 1.0
    assert frame.at[m, "cpi_12m_change"] == pytest.approx(expected, abs=1e-15)
    assert frame.at[m, "cpi_month"] == str(lagged)
    assert bool(frame.at[m, "positive"]) == (expected > 0.03)
    later = cpi.copy()
    later.loc[lagged + 1:] *= 1.5
    assert regime.cpi_regime(later, world["schedule"]["signal_date"]).at[m, "cpi_12m_change"] == pytest.approx(expected, abs=1e-15)
    moved = cpi.copy()
    moved.loc[lagged] *= 1.10
    assert regime.cpi_regime(moved, world["schedule"]["signal_date"]).at[m, "cpi_12m_change"] > expected
    assert bool(regime.cpi_regime(moved, world["schedule"]["signal_date"]).at[m, "positive"])


def test_regime_episodes_counts():
    flags = pd.Series([False, True, True, False, True, True, True, False, False])
    out = regime.regime_episodes(flags)
    assert out == {"months": 9, "positive_months": 5, "positive_share": 5 / 9, "regime_changes": 4,
                   "positive_episodes": 2, "mean_positive_episode_months": 2.5, "longest_positive_episode_months": 3}


def test_v_missing_cpi_month_reads_latest_earlier_print_never_later(world):
    """§16 amendment 2026-10-23: a month without a published CPI value (the
    BLS skipped October 2025) makes the twelve-month change undefined for
    that month and for the month a year later; the flag for a signal month
    whose m − 2 falls there reads the latest defined change on or before
    m − 2, is marked as filled, and never reads a later month."""
    cpi = toy_cpi()
    dates = world["schedule"]["signal_date"]
    frame = regime.cpi_regime(cpi, dates)
    m = frame.index[30]
    lagged = pd.Period(m, "M") - CPI_LAG_MONTHS
    gapped = cpi.copy()
    gapped.loc[lagged] = float("nan")
    filled = regime.cpi_regime(gapped, dates)
    assert filled.at[m, "cpi_month"] == str(lagged - 1) and bool(filled.at[m, "cpi_month_filled"])
    assert filled.at[m, "cpi_12m_change"] == pytest.approx(cpi.loc[lagged - 1] / cpi.loc[lagged - 13] - 1.0, abs=1e-15)
    # the month twelve months after the gap is undefined too and reads the month before it
    m12 = m + 12
    assert filled.at[m12, "cpi_month"] == str(lagged + 11) and bool(filled.at[m12, "cpi_month_filled"])
    # every other month reads its own m - 2
    others = filled.index.difference([m, m12])
    assert not filled.loc[others, "cpi_month_filled"].any()
    assert (filled.loc[others, "cpi_12m_change"] == frame.loc[others, "cpi_12m_change"]).all()
    # a later month's level never moves the filled value
    later = gapped.copy()
    later.loc[lagged + 1:] *= 1.5
    assert regime.cpi_regime(later, dates).at[m, "cpi_12m_change"] == pytest.approx(filled.at[m, "cpi_12m_change"], abs=1e-15)
