"""Daily ETF bars from the Alpaca market-data REST API (§5.1).

``GET https://data.alpaca.markets/v2/stocks/{symbol}/bars`` with
``timeframe=1Day``, ``feed=sip``, ``adjustment=all`` (splits and distributions;
``split`` alone would discard the coupon income that is most of a bond ETF's
return), ``end`` at least 15 minutes in the past, paginated through
``next_page_token``.  Bars are written to ``data/raw/`` (git-ignored, not
redistributable) and only their row count and SHA-256 go into the manifest.

Credentials are read from the environment variables ``APCA_API_KEY_ID`` and
``APCA_API_SECRET_KEY`` only.  Nothing is read from any file.

Usage (from the study folder): ``python -m src.alpaca_bars IEF BIL``.
"""
from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from .config import ETF_BARS_START, MANIFEST_PATH, RAW_DIR, SYMBOLS
from .fred import sha256_of, update_manifest

BARS_URL = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"
KEY_ENV = "APCA_API_KEY_ID"
SECRET_ENV = "APCA_API_SECRET_KEY"
PAGE_LIMIT = 10_000
END_LAG = timedelta(minutes=15)
TIMEOUT_SECONDS = 60
BAR_TIMEZONE = "America/New_York"
COLUMNS = {"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "n": "trades", "vw": "vwap"}


def credentials_from_env() -> dict[str, str]:
    key, secret = os.environ.get(KEY_ENV), os.environ.get(SECRET_ENV)
    if not key or not secret:
        raise RuntimeError(f"set {KEY_ENV} and {SECRET_ENV} in the environment")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def raw_path(symbol: str, raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / f"alpaca_{symbol}_1Day_all.csv"


def _end_timestamp(end: str | None) -> str:
    latest = datetime.now(UTC) - END_LAG
    if end is not None:
        requested = pd.Timestamp(end).tz_localize("UTC") + pd.Timedelta(days=1)
        latest = min(latest, requested.to_pydatetime())
    return latest.strftime("%Y-%m-%dT%H:%M:%SZ")


def bars_to_frame(bars: list[dict]) -> pd.DataFrame:
    """Daily bars keyed by the New York calendar date of the bar."""
    frame = pd.DataFrame(bars).rename(columns=COLUMNS)
    stamps = pd.to_datetime(frame.pop("t"), utc=True).dt.tz_convert(BAR_TIMEZONE)
    frame.insert(0, "date", stamps.dt.tz_localize(None).dt.normalize())
    frame = frame.set_index("date").sort_index()
    if frame.index.has_duplicates:
        raise ValueError("duplicate bar dates in Alpaca response")
    return frame[list(COLUMNS.values())]


def fetch_bars(symbol: str, start: str = ETF_BARS_START, end: str | None = None,
               raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH,
               session: requests.Session | None = None) -> pd.DataFrame:
    """Download all daily bars of ``symbol`` from ``start`` to ``end`` (or
    now minus 15 minutes), write them to ``data/raw/`` and record provenance."""
    headers = credentials_from_env()
    params = {"timeframe": "1Day", "feed": "sip", "adjustment": "all",
              "start": start, "end": _end_timestamp(end), "limit": PAGE_LIMIT}
    url = BARS_URL.format(symbol=symbol)
    client = session or requests
    bars: list[dict] = []
    page_token = None
    downloaded_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
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
    frame = bars_to_frame(bars)
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_path(symbol, raw_dir)
    frame.to_csv(path, date_format="%Y-%m-%d")
    update_manifest(path.name, {
        "source": "Alpaca market data (licensed, not redistributed)",
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


def load_bars(symbol: str, raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Load previously downloaded bars from ``data/raw/``."""
    return pd.read_csv(raw_path(symbol, raw_dir), index_col="date", parse_dates=["date"])


def total_return_index(bars: pd.DataFrame) -> pd.Series:
    """Total-return index from the ``adjustment='all'`` close, normalised to
    1.0 on the first bar (§5.1: ``r_t = close_adj_t / close_adj_{t-1} - 1``)."""
    close = bars["close"].astype(float)
    return (close / close.iloc[0]).rename("tri")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Fetch Alpaca daily bars, adjustment='all' (§5.1).")
    parser.add_argument("symbols", nargs="*", default=list(SYMBOLS))
    parser.add_argument("--start", default=ETF_BARS_START)
    parser.add_argument("--end", default=None, help="last calendar date to include (default: now)")
    args = parser.parse_args(argv)
    with requests.Session() as session:
        for symbol in args.symbols:
            frame = fetch_bars(symbol, args.start, args.end, session=session)
            print(f"{symbol}: {len(frame)} bars, {frame.index[0].date()} to {frame.index[-1].date()}")


if __name__ == "__main__":
    main()
