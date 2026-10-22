"""Reuse Study 001's raw data files without re-downloading (§5.1, §5.3.4).

The IEF and BIL bars were fetched under Study 001 with ``adjustment='all'``,
and its FRED files (DGS10, DTB3, DGS7) on 2026-10-21; its manifest records
every download with a SHA-256.  This module copies a file into this study's
``data/raw/`` only after verifying that its bytes match the hash recorded in
Study 001's manifest, and records the reuse in this study's manifest.  No
credential is needed.  If the file is already present with the recorded hash
nothing is written.

The FRED path exists because FRED serves an HTML maintenance page from time
to time (it did during Study 001's validation and again on 2026-10-22); a
failed fetch never overwrites ``data/raw/``, and this gives the run a
provenance-checked fallback instead of a silent one.

Usage (from the study folder): ``python -m src.reuse_bars IEF BIL`` or
``python -m src.reuse_bars --fred DGS10 DTB3 DGS7``.
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .alpaca_bars import raw_path as alpaca_raw_path
from .config import FRED_SERIES, MANIFEST_PATH, RAW_DIR, STUDY_DIR, SYMBOLS
from .fred import raw_path as fred_raw_path
from .fred import sha256_of, update_manifest

STUDY_001_DIR = STUDY_DIR.parent / "001-slope-duration-switch"
REUSE_NOTE = "Study 001 data/raw (same bytes; SHA-256 verified against Study 001 results/data_manifest.json)"


def reuse_study_001_file(name: str, raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH,
                         source_dir: Path = STUDY_001_DIR) -> Path:
    """Verify and copy ``data/raw/<name>`` from Study 001.  Raises if the
    source bytes do not match Study 001's manifest."""
    recorded = json.loads((source_dir / "results" / "data_manifest.json").read_text(encoding="utf-8"))[name]
    source = source_dir / "data" / "raw" / name
    if sha256_of(source) != recorded["sha256"]:
        raise RuntimeError(f"{name}: SHA-256 differs from Study 001's manifest; not reusing")
    target = raw_dir / name
    if target.exists() and sha256_of(target) == recorded["sha256"]:
        return target
    raw_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    update_manifest(name, dict(recorded, reused_from=REUSE_NOTE,
                               reused_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
                    manifest_path)
    return target


def reuse_study_001_bars(symbol: str, raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH,
                         source_dir: Path = STUDY_001_DIR) -> Path:
    """Alpaca bars of ``symbol`` from Study 001."""
    return reuse_study_001_file(alpaca_raw_path(symbol).name, raw_dir, manifest_path, source_dir)


def reuse_study_001_fred(series_id: str, raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH,
                         source_dir: Path = STUDY_001_DIR) -> Path:
    """FRED series ``series_id`` as downloaded under Study 001."""
    return reuse_study_001_file(fred_raw_path(series_id).name, raw_dir, manifest_path, source_dir)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Reuse Study 001's raw files after a SHA-256 check.")
    parser.add_argument("names", nargs="*", help="ETF symbols, or FRED series ids with --fred")
    parser.add_argument("--fred", action="store_true", help="the names are FRED series ids")
    args = parser.parse_args(argv)
    if args.fred:
        for series_id in args.names or list(FRED_SERIES):
            path = reuse_study_001_fred(series_id)
            print(f"{series_id}: {path.name} present, hash matches Study 001's manifest")
    else:
        for symbol in args.names or list(SYMBOLS):
            path = reuse_study_001_bars(symbol)
            print(f"{symbol}: {path.name} present, hash matches Study 001's manifest")


if __name__ == "__main__":
    main()
