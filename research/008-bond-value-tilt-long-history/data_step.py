"""Study 008, §14 step 2: the data step (dates only).

Adapted from Study 007's ``data_step.py``. It

1. copies the seven §5.1 input files byte for byte from Study 006, after
   checking each file's SHA-256 against Study 006's manifest;
2. fetches ``CPIAUCNS`` (the pre-registration wrote ``CPIAUCNSA``; §16) and ``CPILFENS`` once from FRED (Study 006's endpoint),
   stores the raw bytes and records URL, UTC time, SHA-256, row count, first
   and last month, month gaps and the months whose value is empty;
3. attempts the vintage and release-date check of §5.1 through ALFRED's
   keyless endpoints and records the HTTP outcome of each attempt; if none
   answers with data, the check is recorded as not done (§5.1, last sentence)
   and every signal month takes §6.1's "assumed known" branch;
4. on Study 001's committed execution calendar, records which signal months
   have a defined real yield (both CPI months k = m - 1 and k - 12 present,
   for each measure), the first signal month of each trial by its minimum
   history counted in defined real yields (§6.2), and the exact period counts
   of the test window (§8.1), T1b's window (§7) and the era window (§8.1);
5. reproduces Study 006's vendor plan field for field (inherited check).

No price, yield, return, CPI level, inflation rate, real yield, rank or weight
is computed or printed: for the CPI files only the date column and whether the
value field is empty are read.

Usage: ../../.venv/bin/python data_step.py   (from this folder; writes
data/raw/, results/data_manifest.json, results/data_step.{json,md})
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
SOURCE_STUDY = "006-term-spread-switch-long-history"

FILES = [
    "fred_DGS10.csv",
    "fred_DGS7.csv",
    "fred_DTB3.csv",
    "tiingo_IEF_daily.csv",
    "alpaca_IEF_1Day_all.csv",
    "alpaca_BIL_1Day_all.csv",
    "tiingo_BIL_daily.csv",
]
CPI_SERIES = {"T1": "CPIAUCNS", "T1a": "CPILFENS", "T1b": "CPIAUCNS"}  # §7 (CPIAUCNS: §16 correction of 2026-10-25 17:2x)
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
ALFRED_ATTEMPTS = [  # §5.1 (a)-(b): keyless forms tried; a key is never used (no new credentials)
    "https://alfred.stlouisfed.org/graph/alfredgraph.csv?id={series_id}&vintage_date=2000-01-14",
    "https://alfred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&vintage_date=2000-01-14",
    "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&vintage_date=2000-01-14",
]
MISSING_TOKENS = ("", ".", "NaN", "nan", "NA")
CALENDAR = RESEARCH / "001-slope-duration-switch" / "results" / "execution_calendar.csv"
OVERLAP = ("2003-01-01", "2018-12-31")
TEST_WINDOW = ("1974-07-01", "2018-12-31")
T1B_WINDOW = ("1979-07-01", "2018-12-31")
ERA_WINDOW = ("1986-01-01", "2018-12-31")  # §8.1, by execution month
EPISODE_LAST_SIGNAL_MONTH = "2026-09"  # §8.2
FIRST_SIGNAL_MONTH = "1969-07"
MIN_HISTORY = {"T1": 60, "T1a": 60, "T1b": 120}  # §6.2: T1b's first weight needs 120 defined real yields
EXPECTED_OVERLAP_PERIODS = 192
TIMEOUT_SECONDS = 60


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dates_of(path: Path) -> list[str]:
    with path.open(newline="") as f:
        reader = csv.reader(f)
        next(reader)
        return [row[0][:10] for row in reader if row]


def month_index(month: str) -> int:
    return int(month[:4]) * 12 + int(month[5:7]) - 1


def month_str(index: int) -> str:
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


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


def presence(text: str) -> dict[str, bool]:
    """Month -> whether the value field is non-empty. The value itself is not parsed."""
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows[0]) != 2:
        raise SystemExit(f"STOP: expected two columns, got {rows[0]}")
    out: dict[str, bool] = {}
    for row in rows[1:]:
        if not row:
            continue
        day = row[0][:10]
        if day[8:10] != "01":
            raise SystemExit(f"STOP: CPI row not dated on the first of a month: {day}")
        if day[:7] in out:
            raise SystemExit(f"STOP: duplicate CPI month {day[:7]}")
        out[day[:7]] = row[1].strip() not in MISSING_TOKENS
    return out


def fetch_cpi(series_id: str) -> tuple[dict, dict[str, bool]]:
    url = FRED_URL.format(series_id=series_id)
    response = requests.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    path = HERE / "data" / "raw" / f"fred_{series_id}.csv"
    path.write_text(response.text, encoding="utf-8")
    have = presence(response.text)
    months = sorted(have)
    idx = [month_index(m) for m in months]
    gaps = [(a, b) for a, b, i, j in zip(months, months[1:], idx, idx[1:], strict=False) if j - i != 1]
    entry = {
        "source": "FRED",
        "url": url,
        "downloaded_at_utc": stamp,
        "sha256": sha256(path),
        "rows": len(months),
        "first_month": months[0],
        "last_month": months[-1],
        "month_gaps": gaps,
        "months_with_empty_value": [m for m in months if not have[m]],
        "note": "dates and value presence only; no CPI level read or printed by the data step",
    }
    return entry, have


def alfred_check(series_id: str) -> dict:
    attempts = []
    for template in ALFRED_ATTEMPTS:
        url = template.format(series_id=series_id)
        try:
            r = requests.get(url, timeout=TIMEOUT_SECONDS)
            ok = r.status_code == 200 and r.text[:200].lower().startswith(("observation_date", "date"))
            attempts.append({"url": url, "http_status": r.status_code,
                             "content_type": r.headers.get("content-type", ""), "csv_with_data": ok})
        except requests.RequestException as exc:
            attempts.append({"url": url, "error": type(exc).__name__, "csv_with_data": False})
    done = any(a["csv_with_data"] for a in attempts)
    return {
        "attempts": attempts,
        "check_done": done,
        "consequence": (
            "a keyless ALFRED vintage answered; the comparison is a separate, logged step"
            if done
            else "not done: no keyless ALFRED endpoint answered with data (no API key is used: no new "
            "credentials). Per PREREGISTRATION §5.1 the no-revision property of the unadjusted CPI is "
            "BLS's published policy, unverified here, and no first-release date is read, so every signal "
            "month takes §6.1's 'assumed known' branch (k = m - 1)."
        ),
    }


def calendar_rows() -> list[dict]:
    with CALENDAR.open(newline="") as f:
        return list(csv.DictReader(f))


def in_window(rows: list[dict], window: tuple[str, str]) -> list[dict]:
    return [r for r in rows if window[0] <= r["execution_date"] <= window[1]]


def vendor_plan(rows: list[dict]) -> dict:
    """Study 006 §5.3.2 on the overlap, inherited; reproduced as a check on the copy (Study 007's code)."""
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


def defined_months(rows: list[dict], have: dict[str, bool]) -> tuple[list[str], list[str]]:
    """Signal months whose real yield is defined under §6.1 (k = m - 1 and k - 12 present), and the others.

    Study 001's calendar lists signal month 2018-12 twice (Study 007's data step); months are taken once each.
    """
    months = list(dict.fromkeys(r["month"] for r in rows))
    ok, undefined = [], []
    for m in months:
        k = month_index(m) - 1
        if have.get(month_str(k), False) and have.get(month_str(k - 12), False):
            ok.append(m)
        else:
            undefined.append(m)
    return ok, undefined


def windows(rows: list[dict], cpi: dict[str, dict[str, bool]]) -> dict:
    months = [r["month"] for r in rows]
    if months[0] != FIRST_SIGNAL_MONTH:
        raise SystemExit(f"STOP: calendar starts at {months[0]}, expected {FIRST_SIGNAL_MONTH}")
    test = in_window(rows, TEST_WINDOW)
    t1b = in_window(rows, T1B_WINDOW)
    era = in_window(rows, ERA_WINDOW)
    by_trial = {}
    for trial, series in CPI_SERIES.items():
        ok, undefined = defined_months(rows, cpi[series])
        first = ok[MIN_HISTORY[trial] - 1]
        by_trial[trial] = {
            "cpi_series": series,
            "defined_signal_months": len(ok),
            "undefined_signal_months": undefined,
            "undefined_to_2018_12": [m for m in undefined if m <= "2018-12"],
            "undefined_2019_01_to_2026_09": [m for m in undefined if "2019-01" <= m <= EPISODE_LAST_SIGNAL_MONTH],
            "first_signal_month_with_weight": first,
            "availability_branch_counts": {"release_date_read": 0, "assumed_known": len(ok)},
        }
    return {
        "calendar_file": str(CALENDAR.relative_to(RESEARCH.parent)),
        "calendar_sha256": sha256(CALENDAR),
        "calendar_rows": len(rows),
        "test_window": {
            "execution_dates": TEST_WINDOW,
            "periods": len(test),
            "first_signal_month": test[0]["month"],
            "first_execution_date": test[0]["execution_date"],
            "last_signal_month": test[-1]["month"],
            "last_period_end": test[-1]["period_end"],
        },
        "t1b_window": {
            "execution_dates": T1B_WINDOW,
            "periods": len(t1b),
            "first_signal_month": t1b[0]["month"],
            "first_execution_date": t1b[0]["execution_date"],
        },
        "era_window": {
            "execution_dates": ERA_WINDOW,
            "periods": len(era),
            "first_execution_date": era[0]["execution_date"],
            "last_period_end": era[-1]["period_end"],
        },
        "by_trial": by_trial,
    }


def main() -> None:
    manifest = copy_verified()
    cpi_presence: dict[str, dict[str, bool]] = {}
    alfred: dict[str, dict] = {}
    for series_id in ("CPIAUCNS", "CPILFENS"):
        entry, have = fetch_cpi(series_id)
        manifest[f"fred_{series_id}.csv"] = entry
        cpi_presence[series_id] = have
        alfred[series_id] = alfred_check(series_id)
    rows = calendar_rows()
    plan = vendor_plan(rows)
    win = windows(rows, cpi_presence)
    for trial, first in (("T1", "1974-06"), ("T1a", "1974-06"), ("T1b", "1979-06")):
        if win["by_trial"][trial]["first_signal_month_with_weight"] != first:
            print(f"NOTE: {trial}'s first weight is {win['by_trial'][trial]['first_signal_month_with_weight']}, "
                  f"not {first} as PREREGISTRATION §5.5 expected; recorded, windows of §8.1 unchanged")
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / "data_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    (out / "data_step.json").write_text(
        json.dumps({"run_at_utc": stamp, "windows": win, "alfred_check": alfred,
                    "vendor_plan_inherited_from_006": plan}, indent=2) + "\n"
    )
    tw, tb, er = win["test_window"], win["t1b_window"], win["era_window"]
    lines = [
        "# Study 008 data step (§14 step 2): dates only",
        "",
        f"Run {stamp}. Study 006's seven files copied byte for byte after a SHA-256 match with Study 006's "
        "manifest; `CPIAUCNSA` and `CPILFENS` fetched once from FRED (`data_manifest.json`). Only date columns "
        "and, for the CPI files, whether each month's value is empty were read; no CPI level, inflation rate, "
        "real yield, rank, weight, price, yield or return.",
        "",
        "| File | Source | Rows | First | Last |",
        "|---|---|---|---|---|",
    ]
    for name in FILES:
        m = manifest[name]
        lines.append(f"| `{name}` | Study 006 | {m['rows_read_here']:,} | {m['first_date_read_here']} | {m['last_date_read_here']} |")
    for series_id in ("CPIAUCNS", "CPILFENS"):
        m = manifest[f"fred_{series_id}.csv"]
        lines.append(f"| `fred_{series_id}.csv` | FRED, {m['downloaded_at_utc']} | {m['rows']:,} months | {m['first_month']} | {m['last_month']} |")
    lines += [""]
    for series_id in ("CPIAUCNS", "CPILFENS"):
        m = manifest[f"fred_{series_id}.csv"]
        lines.append(f"- `{series_id}`: month gaps {m['month_gaps'] or 'none'}; months with an empty value "
                     f"{m['months_with_empty_value'] or 'none'}.")
    lines += [
        "",
        "**Vintage and release-date check (§5.1):** "
        + ("done" if all(a["check_done"] for a in alfred.values()) else "**not done**")
        + ". Attempts (keyless; no API key used): "
        + "; ".join(f"`{a['url'].split('?')[0]}` → {a.get('http_status', a.get('error'))}" for a in alfred["CPIAUCNS"]["attempts"])
        + ". " + alfred["CPIAUCNS"]["consequence"],
        "",
        f"Windows on Study 001's execution calendar (SHA-256 `{win['calendar_sha256'][:12]}…`, {win['calendar_rows']} rows from {FIRST_SIGNAL_MONTH}):",
        "",
        f"- **Test window (§8.1): {tw['periods']} holding periods**, signal months {tw['first_signal_month']} to "
        f"{tw['last_signal_month']}, first execution {tw['first_execution_date']}, last period end {tw['last_period_end']}.",
        f"- **T1b's window (§7): {tb['periods']} periods**, first signal month {tb['first_signal_month']}, first execution {tb['first_execution_date']}.",
        f"- **Era window (§8.1): {er['periods']} periods**, execution {er['first_execution_date']} to period end {er['last_period_end']}.",
    ]
    for trial, t in win["by_trial"].items():
        lines.append(
            f"- {trial} (`{t['cpi_series']}`): {t['defined_signal_months']} signal months with a defined real yield; "
            f"undefined to 2018-12: {t['undefined_to_2018_12'] or 'none'}; undefined in 2019-01 to 2026-09: "
            f"{t['undefined_2019_01_to_2026_09'] or 'none'}; first weight at signal month {t['first_signal_month_with_weight']}; "
            f"§6.1 branches: release date read {t['availability_branch_counts']['release_date_read']}, "
            f"assumed known {t['availability_branch_counts']['assumed_known']}."
        )
    lines += [
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
