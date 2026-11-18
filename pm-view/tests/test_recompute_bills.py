"""A fomc_bills candidate held to the inputs it names (2026-11-15 06:15Z, predictions/POST_MORTEMS.md
"A record held to nothing but itself", follow-up): the 00:15Z run held a btc_touch candidate to its
kept download and calibration and left the bill reading admitted on its record alone.  Shown on
aff9c27 before this change, on a scratch copy of the 13 November record: a bill candidate carrying
0.760 in the three figure fields, and one carrying a false as-of date, were both ADMITTED at dry-run
with rc 0.  Now `fomc_calibrate.recompute_candidate` re-reads the kept folder the candidate names
(each file's bytes held to the candidate's hash), the calibration file it names by hash, re-runs the
reading for the candidate's meeting as of its date, and `readings.py add` refuses the row on any
difference (`figures-recompute`); `fomc_calibrate.py --recompute <id>` prints the same answer by hand."""
import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import fomc_calibrate as F
import pm_lib as L
import readings as R
from test_fetch_folders import kept, manifest_of, record, sha
from test_readings import QUOTE, ns, write_manifest

MEETING, AS_OF = "2026-12-09", "2026-11-04"
COMPUTED = datetime(2026, 11, 20, 6, 20, tzinfo=UTC)
LATE_QUOTE = dict(QUOTE, fetched_utc="2026-11-20T06:17:00Z", gamma_sha256="ba" * 32, rules_window="month",
                  market_id="3215008", condition_id="0x8a41", yes_token_id="1116", end_date="2026-12-09T23:59:00Z",
                  question="Will the Fed hike by 25 bp on 9 December?")
LATE_NOW = datetime(2026, 11, 20, 6, 30, tzinfo=UTC)


def kept_bills(tmp_path: Path, mids: dict[str, float] | None = None, name: str = "2026-11-13T061841Z",
               calibration_now: datetime = datetime(2026, 11, 5, 12, 1, tzinfo=UTC)) -> tuple[list[dict], Path, Path, Path, Path]:
    """A synthetic history kept as one fetch folder, the calibration written from it (and put on record by the
    run itself), then one candidate per class written as `--live` writes them, computed at COMPUTED.  Returns
    (candidates, raw root, kept folder, calibration path, candidates path)."""
    root, folder, meetings = kept(tmp_path, name)
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    manifest, cal, cands = tmp_path / "m.json", data / "fomc_calibration.json", data / "candidates.jsonl"
    assert F.run(folder, manifest, cal, fetch=False, now=calibration_now) == 0
    mids = mids or {"hike": 0.635, "none": 0.325}
    for c in F.live_candidates(F.load_dir(folder), meetings, date.fromisoformat(MEETING), date.fromisoformat(AS_OF),
                               F.load_calibration(cal), mids, folder, COMPUTED, calibration=cal):
        L.append_candidate(cands, c)
    return L.read_candidates(cands), root, folder, cal, cands


def rewrite(cands: Path, records: list[dict]) -> None:
    cands.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records), encoding="utf-8")


def recompute_argv(cid: str, cands: Path, root: Path, cal: Path) -> list[str]:
    return ["--recompute", cid, "--candidates", str(cands), "--raw-root", str(root), "--out", str(cal),
            "--manifest", str(root.parent / "m.json")]


# --- the candidate names what it was computed from -----------------------------------------------

def test_the_candidate_names_the_calibration_it_read_and_none_when_there_was_none(tmp_path, capsys):
    got, root, folder, cal, _ = kept_bills(tmp_path)
    assert [c["key"] for c in got] == ["hike", "none"]
    assert all(c["inputs"]["calibration_sha256"] == sha(cal) for c in got)
    assert all(c["inputs"]["input_folder"] == folder.name and c["inputs"]["as_of"] == AS_OF for c in got)
    # the CLI passes the calibration file it read to the writer
    cands = tmp_path / "cli" / "c.jsonl"
    rc = F.main(["--live", MEETING, "--today", AS_OF, "--from-dir", str(folder), "--raw-root", str(root), "--manifest", str(tmp_path / "m.json"),
                 "--out", str(cal), "--candidates", str(cands), "--mid", "hike=0.635"])
    capsys.readouterr()
    assert rc == 0
    c = L.read_candidates(cands)[0]
    assert c["inputs"]["calibration_sha256"] == sha(cal) and F.recompute_candidate(c, root, cal, manifest=manifest_of(root)) == []
    # no calibration file: the candidate says so and carries no climatology
    cands = tmp_path / "none" / "c.jsonl"
    rc = F.main(["--live", MEETING, "--today", AS_OF, "--from-dir", str(folder), "--raw-root", str(root), "--manifest", str(tmp_path / "m.json"),
                 "--out", str(tmp_path / "none" / "absent.json"), "--candidates", str(cands), "--mid", "hike=0.6"])
    capsys.readouterr()
    assert rc == 0
    c = L.read_candidates(cands)[0]
    assert c["inputs"]["calibration_sha256"] is None and c["climatology_p"] is None
    assert F.recompute_candidate(c, root, tmp_path / "none" / "absent.json", manifest=manifest_of(root)) == []


# --- the figures recompute from the kept inputs, and a difference is named ------------------------

def test_a_candidate_reproduces_from_its_kept_inputs_and_the_cli_says_so(tmp_path, capsys):
    got, root, folder, cal, cands = kept_bills(tmp_path)
    for c in got:
        assert F.recompute_candidate(c, root, cal, manifest=manifest_of(root)) == []
    capsys.readouterr()
    rc = F.main(recompute_argv(got[0]["id"], cands, root, cal))
    out = capsys.readouterr().out
    assert rc == 0 and out.startswith(f"recompute {got[0]['id']}: the four figures reproduce from {folder}")
    assert got[0]["inputs"]["input_sha256"]["DTB3"][:12] in out and sha(cal)[:12] in out and f"as of {AS_OF}" in out


def test_a_figure_the_printer_never_computed_is_a_difference(tmp_path, capsys):
    got, root, folder, cal, cands = kept_bills(tmp_path)
    bad = dict(got[0], method_p="0.760", range_lo="0.760", range_hi="0.760")
    diffs = F.recompute_candidate(bad, root, cal, manifest=manifest_of(root))
    assert [d.split(" ")[0] for d in diffs] == ["method_p", "range_lo", "range_hi"]
    assert f"method_p '0.760' on the record, '{got[0]['method_p']}' recomputed from {folder.name} as of {AS_OF}" == diffs[0]
    rewrite(cands, [bad])
    capsys.readouterr()
    rc = F.main(recompute_argv(bad["id"], cands, root, cal))
    out = capsys.readouterr().out
    assert rc == 1 and out.startswith(f"recompute {bad['id']}: DIFFERS\n  method_p '0.760'")


def test_a_false_as_of_date_is_a_difference(tmp_path):
    """The second line admitted on aff9c27: the same figures claimed as of another day.  The prints the reading
    was taken from are dated, so the record disagrees with the kept folder even where the figures happen to agree."""
    got, root, folder, cal, _ = kept_bills(tmp_path)
    moved = dict(got[0], inputs=dict(got[0]["inputs"], as_of="2026-11-02"))
    diffs = F.recompute_candidate(moved, root, cal, manifest=manifest_of(root))
    assert diffs and any(d.startswith("inputs.prints ") and "in the kept folder as of 2026-11-02" in d for d in diffs)
    assert any(d.startswith("inputs.days_to_meeting ") for d in diffs)


def test_a_missing_folder_changed_bytes_a_changed_calibration_and_a_wrong_key_are_differences(tmp_path):
    got, root, folder, cal, _ = kept_bills(tmp_path)
    c = got[0]
    # the folder gone, or named by a name that is not a kept fetch
    elsewhere = dict(c, inputs=dict(c["inputs"], input_folder="2026-11-20T061800Z"))
    diffs = F.recompute_candidate(elsewhere, root, cal, manifest=manifest_of(root))
    assert diffs == [f"no kept folder 2026-11-20T061800Z under {root} holding the four series the manifest recorded: "
                     "the bytes the figures were read from cannot be re-read"]
    # the folder present with other bytes but no fetch recorded it (2026-11-15 12:15Z): not a kept fetch, and the
    # refusal says which file the manifest never saw
    other = root / "2026-11-20T061800Z"
    shutil.copytree(folder, other)
    with (other / "fred_DTB3.csv").open("a", encoding="utf-8") as fh:
        fh.write("2026-11-10,3.99\n")
    moved = dict(c, inputs=dict(c["inputs"], input_folder=other.name))
    diffs = F.recompute_candidate(moved, root, cal, manifest=manifest_of(root))
    assert len(diffs) == 1 and diffs[0].startswith(f"no kept folder {other.name} under {root} holding the four series the manifest recorded")
    assert "fred_DTB3.csv (" in diffs[0] and "has no entry under 2026-11-20T061800Z/ on the manifest: no fetch recorded it" in diffs[0]
    # the same folder recorded by a fetch: a kept fetch whose bytes are not the candidate's; nothing is recomputed from other bytes
    record(root.parent / "m.json", other, "2026-11-20T06:18:01Z")
    diffs = F.recompute_candidate(moved, root, cal, manifest=manifest_of(root))
    assert len(diffs) == 1 and diffs[0].startswith(f"fred_DTB3.csv in {other.name} is {sha(other / 'fred_DTB3.csv')[:12]}, the candidate was read from "
                                                   f"{c['inputs']['input_sha256']['DTB3'][:12]}")
    # the calibration re-written after the candidate: the climatology is another file's; the figures still recompute
    body = json.loads(cal.read_text(encoding="utf-8"))
    body["note"] = "re-written"
    cal.write_text(json.dumps(body), encoding="utf-8")
    diffs = F.recompute_candidate(c, root, cal, manifest=manifest_of(root))
    assert len(diffs) == 1 and diffs[0].startswith(f"the calibration file is {sha(cal)[:12]} and the candidate was read under "
                                                   f"{c['inputs']['calibration_sha256'][:12]}")
    bad_under_other_cal = dict(c, method_p="0.760", range_lo="0.760", range_hi="0.760")
    diffs = F.recompute_candidate(bad_under_other_cal, root, cal, manifest=manifest_of(root))
    assert [d.split(" ")[0] for d in diffs] == ["the", "method_p", "range_lo", "range_hi"]
    # a key that is not a class, a method that is not this one, a date that is not one
    assert F.recompute_candidate(dict(c, key="75000:down"), root, cal, manifest=manifest_of(root))[0].startswith("key '75000:down' is not a fomc_bills class")
    assert F.recompute_candidate(dict(c, method="btc_touch"), root, cal, manifest=manifest_of(root)) == ["a btc_touch candidate; this tool recomputes fomc_bills only"]
    assert F.recompute_candidate(dict(c, inputs=dict(c["inputs"], as_of="soon")), root, cal, manifest=manifest_of(root))[0].startswith("inputs.meeting '2026-12-09' or inputs.as_of 'soon' is not a date")


def test_a_reading_that_stops_early_is_a_difference(tmp_path):
    got, root, folder, cal, _ = kept_bills(tmp_path)
    late = dict(got[0], inputs=dict(got[0]["inputs"], as_of="2026-12-10"))  # the meeting is not after the as-of date
    diffs = F.recompute_candidate(late, root, cal, manifest=manifest_of(root))
    assert diffs == [f"no reading recomputes for {date.fromisoformat(MEETING)} as of 2026-12-10 from {folder.name}: meeting 2026-12-09 is not after 2026-12-10"]


def test_the_cli_refuses_an_unknown_id_a_touch_candidate_and_a_recompute_with_live_or_fetch(tmp_path, capsys):
    got, root, folder, cal, cands = kept_bills(tmp_path)
    touch = L.candidate_record("btc_touch", "75000:down", 0.6, 0.5, 0.7, 0.23, 0.635, COMPUTED, {"month": "2026-11"})
    rewrite(cands, got + [touch])
    capsys.readouterr()
    assert F.main(recompute_argv("K-x", cands, root, cal)) == 1
    assert "K-x: not on" in capsys.readouterr().out
    assert F.main(recompute_argv(touch["id"], cands, root, cal)) == 1
    assert "a btc_touch candidate; this tool recomputes fomc_bills only" in capsys.readouterr().out
    for extra in (["--live", MEETING], ["--fetch"]):
        try:
            F.main(recompute_argv(got[0]["id"], cands, root, cal) + extra)
        except SystemExit as e:
            assert e.code == 2
        else:
            raise AssertionError(f"--recompute with {extra} was admitted")


# --- at admission: readings.py add holds the candidate to its inputs -------------------------------

def admission(tmp_path: Path) -> tuple[list[dict], Path, Path, Path]:
    """write_manifest's quotes and its rules-only calibration files on record, then the kept run's real
    calibration written and put on record after them (by the run itself), so `calibration-on-record` sees the
    file the candidate read.  The candidates are read against the late quote's mid."""
    manifest = write_manifest(tmp_path, [QUOTE, LATE_QUOTE])
    got, root, _, _, cands = kept_bills(tmp_path, mids={"hike": LATE_QUOTE["market_mid"]})
    # readings.recomputer_for reads the kept folders under <here>/data/raw/fred_rates, as the tool does on this host
    here_root = tmp_path / "data" / "raw" / "fred_rates"
    here_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(root), str(here_root))
    # ... and the fetch manifest at <here>/data/fred_rates_manifest.json (2026-11-15 12:15Z: a folder is a kept fetch
    # only when that manifest recorded it)
    shutil.copyfile(tmp_path / "m.json", tmp_path / "data" / "fred_rates_manifest.json")
    return got, manifest, cands, here_root


def test_add_refuses_a_candidate_whose_figures_do_not_recompute_and_admits_one_that_does(tmp_path, capsys):
    got, manifest, cands, root = admission(tmp_path)
    c = got[0]
    # the demonstration of aff9c27: a record whose shape is right and whose figure the printer never computed
    later = datetime(2026, 11, 20, 6, 20, 1, tzinfo=UTC)
    bad = dict(c, id=L.candidate_id("fomc_bills", "hike", later), computed_utc=later.strftime(L.UTC_STAMP_FORMAT),
               method_p="0.760", range_lo="0.760", range_hi="0.760")
    L.append_candidate(cands, bad)
    args = ns(quote=LATE_QUOTE["fetched_utc"], market_id=LATE_QUOTE["market_id"], method="fomc_bills", method_p=None, range_lo=None,
              range_hi=None, climatology_p=None, candidate=bad["id"], proposition="Hike of 25 bp on 9 December")
    assert R.add(args, manifest, tmp_path / "r1.csv", LATE_NOW, candidates=cands) == 1
    out = capsys.readouterr().out
    assert f"[reading:figures-recompute] candidate {bad['id']}: method_p '0.760' on the record, '{c['method_p']}' recomputed from" in out
    assert not (tmp_path / "r1.csv").exists()
    # the honest record is admitted and the tool says what it checked; nothing says "not recomputed" any more
    args = ns(quote=LATE_QUOTE["fetched_utc"], market_id=LATE_QUOTE["market_id"], method="fomc_bills", method_p=None, range_lo=None,
              range_hi=None, climatology_p=None, candidate=c["id"], proposition="Hike of 25 bp on 9 December")
    assert R.add(args, manifest, tmp_path / "r2.csv", LATE_NOW, candidates=cands) == 0
    out = capsys.readouterr().out
    assert f"ADMITTED R-2026-11-20-fomc_bills-{LATE_QUOTE['market_id']}: method_p={c['method_p']}" in out
    assert f"recomputed: the four figures of {c['id']} reproduce from the kept inputs it names" in out and "not recomputed" not in out
    # the kept folder gone before admission: refused, the row is not written
    shutil.rmtree(root / c["inputs"]["input_folder"])
    assert R.add(args, manifest, tmp_path / "r3.csv", LATE_NOW, candidates=cands) == 1
    out = capsys.readouterr().out
    assert "[reading:figures-recompute]" in out and "no kept folder" in out
    assert not (tmp_path / "r3.csv").exists()


# --- the meeting list is an input the record names (2026-11-16 12:15Z) ------------------------------
#
# predictions/POST_MORTEMS.md "A sample held by nothing but the file that listed it": on 1aac328, on a
# scratch worktree, the 2019 meetings cut from tools/fomc_statement_dates_2016_2026-09.txt gave a
# calibration on 66 meetings (net Brier 0.2650 where the committed file reads 0.2983 on 74) that was
# RECORDED with a source line naming the four series and no list, a candidate under it carried a
# climatology of 0.258 (17 of 66) and recomputed with rc 0 under the cut list and under the restored one,
# and a meeting typed in between made the recomputation blame "stale print, a meeting in between, or
# outside the bill's life" from the folder.  Now the list is on the calibration, its history line and
# every candidate, and compared before any figure is.

def cut_dates(tmp_path: Path, drop_prefix: str = "2019", add: str = "") -> Path:
    """A copy of the committed dates file with the lines starting `drop_prefix` cut and `add` appended."""
    kept_lines = [ln for ln in F.DATES_FILE.read_text(encoding="utf-8").splitlines(keepends=True) if not ln.startswith(drop_prefix)]
    out = tmp_path / f"dates_{drop_prefix or 'all'}_{len(add)}.txt"
    out.write_text("".join(kept_lines) + add, encoding="utf-8")
    return out


def test_the_candidate_names_the_meeting_list_and_a_changed_list_is_a_difference(tmp_path):
    got, root, folder, cal, _ = kept_bills(tmp_path)
    rec = F.meetings_record()
    assert rec["dates_file"] == "tools/fomc_statement_dates_2016_2026-09.txt" and rec["count"] == len(F.meeting_dates()) == 87
    assert rec["dates_sha256"] == sha(F.DATES_FILE) and rec["extra_meetings"] == ["2026-10-28", "2026-12-09"]
    assert all(c["inputs"]["meetings"] == rec for c in got)
    man = manifest_of(root)
    assert F.recompute_candidate(got[0], root, cal, manifest=man) == []
    # the 2019 meetings cut from a copy of the file: refused by name, before any figure is compared
    cut = cut_dates(tmp_path)
    assert len(F.meeting_dates(cut)) == 79
    diffs = F.recompute_candidate(got[0], root, cal, manifest=man, dates_path=cut)
    assert len(diffs) == 1 and diffs[0].startswith(f"the meeting list is {sha(cut)[:12]} + ['2026-10-28', '2026-12-09'] (79 meetings), "
                                                   f"the record was made under {rec['dates_sha256'][:12]}")
    assert diffs[0].endswith("(87): the meetings cannot be re-read")
    # a meeting typed in between the as-of date and the meeting: the same refusal, not the folder's
    typed = cut_dates(tmp_path, drop_prefix="zz", add="20261125\n")
    diffs = F.recompute_candidate(got[0], root, cal, manifest=man, dates_path=typed)
    assert len(diffs) == 1 and diffs[0].startswith("the meeting list is") and "stale print" not in diffs[0]
    # one extra date fewer, the file unchanged: refused too (the count and the extras are both compared)
    diffs = F.recompute_candidate(got[0], root, cal, manifest=man, extra=(date(2026, 10, 28),))
    assert len(diffs) == 1 and "+ ['2026-10-28'] (86 meetings)" in diffs[0]


def test_a_candidate_naming_no_meeting_list_is_refused_by_the_recomputation_and_at_admission(tmp_path, capsys):
    got, manifest, cands, root = admission(tmp_path)
    c = got[0]
    unnamed = dict(c, inputs={k: v for k, v in c["inputs"].items() if k != "meetings"})
    diffs = F.recompute_candidate(unnamed, root, tmp_path / "data" / "fomc_calibration.json", manifest=F.qdata.read_manifest(tmp_path / "data" / "fred_rates_manifest.json"))
    assert diffs == ["the record names no meeting list (inputs.meetings): the meetings the reading was made on cannot be re-read"]
    later = datetime(2026, 11, 20, 6, 20, 1, tzinfo=UTC)
    unnamed.update(id=L.candidate_id("fomc_bills", "hike", later), computed_utc=later.strftime(L.UTC_STAMP_FORMAT))
    L.append_candidate(cands, unnamed)
    args = ns(quote=LATE_QUOTE["fetched_utc"], market_id=LATE_QUOTE["market_id"], method="fomc_bills", method_p=None, range_lo=None,
              range_hi=None, climatology_p=None, candidate=unnamed["id"], proposition="Hike of 25 bp on 9 December")
    assert R.add(args, manifest, tmp_path / "r1.csv", LATE_NOW, candidates=cands) == 1
    out = capsys.readouterr().out
    assert f"[reading:figures-recompute] candidate {unnamed['id']}: the record names no meeting list" in out
    assert not (tmp_path / "r1.csv").exists()


def test_the_calibration_names_its_meeting_list_and_a_climatology_from_another_sample_is_a_difference(tmp_path, capsys):
    # the committed list: the calibration and its history line carry it
    got, root, folder, cal, _ = kept_bills(tmp_path)
    written = json.loads(cal.read_text(encoding="utf-8"))
    assert written["inputs_meetings"] == F.meetings_record()
    history = (cal.parent / "calibration_history.csv").read_text(encoding="utf-8")
    assert f"meetings {sha(F.DATES_FILE)[:12]} + 2 extra (87 dates); " in history and "meetings unnamed" not in history
    # the 2019 meetings cut: the calibration run on the cut list names the cut list, with fewer meetings scored
    cut = cut_dates(tmp_path)
    cal2 = tmp_path / "cut" / "fomc_calibration.json"
    assert F.run(folder, tmp_path / "m.json", cal2, fetch=False, now=datetime(2026, 11, 5, 12, 2, tzinfo=UTC), dates_path=cut) == 0
    out = capsys.readouterr().out
    assert f"meetings: 79 dates, {cut} {sha(cut)[:12]} + ['2026-10-28', '2026-12-09']" in out
    w2 = json.loads(cal2.read_text(encoding="utf-8"))
    assert w2["inputs_meetings"]["dates_sha256"] == sha(cut) and w2["inputs_meetings"]["count"] == 79
    assert w2["sample"]["scored_meetings"] < written["sample"]["scored_meetings"]
    assert f"meetings {sha(cut)[:12]} + 2 extra (79 dates); " in (cal2.parent / "calibration_history.csv").read_text(encoding="utf-8")
    # a candidate read on the committed list under the cut calibration: its climatology is another sample's
    meetings = F.meeting_dates()
    cands = [c for c in F.live_candidates(F.load_dir(folder), meetings, date.fromisoformat(MEETING), date.fromisoformat(AS_OF),
                                           F.load_calibration(cal2), {"hike": 0.635}, folder, COMPUTED, calibration=cal2)]
    assert cands[0]["inputs"]["meetings"] == F.meetings_record() and cands[0]["inputs"]["calibration_sha256"] == sha(cal2)
    diffs = F.recompute_candidate(cands[0], root, cal2, manifest=manifest_of(root))
    assert any(d.startswith(f"the calibration file was built on meeting list {sha(cut)[:12]} (79 meetings), the candidate was read under "
                            f"{sha(F.DATES_FILE)[:12]} (87): its climatology is another sample's") for d in diffs)
    # a calibration written before this date names no list: nothing is compared against it, and the candidate still recomputes
    body = json.loads(cal.read_text(encoding="utf-8"))
    del body["inputs_meetings"]
    cal.write_text(json.dumps(body, sort_keys=True), encoding="utf-8")
    old = dict(got[0], inputs=dict(got[0]["inputs"], calibration_sha256=sha(cal)))
    assert F.recompute_candidate(old, root, cal, manifest=manifest_of(root)) == []


# 2026-11-18 00:15Z (predictions/POST_MORTEMS.md, follow-up to "A sample held by nothing but the file that listed
# it"): the source check of the dates file against the Fed's pages (tools/fomc_calendar.py --check: 85 of 85 dates
# the same) found the 2027 calendar published and the list ending at 2026-12-09, and the rule above bound every
# record to the whole file's hash, so the first extension would have made every candidate and the calibration's
# own list unreadable.  A record now carries `through` and `dates_digest`, and a list that carries the same
# dates through `through` is the record's list.

def test_a_list_extended_past_the_record_is_the_same_list_and_a_date_before_its_end_is_not(tmp_path):
    got, root, folder, cal, _ = kept_bills(tmp_path)
    rec = F.meetings_record()
    assert rec["through"] == "2026-12-09" and rec["dates_digest"] == F.dates_digest(F.meeting_dates())
    assert all(c["inputs"]["meetings"]["through"] == "2026-12-09" for c in got)
    man = manifest_of(root)
    # the eight 2027 dates the Fed's calendar lists (read 2026-11-18, tentative) appended: the record reproduces
    extended = cut_dates(tmp_path, drop_prefix="zz", add="20270127\n20270317\n20270428\n20270609\n20270728\n20270915\n20271027\n20271117\n")
    assert len(F.meeting_dates(extended)) == 95 and sha(extended) != rec["dates_sha256"]
    assert F.recompute_candidate(got[0], root, cal, manifest=man, dates_path=extended) == []
    # the calibration's own list, written under the shorter file, is the extended list's through its last date
    written = json.loads(cal.read_text(encoding="utf-8"))
    have = F.meetings_record(extended)
    assert F.meetings_differ(written["inputs_meetings"], have, F.meeting_dates(extended)) is None
    # a 2019 date cut, or a date typed in before the record's last meeting: not the same list, extension or not
    cut_and_extended = cut_dates(tmp_path, drop_prefix="20190130", add="20270127\n")
    diffs = F.recompute_candidate(got[0], root, cal, manifest=man, dates_path=cut_and_extended)
    assert len(diffs) == 1 and diffs[0].startswith("the meeting list is") and diffs[0].endswith("(87): the meetings cannot be re-read")
    typed = cut_dates(tmp_path, drop_prefix="zz", add="20261125\n20270127\n")
    diffs = F.recompute_candidate(got[0], root, cal, manifest=man, dates_path=typed)
    assert len(diffs) == 1 and diffs[0].startswith("the meeting list is")
    # a record without the two fields (written between 16 and 18 November) keeps the whole-file rule
    old = dict(got[0], inputs=dict(got[0]["inputs"], meetings={k: v for k, v in rec.items() if k not in ("through", "dates_digest")}))
    assert F.recompute_candidate(old, root, cal, manifest=man) == []
    diffs = F.recompute_candidate(old, root, cal, manifest=man, dates_path=extended)
    assert len(diffs) == 1 and diffs[0].startswith("the meeting list is")
    # the digest is of the dates alone: the same dates under another header are the same list
    reheaded = tmp_path / "reheaded.txt"
    reheaded.write_text("# another header\n" + "\n".join(d.strftime("%Y%m%d") for d in F.meeting_dates() if d not in F.EXTRA_MEETINGS) + "\n",
                        encoding="utf-8")
    assert sha(reheaded) != rec["dates_sha256"] and F.recompute_candidate(got[0], root, cal, manifest=man, dates_path=reheaded) == []
