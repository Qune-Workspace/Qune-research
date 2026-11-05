"""barrier.py on a series built in memory: the FRED csv parser, the Eastern-time
month window, the already-touched rule, the pre-specified windows, the fetch's
manifest (hashes and dates, never a value) and the printed report.  Every path
is passed by name; nothing touches the network."""
import json
import math
from datetime import UTC, date, datetime, timedelta

import barrier as B
import pm_lib as L
import pytest

NOW = datetime(2026, 11, 4, 12, 30, tzinfo=UTC)


def series(n: int, last: date = date(2026, 11, 3), start: float = 77_000.0, step: float = 0.01) -> list[tuple[date, float]]:
    """n daily closes ending on `last`, alternating +-step in log price so the volatility is known."""
    out = []
    x = math.log(start)
    for k in range(n):
        d = last - timedelta(days=n - 1 - k)
        out.append((d, math.exp(x)))
        x += step if k % 2 == 0 else -step
    return out


def csv_text(obs: list[tuple[date, float]], holes: set[date] = frozenset()) -> str:
    rows = ["observation_date,CBBTCUSD"]
    for d, v in obs:
        rows.append(f"{d.isoformat()},{'.' if d in holes else f'{v:.2f}'}")
    return "\n".join(rows) + "\n"


def test_parse_fred_csv_skips_the_header_and_missing_values_and_keeps_order():
    obs = series(5)
    rows = B.parse_fred_csv(csv_text(obs, holes={obs[2][0]}))
    assert [d for d, _ in rows] == [d for d, _ in obs if d != obs[2][0]]
    assert all(abs(v - round(w, 2)) < 1e-9 for (_, v), (_, w) in zip(rows, [o for o in obs if o[0] != obs[2][0]], strict=True))
    with pytest.raises(ValueError):
        B.parse_fred_csv("<html>not a csv</html>")


def test_month_window_is_the_eastern_time_month_and_ends_at_the_markets_end_date():
    start, end = B.month_window_utc(2026, 11)
    # 00:00 Eastern on 1 November 2026 is still daylight time (DST ends at 02:00 that day): 04:00Z.
    assert start == datetime(2026, 11, 1, 4, 0, tzinfo=UTC)
    # 00:00 Eastern on 1 December 2026 is standard time: 05:00Z, the markets' endDate 2026-12-01T05:00Z.
    assert end == datetime(2026, 12, 1, 5, 0, tzinfo=UTC)
    start, end = B.month_window_utc(2026, 12)
    assert end == datetime(2027, 1, 1, 5, 0, tzinfo=UTC)


def test_spot_time_is_17_pacific_on_the_observation_date():
    assert B.spot_time_utc(date(2026, 11, 3)) == datetime(2026, 11, 4, 1, 0, tzinfo=UTC)   # PST, UTC-8
    assert B.spot_time_utc(date(2026, 10, 15)) == datetime(2026, 10, 16, 0, 0, tzinfo=UTC)  # PDT, UTC-7


def test_already_touched_counts_closes_inside_the_month_only():
    start, end = B.month_window_utc(2026, 11)
    obs = [(date(2026, 10, 31), 81_000.0), (date(2026, 11, 1), 78_000.0), (date(2026, 11, 2), 80_000.0),
           (date(2026, 11, 3), 76_000.0)]
    assert B.already_touched(obs, 80_000.0, "up", start, end) == date(2026, 11, 2)   # at the level counts
    assert B.already_touched(obs, 82_000.0, "up", start, end) is None                 # October's close is outside
    assert B.already_touched(obs, 75_000.0, "down", start, end) is None
    assert B.already_touched(obs, 76_000.0, "down", start, end) == date(2026, 11, 3)


def test_assess_uses_the_pre_specified_windows_and_the_closed_form():
    obs = series(120)
    a = B.assess(obs, [(80_000.0, "up"), (75_000.0, "down")], 2026, 11, NOW)
    closes = [v for _, v in obs]
    assert a["primary_window"] == 30 and a["sensitivity_window"] == 90
    assert abs(a["sigma_primary"] - L.realised_vol(closes[-31:])) < 1e-12
    assert abs(a["sigma_sensitivity"] - L.realised_vol(closes[-91:])) < 1e-12
    spot_at = B.spot_time_utc(date(2026, 11, 3))
    end = datetime(2026, 12, 1, 5, 0, tzinfo=UTC)
    assert abs(a["horizon_days"] - (end - spot_at).total_seconds() / 86400) < 1e-9
    assert abs(a["lag_days"] - (NOW - spot_at).total_seconds() / 86400) < 1e-9 and a["stale"] is False
    spot = closes[-1]
    for r in a["barriers"]:
        assert r["touched_on"] is None
        assert abs(r["p_primary"] - L.touch_probability(spot, r["barrier"], a["sigma_primary"], a["horizon_days"])) < 1e-12
        assert abs(r["p_sensitivity"] - L.touch_probability(spot, r["barrier"], a["sigma_sensitivity"], a["horizon_days"])) < 1e-12
    assert a["spot_level"] == spot and a["spot_date"] == "2026-11-03"


def test_assess_marks_a_touched_barrier_and_flags_a_stale_spot_and_refuses_a_short_series():
    obs = series(40, last=date(2026, 10, 28)) + [(date(2026, 11, 1), 80_500.0), (date(2026, 11, 2), 79_000.0)]
    a = B.assess(obs, [(80_000.0, "up"), (75_000.0, "down")], 2026, 11, NOW)
    up, down = a["barriers"]
    assert up["touched_on"] == "2026-11-01" and up["p_primary"] == 1.0
    assert down["touched_on"] is None and 0.0 < down["p_primary"] < 1.0
    assert a["sigma_sensitivity"] is None and down["p_sensitivity"] is None  # fewer than 91 observations
    a = B.assess(obs, [(80_000.0, "up")], 2026, 11, NOW + timedelta(days=6))
    assert a["stale"] is True
    with pytest.raises(ValueError):
        B.assess(series(30), [(80_000.0, "up")], 2026, 11, NOW)
    with pytest.raises(ValueError):
        B.assess(series(40), [(80_000.0, "sideways")], 2026, 11, NOW)
    with pytest.raises(ValueError):
        B.assess(series(40, last=date(2026, 12, 1)), [(80_000.0, "up")], 2026, 11, NOW)


def test_fetch_keeps_the_download_git_ignored_and_the_manifest_carries_no_value(tmp_path):
    obs = series(40)
    body = csv_text(obs).encode()
    raw, manifest = tmp_path / "raw", tmp_path / "fred_manifest.json"
    rows, entry = B.fetch_series(lambda url: body, raw, manifest, NOW, dry_run=False)
    assert len(rows) == 40 and entry["rows"] == 40 and entry["bytes"] == len(body)
    assert entry["first_obs"] == obs[0][0].isoformat() and entry["last_obs"] == "2026-11-03"
    assert (raw / "2026-11-04T123000Z" / "CBBTCUSD.csv").read_bytes() == body
    text = manifest.read_text()
    entries = json.loads(text)
    assert entries[0]["sha256"] == B.sha256(body) and entries[0]["citation"] == B.CITATION
    # tools/check_data_terms.py markers for the derived FRED series, and no close in the file:
    assert "observation_date" not in text and "DATE," not in text and '"series_id"' not in text
    assert not any(f"{v:.2f}" in text for _, v in obs)
    rows2, _ = B.fetch_series(lambda url: body, raw, manifest, NOW + timedelta(hours=1), dry_run=True)
    assert len(json.loads(manifest.read_text())) == 1 and len(list(raw.iterdir())) == 1  # dry run wrote nothing


def test_run_prints_the_figures_and_withholds_the_level_unless_asked(tmp_path, capsys):
    obs = series(120)
    body = csv_text(obs).encode()
    rc = B.run("2026-11", [(80_000.0, "up"), (75_000.0, "down")], {80_000.0: 0.765}, lambda url: body, None,
               tmp_path / "raw", tmp_path / "m.json", dry_run=True, show_level=False, now=lambda: NOW)
    out = capsys.readouterr().out
    assert rc == 0
    assert "dry run: nothing written" in out and not (tmp_path / "m.json").exists()
    assert "level withheld" in out and f"{obs[-1][1]:,.2f}" not in out
    assert "primary 30 obs" in out and "sensitivity 90 obs" in out
    assert "barrier 80,000 up: P(touch) primary" in out and "market mid 0.765, departure" in out
    assert "barrier 75,000 down: P(touch) primary" in out and "departure" not in out.split("75,000 down")[1].split("\n")[0]
    assert "net sign of its error against the market's rule is not known" in out and B.CITATION in out
    assert "calibration: none read" in out and "R2 gate is not applied" in out
    rc = B.run("2026-11", [(80_000.0, "up")], {}, None, tmp_path / "kept.csv", tmp_path / "raw", tmp_path / "m.json",
               dry_run=False, show_level=True, now=lambda: NOW) if (tmp_path / "kept.csv").write_bytes(body) else 1
    out = capsys.readouterr().out
    assert rc == 0 and "read from kept.csv" in out and f"level {obs[-1][1]:,.2f}" in out
    assert not (tmp_path / "m.json").exists()  # --from-file fetches and writes nothing


def calibration(r2: bool) -> dict:
    return {"rules": {"R1_primary_window": 30, "R2_method_is_a_basis_for_a_call": r2,
                      "R3_mid_bins": {"n": 638, "observed_minus_predicted": -0.108}},
            "pooled": {"months": 126, "first_month": "2016-05", "last_month": "2026-10",
                       "brier30": 0.2171, "brier90": 0.2170, "brier_base": 0.2147},
            "per_barrier": [{"distance": 0.025, "side": "up", "n": 126, "touch_rate": 0.825},
                            {"distance": 0.05, "side": "up", "n": 126, "touch_rate": 0.698},
                            {"distance": 0.025, "side": "down", "n": 126, "touch_rate": 0.690}]}


def test_calibration_gate_decides_first_and_the_climatology_is_printed_beside_each_barrier(tmp_path, capsys):
    # R2 false: every verdict is "no call", whatever the departure; R2 true: the old order applies.
    assert B.departure_verdict(0.80, 0.85, 0.65, calibration(False)).startswith("no call: the method does not beat")
    assert B.departure_verdict(0.80, 0.85, 0.65, calibration(True)).startswith("at or over the 0.10 threshold")
    cal_path = tmp_path / "calibration.json"
    cal_path.write_text(json.dumps(calibration(False)), encoding="utf-8")
    obs = series(120)
    (tmp_path / "kept.csv").write_bytes(csv_text(obs).encode())
    rc = B.run("2026-11", [(80_000.0, "up"), (75_000.0, "down")], {80_000.0: 0.65, 75_000.0: 0.60}, None,
               tmp_path / "kept.csv", tmp_path / "raw", tmp_path / "m.json", dry_run=True, show_level=False,
               now=lambda: NOW, calibration=cal_path)
    out = capsys.readouterr().out
    assert rc == 0
    up_line = out.split("80,000 up")[1].split("\n")[0]
    assert "climatology at distance 0.025 up: touch rate 0.825 over 126 months" in up_line  # the nearest distance
    assert "no call: the method does not beat its climatological baseline" in up_line
    down_line = out.split("75,000 down")[1].split("\n")[0]
    assert "climatology at distance 0.025 down: touch rate 0.690" in down_line
    assert "calibration (calibrate.py, 126 months 2016-05..2026-10): Brier primary 0.2171 vs climatology 0.2147; R2 does NOT beat" in out
    assert "R3 observed - predicted in the 0.5-0.9 bins -0.108" in out
    (tmp_path / "bad.json").write_text("{}", encoding="utf-8")
    rc = B.run("2026-11", [(80_000.0, "up")], {}, None, tmp_path / "kept.csv", tmp_path / "raw", tmp_path / "m.json",
               dry_run=True, show_level=False, now=lambda: NOW, calibration=tmp_path / "bad.json")
    assert rc == 1 and "FAILED bad.json is not a calibrate.py output" in capsys.readouterr().out


def test_departure_verdict_refuses_the_bias_direction_and_a_covered_market_before_the_threshold():
    # Below the market: the direction of the one-minute gap the method cannot see, never a call, whatever the size.
    assert B.departure_verdict(0.607, 0.705, 0.805).startswith("no call: the reading is below the market")
    assert B.departure_verdict(0.60, 0.70, 0.60).startswith("no call: the reading is below the market")  # equal counts
    # Above the market but the market sits between the two windows' readings: covered, never a call.
    assert B.departure_verdict(0.80, 0.60, 0.65).startswith("no call: the market lies inside")
    assert B.departure_verdict(0.80, 0.60, 0.60).startswith("no call: the market lies inside")  # the edge counts
    # Above the market, outside the range: the threshold decides.
    assert B.departure_verdict(0.737, 0.805, 0.645) == "under the 0.10 threshold: nothing to add"
    assert B.departure_verdict(0.80, 0.85, 0.65).startswith("at or over the 0.10 threshold, against the bias")
    assert B.departure_verdict(0.80, None, 0.65).startswith("at or over the 0.10 threshold")  # no sensitivity: no range test


def test_run_reports_a_failed_fetch_and_a_short_series_as_a_refusal(tmp_path, capsys):
    def boom(url: str) -> bytes:
        raise OSError("no route")
    rc = B.run("2026-11", [(80_000.0, "up")], {}, boom, None, tmp_path / "raw", tmp_path / "m.json",
               dry_run=False, show_level=False, now=lambda: NOW)
    assert rc == 1 and "FAILED no route" in capsys.readouterr().out
    short = csv_text(series(10)).encode()
    rc = B.run("2026-11", [(80_000.0, "up")], {}, lambda url: short, None, tmp_path / "raw", tmp_path / "m.json",
               dry_run=True, show_level=False, now=lambda: NOW)
    assert rc == 1 and "primary window needs 31" in capsys.readouterr().out
    assert not (tmp_path / "m.json").exists()
