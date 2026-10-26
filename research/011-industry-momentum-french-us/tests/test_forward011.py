"""Study 011 forward record, part 1 (cohort records), on synthetic series and zips only."""
import csv
import hashlib
import io
import json
import zipfile

import numpy as np
import pandas as pd
import pytest
from src import forward011 as fw
from src import rule
from src.data import FILES
from src.history import TRIALS
from src.rule import cohort_table, formation_returns

P = pd.Period


def synthetic(end: str = "2026-08", seed: int = 11) -> dict[int, pd.DataFrame]:
    idx = pd.period_range("1926-07", end, freq="M")
    rng = np.random.default_rng(seed)
    out = {}
    for n in (17, 30):
        cols = [f"I{n}_{i:02d}" for i in range(n)]
        out[n] = pd.DataFrame(np.round(rng.normal(1.0, 5.0, (len(idx), n)), 2), index=idx, columns=cols)
    return out


def write_release(tmp_path, ind: dict[int, pd.DataFrame], release: str = "202608",
                  zip_release: dict[int, str] | None = None) -> tuple:
    """Two zips in the library's layout (value-weighted monthly section), with a manifest."""
    man = {"files": {}}
    for n, name in FILES.items():
        by = "by CMPT_IND_RETS " if n == 30 else ""  # the library's own wording per file (data step)
        head = f"This file was created {by}using the {release} CRSP database."
        zhead = f"This file was created {by}using the {(zip_release or {}).get(n, release)} CRSP database."
        f = ind[n]
        lines = [zhead, "", "  Average Value Weighted Returns -- Monthly", "," + ",".join(f.columns)]
        lines += [p.strftime("%Y%m") + "," + ",".join(f"{v:.2f}" for v in row) for p, row in f.iterrows()]
        lines += ["", "  Average Equal Weighted Returns -- Monthly"]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(name.replace("_CSV.zip", ".csv"), "\n".join(lines) + "\n")
        b = buf.getvalue()
        (tmp_path / name).write_bytes(b)
        man["files"][name] = {"sha256": hashlib.sha256(b).hexdigest(), "preamble_lines": [head],
                              "downloaded_at_utc": "2026-10-26T15:31:23Z"}
    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(man))
    return tmp_path, mp


def test_cohorts_match_the_history_engine():
    """The cohort recorded for t equals the history engine's cohort ranked at t − 1."""
    ind = synthetic("2026-09")
    rows = {r["trial"]: r for r in fw.cohorts_for(ind, "2026-09")}
    for tid, spec in TRIALS.items():
        w, lo, ties = cohort_table(ind[spec["set"]], spec["F"], spec["n"], P("2026-08", "M"))["2026-08"]
        assert rows[tid]["winners"].split(";") == w
        assert rows[tid]["losers"].split(";") == lo
        assert rows[tid]["boundary_ties"] == ties
        assert rows[tid]["ranking_month"] == "2026-08"
        assert len(rows[tid]["winners"].split(";")) == spec["n"]


def test_month_t_value_never_used():
    ind = synthetic("2026-09")
    a = fw.cohorts_for(ind, "2026-09")
    g = {n: f.copy() for n, f in ind.items()}
    for f in g.values():
        f.loc[P("2026-09", "M")] = -90.0  # month t itself
    assert fw.cohorts_for(g, "2026-09") == a
    for f in g.values():
        f.loc[P("2026-08", "M"), f.columns[0]] = 95.0  # t − 1 is used
    b = {r["trial"]: r for r in fw.cohorts_for(g, "2026-09")}
    assert all(b[t]["winners"].split(";")[0] == g[TRIALS[t]["set"]].columns[0] for t in TRIALS)


def test_formation_returns_full_precision_and_reproduce_the_rank():
    ind = synthetic()
    for r in fw.cohorts_for(ind, "2026-09"):
        R = {k: float(v) for k, v in (x.split("=") for x in r["formation_returns"].split(";"))}
        assert len(R) == r["industries"]
        order = sorted(R, key=lambda c: (-round(R[c], 10), list(R).index(c)))
        assert order[: r["n_side"]] == r["winners"].split(";")
        assert order[-r["n_side"]:] == r["losers"].split(";")
        assert r["formation_months"] == TRIALS[r["trial"]]["F"]


def test_inside_history_refused():
    with pytest.raises(ValueError):
        fw.cohorts_for(synthetic(), "2026-08")


def test_record_writes_once_and_refuses_a_second(tmp_path):
    raw, mp = write_release(tmp_path, synthetic())
    out = tmp_path / "cohorts.csv"
    rows = fw.record("2026-09", raw, mp, out, now_utc="2026-10-26T17:40:00Z")
    assert [r["trial"] for r in rows] == ["M1", "M1a", "M1b"]
    got = list(csv.DictReader(out.open()))
    assert [g["trial"] for g in got] == ["M1", "M1a", "M1b"]
    assert {g["release"] for g in got} == {"202608"} and {g["late"] for g in got} == {"False"}
    assert out.read_text().split("\n", 1)[0] == ",".join(fw.COLUMNS)
    before = out.read_bytes()
    with pytest.raises(SystemExit, match="already recorded"):
        fw.record("2026-09", raw, mp, out)
    assert out.read_bytes() == before


def test_later_release_refused(tmp_path):
    raw, mp = write_release(tmp_path, synthetic("2026-09"), release="202609")
    with pytest.raises(SystemExit, match="is not 202608"):
        fw.record("2026-09", raw, mp, tmp_path / "c.csv")


def test_file_must_end_at_t_minus_1(tmp_path):
    ind = synthetic()
    ind[30] = ind[30].iloc[:-1]  # the 30-industry file ends a month early
    raw, mp = write_release(tmp_path, ind)
    with pytest.raises(SystemExit, match="must end at 2026-08"):
        fw.record("2026-09", raw, mp, tmp_path / "c.csv")


def test_zip_header_must_agree_with_manifest(tmp_path):
    raw, mp = write_release(tmp_path, synthetic(), zip_release={30: "202607"})
    with pytest.raises(SystemExit, match="own header"):
        fw.record("2026-09", raw, mp, tmp_path / "c.csv")


def test_changed_zip_refused(tmp_path):
    raw, mp = write_release(tmp_path, synthetic())
    name = FILES[17]
    (raw / name).write_bytes((raw / name).read_bytes() + b"\0")
    with pytest.raises(SystemExit, match="SHA-256"):
        fw.record("2026-09", raw, mp, tmp_path / "c.csv")


def test_malformed_file_refused_and_kept(tmp_path):
    raw, mp = write_release(tmp_path, synthetic())
    out = tmp_path / "c.csv"
    out.write_text("month,trial\n2026-09,M1\n")
    with pytest.raises(SystemExit, match="malformed"):
        fw.record("2026-09", raw, mp, out)
    assert out.read_text() == "month,trial\n2026-09,M1\n"


def test_append_keeps_earlier_rows(tmp_path):
    ind = synthetic("2026-09")
    raw1 = tmp_path / "a"
    raw1.mkdir()
    r1, m1 = write_release(raw1, {n: f.iloc[:-1] for n, f in ind.items()}, "202608")
    out = tmp_path / "c.csv"
    fw.record("2026-09", r1, m1, out, now_utc="2026-10-26T17:40:00Z")
    first = out.read_text()
    raw2 = tmp_path / "b"
    raw2.mkdir()
    r2, m2 = write_release(raw2, ind, "202609")
    fw.record("2026-10", r2, m2, out, now_utc="2026-11-30T12:00:00Z")
    text = out.read_text()
    assert text.startswith(first)
    assert [r["month"] for r in csv.DictReader(text.splitlines())] == ["2026-09"] * 3 + ["2026-10"] * 3


# --- after the separate code review (CODE_REVIEW.md, fourth part) ---------------------------------------

def test_crash_mid_write_leaves_the_file_whole(tmp_path, monkeypatch):
    raw, mp = write_release(tmp_path, synthetic())
    out = tmp_path / "c.csv"
    out.write_text(",".join(fw.COLUMNS) + "\n")
    before = out.read_bytes()

    def boom(self, rows):
        self.writerow(list(rows)[0])
        raise OSError("disk full")

    monkeypatch.setattr(csv.DictWriter, "writerows", boom)
    with pytest.raises(OSError):
        fw.record("2026-09", raw, mp, out)
    assert out.read_bytes() == before
    assert not out.with_suffix(".tmp").exists()


def test_file_ending_after_t_minus_1_refused(tmp_path):
    ind = synthetic("2026-09")
    ind[30] = ind[30].iloc[:-1]  # 17 reaches 2026-09 under a release named 202608
    raw, mp = write_release(tmp_path, ind, "202608")
    with pytest.raises(SystemExit, match="must end at 2026-08"):
        fw.record("2026-09", raw, mp, tmp_path / "c.csv")


def test_formation_returns_exact_and_nan_left_out():
    ind = synthetic()
    ind[17].loc[P("2026-08", "M"), ind[17].columns[4]] = np.nan
    for r in fw.cohorts_for(ind, "2026-09"):
        spec = TRIALS[r["trial"]]
        want = formation_returns(ind[spec["set"]], spec["F"]).loc[P("2026-08", "M")].dropna()
        got = {k: float(v) for k, v in (x.split("=") for x in r["formation_returns"].split(";"))}
        assert list(got) == list(want.index)
        assert all(got[k] == float(want[k]) for k in got)  # exact, not rounded
    assert "I17_04" not in fw.cohorts_for(ind, "2026-09")[0]["formation_returns"]


def test_column_order_breaks_a_boundary_tie():
    ind = synthetic()
    f = ind[17]
    m = P("2026-08", "M")
    R = formation_returns(f, 6).loc[m].sort_values(ascending=False)
    third, fourth = R.index[2], R.index[3]
    lo, hi = sorted([third, fourth], key=list(f.columns).index)
    f.loc[pd.period_range(m - 5, m, freq="M"), hi] = f.loc[pd.period_range(m - 5, m, freq="M"), lo].values
    row = {r["trial"]: r for r in fw.cohorts_for(ind, "2026-09")}["M1"]
    assert lo in row["winners"].split(";") and hi not in row["winners"].split(";")
    assert row["boundary_ties"] == 1


def test_metadata_columns(tmp_path):
    raw, mp = write_release(tmp_path, synthetic())
    out = tmp_path / "c.csv"
    fw.record("2026-09", raw, mp, out, now_utc="2026-10-26T17:40:00Z")
    got = list(csv.DictReader(out.open()))
    assert {g["release_last_month"] for g in got} == {"2026-08"}
    assert {g["manifest_sha256"] for g in got} == {hashlib.sha256(mp.read_bytes()).hexdigest()}
    assert all("2026-10-26T15:31:23Z" in g["downloaded_at_utc"] for g in got)
    assert {g["recorded_at_utc"] for g in got} == {"2026-10-26T17:40:00Z"}


def test_missing_download_time_refused(tmp_path):
    raw, mp = write_release(tmp_path, synthetic())
    man = json.loads(mp.read_text())
    del man["files"][FILES[30]]["downloaded_at_utc"]
    mp.write_text(json.dumps(man))
    with pytest.raises(SystemExit, match="no download time"):
        fw.record("2026-09", raw, mp, tmp_path / "c.csv")


@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("month", ["2026-09", "2027-01", "2031-08"])
def test_engine_agreement_sweep_and_windows(seed, month):
    t = P(month, "M")
    ind = synthetic(str(t), seed)
    rows = {r["trial"]: r for r in fw.cohorts_for(ind, month)}
    for tid, spec in TRIALS.items():
        w, lo, _ = rule.cohort_table(ind[spec["set"]], spec["F"], spec["n"], t - 1)[str(t - 1)]
        assert (rows[tid]["winners"].split(";"), rows[tid]["losers"].split(";")) == (w, lo)
    g = {n: f.copy() for n, f in ind.items()}
    for f in g.values():
        f.loc[t - 13] = 80.0  # outside every formation window
    assert fw.cohorts_for(g, month) == list(rows.values())
    g = {n: f.copy() for n, f in ind.items()}
    for f in g.values():
        f.loc[t - 7, f.columns[0]] = 900.0  # inside M1b's window only
    after = {r["trial"]: r for r in fw.cohorts_for(g, month)}
    assert after["M1"] == rows["M1"] and after["M1a"] == rows["M1a"]
    assert after["M1b"]["winners"].split(";")[0] == g[17].columns[0]


def test_a_gap_is_refused(tmp_path):
    ind = synthetic("2026-09")
    raw, mp = write_release(tmp_path, ind, "202609")
    with pytest.raises(SystemExit, match="2026-09 is not recorded"):
        fw.record("2026-10", raw, mp, tmp_path / "c.csv")
