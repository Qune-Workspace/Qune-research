"""Scheduled FOMC statement dates and stated release times, 2016-01..2026-09, from the Fed's own pages.

Written 2026-10-27 from 22:2xZ by the clock for checks 2 and 3 of the RESEARCH_AGENDA addition that
queued Study 012 (pre-FOMC drift, 2pm-to-2pm, labelled replication). Reads public web pages only; no
market data, no return. Rules:
- Meetings: the yearly pages fomchistorical2016..2020.htm and the current fomccalendars.htm (2021-2026).
  A meeting row's statement is its link ``pressreleases/monetaryYYYYMMDDa.htm``; rows marked
  "unscheduled", "cancelled", "notation vote" or "conference call" are excluded; dates after 2026-09-30
  are excluded.
- Release time: the statement page's own "For release at ..." line, as stated (an embargo time, not an
  observed timestamp).

Run from the repository root (network needed):
``python tools/fomc_calendar.py > tools/fomc_calendar.txt``; it also rewrites
``tools/fomc_statement_dates_2016_2026-09.txt``.

Source check (2026-11-18 00:15Z, ``tools/fomc_calendar_source_check.md``): ``python tools/fomc_calendar.py
--check [--pages DIR]`` re-reads the pages (from ``DIR`` when given, else the network), prints each page's
size and SHA-256, compares the dates they give under the rule above with the committed file, lists the rows
the cut-off excludes (later statements, and the scheduled rows that have no statement yet, which the Fed
marks tentative), writes nothing and exits 1 on any difference.  The committed file is an input the bill
reading's records name by hash (``pm-view/fomc_calibrate.meetings_record``), so it is checked, never rewritten
in passing.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import re
import sys
import time
import urllib.request

BASE = "https://www.federalreserve.gov"
UA = {"User-Agent": "Mozilla/5.0 (Qune Research; public pages only)"}
EXCLUDE = ("unscheduled", "cancelled", "notation", "conference call")
DATES_FILE = "tools/fomc_statement_dates_2016_2026-09.txt"
CUTOFF = "20260930"
PAGES_DIR: str | None = None  # --pages: read saved copies named by the page's basename instead of the network
FETCHED: dict[str, bytes] = {}  # path -> bytes, for the hashes --check prints


def fetch(path: str) -> str:
    if PAGES_DIR is not None:
        with open(f"{PAGES_DIR}/{path.rsplit('/', 1)[-1]}", "rb") as f:
            body = f.read()
    else:
        req = urllib.request.Request(BASE + path, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
    FETCHED[path] = body
    return body.decode("utf-8", "ignore")


def text(s: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", s).split())


def year_blocks(year: int, current: str) -> list[str]:
    if year <= 2020:
        return re.split(r"panel-heading", fetch(f"/monetarypolicy/fomchistorical{year}.htm"))[1:]
    heads = sorted((m.start(), int(m.group(1))) for m in re.finditer(r"(\d{4}) FOMC Meetings", current))
    for k, (pos, y) in enumerate(heads):
        if y == year:
            end = heads[k + 1][0] if k + 1 < len(heads) else len(current)
            return re.split(r'class="(?:fomc-meeting--shaded )?row fomc-meeting"', current[pos:end])[1:]
    raise SystemExit(f"no {year} section on fomccalendars.htm")


def statement_dates() -> list[str]:
    current = fetch("/monetarypolicy/fomccalendars.htm")
    out: list[str] = []
    for year in range(2016, 2027):
        for block in year_blocks(year, current):
            links = sorted(set(re.findall(r"pressreleases/monetary(\d{8})a\.htm", block)))
            head = text(block[:600]).lower()
            if not links or any(w in head for w in EXCLUDE):
                continue
            d = links[-1] if year >= 2021 else links[0]
            if d <= CUTOFF:
                out.append(d)
        if PAGES_DIR is None:
            time.sleep(0.3)
    return sorted(out)


def rows_beyond_cutoff(current: str) -> list[str]:
    """The rows of fomccalendars.htm the cut-off leaves out, as text: the statements dated after CUTOFF and
    every scheduled row without a statement link (the Fed marks those tentative until the meeting before)."""
    years = sorted({int(m.group(1)) for m in re.finditer(r"(\d{4}) FOMC Meetings", current)})
    out: list[str] = []
    for year in years:
        if year < int(CUTOFF[:4]):
            continue
        for block in year_blocks(year, current):
            links = sorted(set(re.findall(r"pressreleases/monetary(\d{8})a\.htm", block)))
            head = text(block[:400])
            head = head.split(" Statement")[0] if " Statement" in head else head.split(" <")[0]
            head = re.sub(r'^"?>\s*', "", head)[:80]
            if links and links[-1] > CUTOFF:
                out.append(f"{year}: {head} -> statement {links[-1]}")
            elif not links:
                out.append(f"{year}: {head} -> no statement yet (scheduled)")
    return out


def release_time(d: str) -> str:
    t = text(fetch(f"/newsevents/pressreleases/monetary{d}a.htm"))
    m = re.search(r"For release at ([0-9:]+\s*[ap]\.?\s*m\.?\s*[A-Z]{2,3})", t, re.I)
    return m.group(1) if m else "NOT FOUND"


def committed_dates(path: str = DATES_FILE) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]


def check() -> int:
    fresh = statement_dates()
    have = committed_dates()
    print(f"source check of {DATES_FILE} against the Fed's pages ({'saved copies in ' + PAGES_DIR if PAGES_DIR else 'network'})")
    for path, body in FETCHED.items():
        print(f"  {path}: {len(body)} bytes, sha256 {hashlib.sha256(body).hexdigest()}")
    print(f"pages give N = {len(fresh)}, per year {dict(sorted(collections.Counter(d[:4] for d in fresh).items()))}; file N = {len(have)}")
    only_pages, only_file = sorted(set(fresh) - set(have)), sorted(set(have) - set(fresh))
    print(f"only on the pages: {only_pages or 'none'}; only in the file: {only_file or 'none'}; "
          f"same dates in the same order: {fresh == have}")
    print(f"rows beyond the cut-off {CUTOFF} (not in the file by rule):")
    for line in rows_beyond_cutoff(FETCHED["/monetarypolicy/fomccalendars.htm"].decode("utf-8", "ignore")):
        print(f"  {line}")
    if fresh != have:
        print("DIFFERENCE: the committed file does not match the pages under the rule; nothing rewritten")
        return 1
    print("pass: the committed file matches the pages under the rule; nothing written")
    return 0


def main(argv: list[str] | None = None) -> int:
    global PAGES_DIR
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="compare the pages with the committed file; write nothing")
    ap.add_argument("--pages", default=None, metavar="DIR", help="read saved page copies from DIR (basename of each page) instead of the network")
    a = ap.parse_args(argv)
    PAGES_DIR = a.pages
    if a.check:
        return check()
    dates = statement_dates()
    with open(DATES_FILE, "w") as f:
        f.write(f"# Scheduled FOMC meetings held 2016-01..2026-09: statement release date (YYYYMMDD), one a line, N = {len(dates)}.\n")
        f.write("# Source: federalreserve.gov fomchistorical2016..2020.htm and fomccalendars.htm (2021-2026), read 2026-10-27 22:2xZ.\n")
        f.write("# Rule: the statement link monetaryYYYYMMDDa.htm in each meeting row; rows marked unscheduled, cancelled or notation vote excluded.\n")
        f.write("\n".join(dates) + "\n")
    print("Scheduled FOMC statements 2016-01..2026-09: dates and stated release times (Fed pages)")
    print(f"N = {len(dates)}; per year: {dict(sorted(collections.Counter(d[:4] for d in dates).items()))}")
    times = {}
    for d in dates:
        times[d] = release_time(d)
        time.sleep(0.3)
    print(f"stated release times: {dict(collections.Counter(times.values()))}")
    for d in dates:
        print(f"{d} {times[d]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
