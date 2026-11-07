"""Discipline rules on the committed call files (README.md, rule 2), checked on
every call from the first:

1. The desk's probability is a two-decimal probability in (0, 1).
2. The market mid was read before the desk wrote: the row's quote hash is in
   data/manifest.json with the same mid, and the quote was fetched on or before
   the call's `made_on`.
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


def manifest_by_book_hash() -> dict[str, dict]:
    path = HERE / "data" / "manifest.json"
    if not path.exists():
        return {}
    return {e["book_sha256"]: e for e in json.loads(path.read_text(encoding="utf-8")) if e.get("book_sha256")}


def test_ledger_columns_are_the_declared_ones():
    with (HERE / "ledger.csv").open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert tuple(header) == L.LEDGER_COLUMNS


def test_desk_p_is_a_two_decimal_probability():
    for call in read("ledger.csv"):
        p = float(call["desk_p"])
        assert 0.0 < p < 1.0, f"{call['id']}: desk_p {call['desk_p']} is not a probability"
        assert call["desk_p"] == f"{p:.2f}", f"{call['id']}: write desk_p with two decimals"


def test_the_market_was_quoted_before_the_desk_wrote():
    quotes = manifest_by_book_hash()
    for call in read("ledger.csv"):
        q = quotes.get(call["quote_sha256"])
        assert q is not None, f"{call['id']}: quote_sha256 not in data/manifest.json; run fetch.py quote first"
        assert q["market_id"] == call["market_id"] and q["yes_token_id"] == call["yes_token_id"]
        assert float(q["market_mid"]) == float(call["market_mid"]), f"{call['id']}: market_mid differs from the quote"
        assert q["fetched_utc"] <= call["made_on"], f"{call['id']}: quoted after the call was made"
        assert q["eligibility"] == "eligible", f"{call['id']}: the market was not eligible ({q['eligibility']})"


def test_every_call_departs_from_the_market_with_a_reason_that_names_it_and_passes_its_method_gate():
    quotes = manifest_by_book_hash()
    for call in read("ledger.csv"):
        method, method_p, lo, hi = L.ledger_method_fields(call)
        fetched = str(quotes.get(call["quote_sha256"], {}).get("fetched_utc", ""))
        v = L.call_violations(float(call["desk_p"]), float(call["market_mid"]), call["basis"],
                              call.get("settles_on", ""), call.get("proposition", ""),
                              method, method_p, lo, hi, r2_in_force(method, fetched))
        assert v == [], f"{call['id']}: {'; '.join(v)}"


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


def test_the_market_rules_were_fetched_with_the_quote():
    quotes = manifest_by_book_hash()
    for call in read("ledger.csv"):
        q = quotes.get(call["quote_sha256"])
        assert q is not None, f"{call['id']}: quote_sha256 not in data/manifest.json"
        assert q.get("description_sha256"), f"{call['id']}: the quote did not record the market's rules (re-quote)"


def test_ids_are_unique_and_outcomes_refer_to_calls():
    ids = [r["id"] for r in read("ledger.csv")]
    assert len(ids) == len(set(ids)), "ledger.csv: duplicate id"
    out = [r["id"] for r in read("outcomes.csv")]
    assert len(out) == len(set(out)), "outcomes.csv: an id scored twice"
    assert set(out) <= set(ids), "outcomes.csv: an id with no call"
