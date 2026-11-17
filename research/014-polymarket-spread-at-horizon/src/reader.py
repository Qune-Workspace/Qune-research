"""Study 014 reader (PREREGISTRATION.md §5.1–§5.3).

What it reads, and nothing else:

- Study 013's data-step sample file, hash-checked against Study 013's
  `results/data_manifest.json` (`sample_jsonl_sha256`), projected to the nine
  sample fields of §5.1 (`SAMPLE_FIELDS`); the token field of a sample row is
  never read.
- Study 013's data-step report, three keys only (`DATA_STEP_KEYS`): whether the
  step stopped for a gap amendment, whether it halted, whether its §6.2
  price-field check passed.
- The snapshot-of-record row of each sampled market, eight fields (`RECORD_FIELDS`,
  §5.3), after the snapshot's `records.jsonl` has been hashed against its line in
  Study 013's `paper-log/snapshots.csv`; a mismatch or a missing file refuses with
  nothing read (`SnapshotHashMismatch`).
- From earlier snapshots, for the moved-end count of §9.6: `id` and `endDate` only
  (`END_FIELDS`), after the same hash check.

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
SAMPLE_HASH_KEY = "sample_jsonl_sha256"


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
    """The three keys of Study 013's data-step report (§5.1, §5.4); `price_field_pass` is the check's `pass` flag."""
    if not report_json.exists():
        raise Refusal(f"Study 013's data-step report {report_json.name} is missing: its data step has not run (§14 step 3)")
    d = json.loads(report_json.read_text(encoding="utf-8"))
    missing = [k for k in DATA_STEP_KEYS if k not in d]
    if missing:
        raise Refusal(f"Study 013's data-step report lacks {missing}; the three keys of §5.1 are required")
    pfc = d["price_field_check"]
    return {
        "stopped_for_amendment": bool(d["stopped_for_amendment"]),
        "halted": bool(d["halted"]),
        "price_field_pass": bool(pfc.get("pass")) if isinstance(pfc, dict) else bool(pfc),
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


def verify_records(snapshot_root: Path, day: dt.date, logged_sha: str) -> tuple[Path, str]:
    """Hash a snapshot's records file against the log line of its day before any row is read; returns (path, hash)."""
    path = snapshot_root / day.isoformat() / "records.jsonl"
    if not path.exists():
        raise SnapshotHashMismatch(f"snapshot {day.isoformat()} is logged but {path.name} is missing; refused, nothing read")
    h = sha256_file(path)
    if h != logged_sha:
        raise SnapshotHashMismatch(
            f"snapshot {day.isoformat()}: records.jsonl hashes to {h[:12]}..., the log of its day says {logged_sha[:12]}...; "
            "refused, nothing read (§5.1)"
        )
    return path, h


def _iter_rows(path: Path) -> Iterable[dict]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def read_record_rows(snapshot_root: Path, log: dict[dt.date, str], wanted: dict[dt.date, set[str]]) -> tuple[dict[tuple[str, str], dict], dict[str, str]]:
    """The snapshot-of-record rows: for each date, the eight fields of §5.3 for every wanted id.

    Returns ((snapshot date iso, id) -> projected row, snapshot date iso -> verified hash). A snapshot named on a
    sample row but absent from the log is a refusal (Study 013 could not have chosen it)."""
    rows: dict[tuple[str, str], dict] = {}
    hashes: dict[str, str] = {}
    for day in sorted(wanted):
        if day not in log:
            raise Refusal(f"sample rows name snapshot {day.isoformat()}, which Study 013's snapshot log does not list")
        path, h = verify_records(snapshot_root, day, log[day])
        hashes[day.isoformat()] = h
        ids = wanted[day]
        for r in _iter_rows(path):
            rid = str(r.get("id"))
            if rid in ids:
                rows[(day.isoformat(), rid)] = project(r, RECORD_FIELDS)
    return rows, hashes


def first_end_dates(snapshot_root: Path, log: dict[dt.date, str], ids: set[str], from_day: dt.date, to_day: dt.date) -> tuple[dict[str, object], dict[str, str]]:
    """§9.6 moved-end count: for each id, `endDate` on the first snapshot dated in [from_day, to_day] that lists it.

    Reads `id` and `endDate` only, each snapshot verified first; a snapshot in the range with no file is skipped and
    named in the returned hashes as 'missing' (the count is descriptive and the gap is reported, not hidden)."""
    found: dict[str, object] = {}
    hashes: dict[str, str] = {}
    remaining = set(ids)
    for day in sorted(d for d in log if from_day <= d <= to_day):
        if not remaining:
            break
        path = snapshot_root / day.isoformat() / "records.jsonl"
        if not path.exists():
            hashes[day.isoformat()] = "missing"
            continue
        path, h = verify_records(snapshot_root, day, log[day])
        hashes[day.isoformat()] = h
        for r in _iter_rows(path):
            rid = str(r.get("id"))
            if rid in remaining:
                found[rid] = project(r, END_FIELDS)["endDate"]
                remaining.discard(rid)
    return found, hashes


def read_followed_events(events_csv: Path, before: dt.date) -> tuple[set[str], set[str]]:
    """The desk's followed events (§6.3): (the two ids fixed in the pre-registration, every other id with a
    `followed_from` date before `before`). Both sets are strings; a row with an unreadable date is counted as followed."""
    fixed = {"1292829", "770450"}
    later: set[str] = set()
    if not events_csv.exists():
        return fixed, later
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
            if since < before:
                later.add(eid)
    return fixed, later
