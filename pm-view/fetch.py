"""Quote one or more Polymarket markets for the prediction-market view: the
Gamma record and the CLOB book of the YES token, kept raw and git-ignored,
hashed into `data/manifest.json`, summarised on one printed line each.

The printed line is what a call row quotes: the market's id, condition id and
YES token id, the mid and spread of the best bid and ask read from the book
at the fetch time, cumulative volume, scheduled end, and the first reason the
market is not eligible for a call (pm_lib.eligibility, Study 013's §6.3
order), or `eligible`.  The desk reads its own probability only after this
line exists (predictions/README.md, "Baseline before confidence").

Both reads are public, no key, no wallet, read-only, inside the documented
rate limits (Gamma /markets 300 per 10 s; CLOB /book 1,500 per 10 s), with a
declared user agent.  The CLOB book is read for the price because the Gamma
listing is served from a cache of up to five minutes (observed 2026-11-02).

Polymarket's verdict is `derived` (tools/pm_data_terms.md): the raw bodies
stay under `data/raw/quotes/<UTC time>/` (git-ignored); only their hashes and
the numbers the desk computed go in the manifest and the ledger.

Usage (from this folder):
    python fetch.py quote <market_id> [<market_id> ...]
    python fetch.py quote <market_id> --dry-run        # nothing written
Exit 0 when every market was read, 1 when any fetch failed (its line says so).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pm_lib import as_float, best_of_book, decode_list, eligibility, mid, rules_excerpt

HERE = Path(__file__).resolve().parent
GAMMA_MARKET = "https://gamma-api.polymarket.com/markets/"
CLOB_BOOK = "https://clob.polymarket.com/book?token_id="
UA = "qune-research/0.1 (public research; prediction-market view quote; pm-view/fetch.py)"
PAUSE_S = 0.2

Fetcher = Callable[[str], bytes]


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def quote_one(market_id: str, gamma: Fetcher, book: Fetcher, at: datetime) -> dict[str, Any]:
    """One market's quote: raw bodies, hashes and the computed numbers; `error` set when a fetch failed."""
    out: dict[str, Any] = {"market_id": market_id, "fetched_utc": at.strftime("%Y-%m-%dT%H:%M:%SZ")}
    try:
        gbody = gamma(GAMMA_MARKET + market_id)
    except (urllib.error.URLError, OSError, ValueError) as e:
        out["error"] = f"gamma fetch failed: {e}"
        return out
    out["gamma_body"] = gbody
    out["gamma_sha256"] = sha256(gbody)
    try:
        row = json.loads(gbody)
    except ValueError:
        out["error"] = "gamma body is not JSON"
        return out
    if not isinstance(row, dict):
        out["error"] = "gamma body is not a market record"
        return out
    tokens = decode_list(row.get("clobTokenIds")) or []
    out["condition_id"] = row.get("conditionId")
    out["question"] = row.get("question") if isinstance(row.get("question"), str) else None
    desc: str = row["description"] if isinstance(row.get("description"), str) else ""
    out["description_sha256"] = sha256(desc.encode("utf-8")) if desc else None
    out["description_chars"] = len(desc)
    out["rules_excerpt"] = rules_excerpt(row)
    out["yes_token_id"] = str(tokens[0]) if tokens else None
    out["end_date"] = row.get("endDate")
    out["volume_usdc"] = as_float(row.get("volumeNum"))
    best = None
    if out["yes_token_id"]:
        try:
            bbody = book(CLOB_BOOK + out["yes_token_id"])
        except (urllib.error.URLError, OSError, ValueError) as e:
            out["error"] = f"book fetch failed: {e}"
            return out
        out["book_body"] = bbody
        out["book_sha256"] = sha256(bbody)
        try:
            best = best_of_book(json.loads(bbody))
        except ValueError:
            out["error"] = "book body is not JSON"
            return out
    out["best_bid"], out["best_ask"] = best if best else (None, None)
    out["market_mid"] = round(mid(*best), 4) if best else None
    out["market_spread"] = round(best[1] - best[0], 4) if best else None
    out["eligibility"] = eligibility(row, best, at) or "eligible"
    return out


def line(q: dict[str, Any]) -> str:
    """The quote line, then the market's title and the start of its own resolution
    text on a second line (added 2026-11-04, predictions/POST_MORTEMS.md: the
    first view named two touch markets from their titles; the rule is read
    before the desk writes).  The excerpt is printed, never written to a
    committed file; the manifest carries the description's hash and length."""
    if "error" in q:
        return f"{q['market_id']}: FAILED {q['error']}"
    return (f"{q['market_id']}: mid={q['market_mid']} spread={q['market_spread']} "
            f"volume={q['volume_usdc']:,.0f} end={q['end_date']} cond={q['condition_id']} "
            f"yes_token={q['yes_token_id']} {q['eligibility']} (fetched {q['fetched_utc']})\n"
            f"    title: {q.get('question')!r}\n"
            f"    settles on ({q.get('description_chars', 0)} chars, sha256 {str(q.get('description_sha256'))[:12]}): "
            f"{q.get('rules_excerpt')}")


def write_quote(q: dict[str, Any], raw_dir: Path, manifest: Path) -> None:
    """Raw bodies under raw_dir/<fetched time>/, one manifest entry appended (the manifest is a JSON list)."""
    folder = raw_dir / q["fetched_utc"].replace(":", "")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"gamma_{q['market_id']}.json").write_bytes(q["gamma_body"])
    if q.get("book_body") is not None:
        (folder / f"book_{q['market_id']}.json").write_bytes(q["book_body"])
    entry = {k: q.get(k) for k in ("fetched_utc", "market_id", "condition_id", "yes_token_id", "gamma_sha256",
                                   "book_sha256", "best_bid", "best_ask", "market_mid", "market_spread",
                                   "volume_usdc", "end_date", "eligibility", "question", "description_sha256",
                                   "description_chars")}
    entry["source"] = "Polymarket Gamma /markets/<id> and CLOB /book?token_id=<yes token>"
    entries: list[dict[str, Any]] = []
    if manifest.exists():
        entries = json.loads(manifest.read_text(encoding="utf-8"))
    entries.append(entry)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(market_ids: list[str], gamma: Fetcher, book: Fetcher, raw_dir: Path, manifest: Path,
        dry_run: bool, now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> int:
    rc = 0
    for i, market_id in enumerate(market_ids):
        if i:
            time.sleep(PAUSE_S)
        q = quote_one(market_id, gamma, book, now())
        print(line(q))
        if "error" in q:
            rc = 1
            continue
        if not dry_run:
            write_quote(q, raw_dir, manifest)
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("quote")
    q.add_argument("market_ids", nargs="+")
    q.add_argument("--dry-run", action="store_true")
    q.add_argument("--raw-dir", type=Path, default=None)
    q.add_argument("--manifest", type=Path, default=None)
    a = ap.parse_args(argv)
    raw_dir = a.raw_dir if a.raw_dir is not None else HERE / "data" / "raw" / "quotes"
    manifest = a.manifest if a.manifest is not None else HERE / "data" / "manifest.json"
    return run(a.market_ids, http_get, http_get, raw_dir, manifest, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
