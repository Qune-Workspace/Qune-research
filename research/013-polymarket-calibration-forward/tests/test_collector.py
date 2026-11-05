"""Tests of the daily snapshot collector (Study 013), on in-memory pages.

No network: every test passes a fake page fetcher by name, and every path by
name (tools/check_bound_defaults.py: no module constant is patched). The
fixture rows are built here in Python, not in a data file, because a JSON
fixture carrying the listing's raw field names would fail
tools/check_data_terms.py under Polymarket's `derived` verdict.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

import collector
import pytest

NOW = dt.datetime(2026, 11, 2, 5, 40, 0, tzinfo=dt.UTC)


def row(i: int, **over: object) -> dict:
    """One listing row with every field class the collector must handle."""
    r: dict = {
        "id": str(i),
        "conditionId": f"0x{i:064x}",
        "questionID": f"0x{i:064x}",
        "clobTokenIds": json.dumps([str(10 * i), str(10 * i + 1)]),
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.42", "0.58"]',
        "bestBid": 0.41,
        "bestAsk": 0.43,
        "lastTradePrice": 0.42,
        "spread": 0.02,
        "liquidityNum": 12345.6,
        "volumeNum": 98765.4,
        "volume24hr": 100.0,
        "startDate": "2026-10-01T00:00:00Z",
        "endDate": "2026-12-31T12:00:00Z",
        "createdAt": "2026-09-30T00:00:00Z",
        "updatedAt": "2026-11-02T05:00:00Z",
        "closedTime": None,
        "acceptingOrdersTimestamp": "2026-10-01T00:00:00Z",
        "closed": False,
        "active": True,
        "acceptingOrders": True,
        "enableOrderBook": True,
        "negRisk": False,
        "restricted": True,
        "umaResolutionStatus": None,
        "resolutionMechanism": "oracle",
        "orderPriceMinTickSize": 0.01,
        "feesEnabled": False,
        # wording and resolver fields that must never be written
        "question": f"Will thing {i} happen?",
        "description": "A long description of the market.",
        "slug": f"will-thing-{i}-happen",
        "groupItemTitle": f"Thing {i}",
        "image": "https://example.invalid/i.png",
        "icon": "https://example.invalid/i.png",
        "resolutionSource": "https://example.invalid/source",
        "resolvedBy": "0xresolver",
        "events": [{"id": 1000 + i // 2, "title": "Parent event"}],
        "tags": [{"id": 1, "label": "Politics"}, {"id": 2, "label": "Elections"}],
    }
    r.update(over)
    return r


def pages_of(rows: list[dict], page: int = collector.PAGE) -> list[list[dict]]:
    return [rows[i : i + page] for i in range(0, len(rows), page)] or [[]]


def fake_fetcher(pages: list[list[dict]], fail_on: int | None = None):
    """A fetcher over fixed pages; the cursor is the next page index as text."""
    calls: list[str | None] = []

    def fetch(cursor: str | None):
        calls.append(cursor)
        k = int(cursor) if cursor else 0
        if fail_on is not None and k == fail_on:
            raise TimeoutError("simulated timeout")
        body = json.dumps({"markets": pages[k], "next_cursor": str(k + 1) if k + 1 < len(pages) else None}).encode()
        nxt = str(k + 1) if k + 1 < len(pages) else None
        return pages[k], nxt, hashlib.sha256(body).hexdigest(), len(body)

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


def test_strip_keeps_the_whitelist_and_drops_every_wording_field():
    out = collector.strip(row(7))
    for k in collector.KEEP:
        assert k in out
    for k in collector.NEVER:
        assert k not in out
    assert out["eventIds"] == ["1003"]
    assert out["tagLabels"] == ["Elections", "Politics"]
    assert set(out) == set(collector.KEEP) | {"eventIds", "tagLabels"}


def test_snapshot_pages_dedupes_hashes_and_logs_one_line(tmp_path: Path):
    rows = [row(i) for i in range(237)]
    rows.append(row(5))  # the same market served twice across pages
    pages = pages_of(rows)
    fetch = fake_fetcher(pages)
    root, log = tmp_path / "snap", tmp_path / "paper-log" / "snapshots.csv"
    out = collector.take_snapshot(snapshot_root=root, log_csv=log, fetch=fetch, now=NOW, pause_s=0)

    assert fetch.calls == [None, "1", "2"]
    final = root / "2026-11-02"
    assert final.is_dir() and not (root / "2026-11-02.tmp").exists()
    records = [json.loads(line) for line in (final / "records.jsonl").read_text().splitlines()]
    assert len(records) == 237
    assert [r["id"] for r in records][:3] == ["0", "1", "2"]
    for r in records:
        assert not set(r) & set(collector.NEVER)
    page_lines = [json.loads(line) for line in (final / "pages.jsonl").read_text().splitlines()]
    assert [p["rows"] for p in page_lines] == [100, 100, 38]
    assert all(len(p["sha256"]) == 64 for p in page_lines)

    logged = collector.read_log(log)
    assert len(logged) == 1
    assert logged[0]["snapshot_date"] == "2026-11-02"
    assert logged[0]["started_utc"] == "2026-11-02T05:40:00Z"
    assert (logged[0]["pages"], logged[0]["rows"], logged[0]["distinct_markets"]) == ("3", "238", "237")
    assert logged[0]["records_sha256"] == collector.sha256_file(final / "records.jsonl")
    assert logged[0]["pages_sha256"] == collector.sha256_file(final / "pages.jsonl")
    assert out == logged[0]
    # The committed log carries no raw field name (Polymarket verdict: derived).
    text = log.read_text()
    for marker in ("clobTokenIds", "outcomePrices", "asset_id"):
        assert marker not in text


def test_a_second_snapshot_on_the_same_day_refuses_and_writes_nothing(tmp_path: Path):
    pages = pages_of([row(i) for i in range(5)])
    root, log = tmp_path / "snap", tmp_path / "snapshots.csv"
    collector.take_snapshot(snapshot_root=root, log_csv=log, fetch=fake_fetcher(pages), now=NOW, pause_s=0)
    before = log.read_bytes()
    rec_before = (root / "2026-11-02" / "records.jsonl").read_bytes()
    second = fake_fetcher(pages)
    with pytest.raises(collector.SnapshotExists):
        collector.take_snapshot(snapshot_root=root, log_csv=log, fetch=second, now=NOW, pause_s=0)
    assert second.calls == []
    assert log.read_bytes() == before
    assert (root / "2026-11-02" / "records.jsonl").read_bytes() == rec_before


def test_a_failed_fetch_leaves_no_folder_and_no_log_line(tmp_path: Path):
    pages = pages_of([row(i) for i in range(250)])
    root, log = tmp_path / "snap", tmp_path / "snapshots.csv"
    with pytest.raises(TimeoutError):
        collector.take_snapshot(snapshot_root=root, log_csv=log, fetch=fake_fetcher(pages, fail_on=1), now=NOW, pause_s=0)
    assert not (root / "2026-11-02").exists()
    assert not (root / "2026-11-02.tmp").exists()
    assert not log.exists()
    # The next run of the same day starts clean and completes.
    out = collector.take_snapshot(snapshot_root=root, log_csv=log, fetch=fake_fetcher(pages), now=NOW, pause_s=0)
    assert out["pages"] == "3" and (root / "2026-11-02").is_dir()


def test_the_log_is_append_only(tmp_path: Path):
    root, log = tmp_path / "snap", tmp_path / "snapshots.csv"
    d1 = NOW
    d2 = NOW + dt.timedelta(days=1)
    collector.take_snapshot(snapshot_root=root, log_csv=log, fetch=fake_fetcher(pages_of([row(1)])), now=d1, pause_s=0)
    first_line = log.read_text().splitlines()[1]
    collector.take_snapshot(snapshot_root=root, log_csv=log, fetch=fake_fetcher(pages_of([row(1), row(2)])), now=d2, pause_s=0)
    lines = log.read_text().splitlines()
    assert lines[0] == ",".join(collector.LOG_COLUMNS)
    assert lines[1] == first_line
    assert len(lines) == 3
    with open(log, newline="") as f:
        assert [r["snapshot_date"] for r in csv.DictReader(f)] == ["2026-11-02", "2026-11-03"]


def test_gaps_lists_missing_days_and_never_fills_them(tmp_path: Path):
    log = tmp_path / "snapshots.csv"
    assert collector.gaps(log, dt.date(2026, 11, 5)) == []  # nothing started: no gap
    for day in ("2026-11-02", "2026-11-04"):
        collector.append_log(
            log,
            {
                "snapshot_date": day,
                "started_utc": f"{day}T05:40:00Z",
                "finished_utc": f"{day}T05:45:00Z",
                "pages": "1",
                "rows": "1",
                "distinct_markets": "1",
                "bytes": "10",
                "records_sha256": "0" * 64,
                "pages_sha256": "0" * 64,
            },
        )
    assert collector.gaps(log, dt.date(2026, 11, 5)) == ["2026-11-03", "2026-11-05"]
    assert collector.gaps(log, dt.date(2026, 11, 4)) == ["2026-11-03"]


def test_dry_run_fetches_one_page_and_writes_nothing(tmp_path: Path):
    pages = pages_of([row(i) for i in range(150)])
    fetch = fake_fetcher(pages)
    root, log = tmp_path / "snap", tmp_path / "snapshots.csv"
    out = collector.take_snapshot(snapshot_root=root, log_csv=log, fetch=fetch, now=NOW, pause_s=0, dry_run=True)
    assert fetch.calls == [None]
    assert out["rows"] == "100" and out["more"] == "yes"
    assert not root.exists() and not log.exists()


# --- consistency: id-only comparison of consecutive snapshots (2026-11-05) ---------------------


def write_snapshot(root: Path, day: str, started: str, rows: list[dict]) -> None:
    """A logged snapshot folder with whitelisted rows, as take_snapshot leaves it."""
    folder = root / "snapshots" / day
    folder.mkdir(parents=True)
    with open(folder / "records.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(collector.strip(r)) + "\n")
    (folder / "pages.jsonl").write_text("{}\n", encoding="utf-8")
    collector.append_log(
        root / "snapshots.csv",
        {
            "snapshot_date": day,
            "started_utc": started,
            "finished_utc": started,
            "pages": "1",
            "rows": str(len(rows)),
            "distinct_markets": str(len(rows)),
            "bytes": "1",
            "records_sha256": "0",
            "pages_sha256": "0",
        },
    )


def test_consistency_counts_carried_left_appeared_early_and_missed(tmp_path: Path):
    # day 1: markets 1-5; day 2: 1-4 (5 left) plus 6 (new, created after day 1 started) and 7 (created before);
    # day 3: 1-7 plus 5 back again, so day 2 missed at most one (market 5), and 8 appears.
    d1 = [row(i) for i in range(1, 6)]
    d2 = [row(i) for i in range(1, 5)] + [row(6, createdAt="2026-11-02T10:00:00Z"), row(7, createdAt="2026-10-01T00:00:00Z")]
    d3 = [row(i) for i in range(1, 9)]
    write_snapshot(tmp_path, "2026-11-02", "2026-11-02T04:40:00Z", d1)
    write_snapshot(tmp_path, "2026-11-03", "2026-11-03T04:40:00Z", d2)
    write_snapshot(tmp_path, "2026-11-04", "2026-11-04T04:40:00Z", d3)
    out = tmp_path / "consistency.csv"
    rows = collector.consistency(tmp_path / "snapshots", tmp_path / "snapshots.csv", out)
    assert [r["snapshot_date"] for r in rows] == ["2026-11-03", "2026-11-04"]
    r2, r3 = rows
    assert r2["previous_date"] == "2026-11-02"
    assert (r2["previous_markets"], r2["markets"], r2["carried"], r2["left"], r2["appeared"]) == ("5", "6", "4", "1", "2")
    assert r2["appeared_created_before_previous_start"] == "1"  # market 7; market 6 was created after day 1 started
    assert r2["previous_missed_at_most"] == "0"  # no snapshot before day 1 to compare with
    assert (r3["previous_markets"], r3["markets"], r3["carried"], r3["left"], r3["appeared"]) == ("6", "8", "6", "0", "2")
    assert r3["previous_missed_at_most"] == "1"  # market 5: in day 1 and day 3, absent from day 2
    # the committed file holds counts only: no market id, no field name of the listing
    text = out.read_text(encoding="utf-8")
    assert text.splitlines()[0] == ",".join(collector.CONSISTENCY_COLUMNS)
    assert len(text.splitlines()) == 3
    for word in ("bestBid", "outcomePrices", "conditionId", "Yes"):
        assert word not in text
    # append-only and idempotent: a second run adds nothing and rewrites nothing
    assert collector.consistency(tmp_path / "snapshots", tmp_path / "snapshots.csv", out) == []
    assert out.read_text(encoding="utf-8") == text
    # a fourth snapshot appends exactly one more line
    write_snapshot(tmp_path, "2026-11-05", "2026-11-05T04:40:00Z", d3)
    rows = collector.consistency(tmp_path / "snapshots", tmp_path / "snapshots.csv", out)
    assert [r["snapshot_date"] for r in rows] == ["2026-11-05"]
    assert rows[0]["carried"] == "8" and rows[0]["previous_missed_at_most"] == "0"


def test_consistency_reads_only_the_id_and_creation_time(tmp_path: Path):
    """A row that carries nothing but the two fields is enough: the check never touches a price,
    status, label or outcome field."""
    folder = tmp_path / "snapshots"
    for day, ids in (("2026-11-02", [1, 2]), ("2026-11-03", [1, 2, 3])):
        (folder / day).mkdir(parents=True)
        with open(folder / day / "records.jsonl", "w", encoding="utf-8") as f:
            for i in ids:
                f.write(json.dumps({"id": str(i), "createdAt": "2026-11-01T00:00:00Z"}) + "\n")
        collector.append_log(
            tmp_path / "snapshots.csv",
            {"snapshot_date": day, "started_utc": f"{day}T04:40:00Z", "finished_utc": f"{day}T04:41:00Z", "pages": "1",
             "rows": str(len(ids)), "distinct_markets": str(len(ids)), "bytes": "1", "records_sha256": "0", "pages_sha256": "0"},
        )
    rows = collector.consistency(folder, tmp_path / "snapshots.csv", tmp_path / "consistency.csv")
    assert rows[0]["appeared"] == "1" and rows[0]["appeared_created_before_previous_start"] == "1"
    assert collector.CONSISTENCY_FIELDS == ("id", "createdAt")


def test_consistency_line_flags_a_page_or_more_missed():
    base = {"snapshot_date": "2026-11-04", "previous_date": "2026-11-03", "previous_markets": "1000", "markets": "1000",
            "carried": "900", "left": "100", "appeared": "100", "appeared_created_before_previous_start": "0"}
    quiet = collector.consistency_line({**base, "previous_missed_at_most": "99"})
    loud = collector.consistency_line({**base, "previous_missed_at_most": "100"})
    assert "FINDING" not in quiet and "missed at most 99 (9.900% of its 1000)" in quiet
    assert "FINDING" in loud
    assert collector.MISSED_PAGE_THRESHOLD == 100


def test_compare_snapshots_without_a_snapshot_before_the_previous_reports_zero_missed():
    started = dt.datetime(2026, 11, 3, 4, 40, tzinfo=dt.UTC)
    counts = collector.compare_snapshots({"1": "", "2": ""}, started, {"2": "", "3": "x-not-a-time"}, None)
    assert counts == {"previous_markets": 2, "markets": 2, "carried": 1, "left": 1, "appeared": 1,
                      "appeared_created_before_previous_start": 0, "previous_missed_at_most": 0}
