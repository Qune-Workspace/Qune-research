"""Study 013 daily snapshot collector: the open-market listing of Polymarket,
once a day, hashed page by page, rows kept out of the tree.

Why it exists (QUESTION.md §3.2, 2026-11-02): the study's price p is the
YES-token price at a fixed horizon h before a market's venue resolution time,
read from the desk's daily snapshot of the open-market listing, never fetched
after the fact.  A market with no snapshot at the horizon is not in the sample
and is counted.  Nothing is backfilled: a day this collector did not run stays
a gap in `paper-log/snapshots.csv`, and the data step reports the gap.

What it fetches: the Gamma API's keyset listing of open markets
(`/markets/keyset?closed=false`, cursor pagination, 100 rows a page, the page
cap observed on 2026-11-02; `include_tag=true` for the tag labels), public, no
key, no wallet, read-only, inside the documented rate limits (300 requests per
10 s on /markets).  The venue caches the listing for up to five minutes
(`cache-control: public, max-age=300`, observed 2026-11-02 06:19Z); the
snapshot of record is what the venue served, with its hash.

What it keeps (git-ignored under `data/raw/snapshots/<UTC date>/`):
  - `records.jsonl`: one line per market with a whitelist of fields
    (identifiers, the two outcome token ids, the outcome labels, the listing's
    prices `bestBid`, `bestAsk`, `lastTradePrice`, `spread`, `outcomePrices`,
    liquidity and volume, dates, status flags, resolution mechanism, parent
    event ids and tag labels).  The question text, description, slug, group
    title, images, resolution source and the `resolvedBy` address are never
    written: the author of the pre-registration sees no wording.  On an open
    market `outcomePrices` is the listing's mid price per outcome, not an
    outcome; the pre-registration fixes which price field is p.
  - `pages.jsonl`: one line per page fetched (page number, rows, bytes,
    SHA-256 of the response body, fetch time).
A snapshot is written to a `.tmp` folder and renamed into place only when the
last page has been read, so a killed run leaves no half snapshot that a later
step could mistake for a complete one.  One snapshot a day: a second run on
the same UTC date refuses (exit 2) and writes nothing.

What it commits (the caller commits; this script only appends): one line per
complete snapshot in `paper-log/snapshots.csv` (UTC date, start and end time,
pages, rows, distinct markets, bytes, SHA-256 of `records.jsonl` and of
`pages.jsonl`).  The file is append-only: an existing line is never rewritten.
No raw field name appears in it (Polymarket's verdict is `derived`,
tools/pm_data_terms.md; tools/check_data_terms.py holds the tree to it).

Completeness (added 2026-11-05, after the open-market count rose by 23,814
between the first two snapshots): `consistency` compares each logged snapshot
with the one logged before it by market id, reading two fields of a row and
nothing else (`id`, `createdAt`; no price, status, label or outcome field is
decoded into a name).  Per snapshot it counts the markets carried over, the
markets that left the listing, the markets that appeared, how many of those
were created before the previous snapshot started (a market the previous
snapshot could have listed and did not, or one re-opened), and, for the
previous snapshot, how many markets are present both in this snapshot and in
the one before it yet absent from it ("missed at most": an upper bound on
what the previous snapshot failed to list, because a market can also leave
and return).  One line per snapshot date is appended to
`paper-log/consistency.csv` (counts only, never an id); an existing line is
never rewritten.  The rule, fixed before the first live run: a previous
snapshot that missed at most 100 markets or more (one page, the smallest unit
a pagination fault can lose) is a finding to investigate (exit 3, and the due
register lists it); below that the line is information.

Usage (from the study folder, the scheduled job runs it daily):
    .venv/bin/python collector.py snapshot            # fetch today's snapshot
    .venv/bin/python collector.py snapshot --dry-run  # one page, nothing written
    .venv/bin/python collector.py check               # gaps since the first snapshot
    .venv/bin/python collector.py consistency         # id-only comparison of consecutive snapshots
Exit 0 on a complete snapshot (or a check with no gap), 1 on a fetch failure
(nothing counted), 2 when today's snapshot already exists, 3 on gaps or on a
consistency finding at or above the page threshold.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parent
SNAPSHOT_ROOT = STUDY_DIR / "data" / "raw" / "snapshots"
SNAPSHOT_LOG = STUDY_DIR / "paper-log" / "snapshots.csv"

GAMMA_KEYSET = "https://gamma-api.polymarket.com/markets/keyset"
UA = "qune-research/0.1 (public research; daily open-market snapshot; research/013/collector.py)"
PAGE = 100  # the API's page cap, observed 2026-11-02 (a request for 500 returns 100)
PAUSE_S = 0.05  # between pages; well inside 300 requests per 10 s

# Fields copied from each listing row. Wording fields (question, description,
# slug, groupItemTitle, image, icon, resolutionSource) and the resolver
# address (resolvedBy) are deliberately absent.
KEEP = (
    "id",
    "conditionId",
    "questionID",
    "clobTokenIds",
    "outcomes",
    "outcomePrices",
    "bestBid",
    "bestAsk",
    "lastTradePrice",
    "spread",
    "liquidityNum",
    "volumeNum",
    "volume24hr",
    "startDate",
    "endDate",
    "createdAt",
    "updatedAt",
    "closedTime",
    "acceptingOrdersTimestamp",
    "closed",
    "active",
    "acceptingOrders",
    "enableOrderBook",
    "negRisk",
    "restricted",
    "umaResolutionStatus",
    "resolutionMechanism",
    "orderPriceMinTickSize",
    "feesEnabled",
)
NEVER = ("question", "description", "slug", "groupItemTitle", "image", "icon", "resolutionSource", "resolvedBy")

LOG_COLUMNS = (
    "snapshot_date",
    "started_utc",
    "finished_utc",
    "pages",
    "rows",
    "distinct_markets",
    "bytes",
    "records_sha256",
    "pages_sha256",
)

CONSISTENCY_LOG = STUDY_DIR / "paper-log" / "consistency.csv"
CONSISTENCY_COLUMNS = (
    "snapshot_date",
    "previous_date",
    "previous_markets",
    "markets",
    "carried",
    "left",
    "appeared",
    "appeared_created_before_previous_start",
    "previous_missed_at_most",
    "computed_utc",
)
# One page: the smallest unit a pagination fault can lose. Fixed on 2026-11-05 before the first live run.
MISSED_PAGE_THRESHOLD = 100
# The two fields the consistency check reads from a row; nothing else is looked at.
CONSISTENCY_FIELDS = ("id", "createdAt")

# A page fetcher returns (rows, next cursor or None, body hash, body bytes).
Fetcher = Callable[[str | None], tuple[list[dict], str | None, str, int]]


class SnapshotExists(Exception):
    """Today's snapshot folder is already in place."""


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def stamp(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def strip(m: dict) -> dict:
    """The whitelisted copy of a listing row, with parent event ids and tag labels."""
    out = {k: m.get(k) for k in KEEP}
    out["eventIds"] = sorted(str(e.get("id")) for e in (m.get("events") or []) if e.get("id") is not None)
    out["tagLabels"] = sorted(str(t.get("label")) for t in (m.get("tags") or []) if t.get("label"))
    return out


def fetch_page(cursor: str | None) -> tuple[list[dict], str | None, str, int]:
    """One page of the open-market keyset listing (retries on 429 and 5xx)."""
    q = {"closed": "false", "limit": str(PAGE), "include_tag": "true"}
    if cursor:
        q["after_cursor"] = cursor
    url = GAMMA_KEYSET + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    delay = 1.0
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
            page = json.loads(body)
            rows = page.get("markets") or []
            nxt = page.get("next_cursor") or None
            return rows, nxt, hashlib.sha256(body).hexdigest(), len(body)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < 5:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError("unreachable")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_log(log_csv: Path) -> list[dict[str, str]]:
    if not log_csv.exists():
        return []
    with open(log_csv, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_log(log_csv: Path, row: dict[str, str]) -> None:
    """Append one line; never rewrite an existing one. The header is written once."""
    log_csv.parent.mkdir(parents=True, exist_ok=True)
    new = not log_csv.exists() or log_csv.stat().st_size == 0
    with open(log_csv, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLUMNS, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerow({k: row[k] for k in LOG_COLUMNS})


def take_snapshot(
    snapshot_root: Path,
    log_csv: Path,
    fetch: Fetcher,
    now: dt.datetime,
    pause_s: float = PAUSE_S,
    dry_run: bool = False,
) -> dict[str, str]:
    """Fetch every page of the open-market listing into
    ``snapshot_root/<date>/`` and append one line to ``log_csv``.

    Raises SnapshotExists when the day's folder is already in place; any fetch
    error propagates after the `.tmp` folder is removed, so nothing is counted.
    With ``dry_run`` one page is fetched and nothing is written.
    """
    day = now.date().isoformat()
    final = snapshot_root / day
    if final.exists():
        raise SnapshotExists(f"snapshot {day} already exists at {final}")
    if dry_run:
        rows, nxt, digest, nbytes = fetch(None)
        return {
            "snapshot_date": day,
            "rows": str(len(rows)),
            "bytes": str(nbytes),
            "sha256": digest,
            "more": "yes" if nxt else "no",
        }
    tmp = snapshot_root / (day + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    started = stamp(now)
    seen: set[str] = set()
    pages = 0
    rows_total = 0
    nbytes_total = 0
    try:
        with (
            open(tmp / "records.jsonl", "w", encoding="utf-8") as rec,
            open(tmp / "pages.jsonl", "w", encoding="utf-8") as man,
        ):
            cursor: str | None = None
            while True:
                rows, nxt, digest, nbytes = fetch(cursor)
                man.write(
                    json.dumps(
                        {
                            "page": pages,
                            "rows": len(rows),
                            "bytes": nbytes,
                            "sha256": digest,
                            "fetched_utc": stamp(utc_now()),
                        }
                    )
                    + "\n"
                )
                pages += 1
                rows_total += len(rows)
                nbytes_total += nbytes
                for m in rows:
                    mid = str(m.get("id"))
                    if mid in seen:
                        continue
                    seen.add(mid)
                    rec.write(json.dumps(strip(m)) + "\n")
                if len(rows) < PAGE or not nxt:
                    break
                cursor = nxt
                if pause_s:
                    time.sleep(pause_s)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    finished = stamp(utc_now())
    tmp.rename(final)
    row = {
        "snapshot_date": day,
        "started_utc": started,
        "finished_utc": finished,
        "pages": str(pages),
        "rows": str(rows_total),
        "distinct_markets": str(len(seen)),
        "bytes": str(nbytes_total),
        "records_sha256": sha256_file(final / "records.jsonl"),
        "pages_sha256": sha256_file(final / "pages.jsonl"),
    }
    append_log(log_csv, row)
    return row


def gaps(log_csv: Path, today: dt.date) -> list[str]:
    """UTC dates with no complete snapshot between the first logged day and
    ``today`` inclusive. An empty log has no gap (nothing has started)."""
    days = sorted({r["snapshot_date"] for r in read_log(log_csv)})
    if not days:
        return []
    first = dt.date.fromisoformat(days[0])
    have = set(days)
    out = []
    d = first
    while d <= today:
        if d.isoformat() not in have:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def parse_utc(s: str) -> dt.datetime | None:
    """An ISO-8601 time with or without a trailing Z; None when absent or unreadable."""
    if not s:
        return None
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)


def read_ids(records: Path) -> dict[str, str]:
    """Market id -> creation time of every row of a snapshot. The only two
    fields this check reads; the rest of each row is decoded and dropped."""
    out: dict[str, str] = {}
    with open(records, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            out[str(r.get(CONSISTENCY_FIELDS[0]))] = str(r.get(CONSISTENCY_FIELDS[1]) or "")
    return out


def compare_snapshots(
    prev_ids: dict[str, str], prev_started: dt.datetime, cur_ids: dict[str, str], before_prev_ids: set[str] | None
) -> dict[str, int]:
    """Counts for one consecutive pair; ``before_prev_ids`` (the snapshot before
    the previous one, when logged) gives the previous snapshot's missed-at-most."""
    prev = set(prev_ids)
    cur = set(cur_ids)
    appeared = cur - prev
    early = 0
    for mid in appeared:
        created = parse_utc(cur_ids[mid])
        if created is not None and created < prev_started:
            early += 1
    missed = len((cur & before_prev_ids) - prev) if before_prev_ids is not None else 0
    return {
        "previous_markets": len(prev),
        "markets": len(cur),
        "carried": len(cur & prev),
        "left": len(prev - cur),
        "appeared": len(appeared),
        "appeared_created_before_previous_start": early,
        "previous_missed_at_most": missed,
    }


def consistency(snapshot_root: Path, log_csv: Path, out_csv: Path) -> list[dict[str, str]]:
    """Compare each logged snapshot with the one logged before it and append
    one counts line per snapshot date to ``out_csv`` (dates already there are
    kept as they are). Returns the rows appended."""
    log = sorted(read_log(log_csv), key=lambda r: r["snapshot_date"])
    done = {r["snapshot_date"] for r in read_log(out_csv)}
    appended: list[dict[str, str]] = []
    cache: dict[str, dict[str, str]] = {}

    def ids_of(day: str) -> dict[str, str]:
        if day not in cache:
            cache[day] = read_ids(snapshot_root / day / "records.jsonl")
        return cache[day]

    for k in range(1, len(log)):
        day = log[k]["snapshot_date"]
        if day in done:
            continue
        needed = {log[j]["snapshot_date"] for j in range(max(0, k - 2), k + 1)}
        for old in [d for d in cache if d not in needed]:
            cache.pop(old)  # at most three snapshots' ids in memory
        prev = log[k - 1]
        prev_started = parse_utc(prev["started_utc"])
        if prev_started is None:
            raise ValueError(f"unreadable started_utc on {prev['snapshot_date']}")
        before_prev = set(ids_of(log[k - 2]["snapshot_date"])) if k >= 2 else None
        counts = compare_snapshots(ids_of(prev["snapshot_date"]), prev_started, ids_of(day), before_prev)
        row = {
            "snapshot_date": day,
            "previous_date": prev["snapshot_date"],
            **{c: str(v) for c, v in counts.items()},
            "computed_utc": stamp(utc_now()),
        }
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        new = not out_csv.exists() or out_csv.stat().st_size == 0
        with open(out_csv, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CONSISTENCY_COLUMNS, lineterminator="\n")
            if new:
                w.writeheader()
            w.writerow({c: row[c] for c in CONSISTENCY_COLUMNS})
        appended.append(row)
    return appended


def consistency_line(row: dict[str, str]) -> str:
    prev_n = int(row["previous_markets"])
    missed = int(row["previous_missed_at_most"])
    pct = (100.0 * missed / prev_n) if prev_n else 0.0
    flag = " FINDING (at or above one page)" if missed >= MISSED_PAGE_THRESHOLD else ""
    return (
        f"{row['snapshot_date']} vs {row['previous_date']}: {row['markets']} markets ({prev_n} before); "
        f"carried {row['carried']}, left {row['left']}, appeared {row['appeared']} "
        f"({row['appeared_created_before_previous_start']} created before the previous snapshot started); "
        f"previous snapshot missed at most {missed} ({pct:.3f}% of its {prev_n}){flag}"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot", help="fetch today's snapshot of the open-market listing")
    s.add_argument("--dry-run", action="store_true", help="fetch one page, write nothing")
    sub.add_parser("check", help="list UTC dates with no snapshot since the first one")
    sub.add_parser("consistency", help="id-only comparison of consecutive snapshots; appends paper-log/consistency.csv")
    a = ap.parse_args(argv)

    if a.cmd == "check":
        missing = gaps(SNAPSHOT_LOG, utc_now().date())
        n = len(read_log(SNAPSHOT_LOG))
        if missing:
            print(f"snapshots: {n} complete; {len(missing)} day(s) missing: {', '.join(missing)} (never backfilled)")
            return 3
        print(f"snapshots: {n} complete, no gap")
        return 0

    if a.cmd == "consistency":
        rows = consistency(SNAPSHOT_ROOT, SNAPSHOT_LOG, CONSISTENCY_LOG)
        if not rows:
            print(f"consistency: nothing new to compare ({len(read_log(CONSISTENCY_LOG))} line(s) in {CONSISTENCY_LOG.relative_to(STUDY_DIR)})")
            return 0
        rc = 0
        for row in rows:
            print("consistency: " + consistency_line(row))
            if int(row["previous_missed_at_most"]) >= MISSED_PAGE_THRESHOLD:
                rc = 3
        print(f"consistency: {len(rows)} line(s) appended to {CONSISTENCY_LOG.relative_to(STUDY_DIR)}; fields read per row: {', '.join(CONSISTENCY_FIELDS)}")
        return rc

    try:
        row = take_snapshot(
            snapshot_root=SNAPSHOT_ROOT,
            log_csv=SNAPSHOT_LOG,
            fetch=fetch_page,
            now=utc_now(),
            dry_run=a.dry_run,
        )
    except SnapshotExists as e:
        print(f"refused: {e}")
        return 2
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"failed: {type(e).__name__}: {e}; nothing written, nothing counted", file=sys.stderr)
        return 1
    if a.dry_run:
        print(f"dry run: one page, {row['rows']} rows, {row['bytes']} bytes, sha256 {row['sha256'][:16]}…, more pages: {row['more']}; nothing written")
        return 0
    print(
        f"snapshot {row['snapshot_date']}: {row['pages']} pages, {row['rows']} rows, "
        f"{row['distinct_markets']} distinct markets, {row['bytes']} bytes, "
        f"{row['started_utc']}–{row['finished_utc']}; line appended to {SNAPSHOT_LOG.relative_to(STUDY_DIR)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
