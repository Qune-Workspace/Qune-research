"""The mechanical search for a rule in prose with its check elsewhere (2026-11-06
12:15Z, predictions/POST_MORTEMS.md "A rule in prose, a check elsewhere: the
mechanical search").

The class of defect this folder met three times in a week: a rule written in
README.md and enforced in whichever copy of the code happened to be open, or
in none.  The search is three lists that must agree, and a shape rule on the
prose:

1. the `[gate:<tag>]` tags written in README.md beside the rules;
2. `pm_lib.GATE_TAGS`, and the tags the gate's source actually passes to
   `pm_lib.gate(...)` (a tag declared but never used is a check that does not
   exist);
3. the tags the gate emits when driven over rows that each break one rule (a
   tag in the source that no input can reach is dead);

and every bold rule in README.md rule 2 carries at least one tag, so a rule
added in prose without naming its check fails here, on the day it is written.
"""
import re
from pathlib import Path

import pm_lib as L

HERE = Path(__file__).resolve().parent.parent
README = (HERE / "README.md").read_text(encoding="utf-8")
SOURCE = (HERE / "pm_lib.py").read_text(encoding="utf-8")
GATE_CALL_RE = re.compile(r'\bgate\("([a-z-]+)"')
SETTLES = "the upper bound of the target range after the 9 December 2026 meeting is 25 bp higher"
BASIS = "the market prices 0.45; the bills price 0.99 after the November prints"


def rule_2() -> str:
    lines = [ln for ln in README.splitlines() if ln.startswith("2. ")]
    assert len(lines) == 1, "README.md rule 2 is one numbered paragraph"
    return lines[0]


def emitted(**kw) -> set[str]:
    row = dict(desk_p=0.90, market_mid=0.45, basis=BASIS, settles_on=SETTLES, proposition="x",
               method="fomc_bills", method_p=0.99, range_lo=0.60, range_hi=1.00, r2=True)
    row.update(kw)
    return L.gate_tags(" ".join(L.call_violations(**row)))


# one row per rule, each breaking that rule and (as far as the gate's order allows) nothing else
BREAKERS: dict[str, dict] = {
    "probability": dict(desk_p=1.0),
    "departure": dict(desk_p=0.50, method_p=0.50, range_lo=0.48, range_hi=0.52, market_mid=0.45),
    "basis-names-market": dict(basis="no mention of the venue's number"),
    "settles-on": dict(settles_on=""),
    "method-named": dict(method=None),
    "stated-bare": dict(method="stated", method_p=0.99),
    "calibrated": dict(r2=False),
    "range-brackets": dict(range_lo=None),
    "range": dict(market_mid=0.70, desk_p=0.95),
    "touch-below": dict(method="btc_touch", method_p=0.40, range_lo=0.30, range_hi=0.40, market_mid=0.60, desk_p=0.30),
    "method-departure": dict(method_p=0.52, range_lo=0.50, range_hi=0.54, market_mid=0.45, desk_p=0.60),
    "desk-side": dict(desk_p=0.30),
}


def test_the_prose_the_declaration_and_the_source_name_the_same_rules():
    prose = L.gate_tags(README)
    declared = set(L.GATE_TAGS)
    in_source = set(GATE_CALL_RE.findall(SOURCE))
    assert prose == declared, (f"README.md and pm_lib.GATE_TAGS disagree: prose only {sorted(prose - declared)}, "
                               f"declared only {sorted(declared - prose)}")
    assert in_source == declared, (f"pm_lib.GATE_TAGS and the gate's source disagree: declared only "
                                   f"{sorted(declared - in_source)}, source only {sorted(in_source - declared)}")
    assert len(L.GATE_TAGS) == len(declared), "a tag is declared twice"


def test_every_tag_is_reachable_and_each_breaker_trips_its_own_rule():
    assert emitted() == set(), "the clean row must pass the whole gate"
    seen: set[str] = set()
    for tag, kw in BREAKERS.items():
        tags = emitted(**kw)
        assert tag in tags, f"{tag}: the row built to break it did not trip it (got {sorted(tags)})"
        seen |= tags
    assert seen == set(L.GATE_TAGS), f"never emitted: {sorted(set(L.GATE_TAGS) - seen)}"
    assert set(BREAKERS) == set(L.GATE_TAGS), "one breaker per declared tag"


def test_every_bold_rule_in_rule_2_carries_a_tag():
    text = rule_2()
    headings = re.findall(r"\*\*([^*]+)\*\*", text)
    bodies = re.split(r"\*\*[^*]+\*\*", text)[1:]
    assert len(headings) == len(bodies) and headings, "rule 2 is a list of bold rules each followed by its text"
    for heading, body in zip(headings, bodies, strict=True):
        assert L.gate_tags(heading + body), f"a rule with no check tag: {heading!r}"


def test_tags_outside_rule_2_are_not_rules():
    # the tags live where the rules live; a tag elsewhere in the README is a rule in the wrong place
    rest = README.replace(rule_2(), "")
    assert L.gate_tags(rest) == set(), f"gate tags outside rule 2: {sorted(L.gate_tags(rest))}"


def test_gate_refuses_an_unknown_tag():
    import pytest
    with pytest.raises(ValueError):
        L.gate("not-a-rule", "x")
