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

Extended 2026-11-07 00:15Z to the folder's second admitted action, a row to
readings.csv: `[reading:<tag>]` tags in README.md rule 5, `pm_lib.READING_TAGS`
and the tags `pm_lib.reading_violations` emits, held equal the same way; a
`gate:` tag belongs in rule 2 only and a `reading:` tag in rule 5 only.
"""
import re
from collections.abc import Callable
from pathlib import Path

import pm_lib as L

HERE = Path(__file__).resolve().parent.parent
README = (HERE / "README.md").read_text(encoding="utf-8")
SOURCE = (HERE / "pm_lib.py").read_text(encoding="utf-8")
GATE_CALL_RE = re.compile(r'\bgate\("([a-z-]+)"')
READING_CALL_RE = re.compile(r'\breading_gate\("([a-z-]+)"')
SETTLES = "the upper bound of the target range after the 9 December 2026 meeting is 25 bp higher"
BASIS = "the market prices 0.45; the bills price 0.99 after the November prints"
QUOTE = {"fetched_utc": "2026-11-06T06:16:38Z", "market_id": "6507380", "condition_id": "0xc3e5",
         "yes_token_id": "967", "gamma_sha256": "ab" * 32, "market_mid": 0.925, "end_date": "2026-12-01T05:00:00Z",
         "eligibility": "eligible"}


def rule(n: int) -> str:
    lines = [ln for ln in README.splitlines() if ln.startswith(f"{n}. ")]
    assert len(lines) == 1, f"README.md rule {n} is one numbered paragraph"
    return lines[0]


def rule_2() -> str:
    return rule(2)


def bold_rules_carry_a_tag(text: str, tags_in: Callable[[str], set[str]]) -> None:
    headings = re.findall(r"\*\*([^*]+)\*\*", text)
    bodies = re.split(r"\*\*[^*]+\*\*", text)[1:]
    assert len(headings) == len(bodies) and headings, "the rule is a list of bold rules each followed by its text"
    for heading, body in zip(headings, bodies, strict=True):
        assert tags_in(heading + body), f"a rule with no check tag: {heading!r}"


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
    bold_rules_carry_a_tag(rule_2(), L.gate_tags)


def test_tags_outside_rule_2_are_not_rules():
    # the tags live where the rules live; a tag elsewhere in the README is a rule in the wrong place
    rest = README.replace(rule_2(), "")
    assert L.gate_tags(rest) == set(), f"gate tags outside rule 2: {sorted(L.gate_tags(rest))}"


def test_gate_refuses_an_unknown_tag():
    import pytest
    with pytest.raises(ValueError):
        L.gate("not-a-rule", "x")
    with pytest.raises(ValueError):
        L.reading_gate("not-a-rule", "x")


# --- the readings gate (README rule 5), 2026-11-07 ----------------------------

def emitted_reading(**kw) -> set[str]:
    row = dict(method="btc_touch", method_p=0.876, range_lo=0.876, range_hi=0.886, market_mid=0.925,
               climatology_p=0.690, quote=QUOTE, made_on="2026-11-06", due_on="2026-12-01",
               market_id="6507380", existing_ids=("R-2026-11-03-fomc_bills-3215008",))
    row.update(kw)
    return L.reading_tags(" ".join(L.reading_violations(**row)))


# one row per rule, each breaking that rule and (as far as the gate's order allows) nothing else
READING_BREAKERS: dict[str, dict] = {
    "from-a-method": dict(method="stated"),
    "range-brackets": dict(range_lo=0.9),
    "mid-probability": dict(market_mid=1.0, quote=dict(QUOTE, market_mid=1.0)),
    "climatology-probability": dict(climatology_p=1.2),
    "written-quote": dict(quote=None),
    "mid-from-quote": dict(market_mid=0.9),
    "eligible-at-quote": dict(quote=dict(QUOTE, eligibility="spread above cap")),
    "made-on-quote-day": dict(made_on="2026-11-07"),
    "due-on-scheduled-end": dict(due_on="2026-12-09"),
    "one-per-day": dict(existing_ids=("R-2026-11-06-btc_touch-6507380",)),
}


def test_rule_5_prose_the_declaration_and_the_source_name_the_same_reading_rules():
    prose = L.reading_tags(README)
    declared = set(L.READING_TAGS)
    in_source = set(READING_CALL_RE.findall(SOURCE))
    assert prose == declared, (f"README.md and pm_lib.READING_TAGS disagree: prose only {sorted(prose - declared)}, "
                               f"declared only {sorted(declared - prose)}")
    assert in_source == declared, (f"pm_lib.READING_TAGS and the gate's source disagree: declared only "
                                   f"{sorted(declared - in_source)}, source only {sorted(in_source - declared)}")
    assert len(L.READING_TAGS) == len(declared), "a reading tag is declared twice"


def test_every_reading_tag_is_reachable_and_each_breaker_trips_its_own_rule():
    assert emitted_reading() == set(), "the clean reading must pass the whole gate"
    seen: set[str] = set()
    for tag, kw in READING_BREAKERS.items():
        tags = emitted_reading(**kw)
        assert tag in tags, f"{tag}: the row built to break it did not trip it (got {sorted(tags)})"
        seen |= tags
    assert seen == set(L.READING_TAGS), f"never emitted: {sorted(set(L.READING_TAGS) - seen)}"
    assert set(READING_BREAKERS) == set(L.READING_TAGS), "one breaker per declared reading tag"


def test_every_bold_rule_in_rule_5_carries_a_reading_tag():
    bold_rules_carry_a_tag(rule(5), L.reading_tags)


def test_reading_tags_outside_rule_5_are_not_rules():
    rest = README.replace(rule(5), "")
    assert L.reading_tags(rest) == set(), f"reading tags outside rule 5: {sorted(L.reading_tags(rest))}"
    assert L.gate_tags(rule(5)) == set(), "a call-gate tag in the readings rule"
