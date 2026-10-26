"""Study 011: load the value-weighted monthly industry returns from the data step's snapshot (§5).

This is the first code that reads industry values. It is called only by the
history run (``reproduce.sh --history``, §14 step 6) and by the tests on
synthetic zips. Each zip is checked against ``results/data_manifest.json``
(SHA-256 of the zip as downloaded) before it is opened; only the section titled
"Average Value Weighted Returns -- Monthly" is parsed; values stay in percent a
month as printed. A missing-value code ("-99.99", "-999") or an empty field
becomes NaN and is handled by the rule (§6.5); the data step found none.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

SECTION_TITLE = "Average Value Weighted Returns -- Monthly"
MARKERS = ("-99.99", "-999", "")
FILES = {17: "17_Industry_Portfolios_CSV.zip", 30: "30_Industry_Portfolios_CSV.zip"}


def vw_monthly(text: str) -> pd.DataFrame:
    lines = text.splitlines()
    titles = [i for i, ln in enumerate(lines) if " ".join(ln.split()) == SECTION_TITLE]
    if len(titles) != 1:
        raise ValueError(f"{len(titles)} value-weighted monthly sections")
    h = titles[0] + 1
    while not lines[h].strip():
        h += 1
    columns = [c.strip() for c in lines[h].split(",")[1:]]
    months, rows = [], []
    for ln in lines[h + 1 :]:
        fields = [x.strip() for x in ln.split(",")]
        if not re.fullmatch(r"\d{6}", fields[0]):
            break
        if len(fields) - 1 != len(columns):
            raise ValueError(f"wrong field count in {fields[0]}")
        rows.append([np.nan if v in MARKERS else float(v) for v in fields[1:]])
        months.append(pd.Period(f"{fields[0][:4]}-{fields[0][4:]}", "M"))
    idx = pd.PeriodIndex(months, freq="M")
    if len(idx) != len(pd.period_range(idx[0], idx[-1], freq="M")) or not idx.is_monotonic_increasing:
        raise ValueError("month gap, duplicate or disorder")
    return pd.DataFrame(rows, index=idx, columns=columns)


def read_zip(zbytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        members = [n for n in z.namelist() if not n.endswith("/")]
        if len(members) != 1:
            raise ValueError("zip must hold one CSV")
        return z.read(members[0]).decode("latin-1")


def load_industries(raw_dir: Path, manifest_path: Path) -> dict[int, pd.DataFrame]:
    """{17: frame, 30: frame}, each checked against the manifest's SHA-256."""
    manifest = json.loads(manifest_path.read_text())["files"]
    out = {}
    for n, name in FILES.items():
        b = (raw_dir / name).read_bytes()
        if hashlib.sha256(b).hexdigest() != manifest[name]["sha256"]:
            raise SystemExit(f"STOP: {name} does not match the manifest's SHA-256 (§5.2: no second download)")
        f = vw_monthly(read_zip(b))
        if f.shape[1] != n:
            raise SystemExit(f"STOP: {name} has {f.shape[1]} industries, expected {n}")
        out[n] = f
    return out
