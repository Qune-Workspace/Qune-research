"""Pure functions behind the desk view.  No network, no files: every function
takes series in and gives numbers out, so the tests can run on constructed data
and the reader can check each definition in one place.

Conventions
-----------
* Yields are in percent (FRED convention); spreads are returned in basis points.
* "As of" means the last valid observation on or before the date asked for; the
  date actually used is returned beside the value, never hidden.
* The stock-bond correlation is a proxy built from public series only: the daily
  return of the S&P 500 index against the daily *fall* in the 10-year yield (a
  bond-price proxy; the sign is flipped so that a positive number means stocks
  and bonds moved together, as prices).  A constant duration would not change a
  correlation, so none is applied.
"""
from __future__ import annotations

import pandas as pd

BP = 100.0  # basis points per percentage point


def last_valid_on_or_before(series: pd.Series, asof: pd.Timestamp) -> tuple[pd.Timestamp, float]:
    """Return (date, value) of the last non-missing observation on or before ``asof``."""
    window = series.loc[:asof].dropna()
    if window.empty:
        raise ValueError(f"no observation on or before {asof.date()}")
    return window.index[-1], float(window.iloc[-1])


def curve_snapshot(tenors: dict[str, pd.Series], asof: pd.Timestamp) -> pd.DataFrame:
    """One row per tenor: the yield as of the date and the observation date used."""
    rows = []
    for tenor, series in tenors.items():
        date, value = last_valid_on_or_before(series, asof)
        rows.append({"tenor": tenor, "yield_pct": value, "observed_on": date.strftime("%Y-%m-%d")})
    return pd.DataFrame(rows)


def spread_bp(long: pd.Series, short: pd.Series) -> pd.Series:
    """Long minus short, in basis points, on the dates both are observed."""
    aligned = pd.concat([long, short], axis=1, join="inner").dropna()
    return (aligned.iloc[:, 0] - aligned.iloc[:, 1]) * BP


def decomposition(nominal: float, real: float, breakeven: float, term_premium: float) -> dict[str, float]:
    """Split a 10-year nominal yield into its real yield, breakeven inflation and
    the Treasury-model term premium.  ``identity_gap`` is nominal minus real
    minus breakeven, which is zero by the TIPS identity up to rounding and the
    series' different fitting conventions; ``expected_short_rate`` is nominal
    minus term premium, the average policy rate the model's investors expect
    over the ten years.  Everything in percent."""
    return {
        "nominal_pct": nominal,
        "real_pct": real,
        "breakeven_pct": breakeven,
        "term_premium_pct": term_premium,
        "identity_gap_pct": nominal - real - breakeven,
        "expected_short_rate_pct": nominal - term_premium,
    }


def rolling_stock_bond_corr(stock_index: pd.Series, yield_10y: pd.Series, window: int = 63) -> pd.Series:
    """Rolling correlation of daily S&P 500 returns with the daily fall in the
    10-year yield (bond-price proxy), on the days both are observed.  Positive
    means stocks and bonds moved together as prices (the 2022 regime); negative
    means bonds hedged equities (the 2000-2020 regime)."""
    aligned = pd.concat([stock_index, yield_10y], axis=1, join="inner").dropna()
    stock_ret = aligned.iloc[:, 0].pct_change()
    bond_proxy = -aligned.iloc[:, 1].diff()
    corr = stock_ret.rolling(window, min_periods=window).corr(bond_proxy)
    return corr.dropna()


def market_implied_path(effr: pd.Series, bill_3m: pd.Series, note_2y: pd.Series, asof: pd.Timestamp) -> dict:
    """What the front end prices relative to the overnight rate, in basis points:
    the 3-month bill minus the effective funds rate (roughly the next two
    meetings) and the 2-year note minus the effective funds rate (the two-year
    average path, which also carries a small term premium)."""
    d_effr, v_effr = last_valid_on_or_before(effr, asof)
    d_3m, v_3m = last_valid_on_or_before(bill_3m, asof)
    d_2y, v_2y = last_valid_on_or_before(note_2y, asof)
    return {
        "effr_pct": v_effr, "effr_on": d_effr.strftime("%Y-%m-%d"),
        "bill_3m_pct": v_3m, "bill_3m_on": d_3m.strftime("%Y-%m-%d"),
        "note_2y_pct": v_2y, "note_2y_on": d_2y.strftime("%Y-%m-%d"),
        "bill_3m_minus_effr_bp": (v_3m - v_effr) * BP,
        "note_2y_minus_effr_bp": (v_2y - v_effr) * BP,
    }


MINUS = "−"  # the typographic minus the chart tick labels use


def bp(x: float) -> str:
    """Basis points as a signed whole number with the typographic minus: 54.91 -> '+55 bp'."""
    return f"{x:+.0f} bp".replace("-", MINUS)


def curve_finding(tenor_changes_bp: dict[str, float], front_inverted_then: bool, front_inverted_now: bool) -> str:
    """Title of the curve chart, chosen from the one-year change at each tenor.

    ``tenor_changes_bp`` maps the tenor label to its change in basis points over
    the year; the two flags say whether the 2-year sat below the 3-month bill a
    year ago and whether it does today.  The wording cannot overstate: "every
    tenor" needs every sign the same, and the inversion clause needs the flip.
    """
    if not tenor_changes_bp:
        raise ValueError("no tenors")
    values = list(tenor_changes_bp.values())
    most = max(tenor_changes_bp, key=lambda t: abs(tenor_changes_bp[t]))
    lo, hi = min(abs(v) for v in values), max(abs(v) for v in values)
    if all(v > 0 for v in values):
        text = (f"Every tenor yields more than a year ago, by {lo:.0f} to {hi:.0f} bp, most at the {most}")
    elif all(v < 0 for v in values):
        text = (f"Every tenor yields less than a year ago, by {lo:.0f} to {hi:.0f} bp, most at the {most}")
    else:
        parts = ", ".join(f"{t} {bp(v)}" for t, v in tenor_changes_bp.items())
        text = f"The curve has twisted over the year: {parts}"
    if front_inverted_then and not front_inverted_now:
        text += "; the front end no longer inverts"
    elif front_inverted_now and not front_inverted_then:
        text += "; the front end now inverts"
    return text


def front_end_finding(bill_minus_effr_bp: float, note_2y_minus_effr_bp: float, threshold_bp: float = 10.0) -> str:
    """Title of the policy chart from where the bill and the 2-year sit against the funds rate."""
    a, b = bill_minus_effr_bp, note_2y_minus_effr_bp
    where = (f"the 3-month bill sits {bp(a)} and the 2-year note {bp(b)} from the effective funds rate")
    if a > threshold_bp and b > threshold_bp:
        return f"The front end prices a higher policy rate: {where}"
    if a < -threshold_bp and b < -threshold_bp:
        return f"The front end prices cuts: {where}"
    return f"The front end prices a path close to today's rate: {where}"


def decomposition_finding(nominal_bp: float, real_bp: float, breakeven_bp: float, term_premium_bp: float) -> str:
    """Title of the 10-year decomposition chart from the one-year changes in basis points.

    Real yield and breakeven add up to the nominal change by the TIPS identity
    (up to the series' dates and rounding); the term premium is a model estimate
    that overlaps both, so it is stated as a share of the move, not a third addend.
    """
    move = "rise" if nominal_bp >= 0 else "fall"
    n = abs(nominal_bp)
    if abs(real_bp) >= abs(breakeven_bp):
        lead = (f"Of the 10-year's {n:.0f} bp {move} over the year, {bp(real_bp)} is real yield and only "
                f"{bp(breakeven_bp)} breakeven inflation")
    else:
        lead = (f"Of the 10-year's {n:.0f} bp {move} over the year, {bp(breakeven_bp)} is breakeven inflation and "
                f"{bp(real_bp)} real yield")
    return f"{lead}; the term premium accounts for {bp(term_premium_bp)} of it"


def correlation_finding(now: float, share_positive_recent: float, share_positive_before: float,
                        recent_label: str = "since 2022", before_label: str = "in 2016–2021") -> str:
    """Title of the stock-bond correlation chart from the share of positive days in two periods."""
    state = "still positive" if now > 0 else "negative today"
    return (f"Stocks and bonds have moved together on {100 * share_positive_recent:.0f}% of days {recent_label}, "
            f"against {100 * share_positive_before:.0f}% {before_label}; the proxy is {state} at "
            f"{now:+.2f}".replace("-", MINUS))


def change_table(series: pd.Series, asof: pd.Timestamp, lookbacks: dict[str, pd.DateOffset]) -> pd.DataFrame:
    """Value as of the date and the change, in basis points, over each lookback
    (the earlier value is the last valid observation on or before asof minus
    the offset).  Dates used are reported."""
    date_now, now = last_valid_on_or_before(series, asof)
    rows = [{"lookback": "now", "observed_on": date_now.strftime("%Y-%m-%d"), "value_pct": now, "change_bp": 0.0}]
    for label, offset in lookbacks.items():
        date_then, then = last_valid_on_or_before(series, asof - offset)
        rows.append({"lookback": label, "observed_on": date_then.strftime("%Y-%m-%d"),
                     "value_pct": then, "change_bp": (now - then) * BP})
    return pd.DataFrame(rows)
