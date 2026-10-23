"""The forward record's stopping rule and verdict table (§11.3–11.4).

The record is scored once, at the first month-end at which either 24
positive-regime months (T1's variable) have accumulated or 60 holding
periods have passed, whichever is first.  The verdict reads Δ̂, its
Newey–West t and the bootstrap interval; the refuted row is tested first so
that a result meeting both the supported and the refuted conditions is
reported as refuted and the conflict named by the caller.
"""
from __future__ import annotations

from collections.abc import Iterable

from .config import FORWARD_STOP_POSITIVE_MONTHS, FORWARD_STOP_TOTAL_MONTHS, FORWARD_T_MIN, MIN_EDGE_PER_MONTH

VERDICT_SUPPORTED = "supported (forward)"
VERDICT_REFUTED = "refuted (forward)"
VERDICT_INCONCLUSIVE = "inconclusive (forward)"


def stopping_month(positive_flags: Iterable[bool], stop_positive: int = FORWARD_STOP_POSITIVE_MONTHS,
                   stop_total: int = FORWARD_STOP_TOTAL_MONTHS) -> int | None:
    """1-based count of holding periods at which the rule first fires, or
    None if it has not fired on the flags seen so far (§11.3)."""
    n_pos = 0
    for n, flag in enumerate(positive_flags, start=1):
        n_pos += int(bool(flag))
        if n_pos >= stop_positive or n >= stop_total:
            return n
    return None


def forward_verdict(edge: dict, t_min: float = FORWARD_T_MIN, min_edge: float = MIN_EDGE_PER_MONTH) -> str:
    """§11.4 on the forward edge (base costs)."""
    nw, boot = edge.get("newey_west"), edge.get("bootstrap")
    if nw is None or boot is None:
        return VERDICT_INCONCLUSIVE
    t, upper = nw["t"], boot["delta"]["ci_high"]
    if upper < min_edge or t <= -t_min:
        return VERDICT_REFUTED
    if edge["delta"] > 0 and t >= t_min and edge["mean_positive"] > 0 and edge["mean_negative"] < 0:
        return VERDICT_SUPPORTED
    return VERDICT_INCONCLUSIVE
