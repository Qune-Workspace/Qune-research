"""Reuse raw data files fetched under Studies 001 and 002 without
re-downloading (§5.1).

Study 001 fetched the IEF and BIL bars (``adjustment='all'``) and the FRED
files on 2026-10-21; Study 002 fetched the Tiingo IEF series the same day.
Each study's manifest records every download with a SHA-256.  This module
copies a file into this study's ``data/raw/`` only after verifying that its
bytes match the hash recorded in the source study's manifest, and records
the reuse in this study's manifest.  No credential is needed.  If the file
is already present with the recorded hash nothing is written.

Adapted from Study 002's ``reuse_bars.py`` (commit 2dfbdd5): the source study
is a parameter, and the Tiingo IEF file is reused from Study 002 (§5.1: the
vendor's adjusted closes are re-based on every fetch, so reusing the exact
bytes whose overlap check passed is what makes the manifest's hash meaningful).

Usage (from the study folder): ``python -m src.reuse_bars IEF BIL``,
``python -m src.reuse_bars --fred DTB3`` or ``python -m src.reuse_bars --tiingo IEF``.
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .alpaca_bars import raw_path as alpaca_raw_path
from .config import FRED_SERIES, MANIFEST_PATH, RAW_DIR, STUDY_001_DIR, STUDY_002_DIR, SYMBOLS
from .fred import raw_path as fred_raw_path
from .fred import sha256_of, update_manifest


def _reuse_note(source_dir: Path) -> str:
    label = source_dir.name.split("-")[0]
    return (f"Study {label} data/raw (same bytes; SHA-256 verified against "
            f"Study {label} results/data_manifest.json)")


def reuse_file(name: str, source_dir: Path, raw_dir: Path = RAW_DIR,
               manifest_path: Path = MANIFEST_PATH) -> Path:
    """Verify and copy ``data/raw/<name>`` from ``source_dir``.  Raises if the
    source bytes do not match that study's manifest."""
    recorded = json.loads((source_dir / "results" / "data_manifest.json").read_text(encoding="utf-8"))[name]
    source = source_dir / "data" / "raw" / name
    if sha256_of(source) != recorded["sha256"]:
        raise RuntimeError(f"{name}: SHA-256 differs from {source_dir.name}'s manifest; not reusing")
    target = raw_dir / name
    if target.exists() and sha256_of(target) == recorded["sha256"]:
        return target
    raw_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    update_manifest(name, dict(recorded, reused_from=_reuse_note(source_dir),
                               reused_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
                    manifest_path)
    return target


def reuse_study_001_bars(symbol: str, raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH,
                         source_dir: Path = STUDY_001_DIR) -> Path:
    """Alpaca bars of ``symbol`` from Study 001."""
    return reuse_file(alpaca_raw_path(symbol).name, source_dir, raw_dir, manifest_path)


def reuse_study_001_fred(series_id: str, raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH,
                         source_dir: Path = STUDY_001_DIR) -> Path:
    """FRED series ``series_id`` as downloaded under Study 001."""
    return reuse_file(fred_raw_path(series_id).name, source_dir, raw_dir, manifest_path)


def reuse_study_002_tiingo(symbol: str, raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH,
                           source_dir: Path = STUDY_002_DIR) -> Path:
    """Tiingo daily prices of ``symbol`` as fetched under Study 002."""
    return reuse_file(f"tiingo_{symbol}_daily.csv", source_dir, raw_dir, manifest_path)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Reuse earlier studies' raw files after a SHA-256 check.")
    parser.add_argument("names", nargs="*", help="ETF symbols, FRED series ids with --fred, or Tiingo symbols with --tiingo")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--fred", action="store_true", help="the names are FRED series ids (from Study 001)")
    group.add_argument("--tiingo", action="store_true", help="the names are Tiingo symbols (from Study 002)")
    args = parser.parse_args(argv)
    if args.fred:
        for series_id in args.names or list(FRED_SERIES):
            path = reuse_study_001_fred(series_id)
            print(f"{series_id}: {path.name} present, hash matches Study 001's manifest")
    elif args.tiingo:
        for symbol in args.names or ["IEF"]:
            path = reuse_study_002_tiingo(symbol)
            print(f"{symbol}: {path.name} present, hash matches Study 002's manifest")
    else:
        for symbol in args.names or list(SYMBOLS):
            path = reuse_study_001_bars(symbol)
            print(f"{symbol}: {path.name} present, hash matches Study 001's manifest")


if __name__ == "__main__":
    main()
