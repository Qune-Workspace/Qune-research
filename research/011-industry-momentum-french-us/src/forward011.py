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
  replaced after the month's return is seen.  A month after the first is
  refused until t − 1 has been recorded, because §11 takes the five earlier
  cohorts held in t from the earlier records (code review note 5).  The append is atomic under a
  file lock.
- Each row carries every eligible industry's formation return at full
  precision (``repr``), so the ranking can be re-checked from the row alone.

Part 2 (written 2026-10-26, before any forward month can be scored; adapted
from Study 010's part 2 with the fixes of its code review):

- ``fetch``: downloads the two files once into ``paper-log/raw/_incoming-*``,
  reads the release from the zips' own header lines and the industry names
  from the value-weighted monthly section's column header (no value is read),
  and keeps the set only if the two name one new release and every file's
  industry names equal the history's (``results/history/industries_N.csv``
  header, in order).  The history snapshot's release, an archived release and
  a release older than the latest archived one are refused and the download
  discarded.  A kept set moves to ``paper-log/raw/<release>/`` (git-ignored)
  with ``paper-log/releases/<release>.json`` (the format ``record`` reads),
  which is committed.  Every attempt is appended to
  ``paper-log/releases/fetch_log.csv``.
- ``late`` (§11, §16 item 3): a row is late if its first commit time in git is
  after the desk's first download of a release that contains month t.
- ``interim``: months recorded, months with a return in the latest archived
  release, mean d and summed d per trial at base costs; no t-statistic and no
  verdict before the 60th holding month.
- ``score``: once, after 60 holding months (2026-09 to 2031-08), from the
  first archived release that contains 2031-08.  The cohorts scored are the
  committed ones (ranking months 2026-08 on) and the history run's for the
  first five forward months' earlier cohorts (ranking months to 2026-07, §16
  item 4); returns come from the scoring release; costs as §6.3, the first
  month's trade measured from the history's 2026-08 weights.  Each row must
  equal its first commit and be reproduced from its own release.  C2 and C4
  decide, C1 and C3 are reported (§11); worded as a low-power check.  The
  vintage row compares the scoring release with the snapshot over the
  history's months and shows the cohorts recomputed from the scoring release
  beside the committed ones.  Output ``results/forward/score.json``, once.

Usage, from the study folder:
  python -m src.forward011 record --month 2026-09 [--raw-dir data/raw --manifest results/data_manifest.json]
  python -m src.forward011 fetch
  python -m src.forward011 interim
  python -m src.forward011 score --release YYYYMM
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
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .data import FILES, SECTION_TITLE, load_industries, read_zip
from .history import C1_SHARPE, C2_T, C3_DSR, I1_END, I2_START, N_FAMILY, TRIALS, diff_row, stats
from .rule import COST_BASE, COST_STRESS, HOLD, cohort_table, formation_returns, rank_cohort, run

STUDY_DIR = Path(__file__).resolve().parents[1]
PAPER_LOG = STUDY_DIR / "paper-log"
COHORTS_CSV = PAPER_LOG / "cohorts.csv"
SNAPSHOT_MANIFEST = STUDY_DIR / "results" / "data_manifest.json"
SNAPSHOT_RAW = STUDY_DIR / "data" / "raw"
HISTORY_DIR = STUDY_DIR / "results" / "history"
HISTORY_COHORTS = HISTORY_DIR / "cohorts.json"
FORWARD_RAW = PAPER_LOG / "raw"
RELEASES = PAPER_LOG / "releases"
INTERIM_JSON = PAPER_LOG / "interim.json"
SCORE_JSON = STUDY_DIR / "results" / "forward" / "score.json"
H_END = "2026-08"
SCORED_MONTHS = 60
LIBRARY_PAGE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"
UA = {"User-Agent": "qune-research study 011 forward record (one download per file per check)"}
LABEL = "low-power check (60-month detectable Sharpe of d about 1.27 at 80% power, §11)"
NOT_YET_SCORED = "Not yet scored: interim figures, no decision weight (§11 scores once after 60 holding months)"
FIRST_FORWARD_MONTH = "2026-09"
COLUMNS = ["month", "ranking_month", "trial", "industries", "formation_months", "n_side", "winners", "losers",
           "boundary_ties", "formation_returns", "release", "release_last_month", "files_sha256",
           "manifest_sha256", "downloaded_at_utc", "recorded_at_utc", "late"]
# The 30-industry file reads "created by CMPT_IND_RETS using the ..." (data step; code review must-fix 1).
_RELEASE = re.compile(r"created (?:by \S+ )?using the (\d{6}) CRSP database")


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
        have = existing(out)
        done = have & {(r["month"], r["trial"]) for r in rows}
        if done:
            raise SystemExit(f"STOP: already recorded {sorted(done)}; a record is never replaced (§11)")
        prev = str(t - 1)
        if t > pd.Period(FIRST_FORWARD_MONTH, "M") and not all((prev, tid) in have for tid in TRIALS):
            raise SystemExit(f"STOP: {prev} is not recorded for every trial; record the months in order (§11)")
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


def _section_header(text: str) -> tuple[list[str], int]:
    """Lines and index of the value-weighted monthly section's title (no value is read)."""
    lines = text.splitlines()
    titles = [i for i, ln in enumerate(lines) if " ".join(ln.split()) == SECTION_TITLE]
    if len(titles) != 1:
        raise ValueError(f"{len(titles)} value-weighted monthly sections")
    return lines, titles[0]


def preamble_of(zbytes: bytes) -> list[str]:
    """The text lines above the value-weighted monthly section (they name the release; they hold no value)."""
    lines, title = _section_header(read_zip(zbytes))
    return [ln.strip() for ln in lines[:title] if ln.strip()]


def industry_names(zbytes: bytes) -> list[str]:
    """The column header of the value-weighted monthly section, in file order (no value is read)."""
    lines, h = _section_header(read_zip(zbytes))
    h += 1
    while not lines[h].strip():
        h += 1
    return [c.strip() for c in lines[h].split(",")[1:]]


def expected_names(history_dir: Path = HISTORY_DIR) -> dict[str, list[str]]:
    """The history's industry names per file, in order, from the committed industries_N.csv headers."""
    out = {}
    for n, name in FILES.items():
        with (history_dir / f"industries_{n}.csv").open() as fh:
            out[name] = next(csv.reader(fh))[1:]
    return out


def _links(html: str) -> dict[str, str]:
    """The two files' links on the library page (as the data step's find_links)."""
    hrefs = re.findall(r'href\s*=\s*"([^"]+)"', html, flags=re.I)
    links = {}
    for name in _names():
        hits = sorted({h for h in hrefs if h.rsplit("/", 1)[-1] == name})
        if len(hits) != 1:
            raise SystemExit(f"STOP: {len(hits)} links named {name} on the library page; expected exactly one")
        links[name] = requests.compat.urljoin(LIBRARY_PAGE, hits[0])
    return links


def archived(releases_dir: Path = RELEASES) -> dict[str, dict]:
    """Archived forward releases by name, from paper-log/releases/YYYYMM.json."""
    return {p.stem: json.loads(p.read_text()) for p in sorted(releases_dir.glob("[0-9]" * 6 + ".json"))}


def fetch(get=requests.get, raw_root: Path = FORWARD_RAW, releases_dir: Path = RELEASES,
          snapshot_manifest: Path = SNAPSHOT_MANIFEST, history_dir: Path = HISTORY_DIR, now=_utc_now) -> dict:
    """Download the two files once; keep them only if they name one new release with the history's industries.

    Every attempt, kept or refused, is appended to ``releases/fetch_log.csv`` (committed)."""
    raw_root.mkdir(parents=True, exist_ok=True)
    releases_dir.mkdir(parents=True, exist_ok=True)
    with open(raw_root / ".fetch.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)  # two fetches at once cannot share a staging dir
        res = _fetch(get, raw_root, releases_dir, snapshot_manifest, history_dir, now)
        log = releases_dir / "fetch_log.csv"
        new = not log.exists()
        with log.open("a", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            if new:
                w.writerow(["at_utc", "kept", "release", "reason"])
            w.writerow([res.get("at_utc", ""), res["kept"], res.get("release", ""), res.get("reason", "")])
        return res


def _fetch(get, raw_root: Path, releases_dir: Path, snapshot_manifest: Path, history_dir: Path, now) -> dict:
    incoming = Path(tempfile.mkdtemp(prefix="_incoming-", dir=raw_root))
    try:
        page_time = now()
        base = {"at_utc": page_time}
        page = get(LIBRARY_PAGE, headers=UA, timeout=60)
        page.raise_for_status()
        files, names = {}, {}
        for name, url in _links(page.text).items():
            t = now()
            r = get(url, headers=UA, timeout=120)
            r.raise_for_status()
            (incoming / name).write_bytes(r.content)
            try:
                pre, names[name] = preamble_of(r.content), industry_names(r.content)
            except (ValueError, IndexError, zipfile.BadZipFile) as e:
                return {**base, "kept": False, "reason": f"{name} could not be read ({type(e).__name__}: {e})"}
            files[name] = {"url": url, "downloaded_at_utc": t, "sha256": hashlib.sha256(r.content).hexdigest(),
                           "bytes": len(r.content), "preamble_lines": pre}
        rels = {}
        for name in _names():
            hits = {m.group(1) for ln in files[name]["preamble_lines"] for m in [_RELEASE.search(ln)] if m}
            if len(hits) != 1:
                return {**base, "kept": False, "reason": f"{name} names {sorted(hits)} in its header"}
            rels[name] = hits.pop()
        if len(set(rels.values())) != 1:
            return {**base, "kept": False, "reason": f"the files name different releases {rels} (library mid-update?)"}
        rel = rels[_names()[0]]
        want = expected_names(history_dir)
        changed = [n for n in _names() if names[n] != want[n]]
        if changed:
            return {**base, "kept": False, "release": rel,
                    "reason": f"industry names differ from the history's in {changed}; a dated §16 amendment is needed"}
        snap = release_of(snapshot_manifest)
        if rel <= snap:
            return {**base, "kept": False, "release": rel, "reason": f"not newer than the history snapshot's release {snap}"}
        man, dest = releases_dir / f"{rel}.json", raw_root / rel
        if man.exists():
            return {**base, "kept": False, "release": rel, "reason": "already archived (one download per release)"}
        latest = max(archived(releases_dir), default=None)
        if latest is not None and rel < latest:
            return {**base, "kept": False, "release": rel, "reason": f"older than the latest archived release {latest}"}
        if dest.exists():  # files without their json: an earlier fetch stopped before its record
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


def read_cohorts(path: Path = COHORTS_CSV) -> pd.DataFrame:
    body = existing_body(path)
    if not body:
        raise SystemExit(f"STOP: {path.name} has no record")
    pos = pd.read_csv(io.StringIO(body), dtype=str, keep_default_na=False)
    if pos.duplicated(["month", "trial"]).any():
        raise SystemExit("STOP: a (month, trial) is recorded twice")
    return pos


def row_commit_times(path: Path = COHORTS_CSV) -> dict[tuple[str, str], dict]:
    """Per (month, trial): the earliest commit time (UTC) of the row and the row as first committed.

    ``score`` holds every row to its first commit, so a later rewrite or an uncommitted edit is refused.
    Commit times are the committer's clock; push events on the public remote are the stronger evidence."""
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path.parent, check=True,
                         capture_output=True, text=True).stdout.strip()
    shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=top, check=True,
                             capture_output=True, text=True).stdout.strip()
    if shallow == "true":
        raise SystemExit("STOP: a shallow clone cannot date the rows; use a full clone")
    rel = path.resolve().relative_to(Path(top).resolve()).as_posix()
    log = subprocess.run(["git", "log", "--reverse", "--format=%H %cI", "--", rel], cwd=top, check=True,
                         capture_output=True, text=True).stdout.split("\n")
    times: dict[tuple[str, str], dict] = {}
    for line in filter(None, log):
        h, t = line.split()
        when = pd.Timestamp(t).tz_convert("UTC")
        body = subprocess.run(["git", "show", f"{h}:{rel}"], cwd=top, check=True, capture_output=True,
                              text=True).stdout
        for r in csv.DictReader(body.splitlines()):
            key = (r["month"], r["trial"])
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
        key = (r.month, r.trial)
        if key not in commit_times:
            raise SystemExit(f"STOP: {key} is not in any commit; every scored row must be committed first")
        seen = first_seen(r.month, releases)
        out.append(bool(seen is not None and commit_times[key]["time"] > seen))
    return pd.Series(out, index=pos.index)


def history_cohorts(path: Path = HISTORY_COHORTS) -> dict[str, dict[str, tuple[list[str], list[str]]]]:
    """W(m), L(m) per trial and ranking month from the history run's committed cohorts.json."""
    raw = json.loads(path.read_text())
    return {t: {m: (v[0], v[1]) for m, v in raw[t].items()} for t in TRIALS}


def history_ranks_used() -> list[str]:
    """Ranking months whose history cohorts the forward record uses: 2026-02 to 2026-07 (the first
    forward months' earlier cohorts and, through 2026-08's weights, the first month's trade)."""
    first_rank = pd.Period(FIRST_FORWARD_MONTH, "M") - 1
    return [str(first_rank - j) for j in range(HOLD, 0, -1)]


def check_history_cohorts(ind: dict, hist: dict) -> list[list[str]]:
    """The history cohorts the forward record uses, recomputed from a release; returns [month, trial] that differ."""
    differ = []
    start = pd.Period(history_ranks_used()[0], "M")
    for t, spec in TRIALS.items():
        again = cohort_table(ind[spec["set"]][ind[spec["set"]].index <= start + HOLD - 1], spec["F"], spec["n"], start)
        for m in history_ranks_used():
            if m not in hist[t] or m not in again or list(hist[t][m]) != list(again[m][:2]):
                differ.append([m, t])
    return differ


def cohort_map(pos: pd.DataFrame, trial: str, hist: dict[str, tuple[list[str], list[str]]]) -> dict[pd.Period, tuple]:
    """Ranking month -> (W, L): the history's before the first forward ranking month, the committed rows from it (§16 item 4)."""
    first_rank = pd.Period(FIRST_FORWARD_MONTH, "M") - 1
    out = {pd.Period(m, "M"): v for m, v in hist.items() if pd.Period(m, "M") < first_rank}
    for r in pos[pos["trial"] == trial].itertuples(index=False):
        m = pd.Period(r.ranking_month, "M")
        if m != pd.Period(r.month, "M") - 1:
            raise SystemExit(f"STOP: {r.month} {trial} names ranking month {m}, not t − 1")
        out[m] = (r.winners.split(";"), r.losers.split(";"))
    return out


def weights(cmap: dict, t: pd.Period, cols: list[str], n: int) -> pd.Series:
    """§6.3 target weights in month t from the six cohorts ranked t − 1 … t − 6."""
    w = pd.Series(0.0, index=cols)
    for j in range(1, HOLD + 1):
        if t - j not in cmap:
            raise SystemExit(f"STOP: no cohort ranked at {t - j} (needed for {t})")
        W, L = cmap[t - j]
        if (len(set(W)) != n or len(set(L)) != n or set(W) & set(L) or len(W) != n or len(L) != n
                or not set(W) | set(L) <= set(cols)):
            raise SystemExit(f"STOP: the cohort ranked at {t - j} is not {n} + {n} distinct industries of the file")
        w[W] += 1.0 / (HOLD * n)
        w[L] -= 1.0 / (HOLD * n)
    return w


def forward_frame(r: pd.DataFrame, cmap: dict, months: pd.PeriodIndex, n: int) -> pd.DataFrame:
    """d_gross, turnover, d_base, d_stress for the forward months on the given cohorts (§6.2, §6.3, §6.5).

    The first month's trade is measured from the weights of the month before it (the history's
    2026-08 weights for 2026-09), as if the rule ran straight through (§11)."""
    cols = list(r.columns)
    w_prev = weights(cmap, months[0] - 1, cols, n)
    rows = []
    for t in months:
        if t not in r.index:
            raise SystemExit(f"STOP: the release has no row for {t}")
        rt = r.loc[t]
        w_t = weights(cmap, t, cols, n)
        contrib, empty = [], 0
        for j in range(1, HOLD + 1):
            W, L = cmap[t - j]
            rw, rl = rt[W].dropna(), rt[L].dropna()
            if rw.empty or rl.empty:
                empty += int(rw.empty) + int(rl.empty)
                contrib.append(0.0)  # §6.5
                continue
            contrib.append(rw.mean() - rl.mean())
        d = float(np.mean(contrib))
        turnover = float((w_t - w_prev).abs().sum())
        rows.append({"month": t, "d_gross": d, "turnover": turnover, "d_base": d - COST_BASE * turnover,
                     "d_stress": d - COST_STRESS * turnover, "empty_legs": empty})
        w_prev = w_t
    out = pd.DataFrame(rows).set_index("month")
    out.index = pd.PeriodIndex(out.index, freq="M")
    return out


def _release_ind(release: str, raw_root: Path, releases_dir: Path) -> dict[int, pd.DataFrame]:
    man = releases_dir / f"{release}.json"
    if not man.exists():
        raise SystemExit(f"STOP: release {release} is not archived in {releases_dir.name}/")
    ind = load_industries(raw_root / release, man)  # checks every zip against its SHA-256
    if zip_releases(raw_root / release) != {release} or release_of(man) != release:
        raise SystemExit(f"STOP: the archived files do not all name {release}")
    return ind


def interim(pos: pd.DataFrame, raw_root: Path = FORWARD_RAW, releases_dir: Path = RELEASES,
            hist: dict | None = None, now_utc: str | None = None) -> dict:
    """Counts, mean and summed d so far at base costs; no t-statistic and no verdict before the 60th month."""
    hist = hist or history_cohorts()
    rels = archived(releases_dir)
    latest = max(rels, default=None)
    out = {"heading": NOT_YET_SCORED, "label": LABEL, "written_at_utc": now_utc or _utc_now(),
           "scored_after": f"{SCORED_MONTHS} holding months ({FIRST_FORWARD_MONTH} to "
                           f"{pd.Period(FIRST_FORWARD_MONTH, 'M') + SCORED_MONTHS - 1})",
           "latest_archived_release": latest, "trials": {}}
    ind = _release_ind(latest, raw_root, releases_dir) if latest else None
    for t, spec in TRIALS.items():
        recorded = sorted(pos.loc[pos["trial"] == t, "month"].unique())
        row = {"months_recorded": len(recorded), "months_with_return": 0, "mean_d_pct_a_year": None,
               "sum_d_pct": None}
        if ind is not None and recorded:
            r = ind[spec["set"]]
            months = pd.period_range(FIRST_FORWARD_MONTH, recorded[-1], freq="M")
            months = months[months <= r.index[-1]]
            if len(months) and set(str(m) for m in months) <= set(recorded):
                fr = forward_frame(r, cohort_map(pos, t, hist[t]), months, spec["n"])
                row.update(months_with_return=int(len(fr)), mean_d_pct_a_year=float(fr["d_base"].mean() * 12),
                           sum_d_pct=float(fr["d_base"].sum()))
        out["trials"][t] = row
    out["months_to_scoring"] = max(0, SCORED_MONTHS - out["trials"]["M1"]["months_with_return"])
    return out


def vintage_row(ind_score: dict, ind_snap: dict, pos: pd.DataFrame, months: pd.PeriodIndex,
                hist: dict | None = None) -> dict:
    """The scoring release against the snapshot over the history's months, and the cohorts recomputed beside the committed."""
    h_end = pd.Period(H_END, "M")
    per = {}
    for n in FILES:
        a, b = ind_snap[n], ind_score[n]
        a = a[a.index <= h_end]
        b = b[b.index <= h_end].reindex(index=a.index, columns=a.columns)
        both = a.notna() & b.notna()
        diff = (b - a).where(both).stack()
        per[str(n)] = {"cells_compared": int(both.to_numpy().sum()),
                       "cells_only_in_one": int((a.notna() ^ b.notna()).to_numpy().sum()),
                       "cells_differing": int((diff.abs() > 1e-9).sum()),
                       "max_abs_change_pct": float(diff.abs().max()) if len(diff) else 0.0}
    spec = TRIALS["M1"]
    o = {}
    for name, ind in (("snapshot", ind_snap), ("scoring_release", ind_score)):
        f = run(ind[spec["set"]][ind[spec["set"]].index <= h_end], spec["F"], spec["n"], pd.Period(spec["first"], "M"))
        d = f["d_base"]
        d = d[(d.index <= pd.Period(I1_END, "M")) | (d.index >= pd.Period(I2_START, "M"))]
        o[name] = float(d.mean() * 12)
    recomputed = []
    for m in months:
        again = {x["trial"]: x for x in cohorts_for(ind_score, str(m))}
        for r in pos[pos["month"] == str(m)].itertuples(index=False):
            x = again[r.trial]
            recomputed.append({"month": r.month, "trial": r.trial, "same": bool(
                x["winners"] == r.winners and x["losers"] == r.losers)})
    differ = [x for x in recomputed if not x["same"]]
    hist_differ = check_history_cohorts(ind_score, hist) if hist is not None else None
    return {"history_cohorts_compared": len(history_ranks_used()) * len(TRIALS) if hist is not None else 0,
            "history_cohorts_differing": hist_differ,
            "per_file_over_history": per, "M1_mean_d_over_O_pct_a_year": o,
            "cohort_rows_compared": len(recomputed), "cohort_rows_differing": len(differ),
            "cohorts_differing": [[x["month"], x["trial"]] for x in differ]}


def forward_verdict(d: dict, dsr: float, stress_mean_d: float) -> dict:
    """§11: §9.5's C1–C4 on the 60 months; C2 and C4 decide, C1 and C3 are reported; a low-power check."""
    c = {"C1_reported": bool(d["sharpe_annual"] >= C1_SHARPE),
         "C2": bool(d["nw_t"] >= C2_T),
         "C3_reported": bool(dsr >= C3_DSR),
         "C4": bool(np.sign(stress_mean_d) == np.sign(d["mean_pct_a_year"]))}
    row = "meets C2 and C4" if c["C2"] and c["C4"] else "does not meet C2 and C4"
    return {**c, "row": f"{row} ({LABEL})"}


def own_release_loader(raw_root: Path = FORWARD_RAW, releases_dir: Path = RELEASES,
                       snapshot_raw: Path = SNAPSHOT_RAW, snapshot_manifest: Path = SNAPSHOT_MANIFEST):
    """month t -> (industries, release, files_sha256) of the release a row for t must come from (release t − 1)."""
    cache: dict[str, tuple] = {}

    def load(month: str) -> tuple:
        want = (pd.Period(month, "M") - 1).strftime("%Y%m")
        if want not in cache:
            if want == release_of(snapshot_manifest):
                cache[want] = (load_industries(snapshot_raw, snapshot_manifest), want, files_sha256(snapshot_manifest))
            else:
                cache[want] = (_release_ind(want, raw_root, releases_dir), want,
                               files_sha256(releases_dir / f"{want}.json"))
        return cache[want]
    return load


def check_rows(pos: pd.DataFrame, commit_times: dict, own_release) -> list[str]:
    """Each scored row equals its first commit and is reproduced from its own release.

    Winners, losers and ties must match exactly and each formation return to 1e-12 relative.  If a
    release's raw files are no longer on disk, its months are returned as not re-checked (listed in
    score.json); the rows themselves are still held to their first commit."""
    not_rechecked = []
    for r in pos.to_dict("records"):
        key = (r["month"], r["trial"])
        if key not in commit_times:
            raise SystemExit(f"STOP: {key} is not in any commit; every scored row must be committed first")
        first = commit_times[key]["row"]
        if any(str(r[c]) != first[c] for c in first):
            raise SystemExit(f"STOP: {key} differs from its first commit; a record is never replaced (§11)")
    for month in sorted(pos["month"].unique()):
        try:
            ind, release, sha = own_release(month)
        except FileNotFoundError:
            not_rechecked.append(month)
            continue
        mine = pos[pos["month"] == month]
        if set(mine["release"]) != {release} or set(mine["files_sha256"]) != {sha}:
            raise SystemExit(f"STOP: {month}'s rows do not name release {release} and its files' SHA-256")
        again = {x["trial"]: x for x in cohorts_for(ind, month)}
        for r in mine.itertuples(index=False):
            x = again[r.trial]
            same = (x["winners"] == r.winners and x["losers"] == r.losers
                    and int(r.boundary_ties) == int(x["boundary_ties"]))
            a = dict(kv.split("=", 1) for kv in r.formation_returns.split(";"))
            b = dict(kv.split("=", 1) for kv in x["formation_returns"].split(";"))
            same = same and a.keys() == b.keys() and all(
                abs(float(a[k]) - float(b[k])) <= 1e-12 * max(1.0, abs(float(b[k]))) for k in b)
            if not same:
                raise SystemExit(f"STOP: {month} {r.trial} is not reproduced from release {release}")
    return not_rechecked


def scoring_release(months: pd.PeriodIndex, releases: dict[str, dict]) -> str:
    """The first archived release that contains the 60th month: fixed by the archive, not chosen."""
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
    """NaN and infinities become null, so score.json is strict JSON."""
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
          snapshot_manifest: Path = SNAPSHOT_MANIFEST, hist: dict | None = None,
          out: Path = SCORE_JSON, now_utc: str | None = None, own_release=None) -> dict:
    """Score the 60 holding months once, from the first archived release that contains them (§11)."""
    if out.exists() or _ever_committed(out):
        raise SystemExit(f"STOP: {out.name} exists or was committed before; the forward record is scored once (§11)")
    hist = hist or history_cohorts()
    months = pd.period_range(FIRST_FORWARD_MONTH, periods=SCORED_MONTHS, freq="M")
    want = {(str(m), t) for m in months for t in TRIALS}
    have = set(zip(pos["month"], pos["trial"]))
    if not want <= have:
        raise SystemExit(f"STOP: {len(want - have)} of the 60 months' rows are not recorded")
    pos = pos[[k in want for k in zip(pos["month"], pos["trial"])]].reset_index(drop=True)
    first = scoring_release(months, archived(releases_dir))
    if release != first:
        raise SystemExit(f"STOP: the scoring release is {first}, the first archived release containing {months[-1]}")
    not_rechecked = check_rows(pos, commit_times, own_release or own_release_loader(raw_root, releases_dir,
                                                                                   snapshot_raw, snapshot_manifest))
    ind = _release_ind(release, raw_root, releases_dir)
    if any(f.index[-1] < months[-1] for f in ind.values()):
        raise SystemExit(f"STOP: release {release} does not contain {months[-1]} in every file")
    if not all((snapshot_raw / name).exists() for name in _names()):
        raise SystemExit("STOP: the snapshot's raw files are needed for the vintage row (§11)")
    ind_snap = load_industries(snapshot_raw, snapshot_manifest)
    bad = check_history_cohorts(ind_snap, hist)
    if bad:
        raise SystemExit(f"STOP: cohorts.json differs from the snapshot's cohorts at {bad}; the history file was edited")
    late = late_flags(pos, commit_times, archived(releases_dir))
    frames = {t: forward_frame(ind[s["set"]], cohort_map(pos, t, hist[t]), months, s["n"]) for t, s in TRIALS.items()}
    var, floored = stats.trial_variance([stats.sharpe_monthly(frames[t]["d_base"] / 100) for t in TRIALS])
    trials = {}
    for t, fr in frames.items():
        x = fr["d_base"] / 100
        d = diff_row(fr["d_base"])
        dsr = stats.deflated_sharpe(stats.sharpe_monthly(x), len(x), stats.skewness(x), stats.kurtosis(x),
                                    N_FAMILY, var)
        stress = float(fr["d_stress"].mean() * 12)
        sel = pos["trial"] == t
        trials[t] = {"d": d, "dsr": dsr, "stress_mean_d_pct_a_year": stress,
                     "turnover_per_year": float(fr["turnover"].mean() * 12),
                     "months_with_empty_legs": int((fr["empty_legs"] > 0).sum()),
                     "verdict": forward_verdict(d, dsr["dsr"], stress),
                     "rows_late": int(late[sel].sum()), "rows": int(sel.sum()),
                     "late_months": [r.month for r in pos[sel & late].itertuples(index=False)]}
    result = {"release": release, "months": [str(months[0]), str(months[-1])], "label": LABEL,
              "scored_at_utc": now_utc or _utc_now(), "N_family": N_FAMILY,
              "variance_across_trials": var, "floor_applied": floored, "trials": trials,
              "headline": f"M1: {trials['M1']['verdict']['row']}",
              "months_not_rechecked_raw_files_missing": not_rechecked,
              "vintage": vintage_row(ind, ind_snap, pos, months, hist)}
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
    p = argparse.ArgumentParser(prog="python -m src.forward011")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record", help="append one forward month's cohorts")
    r.add_argument("--month", required=True)
    r.add_argument("--raw-dir", type=Path, default=SNAPSHOT_RAW)
    r.add_argument("--manifest", type=Path, default=SNAPSHOT_MANIFEST)
    sub.add_parser("fetch", help="download the two files once; keep them only if they name a new release")
    sub.add_parser("interim", help="write paper-log/interim.json (no t-statistic, no verdict)")
    s = sub.add_parser("score", help="score the 60 holding months once, from one archived release")
    s.add_argument("--release", required=True)
    a = p.parse_args(argv)
    if a.cmd == "fetch":
        print(json.dumps(fetch(), indent=2))
        return 0
    if a.cmd == "interim":
        payload = interim(read_cohorts())
        INTERIM_JSON.write_text(json.dumps(_clean(payload), indent=2, allow_nan=False) + "\n")
        print(json.dumps(payload, indent=2))
        return 0
    if a.cmd == "score":
        res = score(a.release, read_cohorts(), row_commit_times())
        print(res["headline"])
        return 0
    if a.cmd == "record":
        rows = record(a.month, a.raw_dir, a.manifest)
        print(json.dumps([{k: v for k, v in x.items() if k in ("month", "trial", "winners", "losers",
                                                               "boundary_ties", "release")} for x in rows],
                         indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
