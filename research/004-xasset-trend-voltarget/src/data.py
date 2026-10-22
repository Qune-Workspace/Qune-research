"""This study's data files: which are reused from earlier studies and which
are fetched (§5.1), through the shared library's adapters.

* Vendor (Tiingo) daily closes: IEF reused from Study 002 and BIL from
  Study 003 after a SHA-256 check against those manifests; the other eleven
  fetched from 2002-07-01 (or the fund's first bar) to 2026-09-30, one GET
  per symbol (§5.3.1).  ``refetch=True`` fetches again even if the file is
  present (the single retry of §5.3.1).
* Broker (Alpaca) bars, ``adjustment='all'``: IEF and BIL reused from Study
  001; the other ten fetched for the overlap window only (§5.3.2).  A missing
  credential raises, which the check records as "broker bars unavailable".
* FRED DTB3: re-fetched if reachable, else Study 003's file after a SHA-256
  check (§5.1).

Credentials come from the environment only (``TIINGO_API_KEY``,
``APCA_API_KEY_ID``, ``APCA_API_SECRET_KEY``); nothing here reads a file
outside the repository.  Raw files go to ``data/raw/`` (git-ignored);
provenance to ``results/data_manifest.json``.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

from qune_research import data as lib

from .config import (BROKER_FETCH_END, BROKER_FETCH_START, FRED_SERIES, MANIFEST_PATH, RAW_DIR, REUSED_BROKER_FILES,
                     REUSED_FRED_FILE, REUSED_VENDOR_FILES, VENDOR_FETCH_END, VENDOR_FETCH_START)


def vendor_frame(symbol: str, refetch: bool = False, raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH,
                 session: requests.Session | None = None) -> pd.DataFrame:
    """The vendor daily file of ``symbol``: reused by hash, present, or fetched."""
    if symbol in REUSED_VENDOR_FILES:
        name, source = REUSED_VENDOR_FILES[symbol]
        lib.reuse_file(name, source, raw_dir, manifest_path)
        return lib.load_tiingo(symbol, raw_dir)
    path = lib.tiingo_path(symbol, raw_dir)
    if path.exists() and not refetch and path.name in lib.read_manifest(manifest_path):
        return lib.load_tiingo(symbol, raw_dir)
    return lib.fetch_tiingo(symbol, VENDOR_FETCH_START, VENDOR_FETCH_END, raw_dir, manifest_path, session)


def broker_frame(symbol: str, raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH,
                 session: requests.Session | None = None) -> pd.DataFrame:
    """The broker bars of ``symbol`` for the overlap window: reused by hash,
    present, or fetched (raises without credentials)."""
    if symbol in REUSED_BROKER_FILES:
        name, source = REUSED_BROKER_FILES[symbol]
        lib.reuse_file(name, source, raw_dir, manifest_path)
        return lib.load_alpaca(symbol, raw_dir)
    path = lib.alpaca_path(symbol, raw_dir)
    if path.exists() and path.name in lib.read_manifest(manifest_path):
        return lib.load_alpaca(symbol, raw_dir)
    return lib.fetch_alpaca(symbol, BROKER_FETCH_START, BROKER_FETCH_END, raw_dir, manifest_path, session)


def fred_series(raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH,
                session: requests.Session | None = None) -> pd.Series:
    """DTB3: fetched if reachable, else Study 003's file after a SHA-256 check."""
    try:
        return lib.fetch_fred(FRED_SERIES, raw_dir, manifest_path, session)
    except Exception:  # noqa: BLE001  (any failure to reach FRED falls back to the checked file)
        name, source = REUSED_FRED_FILE
        lib.reuse_file(name, source, raw_dir, manifest_path)
        return lib.load_fred(FRED_SERIES, raw_dir)
