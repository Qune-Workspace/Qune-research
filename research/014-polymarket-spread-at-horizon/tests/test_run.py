"""§6.5 tests of the analysis run on synthetic Study 013 folders: the refusals in order with nothing written, the
§5.4 halts on synthetic counts, the followed-event exclusion by any event id, and an end-to-end run that writes
aggregates only."""

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from src import analysis as an
from src import run
from src.reader import Refusal

RUN_DATE = dt.date(2027, 1, 21)
SNAP = "2026-11-20"
S_SHA_COLUMNS = "snapshot_date,started_utc,finished_utc,pages,rows,distinct_markets,bytes,records_sha256,pages_sha256"


def _build_013(root: Path, markets: list[dict], *, price_pass=True, stopped=False, extra_snapshot_rows: dict[str, list[dict]] | None = None) -> Path:
    """A synthetic Study 013 folder: sample.jsonl (C1 rows, C1a = non-Sports rows, C1b = the same rows), its manifest,
    its data-step report, one snapshot of record and the snapshot log."""
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
    (s13 / "results" / "data_step.json").write_text(json.dumps({"stopped_for_amendment": stopped, "halted": False,
                                                                 "price_field_check": {"pass": price_pass, "rows": 10}}), encoding="utf-8")
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


def test_refusals_in_order_and_nothing_written(tmp_path: Path):
    s13 = _build_013(tmp_path, _markets(30, 30))
    s14 = _build_014(tmp_path, approved=False)
    with pytest.raises(Refusal, match="APPROVED"):
        _run(tmp_path, s14, s13)
    (s14 / "APPROVED").write_text("yes\n", encoding="utf-8")
    (s14 / "results" / "run").mkdir(parents=True)
    with pytest.raises(Refusal, match="executed once"):
        _run(tmp_path, s14, s13)
    (s14 / "results" / "run").rmdir()
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
    p.write_text(p.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(Refusal, match="hashes to"):
        _run(tmp_path, s14, s13)
    assert not (s14 / "results" / "run").exists() and not (s14 / "results" / "input_manifest.json").exists()
    assert not (s14 / "results" / "rows.jsonl").exists()


def test_halts_on_synthetic_counts(tmp_path: Path):
    # too few clusters and markets: halted at the analysis run, verdict written, no Delta, runs once
    s13 = _build_013(tmp_path, _markets(30, 30, clusters=5))
    s14 = _build_014(tmp_path)
    s = _run(tmp_path, s14, s13)
    assert s["halted"] and s["verdict"]["M1"] == "inconclusive (halted at the analysis run)"
    assert any("clusters" in r for r in s["halt_reasons"]) and any("longshot bin" in r for r in s["halt_reasons"])
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


def test_end_to_end_fit_counts_and_no_per_market_row(tmp_path: Path):
    ms = _markets()
    ms[5]["tick"] = None  # a null tick
    ms[6]["tick"] = 0.0001  # a tick below 0.001
    ms[7]["bid"] = ms[7]["ask"] = 0.05  # a locked book
    ms[7]["price"] = 0.05
    ms.append({"id": "H1", "cluster": "h", "bid": 0.94, "ask": 0.96})  # the high bin: outside the decision bins
    ms.append({"id": "X1", "cluster": "x", "bid": 0.24, "ask": 0.26})  # outside every named bin
    s13 = _build_013(tmp_path, ms, extra_snapshot_rows={"2026-11-03": [{"id": "L0", "endDate": "moved", "lastTradePrice": 1}]})
    s14 = _build_014(tmp_path)
    s = _run(tmp_path, s14, s13)
    assert not s["halted"]
    m1 = s["fits"]["M1"]["W"]
    assert m1["fitted"] and m1["n_longshot"] == 220 and m1["n_central"] == 220 and m1["G"] == 240
    assert m1["delta"] > 0.59 and m1["boot_available"] and m1["boot_low"] < m1["delta"] < m1["boot_high"]
    assert m1["power"]["ratio"] == pytest.approx(2.842 * m1["se_cl"] / 1.18)
    assert s["criteria"]["M1"]["C1"] and s["verdict"]["M1"].startswith(("supported in one forward window", "inconclusive (fragile"))
    assert s["fits"]["M1"]["W1"]["n"] + s["fits"]["M1"]["W2"]["n"] == 440
    assert s["fits"]["M1a"]["W"]["n"] < 440 and s["fits"]["M1b"]["W"]["n"] == 440
    ex = s["exclusions"]["M1"]
    assert ex["null_tick"] == 1 and ex["tick_below_0.001"] == 1 and ex["locked_book"] == 1 and ex["outside_decision_bins"] == 2
    assert s["programme_count"] == 40 and s["bars"]["N_3"] == 2.128 and s["bars"]["N_13"] == pytest.approx(2.665, abs=0.001)
    assert len(s["deciles_M1"]) == 10 and s["deciles_M1"][2]["suppressed"] and not s["deciles_M1"][0]["suppressed"]
    central = s["secondary_reading_M1"]["central"]
    assert central["wa26_compression_points"] < 0.3  # the slope's compression at a median mid near 0.50 is near 0
    assert central["wa26_at_named_prices"]["0.60"] == pytest.approx(1.1, abs=0.1)
    assert central["wa26_at_named_prices"]["0.05"] == pytest.approx(1.4, abs=0.1)
    assert central["cr26_clears_half_spread"] is True and isinstance(central["wa26_clears_half_spread"], bool)
    assert s["secondary_reading_M1"]["high"]["suppressed"]
    # the first snapshot dated on or after S that lists a market may be its snapshot of record (then its end is unmoved);
    # L0 is listed on 2026-11-03 with another endDate, so it alone counts as moved
    assert s["moved_end_M1"]["longshot"] == {"n": 220, "with_first_listing": 220, "moved": 1}
    assert s["moved_end_M1"]["central"]["moved"] == 0
    assert s["null_tick_0.01_M1"]["fitted"] and s["before_after_D_M1"]["after_D"]["n"] == 440  # n counts the two decision bins
    assert s["before_after_D_M1"]["before_D"]["n"] == 0 and not s["before_after_D_M1"]["before_D"]["fitted"]
    assert 0 < s["early_split_M1"]["early_share"] < 1
    # outputs: aggregates only; the per-market rows sit in the git-ignored rows.jsonl, hashed in the manifest
    run_dir = s14 / "results" / "run"
    assert {p.name for p in run_dir.iterdir()} == {"summary.json", "verdict.md", "deltas.csv", "deciles.csv"}
    for p in run_dir.iterdir():
        text = p.read_text(encoding="utf-8")
        assert "L17" not in text and "C17" not in text, p.name
    manifest = json.loads((s14 / "results" / "input_manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["snapshots_read"]) == {SNAP} and "2026-11-03" in manifest["earlier_snapshots_read"]
    assert manifest["rows_jsonl_sha256"] == hashlib.sha256((s14 / "results" / "rows.jsonl").read_bytes()).hexdigest()
    deltas = (run_dir / "deltas.csv").read_text(encoding="utf-8").splitlines()
    assert deltas[0].startswith("trial,row,n,") and len(deltas) == 1 + 9
    verdict = (run_dir / "verdict.md").read_text(encoding="utf-8")
    assert "h = 24 h" in verdict and "h = 168 h" in verdict and "tick-floored share" in verdict and "Sports share" in verdict
    assert an.LOW_POWER_LABEL not in s["verdict"]["M1"] or s["low_power"]


def test_main_refuses_on_an_empty_folder_and_writes_nothing(tmp_path: Path, capsys):
    s14 = tmp_path / "014"
    s14.mkdir()
    rc = run.main(["--study-dir", str(s14), "--study-013-dir", str(tmp_path / "013"), "--events-csv", str(tmp_path / "e.csv")])
    assert rc == 1 and "refused: no non-empty APPROVED" in capsys.readouterr().out
    assert list(s14.iterdir()) == []
