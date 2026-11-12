"""`src/snapshots.py parse_time` trims the UTC designator by a replace, not a slice (§16, 2026-11-12), and
reads every shape exactly as before: the behaviour the code review approved is unchanged."""
from __future__ import annotations

import datetime as dt

import pytest
from src.snapshots import parse_time

UTC = dt.UTC

CASES = [
    ("2026-11-02T06:21:24Z", dt.datetime(2026, 11, 2, 6, 21, 24, tzinfo=UTC)),
    ("2026-11-02T06:21:24z", dt.datetime(2026, 11, 2, 6, 21, 24, tzinfo=UTC)),
    ("2026-11-02T06:21:24.408Z", dt.datetime(2026, 11, 2, 6, 21, 24, 408000, tzinfo=UTC)),
    ("2026-11-02 06:21:24+00", dt.datetime(2026, 11, 2, 6, 21, 24, tzinfo=UTC)),  # Gamma's closedTime shape
    ("2026-11-02T06:21:24+05:00", dt.datetime(2026, 11, 2, 1, 21, 24, tzinfo=UTC)),  # another zone, to UTC
    ("2026-11-02T06:21:24", dt.datetime(2026, 11, 2, 6, 21, 24, tzinfo=UTC)),  # zoneless: read as UTC (reviewed)
    ("  2026-11-02T06:21:24Z  ", dt.datetime(2026, 11, 2, 6, 21, 24, tzinfo=UTC)),
    ("20261102T062124Z", dt.datetime(2026, 11, 2, 6, 21, 24, tzinfo=UTC)),  # basic format: read by fromisoformat, as before
    ("02/11/2026 06:21", None),
    ("", None),
    (None, None),
    (20261102, None),
]


@pytest.mark.parametrize("text, want", CASES)
def test_parse_time_reads_each_shape_as_before(text: object, want: dt.datetime | None) -> None:
    assert parse_time(text) == want


def test_the_old_slice_and_the_replace_agree_on_every_iso_text() -> None:
    """The form before 2026-11-12 (`t[:-1] + "+00:00"` when the text ends in Z or z) and the replace give the
    same text on every ISO 8601 stamp, where Z occurs only as the zone designator."""
    for text, _ in CASES:
        if not isinstance(text, str):
            continue
        t = text.strip()
        old = t[:-1] + "+00:00" if t.endswith(("Z", "z")) else t
        new = t.replace("Z", "+00:00").replace("z", "+00:00")
        assert old == new, text
