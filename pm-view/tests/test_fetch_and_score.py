"""fetch.py and score.py on fetchers built in memory; every path is passed by
name (tools/check_bound_defaults.py), nothing touches the network or the real
ledger."""
import csv
import json
from datetime import UTC, date, datetime
from pathlib import Path

import fetch as F
import pm_lib
import pytest
import score as S

PM_VIEW = Path(__file__).resolve().parents[1]

AT = datetime(2026, 11, 3, 18, 20, tzinfo=UTC)
GAMMA = {"id": "3215008", "conditionId": "0xcond", "clobTokenIds": '["111", "222"]', "outcomes": '["Yes", "No"]',
         "enableOrderBook": True, "active": True, "closed": False, "acceptingOrders": True,
         "umaResolutionStatus": None, "endDate": "2026-12-09T23:59:00Z", "volumeNum": 2_661_872.09,
         "question": "Fed decision in December?",
         "description": "This market will resolve to \"Yes\" if the upper bound of the target range is raised by 25 bp."}
BOOK = {"bids": [{"price": "0.70", "size": "1"}, {"price": "0.73", "size": "2"}],
        "asks": [{"price": "0.80", "size": "1"}, {"price": "0.74", "size": "2"}]}


def fetcher(bodies: dict[str, object]):
    def get(url: str) -> bytes:
        for key, body in bodies.items():
            if key in url:
                return json.dumps(body).encode()
        raise OSError(f"no body for {url}")
    return get


def test_quote_writes_raw_bodies_hashes_and_the_computed_numbers(tmp_path):
    raw = tmp_path / "raw"
    manifest = tmp_path / "manifest.json"
    g = fetcher({"/markets/3215008": GAMMA})
    b = fetcher({"token_id=111": BOOK})
    rc = F.run(["3215008"], g, b, raw, manifest, dry_run=False, now=lambda: AT)
    assert rc == 0
    entries = json.loads(manifest.read_text())
    assert len(entries) == 1
    e = entries[0]
    assert e["market_mid"] == 0.735 and e["market_spread"] == 0.01 and e["eligibility"] == "eligible"
    assert e["yes_token_id"] == "111" and e["condition_id"] == "0xcond"
    folder = raw / "2026-11-03T182000Z"
    assert (folder / "gamma_3215008.json").exists() and (folder / "book_3215008.json").exists()
    assert len(e["gamma_sha256"]) == 64 and len(e["book_sha256"]) == 64
    assert len(e["description_sha256"]) == 64 and e["description_chars"] == len(GAMMA["description"])
    assert e["question"] == "Fed decision in December?"
    assert "rules_excerpt" not in e  # the rules text is printed, never written to the manifest


def test_quote_prints_the_market_rules_before_the_desk_writes(capsys, tmp_path):
    F.run(["3215008"], fetcher({"/markets/3215008": GAMMA}), fetcher({"token_id=111": BOOK}), tmp_path / "raw",
          tmp_path / "m.json", dry_run=True, now=lambda: AT)
    out = capsys.readouterr().out
    assert "title: 'Fed decision in December?'" in out
    assert "settles on (" in out and "upper bound of the target range is raised by 25 bp" in out


def test_quote_dry_run_writes_nothing_and_a_failed_fetch_is_reported(tmp_path, capsys):
    raw = tmp_path / "raw"
    manifest = tmp_path / "manifest.json"
    rc = F.run(["3215008"], fetcher({"/markets/3215008": GAMMA}), fetcher({"token_id=111": BOOK}), raw, manifest,
               dry_run=True, now=lambda: AT)
    assert rc == 0 and not manifest.exists() and not raw.exists()
    rc = F.run(["999"], fetcher({}), fetcher({}), raw, manifest, dry_run=False, now=lambda: AT)
    assert rc == 1 and "FAILED" in capsys.readouterr().out and not manifest.exists()


def ledger(path, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "made_on", "venue", "market_id", "condition_id", "yes_token_id",
                                           "proposition", "settles_on", "due_on", "market_mid", "market_spread", "volume_usdc",
                                           "desk_p", "basis", "quote_sha256"])
        w.writeheader()
        for r in rows:
            w.writerow(r)


CALL = {"id": "P1-2026-11-03", "made_on": "2026-11-03T18:20Z", "venue": "polymarket", "market_id": "3215008",
        "condition_id": "0xcond", "yes_token_id": "111", "proposition": "25 bp hike on 9 Dec",
        "settles_on": "the upper bound of the target range after the 9 December 2026 meeting is 25 bp higher",
        "due_on": "2026-12-09", "market_mid": "0.735", "market_spread": "0.01", "volume_usdc": "2661872",
        "desk_p": "0.60", "basis": "the market prices 0.735; the bill curve says 0.57", "quote_sha256": "x"}


def resolved(first_wins: bool):
    status = dict(GAMMA, umaResolutionStatus="resolved", closed=True,
                  outcomePrices='["1", "0"]' if first_wins else '["0", "1"]')
    clob = {"tokens": [{"token_id": "111", "winner": first_wins}, {"token_id": "222", "winner": not first_wins}]}
    return fetcher({"/markets/3215008": status}), fetcher({"/markets/0xcond": clob})


def test_score_writes_once_with_both_brier_scores(tmp_path, capsys):
    led, out = tmp_path / "ledger.csv", tmp_path / "outcomes.csv"
    ledger(led, [CALL])
    g, c = resolved(first_wins=True)
    assert S.run(led, out, g, c, date(2026, 12, 10), dry_run=False) == 0
    rows = list(csv.DictReader(out.open()))
    assert len(rows) == 1 and rows[0]["y"] == "1" and rows[0]["kind"] == "first-token"
    assert rows[0]["brier_desk"] == "0.1600" and rows[0]["brier_market"] == "0.0702"
    # A second run refuses the id: nothing appended.
    assert S.run(led, out, g, c, date(2026, 12, 11), dry_run=False) == 0
    assert len(list(csv.DictReader(out.open()))) == 1
    S.write_summary(led, out, tmp_path / "SKILL.md", date(2026, 12, 11))
    text = (tmp_path / "SKILL.md").read_text()
    assert "Scored calls: 1." in text and "Skill (market minus desk): -0.0898." in text and "| YES |" in text


def test_score_waits_for_resolution_and_before_the_due_date(tmp_path, capsys):
    led, out = tmp_path / "ledger.csv", tmp_path / "outcomes.csv"
    ledger(led, [CALL])
    g = fetcher({"/markets/3215008": dict(GAMMA, umaResolutionStatus="proposed", outcomePrices='["1", "0"]')})
    c = fetcher({"/markets/0xcond": {"tokens": [{"token_id": "111", "winner": False}, {"token_id": "222", "winner": False}]}})
    assert S.run(led, out, g, c, date(2026, 12, 10), dry_run=False) == 0
    assert "NOT SCORED P1-2026-11-03: not resolved at the fetch" in capsys.readouterr().out
    assert not out.exists()
    g2, c2 = resolved(first_wins=True)
    assert S.run(led, out, g2, c2, date(2026, 12, 8), dry_run=False) == 0  # not yet due
    assert not out.exists()
    assert S.run(led, out, g2, c2, date(2026, 12, 10), dry_run=True) == 0  # dry run writes nothing
    assert not out.exists()


def test_score_closes_a_fractional_settlement_as_excluded_and_a_failed_fetch_as_retry(tmp_path, capsys):
    led, out = tmp_path / "ledger.csv", tmp_path / "outcomes.csv"
    ledger(led, [CALL])
    g = fetcher({"/markets/3215008": dict(GAMMA, umaResolutionStatus="resolved", outcomePrices='["0.5", "0.5"]')})
    c = fetcher({"/markets/0xcond": {"tokens": [{"token_id": "111", "winner": False}, {"token_id": "222", "winner": False}]}})
    assert S.run(led, out, g, c, date(2026, 12, 10), dry_run=False) == 0
    rows = list(csv.DictReader(out.open()))
    assert rows[0]["kind"] == "settlement not 1/0 or 0/1" and rows[0]["y"] == "" and rows[0]["brier_desk"] == ""
    ledger(led, [dict(CALL, id="P2-2026-11-03", market_id="404")])
    out2 = tmp_path / "outcomes2.csv"
    assert S.run(led, out2, fetcher({}), fetcher({}), date(2026, 12, 10), dry_run=False) == 1
    assert "NOT SCORED P2-2026-11-03: missing or failed fetch" in capsys.readouterr().out
    assert not out2.exists()


def test_quote_of_a_settled_market_comes_from_the_record_not_a_failed_book(tmp_path, capsys):
    """2026-11-06: the 80,000 touch market had resolved on 4 November, its book was gone
    (CLOB 404) and the quote reported a fetch failure, exit 1, record thrown away.  The
    record alone decides a settled market: quoted from it, settlement fields printed as
    the record's own words, gamma body written, no book file, exit 0.  An OPEN market
    whose book fails is still a failure."""
    raw = tmp_path / "raw"
    manifest = tmp_path / "manifest.json"
    settled = dict(GAMMA, id="6507378", closed=True, acceptingOrders=False, umaResolutionStatus="resolved",
                   outcomePrices='["1", "0"]', closedTime="2026-11-04 15:16:24.040261+00")
    rc = F.run(["6507378"], fetcher({"/markets/6507378": settled}), fetcher({}), raw, manifest,
               dry_run=False, now=lambda: AT)
    out = capsys.readouterr().out
    assert rc == 0 and "FAILED" not in out
    assert "not open and accepting orders" in out
    assert "record says closed=True" in out and "umaResolutionStatus='resolved'" in out
    assert "outcomePrices=['1', '0']" in out and "closedTime='2026-11-04 15:16:24.040261+00'" in out
    assert "settles on (" in out  # the rules are still printed
    e = json.loads(manifest.read_text())[0]
    assert e["eligibility"] == "not open and accepting orders" and e["market_mid"] is None
    assert e["settlement"].startswith("record says closed=True") and e["book_sha256"] is None
    folder = raw / "2026-11-03T182000Z"
    assert (folder / "gamma_6507378.json").exists() and not (folder / "book_6507378.json").exists()
    # an open market whose book cannot be read is still a failed quote
    rc = F.run(["3215008"], fetcher({"/markets/3215008": GAMMA}), fetcher({}), raw, manifest,
               dry_run=False, now=lambda: AT)
    assert rc == 1 and "FAILED book fetch failed" in capsys.readouterr().out
    assert len(json.loads(manifest.read_text())) == 1


# --- the settlement-quote path to being due (2026-11-09 06:15Z) --------------------------------------------

CALL_QUOTE = {"market_id": "3215008", "fetched_utc": "2026-11-03T18:20:00Z", "book_sha256": "x"}
SETTLED = {"market_id": "3215008", "fetched_utc": "2026-11-20T06:00:00Z",
           "settlement": "record says closed=True closedTime='2026-11-19 15:00:00+00' umaResolutionStatus='resolved'"}
READING_COLUMNS = ["id", "market_id", "condition_id", "yes_token_id", "method", "method_p", "market_mid",
                   "climatology_p", "due_on", "quote_fetched_utc"]
READING = {"id": "R-2026-11-03-fomc_bills-3215008", "market_id": "3215008", "condition_id": "0xcond",
           "yes_token_id": "111", "method": "fomc_bills", "method_p": "0.58", "market_mid": "0.735",
           "climatology_p": "0.23", "due_on": "2026-12-09", "quote_fetched_utc": "2026-11-03T18:20:00Z"}


def readings_file(path, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=READING_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def test_a_call_is_due_when_a_later_written_quote_carries_the_settlement(tmp_path, capsys):
    """2026-11-09 06:15Z (predictions/POST_MORTEMS.md "A call with no path to being due before its
    scheduled end"): until this date score.py read `due_on` alone for a call while a reading was also
    due on a later written settlement quote, so a call on a market that resolved early would have stood
    "not yet due" in SKILL.md and the due register until its scheduled end.  Now both records take the
    first scoring day from pm_lib.earliest_scoring_day; the call's quote is found by its book hash."""
    led, out = tmp_path / "ledger.csv", tmp_path / "outcomes.csv"
    ledger(led, [CALL])
    g, c = resolved(first_wins=True)
    today = date(2026, 11, 20)  # nineteen days before due_on
    # no settlement quote; a settlement quote of another market; one fetched before the call's own quote
    for entries in ([CALL_QUOTE], [CALL_QUOTE, dict(SETTLED, market_id="999")],
                    [CALL_QUOTE, dict(SETTLED, fetched_utc="2026-11-01T00:00:00Z")]):
        assert S.run(led, out, g, c, today, dry_run=False, manifest_entries=entries) == 0
        assert not out.exists()
        S.write_summary(led, out, tmp_path / "SKILL.md", today, entries)
        assert "| not yet due |" in (tmp_path / "SKILL.md").read_text()
    # the day before the settlement quote: not yet due
    assert S.run(led, out, g, c, date(2026, 11, 19), dry_run=False, manifest_entries=[CALL_QUOTE, SETTLED]) == 0
    assert not out.exists()
    # the settlement quote's own day: scored, with the same row a due_on scoring would have written
    S.write_summary(led, out, tmp_path / "SKILL.md", today, [CALL_QUOTE, SETTLED])
    assert "| due, not resolved |" in (tmp_path / "SKILL.md").read_text()
    assert S.run(led, out, g, c, today, dry_run=False, manifest_entries=[CALL_QUOTE, SETTLED]) == 0
    rows = list(csv.DictReader(out.open()))
    assert len(rows) == 1 and rows[0]["y"] == "1" and rows[0]["scored_on"] == "2026-11-20"
    assert "SCORED P1-2026-11-03: first-token y=1" in capsys.readouterr().out
    # a call with no written quote on record (no book hash matches): any settlement quote of the market counts
    out2 = tmp_path / "outcomes2.csv"
    assert S.run(led, out2, g, c, today, dry_run=False, manifest_entries=[SETTLED]) == 0
    assert len(list(csv.DictReader(out2.open()))) == 1
    # pm_lib: the one function both records and tools/check_due.py read
    assert pm_lib.earliest_scoring_day("2026-12-09", "3215008", "2026-11-03T18:20:00Z", [SETTLED]) == date(2026, 11, 20)
    assert pm_lib.earliest_scoring_day("2026-12-09", "3215008", "2026-11-03T18:20:00Z", [CALL_QUOTE]) == date(2026, 12, 9)
    assert pm_lib.earliest_scoring_day("2026-11-10", "3215008", None, [SETTLED]) == date(2026, 11, 10)
    assert pm_lib.quote_fetched_for_call(CALL, [CALL_QUOTE, SETTLED]) == "2026-11-03T18:20:00Z"
    assert pm_lib.quote_fetched_for_call(CALL, [SETTLED]) is None


def test_a_stamp_in_another_format_refuses_the_row_instead_of_comparing_text(tmp_path, capsys):
    """Candidate (b) of the 2026-11-09 00:15Z run: the manifest's `fetched_utc` was held by nothing and the
    due path compared it with the row's `quote_fetched_utc` as text, so a settlement quote stamped
    `20/11/2026 06:00Z` compared as earlier than every row's quote and the settled market was ignored.
    Now every stamp on the path is parsed in pm_lib.UTC_STAMP_FORMAT; another format refuses the row
    (NOT SCORED, exit 1, nothing written) for a call and for a reading alike."""
    bad = dict(SETTLED, fetched_utc="20/11/2026 06:00Z")
    assert bad["fetched_utc"] < READING["quote_fetched_utc"]  # the text comparison that said "not due"
    with pytest.raises(ValueError, match="fetched_utc of market 3215008 '20/11/2026 06:00Z' is not a UTC stamp"):
        pm_lib.settlement_quote_day("3215008", "2026-11-03T18:20:00Z", [bad])
    with pytest.raises(ValueError, match="the row's quote_fetched_utc '2026-11-03 18:20' is not a UTC stamp"):
        pm_lib.settlement_quote_day("3215008", "2026-11-03 18:20", [SETTLED])
    for other in ("2026-11-20 06:00:00", "2026-11-20T06:00:00.000000+00:00", "2026-11-20T06:00Z", ""):
        with pytest.raises(ValueError):
            pm_lib.parse_utc_stamp(other)
    led, out = tmp_path / "ledger.csv", tmp_path / "outcomes.csv"
    ledger(led, [CALL])
    g, c = resolved(first_wins=True)
    assert S.run(led, out, g, c, date(2026, 11, 20), dry_run=False, manifest_entries=[CALL_QUOTE, bad]) == 1
    assert not out.exists()
    text = capsys.readouterr().out
    assert ("NOT SCORED P1-2026-11-03: data/manifest.json fetched_utc of market 3215008 '20/11/2026 06:00Z' is not a "
            "UTC stamp YYYY-MM-DDTHH:MM:SSZ; fix the stamp") in text
    rd, r_out, m = tmp_path / "readings.csv", tmp_path / "readings_outcomes.csv", tmp_path / "manifest.json"
    readings_file(rd, [READING])
    m.write_text(json.dumps([CALL_QUOTE, bad]))
    assert S.run_readings(rd, r_out, m, g, c, date(2026, 11, 20), dry_run=False) == 1
    assert not r_out.exists()
    assert "READING NOT SCORED R-2026-11-03-fomc_bills-3215008: data/manifest.json fetched_utc" in capsys.readouterr().out
    # with the stamp in the one format the same reading is scored on the settlement quote's day
    m.write_text(json.dumps([CALL_QUOTE, SETTLED]))
    assert S.run_readings(rd, r_out, m, g, c, date(2026, 11, 20), dry_run=False) == 0
    assert len(list(csv.DictReader(r_out.open()))) == 1
    S.write_summary(led, out, tmp_path / "SKILL.md", date(2026, 11, 20), [CALL_QUOTE, bad])
    assert "| not judged: data/manifest.json fetched_utc" in (tmp_path / "SKILL.md").read_text()


def test_the_quote_tool_and_the_committed_manifest_carry_the_one_stamp_format(tmp_path):
    """fetch.py writes `fetched_utc` in pm_lib.UTC_STAMP_FORMAT, the format the due path parses; every
    entry of the committed data/manifest.json parses in it (the committed-file check for the stamp)."""
    raw, manifest = tmp_path / "raw", tmp_path / "manifest.json"
    assert F.run(["3215008"], fetcher({"/markets/3215008": GAMMA}), fetcher({"token_id=111": BOOK}), raw, manifest,
                 dry_run=False, now=lambda: AT) == 0
    e = json.loads(manifest.read_text())[0]
    assert e["fetched_utc"] == "2026-11-03T18:20:00Z" == AT.strftime(pm_lib.UTC_STAMP_FORMAT)
    assert pm_lib.parse_utc_stamp(e["fetched_utc"]) == AT
    committed = json.loads((PM_VIEW / "data" / "manifest.json").read_text(encoding="utf-8"))
    assert committed, "the committed manifest is empty"
    for entry in committed:
        pm_lib.parse_utc_stamp(entry.get("fetched_utc"), f"committed manifest entry for market {entry.get('market_id')}")
