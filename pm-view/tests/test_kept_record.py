"""A kept folder is one the fetch recorded (2026-11-15 12:15Z, predictions/POST_MORTEMS.md "A kept folder
held to nothing but its name").  Until this date `fomc_calibrate.kept_folders` took any folder named by a
fetch time that held four files of the right names, whatever they held, and `--live` never opened the
fetch manifest: shown on 3a55eeb, on a scratch copy of the kept 13 November folder, a copy named
`2026-11-15T120000Z/` with its DTB3 prints since October lowered by 0.60 and no manifest entry was read
by default (`inputs:` named it), read 0.822 for the hike where the recorded bytes read 1.000, wrote a
candidate naming it, and `--recompute` found the four figures reproduced (rc 0); a copy with DTB3 cut
at half its bytes was read by default too and reported as a stale print.  Now a folder is a kept fetch
only when each of its four files hashes to the manifest's entry under `<folder>/<file>`; one that no
fetch recorded, or whose bytes are not the recorded ones, is set aside by name (printed beside the
folder read), refused under `--from-dir`, and refused at a candidate's recomputation and so at the
reading's admission."""
import shutil
from datetime import UTC, datetime
from pathlib import Path

import fomc_calibrate as F
import pm_lib as L
import readings as R
from test_fetch_folders import _Session, kept, manifest_of, record, sha, texts_of
from test_readings import ns
from test_recompute_bills import AS_OF, LATE_NOW, LATE_QUOTE, MEETING, admission, kept_bills

EDITED = "2026-11-15T120000Z"


def edited_copy(folder: Path, name: str = EDITED, by: float = -0.60) -> Path:
    """A copy of a kept folder, newer by name, with every DTB3 print moved by `by`; nothing records it."""
    other = folder.parent / name
    shutil.copytree(folder, other)
    p = other / "fred_DTB3.csv"
    lines = p.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines[1:], start=1):
        d, _, v = line.partition(",")
        if v.strip() not in ("", "."):
            lines[i] = f"{d},{float(v) + by:.2f}"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert sha(p) != sha(folder / "fred_DTB3.csv")
    return other


def live_argv(root: Path, cal: Path, cands: Path, *extra: str) -> list[str]:
    return ["--live", MEETING, "--today", AS_OF, "--mid", "hike=3215008:0.635", "--raw-root", str(root), "--manifest", str(root.parent / "m.json"),
            "--out", str(cal), "--candidates", str(cands), *extra]


# --- what counts as a kept fetch ---------------------------------------------------------------

def test_a_folder_is_a_kept_fetch_only_when_the_manifest_recorded_its_four_files(tmp_path):
    root, folder, _ = kept(tmp_path)
    man = manifest_of(root)
    assert F.folder_record_violations(folder, man) == [] and F.kept_folders(root, man) == [(datetime(2026, 11, 13, 6, 18, 41, tzinfo=UTC), folder)]
    # the same bytes with no record: not kept, and the reason names the file the manifest never saw
    empties: list[dict | None] = [{}, None]
    for empty in empties:
        assert F.kept_folders(root, empty) == []
        why = F.folder_record_violations(folder, empty)
        assert len(why) == 4 and all(f"fred_{k}.csv ({sha(folder / f'fred_{k}.csv')[:12]}) has no entry under {folder.name}/ on the manifest: "
                                     "no fetch recorded it" == w for k, w in zip(F.SERIES, why, strict=True))
    # a recorded folder whose bytes moved after the fetch: not kept, the recorded hash named beside the bytes'
    other = edited_copy(folder)
    record(tmp_path / "m.json", other, "2026-11-15T12:00:01Z")
    with (other / "fred_EFFR.csv").open("a", encoding="utf-8") as fh:
        fh.write("2026-11-12,3.90\n")
    man = manifest_of(root)
    assert F.folder_record_violations(other, man) == [f"fred_EFFR.csv is {sha(other / 'fred_EFFR.csv')[:12]}, the fetch recorded "
                                                      f"{man[f'{other.name}/fred_EFFR.csv']['sha256'][:12]}"]
    assert [p for _, p in F.kept_folders(root, man)] == [folder] and F.unrecorded_folders(root, man) == [(other, F.folder_record_violations(other, man))]
    # a file missing is said first, without reading the manifest for it
    (other / "fred_DTB3.csv").unlink()
    assert F.folder_record_violations(other, man)[0] == "fred_DTB3.csv missing"


def test_the_fetch_records_the_folder_it_writes_and_that_folder_is_kept(tmp_path):
    _, source, _ = kept(tmp_path)
    root, manifest = tmp_path / "root", tmp_path / "fetched.json"
    folder = F.fetch_all(root, manifest, datetime(2026, 11, 20, 6, 18, 0, tzinfo=UTC), _Session(texts_of(source)))
    man = F.qdata.read_manifest(manifest)
    assert F.folder_record_violations(folder, man) == [] and F.newest_folder(root, man) == folder == F.named_folder(folder, man)
    assert F.chosen_folder(root, manifest, None, False) == folder and F.chosen_folder(root, manifest, folder, False) == folder


# --- the run reads the recorded folder and names what it set aside -----------------------------------

def test_an_edited_folder_newer_by_name_is_set_aside_and_the_recorded_folder_is_read(tmp_path, capsys):
    root, folder, _ = kept(tmp_path)
    cal, cands = tmp_path / "data" / "fomc_calibration.json", tmp_path / "c.jsonl"
    assert F.main(["--raw-root", str(root), "--manifest", str(root.parent / "m.json"), "--out", str(cal)]) == 0
    capsys.readouterr()
    other = edited_copy(folder)
    # the defect: on 3a55eeb `inputs:` named `other` here and the candidate carried its hashes
    assert F.main(live_argv(root, cal, cands)) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"inputs: {folder}\nset aside: {other.name} is not a kept fetch (fred_DTB3.csv ({sha(other / 'fred_DTB3.csv')[:12]}) "
                          f"has no entry under {other.name}/ on the manifest: no fetch recorded it; fred_DTB4WK.csv (")
    c = L.read_candidates(cands)[0]
    assert c["inputs"]["input_folder"] == folder.name and c["inputs"]["input_sha256"] == {k: sha(folder / f"fred_{k}.csv") for k in F.SERIES}
    assert F.recompute_candidate(c, root, cal, manifest=manifest_of(root)) == []
    # the calibration run (no --live) reads the same folder and says the same
    assert F.main(["--raw-root", str(root), "--manifest", str(root.parent / "m.json"), "--out", str(cal), "--no-write"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"set aside: {other.name} is not a kept fetch (") and f"\ninputs: {folder}\n" in out


def test_a_half_written_folder_is_set_aside_not_read_as_a_stale_print(tmp_path, capsys):
    root, folder, _ = kept(tmp_path)
    cal, cands = tmp_path / "data" / "fomc_calibration.json", tmp_path / "c.jsonl"
    half = root / "2026-11-15T120100Z"
    shutil.copytree(folder, half)
    body = (half / "fred_DTB3.csv").read_bytes()
    (half / "fred_DTB3.csv").write_bytes(body[: len(body) // 2])   # a write the process did not finish; no manifest entry
    # the defect: on 3a55eeb this folder was read by default and the run printed "no reading ...: stale print"
    assert F.main(live_argv(root, cal, cands)) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"inputs: {folder}\nset aside: {half.name} is not a kept fetch (fred_DTB3.csv (") and "stale print" not in out
    assert L.read_candidates(cands)[0]["inputs"]["input_folder"] == folder.name


def test_from_dir_on_an_unrecorded_or_altered_folder_is_refused_and_nothing_is_written(tmp_path, capsys):
    root, folder, _ = kept(tmp_path)
    cal, cands = tmp_path / "data" / "fomc_calibration.json", tmp_path / "c.jsonl"
    other = edited_copy(folder)
    rc = F.main(live_argv(root, cal, cands, "--from-dir", str(other)))
    out = capsys.readouterr().out
    assert rc == 1 and out.startswith(f"REFUSED: {other} is not a kept fetch: fred_DTB3.csv ({sha(other / 'fred_DTB3.csv')[:12]}) has no entry under")
    assert not cands.exists() and not cal.exists()
    # recorded, then one file's bytes moved: refused naming the recorded hash
    record(tmp_path / "m.json", other, "2026-11-15T12:00:01Z")
    assert F.main(live_argv(root, cal, cands, "--from-dir", str(other))) == 0 and capsys.readouterr().out.startswith(f"inputs: {other}\n")
    with (other / "fred_EFFR.csv").open("a", encoding="utf-8") as fh:
        fh.write("2026-11-12,3.90\n")
    rc = F.main(live_argv(root, cal, cands, "--from-dir", str(other)))
    out = capsys.readouterr().out
    assert rc == 1 and out.startswith(f"REFUSED: {other} is not a kept fetch: fred_EFFR.csv is {sha(other / 'fred_EFFR.csv')[:12]}, the fetch recorded ")
    assert len(L.read_candidates(cands)) == 1, "the refused run wrote no candidate"
    # the calibration run path refuses the same way
    rc = F.main(["--from-dir", str(other), "--raw-root", str(root), "--manifest", str(root.parent / "m.json"), "--out", str(tmp_path / "x.json")])
    assert rc == 1 and capsys.readouterr().out.startswith("REFUSED: ") and not (tmp_path / "x.json").exists()


# --- the candidate is held to a recorded folder, at recomputation and at admission -------------------

def test_a_candidate_naming_an_unrecorded_folder_is_a_difference_even_with_the_same_bytes(tmp_path, capsys):
    got, root, folder, cal, cands = kept_bills(tmp_path)
    c = got[0]
    other = root / EDITED
    shutil.copytree(folder, other)     # the same bytes under a name no fetch recorded
    renamed = dict(c, inputs=dict(c["inputs"], input_folder=other.name))
    diffs = F.recompute_candidate(renamed, root, cal, manifest=manifest_of(root))
    assert len(diffs) == 1 and diffs[0].startswith(f"no kept folder {other.name} under {root} holding the four series the manifest recorded: "
                                                   "the bytes the figures were read from cannot be re-read (fred_DTB3.csv (")
    assert "no fetch recorded it" in diffs[0]
    # the CLI, with the manifest named, says the same; with an empty manifest nothing is a kept fetch
    cands.write_text(cands.read_text(encoding="utf-8") + __import__("json").dumps(dict(renamed, id="K-fomc_bills-hike-20261115T120500Z"), sort_keys=True) + "\n",
                     encoding="utf-8")
    capsys.readouterr()
    rc = F.main(["--recompute", "K-fomc_bills-hike-20261115T120500Z", "--candidates", str(cands), "--raw-root", str(root), "--out", str(cal),
                 "--manifest", str(root.parent / "m.json")])
    assert rc == 1 and capsys.readouterr().out.startswith("recompute K-fomc_bills-hike-20261115T120500Z: DIFFERS\n  no kept folder")
    rc = F.main(["--recompute", c["id"], "--candidates", str(cands), "--raw-root", str(root), "--out", str(cal), "--manifest", str(tmp_path / "none.json")])
    out = capsys.readouterr().out
    assert rc == 1 and f"no kept folder {folder.name} under {root}" in out and "no fetch recorded it" in out


def test_add_refuses_a_candidate_whose_folder_no_fetch_recorded(tmp_path, capsys):
    got, manifest, cands, root = admission(tmp_path)
    c = got[0]
    other = root / EDITED
    shutil.copytree(root / c["inputs"]["input_folder"], other)   # same bytes, same hashes, a name the manifest never saw
    later = datetime(2026, 11, 20, 6, 20, 1, tzinfo=UTC)
    renamed = dict(c, id=L.candidate_id("fomc_bills", "hike", later), computed_utc=later.strftime(L.UTC_STAMP_FORMAT),
                   inputs=dict(c["inputs"], input_folder=other.name))
    L.append_candidate(cands, renamed)
    args = ns(quote=LATE_QUOTE["fetched_utc"], market_id=LATE_QUOTE["market_id"], method="fomc_bills", method_p=None, range_lo=None,
              range_hi=None, climatology_p=None, candidate=renamed["id"], proposition="Hike of 25 bp on 9 December")
    # on 3a55eeb this row was admitted: the folder was found by name and its bytes hashed to the candidate's
    assert R.add(args, manifest, tmp_path / "r1.csv", LATE_NOW, candidates=cands) == 1
    out = capsys.readouterr().out
    assert "[reading:figures-recompute]" in out and f"no kept folder {other.name}" in out and "no fetch recorded it" in out
    assert not (tmp_path / "r1.csv").exists()
    # the recorded folder's candidate is admitted as before
    args = ns(quote=LATE_QUOTE["fetched_utc"], market_id=LATE_QUOTE["market_id"], method="fomc_bills", method_p=None, range_lo=None,
              range_hi=None, climatology_p=None, candidate=c["id"], proposition="Hike of 25 bp on 9 December")
    assert R.add(args, manifest, tmp_path / "r2.csv", LATE_NOW, candidates=cands) == 0
    assert "recomputed: the four figures of" in capsys.readouterr().out
    # the fetch manifest gone from <here>/data: no folder is a kept fetch, the honest candidate is refused too
    (tmp_path / "data" / "fred_rates_manifest.json").unlink()
    assert R.add(args, manifest, tmp_path / "r3.csv", LATE_NOW, candidates=cands) == 1
    assert "no fetch recorded it" in capsys.readouterr().out and not (tmp_path / "r3.csv").exists()
