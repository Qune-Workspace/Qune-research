"""pm_lib on records built in memory: the book's touch, the eligibility reasons in
Study 013's §6.3 order, the call rule and the Brier summary."""
from datetime import UTC, datetime

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


def test_a_call_needs_a_departure_and_a_basis_that_names_the_market():
    assert L.call_violations(0.60, 0.735, "the market prices 0.735; the bill curve says 0.57") == []
    v = L.call_violations(0.68, 0.735, "the market prices 0.735; a reason")
    assert v == ["desk_p is within 0.10 of the market mid: no call"]
    v = L.call_violations(0.50, 0.735, "no mention of the venue's number")
    assert v == ["basis must name the market's probability and what it is missing"]
    assert "desk_p is not a probability" in L.call_violations(1.0, 0.5, "market")


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
