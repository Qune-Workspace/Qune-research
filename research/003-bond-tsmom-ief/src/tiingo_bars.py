"""Daily closes from Tiingo, the second vendor of §5.1 (copied from Study 002
at commit 2dfbdd5; only the default symbol, start date and section references
changed).  In this study the module fetches BIL for the cash-leg check
(§5.3.2 step 1); the IEF series is the one fetched under Study 002 and is
reused by hash.

``GET https://api.tiingo.com/tiingo/daily/{symbol}/prices`` with ``startDate``,
``endDate``, ``format=json`` and ``resampleFreq=daily``.  Tiingo's ``close`` is
the raw close; ``adjClose`` is adjusted for splits and cash distributions,
which is the field the overlap check (§5.3.4 step 2) uses.  Rows go to
``data/raw/`` (git-ignored, not redistributable); only the row count, first
and last dates and SHA-256 go into ``results/data_manifest.json``.

The API token is read from the environment variable ``TIINGO_API_KEY`` only
(the caller exports it from the desk's existing credential file; no new
credential is created) and is sent as a request header, never as a URL
parameter, so no exception text or log line can contain it.  Any response
text that is reported on an error has the token redacted as well.

Usage (from the study folder): ``python -m src.tiingo_bars BIL``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

STUDY_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = STUDY_DIR / "data" / "raw"
MANIFEST_PATH = STUDY_DIR / "results" / "data_manifest.json"

PRICES_URL = "https://api.tiingo.com/tiingo/daily/{symbol}/prices"
ALLOWED_HOST = "api.tiingo.com"
TOKEN_ENV = "TIINGO_API_KEY"
DEFAULT_START = "2007-05-01"  # before BIL's inception (§5.3.2 step 1)
TIMEOUT_SECONDS = 60
COLUMNS = ("open", "high", "low", "close", "volume",
           "adjOpen", "adjHigh", "adjLow", "adjClose", "adjVolume", "divCash", "splitFactor")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update_manifest(key: str, entry: dict, manifest_path: Path = MANIFEST_PATH) -> None:
    """Insert or replace one entry of the JSON manifest, keeping it sorted
    (same layout as Study 001's manifest)."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest[key] = entry
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def token_from_env() -> str:
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(f"set {TOKEN_ENV} in the environment (no file is read by this module)")
    return token


def raw_path(symbol: str, raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / f"tiingo_{symbol}_daily.csv"


def rows_to_frame(rows: list[dict]) -> pd.DataFrame:
    """Tiingo rows -> frame indexed by calendar date, sorted, no duplicates,
    with the twelve price/adjustment columns (missing fields stay NaN)."""
    if not rows:
        raise RuntimeError("no rows returned")
    frame = pd.DataFrame(rows)
    frame.insert(0, "date", pd.to_datetime(frame.pop("date").str.slice(0, 10), format="%Y-%m-%d"))
    frame = frame.set_index("date").sort_index()
    if frame.index.has_duplicates:
        raise ValueError("duplicate dates in Tiingo response")
    for column in COLUMNS:
        if column not in frame.columns:
            frame[column] = float("nan")
    return frame[list(COLUMNS)].astype(float)


def fetch_prices(symbol: str, start: str = DEFAULT_START, end: str | None = None,
                 raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH,
                 session: requests.Session | None = None) -> pd.DataFrame:
    """One GET for ``symbol``; write ``data/raw/tiingo_{symbol}_daily.csv`` and
    record provenance (vendor, URL, parameters, timestamp, rows, dates, SHA-256)."""
    token = token_from_env()
    params = {"startDate": start, "format": "json", "resampleFreq": "daily"}
    if end:
        params["endDate"] = end
    url = PRICES_URL.format(symbol=symbol.lower())
    if requests.utils.urlparse(url).hostname != ALLOWED_HOST:
        raise RuntimeError("host not allowed")
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    downloaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    client = session or requests
    response = client.get(url, headers=headers, params=params, timeout=TIMEOUT_SECONDS, allow_redirects=False)
    if response.status_code != 200:
        snippet = response.text[:160].replace(token, "***")
        raise RuntimeError(f"Tiingo {symbol}: HTTP {response.status_code} {snippet}")
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError(f"Tiingo {symbol}: unexpected response shape")
    frame = rows_to_frame(payload)
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_path(symbol, raw_dir)
    frame.to_csv(path, date_format="%Y-%m-%d")
    update_manifest(path.name, {
        "source": "Tiingo end-of-day prices (licensed, not redistributed); adjClose = split- and distribution-adjusted close",
        "symbol": symbol,
        "url": url,
        "params": params,
        "downloaded_at_utc": downloaded_at,
        "rows": int(len(frame)),
        "first_bar": frame.index[0].strftime("%Y-%m-%d"),
        "last_bar": frame.index[-1].strftime("%Y-%m-%d"),
        "sha256": sha256_of(path),
    }, manifest_path)
    return frame


def load_prices(symbol: str, raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    return pd.read_csv(raw_path(symbol, raw_dir), index_col="date", parse_dates=["date"])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fetch Tiingo daily prices (§5.3.2 step 1).")
    parser.add_argument("symbols", nargs="*", default=["BIL"])
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=None)
    args = parser.parse_args(argv)
    with requests.Session() as session:
        for symbol in args.symbols:
            frame = fetch_prices(symbol, args.start, args.end, session=session)
            print(f"{symbol}: {len(frame)} rows, {frame.index[0].date()} to {frame.index[-1].date()}")


if __name__ == "__main__":
    main()
