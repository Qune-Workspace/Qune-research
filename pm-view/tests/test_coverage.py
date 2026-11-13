"""Coverage of the followed events (event_coverage.py, README rule 6 `[coverage:every-open-leg]`,
added 2026-11-13 12:15Z, predictions/POST_MORTEMS.md "Ten of eleven settled legs with
nothing to score"): the leg parser on the two time shapes Gamma writes, the four standings of a
leg, the miss record written once per leg, the decline tool's refusals, the due-register
line, and the committed files held to the same rules.  Every path is passed by name;
nothing touches the network or the real files except the read-only checks on the
committed record."""
import csv
import importlib.util
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import event_coverage as C

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parent
NOW = datetime(2026, 11, 13, 12, 30, tzinfo=UTC)


def market(mid: str, q: str, start: str, closed: bool = False, closed_time: str | None = None,
           prices: str | None = None) -> dict:
    return {"id": mid, "question": q, "startDate": start, "closed": closed, "closedTime": closed_time,
            "umaResolutionStatus": "resolved" if closed else None, "outcomePrices": prices, "volumeNum": "1000"}


EVENT = [{"id": "1292829", "slug": "ev-slug", "markets": [
    market("1", "dip to 75,000", "2026-11-01T05:07:10Z", True, "2026-11-06 15:21:15.647093+00", '["1", "0"]'),
    market("2", "dip to 70,000", "2026-11-01T05:07:10Z", True, "2026-11-13 03:04:12.310502+00", '["1", "0"]'),
    market("3", "dip to 67,500", "2026-11-01T05:07:10Z"),
    market("4", "dip to 65,000", "2026-11-01T05:07:10Z"),
    market("5", "reach 72,500", "2026-11-12T17:17:07Z"),
    market("6", "listed later", "2026-11-20T17:17:07Z"),
]}]


def write_fixture(tmp_path: Path, readings_ids: list[str], not_read: list[tuple[str, str]] = (),
                  view_days: list[str] = ("2026-11-06T06:16:38Z", "2026-11-13T06:17:41Z")) -> dict[str, Path]:
    pm = tmp_path / "pm-view"
    (pm / "data").mkdir(parents=True)
    paths = {"events": pm / "events.csv", "events_manifest": pm / "data" / "events_manifest.json",
             "readings": pm / "readings.csv", "not_read": pm / "not_read.csv", "manifest": pm / "data" / "manifest.json",
             "misses": pm / "coverage_misses.csv", "raw_dir": pm / "data" / "raw" / "events", "root": pm}
    paths["events"].write_text("venue,event_id,event_slug,method,followed_from,source\n"
                               "polymarket,1292829,ev-slug,btc_touch,2026-11-03,test\n")
    paths["manifest"].write_text(json.dumps([{"fetched_utc": d, "market_id": "x"} for d in view_days]))
    with paths["readings"].open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "market_id"])
        for i in readings_ids:
            w.writerow([f"R-{i}", i])
    if not_read:
        with paths["not_read"].open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(C.NOT_READ_COLUMNS))
            w.writeheader()
            for mid, day in not_read:
                w.writerow({"event_slug": "ev-slug", "market_id": mid, "view_day": day, "why": "test reason given",
                            "recorded_utc": "2026-11-13T06:30:00Z"})
    C.fetch("ev-slug", lambda url: json.dumps(EVENT).encode(), paths["raw_dir"], paths["events_manifest"], NOW,
            paths["root"])
    return paths


# --- parsing ------------------------------------------------------------------------------------

def test_parse_both_venue_time_shapes_and_refuse_others():
    a = C.parse_venue_time("2026-11-01T05:07:10Z")
    b = C.parse_venue_time("2026-11-13 03:04:12.310502+00")
    assert a == datetime(2026, 11, 1, 5, 7, 10, tzinfo=UTC)
    assert b.date() == date(2026, 11, 13) and b.tzinfo is not None
    assert C.parse_venue_time(None) is None and C.parse_venue_time("") is None
    assert C.parse_venue_time("13 November 2026") is None


def test_legs_of_reads_the_first_event_and_every_market():
    event, legs = C.legs_of(json.dumps(EVENT).encode())
    assert event["slug"] == "ev-slug" and len(legs) == 6
    settled = [g for g in legs if g.settled]
    assert [g.market_id for g in settled] == ["1", "2"]
    assert legs[2].settled is False and legs[2].closed_time is None


def test_legs_of_refuses_an_empty_listing():
    try:
        C.legs_of(b"[]")
    except ValueError as e:
        assert "empty" in str(e)
    else:
        raise AssertionError("an empty listing was accepted")


# --- standings ----------------------------------------------------------------------------------

def test_four_standings_as_of_the_view_day():
    _, legs = C.legs_of(json.dumps(EVENT))
    readings = [{"market_id": "1"}]
    not_read = [{"event_slug": "ev-slug", "market_id": "4", "view_day": "2026-11-13"}]
    at = datetime(2026, 11, 13, 6, 17, 41, tzinfo=UTC)
    by_id = {s.leg.market_id: s.status for s in C.coverage(legs, readings, not_read, at, "ev-slug")}
    assert by_id == {"1": "read", "2": "settled-unread", "3": "open-unread", "4": "declined", "5": "open-unread",
                     "6": "not-yet-listed"}


def test_a_decline_for_another_day_or_event_does_not_count():
    _, legs = C.legs_of(json.dumps(EVENT))
    other_day = [{"event_slug": "ev-slug", "market_id": "4", "view_day": "2026-11-06"}]
    other_event = [{"event_slug": "other", "market_id": "4", "view_day": "2026-11-13"}]
    for nr in (other_day, other_event):
        at = datetime(2026, 11, 13, 6, 17, 41, tzinfo=UTC)
        by_id = {s.leg.market_id: s.status for s in C.coverage(legs, [], nr, at, "ev-slug")}
        assert by_id["4"] == "open-unread"


def test_views_while_open_counts_the_view_instants_at_which_the_leg_was_open():
    _, legs = C.legs_of(json.dumps(EVENT))
    times = C.view_times([{"fetched_utc": "2026-11-06T06:16:38Z"}, {"fetched_utc": "2026-11-06T06:20:45Z"},
                          {"fetched_utc": "2026-11-13T06:17:41Z"}, {"fetched_utc": "bad"}])
    assert set(times) == {date(2026, 11, 6), date(2026, 11, 13)}
    assert times[date(2026, 11, 6)] == datetime(2026, 11, 6, 6, 16, 38, tzinfo=UTC)  # the day's first quote
    leg_75k, leg_70k, leg_late = legs[0], legs[1], legs[5]
    assert C.views_while_open(leg_70k, times) == 1  # open at the 6 Nov view; settled 13 Nov 03:04Z, before 06:17Z
    assert C.views_while_open(leg_75k, times) == 1  # settled 6 Nov 15:21Z, after that morning's view
    assert C.views_while_open(leg_late, times) == 0
    # the 70,000 leg at the 13 Nov view: settled three hours before the first quote, so not open then
    assert leg_70k.open_at(datetime(2026, 11, 13, 6, 17, 41, tzinfo=UTC)) is False
    assert leg_70k.open_at(datetime(2026, 11, 6, 6, 16, 38, tzinfo=UTC)) is True
    assert C.view_at_on(date(2026, 11, 7), times) == datetime(2026, 11, 7, 23, 59, 59, tzinfo=UTC)


# --- the tools on a fixture ---------------------------------------------------------------------

def test_fetch_keeps_raw_hashed_and_check_names_the_misses(tmp_path):
    p = write_fixture(tmp_path, readings_ids=["1"])
    entries = json.loads(p["events_manifest"].read_text())
    assert entries[0]["legs"] == 6 and entries[0]["legs_settled"] == 2 and len(entries[0]["sha256"]) == 64
    assert (p["root"] / entries[0]["raw"]).exists()
    lines: list[str] = []
    rc, totals = C.check(p["events"], p["events_manifest"], p["readings"], p["not_read"], p["manifest"],
                         datetime(2026, 11, 13, 6, 17, 41, tzinfo=UTC), p["root"], out=lines.append)
    assert rc == 1
    assert totals["ev-slug"] == {"read": 1, "declined": 0, "open-unread": 3, "settled-unread": 1, "not-yet-listed": 1}
    assert any("settled-unread" in ln and " 2 " in ln and "views while open 1" in ln for ln in lines)


def test_check_passes_when_every_open_leg_is_read_or_declined(tmp_path):
    p = write_fixture(tmp_path, readings_ids=["1", "2", "3"], not_read=[("4", "2026-11-13"), ("5", "2026-11-13")])
    rc, totals = C.check(p["events"], p["events_manifest"], p["readings"], p["not_read"], p["manifest"],
                         datetime(2026, 11, 13, 6, 17, 41, tzinfo=UTC), p["root"], out=lambda s: None)
    assert rc == 0 and totals["ev-slug"]["open-unread"] == 0 and totals["ev-slug"]["settled-unread"] == 0


def test_check_fails_without_a_listing_and_says_what_to_run(tmp_path):
    p = write_fixture(tmp_path, readings_ids=[])
    p["events_manifest"].unlink()
    lines: list[str] = []
    rc, _ = C.check(p["events"], p["events_manifest"], p["readings"], p["not_read"], p["manifest"],
                    datetime(2026, 11, 13, 6, 17, 41, tzinfo=UTC), p["root"], out=lines.append)
    assert rc == 1 and any("no listing kept" in ln and "event_coverage.py fetch ev-slug" in ln for ln in lines)


def test_check_refuses_a_raw_body_that_does_not_match_its_hash(tmp_path):
    p = write_fixture(tmp_path, readings_ids=[])
    entry = json.loads(p["events_manifest"].read_text())[0]
    raw = p["root"] / entry["raw"]
    raw.write_bytes(raw.read_bytes() + b" ")
    try:
        C.check(p["events"], p["events_manifest"], p["readings"], p["not_read"], p["manifest"],
                datetime(2026, 11, 13, 6, 17, 41, tzinfo=UTC), p["root"], out=lambda s: None)
    except ValueError as e:
        assert "hash" in str(e)
    else:
        raise AssertionError("an edited raw listing was read")


def test_record_writes_each_settled_unread_leg_once(tmp_path):
    p = write_fixture(tmp_path, readings_ids=["1"])
    args = (p["events"], p["events_manifest"], p["readings"], p["not_read"], p["manifest"], p["misses"],
            datetime(2026, 11, 13, 12, 30, tzinfo=UTC), p["root"])
    C.record(*args, dry_run=True, out=lambda s: None)
    assert not p["misses"].exists()
    C.record(*args, dry_run=False, out=lambda s: None)
    C.record(*args, dry_run=False, out=lambda s: None)
    rows = list(csv.DictReader(p["misses"].open()))
    assert [r["market_id"] for r in rows] == ["2"]
    assert rows[0]["settled_utc"] == "2026-11-13T03:04:12Z" and rows[0]["views_while_open"] == "1"
    assert rows[0]["noted_on"] == "2026-11-13" and len(rows[0]["listing_sha256"]) == 64
    assert tuple(rows[0].keys()) == C.MISSES_COLUMNS


def test_decline_refusals_and_one_row_per_leg_and_day(tmp_path):
    p = write_fixture(tmp_path, readings_ids=[])
    common = (p["events"], p["events_manifest"], p["root"], p["not_read"])
    assert C.decline(*common, "4", date(2026, 11, 13), "short", NOW, out=lambda s: None) == 2
    assert C.decline(*common, "abc", date(2026, 11, 13), "a reason long enough", NOW, out=lambda s: None) == 2
    assert C.decline(*common, "999", date(2026, 11, 13), "a reason long enough", NOW, out=lambda s: None) == 2
    assert not p["not_read"].exists()
    assert C.decline(*common, "4", date(2026, 11, 13), "mid below 0.01; the method has no reading there", NOW,
                     out=lambda s: None) == 0
    assert C.decline(*common, "4", date(2026, 11, 13), "mid below 0.01; the method has no reading there", NOW,
                     out=lambda s: None) == 0
    rows = list(csv.DictReader(p["not_read"].open()))
    assert len(rows) == 1 and rows[0]["event_slug"] == "ev-slug" and rows[0]["recorded_utc"] == "2026-11-13T12:30:00Z"


# --- the due register -----------------------------------------------------------------------------

def _check_due():
    spec = importlib.util.spec_from_file_location("check_due", ROOT / "tools" / "check_due.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["check_due"] = mod  # dataclasses resolve string annotations through sys.modules
    spec.loader.exec_module(mod)
    return mod


def test_due_register_before_the_first_covered_view_records_misses_only(tmp_path):
    cd = _check_due()
    write_fixture(tmp_path, readings_ids=["1"], view_days=["2026-11-13T06:17:41Z"])
    items = cd.pm_coverage_items(tmp_path, datetime(2026, 11, 13, 12, 30, tzinfo=UTC))
    assert [i.status for i in items] == ["DUE", "info"], [i.line() for i in items]
    assert "misses" in items[0].label and "event_coverage.py record" in items[0].detail
    assert "settled-unread 1" in items[1].detail and not any("2026-11-13" in i.label for i in items)


def test_due_register_holds_the_first_covered_view_to_every_open_leg(tmp_path):
    cd = _check_due()
    p = write_fixture(tmp_path, readings_ids=["1", "2"], view_days=["2026-11-13T06:17:41Z", "2026-11-20T06:17:41Z"])
    C.fetch("ev-slug", lambda url: json.dumps(EVENT).encode(), p["raw_dir"], p["events_manifest"],
            datetime(2026, 11, 20, 6, 20, tzinfo=UTC), p["root"])
    items = cd.pm_coverage_items(tmp_path, datetime(2026, 11, 20, 12, 30, tzinfo=UTC))
    due = [i for i in items if i.status == "DUE"]
    assert len(due) == 1 and "2026-11-20" in due[0].label and "3 leg(s) open" in due[0].detail, [i.line() for i in items]
    assert "3, 4, 5" in due[0].detail  # leg 6 is listed 20 Nov 17:17Z, after the view's first quote


def test_due_register_requires_a_listing_fetched_on_the_view_day(tmp_path):
    cd = _check_due()
    write_fixture(tmp_path, readings_ids=["1"], view_days=["2026-11-20T06:17:41Z"])
    # the only listing kept is from 13 Nov (write_fixture); the 20 Nov view has none
    items = cd.pm_coverage_items(tmp_path, datetime(2026, 11, 20, 12, 30, tzinfo=UTC))
    assert any(i.status == "DUE" and "no listing fetched" in i.detail and "2026-11-20" in i.label for i in items)


def test_due_register_passes_when_the_view_covered_every_leg(tmp_path):
    cd = _check_due()
    p = write_fixture(tmp_path, readings_ids=["1", "2", "3", "4", "5"], view_days=["2026-11-20T06:17:41Z"])
    C.fetch("ev-slug", lambda url: json.dumps(EVENT).encode(), p["raw_dir"], p["events_manifest"],
            datetime(2026, 11, 20, 6, 20, tzinfo=UTC), p["root"])
    items = cd.pm_coverage_items(tmp_path, datetime(2026, 11, 20, 12, 30, tzinfo=UTC))
    assert all(i.status in ("ok", "info") for i in items), [i.line() for i in items]


# --- the committed record -------------------------------------------------------------------------

def test_committed_events_register_names_followed_events_with_a_method():
    rows = C.read_csv(HERE / "events.csv")
    assert rows and tuple(rows[0].keys()) == C.EVENTS_COLUMNS
    for r in rows:
        assert r["venue"] == "polymarket" and r["event_id"].isdigit() and r["event_slug"]
        assert r["method"] in ("btc_touch", "fomc_bills")
        date.fromisoformat(r["followed_from"])


def test_committed_coverage_misses_are_well_formed_and_name_settled_legs():
    path = HERE / "coverage_misses.csv"
    if not path.exists():
        return
    rows = C.read_csv(path)
    slugs = {r["event_slug"] for r in C.read_csv(HERE / "events.csv")}
    seen: set[str] = set()
    for r in rows:
        assert tuple(r.keys()) == C.MISSES_COLUMNS
        assert r["event_slug"] in slugs and r["market_id"].isdigit() and r["market_id"] not in seen
        seen.add(r["market_id"])
        datetime.strptime(r["settled_utc"], C.UTC_STAMP_FORMAT)
        datetime.strptime(r["listed_utc"], C.UTC_STAMP_FORMAT)
        date.fromisoformat(r["noted_on"])
        assert int(r["views_while_open"]) >= 0 and len(r["listing_sha256"]) == 64
    read_ids = {r["market_id"] for r in C.read_csv(HERE / "readings.csv")}
    assert not seen & read_ids, "a leg with a reading is not a coverage miss"


def test_committed_not_read_rows_carry_a_reason_for_a_view_day():
    path = HERE / "not_read.csv"
    if not path.exists():
        return
    for r in C.read_csv(path):
        assert tuple(r.keys()) == C.NOT_READ_COLUMNS and len(r["why"].strip()) >= 12
        date.fromisoformat(r["view_day"])
        datetime.strptime(r["recorded_utc"], C.UTC_STAMP_FORMAT)
