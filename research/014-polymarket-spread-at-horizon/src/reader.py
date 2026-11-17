"""Study 014 reader (PREREGISTRATION.md §5.1–§5.3).

What it reads, and nothing else:

- Study 013's data-step sample file, hash-checked against Study 013's
  `results/data_manifest.json` (`sample_jsonl_sha256`), projected to the nine
  sample fields of §5.1 (`SAMPLE_FIELDS`); the token field of a sample row is
  never read.
- Study 013's data-step report, three keys (`DATA_STEP_KEYS`): whether the
  step stopped for a gap amendment, whether it halted, whether its §6.2
  price-field check passed; and a fourth, optional key (`DATA_STEP_OPTIONAL_KEYS`):
  the dated amendment a re-run was made under, None when absent (§16, 2026-11-17).
- The snapshot-of-record row of each sampled market, eight fields (`RECORD_FIELDS`,
  §5.3), after **every** snapshot the run will touch has been hashed against its
  line in Study 013's `paper-log/snapshots.csv` (`verify_snapshots`); a mismatch
  or a missing file refuses with nothing read (`SnapshotHashMismatch`). The
  readers take the verified table and refuse a day that is not in it.
- From earlier snapshots, for the moved-end count of §9.6: `id` and `endDate` only
  (`END_FIELDS`), from the same verified table; a logged day with no file is
  'missing' in that table and skipped (the count is descriptive).

`project` is the one place a snapshot row's fields are taken; it refuses any
field outside the list it is given, and every list is a module constant that the
tests compare with §5.3. Every path is an argument; no path is bound at import.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

SAMPLE_FIELDS = ("trial", "market", "cluster", "price", "snapshot", "realised_horizon_hours", "half", "sports", "early")
RECORD_FIELDS = ("id", "bestBid", "bestAsk", "orderPriceMinTickSize", "liquidityNum", "feesEnabled", "endDate", "eventIds")
END_FIELDS = ("id", "endDate")
DATA_STEP_KEYS = ("stopped_for_amendment", "halted", "price_field_check")
DATA_STEP_OPTIONAL_KEYS = ("amendment",)  # §16 (2026-11-17): the dated amendment a Study 013 re-run was made under
SAMPLE_HASH_KEY = "sample_jsonl_sha256"
MISSING = "missing"  # a logged snapshot day with no records file (the moved-end scan skips it and says so)
FIXED_FOLLOWED_EVENTS = frozenset({"1292829", "770450"})  # §6.3: the two events the desk's weekly view follows


class Refusal(Exception):
    """The run stops before anything is written (§14; the message says which rule)."""


class SnapshotHashMismatch(Refusal):
    """A snapshot's records file does not hash to the line Study 013 logged on its day (§5.1)."""


class FieldRefusal(Refusal):
    """A field outside the list of §5.3 was asked for."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def project(row: dict, fields: tuple[str, ...], allowed: tuple[str, ...] = RECORD_FIELDS) -> dict:
    """The named fields of a row, and no other; a field outside `allowed` is refused before any value is read."""
    bad = [f for f in fields if f not in allowed]
    if bad:
        raise FieldRefusal(f"field(s) {bad} are outside the list PREREGISTRATION.md §5.3 allows ({list(allowed)})")
    return {f: row.get(f) for f in fields}


def decode_list(v: object) -> list | None:
    """A JSON-encoded list in a string, or a list as it is; None otherwise (the listing's list fields arrive as strings)."""
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            out = json.loads(v)
        except ValueError:
            return None
        return out if isinstance(out, list) else None
    return None


def as_float(v: object) -> float | None:
    """A decimal number from a float, an int or a numeric string; None otherwise (bool is not a number here)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None


def read_data_step(report_json: Path) -> dict:
    """The three keys of Study 013's data-step report (§5.1, §5.4) and the optional `amendment` (§16, 2026-11-17);
    `price_field_pass` is the check's `pass` flag."""
    if not report_json.exists():
        raise Refusal(f"Study 013's data-step report {report_json.name} is missing: its data step has not run (§14 step 3)")
    d = json.loads(report_json.read_text(encoding="utf-8"))
    missing = [k for k in DATA_STEP_KEYS if k not in d]
    if missing:
        raise Refusal(f"Study 013's data-step report lacks {missing}; the three keys of §5.1 are required")
    pfc = d["price_field_check"]
    amendment = d.get("amendment")
    return {
        "stopped_for_amendment": bool(d["stopped_for_amendment"]),
        "halted": bool(d["halted"]),
        "price_field_pass": bool(pfc.get("pass")) if isinstance(pfc, dict) else bool(pfc),
        "amendment": str(amendment) if amendment else None,
    }


def read_sample(sample_jsonl: Path, data_manifest_json: Path) -> tuple[list[dict], str]:
    """Study 013's sample rows projected to §5.1's nine fields, after the file hashes to the manifest's record."""
    if not data_manifest_json.exists():
        raise Refusal(f"Study 013's {data_manifest_json.name} is missing: its data step has not fixed the sample (§14 step 3)")
    manifest = json.loads(data_manifest_json.read_text(encoding="utf-8"))
    recorded = manifest.get(SAMPLE_HASH_KEY)
    if not isinstance(recorded, str) or not recorded:
        raise Refusal(f"Study 013's manifest has no {SAMPLE_HASH_KEY}")
    if not sample_jsonl.exists():
        raise Refusal(f"Study 013's sample file {sample_jsonl.name} is missing")
    h = sha256_file(sample_jsonl)
    if h != recorded:
        raise Refusal(
            f"Study 013's sample file hashes to {h[:12]}..., its manifest says {recorded[:12]}...; refused, nothing read (§5.1)"
        )
    rows: list[dict] = []
    with open(sample_jsonl, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                rows.append(project(r, SAMPLE_FIELDS, SAMPLE_FIELDS))
    return rows, h


def read_snapshot_log(log_csv: Path) -> dict[dt.date, str]:
    """Snapshot date -> the SHA-256 Study 013 logged for its records file on the day it was taken."""
    if not log_csv.exists():
        raise Refusal(f"Study 013's snapshot log {log_csv.name} is missing")
    out: dict[dt.date, str] = {}
    with open(log_csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[dt.date.fromisoformat(r["snapshot_date"])] = r["records_sha256"]
    return out


def records_path(snapshot_root: Path, day: dt.date) -> Path:
    return snapshot_root / day.isoformat() / "records.jsonl"


def verify_records(snapshot_root: Path, day: dt.date, logged_sha: str) -> tuple[Path, str]:
    """Hash a snapshot's records file against the log line of its day before any row is read; returns (path, hash)."""
    path = records_path(snapshot_root, day)
    if not path.exists():
        raise SnapshotHashMismatch(f"snapshot {day.isoformat()} is logged but {path.name} is missing; refused, nothing read")
    h = sha256_file(path)
    if h != logged_sha:
        raise SnapshotHashMismatch(
            f"snapshot {day.isoformat()}: records.jsonl hashes to {h[:12]}..., the log of its day says {logged_sha[:12]}...; "
            "refused, nothing read (§5.1)"
        )
    return path, h


def verify_snapshots(snapshot_root: Path, log: dict[dt.date, str], days: Iterable[dt.date], *,
                     allow_missing: bool = False) -> dict[str, str]:
    """§5.1: every snapshot the run will read, hashed against its logged line **before any row of any of them is read**.

    Returns snapshot date iso -> verified hash. A day the log does not list is a refusal (Study 013 could not have
    chosen it). A logged day with no file is a refusal unless `allow_missing` (the moved-end scan's earlier days), in
    which case it is MISSING in the table and the readers skip it."""
    out: dict[str, str] = {}
    for day in sorted(set(days)):
        if day not in log:
            raise Refusal(f"sample rows name snapshot {day.isoformat()}, which Study 013's snapshot log does not list")
        if allow_missing and not records_path(snapshot_root, day).exists():
            out[day.isoformat()] = MISSING
            continue
        _, h = verify_records(snapshot_root, day, log[day])
        out[day.isoformat()] = h
    return out


def _iter_rows(path: Path) -> Iterable[dict]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def _verified_path(snapshot_root: Path, verified: dict[str, str], day: dt.date) -> Path:
    h = verified.get(day.isoformat())
    if h is None or h == MISSING:
        raise Refusal(f"snapshot {day.isoformat()} was not verified before reading (§5.1); refused, nothing read")
    return records_path(snapshot_root, day)


def read_record_rows(snapshot_root: Path, verified: dict[str, str], wanted: dict[dt.date, set[str]]) -> dict[tuple[str, str], dict]:
    """The snapshot-of-record rows: for each date, the eight fields of §5.3 for every wanted id.

    Returns (snapshot date iso, id) -> projected row. Every wanted day must be in `verified` (from `verify_snapshots`);
    the hashes are checked there, before this function reads a row of any day."""
    paths = {day: _verified_path(snapshot_root, verified, day) for day in sorted(wanted)}  # every day checked first
    rows: dict[tuple[str, str], dict] = {}
    for day, path in paths.items():
        ids = wanted[day]
        for r in _iter_rows(path):
            rid = str(r.get("id"))
            if rid in ids:
                rows[(day.isoformat(), rid)] = project(r, RECORD_FIELDS)
    return rows


def first_end_dates(snapshot_root: Path, verified: dict[str, str], ids: set[str], from_day: dt.date, to_day: dt.date) -> dict[str, object]:
    """§9.6 moved-end count: for each id, `endDate` on the first snapshot dated in [from_day, to_day] that lists it.

    Reads `id` and `endDate` only, from days in `verified` (hashed before any read); a day marked MISSING is skipped
    (the count is descriptive and the gap is reported by the caller, not hidden)."""
    found: dict[str, object] = {}
    remaining = set(ids)
    days = sorted(dt.date.fromisoformat(d) for d in verified)
    for day in days:
        if not from_day <= day <= to_day:
            continue
        if not remaining:
            break
        if verified[day.isoformat()] == MISSING:
            continue
        for r in _iter_rows(records_path(snapshot_root, day)):
            rid = str(r.get("id"))
            if rid in remaining:
                found[rid] = project(r, END_FIELDS)["endDate"]
                remaining.discard(rid)
    return found


def read_followed_events(events_csv: Path, run_date: dt.date) -> tuple[set[str], set[str]]:
    """The desk's followed events (§6.3): (the two ids fixed in the pre-registration, every other id with a
    `followed_from` date on or before `run_date`). Both sets are strings; a row with an unreadable date is counted
    as followed. A missing file is a refusal: it is committed, so its absence means a wrong path."""
    fixed = set(FIXED_FOLLOWED_EVENTS)
    later: set[str] = set()
    if not events_csv.exists():
        raise Refusal(f"the desk's followed-events file {events_csv} is missing; the §6.3 exclusion cannot be applied")
    with open(events_csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            eid = str(r.get("event_id", "")).strip()
            if not eid or eid in fixed:
                continue
            try:
                since = dt.date.fromisoformat(str(r.get("followed_from", "")).strip())
            except ValueError:
                later.add(eid)
                continue
            if since <= run_date:  # the desk may read books on the morning of the run (code review, should-fix 3)
                later.add(eid)
    return fixed, later
