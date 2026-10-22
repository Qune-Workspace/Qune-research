"""Data adapters without any network access: parsing, provenance, the
credential-from-environment rule and the hash-checked reuse of an earlier
study's file (§5.1).  Constructed inputs only."""
import json
from pathlib import Path

import pandas as pd
import pytest

from qune_research import data

FRED_TEXT = "observation_date,DTB3\n2024-01-01,\n2024-01-02,5.25\n2024-01-03,.\n2024-01-04,NaN\n2024-01-05,5.21\n"


def test_parse_fred_csv_treats_empty_dot_and_nan_as_missing():
    s = data.parse_fred_csv(FRED_TEXT)
    assert len(s) == 5 and s.isna().sum() == 3
    assert s.loc["2024-01-02"] == 5.25 and s.loc["2024-01-05"] == 5.21
    assert isinstance(s.index, pd.DatetimeIndex) and s.name == "DTB3"
    with pytest.raises(ValueError):
        data.parse_fred_csv("observation_date,X\n2024-01-02,1\n2024-01-01,2\n")


def test_manifest_round_trip_and_sha256(tmp_path):
    manifest = tmp_path / "m.json"
    data.update_manifest("a.csv", {"rows": 1}, manifest)
    data.update_manifest("b.csv", {"rows": 2}, manifest)
    data.update_manifest("a.csv", {"rows": 3}, manifest)
    assert data.read_manifest(manifest) == {"a.csv": {"rows": 3}, "b.csv": {"rows": 2}}
    assert data.read_manifest(tmp_path / "absent.json") == {}
    f = tmp_path / "x.bin"
    f.write_bytes(b"abc")
    assert data.sha256_of(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_tiingo_rows_to_frame_sorts_fills_and_rejects_duplicates():
    rows = [{"date": "2007-06-01T00:00:00.000Z", "close": 2.0, "adjClose": 1.9},
            {"date": "2007-05-31T00:00:00.000Z", "close": 1.0, "adjClose": 0.9}]
    frame = data.tiingo_rows_to_frame(rows)
    assert list(frame.index) == list(pd.to_datetime(["2007-05-31", "2007-06-01"]))
    assert list(frame.columns) == list(data.TIINGO_COLUMNS)
    assert frame["adjClose"].tolist() == [0.9, 1.9] and frame["divCash"].isna().all()
    with pytest.raises(ValueError):
        data.tiingo_rows_to_frame(rows + [rows[0]])
    with pytest.raises(RuntimeError):
        data.tiingo_rows_to_frame([])


def test_alpaca_bars_to_frame_keys_by_new_york_date():
    bars = [{"t": "2024-01-03T05:00:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10, "n": 3, "vw": 1.4},
            {"t": "2024-01-02T05:00:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.0, "v": 10, "n": 3, "vw": 1.1}]
    frame = data.alpaca_bars_to_frame(bars)
    assert list(frame.index) == list(pd.to_datetime(["2024-01-02", "2024-01-03"]))
    assert frame["close"].tolist() == [1.0, 1.5]
    with pytest.raises(ValueError):
        data.alpaca_bars_to_frame(bars + [bars[0]])


def test_credentials_come_from_the_environment_only(monkeypatch):
    for name in (data.TIINGO_TOKEN_ENV, data.ALPACA_KEY_ENV, data.ALPACA_SECRET_ENV):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError):
        data.tiingo_token_from_env()
    with pytest.raises(RuntimeError):
        data.alpaca_credentials_from_env()
    monkeypatch.setenv(data.TIINGO_TOKEN_ENV, " t ")
    monkeypatch.setenv(data.ALPACA_KEY_ENV, "k")
    monkeypatch.setenv(data.ALPACA_SECRET_ENV, "s")
    assert data.tiingo_token_from_env() == "t"
    assert data.alpaca_credentials_from_env() == {"APCA-API-KEY-ID": "k", "APCA-API-SECRET-KEY": "s"}


class _Response:
    def __init__(self, status, payload=None, text=""):
        self.status_code, self._payload, self.text = status, payload, text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code != 200:
            raise RuntimeError(f"HTTP {self.status_code}")


class _Session:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def test_fetch_tiingo_writes_file_and_manifest_and_redacts_the_token(tmp_path, monkeypatch):
    monkeypatch.setenv(data.TIINGO_TOKEN_ENV, "SECRET-TOKEN")
    rows = [{"date": "2016-01-04T00:00:00.000Z", "close": 1.0, "adjClose": 1.0},
            {"date": "2016-01-05T00:00:00.000Z", "close": 1.1, "adjClose": 1.1}]
    raw, manifest = tmp_path / "raw", tmp_path / "m.json"
    session = _Session([_Response(200, rows)])
    frame = data.fetch_tiingo("SPY", "2016-01-01", "2016-01-31", raw, manifest, session)
    assert len(frame) == 2 and data.tiingo_path("SPY", raw).exists()
    url, kwargs = session.calls[0]
    assert url == "https://api.tiingo.com/tiingo/daily/spy/prices"
    assert kwargs["headers"]["Authorization"] == "Token SECRET-TOKEN" and "token" not in kwargs["params"]
    entry = data.read_manifest(manifest)["tiingo_SPY_daily.csv"]
    assert entry["rows"] == 2 and entry["first_bar"] == "2016-01-04" and entry["last_bar"] == "2016-01-05"
    assert entry["sha256"] == data.sha256_of(data.tiingo_path("SPY", raw))
    assert "SECRET-TOKEN" not in json.dumps(entry)
    with pytest.raises(RuntimeError) as err:
        data.fetch_tiingo("SPY", "2016-01-01", None, raw, manifest, _Session([_Response(403, text="bad SECRET-TOKEN")]))
    assert "SECRET-TOKEN" not in str(err.value) and "***" in str(err.value)


def test_fetch_alpaca_pages_and_records(tmp_path, monkeypatch):
    monkeypatch.setenv(data.ALPACA_KEY_ENV, "k")
    monkeypatch.setenv(data.ALPACA_SECRET_ENV, "s")
    page1 = {"bars": [{"t": "2016-01-04T05:00:00Z", "o": 1, "h": 1, "l": 1, "c": 1.0, "v": 1, "n": 1, "vw": 1}],
             "next_page_token": "p2"}
    page2 = {"bars": [{"t": "2016-01-05T05:00:00Z", "o": 1, "h": 1, "l": 1, "c": 2.0, "v": 1, "n": 1, "vw": 1}],
             "next_page_token": None}
    raw, manifest = tmp_path / "raw", tmp_path / "m.json"
    session = _Session([_Response(200, page1), _Response(200, page2)])
    frame = data.fetch_alpaca("SPY", "2016-01-04", "2018-12-31", raw, manifest, session)
    assert frame["close"].tolist() == [1.0, 2.0] and len(session.calls) == 2
    assert session.calls[1][1]["params"]["page_token"] == "p2"
    params = session.calls[0][1]["params"]
    assert params["adjustment"] == "all" and params["feed"] == "sip" and params["end"].startswith("2019-01-01T00:00:00")
    entry = data.read_manifest(manifest)["alpaca_SPY_1Day_all.csv"]
    assert entry["rows"] == 2 and entry["params"]["adjustment"] == "all"
    with pytest.raises(RuntimeError):
        data.fetch_alpaca("SPY", "2016-01-04", None, raw, manifest, _Session([_Response(200, {"bars": []})]))


def test_fetch_fred_records_last_valid_observation(tmp_path):
    raw, manifest = tmp_path / "raw", tmp_path / "m.json"
    series = data.fetch_fred("DTB3", raw, manifest, _Session([_Response(200, text=FRED_TEXT)]))
    assert series.notna().sum() == 2
    entry = data.read_manifest(manifest)["fred_DTB3.csv"]
    assert entry["last_valid"] == "2024-01-05" and entry["rows"] == 5
    assert data.load_fred("DTB3", raw).equals(series)


def _fake_study(root: Path, name: str, content: bytes, recorded_sha: str) -> Path:
    source = root / name
    (source / "data" / "raw").mkdir(parents=True)
    (source / "results").mkdir()
    (source / "data" / "raw" / "tiingo_IEF_daily.csv").write_bytes(content)
    (source / "results" / "data_manifest.json").write_text(json.dumps(
        {"tiingo_IEF_daily.csv": {"sha256": recorded_sha, "rows": 1, "source": "test"}}))
    return source


def test_reuse_copies_only_when_the_hash_matches_the_source_manifest(tmp_path):
    content = b"date,close\n2016-01-04,100\n"
    probe = tmp_path / "probe.csv"
    probe.write_bytes(content)
    good = data.sha256_of(probe)
    source = _fake_study(tmp_path, "003-bond", content, good)
    raw, manifest = tmp_path / "raw", tmp_path / "manifest.json"
    target = data.reuse_file("tiingo_IEF_daily.csv", source, raw, manifest)
    assert target.read_bytes() == content
    entry = data.read_manifest(manifest)["tiingo_IEF_daily.csv"]
    assert entry["sha256"] == good and "Study 003" in entry["reused_from"] and "reused_at_utc" in entry
    manifest.write_text("{}")                      # a second call with the file in place writes nothing
    data.reuse_file("tiingo_IEF_daily.csv", source, raw, manifest)
    assert manifest.read_text() == "{}"
    bad = _fake_study(tmp_path / "bad", "001-bad", content, "0" * 64)
    with pytest.raises(RuntimeError):
        data.reuse_file("tiingo_IEF_daily.csv", bad, tmp_path / "raw2", tmp_path / "m2.json")
    assert not (tmp_path / "raw2").exists()
