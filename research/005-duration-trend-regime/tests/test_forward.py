"""§11 forward record: the decision record against the engine's own frames,
no look-ahead, the gates, the shadow line against the frozen engine, the
append rules, interim figures and the single scoring.  Toy data only."""
import json

import numpy as np
import pandas as pd
import pytest

from src import forward, pipeline, report, switching
from src.cash import cash_index
from src.conditional import conditional_targets
from src.config import CASH_LEG, COST_CASES, DURATION_LEG
from tests.toy import toy_bars, toy_closes, toy_cpi, toy_dtb3


@pytest.fixture(scope="module")
def world():
    bars = toy_bars("2000-01-03", "2007-12-31")
    closes = toy_closes(bars)
    bil = (100.0 * cash_index(toy_dtb3()).reindex(bars, method="ffill")).dropna().rename("close")
    closes = {DURATION_LEG: closes["IEF"].rename("close"), "SPY": closes["SPY"].rename("close"), CASH_LEG: bil}
    cpi = toy_cpi()
    indices = pipeline.etf_indices(closes)
    window_bars = pipeline.window_bars(indices, etf_cash=True)
    schedule, month_ends = pipeline.window_schedule(window_bars, "2001-06", "2007-11")
    trend = pipeline.trend_frame(indices, month_ends, schedule)
    regimes = report.regime_frames(closes["SPY"], closes[DURATION_LEG], cpi, schedule)
    return dict(closes=closes, cpi=cpi, indices=indices, schedule=schedule, trend=trend, regimes=regimes)


def _record(world, month: str, holding_before=None):
    t = world["schedule"].loc[pd.Period(month, "M"), "signal_date"]
    return forward.decision_record(world["closes"], world["cpi"], t, holding_before or {}, run_at_utc="2007-01-01T00:00:00Z")


def test_record_matches_the_engine_frames(world):
    for month in ("2004-03", "2005-11", "2006-06", "2007-10"):
        period = pd.Period(month, "M")
        record = _record(world, month)
        assert record["status"] == "ok", record
        assert record["execution_date"] == str(world["schedule"].loc[period, "execution_date"].date())
        assert record["trend"]["mom"] == pytest.approx(world["trend"].loc[period, "value"], abs=1e-12)
        assert record["targets"]["B2"] == world["trend"].loc[period, "target"]
        for trial in ("T1", "T2"):
            assert record["regimes"][trial]["rho"] == pytest.approx(world["regimes"][trial].loc[period, "rho"], abs=1e-12)
            assert record["regimes"][trial]["positive"] == bool(world["regimes"][trial].loc[period, "positive"])
        t3 = world["regimes"]["T3"].loc[period]
        assert record["regimes"]["T3"]["cpi_12m_change"] == pytest.approx(t3["cpi_12m_change"], abs=1e-12)
        assert record["regimes"]["T3"]["cpi_month"] == t3["cpi_month"]
        expected_t1 = conditional_targets(world["trend"]["target"].loc[[period]],
                                          world["regimes"]["T1"]["positive"].loc[[period]]).iloc[0]
        assert record["targets"]["T1"] == expected_t1
        assert record["paper_order"] is False and record["orders"] == []


def test_record_uses_nothing_after_the_signal_date(world):
    t = world["schedule"].loc[pd.Period("2005-08", "M"), "signal_date"]
    truncated = {k: v.loc[v.index <= t] for k, v in world["closes"].items()}
    cpi_truncated = world["cpi"].loc[world["cpi"].index <= pd.Period("2005-08", "M")]
    full = forward.decision_record(world["closes"], world["cpi"], t, {}, run_at_utc="x")
    cut = forward.decision_record(truncated, cpi_truncated, t, {}, run_at_utc="x")
    assert full == cut


def test_record_refuses_non_month_end_and_missing_bar(world):
    schedule = world["schedule"]
    t = schedule.loc[pd.Period("2006-03", "M"), "signal_date"]
    mid = world["closes"][DURATION_LEG].index[world["closes"][DURATION_LEG].index.get_loc(t) - 5]
    off = forward.decision_record(world["closes"], world["cpi"], mid, {}, run_at_utc="x")
    assert off["status"] == "signal unavailable" and "not the last NYSE trading day" in off["notes"]
    assert off["targets"] is None and off["execution_date"] is None
    without_spy = dict(world["closes"], SPY=world["closes"]["SPY"].drop(t))
    missing = forward.decision_record(without_spy, world["cpi"], t, {}, run_at_utc="x")
    assert missing["status"] == "signal unavailable" and missing["notes"].startswith("no SPY bar")
    short = {k: v.loc[v.index >= t - pd.Timedelta(days=200)] for k, v in world["closes"].items()}
    lookback = forward.decision_record(short, world["cpi"], t, {}, run_at_utc="x")
    assert lookback["status"] == "signal unavailable" and "lookback" in lookback["notes"]


def test_record_without_cpi_marks_t3_unavailable(world):
    t = world["schedule"].loc[pd.Period("2006-03", "M"), "signal_date"]
    record = forward.decision_record(world["closes"], None, t, {}, run_at_utc="x")
    assert record["status"] == "ok" and record["targets"]["T3"] is None
    assert record["regimes"]["T3"]["status"].startswith("not available")


def test_switch_flags_against_holding_before(world):
    record = _record(world, "2006-06")
    other = {name: (CASH_LEG if target == DURATION_LEG else DURATION_LEG) for name, target in record["targets"].items()}
    same = _record(world, "2006-06", holding_before=dict(record["targets"]))
    flipped = _record(world, "2006-06", holding_before=other)
    assert all(v is False for v in same["switch"].values())
    assert all(v is True for v in flipped["switch"].values())
    assert all(v is None for v in record["switch"].values())            # no holding known: no switch flag


def test_write_record_never_overwrites(world, tmp_path):
    record = _record(world, "2006-06")
    path = forward.write_record(record, tmp_path)
    assert json.loads(path.read_text())["signal_date"] == record["signal_date"]
    with pytest.raises(FileExistsError):
        forward.write_record(record, tmp_path)


def test_gates():
    assert forward.refusal("2026-09-30", "2026-09-30T23:00:00Z") is not None        # before the first forward month
    assert "before the first forward signal date" in forward.refusal("2026-10-29", "2026-10-29T23:00:00Z")
    assert "before 21:15 UTC" in forward.refusal("2026-10-30", "2026-10-30T20:00:00Z")
    assert "before 21:15 UTC" in forward.refusal("2026-10-30", "2026-10-30T21:14:59Z")
    assert forward.refusal("2026-10-30", "2026-10-30T21:15:00Z") is None
    assert forward.refusal("2026-10-30", "2026-11-02T09:00:00Z") is None
    assert forward.refusal("2026-11-30", "2026-11-30T21:00:00Z") is not None        # EST: 16:00 New York = 21:00 UTC


def test_shadow_line_matches_the_frozen_engine(world):
    schedule, indices = world["schedule"], world["indices"]
    for month, holding_b2 in (("2005-02", CASH_LEG), ("2005-02", DURATION_LEG), ("2006-09", CASH_LEG)):
        period = pd.Period(month, "M")
        previous = _record(world, month, holding_before={"B2": holding_b2, "T1": holding_b2, "T2": DURATION_LEG,
                                                         "T3": CASH_LEG})
        current = _record(world, str(period + 1))
        line = forward.shadow_line(world["closes"], previous, current, cost_per_side=COST_CASES["base"])
        returns = switching.instrument_returns(indices, schedule).loc[[period]]
        assert line["r_IEF"] == pytest.approx(returns.at[period, DURATION_LEG], abs=1e-12)
        assert line["r_BIL"] == pytest.approx(returns.at[period, CASH_LEG], abs=1e-12)
        assert line["B1"] == line["r_IEF"]
        for name, start in (("B2", holding_b2), ("T1", holding_b2), ("T2", DURATION_LEG), ("T3", CASH_LEG)):
            engine = switching.run_switching(pd.Series([previous["targets"][name]], index=[period]), returns,
                                             COST_CASES["base"], initial_holding=start)
            assert line[name] == pytest.approx(engine.at[period, "r"], abs=1e-12), name
            assert line[f"{name}_switched"] == bool(engine.at[period, "switched"])
            assert line[f"{name}_holding"] == engine.at[period, "holding"]
        assert line["d"] == pytest.approx(line["B2"] - line["B1"], abs=1e-15)
        assert line["positive_T1"] == previous["regimes"]["T1"]["positive"]
        assert line["period_end"] == current["execution_date"] and line["execution_date"] == previous["execution_date"]
        assert line["days_slipped_start"] == 0 and line["days_slipped_end"] == 0
        assert list(line) == forward.SHADOW_COLUMNS


def test_shadow_line_refuses_before_the_period_end_bar(world):
    previous, current = _record(world, "2007-09"), _record(world, "2007-10")
    end = pd.Timestamp(current["execution_date"])
    early = {k: v.loc[v.index < end] for k, v in world["closes"].items()}
    with pytest.raises(ValueError, match="never before"):
        forward.shadow_line(early, previous, current)
    with pytest.raises(ValueError, match="must follow"):
        forward.shadow_line(world["closes"], current, previous)


def test_append_shadow_order_and_duplicates(world, tmp_path):
    path = tmp_path / "shadow.csv"
    records = [_record(world, m, holding_before={"B2": CASH_LEG, "T1": CASH_LEG, "T2": CASH_LEG, "T3": CASH_LEG})
               for m in ("2006-01", "2006-02", "2006-03", "2006-04")]
    first = forward.shadow_line(world["closes"], records[0], records[1], run_at_utc="x")
    forward.append_shadow(first, path)
    with pytest.raises(FileExistsError):
        forward.append_shadow(first, path)
    skipped = forward.shadow_line(world["closes"], records[2], records[3], run_at_utc="x")
    with pytest.raises(ValueError, match="does not follow"):
        forward.append_shadow(skipped, path)
    second = forward.shadow_line(world["closes"], records[1], records[2], run_at_utc="x")
    forward.append_shadow(second, path)
    frame = forward.read_shadow(path)
    assert len(frame) == 2 and list(frame.columns) == forward.SHADOW_COLUMNS
    assert frame["d"].to_numpy() == pytest.approx([first["d"], second["d"]], abs=1e-12)


def _synthetic_shadow(n: int, seed: int = 7, delta: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    positive = rng.random(n) < 0.4
    d = rng.normal(0.0, 0.007, n) + np.where(positive, delta, 0.0)
    months = pd.period_range("2026-10", periods=n + 1, freq="M")
    return pd.DataFrame({"signal_date": [str(m.to_timestamp(how="end").date()) for m in months[:-1]],
                         "execution_date": [str((m + 1).to_timestamp().date()) for m in months[:-1]],
                         "period_end": [str((m + 1).to_timestamp().date()) for m in months[1:]],
                         "B1": d * 0 + 0.001, "B2": d + 0.001, "T1": np.where(positive, d + 0.001, 0.001),
                         "T2": np.nan, "T3": np.nan, "d": d, "positive_T1": positive})


def test_interim_before_and_after_the_rule_fires():
    empty = forward.interim(forward.read_shadow("/nonexistent/shadow.csv"), "x")
    assert empty["heading"] == forward.NOT_YET_SCORED and empty["holding_periods"] == 0 and empty["stopping_month"] is None
    short = _synthetic_shadow(10)
    figures = forward.interim(short, "x")
    assert figures["holding_periods"] == 10 and figures["stopping_month"] is None
    assert figures["n_pos_T1"] + figures["n_neg_T1"] == 10
    pos = short["positive_T1"].to_numpy()
    assert figures["delta_so_far"] == pytest.approx(short["d"][pos].mean() - short["d"][~pos].mean())
    assert figures["cumulative"]["B1"] == pytest.approx(1.001 ** 10 - 1)
    assert figures["cumulative"]["T2"] is None
    assert "verdict" not in figures
    with pytest.raises(RuntimeError, match="not fired"):
        forward.score(short)


def test_score_once_the_rule_fires():
    long = _synthetic_shadow(70)
    fired = forward.stopping_month(long["positive_T1"].to_numpy())
    assert fired is not None and fired <= 60
    result = forward.score(long)
    assert result["scored_periods"] == fired
    assert result["verdict"] in (forward.VERDICT_SUPPORTED, forward.VERDICT_REFUTED, forward.VERDICT_INCONCLUSIVE)
    assert result["edge"]["n"] == fired and result["in_sample_row"] == "refuted in-sample"
    strong = forward.score(_synthetic_shadow(70, delta=0.02))
    assert strong["verdict"] == forward.VERDICT_SUPPORTED and strong["conflict"] is None
    assert forward.score(_synthetic_shadow(70, delta=-0.02))["verdict"] == forward.VERDICT_REFUTED


def test_previous_targets_from_episode_then_records(world, tmp_path):
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({"terminal_trend_target": CASH_LEG,
                                   "terminal_regime": {"T1": {"signal_date": "2026-09-30", "positive": True},
                                                       "T2": {"signal_date": "2026-09-30", "positive": False},
                                                       "T3": {"signal_date": "2026-09-30", "positive": True}}}))
    decisions = tmp_path / "decisions"
    targets, source = forward.previous_targets(decisions, summary, before="2026-10-30")
    assert targets == {"B2": CASH_LEG, "T1": CASH_LEG, "T2": DURATION_LEG, "T3": CASH_LEG}
    assert source.startswith("episode terminal targets")
    forward.write_record(dict(_record(world, "2006-06"), signal_date="2026-10-30"), decisions)
    forward.write_record(dict(_record(world, "2006-07"), signal_date="2026-11-30"), decisions)
    later, source = forward.previous_targets(decisions, summary, before="2026-12-31")
    assert source == "decision record 2026-11-30" and later == _record(world, "2006-07")["targets"]
    earlier, source = forward.previous_targets(decisions, summary, before="2026-11-30")
    assert source == "decision record 2026-10-30"


def test_cli_refuses_before_the_first_forward_date(capsys):
    assert forward.main(["decide", "--signal-date", "2026-09-30", "--dry-run"]) == 1
    assert "before the first forward signal date" in capsys.readouterr().out
