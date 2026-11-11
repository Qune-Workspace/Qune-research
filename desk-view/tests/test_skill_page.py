"""predictions/SKILL.md is a regeneration from its records (tools/check_skill_pages.py,
2026-11-11 12:15Z; the class of predictions/POST_MORTEMS.md "A Brier figure rounded
twice": a page printing figures from a record with nothing reading the page back).
These tests hold the committed page equal to `baseline.page_text` at the page's own
date, the date between the newest record row and today, the `--summary --dry-run`
output byte-identical to the page, and the gate naming an alteration by line."""
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


@pytest.mark.parametrize("alteration, named", [
    (("0.0455", "0.0456"), "first at line 14"),                       # a digit of the baseline Brier
    (("| V3-2026-10-23 |", "| V3-2026-10-24 |"), "first at line 9"),  # an id
    (("not yet due", "hit"), "first at line 8"),                      # an outcome typed onto the page
    (("\n\nScored calls", "\nScored calls"), "first at line 12"),     # a blank line removed
])
def test_an_alteration_of_the_committed_page_is_named_by_line(alteration, named):
    text = PAGE.read_text(encoding="utf-8")
    altered = text.replace(*alteration, 1)
    assert altered != text, alteration
    (only,) = csp.page_violations(altered, bl.PAGE_GENERATOR, regenerate, None, "2026-12-31")
    assert named in only and "rewrite the page with `predictions/baseline.py --summary`" in only


def test_the_newest_record_day_is_the_newest_stamp_of_the_three_records():
    ledger = sc.read_ledger(sc.LEDGER)
    stamps = [str(d)[:10] for d in ledger["made_on"]]
    stamps += [str(d)[:10] for d in bl.read_baselines(ledger, bl.BASELINES)["computed_on"]]
    stamps += [str(d)[:10] for d in sc.read_outcomes(ledger, sc.OUTCOMES)["scored_on"]]
    assert bl.records_newest_day(sc.LEDGER, bl.BASELINES, sc.OUTCOMES) == max(stamps)
