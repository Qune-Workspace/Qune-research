"""Admit one call to the ledger, `ledger.csv`, from a quote that fetch.py wrote
(added 2026-11-07 18:15Z, predictions/POST_MORTEMS.md "A gate that only a test
applied").

Until this date no tool wrote a call: logging one meant hand-typing a CSV row,
and the call gate, `pm_lib.call_violations`, ran only in
tests/test_ledger_discipline.py on the committed file, after the row was
written.  A call now enters the ledger only through this tool, which applies
the gate where the row is admitted, as readings.py does for a reading.

The row is built from the manifest entry, not retyped: the market's condition
id, YES token, mid, spread, volume, scheduled end (`due_on`) and book hash come
from `data/manifest.json` by market id and fetch time, and `made_on` is the
quote's day (`pm_lib.quote_day`); the method's three numbers come from the
printer's candidate line (barrier.py or fomc_calibrate.py --live, "(ledger:
method=... method_p=... range_lo=... range_hi=...)"); the desk's probability,
the proposition, `settles_on` and the basis are the desk's own words.
`pm_lib.ledger_row_violations` is the gate, applied here and again by the
committed-file test: the row's own checks (a two-decimal desk number, the quote
written with its book hash in the row, the mid copied, the market eligible, the
rules' hash on record, one call per market and day) and then call_violations,
with R2 taken from the method's line of data/calibration_history.csv in force at
the quote's fetch, the judgement the committed-file test makes.  Every refusal
carries a `[gate:<tag>]` from `pm_lib.GATE_TAGS`, the tag README.md rule 2 puts
beside the rule.  A call made on a `--dry-run` quote has no manifest entry and is
refused: re-quote without `--dry-run` first.  A refusal writes nothing.

Usage (from this folder):
    python ledger.py add --market-id 3215008 --quote 2026-11-06T06:16:37Z --desk-p 0.85 --method fomc_bills \\
        --method-p 1.000 --range-lo 0.585 --range-hi 1.000 --proposition "Hike of 25 bp on 9 December" \\
        --settles-on "<the market's resolution rule restated: source and level or date>" \\
        --basis "<the market's number and what it is missing, in one testable sentence>" [--dry-run]
Exit 0 when the call was admitted (or would be, --dry-run); 1 when the gate refused it
(the refusals on stderr, nothing written).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pm_lib as L
from readings import find_quote
from score import append_row, read_csv

HERE = Path(__file__).resolve().parent
VENUE = "polymarket"


def num(v: float | None) -> str | None:
    return None if v is None else f"{v:.3f}"


def build_row(quote: dict[str, Any] | None, market_id: str, desk_p: str, method: str, method_p: float | None,
              range_lo: float | None, range_hi: float | None, proposition: str, settles_on: str,
              basis: str) -> dict[str, Any]:
    """The ledger.csv row: the quote's fields copied from its manifest entry, the desk's typed as given."""
    q = quote or {}
    made_on = L.quote_day(q.get("fetched_utc"))
    return {
        "id": L.call_id(made_on, method, market_id), "made_on": made_on, "venue": VENUE, "market_id": market_id,
        "condition_id": q.get("condition_id"), "yes_token_id": q.get("yes_token_id"), "proposition": proposition,
        "settles_on": settles_on, "due_on": str(q.get("end_date", ""))[:10], "market_mid": q.get("market_mid"),
        "market_spread": q.get("market_spread"), "volume_usdc": q.get("volume_usdc"), "desk_p": desk_p,
        "method": method, "method_p": num(method_p), "range_lo": num(range_lo), "range_hi": num(range_hi),
        "basis": basis, "quote_sha256": q.get("book_sha256"),
    }


def add(args: argparse.Namespace, manifest: Path, ledger: Path) -> int:
    entries = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
    quote = find_quote(entries, args.market_id, args.quote)
    history = read_csv(manifest.parent.parent / L.CALIBRATION_HISTORY)
    row = build_row(quote, args.market_id, args.desk_p, args.method, args.method_p, args.range_lo, args.range_hi,
                    args.proposition, args.settles_on, args.basis)
    v = L.ledger_row_violations(row, quote, history, read_csv(ledger))
    if quote is None:
        v.append(f"(no manifest entry for market {args.market_id} fetched at {args.quote} in {manifest.name})")
    if v:
        print(f"REFUSED {row['id']}: " + "; ".join(v), file=sys.stderr)
        return 1
    print(f"{'DRY RUN ' if args.dry_run else ''}ADMITTED {row['id']}: desk_p={row['desk_p']} "
          f"market_mid={row['market_mid']} method={row['method']} method_p={row['method_p']} "
          f"range=[{row['range_lo']}, {row['range_hi']}] due_on={row['due_on']}")
    if not args.dry_run:
        append_row(ledger, L.LEDGER_COLUMNS, row)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--market-id", required=True)
    a.add_argument("--quote", required=True, help="the manifest entry's fetched_utc, e.g. 2026-11-06T06:16:37Z")
    a.add_argument("--desk-p", required=True, help="the desk's probability, two decimals, as it goes in the row")
    a.add_argument("--method", required=True, choices=L.METHODS)
    a.add_argument("--method-p", type=float, default=None, help="from the printer's candidate line; empty for stated")
    a.add_argument("--range-lo", type=float, default=None)
    a.add_argument("--range-hi", type=float, default=None)
    a.add_argument("--proposition", required=True, help="the desk's own words for what YES means")
    a.add_argument("--settles-on", required=True, help="the market's resolution rule restated: source, level or date")
    a.add_argument("--basis", required=True, help="the market's number and what it is missing")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--manifest", type=Path, default=None)
    a.add_argument("--ledger", type=Path, default=None)
    args = ap.parse_args(argv)
    manifest = args.manifest if args.manifest is not None else HERE / "data" / "manifest.json"
    ledger = args.ledger if args.ledger is not None else HERE / "ledger.csv"
    return add(args, manifest, ledger)


if __name__ == "__main__":
    sys.exit(main())
