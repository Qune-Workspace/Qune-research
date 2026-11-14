"""The readings record (readings.py, score.py, pm_lib.reading_violations), added
2026-11-06 18:15Z (predictions/POST_MORTEMS.md "A week of readings that no
record could score"): the gate on synthetic rows, the admission tool against a
manifest built in memory, the scorer on fetchers built in memory, and the
committed readings.csv held to the same gate and to data/manifest.json.  Every
path is passed by name; nothing touches the network or the real files except
the read-only checks on the committed record."""
import csv
import json
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pm_lib as L
import readings as R
import score as S

HERE = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 11, 6, 18, 30, tzinfo=UTC)
QUOTE = {"fetched_utc": "2026-11-06T06:16:38Z", "market_id": "6507380", "condition_id": "0xc3e5",
         "yes_token_id": "967", "gamma_sha256": "ab" * 32, "book_sha256": "cd" * 32, "market_mid": 0.925,
         "end_date": "2026-12-01T05:00:00Z", "eligibility": "eligible", "question": "Will Bitcoin dip to $75,000?"}
SETTLED = {"fetched_utc": "2026-11-06T06:20:45Z", "market_id": "6507378", "condition_id": "0x0c0e",
           "yes_token_id": "113", "gamma_sha256": "ef" * 32, "book_sha256": None, "market_mid": None,
           "end_date": "2026-12-01T05:00:00Z", "eligibility": "not open and accepting orders",
           "settlement": "record says closed=True ..."}


def ns(**kw) -> SimpleNamespace:
    base = dict(market_id="6507380", quote="2026-11-06T06:16:38Z", method="btc_touch", method_p=0.876,
                range_lo=0.876, range_hi=0.886, climatology_p=0.690, proposition="Bitcoin dips to 75,000 in November",
                source="PM_VIEW.md 2026-11-06", dry_run=False)
    base.update(kw)
    return SimpleNamespace(**base)


def write_manifest(tmp_path: Path, entries: list[dict]) -> Path:
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    m = data / "manifest.json"
    m.write_text(json.dumps(entries))
    # the method calibration files the gate column reads, as committed today (touch R2 false, bills R2 true),
    # each put on record in data/calibration_history.csv before NOW
    (data / "calibration.json").write_text(json.dumps({"rules": {"R2_method_is_a_basis_for_a_call": False}}))
    (data / "fomc_calibration.json").write_text(json.dumps({"rules": {"R2_basis_for_a_call": True}}))
    for method in ("btc_touch", "fomc_bills"):
        assert R.record_calibration(method, "test", tmp_path, datetime(2026, 11, 5, 12, 0, tzinfo=UTC)) == 0
    return m


def history(tmp_path: Path) -> list[dict]:
    return S.read_csv(tmp_path / L.CALIBRATION_HISTORY)


# --- the gate on synthetic rows -----------------------------------------------

def test_gate_admits_a_reading_on_a_written_eligible_quote_with_the_quotes_mid():
    v = L.reading_violations("btc_touch", 0.876, 0.876, 0.886, 0.925, 0.690, QUOTE, "2026-11-06", "2026-12-01")
    assert v == []


def test_gate_refuses_each_rule_once():
    args = ("btc_touch", 0.876, 0.876, 0.886, 0.925, 0.690, QUOTE, "2026-11-06", "2026-12-01")
    def with_(**kw):
        names = ("method", "method_p", "range_lo", "range_hi", "market_mid", "climatology_p", "quote", "made_on", "due_on")
        d = dict(zip(names, args, strict=True))
        d.update(kw)
        return L.reading_violations(**d)
    assert any("method must be" in x for x in with_(method="stated"))
    assert any("required" in x for x in with_(range_lo=None))
    assert any("bracket" in x for x in with_(range_lo=0.9))
    assert any("not a probability" in x for x in with_(market_mid=1.0))
    assert any("climatology_p" in x for x in with_(climatology_p=1.2))
    assert any("no written quote" in x for x in with_(quote=None))
    assert any("copy the mid" in x for x in with_(market_mid=0.9))
    assert any("not eligible" in x for x in with_(quote=SETTLED, market_mid=0.5))
    assert any("day of its quote" in x for x in with_(made_on="2026-11-07"))
    assert any("scheduled end" in x for x in with_(due_on="2026-12-09"))


# --- the admission tool ------------------------------------------------------

def test_add_builds_the_row_from_the_manifest_and_records_the_call_gates_refusals(tmp_path, capsys):
    m = write_manifest(tmp_path, [QUOTE, SETTLED])
    out = tmp_path / "readings.csv"
    assert R.add(ns(), m, out, NOW) == 0
    rows = list(csv.DictReader(out.open()))
    assert len(rows) == 1
    r = rows[0]
    assert tuple(rows[0].keys()) == L.READING_COLUMNS
    assert r["id"] == "R-2026-11-06-btc_touch-6507380" and r["made_on"] == "2026-11-06"
    assert r["condition_id"] == "0xc3e5" and r["yes_token_id"] == "967" and r["quote_sha256"] == "ab" * 32
    assert r["market_mid"] == "0.925" and r["due_on"] == "2026-12-01" and r["recorded_utc"] == "2026-11-06T18:30:00Z"
    # why it was not a call, from the one copy of the call gate: R2 false, inside no; below the market; departure
    assert set(r["gate"].split(";")) == {"calibrated", "touch-below", "method-departure"}
    assert "ADMITTED" in capsys.readouterr().out
    # the same reading twice is refused
    assert R.add(ns(), m, out, NOW) == 1
    assert "already on the record" in capsys.readouterr().out
    assert len(list(csv.DictReader(out.open()))) == 1


def test_add_refuses_a_reading_whose_quote_was_a_dry_run(tmp_path, capsys):
    m = write_manifest(tmp_path, [QUOTE])
    out = tmp_path / "readings.csv"
    assert R.add(ns(quote="2026-11-04T12:25:26Z"), m, out, NOW) == 1
    msg = capsys.readouterr().out
    assert "REFUSED" in msg and "no manifest entry" in msg and "--dry-run" in msg
    assert not out.exists()


def test_add_refuses_a_reading_on_a_market_the_record_had_settled(tmp_path, capsys):
    m = write_manifest(tmp_path, [QUOTE, SETTLED])
    out = tmp_path / "readings.csv"
    assert R.add(ns(market_id="6507378", quote="2026-11-06T06:20:45Z", method_p=0.607, range_lo=0.607,
                    range_hi=0.705), m, out, NOW) == 1
    assert "not eligible" in capsys.readouterr().out
    assert not out.exists()


def test_add_dry_run_writes_nothing(tmp_path):
    m = write_manifest(tmp_path, [QUOTE])
    out = tmp_path / "readings.csv"
    assert R.add(ns(dry_run=True), m, out, NOW) == 0
    assert not out.exists()


def test_add_refuses_while_a_rerun_calibration_is_not_on_record_and_record_calibration_puts_it_there(tmp_path, capsys):
    # 2026-11-07 06:15Z: a re-run of calibrate.py that flips R2 overwrites the file; until its dated line is
    # in data/calibration_history.csv no reading is admitted under it, and the line is appended once
    m = write_manifest(tmp_path, [QUOTE])
    out = tmp_path / "readings.csv"
    (tmp_path / "data" / "calibration.json").write_text(json.dumps({"rules": {"R2_method_is_a_basis_for_a_call": True}}))
    assert R.add(ns(), m, out, NOW) == 1
    assert "[reading:calibration-on-record]" in capsys.readouterr().out and not out.exists()
    assert R.record_calibration("btc_touch", "re-run", tmp_path, NOW) == 0
    assert R.record_calibration("btc_touch", "re-run", tmp_path, NOW) == 1  # the same file twice: refused
    assert "already its latest line" in capsys.readouterr().out
    lines = [h for h in history(tmp_path) if h["method"] == "btc_touch"]
    assert [h["r2"] for h in lines] == ["false", "true"] and lines[1]["in_force_utc"] == "2026-11-06T18:30:00Z"
    assert R.add(ns(), m, out, NOW) == 0
    assert list(csv.DictReader(out.open()))[0]["gate"] == "method-departure;touch-below"  # R2 true: no `calibrated`


def test_add_refuses_with_no_calibration_on_record(tmp_path, capsys):
    m = write_manifest(tmp_path, [QUOTE])
    (tmp_path / L.CALIBRATION_HISTORY).unlink()
    assert R.add(ns(), m, tmp_path / "readings.csv", NOW) == 1
    assert "[reading:calibration-on-record]" in capsys.readouterr().out


def test_a_row_is_judged_under_the_calibration_in_force_when_it_was_recorded_not_todays(tmp_path):
    # the defect of 2026-11-07 06:15Z: the committed-file test judged every row under today's file, so a
    # correct re-run flipping R2 failed rows that were right when written
    m = write_manifest(tmp_path, [QUOTE])
    out = tmp_path / "readings.csv"
    assert R.add(ns(), m, out, NOW) == 0
    row = list(csv.DictReader(out.open()))[0]
    assert row["gate"] == "calibrated;method-departure;touch-below"
    (tmp_path / "data" / "calibration.json").write_text(json.dumps({"rules": {"R2_method_is_a_basis_for_a_call": True}}))
    later = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    assert R.record_calibration("btc_touch", "re-run", tmp_path, later) == 0
    h = history(tmp_path)
    def judged(at: str) -> list[str]:
        return L.reading_violations(row["method"], float(row["method_p"]), float(row["range_lo"]),
                                    float(row["range_hi"]), float(row["market_mid"]), 0.690, QUOTE, row["made_on"],
                                    row["due_on"], gate_col=row["gate"],
                                    calibration=L.calibration_in_force(h, "btc_touch", at))
    assert judged(row["recorded_utc"]) == []  # under the line in force when recorded: right, as written
    assert any("[reading:gate-column]" in x for x in judged("2026-11-20T12:00:00Z"))  # under today's: stale
    # and a reading admitted after the re-run is judged under the new line
    assert L.calibration_in_force(h, "btc_touch", "2026-11-20T12:00:00Z")["r2"] == "true"
    assert L.calibration_in_force(h, "btc_touch", "2026-11-05T11:59:59Z") is None


def test_add_gate_column_is_open_when_the_call_gate_would_pass(tmp_path):
    m = write_manifest(tmp_path, [dict(QUOTE, market_id="3215008", market_mid=0.40, end_date="2026-12-09T23:59:00Z",
                                       fetched_utc="2026-11-06T06:16:37Z")])
    out = tmp_path / "readings.csv"
    assert R.add(ns(market_id="3215008", quote="2026-11-06T06:16:37Z", method="fomc_bills", method_p=0.9,
                    range_lo=0.6, range_hi=1.0, climatology_p=0.23, proposition="Hike of 25 bp on 9 December"),
                 m, out, NOW) == 0
    assert list(csv.DictReader(out.open()))[0]["gate"] == "open"


# --- the scorer -------------------------------------------------------------

def fetcher(bodies: dict[str, object]):
    def get(url: str) -> bytes:
        for key, body in bodies.items():
            if key in url:
                return json.dumps(body).encode()
        raise OSError(f"no body for {url}")
    return get


def reading_row(**kw) -> dict:
    base = {"id": "R-2026-11-06-btc_touch-6507380", "made_on": "2026-11-06", "recorded_utc": "2026-11-06T18:30:00Z",
            "venue": "polymarket", "market_id": "6507380", "condition_id": "0xc3e5", "yes_token_id": "967",
            "proposition": "p", "method": "btc_touch", "method_p": "0.876", "range_lo": "0.876", "range_hi": "0.886",
            "market_mid": "0.925", "climatology_p": "0.690", "due_on": "2026-12-01", "gate": "calibrated",
            "quote_fetched_utc": "2026-11-06T06:16:38Z", "quote_sha256": "ab" * 32, "source": "s"}
    base.update(kw)
    return base


def write_readings(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(L.READING_COLUMNS))
        w.writeheader()
        w.writerows(rows)


RESOLVED_YES = {"umaResolutionStatus": "resolved", "outcomePrices": '["1", "0"]', "closed": True}
CLOB_YES = {"tokens": [{"token_id": "967", "winner": True}, {"token_id": "968", "winner": False}]}


def test_reading_not_due_is_not_fetched_and_a_due_one_is_scored_against_all_three(tmp_path, capsys):
    readings = tmp_path / "readings.csv"
    out = tmp_path / "readings_outcomes.csv"
    m = tmp_path / "manifest.json"
    m.write_text(json.dumps([QUOTE]))
    write_readings(readings, [reading_row()])
    boom = fetcher({})  # any fetch raises: nothing may be fetched before the due date
    assert S.run_readings(readings, out, m, boom, boom, date(2026, 11, 20), dry_run=False) == 0
    assert "none due (of 1" in capsys.readouterr().out and not out.exists()
    g = fetcher({"/markets/6507380": RESOLVED_YES})
    c = fetcher({"/markets/0xc3e5": CLOB_YES})
    assert S.run_readings(readings, out, m, g, c, date(2026, 12, 1), dry_run=False) == 0
    rows = list(csv.DictReader(out.open()))
    assert len(rows) == 1 and tuple(rows[0].keys()) == L.READING_OUTCOME_COLUMNS
    r = rows[0]
    assert r["y"] == "1" and r["brier_method"] == f"{(0.876 - 1) ** 2:.4f}"
    assert r["brier_market"] == f"{(0.925 - 1) ** 2:.4f}" and r["brier_climatology"] == f"{(0.690 - 1) ** 2:.4f}"
    # scored once: a second run with the same files fetches nothing
    assert S.run_readings(readings, out, m, boom, boom, date(2026, 12, 2), dry_run=False) == 0
    assert len(list(csv.DictReader(out.open()))) == 1


def test_a_later_written_quote_with_a_settlement_makes_the_reading_due_early(tmp_path):
    readings = tmp_path / "readings.csv"
    out = tmp_path / "readings_outcomes.csv"
    m = tmp_path / "manifest.json"
    early = dict(SETTLED, market_id="6507380", fetched_utc="2026-11-10T06:00:00Z")
    m.write_text(json.dumps([QUOTE, early]))
    write_readings(readings, [reading_row()])
    g = fetcher({"/markets/6507380": RESOLVED_YES})
    c = fetcher({"/markets/0xc3e5": CLOB_YES})
    assert S.run_readings(readings, out, m, g, c, date(2026, 11, 10), dry_run=False) == 0
    assert len(list(csv.DictReader(out.open()))) == 1
    # a settlement quote made BEFORE the reading does not make it due
    m.write_text(json.dumps([QUOTE, dict(early, fetched_utc="2026-11-01T06:00:00Z")]))
    out2 = tmp_path / "o2.csv"
    boom = fetcher({})
    assert S.run_readings(readings, out2, m, boom, boom, date(2026, 11, 10), dry_run=False) == 0
    assert not out2.exists()


def test_unresolved_reading_is_retried_and_a_failed_fetch_sets_rc(tmp_path, capsys):
    readings = tmp_path / "readings.csv"
    out = tmp_path / "readings_outcomes.csv"
    m = tmp_path / "manifest.json"
    m.write_text("[]")
    write_readings(readings, [reading_row()])
    g = fetcher({"/markets/6507380": {"umaResolutionStatus": None, "outcomePrices": '["0.5", "0.5"]', "closed": False}})
    c = fetcher({"/markets/0xc3e5": {"tokens": [{"token_id": "967", "winner": False}, {"token_id": "968", "winner": False}]}})
    assert S.run_readings(readings, out, m, g, c, date(2026, 12, 1), dry_run=False) == 0
    assert "READING NOT SCORED" in capsys.readouterr().out and not out.exists()
    assert S.run_readings(readings, out, m, fetcher({}), fetcher({}), date(2026, 12, 1), dry_run=False) == 1


def test_summary_carries_the_readings_table(tmp_path):
    ledger = tmp_path / "ledger.csv"
    ledger.write_text(",".join(L.LEDGER_COLUMNS) + "\n")
    write_readings(tmp_path / "readings.csv", [reading_row(), reading_row(id="R-2", method="fomc_bills", method_p="0.9",
                                                                       market_mid="0.6", climatology_p="")])
    with (tmp_path / "readings_outcomes.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(L.READING_OUTCOME_COLUMNS))
        w.writeheader()
        # a row as score.py writes it; until 2026-11-10 this fixture carried kind "first" and one-letter hashes
        # and the summary read it, because the scored record was held by nothing at the reader
        w.writerow({"id": "R-2", "scored_on": "2026-12-10", "kind": "first-token", "y": "1", "method_p": "0.9",
                    "market_mid": "0.6", "climatology_p": "", "brier_method": "0.0100", "brier_market": "0.1600",
                    "brier_climatology": "", "gamma_sha256": "a" * 64, "clob_sha256": "b" * 64})
    skill = tmp_path / "SKILL.md"
    S.write_summary(ledger, tmp_path / "outcomes.csv", skill, date(2026, 12, 10))
    text = skill.read_text()
    assert "## Method readings against the market, as information" in text
    assert "| fomc_bills | 1 | 1 | 0.0100 | 0.1600 | – (0) |" in text
    assert "| btc_touch | 1 | 0 | – | – | – (0) |" in text
    assert "Readings on record: 2; scored: 1; not yet due or not yet resolved: 1." in text


# --- the committed record ----------------------------------------------------

def read(name: str) -> list[dict]:
    path = HERE / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_committed_readings_columns_are_the_declared_ones():
    with (HERE / "readings.csv").open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert tuple(header) == L.READING_COLUMNS


def test_every_committed_reading_passes_the_gate_on_a_written_eligible_quote_of_its_day():
    # 2026-11-09 00:15Z (predictions/POST_MORTEMS.md "A readings gate that never saw the row"): the one copy of
    # the row gate, pm_lib.reading_row_violations, judges every committed row as written (ids, venue, hash,
    # fetch time and recorded_utc held to the quote; the gate column under the calibration in force when the
    # row was recorded, never today's; the ids above each row for one-per-day), in place of this test's own
    # assertions, which held five columns outside the gate and its tags and nothing at admission.
    entries = json.loads((HERE / "data" / "manifest.json").read_text(encoding="utf-8"))
    rows = read("readings.csv")
    v = L.reading_file_violations(rows, entries, read(L.CALIBRATION_HISTORY))
    assert v == [], "\n".join(v)
    for r in rows:
        assert r["source"].strip(), f"{r['id']}: source is empty"  # free text from the desk: not a column the tool fills


# 2026-11-09 00:15Z, predictions/POST_MORTEMS.md "A readings gate that never saw the row": the mechanical search
# of tests/test_ledger.py (8 November) run on the readings record, kept.  Every column of a reading row comes
# either from the desk's arguments (FROM_ARGS, held by reading_violations' own rules where one exists) or from
# the written quote and the tool itself; each of the latter, altered on a clean row, must be refused by the
# row gate, or a hand-typed row could carry it at any value past the committed-file test.  On 39e6fa7 the
# gate held five of the twelve, this file's own assertions five more (no tag, never at admission), and
# nothing held `venue` or `recorded_utc`.  A new column must be classified here before the test passes.
FROM_ARGS = {"proposition", "method", "method_p", "range_lo", "range_hi", "climatology_p", "source"}
ALTERED = {"id": "R-2026-11-06-fomc_bills-6507380", "made_on": "2026-11-07", "venue": "kalshi", "market_id": "6507381",
           "condition_id": "0xdead", "yes_token_id": "999", "market_mid": "0.900", "due_on": "2026-12-09", "gate": "open",
           "quote_fetched_utc": "2026-11-06T06:16:39Z", "quote_sha256": "ee" * 32, "recorded_utc": "2026-11-06T00:00:00Z",
           "window_from_utc": "2026-11-05T17:17:00Z"}  # 2026-11-14: copied from the quote, held by window-from-rules


def test_every_column_the_tool_copies_or_sets_is_held_by_the_row_gate(tmp_path):
    assert FROM_ARGS | set(ALTERED) == set(L.READING_COLUMNS) and not FROM_ARGS & set(ALTERED), \
        "classify every reading column: from the desk's arguments, or copied from the quote / set by the tool"
    write_manifest(tmp_path, [QUOTE])
    hist = history(tmp_path)
    row, v = R.build_row(QUOTE, "6507380", "btc_touch", 0.876, 0.876, 0.886, 0.690, "p", "s", hist,
                         R.calibration_sha256("btc_touch", tmp_path), NOW)
    assert v == [] and tuple(row) == L.READING_COLUMNS
    row = {k: ("" if x is None else str(x)) for k, x in row.items()}
    assert L.reading_file_violations([row], [QUOTE], hist) == []
    unheld = [col for col, bad in ALTERED.items() if not L.reading_file_violations([dict(row, **{col: bad})], [QUOTE], hist)]
    assert unheld == [], f"columns a hand-typed row could carry at any value: {unheld}"
    # the columns the search found on 2026-11-09, each refused by its own tag through the file gate
    for col, bad, tag in (("venue", "kalshi", "id-rule"), ("id", "R-x", "id-rule"),
                          ("recorded_utc", "2026-11-06T00:00:00Z", "recorded-after-quote"),
                          ("recorded_utc", "2026-11-06 18:30:00", "recorded-after-quote"),
                          ("condition_id", "0xdead", "written-quote"), ("yes_token_id", "999", "written-quote"),
                          ("quote_fetched_utc", "2026-11-06T06:16:39Z", "written-quote")):
        v = L.reading_file_violations([dict(row, **{col: bad})], [QUOTE], hist)
        assert v and v[0].startswith(f"{row['id'] if col != 'id' else bad}: [reading:{tag}]"), (col, v)
    # a stamp in another format is refused on its format alone, and also loses its calibration line (judged as text)
    tags = L.reading_tags(" ".join(L.reading_file_violations([dict(row, recorded_utc="2026-11-06 18:30:00")], [QUOTE], hist)))
    assert "recorded-after-quote" in tags


def test_committed_calibration_history_is_dated_append_only_and_ends_at_the_committed_files():
    # Replaces, 2026-11-07 06:15Z, a test that recomputed every row's gate column from the calibration files as
    # they stand today: a correct re-run flipping R2 would have failed it on rows right when written.  Now each
    # calibration that has been in force is a dated line, rows are judged under theirs (the test above), and
    # the committed file must be its method's latest line, so a re-run not put on record fails here at once.
    with (HERE / L.CALIBRATION_HISTORY).open(newline="", encoding="utf-8") as fh:
        assert tuple(next(csv.reader(fh))) == L.CALIBRATION_HISTORY_COLUMNS
    hist = read(L.CALIBRATION_HISTORY)
    last: dict[str, str] = {}
    for h in hist:
        assert h["method"] in L.METHOD_CALIBRATION and h["r2"] in ("true", "false") and h["source"].strip()
        assert len(h["sha256"]) == 64 and all(c in "0123456789abcdef" for c in h["sha256"])
        in_force = L.parse_utc_stamp(h["in_force_utc"], f"calibration_history.csv in_force_utc of {h['method']}")
        # parsed before it is ordered (2026-11-11 18:15Z: this line ordered the stamps as text, outside the
        # stamp check's universe, which read the modules and not the tests)
        assert in_force >= last.get(h["method"], in_force), f"{h['method']}: a line dated before the one above it"
        last[h["method"]] = in_force
    for method in L.METHOD_CALIBRATION:
        latest = L.latest_calibration(hist, method)
        assert latest is not None, f"{method}: no calibration on record"
        assert latest["sha256"] == R.calibration_sha256(method, HERE), (
            f"{method}: the committed calibration file is not its latest line; run readings.py record-calibration")
        assert L.history_r2(latest) is R.calibration_r2(method, HERE)
    # the first lines, as written on 2026-11-05: the bills pass R2, the touch formula does not
    first = {m: next(h for h in hist if h["method"] == m) for m in L.METHOD_CALIBRATION}
    assert first["fomc_bills"]["r2"] == "true" and first["btc_touch"]["r2"] == "false"


def test_committed_reading_ids_are_unique_and_outcomes_refer_to_readings():
    ids = [r["id"] for r in read("readings.csv")]
    assert len(ids) == len(set(ids)), "readings.csv: duplicate id"
    out = [r["id"] for r in read("readings_outcomes.csv")]
    assert len(out) == len(set(out)), "readings_outcomes.csv: an id scored twice"
    assert set(out) <= set(ids), "readings_outcomes.csv: an id with no reading"
