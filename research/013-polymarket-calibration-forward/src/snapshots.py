"""Study 013: reading the daily snapshots the collector wrote (PREREGISTRATION.md §5.1–§5.2).

Shared by the resolution fetch (the candidate set, §6.4) and the data step
(§5.3). Nothing here reads the fetch's outcome file, fetches anything or knows about
outcomes; it decodes the whitelisted rows `collector.py` kept and the
provenance log `paper-log/snapshots.csv`.

The listing's list fields (`outcomes`, `clobTokenIds`, `outcomePrices`) arrive
as JSON-encoded strings (observed 2026-11-01, §6.2): a string is decoded with a
JSON parser first, a list is used as it is, anything else decodes to None.
Times are ISO 8601 with a trailing Z or an offset, with or without fractional
seconds; a time with no offset is read as UTC.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

UTC = dt.UTC


def parse_time(s: object) -> dt.datetime | None:
    """ISO 8601 text to an aware UTC datetime; None when absent or unreadable."""
    if not isinstance(s, str) or not s:
        return None
    t = s.strip()
    if t.endswith("Z") or t.endswith("z"):
        t = t[:-1] + "+00:00"
    try:
        d = dt.datetime.fromisoformat(t)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return d.astimezone(UTC)


def decode_list(v: object) -> list | None:
    """A JSON-encoded list in a string, or a list as it is; None otherwise."""
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


@dataclass(frozen=True)
class Snapshot:
    """One line of `paper-log/snapshots.csv`."""

    date: dt.date
    started: dt.datetime  # t_s of §5.1
    distinct_markets: int
    records_sha256: str

    @property
    def folder_name(self) -> str:
        return self.date.isoformat()


def read_snapshot_log(log_csv: Path) -> list[Snapshot]:
    """Every complete snapshot the collector logged, oldest first."""
    if not log_csv.exists():
        return []
    out: list[Snapshot] = []
    with open(log_csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            started = parse_time(r["started_utc"])
            if started is None:
                raise ValueError(f"{log_csv}: unreadable started_utc on {r.get('snapshot_date')}")
            out.append(
                Snapshot(
                    date=dt.date.fromisoformat(r["snapshot_date"]),
                    started=started,
                    distinct_markets=int(r["distinct_markets"]),
                    records_sha256=r["records_sha256"],
                )
            )
    return sorted(out, key=lambda s: s.date)


def iter_rows(snapshot_root: Path, snap: Snapshot) -> Iterator[dict]:
    """The whitelisted rows of one snapshot, one dict a line."""
    path = snapshot_root / snap.folder_name / "records.jsonl"
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def candidate_set(snapshot_root: Path, snapshots: list[Snapshot], first_day: dt.date, last_day: dt.date) -> dict[str, str]:
    """§6.4: every market id in any snapshot dated from `first_day` to `last_day` inclusive, with its
    condition id (the CLOB key). Only these two identifiers are read from each row."""
    out: dict[str, str] = {}
    for snap in snapshots:
        if snap.date < first_day or snap.date > last_day:
            continue
        for row in iter_rows(snapshot_root, snap):
            mid = str(row.get("id"))
            cid = row.get("conditionId")
            if mid not in out:
                out[mid] = str(cid) if cid is not None else ""
    return out
