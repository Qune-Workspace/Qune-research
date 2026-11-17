"""§6.5 tests of the analysis run on synthetic Study 013 folders: the refusals in order with nothing written, the
once-only marker before the first row is read, every snapshot verified before any row, the §5.4 halts on synthetic
counts (per bin), the followed-event exclusion by any event id, the small-cell suppression, and an end-to-end run
that writes aggregates only."""

import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pytest
from src import analysis as an
from src import reader, run
from src.reader import Refusal, SnapshotHashMismatch

RUN_DATE = dt.date(2027, 1, 21)
SNAP = "2026-11-20"
S_SHA_COLUMNS = "snapshot_date,started_utc,finished_utc,pages,rows,distinct_markets,bytes,records_sha256,pages_sha256"


def _build_013(root: Path, markets: list[dict], *, price_pass=True, stopped=False, halted=False, amendment=None,
               extra_snapshot_rows: dict[str, list[dict]] | None = None) -> Path:
    """A synthetic Study 013 folder: sample.jsonl (C1 rows, C1a = non-Sports rows, C1b = the same rows), its manifest,
    its data-step report, the snapshots of record and the snapshot log."""
    s13 = root / "013"
    (s13 / "results").mkdir(parents=True)
    (s13 / "paper-log").mkdir()
    sample_lines = []
    for m in markets:
        base = {"market": m["id"], "cluster": m["cluster"], "price": (m["bid"] + m["ask"]) / 2 if "price" not in m else m["price"],
                "snapshot": m.get("snapshot", SNAP), "realised_horizon_hours": 25.0, "half": m.get("half", "W1"),
                "sports": m.get("sports", False), "early": m.get("early", False), "first_label_yes": True,
                "volume_at_horizon": 20000.0, "tag_family": "other", "first_token": "t"}
        sample_lines.append(json.dumps({"trial": "C1", **base}))
        if not base["sports"]:
            sample_lines.append(json.dumps({"trial": "C1a", **base}))
        sample_lines.append(json.dumps({"trial": "C1b", **base}))
    text = "\n".join(sample_lines) + "\n"
    (s13 / "results" / "sample.jsonl").write_text(text, encoding="utf-8")
    (s13 / "results" / "data_manifest.json").write_text(json.dumps({"sample_jsonl_sha256": hashlib.sha256(text.encode()).hexdigest()}),
                                                         encoding="utf-8")
    report = {"stopped_for_amendment": stopped, "halted": halted, "price_field_check": {"pass": price_pass, "rows": 10}}
    if amendment:
        report["amendment"] = amendment
    (s13 / "results" / "data_step.json").write_text(json.dumps(report), encoding="utf-8")
    snapshots: dict[str, list[dict]] = {}
    for m in markets:
        if m.get("absent"):
            continue
        row = {"id": m["id"], "bestBid": m["bid"], "bestAsk": m["ask"], "orderPriceMinTickSize": m.get("tick", 0.01),
               "liquidityNum": 15000.0, "feesEnabled": m.get("fees", False), "endDate": m.get("end", "2026-11-21T12:00:00Z"),
               "eventIds": json.dumps(m.get("events", [m["cluster"]])), "lastTradePrice": 0.5, "closedTime": "x"}
        snapshots.setdefault(m.get("snapshot", SNAP), []).append(row)
    for day, rows in (extra_snapshot_rows or {}).items():
        snapshots.setdefault(day, []).extend(rows)
    log_lines = [S_SHA_COLUMNS]
    for day, rows in sorted(snapshots.items()):
        folder = s13 / "data" / "raw" / "snapshots" / day
        folder.mkdir(parents=True)
        t = "".join(json.dumps(r) + "\n" for r in rows)
        (folder / "records.jsonl").write_text(t, encoding="utf-8")
        log_lines.append(f"{day},{day}T04:40:00Z,{day}T04:45:00Z,1,{len(rows)},{len(rows)},{len(t)},{hashlib.sha256(t.encode()).hexdigest()},{'0' * 64}")
    (s13 / "paper-log" / "snapshots.csv").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    return s13


def _build_014(root: Path, *, approved=True, trials_row=True) -> Path:
    s14 = root / "014"
    s14.mkdir(parents=True)
    if approved:
        (s14 / "APPROVED").write_text("approved 2027-01-01 by the separate-session code review\n", encoding="utf-8")
    rows = ["| ID | Rule |", "|---|---|", "| M1 | ... |"]
    if trials_row:
        rows.append("| Analysis run logged (§14 step 5) | 2027-01-21 | N_programme = 40 (count of trials.md rows and the desk registry) |")
    (s14 / "trials.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return s14


def _events(root: Path) -> Path:
    p = root / "events.csv"
    if not p.exists():
        p.write_text("venue,event_id,event_slug,method,followed_from,source\n"
                     "polymarket,1292829,btc,btc_touch,2026-11-03,x\npolymarket,770450,fed,fomc_bills,2026-11-03,x\n"
                     "polymarket,9009,later,btc_touch,2026-12-05,x\n", encoding="utf-8")
    return p


def _markets(n_long=220, n_cent=220, seed=1, clusters=120):
    """Enough synthetic markets for the §5.4 floors: longshot quotes wide, central quotes tight, a true premium."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n_long):
        mid = float(rng.uniform(0.02, 0.09))
        q = float(rng.choice([0.01, 0.02, 0.03]))
        out.append({"id": f"L{i}", "cluster": f"c{i % clusters}", "bid": round(mid - q / 2, 4), "ask": round(mid + q / 2, 4),
                    "half": "W1" if i % 2 else "W2", "early": i % 5 == 0, "sports": i % 7 == 0})
    for i in range(n_cent):
        mid = float(rng.uniform(0.42, 0.58))
        q = float(rng.choice([0.01, 0.02]))
        out.append({"id": f"C{i}", "cluster": f"d{i % clusters}", "bid": round(mid - q / 2, 4), "ask": round(mid + q / 2, 4),
                    "half": "W1" if i % 2 else "W2", "early": i % 5 == 0, "sports": i % 7 == 0})
    return out


def _run(root: Path, s14: Path, s13: Path, resamples=50):
    return run.run_analysis(study=s14, study_013=s13, events_csv=_events(root), run_date=RUN_DATE, resamples=resamples)


def _nothing_written(s14: Path) -> bool:
    return not (s14 / "results").exists()


def test_refusals_in_order_and_nothing_written(tmp_path: Path, monkeypatch):
    s13 = _build_013(tmp_path, _markets(30, 30))
    s14 = _build_014(tmp_path, approved=False)
    with pytest.raises(Refusal, match="APPROVED"):
        _run(tmp_path, s14, s13)
    (s14 / "APPROVED").write_text("yes\n", encoding="utf-8")
    (s14 / "results" / "run").mkdir(parents=True)
    with pytest.raises(Refusal, match="executed once"):
        _run(tmp_path, s14, s13)
    (s14 / "results" / "run").rmdir()
    (s14 / "results").rmdir()
    (s13 / "results" / "data_step.json").rename(s13 / "results" / "ds.bak")
    with pytest.raises(Refusal, match="has not run"):
        _run(tmp_path, s14, s13)
    (s13 / "results" / "ds.bak").rename(s13 / "results" / "data_step.json")
    (s13 / "results" / "data_manifest.json").rename(s13 / "results" / "dm.bak")
    with pytest.raises(Refusal, match="not fixed the sample"):
        _run(tmp_path, s14, s13)
    (s13 / "results" / "dm.bak").rename(s13 / "results" / "data_manifest.json")
    (s13 / "results" / "data_step.json").write_text(json.dumps({"stopped_for_amendment": True, "halted": False,
                                                                 "price_field_check": {"pass": True}}), encoding="utf-8")
    with pytest.raises(Refusal, match="waits"):
        _run(tmp_path, s14, s13)
    (s13 / "results" / "data_step.json").write_text(json.dumps({"stopped_for_amendment": False, "halted": False,
                                                                 "price_field_check": {"pass": True}}), encoding="utf-8")
    (s14 / "trials.md").write_text("| M1 | ... |\n", encoding="utf-8")
    with pytest.raises(Refusal, match="no analysis-run row"):
        _run(tmp_path, s14, s13)
    (s14 / "trials.md").write_text("| Analysis run logged (§14 step 5) | no count |\n", encoding="utf-8")
    with pytest.raises(Refusal, match="programme count"):
        _run(tmp_path, s14, s13)
    _build_014(tmp_path / "again")
    (s14 / "trials.md").write_text((tmp_path / "again" / "014" / "trials.md").read_text(encoding="utf-8"), encoding="utf-8")
    p = s13 / "results" / "sample.jsonl"
    good = p.read_text(encoding="utf-8")
    p.write_text(good + "\n", encoding="utf-8")
    with pytest.raises(Refusal, match="hashes to"):
        _run(tmp_path, s14, s13)
    p.write_text(good, encoding="utf-8")
    # the followed-events file missing is a refusal (should-fix 2), before any snapshot is touched
    with pytest.raises(Refusal, match="followed-events file"):
        run.run_analysis(study=s14, study_013=s13, events_csv=tmp_path / "nowhere.csv", run_date=RUN_DATE, resamples=5)
    # a snapshot of record off its logged hash: refused before any row of any snapshot is read
    calls: list[Path] = []
    real = reader._iter_rows
    monkeypatch.setattr(reader, "_iter_rows", lambda path: calls.append(path) or real(path))
    rec = s13 / "data" / "raw" / "snapshots" / SNAP / "records.jsonl"
    rec_good = rec.read_text(encoding="utf-8")
    rec.write_text(rec_good.replace("0.5,", "0.6,", 1), encoding="utf-8")
    with pytest.raises(SnapshotHashMismatch, match="hashes to"):
        _run(tmp_path, s14, s13)
    rec.write_text(rec_good, encoding="utf-8")
    assert calls == [] and _nothing_written(s14)


def test_an_earlier_snapshot_off_its_hash_refuses_before_any_row_is_read(tmp_path: Path, monkeypatch):
    """Must-fix 2: a non-record day inside the moved-end scan's range [S, last record day] is verified with the rest,
    before the first snapshot-of-record row is read, never after the fits."""
    s13 = _build_013(tmp_path, _markets(), extra_snapshot_rows={"2026-11-05": [{"id": "Z", "endDate": "e"}],
                                                                 "2026-11-10": [{"id": "Y", "endDate": "e"}]})
    s14 = _build_014(tmp_path)
    bad = s13 / "data" / "raw" / "snapshots" / "2026-11-05" / "records.jsonl"
    bad.write_text(bad.read_text(encoding="utf-8").replace('"e"', '"f"'), encoding="utf-8")
    calls: list[Path] = []
    real = reader._iter_rows
    monkeypatch.setattr(reader, "_iter_rows", lambda path: calls.append(path) or real(path))
    fits: list[int] = []
    real_fit = run.fit_rows
    monkeypatch.setattr(run, "fit_rows", lambda *a, **k: fits.append(1) or real_fit(*a, **k))
    with pytest.raises(SnapshotHashMismatch, match="2026-11-05"):
        _run(tmp_path, s14, s13)
    assert calls == [] and fits == [] and _nothing_written(s14)
    # a logged earlier day with no file is not a refusal: it is named missing in the manifest and the count says so
    (s13 / "data" / "raw" / "snapshots" / "2026-11-05" / "records.jsonl").unlink()
    (s13 / "data" / "raw" / "snapshots" / "2026-11-05").rmdir()
    s = _run(tmp_path, s14, s13)
    manifest = json.loads((s14 / "results" / "input_manifest.json").read_text(encoding="utf-8"))
    assert manifest["earlier_snapshots_read"]["2026-11-05"] == "missing" and len(manifest["earlier_snapshots_read"]["2026-11-10"]) == 64
    assert s["moved_end_M1"]["missing_snapshot_days_in_scan"] == ["2026-11-05"]
    assert set(manifest["snapshots_read"]) == {SNAP}


def test_a_death_after_the_marker_blocks_a_second_run(tmp_path: Path, monkeypatch):
    """Must-fix 1: the once-only marker is written before the first snapshot-of-record row is read; a run that dies
    between the marker and the outputs leaves it, and the next attempt is refused at 'results/run exists'."""
    s13 = _build_013(tmp_path, _markets())
    s14 = _build_014(tmp_path)

    def boom(*a, **k):
        raise MemoryError("synthetic death inside the descriptives")

    monkeypatch.setattr(run, "decile_table", boom)
    with pytest.raises(MemoryError):
        _run(tmp_path, s14, s13)
    marker = s14 / "results" / "run" / "started.txt"
    assert marker.exists() and "executes once" in marker.read_text(encoding="utf-8")
    assert not (s14 / "results" / "run" / "summary.json").exists() and not (s14 / "results" / "rows.jsonl").exists()
    monkeypatch.undo()
    with pytest.raises(Refusal, match="executed once"):
        _run(tmp_path, s14, s13)
    assert not (s14 / "results" / "run" / "summary.json").exists()
    # the marker is written after every refusal and after the verification of every snapshot, not before:
    r2 = tmp_path / "two"
    s13b = _build_013(r2, _markets(30, 30))
    s14b = _build_014(r2)
    calls: list[Path] = []
    real = reader._iter_rows
    monkeypatch.setattr(reader, "_iter_rows", lambda path: calls.append(path) or real(path))
    marked: list[bool] = []
    real_marker = run._start_marker
    monkeypatch.setattr(run, "_start_marker", lambda d, now: marked.append(calls == []) or real_marker(d, now))
    _run(r2, s14b, s13b)
    assert marked == [True] and calls  # the marker went down before the first row was read


def test_the_price_field_halt_wins_over_the_stop_flag(tmp_path: Path):
    """Must-fix 5: Study 013 writes both flags when both fire and never re-runs after a halt; this study halts."""
    s13 = _build_013(tmp_path, _markets(30, 30), price_pass=False, stopped=True, halted=True)
    s14 = _build_014(tmp_path)
    s = _run(tmp_path, s14, s13)
    assert s["halted"] and s["verdict"]["M1"] == "inconclusive (halted: the quote fields do not mean what both documents say)"
    assert not (s14 / "results" / "rows.jsonl").exists()
    with pytest.raises(Refusal, match="executed once"):
        _run(tmp_path, s14, s13)
    # a stop that Study 013 re-ran under a dated amendment and that still reports the stop flag does not make this
    # study wait for good (should-fix 4; Study 013's own scoring run proceeds on the same pair of keys)
    r2 = tmp_path / "two"
    s13b = _build_013(r2, _markets(30, 30), stopped=True, amendment="2027-01-25")
    s14b = _build_014(r2)
    s2 = _run(r2, s14b, s13b)
    assert s2["inherited_data_step"]["amendment"] == "2027-01-25" and "fits" not in s2  # halted on its own floors below


def test_halts_on_synthetic_counts(tmp_path: Path):
    # too few clusters and markets: halted at the analysis run, verdict written, no Delta, runs once
    s13 = _build_013(tmp_path, _markets(30, 30, clusters=5))
    s14 = _build_014(tmp_path)
    s = _run(tmp_path, s14, s13)
    assert s["halted"] and s["verdict"]["M1"] == "inconclusive (halted at the analysis run)"
    assert any("clusters in the M1 longshot bin" in r for r in s["halt_reasons"]) and any("markets in the M1 longshot bin" in r for r in s["halt_reasons"])
    assert "fits" not in s and (s14 / "results" / "run" / "verdict.md").read_text(encoding="utf-8").startswith("# Study 014 verdict")
    with pytest.raises(Refusal, match="executed once"):
        _run(tmp_path, s14, s13)
    # Study 013's price-field check failed: the inherited permanent halt, before any row is read
    r2 = tmp_path / "two"
    s13b = _build_013(r2, _markets(30, 30), price_pass=False)
    s14b = _build_014(r2)
    s2 = _run(r2, s14b, s13b)
    assert s2["halted"] and s2["verdict"]["M1"].startswith("inconclusive (halted: the quote fields")
    assert not (s14b / "results" / "rows.jsonl").exists()
    # rows not as recorded above 1 percent of the M1 rows
    r3 = tmp_path / "three"
    ms = _markets()
    for m in ms[:10]:
        m["price"] = 0.3  # Study 013's p off the quoted mid on ten rows
    s13c = _build_013(r3, ms)
    s14c = _build_014(r3)
    s3 = _run(r3, s14c, s13c)
    assert s3["halted"] and any("not as Study 013 recorded" in r for r in s3["halt_reasons"])
    assert s3["exclusions"]["M1"]["not_as_recorded"] == 10


def _rows(n_long, g_long, n_cent, g_cent):
    rows = [{"bin": an.LONGSHOT, "cluster": f"l{i % g_long}"} for i in range(n_long)]
    rows += [{"bin": an.CENTRAL, "cluster": f"c{i % g_cent}"} for i in range(n_cent)]
    return rows


def test_own_halt_floors_are_read_per_bin_at_their_boundaries():
    """Must-fix 6: §5.4 "fewer than 100 clusters or fewer than 200 markets in either decision bin", both per bin."""
    ok = Counter(after_followed_exclusion=1000)
    assert run.own_halts(ok, _rows(200, 100, 200, 100)) == []
    assert run.own_halts(ok, _rows(199, 100, 200, 100)) == ["199 markets in the M1 longshot bin (fewer than 200)"]
    assert run.own_halts(ok, _rows(200, 100, 199, 100)) == ["199 markets in the M1 central bin (fewer than 200)"]
    assert run.own_halts(ok, _rows(200, 99, 200, 100)) == ["99 clusters in the M1 longshot bin (fewer than 100)"]
    assert run.own_halts(ok, _rows(200, 100, 200, 99)) == ["99 clusters in the M1 central bin (fewer than 100)"]
    # the reviewer's case: 110 longshot clusters and 20 central clusters, 130 over the union, halts on the central bin
    assert run.own_halts(ok, _rows(220, 110, 220, 20)) == ["20 clusters in the M1 central bin (fewer than 100)"]


def test_not_as_recorded_share_boundary_and_its_base():
    rows = _rows(220, 110, 220, 110)
    # base 440 after the followed-event exclusion: 4 of 440 is 0.91 percent (no halt), 5 is 1.14 percent (halt)
    assert run.own_halts(Counter(after_followed_exclusion=440, not_as_recorded=4), rows) == []
    assert run.own_halts(Counter(after_followed_exclusion=440, not_as_recorded=5), rows) == [
        "rows not as Study 013 recorded them: 5 of 440 (above 1 percent)"]
    # a missing record row is counted in the base as well as in the numerator
    c = Counter(after_followed_exclusion=436, not_as_recorded=5, not_as_recorded_missing_row=4)
    assert run.own_halts(c, rows) == ["rows not as Study 013 recorded them: 5 of 440 (above 1 percent)"]
    c2 = Counter(after_followed_exclusion=436, not_as_recorded=4, not_as_recorded_missing_row=4)
    assert run.own_halts(c2, rows) == []


def test_followed_events_are_excluded_by_any_event_id(tmp_path: Path):
    ms = _markets()
    ms[0]["events"] = ["424242", "1292829"]  # the btc event among several ids
    ms[1]["events"] = ["770450"]
    ms[2]["events"] = ["1", "9009"]  # followed later (2026-12-05, before the run date)
    ms[3]["absent"] = True  # no snapshot-of-record row: not as recorded
    s13 = _build_013(tmp_path, ms)
    s14 = _build_014(tmp_path)
    s = _run(tmp_path, s14, s13)
    ex = s["exclusions"]["M1"]
    assert ex["followed_fixed"] == 2 and ex["followed_later"] == 1 and ex["followed_later_ids"] == ["9009"]
    assert ex["not_as_recorded"] == 1 and ex["not_as_recorded_missing_row"] == 1
    assert ex["after_followed_exclusion"] == 440 - 4
    assert s["followed_events"]["later"] == ["9009"]
    rows = [json.loads(line) for line in (s14 / "results" / "rows.jsonl").read_text(encoding="utf-8").splitlines()]
    ids = {r["id"] for r in rows if r["trial"] == "M1"}
    assert not ids & {"L0", "L1", "L2", "L3"} and len(ids) == 436
    # the ordered list of §9.6 (should-fix 7): keys in the document's order, the ids beside the later-followed count
    order = [row[0] for row in s["exclusions_in_order"]["M1"]]
    assert order[:9] == ["sample_rows", "followed_fixed", "followed_later", "outside_decision_bins", "not_as_recorded",
                         "not_as_recorded_missing_row", "null_tick", "tick_below_0.001", "locked_book"]
    assert s["exclusions_in_order"]["M1"][2][3] == ["9009"] and order[9].startswith("bin_longshot_W1")
    verdict = (s14 / "results" / "run" / "verdict.md").read_text(encoding="utf-8")
    assert "Exclusion counts in the order of §9.6" in verdict and "removed for the two followed events (§6.3): 2" in verdict


def test_small_cells_publish_counts_only(tmp_path: Path):
    """Must-fix 4: one high-bin market, a four-market before-D split and a three-market M1a half: counts only."""
    ms = _markets()
    for m in ms[:4]:
        m["snapshot"] = "2026-11-16"  # before D = 2026-11-17: four markets in the before-D split
    ms.append({"id": "H1", "cluster": "h", "bid": 0.94, "ask": 0.96})  # one high-bin market
    s13 = _build_013(tmp_path, ms)
    s14 = _build_014(tmp_path)
    s = _run(tmp_path, s14, s13)
    hb = s["high_bin_M1"]
    assert hb == {"n_high": 1, "G_high": 1, "suppressed": True}
    bd = s["before_after_D_M1"]["before_D"]
    assert bd["n"] == 4 and bd["suppressed"] and "delta" not in bd and "alpha" not in bd and "sd_longshot" not in bd
    assert s["before_after_D_M1"]["after_D"]["n"] == 436 and not s["before_after_D_M1"]["after_D"]["suppressed"]
    text = (s14 / "results" / "run" / "summary.json").read_text(encoding="utf-8")
    ln_s_h1 = float(np.log((0.96 - 0.94) / 0.95))
    assert f"{ln_s_h1:.6f}"[:8] not in text  # the one market's ln s is in no committed output
    for name in ("deltas.csv", "deciles.csv", "verdict.md"):
        assert f"{ln_s_h1:.6f}"[:8] not in (s14 / "results" / "run" / name).read_text(encoding="utf-8")
    # a trial's half with fewer than ten markets: counts and the sign C4 saw, nothing else
    r2 = tmp_path / "two"
    ms2 = _markets()
    for m in ms2:
        m["sports"] = True
    for m in ms2[:3]:
        m["sports"] = False  # M1a holds three markets
        m["half"] = "W1"
    s13b = _build_013(r2, ms2)
    s14b = _build_014(r2)
    s2 = _run(r2, s14b, s13b)
    w1 = s2["fits"]["M1a"]["W1"]
    assert w1["n"] == 3 and w1["suppressed"] and "delta" not in w1 and w1["delta_sign"] in (None, -1, 0, 1)
    assert s2["fits"]["M1a"]["W2"] == {**{k: s2["fits"]["M1a"]["W2"][k] for k in run.COUNTS_ONLY_KEYS}, "delta_sign": None}
    deltas = (s14b / "results" / "run" / "deltas.csv").read_text(encoding="utf-8").splitlines()
    assert deltas[0].startswith("trial,row,n,n_longshot,n_central,G,G_longshot,G_central,fitted,no_fit_reason,suppressed,delta_sign,")
    assert s2["verdict"]["M1a"].startswith("not supported")  # the companion's row is decided on the full fit in memory


def test_end_to_end_fit_counts_and_no_per_market_row(tmp_path: Path):
    ms = _markets()
    ms[5]["tick"] = None  # a null tick
    ms[6]["tick"] = 0.0001  # a tick below 0.001
    ms[7]["bid"] = ms[7]["ask"] = 0.05  # a locked book
    ms[7]["price"] = 0.05
    ms.extend({"id": f"H{i}", "cluster": f"h{i}", "bid": 0.94, "ask": 0.96} for i in range(12))  # the high bin, 12 markets
    ms.append({"id": "X1", "cluster": "x", "bid": 0.24, "ask": 0.26})  # outside every named bin
    s13 = _build_013(tmp_path, ms, extra_snapshot_rows={
        "2026-11-02": [{"id": "L1", "endDate": "moved-before-S", "lastTradePrice": 1}],  # before S: ignored by the scan
        "2026-11-03": [{"id": "L0", "endDate": "moved", "lastTradePrice": 1}]})
    s14 = _build_014(tmp_path)
    s = _run(tmp_path, s14, s13)
    assert not s["halted"]
    m1 = s["fits"]["M1"]["W"]
    assert m1["fitted"] and m1["n_longshot"] == 220 and m1["n_central"] == 220 and m1["G"] == 240
    assert m1["G_longshot"] == 120 and m1["G_central"] == 120
    assert m1["delta"] > 0.59 and m1["boot_available"] and m1["boot_low"] < m1["delta"] < m1["boot_high"]
    assert m1["power"]["ratio"] == pytest.approx(2.842 * m1["se_cl"] / 1.18)
    assert s["criteria"]["M1"]["C1"] and s["verdict"]["M1"].startswith(("supported in one forward window", "inconclusive (fragile"))
    assert s["fits"]["M1"]["W1"]["n"] + s["fits"]["M1"]["W2"]["n"] == 440
    assert s["fits"]["M1a"]["W"]["n"] < 440 and s["fits"]["M1b"]["W"]["n"] == 440
    # the bootstrap runs for the W rows only (§9.3); the halves carry Wald intervals
    for half in ("W1", "W2"):
        h = s["fits"]["M1"][half]
        assert not h["boot_available"] and h["boot_dropped"] == 0 and np.isnan(h["boot_low"]) and np.isfinite(h["wald_low"])
    # the tick-floored share: every synthetic quote is one, two or three ticks wide; only the locked book L7 is floored
    assert m1["floored_share_longshot"] == pytest.approx(1 / 220) and m1["floored_share_central"] == 0.0
    ex = s["exclusions"]["M1"]
    assert ex["null_tick"] == 1 and ex["tick_below_0.001"] == 1 and ex["locked_book"] == 1 and ex["outside_decision_bins"] == 13
    assert s["programme_count"] == 40 and s["bars"]["N_3"] == 2.128 and s["bars"]["N_13"] == pytest.approx(2.665, abs=0.001)
    assert len(s["deciles_M1"]) == 10 and s["deciles_M1"][2]["suppressed"] and not s["deciles_M1"][0]["suppressed"]
    assert s["deciles_M1"][0]["decile_low"] == 0.01 and s["deciles_M1"][9]["decile_high"] == 0.99
    central = s["secondary_reading_M1"]["central"]
    assert central["wa26_compression_points"] < 0.3  # the slope's compression at a median mid near 0.50 is near 0
    assert central["wa26_at_named_prices"]["0.60"] == pytest.approx(1.1, abs=0.1)
    assert central["wa26_at_named_prices"]["0.05"] == pytest.approx(1.4, abs=0.1)
    assert central["cr26_clears_half_spread"] is True and isinstance(central["wa26_clears_half_spread"], bool)
    assert s["secondary_reading_M1"]["high"]["n"] == 12 and not s["secondary_reading_M1"]["high"]["suppressed"]
    hb = s["high_bin_M1"]
    assert hb["n_high"] == 12 and hb["G_high"] == 12 and not hb["suppressed"] and hb["fitted"]
    assert hb["mean_ln_s_high"] == pytest.approx(np.log((0.96 - 0.94) / 0.95))  # twelve equal quotes: a mean, not a row
    # the first snapshot dated on or after S that lists a market may be its snapshot of record (then its end is unmoved);
    # L0 is listed on 2026-11-03 with another endDate, so it alone counts as moved; L1's 2026-11-02 listing is before S
    assert s["moved_end_M1"]["longshot"] == {"n": 220, "with_first_listing": 220, "without_first_listing": 0, "moved": 1}
    assert s["moved_end_M1"]["central"]["moved"] == 0 and s["moved_end_M1"]["missing_snapshot_days_in_scan"] == []
    assert s["null_tick_0.01_M1"]["fitted"] and s["before_after_D_M1"]["after_D"]["n"] == 440  # n counts the two decision bins
    assert s["before_after_D_M1"]["before_D"]["n"] == 0 and s["before_after_D_M1"]["before_D"]["suppressed"]
    assert 0 < s["early_split_M1"]["early_share"] < 1 and not s["early_split_M1"]["early"]["suppressed"]
    # outputs: aggregates only; the per-market rows sit in the git-ignored rows.jsonl, hashed in the manifest
    run_dir = s14 / "results" / "run"
    assert {p.name for p in run_dir.iterdir()} == {"started.txt", "summary.json", "verdict.md", "deltas.csv", "deciles.csv"}
    for p in run_dir.iterdir():
        text = p.read_text(encoding="utf-8")
        assert "L17" not in text and "C17" not in text, p.name
    manifest = json.loads((s14 / "results" / "input_manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["snapshots_read"]) == {SNAP} and set(manifest["earlier_snapshots_read"]) == {"2026-11-03"}
    assert manifest["rows_jsonl_sha256"] == hashlib.sha256((s14 / "results" / "rows.jsonl").read_bytes()).hexdigest()
    for key, path in (("approved_sha256", s14 / "APPROVED"), ("trials_md_sha256", s14 / "trials.md"), ("events_csv_sha256", tmp_path / "events.csv")):
        assert manifest[key] == hashlib.sha256(path.read_bytes()).hexdigest()  # should-fix 9: the gates and the exclusion input
    deltas = (run_dir / "deltas.csv").read_text(encoding="utf-8").splitlines()
    assert deltas[0].startswith("trial,row,n,") and len(deltas) == 1 + 9
    verdict = (run_dir / "verdict.md").read_text(encoding="utf-8")
    assert "h = 24 h" in verdict and "h = 168 h" in verdict and "tick-floored share" in verdict and "Sports share" in verdict
    assert "G = 240 (longshot 120, central 120)" in verdict
    assert an.LOW_POWER_LABEL not in s["verdict"]["M1"] or s["low_power"]


def test_before_and_after_D_split_boundary(tmp_path: Path):
    ms = _markets()
    for m in ms[:20]:
        m["snapshot"] = "2026-11-16"  # the day before D: before_D
    for m in ms[20:40]:
        m["snapshot"] = "2026-11-17"  # D itself: after_D ("dated before 2026-11-17" is strict)
    s13 = _build_013(tmp_path, ms)
    s14 = _build_014(tmp_path)
    s = _run(tmp_path, s14, s13)
    assert s["before_after_D_M1"]["before_D"]["n"] == 20 and s["before_after_D_M1"]["after_D"]["n"] == 420
    manifest = json.loads((s14 / "results" / "input_manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["snapshots_read"]) == {"2026-11-16", "2026-11-17", SNAP}


def test_main_refuses_on_an_empty_folder_and_writes_nothing(tmp_path: Path, capsys):
    s14 = tmp_path / "014"
    s14.mkdir()
    rc = run.main(["--study-dir", str(s14), "--study-013-dir", str(tmp_path / "013"), "--events-csv", str(tmp_path / "e.csv")])
    assert rc == 1 and "refused: no non-empty APPROVED" in capsys.readouterr().out
    assert list(s14.iterdir()) == []
