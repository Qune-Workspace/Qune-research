"""Study 010 forward record, part 2 (fetch, lateness, interim, scoring), on synthetic series and zips only."""
import json
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest
from src import forward010 as fw
from src.rule import COST_BASE, COST_STRESS, TRIALS, run

from tests.test_forward010 import synthetic, write_release

MONTHS = pd.period_range("2026-09", periods=60, freq="M")


class Resp:
    def __init__(self, content: bytes):
        self.content = content
        self.text = content.decode("latin-1")

    def raise_for_status(self):
        pass


def fake_get(src_dir):
    page = "".join(f'<a href="ftp/{n}">x</a>' for n in fw.FILES).encode()

    def get(url, headers=None, timeout=None):
        if url == fw.LIBRARY_PAGE:
            return Resp(page)
        return Resp((src_dir / url.rsplit("/", 1)[-1]).read_bytes())
    return get


def snapshot(tmp_path, f=None):
    d = tmp_path / "snap"
    d.mkdir()
    return write_release(d, synthetic("2026-08") if f is None else f, "202608")


def library(tmp_path, f, release, name="lib"):
    d = tmp_path / name
    d.mkdir()
    write_release(d, f, release)
    return d


def test_fetch_keeps_a_new_release_once(tmp_path):
    _, snap_man = snapshot(tmp_path)
    src = library(tmp_path, synthetic("2026-09"), "202609")
    raw, rel = tmp_path / "raw", tmp_path / "releases"
    stamps = iter(f"2026-11-0{i}T10:00:00Z" for i in range(1, 9))
    got = fw.fetch(fake_get(src), raw, rel, snap_man, now=lambda: next(stamps))
    assert got["kept"] and got["release"] == "202609"
    man = json.loads((rel / "202609.json").read_text())
    assert set(man["files"]) == set(fw.FILES) and not (raw / "_incoming").exists()
    assert fw.release_of(rel / "202609.json") == "202609"
    again = fw.fetch(fake_get(src), raw, rel, snap_man)
    assert not again["kept"] and "already archived" in again["reason"]
    assert json.loads((rel / "202609.json").read_text()) == man  # the first download is never replaced
    # the archived set is what record reads: the 2026-10 positions come from release 202609
    rows = fw.record("2026-10", raw / "202609", rel / "202609.json", out=tmp_path / "positions.csv")
    assert {r["release"] for r in rows} == {"202609"}


def test_fetch_refuses_the_snapshot_release_mixed_releases_and_older(tmp_path):
    _, snap_man = snapshot(tmp_path)
    raw, rel = tmp_path / "raw", tmp_path / "releases"
    same = fw.fetch(fake_get(library(tmp_path, synthetic("2026-08"), "202608", "a")), raw, rel, snap_man)
    assert not same["kept"] and "snapshot" in same["reason"]
    mixed_dir = library(tmp_path, synthetic("2026-09"), "202609", "b")
    other = library(tmp_path, synthetic("2026-10"), "202610", "c")
    shutil.copy(other / "F-F_LT_Reversal_Factor_CSV.zip", mixed_dir / "F-F_LT_Reversal_Factor_CSV.zip")
    mixed = fw.fetch(fake_get(mixed_dir), raw, rel, snap_man)
    assert not mixed["kept"] and "different releases" in mixed["reason"]
    assert not rel.exists() and list(raw.iterdir()) == []  # nothing kept, staging removed
    assert fw.fetch(fake_get(other), raw, rel, snap_man)["kept"]
    older = fw.fetch(fake_get(library(tmp_path, synthetic("2026-09"), "202609", "d")), raw, rel, snap_man)
    assert not older["kept"] and "older" in older["reason"]


def engine_positions(f):
    rows = []
    for m in MONTHS:
        rows += fw.positions_for(f, str(m))
    return pd.DataFrame(rows).astype(str)


def test_forward_frame_matches_the_history_engine():
    """On committed h equal to the engine's h, T, costs and B1 equal the engine's over the forward months."""
    f = synthetic("2031-08", seed=5)
    pos = engine_positions(f)
    for case, c in (("base", COST_BASE), ("stress", COST_STRESS)):
        for t, trial in TRIALS.items():
            eng = run(f, trial, "2031-08", c)
            h_prev = {k: float(eng["h"].loc[pd.Period("2026-08", "M"), k]) for k in trial.factors}
            hbar = {k: 0.25 for k in trial.factors}
            fr = fw.forward_frame(fw.committed_h(pos, t, MONTHS), f, hbar, h_prev, c)
            e = eng["frame"].loc[MONTHS]
            for col in ("T_gross", "cost", "T", "B1"):
                np.testing.assert_allclose(fr[col].to_numpy(), e[col].to_numpy(), atol=1e-12)
            b3 = (f.loc[MONTHS, trial.factors] * 0.25).sum(axis=1) / len(trial.factors)
            np.testing.assert_allclose(fr["B3"].to_numpy(), b3.to_numpy(), atol=1e-12)


def test_first_month_trade_is_measured_from_h_at_h_end():
    f = synthetic("2031-08", seed=5)
    pos = engine_positions(f)
    h = fw.committed_h(pos, "T1a", MONTHS)
    same = fw.forward_frame(h, f, {"SMB": 0, "HML": 0}, h.iloc[0].to_dict(), 0.10)
    flipped = fw.forward_frame(h, f, {"SMB": 0, "HML": 0}, (-h.iloc[0]).to_dict(), 0.10)
    assert same["cost"].iloc[0] == 0.0
    assert flipped["cost"].iloc[0] == pytest.approx(0.10 * 2 * 2 * 2 / 2)  # two flips of 4c each, over K = 2


def test_late_flags_use_the_desk_first_download():
    pos = pd.DataFrame({"month": ["2026-09", "2026-10"], "trial": ["T1"] * 2, "factor": ["SMB"] * 2})
    rels = {"202609": {"files": {"a": {"downloaded_at_utc": "2026-11-02T10:00:00Z"},
                                 "b": {"downloaded_at_utc": "2026-11-02T10:05:00Z"}}},
            "202610": {"files": {"a": {"downloaded_at_utc": "2026-12-01T10:00:00Z"}}}}
    ts = pd.Timestamp
    times = {("2026-09", "T1", "SMB"): ts("2026-11-02T10:06:00Z"), ("2026-10", "T1", "SMB"): ts("2026-11-03T09:00:00Z")}
    assert fw.late_flags(pos, times, rels).tolist() == [True, False]
    with pytest.raises(SystemExit, match="not in any commit"):
        fw.late_flags(pos, {}, rels)


def test_row_commit_times_from_git(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    p = tmp_path / "positions.csv"
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
    head = ",".join(fw.COLUMNS) + "\n"
    row = lambda m: f"{m},T1,SMB,12,0.1,1,r,m,s,s,d,d,False\n"  # noqa: E731
    for i, body in enumerate([head + row("2026-09"), head + row("2026-09") + row("2026-10")]):
        p.write_text(body)
        subprocess.run(["git", "add", "positions.csv"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-qm", str(i)], cwd=tmp_path, check=True,
                       env={**env, "GIT_COMMITTER_DATE": f"2026-11-0{i + 1}T12:00:00+01:00", "PATH": "/usr/bin:/bin"})
    t = fw.row_commit_times(p)
    assert t[("2026-09", "T1", "SMB")] == pd.Timestamp("2026-11-01T11:00:00Z")
    assert t[("2026-10", "T1", "SMB")] == pd.Timestamp("2026-11-02T11:00:00Z")


def setup_score(tmp_path, f, release="203108", f_snap=None):
    snap_dir, snap_man = snapshot(tmp_path, f.loc[: pd.Period("2026-08", "M")] if f_snap is None else f_snap)
    raw, rel = tmp_path / "raw", tmp_path / "releases"
    d = raw / release
    d.mkdir(parents=True)
    _, man = write_release(d, f, release)
    rel.mkdir()
    man.rename(rel / f"{release}.json")
    pos = engine_positions(f)
    times = {k: pd.Timestamp("2026-01-01T00:00:00Z") for k in zip(pos["month"], pos["trial"], pos["factor"])}
    hbar = json.loads(json.dumps({t: {k: 0.2 for k in tr.factors} for t, tr in TRIALS.items()}))
    h_prev = {t: {k: 1.0 for k in tr.factors} for t, tr in TRIALS.items()}
    kw = dict(raw_root=raw, releases_dir=rel, snapshot_raw=snap_dir, snapshot_manifest=snap_man, hbar=hbar,
              h_prev=h_prev, out=tmp_path / "score.json")
    return pos, times, kw


def test_score_once_with_decision_rows_and_vintage(tmp_path):
    f = synthetic("2031-08", seed=7)
    snap = f.loc[: pd.Period("2026-08", "M")].copy()
    f.loc[pd.Period("2000-01", "M"), "HML"] += 1.0  # a revision inside H, seen by the vintage row
    pos, times, kw = setup_score(tmp_path, f, f_snap=snap)
    res = fw.score("203108", pos, times, **kw)
    assert res["months"] == ["2026-09", "2031-08"] and res["N_family"] == 3
    for t in TRIALS:
        v = res["trials"][t]["verdict"]
        assert set(v) == {"C1_reported", "C2", "C3_reported", "C4", "row"} and "low-power check" in v["row"]
        assert (v["row"].startswith("meets C2 and C4")) == (v["C2"] and v["C4"])
        assert res["trials"][t]["rows_late"] == 0
    vin = res["vintage"]
    assert vin["per_factor_over_H"]["HML"]["months_differing"] == 1
    assert vin["per_factor_over_H"]["SMB"]["months_differing"] == 0
    assert vin["h_rows_compared"] == len(pos) and vin["h_rows_differing"] == 0
    with pytest.raises(SystemExit, match="scored once"):
        fw.score("203108", pos, times, **kw)


def test_score_refuses_short_record_missing_release_and_short_release(tmp_path):
    f = synthetic("2031-08", seed=7)
    pos, times, kw = setup_score(tmp_path, f)
    with pytest.raises(SystemExit, match="not recorded"):
        fw.score("203108", pos[pos["month"] != "2031-08"], times, **kw)
    with pytest.raises(SystemExit, match="not archived"):
        fw.score("203107", pos, times, **kw)
    assert not kw["out"].exists()
    (tmp_path / "x").mkdir()
    _, _, kw2 = setup_score(tmp_path / "x", synthetic("2031-07", seed=7), "203107")
    with pytest.raises(SystemExit, match="does not contain 2031-08"):
        fw.score("203107", pos, times, **kw2)


def test_c2_and_c4_decide_on_constructed_returns(tmp_path):
    """Committed h fixed first, then each forward return set to agree with T1's h: the scored h is the
    committed h (not recomputed from the scoring release), mean d is large and positive, C2 and C4 pass."""
    f = synthetic("2031-08", seed=3)
    pos = engine_positions(f)
    for r in pos[pos["trial"] == "T1"].itertuples():
        m = pd.Period(r.month, "M")
        v = abs(f.loc[m, r.factor]) + 0.5
        f.loc[m, r.factor] = v if r.h == "1" else -v
    _, times, kw = setup_score(tmp_path, f)
    res = fw.score("203108", pos, times, **kw)
    v = res["trials"]["T1"]["verdict"]
    assert v["C2"] and v["C4"] and res["headline"].startswith("T1: meets C2 and C4")
    assert res["vintage"]["h_rows_differing"] > 0  # h recomputed from the revised release is shown beside it


def test_interim_has_no_t_and_no_verdict(tmp_path):
    f = synthetic("2027-02", seed=9)
    raw, rel = tmp_path / "raw", tmp_path / "releases"
    (raw / "202702").mkdir(parents=True)
    _, man = write_release(raw / "202702", f, "202702")
    rel.mkdir()
    man.rename(rel / "202702.json")
    rows = []
    for m in pd.period_range("2026-09", "2027-03", freq="M"):
        rows += fw.positions_for(f, str(m))
    pos = pd.DataFrame(rows).astype(str)
    hbar = {t: {k: 0.0 for k in tr.factors} for t, tr in TRIALS.items()}
    h_prev = {t: {k: 1.0 for k in tr.factors} for t, tr in TRIALS.items()}
    out = fw.interim(pos, raw, rel, hbar, h_prev, now_utc="2027-04-01T00:00:00Z")
    assert out["trials"]["T1"]["months_recorded"] == 7 and out["trials"]["T1"]["months_with_return"] == 6
    assert out["months_to_scoring"] == 54
    keys = {k for row in out["trials"].values() for k in row}
    assert keys == {"months_recorded", "months_with_return", "cumulative_T", "cumulative_B3", "mean_d_pct_a_year"}
