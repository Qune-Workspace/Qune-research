"""Discipline rules on the committed call files (README.md, rule 2), checked on
every call from the first:

1. The desk's probability is a two-decimal probability in (0, 1).
2. The market mid was read before the desk wrote: the row's quote hash is in
   data/manifest.json with the same mid, and the quote was fetched on or before
   the call's `made_on`.
3. A call departs from the market by at least MIN_DEPARTURE, and its basis names
   the market's number and what it is missing (the word 'market' appears).
4. Ids are unique; the ledger's columns are the ones pm_lib declares.
"""
import csv
import json
from pathlib import Path

import pm_lib as L

HERE = Path(__file__).resolve().parent.parent


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


def test_every_call_departs_from_the_market_with_a_reason_that_names_it():
    for call in read("ledger.csv"):
        v = L.call_violations(float(call["desk_p"]), float(call["market_mid"]), call["basis"])
        assert v == [], f"{call['id']}: {'; '.join(v)}"


def test_ids_are_unique_and_outcomes_refer_to_calls():
    ids = [r["id"] for r in read("ledger.csv")]
    assert len(ids) == len(set(ids)), "ledger.csv: duplicate id"
    out = [r["id"] for r in read("outcomes.csv")]
    assert len(out) == len(set(out)), "outcomes.csv: an id scored twice"
    assert set(out) <= set(ids), "outcomes.csv: an id with no call"
