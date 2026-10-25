"""Study 007, §14 step 2: the data step (dates only).

Copies the seven §5.1 input files byte for byte from Study 006, after checking
each file's SHA-256 against Study 006's manifest, and records dates only:
first and last rows of each file; on Study 001's committed execution calendar,
the exact holding-period counts of the test window (§8.1) and of T1b's window
(§7), the first signal month of each trial by its minimum history (§5.5), and
the vendor plan of Study 006 §5.3.2, which must reproduce Study 006's committed
``results/data_step.json`` field for field (it is inherited, not new). No
price, yield, return, carry, rank or signal value is read: only the date
column of each file.

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
SOURCE_STUDY = "006-term-spread-switch-long-history"

# All seven files from Study 006 (PREREGISTRATION.md §5.1)
FILES = [
    "fred_DGS10.csv",
    "fred_DGS7.csv",
    "fred_DTB3.csv",
    "tiingo_IEF_daily.csv",
    "alpaca_IEF_1Day_all.csv",
    "alpaca_BIL_1Day_all.csv",
    "tiingo_BIL_daily.csv",
]
CALENDAR = RESEARCH / "001-slope-duration-switch" / "results" / "execution_calendar.csv"
# Study 006 §5.3.1 overlap (inherited); Study 007 §8.1 test window; §7 T1b window.
OVERLAP = ("2003-01-01", "2018-12-31")
TEST_WINDOW = ("1974-07-01", "2018-12-31")
T1B_WINDOW = ("1979-07-01", "2018-12-31")
FIRST_SIGNAL_MONTH = "1969-07"  # first month with DGS7 (Study 001 §16); carries are counted from it
MIN_HISTORY = {"T1": 60, "T1a": 36, "T1b": 120}  # §6.2
TREND_LAG_ROWS = 12  # §6.3: the trend signal needs twelve earlier signal dates
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
    src_dir = RESEARCH / SOURCE_STUDY
    src_manifest = json.loads((src_dir / "results" / "data_manifest.json").read_text())
    for name in FILES:
        expected = src_manifest[name]["sha256"]
        src = src_dir / "data" / "raw" / name
        got = sha256(src)
        if got != expected:
            raise SystemExit(f"STOP: {name} in Study 006 has SHA-256 {got}, manifest says {expected}")
        dst = raw / name
        shutil.copyfile(src, dst)
        if sha256(dst) != expected:
            raise SystemExit(f"STOP: copy of {name} does not match")
        d = dates_of(dst)
        entry = {k: v for k, v in src_manifest[name].items() if k not in ("reused_at_utc", "reused_from")}
        entry.update(
            {
                "reused_from": "Study 006 data/raw (same bytes; SHA-256 verified against Study 006 results/data_manifest.json)",
                "reused_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "rows_read_here": len(d),
                "first_date_read_here": d[0],
                "last_date_read_here": d[-1],
            }
        )
        manifest[name] = entry
    return manifest


def calendar_rows() -> list[dict]:
    with CALENDAR.open(newline="") as f:
        return [r for r in csv.DictReader(f)]


def in_window(rows: list[dict], window: tuple[str, str]) -> list[dict]:
    return [r for r in rows if window[0] <= r["execution_date"] <= window[1]]


def vendor_plan(rows: list[dict]) -> dict:
    """Study 006 §5.3.2 on the overlap, inherited; reproduced here as a check on the copy."""
    raw = HERE / "data" / "raw"
    have = {
        "ief_alpaca": set(dates_of(raw / "alpaca_IEF_1Day_all.csv")),
        "ief_tiingo": set(dates_of(raw / "tiingo_IEF_daily.csv")),
        "bil_alpaca": set(dates_of(raw / "alpaca_BIL_1Day_all.csv")),
        "bil_tiingo": set(dates_of(raw / "tiingo_BIL_daily.csv")),
    }
    cal = in_window(rows, OVERLAP)
    if len(cal) != EXPECTED_OVERLAP_PERIODS:
        raise SystemExit(f"STOP: {len(cal)} overlap periods, expected {EXPECTED_OVERLAP_PERIODS}")

    def pick(asset: str, a: str, b: str) -> str | None:
        if a in have[f"{asset}_alpaca"] and b in have[f"{asset}_alpaca"]:
            return "alpaca"
        if a in have[f"{asset}_tiingo"] and b in have[f"{asset}_tiingo"]:
            return "tiingo"
        return None

    periods = [
        {
            "signal_month": r["month"],
            "execution_date": r["execution_date"],
            "period_end": r["period_end"],
            "ief": pick("ief", r["execution_date"], r["period_end"]),
            "bil": pick("bil", r["execution_date"], r["period_end"]),
        }
        for r in cal
    ]
    first_bil = next(p for p in periods if p["bil"] is not None)
    after = periods[periods.index(first_bil) :]
    plan = {
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
    }
    committed = json.loads((RESEARCH / SOURCE_STUDY / "results" / "data_step.json").read_text())
    diffs = {k: (plan[k], committed.get(k)) for k in plan if plan[k] != committed.get(k)}
    if diffs:
        raise SystemExit(f"STOP: vendor plan differs from Study 006's committed data_step.json: {diffs}")
    plan["matches_study_006_data_step_json"] = True
    return plan


def windows(rows: list[dict]) -> dict:
    """Exact period counts and first signal months (§5.5, §7, §8.1), from the calendar's dates only."""
    months = [r["month"] for r in rows]
    if months[0] != FIRST_SIGNAL_MONTH:
        raise SystemExit(f"STOP: calendar starts at {months[0]}, expected {FIRST_SIGNAL_MONTH}")
    gaps = [
        (a, b)
        for a, b in zip(months, months[1:], strict=False)
        if (int(b[:4]) * 12 + int(b[5:7])) - (int(a[:4]) * 12 + int(a[5:7])) != 1
    ]
    test = in_window(rows, TEST_WINDOW)
    t1b = in_window(rows, T1B_WINDOW)
    first_signal = {k: months[m - 1] for k, m in MIN_HISTORY.items()}  # the m-th carry is the m-th calendar row
    first_signal["T2_T3_trend"] = months[TREND_LAG_ROWS]  # the first signal date with twelve earlier rows
    return {
        "calendar_file": str(CALENDAR.relative_to(RESEARCH.parent)),
        "calendar_sha256": sha256(CALENDAR),
        "calendar_rows": len(rows),
        "calendar_month_gaps": gaps,
        "test_window": {
            "execution_dates": TEST_WINDOW,
            "periods": len(test),
            "first_signal_month": test[0]["month"],
            "first_signal_date": test[0]["signal_date"],
            "first_execution_date": test[0]["execution_date"],
            "last_signal_month": test[-1]["month"],
            "last_period_end": test[-1]["period_end"],
        },
        "t1b_window": {
            "execution_dates": T1B_WINDOW,
            "periods": len(t1b),
            "first_signal_month": t1b[0]["month"],
            "first_execution_date": t1b[0]["execution_date"],
            "last_period_end": t1b[-1]["period_end"],
        },
        "first_signal_month_by_minimum_history": first_signal,
        "note": (
            "Counted from the calendar's rows: the m-th month-end carry is the m-th calendar row from "
            f"{FIRST_SIGNAL_MONTH}. Whether DGS7 is present on every signal date (a carry undefined on a "
            "date is handled at the code step, Study 006 section 16 (c)) is not read here."
        ),
    }


def main() -> None:
    manifest = copy_verified()
    rows = calendar_rows()
    plan = vendor_plan(rows)
    win = windows(rows)
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / "data_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    (out / "data_step.json").write_text(
        json.dumps({"run_at_utc": stamp, "windows": win, "vendor_plan_inherited_from_006": plan}, indent=2) + "\n"
    )
    tw, tb, fs = win["test_window"], win["t1b_window"], win["first_signal_month_by_minimum_history"]
    lines = [
        "# Study 007 data step (§14 step 2): dates only",
        "",
        f"Run {stamp}. Study 006's seven files copied byte for byte after a SHA-256 match with Study 006's "
        "manifest (`data_manifest.json`). Only date columns were read; no price, yield, return, carry, rank "
        "or signal value.",
        "",
        "| File | Source | Rows | First date | Last date |",
        "|---|---|---|---|---|",
    ]
    for name in FILES:
        m = manifest[name]
        lines.append(f"| `{name}` | Study 006 | {m['rows_read_here']:,} | {m['first_date_read_here']} | {m['last_date_read_here']} |")
    lines += [
        "",
        f"Windows on Study 001's execution calendar (SHA-256 `{win['calendar_sha256'][:12]}…`, "
        f"{win['calendar_rows']} rows from {FIRST_SIGNAL_MONTH}; month gaps: {win['calendar_month_gaps'] or 'none'}):",
        "",
        f"- **Test window (§8.1): {tw['periods']} holding periods**, signal months {tw['first_signal_month']} to "
        f"{tw['last_signal_month']}, first execution date {tw['first_execution_date']}, last period end {tw['last_period_end']}.",
        f"- **T1b's window (§7): {tb['periods']} periods**, first signal month {tb['first_signal_month']}, "
        f"first execution date {tb['first_execution_date']}.",
        f"- First signal month by minimum history (§5.5, §6.2): T1 (60) {fs['T1']}, T1a (36) {fs['T1a']}, "
        f"T1b (120) {fs['T1b']}; the trend signal (twelve earlier rows, §6.3) from {fs['T2_T3_trend']}.",
        f"- {win['note']}",
        "",
        "Vendor plan on the 2003–2018 overlap (Study 006 §5.3.2, inherited): reproduced field for field from "
        f"Study 006's committed `data_step.json` ({plan['overlap_periods']} periods; IEF Tiingo "
        f"{plan['ief_tiingo_periods']} / Alpaca {plan['ief_alpaca_periods']}; first BIL period signal month "
        f"{plan['first_bil_period']['signal_month']}; {plan['periods_with_synthetic_cash_both_sides']} periods with synthetic cash on both sides).",
        "",
    ]
    (out / "data_step.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
