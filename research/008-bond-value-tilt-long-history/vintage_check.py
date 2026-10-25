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

Cache (added at the second attempt, trial log 2026-10-25 18:2x GMT): every
ALFRED response is written as it arrives to the git-ignored ``data/raw/alfred/``
(``<SERIES>_<date>.csv`` for HTTP 200, an empty ``<SERIES>_<date>.404`` for
HTTP 404, meaning ALFRED holds no vintage of that series at that date), with
one line per request in ``fetch_log.jsonl``; a stopped run resumes from the
cache. Requests run on ``WORKERS`` threads with up to ``RETRIES`` tries for a
timeout or a 5xx. The analysis runs only once every request is resolved (200
or 404), unless ``--accept-unread`` is given, in which case unresolved months
take §6.1's "assumed known" branch and are counted. Per-file SHA-256 in
``results/alfred_cache_manifest.csv``.

Outputs: ``results/cpi_availability.csv`` (dates and flags only: the months k
and k - 12 each trial's real yield will use), ``results/vintage_check.{json,md}``
(counts and the size of any departure). No inflation rate, real yield, rank or
weight is computed; index levels are read only to form the ratios above, and
no level is written.

Usage: ../../.venv/bin/python vintage_check.py [--accept-unread]   (from this folder)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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
CACHE = HERE / "data" / "raw" / "alfred"
WORKERS = 4
RETRIES = 3
_LOG_LOCK = threading.Lock()


def cache_paths(series_id: str, date: str) -> tuple[Path, Path]:
    return CACHE / f"{series_id}_{date}.csv", CACHE / f"{series_id}_{date}.404"


def fetch_one(series_id: str, date: str) -> str:
    """Fill the cache for one (series, date); return '200', '404' or the last error name."""
    ok, missing = cache_paths(series_id, date)
    if ok.exists():
        return "200"
    if missing.exists():
        return "404"
    session = requests.Session()
    outcome = "unknown"
    for attempt in range(1, RETRIES + 1):
        try:
            r = session.get(URL.format(series_id=series_id, date=date), timeout=TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            outcome = type(exc).__name__
        else:
            if r.status_code == 200:
                parse(r.text)  # header check before anything is cached
                tmp = ok.with_suffix(".part")
                tmp.write_bytes(r.content)
                tmp.replace(ok)
                outcome = "200"
            elif r.status_code == 404:
                missing.write_bytes(b"")
                outcome = "404"
            else:
                outcome = f"HTTP{r.status_code}"
        with _LOG_LOCK, (CACHE / "fetch_log.jsonl").open("a") as f:
            f.write(json.dumps({"series": series_id, "vintage_date": date, "attempt": attempt, "outcome": outcome,
                                "utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}) + "\n")
        if outcome in ("200", "404"):
            return outcome
        time.sleep(PAUSE_SECONDS * 10 * attempt)
    return outcome


def fill_cache(dates: list[tuple[str, str]]) -> dict[tuple[str, str], str]:
    CACHE.mkdir(parents=True, exist_ok=True)
    jobs = [(s, t) for s in SERIES for _, t in dates]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        outcomes = list(pool.map(lambda j: fetch_one(*j), jobs))
    return dict(zip(jobs, outcomes))


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--accept-unread", action="store_true")
    args = ap.parse_args()
    dates = signal_dates()
    started = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    outcomes = fill_cache(dates)
    unresolved = {k: v for k, v in outcomes.items() if v not in ("200", "404")}
    print(f"cache: {sum(v == '200' for v in outcomes.values())} vintages, "
          f"{sum(v == '404' for v in outcomes.values())} not held (404), {len(unresolved)} unresolved")
    if unresolved and not args.accept_unread:
        print("unresolved requests remain; re-run to resume (nothing written to results/)")
        sys.exit(2)
    out_rows: dict[str, dict] = {m: {"signal_month": m, "signal_date": t} for m, t in dates}
    summary: dict = {"started_utc": started, "url_form": URL, "series": {}}
    for series_id in SERIES:
        current = parse((HERE / "data" / "raw" / f"fred_{series_id}.csv").read_text(encoding="utf-8"))
        unread, late, revisions = [], [], {}
        digest = hashlib.sha256()
        for m, t in dates:
            m1 = month_str(month_index(m) - 1)
            ok, _ = cache_paths(series_id, t)
            vintage = {}
            if outcomes[(series_id, t)] == "200":
                raw = ok.read_bytes()
                digest.update(raw)
                vintage = parse(raw.decode("utf-8"))
            if not any(x <= m1 for x in vintage):
                reason = outcomes[(series_id, t)]
                unread.append({"signal_month": m, "error": "no_month_at_or_before_m1" if reason == "200" else reason})
                out_rows[m][f"{series_id}_m1_published_by_t"] = ""
                out_rows[m][f"{series_id}_k"] = m1
                out_rows[m][f"{series_id}_branch"] = "assumed_known"
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
    with (res / "alfred_cache_manifest.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "vintage_date", "outcome", "file", "bytes", "sha256"])
        for (series_id, t), o in sorted(outcomes.items()):
            ok, missing = cache_paths(series_id, t)
            path = ok if o == "200" else missing if o == "404" else None
            data = path.read_bytes() if path else b""
            w.writerow([series_id, t, o, path.name if path else "", len(data),
                        hashlib.sha256(data).hexdigest() if path else ""])
    summary["cache"] = {"dir": "data/raw/alfred (git-ignored)", "workers": WORKERS, "retries": RETRIES,
                        "unresolved_accepted": sorted(f"{s}@{t}" for s, t in unresolved)}
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
