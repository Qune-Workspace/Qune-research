"""The window a touch market's own rules open, read from the venue's text and carried from the
quote to the method and the reading (2026-11-14 06:15Z, predictions/POST_MORTEMS.md "A window
the venue moved and the method did not").

What was found: the venue re-lists a level after the original market settles, and the re-listed
market's resolution text counts price action from the market's creation only; barrier.py scanned
every leg from the first of the month and read P(touch) = 1.000 for four open legs the market
priced at 0.10 to 0.60.  Now: pm_lib.rules_window names the window class from the text; the quote
records it and the creation time; barrier.py takes the time per level and a touch before it is
not a touch; readings.py copies the time into the row and the gate holds the copy and refuses a
touch reading on a quote whose rules window is unrecorded or unknown; event_coverage prints the
class per leg and counts it per listing.  The texts below are the shapes' key phrases, not the
venue's text."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import barrier as B
import event_coverage as C
import fetch as F
import pm_lib as L
import pytest
import readings as R

MONTH_TEXT = ('This market will immediately resolve to "Yes" if any Binance 1 minute candle for BTC/USDT during the '
              "month specified in the title (from 00:00 AM ET on the first day to 11:59 PM ET on the last), has a final "
              "High price equal to or greater than the price specified in the title.")
CREATION_TEXT = ('This market will resolve to "Yes" if any Binance 1 minute candle for BTC/USDT from the creation of '
                 "this market through 11:59 PM ET on the last day of the month specified in the title has a final High "
                 "price equal to or greater than the price specified in the title. Price action before this market's "
                 "creation will not be considered.")
GAMMA = {"id": "6721566", "conditionId": "0xcond", "clobTokenIds": '["111", "222"]', "outcomes": '["Yes", "No"]',
         "active": True, "closed": False, "acceptingOrders": True, "enableOrderBook": True,
         "endDate": "2026-12-01T05:00:00Z", "createdAt": "2026-11-05T17:17:00.968425Z", "volumeNum": 76426.0,
         "question": "Will Bitcoin reach $80,000 in November?", "description": CREATION_TEXT}
BOOK = {"bids": [{"price": "0.09", "size": "1000"}], "asks": [{"price": "0.10", "size": "1000"}]}
AT = datetime(2026, 11, 14, 6, 30, tzinfo=UTC)


def test_rules_window_names_the_three_shapes():
    assert L.rules_window(MONTH_TEXT) == "month"
    assert L.rules_window(CREATION_TEXT) == "creation"
    assert L.rules_window(CREATION_TEXT.replace("High", "Low")) == "creation"
    assert L.rules_window("") == "unknown" and L.rules_window(None) == "unknown"
    assert L.rules_window("Resolves YES if the upper bound of the target range is raised.") == "unknown"
    assert L.rules_window(MONTH_TEXT + " " + CREATION_TEXT) == "unknown", "text naming both windows is not read"
    assert L.rules_window(" from  the\ncreation of  this market ") == "creation", "whitespace and case are not the rule"


def fetcher(bodies: dict[str, object]):
    def get(url: str) -> bytes:
        for key, body in bodies.items():
            if key in url:
                return json.dumps(body).encode()
        raise AssertionError(url)
    return get


def test_the_quote_records_the_rules_window_and_the_creation_time_and_prints_them(tmp_path, capsys):
    q = F.quote_one("6721566", fetcher({"markets/": GAMMA}), fetcher({"book": BOOK}), AT)
    assert q["rules_window"] == "creation" and q["window_from_utc"] == "2026-11-05T17:17:00Z"
    assert "rules window: creation from 2026-11-05T17:17:00Z" in F.line(q)
    assert "--window-from <level>=2026-11-05T17:17:00Z" in F.line(q)
    F.write_quote(q, tmp_path / "raw", tmp_path / "manifest.json")
    entry = json.loads((tmp_path / "manifest.json").read_text())[0]
    assert entry["rules_window"] == "creation" and entry["window_from_utc"] == "2026-11-05T17:17:00Z"
    assert "description" not in json.dumps(entry) or entry.get("description") is None, "the text itself is never written"
    month = F.quote_one("6507383", fetcher({"markets/": dict(GAMMA, id="6507383", description=MONTH_TEXT)}),
                        fetcher({"book": BOOK}), AT)
    assert month["rules_window"] == "month" and month["window_from_utc"] is None
    assert F.line(month).rstrip().endswith("rules window: month")
    odd = F.quote_one("1", fetcher({"markets/": dict(GAMMA, id="1", description="settles on the venue's say-so")}),
                      fetcher({"book": BOOK}), AT)
    assert odd["rules_window"] == "unknown" and odd["window_from_utc"] is None
    no_time = F.quote_one("2", fetcher({"markets/": dict(GAMMA, id="2", createdAt=None)}), fetcher({"book": BOOK}), AT)
    assert no_time["rules_window"] == "unknown", "a creation window with no readable creation time cannot be read"


def closes(values: list[tuple[date, float]], n_before: int = 40) -> list[tuple[date, float]]:
    first = values[0][0]
    pre = [(first - timedelta(days=n_before - k), 70_000.0 + (k % 2) * 300.0) for k in range(n_before)]
    return pre + values


def test_a_close_beyond_the_level_before_the_legs_own_window_is_not_a_touch():
    obs = closes([(date(2026, 11, 1), 80_500.0), (date(2026, 11, 2), 79_000.0), (date(2026, 11, 3), 76_000.0),
                  (date(2026, 11, 6), 74_000.0)])
    now = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    before = B.assess(obs, [(80_000.0, "up")], 2026, 11, now)["barriers"][0]
    assert before["touched_on"] == "2026-11-01" and before["p_primary"] == 1.0 and before["window_from_utc"] is None
    opens = {80_000.0: datetime(2026, 11, 5, 17, 17, tzinfo=UTC)}
    after = B.assess(obs, [(80_000.0, "up")], 2026, 11, now, window_from=opens)["barriers"][0]
    assert after["touched_on"] is None and 0.0 < after["p_primary"] < 1.0
    assert after["window_from_utc"] == "2026-11-05T17:17:00+00:00"
    # a close beyond the level inside the leg's own window is still a touch
    late = closes([(date(2026, 11, 1), 70_000.0), (date(2026, 11, 5), 70_500.0), (date(2026, 11, 6), 80_100.0)])
    row = B.assess(late, [(80_000.0, "up")], 2026, 11, now, window_from=opens)["barriers"][0]
    assert row["touched_on"] == "2026-11-06" and row["p_primary"] == 1.0
    # a window opening before the month's start is the month's start
    early = {80_000.0: datetime(2026, 10, 20, tzinfo=UTC)}
    row = B.assess(obs, [(80_000.0, "up")], 2026, 11, now, window_from=early)["barriers"][0]
    assert row["touched_on"] == "2026-11-01" and row["window_from_utc"] == B.month_window_utc(2026, 11)[0].isoformat()
    with pytest.raises(ValueError):
        B.assess(obs, [(80_000.0, "up")], 2026, 11, now, window_from={80_000.0: datetime(2026, 12, 1, 5, tzinfo=UTC)})
    printed = "\n".join(B.lines(B.assess(obs, [(80_000.0, "up")], 2026, 11, now, window_from=opens), {}, False))
    assert "[window from 2026-11-05T17:17:00+00:00" in printed and "TOUCHED" not in printed


def test_window_from_is_read_from_the_command_line_as_the_quote_prints_it(tmp_path, capsys):
    text = "DATE,CBBTCUSD\n" + "\n".join(f"{d.isoformat()},{v}" for d, v in closes(
        [(date(2026, 11, 1), 80_500.0), (date(2026, 11, 2), 79_000.0), (date(2026, 11, 6), 74_000.0)]))
    f = tmp_path / "s.csv"
    f.write_text(text)
    rc = B.main(["--month", "2026-11", "--barrier", "80000:up", "--from-file", str(f),
                 "--window-from", "80000=2026-11-05T17:17:00Z", "--calibration", str(tmp_path / "none.json")])
    out = capsys.readouterr().out
    assert rc == 0 and "[window from 2026-11-05T17:17:00+00:00" in out and "TOUCHED" not in out
    rc = B.main(["--month", "2026-11", "--barrier", "80000:up", "--from-file", str(f), "--window-from", "80000:2026-11-05"])
    assert rc == 1 and "FAILED" in capsys.readouterr().out
    rc = B.main(["--month", "2026-11", "--barrier", "80000:up", "--from-file", str(f),
                 "--window-from", "80000=2026-11-05 17:17:00 UTC"])
    assert rc == 1 and "not a UTC stamp" in capsys.readouterr().out
    assert B.parse_window_from("80000=2026-11-05T17:17:00Z") == (80_000.0, datetime(2026, 11, 5, 17, 17, tzinfo=UTC))


QUOTE = {"fetched_utc": "2026-11-14T06:17:00Z", "market_id": "6721566", "condition_id": "0xcond", "yes_token_id": "111",
         "gamma_sha256": "ab" * 32, "book_sha256": "cd" * 32, "market_mid": 0.095, "market_spread": 0.01,
         "volume_usdc": 76426.0, "end_date": "2026-12-01T05:00:00Z", "eligibility": "eligible",
         "description_sha256": "de" * 32, "rules_window": "creation", "window_from_utc": "2026-11-05T17:17:00Z"}
HISTORY = [{"method": "btc_touch", "in_force_utc": "2026-11-05T12:23:00Z", "sha256": "f2" * 32, "r2": "false",
            "source": "s"}]
NOW = datetime(2026, 11, 14, 6, 30, tzinfo=UTC)


def row_for(quote: dict, **kw) -> tuple[dict, list[str]]:
    row, v = R.build_row(quote, quote["market_id"], "btc_touch", 0.120, 0.100, 0.150, 0.49, "p", "s", HISTORY,
                         "f2" * 32, NOW)
    row = {k: ("" if x is None else str(x)) for k, x in row.items()}
    row.update(kw)
    return row, L.reading_row_violations(row, quote, HISTORY, (), "f2" * 32)


def test_the_reading_copies_the_window_from_the_quote_and_the_gate_holds_the_copy():
    row, v = row_for(QUOTE)
    assert v == [] and row["window_from_utc"] == "2026-11-05T17:17:00Z" and tuple(row) == L.READING_COLUMNS
    _, v = row_for(QUOTE, window_from_utc="")
    assert L.reading_tags(" ".join(v)) == {"window-from-rules"}
    _, v = row_for(QUOTE, window_from_utc="2026-11-06T17:17:00Z")
    assert L.reading_tags(" ".join(v)) == {"window-from-rules"} and "copy it from the quote" in v[0]
    month = dict(QUOTE, rules_window="month", window_from_utc=None)
    row, v = row_for(month)
    assert v == [] and row["window_from_utc"] == ""
    _, v = row_for(month, window_from_utc="2026-11-05T17:17:00Z")
    assert L.reading_tags(" ".join(v)) == {"window-from-rules"}


def test_a_touch_reading_needs_a_rules_window_the_method_can_read_from_this_date():
    _, v = row_for(dict(QUOTE, rules_window="unknown", window_from_utc=None))
    assert L.reading_tags(" ".join(v)) == {"window-from-rules"} and "decline the leg" in v[0]
    _, v = row_for(dict(QUOTE, rules_window="creation", window_from_utc=None))
    assert L.reading_tags(" ".join(v)) == {"window-from-rules"} and "re-quote" in v[0]
    unrecorded = {k: x for k, x in QUOTE.items() if k not in ("rules_window", "window_from_utc")}
    _, v = row_for(unrecorded)
    assert L.reading_tags(" ".join(v)) == {"window-from-rules"} and "records no rules_window" in v[0]
    # a quote fetched before the rule (the three touch readings of 6 and 13 November) is held on the copy alone
    older = dict(unrecorded, fetched_utc="2026-11-13T06:17:41Z")
    row, v = R.build_row(older, older["market_id"], "btc_touch", 0.120, 0.100, 0.150, 0.49, "p", "s", HISTORY,
                         "f2" * 32, datetime(2026, 11, 13, 6, 30, tzinfo=UTC))
    row = {k: ("" if x is None else str(x)) for k, x in row.items()}
    assert L.reading_row_violations(row, older, HISTORY, (), "f2" * 32) == []
    # another method does not read a window
    bills = dict(unrecorded, market_id="3215008", market_mid=0.735, end_date="2026-12-09T23:59:00Z")
    hist = [{"method": "fomc_bills", "in_force_utc": "2026-11-05T18:29:17Z", "sha256": "ab" * 32, "r2": "true",
             "source": "s"}]
    row, v = R.build_row(bills, "3215008", "fomc_bills", 0.58, 0.22, 0.79, 0.23, "p", "s", hist, "ab" * 32, NOW)
    assert v == [], v


def test_coverage_names_the_rules_window_of_every_leg_and_counts_it_per_listing(tmp_path):
    event = [{"id": "1292829", "slug": "ev", "markets": [
        {"id": "6507378", "question": "reach 80,000", "startDate": "2026-11-01T05:07:10Z", "closed": True,
         "closedTime": "2026-11-04 15:16:24.040261+00", "umaResolutionStatus": "resolved", "outcomePrices": '["1", "0"]',
         "volumeNum": "1", "description": MONTH_TEXT, "createdAt": "2026-11-01T05:07:02.067036Z"},
        {"id": "6721566", "question": "reach 80,000", "startDate": "2026-11-05T17:17:07Z", "closed": False,
         "closedTime": None, "umaResolutionStatus": None, "outcomePrices": None, "volumeNum": "1",
         "description": CREATION_TEXT, "createdAt": "2026-11-05T17:17:00.968425Z"},
        {"id": "9", "question": "odd", "startDate": "2026-11-05T17:17:07Z", "closed": False, "closedTime": None,
         "umaResolutionStatus": None, "outcomePrices": None, "volumeNum": "1"},
    ]}]
    _, legs = C.legs_of(json.dumps(event).encode())
    assert [g.rules_window for g in legs] == ["month", "creation", "unknown"]
    assert legs[1].created == datetime(2026, 11, 5, 17, 17, 0, 968425, tzinfo=UTC)
    entry = C.fetch("ev", lambda url: json.dumps(event).encode(), tmp_path / "raw", tmp_path / "events_manifest.json",
                    AT, tmp_path)
    assert entry["rules_windows"] == {"month": 1, "creation": 1, "unknown": 1}
    events = tmp_path / "events.csv"
    events.write_text("venue,event_id,event_slug,method,followed_from,source\npolymarket,1292829,ev,btc_touch,2026-11-03,s\n")
    lines: list[str] = []
    rc, totals = C.check(events, tmp_path / "events_manifest.json", tmp_path / "readings.csv", tmp_path / "not_read.csv",
                         tmp_path / "manifest.json", AT, tmp_path, out=lines.append)
    assert rc == 1 and totals["ev"]["open-unread"] == 2
    assert any("6721566" in ln and "rules window creation from 2026-11-05T17:17:00Z" in ln for ln in lines), lines
    assert any(" 9 " in ln and "rules window unknown" in ln for ln in lines), lines
    assert any("6507378" in ln and "rules window month" in ln for ln in lines), lines
    assert all("creation of this market" not in ln for ln in lines), "the text is never printed by the check"


def test_every_committed_reading_carries_the_column_as_its_quote_gives_it():
    here = Path(__file__).resolve().parent.parent
    import csv
    rows = list(csv.DictReader((here / "readings.csv").open(encoding="utf-8", newline="")))
    entries = json.loads((here / "data" / "manifest.json").read_text(encoding="utf-8"))
    by_hash = {e.get("gamma_sha256"): e for e in entries}
    assert rows and all("window_from_utc" in r for r in rows)
    for r in rows:
        q = by_hash[r["quote_sha256"]]
        assert r["window_from_utc"] == str(q.get("window_from_utc") or ""), r["id"]
