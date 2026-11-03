"""Tests of the Study 013 data step (PREREGISTRATION.md §6.6), on synthetic snapshots built in memory.

No network and no real snapshot: every snapshot folder, log line and status row is written under
tmp_path by the fixtures here, in the shape `collector.py` writes (list fields as JSON strings).
Every path is passed by name. The checks §6.6 names: the snapshot-of-record choice (latest t_s <= T - h,
the gap cap, the S bound, S0 never chosen); every eligibility rule and its counter; the cluster rule
including a market in two events; the decoding of string-encoded lists; the data step refusing to open
the outcome file; the gap-day rules of §5.4; plus the halt rules, the early flag and the power row.
"""

from __future__ import annotations

import ast
import builtins
import csv
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path

import numpy as np
import pytest
from src import data_step as ds
from src.snapshots import Snapshot

UTC = dt.UTC
S = ds.S


def ts(day: dt.date, hh: int = 4, mm: int = 40) -> dt.datetime:
    return dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=UTC)


def row(i: int, **over: object) -> dict:
    """One whitelisted snapshot row, eligible under §6.3 by default."""
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
        "eventIds": [str(1000 + i // 2)],
        "tagLabels": ["Elections", "Politics"],
    }
    r.update(over)
    return r


class World:
    """A study folder under tmp_path: snapshots, log, status file, results folder."""

    def __init__(self, root: Path):
        self.root = root
        self.snapshot_root = root / "data" / "raw" / "snapshots"
        self.log = root / "paper-log" / "snapshots.csv"
        self.status = root / "data" / "raw" / "resolution" / "status.jsonl"
        self.fetch_log = root / "paper-log" / "resolution_fetch.csv"
        self.results = root / "results"
        self.log.parent.mkdir(parents=True)
        self.status.parent.mkdir(parents=True)
        self.fetch_log.write_text("started_utc\n2027-01-20T00:10:00Z\n", encoding="utf-8")
        self.status.write_text("", encoding="utf-8")
        with open(self.log, "w", newline="", encoding="utf-8") as f:
            csv.writer(f, lineterminator="\n").writerow(
                ["snapshot_date", "started_utc", "finished_utc", "pages", "rows", "distinct_markets", "bytes", "records_sha256", "pages_sha256"]
            )

    def snapshot(self, day: dt.date, rows: list[dict], started: dt.datetime | None = None, distinct: int | None = None) -> None:
        folder = self.snapshot_root / day.isoformat()
        folder.mkdir(parents=True)
        text = "".join(json.dumps(r) + "\n" for r in rows)
        (folder / "records.jsonl").write_text(text, encoding="utf-8")
        (folder / "pages.jsonl").write_text("", encoding="utf-8")
        t0 = started or ts(day)
        with open(self.log, "a", newline="", encoding="utf-8") as f:
            csv.writer(f, lineterminator="\n").writerow(
                [day.isoformat(), t0.strftime("%Y-%m-%dT%H:%M:%SZ"), (t0 + dt.timedelta(minutes=4)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 1, len(rows), distinct if distinct is not None else len(rows), 1,
                 hashlib.sha256(text.encode("utf-8")).hexdigest(), "b" * 64]  # the real hash, as the collector logs it
            )

    def status_row(self, mid: str, closed: dt.datetime | None, failed: bool = False) -> None:
        with open(self.status, "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": mid, "closedTime": closed.strftime("%Y-%m-%dT%H:%M:%SZ") if closed else None, "fetch_failed": failed}) + "\n")

    def run(self, **kw) -> dict:
        return ds.run_data_step(snapshot_root=self.snapshot_root, snapshot_log=self.log, status_jsonl=self.status,
                                results_dir=self.results, fetch_log_csv=self.fetch_log,
                                now=dt.datetime(2027, 1, 21, tzinfo=UTC), **kw)


def full_window(world: World, rows_by_day=None, skip: set[dt.date] = frozenset(), n_rows: int = 10) -> None:
    """Every serving day from S to 2026-12-28 with the same rows (so the gap rules see a full window)."""
    d = S
    while d <= dt.date(2026, 12, 28):
        if d not in skip:
            rows = rows_by_day(d) if rows_by_day else [row(i) for i in range(n_rows)]
            world.snapshot(d, rows)
        d += dt.timedelta(days=1)


# ---- snapshot of record (§5.2) ----


def snaps(*days: dt.date) -> list[Snapshot]:
    return [Snapshot(date=d, started=ts(d), distinct_markets=10, records_sha256="x") for d in days]


def test_snapshot_of_record_is_the_latest_at_or_before_t_minus_h():
    d1, d2, d3 = dt.date(2026, 11, 10), dt.date(2026, 11, 11), dt.date(2026, 11, 12)
    usable = snaps(d1, d2, d3)
    t_close = ts(d3) + dt.timedelta(hours=30)  # 2026-11-13 10:40Z; T - 24 h = 11-12 10:40Z: the 11-12 snapshot (04:40Z) serves
    assert ds.snapshot_of_record(t_close, 24, usable).date == d3
    t_close = ts(d3) + dt.timedelta(hours=23)  # T - 24 h is before the 11-12 snapshot: 11-11 serves
    assert ds.snapshot_of_record(t_close, 24, usable).date == d2
    # exactly t_s = T - h is allowed (<=)
    assert ds.snapshot_of_record(ts(d3) + dt.timedelta(hours=24), 24, usable).date == d3
    # the 168-hour horizon reaches back a week
    assert ds.snapshot_of_record(ts(d3) + dt.timedelta(hours=168), 168, usable).date == d3
    assert ds.snapshot_of_record(ts(d3) + dt.timedelta(hours=167), 168, usable).date == d2


def test_snapshot_of_record_applies_the_gap_cap_and_never_chooses_s0():
    d1 = dt.date(2026, 11, 10)
    usable = snaps(d1)
    # T - t_s = 24 h + 47 h: inside the cap; 24 h + 48 h: not in the sample
    assert ds.snapshot_of_record(ts(d1) + dt.timedelta(hours=71), 24, usable) is not None
    assert ds.snapshot_of_record(ts(d1) + dt.timedelta(hours=72), 24, usable) is None
    # S0 = 2026-11-02 is never chosen even when it is the only snapshot before T - h
    s0 = Snapshot(date=dt.date(2026, 11, 2), started=ts(dt.date(2026, 11, 2), 6, 21), distinct_markets=10, records_sha256="x")
    assert ds.snapshot_of_record(ts(dt.date(2026, 11, 3)) + dt.timedelta(hours=20), 24, [s0]) is None
    assert ds.snapshot_of_record(ts(dt.date(2026, 11, 4)) + dt.timedelta(hours=30), 24, [s0, *snaps(dt.date(2026, 11, 4))]).date == dt.date(2026, 11, 4)


# ---- eligibility (§6.3), one counter each, in order ----


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({"outcomes": '["Yes", "No", "Maybe"]'}, ds.EXCLUSION_ORDER[0]),
        ({"clobTokenIds": '["1"]'}, ds.EXCLUSION_ORDER[0]),
        ({"outcomes": "not json"}, ds.EXCLUSION_ORDER[0]),
        ({"enableOrderBook": False}, ds.EXCLUSION_ORDER[1]),
        ({"active": False}, ds.EXCLUSION_ORDER[2]),
        ({"closed": True}, ds.EXCLUSION_ORDER[2]),
        ({"acceptingOrders": False}, ds.EXCLUSION_ORDER[2]),
        ({"umaResolutionStatus": "proposed"}, ds.EXCLUSION_ORDER[3]),
        ({"umaResolutionStatus": "disputed"}, ds.EXCLUSION_ORDER[3]),
        ({"umaResolutionStatus": "resolved"}, ds.EXCLUSION_ORDER[3]),
        ({"endDate": None}, ds.EXCLUSION_ORDER[4]),
        ({"endDate": "2026-11-01T00:00:00Z"}, ds.EXCLUSION_ORDER[4]),
        ({"bestBid": None}, ds.EXCLUSION_ORDER[5]),
        ({"bestBid": 0.0, "bestAsk": 0.02}, ds.EXCLUSION_ORDER[5]),
        ({"bestBid": 0.5, "bestAsk": 0.4}, ds.EXCLUSION_ORDER[5]),
        ({"bestBid": 0.98, "bestAsk": 1.0}, ds.EXCLUSION_ORDER[5]),
        ({"bestBid": 0.30, "bestAsk": 0.41}, ds.EXCLUSION_ORDER[6]),
        ({"bestBid": 0.001, "bestAsk": 0.005}, ds.EXCLUSION_ORDER[7]),
        ({"bestBid": 0.99, "bestAsk": 0.995}, ds.EXCLUSION_ORDER[7]),
        ({"volumeNum": 9999.99}, ds.EXCLUSION_ORDER[8]),
        ({"volumeNum": None}, ds.EXCLUSION_ORDER[8]),
    ],
)
def test_each_eligibility_rule_excludes_under_its_own_reason(over, reason):
    got, facts = ds.eligibility(row(1, **over), ts(dt.date(2026, 11, 10)))
    assert got == reason and facts is None


def test_eligible_row_gives_mid_price_cluster_and_facts():
    reason, facts = ds.eligibility(row(1, bestBid=0.30, bestAsk=0.40, volumeNum=10_000.0), ts(dt.date(2026, 11, 10)))
    assert reason is None and facts is not None
    assert facts.p == pytest.approx(0.35)
    assert facts.cluster == "1000" and facts.n_events == 1 and not facts.cluster_unparsed
    assert facts.first_label_yes and not facts.sports and facts.listing_mid == pytest.approx(0.42)
    assert facts.first_token == "10"  # clobTokenIds[0] of the row, decoded from its JSON string (§6.2)
    # the first failing reason counts: a row failing both the spread and the floor is counted under the spread
    reason, _ = ds.eligibility(row(2, bestBid=0.30, bestAsk=0.41, volumeNum=1.0), ts(dt.date(2026, 11, 10)))
    assert reason == ds.EXCLUSION_ORDER[6]


def test_string_encoded_lists_and_plain_lists_both_decode():
    a = ds.eligibility(row(1, outcomes='["Yes", "No"]', clobTokenIds='["5", "6"]'), ts(S))
    b = ds.eligibility(row(1, outcomes=["Yes", "No"], clobTokenIds=["5", "6"], outcomePrices=["0.42", "0.58"]), ts(S))
    assert a[0] is None and b[0] is None
    assert a[1].listing_mid == b[1].listing_mid == pytest.approx(0.42)


def test_cluster_rule_smallest_event_id_two_events_and_unparsable_ids():
    assert ds.cluster_of(row(1, eventIds=["2001", "1999", "3000"])) == ("1999", False, 3)
    assert ds.cluster_of(row(1, eventIds=["9", "10"])) == ("9", False, 2)  # numeric, not string, order
    assert ds.cluster_of(row(1, eventIds=["abc", "10"])) == ("10", True, 2)  # string order, counted
    assert ds.cluster_of(row(7, eventIds=[])) == ("market:7", False, 0)


def test_sports_tag_is_exact_case_insensitive_and_tag_family_precedence():
    assert ds.eligibility(row(1, tagLabels=["sports", "NBA"]), ts(S))[1].sports
    assert ds.eligibility(row(1, tagLabels=["Sportsbook"]), ts(S))[1].sports is False
    assert ds.tag_family(["Crypto", "Politics"]) == "Politics"
    assert ds.tag_family(["NBA", "Sports", "Politics"]) == "Sports"
    assert ds.tag_family(["Weather"]) == "other"


def test_early_flag_is_closed_more_than_24_hours_before_the_scheduled_end():
    end = ts(dt.date(2026, 12, 31), 12, 0)
    assert ds.early_flag(end - dt.timedelta(hours=25), end)
    assert not ds.early_flag(end - dt.timedelta(hours=24), end)
    assert not ds.early_flag(end, None)


# ---- gap days (§5.4) ----


def test_gap_days_missing_short_listing_and_all_null_field():
    days = [S + dt.timedelta(days=k) for k in range(56)]
    assert days[-1] == dt.date(2026, 12, 28)
    present = [d for d in days if d not in {days[3], days[4]}]  # two missing days in a row
    snapshots = [Snapshot(date=d, started=ts(d), distinct_markets=200_000 if d != days[10] else 90_000, records_sha256="x") for d in present]
    snapshots.append(Snapshot(date=dt.date(2026, 11, 2), started=ts(dt.date(2026, 11, 2)), distinct_markets=5, records_sha256="s0"))  # S0 is not looked at
    nulls = {d: [] for d in present}
    nulls[days[20]] = ["endDate"]
    g = ds.classify_gaps(Path("unused"), snapshots, dt.date(2026, 12, 28), null_fields=nulls)
    assert g.gap_days[days[3].isoformat()] == "missing" and g.gap_days[days[4].isoformat()] == "missing"
    assert g.gap_days[days[10].isoformat()].startswith("short listing (90000")
    assert g.gap_days[days[20].isoformat()].startswith("field null on every row")
    assert len(g.gap_days) == 4 and g.serving_days_present == 52 and g.longest_run == 2
    assert not g.stop
    # a run of three stops; fewer than 42 present stops
    g3 = ds.classify_gaps(Path("unused"), [s for s in snapshots if s.date != days[5]], dt.date(2026, 12, 28), null_fields=nulls)
    assert g3.longest_run == 3 and g3.stop
    # fewer than 42 present stops on the floor alone: fifteen isolated gaps (no run above one), 41 present
    isolated = {days[k] for k in range(0, 56, 4)} | {days[54]}
    few = [Snapshot(date=d, started=ts(d), distinct_markets=200_000, records_sha256="x") for d in days if d not in isolated]
    nulls_few = {d: [] for d in days}
    g41 = ds.classify_gaps(Path("unused"), few, dt.date(2026, 12, 28), null_fields=nulls_few)
    assert g41.serving_days_present == 41 and g41.longest_run == 1 and g41.stop
    # the floor names the C1 window only (§5.4; code review of 2026-11-03, must-fix 2): the C1b window, nine
    # isolated gaps, 41 of 50 present, does not stop; with the floor applied it would
    nine = [S + dt.timedelta(days=k) for k in range(50) if k % 5 != 2]
    nulls_nine = {d: [] for d in nine}
    gb = ds.classify_gaps(Path("unused"), snaps(*nine), dt.date(2026, 12, 22), null_fields=nulls_nine, median=10, floor=False)
    assert gb.serving_days_present == 40 and gb.longest_run == 1 and not gb.stop
    assert ds.classify_gaps(Path("unused"), snaps(*nine), dt.date(2026, 12, 22), null_fields=nulls_nine, median=10, floor=True).stop


def test_all_null_fields_reads_rows(tmp_path: Path):
    w = World(tmp_path)
    d = S
    w.snapshot(d, [row(1, endDate=None), row(2, endDate=None), row(3, endDate=None, bestBid=None)])
    snap = Snapshot(date=d, started=ts(d), distinct_markets=3, records_sha256="x")
    assert ds.all_null_fields(w.snapshot_root, snap) == ["endDate"]  # bestBid is null on one row only
    # a correct open-market snapshot has the resolution status null on every row (its legitimate value when
    # no resolution has begun), and that is not a gap (§16 note of 2026-11-03; the first version flagged it)
    w.snapshot(d + dt.timedelta(days=1), [row(1), row(2)])
    assert ds.all_null_fields(w.snapshot_root, Snapshot(date=d + dt.timedelta(days=1), started=ts(d), distinct_markets=2, records_sha256="x")) == []
    assert "umaResolutionStatus" not in ds.GAP_FIELDS


# ---- the step end to end on a synthetic world ----


def build_world(tmp_path: Path, n_markets: int = 5200, clusters: int = 2600, seed: int = 13, skip: set[dt.date] = frozenset()) -> World:
    """A full window of identical snapshots over n_markets eligible markets, each closing inside the window."""
    rng = np.random.default_rng(seed)
    bids = rng.uniform(0.05, 0.90, size=n_markets)
    rows = []
    for i in range(n_markets):
        bid = round(float(bids[i]), 2)
        rows.append(row(i, bestBid=bid, bestAsk=round(bid + 0.02, 2), outcomePrices=json.dumps([f"{bid + 0.01:.3f}", f"{1 - bid - 0.01:.3f}"]),
                        eventIds=[str(5000 + i % clusters)], tagLabels=["Sports"] if i % 3 == 0 else ["Politics"]))
    w = World(tmp_path)
    full_window(w, rows_by_day=lambda d: rows, skip=skip)
    for i in range(n_markets):
        # closes at 12:00Z on a day spread over the window [11-04, 12-30)
        close_day = dt.date(2026, 11, 4) + dt.timedelta(days=i % 56)
        w.status_row(str(i), ts(close_day, 12, 0))
    return w


def test_data_step_end_to_end_samples_counts_and_power(tmp_path: Path):
    w = build_world(tmp_path)
    w.status_row("999999", ts(dt.date(2027, 1, 5)))  # a candidate? no: not in any snapshot, so not a candidate
    r = w.run()
    c1, c1a, c1b = r["trials"]["C1"], r["trials"]["C1a"], r["trials"]["C1b"]
    assert r["counts"]["candidates"] == 5200 and r["counts"]["windowed"] == 5200
    # C1: every market has a snapshot of record (12:00Z close, 04:40Z snapshot the day before: 31.3 h in [24, 72))
    assert c1["n"] == 5200 and c1["G"] == 2600 and c1["excluded"][ds.NO_SNAPSHOT_REASON] == 0
    assert c1["realised_horizon_hours"]["min"] == pytest.approx(31.3333, abs=1e-3)
    # C1a sets Sports aside under its own counter
    assert c1a["n"] == 5200 - len([i for i in range(5200) if i % 3 == 0]) and c1a["excluded"][ds.SPORTS_REASON] == 1734
    # C1b: a market closing before S + 168 h has no snapshot of record; the rest do
    early_closers = sum(1 for i in range(5200) if ts(dt.date(2026, 11, 4) + dt.timedelta(days=i % 56), 12, 0) - dt.timedelta(hours=168) < ts(S))
    assert c1b["excluded"][ds.NO_SNAPSHOT_REASON] == early_closers and c1b["n"] == 5200 - early_closers
    # halves, early flag, labels, price check, power
    assert c1["n_W1"] + c1["n_W2"] == 5200 and c1["n_W1"] == sum(1 for i in range(5200) if i % 56 < 28)
    assert c1["early_share"] == 1.0  # every synthetic market closes before its 12-31 scheduled end by more than a day
    assert r["price_field_check"]["pass"] and r["price_field_check"]["rows"] == 5200
    assert set(r["tag_labels_in_C1_sample"]) == {"Sports", "Politics"}
    assert c1["sports_share"] == pytest.approx(1734 / 5200)
    p = np.array([0.01 + round(float(b), 2) for b in np.random.default_rng(13).uniform(0.05, 0.90, size=5200)])
    expect = ds.fit.power_row(p, 2600)
    assert c1["power"]["E_hat"] == pytest.approx(expect["E_hat"], rel=1e-9) and c1["power"]["ratio"] == pytest.approx(expect["ratio"], rel=1e-9)
    assert not r["halted"] and not r["stopped_for_amendment"] and r["verdict_row"] is None and r["no_outcome_read"]
    # outputs: four files; the sample holds one line per (trial, market); the manifest hashes the sample
    sample = [json.loads(line) for line in (w.results / "sample.jsonl").read_text().splitlines()]
    assert len(sample) == c1["n"] + c1a["n"] + c1b["n"]
    assert {s["trial"] for s in sample} == {"C1", "C1a", "C1b"}
    # every sample row names the first listed token of its snapshot-of-record row, which the scoring run's outcome rule needs
    assert all(s["first_token"] == str(10 * int(s["market"])) for s in sample)
    manifest = json.loads((w.results / "data_manifest.json").read_text())
    assert len(manifest["sample_jsonl_sha256"]) == 64 and manifest["snapshots_read"]
    md = (w.results / "data_step.md").read_text()
    assert "| C1 | 24 | 5200 | 2600 |" in md
    # no raw venue field name in the committed outputs (tools/check_data_terms.py markers)
    for name in ("data_step.json", "data_step.md", "data_manifest.json"):
        text = (w.results / name).read_text()
        assert '"clobTokenIds"' not in text and '"outcomePrices"' not in text and "volumeNum" not in text


def test_data_step_never_opens_the_outcome_file(tmp_path: Path, monkeypatch):
    w = build_world(tmp_path, n_markets=60, clusters=30)
    forbidden = w.status.parent / "outcome.jsonl"
    forbidden.write_text('{"id": "0"}\n', encoding="utf-8")
    real_open, real_io_open, real_os_open = builtins.open, io.open, os.open

    def guard(file, *a, **k):
        if "outcome.jsonl" in str(file):
            raise AssertionError("the data step opened the outcome file")
        return real_open(file, *a, **k)

    def io_guard(file, *a, **k):  # Path.read_text / Path.open go through io.open, not builtins.open
        if "outcome.jsonl" in str(file):
            raise AssertionError("the data step opened the outcome file")
        return real_io_open(file, *a, **k)

    def os_guard(path, *a, **k):
        if "outcome.jsonl" in str(path):
            raise AssertionError("the data step opened the outcome file")
        return real_os_open(path, *a, **k)

    monkeypatch.setattr(builtins, "open", guard)
    monkeypatch.setattr(io, "open", io_guard)
    monkeypatch.setattr(os, "open", os_guard)
    r = w.run()
    assert r["no_outcome_read"] and r["trials"]["C1"]["n"] == 60
    # and no string literal in the module names the file or any .jsonl with "outcome" in it, so no path to it
    # can be built (the first version of this check compared against a list that was always empty)
    src = Path(ds.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, ast.Module | ast.FunctionDef | ast.ClassDef) and node.body
                  and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)}
    literals = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings]
    jsonl_literals = [s for s in literals if ".jsonl" in s]
    assert jsonl_literals  # the check is not vacuous: the module does name status.jsonl and sample.jsonl
    assert "outcome.jsonl" not in src and not [s for s in jsonl_literals if "outcome" in s.lower()]


def test_data_step_halts_on_small_samples_and_on_the_price_check(tmp_path: Path):
    w = build_world(tmp_path, n_markets=60, clusters=30)
    r = w.run()
    assert r["halted"] and r["verdict_row"] == "inconclusive (halted at the data step)"
    assert any("clusters" in h for h in r["halt_reasons"]) and any("markets" in h for h in r["halt_reasons"])
    assert (w.results / "data_step.json").exists()  # the counts are published whatever they show
    # the price-field check: listing mids far from (bid + ask)/2 on more than 1 percent of rows
    w2 = World(tmp_path / "w2")
    rows = [row(i, outcomePrices='["0.90", "0.10"]') for i in range(50)]
    full_window(w2, rows_by_day=lambda d: rows)
    for i in range(50):
        w2.status_row(str(i), ts(dt.date(2026, 11, 20), 12, 0))
    r2 = w2.run()
    assert not r2["price_field_check"]["pass"] and r2["price_field_check"]["within_0.02"] == 0
    assert any("price-field" in h for h in r2["halt_reasons"])


def test_data_step_stops_for_amendment_on_gap_run_and_refuses_twice_without_one(tmp_path: Path):
    # a full-size world (no halt) with a run of three missing days: stops for an amendment, and only then re-runs
    w = build_world(tmp_path, skip={S + dt.timedelta(days=k) for k in (10, 11, 12)})
    r = w.run()
    assert r["stopped_for_amendment"] and not r["halted"]
    assert r["gap_days"]["C1 and C1a (to 2026-12-28)"]["longest_run"] == 3
    assert r["gap_days"]["C1 and C1a (to 2026-12-28)"]["serving_days_present"] == 53
    with pytest.raises(ds.Refusal, match="runs once"):
        w.run()
    r2 = w.run(amendment="§16 note of 2027-01-22: gap cap widened to h + 72 h")
    assert r2["amendment"].startswith("§16")
    # a run that both stops and halts: the halt wins and no amendment re-runs it (§16 note of 2026-11-03)
    w2 = World(tmp_path / "w2")
    rows = [row(i) for i in range(20)]
    full_window(w2, rows_by_day=lambda d: rows, skip={S + dt.timedelta(days=k) for k in (10, 11, 12)})
    for i in range(20):
        w2.status_row(str(i), ts(dt.date(2026, 11, 20), 12, 0))
    r3 = w2.run()
    assert r3["stopped_for_amendment"] and r3["halted"] and r3["verdict_row"] == "inconclusive (halted at the data step)"
    with pytest.raises(ds.Refusal, match="halted the study permanently"):
        w2.run(amendment="§16 note of 2027-01-22: gap cap widened to h + 72 h")


def test_data_step_refuses_before_the_fetch_and_counts_failed_and_unwindowed(tmp_path: Path):
    w = World(tmp_path)
    w.fetch_log.unlink()
    with pytest.raises(ds.Refusal, match="resolution fetch has not completed"):
        w.run()
    w.fetch_log.write_text("started_utc\nx\n", encoding="utf-8")
    rows = [row(i) for i in range(6)]
    full_window(w, rows_by_day=lambda d: rows)
    w.status_row("0", ts(dt.date(2026, 11, 20), 12, 0))
    w.status_row("1", None)  # no close time
    w.status_row("2", ts(dt.date(2027, 1, 2)))  # after the window
    w.status_row("3", ts(dt.date(2026, 11, 3), 23, 0))  # before the window
    w.status_row("4", ts(dt.date(2026, 11, 20)), failed=True)
    # market 5: no status row at all
    r = w.run()
    assert r["counts"]["candidates"] == 6 and r["counts"]["windowed"] == 1
    assert r["counts"]["candidates_unfetched_or_failed"] == 2 and r["counts"]["candidates_without_close_time"] == 1
    assert r["trials"]["C1"]["n"] == 1


def test_market_absent_from_its_snapshot_of_record_is_counted(tmp_path: Path):
    w = World(tmp_path)
    full_window(w, rows_by_day=lambda d: [row(1)] if d != dt.date(2026, 11, 19) else [row(2)])
    w.status_row("1", ts(dt.date(2026, 11, 20), 12, 0))  # snapshot of record is 11-19, where market 1 is absent
    w.status_row("2", ts(dt.date(2026, 11, 20), 12, 0))
    r = w.run()
    assert r["trials"]["C1"]["excluded"][ds.NO_ROW_REASON] == 1 and r["trials"]["C1"]["n"] == 1


# ---- the code review of 2026-11-03 (must-fix 1 to 4; should-fix 5) ----


def test_price_check_counts_every_c1_row_and_a_missing_mid_as_outside(tmp_path: Path):
    # must-fix 1: rows without a decodable listing mid were dropped from the denominator, so 20 null mids out of
    # 40 rows read as "20 of 20 within" and passed; §6.2 names the C1 sample's rows as the denominator
    w = World(tmp_path)
    rows = [row(i, outcomePrices=None if i % 2 else '["0.42", "0.58"]') for i in range(40)]
    full_window(w, rows_by_day=lambda d: rows)
    for i in range(40):
        w.status_row(str(i), ts(dt.date(2026, 11, 20), 12, 0))
    r = w.run()
    pc = r["price_field_check"]
    assert pc["rows"] == 40 and pc["within_0.02"] == 20 and pc["rows_without_listing_mid"] == 20 and not pc["pass"]
    assert r["halted"] and any("price-field" in h and "20 without a decodable mid" in h for h in r["halt_reasons"])


def test_the_floor_applies_to_the_c1_window_only_and_one_median_serves_both(tmp_path: Path):
    # must-fix 2: nine isolated gaps before 12-22 leave C1 with 47 of 56 days and C1b with 41 of 50; the first
    # version applied the floor to both and stopped for an amendment §5.4 does not require. Should-fix 4: one
    # median over the 56-day window, one set of usable days.
    w = World(tmp_path)
    rows = [row(i) for i in range(20)]
    skip = {S + dt.timedelta(days=k) for k in (2, 5, 8, 11, 14, 17, 20, 23, 26)}
    full_window(w, rows_by_day=lambda d: rows, skip=skip)
    for i in range(20):
        w.status_row(str(i), ts(dt.date(2026, 12, 27), 12, 0))
    r = w.run()
    g1, g1b = r["gap_days"]["C1 and C1a (to 2026-12-28)"], r["gap_days"]["C1b (to 2026-12-22)"]
    assert g1["serving_days_present"] == 47 and g1["longest_run"] == 1
    assert g1b["serving_days_present"] == 41 and g1b["longest_run"] == 1
    assert not r["stopped_for_amendment"]
    # the gap-cap reason is counted apart from "none before T - h" (should-fix 5): with 11-05 and 11-06 missing, a
    # market closing at 12:00Z on 11-06 reads the 11-04 snapshot (04:40Z), 55.3 h before close, inside the cap of
    # 72 h; one closing at 12:00Z on 11-07 would read the same snapshot 79.3 h before close, outside it
    w2 = World(tmp_path / "w2")
    full_window(w2, rows_by_day=lambda d: rows, skip={dt.date(2026, 11, 5), dt.date(2026, 11, 6)})
    w2.status_row("0", ts(dt.date(2026, 11, 6), 12, 0))
    w2.status_row("1", ts(dt.date(2026, 11, 7), 12, 0))
    r2 = w2.run()
    c1 = r2["trials"]["C1"]
    assert c1["n"] == 1 and c1["excluded"][ds.GAP_CAP_REASON] == 1 and c1["excluded"][ds.NO_SNAPSHOT_REASON] == 0
    assert c1["realised_horizon_hours"]["max"] == pytest.approx(55.3333, abs=1e-3)
    assert not r2["stopped_for_amendment"]  # two missing days in a row: no stop


def test_a_rerun_follows_a_stop_only_and_names_an_amendment_dated_in_the_register(tmp_path: Path):
    # must-fix 3: any --amendment text allowed a re-run, even after a permanent halt, and overwrote the report
    w = World(tmp_path)
    rows = [row(i) for i in range(5)]
    full_window(w, rows_by_day=lambda d: rows)
    for i in range(5):
        w.status_row(str(i), ts(dt.date(2026, 11, 20), 12, 0))
    w.results.mkdir()
    report = w.results / "data_step.json"
    report.write_text(json.dumps({"halted": True, "stopped_for_amendment": True}), encoding="utf-8")
    with pytest.raises(ds.Refusal, match="halted the study permanently"):
        w.run(amendment="§16 note of 2027-01-22: anything")
    report.write_text(json.dumps({"halted": False, "stopped_for_amendment": False}), encoding="utf-8")
    with pytest.raises(ds.Refusal, match="did not stop for a gap amendment"):
        w.run(amendment="§16 note of 2027-01-22: gap cap widened")
    report.write_text(json.dumps({"halted": False, "stopped_for_amendment": True}), encoding="utf-8")
    register = tmp_path / "PREREGISTRATION.md"
    register.write_text("## 15. Not\n\n2027-01-23 is mentioned here only.\n\n## 16. Amendments\n\n- **2027-01-22 (gap amendment):** the cap is h + 72 h.\n", encoding="utf-8")
    with pytest.raises(ds.Refusal, match="must carry the amendment's date"):
        w.run(amendment="gap cap widened", amendment_register=register)
    with pytest.raises(ds.Refusal, match="no §16 amendment dated 2027-01-23"):
        w.run(amendment="§16 note of 2027-01-23: gap cap widened", amendment_register=register)
    assert report.read_text(encoding="utf-8").startswith('{"halted": false')  # nothing overwritten by a refusal
    r = w.run(amendment="§16 note of 2027-01-22: gap cap widened to h + 72 h", amendment_register=register)
    assert r["amendment"].startswith("§16") and r["trials"]["C1"]["n"] == 5


def test_an_edited_snapshot_is_refused_before_any_row_is_read(tmp_path: Path):
    # must-fix 4: the rows were read without a check against the hash logged on the snapshot's day
    w = World(tmp_path)
    rows = [row(i) for i in range(5)]
    full_window(w, rows_by_day=lambda d: rows)
    for i in range(5):
        w.status_row(str(i), ts(dt.date(2026, 11, 20), 12, 0))
    target = w.snapshot_root / "2026-11-10" / "records.jsonl"
    data = target.read_bytes()
    edited = data.replace(b'"bestBid": 0.41', b'"bestBid": 0.61', 1)
    assert edited != data
    target.write_bytes(edited)
    with pytest.raises(ds.Refusal, match="2026-11-10: records.jsonl hashes to"):
        w.run()
    assert not w.results.exists()
    target.unlink()
    with pytest.raises(ds.Refusal, match="logged but records.jsonl is missing"):
        w.run()
    target.write_bytes(data)
    r = w.run()
    assert r["trials"]["C1"]["n"] == 5
    manifest = json.loads((w.results / "data_manifest.json").read_text(encoding="utf-8"))
    assert manifest["snapshots_verified_against_log"] and manifest["snapshots_read"]["2026-11-10"] == hashlib.sha256(data).hexdigest()
