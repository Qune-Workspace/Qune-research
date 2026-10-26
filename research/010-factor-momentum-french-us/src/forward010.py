"""Study 010 forward record, part 1: the monthly position records (PREREGISTRATION.md §11).

Shadow only: the factors are not approved instruments, so there is no paper
order and no paper sleeve.  For each forward holding month t (the first is
2026-09, the month after the snapshot's last month), the positions h_k,t of
T1, T1a and T1b are computed with the study's own signal code (``rule.py``:
formation return over t − L to t − 1, no skipped month; +1 above 10⁻¹², −1
otherwise) from a release of the library that contains month t − 1, and
appended to ``paper-log/positions.csv`` with the release, the files' SHA-256
and the record time.

- The release is read from the three files' header line ("created using the
  YYYYMM CRSP database"); the three must agree, and the release must contain
  month t − 1 in every file, or nothing is written.
- §11 computes h_k,t "from the first release that contains month t − 1":
  the release must be named t − 1 (YYYYMM) and every file must end exactly
  at t − 1, or nothing is written.  A later release is refused, because the
  library revises history and a later release could give a different h_t,
  chosen after month t's return is visible (separate code review, must-fix 1).
  If the first release was not archived, a dated §16 amendment is needed.
- §11: rows committed after the first release that contains month t are
  labelled "late" and still scored.  Lateness comes from the commit time,
  which this module cannot see, so the ``late`` column is written False here
  and set at scoring from git.
- One record per (month, trial); a second is refused, so a record cannot be
  replaced after the month's return is seen.
- B3's h̄ is frozen from the history run (``results/history/summary.json``)
  and written once to ``paper-log/frozen_hbar.json``; it is never re-estimated.

Part 2 (scoring after 60 holding months, interim figures, the vintage row,
the fetch of later releases into ``paper-log/raw/``) is written before any
forward month can be scored; nothing here computes a forward return.

Usage, from the study folder:
  python -m src.forward010 record --month 2026-09 [--raw-dir data/raw --manifest results/data_manifest.json]
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

from .data import FILES, load_factors, read_zip
from .rule import TRIALS, formation_return, sign_position

STUDY_DIR = Path(__file__).resolve().parents[1]
PAPER_LOG = STUDY_DIR / "paper-log"
POSITIONS_CSV = PAPER_LOG / "positions.csv"
FROZEN_HBAR = PAPER_LOG / "frozen_hbar.json"
HISTORY_SUMMARY = STUDY_DIR / "results" / "history" / "summary.json"
FIRST_FORWARD_MONTH = "2026-09"
COLUMNS = ["month", "trial", "factor", "formation_months", "formation_return", "h", "release",
           "release_last_month", "files_sha256", "manifest_sha256", "downloaded_at_utc", "recorded_at_utc", "late"]
FACTORS = ("SMB", "HML", "ST_Rev", "LT_Rev")
_RELEASE = re.compile(r"created using the (\d{6}) CRSP database")


def release_of(manifest_path: Path) -> str:
    """The one release named in the header line of all three files, or an error."""
    files = json.loads(manifest_path.read_text())["files"]
    found = set()
    for name in FILES:
        hits = {m.group(1) for line in files[name]["preamble_lines"] for m in [_RELEASE.search(line)] if m}
        if len(hits) != 1:
            raise ValueError(f"{name}: expected one release line, found {sorted(hits)}")
        found |= hits
    if len(found) != 1:
        raise ValueError(f"the three files name different releases: {sorted(found)}")
    return found.pop()


def files_sha256(manifest_path: Path) -> str:
    files = json.loads(manifest_path.read_text())["files"]
    return ";".join(f"{name}={files[name]['sha256']}" for name in sorted(FILES))


def positions_for(f: pd.DataFrame, month: str) -> list[dict]:
    """h_k,t for every factor each trial holds in month t, from f up to t − 1 only.

    f is the release's monthly frame (percent a month, PeriodIndex).  Every
    factor's last row must be month t − 1 or later; values at t or after are
    dropped before the signal is computed, so a later release cannot leak
    month t into its own position.
    """
    t = pd.Period(month, "M")
    if t < pd.Period(FIRST_FORWARD_MONTH, "M"):
        raise ValueError(f"{month} is inside H; the forward record starts at {FIRST_FORWARD_MONTH}")
    f = f[f.index <= t - 1]
    idx = pd.period_range(f.index[0], t, freq="M")
    rows = []
    for trial in TRIALS.values():
        for k, entry in trial.entry.items():
            if pd.Period(entry, "M") > t:
                continue
            s = f[k].reindex(idx)
            if pd.isna(s.loc[t - 1]):
                raise ValueError(f"{k}: the release has no value for {t - 1}")
            r = formation_return(s, trial.formation).loc[t]
            if pd.isna(r):
                raise ValueError(f"{trial.trial_id} {k}: formation return undefined for {month}")
            h = float(sign_position(pd.Series([r], index=[t])).iloc[0])
            rows.append({"month": str(t), "trial": trial.trial_id, "factor": k,
                         "formation_months": trial.formation, "formation_return": repr(float(r)), "h": int(h)})
    return rows


def freeze_hbar(summary_path: Path = HISTORY_SUMMARY, out: Path = FROZEN_HBAR) -> dict:
    """Write h̄ per trial and factor from the history run once; refuse a different later value."""
    s = json.loads(summary_path.read_text())
    hbar = {t: {k: v["hbar"] for k, v in s["cost_cases"]["base"]["trials"][t]["per_factor"].items()}
            for t in TRIALS}
    for t, trial in TRIALS.items():
        if sorted(hbar[t]) != sorted(trial.factors):
            raise ValueError(f"{t}: h̄ factors {sorted(hbar[t])} differ from the trial's {sorted(trial.factors)}")
    record = {"source": "results/history/summary.json (cost_cases.base.trials.*.per_factor.hbar)",
              "source_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(), "hbar": hbar}
    if out.exists():
        if json.loads(out.read_text())["hbar"] != hbar:
            raise SystemExit(f"STOP: {out.name} exists with a different h̄; it is frozen (§11)")
        return record
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n")
    return record


def downloaded_at(manifest_path: Path) -> str:
    files = json.loads(manifest_path.read_text())["files"]
    missing = [n for n in FILES if not files[n].get("downloaded_at_utc")]
    if missing:
        raise SystemExit(f"STOP: the manifest has no download time for {missing}")
    return ";".join(f"{name}={files[name]['downloaded_at_utc']}" for name in sorted(FILES))


def zip_releases(raw_dir: Path) -> set[str]:
    """The release named in each zip's own header line (re-check note N1: not only the manifest's copy)."""
    found = set()
    for name in FILES:
        hits = {m.group(1) for line in read_zip((raw_dir / name).read_bytes()).splitlines()[:20]
                for m in [_RELEASE.search(line)] if m}
        if len(hits) != 1:
            raise SystemExit(f"STOP: {name} names {sorted(hits)} in its own header")
        found |= hits
    return found


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


def record(month: str, raw_dir: Path, manifest_path: Path, out: Path = POSITIONS_CSV,
           now_utc: str | None = None) -> list[dict]:
    """Append month t's positions for T1, T1a and T1b; refuse if any of them is already recorded."""
    t = pd.Period(month, "M")
    release = release_of(manifest_path)
    want = (t - 1).strftime("%Y%m")
    if release != want:
        raise SystemExit(f"STOP: release {release} is not {want}; §11 requires the first release that contains "
                         f"{t - 1} (a later release could revise it; if {want} was not archived, a dated §16 "
                         f"amendment is needed)")
    f = load_factors(raw_dir, manifest_path)  # checks every zip against the manifest's SHA-256
    if zip_releases(raw_dir) != {want}:
        raise SystemExit(f"STOP: the zips' own header lines do not all name {want}")
    lasts = {k: f[k].last_valid_index() for k in FACTORS}
    if any(v != t - 1 for v in lasts.values()):
        raise SystemExit(f"STOP: every file must end at {t - 1} in the first release; last months {lasts}")
    rows = positions_for(f, month)
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
    p = argparse.ArgumentParser(prog="python -m src.forward010")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record", help="append one forward month's positions")
    r.add_argument("--month", required=True)
    r.add_argument("--raw-dir", type=Path, default=STUDY_DIR / "data" / "raw")
    r.add_argument("--manifest", type=Path, default=STUDY_DIR / "results" / "data_manifest.json")
    a = p.parse_args(argv)
    freeze_hbar()
    rows = record(a.month, a.raw_dir, a.manifest)
    for row in rows:
        print(f"{row['month']} {row['trial']:>4} {row['factor']:>6} h={row['h']:+d} release {row['release']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
