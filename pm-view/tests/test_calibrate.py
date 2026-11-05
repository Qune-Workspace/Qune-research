"""calibrate.py on series built in memory: the sample months (the live month
excluded), the outcome counts only closes after the evaluation observation, the
predictions are barrier.py's own functions on the same windows, the baseline
never looks ahead, and the written aggregates hold no level.  Nothing touches
the network."""
import json
import math
from datetime import date, timedelta

import calibrate as C
import pm_lib as L
import pytest


def flat_series(first: date, last: date, level: float = 50_000.0, step: float = 0.02) -> list[tuple[date, float]]:
    """Daily closes alternating +-step in log price: known volatility, never drifting."""
    out, x, k = [], math.log(level), 0
    d = first
    while d <= last:
        out.append((d, math.exp(x)))
        x += step if k % 2 == 0 else -step
        k += 1
        d += timedelta(days=1)
    return out


def test_sample_months_exclude_the_live_month_and_months_before_the_series():
    obs = flat_series(date(2025, 1, 15), date(2025, 6, 10))
    months = C.months_in(obs)
    assert months == [(2025, 1), (2025, 2), (2025, 3), (2025, 4), (2025, 5)]  # June is live, excluded


def test_rows_use_barrier_functions_on_the_prespecified_windows_and_skip_short_history():
    obs = flat_series(date(2024, 1, 1), date(2024, 12, 31))
    rows = C.rows_for(obs)
    # the first month with 90 observations before its first in-month observation is April
    assert sorted({r["month"] for r in rows})[0] == "2024-04"
    assert len({r["month"] for r in rows}) == 8  # April..November; December's end is after the last spot
    r = next(r for r in rows if r["month"] == "2024-05" and r["distance"] == 0.10 and r["side"] == "up")
    i = C.evaluation_index(obs, 2024, 5)
    spot = obs[i][1]
    closes = [v for _, v in obs[: i + 1]]
    s30 = L.realised_vol(closes[-31:])
    assert r["p30"] == pytest.approx(L.touch_probability(spot, spot * math.exp(0.10), s30, r["horizon_days"]))
    assert 25 < r["horizon_days"] < 32
    assert "level" not in r and "spot" not in r


def test_outcome_counts_only_later_closes_inside_the_month():
    obs = flat_series(date(2024, 1, 1), date(2024, 5, 31), step=0.001)
    i = C.evaluation_index(obs, 2024, 4)
    _, end = C.B.month_window_utc(2024, 4)
    spot = obs[i][1]
    up = spot * math.exp(0.05)
    assert C.touched_after(obs, i, up, "up", end) == 0
    # a close beyond the barrier before the evaluation observation does not count
    obs2 = list(obs)
    obs2[i - 1] = (obs2[i - 1][0], up * 1.01)
    assert C.touched_after(obs2, i, up, "up", end) == 0
    # one inside the month after it does; one in the next month does not
    obs3 = list(obs)
    obs3[i + 10] = (obs3[i + 10][0], up * 1.01)
    assert C.touched_after(obs3, i, up, "up", end) == 1
    obs4 = list(obs)
    j = C.evaluation_index(obs, 2024, 5)
    obs4[j + 1] = (obs4[j + 1][0], up * 1.01)
    assert C.touched_after(obs4, i, up, "up", end) == 0


def test_baseline_is_the_frequency_over_earlier_months_only():
    rows = []
    for k in range(15):
        rows.append({"month": f"2020-{k + 1:02d}" if k < 12 else f"2021-{k - 11:02d}", "distance": 0.05, "side": "up",
                     "p30": 0.5, "p90": 0.5, "y": 1 if k % 3 == 0 else 0, "horizon_days": 30.0})
    scored = C.add_baseline(rows, min_months=12)
    assert [r["month"] for r in scored] == ["2021-01", "2021-02", "2021-03"]
    # 2021-01 sees the 12 months of 2020: touches at k = 0, 3, 6, 9 -> 4/12
    assert scored[0]["p_base"] == pytest.approx(4 / 12)
    # 2021-02 sees 13 months: k = 12 touched too -> 5/13; its own outcome never enters its baseline
    assert scored[1]["p_base"] == pytest.approx(5 / 13)


def test_bootstrap_and_rules_on_a_known_difference():
    rows = []
    for k in range(40):
        y = k % 2
        rows.append({"month": f"m{k:02d}", "distance": 0.05, "side": "up", "horizon_days": 30.0, "y": y,
                     "p30": 0.9 if y else 0.1, "p90": 0.5, "p_base": 0.5})
    d = C.bootstrap_diff(rows, "p30", "p90", draws=200)
    assert d["point"] == pytest.approx(0.01 - 0.25)
    assert d["hi"] < 0
    s = C.summarise(rows, [])
    assert s["rules"]["R1_primary_window"] == 30
    assert s["rules"]["R2_method_is_a_basis_for_a_call"] is True
    assert s["pooled"]["disagreement_share"] == 1.0


def test_run_writes_aggregates_without_any_level(tmp_path):
    obs = flat_series(date(2023, 1, 1), date(2024, 12, 31), level=31_234.56)
    src = tmp_path / "CBBTCUSD.csv"
    src.write_text("observation_date,CBBTCUSD\n" + "".join(f"{d.isoformat()},{v:.2f}\n" for d, v in obs), encoding="utf-8")
    out = tmp_path / "calibration.json"
    assert C.run(src, out) == 0
    text = out.read_text(encoding="utf-8")
    s = json.loads(text)
    assert s["pooled"]["n"] == s["pooled"]["months"] * len(C.DISTANCES) * 2
    assert "31234" not in text and "31,234" not in text
    for v in (v for v in json.loads(text)["pooled"].values() if isinstance(v, float)):
        assert v <= 1.0
    assert s["rules"]["R1_primary_window"] in (30, 90)
