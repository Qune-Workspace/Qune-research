"""Tests for the tear-sheet module on constructed monthly returns."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest
from matplotlib import pyplot as plt

from qune_research import report, stats, style


def _monthly(n: int = 36, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2016-01-31", periods=n, freq="ME")
    cash = pd.Series(0.001, index=idx)
    strat = pd.Series(rng.normal(0.006, 0.02, n), index=idx)
    bench = pd.Series(rng.normal(0.004, 0.03, n), index=idx)
    other = pd.Series(rng.normal(0.002, 0.01, n), index=idx)
    return pd.DataFrame({"T1": strat, "B1": bench, "B2": other, "B0": cash})


def test_metrics_of_a_constant_series_are_exact():
    idx = pd.date_range("2020-01-31", periods=24, freq="ME")
    m = pd.DataFrame({"S": 0.01, "C": 0.0}, index=idx)
    met = report.metrics_table(m, ["S"], cash="C")
    assert met.loc["months", "S"] == 24
    assert met.loc["ann_return", "S"] == pytest.approx(1.01 ** 12 - 1.0)
    assert met.loc["ann_volatility", "S"] == 0.0
    assert math.isnan(met.loc["sharpe", "S"])          # no variance: no Sharpe ratio
    assert met.loc["max_drawdown", "S"] == 0.0
    assert met.loc["hit_rate", "S"] == 1.0
    assert met.loc["final_growth", "S"] == pytest.approx(1.01 ** 24)
    assert math.isnan(met.loc["skewness", "S"])


def test_metrics_use_the_library_functions_on_the_excess():
    m = _monthly()
    met = report.metrics_table(m, ["T1", "B1"], cash="B0")
    assert met.loc["sharpe", "T1"] == pytest.approx(stats.sharpe_annual(m["T1"] - m["B0"]))
    assert met.loc["ann_return", "B1"] == pytest.approx(stats.annualised_geometric_return(m["B1"]))
    assert met.loc["max_drawdown", "T1"] == pytest.approx(stats.max_drawdown(stats.total_return_index(m["T1"])))
    assert met.loc["worst_month", "T1"] == m["T1"].min()
    assert met.loc["best_month", "T1"] == m["T1"].max()
    assert met.loc["skewness", "T1"] == pytest.approx(stats.skewness(m["T1"]))
    # Without a cash column the Sharpe ratio is of the raw return.
    raw = report.metrics_table(m, ["T1"])
    assert raw.loc["sharpe", "T1"] == pytest.approx(stats.sharpe_annual(m["T1"]))


def test_calendar_years_compound_and_flag_partial_years():
    idx = pd.date_range("2019-11-30", periods=15, freq="ME")      # Nov-Dec 2019, all 2020, Jan 2021
    m = pd.DataFrame({"S": 0.01}, index=idx)
    cal = report.calendar_year_returns(m, ["S"])
    assert list(cal.index) == [2019, 2020, 2021]
    assert cal.loc[2019, "months"] == 2 and cal.loc[2020, "months"] == 12 and cal.loc[2021, "months"] == 1
    assert cal.loc[2020, "S"] == pytest.approx(1.01 ** 12 - 1.0)
    assert cal.loc[2021, "S"] == pytest.approx(0.01)


def test_difference_table_matches_newey_west_and_is_zero_against_itself():
    m = _monthly()
    d = report.difference_table(m, "T1", ["B1", "B2"], cash="B0")
    nw = stats.newey_west_mean(m["T1"] - m["B1"])
    assert d.loc["B1", "t_newey_west"] == pytest.approx(nw["t"])
    assert d.loc["B1", "mean_monthly_diff"] == pytest.approx(nw["mean"])
    assert d.loc["B1", "n"] == len(m)
    m2 = m.assign(SAME=m["T1"])
    d2 = report.difference_table(m2, "T1", ["SAME"], cash="B0")
    assert d2.loc["SAME", "mean_monthly_diff"] == 0.0
    assert d2.loc["SAME", "sharpe_gap"] == 0.0
    assert d2.loc["SAME", "ann_return_gap"] == 0.0


def test_validation_refuses_bad_input():
    m = _monthly()
    with pytest.raises(TypeError):
        report.metrics_table(m.reset_index(drop=True), ["T1"])
    with pytest.raises(ValueError):
        report.metrics_table(m.iloc[::-1], ["T1"])
    with pytest.raises(KeyError):
        report.metrics_table(m, ["T9"])
    gap = m.copy()
    gap.iloc[3, 0] = np.nan
    with pytest.raises(ValueError, match="missing"):
        report.metrics_table(gap, ["T1"])


def test_headline_is_built_from_the_table_and_follows_the_sign():
    m = _monthly()
    met = report.metrics_table(m, ["T1", "B1"], cash="B0")
    text = report.headline(met, "T1", "B1", {"T1": "Rule", "B1": "Buy and hold"})
    assert text.startswith("Rule ")
    minus = lambda s: s.replace("-", "−")  # noqa: E731
    assert minus(f"{met.loc['sharpe', 'T1']:.2f} to {met.loc['sharpe', 'B1']:.2f}") in text
    assert minus(f"{met.loc['ann_return', 'T1'] * 100:+.1f}% a year") in text
    assert minus(f"maximum drawdown {met.loc['max_drawdown', 'T1'] * 100:.1f}%") in text
    gap = float(met.loc["sharpe", "T1"] - met.loc["sharpe", "B1"])
    assert abs(gap) >= report.MATCHED_SHARPE_GAP, "the constructed data should give a clear gap"
    verb = "beat" if gap > 0 else "lagged"
    assert f" {verb} " in text
    # Reversed roles reverse the verb.
    rev = report.headline(met, "B1", "T1")
    other = "lagged" if verb == "beat" else "beat"
    assert f" {other} " in rev
    # No variance on either side: a plain statement of the returns, no verb of comparison.
    flat = met.copy()
    flat.loc["sharpe", "T1"] = float("nan")
    assert " returned " in report.headline(flat, "T1", "B1") and " beat " not in report.headline(flat, "T1", "B1")
    # A gap inside MATCHED_SHARPE_GAP is "matched", whichever side is ahead.
    close = met.copy()
    close.loc["sharpe", "T1"] = float(met.loc["sharpe", "B1"]) + report.MATCHED_SHARPE_GAP / 2.0
    assert " matched " in report.headline(close, "T1", "B1")
    close.loc["sharpe", "T1"] = float(met.loc["sharpe", "B1"]) - report.MATCHED_SHARPE_GAP / 2.0
    assert " matched " in report.headline(close, "T1", "B1")
    # The Newey-West t is quoted when given and absent otherwise; minus signs are typographic.
    assert "(Newey-West t −1.23)" in report.headline(met, "T1", "B1", t_stat=-1.23)
    assert "Newey-West" not in text
    assert "-" not in report.headline(met, "T1", "B1", t_stat=-1.23).replace("Newey-West", "")


def test_table_numbers_use_the_typographic_minus():
    assert report._fmt("ann_return", -0.0123) == "−1.2"
    assert report._fmt("sharpe", -0.26) == "−0.26"
    assert report._fmt("hit_rate", 0.5) == "50.0"
    assert "-" not in report._fmt("max_drawdown", -0.149)


def test_build_passes_the_decisive_t_into_the_headline():
    m = _monthly()
    sheet = report.build(m, "T1", ["B1", "B2"], cash="B0")
    t = float(sheet.differences.loc["B1", "t_newey_west"])
    assert f"(Newey-West t {t:.2f})".replace("t -", "t −") in sheet.headline


def test_source_line_wraps_inside_the_right_margin():
    style.apply()
    fig = plt.figure(figsize=(8.5, 10.5))
    long_note = "Post hoc, no decision weight; drawn from the committed result files. " * 3
    style.source(fig, "Alpaca and Tiingo daily IEF and BIL bars", "2019-01 to 2026-09", "Study 003", long_note)
    fig.canvas.draw()
    text = [t for t in fig.texts if t.get_gid() == style._SOURCE_TAG][0]
    assert "\n" in text.get_text()
    bbox = text.get_window_extent(fig.canvas.get_renderer())
    assert bbox.x1 <= 0.98 * fig.bbox.width
    plt.close(fig)


def test_build_draw_write_round_trip(tmp_path):
    m = _monthly()
    labels = {"T1": "Trend rule (T1)", "B1": "Buy and hold (B1)", "B2": "Half and half (B2)", "B0": "Cash (B0)"}
    sheet = report.build(m, "T1", ["B1", "B2"], cash="B0", labels=labels, inputs={"test": "0" * 64})
    assert sheet.period == "2016-01 to 2018-12"
    assert sheet.index.iloc[0].tolist() == [1.0, 1.0, 1.0]          # the sheet starts at one
    assert sheet.index.index[0] < m.index[0]
    assert (sheet.drawdown <= 0).all().all()
    assert sheet.headline == report.headline(sheet.metrics, "T1", "B1", labels,
                                             t_stat=float(sheet.differences.loc["B1", "t_newey_west"]))

    fig = report.draw(sheet, "constructed data", "Study 000")
    assert style.check(fig) == []
    paths = report.write(sheet, fig, tmp_path, "sheet")
    plt.close(fig)
    for p in paths.values():
        assert p.exists() and p.stat().st_size > 0
    doc = json.loads(paths["json"].read_text())
    assert doc["headline"] == sheet.headline
    assert doc["months"] == len(m)
    assert doc["metrics"]["sharpe"]["T1"] == pytest.approx(sheet.metrics.loc["sharpe", "T1"])
    assert doc["inputs"] == {"test": "0" * 64}
    met_back = pd.read_csv(paths["metrics"], index_col=0)
    assert met_back.loc["ann_return", "T1"] == pytest.approx(sheet.metrics.loc["ann_return", "T1"])
    # The title text on the figure is the headline.
    titles = [t.get_text() for t in fig.texts if t.get_gid() == style._TITLE_TAG]
    assert titles and sheet.headline.split(";")[0].split()[0] in titles[0]


def test_json_turns_nan_into_null():
    idx = pd.date_range("2020-01-31", periods=12, freq="ME")
    m = pd.DataFrame({"S": 0.01, "B": 0.005, "C": 0.0}, index=idx)
    sheet = report.build(m, "S", ["B"], cash="C")
    doc = sheet.to_dict()
    assert doc["metrics"]["sharpe"]["S"] is None
    json.dumps(doc)                                                  # no NaN leaks into the file


def test_write_twice_is_byte_identical_for_the_png(tmp_path):
    m = _monthly()
    sheet = report.build(m, "T1", ["B1"], cash="B0")
    fig = report.draw(sheet, "constructed data", "Study 000")
    first = report.write(sheet, fig, tmp_path, "a")
    plt.close(fig)
    fig2 = report.draw(sheet, "constructed data", "Study 000")
    second = report.write(sheet, fig2, tmp_path, "b")
    plt.close(fig2)
    assert first["png"].read_bytes() == second["png"].read_bytes()
    assert first["json"].read_text() == second["json"].read_text()
