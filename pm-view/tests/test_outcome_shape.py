"""The two scored records, `outcomes.csv` and `readings_outcomes.csv`, held at their readers
(2026-11-10 06:15Z, predictions/POST_MORTEMS.md "A score that nothing read back").

The column search of that run, kept as a test: a clean row of each record is built by
score.py itself on synthetic resolved records, each column is altered in turn, and
`pm_lib.outcome_row_violations` must refuse every alteration with a sentence naming the
id and the column.  Then the readers: score.run / run_readings refuse a malformed record
and write nothing, write_summary refuses, the summaries refuse a y or a probability they
cannot name, the writer refuses its own malformed row, and the committed files pass
through the reader against the committed ledger and readings record.
"""
import csv
import json
import sys
from datetime import date
from pathlib import Path

import pm_lib as L
import pytest
import score as S

HERE = Path(__file__).resolve().parents[1]
STUDY_013 = HERE.parent / "research" / "013-polymarket-calibration-forward"
if str(STUDY_013) not in sys.path:
    sys.path.insert(0, str(STUDY_013))
from src import outcome as O  # noqa: E402

GAMMA = {"id": "3215008", "conditionId": "0xcond", "clobTokenIds": '["111", "222"]', "outcomes": '["Yes", "No"]',
         "umaResolutionStatus": "resolved", "closed": True, "outcomePrices": '["1", "0"]'}
CLOB = {"tokens": [{"token_id": "111", "winner": True}, {"token_id": "222", "winner": False}]}
CALL = {"id": "P1-2026-11-03", "made_on": "2026-11-03", "venue": "polymarket", "market_id": "3215008",
        "condition_id": "0xcond", "yes_token_id": "111", "proposition": "Hike of 25 bp on 9 December",
        "settles_on": "resolves YES on a 25 bp hike at the 9 December meeting", "due_on": "2026-12-09",
        "market_mid": "0.735", "market_spread": "0.010", "volume_usdc": "500000", "desk_p": "0.60",
        "method": "stated", "method_p": "", "range_lo": "", "range_hi": "", "basis": "bills", "quote_sha256": "a" * 64}
READING = {"id": "R-2026-11-06-fomc_bills-3215008", "made_on": "2026-11-06", "recorded_utc": "2026-11-06T18:22:09Z",
           "venue": "polymarket", "market_id": "3215008", "condition_id": "0xcond", "yes_token_id": "111",
           "proposition": "Hike of 25 bp on 9 December", "method": "fomc_bills", "method_p": "0.580", "range_lo": "0.220",
           "range_hi": "0.790", "market_mid": "0.735", "climatology_p": "0.230", "due_on": "2026-12-09", "gate": "range",
           "quote_fetched_utc": "2026-11-06T06:16:37Z", "quote_sha256": "b" * 64, "source": "PM_VIEW.md"}


def fetcher(table):
    def f(url):
        for k, v in table.items():
            if url.endswith(k):
                return json.dumps(v).encode()
        raise OSError(f"no record for {url}")
    return f


def write(path, columns, rows):
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(columns))
        w.writeheader()
        for r in rows:
            w.writerow({k: v for k, v in r.items() if k in columns})


def rows_of(path):
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture
def clean(tmp_path):
    """(outcome row, reading outcome row) as score.py writes them on a market that resolved YES."""
    led, out = tmp_path / "ledger.csv", tmp_path / "outcomes.csv"
    rd, r_out, m = tmp_path / "readings.csv", tmp_path / "readings_outcomes.csv", tmp_path / "manifest.json"
    write(led, L.LEDGER_COLUMNS, [CALL])
    write(rd, L.READING_COLUMNS, [READING])
    m.write_text("[]")
    g, c = fetcher({"/markets/3215008": GAMMA}), fetcher({"/markets/0xcond": CLOB})
    assert S.run(led, out, g, c, date(2026, 12, 10), dry_run=False) == 0
    assert S.run_readings(rd, r_out, m, g, c, date(2026, 12, 10), dry_run=False) == 0
    return rows_of(out)[0], rows_of(r_out)[0]


# --- the kinds are Study 013's words ---------------------------------------------------------------

def test_the_closed_set_of_kinds_is_what_study_013_writes():
    assert L.SCORED_KINDS == (O.FIRST, O.SECOND)
    assert L.EXCLUDED_KINDS == (O.NOT_BINARY_SETTLEMENT, O.DISAGREEMENT)
    assert O.NOT_RESOLVED not in L.OUTCOME_KINDS and O.UNFETCHED not in L.OUTCOME_KINDS  # never written


# --- the search, kept ------------------------------------------------------------------------------

ALTER = {
    "id": [lambda r: dict(r, id=r["id"] + " "), lambda r: dict(r, id="P9-2026-11-03"), lambda r: dict(r, id="")],
    "scored_on": [lambda r: dict(r, scored_on="2026-10-01"), lambda r: dict(r, scored_on="10/12/2026"), lambda r: dict(r, scored_on="")],
    "kind": [lambda r: dict(r, kind="resolved"), lambda r: dict(r, kind="not resolved at the fetch"), lambda r: dict(r, kind="")],
    "y": [lambda r: dict(r, y="yes"), lambda r: dict(r, y="2"), lambda r: dict(r, y="0"), lambda r: dict(r, y="")],
    "desk_p": [lambda r: dict(r, desk_p="1.5"), lambda r: dict(r, desk_p="0.90"), lambda r: dict(r, desk_p="")],
    "method_p": [lambda r: dict(r, method_p="1.5"), lambda r: dict(r, method_p="0.900"), lambda r: dict(r, method_p="")],
    "market_mid": [lambda r: dict(r, market_mid="1.5"), lambda r: dict(r, market_mid="0.100"), lambda r: dict(r, market_mid="")],
    "climatology_p": [lambda r: dict(r, climatology_p="1.5"), lambda r: dict(r, climatology_p=""), lambda r: dict(r, climatology_p="0.5")],
    "brier_desk": [lambda r: dict(r, brier_desk="9.9999"), lambda r: dict(r, brier_desk=""), lambda r: dict(r, brier_desk="0.16")],
    "brier_method": [lambda r: dict(r, brier_method="9.9999"), lambda r: dict(r, brier_method="")],
    "brier_market": [lambda r: dict(r, brier_market="9.9999"), lambda r: dict(r, brier_market="")],
    "brier_climatology": [lambda r: dict(r, brier_climatology="9.9999"), lambda r: dict(r, brier_climatology="")],
    "gamma_sha256": [lambda r: dict(r, gamma_sha256="abc"), lambda r: dict(r, gamma_sha256=""), lambda r: dict(r, gamma_sha256="A" * 64)],
    "clob_sha256": [lambda r: dict(r, clob_sha256="abc"), lambda r: dict(r, clob_sha256="")],
}


@pytest.mark.parametrize("which", ["outcomes", "readings_outcomes"])
def test_every_column_of_both_records_is_held_against_the_row_it_scores(clean, which):
    row, record, source = (clean[0], L.OUTCOME_RECORD, CALL) if which == "outcomes" else (clean[1], L.READING_OUTCOME_RECORD, READING)
    assert tuple(row) == record.columns
    assert L.outcome_row_violations(row, source, record) == []
    for column in record.columns:
        for alter in ALTER[column]:
            bad = alter(row)
            problems = L.outcome_row_violations(bad, source, record)
            assert problems, (column, bad[column])
            named = [p for p in problems if column in p and (row["id"] in p or bad["id"].strip() == "")]
            assert named, (column, bad[column], problems)
    # a column missing or one too many, and the row of the wrong record
    assert any("columns are not" in p for p in L.outcome_row_violations({k: v for k, v in row.items() if k != "kind"}, source, record))
    assert any("columns are not" in p for p in L.outcome_row_violations({**row, "note": "x"}, source, record))
    other = L.READING_OUTCOME_RECORD if which == "outcomes" else L.OUTCOME_RECORD
    assert any("columns are not" in p for p in L.outcome_row_violations(row, source, other))


def test_an_excluded_kind_has_an_empty_y_and_empty_brier_columns(clean):
    row = dict(clean[0], kind=O.NOT_BINARY_SETTLEMENT, y="", brier_desk="", brier_market="")
    assert L.outcome_row_violations(row, CALL, L.OUTCOME_RECORD) == []
    assert any("y '1' is not ''" in p for p in L.outcome_row_violations(dict(row, y="1"), CALL, L.OUTCOME_RECORD))
    assert any("brier_desk '0.1600' must be empty" in p
               for p in L.outcome_row_violations(dict(row, brier_desk="0.1600"), CALL, L.OUTCOME_RECORD))


def test_an_optional_probability_is_empty_exactly_when_the_source_row_is(clean):
    row = clean[1]
    src = dict(READING, climatology_p="")
    assert L.outcome_row_violations(dict(row, climatology_p="", brier_climatology=""), src, L.READING_OUTCOME_RECORD) == []
    problems = L.outcome_row_violations(row, src, L.READING_OUTCOME_RECORD)
    assert any("climatology_p '0.230' is not the readings.csv row's ('')" in p for p in problems)


def test_the_file_reader_refuses_a_repeated_id_and_a_stray_id(clean, tmp_path):
    row = clean[0]
    out = tmp_path / "o.csv"
    write(out, L.OUTCOME_COLUMNS, [row, dict(row, desk_p="0.90")])
    with pytest.raises(ValueError, match="repeated id in outcomes.csv"):
        L.read_scored(out, [CALL], L.OUTCOME_RECORD)
    write(out, L.OUTCOME_COLUMNS, [dict(row, id="P9-2026-11-03")])
    with pytest.raises(ValueError, match="P9-2026-11-03: id is not a row of ledger.csv"):
        L.read_scored(out, [CALL], L.OUTCOME_RECORD)
    assert L.read_scored(tmp_path / "absent.csv", [CALL], L.OUTCOME_RECORD) == []
    write(out, L.OUTCOME_COLUMNS, [row])
    assert L.read_scored(out, [CALL], L.OUTCOME_RECORD) == [row]


# --- the readers -----------------------------------------------------------------------------------

def test_run_refuses_a_malformed_record_and_writes_nothing(clean, tmp_path, capsys):
    """On fc7a3a8 an id with a trailing space had the call scored again into a second row."""
    led, out = tmp_path / "l.csv", tmp_path / "o.csv"
    write(led, L.LEDGER_COLUMNS, [CALL])
    write(out, L.OUTCOME_COLUMNS, [dict(clean[0], id=clean[0]["id"] + " ")])
    before = out.read_bytes()
    g, c = fetcher({"/markets/3215008": GAMMA}), fetcher({"/markets/0xcond": CLOB})
    assert S.run(led, out, g, c, date(2026, 12, 11), dry_run=False) == 1
    text = capsys.readouterr().out
    assert "NOT SCORED: outcomes.csv refused, fix the record" in text and "is not a row of ledger.csv" in text
    assert out.read_bytes() == before
    with pytest.raises(ValueError, match="outcomes.csv refused"):
        S.write_summary(led, out, tmp_path / "SKILL.md", date(2026, 12, 11))
    assert S.main(["--summary", "--ledger", str(led), "--outcomes", str(out), "--skill", str(tmp_path / "SKILL.md"),
                   "--manifest", str(tmp_path / "none.json")]) == 1
    assert not (tmp_path / "SKILL.md").exists()


def test_run_readings_refuses_a_malformed_record_and_writes_nothing(clean, tmp_path, capsys):
    rd, out, m = tmp_path / "r.csv", tmp_path / "ro.csv", tmp_path / "m.json"
    write(rd, L.READING_COLUMNS, [READING])
    m.write_text("[]")
    write(out, L.READING_OUTCOME_COLUMNS, [dict(clean[1], kind="not resolved at the fetch", y="", brier_method="",
                                                brier_market="", brier_climatology="")])
    before = out.read_bytes()
    g, c = fetcher({"/markets/3215008": GAMMA}), fetcher({"/markets/0xcond": CLOB})
    assert S.run_readings(rd, out, m, g, c, date(2026, 12, 11), dry_run=False) == 1
    text = capsys.readouterr().out
    assert "READING NOT SCORED: readings_outcomes.csv refused" in text and "kind 'not resolved at the fetch' is not one of" in text
    assert out.read_bytes() == before
    led = tmp_path / "l.csv"
    write(led, L.LEDGER_COLUMNS, [])
    with pytest.raises(ValueError, match="readings_outcomes.csv refused"):
        S.readings_lines(rd, out, date(2026, 12, 11))


def test_the_summaries_refuse_a_y_or_a_probability_they_cannot_name(clean):
    for bad in (dict(clean[0], y="yes"), dict(clean[0], y="2")):
        with pytest.raises(ValueError, match=r"P1-2026-11-03: y .* is not 0 or 1"):
            L.skill_summary([bad])
    with pytest.raises(ValueError, match=r"P1-2026-11-03: desk_p '1.5' is not a decimal"):
        L.skill_summary([dict(clean[0], desk_p="1.5")])
    merged = {**READING, **clean[1]}
    with pytest.raises(ValueError, match=r"R-2026-11-06-fomc_bills-3215008: y '2' is not 0 or 1"):
        L.reading_summary([dict(merged, y="2")])
    with pytest.raises(ValueError, match=r"climatology_p '1.5' is not a decimal"):
        L.reading_summary([dict(merged, climatology_p="1.5")])
    assert L.skill_summary([clean[0]])["n"] == 1


def test_the_writer_refuses_its_own_malformed_row(clean, tmp_path):
    out = tmp_path / "o.csv"
    with pytest.raises(ValueError, match="the row built for 'P1-2026-11-03' is refused, nothing written"):
        S.append_scored(out, L.OUTCOME_RECORD, dict(clean[0], desk_p="0.90"), [CALL], [])
    assert not out.exists()
    with pytest.raises(ValueError, match="repeated id"):
        S.append_scored(out, L.OUTCOME_RECORD, clean[0], [CALL], [clean[0]])
    assert not out.exists()
    S.append_scored(out, L.OUTCOME_RECORD, clean[0], [CALL], [])
    assert rows_of(out) == [clean[0]]


# --- the committed record ----------------------------------------------------------------------------

def read(name: str) -> list[dict]:
    path = HERE / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_the_committed_scored_records_pass_the_reader_against_their_sources():
    outcomes = L.read_scored(HERE / "outcomes.csv", read("ledger.csv"), L.OUTCOME_RECORD)
    readings = L.read_scored(HERE / "readings_outcomes.csv", read("readings.csv"), L.READING_OUTCOME_RECORD)
    assert all(tuple(r) == L.OUTCOME_COLUMNS for r in outcomes)
    assert all(tuple(r) == L.READING_OUTCOME_COLUMNS for r in readings)
