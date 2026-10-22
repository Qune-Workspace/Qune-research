"""§5.1 parsing and provenance without any network access, the hash-checked
reuse of earlier studies' files, the vendor module, the §5.3.2 overlap
statistics on toy series, and the ``reproduce.sh`` gates."""
import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import alpaca_bars, bil_overlap_check, fred, reuse_bars, tiingo_bars
from src.config import STUDY_DIR

FRED_TEXT = "observation_date,DTB3\n2024-01-01,\n2024-01-02,5.25\n2024-01-03,.\n2024-01-04,NaN\n2024-01-05,5.21\n"


def test_parse_fred_csv_treats_empty_dot_and_nan_as_missing():
    s = fred.parse_fred_csv(FRED_TEXT)
    assert len(s) == 5 and s.isna().sum() == 3
    assert s.loc["2024-01-02"] == 5.25 and s.loc["2024-01-05"] == 5.21
    assert isinstance(s.index, pd.DatetimeIndex) and s.name == "DTB3"


def test_parse_fred_csv_rejects_unsorted_dates():
    with pytest.raises(ValueError):
        fred.parse_fred_csv("observation_date,X\n2024-01-02,1\n2024-01-01,2\n")


def test_manifest_round_trip(tmp_path):
    manifest = tmp_path / "m.json"
    fred.update_manifest("a.csv", {"rows": 1}, manifest)
    fred.update_manifest("b.csv", {"rows": 2}, manifest)
    fred.update_manifest("a.csv", {"rows": 3}, manifest)
    assert json.loads(manifest.read_text()) == {"a.csv": {"rows": 3}, "b.csv": {"rows": 2}}
    f = tmp_path / "x.bin"
    f.write_bytes(b"abc")
    assert fred.sha256_of(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_alpaca_bars_to_frame_keys_by_new_york_date():
    bars = [{"t": "2024-01-03T05:00:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10, "n": 3, "vw": 1.4},
            {"t": "2024-01-02T05:00:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.0, "v": 10, "n": 3, "vw": 1.1}]
    frame = alpaca_bars.bars_to_frame(bars)
    assert list(frame.index) == list(pd.to_datetime(["2024-01-02", "2024-01-03"]))
    assert alpaca_bars.total_return_index(frame).tolist() == [1.0, 1.5]


def test_alpaca_credentials_come_from_the_environment_only(monkeypatch):
    monkeypatch.delenv(alpaca_bars.KEY_ENV, raising=False)
    monkeypatch.delenv(alpaca_bars.SECRET_ENV, raising=False)
    with pytest.raises(RuntimeError):
        alpaca_bars.credentials_from_env()
    monkeypatch.setenv(alpaca_bars.KEY_ENV, "k")
    monkeypatch.setenv(alpaca_bars.SECRET_ENV, "s")
    assert alpaca_bars.credentials_from_env() == {"APCA-API-KEY-ID": "k", "APCA-API-SECRET-KEY": "s"}


# --- Reuse of earlier studies' files -----------------------------------------------------

def _fake_study(root: Path, name: str, content: bytes, recorded_sha: str) -> Path:
    source = root / name
    (source / "data" / "raw").mkdir(parents=True)
    (source / "results").mkdir()
    for file in ("alpaca_IEF_1Day_all.csv", "fred_DTB3.csv", "tiingo_IEF_daily.csv"):
        (source / "data" / "raw" / file).write_bytes(content)
    (source / "results" / "data_manifest.json").write_text(json.dumps(
        {file: {"sha256": recorded_sha, "rows": 1, "source": "test"}
         for file in ("alpaca_IEF_1Day_all.csv", "fred_DTB3.csv", "tiingo_IEF_daily.csv")}))
    return source


def test_reuse_copies_only_when_the_hash_matches_the_source_manifest(tmp_path):
    content = b"date,close\n2016-01-04,100\n"
    probe = _fake_study(tmp_path / "probe", "001-x", content, "x")
    good = fred.sha256_of(probe / "data" / "raw" / "alpaca_IEF_1Day_all.csv")
    source = _fake_study(tmp_path, "001-slope", content, good)
    raw, manifest = tmp_path / "raw", tmp_path / "manifest.json"
    target = reuse_bars.reuse_study_001_bars("IEF", raw, manifest, source)
    assert target.read_bytes() == content
    entry = json.loads(manifest.read_text())["alpaca_IEF_1Day_all.csv"]
    assert entry["sha256"] == good and "Study 001" in entry["reused_from"] and "reused_at_utc" in entry
    assert reuse_bars.reuse_study_001_fred("DTB3", raw, manifest, source).name == "fred_DTB3.csv"
    source_002 = _fake_study(tmp_path / "s2", "002-slope", content, good)
    tiingo = reuse_bars.reuse_study_002_tiingo("IEF", raw, manifest, source_002)
    assert tiingo.name == "tiingo_IEF_daily.csv"
    assert "Study 002" in json.loads(manifest.read_text())["tiingo_IEF_daily.csv"]["reused_from"]
    # a second call with the file already in place writes nothing
    manifest.write_text("{}")
    reuse_bars.reuse_study_001_bars("IEF", raw, manifest, source)
    assert manifest.read_text() == "{}"
    # a mismatching hash refuses and copies nothing
    bad = _fake_study(tmp_path / "bad", "001-bad", content, "0" * 64)
    with pytest.raises(RuntimeError):
        reuse_bars.reuse_study_001_bars("IEF", tmp_path / "raw2", tmp_path / "m2.json", bad)
    assert not (tmp_path / "raw2").exists()


# --- Vendor module -----------------------------------------------------------------------

def test_tiingo_token_comes_from_the_environment_only(monkeypatch):
    monkeypatch.delenv(tiingo_bars.TOKEN_ENV, raising=False)
    with pytest.raises(RuntimeError):
        tiingo_bars.token_from_env()
    monkeypatch.setenv(tiingo_bars.TOKEN_ENV, " t ")
    assert tiingo_bars.token_from_env() == "t"


def test_tiingo_rows_to_frame_sorts_fills_and_rejects_duplicates():
    rows = [{"date": "2007-06-01T00:00:00.000Z", "close": 2.0, "adjClose": 1.9},
            {"date": "2007-05-31T00:00:00.000Z", "close": 1.0, "adjClose": 0.9}]
    frame = tiingo_bars.rows_to_frame(rows)
    assert list(frame.index) == list(pd.to_datetime(["2007-05-31", "2007-06-01"]))
    assert list(frame.columns) == list(tiingo_bars.COLUMNS)
    assert frame["adjClose"].tolist() == [0.9, 1.9] and frame["divCash"].isna().all()
    with pytest.raises(ValueError):
        tiingo_bars.rows_to_frame(rows + [rows[0]])
    with pytest.raises(RuntimeError):
        tiingo_bars.rows_to_frame([])


# --- §5.3.2 step 2 on toy series ---------------------------------------------------------

def test_bil_overlap_statistics_and_branches_on_toy_series():
    days = pd.bdate_range("2015-12-31", "2018-12-31")
    rng = np.random.default_rng(11)
    base = 91 * np.exp(np.cumsum(rng.normal(0, 0.0001, len(days))))
    alpaca = pd.Series(base, index=days)
    identical = bil_overlap_check.overlap_statistics(alpaca, alpaca)
    assert identical["mean_diff_annual_vendor_minus_alpaca"] == 0.0 and identical["checks"]["mean_diff_annual"]["pass"]
    assert bil_overlap_check.decide(identical, "2007-05-30")["outcome"] == "vendor_accepted"
    assert bil_overlap_check.decide(identical, "2007-06-15")["outcome"] == "branch_F"
    drift = np.exp(0.005 / 252 * np.arange(len(days)))
    off = bil_overlap_check.overlap_statistics(pd.Series(base * drift, index=days), alpaca)
    assert not off["checks"]["mean_diff_annual"]["pass"]
    assert off["mean_diff_annual_vendor_minus_alpaca"] == pytest.approx(0.005, rel=0.05)
    assert bil_overlap_check.decide(off, "2007-05-30")["outcome"] == "branch_F"
    assert bil_overlap_check.decide(off, "2007-05-30")["cash_check_window"]["start"] == "2016-01-04"


# --- reproduce.sh gates ------------------------------------------------------------------

@pytest.mark.parametrize("flag", ["--check", "--insample", "--oos"])
def test_reproduce_refuses_without_approval(flag, tmp_path):
    """In a copy of the script with no APPROVED file every mode must refuse
    (the study folder itself carries the approval record, so the test runs on
    a copy and never touches that file)."""
    copy = tmp_path / "study"
    copy.mkdir()
    (copy / "reproduce.sh").write_text((STUDY_DIR / "reproduce.sh").read_text())
    proc = subprocess.run(["bash", "reproduce.sh", flag], cwd=copy,
                          capture_output=True, text=True, env={**os.environ, "PATH": os.environ["PATH"]})
    assert proc.returncode != 0
    assert "APPROVED" in proc.stdout + proc.stderr


def test_reproduce_refuses_a_second_oos_run(tmp_path):
    """With a fake approval in a copy of the folder, --oos must refuse when
    results/oos/ already exists."""
    copy = tmp_path / "study"
    copy.mkdir()
    (copy / "reproduce.sh").write_text((STUDY_DIR / "reproduce.sh").read_text())
    (copy / "APPROVED").write_text("2099-01-01 test fixture, not an approval\n")
    (copy / "results" / "oos").mkdir(parents=True)
    proc = subprocess.run(["bash", "reproduce.sh", "--oos"], cwd=copy, capture_output=True, text=True)
    assert proc.returncode != 0 and "results/oos" in proc.stdout + proc.stderr
