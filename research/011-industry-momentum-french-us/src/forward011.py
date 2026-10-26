"""Study 011 forward record, part 1: the monthly cohort records (PREREGISTRATION.md §11).

Shadow only: the industry portfolios are not approved instruments, so there is
no paper order and no paper sleeve.  For each forward holding month t (the
first is 2026-09, the month after the snapshot's last month), the cohort of
each trial ranked at the end of t − 1 (W(t − 1) and L(t − 1)) is computed with
the study's own signal code (``rule.py``: compounded return over the F months
to t − 1, no skipped month; sort key (−round(R, 10), column order)) from the
first release of the library that contains month t − 1, and appended to
``paper-log/cohorts.csv`` with the release, the two zips' SHA-256 and the
record time.  The five earlier cohorts held in t are those already recorded
or, for the first forward months, those of the history run (§11).

Adapted from Study 010's ``forward010.py`` part 1, with the fixes of its code
review:

- The release is read from the two files' header line ("created using the
  YYYYMM CRSP database"), in the manifest and in each zip's own header; the
  two must agree, the release must be named t − 1 (YYYYMM) and every file must
  end exactly at t − 1, or nothing is written.  A later release is refused,
  because the library revises history and a later release could give a
  different cohort, chosen after month t's return is visible.  If the first
  release was not archived, a dated §16 amendment is needed.
- Values at t or after are dropped before ranking, so no release can leak
  month t into its own cohort.
- §11: rows committed after the first release that contains month t are
  labelled "late" and still scored.  Lateness comes from the commit time,
  which this module cannot see, so ``late`` is written False here and set at
  scoring from git (part 2).
- One record per (month, trial); a second is refused, so a record cannot be
  replaced after the month's return is seen.  The append is atomic under a
  file lock.
- Each row carries every eligible industry's formation return at full
  precision (``repr``), so the ranking can be re-checked from the row alone.

Part 2 (fetch, interim, score) is written later, before any forward month can
be scored, after its own separate code review.

Usage, from the study folder:
  python -m src.forward011 record --month 2026-09 [--raw-dir data/raw --manifest results/data_manifest.json]
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .data import FILES, load_industries, read_zip
from .history import TRIALS
from .rule import formation_returns, rank_cohort

STUDY_DIR = Path(__file__).resolve().parents[1]
PAPER_LOG = STUDY_DIR / "paper-log"
COHORTS_CSV = PAPER_LOG / "cohorts.csv"
SNAPSHOT_MANIFEST = STUDY_DIR / "results" / "data_manifest.json"
SNAPSHOT_RAW = STUDY_DIR / "data" / "raw"
FIRST_FORWARD_MONTH = "2026-09"
COLUMNS = ["month", "ranking_month", "trial", "industries", "formation_months", "n_side", "winners", "losers",
           "boundary_ties", "formation_returns", "release", "release_last_month", "files_sha256",
           "manifest_sha256", "downloaded_at_utc", "recorded_at_utc", "late"]
_RELEASE = re.compile(r"created using the (\d{6}) CRSP database")


def _names() -> list[str]:
    return sorted(FILES.values())


def _preamble(entry: dict) -> list[str]:
    lines = entry["preamble_lines"]
    return lines if isinstance(lines, list) else [str(lines)]


def release_of(manifest_path: Path) -> str:
    """The one release named in the header line of both files, or an error."""
    files = json.loads(manifest_path.read_text())["files"]
    found = set()
    for name in _names():
        hits = {m.group(1) for line in _preamble(files[name]) for m in [_RELEASE.search(line)] if m}
        if len(hits) != 1:
            raise ValueError(f"{name}: expected one release line, found {sorted(hits)}")
        found |= hits
    if len(found) != 1:
        raise ValueError(f"the two files name different releases: {sorted(found)}")
    return found.pop()


def zip_releases(raw_dir: Path) -> set[str]:
    """The release named in each zip's own header line, not only the manifest's copy."""
    found = set()
    for name in _names():
        hits = {m.group(1) for line in read_zip((raw_dir / name).read_bytes()).splitlines()[:20]
                for m in [_RELEASE.search(line)] if m}
        if len(hits) != 1:
            raise SystemExit(f"STOP: {name} names {sorted(hits)} in its own header")
        found |= hits
    return found


def files_sha256(manifest_path: Path) -> str:
    files = json.loads(manifest_path.read_text())["files"]
    return ";".join(f"{name}={files[name]['sha256']}" for name in _names())


def downloaded_at(manifest_path: Path) -> str:
    files = json.loads(manifest_path.read_text())["files"]
    missing = [n for n in _names() if not files[n].get("downloaded_at_utc")]
    if missing:
        raise SystemExit(f"STOP: the manifest has no download time for {missing}")
    return ";".join(f"{name}={files[name]['downloaded_at_utc']}" for name in _names())


def cohorts_for(ind: dict[int, pd.DataFrame], month: str) -> list[dict]:
    """The cohort of every trial ranked at the end of t − 1, from data up to t − 1 only."""
    t = pd.Period(month, "M")
    if t < pd.Period(FIRST_FORWARD_MONTH, "M"):
        raise ValueError(f"{month} is inside the history; the forward record starts at {FIRST_FORWARD_MONTH}")
    m = t - 1
    rows = []
    for trial_id, spec in TRIALS.items():
        r = ind[spec["set"]]
        r = r[r.index <= m]
        if r.index[-1] != m:
            raise ValueError(f"{trial_id}: the {spec['set']}-industry file has no row for {m}")
        R = formation_returns(r, spec["F"]).loc[m]
        winners, losers, ties = rank_cohort(R, spec["n"])
        rows.append({"month": str(t), "ranking_month": str(m), "trial": trial_id, "industries": spec["set"],
                     "formation_months": spec["F"], "n_side": spec["n"], "winners": ";".join(winners),
                     "losers": ";".join(losers), "boundary_ties": ties,
                     "formation_returns": ";".join(f"{c}={float(v)!r}" for c, v in R.items() if pd.notna(v))})
    return rows


def existing_body(path: Path) -> str:
    """The current file as text, checked: header equal to COLUMNS and a final newline."""
    if not path.exists():
        return ""
    body = path.read_text()
    if body and (not body.endswith("\n") or body.split("\n", 1)[0] != ",".join(COLUMNS)):
        raise SystemExit(f"STOP: {path.name} is malformed; restore it from git")
    return body


def existing(path: Path) -> set[tuple[str, str]]:
    body = existing_body(path)
    return {(r["month"], r["trial"]) for r in csv.DictReader(body.splitlines())} if body else set()


def record(month: str, raw_dir: Path = SNAPSHOT_RAW, manifest_path: Path = SNAPSHOT_MANIFEST,
           out: Path = COHORTS_CSV, now_utc: str | None = None) -> list[dict]:
    """Append month t's cohorts for M1, M1a and M1b; refuse if any of them is already recorded."""
    t = pd.Period(month, "M")
    release = release_of(manifest_path)
    want = (t - 1).strftime("%Y%m")
    if release != want:
        raise SystemExit(f"STOP: release {release} is not {want}; §11 requires the first release that contains "
                         f"{t - 1} (a later release could revise it; if {want} was not archived, a dated §16 "
                         f"amendment is needed)")
    ind = load_industries(raw_dir, manifest_path)  # checks every zip against the manifest's SHA-256
    if zip_releases(raw_dir) != {want}:
        raise SystemExit(f"STOP: the zips' own header lines do not all name {want}")
    lasts = {n: f.index[-1] for n, f in ind.items()}
    if any(v != t - 1 for v in lasts.values()):
        raise SystemExit(f"STOP: every file must end at {t - 1} in the first release; last months {lasts}")
    rows = cohorts_for(ind, month)
    stamp = now_utc or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = {"release": release, "release_last_month": str(t - 1), "files_sha256": files_sha256(manifest_path),
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "downloaded_at_utc": downloaded_at(manifest_path), "recorded_at_utc": stamp,
            "late": False}  # lateness is set at scoring from the commit time (§11)
    for r in rows:
        r.update(meta)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)  # two runs at once cannot both pass the duplicate check
        done = existing(out) & {(r["month"], r["trial"]) for r in rows}
        if done:
            raise SystemExit(f"STOP: already recorded {sorted(done)}; a record is never replaced (§11)")
        body = existing_body(out)
        tmp = out.with_suffix(".tmp")
        try:
            with tmp.open("w", newline="") as fh:
                fh.write(body)
                w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
                if not body:
                    w.writeheader()
                w.writerows(rows)
                fh.flush()
                os.fsync(fh.fileno())
            tmp.replace(out)  # atomic: a crash leaves the old file whole
            dfd = os.open(out.parent, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        finally:
            tmp.unlink(missing_ok=True)
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.forward011")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record", help="append one forward month's cohorts")
    r.add_argument("--month", required=True)
    r.add_argument("--raw-dir", type=Path, default=SNAPSHOT_RAW)
    r.add_argument("--manifest", type=Path, default=SNAPSHOT_MANIFEST)
    a = p.parse_args(argv)
    if a.cmd == "record":
        rows = record(a.month, a.raw_dir, a.manifest)
        print(json.dumps([{k: v for k, v in x.items() if k in ("month", "trial", "winners", "losers",
                                                               "boundary_ties", "release")} for x in rows],
                         indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
