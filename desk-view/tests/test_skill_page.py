"""predictions/SKILL.md is a regeneration from its records (tools/check_skill_pages.py,
2026-11-11 12:15Z; the class of predictions/POST_MORTEMS.md "A Brier figure rounded
twice": a page printing figures from a record with nothing reading the page back).
These tests hold the committed page equal to `baseline.page_text` at the page's own
date, the date between the newest record row and today, the `--summary --dry-run`
output byte-identical to the page, and the gate naming an alteration by line."""
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "predictions"))
sys.path.insert(0, str(ROOT / "tools"))

import baseline as bl  # noqa: E402
import check_skill_pages as csp  # noqa: E402
import score as sc  # noqa: E402

PAGE = ROOT / "predictions" / "SKILL.md"


def regenerate(day: str) -> str:
    return bl.page_text(pd.Timestamp(day), sc.LEDGER, bl.BASELINES, sc.OUTCOMES)


def test_the_committed_page_is_the_regeneration_at_its_own_date():
    text = PAGE.read_text(encoding="utf-8")
    day, problems = csp.generated_on(text, bl.PAGE_GENERATOR)
    assert problems == [] and day is not None
    assert regenerate(day) == text


def test_the_page_date_lies_between_the_newest_record_row_and_today():
    day, _ = csp.generated_on(PAGE.read_text(encoding="utf-8"), bl.PAGE_GENERATOR)
    newest = bl.records_newest_day(sc.LEDGER, bl.BASELINES, sc.OUTCOMES)
    assert newest is not None and day is not None
    assert newest <= day <= datetime.now(UTC).date().isoformat()
    assert csp.page_violations(PAGE.read_text(encoding="utf-8"), bl.PAGE_GENERATOR, regenerate, newest,
                               datetime.now(UTC).date().isoformat()) == []


def test_summary_dry_run_prints_exactly_the_page():
    text = PAGE.read_text(encoding="utf-8")
    day, _ = csp.generated_on(text, bl.PAGE_GENERATOR)
    proc = subprocess.run([sys.executable, "baseline.py", "--summary", "--dry-run", "--today", str(day)],
                          cwd=ROOT / "predictions", capture_output=True, text=True, check=True)
    assert proc.stdout == text
    assert PAGE.read_text(encoding="utf-8") == text  # a dry run writes nothing


# Until 2026-11-13 18:15Z the four alterations below were typed from the page as it stood on
# 2026-10-29 ("0.0455" at line 14, "not yet due" at line 8, "| V3-2026-10-23 |" at line 9, the
# blank line at 12): the page's current values in the test's expectations, the class that
# failed pm-view's copy of this file on the first weekly regeneration (BUILD_LOG 2026-11-13
# 06:15Z) and that would have failed this one on the first scoring after 31 December, when
# every outcome cell changes and the baseline Brier is over five calls.  Each alteration is
# now built from the page as it stands and names the line by where it is; the test after them
# holds the builders against a page in the record's next state (every call scored).

def _bump(pattern: str):
    """Add one to the first integer the pattern captures on the first line it matches;
    returns the altered text and that line's 1-based number."""
    def alter(text: str) -> tuple[str, int]:
        lines = text.split("\n")
        for i, line in enumerate(lines):
            m = re.search(pattern, line)
            if m:
                lines[i] = line[:m.start(1)] + str(int(m.group(1)) + 1) + line[m.end(1):]
                return "\n".join(lines), i + 1
        raise AssertionError(f"no line matches {pattern!r}")
    alter.__name__ = f"bump:{pattern}"
    return alter


def _alter_first_id(text: str) -> tuple[str, int]:
    """Append a character to the first call id in the table."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"^\| (V\d+-\d{4}-\d{2}-\d{2}) \|", line)
        if m:
            lines[i] = line[:m.end(1)] + "x" + line[m.end(1):]
            return "\n".join(lines), i + 1
    raise AssertionError("no call row on the page")


def _swap_first_outcome(text: str) -> tuple[str, int]:
    """Change the first row's outcome cell to another word of the closed set (hit, miss, not yet due)."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"^\| V\d+-\d{4}-\d{2}-\d{2} \|.* \| (not yet due|hit|miss) \|$", line)
        if m:
            other = "miss" if m.group(1) == "hit" else "hit"
            lines[i] = line[:m.start(1)] + other + line[m.end(1):]
            return "\n".join(lines), i + 1
    raise AssertionError("no call row with an outcome cell on the page")


def _drop_blank_before_scored(text: str) -> tuple[str, int]:
    """Remove the blank line before the "Scored calls" line; the first differing line is the blank's."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("Scored calls with a baseline:") and lines[i - 1] == "":
            del lines[i - 1]
            return "\n".join(lines), i
    raise AssertionError("no blank line before the Scored calls line")


ALTERATIONS = [
    _bump(r"^Brier, desk: \d\.\d{4}\. Brier, baseline: \d\.\d{3}(\d)\."),  # a digit of the baseline Brier
    _alter_first_id,                                                      # an id
    _swap_first_outcome,                                                  # an outcome typed onto the page
    _drop_blank_before_scored,                                            # a blank line removed
]


@pytest.mark.parametrize("alteration", ALTERATIONS, ids=lambda f: f.__name__)
def test_an_alteration_of_the_committed_page_is_named_by_line(alteration):
    text = PAGE.read_text(encoding="utf-8")
    altered, line = alteration(text)
    assert altered != text
    # the today bound is far off on purpose: this test is about the line named, not the date
    (only,) = csp.page_violations(altered, bl.PAGE_GENERATOR, regenerate, None, "2099-12-31")
    assert f"first at line {line}" in only and "rewrite the page with `predictions/baseline.py --summary`" in only


def test_the_alterations_apply_to_the_page_in_the_records_next_state(tmp_path):
    # The record's next state: every call scored (V2–V5 are due 2026-12-31).  The page then has no
    # "not yet due" cell, a baseline Brier over five calls and a different figure on every line the
    # alterations touch.  Each builder must still find its line there, so the expectations are shown to
    # come from the page and not from its state on the day the test was written.  Synthetic rows, in a
    # temporary copy of outcomes.csv only; the committed record is not touched.
    outcomes = sc.read_outcomes(sc.read_ledger(sc.LEDGER), sc.OUTCOMES)
    rows = [dict(zip(outcomes.columns, r, strict=True)) for r in outcomes.itertuples(index=False)]
    ledger = sc.read_ledger(sc.LEDGER)
    scored = {r["id"] for r in rows}
    for n, call in enumerate(ledger.itertuples(index=False)):
        if call.id in scored:
            continue
        rows.append({"id": call.id, "scored_on": call.due_on, "observed_on": call.due_on, "observed_value": "4.9",
                     "result": "hit" if n % 2 else "miss", "note": "synthetic: the record's next state",
                     "raw_sha256": "c" * 64})
    out = tmp_path / "outcomes.csv"
    pd.DataFrame(rows, columns=outcomes.columns).to_csv(out, index=False)

    def regen(day: str) -> str:
        return bl.page_text(pd.Timestamp(day), sc.LEDGER, bl.BASELINES, out)

    future = regen("2026-12-31")
    assert "not yet due" not in future and f"Scored calls with a baseline: {len(ledger)} (" in future
    for alteration in ALTERATIONS:
        altered, line = alteration(future)
        assert altered != future, alteration.__name__
        (only,) = csp.page_violations(altered, bl.PAGE_GENERATOR, regen, None, "2099-12-31")
        assert f"first at line {line}" in only, (alteration.__name__, only)


def test_the_newest_record_day_is_the_newest_stamp_of_the_three_records():
    ledger = sc.read_ledger(sc.LEDGER)
    stamps = [str(d)[:10] for d in ledger["made_on"]]
    stamps += [str(d)[:10] for d in bl.read_baselines(ledger, bl.BASELINES)["computed_on"]]
    stamps += [str(d)[:10] for d in sc.read_outcomes(ledger, sc.OUTCOMES)["scored_on"]]
    assert bl.records_newest_day(sc.LEDGER, bl.BASELINES, sc.OUTCOMES) == max(stamps)
