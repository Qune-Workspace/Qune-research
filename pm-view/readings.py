"""Admit one method reading to the readings record, `readings.csv`, from a quote
that fetch.py wrote (added 2026-11-06 18:15Z, predictions/POST_MORTEMS.md "A week
of readings that no record could score").

A call is rare by design, so the ledger alone says little about whether a
method's reading carries information against the market.  The readings record
keeps, per view, each method reading beside the market mid it was read against;
score.py scores both (and the climatological probability where one was on
record) on the venue's settlement by the same pre-registered rule as a call,
into `readings_outcomes.csv`, and `score.py --summary` reports the per-method
figures in SKILL.md as information, never as a call or a position.

The row is built from the manifest entry, not retyped: the market's condition
id, YES token, mid, scheduled end and quote hash come from `data/manifest.json`
by market id and fetch time; the method's four numbers come from the printer's
candidate line (barrier.py or fomc_calibrate.py --live).  `pm_lib.reading_violations`
is the gate, applied here where the row is admitted and again by
tests/test_readings.py on the committed file; every refusal it gives carries a
`[reading:<tag>]` from `pm_lib.READING_TAGS`, the same tag README.md rule 5 puts
beside the rule (2026-11-07 00:15Z; tests/test_rule_tags.py holds the two equal).
A reading made on a `--dry-run` quote has no hash and is refused: re-quote
without `--dry-run` first.  The `gate` column records the call gate's refusals
for the same numbers (or `open`), so the record also shows why each reading was
not a call.

Usage (from this folder):
    python readings.py add --market-id 6507380 --quote 2026-11-06T06:16:38Z --method btc_touch \\
        --method-p 0.876 --range-lo 0.876 --range-hi 0.886 --climatology-p 0.690 \\
        --proposition "Bitcoin dips to 75,000 in November" --source "PM_VIEW.md 2026-11-06" [--dry-run]
Exit 0 when the row was admitted (or would be, --dry-run); 1 when the gate refused it.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pm_lib as L
from score import append_row, read_csv

HERE = Path(__file__).resolve().parent
VENUE = "polymarket"


def calibration_r2(method: str, here: Path = HERE) -> bool | None:
    """R2 of the method's committed calibration file, as the ledger test reads it."""
    if method not in L.METHOD_CALIBRATION:
        return None
    path = here / L.METHOD_CALIBRATION[method][0]
    cal = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    return L.method_gate(method, cal)


def find_quote(entries: list[dict[str, Any]], market_id: str, fetched_utc: str) -> dict[str, Any] | None:
    hits = [e for e in entries if e.get("market_id") == market_id and e.get("fetched_utc") == fetched_utc]
    return hits[0] if len(hits) == 1 else None


reading_id = L.reading_id  # the id rule lives with the gate that refuses a duplicate (2026-11-07)


def build_row(quote: dict[str, Any] | None, market_id: str, method: str, method_p: float, range_lo: float,
              range_hi: float, climatology_p: float | None, proposition: str, source: str, r2: bool | None,
              now: datetime, existing_ids: Iterable[str] = ()) -> tuple[dict[str, Any], list[str]]:
    """The readings.csv row and the gate's refusals (empty when admitted)."""
    q = quote or {}
    made_on = str(q.get("fetched_utc", ""))[:10]
    due_on = str(q.get("end_date", ""))[:10]
    market_mid = L.as_float(q.get("market_mid"))
    v = L.reading_violations(method, method_p, range_lo, range_hi, market_mid, climatology_p, quote, made_on, due_on,
                             market_id=market_id, existing_ids=existing_ids)
    gate_tags = [] if market_mid is None else L.method_violations(method, method_p, range_lo, range_hi, market_mid, r2)
    row: dict[str, Any] = {
        "id": reading_id(made_on, method, market_id), "made_on": made_on,
        "recorded_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "venue": VENUE, "market_id": market_id,
        "condition_id": q.get("condition_id"), "yes_token_id": q.get("yes_token_id"), "proposition": proposition,
        "method": method, "method_p": f"{method_p:.3f}", "range_lo": f"{range_lo:.3f}", "range_hi": f"{range_hi:.3f}",
        "market_mid": q.get("market_mid"), "climatology_p": None if climatology_p is None else f"{climatology_p:.3f}",
        "due_on": due_on, "gate": ";".join(sorted(L.gate_tags(" ".join(gate_tags)))) or "open",
        "quote_fetched_utc": q.get("fetched_utc"), "quote_sha256": q.get("gamma_sha256"), "source": source,
    }
    return row, v


def add(args: argparse.Namespace, manifest: Path, readings: Path, now: datetime) -> int:
    entries = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
    quote = find_quote(entries, args.market_id, args.quote)
    r2 = calibration_r2(args.method, manifest.parent.parent)
    row, v = build_row(quote, args.market_id, args.method, args.method_p, args.range_lo, args.range_hi,
                       args.climatology_p, args.proposition, args.source, r2, now,
                       existing_ids=[r["id"] for r in read_csv(readings)])
    if quote is None:
        # the mid comes from the quote, so with no quote there is no mid to judge; the gate's own
        # refusal keeps its tag, and the tool adds what it looked for
        v = [x for x in v if "[reading:mid-probability]" not in x]
        v.append(f"(no manifest entry for market {args.market_id} fetched at {args.quote} in {manifest.name}; "
                 "a --dry-run quote writes none: re-quote without --dry-run)")
    if v:
        print(f"REFUSED {row['id']}: " + "; ".join(v))
        return 1
    print(f"{'DRY RUN ' if args.dry_run else ''}ADMITTED {row['id']}: method_p={row['method_p']} "
          f"range=[{row['range_lo']}, {row['range_hi']}] market_mid={row['market_mid']} "
          f"climatology_p={row['climatology_p']} due_on={row['due_on']} gate={row['gate']}")
    if not args.dry_run:
        append_row(readings, L.READING_COLUMNS, row)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--market-id", required=True)
    a.add_argument("--quote", required=True, help="the manifest entry's fetched_utc, e.g. 2026-11-06T06:16:38Z")
    a.add_argument("--method", required=True, choices=L.READING_METHODS)
    a.add_argument("--method-p", type=float, required=True)
    a.add_argument("--range-lo", type=float, required=True)
    a.add_argument("--range-hi", type=float, required=True)
    a.add_argument("--climatology-p", type=float, default=None)
    a.add_argument("--proposition", required=True)
    a.add_argument("--source", required=True, help="where the reading was published (view file and date)")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--manifest", type=Path, default=None)
    a.add_argument("--readings", type=Path, default=None)
    args = ap.parse_args(argv)
    manifest = args.manifest if args.manifest is not None else HERE / "data" / "manifest.json"
    readings = args.readings if args.readings is not None else HERE / "readings.csv"
    return add(args, manifest, readings, datetime.now(UTC))


if __name__ == "__main__":
    sys.exit(main())
