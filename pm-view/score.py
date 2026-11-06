"""Score the prediction-market view's due calls on the venue's own settlement,
once each, by Study 013's pre-registered outcome rule, and write SKILL.md.

A call is due once its `due_on` (the market's scheduled end date) has passed.
For each due, unscored call the scorer reads the Gamma market record and the
CLOB market record (`/markets/<conditionId>`, which carries each token's
`winner` flag) and applies research/013-polymarket-calibration-forward
`src/outcome.py::classify` unchanged: YES wins when the UMA status is
`resolved`, the settlement prices are exactly 1 and 0 and the CLOB winner flags
agree; NO wins on the reverse; anything else (not yet resolved, a fractional
or 50/50 settlement, a disagreement, a failed fetch) excludes the call.

What is written, append-only, to `outcomes.csv`: a settled call with y and
both Brier scores (the desk's probability and the market mid at the time of
the call, against the same outcome); a call whose market settled outside 1/0
or 0/1, or whose records disagree, as an excluded row with its kind and no y,
so it is closed and never retried.  A call whose market is not yet resolved
is not written: the scorer prints `NOT SCORED ... retry on a later run`.
An id already in `outcomes.csv` is refused.  The ledger is never written.

The readings record (added 2026-11-06 18:15Z, `readings.csv`, written by
readings.py) is scored the same way into `readings_outcomes.csv`: a reading is
checked once its `due_on` has passed, or earlier when a later written quote of
the same market carries a `settlement` (a market can resolve before its
scheduled end, as the 80,000 touch market did on 4 November).  Each scored row
carries the Brier of the method's reading, of the market mid and, where the row
has one, of the climatological probability, against the same outcome.  It is
information about the methods, not a call.

`--summary` rewrites SKILL.md from the five files: desk and market Brier over
the scored calls and the skill (market minus desk), with the count.  With
fewer than about thirty scored calls the figure is descriptive.

Usage (from this folder):
    python score.py [--today YYYY-MM-DD] [--dry-run]
    python score.py --summary
Exit 0; 1 on a fetch failure (nothing written for that call).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pm_lib import OUTCOME_COLUMNS, READING_OUTCOME_COLUMNS, brier, reading_summary, skill_summary

HERE = Path(__file__).resolve().parent
STUDY_013 = HERE.parent / "research" / "013-polymarket-calibration-forward"
if str(STUDY_013) not in sys.path:
    sys.path.insert(0, str(STUDY_013))
from src.outcome import FIRST, NOT_RESOLVED, SECOND, UNFETCHED, classify  # noqa: E402

GAMMA_MARKET = "https://gamma-api.polymarket.com/markets/"
CLOB_MARKET = "https://clob.polymarket.com/markets/"
UA = "qune-research/0.1 (public research; prediction-market view scoring; pm-view/score.py)"

Fetcher = Callable[[str], bytes]


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def append_row(path: Path, columns: tuple[str, ...], row: dict[str, Any]) -> None:
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(columns))
        if new:
            w.writeheader()
        w.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in columns})


def fetch_records(call: dict[str, str], gamma: Fetcher, clob: Fetcher) -> tuple[dict | None, dict | None, str, str]:
    """(status record, outcome record, gamma sha, clob sha); a failed fetch gives a record with fetch_failed."""
    try:
        gbody = gamma(GAMMA_MARKET + call["market_id"])
        status = json.loads(gbody)
        gsha = hashlib.sha256(gbody).hexdigest()
    except (urllib.error.URLError, OSError, ValueError):
        return {"fetch_failed": True}, None, "", ""
    try:
        cbody = clob(CLOB_MARKET + call["condition_id"])
        cm = json.loads(cbody)
        csha = hashlib.sha256(cbody).hexdigest()
    except (urllib.error.URLError, OSError, ValueError):
        return status, {"fetch_failed": True}, gsha, ""
    outcome = {"outcomePrices": status.get("outcomePrices") if isinstance(status, dict) else None,
               "tokens": cm.get("tokens") if isinstance(cm, dict) else None}
    return status if isinstance(status, dict) else {"fetch_failed": True}, outcome, gsha, csha


def score_call(call: dict[str, str], status: dict | None, outcome: dict | None, gsha: str, csha: str,
               today: date) -> dict[str, Any] | None:
    """The outcomes.csv row for one call, or None when it is not scored today."""
    kind = classify(status, outcome, call["yes_token_id"])
    if kind in (NOT_RESOLVED, UNFETCHED):
        return None
    row: dict[str, Any] = {"id": call["id"], "scored_on": today.isoformat(), "kind": kind, "y": None,
                           "desk_p": call["desk_p"], "market_mid": call["market_mid"], "brier_desk": None,
                           "brier_market": None, "gamma_sha256": gsha, "clob_sha256": csha}
    if kind in (FIRST, SECOND):
        y = 1 if kind == FIRST else 0
        row["y"] = y
        row["brier_desk"] = f"{brier(float(call['desk_p']), y):.4f}"
        row["brier_market"] = f"{brier(float(call['market_mid']), y):.4f}"
    return row


def run(ledger: Path, outcomes: Path, gamma: Fetcher, clob: Fetcher, today: date, dry_run: bool) -> int:
    scored = {r["id"] for r in read_csv(outcomes)}
    rc = 0
    for call in read_csv(ledger):
        if call["id"] in scored:
            continue
        if date.fromisoformat(call["due_on"]) > today:
            continue
        status, outcome, gsha, csha = fetch_records(call, gamma, clob)
        row = score_call(call, status, outcome, gsha, csha, today)
        if row is None:
            kind = classify(status, outcome, call["yes_token_id"])
            if kind == UNFETCHED:
                rc = 1
            print(f"NOT SCORED {call['id']}: {kind}; retry on a later run")
            continue
        print(f"{'DRY RUN ' if dry_run else ''}SCORED {call['id']}: {row['kind']} y={row['y']} "
              f"brier desk={row['brier_desk']} market={row['brier_market']}")
        if not dry_run:
            append_row(outcomes, OUTCOME_COLUMNS, row)
    return rc


def reading_due(reading: dict[str, str], today: date, manifest_entries: list[dict[str, Any]]) -> bool:
    """Due once due_on has passed, or when a written quote of the market made after the reading carries a settlement."""
    if date.fromisoformat(reading["due_on"]) <= today:
        return True
    return any(e.get("market_id") == reading["market_id"] and e.get("settlement")
               and str(e.get("fetched_utc", "")) > str(reading["quote_fetched_utc"]) for e in manifest_entries)


def score_reading(reading: dict[str, str], status: dict | None, outcome: dict | None, gsha: str, csha: str,
                  today: date) -> dict[str, Any] | None:
    """The readings_outcomes.csv row for one reading, or None when it is not scored today."""
    kind = classify(status, outcome, reading["yes_token_id"])
    if kind in (NOT_RESOLVED, UNFETCHED):
        return None
    clim = reading.get("climatology_p") or ""
    row: dict[str, Any] = {"id": reading["id"], "scored_on": today.isoformat(), "kind": kind, "y": None,
                           "method_p": reading["method_p"], "market_mid": reading["market_mid"],
                           "climatology_p": clim or None, "brier_method": None, "brier_market": None,
                           "brier_climatology": None, "gamma_sha256": gsha, "clob_sha256": csha}
    if kind in (FIRST, SECOND):
        y = 1 if kind == FIRST else 0
        row["y"] = y
        row["brier_method"] = f"{brier(float(reading['method_p']), y):.4f}"
        row["brier_market"] = f"{brier(float(reading['market_mid']), y):.4f}"
        if clim:
            row["brier_climatology"] = f"{brier(float(clim), y):.4f}"
    return row


def run_readings(readings: Path, outcomes: Path, manifest: Path, gamma: Fetcher, clob: Fetcher, today: date,
                 dry_run: bool) -> int:
    entries: list[dict[str, Any]] = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
    scored = {r["id"] for r in read_csv(outcomes)}
    rc = 0
    checked = 0
    for reading in read_csv(readings):
        if reading["id"] in scored or not reading_due(reading, today, entries):
            continue
        checked += 1
        status, outcome, gsha, csha = fetch_records(reading, gamma, clob)
        row = score_reading(reading, status, outcome, gsha, csha, today)
        if row is None:
            kind = classify(status, outcome, reading["yes_token_id"])
            if kind == UNFETCHED:
                rc = 1
            print(f"READING NOT SCORED {reading['id']}: {kind}; retry on a later run")
            continue
        print(f"{'DRY RUN ' if dry_run else ''}READING SCORED {reading['id']}: {row['kind']} y={row['y']} "
              f"brier method={row['brier_method']} market={row['brier_market']} "
              f"climatology={row['brier_climatology']}")
        if not dry_run:
            append_row(outcomes, READING_OUTCOME_COLUMNS, row)
    if checked == 0:
        print(f"readings: none due (of {len(read_csv(readings))} on the record)")
    return rc


def write_summary(ledger: Path, outcomes: Path, skill: Path, today: date) -> None:
    calls = read_csv(ledger)
    done = {r["id"]: r for r in read_csv(outcomes)}
    s = skill_summary(list(done.values()))
    lines = [
        "# Desk calls against the market mid",
        "",
        f"Generated by `pm-view/score.py --summary` on {today.isoformat()} from `ledger.csv` and `outcomes.csv`. "
        "The market mid is the probability the venue's order book gave at the time of the call, read before the "
        "desk's own (pm_lib.py). Skill is the market's Brier score minus the desk's: positive means the desk did "
        "better than the market, negative means worse. A hit rate is not reported.",
        "",
        "| id | proposition | due | desk p | market mid | outcome |",
        "|---|---|---|---|---|---|",
    ]
    for c in calls:
        o = done.get(c["id"])
        if o is None:
            res = "not yet due" if date.fromisoformat(c["due_on"]) > today else "due, not resolved"
        elif o["y"] == "":
            res = f"excluded: {o['kind']}"
        else:
            res = "YES" if o["y"] == "1" else "NO"
        lines.append(f"| {c['id']} | {c['proposition']} | {c['due_on']} | {float(c['desk_p']):.2f} | "
                     f"{float(c['market_mid']):.3f} | {res} |")
    if not calls:
        lines.append("| (no call logged yet) | | | | | |")
    lines.append("")
    if s["n"] == 0:
        lines.append("Scored calls: 0. No Brier score yet.")
    else:
        lines.append(f"Scored calls: {s['n']}. Brier, desk: {s['brier_desk']:.4f}. Brier, market mid: "
                     f"{s['brier_market']:.4f}. Skill (market minus desk): {s['skill']:+.4f}.")
    lines.append("With fewer than about thirty scored calls this figure is descriptive, not evidence.")
    lines += readings_lines(ledger.parent / "readings.csv", ledger.parent / "readings_outcomes.csv", today)
    skill.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _f(v: float | None) -> str:
    return "–" if v is None else f"{v:.4f}"


def readings_lines(readings: Path, outcomes: Path, today: date) -> list[str]:
    """The readings section of SKILL.md: per method, the scored count and the three Brier figures; information only."""
    rows = read_csv(readings)
    done = {r["id"]: r for r in read_csv(outcomes)}
    merged = [{**r, **done.get(r["id"], {})} for r in rows]
    s = reading_summary(merged)
    pending = sum(1 for r in rows if r["id"] not in done)
    lines = [
        "",
        "## Method readings against the market, as information",
        "",
        "From `readings.csv` and `readings_outcomes.csv` (readings.py, score.py; added 2026-11-06). Each row is a "
        "method's reading recorded beside the market mid of a written quote while the market was open, scored on the "
        "venue's settlement by the same rule as a call. These are not calls: the call gate refused each of them for the "
        "reason in its `gate` column, and nothing here is a position. Brier is lower-better; the climatology column is "
        "the method's own baseline where one was on record at the time of the reading.",
        "",
        "| method | readings on record | scored | Brier, reading | Brier, market mid | Brier, climatology (n) |",
        "|---|---|---|---|---|---|",
    ]
    for method, e in s.items():
        on_record = sum(1 for r in rows if r["method"] == method)
        lines.append(f"| {method} | {on_record} | {e['n']} | {_f(e['brier_method'])} | {_f(e['brier_market'])} | "
                     f"{_f(e['brier_climatology'])} ({e['n_climatology']}) |")
    lines.append("")
    lines.append(f"Readings on record: {len(rows)}; scored: {len(done)}; not yet due or not yet resolved: {pending}. "
                 "With fewer than about thirty scored readings per method the figures describe the rows, nothing more.")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--today", type=date.fromisoformat, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--ledger", type=Path, default=None)
    ap.add_argument("--outcomes", type=Path, default=None)
    ap.add_argument("--skill", type=Path, default=None)
    ap.add_argument("--readings", type=Path, default=None)
    ap.add_argument("--readings-outcomes", type=Path, default=None)
    ap.add_argument("--manifest", type=Path, default=None)
    a = ap.parse_args(argv)
    today = a.today or datetime.now(UTC).date()
    ledger = a.ledger if a.ledger is not None else HERE / "ledger.csv"
    outcomes = a.outcomes if a.outcomes is not None else HERE / "outcomes.csv"
    skill = a.skill if a.skill is not None else HERE / "SKILL.md"
    if a.summary:
        write_summary(ledger, outcomes, skill, today)
        print(f"wrote {skill.name}")
        return 0
    rc = run(ledger, outcomes, http_get, http_get, today, a.dry_run)
    readings = a.readings if a.readings is not None else HERE / "readings.csv"
    r_out = a.readings_outcomes if a.readings_outcomes is not None else HERE / "readings_outcomes.csv"
    manifest = a.manifest if a.manifest is not None else HERE / "data" / "manifest.json"
    return max(rc, run_readings(readings, r_out, manifest, http_get, http_get, today, a.dry_run))


if __name__ == "__main__":
    sys.exit(main())
