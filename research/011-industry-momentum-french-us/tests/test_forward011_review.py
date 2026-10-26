"""Study 011 forward record: tests added after the separate code review of part 2 (CODE_REVIEW.md, third part).

Each test targets a mutation that survived the review; synthetic data only."""
import json
import subprocess

import pandas as pd
import pytest
from src import forward011 as fw

from tests.test_forward011 import synthetic, write_release
from tests.test_forward011_part2 import _forward_book, _own, _setup_fetch, cut, fake_get, hist_from

P = pd.Period


def test_verdict_needs_c2_and_c4():
    d = {"sharpe_annual": 0.1, "nw_t": 2.5, "mean_pct_a_year": 1.0}
    assert fw.forward_verdict(d, 0.5, 0.4)["row"].startswith("meets C2 and C4")
    assert fw.forward_verdict(d, 0.5, -0.4)["row"].startswith("does not meet")  # C2 only
    assert fw.forward_verdict(dict(d, nw_t=1.0), 0.99, 0.4)["row"].startswith("does not meet")  # C4 only
    v = fw.forward_verdict(d, 0.5, 0.4)
    assert fw.LABEL in v["row"] and {"C1_reported", "C3_reported"} <= set(v)  # reported, not deciding
    assert fw.forward_verdict(d, 0.0, 0.4)["row"] == v["row"]  # C3 does not decide


def test_scoring_release_is_the_first_containing_the_60th_month():
    months = pd.period_range("2026-09", periods=60, freq="M")
    assert fw.scoring_release(months, {"203107": {}, "203108": {}, "203109": {}, "203112": {}}) == "203108"
    assert fw.scoring_release(months, {"203109": {}, "203110": {}}) == "203109"
    with pytest.raises(SystemExit, match="no archived release"):
        fw.scoring_release(months, {"203107": {}})


def _book_and_own():
    ind = synthetic("2026-10", seed=21)
    pos, times = _forward_book(ind, "2026-10")
    return ind, pos, times


def _recommit(pos):
    return {(r["month"], r["trial"]): {"time": pd.Timestamp("2026-10-01T00:00:00Z"),
                                       "row": {c: r[c] for c in fw.COLUMNS if c != "late"}}
            for r in pos.to_dict("records")}


def test_check_rows_refuses_a_wrong_release_or_hash():
    ind, pos, times = _book_and_own()
    assert fw.check_rows(pos, times, _own(ind)) == []
    wrong_sha = lambda m: (*_own(ind)(m)[:2], "sha-other")  # noqa: E731
    with pytest.raises(SystemExit, match="do not name release"):
        fw.check_rows(pos, times, wrong_sha)
    wrong_rel = lambda m: (_own(ind)(m)[0], "209901", _own(ind)(m)[2])  # noqa: E731
    with pytest.raises(SystemExit, match="do not name release"):
        fw.check_rows(pos, times, wrong_rel)


def test_check_rows_refuses_a_changed_formation_return_or_tie_count():
    ind, pos, _ = _book_and_own()
    a = pos.copy()
    kv = a.loc[0, "formation_returns"].split(";")
    k, v = kv[0].split("=", 1)
    kv[0] = f"{k}={float(v) + 1e-6!r}"
    a.loc[0, "formation_returns"] = ";".join(kv)
    with pytest.raises(SystemExit, match="not reproduced"):
        fw.check_rows(a, _recommit(a), _own(ind))
    b = pos.copy()
    b.loc[0, "boundary_ties"] = str(int(b.loc[0, "boundary_ties"]) + 1)
    with pytest.raises(SystemExit, match="not reproduced"):
        fw.check_rows(b, _recommit(b), _own(ind))
    c = pos.copy()  # a formation return within 1e-12 relative still passes (no exact-string rule)
    kv = c.loc[0, "formation_returns"].split(";")
    k, v = kv[0].split("=", 1)
    kv[0] = f"{k}={float(v) * (1 + 1e-14)!r}"
    c.loc[0, "formation_returns"] = ";".join(kv)
    assert fw.check_rows(c, _recommit(c), _own(ind)) == []


def test_weights_refuse_duplicate_or_overlapping_industries():
    cols = [f"I17_{i:02d}" for i in range(17)]
    good = (cols[:3], cols[3:6])
    cmap = {P("2026-08", "M") - j: good for j in range(6)}
    fw.weights(cmap, P("2026-09", "M"), cols, 3)
    for bad in ((cols[:2] + cols[:1], cols[3:6]), (cols[:3], cols[2:5])):
        cmap2 = {**cmap, P("2026-05", "M"): bad}
        with pytest.raises(SystemExit, match="distinct industries"):
            fw.weights(cmap2, P("2026-09", "M"), cols, 3)


def test_history_cohorts_checked_against_a_release():
    ind = synthetic("2026-08", seed=22)
    hist = hist_from(ind)
    assert fw.history_ranks_used() == ["2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07"]
    assert fw.check_history_cohorts(ind, hist) == []
    W, L = hist["M1a"]["2026-02"]
    hist["M1a"]["2026-02"] = (L, W)
    assert fw.check_history_cohorts(ind, hist) == [["2026-02", "M1a"]]


def test_own_release_loader_uses_release_t_minus_1(tmp_path):
    ind = synthetic("2026-09", seed=23)
    snap = tmp_path / "snap"
    snap.mkdir()
    _, snap_man = write_release(snap, cut(ind, "2026-08"), "202608")
    raw, rel = tmp_path / "raw", tmp_path / "releases"
    (raw / "202609").mkdir(parents=True)
    _, man = write_release(raw / "202609", ind, "202609")
    rel.mkdir()
    (rel / "202609.json").write_text(man.read_text())
    load = fw.own_release_loader(raw, rel, snap, snap_man)
    i0, r0, h0 = load("2026-09")
    assert r0 == "202608" and h0 == fw.files_sha256(snap_man) and i0[17].index[-1] == P("2026-08", "M")
    i1, r1, h1 = load("2026-10")
    assert r1 == "202609" and h1 == fw.files_sha256(rel / "202609.json") and i1[17].index[-1] == P("2026-09", "M")
    for n in fw.FILES.values():
        (raw / "202609" / n).unlink()
    with pytest.raises(FileNotFoundError):
        fw.own_release_loader(raw, rel, snap, snap_man)("2026-10")


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    return repo


def _commit(repo, when):
    _git(repo, "add", "-A")
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=repo, check=True, capture_output=True,
                   env={"GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when, "PATH": "/usr/bin:/bin",
                        "HOME": str(repo)})


def test_row_commit_times_keeps_the_earliest_commit_and_its_row(tmp_path):
    repo = _repo(tmp_path)
    ind, pos, _ = _book_and_own()
    path = repo / "cohorts.csv"
    first = pos[pos["month"] == "2026-09"]
    first.to_csv(path, index=False)
    _commit(repo, "2026-10-26T17:35:18Z")
    later = pos.copy()
    later.loc[later["month"] == "2026-09", "winners"] = "X;Y;Z"  # a rewrite in a later commit
    later.to_csv(path, index=False)
    _commit(repo, "2026-11-05T10:00:00Z")
    times = fw.row_commit_times(path)
    assert times[("2026-09", "M1")]["time"] == pd.Timestamp("2026-10-26T17:35:18Z")
    assert times[("2026-09", "M1")]["row"]["winners"] == first.iloc[0]["winners"]
    assert times[("2026-10", "M1")]["time"] == pd.Timestamp("2026-11-05T10:00:00Z")
    with pytest.raises(SystemExit, match="differs from its first commit"):
        fw.check_rows(later, times, _own(ind))


def test_shallow_clone_refused(tmp_path):
    repo = _repo(tmp_path)
    _, pos, _ = _book_and_own()
    pos.to_csv(repo / "cohorts.csv", index=False)
    _commit(repo, "2026-10-26T17:35:18Z")
    (repo / "x").write_text("x")
    _commit(repo, "2026-10-27T17:35:18Z")
    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{repo}", str(shallow)], check=True,
                   capture_output=True)
    with pytest.raises(SystemExit, match="shallow clone"):
        fw.row_commit_times(shallow / "cohorts.csv")


def test_ever_committed_and_git_failure(tmp_path):
    repo = _repo(tmp_path)
    out = repo / "results" / "forward" / "score.json"
    assert fw._ever_committed(out) is False
    out.parent.mkdir(parents=True)
    out.write_text("{}")
    _commit(repo, "2031-10-01T00:00:00Z")
    out.unlink()
    _commit(repo, "2031-10-02T00:00:00Z")
    assert fw._ever_committed(out) is True  # a deleted score.json does not reopen the scoring
    nogit = tmp_path / "nogit" / "score.json"
    nogit.parent.mkdir()
    with pytest.raises(SystemExit, match="git could not say"):
        fw._ever_committed(nogit)


def test_fetch_never_writes_the_json_before_the_files(tmp_path, monkeypatch):
    """A crash while moving the files leaves no release json; the next fetch clears the leftovers and keeps it."""
    ind = synthetic("2026-09", seed=24)
    snap_man, src, hdir = _setup_fetch(tmp_path, cut(ind, "2026-08"), "202609")
    write_release(src, ind, "202609")
    raw, rel = tmp_path / "raw", tmp_path / "releases"
    real_rename = fw.Path.rename

    def crash(self, target):
        if self.name.startswith("_incoming-"):
            raise OSError("simulated crash while moving the files")
        return real_rename(self, target)
    monkeypatch.setattr(fw.Path, "rename", crash)
    with pytest.raises(OSError):
        fw.fetch(fake_get(src), raw, rel, snap_man, hdir, now=lambda: "2026-11-05T10:00:00Z")
    assert not (rel / "202609.json").exists()
    monkeypatch.setattr(fw.Path, "rename", real_rename)
    (raw / "202609").mkdir()  # leftover files without their json, as after a crash in a later step
    (raw / "202609" / "junk").write_text("x")
    res = fw.fetch(fake_get(src), raw, rel, snap_man, hdir, now=lambda: "2026-11-05T11:00:00Z")
    assert res["kept"] and not (raw / "202609" / "junk").exists()
    assert json.loads((rel / "202609.json").read_text())["release"] == "202609"
    assert fw.load_industries(raw / "202609", rel / "202609.json")[17].index[-1] == P("2026-09", "M")
