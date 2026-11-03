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
from datetime import datetime
from typing import Any

MIN_DEPARTURE = 0.10  # |desk p - market mid| below this: no call
VOLUME_FLOOR = 10_000.0  # USDC, cumulative, as Study 013 §6.3
SPREAD_CAP = 0.10
RESOLUTION_BEGUN = ("proposed", "disputed", "resolved")

LEDGER_COLUMNS = (
    "id", "made_on", "venue", "market_id", "condition_id", "yes_token_id", "proposition",
    "due_on", "market_mid", "market_spread", "volume_usdc", "desk_p", "basis", "quote_sha256",
)
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


def eligibility(row: dict[str, Any], best: tuple[float, float] | None, at: datetime) -> str | None:
    """The first reason, in Study 013's §6.3 order, that excludes a market from a call; None when eligible.

    `row` is the Gamma market record; `best` the CLOB book's best bid and ask
    (None for a one-sided or empty book)."""
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


def call_violations(desk_p: float, market_mid: float, basis: str) -> list[str]:
    """What stops a draft call from being logged; empty when it may be."""
    out: list[str] = []
    if not (0.0 < desk_p < 1.0):
        out.append("desk_p is not a probability")
    if departure(desk_p, market_mid) < MIN_DEPARTURE:
        out.append(f"desk_p is within {MIN_DEPARTURE:.2f} of the market mid: no call")
    if "market" not in basis.lower():
        out.append("basis must name the market's probability and what it is missing")
    return out


def skill_summary(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Brier for the desk and for the market mid over the scored calls (y present); skill = market minus desk."""
    scored = [o for o in outcomes if o.get("y") not in (None, "")]
    n = len(scored)
    if n == 0:
        return {"n": 0, "brier_desk": None, "brier_market": None, "skill": None}
    bd = sum(brier(float(o["desk_p"]), int(o["y"])) for o in scored) / n
    bm = sum(brier(float(o["market_mid"]), int(o["y"])) for o in scored) / n
    return {"n": n, "brier_desk": bd, "brier_market": bm, "skill": bm - bd}
