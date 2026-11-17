"""§6.5 tests of the reader on synthetic files: the field lists against §5.3, the refusal on any other field,
the hash checks, the followed-events file."""

import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest
from src import reader

SECTION_5_3_FIELDS = {"id", "bestBid", "bestAsk", "orderPriceMinTickSize", "liquidityNum", "feesEnabled", "endDate", "eventIds"}
SECTION_5_1_SAMPLE_FIELDS = {"trial", "market", "cluster", "price", "snapshot", "realised_horizon_hours", "half", "sports", "early"}


def test_field_lists_are_exactly_those_of_the_preregistration():
    assert set(reader.RECORD_FIELDS) == SECTION_5_3_FIELDS and len(reader.RECORD_FIELDS) == 8
    assert set(reader.SAMPLE_FIELDS) == SECTION_5_1_SAMPLE_FIELDS
    assert reader.END_FIELDS == ("id", "endDate")
    assert set(reader.DATA_STEP_KEYS) == {"stopped_for_amendment", "halted", "price_field_check"}


@pytest.mark.parametrize("field", ["outcomePrices", "lastTradePrice", "umaResolutionStatus", "closedTime", "outcomes",
                                   "clobTokenIds", "tagLabels", "conditionId", "volumeNum"])
def test_project_refuses_any_field_outside_section_5_3(field):
    row = {f: 1 for f in SECTION_5_3_FIELDS} | {field: "x"}
    with pytest.raises(reader.FieldRefusal):
        reader.project(row, (field,))
    with pytest.raises(reader.FieldRefusal):
        reader.project(row, ("id", field))
    out = reader.project(row, reader.RECORD_FIELDS)
    assert set(out) == SECTION_5_3_FIELDS and field not in out


def test_project_on_the_end_fields_only_takes_two():
    row = {"id": "1", "endDate": "2026-12-01T00:00:00Z", "bestBid": 0.5}
    assert reader.project(row, reader.END_FIELDS) == {"id": "1", "endDate": "2026-12-01T00:00:00Z"}


def _snapshot(root: Path, day: str, rows: list[dict]) -> str:
    folder = root / "snapshots" / day
    folder.mkdir(parents=True)
    text = "".join(json.dumps(r) + "\n" for r in rows)
    (folder / "records.jsonl").write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode()).hexdigest()


def _log(path: Path, entries: dict[str, str]) -> None:
    lines = ["snapshot_date,started_utc,finished_utc,pages,rows,distinct_markets,bytes,records_sha256,pages_sha256"]
    for day, sha in entries.items():
        lines.append(f"{day},{day}T04:40:00Z,{day}T04:45:00Z,1,{1},{1},10,{sha},{'0' * 64}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_hash_check_refuses_a_changed_or_missing_snapshot_file(tmp_path: Path):
    row = {"id": 7, "bestBid": 0.5, "bestAsk": 0.52, "orderPriceMinTickSize": 0.01, "liquidityNum": 1000, "feesEnabled": False,
           "endDate": "2026-12-01T00:00:00Z", "eventIds": "[\"5\"]", "lastTradePrice": 0.51}
    sha = _snapshot(tmp_path, "2026-11-10", [row])
    _snapshot(tmp_path, "2026-11-11", [row])  # a second day, logged under a wrong hash below
    log_csv = tmp_path / "snapshots.csv"
    _log(log_csv, {"2026-11-10": sha, "2026-11-11": "f" * 64, "2026-11-12": sha})
    log = reader.read_snapshot_log(log_csv)
    rows, hashes = reader.read_record_rows(tmp_path / "snapshots", log, {dt.date(2026, 11, 10): {"7"}})
    assert set(rows) == {("2026-11-10", "7")} and hashes == {"2026-11-10": sha}
    assert set(rows[("2026-11-10", "7")]) == SECTION_5_3_FIELDS  # the ninth field on the row is not taken
    with pytest.raises(reader.SnapshotHashMismatch, match="hashes to"):
        reader.read_record_rows(tmp_path / "snapshots", log, {dt.date(2026, 11, 11): {"7"}})
    with pytest.raises(reader.SnapshotHashMismatch, match="missing"):
        reader.read_record_rows(tmp_path / "snapshots", log, {dt.date(2026, 11, 12): {"7"}})
    with pytest.raises(reader.Refusal, match="does not list"):
        reader.read_record_rows(tmp_path / "snapshots", log, {dt.date(2026, 11, 13): {"7"}})
    # an edited file after logging
    p = tmp_path / "snapshots" / "2026-11-10" / "records.jsonl"
    p.write_text(p.read_text(encoding="utf-8").replace("0.52", "0.53"), encoding="utf-8")
    with pytest.raises(reader.SnapshotHashMismatch):
        reader.read_record_rows(tmp_path / "snapshots", log, {dt.date(2026, 11, 10): {"7"}})


def test_first_end_dates_reads_id_and_end_only_from_the_first_listing_snapshot(tmp_path: Path):
    a = _snapshot(tmp_path, "2026-11-03", [{"id": 1, "endDate": "A", "bestBid": 0.1}])
    b = _snapshot(tmp_path, "2026-11-04", [{"id": 1, "endDate": "B"}, {"id": 2, "endDate": "X"}])
    log_csv = tmp_path / "snapshots.csv"
    _log(log_csv, {"2026-11-03": a, "2026-11-04": b, "2026-11-05": a})  # 05 has no file
    log = reader.read_snapshot_log(log_csv)
    found, hashes = reader.first_end_dates(tmp_path / "snapshots", log, {"1", "2", "3"}, dt.date(2026, 11, 3), dt.date(2026, 11, 5))
    assert found == {"1": "A", "2": "X"} and hashes == {"2026-11-03": a, "2026-11-04": b, "2026-11-05": "missing"}


def test_read_sample_checks_the_manifest_hash_and_drops_the_token_field(tmp_path: Path):
    sample = tmp_path / "sample.jsonl"
    row = {"trial": "C1", "market": "7", "cluster": "9", "price": 0.51, "snapshot": "2026-11-10", "realised_horizon_hours": 25.0,
           "half": "W1", "sports": False, "early": False, "first_label_yes": True, "volume_at_horizon": 1.0, "tag_family": "x",
           "first_token": "tok"}
    sample.write_text(json.dumps(row) + "\n", encoding="utf-8")
    manifest = tmp_path / "data_manifest.json"
    manifest.write_text(json.dumps({"sample_jsonl_sha256": "0" * 64}), encoding="utf-8")
    with pytest.raises(reader.Refusal, match="hashes to"):
        reader.read_sample(sample, manifest)
    manifest.write_text(json.dumps({"sample_jsonl_sha256": reader.sha256_file(sample)}), encoding="utf-8")
    rows, h = reader.read_sample(sample, manifest)
    assert len(rows) == 1 and set(rows[0]) == SECTION_5_1_SAMPLE_FIELDS and h == reader.sha256_file(sample)
    with pytest.raises(reader.Refusal, match="missing"):
        reader.read_sample(sample, tmp_path / "nope.json")


def test_read_data_step_three_keys(tmp_path: Path):
    p = tmp_path / "data_step.json"
    with pytest.raises(reader.Refusal, match="has not run"):
        reader.read_data_step(p)
    p.write_text(json.dumps({"stopped_for_amendment": False, "halted": True}), encoding="utf-8")
    with pytest.raises(reader.Refusal, match="price_field_check"):
        reader.read_data_step(p)
    p.write_text(json.dumps({"stopped_for_amendment": False, "halted": True, "price_field_check": {"pass": True, "rows": 5}, "other": 1}),
                 encoding="utf-8")
    assert reader.read_data_step(p) == {"stopped_for_amendment": False, "halted": True, "price_field_pass": True}


def test_followed_events_fixed_two_and_later_by_date(tmp_path: Path):
    csv_path = tmp_path / "events.csv"
    csv_path.write_text(
        "venue,event_id,event_slug,method,followed_from,source\n"
        "polymarket,1292829,btc,btc_touch,2026-11-03,x\n"
        "polymarket,770450,fed,fomc_bills,2026-11-03,x\n"
        "polymarket,555,later,btc_touch,2026-12-01,x\n"
        "polymarket,666,after-run,btc_touch,2027-02-01,x\n"
        "polymarket,777,bad-date,btc_touch,unknown,x\n", encoding="utf-8")
    fixed, later = reader.read_followed_events(csv_path, dt.date(2027, 1, 21))
    assert fixed == {"1292829", "770450"} and later == {"555", "777"}
    fixed2, later2 = reader.read_followed_events(tmp_path / "none.csv", dt.date(2027, 1, 21))
    assert fixed2 == fixed and later2 == set()
