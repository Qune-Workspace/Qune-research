"""Study 011 forward record, part 2 (fetch, lateness, interim, scoring), on synthetic series and zips only."""
import csv
import hashlib
import json

import pandas as pd
import pytest
from src import forward011 as fw
from src.data import FILES
from src.history import TRIALS
from src.rule import cohort_table, run

from tests.test_forward011 import synthetic, write_release

P = pd.Period


def hist_from(ind, last_rank="2026-08"):
    """cohorts.json in the history's layout, built by the history engine."""
    out = {}
    for t, s in TRIALS.items():
        tab = cohort_table(ind[s["set"]], s["F"], s["n"], P("2026-01", "M"))  # the forward months need 2026-03 on
        out[t] = {m: (v[0], v[1]) for m, v in tab.items() if P(m, "M") <= P(last_rank, "M")}
    return out


def cut(ind, end):
    return {n: f[f.index <= P(end, "M")] for n, f in ind.items()}


def history_dir(tmp_path, ind):
    d = tmp_path / "hist"
    d.mkdir()
    for n, f in ind.items():
        f.to_csv(d / f"industries_{n}.csv", index_label="month")
    return d


class Resp:
    def __init__(self, content: bytes):
        self.content = content
        self.text = content.decode("latin-1")

    def raise_for_status(self):
        pass


def fake_get(src_dir):
    page = "".join(f'<a href="ftp/{name}">x</a>' for name in FILES.values()).encode()

    def get(url, headers=None, timeout=None):
        if url == fw.LIBRARY_PAGE:
            return Resp(page)
        return Resp((src_dir / url.rsplit("/", 1)[-1]).read_bytes())
    return get


def test_forward_frame_equals_the_history_engine():
    """Same cohorts and returns: d, turnover and costs equal rule.run month by month, first month included."""
    ind = synthetic("2027-08")
    for t, s in TRIALS.items():
        r = ind[s["set"]]
        cmap = {P(m, "M"): v[:2] for m, v in cohort_table(r, s["F"], s["n"], P("2026-01", "M")).items()}
        months = pd.period_range("2026-09", "2027-08", freq="M")
        a = fw.forward_frame(r, cmap, months, s["n"])
        b = run(r, s["F"], s["n"], P(s["first"], "M")).loc[months]
        for c in ("d_gross", "turnover", "d_base", "d_stress", "empty_legs"):
            assert a[c].to_numpy() == pytest.approx(b[c].to_numpy(), abs=1e-12), (t, c)


def test_empty_leg_contributes_zero():
    ind = synthetic("2026-09")
    s = TRIALS["M1"]
    r = ind[17].copy()
    cmap = {P(m, "M"): v[:2] for m, v in cohort_table(r, s["F"], s["n"], P("2026-01", "M")).items()}
    W, _ = cmap[P("2026-08", "M")]
    r.loc[P("2026-09", "M"), W] = float("nan")
    a = fw.forward_frame(r, cmap, pd.period_range("2026-09", "2026-09", freq="M"), 3)
    b = run(r, s["F"], s["n"], P(s["first"], "M")).loc[[P("2026-09", "M")]]
    assert a["empty_legs"].iloc[0] >= 1
    assert a["d_base"].iloc[0] == pytest.approx(b["d_base"].iloc[0], abs=1e-12)


def test_cohort_map_history_before_first_rank_and_committed_after():
    ind = synthetic("2026-09")
    hist = hist_from(ind)
    row = {r["trial"]: r for r in fw.cohorts_for(ind, "2026-09")}
    fake = dict(row["M1"], winners="A;B;C", losers="D;E;F")
    pos = pd.DataFrame([fake])
    cmap = fw.cohort_map(pos, "M1", hist["M1"])
    assert cmap[P("2026-08", "M")] == (["A", "B", "C"], ["D", "E", "F"])  # the committed row, not the history's
    assert cmap[P("2026-07", "M")] == hist["M1"]["2026-07"]
    bad = pd.DataFrame([dict(row["M1"], ranking_month="2026-07")])
    with pytest.raises(SystemExit, match="not t − 1"):
        fw.cohort_map(bad, "M1", hist["M1"])


def test_missing_cohort_refused():
    ind = synthetic("2026-09")
    with pytest.raises(SystemExit, match="no cohort ranked"):
        fw.forward_frame(ind[17], {}, pd.period_range("2026-09", "2026-09", freq="M"), 3)


def test_preamble_and_names_read_no_value(tmp_path):
    ind = synthetic()
    raw, _ = write_release(tmp_path, ind, "202609")
    for n, name in FILES.items():
        b = (raw / name).read_bytes()
        assert fw.preamble_of(b) == [l for l in [f"This file was created {'by CMPT_IND_RETS ' if n == 30 else ''}"
                                                 f"using the 202609 CRSP database."]]
        assert fw.industry_names(b) == list(ind[n].columns)


def _setup_fetch(tmp_path, ind, release, names_ind=None):
    snap_dir = tmp_path / "snap"
    snap_dir.mkdir()
    _, snap_man = write_release(snap_dir, ind, "202608")
    src = tmp_path / "src"
    src.mkdir()
    write_release(src, names_ind or ind, release)
    return snap_man, src, history_dir(tmp_path, ind)


def test_fetch_keeps_a_new_release_and_logs(tmp_path):
    ind = synthetic("2026-09")
    snap_man, src, hdir = _setup_fetch(tmp_path, cut(ind, "2026-08"), "202609")
    write_release(src, ind, "202609")
    raw, rel = tmp_path / "raw", tmp_path / "releases"
    res = fw.fetch(fake_get(src), raw, rel, snap_man, hdir, now=lambda: "2026-11-05T10:00:00Z")
    assert res["kept"] and res["release"] == "202609"
    man = json.loads((rel / "202609.json").read_text())
    assert fw.release_of(rel / "202609.json") == "202609"
    assert all(man["files"][n]["sha256"] == hashlib.sha256((raw / "202609" / n).read_bytes()).hexdigest()
               for n in FILES.values())
    assert not list(raw.glob("_incoming-*"))
    again = fw.fetch(fake_get(src), raw, rel, snap_man, hdir, now=lambda: "2026-11-05T11:00:00Z")
    assert not again["kept"] and "already archived" in again["reason"]
    log = list(csv.DictReader((rel / "fetch_log.csv").open()))
    assert [r["kept"] for r in log] == ["True", "False"]
    # the archived release is read by record() and gives the next month's cohorts
    ind_rel = fw.load_industries(raw / "202609", rel / "202609.json")
    assert ind_rel[17].index[-1] == P("2026-09", "M")


@pytest.mark.parametrize("case", ["snapshot", "names", "mixed"])
def test_fetch_refusals(tmp_path, case):
    ind = synthetic("2026-09")
    names = None
    if case == "names":
        names = {n: f.rename(columns={f.columns[0]: "Renamed"}) for n, f in ind.items()}
    snap_man, src, hdir = _setup_fetch(tmp_path, cut(ind, "2026-08"), "202608" if case == "snapshot" else "202609",
                                       names)
    if case == "mixed":
        write_release(src, ind, "202609", zip_release={30: "202610"})
    raw, rel = tmp_path / "raw", tmp_path / "releases"
    res = fw.fetch(fake_get(src), raw, rel, snap_man, hdir, now=lambda: "2026-11-05T10:00:00Z")
    assert not res["kept"]
    assert {"snapshot": "not newer", "names": "industry names differ", "mixed": "different releases"}[case] in res["reason"]
    assert not list(rel.glob("2*.json")) and not [p for p in raw.iterdir() if p.is_dir()]


def test_fetch_older_than_latest_refused(tmp_path):
    ind = synthetic("2026-10")
    snap_man, src, hdir = _setup_fetch(tmp_path, cut(ind, "2026-08"), "202609")
    rel = tmp_path / "releases"
    rel.mkdir()
    (rel / "202610.json").write_text("{}")
    res = fw.fetch(fake_get(src), tmp_path / "raw", rel, snap_man, hdir, now=lambda: "2026-11-05T10:00:00Z")
    assert not res["kept"] and "older than the latest" in res["reason"]


def test_late_flags():
    releases = {"202609": {"files": {"a": {"downloaded_at_utc": "2026-10-05T10:00:00Z"},
                                     "b": {"downloaded_at_utc": "2026-10-05T10:00:05Z"}}}}
    pos = pd.DataFrame([{"month": "2026-09", "trial": "M1"}, {"month": "2026-10", "trial": "M1"}])
    times = {("2026-09", "M1"): {"time": pd.Timestamp("2026-10-05T10:00:06Z")},
             ("2026-10", "M1"): {"time": pd.Timestamp("2026-10-06T10:00:00Z")}}
    assert list(fw.late_flags(pos, times, releases)) == [True, False]  # 2026-10's return is in no release yet
    with pytest.raises(SystemExit, match="not in any commit"):
        fw.late_flags(pos, {}, releases)


def _forward_book(ind, last="2031-08"):
    """Rows for every forward month from release t − 1 (as record() writes them), with their first commits."""
    rows = []
    for m in pd.period_range("2026-09", last, freq="M"):
        rel = (m - 1).strftime("%Y%m")
        for r in fw.cohorts_for(cut(ind, str(m - 1)), str(m)):
            r.update(release=rel, release_last_month=str(m - 1), files_sha256=f"sha-{rel}", manifest_sha256="x",
                     downloaded_at_utc="d", recorded_at_utc="r", late=False)
            rows.append({c: str(r[c]) for c in fw.COLUMNS})
    pos = pd.DataFrame(rows)
    times = {(r["month"], r["trial"]): {"time": pd.Timestamp("2026-10-01T00:00:00Z"),
                                        "row": {c: r[c] for c in fw.COLUMNS if c != "late"}} for r in rows}
    return pos, times


def _own(ind):
    return lambda month: (cut(ind, str(P(month, "M") - 1)), (P(month, "M") - 1).strftime("%Y%m"),
                          f"sha-{(P(month, 'M') - 1).strftime('%Y%m')}")


def _score_setup(tmp_path, ind):
    snap = tmp_path / "snap"
    snap.mkdir()
    _, snap_man = write_release(snap, cut(ind, "2026-08"), "202608")
    raw, rel = tmp_path / "raw", tmp_path / "releases"
    (raw / "203108").mkdir(parents=True)
    _, man = write_release(raw / "203108", ind, "203108")
    rel.mkdir()
    m = json.loads(man.read_text())
    (rel / "203108.json").write_text(json.dumps(m))
    return snap, snap_man, raw, rel


def test_score_end_to_end_and_once(tmp_path, monkeypatch):
    monkeypatch.setattr(fw, "_ever_committed", lambda p: False)
    ind = synthetic("2031-08", seed=5)
    pos, times = _forward_book(ind)
    snap, snap_man, raw, rel = _score_setup(tmp_path, ind)
    out = tmp_path / "score.json"
    res = fw.score("203108", pos, times, raw, rel, snap, snap_man, hist_from(ind), out, "2031-10-01T00:00:00Z",
                   own_release=_own(ind))
    months = pd.period_range("2026-09", "2031-08", freq="M")
    for t, s in TRIALS.items():
        ref = run(ind[s["set"]], s["F"], s["n"], P(s["first"], "M")).loc[months]
        assert res["trials"][t]["d"]["mean_pct_a_year"] == pytest.approx(ref["d_base"].mean() * 12, abs=1e-10)
        assert res["trials"][t]["stress_mean_d_pct_a_year"] == pytest.approx(ref["d_stress"].mean() * 12, abs=1e-10)
        assert res["trials"][t]["d"]["months"] == 60
    assert res["headline"].startswith("M1: ") and fw.LABEL in res["headline"]
    assert res["vintage"]["cohort_rows_differing"] == 0 and res["vintage"]["cohort_rows_compared"] == 180
    assert res["vintage"]["per_file_over_history"]["17"]["cells_differing"] == 0
    json.loads(out.read_text())
    with pytest.raises(SystemExit, match="scored once"):
        fw.score("203108", pos, times, raw, rel, snap, snap_man, hist_from(ind), out, own_release=_own(ind))


def test_score_refusals(tmp_path, monkeypatch):
    monkeypatch.setattr(fw, "_ever_committed", lambda p: False)
    ind = synthetic("2031-08", seed=6)
    pos, times = _forward_book(ind)
    snap, snap_man, raw, rel = _score_setup(tmp_path, ind)
    args = (raw, rel, snap, snap_man, hist_from(ind))
    with pytest.raises(SystemExit, match="the scoring release is 203108"):
        fw.score("203109", pos, times, *args, tmp_path / "a.json", own_release=_own(ind))
    with pytest.raises(SystemExit, match="not recorded"):
        fw.score("203108", pos[pos["month"] != "2030-01"], times, *args, tmp_path / "b.json", own_release=_own(ind))
    edited = pos.copy()
    edited.loc[0, "winners"] = "X;Y;Z"
    with pytest.raises(SystemExit, match="differs from its first commit"):
        fw.score("203108", edited, times, *args, tmp_path / "c.json", own_release=_own(ind))
    # a row whose cohort is not what its own release gives
    other = synthetic("2031-08", seed=7)
    with pytest.raises(SystemExit, match="not reproduced"):
        fw.score("203108", pos, times, *args, tmp_path / "d.json", own_release=_own(other))
    assert not any((tmp_path / f"{x}.json").exists() for x in "abcd")


def test_check_rows_reports_missing_raw_files():
    ind = synthetic("2031-08", seed=8)
    pos, times = _forward_book(ind, "2026-10")

    def own(month):
        if month == "2026-10":
            raise FileNotFoundError
        return _own(ind)(month)
    assert fw.check_rows(pos, times, own) == ["2026-10"]


def test_interim_has_no_t_and_no_verdict(tmp_path):
    ind = synthetic("2026-10", seed=9)
    pos, _ = _forward_book(ind, "2026-10")
    rel, raw = tmp_path / "releases", tmp_path / "raw"
    rel.mkdir()
    empty = fw.interim(pos, raw, rel, hist_from(ind), "2026-11-01T00:00:00Z")
    assert empty["trials"]["M1"]["months_with_return"] == 0 and empty["months_to_scoring"] == 60
    (raw / "202610").mkdir(parents=True)
    _, man = write_release(raw / "202610", ind, "202610")
    (rel / "202610.json").write_text(man.read_text())
    res = fw.interim(pos, raw, rel, hist_from(ind), "2026-11-01T00:00:00Z")
    ref = run(ind[17], 6, 3, P("1927-06", "M")).loc[pd.period_range("2026-09", "2026-10", freq="M")]
    assert res["trials"]["M1"]["months_with_return"] == 2
    assert res["trials"]["M1"]["mean_d_pct_a_year"] == pytest.approx(ref["d_base"].mean() * 12, abs=1e-10)
    assert "t" not in json.dumps(res["trials"]).replace('"', " ").split() and res["heading"] == fw.NOT_YET_SCORED
