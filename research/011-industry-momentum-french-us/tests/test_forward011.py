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
from src.data import FILES
from src.history import TRIALS
from src.rule import cohort_table

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
        head = f"This file was created using the {release} CRSP database."
        zhead = f"This file was created using the {(zip_release or {}).get(n, release)} CRSP database."
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
