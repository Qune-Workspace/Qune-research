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
"""

from __future__ import annotations

import collections
import re
import time
import urllib.request

BASE = "https://www.federalreserve.gov"
UA = {"User-Agent": "Mozilla/5.0 (Qune Research; public pages only)"}
EXCLUDE = ("unscheduled", "cancelled", "notation", "conference call")
DATES_FILE = "tools/fomc_statement_dates_2016_2026-09.txt"


def fetch(path: str) -> str:
    req = urllib.request.Request(BASE + path, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


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
            if d <= "20260930":
                out.append(d)
        time.sleep(0.3)
    return sorted(out)


def release_time(d: str) -> str:
    t = text(fetch(f"/newsevents/pressreleases/monetary{d}a.htm"))
    m = re.search(r"For release at ([0-9:]+\s*[ap]\.?\s*m\.?\s*[A-Z]{2,3})", t, re.I)
    return m.group(1) if m else "NOT FOUND"


def main() -> None:
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


if __name__ == "__main__":
    main()
