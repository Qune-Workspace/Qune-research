"""Data adapters with provenance hashing (Study 004 §5.1, §13).

Ported by attribution from Study 003's frozen ``src/tiingo_bars.py``,
``src/alpaca_bars.py``, ``src/fred.py`` and ``src/reuse_bars.py`` (the tree
at a18d02c), with one structural change: nothing here knows a study
directory.  Every function takes the raw-data directory and the manifest
path as parameters, so that a study passes its own and a test passes a
temporary one.  Behaviour is otherwise the same:

* **Tiingo** ``GET https://api.tiingo.com/tiingo/daily/{symbol}/prices``
  (``startDate``, ``endDate``, ``format=json``, ``resampleFreq=daily``);
  ``adjClose`` is the split- and distribution-adjusted close.  The token is
  read from ``TIINGO_API_KEY`` only and sent as a header, never as a URL
  parameter; any response text reported on an error has it redacted.
* **Alpaca** ``GET https://data.alpaca.markets/v2/stocks/{symbol}/bars``
  (``timeframe=1Day``, ``feed=sip``, ``adjustment=all``, paged through
  ``next_page_token``); credentials from ``APCA_API_KEY_ID`` and
  ``APCA_API_SECRET_KEY`` only.
* **FRED** ``https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>``;
  empty, ``.`` and ``NaN`` are missing.
* **Reuse** of a file fetched under an earlier study: copied only after its
  bytes match the SHA-256 recorded in that study's manifest, and recorded.

Raw files are written to the raw directory (git-ignored in this repository;
licensed data are never redistributed).  The manifest records vendor, URL,
parameters, UTC timestamp, row count, first and last bar and SHA-256 of
every file used, so that a later revision shows as a hash change.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

TIMEOUT_SECONDS = 60


# --- Provenance ------------------------------------------------------------------------

def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_manifest(manifest_path: Path) -> dict:
    manifest_path = Path(manifest_path)
    return json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}


def update_manifest(key: str, entry: dict, manifest_path: Path) -> None:
    """Insert or replace one entry of the JSON manifest, keeping it sorted."""
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(manifest_path)
    manifest[key] = entry
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _record(path: Path, frame: pd.DataFrame, manifest_path: Path, **fields) -> None:
    update_manifest(path.name, dict(fields, rows=int(len(frame)),
                                    first_bar=frame.index[0].strftime("%Y-%m-%d"),
                                    last_bar=frame.index[-1].strftime("%Y-%m-%d"),
                                    sha256=sha256_of(path)), manifest_path)


# --- Tiingo ----------------------------------------------------------------------------

TIINGO_URL = "https://api.tiingo.com/tiingo/daily/{symbol}/prices"
TIINGO_HOST = "api.tiingo.com"
TIINGO_TOKEN_ENV = "TIINGO_API_KEY"
TIINGO_COLUMNS = ("open", "high", "low", "close", "volume",
                  "adjOpen", "adjHigh", "adjLow", "adjClose", "adjVolume", "divCash", "splitFactor")
TIINGO_SOURCE = ("Tiingo end-of-day prices (licensed, not redistributed); "
                 "adjClose = split- and distribution-adjusted close")


def tiingo_token_from_env() -> str:
    token = os.environ.get(TIINGO_TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(f"set {TIINGO_TOKEN_ENV} in the environment (no file is read by this module)")
    return token


def tiingo_path(symbol: str, raw_dir: Path) -> Path:
    return Path(raw_dir) / f"tiingo_{symbol}_daily.csv"


def tiingo_rows_to_frame(rows: list[dict]) -> pd.DataFrame:
    """Tiingo rows -> frame indexed by calendar date, sorted, no duplicates,
    with the twelve price/adjustment columns (missing fields stay NaN)."""
    if not rows:
        raise RuntimeError("no rows returned")
    frame = pd.DataFrame(rows)
    frame.insert(0, "date", pd.to_datetime(frame.pop("date").str.slice(0, 10), format="%Y-%m-%d"))
    frame = frame.set_index("date").sort_index()
    if frame.index.has_duplicates:
        raise ValueError("duplicate dates in Tiingo response")
    for column in TIINGO_COLUMNS:
        if column not in frame.columns:
            frame[column] = float("nan")
    return frame[list(TIINGO_COLUMNS)].astype(float)


def fetch_tiingo(symbol: str, start: str, end: str | None, raw_dir: Path, manifest_path: Path,
                 session: requests.Session | None = None) -> pd.DataFrame:
    """One GET for ``symbol``; write ``tiingo_{symbol}_daily.csv`` and record provenance."""
    token = tiingo_token_from_env()
    params = {"startDate": start, "format": "json", "resampleFreq": "daily"}
    if end:
        params["endDate"] = end
    url = TIINGO_URL.format(symbol=symbol.lower())
    if requests.utils.urlparse(url).hostname != TIINGO_HOST:
        raise RuntimeError("host not allowed")
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    downloaded_at = utc_now()
    client = session or requests
    response = client.get(url, headers=headers, params=params, timeout=TIMEOUT_SECONDS, allow_redirects=False)
    if response.status_code != 200:
        snippet = response.text[:160].replace(token, "***")
        raise RuntimeError(f"Tiingo {symbol}: HTTP {response.status_code} {snippet}")
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError(f"Tiingo {symbol}: unexpected response shape")
    frame = tiingo_rows_to_frame(payload)
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    path = tiingo_path(symbol, raw_dir)
    frame.to_csv(path, date_format="%Y-%m-%d")
    _record(path, frame, manifest_path, source=TIINGO_SOURCE, symbol=symbol, url=url, params=params,
            downloaded_at_utc=downloaded_at)
    return frame


def load_tiingo(symbol: str, raw_dir: Path) -> pd.DataFrame:
    return pd.read_csv(tiingo_path(symbol, raw_dir), index_col="date", parse_dates=["date"])


# --- Alpaca ----------------------------------------------------------------------------

ALPACA_URL = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"
ALPACA_KEY_ENV = "APCA_API_KEY_ID"
ALPACA_SECRET_ENV = "APCA_API_SECRET_KEY"
ALPACA_PAGE_LIMIT = 10_000
ALPACA_END_LAG = timedelta(minutes=15)
ALPACA_BAR_TIMEZONE = "America/New_York"
ALPACA_COLUMNS = {"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "n": "trades", "vw": "vwap"}
ALPACA_SOURCE = "Alpaca market data (licensed, not redistributed)"


def alpaca_credentials_from_env() -> dict[str, str]:
    key, secret = os.environ.get(ALPACA_KEY_ENV), os.environ.get(ALPACA_SECRET_ENV)
    if not key or not secret:
        raise RuntimeError(f"set {ALPACA_KEY_ENV} and {ALPACA_SECRET_ENV} in the environment")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def alpaca_path(symbol: str, raw_dir: Path) -> Path:
    return Path(raw_dir) / f"alpaca_{symbol}_1Day_all.csv"


def _alpaca_end_timestamp(end: str | None) -> str:
    latest = datetime.now(timezone.utc) - ALPACA_END_LAG
    if end is not None:
        requested = pd.Timestamp(end).tz_localize("UTC") + pd.Timedelta(days=1)
        latest = min(latest, requested.to_pydatetime())
    return latest.strftime("%Y-%m-%dT%H:%M:%SZ")


def alpaca_bars_to_frame(bars: list[dict]) -> pd.DataFrame:
    """Daily bars keyed by the New York calendar date of the bar."""
    frame = pd.DataFrame(bars).rename(columns=ALPACA_COLUMNS)
    stamps = pd.to_datetime(frame.pop("t"), utc=True).dt.tz_convert(ALPACA_BAR_TIMEZONE)
    frame.insert(0, "date", stamps.dt.tz_localize(None).dt.normalize())
    frame = frame.set_index("date").sort_index()
    if frame.index.has_duplicates:
        raise ValueError("duplicate bar dates in Alpaca response")
    return frame[list(ALPACA_COLUMNS.values())]


def fetch_alpaca(symbol: str, start: str, end: str | None, raw_dir: Path, manifest_path: Path,
                 session: requests.Session | None = None) -> pd.DataFrame:
    """All daily bars of ``symbol`` from ``start`` to ``end`` (or now minus 15
    minutes), ``adjustment='all'``; written and recorded."""
    headers = alpaca_credentials_from_env()
    params = {"timeframe": "1Day", "feed": "sip", "adjustment": "all",
              "start": start, "end": _alpaca_end_timestamp(end), "limit": ALPACA_PAGE_LIMIT}
    url = ALPACA_URL.format(symbol=symbol)
    client = session or requests
    bars: list[dict] = []
    page_token = None
    downloaded_at = utc_now()
    while True:
        query = dict(params, page_token=page_token) if page_token else params
        response = client.get(url, headers=headers, params=query, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        bars.extend(payload.get("bars") or [])
        page_token = payload.get("next_page_token")
        if not page_token:
            break
    if not bars:
        raise RuntimeError(f"no bars returned for {symbol}")
    frame = alpaca_bars_to_frame(bars)
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    path = alpaca_path(symbol, raw_dir)
    frame.to_csv(path, date_format="%Y-%m-%d")
    _record(path, frame, manifest_path, source=ALPACA_SOURCE, symbol=symbol, url=url, params=params,
            downloaded_at_utc=downloaded_at)
    return frame


def load_alpaca(symbol: str, raw_dir: Path) -> pd.DataFrame:
    return pd.read_csv(alpaca_path(symbol, raw_dir), index_col="date", parse_dates=["date"])


# --- FRED ------------------------------------------------------------------------------

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
FRED_MISSING_TOKENS = ("", ".", "NaN", "nan", "NA")


def parse_fred_csv(text: str) -> pd.Series:
    """Parse a fredgraph CSV into a float series indexed by date, NaN where
    the value is missing.  The first column is the date, the second the value."""
    frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    if frame.shape[1] != 2:
        raise ValueError(f"expected two columns in FRED CSV, got {list(frame.columns)}")
    dates = pd.to_datetime(frame.iloc[:, 0], format="%Y-%m-%d")
    raw = frame.iloc[:, 1].str.strip()
    values = pd.to_numeric(raw.where(~raw.isin(FRED_MISSING_TOKENS)), errors="raise")
    series = pd.Series(values.to_numpy(dtype=float), index=pd.DatetimeIndex(dates), name=frame.columns[1])
    if not series.index.is_monotonic_increasing or series.index.has_duplicates:
        raise ValueError("FRED CSV dates must be strictly increasing")
    return series


def fred_path(series_id: str, raw_dir: Path) -> Path:
    return Path(raw_dir) / f"fred_{series_id}.csv"


def fetch_fred(series_id: str, raw_dir: Path, manifest_path: Path,
               session: requests.Session | None = None) -> pd.Series:
    url = FRED_URL.format(series_id=series_id)
    client = session or requests
    downloaded_at = utc_now()
    response = client.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    series = parse_fred_csv(response.text)
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    path = fred_path(series_id, raw_dir)
    path.write_text(response.text, encoding="utf-8")
    update_manifest(path.name, {"source": "FRED (fredgraph.csv)", "series_id": series_id, "url": url,
                                "downloaded_at_utc": downloaded_at, "rows": int(len(series)),
                                "first_bar": series.index[0].strftime("%Y-%m-%d"),
                                "last_bar": series.index[-1].strftime("%Y-%m-%d"),
                                "last_valid": series.dropna().index[-1].strftime("%Y-%m-%d"),
                                "sha256": sha256_of(path)}, manifest_path)
    return series


def load_fred(series_id: str, raw_dir: Path) -> pd.Series:
    return parse_fred_csv(fred_path(series_id, raw_dir).read_text(encoding="utf-8"))


# --- Reuse of an earlier study's file ---------------------------------------------------

def reuse_file(name: str, source_study_dir: Path, raw_dir: Path, manifest_path: Path) -> Path:
    """Verify and copy ``<source_study_dir>/data/raw/<name>``.  Raises if the
    source bytes do not match that study's manifest.  Writes nothing when the
    target is already present with the recorded hash."""
    source_study_dir = Path(source_study_dir)
    recorded = json.loads((source_study_dir / "results" / "data_manifest.json").read_text(encoding="utf-8"))[name]
    source = source_study_dir / "data" / "raw" / name
    if sha256_of(source) != recorded["sha256"]:
        raise RuntimeError(f"{name}: SHA-256 differs from {source_study_dir.name}'s manifest; not reusing")
    target = Path(raw_dir) / name
    if target.exists() and sha256_of(target) == recorded["sha256"]:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    label = source_study_dir.name.split("-")[0]
    note = f"Study {label} data/raw (same bytes; SHA-256 verified against Study {label} results/data_manifest.json)"
    update_manifest(name, dict(recorded, reused_from=note, reused_at_utc=utc_now()), manifest_path)
    return target
