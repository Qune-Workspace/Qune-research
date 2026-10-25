"""Study 006, §14 step 2: the data step (dates only).

Copies the §5.1 input files byte for byte from the studies that fetched them,
after checking each file's SHA-256 against the source study's manifest, and
records dates only: first and last rows, and, on Study 001's committed
execution calendar, which vendor serves each of the 192 overlap holding
periods under §5.3.2 and the first period with BIL. No price, yield, return or
signal value is read: only the date column of each file.

Usage: python data_step.py   (from this folder; writes data/raw/,
results/data_manifest.json, results/data_step.{json,md})
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent

# (file name, source study folder) as PREREGISTRATION.md §5.1
SOURCES = [
    ("fred_DGS10.csv", "002-slope-duration-switch-r"),
    ("fred_DGS7.csv", "002-slope-duration-switch-r"),
    ("fred_DTB3.csv", "002-slope-duration-switch-r"),
    ("tiingo_IEF_daily.csv", "002-slope-duration-switch-r"),
    ("alpaca_IEF_1Day_all.csv", "002-slope-duration-switch-r"),
    ("alpaca_BIL_1Day_all.csv", "002-slope-duration-switch-r"),
    ("tiingo_BIL_daily.csv", "004-xasset-trend-voltarget"),
]
CALENDAR = RESEARCH / "001-slope-duration-switch" / "results" / "execution_calendar.csv"
OVERLAP_FIRST_EXEC = "2003-01-01"  # first NYSE trading day of January 2003 and later
OVERLAP_LAST_EXEC = "2018-12-31"  # last period starts in December 2018
EXPECTED_OVERLAP_PERIODS = 192


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dates_of(path: Path) -> list[str]:
    """Date column only (first column); FRED rows with a missing value count as dates too."""
    with path.open(newline="") as f:
        reader = csv.reader(f)
        next(reader)
        return [row[0][:10] for row in reader if row]


def copy_verified() -> dict:
    manifest: dict = {}
    raw = HERE / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for name, study in SOURCES:
        src_dir = RESEARCH / study
        src_manifest = json.loads((src_dir / "results" / "data_manifest.json").read_text())
        expected = src_manifest[name]["sha256"]
        src = src_dir / "data" / "raw" / name
        got = sha256(src)
        if got != expected:
            raise SystemExit(f"STOP: {name} in {study} has SHA-256 {got}, manifest says {expected}")
        dst = raw / name
        shutil.copyfile(src, dst)
        if sha256(dst) != expected:
            raise SystemExit(f"STOP: copy of {name} does not match")
        d = dates_of(dst)
        entry = {k: v for k, v in src_manifest[name].items() if k not in ("reused_at_utc", "reused_from")}
        entry.update(
            {
                "reused_from": f"Study {study[:3]} data/raw (same bytes; SHA-256 verified against Study {study[:3]} results/data_manifest.json)",
                "reused_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "rows_read_here": len(d),
                "first_date_read_here": d[0],
                "last_date_read_here": d[-1],
            }
        )
        manifest[name] = entry
    return manifest


def vendor_plan() -> dict:
    raw = HERE / "data" / "raw"
    have = {
        "ief_alpaca": set(dates_of(raw / "alpaca_IEF_1Day_all.csv")),
        "ief_tiingo": set(dates_of(raw / "tiingo_IEF_daily.csv")),
        "bil_alpaca": set(dates_of(raw / "alpaca_BIL_1Day_all.csv")),
        "bil_tiingo": set(dates_of(raw / "tiingo_BIL_daily.csv")),
    }
    with CALENDAR.open(newline="") as f:
        cal = [r for r in csv.DictReader(f) if OVERLAP_FIRST_EXEC <= r["execution_date"] <= OVERLAP_LAST_EXEC]
    if len(cal) != EXPECTED_OVERLAP_PERIODS:
        raise SystemExit(f"STOP: {len(cal)} overlap periods, expected {EXPECTED_OVERLAP_PERIODS}")

    def pick(asset: str, a: str, b: str) -> str | None:
        if a in have[f"{asset}_alpaca"] and b in have[f"{asset}_alpaca"]:
            return "alpaca"
        if a in have[f"{asset}_tiingo"] and b in have[f"{asset}_tiingo"]:
            return "tiingo"
        return None

    periods = []
    for r in cal:
        a, b = r["execution_date"], r["period_end"]
        periods.append(
            {
                "signal_month": r["month"],
                "execution_date": a,
                "period_end": b,
                "ief": pick("ief", a, b),
                "bil": pick("bil", a, b),
            }
        )
    first_bil = next(p for p in periods if p["bil"] is not None)
    after = periods[periods.index(first_bil) :]
    return {
        "calendar_file": str(CALENDAR.relative_to(RESEARCH.parent)),
        "calendar_sha256": sha256(CALENDAR),
        "overlap_periods": len(periods),
        "first_execution_date": periods[0]["execution_date"],
        "last_period_end": periods[-1]["period_end"],
        "ief_tiingo_periods": sum(p["ief"] == "tiingo" for p in periods),
        "ief_alpaca_periods": sum(p["ief"] == "alpaca" for p in periods),
        "ief_missing_periods": [p["signal_month"] for p in periods if p["ief"] is None],
        "first_bil_period": first_bil,
        "periods_with_synthetic_cash_both_sides": periods.index(first_bil),
        "bil_tiingo_periods": sum(p["bil"] == "tiingo" for p in periods),
        "bil_alpaca_periods": sum(p["bil"] == "alpaca" for p in periods),
        "bil_missing_after_first": [p["signal_month"] for p in after if p["bil"] is None],
        "first_alpaca_ief_period": next(p for p in periods if p["ief"] == "alpaca"),
        "periods": periods,
    }


def main() -> None:
    manifest = copy_verified()
    plan = vendor_plan()
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / "data_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    (out / "data_step.json").write_text(json.dumps({"run_at_utc": stamp, **plan}, indent=2) + "\n")
    lines = [
        "# Study 006 data step (§14 step 2): dates only",
        "",
        f"Run {stamp}. Files copied byte for byte after a SHA-256 match with the source study's manifest "
        "(`data_manifest.json`). Only date columns were read; no price, yield, return or signal value.",
        "",
        "| File | Source | Rows | First date | Last date |",
        "|---|---|---|---|---|",
    ]
    for name, study in SOURCES:
        m = manifest[name]
        lines.append(
            f"| `{name}` | Study {study[:3]} | {m['rows_read_here']:,} | {m['first_date_read_here']} | {m['last_date_read_here']} |"
        )
    fb, fa = plan["first_bil_period"], plan["first_alpaca_ief_period"]
    lines += [
        "",
        f"Vendor plan on Study 001's execution calendar (SHA-256 `{plan['calendar_sha256'][:12]}…`), §5.3.2:",
        "",
        f"- Overlap periods: {plan['overlap_periods']} (execution {plan['first_execution_date']} to period end {plan['last_period_end']}).",
        f"- IEF: Tiingo {plan['ief_tiingo_periods']}, Alpaca {plan['ief_alpaca_periods']} (first Alpaca period: execution {fa['execution_date']}); missing: {plan['ief_missing_periods'] or 'none'}.",
        f"- BIL: first period with BIL at both ends: signal month {fb['signal_month']}, execution {fb['execution_date']} to {fb['period_end']} ({fb['bil']}). "
        f"Synthetic cash on both sides before it: {plan['periods_with_synthetic_cash_both_sides']} periods. "
        f"From it: Tiingo {plan['bil_tiingo_periods']}, Alpaca {plan['bil_alpaca_periods']}; missing afterwards: {plan['bil_missing_after_first'] or 'none'}.",
        "",
    ]
    (out / "data_step.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
