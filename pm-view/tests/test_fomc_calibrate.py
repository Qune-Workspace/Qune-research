"""fomc_calibrate.py on series built in memory: the reading reproduces the
2026-11-03 view's arithmetic, refuses a stale print, a meeting between the
reading and the decision and a 4-week bill that spans the meeting, the outcome
classes follow the target's change, the baselines never look ahead and start
after twelve earlier meetings, the rules fire on known differences, and the
written file holds aggregates only.  Nothing touches the network."""
import argparse
import json
from datetime import date, timedelta

import fomc_calibrate as F
import pandas as pd
import pytest


def daily(first: date, last: date, value) -> pd.Series:
    """A daily series (weekends included) with a constant or a callable value."""
    idx = pd.date_range(first, last, freq="D")
    vals = [value(d.date()) if callable(value) else value for d in idx]
    return pd.Series(vals, index=idx, dtype=float)


def constant_set(first=date(2026, 1, 1), last=date(2026, 12, 31), dtb3=3.99, dtb4wk=3.91, effr=3.88, upper=4.00):
    return {"DTB3": daily(first, last, dtb3), "DTB4WK": daily(first, last, dtb4wk),
            "EFFR": daily(first, last, effr), "DFEDTARU": daily(first, last, upper)}


def test_policy_content_forecast_and_clipping_follow_the_spec():
    assert F.policy_content(35) == pytest.approx(0.25 * 56 / 91)
    assert F.policy_content(50, bill_days=90) == pytest.approx(0.25 * 40 / 90)  # the view's 13.9 bp
    with pytest.raises(ValueError):
        F.policy_content(91)
    assert F.implied_steps(0.5, 0.15) == 1.0 and F.implied_steps(-0.5, 0.15) == -1.0
    f = F.forecast(0.52)
    assert f == pytest.approx({"hike": 0.52, "cut": 0.0, "none": 0.48})
    assert F.forecast(-0.3) == pytest.approx({"hike": 0.0, "cut": 0.3, "none": 0.7})


def test_reading_reproduces_the_view_arithmetic_at_the_primary_lag():
    s = constant_set()
    d = date(2026, 12, 9)
    r = F.reading(s, [d], d, F.PRIMARY_LAG_DAYS)
    assert r is not None and r["read_on"] == date(2026, 11, 4) and r["days_to_meeting"] == 35
    content = 0.25 * 56 / 91
    assert r["x_net"] == pytest.approx(0.08 / content)   # (11 - 3) bp over the content
    assert r["x_raw"] == pytest.approx(0.11 / content)   # the basis attributed to policy
    assert r["net"]["hike"] == pytest.approx(0.08 / content) and r["net"]["cut"] == 0.0


def test_reading_refuses_a_meeting_in_between_a_stale_print_and_a_spanning_basis_bill():
    s = constant_set()
    d = date(2026, 12, 9)
    assert F.reading(s, [date(2026, 11, 20), d], d, F.PRIMARY_LAG_DAYS) is None  # another decision in between
    stale = constant_set(last=date(2026, 10, 20))
    assert F.reading(stale, [d], d, F.PRIMARY_LAG_DAYS) is None                 # last print 15 days before R
    r7 = F.reading(s, [d], d, F.SECONDARY_LAG_DAYS)
    assert r7 is not None and r7["net"] is None and r7["raw"] is not None       # 4-week bill spans the meeting
    assert r7["x_raw"] == pytest.approx(0.11 / F.policy_content(7))


def test_outcome_classes_and_an_unknown_outcome():
    d = date(2026, 12, 9)
    step = lambda to: (lambda day: 4.00 if day <= d else to)  # noqa: E731
    first, last = date(2026, 11, 1), date(2026, 12, 31)
    assert F.outcome(daily(first, last, step(4.25)), d) == "hike"
    assert F.outcome(daily(first, last, step(3.75)), d) == "cut"
    assert F.outcome(daily(first, last, step(4.50)), d) == "hike"   # a 50 bp move scores as one step
    assert F.outcome(daily(first, last, 4.00), d) == "none"
    assert F.outcome(daily(first, d, 4.00), d) is None             # nothing observed after the meeting


def test_baselines_use_earlier_meetings_only_and_start_after_twelve():
    ys = ["none"] * 10 + ["hike"] * 6 + ["cut"] * 4
    rows = [{"meeting": date(2016, 1, 1) + timedelta(days=45 * i), "year": 2016 + i // 8, "y": y,
             "net": F.forecast(0.5), "raw": F.forecast(0.6)} for i, y in enumerate(ys)]
    scored = F.add_baselines(rows)
    assert len(scored) == len(ys) - F.MIN_BASELINE_MEETINGS
    first = scored[0]
    assert first["n_earlier"] == 12
    assert first["climatology"] == pytest.approx({"none": 10 / 12, "hike": 2 / 12, "cut": 0.0})
    assert first["persistence"] == {"hike": 1.0, "none": 0.0, "cut": 0.0}   # the previous meeting hiked
    last = scored[-1]
    assert last["climatology"]["cut"] == pytest.approx(3 / 19)             # the row's own outcome is not counted
    assert last["persistence"]["cut"] == 1.0


def test_brier_rules_and_bootstrap_on_known_differences():
    assert F.brier3({"hike": 1.0, "none": 0.0, "cut": 0.0}, "hike") == 0.0
    assert F.brier3({"hike": 1.0, "none": 0.0, "cut": 0.0}, "none") == 2.0
    assert F.brier3({"hike": 0.5, "none": 0.5, "cut": 0.0}, "hike") == pytest.approx(0.5)
    # perfect net, useless raw, over three years: net beats everything, raw does not
    rows = []
    for i in range(30):
        y = "hike" if i % 2 else "none"
        rows.append({"meeting": date(2017, 1, 1) + timedelta(days=45 * i), "year": 2017 + i // 10, "y": y,
                     "net": {"hike": 1.0 if y == "hike" else 0.0, "none": 1.0 if y == "none" else 0.0, "cut": 0.0},
                     "raw": {"hike": 0.0, "none": 0.0, "cut": 1.0},
                     "climatology": {"hike": 0.5, "none": 0.5, "cut": 0.0},
                     "persistence": {"hike": 1.0 if y == "none" else 0.0, "none": 1.0 if y == "hike" else 0.0, "cut": 0.0}})
    s = F.summarise(rows, [], None)
    assert s["pooled_brier"]["net"] == 0.0 and s["pooled_brier"]["raw"] == 2.0
    assert s["bootstrap"]["net_minus_climatology"]["hi"] < 0 and s["bootstrap"]["net_minus_raw"]["hi"] < 0
    assert s["rules"] == {"R1_primary": "net", "R2_basis_for_a_call": True, "R3_live_bin_sign": None,
                          "R3_observed_minus_predicted": None}
    # swap: raw perfect and net useless -> R1 moves the primary to raw, which then passes R2
    for r in rows:
        r["net"], r["raw"] = r["raw"], r["net"]
    s2 = F.summarise(rows, [], None)
    assert s2["rules"]["R1_primary"] == "raw" and s2["rules"]["R2_basis_for_a_call"] is True
    # a method inside the baselines' noise is not a basis for a call
    for r in rows:
        r["raw"] = dict(r["climatology"])
    s3 = F.summarise(rows, [], None)
    assert s3["rules"]["R1_primary"] == "raw" and s3["rules"]["R2_basis_for_a_call"] is False


def test_end_to_end_on_a_synthetic_history_writes_aggregates_only(tmp_path):
    """A decade of synthetic prints: the bill carries half a step before every
    hike and nothing otherwise; the target steps up at each hiking meeting."""
    meetings = F.meeting_dates()
    hikes = {m for i, m in enumerate(meetings) if i % 3 == 0 and m.year <= 2025}
    first, last = date(2015, 6, 1), date(2026, 11, 4)

    def upper(day):
        return 1.00 + 0.25 * sum(1 for m in hikes if day > m)

    def dtb3(day):
        nxt = min((m for m in meetings if m > day), default=None)
        return (upper(day) - 0.12) + (0.5 * F.policy_content(min((nxt - day).days, 90)) if nxt in hikes and nxt else 0.0)

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    series = {"DTB3": daily(first, last, dtb3), "DTB4WK": daily(first, last, lambda d: upper(d) - 0.10),
              "EFFR": daily(first, last, lambda d: upper(d) - 0.12), "DFEDTARU": daily(first, last, upper)}
    for k, s in series.items():
        lines = [f"observation_date,{k}"] + [f"{d.date()},{v:.2f}" for d, v in s.items()]
        (raw_dir / f"fred_{k}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = tmp_path / "cal.json"
    rc = F.run(raw_dir, tmp_path / "manifest.json", out, fetch=False)
    assert rc == 0
    s = json.loads(out.read_text(encoding="utf-8"))
    assert s["sample"]["scored_meetings"] >= F.MIN_SCORED
    assert set(s) >= {"spec", "sample", "pooled_brier", "bootstrap", "rules", "reliability", "live_bin", "limits"}
    assert "rows" not in s and s["inputs_manifest"] is None
    text = out.read_text(encoding="utf-8")
    for d, v in series["DTB3"].items():        # no date-value pair of any input series is written
        assert f"{d.date()},{v:.2f}" not in text and f'"{d.date()}": {v:.2f}' not in text
    # the synthetic bill is informative, so the reading should beat climatology here
    assert s["pooled_brier"]["net"] < s["pooled_brier"]["climatology"]
    # the live mode reads the same folder and the written calibration, prints, writes nothing
    before = sorted(p.name for p in tmp_path.iterdir())
    lines = F.live_lines(F.load_dir(raw_dir), meetings, date(2026, 12, 9), date(2026, 11, 4),
                         F.load_calibration(out), {"hike": 0.635, "none": 0.325})
    assert lines[0].startswith("FOMC 2026-12-09: prints as of 2026-11-04") and any("p_hike" in ln for ln in lines)
    assert any("calibration:" in ln for ln in lines)
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_live_verdict_order_gate_range_then_threshold():
    cal = {"rules": {"R1_primary": "net", "R2_basis_for_a_call": True},
           "live_bin": {"net": {"n": 4, "observed_minus_predicted": -0.32}, "raw": {"n": 7, "observed_minus_predicted": 0.08}}}
    gated = {**cal, "rules": {**cal["rules"], "R2_basis_for_a_call": False}}
    assert F.live_verdict(None, 0.6, 0.5, 0.7, 0.2).startswith("no call: no calibration")
    assert F.live_verdict(gated, 0.6, 0.5, 0.7, 0.2).startswith("no call: the reading does not beat")
    assert "inside the reading's range under the historical basis" in F.live_verdict(cal, 0.6, 0.5, 0.7, 0.6)
    assert "under 0.1" in F.live_verdict(cal, 0.6, 0.58, 0.62, 0.52)   # outside a narrow range, departure 0.08
    v = F.live_verdict(cal, 0.6, 0.5, 0.7, 0.3)
    assert v.startswith("call candidate: departure +0.300") and "on 4 meetings" in v
    assert "ledger: method=fomc_bills method_p=0.600 range_lo=0.500 range_hi=0.700" in v  # 2026-11-06: copied, not retyped
    assert "departure -0.100" in F.live_verdict(cal, 0.7, 0.5, 0.7, 0.8, "raw")
    # a point range (the day's basis exactly zero) must not pass a mid through: the range is the history's
    s = constant_set()
    assert F.basis_range(s["DTB4WK"], s["EFFR"], date(2026, 12, 31)) == pytest.approx((0.03, 0.03))
    assert F.basis_range(s["DTB4WK"], s["EFFR"], date(2026, 3, 1)) is None   # fewer than 252 observations
    wide = constant_set(dtb4wk=None)
    wide["DTB4WK"] = daily(date(2026, 1, 1), date(2026, 12, 31), lambda d: 3.88 + (0.08 if d.day % 2 else 0.0))
    lo, hi = F.basis_range(wide["DTB4WK"], wide["EFFR"], date(2026, 12, 31))
    assert lo == pytest.approx(0.0) and hi == pytest.approx(0.08)
    assert F.bin_frequency({"reliability": {"net": [{"bin": "0.9-1.0", "n": 19, "mean_p_hike": 0.99, "observed_hike": 0.79}]}},
                           "net", 0.993)["n"] == 19
    assert F.bin_frequency({"reliability": {"net": []}}, "net", 0.5) is None
    with pytest.raises(argparse.ArgumentTypeError):
        F.parse_mid("up=0.5")
    assert F.parse_mid("hike=0.635") == ("hike", 0.635)


def test_live_verdict_agrees_with_the_ledger_gate_on_a_grid():
    # 2026-11-06: the printer is advice; pm_lib.method_violations is the rule the committed ledger is held to.
    # On every grid point where the reading lies inside its range (the live range is the hull of both), the
    # printer says "call candidate" exactly when the gate is empty, under both states of R2 and with no file.
    import pm_lib as L
    cal = {"rules": {"R1_primary": "net", "R2_basis_for_a_call": True},
           "live_bin": {"net": {"n": 4, "observed_minus_predicted": -0.32}}}
    gated = {**cal, "rules": {**cal["rules"], "R2_basis_for_a_call": False}}
    grid = [x / 20 for x in range(1, 20)]
    checked = 0
    for file, r2 in ((cal, True), (gated, False), (None, None)):
        for lo in grid:
            for hi in grid:
                if hi < lo:
                    continue
                for p in (lo, (lo + hi) / 2, hi):
                    for mid in grid:
                        printed = F.live_verdict(file, p, lo, hi, mid).startswith("call candidate")
                        gate = L.method_violations("fomc_bills", p, lo, hi, mid, r2) == []
                        assert printed == gate, (r2, p, lo, hi, mid)
                        checked += 1
    assert checked > 10_000
