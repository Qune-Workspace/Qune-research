"""Study 010 forward record, part 1 (position records), on synthetic series and zips only."""
import csv
import hashlib
import io
import json
import zipfile

import numpy as np
import pandas as pd
import pytest
from src import forward010 as fw
from src.rule import TRIALS, run

STARTS = {"SMB": "1926-07", "HML": "1926-07", "ST_Rev": "1926-02", "LT_Rev": "1931-01"}


def synthetic(end: str = "2026-08", seed: int = 11) -> pd.DataFrame:
    idx = pd.period_range("1926-02", end, freq="M")
    rng = np.random.default_rng(seed)
    f = pd.DataFrame(np.round(rng.normal(0.3, 3.0, (len(idx), 4)), 2), index=idx, columns=list(STARTS))
    for k, s in STARTS.items():
        f.loc[f.index < pd.Period(s, "M"), k] = np.nan
    return f


def write_release(tmp_path, f: pd.DataFrame, release: str = "202608") -> tuple:
    """Three zips in the library's layout, with a manifest of their SHA-256 and header lines."""
    groups = {"F-F_Research_Data_Factors_CSV.zip": ["SMB", "HML"], "F-F_ST_Reversal_Factor_CSV.zip": ["ST_Rev"],
              "F-F_LT_Reversal_Factor_CSV.zip": ["LT_Rev"]}
    man = {"files": {}}
    head = f"This file was created using the {release} CRSP database."
    for name, cols in groups.items():
        sub = f[cols].dropna(how="all")
        lines = [head, "", "," + ",".join(cols)]
        lines += [p.strftime("%Y%m") + "," + ",".join(f"{v:.2f}" for v in row) for p, row in sub.iterrows()]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(name.replace("_CSV.zip", ".csv"), "\n".join(lines) + "\n")
        b = buf.getvalue()
        (tmp_path / name).write_bytes(b)
        man["files"][name] = {"sha256": hashlib.sha256(b).hexdigest(), "preamble_lines": [head],
                              "downloaded_at_utc": "2026-10-26T09:17:57Z"}
    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(man))
    return tmp_path, mp


def test_positions_match_the_history_engine():
    """h_t from f up to t − 1 equals the engine's h_t on a frame that ends at t."""
    f = synthetic("2026-09")
    t = "2026-09"
    rows = fw.positions_for(f, t)
    for trial in TRIALS.values():
        h = run(f, trial, t, 0.10)["h"].loc[pd.Period(t, "M")]
        got = {r["factor"]: r["h"] for r in rows if r["trial"] == trial.trial_id}
        assert got == {k: int(h[k]) for k in trial.factors}


def test_month_t_value_never_used():
    f = synthetic("2026-09")
    a = fw.positions_for(f, "2026-09")
    g = f.copy()
    g.loc[pd.Period("2026-09", "M")] = -50.0  # month t itself
    assert fw.positions_for(g, "2026-09") == a
    g.loc[pd.Period("2026-08", "M"), "SMB"] += 40.0  # t − 1 is used
    b = fw.positions_for(g, "2026-09")
    assert [r for r in b if r["factor"] == "SMB"] != [r for r in a if r["factor"] == "SMB"]


def test_formation_lengths_and_trials():
    rows = fw.positions_for(synthetic(), "2026-09")
    assert {(r["trial"], r["factor"]) for r in rows} == {(t, k) for t, tr in TRIALS.items() for k in tr.factors}
    assert {r["formation_months"] for r in rows if r["trial"] == "T1b"} == {6}
    assert {r["formation_months"] for r in rows if r["trial"] != "T1b"} == {12}


def test_tie_takes_minus_one():
    f = synthetic()
    t = pd.Period("2026-09", "M")
    f.loc[pd.period_range(t - 12, t - 1, freq="M"), "HML"] = 0.0
    rows = fw.positions_for(f, "2026-09")
    assert {r["h"] for r in rows if r["factor"] == "HML" and r["formation_months"] == 12} == {-1}


def test_refuses_inside_h_and_missing_t_minus_1():
    f = synthetic()
    with pytest.raises(ValueError):
        fw.positions_for(f, "2026-08")
    with pytest.raises(ValueError):
        fw.positions_for(f, "2026-10")  # release ends 2026-08; 2026-10 needs 2026-09


def test_record_writes_once(tmp_path):
    raw, mp = write_release(tmp_path, synthetic("2026-08"))
    out = tmp_path / "positions.csv"
    rows = fw.record("2026-09", raw, mp, out=out, now_utc="2026-10-26T12:00:00Z")
    assert len(rows) == 4 + 2 + 4 and not any(r["late"] for r in rows)
    assert {r["release"] for r in rows} == {"202608"} and {r["release_last_month"] for r in rows} == {"2026-08"}
    assert out.read_text().split("\n", 1)[0] == ",".join(fw.COLUMNS)
    with pytest.raises(SystemExit):
        fw.record("2026-09", raw, mp, out=out)
    with out.open(newline="") as fh:
        assert len(list(csv.DictReader(fh))) == 10
    # The next month from its own first release appends; the earlier rows stay byte-identical.
    before = out.read_text()
    raw2 = tmp_path / "r2"
    raw2.mkdir()
    raw2, mp2 = write_release(raw2, synthetic("2026-09"), release="202609")
    nxt = fw.record("2026-10", raw2, mp2, out=out)
    assert out.read_text().startswith(before) and len(nxt) == 10
    ref = fw.positions_for(synthetic("2026-09"), "2026-10")
    assert [r["h"] for r in nxt] == [r["h"] for r in ref]


def test_record_refuses_a_later_release(tmp_path):
    """§11: only the first release that contains t − 1 (code review must-fix 1)."""
    raw, mp = write_release(tmp_path, synthetic("2026-10"), release="202610")
    out = tmp_path / "positions.csv"
    with pytest.raises(SystemExit):
        fw.record("2026-10", raw, mp, out=out)
    with pytest.raises(SystemExit):
        fw.record("2026-09", raw, mp, out=out)
    assert not out.exists()


def test_record_refuses_a_partial_release(tmp_path):
    f = synthetic("2026-08")
    f.loc[pd.Period("2026-08", "M"), "LT_Rev"] = np.nan  # LT_Rev ends at t − 2
    raw, mp = write_release(tmp_path, f)
    with pytest.raises(SystemExit):
        fw.record("2026-09", raw, mp, out=tmp_path / "positions.csv")
    g = synthetic("2026-09")
    g.loc[pd.Period("2026-09", "M"), ["ST_Rev", "LT_Rev"]] = np.nan  # 3-factor file already has month t
    raw2 = tmp_path / "r2"
    raw2.mkdir()
    raw2, mp2 = write_release(raw2, g, release="202608")
    with pytest.raises(SystemExit):
        fw.record("2026-09", raw2, mp2, out=tmp_path / "positions.csv")
    assert not (tmp_path / "positions.csv").exists()


def test_record_refuses_a_malformed_file_and_survives_a_crash(tmp_path, monkeypatch):
    raw, mp = write_release(tmp_path, synthetic("2026-08"))
    out = tmp_path / "positions.csv"
    out.write_text(",".join(fw.COLUMNS) + "\nno-final-newline")
    with pytest.raises(SystemExit):
        fw.record("2026-09", raw, mp, out=out)
    out.unlink()
    raw2 = tmp_path / "r2"
    raw2.mkdir()
    raw2, mp2 = write_release(raw2, synthetic("2026-09"), release="202609")
    fw.record("2026-10", raw2, mp2, out=out)
    before = out.read_bytes()

    def boom(*_a, **_k):
        raise RuntimeError("crash")

    monkeypatch.setattr(csv.DictWriter, "writerows", boom)
    with pytest.raises(RuntimeError):
        fw.record("2026-09", raw, mp, out=out)
    assert out.read_bytes() == before and not out.with_suffix(".tmp").exists()


def test_t1b_ignores_t_minus_7_and_matches_engine_over_seeds():
    f = synthetic("2026-09")
    t = pd.Period("2026-09", "M")
    a = [r for r in fw.positions_for(f, "2026-09") if r["trial"] == "T1b"]
    g = f.copy()
    g.loc[t - 7] += 30.0
    assert [r for r in fw.positions_for(g, "2026-09") if r["trial"] == "T1b"] == a
    for seed in (1, 2, 3):
        for m in ("2026-12", "2028-03"):
            fs = synthetic(m, seed)
            rows = fw.positions_for(fs, m)
            for trial in TRIALS.values():
                h = run(fs, trial, m, 0.10)["h"].loc[pd.Period(m, "M")]
                got = {r["factor"]: r["h"] for r in rows if r["trial"] == trial.trial_id}
                assert got == {k: int(h[k]) for k in trial.factors}


def test_release_lines_must_agree(tmp_path):
    raw, mp = write_release(tmp_path, synthetic())
    man = json.loads(mp.read_text())
    man["files"]["F-F_ST_Reversal_Factor_CSV.zip"]["preamble_lines"] = ["created using the 202607 CRSP database"]
    mp.write_text(json.dumps(man))
    with pytest.raises(ValueError):
        fw.release_of(mp)


def test_freeze_hbar_once(tmp_path):
    s = {"cost_cases": {"base": {"trials": {t: {"per_factor": {k: {"hbar": 0.1 * i} for i, k in enumerate(tr.factors)}}
                                            for t, tr in TRIALS.items()}}}}
    sp = tmp_path / "summary.json"
    sp.write_text(json.dumps(s))
    out = tmp_path / "frozen.json"
    first = fw.freeze_hbar(sp, out)
    assert fw.freeze_hbar(sp, out)["hbar"] == first["hbar"]
    s["cost_cases"]["base"]["trials"]["T1"]["per_factor"]["SMB"]["hbar"] = 0.9
    sp.write_text(json.dumps(s))
    with pytest.raises(SystemExit):
        fw.freeze_hbar(sp, out)


def test_record_checks_the_zips_own_release_line_and_download_time(tmp_path):
    """Re-check notes N1 and N2: the zip's own header must name t − 1; a manifest without a download time stops."""
    raw, mp = write_release(tmp_path, synthetic("2026-08"), release="202610")
    man = json.loads(mp.read_text())
    for v in man["files"].values():
        v["preamble_lines"] = ["This file was created using the 202608 CRSP database."]
    mp.write_text(json.dumps(man))
    with pytest.raises(SystemExit):
        fw.record("2026-09", raw, mp, out=tmp_path / "positions.csv")
    raw2 = tmp_path / "r2"
    raw2.mkdir()
    raw2, mp2 = write_release(raw2, synthetic("2026-08"))
    man = json.loads(mp2.read_text())
    del man["files"]["F-F_ST_Reversal_Factor_CSV.zip"]["downloaded_at_utc"]
    mp2.write_text(json.dumps(man))
    with pytest.raises(SystemExit):
        fw.record("2026-09", raw2, mp2, out=tmp_path / "positions.csv")
    assert not (tmp_path / "positions.csv").exists()
