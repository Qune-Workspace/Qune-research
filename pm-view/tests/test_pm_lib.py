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
    assert L.call_violations(0.60, 0.735, "the market prices 0.735; the bill curve says 0.57", SETTLES) == []
    v = L.call_violations(0.68, 0.735, "the market prices 0.735; a reason", SETTLES)
    assert v == ["desk_p is within 0.10 of the market mid: no call"]
    v = L.call_violations(0.50, 0.735, "no mention of the venue's number", SETTLES)
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


# --- settles_on and the rules excerpt (2026-11-04, predictions/POST_MORTEMS.md) ---

def test_a_call_needs_settles_on_with_source_and_level_and_not_the_title():
    good = "any Binance BTC/USDT 1-minute High at or above 80,000 between 00:00 ET 1 Nov and 23:59 ET 30 Nov"
    assert L.call_violations(0.60, 0.735, "the market prices 0.735; ...", good, "Bitcoin reaches $80,000 in November") == []
    v = L.call_violations(0.60, 0.735, "the market prices 0.735; ...", "", "x")
    assert any("settles_on must restate" in x for x in v)
    v = L.call_violations(0.60, 0.735, "the market prices 0.735; ...", "Bitcoin reaches eighty thousand dollars", "x")
    assert any("settles_on must restate" in x for x in v)  # no level or date given as a number
    v = L.call_violations(0.60, 0.735, "the market prices 0.735; ...", "Bitcoin reaches $80,000 in November 2026",
                          "Bitcoin reaches $80,000 in November 2026")
    assert any("repeats the proposition" in x for x in v)


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
