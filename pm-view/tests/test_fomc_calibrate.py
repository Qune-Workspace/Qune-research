"""fomc_calibrate.py on series built in memory: the reading reproduces the
2026-11-03 view's arithmetic, refuses a stale print, a meeting between the
reading and the decision and a 4-week bill that spans the meeting, the outcome
classes follow the target's change, the baselines never look ahead and start
after twelve earlier meetings, the rules fire on known differences, and the
written file holds aggregates only.  Nothing touches the network."""
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
