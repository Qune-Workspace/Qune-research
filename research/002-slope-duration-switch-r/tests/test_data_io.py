"""§5.1 parsing and provenance without any network access, the reuse of
Study 001's bars, the second-vendor module, the §5.3.4 overlap check on toy
series, and the ``reproduce.sh`` approval gate."""
import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import alpaca_bars, fred, overlap_check, reuse_bars, tiingo_bars
from src.config import STUDY_DIR

FRED_TEXT = "observation_date,DGS10\n2024-01-01,\n2024-01-02,3.95\n2024-01-03,.\n2024-01-04,NaN\n2024-01-05,4.05\n"


def test_parse_fred_csv_treats_empty_dot_and_nan_as_missing():
    s = fred.parse_fred_csv(FRED_TEXT)
    assert len(s) == 5 and s.isna().sum() == 3
    assert s.loc["2024-01-02"] == 3.95 and s.loc["2024-01-05"] == 4.05
    assert isinstance(s.index, pd.DatetimeIndex) and s.name == "DGS10"


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


def test_alpaca_end_timestamp_is_in_the_past():
    end = pd.Timestamp(alpaca_bars._end_timestamp(None))
    assert end <= pd.Timestamp.now("UTC") - pd.Timedelta(minutes=14)
    capped = pd.Timestamp(alpaca_bars._end_timestamp("2018-12-31"))
    assert capped == pd.Timestamp("2019-01-01", tz="UTC")


# --- Reuse of Study 001's bars ---------------------------------------------------------

def _fake_study_001(root: Path, content: bytes, recorded_sha: str) -> Path:
    source = root / "001"
    (source / "data" / "raw").mkdir(parents=True)
    (source / "results").mkdir()
    (source / "data" / "raw" / "alpaca_IEF_1Day_all.csv").write_bytes(content)
    (source / "results" / "data_manifest.json").write_text(json.dumps(
        {"alpaca_IEF_1Day_all.csv": {"sha256": recorded_sha, "rows": 1, "source": "test"}}))
    return source


def test_reuse_copies_only_when_the_hash_matches_study_001_manifest(tmp_path):
    content = b"date,close\n2016-01-04,100\n"
    probe = _fake_study_001(tmp_path / "probe", content, "x")
    good = fred.sha256_of(probe / "data" / "raw" / "alpaca_IEF_1Day_all.csv")
    source = _fake_study_001(tmp_path, content, good)
    raw, manifest = tmp_path / "raw", tmp_path / "manifest.json"
    target = reuse_bars.reuse_study_001_bars("IEF", raw, manifest, source)
    assert target.read_bytes() == content
    entry = json.loads(manifest.read_text())["alpaca_IEF_1Day_all.csv"]
    assert entry["sha256"] == good and "Study 001" in entry["reused_from"] and "reused_at_utc" in entry
    # a second call with the file already in place writes nothing
    manifest.write_text("{}")
    reuse_bars.reuse_study_001_bars("IEF", raw, manifest, source)
    assert manifest.read_text() == "{}"
    # a mismatching hash refuses and copies nothing
    bad = _fake_study_001(tmp_path / "bad", content, "0" * 64)
    with pytest.raises(RuntimeError):
        reuse_bars.reuse_study_001_bars("IEF", tmp_path / "raw2", tmp_path / "m2.json", bad)
    assert not (tmp_path / "raw2").exists()


# --- Second vendor ---------------------------------------------------------------------

def test_tiingo_token_comes_from_the_environment_only(monkeypatch):
    monkeypatch.delenv(tiingo_bars.TOKEN_ENV, raising=False)
    with pytest.raises(RuntimeError):
        tiingo_bars.token_from_env()
    monkeypatch.setenv(tiingo_bars.TOKEN_ENV, " t ")
    assert tiingo_bars.token_from_env() == "t"


def test_tiingo_rows_to_frame_sorts_fills_and_rejects_duplicates():
    rows = [{"date": "2003-01-03T00:00:00.000Z", "close": 2.0, "adjClose": 1.9},
            {"date": "2003-01-02T00:00:00.000Z", "close": 1.0, "adjClose": 0.9}]
    frame = tiingo_bars.rows_to_frame(rows)
    assert list(frame.index) == list(pd.to_datetime(["2003-01-02", "2003-01-03"]))
    assert list(frame.columns) == list(tiingo_bars.COLUMNS)
    assert frame["adjClose"].tolist() == [0.9, 1.9] and frame["divCash"].isna().all()
    with pytest.raises(ValueError):
        tiingo_bars.rows_to_frame(rows + [rows[0]])
    with pytest.raises(RuntimeError):
        tiingo_bars.rows_to_frame([])


# --- §5.3.4 step 2 on toy series -------------------------------------------------------

def test_overlap_statistics_and_decision_on_toy_series():
    days = pd.bdate_range("2015-12-31", "2018-12-31")
    rng = np.random.default_rng(11)
    base = 100 * np.exp(np.cumsum(rng.normal(0, 0.003, len(days))))
    alpaca = pd.Series(base, index=days)
    identical = overlap_check.overlap_statistics(alpaca, alpaca)
    assert identical["correlation"] == pytest.approx(1.0) and identical["mean_diff_annual_vendor_minus_alpaca"] == 0.0
    assert identical["common_return_days"] == len(days[days >= "2016-01-04"])   # 2016-01-04 has a return here
    assert all(c["pass"] for c in identical["checks"].values())
    assert overlap_check.decide(identical, "2002-07-26")["window2"] == "accepted"
    assert overlap_check.decide(identical, "2003-06-01")["window2"] == "excluded_unavailable"
    # a vendor series that earns 0.5% p.a. more fails the mean-difference check only
    drift = np.exp(0.005 / 252 * np.arange(len(days)))
    vendor = pd.Series(base * drift, index=days)
    off = overlap_check.overlap_statistics(vendor, alpaca)
    assert off["checks"]["correlation"]["pass"] and not off["checks"]["mean_diff_annual"]["pass"]
    assert off["mean_diff_annual_vendor_minus_alpaca"] == pytest.approx(0.005, rel=0.05)
    assert overlap_check.decide(off, "2002-07-26")["window2"] == "excluded_data_quality"
    # a day present in one series only is reported, not silently dropped (the
    # shorter series still has a return on the next day, spanning the gap)
    short = alpaca.drop(pd.Timestamp("2017-03-01"))
    gap = overlap_check.overlap_statistics(alpaca, short)
    assert gap["days_only_in_vendor"] == ["2017-03-01"] and gap["days_only_in_alpaca"] == []
    assert gap["common_return_days"] == identical["common_return_days"] - 1


# --- reproduce.sh gates ----------------------------------------------------------------

@pytest.mark.parametrize("flag", ["--validate", "--insample", "--oos"])
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
