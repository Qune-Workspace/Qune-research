"""pm_lib on records built in memory: the book's touch, the eligibility reasons in
Study 013's §6.3 order, the call rule and the Brier summary."""
import math
from datetime import UTC, datetime

import numpy as np
import pm_lib as L
import pytest

AT = datetime(2026, 11, 3, 18, 0, tzinfo=UTC)


def market(**over):
    row = {
        "outcomes": '["Yes", "No"]', "clobTokenIds": '["111", "222"]', "enableOrderBook": True,
        "active": True, "closed": False, "acceptingOrders": True, "umaResolutionStatus": None,
        "endDate": "2026-12-09T23:59:00Z", "volumeNum": 2_661_872.09,
    }
    row.update(over)
    return row


def test_best_of_book_takes_the_touch_not_the_position():
    # The venue lists the best price last; max/min must not depend on that.
    book = {"bids": [{"price": "0.70", "size": "1"}, {"price": "0.73", "size": "2"}],
            "asks": [{"price": "0.80", "size": "1"}, {"price": "0.74", "size": "2"}]}
    assert L.best_of_book(book) == (0.73, 0.74)
    assert L.best_of_book({"bids": [], "asks": [{"price": "0.5"}]}) is None
    assert L.best_of_book({"bids": [{"price": "0.5"}]}) is None


def test_mid_and_decode():
    assert L.mid(0.73, 0.74) == pytest.approx(0.735)
    assert L.decode_list('["a", "b"]') == ["a", "b"]
    assert L.decode_list("not json") is None
    assert L.as_float("0.735") == 0.735 and L.as_float(True) is None


@pytest.mark.parametrize("over, best, reason", [
    ({}, (0.73, 0.74), None),
    ({"outcomes": '["A", "B", "C"]'}, (0.73, 0.74), "not a binary market"),
    ({"enableOrderBook": False}, (0.73, 0.74), "no order book"),
    ({"acceptingOrders": False}, (0.73, 0.74), "not open and accepting orders"),
    ({"umaResolutionStatus": "proposed"}, (0.73, 0.74), "resolution begun"),
    ({"endDate": None}, (0.73, 0.74), "no scheduled end"),
    ({"endDate": "2026-11-01T00:00:00Z"}, (0.73, 0.74), "past the scheduled end"),
    ({}, None, "one-sided or empty book"),
    ({}, (0.60, 0.72), "spread above 0.10"),
    ({}, (0.002, 0.004), "mid outside [0.01, 0.99]"),
    ({"volumeNum": 9_999}, (0.73, 0.74), "volume below 10,000 USDC"),
])
def test_eligibility_reasons_in_order(over, best, reason):
    assert L.eligibility(market(**over), best, AT) == reason


def test_eligibility_reports_the_first_reason_only():
    # Three faults at once: the binary check comes first in §6.3's order.
    assert L.eligibility(market(outcomes='["A"]', enableOrderBook=False, volumeNum=1), None, AT) == "not a binary market"


SETTLES = "the upper bound of the target range after the 9 December 2026 meeting is 25 bp higher"


def test_a_call_needs_a_departure_and_a_basis_that_names_the_market():
    assert L.call_violations(0.60, 0.735, "the market prices 0.735; the bill curve says 0.57", SETTLES, method="stated") == []
    v = L.call_violations(0.68, 0.735, "the market prices 0.735; a reason", SETTLES, method="stated")
    # 2026-11-06 12:15Z: every refusal carries the tag of its rule (tests/test_rule_tags.py)
    assert v == ["[gate:departure] desk_p is within 0.10 of the market mid: no call"]
    v = L.call_violations(0.50, 0.735, "no mention of the venue's number", SETTLES, method="stated")
    assert v == ["[gate:basis-names-market] basis must name the market's probability and what it is missing"]
    assert "[gate:probability] desk_p is not a probability" in L.call_violations(1.0, 0.5, "market", method="stated")
    # 2026-11-06: a call with no method is refused; the ledger can no longer carry a row the gate never saw
    v = L.call_violations(0.60, 0.735, "the market prices 0.735; ...", SETTLES)
    assert v == ["[gate:method-named] method must be stated: one of fomc_bills, btc_touch, stated"]


FETCHED = "2026-11-06T06:16:37Z"  # the 6 November quote of the December hike market (data/manifest.json)


def test_a_call_is_made_on_its_quotes_day_compared_as_dates():
    # 2026-11-07 12:15Z (predictions/POST_MORTEMS.md "A timestamp compared with a date"): the ledger test
    # compared fetched_utc with made_on as strings; these are the three cases it got wrong or right by luck
    assert not (FETCHED <= "2026-11-06") and FETCHED <= "2026-11-07"  # the old comparison, inverted on both
    assert L.quote_day(FETCHED) == "2026-11-06" and L.quote_day(None) == ""
    assert L.quote_timing_violations("2026-11-06", FETCHED) == []  # same day: the call stands
    nxt = L.quote_timing_violations("2026-11-07", FETCHED)  # next day from the same quote: a stale mid
    assert nxt == ["[gate:made-on-quote-day] made_on 2026-11-07 is not the quote's day 2026-11-06: "
                   "the quote's mid is stale; a call is made on the day of its quote"]
    prev = L.quote_timing_violations("2026-11-05", FETCHED)  # previous day: quoted after the call was made
    assert prev == ["[gate:made-on-quote-day] made_on 2026-11-05 is not the quote's day 2026-11-06: "
                    "the quote was read after the call was made; a call is made on the day of its quote"]
    assert L.gate_tags(" ".join(L.quote_timing_violations("2026-11-06", ""))) == {"made-on-quote-day"}


def test_the_call_gate_applies_the_timing_rule_only_to_a_row_and_the_reading_gate_shares_the_day():
    args = (0.60, 0.735, "the market prices 0.735; the bill curve says 0.57", SETTLES)
    # the printers and the grid tests judge numbers with no row: no made_on, no timing rule
    assert L.call_violations(*args, method="stated") == []
    assert L.call_violations(*args, method="stated", made_on="2026-11-06", quote_fetched_utc=FETCHED) == []
    v = L.call_violations(*args, method="stated", made_on="2026-11-07", quote_fetched_utc=FETCHED)
    assert L.gate_tags(" ".join(v)) == {"made-on-quote-day"}
    # one function names the quote's day for both gates
    quote = {"fetched_utc": FETCHED, "market_mid": 0.665, "eligibility": "eligible", "end_date": "2026-12-10T00:00:00Z"}
    reading = dict(method="fomc_bills", method_p=0.90, range_lo=0.80, range_hi=1.0, market_mid=0.665,
                   climatology_p=None, quote=quote, due_on="2026-12-10")
    assert L.reading_violations(made_on="2026-11-06", **reading) == []
    assert L.reading_tags(" ".join(L.reading_violations(made_on="2026-11-07", **reading))) == {"made-on-quote-day"}


def test_method_gate_reads_r2_from_the_methods_own_calibration_and_nothing_else():
    bills = {"rules": {"R1_primary": "net", "R2_basis_for_a_call": True}}
    touch = {"rules": {"R1_primary_window": 30, "R2_method_is_a_basis_for_a_call": False}}
    assert L.method_gate("fomc_bills", bills) is True
    assert L.method_gate("btc_touch", touch) is False
    assert L.method_gate("fomc_bills", touch) is None      # the other method's file: no gate
    assert L.method_gate("btc_touch", None) is None
    assert L.method_gate("stated", bills) is None
    assert L.method_gate("fomc_bills", {"rules": {"R2_basis_for_a_call": "yes"}}) is None  # not a bool: no gate


def test_method_violations_in_the_readme_order():
    ok = L.method_violations("fomc_bills", 0.99, 0.60, 1.00, 0.45, True, desk_p=0.90)
    assert ok == []
    assert L.method_violations("bills", 0.9, 0.6, 1.0, 0.4, True) == [
        "[gate:method-named] method must be one of fomc_bills, btc_touch, stated"]
    # stated: no reading, no range, no gate beyond the departure
    assert L.method_violations("stated", None, None, None, 0.4, None) == []
    assert L.method_violations("stated", 0.9, None, None, 0.4, None) == [
        "[gate:stated-bare] a stated reason carries no method reading or range: leave method_p, range_lo, range_hi empty"]
    # the calibration gate comes first
    assert L.method_violations("fomc_bills", 0.99, 0.60, 1.00, 0.45, None)[0].startswith(
        "[gate:calibrated] no calibration gate for fomc_bills")
    assert L.method_violations("btc_touch", 0.80, 0.80, 0.85, 0.65, False)[0] == (
        "[gate:calibrated] btc_touch does not beat its baselines on its own history (R2): not a basis for a call")
    # the numbers must be there and the range must bracket the reading
    assert L.method_violations("fomc_bills", None, 0.6, 1.0, 0.4, True) == [
        "[gate:range-brackets] method_p, range_lo and range_hi are required for a method call"]
    assert L.method_violations("fomc_bills", 0.55, 0.60, 1.00, 0.40, True) == [
        "[gate:range-brackets] the range [0.600, 1.000] must bracket the method reading 0.550 inside [0, 1]"]
    # the market inside the range: covered (the 2026-11-05 18:26Z case: 0.993 in [0.596, 1.000] against 0.635)
    v = L.method_violations("fomc_bills", 0.993, 0.596, 1.000, 0.635, True, desk_p=0.90)
    assert v == ["[gate:range] the market mid 0.635 lies inside the reading's range [0.596, 1.000]: no call"]
    # a touch reading below the market is never a call, even outside the range and over the threshold
    v = L.method_violations("btc_touch", 0.607, 0.607, 0.705, 0.805, True)
    assert v == ["[gate:touch-below] btc_touch: the reading is at or below the market, "
                 "the direction of the gap the method cannot see: never a call"]
    # the bills reading below the market may be a call (no one-sided gap in that method)
    assert L.method_violations("fomc_bills", 0.30, 0.20, 0.40, 0.60, True, desk_p=0.35) == []
    # under the threshold outside the range
    v = L.method_violations("fomc_bills", 0.60, 0.58, 0.62, 0.52, True)
    assert v == ["[gate:method-departure] the method reading is within 0.10 of the market mid: no call"]
    # the desk on the other side of the market from its own method
    v = L.method_violations("fomc_bills", 0.99, 0.60, 1.00, 0.45, True, desk_p=0.40)
    assert v == ["[gate:desk-side] desk_p and the method reading sit on opposite sides of the market (or on it)"]


def test_ledger_method_fields_type_the_four_columns_and_read_blanks_as_none():
    row = {"method": "fomc_bills", "method_p": "0.993", "range_lo": "0.596", "range_hi": "1.000"}
    assert L.ledger_method_fields(row) == ("fomc_bills", 0.993, 0.596, 1.0)
    assert L.ledger_method_fields({"method": "stated", "method_p": "", "range_lo": " ", "range_hi": ""}) == ("stated", None, None, None)
    assert L.ledger_method_fields({}) == (None, None, None, None)
    assert L.LEDGER_COLUMNS.index("method") == L.LEDGER_COLUMNS.index("desk_p") + 1
    assert L.LEDGER_COLUMNS[-2:] == ("basis", "quote_sha256")


def test_skill_summary_over_scored_calls_only():
    rows = [
        {"desk_p": "0.60", "market_mid": "0.735", "y": "1"},
        {"desk_p": "0.20", "market_mid": "0.10", "y": "0"},
        {"desk_p": "0.50", "market_mid": "0.50", "y": ""},  # excluded: not scored
    ]
    s = L.skill_summary(rows)
    assert s["n"] == 2
    assert s["brier_desk"] == pytest.approx(((0.60 - 1) ** 2 + 0.20 ** 2) / 2)
    assert s["brier_market"] == pytest.approx(((0.735 - 1) ** 2 + 0.10 ** 2) / 2)
    assert s["skill"] == pytest.approx(s["brier_market"] - s["brier_desk"])
    assert L.skill_summary([])["n"] == 0


# --- settles_on and the rules excerpt (2026-11-04, predictions/POST_MORTEMS.md) ---

def test_a_call_needs_settles_on_with_source_and_level_and_not_the_title():
    good = "any Binance BTC/USDT 1-minute High at or above 80,000 between 00:00 ET 1 Nov and 23:59 ET 30 Nov"
    assert L.call_violations(0.60, 0.735, "the market prices 0.735; ...", good, "Bitcoin reaches $80,000 in November",
                             method="stated") == []
    v = L.call_violations(0.60, 0.735, "the market prices 0.735; ...", "", "x", method="stated")
    assert any("settles_on must restate" in x for x in v)
    v = L.call_violations(0.60, 0.735, "the market prices 0.735; ...", "Bitcoin reaches eighty thousand dollars", "x", method="stated")
    assert any("settles_on must restate" in x for x in v)  # no level or date given as a number
    v = L.call_violations(0.60, 0.735, "the market prices 0.735; ...", "Bitcoin reaches $80,000 in November 2026",
                          "Bitcoin reaches $80,000 in November 2026", method="stated")
    assert any("repeats the proposition" in x for x in v)
    # a method call: the whole row passes only when the gate does
    full = L.call_violations(0.90, 0.45, "the market prices 0.45; the bills price 0.99 ...", good, "x",
                             "fomc_bills", 0.99, 0.60, 1.00, True)
    assert full == []
    gated = L.call_violations(0.90, 0.45, "the market prices 0.45; ...", good, "x", "btc_touch", 0.99, 0.60, 1.00, False)
    assert gated == ["[gate:calibrated] btc_touch does not beat its baselines on its own history (R2): "
                     "not a basis for a call"]


def test_rules_excerpt_is_one_line_cut_at_the_limit_and_names_a_missing_description():
    row = {"description": "This market will resolve to \"Yes\" if any Binance 1 minute\n\ncandle has a High >= 80,000."}
    assert L.rules_excerpt(row) == 'This market will resolve to "Yes" if any Binance 1 minute candle has a High >= 80,000.'
    assert L.rules_excerpt(row, chars=20) == "This market will res..."
    assert L.rules_excerpt({}) == "(no description on the record)"
    assert L.rules_excerpt({"description": "   "}) == "(no description on the record)"


# --- touch probability (first passage) ---------------------------------------

def test_touch_probability_edges_and_symmetry():
    assert L.touch_probability(100.0, 100.0, 0.5, 30) == 1.0
    assert L.touch_probability(100.0, 120.0, 0.5, 0) == 0.0
    assert L.touch_probability(100.0, 120.0, 0.0, 30) == 0.0
    up = L.touch_probability(100.0, 120.0, 0.5, 30)
    down = L.touch_probability(100.0, 100.0 / 1.2, 0.5, 30)
    assert abs(up - down) < 1e-12  # same log distance, same chance
    assert 0.0 < up < 1.0
    assert L.touch_probability(100.0, 120.0, 0.8, 30) > up > L.touch_probability(100.0, 120.0, 0.3, 30)
    assert L.touch_probability(100.0, 120.0, 0.5, 60) > up
    with pytest.raises(ValueError):
        L.touch_probability(0.0, 120.0, 0.5, 30)
    with pytest.raises(ValueError):
        L.touch_probability(100.0, 120.0, -0.1, 30)


def test_touch_probability_is_twice_the_terminal_probability_and_matches_a_simulation():
    # Reflection principle: P(touch) = 2 P(S_T beyond the barrier) for a driftless log price.
    spot, barrier, sigma, days = 77_000.0, 80_000.0, 0.55, 27
    t = days / 365
    d = math.log(barrier / spot) / (sigma * math.sqrt(t))
    terminal = 0.5 * math.erfc(d / math.sqrt(2))
    assert abs(L.touch_probability(spot, barrier, sigma, days) - 2 * terminal) < 1e-12
    # Monte Carlo of the same driftless log price over a shorter window, one step a minute, seeded (numpy).
    spot, barrier, sigma, days = 77_000.0, 80_000.0, 0.60, 5
    t = days / 365
    steps, paths = days * 1440, 40_000
    rng = np.random.default_rng(20261104)
    x = np.full(paths, math.log(spot))
    hit = np.zeros(paths, dtype=bool)
    sd = sigma * math.sqrt(t / steps)
    for _ in range(steps):
        x += sd * rng.standard_normal(paths)
        hit |= x >= math.log(barrier)
    p_hat = float(hit.mean())
    p = L.touch_probability(spot, barrier, sigma, days)
    se = math.sqrt(p * (1 - p) / paths)
    # Minute monitoring reads a touch slightly less often than the continuous formula (BGK shift at dt = 1 min):
    # allow 3 SE either side plus that small downward bias.
    assert p - 3 * se - 0.01 <= p_hat <= p + 3 * se, (p, p_hat, se)


def test_realised_vol_from_closes():
    closes = [100.0 * math.exp(0.01 * k) for k in range(10)]  # constant log return: zero variance
    assert L.realised_vol(closes) < 1e-12
    closes = [100.0, 110.0, 100.0, 110.0, 100.0]  # alternating +-ln(1.1)
    r = math.log(1.1)
    sd = math.sqrt(sum((x - 0.0) ** 2 for x in [r, -r, r, -r]) / 3)
    assert abs(L.realised_vol(closes) - sd * math.sqrt(365)) < 1e-12
    with pytest.raises(ValueError):
        L.realised_vol([100.0, 101.0])
    with pytest.raises(ValueError):
        L.realised_vol([100.0, 0.0, 101.0])


# --- record_calibration_line: the one writer of data/calibration_history.csv (2026-11-08 00:15Z) ---

def _history_lines(path):
    import csv
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_record_calibration_line_records_then_leaves_an_unchanged_file_and_refuses_a_file_with_no_r2(tmp_path):
    import hashlib
    import json
    hist, cal = tmp_path / "calibration_history.csv", tmp_path / "calibration.json"
    t1, t2 = datetime(2026, 11, 8, 0, 20, tzinfo=UTC), datetime(2026, 11, 8, 0, 30, tzinfo=UTC)
    # refused: no file, a file that is not json, a file with no R2; nothing written
    assert L.record_calibration_line(hist, "btc_touch", cal, t1, "s") == ("refused", None)
    cal.write_text("not json")
    assert L.record_calibration_line(hist, "btc_touch", cal, t1, "s") == ("refused", None)
    cal.write_text(json.dumps({"rules": {"R1_primary_window": 30}}))
    assert L.record_calibration_line(hist, "btc_touch", cal, t1, "s") == ("refused", None)
    assert L.record_calibration_line(hist, "fomc_bills", cal, t1, "s") == ("refused", None)  # another method's key
    assert not hist.exists()
    # recorded: hash of the bytes as written, R2 read through method_gate, the header on a new file
    cal.write_text(json.dumps({"rules": {"R2_method_is_a_basis_for_a_call": False}}))
    status, line = L.record_calibration_line(hist, "btc_touch", cal, t1, "calibrate.py: test")
    assert status == "recorded" and line is not None
    assert line["sha256"] == hashlib.sha256(cal.read_bytes()).hexdigest() and line["r2"] == "false"
    assert line["in_force_utc"] == "2026-11-08T00:20:00Z" and line["source"] == "calibrate.py: test"
    assert _history_lines(hist) == [line] and b"\r" not in hist.read_bytes()
    # unchanged: the same file again appends nothing and returns the latest line
    before = hist.read_bytes()
    assert L.record_calibration_line(hist, "btc_touch", cal, t2, "again") == ("unchanged", line)
    assert hist.read_bytes() == before
    # another method's line does not make this method's file unchanged; a new file is a new line
    fomc = tmp_path / "fomc_calibration.json"
    fomc.write_text(json.dumps({"rules": {"R2_basis_for_a_call": True}}))
    assert L.record_calibration_line(hist, "fomc_bills", fomc, t2, "f")[0] == "recorded"
    cal.write_text(json.dumps({"rules": {"R2_method_is_a_basis_for_a_call": True}}))
    status, line2 = L.record_calibration_line(hist, "btc_touch", cal, t2, "re-run")
    assert status == "recorded" and line2 is not None and line2["r2"] == "true"
    lines = _history_lines(hist)
    assert [h["method"] for h in lines] == ["btc_touch", "fomc_bills", "btc_touch"]
    assert L.calibration_in_force(lines, "btc_touch", "9999") == line2
    assert L.history_r2(L.calibration_in_force(lines, "btc_touch", "2026-11-08T00:25:00Z")) is False
