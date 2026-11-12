"""tools/power_pm013.py labels its counts by the parsed stamp's UTC month and day, never by a slice of the
text (2026-11-12 00:15Z, predictions/POST_MORTEMS.md "A universe listed by hand").

Shown on 00dac67 before the change, over the six rows below: the `+05:00` row was counted under
2026-09-01 and 2026-09 (its UTC time is 2026-08-31 21:00), the basic-format row under the labels
`2026090` and `20260901T0`, the `dd/mm/yyyy` row under `01/09/2` and `01/09/2026`, and the zoneless row as
if it were UTC.  The kept records of 2026-11-02 all carry `...+00` (closedTime) and `...Z` (endDate), so
the committed output tools/power_pm013.txt is unchanged by the fix (recounted on the day).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
for folder in ("tools", "pm-view"):
    if str(ROOT / folder) not in sys.path:
        sys.path.insert(0, str(ROOT / folder))

import check_stamp_compares  # noqa: E402
import power_pm013 as power  # noqa: E402


def _row(mid: str, closed: object, end: object) -> dict:
    return {"id": mid, "closedTime": closed, "endDate": end, "eventIds": [f"e{mid}"]}


SHAPES = [
    # (closedTime, endDate, month label, day label)
    ("2026-08-01 06:04:36+00", "2026-08-01T03:59:00Z", "2026-08", "2026-08-01"),  # as Gamma writes them
    ("2026-08-02T16:15:51Z", "2026-08-01T00:00:00.000Z", "2026-08", "2026-08-01"),  # Z, fractional seconds
    ("2026-09-01T02:00:00+05:00", "2026-09-01T02:00:00+05:00", "2026-08", "2026-08-31"),  # another zone: UTC day
    ("2026-08-31T23:30:00-02:00", "2026-08-31T23:30:00-02:00", "2026-09", "2026-09-01"),  # the other way
    ("20260901T050000Z", "20260901T050000Z", "2026-09", "2026-09-01"),  # basic format: a valid ISO 8601 time, read
    ("01/09/2026 05:00", "01/09/2026", "unreadable closedTime", "unreadable endDate"),  # another format
    ("2026-09-01 05:00:00", "2026-09-01T05:00:00", "unreadable closedTime", "unreadable endDate"),  # no zone
    (None, None, "no closedTime", "no endDate"),  # missing
    ("", "", "no closedTime", "no endDate"),  # empty text
]


@pytest.mark.parametrize("closed, end, month, day", SHAPES)
def test_labels_are_the_parsed_utc_month_and_day(closed: object, end: object, month: str, day: str) -> None:
    assert power.month_of(closed) == month
    assert power.day_of(end) == day


def test_count_table_keys_by_parsed_labels() -> None:
    rows = [_row(str(i), c, e) for i, (c, e, _, _) in enumerate(SHAPES)]
    by_month, by_day, n = power.count_table(rows)
    assert n == len(SHAPES)
    assert sorted(by_month) == sorted({m for _, _, m, _ in SHAPES})
    assert sorted(by_day) == sorted({d for _, _, _, d in SHAPES})
    # the two rows in other zones sit under their UTC day, not the day their text begins with
    assert by_day["2026-08-31"]["markets"] == 1
    assert by_day["2026-09-01"]["markets"] == 2  # the -02:00 row and the basic-format row
    assert by_month["2026-08"]["markets"] == 3


def test_period_labels_exclude_the_unreadable_and_missing() -> None:
    assert power.is_period_label("2026-08-01")
    assert power.is_period_label("2026-08")
    assert not power.is_period_label("no endDate")
    assert not power.is_period_label("unreadable endDate")


def test_the_tool_is_in_the_stamp_check_universe_and_clean() -> None:
    """The check's universe is found by reading the tree; this tool is in it and has no hit."""
    found, _excluded = check_stamp_compares._modules(ROOT)
    rels = {p.relative_to(ROOT).as_posix() for p in found}
    assert "tools/power_pm013.py" in rels
    assert check_stamp_compares.check_file(ROOT / "tools" / "power_pm013.py", ROOT) == []
