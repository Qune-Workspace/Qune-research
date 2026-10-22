"""Reuse Study 001's Alpaca bars without re-downloading (§5.1, §5.3.4).

The IEF and BIL bars were fetched under Study 001 with ``adjustment='all'``
(its manifest records the download).  This module copies a bar file into
this study's ``data/raw/`` only after verifying that its bytes match the
SHA-256 recorded in Study 001's manifest, and records the reuse in this
study's manifest.  No credential is needed.  If the file is already present
with the recorded hash nothing is written.

Usage (from the study folder): ``python -m src.reuse_bars IEF BIL``.
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .alpaca_bars import raw_path
from .config import MANIFEST_PATH, RAW_DIR, STUDY_DIR, SYMBOLS
from .fred import sha256_of, update_manifest

STUDY_001_DIR = STUDY_DIR.parent / "001-slope-duration-switch"
REUSE_NOTE = "Study 001 data/raw (same bytes; SHA-256 verified against Study 001 results/data_manifest.json)"


def reuse_study_001_bars(symbol: str, raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH,
                         source_dir: Path = STUDY_001_DIR) -> Path:
    """Verify and copy ``symbol``'s Alpaca bars from Study 001.  Raises if the
    source bytes do not match Study 001's manifest."""
    name = raw_path(symbol).name
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Reuse Study 001's Alpaca bars after a SHA-256 check.")
    parser.add_argument("symbols", nargs="*", default=list(SYMBOLS))
    args = parser.parse_args(argv)
    for symbol in args.symbols:
        path = reuse_study_001_bars(symbol)
        print(f"{symbol}: {path.name} present, hash matches Study 001's manifest")


if __name__ == "__main__":
    main()
