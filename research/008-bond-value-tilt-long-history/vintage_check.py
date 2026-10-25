"""Study 008, §14 step 2 (second part): the CPI vintage and release-date check of §5.1.

For each series (``CPIAUCNS``, ``CPILFENS``) and each signal month m of Study
001's execution calendar, one ALFRED vintage is read, dated on the signal date
t (``alfredgraph.csv?id=<SERIES>&vintage_date=<t>``, keyless):

* **Release (§5.1 (b), §6.1):** whether the index for month m - 1 is in the
  vintage of t, i.e. had been published by t. If it is, k = m - 1; if not, k
  is the latest month in that vintage (normally m - 2), and the month is
  listed. If the vintage cannot be read, the month takes §6.1's "assumed
  known" branch (k = m - 1) and is counted as such. ALFRED's vintage dates are
  taken as the publication dates; they are not checked against BLS's release
  archives.
* **Revisions (§5.1 (a)):** for the December signal date of each year
  1995-2018, that vintage's index is compared month by month with the current
  file. Because the index was re-based (1967 = 100 to 1982-84 = 100) and older
  vintages carry fewer decimals, the comparison is on the ratio current /
  vintage: a pure re-basing gives one constant ratio; a revision shows as a
  month whose ratio departs from the vintage's median ratio by more than the
  two files' rounding (0.05 / vintage value + 0.0005 / current value).

Outputs: ``results/cpi_availability.csv`` (dates and flags only: the months k
and k - 12 each trial's real yield will use), ``results/vintage_check.{json,md}``
(counts and the size of any departure). No inflation rate, real yield, rank or
weight is computed; index levels are read only to form the ratios above, and
no level is written.

Usage: ../../.venv/bin/python vintage_check.py   (from this folder)
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
CALENDAR = RESEARCH / "001-slope-duration-switch" / "results" / "execution_calendar.csv"
SERIES = ("CPIAUCNS", "CPILFENS")
URL = "https://alfred.stlouisfed.org/graph/alfredgraph.csv?id={series_id}&vintage_date={date}"
MISSING_TOKENS = ("", ".", "NaN", "nan", "NA")
REVISION_YEARS = range(1995, 2019)  # §5.1 (a)
TEST_SIGNAL_MONTHS = ("1974-06", "2018-11")  # data step: the test window's signal months
PAUSE_SECONDS = 0.2
TIMEOUT_SECONDS = 60


def month_index(month: str) -> int:
    return int(month[:4]) * 12 + int(month[5:7]) - 1


def month_str(index: int) -> str:
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def parse(text: str) -> dict[str, str]:
    """Month -> value string, non-empty values only."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or len(rows[0]) != 2 or rows[0][0] != "observation_date":
        raise ValueError(f"unexpected header {rows[0] if rows else None}")
    return {r[0][:7]: r[1].strip() for r in rows[1:] if r and r[1].strip() not in MISSING_TOKENS}


def signal_dates() -> list[tuple[str, str]]:
    with CALENDAR.open(newline="") as f:
        rows = list(csv.DictReader(f))
    seen: dict[str, str] = {}
    for r in rows:
        seen.setdefault(r["month"], r["signal_date"])  # 2018-12 is listed twice with the same signal date
    return list(seen.items())


def revision_stats(current: dict[str, str], vintage: dict[str, str]) -> dict:
    common = sorted(set(current) & set(vintage))
    ratios = {m: float(current[m]) / float(vintage[m]) for m in common}
    med = statistics.median(ratios.values())
    departures = []
    for m in common:
        tol = 0.05 / float(vintage[m]) + 0.0005 / float(current[m])
        dev = abs(ratios[m] / med - 1.0)
        if dev > tol:
            departures.append({"month": m, "relative_departure": dev, "tolerance": tol})
    return {
        "months_compared": len(common),
        "median_ratio_current_over_vintage": med,
        "months_beyond_rounding": len(departures),
        "largest_relative_departure": max((abs(r / med - 1.0) for r in ratios.values()), default=0.0),
        "departures": departures[:20],
    }


def main() -> None:
    dates = signal_dates()
    started = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    session = requests.Session()
    out_rows: dict[str, dict] = {m: {"signal_month": m, "signal_date": t} for m, t in dates}
    summary: dict = {"started_utc": started, "url_form": URL, "series": {}}
    for series_id in SERIES:
        current = parse((HERE / "data" / "raw" / f"fred_{series_id}.csv").read_text(encoding="utf-8"))
        unread, late, revisions = [], [], {}
        digest = hashlib.sha256()
        for m, t in dates:
            m1 = month_str(month_index(m) - 1)
            try:
                r = session.get(URL.format(series_id=series_id, date=t), timeout=TIMEOUT_SECONDS)
                r.raise_for_status()
                vintage = parse(r.text)
                digest.update(r.content)
            except (requests.RequestException, ValueError) as exc:
                unread.append({"signal_month": m, "error": type(exc).__name__})
                out_rows[m][f"{series_id}_m1_published_by_t"] = ""
                out_rows[m][f"{series_id}_k"] = m1
                out_rows[m][f"{series_id}_branch"] = "assumed_known"
                time.sleep(PAUSE_SECONDS)
                continue
            published = m1 in vintage
            k = m1 if published else max(x for x in vintage if x <= m1)
            if not published:
                late.append({"signal_month": m, "signal_date": t, "k_used": k})
            out_rows[m][f"{series_id}_m1_published_by_t"] = "1" if published else "0"
            out_rows[m][f"{series_id}_k"] = k
            out_rows[m][f"{series_id}_branch"] = "release_date_read"
            if m[5:7] == "12" and int(m[:4]) in REVISION_YEARS:
                revisions[m] = revision_stats(current, vintage)
            time.sleep(PAUSE_SECONDS)
        in_test = [x for x in late if TEST_SIGNAL_MONTHS[0] <= x["signal_month"] <= TEST_SIGNAL_MONTHS[1]]
        summary["series"][series_id] = {
            "signal_months": len(dates),
            "vintages_read": len(dates) - len(unread),
            "vintages_unread": unread,
            "m1_not_published_by_t": late,
            "m1_not_published_by_t_in_test_window": len(in_test),
            "m1_not_published_by_t_before_test_window": len([x for x in late if x["signal_month"] < TEST_SIGNAL_MONTHS[0]]),
            "m1_not_published_by_t_after_test_window": len([x for x in late if x["signal_month"] > TEST_SIGNAL_MONTHS[1]]),
            "sha256_of_all_vintage_responses": digest.hexdigest(),
            "revision_check": revisions,
            "revision_years_with_any_month_beyond_rounding": sorted(
                y for y, v in revisions.items() if v["months_beyond_rounding"] > 0
            ),
        }
    summary["finished_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    res = HERE / "results"
    fields = ["signal_month", "signal_date"] + [f"{s}_{c}" for s in SERIES for c in ("m1_published_by_t", "k", "branch")]
    with (res / "cpi_availability.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for m, _ in dates:
            w.writerow(out_rows[m])
    (res / "vintage_check.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [
        "# Study 008 CPI vintage and release-date check (§5.1, §6.1)",
        "",
        f"Run {started} to {summary['finished_utc']}. One ALFRED vintage per series per signal month, dated on the "
        "signal date (keyless `alfredgraph.csv`). Dates, flags and ratios only; no inflation rate or real yield.",
        "",
    ]
    for series_id, s in summary["series"].items():
        yrs = s["revision_years_with_any_month_beyond_rounding"]
        worst = max((v["largest_relative_departure"] for v in s["revision_check"].values()), default=0.0)
        lines += [
            f"## `{series_id}`",
            "",
            f"- Vintages read: {s['vintages_read']} of {s['signal_months']} signal months; unread: "
            f"{[u['signal_month'] for u in s['vintages_unread']] or 'none'}.",
            f"- Index for m − 1 **not yet published** at the signal date: {len(s['m1_not_published_by_t'])} months "
            f"({s['m1_not_published_by_t_before_test_window']} before the test window, "
            f"**{s['m1_not_published_by_t_in_test_window']} in it**, {s['m1_not_published_by_t_after_test_window']} after): "
            + (", ".join(f"{x['signal_month']} (k = {x['k_used']})" for x in s["m1_not_published_by_t"]) or "none")
            + ".",
            f"- Revisions, December vintages 1995–2018: {len(s['revision_check'])} compared; years with any month "
            f"beyond rounding: {yrs or 'none'}; largest relative departure from the vintage's median ratio "
            f"{worst:.2e}.",
            "",
        ]
    (res / "vintage_check.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
