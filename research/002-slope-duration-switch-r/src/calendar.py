"""Signal dates (FRED calendar) and execution dates (NYSE calendar) (§6.3).

Signal date t = last FRED business day of the month on which both DGS10 and
DTB3 are non-missing.  Execution date e = first NYSE trading day strictly
after t.  The NYSE calendar is rule-based (regular holidays, their observance
rules and the exchange's unscheduled closures since 1962); where actual ETF
bars exist, the backtest additionally resolves e against the bars present
(§6.5) so that any calendar error shows up as logged slippage rather than as
a silent assumption.

This module is ``src.calendar`` (the file name is fixed by §13); it must not
be run with ``src/`` as the working directory or it would shadow the standard
library's ``calendar``.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .config import (
    INSAMPLE_FIRST_SIGNAL_MONTH,
    INSAMPLE_LAST_SIGNAL_MONTH,
    OOS_FIRST_SIGNAL_MONTH,
    OOS_LAST_SIGNAL_MONTH,
    RESULTS_DIR,
    STUDY_DIR,
)

# Unscheduled or one-off NYSE closures since 1962 (weekdays that would
# otherwise be trading days).  Sources: NYSE's published list of historical
# closings; to be re-verified against it at review.
SPECIAL_CLOSURES = [
    "1963-11-25",  # funeral of President Kennedy
    "1968-02-12",  # Lincoln's Birthday (observed by the exchange in 1968)
    "1968-04-09",  # day of mourning for Martin Luther King Jr.
    "1968-07-05",  # day after Independence Day
    "1969-02-10",  # snowstorm
    "1969-03-31",  # funeral of President Eisenhower
    "1969-07-21",  # first lunar landing
    "1972-12-28",  # funeral of President Truman
    "1973-01-25",  # funeral of President Johnson
    "1977-07-14",  # New York City blackout
    "1985-09-27",  # Hurricane Gloria
    "1994-04-27",  # funeral of President Nixon
    "2001-09-11", "2001-09-12", "2001-09-13", "2001-09-14",  # September 11 attacks
    "2004-06-11",  # funeral of President Reagan
    "2007-01-02",  # funeral of President Ford
    "2012-10-29", "2012-10-30",  # Hurricane Sandy
    "2018-12-05",  # funeral of President G. H. W. Bush
    "2025-01-09",  # funeral of President Carter
]
# Paperwork crisis of 1968: the exchange closed every Wednesday from
# 1968-06-12 to the end of the year, except in the weeks of Independence Day
# and Labor Day.
PAPERWORK_CRISIS_START = date(1968, 6, 12)
PAPERWORK_CRISIS_END = date(1968, 12, 31)
PAPERWORK_CRISIS_OPEN_WEDNESDAYS = {date(1968, 7, 3), date(1968, 9, 4)}


def easter_sunday(year: int) -> date:
    """Gregorian Easter (anonymous algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _nearest_workday(d: date) -> date:
    """Saturday -> Friday, Sunday -> Monday (the exchange's observance rule
    for fixed-date holidays other than New Year's Day)."""
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def nyse_holidays(year: int) -> set[date]:
    """Weekday holidays of the NYSE in ``year`` (1962 onwards)."""
    holidays: set[date] = set()
    new_year = date(year, 1, 1)
    if new_year.weekday() == 6:          # Sunday -> Monday; a Saturday is not observed
        holidays.add(new_year + timedelta(days=1))
    elif new_year.weekday() < 5:
        holidays.add(new_year)
    if year >= 1998:
        holidays.add(_nth_weekday(year, 1, 0, 3))                # Martin Luther King Jr. Day
    if year >= 1971:
        holidays.add(_nth_weekday(year, 2, 0, 3))                # Washington's Birthday
    else:
        holidays.add(_nearest_workday(date(year, 2, 22)))
    holidays.add(easter_sunday(year) - timedelta(days=2))        # Good Friday
    if year >= 1971:
        holidays.add(_last_weekday(year, 5, 0))                  # Memorial Day
    elif year <= 1969:
        holidays.add(_nearest_workday(date(year, 5, 30)))
    if year >= 2022:
        holidays.add(_nearest_workday(date(year, 6, 19)))        # Juneteenth
    holidays.add(_nearest_workday(date(year, 7, 4)))             # Independence Day
    holidays.add(_nth_weekday(year, 9, 0, 1))                    # Labor Day
    if year <= 1968 or year in (1972, 1976, 1980):               # Election Day
        holidays.add(_nth_weekday(year, 11, 0, 1) + timedelta(days=1))
    holidays.add(_nth_weekday(year, 11, 3, 4))                   # Thanksgiving
    holidays.add(_nearest_workday(date(year, 12, 25)))           # Christmas
    holidays.update(d for d in map(date.fromisoformat, SPECIAL_CLOSURES) if d.year == year)
    if year == 1968:
        wednesday = PAPERWORK_CRISIS_START
        while wednesday <= PAPERWORK_CRISIS_END:
            if wednesday not in PAPERWORK_CRISIS_OPEN_WEDNESDAYS:
                holidays.add(wednesday)
            wednesday += timedelta(days=7)
    return {d for d in holidays if d.weekday() < 5}


def nyse_trading_days(start, end) -> pd.DatetimeIndex:
    """NYSE trading days in [start, end] from the rule-based calendar."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    weekdays = pd.bdate_range(start, end)
    closed = set()
    for year in range(start.year, end.year + 1):
        closed.update(pd.Timestamp(d) for d in nyse_holidays(year))
    return weekdays[~weekdays.isin(closed)]


def signal_dates(dgs10: pd.Series, dtb3: pd.Series,
                 first_month: str, last_month: str) -> pd.Series:
    """Last FRED business day of each calendar month on which both series are
    non-missing (§6.3), indexed by month period.  A month with no such day
    (never seen in the verified data, §6.5) is NaT."""
    both = pd.concat([dgs10, dtb3], axis=1, sort=True).dropna()
    valid = pd.Series(both.index, index=both.index)
    last_valid = valid.groupby(valid.index.to_period("M")).last()
    months = pd.period_range(first_month, last_month, freq="M")
    return last_valid.reindex(months).rename("signal_date")


def execution_dates(signal: pd.Series, trading_days: pd.DatetimeIndex) -> pd.Series:
    """First trading day strictly after each signal date (§6.3)."""
    if trading_days[-1] <= signal.dropna().max():
        raise ValueError("trading-day calendar ends before the last signal date")
    positions = trading_days.searchsorted(signal.dropna().values, side="right")
    mapped = pd.Series(trading_days[positions], index=signal.dropna().index)
    return mapped.reindex(signal.index).rename("execution_date")


def build_schedule(dgs10: pd.Series, dtb3: pd.Series, first_month: str, last_month: str,
                   trading_days: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    """Monthly schedule: one row per signal month with ``signal_date``,
    ``execution_date`` and ``period_end`` (the next row's execution date;
    NaT on the last row, which starts no holding period inside the window).
    Months without a signal (§6.5) are dropped: the position is held through
    them, so the previous holding period simply runs on."""
    signal = signal_dates(dgs10, dtb3, first_month, last_month)
    n_missing = int(signal.isna().sum())
    signal = signal.dropna()
    if trading_days is None:
        trading_days = nyse_trading_days(signal.iloc[0], signal.iloc[-1] + pd.Timedelta(days=10))
    schedule = pd.DataFrame({"signal_date": signal,
                             "execution_date": execution_dates(signal, trading_days)})
    schedule["period_end"] = schedule["execution_date"].shift(-1)
    schedule.index.name = "month"
    schedule.attrs["months_without_signal"] = n_missing
    return schedule


def holding_periods(schedule: pd.DataFrame) -> pd.DataFrame:
    """Rows of the schedule that start a holding period (all but the last)."""
    return schedule.iloc[:-1]


def main(argv: list[str] | None = None) -> None:
    """Write the signal-to-execution date mapping for both windows.  Uses
    dates only; no return is computed."""
    from .fred import load_series

    parser = argparse.ArgumentParser(description="Signal -> execution date mapping (§6.3).")
    parser.add_argument("--out", default=str(RESULTS_DIR / "execution_calendar.csv"))
    args = parser.parse_args(argv)
    dgs10, dtb3 = load_series("DGS10"), load_series("DTB3")
    frames = []
    for window, first, last in (("insample", INSAMPLE_FIRST_SIGNAL_MONTH, INSAMPLE_LAST_SIGNAL_MONTH),
                                ("oos", OOS_FIRST_SIGNAL_MONTH, OOS_LAST_SIGNAL_MONTH)):
        schedule = build_schedule(dgs10, dtb3, first, last)
        schedule.insert(0, "window", window)
        frames.append(schedule)
        print(f"{window}: {len(schedule)} signal dates, {len(holding_periods(schedule))} holding periods, "
              f"{schedule.attrs['months_without_signal']} months without signal")
    out = pd.concat(frames)
    for col in ("signal_date", "execution_date", "period_end"):
        out[col] = out[col].dt.strftime("%Y-%m-%d")
    out.to_csv(args.out)
    print(f"written {Path(args.out).resolve().relative_to(STUDY_DIR)}")


if __name__ == "__main__":
    main()
