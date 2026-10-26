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

Part 2 (written 2026-10-26, before any forward month can be scored):

- ``fetch``: downloads the three files once into ``paper-log/raw/_incoming/``,
  reads the release from the zips' own header lines (no value is read), and
  keeps the set only if the three agree and the release is new: the history
  snapshot's release and an already archived release are refused and the
  download discarded.  A kept set moves to ``paper-log/raw/<release>/``
  (git-ignored, as ``data/raw/``) with ``paper-log/releases/<release>.json``
  (URL, download time, SHA-256, bytes, header lines; the format ``record``
  reads), which is committed.
- ``late`` (§11): a row is late if its first commit time in git is after the
  desk's first download of a release that contains month t.  The library's own
  publication time is not observable, so lateness is measured against what the
  desk had seen; disclosed in §16 (code decisions).
- ``interim``: months recorded, months with a return in the latest archived
  release, cumulative T and B3 per trial; no t-statistic and no verdict before
  the 60th holding month (Study 008's interim convention).
- ``score``: once, after 60 holding months (2026-09 to 2031-08), from one
  archived release named at scoring that contains all 60 months.  The h scored
  is the committed h; f, B1 and B3 (frozen h̄) come from the scoring release;
  costs as §6.3, the first month's trade measured from h at H's end
  (``results/history/monthly_base.csv``).  C2 and C4 decide, C1 and C3 are
  reported (§11), and the row is worded as a low-power check.  The vintage
  row compares the scoring release with the snapshot over H's months and
  shows h recomputed from the scoring release beside the committed h.
  Output ``results/forward/score.json``, written once.

Usage, from the study folder:
  python -m src.forward010 record --month 2026-09 [--raw-dir data/raw --manifest results/data_manifest.json]
  python -m src.forward010 fetch
  python -m src.forward010 interim
  python -m src.forward010 score --release YYYYMM
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .data import FILES, load_factors, read_zip
from .history import C1_MARGIN, C2_T, C3_DSR, N_FAMILY, diff_row, series_metrics, stats
from .rule import COST_BASE, COST_STRESS, TRIALS, formation_return, run, sign_position

STUDY_DIR = Path(__file__).resolve().parents[1]
PAPER_LOG = STUDY_DIR / "paper-log"
POSITIONS_CSV = PAPER_LOG / "positions.csv"
FROZEN_HBAR = PAPER_LOG / "frozen_hbar.json"
HISTORY_SUMMARY = STUDY_DIR / "results" / "history" / "summary.json"
HISTORY_MONTHLY = STUDY_DIR / "results" / "history" / "monthly_base.csv"
SNAPSHOT_MANIFEST = STUDY_DIR / "results" / "data_manifest.json"
SNAPSHOT_RAW = STUDY_DIR / "data" / "raw"
FORWARD_RAW = PAPER_LOG / "raw"
RELEASES = PAPER_LOG / "releases"
INTERIM_JSON = PAPER_LOG / "interim.json"
SCORE_JSON = STUDY_DIR / "results" / "forward" / "score.json"
H_END = "2026-08"
SCORED_MONTHS = 60
LIBRARY_PAGE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"
UA = {"User-Agent": "qune-research study 010 forward record (one download per file per check)"}
LABEL = "low-power check (60-month detectable Sharpe of d about 1.27 at 80% power, §11)"
NOT_YET_SCORED = "Not yet scored: interim figures, no decision weight (§11 scores once after 60 holding months)"
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


# --- Part 2: fetch, lateness, interim, scoring (§11) ----------------------------------------------------

def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def preamble_of(zbytes: bytes) -> list[str]:
    """The text lines above the monthly column header (they name the release; they hold no value)."""
    lines = read_zip(zbytes).splitlines()
    first = next(i for i, ln in enumerate(lines) if re.fullmatch(r"\d{6}", ln.split(",")[0].strip()))
    return [ln.strip() for ln in lines[: first - 1] if ln.strip()]


def _links(html: str) -> dict[str, str]:
    """The three files' links on the library page (copied from data_step.find_links)."""
    hrefs = re.findall(r'href\s*=\s*"([^"]+)"', html, flags=re.I)
    links = {}
    for name in FILES:
        hits = sorted({h for h in hrefs if h.rsplit("/", 1)[-1] == name})
        if len(hits) != 1:
            raise SystemExit(f"STOP: {len(hits)} links named {name} on the library page; expected exactly one")
        links[name] = requests.compat.urljoin(LIBRARY_PAGE, hits[0])
    return links


def archived(releases_dir: Path = RELEASES) -> dict[str, dict]:
    """Archived forward releases by name, from paper-log/releases/YYYYMM.json."""
    return {p.stem: json.loads(p.read_text()) for p in sorted(releases_dir.glob("[0-9]" * 6 + ".json"))}


def fetch(get=requests.get, raw_root: Path = FORWARD_RAW, releases_dir: Path = RELEASES,
          snapshot_manifest: Path = SNAPSHOT_MANIFEST, now=_utc_now) -> dict:
    """Download the three files once; keep them only if they name one new release (see the module docstring).

    Every attempt, kept or refused, is appended to ``releases/fetch_log.csv`` (committed), so a refused
    download is on record too (code review note 2)."""
    raw_root.mkdir(parents=True, exist_ok=True)
    releases_dir.mkdir(parents=True, exist_ok=True)
    with open(raw_root / ".fetch.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)  # two fetches at once cannot share a staging dir (should-fix 4)
        res = _fetch(get, raw_root, releases_dir, snapshot_manifest, now)
        log = releases_dir / "fetch_log.csv"
        new = not log.exists()
        with log.open("a", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            if new:
                w.writerow(["at_utc", "kept", "release", "reason"])
            w.writerow([res.get("at_utc", ""), res["kept"], res.get("release", ""), res.get("reason", "")])
        return res


def _fetch(get, raw_root: Path, releases_dir: Path, snapshot_manifest: Path, now) -> dict:
    incoming = Path(tempfile.mkdtemp(prefix="_incoming-", dir=raw_root))
    try:
        page_time = now()
        base = {"at_utc": page_time}
        page = get(LIBRARY_PAGE, headers=UA, timeout=60)
        page.raise_for_status()
        files = {}
        for name, url in _links(page.text).items():
            t = now()
            r = get(url, headers=UA, timeout=120)
            r.raise_for_status()
            (incoming / name).write_bytes(r.content)
            files[name] = {"url": url, "downloaded_at_utc": t, "sha256": hashlib.sha256(r.content).hexdigest(),
                           "bytes": len(r.content), "preamble_lines": preamble_of(r.content)}
        rels = {}
        for name in FILES:
            hits = {m.group(1) for ln in files[name]["preamble_lines"] for m in [_RELEASE.search(ln)] if m}
            if len(hits) != 1:
                return {**base, "kept": False, "reason": f"{name} names {sorted(hits)} in its header"}
            rels[name] = hits.pop()
        if len(set(rels.values())) != 1:
            return {**base, "kept": False, "reason": f"the files name different releases {rels} (library mid-update?)"}
        rel = rels[next(iter(FILES))]
        snap = release_of(snapshot_manifest)
        if rel <= snap:
            return {**base, "kept": False, "release": rel, "reason": f"not newer than the history snapshot's release {snap}"}
        man, dest = releases_dir / f"{rel}.json", raw_root / rel
        if man.exists():
            return {**base, "kept": False, "release": rel, "reason": "already archived (one download per release)"}
        latest = max(archived(releases_dir), default=None)
        if latest is not None and rel < latest:
            return {**base, "kept": False, "release": rel, "reason": f"older than the latest archived release {latest}"}
        if dest.exists():  # files without their json: an earlier fetch stopped before its record (should-fix 3)
            shutil.rmtree(dest)
        rec = {"release": rel, "library_page": {"url": LIBRARY_PAGE, "read_at_utc": page_time,
                                                "sha256": hashlib.sha256(page.content).hexdigest()},
               "files": files}
        tmp = man.with_suffix(".tmp")
        tmp.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
        incoming.rename(dest)
        tmp.replace(man)  # the json exists only once the files are in place
        return {**base, "kept": True, "release": rel, "raw_dir": str(dest), "manifest": str(man)}
    finally:
        shutil.rmtree(incoming, ignore_errors=True)


def read_positions(path: Path = POSITIONS_CSV) -> pd.DataFrame:
    body = existing_body(path)
    if not body:
        raise SystemExit(f"STOP: {path.name} has no record")
    pos = pd.read_csv(io.StringIO(body), dtype=str)
    key = ["month", "trial", "factor"]
    if pos.duplicated(key).any():
        raise SystemExit("STOP: a (month, trial, factor) is recorded twice")
    return pos


def row_commit_times(path: Path = POSITIONS_CSV) -> dict[tuple[str, str, str], dict]:
    """Per (month, trial, factor): the earliest commit time (UTC) of the row and the row as first committed.

    The row as first committed is what ``score`` uses: a later rewrite or an uncommitted edit is refused
    there (code review must-fix 1).  Commit times are the committer's clock; the push events on the public
    remote are the stronger evidence and are cited in BUILD_LOG (review note 1)."""
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path.parent, check=True,
                         capture_output=True, text=True).stdout.strip()
    shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=top, check=True,
                             capture_output=True, text=True).stdout.strip()
    if shallow == "true":
        raise SystemExit("STOP: a shallow clone cannot date the rows; use a full clone")
    rel = path.resolve().relative_to(Path(top).resolve()).as_posix()
    log = subprocess.run(["git", "log", "--reverse", "--format=%H %cI", "--", rel], cwd=top, check=True,
                         capture_output=True, text=True).stdout.split("\n")
    times: dict[tuple[str, str, str], dict] = {}
    for line in filter(None, log):
        h, t = line.split()
        when = pd.Timestamp(t).tz_convert("UTC")
        body = subprocess.run(["git", "show", f"{h}:{rel}"], cwd=top, capture_output=True, text=True).stdout
        for r in csv.DictReader(body.splitlines()):
            key = (r["month"], r["trial"], r["factor"])
            if key not in times or when < times[key]["time"]:
                times[key] = {"time": when, "row": {c: r[c] for c in COLUMNS if c != "late"}}
    return times


def first_seen(month: str, releases: dict[str, dict]) -> pd.Timestamp | None:
    """When the desk first held a release containing month t: the last file download of the earliest such set."""
    want = pd.Period(month, "M").strftime("%Y%m")
    seen = [max(pd.Timestamp(v["downloaded_at_utc"]) for v in rec["files"].values())
            for name, rec in releases.items() if name >= want]
    return min(seen) if seen else None


def late_flags(pos: pd.DataFrame, commit_times: dict, releases: dict[str, dict]) -> pd.Series:
    """§11 "late": committed after the desk first held a release containing month t (True / False)."""
    out = []
    for r in pos.itertuples(index=False):
        key = (r.month, r.trial, r.factor)
        if key not in commit_times:
            raise SystemExit(f"STOP: {key} is not in any commit; every scored row must be committed first")
        seen = first_seen(r.month, releases)
        out.append(bool(seen is not None and commit_times[key]["time"] > seen))
    return pd.Series(out, index=pos.index)


def h_at_h_end(path: Path = HISTORY_MONTHLY) -> dict[str, dict[str, float]]:
    """h at H's last month (2026-08) per trial and factor, from the history run's committed monthly file."""
    m = pd.read_csv(path, dtype={"month": str}).set_index("month")
    if m.index[-1] != H_END:
        raise SystemExit(f"STOP: {path.name} ends at {m.index[-1]}, not {H_END}")
    last = m.loc[H_END]
    return {t: {k: float(last[f"{t}_h_{k}"]) for k in trial.factors} for t, trial in TRIALS.items()}


def committed_h(pos: pd.DataFrame, trial: str, months: pd.PeriodIndex) -> pd.DataFrame:
    sub = pos[pos["trial"] == trial]
    h = sub.pivot(index="month", columns="factor", values="h").astype(float)
    h.index = pd.PeriodIndex(h.index, freq="M")
    h = h.reindex(index=months, columns=TRIALS[trial].factors)
    if h.isna().any().any():
        raise SystemExit(f"STOP: {trial} has no committed h for some month or factor in {months[0]}..{months[-1]}")
    if not h.isin([1.0, -1.0]).all().all():
        raise SystemExit(f"STOP: {trial} has an h other than +1 / −1")
    return h


def forward_frame(h: pd.DataFrame, f: pd.DataFrame, hbar: dict[str, float], h_prev: dict[str, float],
                  cost: float) -> pd.DataFrame:
    """T, B1, B3, d on the committed h (§9.1, §6.3); the first month's trade from h at H's end."""
    fh = f.reindex(h.index)[h.columns]
    if fh.isna().any().any():
        raise SystemExit("STOP: the release has no return for a scored month")
    K = float(h.shape[1])
    prev = h.shift(1)
    prev.iloc[0] = pd.Series(h_prev)[h.columns]
    traded = (2.0 * (h - prev).abs()).sum(axis=1) / K
    t_gross = (h * fh).sum(axis=1) / K
    b3 = (fh * pd.Series(hbar)[h.columns]).sum(axis=1) / K
    t_net = t_gross - cost * traded
    return pd.DataFrame({"T_gross": t_gross, "cost": cost * traded, "T": t_net, "B1": fh.sum(axis=1) / K,
                         "B3": b3, "d": t_net - b3, "K": K})


def _release_frame(release: str, raw_root: Path, releases_dir: Path) -> pd.DataFrame:
    man = releases_dir / f"{release}.json"
    if not man.exists():
        raise SystemExit(f"STOP: release {release} is not archived in {releases_dir.name}/")
    f = load_factors(raw_root / release, man)  # checks every zip against its SHA-256
    if zip_releases(raw_root / release) != {release} or release_of(man) != release:
        raise SystemExit(f"STOP: the archived files do not all name {release}")
    return f


def interim(pos: pd.DataFrame, raw_root: Path = FORWARD_RAW, releases_dir: Path = RELEASES,
            hbar: dict | None = None, h_prev: dict | None = None, now_utc: str | None = None) -> dict:
    """Counts and cumulative returns so far; no t-statistic and no verdict before the 60th month."""
    hbar = hbar or json.loads(FROZEN_HBAR.read_text())["hbar"]
    h_prev = h_prev or h_at_h_end()
    rels = archived(releases_dir)
    latest = max(rels, default=None)
    out = {"heading": NOT_YET_SCORED, "label": LABEL, "written_at_utc": now_utc or _utc_now(),
           "scored_after": f"{SCORED_MONTHS} holding months ({FIRST_FORWARD_MONTH} to "
                           f"{pd.Period(FIRST_FORWARD_MONTH, 'M') + SCORED_MONTHS - 1})",
           "latest_archived_release": latest, "trials": {}}
    f = _release_frame(latest, raw_root, releases_dir) if latest else None
    for t in TRIALS:
        recorded = sorted(pos.loc[pos["trial"] == t, "month"].unique())
        row = {"months_recorded": len(recorded), "months_with_return": 0, "cumulative_T": None,
               "cumulative_B3": None, "mean_d_pct_a_year": None}
        if f is not None and recorded:
            last_f = min(f[k].last_valid_index() for k in TRIALS[t].factors)
            months = pd.period_range(FIRST_FORWARD_MONTH, recorded[-1], freq="M")
            months = months[months <= last_f]
            if len(months) and set(str(m) for m in months) <= set(recorded):
                fr = forward_frame(committed_h(pos, t, months), f, hbar[t], h_prev[t], COST_BASE)
                row.update(months_with_return=int(len(fr)),
                           cumulative_T=float(np.prod(1 + fr["T"].to_numpy() / 100) - 1),
                           cumulative_B3=float(np.prod(1 + fr["B3"].to_numpy() / 100) - 1),
                           mean_d_pct_a_year=float(fr["d"].mean() * 12))
        out["trials"][t] = row
    out["months_to_scoring"] = SCORED_MONTHS - out["trials"]["T1"]["months_with_return"]
    return out


def vintage_row(f_score: pd.DataFrame, f_snap: pd.DataFrame, pos: pd.DataFrame, months: pd.PeriodIndex) -> dict:
    """The scoring release against the snapshot over H's months, and h recomputed beside the committed h."""
    h_idx = pd.period_range("1926-02", H_END, freq="M")
    per = {}
    for k in FACTORS:
        a, b = f_snap[k].reindex(h_idx), f_score[k].reindex(h_idx)
        both = a.notna() & b.notna()
        diff = (b - a)[both]
        per[k] = {"months_compared": int(both.sum()), "months_only_in_one": int((a.notna() ^ b.notna()).sum()),
                  "months_differing": int((diff.abs() > 1e-9).sum()),
                  "max_abs_change_pct": float(diff.abs().max()) if len(diff) else 0.0,
                  "mean_change_pct_a_year": float(diff.mean() * 12) if len(diff) else 0.0}
    d_score = run(f_score, TRIALS["T1"], H_END, COST_BASE)["frame"]["d"]
    d_snap = run(f_snap, TRIALS["T1"], H_END, COST_BASE)["frame"]["d"]
    recomputed = []
    for m in months:
        for r in positions_for(f_score, str(m)):
            c = pos[(pos["month"] == r["month"]) & (pos["trial"] == r["trial"]) & (pos["factor"] == r["factor"])]
            recomputed.append({"month": r["month"], "trial": r["trial"], "factor": r["factor"],
                               "h_committed": int(c["h"].iloc[0]), "h_scoring_release": r["h"]})
    differ = [x for x in recomputed if x["h_committed"] != x["h_scoring_release"]]
    return {"per_factor_over_H": per,
            "T1_mean_d_over_H_pct_a_year": {"snapshot": float(d_snap.mean() * 12),
                                            "scoring_release": float(d_score.mean() * 12)},
            "h_rows_compared": len(recomputed), "h_rows_differing": len(differ), "h_differing": differ}


def forward_verdict(m: dict, stress_mean_d: float) -> dict:
    """§11: §9.5's C1–C4 on the 60 months; C2 and C4 decide, C1 and C3 are reported; a low-power check."""
    sT, s1 = m["T"]["sharpe_annual"], m["B1"]["sharpe_annual"]
    c1_b3 = sT >= C1_MARGIN if m["B3"] is None else sT >= m["B3"]["sharpe_annual"] + C1_MARGIN
    c = {"C1_reported": bool(sT >= s1 + C1_MARGIN and c1_b3),
         "C2": bool(m["d"]["nw_t"] >= C2_T),
         "C3_reported": bool(m["dsr"]["dsr"] >= C3_DSR),
         "C4": bool(np.sign(stress_mean_d) == np.sign(m["d"]["mean_pct_a_year"]))}
    row = "meets C2 and C4" if c["C2"] and c["C4"] else "does not meet C2 and C4"
    return {**c, "row": f"{row} ({LABEL})"}


def own_release_loader(raw_root: Path = FORWARD_RAW, releases_dir: Path = RELEASES,
                       snapshot_raw: Path = SNAPSHOT_RAW, snapshot_manifest: Path = SNAPSHOT_MANIFEST):
    """month t -> (frame, release, files_sha256) of the release a row for t must come from (release t − 1)."""
    cache: dict[str, tuple] = {}

    def load(month: str) -> tuple:
        want = (pd.Period(month, "M") - 1).strftime("%Y%m")
        if want not in cache:
            if want == release_of(snapshot_manifest):
                cache[want] = (load_factors(snapshot_raw, snapshot_manifest), want, files_sha256(snapshot_manifest))
            else:
                cache[want] = (_release_frame(want, raw_root, releases_dir), want,
                               files_sha256(releases_dir / f"{want}.json"))
        return cache[want]
    return load


def check_rows(pos: pd.DataFrame, commit_times: dict, own_release) -> list[str]:
    """Each scored row equals its first commit and is reproduced from its own release (review must-fix 1, should-fix 2).

    h must match exactly and the formation return to 1e-12 relative (a library upgrade by 2031 may move the last
    digit; re-check should-fix 1).  If a release's raw files are no longer on disk (the library serves only the
    latest release), its months are returned as not re-checked and listed in score.json; the rows themselves are
    still held to their first commit (re-check should-fix 4)."""
    not_rechecked = []
    for r in pos.to_dict("records"):
        key = (r["month"], r["trial"], r["factor"])
        if key not in commit_times:
            raise SystemExit(f"STOP: {key} is not in any commit; every scored row must be committed first")
        first = commit_times[key]["row"]
        if any(str(r[c]) != first[c] for c in first):
            raise SystemExit(f"STOP: {key} differs from its first commit; a record is never replaced (§11)")
    for month in sorted(pos["month"].unique()):
        try:
            f, release, sha = own_release(month)
        except FileNotFoundError:
            not_rechecked.append(month)
            continue
        mine = pos[pos["month"] == month]
        if set(mine["release"]) != {release} or set(mine["files_sha256"]) != {sha}:
            raise SystemExit(f"STOP: {month}'s rows do not name release {release} and its files' SHA-256")
        again = {(x["trial"], x["factor"]): x for x in positions_for(f, month)}
        for r in mine.itertuples(index=False):
            x = again[(r.trial, r.factor)]
            a, b = float(r.formation_return), float(x["formation_return"])
            if int(r.h) != x["h"] or abs(a - b) > 1e-12 * max(1.0, abs(b)):
                raise SystemExit(f"STOP: {month} {r.trial} {r.factor} is not reproduced from release {release}")
    return not_rechecked


def scoring_release(months: pd.PeriodIndex, releases: dict[str, dict]) -> str:
    """The first archived release that contains the 60th month: fixed by the archive, not chosen (should-fix 1)."""
    want = months[-1].strftime("%Y%m")
    hits = sorted(r for r in releases if r >= want)
    if not hits:
        raise SystemExit(f"STOP: no archived release contains {months[-1]} yet")
    return hits[0]


def _ever_committed(path: Path) -> bool:
    """True if git has any commit of this path (a deleted score.json does not reopen the scoring)."""
    cwd = next(d for d in [path.parent, *path.parent.parents] if d.exists())
    r = subprocess.run(["git", "log", "--all", "--format=%H", "--", str(path.resolve())], cwd=cwd,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"STOP: git could not say whether {path.name} was committed before ({r.stderr.strip()})")
    return bool(r.stdout.strip())


def _clean(o):
    """NaN and infinities become null, so score.json is strict JSON (review note 5)."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, (np.integer, np.bool_)):
        return o.item()
    return o


def score(release: str, pos: pd.DataFrame, commit_times: dict, raw_root: Path = FORWARD_RAW,
          releases_dir: Path = RELEASES, snapshot_raw: Path = SNAPSHOT_RAW,
          snapshot_manifest: Path = SNAPSHOT_MANIFEST, hbar: dict | None = None, h_prev: dict | None = None,
          out: Path = SCORE_JSON, now_utc: str | None = None, own_release=None) -> dict:
    """Score the 60 holding months once, from the first archived release that contains them (§11)."""
    if out.exists() or _ever_committed(out):
        raise SystemExit(f"STOP: {out.name} exists or was committed before; the forward record is scored once (§11)")
    hbar = hbar or json.loads(FROZEN_HBAR.read_text())["hbar"]
    h_prev = h_prev or h_at_h_end()
    months = pd.period_range(FIRST_FORWARD_MONTH, periods=SCORED_MONTHS, freq="M")
    want = {(str(m), t, k) for m in months for t, tr in TRIALS.items() for k in tr.factors}
    have = set(zip(pos["month"], pos["trial"], pos["factor"]))
    if not want <= have:
        raise SystemExit(f"STOP: {len(want - have)} of the 60 months' rows are not recorded")
    pos = pos[[k in want for k in zip(pos["month"], pos["trial"], pos["factor"])]].reset_index(drop=True)
    first = scoring_release(months, archived(releases_dir))
    if release != first:
        raise SystemExit(f"STOP: the scoring release is {first}, the first archived release containing {months[-1]}")
    not_rechecked = check_rows(pos, commit_times, own_release or own_release_loader(raw_root, releases_dir,
                                                                                   snapshot_raw, snapshot_manifest))
    f = _release_frame(release, raw_root, releases_dir)
    if any(f[k].last_valid_index() < months[-1] for k in FACTORS):
        raise SystemExit(f"STOP: release {release} does not contain {months[-1]} for every factor")
    if not (snapshot_raw / next(iter(FILES))).exists():
        raise SystemExit("STOP: the snapshot's raw files are needed for the vintage row (§11)")
    f_snap = load_factors(snapshot_raw, snapshot_manifest)
    late = late_flags(pos, commit_times, archived(releases_dir))
    frames = {case: {t: forward_frame(committed_h(pos, t, months), f, hbar[t], h_prev[t], c)
                     for t in TRIALS} for case, c in (("base", COST_BASE), ("stress", COST_STRESS))}
    var, floored = stats.trial_variance([stats.sharpe_monthly(frames["base"][t]["T"] / 100) for t in TRIALS])
    trials = {}
    for t in TRIALS:
        fr = frames["base"][t]
        x = fr["T"] / 100
        b3_zero = all(v == 0 for v in hbar[t].values())
        m = {"T": series_metrics(fr["T"], None), "B1": series_metrics(fr["B1"], None),
             "B3": None if b3_zero else series_metrics(fr["B3"], None), "d": diff_row(fr["d"]),
             "T_minus_B1": diff_row(fr["T"] - fr["B1"]), "cost_pct_a_year": float(fr["cost"].mean() * 12),
             "dsr": stats.deflated_sharpe(stats.sharpe_monthly(x), len(x), stats.skewness(x), stats.kurtosis(x),
                                          N_FAMILY, var)}
        stress = float(frames["stress"][t]["d"].mean() * 12)
        sel = pos["trial"] == t
        trials[t] = {**m, "stress_mean_d_pct_a_year": stress, "verdict": forward_verdict(m, stress),
                     "rows_late": int(late[sel].sum()), "rows": int(sel.sum()),
                     "late_rows": [[r.month, r.factor] for r in pos[sel & late].itertuples(index=False)]}
    result = {"release": release, "months": [str(months[0]), str(months[-1])], "label": LABEL,
              "scored_at_utc": now_utc or _utc_now(), "N_family": N_FAMILY,
              "variance_across_trials": var, "floor_applied": floored, "trials": trials,
              "headline": f"T1: {trials['T1']['verdict']['row']}",
              "months_not_rechecked_raw_files_missing": not_rechecked,
              "vintage": vintage_row(f, f_snap, pos, months)}
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if out.exists():
            raise SystemExit(f"STOP: {out.name} exists; the forward record is scored once (§11)")
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(_clean(result), indent=2, allow_nan=False) + "\n")
        tmp.replace(out)
    return result

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m src.forward010")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record", help="append one forward month's positions")
    r.add_argument("--month", required=True)
    r.add_argument("--raw-dir", type=Path, default=STUDY_DIR / "data" / "raw")
    r.add_argument("--manifest", type=Path, default=STUDY_DIR / "results" / "data_manifest.json")
    sub.add_parser("fetch", help="download the three files once; keep them only if they name a new release")
    sub.add_parser("interim", help="write paper-log/interim.json (no t-statistic, no verdict)")
    s = sub.add_parser("score", help="score the 60 holding months once, from one archived release")
    s.add_argument("--release", required=True)
    a = p.parse_args(argv)
    if a.cmd == "fetch":
        print(json.dumps(fetch(), indent=2))
        return 0
    if a.cmd == "interim":
        payload = interim(read_positions())
        INTERIM_JSON.write_text(json.dumps(payload, indent=2) + "\n")
        print(json.dumps(payload, indent=2))
        return 0
    if a.cmd == "score":
        res = score(a.release, read_positions(), row_commit_times())
        print(res["headline"])
        return 0
    freeze_hbar()
    rows = record(a.month, a.raw_dir, a.manifest)
    for row in rows:
        print(f"{row['month']} {row['trial']:>4} {row['factor']:>6} h={row['h']:+d} release {row['release']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
