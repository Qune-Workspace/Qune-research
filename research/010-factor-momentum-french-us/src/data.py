"""Study 010: load the monthly factor values from the data step's snapshot (§5).

This is the first code that reads factor values. It is called only by the
history run (``reproduce.sh --history``, §14 step 6) and by the tests on
synthetic zips. Each zip is checked against ``results/data_manifest.json``
(SHA-256 of the zip as downloaded) before it is opened; only the monthly
section (first field a six-digit YYYYMM) is parsed; values stay in percent a
month as printed. A missing-value code (−99.99, −999) or an empty field raises,
since the data step found none and §6.5 stops the study on one.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import pandas as pd

FILES = {
    "F-F_Research_Data_Factors_CSV.zip": ["SMB", "HML"],
    "F-F_ST_Reversal_Factor_CSV.zip": ["ST_Rev"],
    "F-F_LT_Reversal_Factor_CSV.zip": ["LT_Rev"],
}
MARKERS = (-99.99, -999.0)


def monthly_section(text: str) -> pd.DataFrame:
    lines = text.splitlines()
    first = next(i for i, ln in enumerate(lines) if re.fullmatch(r"\d{6}", ln.split(",")[0].strip()))
    columns = [c.strip() for c in lines[first - 1].split(",")[1:]]
    months, rows = [], []
    for ln in lines[first:]:
        fields = [x.strip() for x in ln.split(",")]
        if not re.fullmatch(r"\d{6}", fields[0]):
            break
        if len(fields) - 1 != len(columns):
            raise ValueError(f"wrong field count in {fields[0]}")
        vals = []
        for c, v in zip(columns, fields[1:]):
            if v == "" or float(v) in MARKERS:
                raise ValueError(f"missing value in {c} {fields[0]} (§6.5 stops the study)")
            vals.append(float(v))
        months.append(pd.Period(f"{fields[0][:4]}-{fields[0][4:]}", "M"))
        rows.append(vals)
    return pd.DataFrame(rows, index=pd.PeriodIndex(months, freq="M"), columns=columns)


def read_zip(zbytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        members = [n for n in z.namelist() if not n.endswith("/")]
        if len(members) != 1:
            raise ValueError("zip must hold one CSV")
        return z.read(members[0]).decode("latin-1")


def load_factors(raw_dir: Path, manifest_path: Path) -> pd.DataFrame:
    """SMB, HML, ST_Rev, LT_Rev on the union of months (NaN where a file has no row)."""
    manifest = json.loads(manifest_path.read_text())["files"]
    parts = []
    for name, cols in FILES.items():
        b = (raw_dir / name).read_bytes()
        if hashlib.sha256(b).hexdigest() != manifest[name]["sha256"]:
            raise SystemExit(f"STOP: {name} does not match the manifest's SHA-256 (§5.2: no second download)")
        parts.append(monthly_section(read_zip(b))[cols])
    f = pd.concat(parts, axis=1).sort_index()
    full = pd.period_range(f.index[0], f.index[-1], freq="M")
    if len(full) != len(f):
        raise ValueError("month gap across the files")
    return f
