"""Prediction-market view: the pure functions behind the ledger, the quote and the score.

Why this folder exists (BACKLOG PM5, 2026-11-03): the rates desk view logs calls
against a market-anchored baseline that it has to construct from bills and
forwards.  On a prediction market the baseline is the market itself: the mid of
the best bid and ask on the YES token is a probability, read at the time of the
call.  So the discipline adopted after the V1 miss (predictions/POST_MORTEMS.md,
2026-10-30) becomes simpler and stricter here:

  - the market's probability is read and written down before the desk's;
  - a call is logged only when the desk's probability differs from the market
    mid by at least MIN_DEPARTURE, and its basis names the market's number and
    says in one testable sentence what the market is missing.  Nearer than
    that the desk has nothing to add and says so in the view instead;
  - every call is scored by Brier against the market mid at the time of the
    call, on the venue's own settlement, by the same outcome rule Study 013
    pre-registered (research/013-polymarket-calibration-forward, §6.5).

Eligibility mirrors Study 013's §6.3 (same floors, same order), so a market the
study would not count is not one the desk calls either: a binary market with an
order book, open and accepting orders, resolution not begun, scheduled end in
the future, a two-sided book with spread at most SPREAD_CAP, mid inside
[0.01, 0.99] and cumulative volume of at least VOLUME_FLOOR USDC.

Nothing here reads a file or the network; fetch.py and score.py do that and
pass the rows in.  The functions are tested on dicts built in memory.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any

MIN_DEPARTURE = 0.10  # |desk p - market mid| below this: no call
VOLUME_FLOOR = 10_000.0  # USDC, cumulative, as Study 013 §6.3
SPREAD_CAP = 0.10
RESOLUTION_BEGUN = ("proposed", "disputed", "resolved")

LEDGER_COLUMNS = (
    "id", "made_on", "venue", "market_id", "condition_id", "yes_token_id", "proposition", "settles_on",
    "due_on", "market_mid", "market_spread", "volume_usdc", "desk_p",
    "method", "method_p", "range_lo", "range_hi",  # added 2026-11-06: the method gate on the committed row
    "basis", "quote_sha256",
)
MIN_SETTLES_ON_CHARS = 20  # the resolution rule restated: source and measure, not the title

# The methods a call may rest on, and where each one's calibration gate (rule R2:
# the method beats its dumb baseline on its own history, or it is no basis for a
# call) is written.  Added 2026-11-06 (predictions/POST_MORTEMS.md, "A call gate
# that knew one rule of three"): until then README rule 2 stated the R2 gate and
# the range rule, barrier.py and fomc_calibrate.py printed them as advice and
# never wrote a call, and the only check on the committed ledger was the 0.10
# departure plus `settles_on`, so a hand-written row could pass every test while
# breaking two of the three rules.  `stated` is the README's other path, a
# reason outside any method (a data release, written before the market moves on
# it); it carries no method reading and no gate beyond the departure, and the
# ledger shows that plainly.
METHODS = ("fomc_bills", "btc_touch", "stated")
METHOD_CALIBRATION = {  # method -> (calibration file under pm-view/, the R2 key in its "rules")
    "fomc_bills": ("data/fomc_calibration.json", "R2_basis_for_a_call"),
    "btc_touch": ("data/calibration.json", "R2_method_is_a_basis_for_a_call"),
}
BELOW_MARKET_NEVER = ("btc_touch",)  # a reading below the market is in the direction of the one-minute gap: never a call
OUTCOME_COLUMNS = (
    "id", "scored_on", "kind", "y", "desk_p", "market_mid", "brier_desk", "brier_market",
    "gamma_sha256", "clob_sha256",
)


def as_float(v: object) -> float | None:
    """A decimal number from a float, an int or a numeric string; None otherwise."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None


def decode_list(v: object) -> list | None:
    """A JSON-encoded list in a string (Gamma encodes `outcomes` and the token ids so), or a list as it is."""
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            out = json.loads(v)
        except ValueError:
            return None
        return out if isinstance(out, list) else None
    return None


def mid(bid: float, ask: float) -> float:
    return (bid + ask) / 2.0


def best_of_book(book: dict[str, Any]) -> tuple[float, float] | None:
    """Best bid and best ask of a CLOB `/book` body: the best price is the LAST
    entry of each array (observed 2026-11-01, ops/trading pm-data-sources; the
    arrays are sorted away from the touch).  Taken as max and min, not by
    position, so an unsorted body cannot mislead.  None when either side is empty."""
    bids = book.get("bids")
    asks = book.get("asks")
    if not isinstance(bids, list) or not isinstance(asks, list) or not bids or not asks:
        return None
    b = [as_float(x.get("price")) for x in bids if isinstance(x, dict)]
    a = [as_float(x.get("price")) for x in asks if isinstance(x, dict)]
    bb = [x for x in b if x is not None]
    aa = [x for x in a if x is not None]
    if not bb or not aa:
        return None
    return max(bb), min(aa)


def record_eligibility(row: dict[str, Any], at: datetime) -> str | None:
    """The reasons of `eligibility` that the Gamma record alone decides, in the
    same §6.3 order, before any book is read (added 2026-11-06: a settled
    market's book is gone (CLOB 404), and the quote had thrown the record away
    as a fetch failure, predictions/POST_MORTEMS.md).  None when the record
    leaves the market open to a call, so the book decides the rest."""
    outcomes = decode_list(row.get("outcomes"))
    tokens = decode_list(row.get("clobTokenIds"))
    if outcomes is None or tokens is None or len(outcomes) != 2 or len(tokens) != 2:
        return "not a binary market"
    if row.get("enableOrderBook") is not True:
        return "no order book"
    if row.get("active") is not True or row.get("closed") is not False or row.get("acceptingOrders") is not True:
        return "not open and accepting orders"
    uma = row.get("umaResolutionStatus")
    if isinstance(uma, str) and uma.lower() in RESOLUTION_BEGUN:
        return "resolution begun"
    end = row.get("endDate")
    if not isinstance(end, str) or not end:
        return "no scheduled end"
    try:
        end_at = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError:
        return "no scheduled end"
    if at >= end_at:
        return "past the scheduled end"
    return None


def settlement_state(row: dict[str, Any]) -> str:
    """What the Gamma record says about a market that is no longer open, in the
    record's own fields (closed, closedTime, umaResolutionStatus, outcomePrices),
    reported as information: the outcome rule that scores a call is Study 013
    §6.5 in score.py, not this line."""
    prices = decode_list(row.get("outcomePrices"))
    return (f"record says closed={row.get('closed')!r} closedTime={row.get('closedTime')!r} "
            f"umaResolutionStatus={row.get('umaResolutionStatus')!r} outcomePrices={prices!r}")


def eligibility(row: dict[str, Any], best: tuple[float, float] | None, at: datetime) -> str | None:
    """The first reason, in Study 013's §6.3 order, that excludes a market from a call; None when eligible.

    `row` is the Gamma market record; `best` the CLOB book's best bid and ask
    (None for a one-sided or empty book)."""
    reason = record_eligibility(row, at)
    if reason is not None:
        return reason
    if best is None:
        return "one-sided or empty book"
    bid, ask = best
    if not (0.0 < bid <= ask < 1.0):
        return "book not two-sided inside (0, 1)"
    if ask - bid > SPREAD_CAP:
        return f"spread above {SPREAD_CAP:.2f}"
    m = mid(bid, ask)
    if not (0.01 <= m <= 0.99):
        return "mid outside [0.01, 0.99]"
    vol = as_float(row.get("volumeNum"))
    if vol is None or vol < VOLUME_FLOOR:
        return f"volume below {VOLUME_FLOOR:,.0f} USDC"
    return None


def brier(p: float, y: int) -> float:
    return (p - y) ** 2


def departure(desk_p: float, market_mid: float) -> float:
    return abs(desk_p - market_mid)


def method_gate(method: str, calibration: dict[str, Any] | None) -> bool | None:
    """R2 of the method's calibration file (already loaded by the caller): True
    when the method beats its baselines on its own history, False when it does
    not, None when the file is missing or is not that method's calibration."""
    if method not in METHOD_CALIBRATION or calibration is None:
        return None
    key = METHOD_CALIBRATION[method][1]
    rules = calibration.get("rules") if isinstance(calibration, dict) else None
    v = rules.get(key) if isinstance(rules, dict) else None
    return v if isinstance(v, bool) else None


def method_violations(method: str, method_p: float | None, range_lo: float | None, range_hi: float | None,
                      market_mid: float, r2: bool | None, desk_p: float | None = None) -> list[str]:
    """The method gate of README rule 2, in the order the reasons are checked,
    on the numbers a ledger row carries; empty when the method may be a basis
    for a call.  The one copy of the rule: barrier.departure_verdict and
    fomc_calibrate.live_verdict print the same reasons and the tests hold them
    to this function.

    1. the method is one the desk has (METHODS);
    2. `stated` carries no method reading and no range (the gate is the
       departure alone, and the row says so);
    3. the method's calibration gate R2 is true (None: no calibration, refused);
    4. the reading and its range are probabilities with lo <= p <= hi (the
       range the ledger carries is the hull of the reading and its range under
       the method's own uncertainty: the historical basis for the bills, the
       primary-to-sensitivity window for the touch formula);
    5. the market mid lies outside the range (inside: covered, never a call);
    6. for BELOW_MARKET_NEVER methods the reading is above the market;
    7. the reading departs from the mid by at least MIN_DEPARTURE;
    8. the desk's probability sits on the same side of the market as the
       reading it rests on."""
    out: list[str] = []
    if method not in METHODS:
        return [f"method must be one of {', '.join(METHODS)}"]
    if method == "stated":
        if any(v is not None for v in (method_p, range_lo, range_hi)):
            out.append("a stated reason carries no method reading or range: leave method_p, range_lo, range_hi empty")
        return out
    if r2 is None:
        out.append(f"no calibration gate for {method}: run its calibration first ({METHOD_CALIBRATION[method][0]})")
    elif not r2:
        out.append(f"{method} does not beat its baselines on its own history (R2): not a basis for a call")
    if method_p is None or range_lo is None or range_hi is None:
        out.append("method_p, range_lo and range_hi are required for a method call")
        return out
    if not (0.0 <= range_lo <= method_p <= range_hi <= 1.0):
        out.append(f"the range [{range_lo:.3f}, {range_hi:.3f}] must bracket the method reading {method_p:.3f} inside [0, 1]")
        return out
    if range_lo <= market_mid <= range_hi:
        out.append(f"the market mid {market_mid:.3f} lies inside the reading's range [{range_lo:.3f}, {range_hi:.3f}]: no call")
    if method in BELOW_MARKET_NEVER and method_p <= market_mid:
        out.append(f"{method}: the reading is at or below the market, the direction of the gap the method cannot see: never a call")
    if departure(method_p, market_mid) < MIN_DEPARTURE:
        out.append(f"the method reading is within {MIN_DEPARTURE:.2f} of the market mid: no call")
    if desk_p is not None and (desk_p - market_mid) * (method_p - market_mid) <= 0:
        out.append("desk_p and the method reading sit on opposite sides of the market (or on it)")
    return out


def call_violations(desk_p: float, market_mid: float, basis: str, settles_on: str = "",
                    proposition: str = "", method: str | None = None, method_p: float | None = None,
                    range_lo: float | None = None, range_hi: float | None = None,
                    r2: bool | None = None) -> list[str]:
    """What stops a draft call from being logged; empty when it may be.

    `settles_on` (added 2026-11-04 after the first view described two touch
    markets as price-level markets from their titles, predictions/POST_MORTEMS.md)
    restates the market's resolution rule in the desk's words: the source and
    the measure that settle YES.  It must be present, long enough to say both,
    and not a copy of the proposition or of the title.

    `method` and the three numbers beside it (added 2026-11-06) carry the
    method gate: see method_violations.  A call with no method is refused."""
    out: list[str] = []
    if not (0.0 < desk_p < 1.0):
        out.append("desk_p is not a probability")
    if departure(desk_p, market_mid) < MIN_DEPARTURE:
        out.append(f"desk_p is within {MIN_DEPARTURE:.2f} of the market mid: no call")
    if "market" not in basis.lower():
        out.append("basis must name the market's probability and what it is missing")
    so = settles_on.strip()
    if len(so) < MIN_SETTLES_ON_CHARS or not any(c.isdigit() for c in so):
        out.append("settles_on must restate the market's resolution rule with its source and the measured level or date")
    elif so.lower() == proposition.strip().lower():
        out.append("settles_on repeats the proposition; restate the rule, not the title")
    if method is None:
        out.append(f"method must be stated: one of {', '.join(METHODS)}")
    else:
        out.extend(method_violations(method, method_p, range_lo, range_hi, market_mid, r2, desk_p))
    return out


def ledger_method_fields(call: dict[str, Any]) -> tuple[str | None, float | None, float | None, float | None]:
    """The four method columns of a ledger row as typed values; an empty cell is None."""
    def num(k: str) -> float | None:
        v = call.get(k, "")
        return as_float(v) if isinstance(v, str) and v.strip() else None
    m = call.get("method", "")
    return (m.strip() if isinstance(m, str) and m.strip() else None, num("method_p"), num("range_lo"), num("range_hi"))


def rules_excerpt(row: dict[str, Any], chars: int = 400) -> str:
    """The first `chars` characters of the market's own resolution text (Gamma
    `description`), one line, for the quote's printed output: the desk reads
    how YES settles before it writes a proposition or a probability.  Nothing
    of this is written to a committed file; the manifest carries its hash."""
    d = row.get("description")
    if not isinstance(d, str) or not d.strip():
        return "(no description on the record)"
    one = " ".join(d.split())
    return one if len(one) <= chars else one[:chars] + "..."


# --- Touch (first-passage) probability for the barrier markets -----------------
#
# Added 2026-11-04 with the post-mortem above: the monthly Bitcoin markets
# settle YES if ANY one-minute Binance BTC/USDT candle in the month has a High
# at or above the level (or a Low at or below it), so the desk's number is a
# first-passage probability, not the probability of ending above the level.
# Model: driftless geometric Brownian motion of the price with annualised
# volatility `sigma` over `days` calendar days (crypto trades every day, so the
# year is 365 days).  Reflection principle: P(max_{t<=T} S_t >= B) =
# 2 * Phi(-ln(B/S) / (sigma * sqrt(T))) for an upper barrier B > S, and the
# mirror for a lower barrier.  One-minute monitoring is treated as continuous
# (the Broadie-Glasserman-Kou correction at dt = 1 minute moves the barrier
# by exp(0.5826 * sigma * sqrt(dt)), under 0.1% at sigma = 0.6: inside the
# rounding of the view).  The drift is set to zero on purpose: any drift the
# desk believes in is a reason it must state in the basis, not a parameter.
# What the formula does NOT carry, and the view's basis sentence must say:
# a volatility estimated from Coinbase daily closes understates the intraday
# range Binance's one-minute extremes see, so the probability below is a
# lower reading of the touch chance, and the two venues' prices differ by a
# basis of their own (tools/pm_data_terms.md, "Price series for the Bitcoin
# barrier markets", condition 3).


def realised_vol(closes: list[float], days_per_year: int = 365) -> float:
    """Annualised close-to-close volatility: standard deviation (ddof = 1) of the
    log returns of consecutive daily closes, times sqrt(days_per_year).  Needs at
    least three closes; a non-positive close is refused."""
    if len(closes) < 3:
        raise ValueError("realised_vol needs at least three closes")
    if any(c <= 0 for c in closes):
        raise ValueError("realised_vol: a close is not positive")
    rets = [math.log(b / a) for a, b in zip(closes[:-1], closes[1:], strict=True)]
    n = len(rets)
    m = sum(rets) / n
    var = sum((r - m) ** 2 for r in rets) / (n - 1)
    return math.sqrt(var) * math.sqrt(days_per_year)


def touch_probability(spot: float, barrier: float, sigma: float, days: float, days_per_year: int = 365) -> float:
    """Probability that a driftless lognormal price with annualised volatility
    `sigma` touches `barrier` (above or below `spot`) within `days` calendar
    days.  1.0 when the barrier is already at or past the spot; 0.0 when no
    time or no volatility is left."""
    if spot <= 0 or barrier <= 0:
        raise ValueError("touch_probability: spot and barrier must be positive")
    if sigma < 0 or days < 0:
        raise ValueError("touch_probability: sigma and days must be non-negative")
    if barrier == spot:
        return 1.0
    if days == 0 or sigma == 0:
        return 0.0
    dist = abs(math.log(barrier / spot))
    return 2.0 * _phi(-dist / (sigma * math.sqrt(days / days_per_year)))


def _phi(x: float) -> float:
    """Standard normal CDF."""
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def skill_summary(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Brier for the desk and for the market mid over the scored calls (y present); skill = market minus desk."""
    scored = [o for o in outcomes if o.get("y") not in (None, "")]
    n = len(scored)
    if n == 0:
        return {"n": 0, "brier_desk": None, "brier_market": None, "skill": None}
    bd = sum(brier(float(o["desk_p"]), int(o["y"])) for o in scored) / n
    bm = sum(brier(float(o["market_mid"]), int(o["y"])) for o in scored) / n
    return {"n": n, "brier_desk": bd, "brier_market": bm, "skill": bm - bd}
