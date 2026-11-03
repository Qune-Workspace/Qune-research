"""Study 013 outcome rule (PREREGISTRATION.md §6.5), a pure function for the scoring run.

Only the scoring run (§14 step 9, after `APPROVED`) reads the fetch's outcome
file and calls this; the data step never imports this module. The tests call
it on dicts built in memory (§6.6: "the outcome rule on each excluded state").

A market resolves **first-token** when the UMA status is `resolved`, the
decoded outcome prices are exactly 1 and 0 in that order, and the CLOB token
whose id equals the first listed token id has `winner` true while the other has
`winner` false; **second-token** when the prices are exactly 0 and 1 with the
winners reversed. Every other state excludes the market and is counted by
kind, in the order §6.5 writes them: not resolved at the fetch; prices not one
of the two vectors (a 50/50 or fractional settlement); disagreement between the
prices and the winner flags; a missing or failed fetch.

Reading recorded with the code (2026-11-03): a failed or missing fetch carries
no status at all, so none of the first three kinds can be evaluated on it; the
code therefore tests for it first and reports it under the fourth kind, which
is where §6.5 lists it. The order of the kinds in the report is as written.
"""

from __future__ import annotations

from src.snapshots import as_float, decode_list

FIRST = "first-token"
SECOND = "second-token"
NOT_RESOLVED = "not resolved at the fetch"
NOT_BINARY_SETTLEMENT = "settlement not 1/0 or 0/1"
DISAGREEMENT = "prices and winner flags disagree"
UNFETCHED = "missing or failed fetch"
KINDS = (NOT_RESOLVED, NOT_BINARY_SETTLEMENT, DISAGREEMENT, UNFETCHED)


def _exact(v: object, target: float) -> bool:
    x = as_float(v)
    return x is not None and x == target


def classify(status: dict | None, outcome: dict | None, first_token_id: str) -> str:
    """§6.5 on one market: FIRST, SECOND, or the excluding kind."""
    if status is None or outcome is None or status.get("fetch_failed") or outcome.get("fetch_failed"):
        return UNFETCHED
    uma = status.get("umaResolutionStatus")
    if not isinstance(uma, str) or uma.lower() != "resolved":
        return NOT_RESOLVED
    prices = decode_list(outcome.get("outcomePrices"))
    if prices is None or len(prices) != 2:
        return NOT_BINARY_SETTLEMENT
    if _exact(prices[0], 1.0) and _exact(prices[1], 0.0):
        side = FIRST
    elif _exact(prices[0], 0.0) and _exact(prices[1], 1.0):
        side = SECOND
    else:
        return NOT_BINARY_SETTLEMENT
    tokens = outcome.get("tokens")
    if not isinstance(tokens, list) or len(tokens) != 2:
        return DISAGREEMENT
    first = [t for t in tokens if str(t.get("token_id")) == str(first_token_id)]
    other = [t for t in tokens if str(t.get("token_id")) != str(first_token_id)]
    if len(first) != 1 or len(other) != 1:
        return DISAGREEMENT
    w_first, w_other = first[0].get("winner"), other[0].get("winner")
    if side == FIRST and w_first is True and w_other is False:
        return FIRST
    if side == SECOND and w_first is False and w_other is True:
        return SECOND
    return DISAGREEMENT


def y_of(kind: str) -> int | None:
    """1 for first-token, 0 for second-token, None when excluded."""
    return {FIRST: 1, SECOND: 0}.get(kind)
