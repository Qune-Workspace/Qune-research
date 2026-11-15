"""A candidate held to the inputs it names (2026-11-15 00:15Z, predictions/POST_MORTEMS.md
"A record held to nothing but itself"): on 6b7a0b4 the row was held to the candidate
(`figures-from-tool`) and the candidate to nothing, so a candidate line carrying a
figure the printer never computed was admitted with rc 0 on a scratch copy of the
13 November record.  Now `barrier.recompute_candidate` re-reads the kept download
and the calibration file the candidate names by hash, re-runs the method on the
candidate's month, leg and window, and `readings.py add` refuses the row on any
difference (`figures-recompute`); `barrier.py --recompute <id>` prints the same
answer by hand."""
import json
from datetime import UTC, datetime
from pathlib import Path

import barrier as B
import pm_lib as L
import readings as R
from test_barrier import calibration, csv_text, series
from test_readings import QUOTE, ns, write_manifest

COMPUTED = datetime(2026, 11, 20, 6, 20, tzinfo=UTC)
LATE_QUOTE = dict(QUOTE, fetched_utc="2026-11-20T06:17:00Z", gamma_sha256="ba" * 32, rules_window="month")
LATE_NOW = datetime(2026, 11, 20, 6, 30, tzinfo=UTC)


def kept(tmp_path: Path, r2: bool = False, window_from: dict | None = None) -> tuple[list[dict], Path, Path, Path]:
    """A fetched run into tmp_path/data: the kept download, the calibration file, one candidate for the
    75,000 down leg against a mid of 0.925.  Returns (candidates, raw_dir, calibration path, candidates path)."""
    body = csv_text(series(120)).encode()
    data = tmp_path / "data"
    data.mkdir(parents=True, exist_ok=True)
    cal = data / "calibration.json"
    cal.write_text(json.dumps(calibration(r2)))
    raw_dir, cands = data / "raw" / "fred", data / "candidates.jsonl"
    rc = B.run("2026-11", [(75_000.0, "down")], {75_000.0: 0.925}, lambda url: body, None, raw_dir,
               data / "fred_manifest.json", dry_run=False, show_level=False, now=lambda: COMPUTED,
               calibration=cal, window_from=window_from, candidates=cands)
    assert rc == 0
    return L.read_candidates(cands), raw_dir, cal, cands


def rewrite(cands: Path, records: list[dict]) -> None:
    cands.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records), encoding="utf-8")


# --- the candidate names what it was computed from -----------------------------------------------

def test_the_candidate_names_the_calibration_it_read_and_none_when_there_was_none(tmp_path):
    got, raw_dir, cal, _ = kept(tmp_path)
    assert got[0]["inputs"]["calibration_sha256"] == B.file_sha256(cal)
    assert got[0]["inputs"]["series_sha256"] == B.sha256(next(raw_dir.glob("*/CBBTCUSD.csv")).read_bytes())
    body = csv_text(series(120)).encode()
    cands = tmp_path / "none" / "c.jsonl"
    rc = B.run("2026-11", [(75_000.0, "down")], {75_000.0: 0.925}, lambda url: body, None, tmp_path / "none" / "raw",
               tmp_path / "none" / "m.json", dry_run=False, show_level=False, now=lambda: COMPUTED,
               calibration=tmp_path / "none" / "absent.json", candidates=cands)
    assert rc == 0
    c = L.read_candidates(cands)[0]
    assert c["inputs"]["calibration_sha256"] is None and c["climatology_p"] is None


# --- the figures recompute from the kept inputs, and a difference is named ------------------------

def test_a_candidate_reproduces_from_its_kept_inputs_and_the_cli_says_so(tmp_path, capsys):
    got, raw_dir, cal, cands = kept(tmp_path)
    assert B.recompute_candidate(got[0], raw_dir, cal) == []
    capsys.readouterr()
    rc = B.main(["--recompute", got[0]["id"], "--candidates", str(cands), "--raw-dir", str(raw_dir), "--calibration", str(cal)])
    out = capsys.readouterr().out
    assert rc == 0 and out.startswith(f"recompute {got[0]['id']}: the four figures reproduce from {raw_dir}")
    assert got[0]["inputs"]["series_sha256"][:12] in out and got[0]["inputs"]["calibration_sha256"][:12] in out


def test_a_candidate_with_a_creation_window_reproduces_with_it(tmp_path):
    opens = datetime(2026, 11, 2, 17, 17, tzinfo=UTC)
    got, raw_dir, cal, _ = kept(tmp_path, window_from={75_000.0: opens})
    assert got[0]["window_from_utc"] == "2026-11-02T17:17:00Z"
    assert B.recompute_candidate(got[0], raw_dir, cal) == []
    # the same record with its window dropped is another computation: the whole month is scanned for a touch
    without = dict(got[0], window_from_utc="")
    diffs = B.recompute_candidate(without, raw_dir, cal)
    assert diffs == [] or all("recomputed from" in d for d in diffs)  # equal only if no close crossed before the window


def test_a_figure_the_printer_never_computed_is_a_difference(tmp_path, capsys):
    got, raw_dir, cal, cands = kept(tmp_path)
    bad = dict(got[0], method_p="0.760", range_lo="0.760", range_hi="0.760")
    diffs = B.recompute_candidate(bad, raw_dir, cal)
    assert [d.split(" ")[0] for d in diffs] == ["method_p", "range_lo", "range_hi"]
    assert f"method_p '0.760' on the record, '{got[0]['method_p']}' recomputed from" in diffs[0]
    rewrite(cands, [bad])
    capsys.readouterr()
    rc = B.main(["--recompute", bad["id"], "--candidates", str(cands), "--raw-dir", str(raw_dir), "--calibration", str(cal)])
    out = capsys.readouterr().out
    assert rc == 1 and out.startswith(f"recompute {bad['id']}: DIFFERS\n  method_p '0.760'")


def test_a_missing_download_a_changed_calibration_and_a_wrong_input_date_are_differences(tmp_path):
    got, raw_dir, cal, _ = kept(tmp_path)
    for p in raw_dir.glob("*/CBBTCUSD.csv"):
        p.unlink()
    diffs = B.recompute_candidate(got[0], raw_dir, cal)
    assert len(diffs) == 1 and diffs[0].startswith(f"no kept download under {raw_dir} has sha256 {got[0]['inputs']['series_sha256'][:12]}")
    got, raw_dir, cal, _ = kept(tmp_path / "again")
    cal.write_text(json.dumps(calibration(True)))  # re-calibrated after the candidate: the climatology is another file's
    diffs = B.recompute_candidate(got[0], raw_dir, cal)
    assert len(diffs) == 1 and diffs[0].startswith(f"the calibration file is {B.file_sha256(cal)[:12]} and the candidate was read under "
                                                   f"{got[0]['inputs']['calibration_sha256'][:12]}")
    cal.write_text(json.dumps(calibration(False)))
    wrong = dict(got[0], inputs=dict(got[0]["inputs"], spot_date="2026-11-02"))
    diffs = B.recompute_candidate(wrong, raw_dir, cal)
    assert diffs == [f"inputs.spot_date '2026-11-02' on the record, '{got[0]['inputs']['spot_date']}' in the kept download"]
    assert B.recompute_candidate(dict(got[0], key="hike"), raw_dir, cal)[0].startswith("key 'hike'")


def test_the_cli_refuses_an_unknown_id_and_a_bills_candidate(tmp_path, capsys):
    got, raw_dir, cal, cands = kept(tmp_path)
    bills = L.candidate_record("fomc_bills", "hike", 0.6, 0.5, 0.7, 0.23, 0.635, COMPUTED, {"meeting": "2026-12-09"})
    rewrite(cands, got + [bills])
    capsys.readouterr()
    assert B.main(["--recompute", "K-x", "--candidates", str(cands), "--raw-dir", str(raw_dir), "--calibration", str(cal)]) == 1
    assert "K-x: not on" in capsys.readouterr().out
    assert B.main(["--recompute", bills["id"], "--candidates", str(cands), "--raw-dir", str(raw_dir), "--calibration", str(cal)]) == 1
    assert "a fomc_bills candidate; this tool recomputes btc_touch only" in capsys.readouterr().out
    assert B.main(["--mid", "75000:0.9"]) == 2  # neither a run nor a recomputation
    assert "--month and at least one --barrier are needed" in capsys.readouterr().out


# --- at admission: readings.py add holds the candidate to its inputs -------------------------------

def admission(tmp_path: Path) -> tuple[list[dict], Path, Path, Path]:
    """write_manifest's quotes and history, then the kept run's calibration file put on record after
    write_manifest's rules-only one, so the gate's `calibration-on-record` sees the file the candidate read."""
    manifest = write_manifest(tmp_path, [QUOTE, LATE_QUOTE])
    got, raw_dir, cal, cands = kept(tmp_path)
    assert R.record_calibration("btc_touch", "test", tmp_path, datetime(2026, 11, 5, 12, 1, tzinfo=UTC)) == 0
    return got, manifest, cands, raw_dir


def test_add_refuses_a_candidate_whose_figures_do_not_recompute_and_admits_one_that_does(tmp_path, capsys):
    got, manifest, cands, raw_dir = admission(tmp_path)
    c = got[0]
    # the demonstration of 6b7a0b4: a record whose shape is right and whose figure the printer never computed
    bad = dict(c, id=c["id"].replace("T062000Z", "T062001Z"), computed_utc="2026-11-20T06:20:01Z",
               method_p="0.760", range_lo="0.760", range_hi="0.760")
    L.append_candidate(cands, bad)
    args = ns(quote=LATE_QUOTE["fetched_utc"], method_p=None, range_lo=None, range_hi=None, climatology_p=None, candidate=bad["id"])
    assert R.add(args, manifest, tmp_path / "r1.csv", LATE_NOW, candidates=cands) == 1
    out = capsys.readouterr().out
    assert f"[reading:figures-recompute] candidate {bad['id']}: method_p '0.760' on the record, '{c['method_p']}' recomputed from" in out
    assert not (tmp_path / "r1.csv").exists()
    # the honest record is admitted and the tool says what it checked
    args = ns(quote=LATE_QUOTE["fetched_utc"], method_p=None, range_lo=None, range_hi=None, climatology_p=None, candidate=c["id"])
    assert R.add(args, manifest, tmp_path / "r2.csv", LATE_NOW, candidates=cands) == 0
    out = capsys.readouterr().out
    assert f"ADMITTED R-2026-11-20-btc_touch-6507380: method_p={c['method_p']}" in out
    assert f"recomputed: the four figures of {c['id']} reproduce from the kept inputs it names" in out
    # the kept download gone before admission: refused, the row is not written
    for p in raw_dir.glob("*/CBBTCUSD.csv"):
        p.unlink()
    assert R.add(args, manifest, tmp_path / "r3.csv", LATE_NOW, candidates=cands) == 1
    out = capsys.readouterr().out
    assert "[reading:figures-recompute]" in out and "no kept download" in out
    assert not (tmp_path / "r3.csv").exists()


def test_a_method_without_a_recomputer_is_admitted_on_its_record_and_the_tool_says_so(tmp_path, capsys):
    manifest = write_manifest(tmp_path, [QUOTE, LATE_QUOTE])
    cands = tmp_path / "data" / "candidates.jsonl"
    bills = L.candidate_record("fomc_bills", "hike", 0.6, 0.5, 0.7, 0.23, 0.925, COMPUTED, {"meeting": "2026-12-09"})
    L.append_candidate(cands, bills)
    assert R.recomputer_for("fomc_bills", tmp_path) is None and R.recomputer_for("btc_touch", tmp_path) is not None
    args = ns(quote=LATE_QUOTE["fetched_utc"], method="fomc_bills", method_p=None, range_lo=None, range_hi=None,
              climatology_p=None, candidate=bills["id"], proposition="Hike of 25 bp on 9 December")
    assert R.add(args, manifest, tmp_path / "r.csv", LATE_NOW, candidates=cands) == 0
    out = capsys.readouterr().out
    assert "not recomputed: no recomputer for fomc_bills yet" in out and "ADMITTED" in out and "recomputed: the four" not in out


def test_the_library_applies_nothing_without_a_recomputer_or_a_single_candidate():
    c = L.candidate_record("btc_touch", "75000:down", 0.876, 0.876, 0.886, 0.690, 0.925, COMPUTED, {"series": "CBBTCUSD"})
    row = {"candidate_id": c["id"]}
    assert L.figures_recompute_violations(row, [c], None) == []
    assert L.figures_recompute_violations({"candidate_id": ""}, [c], lambda x: ["d"]) == []
    assert L.figures_recompute_violations(row, [c, c], lambda x: ["d"]) == []
    assert L.figures_recompute_violations(row, [c], lambda x: None) == []
    assert L.figures_recompute_violations(row, [c], lambda x: ["d1", "d2"]) == [
        f"[reading:figures-recompute] candidate {c['id']}: d1", f"[reading:figures-recompute] candidate {c['id']}: d2"]
