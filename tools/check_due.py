"""The due register: what the forward records and the desk owe by the calendar,
and whether it exists in the committed files.

Written on 2026-10-31, the morning after the first month-end records (signal
date 2026-10-30) were written nine hours late. MONTH_END.md said "every step
is run by the hourly loop from 2026-10-30 21:15 UTC"; at 16:50 UTC that day
the loop's cadence changed to four runs a day and the 22:15 run that would
have written the records stopped existing. No run read a list of what was
due, because the list lived in prose and in the old schedule
(research/POST_MORTEMS.md, "The slip of 26-30 October"). This script is that
list, computed from the NYSE calendar and the files, so that nothing depends
on a schedule or on anyone remembering.

What it checks (each line: item, status, detail):

  Studies 003-008, monthly decision record. Due 21:15 UTC on the last NYSE
      trading day t of each month from 2026-10 (after the New York close
      and the H.15 release). Deadline: 21:00 UTC on the third NYSE trading
      day after t (the pre-registrations allow the execution to slip at
      most three NYSE days; 21:00 is the close under EST and one hour after
      it under EDT, the lenient side). Evidence: 003-005
      paper-log/decisions/<t>.json; 006-008 any paper-log/decisions/*.json
      whose signal_month is the month (their t can be the 29th when FRED
      never posts the 30th). A paper-log/waits.csv row for the month after
      the due time reads "waiting" (attended, not written). A row in
      paper-log/missed.csv (signal_month, logged_at_utc, why) reads
      "missed (logged)": the month is lost but on record, which the
      pre-registrations require ("a missed month is logged, never filled").
  Desk view, weekly. Due Fridays from 2026-10-30 at 06:00 UTC (the morning
      run); deadline the Sunday 23:59 UTC. Evidence:
      desk-view/data/numbers_<friday>.json; desk-view/missed.csv as above.
  PM view, weekly (added 2026-11-04). Due Fridays from 2026-11-06 at 06:00
      UTC with the desk view; deadline the Sunday 23:59 UTC. Evidence: a
      quote in pm-view/data/manifest.json fetched on the Friday or in the
      two grace days; pm-view/missed.csv (key, logged_at_utc, why) as above.
  Predictions. Every predictions/ledger.csv row whose due_on has passed must
      have a row in outcomes.csv (score.py scores once a FRED row dated on
      or after the due date exists, usually the next day); deadline three
      days after due_on.
  Studies 010 and 011 (release-bound). Informational only: their record for
      a month exists once the library release that contains the previous
      month has been kept, and the release has no fixed date. The line
      shows the last record and the last release checked.

Statuses: ok, not due, waiting, DUE, OVERDUE, missed (logged), info.
Exit 1 when any item is OVERDUE (past its deadline, no record, no logged
miss), so the CI lint job turns red; exit 0 otherwise. DUE is the normal
state between the due time and the deadline: the loop run that sees it works
it before anything else (MISSION.md, learning mode; MONTH_END.md).

Usage: python tools/check_due.py [--at 2026-11-02T22:00Z] [--root PATH] [--selftest]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qune_research.nyse import nyse_trading_days  # noqa: E402

FIRST_MONTH = (2026, 10)
MONTH_END_STUDIES: dict[str, str] = {"003": "date", "004": "date", "005": "date",
                                     "006": "month", "007": "month", "008": "month"}
GATE_UTC = time(21, 15)
DEADLINE_CLOSE_UTC = time(21, 0)
MAX_NYSE_DAYS_SLIP = 3
FIRST_DESK_VIEW = date(2026, 10, 30)
FIRST_PM_VIEW = date(2026, 11, 6)  # the weekly prediction-market view, with the rates view (2026-11-04)
DESK_VIEW_DUE_UTC = time(6, 0)
DESK_VIEW_GRACE_DAYS = 2
PREDICTION_GRACE_DAYS = 3
RELEASE_STUDIES = ("010", "011")
# Study 013: the daily snapshot of the open-market listing (research/013/collector.py), one a UTC day,
# taken by the no-model job at 04:40 UTC; a learning run that finds today's missing takes it (same day,
# the collector refuses only when the day's folder exists). A past day with no snapshot is a gap that
# is never filled (QUESTION.md §3.2): it is listed, not owed.
SNAPSHOT_STUDY = "013"
SNAPSHOT_DUE_UTC = time(4, 40)
# Study 013's window and scoring deadline (PREREGISTRATION.md §5.4, §11, §14 step 3): the snapshot days that
# can serve C1 run from S = 2026-11-03 to 2026-12-28 (56 days); the study stops for a dated §16 amendment
# when fewer than 42 of them exist or three or more consecutive days are gaps. The resolution fetch runs once
# on or after 2027-01-20 00:00Z and is evidenced by the committed provenance line in
# paper-log/resolution_fetch.csv (the fetch's two files and its hash manifest are git-ignored). The grace of
# seven days for the fetch is this register's own: the pre-registration fixes "on or after", not a deadline.
SNAPSHOT_WINDOW = (date(2026, 11, 3), date(2026, 12, 28))
SNAPSHOT_STOP_MIN_DAYS = 42
SNAPSHOT_STOP_RUN = 3
# collector.py consistency (2026-11-05): a previous snapshot that missed at most one page of markets or more
# (the smallest unit a pagination fault can lose) is a finding to investigate while the window is still open.
SNAPSHOT_MISSED_PAGE = 100
RESOLUTION_DUE = datetime(2027, 1, 20, 0, 0, tzinfo=UTC)
RESOLUTION_GRACE_DAYS = 7


@dataclass
class Item:
    label: str
    status: str
    detail: str

    def line(self) -> str:
        return f"  {self.label}: {self.status} ({self.detail})" if self.detail else f"  {self.label}: {self.status}"


# --- calendar -----------------------------------------------------------------------------------

def last_trading_day(year: int, month: int) -> date:
    first = date(year, month, 1)
    last = (date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)) - timedelta(days=1)
    return nyse_trading_days(first, last)[-1].date()


def deadline_for(t: date) -> datetime:
    days = nyse_trading_days(t + timedelta(days=1), t + timedelta(days=20))
    return datetime.combine(days[MAX_NYSE_DAYS_SLIP - 1].date(), DEADLINE_CLOSE_UTC, tzinfo=UTC)


def months_through(at: datetime) -> list[tuple[int, int]]:
    """FIRST_MONTH .. the month of ``at`` plus one (the next due line is the schedule)."""
    out: list[tuple[int, int]] = []
    y, m = FIRST_MONTH
    while (y, m) <= (at.year, at.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    out.append((y, m))
    return out


def fridays_through(at: datetime, first: date = FIRST_DESK_VIEW) -> list[date]:
    out: list[date] = []
    d = first
    while d <= at.date():
        out.append(d)
        d += timedelta(days=7)
    out.append(d)
    return out


# --- evidence -----------------------------------------------------------------------------------

def study_dir(root: Path, sid: str) -> Path | None:
    hits = sorted((root / "research").glob(f"{sid}-*"))
    return hits[0] if hits else None


def logged_miss(folder: Path, key: str) -> str | None:
    path = folder / "missed.csv"
    if not path.exists():
        return None
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if (row.get("signal_month") or row.get("key") or "") == key:
                return row.get("logged_at_utc", "")
    return None


def wait_after(folder: Path, month: str, due: datetime) -> str | None:
    path = folder / "waits.csv"
    if not path.exists():
        return None
    last = None
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("signal_month") != month:
                continue
            checked = row.get("checked_at_utc", "")
            try:
                when = datetime.strptime(checked, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            except ValueError:
                continue
            if when >= due:
                last = checked
    return last


def record_for(folder: Path, kind: str, t: date, month: str) -> Path | None:
    decisions = folder / "decisions"
    if kind == "date":
        path = decisions / f"{t.isoformat()}.json"
        return path if path.exists() else None
    if not decisions.exists():
        return None
    for path in sorted(decisions.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if record.get("signal_month") == month or str(record.get("signal_date", "")).startswith(month):
            return path
    return None


def classify(at: datetime, due: datetime, deadline: datetime, evidence: str | None,
             waiting: str | None, missed: str | None) -> tuple[str, str]:
    if evidence:
        return "ok", evidence
    if at < due:
        return "not due", f"due {due:%Y-%m-%d %H:%M}Z"
    if missed is not None:
        return "missed (logged)", f"logged {missed}"
    if at < deadline:
        if waiting:
            return "waiting", f"last check {waiting}; deadline {deadline:%Y-%m-%d %H:%M}Z"
        return "DUE", f"since {due:%Y-%m-%d %H:%M}Z; deadline {deadline:%Y-%m-%d %H:%M}Z"
    return "OVERDUE", f"deadline {deadline:%Y-%m-%d %H:%M}Z passed; write the record or log the miss in missed.csv"


# --- items --------------------------------------------------------------------------------------

def month_end_items(root: Path, at: datetime) -> list[Item]:
    items: list[Item] = []
    for sid, kind in MONTH_END_STUDIES.items():
        folder = study_dir(root, sid)
        if folder is None or not (folder / "paper-log").exists():
            items.append(Item(f"Study {sid} forward record", "info", "no paper-log folder"))
            continue
        paper_log = folder / "paper-log"
        for y, m in months_through(at):
            month = f"{y:04d}-{m:02d}"
            t = last_trading_day(y, m)
            due = datetime.combine(t, GATE_UTC, tzinfo=UTC)
            deadline = deadline_for(t)
            record = record_for(paper_log, kind, t, month)
            evidence = str(record.relative_to(root)) if record else None
            status, detail = classify(at, due, deadline, evidence,
                                      wait_after(paper_log, month, due), logged_miss(paper_log, month))
            items.append(Item(f"Study {sid} record {month} (signal date {t})", status, detail))
            if status == "not due":
                break
    return items


def pm_view_weekly_items(root: Path, at: datetime) -> list[Item]:
    """The weekly prediction-market view (pm-view/, added 2026-11-04): due Fridays from
    2026-11-06 at 06:00 UTC with the rates desk view, deadline the Sunday 23:59 UTC. Evidence is
    a quote in pm-view/data/manifest.json fetched on the Friday or inside the grace days (the
    README's rule 1: every view starts with the market's own numbers); pm-view/missed.csv
    (key, logged_at_utc, why) logs a lost week."""
    items: list[Item] = []
    folder = root / "pm-view"
    if not folder.exists():
        return [Item("PM view", "info", "no pm-view folder")]
    manifest = folder / "data" / "manifest.json"
    fetched: set[date] = set()
    if manifest.exists():
        try:
            for entry in json.loads(manifest.read_text(encoding="utf-8")):
                fetched.add(date.fromisoformat(str(entry.get("fetched_utc", ""))[:10]))
        except (ValueError, TypeError, AttributeError):
            pass
    for friday in fridays_through(at, FIRST_PM_VIEW):
        due = datetime.combine(friday, DESK_VIEW_DUE_UTC, tzinfo=UTC)
        deadline = datetime.combine(friday + timedelta(days=DESK_VIEW_GRACE_DAYS), time(23, 59), tzinfo=UTC)
        days = [friday + timedelta(days=k) for k in range(DESK_VIEW_GRACE_DAYS + 1)]
        hit = next((d for d in days if d in fetched), None)
        evidence = f"pm-view/data/manifest.json quote fetched {hit}" if hit else None
        status, detail = classify(at, due, deadline, evidence, None, logged_miss(folder, friday.isoformat()))
        items.append(Item(f"PM view {friday}", status, detail))
        if status == "not due":
            break
    return items


def desk_view_items(root: Path, at: datetime) -> list[Item]:
    items: list[Item] = []
    folder = root / "desk-view"
    if not folder.exists():
        return [Item("Desk view", "info", "no desk-view folder")]
    for friday in fridays_through(at):
        due = datetime.combine(friday, DESK_VIEW_DUE_UTC, tzinfo=UTC)
        deadline = datetime.combine(friday + timedelta(days=DESK_VIEW_GRACE_DAYS), time(23, 59), tzinfo=UTC)
        path = folder / "data" / f"numbers_{friday.isoformat()}.json"
        evidence = str(path.relative_to(root)) if path.exists() else None
        status, detail = classify(at, due, deadline, evidence, None, logged_miss(folder, friday.isoformat()))
        items.append(Item(f"Desk view {friday}", status, detail))
        if status == "not due":
            break
    return items


def prediction_items(root: Path, at: datetime) -> list[Item]:
    ledger = root / "predictions" / "ledger.csv"
    outcomes = root / "predictions" / "outcomes.csv"
    if not ledger.exists():
        return [Item("Predictions", "info", "no ledger")]
    scored: set[str] = set()
    if outcomes.exists():
        with outcomes.open(encoding="utf-8", newline="") as fh:
            scored = {row["id"] for row in csv.DictReader(fh) if row.get("id")}
    items: list[Item] = []
    pending = 0
    with ledger.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                due_on = date.fromisoformat(row["due_on"])
            except (KeyError, ValueError):
                continue
            if due_on > at.date():
                pending += 1
                continue
            due = datetime.combine(due_on, time(23, 59), tzinfo=UTC)
            deadline = datetime.combine(due_on + timedelta(days=PREDICTION_GRACE_DAYS), time(23, 59), tzinfo=UTC)
            evidence = "outcomes.csv row" if row["id"] in scored else None
            status, detail = classify(at, due, deadline, evidence, None, None)
            items.append(Item(f"Call {row['id']} scored", status, detail))
    items.append(Item("Calls not yet due", "info", f"{pending}"))
    return items


def pm_view_items(root: Path, at: datetime) -> list[Item]:
    """The prediction-market view's calls (pm-view/ledger.csv, added 2026-11-03): a call is due
    the day after its market's scheduled end; scored when pm-view/outcomes.csv holds its id
    (settled or excluded); an unresolved market past the grace period is reported, not filled."""
    ledger = root / "pm-view" / "ledger.csv"
    outcomes = root / "pm-view" / "outcomes.csv"
    if not ledger.exists():
        return [Item("PM view calls", "info", "no ledger")]
    scored: set[str] = set()
    if outcomes.exists():
        with outcomes.open(encoding="utf-8", newline="") as fh:
            scored = {row["id"] for row in csv.DictReader(fh) if row.get("id")}
    items: list[Item] = []
    pending = 0
    with ledger.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                due_on = date.fromisoformat(row["due_on"]) + timedelta(days=1)
            except (KeyError, ValueError):
                continue
            if due_on > at.date():
                pending += 1
                continue
            due = datetime.combine(due_on, time(0, 0), tzinfo=UTC)
            deadline = datetime.combine(due_on + timedelta(days=PREDICTION_GRACE_DAYS), time(23, 59), tzinfo=UTC)
            evidence = "pm-view/outcomes.csv row" if row["id"] in scored else None
            status, detail = classify(at, due, deadline, evidence, None, None)
            items.append(Item(f"PM call {row['id']} scored", status, detail))
    items.append(Item("PM calls not yet due", "info", f"{pending}"))
    return items


def release_items(root: Path) -> list[Item]:
    items: list[Item] = []
    for sid in RELEASE_STUDIES:
        folder = study_dir(root, sid)
        if folder is None:
            items.append(Item(f"Study {sid}", "info", "no folder"))
            continue
        paper_log = folder / "paper-log"
        records = paper_log / ("positions.csv" if sid == "010" else "cohorts.csv")
        fetch_log = paper_log / "releases" / "fetch_log.csv"
        last_month = "none"
        if records.exists():
            with records.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.reader(fh))
            if len(rows) > 1:
                last_month = max(r[0] for r in rows[1:] if r)
        last_fetch = "none"
        if fetch_log.exists():
            with fetch_log.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.reader(fh))
            if len(rows) > 1 and rows[-1]:
                last_fetch = ", ".join(rows[-1][:3])
        items.append(Item(f"Study {sid} release-bound record", "info",
                          f"last record {last_month}; last fetch check {last_fetch}; next record when the next release is kept"))
    return items


def snapshot_items(root: Path, at: datetime) -> list[Item]:
    folder = study_dir(root, SNAPSHOT_STUDY)
    if folder is None:
        return [Item(f"Study {SNAPSHOT_STUDY} snapshot", "info", "no folder")]
    log = folder / "paper-log" / "snapshots.csv"
    if not log.exists():
        return [Item(f"Study {SNAPSHOT_STUDY} snapshot", "info", "no snapshot yet (collector not started)")]
    with log.open(encoding="utf-8", newline="") as fh:
        days = sorted({row["snapshot_date"] for row in csv.DictReader(fh) if row.get("snapshot_date")})
    if not days:
        return [Item(f"Study {SNAPSHOT_STUDY} snapshot", "info", "empty log")]
    today = at.date()
    first = date.fromisoformat(days[0])
    have = set(days)
    gaps = [d.isoformat() for d in (first + timedelta(days=k) for k in range((today - first).days))
            if d.isoformat() not in have]
    items = [Item(f"Study {SNAPSHOT_STUDY} snapshots", "info", f"{len(days)} complete since {days[0]}")]
    if today < first:
        return items
    if gaps:
        items.append(Item(f"Study {SNAPSHOT_STUDY} snapshot gaps", "missed (logged)",
                          f"{len(gaps)} day(s) with no snapshot, never filled: {', '.join(gaps[-5:])}"))
    due = datetime.combine(today, SNAPSHOT_DUE_UTC, tzinfo=UTC)
    deadline = datetime.combine(today, time(23, 59), tzinfo=UTC)
    evidence = "snapshots.csv row" if today.isoformat() in have else None
    status, detail = classify(at, due, deadline, evidence, None, None)
    if status == "DUE":
        detail += "; run collector.py snapshot in the study folder (same UTC day), then commit the appended line"
    items.append(Item(f"Study {SNAPSHOT_STUDY} snapshot {today}", status, detail))
    return items


def study013_items(root: Path, at: datetime) -> list[Item]:
    """The window's serving days and the stop rule (info, or DUE once the rule has fired), and the resolution fetch."""
    folder = study_dir(root, SNAPSHOT_STUDY)
    if folder is None:
        return []
    items: list[Item] = []
    first, last = SNAPSHOT_WINDOW
    have: set[str] = set()
    log = folder / "paper-log" / "snapshots.csv"
    if log.exists():
        with log.open(encoding="utf-8", newline="") as fh:
            have = {row["snapshot_date"] for row in csv.DictReader(fh) if row.get("snapshot_date")}
    total = (last - first).days + 1
    if at.date() >= first:
        # days owed so far: through yesterday, plus today once its due time has passed
        through = min(last, at.date() if at.time() >= SNAPSHOT_DUE_UTC else at.date() - timedelta(days=1))
        owed = [first + timedelta(days=k) for k in range((through - first).days + 1)] if through >= first else []
        present = [d for d in owed if d.isoformat() in have]
        run_len = best = 0
        for d in owed:
            run_len = 0 if d.isoformat() in have else run_len + 1
            best = max(best, run_len)
        lost = len(owed) - len(present)
        fired = best >= SNAPSHOT_STOP_RUN or (total - lost) < SNAPSHOT_STOP_MIN_DAYS
        amended = False
        prereg = folder / "PREREGISTRATION.md"
        if prereg.exists():
            tail = prereg.read_text(encoding="utf-8").rsplit("## 16. Amendments", 1)[-1]
            amended = "stop rule" in tail.lower() or "gap" in tail.lower()
        detail = (f"{len(present)} of {len(owed)} serving days so far present ({total} in the window to {last}); "
                  f"{lost} gap day(s), longest run {best}; stop rule at fewer than {SNAPSHOT_STOP_MIN_DAYS} days or a run of {SNAPSHOT_STOP_RUN}")
        if fired and not amended:
            items.append(Item(f"Study {SNAPSHOT_STUDY} snapshot window", "DUE",
                              detail + "; §5.4 stop: write a dated §16 amendment on gap handling before the data step"))
        else:
            items.append(Item(f"Study {SNAPSHOT_STUDY} snapshot window", "info", detail + (" (amended)" if fired else "")))
    # completeness of the record (collector.py consistency, 2026-11-05): the latest id-only comparison of
    # consecutive snapshots; a previous snapshot that missed at most one page (100 markets) or more is a
    # finding to investigate before the window closes, not after it.
    cons = folder / "paper-log" / "consistency.csv"
    if cons.exists():
        with cons.open(encoding="utf-8", newline="") as fh:
            rows = [r for r in csv.DictReader(fh) if r.get("snapshot_date")]
        if rows:
            latest = max(rows, key=lambda r: r["snapshot_date"])
            worst = max(int(r.get("previous_missed_at_most") or 0) for r in rows)
            detail = (f"latest {latest['snapshot_date']} vs {latest['previous_date']}: {latest['markets']} markets, "
                      f"appeared {latest['appeared']} ({latest['appeared_created_before_previous_start']} created before the previous "
                      f"snapshot started), left {latest['left']}; previous snapshot missed at most {latest['previous_missed_at_most']}; "
                      f"worst missed-at-most over {len(rows)} comparison(s): {worst}")
            if worst >= SNAPSHOT_MISSED_PAGE:
                items.append(Item(f"Study {SNAPSHOT_STUDY} snapshot consistency", "DUE",
                                  detail + f"; at or above one page ({SNAPSHOT_MISSED_PAGE}): investigate the collector before the window closes"))
            else:
                items.append(Item(f"Study {SNAPSHOT_STUDY} snapshot consistency", "info", detail))
    evidence = "resolution_fetch.csv" if (folder / "paper-log" / "resolution_fetch.csv").exists() else None
    status, detail = classify(at, RESOLUTION_DUE, RESOLUTION_DUE + timedelta(days=RESOLUTION_GRACE_DAYS), evidence, None, None)
    if status == "DUE":
        detail += "; log the row in trials.md, then run the resolution fetch detached (§14 step 4)"
    items.append(Item(f"Study {SNAPSHOT_STUDY} resolution fetch", status, detail))
    return items


def run(root: Path, at: datetime) -> tuple[list[Item], int]:
    items = (month_end_items(root, at) + desk_view_items(root, at) + prediction_items(root, at)
             + pm_view_weekly_items(root, at) + pm_view_items(root, at) + release_items(root)
             + snapshot_items(root, at)
             + study013_items(root, at))
    overdue = sum(1 for i in items if i.status == "OVERDUE")
    return items, (1 if overdue else 0)


# --- self-test over a built fixture -------------------------------------------------------------

def _fixture(root: Path) -> None:
    (root / "research" / "004-f" / "paper-log" / "decisions").mkdir(parents=True)
    (root / "research" / "004-f" / "paper-log" / "decisions" / "2026-10-30.json").write_text(
        json.dumps({"signal_date": "2026-10-30"}), encoding="utf-8")
    (root / "research" / "006-f" / "paper-log").mkdir(parents=True)
    (root / "research" / "006-f" / "paper-log" / "waits.csv").write_text(
        "signal_month,checked_at_utc,why\n2026-10,2026-10-31T06:18:48Z,no row yet\n", encoding="utf-8")
    (root / "research" / "007-f" / "paper-log").mkdir(parents=True)
    (root / "research" / "008-f" / "paper-log").mkdir(parents=True)
    (root / "research" / "008-f" / "paper-log" / "missed.csv").write_text(
        "signal_month,logged_at_utc,why\n2026-10,2026-11-05T00:00:00Z,fixture\n", encoding="utf-8")
    (root / "desk-view" / "data").mkdir(parents=True)
    (root / "desk-view" / "data" / "numbers_2026-10-30.json").write_text("{}", encoding="utf-8")
    (root / "predictions").mkdir()
    (root / "predictions" / "ledger.csv").write_text(
        "id,made_on,due_on\nV1,2026-10-23,2026-10-29\nV2,2026-10-23,2026-12-31\n", encoding="utf-8")
    (root / "predictions" / "outcomes.csv").write_text("id,scored_on\n", encoding="utf-8")
    (root / "pm-view" / "data").mkdir(parents=True)
    (root / "pm-view" / "data" / "manifest.json").write_text(
        json.dumps([{"market_id": "1", "fetched_utc": "2026-11-03T18:23:14Z"}]), encoding="utf-8")
    (root / "research" / "013-f" / "paper-log").mkdir(parents=True)
    (root / "research" / "013-f" / "paper-log" / "snapshots.csv").write_text(
        "snapshot_date,started_utc,finished_utc,pages,rows,distinct_markets,bytes,records_sha256,pages_sha256\n"
        "2026-11-02,2026-11-02T06:21:23Z,2026-11-02T06:40:00Z,1,1,1,10,0,0\n"
        "2026-11-04,2026-11-04T04:40:10Z,2026-11-04T04:55:00Z,1,1,1,10,0,0\n", encoding="utf-8")


def selftest() -> int:
    def status_of(items: list[Item], prefix: str) -> str:
        hits = [i for i in items if i.label.startswith(prefix)]
        assert len(hits) == 1, (prefix, [i.label for i in items])
        return hits[0].status

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fixture(root)
        assert last_trading_day(2026, 10) == date(2026, 10, 30)
        assert last_trading_day(2026, 11) == date(2026, 11, 30)
        assert deadline_for(date(2026, 10, 30)) == datetime(2026, 11, 4, 21, 0, tzinfo=UTC)

        items, rc = run(root, datetime(2026, 10, 30, 20, 0, tzinfo=UTC))
        assert status_of(items, "Study 004 record 2026-10") == "ok"      # a record that exists is ok at any time
        assert status_of(items, "Study 006 record 2026-10") == "not due"
        assert status_of(items, "Study 007 record 2026-10") == "not due"
        assert status_of(items, "Study 003 forward record") == "info"
        assert status_of(items, "Desk view 2026-10-30") == "ok"
        assert status_of(items, "Call V1") == "DUE"
        assert rc == 0, rc

        items, rc = run(root, datetime(2026, 11, 2, 22, 0, tzinfo=UTC))
        assert status_of(items, "Study 004 record 2026-10") == "ok"
        assert status_of(items, "Study 013 snapshot 2026-11-02") == "ok"
        assert not [i for i in items if i.label.startswith("Study 013 snapshot gaps")]
        assert status_of(items, "Study 004 record 2026-11") == "not due"
        assert status_of(items, "Study 006 record 2026-10") == "waiting"
        assert status_of(items, "Study 007 record 2026-10") == "DUE"
        assert status_of(items, "Study 008 record 2026-10") == "missed (logged)"
        assert status_of(items, "Desk view 2026-10-30") == "ok"
        assert status_of(items, "Desk view 2026-11-06") == "not due"
        assert status_of(items, "Call V1") == "OVERDUE"
        assert rc == 1, rc

        items, rc = run(root, datetime(2026, 11, 5, 22, 0, tzinfo=UTC))
        assert status_of(items, "Study 006 record 2026-10") == "OVERDUE"
        assert status_of(items, "Study 007 record 2026-10") == "OVERDUE"
        assert rc == 1, rc
        assert status_of(items, "Study 013 snapshot 2026-11-05") == "DUE"
        assert status_of(items, "Study 013 snapshot gaps") == "missed (logged)"
        assert "2026-11-03" in [i for i in items if i.label == "Study 013 snapshot gaps"][0].detail
        items, _ = run(root, datetime(2026, 11, 5, 4, 0, tzinfo=UTC))
        assert status_of(items, "Study 013 snapshot 2026-11-05") == "not due"
        items, _ = run(root, datetime(2026, 10, 30, 20, 0, tzinfo=UTC))
        assert not [i for i in items if i.label.startswith("Study 013 snapshot 2026")]
        assert not [i for i in items if i.label == "Study 013 snapshot window"]  # before S
        assert status_of(items, "Study 013 resolution fetch") == "not due"

        # Study 013's window and resolution fetch
        items, _ = run(root, datetime(2026, 11, 5, 22, 0, tzinfo=UTC))
        window = [i for i in items if i.label == "Study 013 snapshot window"][0]
        assert window.status == "info" and window.detail.startswith("1 of 3 serving days so far present (56 in the window to 2026-12-28); 2 gap day(s), longest run 1"), window.detail
        assert status_of(items, "Study 013 resolution fetch") == "not due"
        items, _ = run(root, datetime(2026, 11, 7, 22, 0, tzinfo=UTC))  # 11-05, 11-06, 11-07 missing: a run of three
        assert status_of(items, "Study 013 snapshot window") == "DUE"
        items, _ = run(root, datetime(2027, 1, 20, 1, 0, tzinfo=UTC))
        assert status_of(items, "Study 013 resolution fetch") == "DUE"
        items, rc = run(root, datetime(2027, 1, 28, 1, 0, tzinfo=UTC))
        assert status_of(items, "Study 013 resolution fetch") == "OVERDUE"
        assert rc == 1
        (root / "research" / "013-f" / "paper-log" / "resolution_fetch.csv").write_text("fetched_at_utc\n", encoding="utf-8")
        items, _ = run(root, datetime(2027, 1, 28, 1, 0, tzinfo=UTC))
        assert status_of(items, "Study 013 resolution fetch") == "ok"

        # snapshot consistency (2026-11-05): info below one page missed, DUE at or above it; absent without the file
        assert not [i for i in items if i.label == "Study 013 snapshot consistency"]
        cons = root / "research" / "013-f" / "paper-log" / "consistency.csv"
        header = ("snapshot_date,previous_date,previous_markets,markets,carried,left,appeared,"
                  "appeared_created_before_previous_start,previous_missed_at_most,computed_utc\n")
        cons.write_text(header + "2026-11-04,2026-11-02,5,6,4,1,2,1,0,2026-11-05T06:30:00Z\n", encoding="utf-8")
        items, _ = run(root, datetime(2026, 11, 5, 22, 0, tzinfo=UTC))
        assert status_of(items, "Study 013 snapshot consistency") == "info"
        cons.write_text(header + "2026-11-04,2026-11-02,5,6,4,1,2,1,0,2026-11-05T06:30:00Z\n"
                        "2026-11-05,2026-11-04,6,8,6,0,2,0,100,2026-11-05T06:31:00Z\n", encoding="utf-8")
        items, _ = run(root, datetime(2026, 11, 5, 22, 0, tzinfo=UTC))
        assert status_of(items, "Study 013 snapshot consistency") == "DUE"
        assert "worst missed-at-most over 2 comparison(s): 100" in [i for i in items if i.label == "Study 013 snapshot consistency"][0].detail

        # the weekly PM view (2026-11-04): a Saturday quote covers the Friday; a week without one is DUE,
        # then OVERDUE after the Sunday, then "missed (logged)" once pm-view/missed.csv has the key
        items, _ = run(root, datetime(2026, 11, 2, 22, 0, tzinfo=UTC))
        assert status_of(items, "PM view 2026-11-06") == "not due"
        assert not [i for i in items if i.label.startswith("PM view 2026-11-13")]
        items, _ = run(root, datetime(2026, 11, 6, 5, 0, tzinfo=UTC))
        assert status_of(items, "PM view 2026-11-06") == "not due"  # the Tuesday quote is not this week's
        items, _ = run(root, datetime(2026, 11, 6, 8, 0, tzinfo=UTC))
        assert status_of(items, "PM view 2026-11-06") == "DUE"
        (root / "pm-view" / "data" / "manifest.json").write_text(
            json.dumps([{"market_id": "1", "fetched_utc": "2026-11-03T18:23:14Z"},
                        {"market_id": "1", "fetched_utc": "2026-11-07T09:00:00Z"}]), encoding="utf-8")
        items, _ = run(root, datetime(2026, 11, 7, 22, 0, tzinfo=UTC))
        assert status_of(items, "PM view 2026-11-06") == "ok"
        assert status_of(items, "PM view 2026-11-13") == "not due"
        items, _ = run(root, datetime(2026, 11, 13, 8, 0, tzinfo=UTC))
        assert status_of(items, "PM view 2026-11-13") == "DUE"
        items, rc = run(root, datetime(2026, 11, 16, 1, 0, tzinfo=UTC))
        assert status_of(items, "PM view 2026-11-13") == "OVERDUE"
        assert rc == 1
        (root / "pm-view" / "missed.csv").write_text(
            "key,logged_at_utc,why\n2026-11-13,2026-11-16T00:30:00Z,fixture\n", encoding="utf-8")
        items, _ = run(root, datetime(2026, 11, 16, 1, 0, tzinfo=UTC))
        assert status_of(items, "PM view 2026-11-13") == "missed (logged)"
        (root / "pm-view" / "missed.csv").unlink()

        # the first fixture item becomes ok once the record exists
        (root / "research" / "007-f" / "paper-log" / "decisions").mkdir()
        (root / "research" / "007-f" / "paper-log" / "decisions" / "2026-10-30.json").write_text(
            json.dumps({"signal_month": "2026-10"}), encoding="utf-8")
        items, _ = run(root, datetime(2026, 11, 5, 22, 0, tzinfo=UTC))
        assert status_of(items, "Study 007 record 2026-10") == "ok"
    print("due register self-test: pass")
    return 0


def parse_at(text: str | None) -> datetime:
    if not text:
        return datetime.now(UTC).replace(microsecond=0)
    return datetime.strptime(text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--at", help="UTC time to evaluate at, e.g. 2026-11-02T22:00Z (default: now)")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    at = parse_at(args.at)
    items, rc = run(args.root, at)
    print(f"due register at {at:%Y-%m-%dT%H:%M}Z:")
    for item in items:
        print(item.line())
    counts = {s: sum(1 for i in items if i.status == s) for s in ("DUE", "waiting", "OVERDUE")}
    print(f"due register: {'OVERDUE' if rc else 'pass'} (due {counts['DUE']}, waiting {counts['waiting']}, overdue {counts['OVERDUE']})")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
