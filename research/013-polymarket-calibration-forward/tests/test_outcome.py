"""Tests of the Study 013 outcome rule (PREREGISTRATION.md §6.5, §6.6: "the outcome rule on each excluded state")."""

from __future__ import annotations

import pytest
from src import outcome as oc


def status(uma="resolved", failed=False) -> dict:
    return {"id": "1", "umaResolutionStatus": uma, "fetch_failed": failed}


def result(prices='["1", "0"]', winners=(True, False), tokens=("10", "11")) -> dict:
    return {"id": "1", "outcomePrices": prices, "tokens": [{"token_id": tokens[0], "winner": winners[0]}, {"token_id": tokens[1], "winner": winners[1]}]}


def test_first_and_second_token_resolutions():
    assert oc.classify(status(), result(), "10") == oc.FIRST
    assert oc.classify(status(), result('["0", "1"]', (False, True)), "10") == oc.SECOND
    # the listing's first token may be the CLOB's second entry; the id decides, not the position
    assert oc.classify(status(), result('["1", "0"]', (False, True), tokens=("11", "10")), "10") == oc.FIRST
    # decimal strings and numbers both read as exactly 1 and 0
    assert oc.classify(status(), result('["1.0", "0.0"]'), "10") == oc.FIRST
    assert oc.classify(status(), result([1, 0]), "10") == oc.FIRST
    assert oc.y_of(oc.FIRST) == 1 and oc.y_of(oc.SECOND) == 0 and oc.y_of(oc.NOT_RESOLVED) is None


@pytest.mark.parametrize(
    ("st", "res", "kind"),
    [
        (status(uma=None), result(), oc.NOT_RESOLVED),
        (status(uma="proposed"), result(), oc.NOT_RESOLVED),
        (status(uma="disputed"), result(), oc.NOT_RESOLVED),
        (status(), result('["0.5", "0.5"]'), oc.NOT_BINARY_SETTLEMENT),
        (status(), result('["0.999", "0.001"]'), oc.NOT_BINARY_SETTLEMENT),
        (status(), result('["1"]'), oc.NOT_BINARY_SETTLEMENT),
        (status(), result("not json"), oc.NOT_BINARY_SETTLEMENT),
        (status(), result('["1", "0"]', (False, True)), oc.DISAGREEMENT),
        (status(), result('["1", "0"]', (True, True)), oc.DISAGREEMENT),
        (status(), result('["0", "1"]', (True, False)), oc.DISAGREEMENT),
        (status(), result('["1", "0"]', (True, False), tokens=("77", "78")), oc.DISAGREEMENT),  # first token id absent
        (status(), {"id": "1", "outcomePrices": '["1", "0"]'}, oc.DISAGREEMENT),  # no token list
        (status(failed=True), result(), oc.UNFETCHED),
        (None, result(), oc.UNFETCHED),
        (status(), None, oc.UNFETCHED),
    ],
)
def test_each_excluded_state_is_counted_under_its_kind(st, res, kind):
    assert oc.classify(st, res, "10") == kind


def test_a_resolved_market_whose_prices_came_before_finality_is_not_counted_as_resolved():
    # pitfall 2: outcomePrices is set before UMA finality; UMA resolved is required first
    assert oc.classify(status(uma="proposed"), result(), "10") == oc.NOT_RESOLVED
    assert oc.KINDS == (oc.NOT_RESOLVED, oc.NOT_BINARY_SETTLEMENT, oc.DISAGREEMENT, oc.UNFETCHED)
