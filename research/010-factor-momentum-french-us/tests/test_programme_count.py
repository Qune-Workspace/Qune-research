"""Programme-wide re-count (§9.4, §14 step 5) on synthetic files."""
import json

import pytest

import programme_count as pc

TABLE = """# Trial log

| ID | Date logged | Description | Window |
|---|---|---|---|
| T1 | 2026-10-26 | primary | H |
| T1a | 2026-10-26 | companion | H |

## Log

| Step | Date | Outcome |
|---|---|---|
| Data step | 2026-10-26 | pass |
"""


def test_registered_rows_reads_only_the_id_table(tmp_path):
    p = tmp_path / "trials.md"
    p.write_text(TABLE)
    assert pc.registered_rows(p) == ["T1", "T1a"]


def test_registered_rows_refuses_without_table(tmp_path):
    p = tmp_path / "trials.md"
    p.write_text("| Step | Date |\n|---|---|\n| x | y |\n")
    with pytest.raises(SystemExit):
        pc.registered_rows(p)


def test_count_public_sums_studies(tmp_path):
    for name in ("001-a", "002-b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "trials.md").write_text(TABLE)
    assert pc.count_public(tmp_path) == {"001-a": ["T1", "T1a"], "002-b": ["T1", "T1a"]}


def test_count_desk_rows_corrections_and_family_hits(tmp_path):
    rows = [{"id": "A", "corrects": None, "note": "trend"},
            {"id": "B", "corrects": "A", "note": "fix"},
            {"id": "C", "corrects": None, "note": "HML momentum"}]
    p = tmp_path / "reg.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    assert pc.count_desk(p) == {"rows": 3, "correction_rows": 1, "family_keyword_hits": 1}
