"""The quote's scheduled end is parsed, and `due_on` is its UTC day: the search kept as a test.

2026-11-11 18:15Z, predictions/POST_MORTEMS.md "A stamp under another name": `due_on` was
`str(quote["end_date"])[:10]` in both writers (readings.py add, ledger.py add) and both gates
agreed with the slice, so on 45147b7 an end in a zone other than Z gave a wrong day, a basic-format
end gave `20261201T0`, `01/12/2026 05:00Z` gave `01/12/2026` and a missing end gave the word `None`,
each admitted by the readings gate with no refusal and by the ledger gate with none about the day.
tools/check_stamp_compares.py never saw the four sites because the key does not end in `_utc`.
Now pm_lib.parse_scheduled_end is the one parser (fetch-time eligibility, the writers, the gates),
`scheduled_end_day` is the day both writers write, and a quote whose end does not parse refuses the
row `[gate:utc-stamp]` / `[reading:utc-stamp]`.
"""
import csv
from datetime import UTC, datetime
from pathlib import Path

import ledger as G
import pm_lib as L
import pytest
import readings as R

HERE = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 11, 6, 7, 0, tzinfo=UTC)
TOUCH_QUOTE = {"fetched_utc": "2026-11-06T06:16:38Z", "market_id": "6507380", "condition_id": "0xc3e5",
               "yes_token_id": "967", "gamma_sha256": "ab" * 32, "book_sha256": "ef" * 32, "market_mid": 0.925,
               "market_spread": 0.01, "volume_usdc": 250000.0, "end_date": "2026-12-01T05:00:00Z",
               "eligibility": "eligible", "description_sha256": "cd" * 32}
HIKE_QUOTE = {"fetched_utc": "2026-11-06T06:16:37Z", "market_id": "3215008", "condition_id": "0xa1b2",
              "yes_token_id": "123", "gamma_sha256": "ba" * 32, "book_sha256": "fe" * 32, "market_mid": 0.45,
              "market_spread": 0.01, "volume_usdc": 900000.0, "end_date": "2026-12-09T23:59:00Z",
              "eligibility": "eligible", "description_sha256": "dc" * 32}
SETTLES = "the upper bound of the target range after the 9 December 2026 meeting is 25 bp higher"
BASIS = "the market prices 0.45; the bills price 0.99 after the November prints"

# end_date as the manifest might carry it -> the due day both writers write, and the tag the gates give
CASES = [
    ("2026-12-01T05:00:00Z", "2026-12-01", None),                 # Gamma's shape today
    ("2026-12-01 05:00:00+00:00", "2026-12-01", None),            # another ISO 8601 spelling of the same time
    ("2026-12-01T03:00:00+05:00", "2026-11-30", None),            # the UTC day, not the first ten characters
    ("20261201T050000Z", "2026-12-01", None),                     # basic format: the slice gave 20261201T0
    ("01/12/2026 05:00Z", "", "utc-stamp"),                       # not ISO 8601: refused by name
    ("2026-12-01T05:00:00", "", "utc-stamp"),                     # no zone: refused, not a TypeError
    (None, "", "utc-stamp"),                                      # missing: the slice gave the word None
]


def history() -> list[dict]:
    with (HERE / L.CALIBRATION_HISTORY).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def tags(sentences: list[str]) -> set[str]:
    return {s.split("]")[0].lstrip("[").split(":")[1] for s in sentences if s.startswith("[")}


@pytest.mark.parametrize(("end", "day", "tag"), CASES)
def test_scheduled_end_day_is_the_parsed_ends_utc_day(end, day, tag):
    assert L.scheduled_end_day(end) == day
    assert (L.scheduled_end_violation(end) is None) == (tag is None)


@pytest.mark.parametrize(("end", "day", "tag"), CASES)
def test_the_readings_writer_and_gate_agree_on_the_parsed_day(end, day, tag):
    quote = dict(TOUCH_QUOTE, end_date=end)
    sha = R.calibration_sha256("btc_touch", HERE)
    row, _ = R.build_row(quote, "6507380", "btc_touch", 0.876, 0.80, 0.95, None,
                         "BTC at or below 75,000 in November", "PM_VIEW.md 2026-11-06", history(), sha, NOW)
    assert row["due_on"] == day
    got = tags(L.reading_row_violations(row, quote, history(), (), sha))
    assert ("utc-stamp" in got) == (tag == "utc-stamp")
    assert "due-on-scheduled-end" not in got
    if tag is None:
        # a row typed with the slice's day on an end in another zone is refused by the gate
        sliced = dict(row, due_on=str(end)[:10])
        got = tags(L.reading_row_violations(sliced, quote, history(), (), sha))
        assert ("due-on-scheduled-end" in got) == (str(end)[:10] != day)


@pytest.mark.parametrize(("end", "day", "tag"), CASES)
def test_the_ledger_writer_and_gate_agree_on_the_parsed_day(end, day, tag):
    quote = dict(HIKE_QUOTE, end_date=end)
    call = G.build_row(quote, "3215008", "0.90", "stated", None, None, None, "a 25 bp hike on 9 December",
                       SETTLES, BASIS)
    assert call["due_on"] == day
    got = tags(L.ledger_row_violations(call, quote, history(), (), "2026-11-06T07:00:00Z", None))
    assert ("utc-stamp" in got) == (tag == "utc-stamp")
    assert "due-on-scheduled-end" not in got
    if tag is None:
        sliced = dict(call, due_on=str(end)[:10])
        got = tags(L.ledger_row_violations(sliced, quote, history(), (), "2026-11-06T07:00:00Z", None))
        assert ("due-on-scheduled-end" in got) == (str(end)[:10] != day)


def test_record_eligibility_reads_the_end_through_the_same_parser():
    row = dict(outcomes='["Yes","No"]', clobTokenIds='["1","2"]', enableOrderBook=True, active=True, closed=False,
               acceptingOrders=True)
    at = datetime(2026, 11, 30, 23, 0, tzinfo=UTC)
    assert L.record_eligibility(dict(row, endDate="2026-12-01T05:00:00Z"), at) is None
    assert L.record_eligibility(dict(row, endDate="2026-12-01T03:00:00+05:00"), at) == "past the scheduled end"  # 22:00Z
    assert L.record_eligibility(dict(row, endDate="2026-12-01T05:00:00"), at) == "no scheduled end"  # no zone: not a TypeError
    assert L.record_eligibility(dict(row, endDate="01/12/2026 05:00Z"), at) == "no scheduled end"
    assert L.record_eligibility(dict(row, endDate=None), at) == "no scheduled end"
    assert L.record_eligibility(row, at) == "no scheduled end"


def test_the_stamp_keys_name_the_fields_the_folder_reads():
    for key in ("end_date", "endDate", "closedTime", "createdAt"):
        assert key in L.STAMP_KEYS
    assert not any(k.endswith("_utc") for k in L.STAMP_KEYS), "a _utc name is tainted by its suffix already"
