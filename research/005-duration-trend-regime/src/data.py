"""This study's data files (§5.1, §5.3.3) through the shared library's
adapters: which are reused by SHA-256 check from earlier studies and which
are fetched under this study.

* Tiingo IEF and SPY: reused from Study 004's ``data/raw`` after a hash check
  against Study 004's manifest (in-sample legs and regime input).
* FRED DTB3: reused from Study 003 (in-sample cash leg).
* Alpaca IEF and BIL: reused from Study 003 (episode legs and signal).
* Alpaca SPY 2016–2018 (the overlap file of Study 004): reused into
  ``data/raw/overlap/`` for D1 only, recorded under the key
  ``overlap/alpaca_SPY_1Day_all.csv`` so it never collides with the episode
  fetch of the same symbol.
* Alpaca SPY 2018-09-01 to 2026-09-30: **fetched under this study** (§5.3.3
  step 1) with the desk's credential from the environment; never logged.
* CPIAUCNS: fetched from FRED (§5.3.3 step 2).

Every file's provenance and SHA-256 go to ``results/data_manifest.json``.
Raw files are git-ignored.  Credentials come from the environment only.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import requests

from qune_research import data as lib

from .config import (ALPACA_FETCH, CASH_LEG, CPI_SERIES, DURATION_LEG, MANIFEST_PATH, OVERLAP_SUBDIR, RAW_DIR,
                     REGIME_SYMBOL, REUSED_ALPACA, REUSED_ALPACA_OVERLAP, REUSED_FRED, REUSED_TIINGO)


def tiingo_frame(symbol: str, raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH) -> pd.DataFrame:
    name, source = REUSED_TIINGO[symbol]
    lib.reuse_file(name, source, raw_dir, manifest_path)
    return lib.load_tiingo(symbol, raw_dir)


def dtb3_series(raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH) -> pd.Series:
    name, source = REUSED_FRED["DTB3"]
    lib.reuse_file(name, source, raw_dir, manifest_path)
    return lib.load_fred("DTB3", raw_dir)


def alpaca_frame(symbol: str, raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH,
                 session: requests.Session | None = None, refetch: bool = False) -> pd.DataFrame:
    """IEF and BIL reused from Study 003; SPY fetched for the episode window
    (present and recorded files are not fetched again unless ``refetch``)."""
    if symbol in REUSED_ALPACA:
        name, source = REUSED_ALPACA[symbol]
        lib.reuse_file(name, source, raw_dir, manifest_path)
        return lib.load_alpaca(symbol, raw_dir)
    start, end = ALPACA_FETCH[symbol]
    path = lib.alpaca_path(symbol, raw_dir)
    if path.exists() and not refetch and path.name in lib.read_manifest(manifest_path):
        return lib.load_alpaca(symbol, raw_dir)
    return lib.fetch_alpaca(symbol, start, end, raw_dir, manifest_path, session)


def alpaca_overlap_frame(symbol: str = REGIME_SYMBOL, raw_dir: Path = RAW_DIR,
                         manifest_path: Path = MANIFEST_PATH) -> pd.DataFrame:
    """Study 004's 2016–2018 broker SPY file for D1, kept in a sub-folder and
    recorded under a prefixed key."""
    name, source = REUSED_ALPACA_OVERLAP[symbol]
    sub = Path(raw_dir) / OVERLAP_SUBDIR
    scratch = sub / "manifest.tmp.json"
    lib.reuse_file(name, source, sub, scratch)
    entry = json.loads(scratch.read_text(encoding="utf-8"))[name]
    scratch.unlink()
    lib.update_manifest(f"{OVERLAP_SUBDIR}/{name}", entry, manifest_path)
    return lib.load_alpaca(symbol, sub)


def cpi_series(raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH,
               session: requests.Session | None = None, refetch: bool = False) -> pd.Series:
    """CPIAUCNS, fetched once and recorded; reloaded from disk afterwards."""
    path = lib.fred_path(CPI_SERIES, raw_dir)
    if path.exists() and not refetch and path.name in lib.read_manifest(manifest_path):
        return lib.load_fred(CPI_SERIES, raw_dir)
    return lib.fetch_fred(CPI_SERIES, raw_dir, manifest_path, session)


def insample_closes(raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH) -> dict[str, pd.Series]:
    """Tiingo adjusted closes of IEF and SPY (in-sample window inputs)."""
    return {s: tiingo_frame(s, raw_dir, manifest_path)["adjClose"].astype(float).dropna()
            for s in (DURATION_LEG, REGIME_SYMBOL)}


def episode_closes(raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH,
                   session: requests.Session | None = None) -> dict[str, pd.Series]:
    """Alpaca ``adjustment='all'`` closes of IEF, BIL and SPY (episode and forward inputs)."""
    return {s: alpaca_frame(s, raw_dir, manifest_path, session)["close"].astype(float).dropna()
            for s in (DURATION_LEG, CASH_LEG, REGIME_SYMBOL)}


def main(argv: list[str] | None = None) -> None:
    """The two fetches of §5.3.3, each run on its own after its trials.md
    row: ``fetch-alpaca-spy`` (the episode window, credential from the
    environment, never printed) and ``fetch-cpi`` (FRED CPIAUCNS).  Prints
    the row count, first and last date and the recorded SHA-256 prefix."""
    import argparse
    parser = argparse.ArgumentParser(description="Study 005 fetches (§5.3.3). Log the row in trials.md first.")
    parser.add_argument("step", choices=("fetch-alpaca-spy", "fetch-cpi"))
    parser.add_argument("--refetch", action="store_true", help="fetch again even if a recorded file exists")
    args = parser.parse_args(argv)
    if args.step == "fetch-alpaca-spy":
        frame = alpaca_frame(REGIME_SYMBOL, refetch=args.refetch)
        key = lib.alpaca_path(REGIME_SYMBOL, RAW_DIR).name
    else:
        frame = cpi_series(refetch=args.refetch).to_frame()
        key = lib.fred_path(CPI_SERIES, RAW_DIR).name
    entry = lib.read_manifest(MANIFEST_PATH)[key]
    print(f"{key}: {len(frame)} rows, {frame.index[0]} to {frame.index[-1]}, sha256 {entry['sha256'][:12]}..., "
          f"recorded {entry.get('downloaded_at_utc', entry.get('reused_at_utc', '?'))}")


if __name__ == "__main__":
    main()
