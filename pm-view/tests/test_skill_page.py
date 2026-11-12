"""pm-view/SKILL.md is a regeneration from its records (tools/check_skill_pages.py,
2026-11-11 12:15Z; the class of predictions/POST_MORTEMS.md "A Brier figure rounded
twice": a page printing figures from a record with nothing reading the page back).
These tests hold the committed page equal to `score.summary_text` at the page's own
date, `write_summary` writing exactly that text, the date between the newest record
row and today, and the gate naming an alteration by line."""
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import score as S

PM_VIEW = Path(__file__).resolve().parents[1]
ROOT = PM_VIEW.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_skill_pages as csp  # noqa: E402

PAGE = PM_VIEW / "SKILL.md"
LEDGER, OUTCOMES = PM_VIEW / "ledger.csv", PM_VIEW / "outcomes.csv"
READINGS, READINGS_OUTCOMES = PM_VIEW / "readings.csv", PM_VIEW / "readings_outcomes.csv"


def entries() -> list[dict]:
    manifest = PM_VIEW / "data" / "manifest.json"
    return json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []


def regenerate(day: str) -> str:
    return S.summary_text(LEDGER, OUTCOMES, date.fromisoformat(day), entries())


def test_the_committed_page_is_the_regeneration_at_its_own_date():
    text = PAGE.read_text(encoding="utf-8")
    day, problems = csp.generated_on(text, S.PAGE_GENERATOR)
    assert problems == [] and day is not None
    assert regenerate(day) == text


def test_the_page_date_lies_between_the_newest_record_row_and_today():
    text = PAGE.read_text(encoding="utf-8")
    day, _ = csp.generated_on(text, S.PAGE_GENERATOR)
    newest = S.records_newest_day(LEDGER, OUTCOMES, READINGS, READINGS_OUTCOMES)
    today = datetime.now(UTC).date().isoformat()
    assert newest is not None and day is not None
    assert newest <= day <= today
    assert csp.page_violations(text, S.PAGE_GENERATOR, regenerate, newest, today) == []


def _main_paths(tmp_path: Path, skill: Path) -> list[str]:
    return ["--today", "2026-11-06", "--ledger", str(LEDGER), "--outcomes", str(OUTCOMES), "--skill", str(skill),
            "--manifest", str(PM_VIEW / "data" / "manifest.json")]


def test_summary_dry_run_prints_exactly_the_page_and_writes_nothing(tmp_path, capsys):
    # 2026-11-12 06:15Z (predictions/POST_MORTEMS.md "A dry run that wrote the page"): `--summary --dry-run`
    # wrote SKILL.md dated that day, because main read the flag on its scoring branch only; a page so
    # written is a true regeneration, so the page check admits it. The tool must not write it.
    skill = tmp_path / "SKILL.md"
    assert S.main(["--summary", "--dry-run", *_main_paths(tmp_path, skill)]) == 0
    assert capsys.readouterr().out == regenerate("2026-11-06") == PAGE.read_text(encoding="utf-8")
    assert sorted(p.name for p in tmp_path.iterdir()) == []


def test_summary_without_dry_run_writes_the_page_and_says_so(tmp_path, capsys):
    skill = tmp_path / "SKILL.md"
    assert S.main(["--summary", *_main_paths(tmp_path, skill)]) == 0
    assert capsys.readouterr().out == "wrote SKILL.md\n"
    assert skill.read_text(encoding="utf-8") == regenerate("2026-11-06")


def test_scoring_dry_run_writes_nothing_either(tmp_path):
    # the other path of main, with a reading on record and nothing due, no manifest and so no fetch
    rd = tmp_path / "readings.csv"
    rd.write_text(READINGS.read_text(encoding="utf-8"), encoding="utf-8")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert S.main(["--dry-run", "--today", "2026-11-01", "--ledger", str(LEDGER), "--outcomes", str(tmp_path / "o.csv"),
                   "--readings", str(rd), "--readings-outcomes", str(tmp_path / "ro.csv"),
                   "--manifest", str(tmp_path / "none.json")]) == 0
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_write_summary_writes_exactly_summary_text(tmp_path):
    out = tmp_path / "SKILL.md"
    S.write_summary(LEDGER, OUTCOMES, out, date(2026, 11, 6), entries())
    assert out.read_text(encoding="utf-8") == regenerate("2026-11-06") == PAGE.read_text(encoding="utf-8")


@pytest.mark.parametrize("alteration, named", [
    (("| fomc_bills | 3 | 0 |", "| fomc_bills | 4 | 0 |"), "first at line 18"),  # a count typed onto the page
    (("Scored calls: 0.", "Scored calls: 1."), "first at line 9"),                 # the headline count
    (("Readings on record: 4;", "Readings on record: 5;"), "first at line 21"),   # the readings count
    (("| (no call logged yet) | | | | | |\n", ""), "first at line 7"),            # a row removed
])
def test_an_alteration_of_the_committed_page_is_named_by_line(alteration, named):
    text = PAGE.read_text(encoding="utf-8")
    altered = text.replace(*alteration, 1)
    assert altered != text, alteration
    (only,) = csp.page_violations(altered, S.PAGE_GENERATOR, regenerate, None, "2026-12-31")
    assert named in only and "rewrite the page with `pm-view/score.py --summary`" in only


def test_the_newest_record_day_reads_every_record_the_page_summarises(tmp_path):
    # calls, readings and both scored records, through the scored records' gates; a missing file is empty
    led = tmp_path / "ledger.csv"
    led.write_text("id,made_on\nC1,2026-11-03\n", encoding="utf-8")
    rd = tmp_path / "readings.csv"
    rd.write_text("id,made_on\nR1,2026-11-06\n", encoding="utf-8")
    assert S.records_newest_day(led, tmp_path / "outcomes.csv", rd, tmp_path / "readings_outcomes.csv") == "2026-11-06"
    assert S.records_newest_day(tmp_path / "none.csv", tmp_path / "none2.csv", tmp_path / "none3.csv",
                                tmp_path / "none4.csv") is None
