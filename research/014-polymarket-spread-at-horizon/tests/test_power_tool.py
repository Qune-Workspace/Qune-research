"""tools/power_pm014.py computes Study 014's minimum detectable effect from counts only: the sd
bounds follow from the sample's spread cap and tick, the clean counts are read from Study 013's
power file, and the snapshot cross-check reads no price field (2026-11-16 18:15Z run)."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import power_pm014 as power  # noqa: E402


def test_sd_bounds_are_half_the_log_range() -> None:
    # longshot bin: s in [0.001/0.10, 0.10/0.01] = [0.01, 10]
    assert power.log_sd_bound(0.01, 0.10) == pytest.approx(math.log(1000) / 2)
    # central bin: s in [0.001/0.60, 0.10/0.40]
    assert power.log_sd_bound(0.40, 0.60) == pytest.approx((math.log(0.25) - math.log(0.001 / 0.6)) / 2)


def test_mde_matches_the_closed_form_and_refuses_an_empty_bin() -> None:
    sd1, sd2 = power.log_sd_bound(*power.LONGSHOT), power.log_sd_bound(*power.CENTRAL)
    want = 2.842 * math.sqrt(sd1**2 / 4469.4 + sd2**2 / 893.88)
    assert power.mde(4469.4, 893.88, 2.842) == pytest.approx(want)
    assert power.mde(100, 100, 2.486) < power.mde(100, 100, 2.842)
    with pytest.raises(ValueError):
        power.mde(0, 100, 2.842)


def test_clean_counts_read_the_four_rows_of_the_013_file() -> None:
    text = (ROOT / "tools" / "power_pm013.txt").read_text(encoding="utf-8")
    counts = power.clean_counts(text)
    assert counts[(8, "events")] == 44_694 and counts[(4, "events")] == 22_347
    assert counts[(8, "markets")] == 77_967 and counts[(4, "markets")] == 38_983
    with pytest.raises(ValueError):
        power.clean_counts("no rows here\n")


def test_snapshot_counts_read_no_price_field(tmp_path: Path) -> None:
    rows = [
        # in the window, at the floor, no price field present at all
        {"id": "1", "enableOrderBook": True, "outcomes": '["Yes", "No"]', "endDate": "2026-12-01T12:00:00Z", "volumeNum": 20000, "eventIds": ["e1"]},
        # same event, so one event; a +05:00 stamp still inside the window in UTC
        {"id": "2", "enableOrderBook": True, "outcomes": '["Yes", "No"]', "endDate": "2026-12-30T04:00:00+05:00", "volumeNum": 10000, "eventIds": ["e1"]},
        # below the floor
        {"id": "3", "enableOrderBook": True, "outcomes": '["Yes", "No"]', "endDate": "2026-12-01T12:00:00Z", "volumeNum": 999, "eventIds": ["e3"]},
        # scheduled end exactly at the window's end: out
        {"id": "4", "enableOrderBook": True, "outcomes": '["Yes", "No"]', "endDate": "2026-12-30T00:00:00Z", "volumeNum": 50000, "eventIds": ["e4"]},
        # not binary; no order book; a zoneless end
        {"id": "5", "enableOrderBook": True, "outcomes": '["A", "B", "C"]', "endDate": "2026-12-01T12:00:00Z", "volumeNum": 50000, "eventIds": ["e5"]},
        {"id": "6", "enableOrderBook": False, "outcomes": '["Yes", "No"]', "endDate": "2026-12-01T12:00:00Z", "volumeNum": 50000, "eventIds": ["e6"]},
        {"id": "7", "enableOrderBook": True, "outcomes": '["Yes", "No"]', "endDate": "2026-12-01T12:00:00", "volumeNum": 50000, "eventIds": ["e7"]},
    ]
    p = tmp_path / "records.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    c = power.snapshot_counts(p)
    assert c == {
        "rows": 7,
        "order_book": 6,
        "binary": 5,
        "end_unreadable_or_missing": 1,
        "end_in_window": 3,
        "at_volume_floor": 2,
        "events_at_floor": 1,
    }
    assert not set(power.SNAPSHOT_FIELDS_READ) & set(power.PRICE_FIELDS_NEVER_READ)
