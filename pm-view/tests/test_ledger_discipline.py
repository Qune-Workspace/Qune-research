"""Discipline rules on the committed call files (README.md, rule 2), checked on
every call from the first:

1. The desk's probability is a two-decimal probability in (0, 1).
2. The market mid was read before the desk wrote: the row's quote hash is in
   data/manifest.json with the same mid, and the call was made on the quote's
   day (pm_lib.quote_timing_violations, `[gate:made-on-quote-day]`; 2026-11-07
   12:15Z, predictions/POST_MORTEMS.md "A timestamp compared with a date":
   until then this test compared the quote's `fetched_utc` with `made_on` as
   strings, which refused a call made on its quote's day and passed one
   written the next day from a stale quote).
3. A call departs from the market by at least MIN_DEPARTURE, and its basis names
   the market's number and what it is missing (the word 'market' appears).
4. Ids are unique; the ledger's columns are the ones pm_lib declares.
5. (2026-11-04, predictions/POST_MORTEMS.md "PM view 2026-11-03") The call's
   `settles_on` restates the market's own resolution rule, with its source and
   the level or date, and is not the title; and the quote it rests on recorded
   the description's hash, so the rule was fetched before the desk wrote.
6. (2026-11-06, predictions/POST_MORTEMS.md "A call gate that knew one rule of
   three") The call names its method; a method call carries the method's
   reading and range, the method's committed calibration says R2 true, the
   market mid lies outside the range, a touch reading is above the market, and
   the desk's probability sits on the reading's side of the market
   (pm_lib.method_violations).  Until this rule the committed ledger was held
   to the departure and `settles_on` only, while the R2 gate and the range rule
   lived in two printers that never wrote a call.
7. (2026-11-07 18:15Z, predictions/POST_MORTEMS.md "A gate that only a test
   applied") A call enters the ledger only through `ledger.py add`, which
   applies pm_lib.ledger_row_violations at admission; this file applies the
   same function to every committed row, and rules 1, 2, 3 and 5 above are
   checks of that function (one call per market and day among them), not
   assertions of this file's own.
8. (2026-11-08 12:15Z, predictions/POST_MORTEMS.md "Five columns the gate never
   read") Every column the tool copies from the quote or sets itself is held
   by the gate: `due_on` the quote's scheduled end, `market_spread` and
   `volume_usdc` the quote's, the id and venue by their rules.  Until then a
   mechanical search found five of eleven such columns admitted at any value by
   this file's gate; tests/test_ledger.py keeps the search.
"""
import csv
import json
from pathlib import Path

import pm_lib as L

HERE = Path(__file__).resolve().parent.parent


def calibration_gates() -> dict[str, bool | None]:
    """R2 per method from the committed calibration files as they stand."""
    out: dict[str, bool | None] = {}
    for method, (rel, _key) in L.METHOD_CALIBRATION.items():
        path = HERE / rel
        cal = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        out[method] = L.method_gate(method, cal)
    return out


def r2_in_force(method: str | None, at_utc: str) -> bool | None:
    """R2 of the method's calibration as on record (data/calibration_history.csv) at `at_utc`: a call
    is judged under the calibration in force when its quote was fetched, never under a later re-run
    (2026-11-07 06:15Z, predictions/POST_MORTEMS.md "A gate column judged against today's calibration")."""
    return L.history_r2(L.calibration_in_force(read(L.CALIBRATION_HISTORY), method or "", at_utc))


def read(name: str) -> list[dict]:
    path = HERE / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_ledger_columns_are_the_declared_ones():
    with (HERE / "ledger.csv").open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert tuple(header) == L.LEDGER_COLUMNS


def test_every_committed_call_passes_the_admission_gate():
    # (2026-11-07 18:15Z, predictions/POST_MORTEMS.md "A gate that only a test applied") the one copy of
    # rules 1, 2, 3 and 5 above, pm_lib.ledger_row_violations, which ledger.py add applies at admission;
    # until then this file held the two-decimal desk number, the quote, the mid, the eligibility and the
    # rules' hash in its own assertions, outside the gate and its tags
    manifest = json.loads((HERE / "data" / "manifest.json").read_text(encoding="utf-8"))
    v = L.ledger_file_violations(read("ledger.csv"), manifest, read(L.CALIBRATION_HISTORY))
    assert v == [], "; ".join(v)


def test_the_committed_calibration_files_carry_the_gate_the_ledger_reads():
    # Both method calibrations are committed and readable; the gate is a bool, never a guess.
    gates = calibration_gates()
    assert set(gates) == {"fomc_bills", "btc_touch"}
    for method, r2 in gates.items():
        assert isinstance(r2, bool), f"{method}: calibration missing or without its R2 key"
    # the pin "as written on 2026-11-05: the bills pass, the touch formula does not" moved on 2026-11-07 to the
    # first lines of data/calibration_history.csv (tests/test_readings.py), so a correct re-run that flips R2
    # needs no edit here; what stays is that each file as committed is its method's latest line
    for method, r2 in gates.items():
        assert r2_in_force(method, "9999") is r2, f"{method}: the committed calibration is not on record"


def test_ids_are_unique_and_outcomes_refer_to_calls():
    ids = [r["id"] for r in read("ledger.csv")]
    assert len(ids) == len(set(ids)), "ledger.csv: duplicate id"
    out = [r["id"] for r in read("outcomes.csv")]
    assert len(out) == len(set(out)), "outcomes.csv: an id scored twice"
    assert set(out) <= set(ids), "outcomes.csv: an id with no call"
