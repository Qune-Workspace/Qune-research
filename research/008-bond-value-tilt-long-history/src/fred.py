"""FRED download, parsing and provenance (§5.1).

Endpoint: ``https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>``.
The CSV has a row for every weekday; holidays carry an empty value.  Empty,
``.`` and ``NaN`` are all treated as missing.  Every download is recorded in
``results/data_manifest.json`` with URL, UTC timestamp, row count and SHA-256
so that a later revision of a published yield would show as a hash change.

Usage (from the study folder): ``python -m src.fred DGS10 DTB3 DGS7``.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

from .config import FRED_SERIES, MANIFEST_PATH, RAW_DIR

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
MISSING_TOKENS = ("", ".", "NaN", "nan", "NA")
TIMEOUT_SECONDS = 60


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_fred_csv(text: str) -> pd.Series:
    """Parse a fredgraph CSV into a float series indexed by date, NaN where
    the value is missing.  The first column is the date, the second the
    value, whatever the header names are."""
    frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    if frame.shape[1] != 2:
        raise ValueError(f"expected two columns in FRED CSV, got {list(frame.columns)}")
    dates = pd.to_datetime(frame.iloc[:, 0], format="%Y-%m-%d")
    raw = frame.iloc[:, 1].str.strip()
    values = pd.to_numeric(raw.where(~raw.isin(MISSING_TOKENS)), errors="raise")
    series = pd.Series(values.to_numpy(dtype=float), index=pd.DatetimeIndex(dates),
                       name=frame.columns[1])
    if not series.index.is_monotonic_increasing or series.index.has_duplicates:
        raise ValueError("FRED CSV dates must be strictly increasing")
    return series


def raw_path(series_id: str, raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / f"fred_{series_id}.csv"


def load_series(series_id: str, raw_dir: Path = RAW_DIR) -> pd.Series:
    """Load a previously downloaded series from ``data/raw/``."""
    return parse_fred_csv(raw_path(series_id, raw_dir).read_text(encoding="utf-8"))


def update_manifest(key: str, entry: dict, manifest_path: Path = MANIFEST_PATH) -> None:
    """Insert or replace one entry of the JSON manifest, keeping it sorted."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest[key] = entry
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fetch_series(series_id: str, raw_dir: Path = RAW_DIR,
                 manifest_path: Path = MANIFEST_PATH,
                 session: requests.Session | None = None) -> pd.Series:
    """Download one series, write it to ``data/raw/`` and record provenance.
    The manifest records dates only, never values."""
    url = FRED_URL.format(series_id=series_id)
    response = (session or requests).get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    downloaded_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    series = parse_fred_csv(response.text)
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_path(series_id, raw_dir)
    path.write_text(response.text, encoding="utf-8")
    valid = series.dropna()
    update_manifest(path.name, {
        "source": "FRED",
        "series_id": series_id,
        "url": url,
        "downloaded_at_utc": downloaded_at,
        "rows": int(len(series)),
        "missing": int(series.isna().sum()),
        "first_valid": valid.index[0].strftime("%Y-%m-%d"),
        "last_valid": valid.index[-1].strftime("%Y-%m-%d"),
        "sha256": sha256_of(path),
    }, manifest_path)
    return series


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Download FRED series into data/raw/ (§5.1).")
    parser.add_argument("series", nargs="*", default=list(FRED_SERIES))
    args = parser.parse_args(argv)
    with requests.Session() as session:
        for series_id in args.series:
            series = fetch_series(series_id, session=session)
            valid = series.dropna()
            print(f"{series_id}: {len(series)} rows, {len(valid)} valid, "
                  f"{valid.index[0].date()} to {valid.index[-1].date()}")


if __name__ == "__main__":
    main()
