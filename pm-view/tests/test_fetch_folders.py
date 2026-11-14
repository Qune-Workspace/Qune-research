"""One folder per fetch for the bill reading's inputs (2026-11-14 18:15Z, predictions/POST_MORTEMS.md
"A download the next fetch replaced"): until this date `fomc_calibrate.py --fetch` wrote the four FRED
files in place and the manifest entry under the file's name, so the 13 November fetch replaced the
bytes the two 6 November readings were read from, and their hashes survive only in git.  Now a
fetch writes `data/raw/fred_rates/<UTC time>/`, never over a kept folder, the manifest keeps one
entry per fetched file under `<folder>/<file>`, a run reads the newest kept folder unless told
which, and a candidate names the folder its figures were computed from so they recompute."""
import hashlib
import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import fomc_calibrate as F
import pm_lib as L
from test_fomc_calibrate import synthetic_history

T1 = datetime(2026, 11, 6, 6, 17, 22, tzinfo=UTC)
T2 = datetime(2026, 11, 13, 6, 18, 41, tzinfo=UTC)


class _Response:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class _Session:
    """Serves one text per series id from the URL's `id=`; counts the calls."""

    def __init__(self, texts: dict[str, str]) -> None:
        self.texts, self.urls = texts, []

    def get(self, url: str, timeout: int) -> _Response:
        self.urls.append(url)
        return _Response(self.texts[url.rsplit("id=", 1)[1]])


def texts_of(folder: Path, extra_row: str | None = None) -> dict[str, str]:
    out = {}
    for k in F.SERIES:
        t = (folder / f"fred_{k}.csv").read_text(encoding="utf-8")
        out[k] = t if extra_row is None else t + f"{extra_row},{t.strip().splitlines()[-1].split(',')[1]}\n"
    return out


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def kept(tmp_path: Path, name: str = "2026-11-13T061841Z") -> tuple[Path, Path, list]:
    """A synthetic history kept as one fetch folder under a root."""
    meetings, raw_dir, _ = synthetic_history(tmp_path)
    root = tmp_path / "fred_rates"
    root.mkdir()
    folder = root / name
    shutil.move(str(raw_dir), str(folder))
    return root, folder, meetings


# --- the fetch keeps every download ----------------------------------------------------------

def test_a_fetch_writes_its_own_folder_and_the_next_fetch_leaves_it_untouched(tmp_path):
    _, source, _ = kept(tmp_path)
    root, manifest = tmp_path / "root", tmp_path / "fred_rates_manifest.json"
    first = F.fetch_all(root, manifest, T1, _Session(texts_of(source)))
    assert first == root / "2026-11-06T061722Z" and sorted(p.name for p in first.iterdir()) == sorted(f"fred_{k}.csv" for k in F.SERIES)
    first_hashes = {p.name: sha(p) for p in first.iterdir()}
    first_manifest = json.loads(manifest.read_text(encoding="utf-8"))
    assert sorted(first_manifest) == sorted(f"2026-11-06T061722Z/fred_{k}.csv" for k in F.SERIES)
    assert all(first_manifest[f"2026-11-06T061722Z/{n}"]["sha256"] == h for n, h in first_hashes.items())
    # the defect: on HEAD before this date the second fetch wrote the same four paths and the same four keys
    second = F.fetch_all(root, manifest, T2, _Session(texts_of(source, extra_row="2026-11-10")))
    assert second == root / "2026-11-13T061841Z" and second != first
    assert {p.name: sha(p) for p in first.iterdir()} == first_hashes, "the first fetch's bytes are untouched"
    m = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(m) == 8 and all(m[k] == v for k, v in first_manifest.items()), "the first fetch's entries are untouched"
    assert all(m[f"2026-11-13T061841Z/fred_{k}.csv"]["last_bar"] == "2026-11-10" for k in F.SERIES)
    assert all(m[f"2026-11-13T061841Z/fred_{k}.csv"]["sha256"] != first_hashes[f"fred_{k}.csv"] for k in F.SERIES)
    assert F.kept_folders(root) == [(T1.replace(microsecond=0), first), (T2.replace(microsecond=0), second)]
    assert F.manifest_entries_for(m, first) == first_manifest and F.manifest_entries_for(m, tmp_path / "nowhere") is None


def test_a_fetch_never_writes_over_a_kept_folder(tmp_path):
    _, source, _ = kept(tmp_path)
    root, manifest = tmp_path / "root", tmp_path / "m.json"
    F.fetch_all(root, manifest, T1, _Session(texts_of(source)))
    before = {p.name: sha(p) for p in (root / "2026-11-06T061722Z").iterdir()}
    try:
        F.fetch_all(root, manifest, T1, _Session(texts_of(source, extra_row="2026-11-10")))
    except FileExistsError as e:
        assert "2026-11-06T061722Z already holds fred_DTB3.csv" in str(e) and "never over a kept one" in str(e)
    else:
        raise AssertionError("a second fetch at the same time wrote over the kept folder")
    assert {p.name: sha(p) for p in (root / "2026-11-06T061722Z").iterdir()} == before
    assert len(json.loads(manifest.read_text(encoding="utf-8"))) == 4


# --- the run reads the newest kept folder unless told which -----------------------------------

def test_the_default_input_is_the_newest_kept_folder_by_parsed_time_and_none_is_refused(tmp_path, capsys):
    root, newest, _ = kept(tmp_path, "2026-11-13T061841Z")
    older = root / "2026-11-06T061722Z"
    shutil.copytree(newest, older)
    (root / "explore-2026-11-30").mkdir()                       # not a fetch time
    (root / "explore-2026-11-30" / "fred_DTB3.csv").write_text("x", encoding="utf-8")
    (root / "2026-11-20T061800Z").mkdir()                        # a fetch time, but the folder is incomplete
    (root / "2026-11-20T061800Z" / "fred_DTB3.csv").write_text("x", encoding="utf-8")
    (root / "fred_DTB3.csv").write_text("x", encoding="utf-8")   # a file in place, the old layout
    assert [p for _, p in F.kept_folders(root)] == [older, newest]
    assert F.newest_folder(root) == newest
    empty = tmp_path / "empty"
    empty.mkdir()
    for root_ in (empty, tmp_path / "absent"):
        try:
            F.newest_folder(root_)
        except FileNotFoundError as e:
            assert str(root_) in str(e) and "--fetch" in str(e) and "--from-dir" in str(e)
        else:
            raise AssertionError(f"{root_} gave a folder")
        # main refuses by name on both paths, writes nothing, exit 1
        rc = F.main(["--live", "2026-12-09", "--today", "2026-11-04", "--mid", "hike=0.6", "--raw-root", str(root_),
                     "--manifest", str(tmp_path / "m.json"), "--out", str(tmp_path / "cal.json"),
                     "--candidates", str(tmp_path / "c.jsonl")])
        out = capsys.readouterr().out
        assert rc == 1 and out.startswith("REFUSED: no kept download under") and str(root_) in out
        rc = F.main(["--raw-root", str(root_), "--manifest", str(tmp_path / "m.json"), "--out", str(tmp_path / "cal.json")])
        assert rc == 1 and capsys.readouterr().out.startswith("REFUSED: no kept download under")
    assert not (tmp_path / "cal.json").exists() and not (tmp_path / "c.jsonl").exists()


def test_fetch_and_from_dir_together_are_refused(tmp_path):
    try:
        F.main(["--fetch", "--from-dir", str(tmp_path), "--no-write"])
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("--fetch with --from-dir was admitted")


# --- the candidate names its folder and the figures recompute from it --------------------------

def test_a_candidate_names_its_input_folder_and_the_figures_recompute_from_it(tmp_path, capsys):
    root, folder, meetings = kept(tmp_path)
    manifest, out = tmp_path / "m.json", tmp_path / "data" / "fomc_calibration.json"
    assert F.main(["--raw-root", str(root), "--manifest", str(manifest), "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert printed.startswith(f"inputs: {folder}\n")
    cal = F.load_calibration(out)
    mids = {"hike": 0.635, "none": 0.325}
    got = F.live_candidates(F.load_dir(folder), meetings, date(2026, 12, 9), date(2026, 11, 4), cal, mids, folder, T2)
    assert [c["inputs"]["input_folder"] for c in got] == ["2026-11-13T061841Z"] * 2
    assert all(c["inputs"]["input_sha256"] == {k: sha(folder / f"fred_{k}.csv") for k in F.SERIES} for c in got)
    # the record says what to run: the same folder's bytes elsewhere, --today the candidate's as_of, give the same figures
    other_root = tmp_path / "elsewhere" / "fred_rates"
    shutil.copytree(folder, other_root / folder.name)
    cands = tmp_path / "c.jsonl"
    rc = F.main(["--live", "2026-12-09", "--today", got[0]["inputs"]["as_of"], "--from-dir", str(other_root / folder.name),
                 "--mid", "hike=0.635", "--mid", "none=0.325", "--manifest", str(manifest), "--out", str(out),
                 "--candidates", str(cands)])
    assert rc == 0 and capsys.readouterr().out.startswith(f"inputs: {other_root / folder.name}\n")
    again = L.read_candidates(cands)
    assert [(c["key"], c["method_p"], c["range_lo"], c["range_hi"], c["climatology_p"]) for c in again] == \
        [(c["key"], c["method_p"], c["range_lo"], c["range_hi"], c["climatology_p"]) for c in got]
    assert all(c["inputs"]["input_sha256"] == got[0]["inputs"]["input_sha256"] for c in again)


def test_run_names_the_folder_and_holds_the_manifest_hash_by_the_folder_key(tmp_path, capsys):
    import csv
    root, folder, _ = kept(tmp_path)
    manifest, out = tmp_path / "m.json", tmp_path / "data" / "fomc_calibration.json"
    entries = {f"{folder.name}/fred_{k}.csv": {"sha256": sha(folder / f"fred_{k}.csv"), "series_id": k} for k in F.SERIES}
    entries[f"{folder.name}/fred_DTB3.csv"] = {"sha256": "ab" * 32, "series_id": "DTB3"}          # disagrees with the bytes
    entries["2026-11-06T061722Z/fred_EFFR.csv"] = {"sha256": "cd" * 32, "series_id": "EFFR"}     # another fetch's entry
    manifest.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert F.run(folder, manifest, out, fetch=False, now=datetime(2026, 11, 14, 18, 30, tzinfo=UTC)) == 0
    capsys.readouterr()
    with (out.parent / "calibration_history.csv").open(encoding="utf-8", newline="") as fh:
        line = list(csv.DictReader(fh))[-1]
    assert line["source"].startswith(f"fomc_calibrate.py: folder {folder.name}, fred_DTB3.csv {sha(folder / 'fred_DTB3.csv')[:12]} (manifest abababababab), ")
    assert "fred_EFFR.csv" in line["source"] and "(manifest cdcd" not in line["source"]
    written = json.loads(out.read_text(encoding="utf-8"))
    assert sorted(written["inputs_manifest"]) == sorted(f"{folder.name}/fred_{k}.csv" for k in F.SERIES)
