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

Usage (from the study folder, the scheduled job runs it daily):
    .venv/bin/python collector.py snapshot            # fetch today's snapshot
    .venv/bin/python collector.py snapshot --dry-run  # one page, nothing written
    .venv/bin/python collector.py check               # gaps since the first snapshot
Exit 0 on a complete snapshot (or a check with no gap), 1 on a fetch failure
(nothing counted), 2 when today's snapshot already exists, 3 on gaps.
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot", help="fetch today's snapshot of the open-market listing")
    s.add_argument("--dry-run", action="store_true", help="fetch one page, write nothing")
    sub.add_parser("check", help="list UTC dates with no snapshot since the first one")
    a = ap.parse_args(argv)

    if a.cmd == "check":
        missing = gaps(SNAPSHOT_LOG, utc_now().date())
        n = len(read_log(SNAPSHOT_LOG))
        if missing:
            print(f"snapshots: {n} complete; {len(missing)} day(s) missing: {', '.join(missing)} (never backfilled)")
            return 3
        print(f"snapshots: {n} complete, no gap")
        return 0

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
