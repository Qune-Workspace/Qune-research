"""Would the proposed bar-age rule (RISK_CLEARANCE condition 3) pass the
Study 003 sleeve's own orders?  Calendar arithmetic only: no prices, no
returns, nothing fetched, so it is not a trial and cannot see an outcome.

Question.  Condition 3 quotes Independent Risk's opinion of a timeframe-aware
rule: "signal bar is the last closed bar of the strategy's own timeframe, at
most one bar-length plus 24 h old".  For daily bars that reads as 48 h.  The
owner was asked (daily summary 2026-10-27) to approve a rule of this shape.
This script checks the wording against the orders the monthly runner sends.

Inputs, all from committed code:
* signal date t = last NYSE trading day of the month, execution date e = the
  next NYSE trading day (``src.calendar``, the backtest's own calendar);
* orders are sent inside 15:30-16:00 ET on e (run-monthly-core.mjs
  ``windowEt``); an engine-blocked buy is retried on up to three later
  sessions with the same signal record (``maxEngineRetries``);
* the runner sets ``signal_bar_time`` to ``<t>T04:00:00Z`` (the daily bar's
  timestamp as Alpaca returns it) and the engine computes
  age = now - signal_bar_time - 1 h (risk.mjs, written for hourly bars).

Rules compared (each fixed here before the first run):
* R0  the engine today: age <= 2 h;
* R1  the quoted wording with the engine's own age arithmetic: age <= 48 h;
* R1c the quoted wording with age counted from the bar's real close
      (16:00 ET on t, 13:00 ET on an early-close day is ignored: using 16:00
      makes the age shorter, so it can only flatter the rule);
* R2  a session-count form: the signal bar is dated on an NYSE session and
      at most k NYSE sessions lie strictly between t and the order's session
      (k = 0 for the first attempt; k = 3 to also admit the three retries).

Reading rule (fixed before the run): a rule "works" only if it passes every
first attempt at both ends of the window (15:30 and 15:59 ET) for every month
from 2026-10 to 2036-12.  Any failure is reported with its count and the
first failing month.  The calendar is rule-based and cannot know closures not
yet announced; that limit is stated in the output.

Run from the study folder: ``python -m paper.bar_age_rule_check``.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from src.calendar import nyse_trading_days

ET = ZoneInfo("America/New_York")
FIRST, LAST = "2026-10", "2036-12"
WINDOW = (time(15, 30), time(15, 59))
RETRIES = 3


def engine_age_h(signal_day, now_utc: datetime) -> float:
    bar_ts = datetime(signal_day.year, signal_day.month, signal_day.day, 4, 0, tzinfo=timezone.utc)
    return (now_utc - bar_ts - timedelta(hours=1)).total_seconds() / 3600


def close_age_h(signal_day, now_utc: datetime) -> float:
    close = datetime.combine(signal_day, time(16, 0), tzinfo=ET)
    return (now_utc - close).total_seconds() / 3600


def at_et(day, t: time) -> datetime:
    return datetime.combine(day, t, tzinfo=ET).astimezone(timezone.utc)


def main() -> None:
    days = nyse_trading_days("2026-09-01", "2037-02-28")
    s = pd.Series(days, index=days)
    sig = s.groupby(days.to_period("M")).last()
    sig = sig[(sig.index >= pd.Period(FIRST)) & (sig.index <= pd.Period(LAST))]
    rows = []
    for month, t in sig.items():
        i = days.get_loc(t)
        for attempt in range(RETRIES + 1):
            e = days[i + 1 + attempt]
            between = attempt  # sessions strictly between t and e
            for w in WINDOW:
                now = at_et(e.date(), w)
                rows.append(dict(month=str(month), t=t.date(), e=e.date(), attempt=attempt, et=w.strftime("%H:%M"),
                                 engine_h=engine_age_h(t.date(), now), close_h=close_age_h(t.date(), now),
                                 between=between))
    df = pd.DataFrame(rows)
    df["R0"] = df.engine_h <= 2
    df["R1"] = df.engine_h <= 48
    df["R1c"] = df.close_h <= 48
    df["R2k0"] = df.between <= 0
    df["R2k3"] = df.between <= 3

    first = df[df.attempt == 0]
    n_months = first.month.nunique()
    print(f"Study 003 bar-age rule check: {n_months} month-ends {FIRST} to {LAST}, first attempt at 15:30 and 15:59 ET,"
          f" retries 1-{RETRIES} at the same times; rule-based NYSE calendar (closures not yet announced are unknown)")
    print()
    print("signal t -> execution e for the first record: "
          f"{first.iloc[0].t} -> {first.iloc[0].e}, engine age {first.iloc[0].engine_h:.2f}-{first.iloc[1].engine_h:.2f} h,"
          f" age from the close {first.iloc[0].close_h:.2f}-{first.iloc[1].close_h:.2f} h")
    print()
    print(f"{'rule':<6} {'first attempts failing':>24} {'months failing':>15} {'first failing month':>20} {'retries failing':>16}")
    for r in ["R0", "R1", "R1c", "R2k0", "R2k3"]:
        fa = first[~first[r]]
        rt = df[(df.attempt > 0) & ~df[r]]
        print(f"{r:<6} {len(fa):>13} of {len(first):<8} {fa.month.nunique():>8} of {n_months:<4} "
              f"{(fa.month.iloc[0] if len(fa) else '-'):>20} {len(rt):>8} of {len(df) - len(first):<5}")
    print()
    gaps = (pd.Series([e - t for t, e in zip(first.t, first.e)]).dt.days)
    print("calendar days from t to e on first attempts: " + ", ".join(f"{d} d: {(gaps == d).sum() // 2}" for d in sorted(gaps.unique())))
    print(f"largest first-attempt age: engine {first.engine_h.max():.2f} h, from the close {first.close_h.max():.2f} h;"
          f" largest third-retry age from the close {df[df.attempt == RETRIES].close_h.max():.2f} h")
    works = [r for r in ["R0", "R1", "R1c", "R2k0", "R2k3"] if first[r].all()]
    print("rules that pass every first attempt (reading rule): " + (", ".join(works) if works else "none"))


if __name__ == "__main__":
    main()
