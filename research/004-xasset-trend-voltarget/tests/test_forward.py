"""§11 forward record on constructed series (no raw file, no network): the
decision record against the run module's own signal table and weights, no
look-ahead, the gates, the carried weight of a missing bar, the shadow line
and the books against the frozen engine, the append rules, the terminal
position as the first holding."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from src import forward, run
from src.config import CASH_ETF

from qune_research import engine
from qune_research.dates import month_end_signal_dates, schedule

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


ZERO = {name: {a: 0.0 for a in UNIVERSE} for name in forward.STRATEGY_IDS}  # a holding every run has (2026-11-10)


def _record(world, signal_date, holding_before=None):
    return forward.decision_record(world["closes"], signal_date, UNIVERSE, K, holding_before or ZERO,
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


def _frozen(world, tmp_path):
    """The frozen starting state written once from the out-of-sample signal and volatility tables."""
    table = world["table"]
    oos = tmp_path / "oos"
    oos.mkdir()
    table["s12"].to_csv(oos / f"signal_s12_{len(UNIVERSE)}assets.csv")
    table["vol"].to_csv(oos / f"signal_vol_{len(UNIVERSE)}assets.csv")
    return forward.freeze_terminal_position(UNIVERSE, K, oos, tmp_path / "frozen_start.json",
                                            frozen_at_utc="2026-10-31T18:30:00Z")


def test_frozen_starting_state_is_the_tables_last_row_written_once(world, tmp_path):
    """Desk improvement of 2026-10-31 (BACKLOG item 6): the starting state is a committed file, not the last row
    of signal files read at run time; the file carries its inputs, their hashes and the weights they imply."""
    table = world["table"]
    path = _frozen(world, tmp_path)
    frozen = json.loads(path.read_text(encoding="utf-8"))
    last = table["s12"].index[-1]
    assert frozen["signal_date"] == str(last.date()) and frozen["frozen_at_utc"] == "2026-10-31T18:30:00Z"
    assert frozen["universe"] == UNIVERSE and frozen["k_exposure_ratio_frozen"] == K
    assert frozen["s12"] == {a: float(table["s12"].at[last, a]) for a in UNIVERSE}
    assert frozen["vol63_annualised"] == pytest.approx({a: float(table["vol"].at[last, a]) for a in UNIVERSE}, abs=1e-15)
    assert set(frozen["source"]) == {f"signal_s12_{len(UNIVERSE)}assets.csv", f"signal_vol_{len(UNIVERSE)}assets.csv"}
    assert all(len(v["sha256"]) == 64 for v in frozen["source"].values())
    expected = run.weights_from(run.trial_signal(table, "T1"), table["vol"])[last]
    assert frozen["targets"]["T1"] == pytest.approx({a: expected.get(a, 0.0) for a in UNIVERSE}, abs=1e-12)
    with pytest.raises(FileExistsError):
        forward.freeze_terminal_position(UNIVERSE, K, tmp_path / "oos", path)


def test_terminal_targets_read_the_frozen_file_and_refuse_an_edited_one(world, tmp_path):
    path = _frozen(world, tmp_path)
    frozen = json.loads(path.read_text(encoding="utf-8"))
    targets, source = forward.terminal_targets(UNIVERSE, K, path)
    assert source.startswith("terminal position") and frozen["signal_date"] in source
    assert targets == frozen["targets"]
    assert targets["B4"] == pytest.approx({a: K * w for a, w in targets["B3"].items()}, abs=1e-12)
    with pytest.raises(ValueError, match="another universe"):
        forward.terminal_targets(UNIVERSE + ["DDD"], K, path)
    with pytest.raises(ValueError, match="frozen with k"):
        forward.terminal_targets(UNIVERSE, K + 0.1, path)
    edited = dict(frozen, targets={**frozen["targets"], "T1": {**frozen["targets"]["T1"], "AAA": 0.5}})
    (tmp_path / "edited.json").write_text(json.dumps(edited), encoding="utf-8")
    with pytest.raises(ValueError, match="was edited"):
        forward.terminal_targets(UNIVERSE, K, tmp_path / "edited.json")
    # Review of 2026-10-31: a NaN target slipped through "abs(diff) > tol"; an edited input must fail too.
    nan_target = dict(frozen, targets={**frozen["targets"], "T1": {**frozen["targets"]["T1"], "AAA": float("nan")}})
    (tmp_path / "nan.json").write_text(json.dumps(nan_target), encoding="utf-8")
    with pytest.raises(ValueError, match="was edited"):
        forward.terminal_targets(UNIVERSE, K, tmp_path / "nan.json")
    edited_input = dict(frozen, vol63_annualised={**frozen["vol63_annualised"], "AAA": 0.5})
    (tmp_path / "input.json").write_text(json.dumps(edited_input), encoding="utf-8")
    with pytest.raises(ValueError, match="was edited"):
        forward.terminal_targets(UNIVERSE, K, tmp_path / "input.json")
    (tmp_path / "truncated.json").write_text(json.dumps({"universe": UNIVERSE}), encoding="utf-8")
    with pytest.raises(KeyError):
        forward.terminal_targets(UNIVERSE, K, tmp_path / "truncated.json")
    with pytest.raises(FileNotFoundError):
        forward.terminal_targets(UNIVERSE, K, tmp_path / "no-such-file.json")


def test_previous_targets_from_the_terminal_position_then_records(world, tmp_path):
    table = world["table"]
    frozen_path = _frozen(world, tmp_path)
    last = table["s12"].index[-1]
    targets, source = forward.previous_targets(UNIVERSE, K, tmp_path / "decisions", frozen_path, before="2026-10-30")
    assert source.startswith("terminal position") and str(last.date()) in source
    expected = run.weights_from(run.trial_signal(table, "T1"), table["vol"])[last]
    assert targets["T1"] == pytest.approx({a: expected.get(a, 0.0) for a in UNIVERSE}, abs=1e-12)
    assert targets["B4"] == pytest.approx({a: K * w for a, w in targets["B3"].items()}, abs=1e-12)
    # the chain as a run writes it (2026-11-10): each record starts from the state in force before it and is
    # executed after its signal date; a fixture the reader's gate would refuse is not a fixture
    first = dict(_record(world, world["sched"]["signal_date"].iloc[3], holding_before=targets),
                 signal_date="2026-10-30", execution_date="2026-11-02")
    second = dict(_record(world, world["sched"]["signal_date"].iloc[4], holding_before=first["targets"]),
                  signal_date="2026-11-30", execution_date="2026-12-01")
    forward.write_record(first, tmp_path / "decisions")
    forward.write_record(second, tmp_path / "decisions")
    later, source = forward.previous_targets(UNIVERSE, K, tmp_path / "decisions", frozen_path, before="2026-12-31")
    assert source == "decision record 2026-11-30" and later == second["targets"]
    earlier, source = forward.previous_targets(UNIVERSE, K, tmp_path / "decisions", frozen_path, before="2026-11-30")
    assert source == "decision record 2026-10-30" and earlier == first["targets"]


def test_dry_run_without_inputs_or_frozen_state_refuses_and_writes_nothing(tmp_path, monkeypatch, capsys):
    """Same class as the 006/007 finding of 2026-10-31 12:15Z: a missing forward input or a missing frozen
    starting state is a refusal, never a traceback; nothing is written."""
    for name in ("FORWARD_RAW_DIR", "FORWARD_MANIFEST", "FORWARD_DECISIONS_DIR", "FORWARD_FROZEN_START"):
        monkeypatch.setattr(forward, name, tmp_path / name)
    monkeypatch.setattr(forward, "utc_now", lambda: "2026-10-31T09:00:00Z")
    monkeypatch.setattr(forward, "universe_from_checks", lambda: list(UNIVERSE))
    monkeypatch.setattr(forward, "frozen_k", lambda: K)
    assert forward.main(["decide", "--signal-date", "2026-10-30", "--fetch", "--dry-run"]) == 1
    assert "refused: an input is not in paper-log/raw/" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []
    world = _world()
    raw = tmp_path / "FORWARD_RAW_DIR"
    raw.mkdir()
    for symbol, series in world["closes"].items():
        pd.DataFrame({"close": series.dropna()}).rename_axis("date").to_csv(raw / f"alpaca_{symbol}_1Day_all.csv")
    (tmp_path / "FORWARD_MANIFEST").write_text("{}", encoding="utf-8")
    assert forward.main(["decide", "--signal-date", "2026-10-30", "--dry-run"]) == 1
    assert "refused: the frozen starting state is not in paper-log/" in capsys.readouterr().out
    assert sorted(p.name for p in tmp_path.iterdir()) == ["FORWARD_MANIFEST", "FORWARD_RAW_DIR"]
    # Review of 2026-10-31: an edited or truncated frozen file is a refusal, not a traceback.
    (tmp_path / "good").mkdir()
    frozen = json.loads(_frozen(world, tmp_path / "good").read_text(encoding="utf-8"))
    edited = dict(frozen, targets={**frozen["targets"], "B3": {**frozen["targets"]["B3"], "BBB": 0.9}})
    (tmp_path / "FORWARD_FROZEN_START").write_text(json.dumps(edited), encoding="utf-8")
    assert forward.main(["decide", "--signal-date", "2026-10-30", "--dry-run"]) == 1
    assert "refused: the frozen starting state cannot be used (ValueError" in capsys.readouterr().out
    (tmp_path / "FORWARD_FROZEN_START").write_text("{", encoding="utf-8")
    assert forward.main(["decide", "--signal-date", "2026-10-30", "--dry-run"]) == 1
    assert "refused: the frozen starting state cannot be used (JSONDecodeError" in capsys.readouterr().out
    assert not (tmp_path / "FORWARD_DECISIONS_DIR").exists()


def test_decide_writes_into_the_patched_folder_never_the_real_one(tmp_path, monkeypatch, capsys):
    """2026-11-01 (research/POST_MORTEMS.md): the test above patches four module paths and asserts refusals on
    ``--dry-run`` only, so it never showed that main's write and read of the decisions folder went through a
    default bound at import, that is, to the real paper-log/decisions/. A test that patched the folder and ran
    decide without --dry-run would have written a real record and passed. Here the real folder's listing is
    taken before and after, and the record must land in the patched folder."""
    real_decisions = forward.FORWARD_DECISIONS_DIR
    real_before = sorted(p.name for p in real_decisions.iterdir()) if real_decisions.exists() else []
    for name in ("FORWARD_RAW_DIR", "FORWARD_MANIFEST", "FORWARD_DECISIONS_DIR", "FORWARD_FROZEN_START",
                 "FORWARD_SHADOW_CSV", "FORWARD_BOOKS_DIR"):
        monkeypatch.setattr(forward, name, tmp_path / name)
    monkeypatch.setattr(forward, "utc_now", lambda: "2026-10-31T09:00:00Z")
    monkeypatch.setattr(forward, "universe_from_checks", lambda: list(UNIVERSE))
    monkeypatch.setattr(forward, "frozen_k", lambda: K)
    world = _world()
    shifted = pd.bdate_range(end="2026-10-30", periods=len(world["days"]))   # the constructed world, moved so
    raw = tmp_path / "FORWARD_RAW_DIR"                                        # that its last close is the signal date
    raw.mkdir()
    for symbol, series in world["closes"].items():
        moved = pd.Series(series.to_numpy(), index=shifted).dropna()
        pd.DataFrame({"close": moved}).rename_axis("date").to_csv(raw / f"alpaca_{symbol}_1Day_all.csv")
    (tmp_path / "FORWARD_MANIFEST").write_text("{}", encoding="utf-8")
    (tmp_path / "good").mkdir()
    (tmp_path / "FORWARD_FROZEN_START").write_bytes(_frozen(world, tmp_path / "good").read_bytes())
    code = forward.main(["decide", "--signal-date", "2026-10-30"])
    out = capsys.readouterr().out
    assert "written: " in out, out
    written = tmp_path / "FORWARD_DECISIONS_DIR" / "2026-10-30.json"
    assert written.exists(), sorted(p.name for p in tmp_path.rglob("*"))
    record = json.loads(written.read_text(encoding="utf-8"))
    assert record["signal_date"] == "2026-10-30" and code == (0 if record["status"].startswith("ok") else 1)
    real_after = sorted(p.name for p in real_decisions.iterdir()) if real_decisions.exists() else []
    assert real_after == real_before
    # the shadow step reads the records from the same patched folder, not the real one (no earlier record there)
    assert forward.main(["shadow", "--signal-date", "2026-10-30", "--dry-run"]) == 1
    assert "refused: no earlier decision record" in capsys.readouterr().out


def test_cli_refuses_before_the_first_forward_date(capsys):
    assert forward.main(["decide", "--signal-date", "2026-09-30", "--dry-run"]) == 1
    assert "before the first forward signal date" in capsys.readouterr().out


# --- The alter-each-column search of 2026-11-10, kept (research/POST_MORTEMS.md "A starting state no reader held") ---
# Before the fix every alteration below became the next record's starting state or a silent fall-back to the
# frozen start; the committed record passes its own gate and each altered copy is refused by name.
COMMITTED_RECORD = Path(__file__).resolve().parents[1] / "paper-log" / "decisions" / "2026-10-30.json"
_DEL = object()
COMMON_ALTERATIONS = [
    (("status",), "OK"), (("status",), "ok "), (("status",), "done"), (("status",), _DEL),
    (("signal_date",), "2026-10-3"), (("signal_date",), "2026-11-30"), (("signal_date",), _DEL),
    (("execution_date",), "2026-10-01"), (("execution_date",), None), (("run_at_utc",), "soon"),
    (("study",), "999-other-study"), (("paper_order",), True), (("orders",), [{"symbol": "IEF", "qty": 1}]),
]
def _load_committed(directory):
    committed = json.loads(COMMITTED_RECORD.read_text(encoding="utf-8"))
    return forward.load_records(directory, universe=committed["universe"], k=committed["k_exposure_ratio_frozen"])


STUDY_ALTERATIONS = [
    (("targets", "T1", "IEF"), 1.5), (("targets", "T1", "IEF"), -0.2), (("targets", "T1", "GLD"), "0.1"),
    (("targets", "T1", "GLD"), float("nan")), (("targets", "T1", "GLD"), _DEL), (("targets", "T1", "XYZ"), 0.1),
    (("targets", "B4"), _DEL), (("targets",), None), (("universe",), ["EEM"]),
    (("holding_before", "T1", "IEF"), 2.0), (("k_exposure_ratio_frozen",), 0.5), (("carried",), ["GLD"]),
]


def _altered(record: dict, path: tuple, value):
    record = json.loads(json.dumps(record))
    node = record
    for key in path[:-1]:
        node = node[key]
    if value is _DEL:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return record


def test_committed_record_passes_its_own_gate():
    record = json.loads(COMMITTED_RECORD.read_text(encoding="utf-8"))
    assert forward.record_violations(record, COMMITTED_RECORD) == []


@pytest.mark.parametrize("path,value", COMMON_ALTERATIONS + STUDY_ALTERATIONS)
def test_an_altered_column_of_the_committed_record_is_refused_by_name(path, value, tmp_path):
    record = _altered(json.loads(COMMITTED_RECORD.read_text(encoding="utf-8")), path, value)
    (tmp_path / "2026-10-30.json").write_text(json.dumps(record, indent=2, sort_keys=True, allow_nan=True) + "\n",
                                              encoding="utf-8")
    with pytest.raises(ValueError) as refused:
        _load_committed(tmp_path)
    assert any(str(part) in str(refused.value) for part in path), str(refused.value)


def test_two_records_for_one_month_are_refused(tmp_path):
    record = json.loads(COMMITTED_RECORD.read_text(encoding="utf-8"))
    (tmp_path / "2026-10-30.json").write_text(json.dumps(record), encoding="utf-8")
    (tmp_path / "2026-10-29.json").write_text(json.dumps(dict(record, signal_date="2026-10-29")), encoding="utf-8")
    with pytest.raises(ValueError, match="two records"):
        _load_committed(tmp_path)
    (tmp_path / "2026-10-29.json").unlink()
    (tmp_path / "2026-10-30 (1).json").write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError):
        _load_committed(tmp_path)
