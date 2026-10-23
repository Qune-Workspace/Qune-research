"""Rule-based NYSE trading calendar (Study 004 §5.3.1, §6.3).

Copied by attribution from Study 003's frozen ``src/calendar.py`` (itself
copied unchanged from Study 002), which the data checks of Studies 001–003
used: regular holidays with their observance rules, the exchange's
unscheduled closures since 1962 and the 1968 paperwork-crisis Wednesdays.
Only the module name changed (``nyse`` rather than ``calendar``, so that it
can never shadow the standard library).  The backtest engine resolves
execution dates against the bars actually present, so a calendar error shows
up as a coverage finding, never as a silent assumption.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

# Unscheduled or one-off NYSE closures since 1962 (weekdays that would
# otherwise be trading days).  Source: NYSE's published list of historical
# closings; Study 003's review did not contest it.
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
PAPERWORK_CRISIS_START = date(1968, 6, 12)
PAPERWORK_CRISIS_END = date(1968, 12, 31)
PAPERWORK_CRISIS_OPEN_WEDNESDAYS = {date(1968, 7, 3), date(1968, 9, 4)}


def easter_sunday(year: int) -> date:
    """Gregorian Easter (Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _nearest_workday(d: date) -> date:
    """Saturday -> Friday, Sunday -> Monday (NYSE observance rule)."""
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
    closed: set[pd.Timestamp] = set()
    for year in range(start.year, end.year + 1):
        closed.update(pd.Timestamp(d) for d in nyse_holidays(year))
    return weekdays[~weekdays.isin(closed)]
