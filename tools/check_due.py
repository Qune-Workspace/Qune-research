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
DESK_VIEW_DUE_UTC = time(6, 0)
DESK_VIEW_GRACE_DAYS = 2
PREDICTION_GRACE_DAYS = 3
RELEASE_STUDIES = ("010", "011")


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


def fridays_through(at: datetime) -> list[date]:
    out: list[date] = []
    d = FIRST_DESK_VIEW
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


def run(root: Path, at: datetime) -> tuple[list[Item], int]:
    items = month_end_items(root, at) + desk_view_items(root, at) + prediction_items(root, at) + release_items(root)
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
