"""§5.1 parsing and provenance without any network access, and the
``reproduce.sh`` approval gate."""
import json
import os
import subprocess

import pandas as pd
import pytest
from src import alpaca_bars, fred
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


@pytest.mark.parametrize("flag", ["--validate", "--insample", "--oos"])
def test_reproduce_refuses_without_approval(flag, tmp_path):
    """In a copy of the script with no APPROVED file every mode must refuse
    (the study folder itself carries the owner's approval since 2026-10-21,
    so the test runs on a copy and never touches that file)."""
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
