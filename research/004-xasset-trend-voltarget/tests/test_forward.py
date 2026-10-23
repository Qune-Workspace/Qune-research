"""§11 forward record on constructed series (no raw file, no network): the
decision record against the run module's own signal table and weights, no
look-ahead, the gates, the carried weight of a missing bar, the shadow line
and the books against the frozen engine, the append rules, the terminal
position as the first holding."""
import json

import numpy as np
import pandas as pd
import pytest

from qune_research import engine
from qune_research.dates import month_end_signal_dates, schedule
from src import forward, run
from src.config import CASH_ETF

COSTS = {"AAA": 2.0, "BBB": 2.5, "CCC": 3.0}   # bp, constructed symbols only
UNIVERSE = ["AAA", "BBB", "CCC"]
K = 0.8


def _world(seed: int = 3):
    days = pd.bdate_range("2010-01-04", "2013-12-31")
    rng = np.random.default_rng(seed)
    cols = {}
    for i, a in enumerate(UNIVERSE):
        r = rng.normal(0.0003, 0.008 + 0.004 * i, len(days))
        cols[a] = pd.Series(np.cumprod(1 + r), index=days)
    cols["BBB"].iloc[:300] = np.nan                       # BBB lists later: staggered entry (§8.1)
    prices = pd.DataFrame(cols)
    cash = pd.Series(np.cumprod(1 + np.full(len(days), 0.00005)), index=days)
    spy = pd.Series(np.cumprod(1 + rng.normal(0.0004, 0.01, len(days))), index=days)
    closes = {a: prices[a] for a in UNIVERSE}
    closes[CASH_ETF], closes["SPY"] = cash, spy
    sched = schedule(days, month_end_signal_dates(days, "2011-01-31", "2013-11-30"))
    table = run.signal_table(prices, cash, UNIVERSE, pd.DatetimeIndex(sched["signal_date"]))
    return dict(days=days, prices=prices, cash=cash, closes=closes, sched=sched, table=table)


@pytest.fixture(scope="module")
def world():
    return _world()


def _record(world, signal_date, holding_before=None):
    return forward.decision_record(world["closes"], signal_date, UNIVERSE, K, holding_before or {},
                                   run_at_utc="2013-01-01T00:00:00Z", trading_days=world["days"])


def test_record_matches_the_run_module(world):
    table, sched = world["table"], world["sched"]
    t1 = run.weights_from(run.trial_signal(table, "T1"), table["vol"])
    ones = table["present"].astype(float).where(table["present"])
    b3 = run.weights_from(ones, table["vol"])
    for t in sched["signal_date"].iloc[[0, 5, 14, 30, -1]]:
        record = _record(world, t)
        assert record["status"].startswith("ok"), record
        assert record["execution_date"] == str(sched.set_index("signal_date").loc[t, "execution_date"].date())
        for a in UNIVERSE:
            present = bool(table["present"].at[t, a])
            if present:
                assert record["assets"][a]["s12"] == table["s12"].at[t, a]
                assert record["assets"][a]["vol63_annualised"] == pytest.approx(table["vol"].at[t, a], abs=1e-12)
            else:
                assert record["assets"][a]["status"] == "signal unavailable" and a in record["carried"]
            assert record["targets"]["T1"][a] == pytest.approx(t1[t].get(a, 0.0), abs=1e-12)
            assert record["targets"]["B3"][a] == pytest.approx(b3[t].get(a, 0.0), abs=1e-12)
            assert record["targets"]["B4"][a] == pytest.approx(K * b3[t].get(a, 0.0), abs=1e-12)
        assert record["paper_order"] is False and record["orders"] == []
        assert record["gross_exposure"]["T1"] <= 1.0 + 1e-12


def test_record_uses_nothing_after_the_signal_date(world):
    t = world["sched"]["signal_date"].iloc[20]
    truncated = {k: v.loc[v.index <= t] for k, v in world["closes"].items()}
    full = forward.decision_record(world["closes"], t, UNIVERSE, K, {}, run_at_utc="x", trading_days=world["days"])
    cut = forward.decision_record(truncated, t, UNIVERSE, K, {}, run_at_utc="x", trading_days=world["days"])
    assert full == cut


def test_record_refuses_non_month_end_and_missing_cash_bar(world):
    t = world["sched"]["signal_date"].iloc[20]
    mid = world["days"][world["days"].get_loc(t) - 5]
    off = _record(world, mid)
    assert off["status"] == "signal unavailable" and "not the last NYSE trading day" in off["notes"]
    assert off["targets"] is None and off["execution_date"] is None
    without_cash = dict(world["closes"], **{CASH_ETF: world["closes"][CASH_ETF].drop(t)})
    missing = forward.decision_record(without_cash, t, UNIVERSE, K, {}, run_at_utc="x", trading_days=world["days"])
    assert missing["status"] == "signal unavailable" and missing["notes"].startswith(f"no {CASH_ETF} bar")


def test_missing_asset_bar_carries_the_previous_weight(world):
    t = world["sched"]["signal_date"].iloc[25]
    before = _record(world, t)["targets"]
    holding = {name: dict(before[name], CCC=0.1234) for name in forward.STRATEGY_IDS}
    without_ccc = dict(world["closes"], CCC=world["closes"]["CCC"].drop(t))
    record = forward.decision_record(without_ccc, t, UNIVERSE, K, holding, run_at_utc="x", trading_days=world["days"])
    assert record["status"] == "ok, weights carried for: CCC" and record["carried"] == ["CCC"]
    assert record["assets"]["CCC"]["status"] == "signal unavailable"
    for name in forward.STRATEGY_IDS:
        assert record["targets"][name]["CCC"] == pytest.approx(0.1234)
        assert sum(record["targets"][name].values()) <= 1.0 + 1e-12
    assert record["n_assets_signalled"] == 2


def test_write_record_never_overwrites(world, tmp_path):
    record = _record(world, world["sched"]["signal_date"].iloc[3])
    path = forward.write_record(record, tmp_path)
    assert json.loads(path.read_text())["signal_date"] == record["signal_date"]
    with pytest.raises(FileExistsError):
        forward.write_record(record, tmp_path)


def test_gates():
    assert forward.refusal("2026-09-30", "2026-09-30T23:00:00Z") is not None        # the held-back window
    assert "before the first forward signal date" in forward.refusal("2026-10-29", "2026-10-29T23:00:00Z")
    assert "before 21:15 UTC" in forward.refusal("2026-10-30", "2026-10-30T20:00:00Z")
    assert "before 21:15 UTC" in forward.refusal("2026-10-30", "2026-10-30T21:14:59Z")
    assert forward.refusal("2026-10-30", "2026-10-30T21:15:00Z") is None
    assert forward.refusal("2026-10-30", "2026-11-02T09:00:00Z") is None
    assert forward.refusal("2026-11-30", "2026-11-30T21:00:00Z") is not None        # EST: 16:00 New York = 21:00 UTC


def _lines(world, months: slice, holding_first=None):
    """Decision records for consecutive signal dates and the shadow lines between them."""
    dates = list(world["sched"]["signal_date"].iloc[months])
    records = [_record(world, dates[0], holding_first)]
    for t in dates[1:]:
        records.append(_record(world, t, records[-1]["targets"]))
    books = forward.initial_books(UNIVERSE)
    lines = []
    for previous, current in zip(records[:-1], records[1:]):
        line, books = forward.shadow_line(world["closes"], previous, current, books, run_at_utc="x", cost_bp=COSTS)
        lines.append(line)
    return records, lines, books


def test_shadow_lines_and_books_match_the_frozen_engine(world):
    records, lines, books = _lines(world, slice(10, 19))
    sub = world["sched"].iloc[10:19].reset_index(drop=True)
    costs = run.costs_for(UNIVERSE, 1.0, COSTS)
    for name in forward.STRATEGY_IDS:
        weights = {pd.Timestamp(r["signal_date"]): r["targets"][name] for r in records}
        frame = engine.run(world["prices"], world["cash"], sub, weights, costs)
        assert len(frame) == len(lines) == 8
        for line, (t, row) in zip(lines, frame.iterrows()):
            assert line["signal_date"] == str(t.date())
            assert line[f"{name}_net"] == pytest.approx(row["net"], abs=1e-14)
            assert line[f"{name}_cost"] == pytest.approx(row["cost"], abs=1e-14)
            assert line[f"{name}_turnover"] == pytest.approx(row["turnover"], abs=1e-14)
            assert line[f"{name}_gross_exposure"] == pytest.approx(row["gross_exposure"], abs=1e-14)
        assert lines[-1][f"{name}_book"] == pytest.approx(10_000.0 * float(np.prod(1.0 + frame["net"])), rel=1e-12)
    assert books["period_end"] == records[-1]["execution_date"]
    assert all(line["days_slipped_start"] == 0 and line["days_slipped_end"] == 0 for line in lines)
    assert list(lines[0]) == forward.SHADOW_COLUMNS
    assert lines[0]["r_BIL"] == pytest.approx(
        world["cash"].loc[pd.Timestamp(lines[0]["period_end_bar"])] / world["cash"].loc[pd.Timestamp(lines[0]["period_start_bar"])] - 1.0)


def test_shadow_line_refuses_before_the_end_bar_and_out_of_order(world):
    records, lines, books = _lines(world, slice(10, 13))
    previous, current = records[1], records[2]
    end = pd.Timestamp(current["execution_date"])
    early = {k: v.loc[v.index < end] for k, v in world["closes"].items()}
    with pytest.raises(ValueError, match="never before"):
        forward.shadow_line(early, previous, current, forward.initial_books(UNIVERSE), cost_bp=COSTS)
    with pytest.raises(ValueError, match="must follow"):
        forward.shadow_line(world["closes"], current, previous, forward.initial_books(UNIVERSE), cost_bp=COSTS)
    with pytest.raises(ValueError, match="recorded in order"):
        forward.shadow_line(world["closes"], records[0], records[1], books, cost_bp=COSTS)   # books already past it


def test_append_shadow_and_books_order_and_duplicates(world, tmp_path):
    records, lines, _ = _lines(world, slice(10, 14))
    path = tmp_path / "shadow.csv"
    forward.append_shadow(lines[0], path)
    with pytest.raises(FileExistsError):
        forward.append_shadow(lines[0], path)
    with pytest.raises(ValueError, match="does not follow"):
        forward.append_shadow(lines[2], path)
    forward.append_shadow(lines[1], path)
    frame = forward.read_shadow(path)
    assert len(frame) == 2 and list(frame.columns) == forward.SHADOW_COLUMNS
    assert frame["T1_book"].to_numpy() == pytest.approx([lines[0]["T1_book"], lines[1]["T1_book"]], rel=1e-12)
    books = {"period_end": lines[0]["period_end"], "books": {}}
    forward.write_books(books, tmp_path / "books")
    with pytest.raises(FileExistsError):
        forward.write_books(books, tmp_path / "books")
    assert forward.latest_books(UNIVERSE, tmp_path / "books")["period_end"] == lines[0]["period_end"]
    assert forward.latest_books(UNIVERSE, tmp_path / "nothing")["period_end"] is None


def test_previous_targets_from_the_terminal_position_then_records(world, tmp_path):
    table = world["table"]
    oos = tmp_path / "oos"
    oos.mkdir()
    table["s12"].to_csv(oos / f"signal_s12_{len(UNIVERSE)}assets.csv")
    table["vol"].to_csv(oos / f"signal_vol_{len(UNIVERSE)}assets.csv")
    last = table["s12"].index[-1]
    targets, source = forward.previous_targets(UNIVERSE, K, tmp_path / "decisions", oos, before="2026-10-30")
    assert source.startswith("terminal position") and str(last.date()) in source
    expected = run.weights_from(run.trial_signal(table, "T1"), table["vol"])[last]
    assert targets["T1"] == pytest.approx({a: expected.get(a, 0.0) for a in UNIVERSE}, abs=1e-12)
    assert targets["B4"] == pytest.approx({a: K * w for a, w in targets["B3"].items()}, abs=1e-12)
    first = dict(_record(world, world["sched"]["signal_date"].iloc[3]), signal_date="2026-10-30")
    second = dict(_record(world, world["sched"]["signal_date"].iloc[4]), signal_date="2026-11-30")
    forward.write_record(first, tmp_path / "decisions")
    forward.write_record(second, tmp_path / "decisions")
    later, source = forward.previous_targets(UNIVERSE, K, tmp_path / "decisions", oos, before="2026-12-31")
    assert source == "decision record 2026-11-30" and later == second["targets"]
    earlier, source = forward.previous_targets(UNIVERSE, K, tmp_path / "decisions", oos, before="2026-11-30")
    assert source == "decision record 2026-10-30" and earlier == first["targets"]


def test_cli_refuses_before_the_first_forward_date(capsys):
    assert forward.main(["decide", "--signal-date", "2026-09-30", "--dry-run"]) == 1
    assert "before the first forward signal date" in capsys.readouterr().out
