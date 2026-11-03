"""Tests of the Study 013 resolution fetch (PREREGISTRATION.md §5.3, §6.6), on in-memory bodies.

No network: fake fetchers return bodies built here. The checks: the two files hold what §5.3 says and
nothing else (no outcome field in status.jsonl, no status field in outcome.jsonl, bodies not kept, every
body hashed into the manifest); a market failing after three attempts is written as failed and counted;
the fetch refuses before the deadline and after completion; it resumes without re-fetching; a shape failure
on every first market aborts with no line written; the candidate set is every id in the window's snapshots.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest
from src import resolution as rs
from src.snapshots import Snapshot, SnapshotHashMismatch, candidate_set

UTC = dt.UTC
AFTER = dt.datetime(2027, 1, 20, 0, 5, tzinfo=UTC)


def gamma_body(i: int, uma="resolved", prices='["1", "0"]') -> bytes:
    return json.dumps({
        "id": str(i), "conditionId": f"0x{i:064x}", "question": f"Will thing {i} happen?", "description": "wording",
        "closedTime": "2026-11-20 12:00:00+00", "closed": True, "umaResolutionStatus": uma, "endDate": "2026-11-21T00:00:00Z",
        "volumeNum": 12345.0, "outcomes": '["Yes", "No"]', "clobTokenIds": json.dumps([str(10 * i), str(10 * i + 1)]),
        "outcomePrices": prices, "events": [{"id": 1000 + i, "title": "Parent"}], "tags": [{"label": "Politics"}],
    }).encode()


def clob_body(i: int) -> bytes:
    return json.dumps({"condition_id": f"0x{i:064x}", "tokens": [
        {"token_id": str(10 * i), "outcome": "Yes", "price": 1, "winner": True},
        {"token_id": str(10 * i + 1), "outcome": "No", "price": 0, "winner": False}]}).encode()


class Fake:
    def __init__(self, bodies: dict[str, bytes], fail: dict[str, int] | None = None):
        self.bodies, self.fail, self.calls = bodies, dict(fail or {}), []

    def __call__(self, key: str) -> bytes:
        self.calls.append(key)
        if self.fail.get(key, 0) > 0:
            self.fail[key] -= 1
            raise TimeoutError("simulated")
        return self.bodies[key]


def world(tmp_path: Path):
    return tmp_path / "data" / "raw" / "resolution", tmp_path / "paper-log" / "resolution_fetch.csv"


def test_two_files_hold_their_fields_only_and_bodies_are_hashed_not_kept(tmp_path: Path):
    out, log = world(tmp_path)
    cands = {str(i): f"0x{i:064x}" for i in range(3)}
    gamma = Fake({str(i): gamma_body(i) for i in range(3)})
    clob = Fake({f"0x{i:064x}": clob_body(i) for i in range(3)})
    row = rs.fetch_resolution(candidates=cands, out_dir=out, log_csv=log, gamma=gamma, clob=clob, now=lambda: AFTER, pause_s=0)
    assert row["complete"] == "yes" and row["candidates"] == "3" and row["fetched"] == "3" and row["failed"] == "0"
    status = [json.loads(line) for line in (out / "status.jsonl").read_text().splitlines()]
    outcome = [json.loads(line) for line in (out / "outcome.jsonl").read_text().splitlines()]
    assert [s["id"] for s in status] == ["0", "1", "2"] and [o["id"] for o in outcome] == ["0", "1", "2"]
    for s in status:
        assert set(s) == {"id", "conditionId", "closedTime", "closed", "umaResolutionStatus", "endDate", "volumeNum", "eventIds", "tagLabels",
                          "outcomeLabels", "clobTokenIds", "fetch_failed", "fetched_utc", "gamma_sha256", "clob_sha256"}
        assert "outcomePrices" not in s and "tokens" not in s and "question" not in s and "description" not in s
        assert s["eventIds"] == [str(1000 + int(s["id"]))] and s["tagLabels"] == ["Politics"] and s["fetch_failed"] is False
    for o in outcome:
        assert set(o) == {"id", "outcomePrices", "tokens", "fetched_utc", "gamma_sha256", "clob_sha256"}
        assert o["tokens"][0] == {"token_id": str(10 * int(o["id"])), "winner": True}
    # hashes are of the bodies; no body is kept anywhere under the output folder
    assert status[1]["gamma_sha256"] == hashlib.sha256(gamma_body(1)).hexdigest()
    assert status[1]["clob_sha256"] == hashlib.sha256(clob_body(1)).hexdigest()
    for f in out.iterdir():
        assert b"Will thing" not in f.read_bytes()
    manifest = [json.loads(line) for line in (out / "manifest.jsonl").read_text().splitlines()]
    assert len(manifest) == 6 and all(m["ok"] and len(m["sha256"]) == 64 and m["bytes"] > 0 for m in manifest)
    with open(log, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1 and rows[0]["status_sha256"] == hashlib.sha256((out / "status.jsonl").read_bytes()).hexdigest()
    assert tuple(rows[0]) == rs.LOG_COLUMNS


def test_retries_three_times_then_writes_a_failed_line_and_counts_it(tmp_path: Path):
    out, log = world(tmp_path)
    cands = {"0": "0xa", "1": "0xb"}
    gamma = Fake({"0": gamma_body(0), "1": gamma_body(1)}, fail={"1": 2})  # two failures then success
    clob = Fake({"0xa": clob_body(0), "0xb": clob_body(1)}, fail={"0xa": 3})  # fails every attempt
    row = rs.fetch_resolution(candidates=cands, out_dir=out, log_csv=log, gamma=gamma, clob=clob, now=lambda: AFTER, pause_s=0)
    assert row["fetched"] == "1" and row["failed"] == "1"
    status = {json.loads(line)["id"]: json.loads(line) for line in (out / "status.jsonl").read_text().splitlines()}
    assert status["0"]["fetch_failed"] is True and status["0"]["reason"] == "request" and "umaResolutionStatus" not in status["0"]
    assert status["1"]["fetch_failed"] is False
    assert clob.calls.count("0xa") == 3 and gamma.calls.count("1") == 3
    outcome_ids = [json.loads(line)["id"] for line in (out / "outcome.jsonl").read_text().splitlines()]
    assert outcome_ids == ["1"]
    manifest = [json.loads(line) for line in (out / "manifest.jsonl").read_text().splitlines()]
    assert sum(1 for m in manifest if not m["ok"]) == 5 and all(m["error"] == "TimeoutError" for m in manifest if not m["ok"])


def test_refuses_before_the_deadline_and_after_completion(tmp_path: Path):
    out, log = world(tmp_path)
    gamma, clob = Fake({"0": gamma_body(0)}), Fake({"0xa": clob_body(0)})
    with pytest.raises(ValueError, match="before the scoring deadline"):
        rs.fetch_resolution(candidates={"0": "0xa"}, out_dir=out, log_csv=log, gamma=gamma, clob=clob,
                            now=lambda: dt.datetime(2027, 1, 19, 23, 59, tzinfo=UTC), pause_s=0)
    assert not out.exists() and gamma.calls == []
    rs.fetch_resolution(candidates={"0": "0xa"}, out_dir=out, log_csv=log, gamma=gamma, clob=clob, now=lambda: AFTER, pause_s=0)
    with pytest.raises(ValueError, match="ran once already"):
        rs.fetch_resolution(candidates={"0": "0xa"}, out_dir=out, log_csv=log, gamma=gamma, clob=clob, now=lambda: AFTER, pause_s=0)
    assert gamma.calls == ["0"]


def test_resumes_without_refetching_and_the_limit_never_completes_early(tmp_path: Path):
    out, log = world(tmp_path)
    cands = {str(i): f"0x{i:064x}" for i in range(5)}
    gamma = Fake({str(i): gamma_body(i) for i in range(5)})
    clob = Fake({f"0x{i:064x}": clob_body(i) for i in range(5)})
    first = rs.fetch_resolution(candidates=cands, out_dir=out, log_csv=log, gamma=gamma, clob=clob, now=lambda: AFTER, pause_s=0, limit=2)
    assert first["complete"] == "no" and first["remaining"] == "3" and not log.exists()
    assert len(gamma.calls) == 2
    second = rs.fetch_resolution(candidates=cands, out_dir=out, log_csv=log, gamma=gamma, clob=clob, now=lambda: AFTER, pause_s=0)
    assert second["complete"] == "yes" and second["fetched"] == "5" and sorted(gamma.calls) == [str(i) for i in range(5)]
    assert len((out / "status.jsonl").read_text().splitlines()) == 5


def test_shape_failure_on_every_first_market_aborts_with_no_line(tmp_path: Path):
    out, log = world(tmp_path)
    n = rs.SHAPE_ABORT_AFTER + 5
    cands = {str(i): f"0x{i:064x}" for i in range(n)}
    gamma = Fake({str(i): json.dumps({"unexpected": True}).encode() for i in range(n)})
    clob = Fake({f"0x{i:064x}": clob_body(i) for i in range(n)})
    with pytest.raises(rs.ShapeError, match="all failed on shape"):
        rs.fetch_resolution(candidates=cands, out_dir=out, log_csv=log, gamma=gamma, clob=clob, now=lambda: AFTER, pause_s=0)
    assert (out / "status.jsonl").read_text() == "" and (out / "outcome.jsonl").read_text() == ""
    assert len(gamma.calls) == rs.SHAPE_ABORT_AFTER  # the budget stops there
    # a single shape failure among sound markets is a counted failure, not an abort
    gamma2 = Fake({"0": json.dumps({"id": "99"}).encode(), **{str(i): gamma_body(i) for i in range(1, 4)}})
    clob2 = Fake({f"0x{i:064x}": clob_body(i) for i in range(4)})
    out2, log2 = world(tmp_path / "two")
    row = rs.fetch_resolution(candidates={str(i): f"0x{i:064x}" for i in range(4)}, out_dir=out2, log_csv=log2, gamma=gamma2, clob=clob2,
                              now=lambda: AFTER, pause_s=0)
    assert row["failed"] == "1" and row["fetched"] == "3"
    status = {json.loads(line)["id"]: json.loads(line) for line in (out2 / "status.jsonl").read_text().splitlines()}
    assert status["0"]["fetch_failed"] and status["0"]["reason"] == "shape"


def test_candidate_set_is_every_id_in_the_window_snapshots(tmp_path: Path):
    root = tmp_path / "snapshots"
    days = {dt.date(2026, 11, 2): ["1", "2"], dt.date(2026, 11, 3): ["2", "3"], dt.date(2026, 12, 28): ["4"], dt.date(2026, 12, 29): ["5"]}
    snaps = []
    for d, ids in days.items():
        (root / d.isoformat()).mkdir(parents=True)
        text = "".join(json.dumps({"id": i, "conditionId": "0x" + i, "bestBid": 0.5}) + "\n" for i in ids)
        (root / d.isoformat() / "records.jsonl").write_text(text, encoding="utf-8")
        snaps.append(Snapshot(date=d, started=dt.datetime(d.year, d.month, d.day, 4, 40, tzinfo=UTC), distinct_markets=len(ids),
                              records_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest()))
    c = candidate_set(root, snaps, rs.FIRST_DAY, rs.LAST_DAY)
    assert c == {"2": "0x2", "3": "0x3", "4": "0x4"}  # S0's market 1 and 12-29's market 5 are not candidates
    # every snapshot is verified against the hash logged on its day before a row is read (code review of
    # 2026-11-03, must-fix 4): one edited byte in 12-28's file refuses the whole candidate set
    target = root / "2026-12-28" / "records.jsonl"
    target.write_bytes(target.read_bytes().replace(b"0.5", b"0.6", 1))
    with pytest.raises(SnapshotHashMismatch, match="2026-12-28: records.jsonl hashes to"):
        candidate_set(root, snaps, rs.FIRST_DAY, rs.LAST_DAY)
