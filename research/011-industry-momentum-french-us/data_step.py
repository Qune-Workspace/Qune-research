"""Study 011, §14 step 2: the data step (dates, column names, counts and missing-value markers only).

1. Reads the Kenneth French Data Library's page once and takes the download
   links of the two §5.1 files from it (the expected file names are matched
   against the page's links; a different name stops the step).
2. Downloads each file **once** into ``data/raw/`` (git-ignored) and writes
   ``results/data_manifest.json``: URL, UTC download time, SHA-256 and byte
   size of the zip and of the CSV inside it, and the text lines above the
   first section (they name the CRSP release; they hold no value). If the
   manifest already exists the step refuses to download again (§5.2: no
   second download before the history run); ``--parse-only`` re-checks the
   stored files' hashes against the manifest and re-parses.
3. Parses the **value-weighted monthly section only** (the rows under the
   title "Average Value Weighted Returns -- Monthly" whose first field is a
   six-digit YYYYMM) for dates and column names, and compares each value
   field, as a stripped string, with "-99.99", "-999" and "" (§5.3),
   recording only whether it matched. No field is parsed as a number; no
   return value is written, printed or summarised; no other section is read.
4. Applies the §5.4 stop rules and writes ``results/data_step.{json,md}``:
   first and last month, row count, gaps, duplicates, order; the last common
   month; the month counts of I1, I2, O, M and full per trial; per-month
   counts of industries with a value where below the full set; the eligible
   count at every ranking month whose cohort is held (F = 6 and 12 on the 17,
   F = 6 on the 30).

Usage: ../../.venv/bin/python data_step.py [--parse-only]   (from this folder)
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"
OUT = HERE / "results"
MANIFEST = OUT / "data_manifest.json"

LIBRARY_PAGE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"
UA = {"User-Agent": "qune-research study 011 data step (one download per file)"}

SECTION_TITLE = "Average Value Weighted Returns -- Monthly"
MARKERS = ("-99.99", "-999", "")
LIB_START = "1926-07"
END_MIN = "2026-06"

# file name -> (industries expected, eligibility floor, formation lengths used on it), PREREGISTRATION.md §5.4
FILES = {
    "17_Industry_Portfolios_CSV.zip": {"n": 17, "floor": 12, "F": (6, 12)},
    "30_Industry_Portfolios_CSV.zip": {"n": 30, "floor": 20, "F": (6,)},
}
# first ranking month whose cohort is held in any row, per formation length (§5.4)
FIRST_RANKING = {6: "1926-12", 12: "1927-06"}
# PREREGISTRATION.md §7-§8
TRIALS = {
    "M1": {"file": "17_Industry_Portfolios_CSV.zip", "F": 6, "first_holding": "1927-06"},
    "M1a": {"file": "30_Industry_Portfolios_CSV.zip", "F": 6, "first_holding": "1927-06"},
    "M1b": {"file": "17_Industry_Portfolios_CSV.zip", "F": 12, "first_holding": "1927-12"},
}
I1_END = "1963-06"
M = ("1963-07", "1995-07")
I2_START = "1995-08"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def ym_index(s: str) -> int:
    return int(s[:4]) * 12 + int(s[5:7]) - 1


def ym(i: int) -> str:
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def months_between(a: str, b: str) -> int:
    """Inclusive count of months from a to b."""
    return ym_index(b) - ym_index(a) + 1


def find_links(html: str) -> dict[str, str]:
    import requests

    hrefs = re.findall(r'href\s*=\s*"([^"]+)"', html, flags=re.I)
    links = {}
    for name in FILES:
        hits = sorted({h for h in hrefs if h.rsplit("/", 1)[-1] == name})
        if len(hits) != 1:
            raise SystemExit(f"STOP: {len(hits)} links named {name} on the library page; expected exactly one (§5.1)")
        links[name] = requests.compat.urljoin(LIBRARY_PAGE, hits[0])
    return links


def download() -> dict:
    import requests

    if MANIFEST.exists():
        raise SystemExit("STOP: results/data_manifest.json exists; §5.2 allows one download. Use --parse-only.")
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)
    page_time = now()
    page = requests.get(LIBRARY_PAGE, headers=UA, timeout=60)
    page.raise_for_status()
    links = find_links(page.text)
    manifest: dict = {
        "library_page": {"url": LIBRARY_PAGE, "read_at_utc": page_time, "sha256": sha256(page.content), "bytes": len(page.content)},
        "files": {},
    }
    for name, url in links.items():
        t = now()
        r = requests.get(url, headers=UA, timeout=120)
        r.raise_for_status()
        (RAW / name).write_bytes(r.content)
        manifest["files"][name] = {"url": url, "downloaded_at_utc": t, "sha256": sha256(r.content), "bytes": len(r.content)}
        # written after each file so that a later failure leaves the record of what was fetched
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def load_verified(manifest: dict) -> dict[str, bytes]:
    out = {}
    for name in FILES:
        b = (RAW / name).read_bytes()
        if sha256(b) != manifest["files"][name]["sha256"]:
            raise SystemExit(f"STOP: {name} on disk does not match the manifest's SHA-256")
        out[name] = b
    return out


def csv_text(zbytes: bytes) -> tuple[str, str, bytes]:
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        members = [n for n in z.namelist() if not n.endswith("/")]
        if len(members) != 1:
            raise SystemExit(f"STOP: zip holds {len(members)} files, expected one CSV")
        raw = z.read(members[0])
    return members[0], raw.decode("latin-1"), raw


def is_month(field: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", field.strip()))


def norm(s: str) -> str:
    return " ".join(s.split())


def parse_vw_monthly(text: str) -> dict:
    """Dates, column names and marker flags of the value-weighted monthly section.

    No field is converted to a number and no value leaves this function: each
    value field is compared, stripped, with the marker strings only.
    """
    lines = text.splitlines()
    titles = [i for i, ln in enumerate(lines) if norm(ln) == SECTION_TITLE]
    if len(titles) != 1:
        return {"error": f"{len(titles)} lines titled '{SECTION_TITLE}' (whitespace-normalised); expected one"}
    t = titles[0]
    preamble = [ln.strip() for ln in lines[:t] if ln.strip()]
    h = t + 1
    while h < len(lines) and not lines[h].strip():
        h += 1
    columns = [c.strip() for c in lines[h].split(",")[1:]]
    months: list[str] = []
    has_value: list[list[bool]] = []
    width_problems: list[str] = []
    for ln in lines[h + 1 :]:
        fields = ln.split(",")
        if not fields or not is_month(fields[0]):
            break
        f0 = fields[0].strip()
        m = f"{f0[:4]}-{f0[4:]}"
        months.append(m)
        vals = fields[1:]
        if len(vals) != len(columns):
            width_problems.append(m)
            has_value.append([False] * len(columns))
            continue
        has_value.append([v.strip() not in MARKERS for v in vals])
    if not months:
        return {"error": "no month rows under the section title"}
    idx = [ym_index(m) for m in months]
    gaps = [f"{ym(a)}..{ym(b)}" for a, b in zip(idx, idx[1:]) if b > a + 1]
    disorder = [f"{ym(a)}->{ym(b)}" for a, b in zip(idx, idx[1:]) if b <= a]
    return {
        "preamble_lines": preamble,
        "section_title_line": lines[t].strip(),
        "column_header": columns,
        "first_month": months[0],
        "last_month": months[-1],
        "rows": len(months),
        "month_gaps": gaps,
        "duplicate_or_out_of_order": disorder,
        "rows_with_wrong_field_count": width_problems,
        "months": months,
        "has_value": has_value,
    }


def eligible_counts(p: dict, F: int, first_rank: str, last_rank: str) -> dict[str, int]:
    """Eligible industries at each ranking month m: a value in every month m-F+1..m (marker flags only)."""
    pos = {m: i for i, m in enumerate(p["months"])}
    out = {}
    for k in range(ym_index(first_rank), ym_index(last_rank) + 1):
        m = ym(k)
        rows = [pos.get(ym(k - j)) for j in range(F)]
        if any(r is None for r in rows):
            out[m] = 0
            continue
        n = len(p["column_header"])
        out[m] = sum(all(p["has_value"][r][c] for r in rows) for c in range(n))
    return out


def main() -> None:
    parse_only = "--parse-only" in sys.argv[1:]
    manifest = json.loads(MANIFEST.read_text()) if parse_only else download()
    blobs = load_verified(manifest)
    stops: list[str] = []
    files: dict[str, dict] = {}
    for name, spec in FILES.items():
        member, text, raw = csv_text(blobs[name])
        manifest["files"][name].update({"csv_member": member, "csv_sha256": sha256(raw), "csv_bytes": len(raw)})
        p = parse_vw_monthly(text)
        if "error" in p:
            stops.append(f"{name}: {p['error']}")
            files[name] = p
            continue
        manifest["files"][name]["preamble_lines"] = p["preamble_lines"]
        files[name] = p
        if len(p["column_header"]) != spec["n"]:
            stops.append(f"{name}: {len(p['column_header'])} industry columns, expected {spec['n']}")
        if p["first_month"] != LIB_START:
            stops.append(f"{name}: value-weighted monthly section starts {p['first_month']}, expected {LIB_START}")
        for k in ("month_gaps", "duplicate_or_out_of_order", "rows_with_wrong_field_count"):
            if p[k]:
                stops.append(f"{name}: {k}: {p[k]}")
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    if any("error" in p for p in files.values()):
        end = None
    else:
        end = min(p["last_month"] for p in files.values())
        if ym_index(end) < ym_index(END_MIN):
            stops.append(f"last common month {end} is before {END_MIN}")

    value_counts: dict[str, dict[str, int]] = {}
    eligibility: dict[str, dict] = {}
    windows: dict[str, dict] = {}
    if end is not None:
        for name, spec in FILES.items():
            p = files[name]
            n = len(p["column_header"])
            below = {m: sum(v) for m, v in zip(p["months"], p["has_value"]) if ym_index(m) <= ym_index(end) and sum(v) < n}
            value_counts[name] = below
            for F in spec["F"]:
                ec = eligible_counts(p, F, FIRST_RANKING[F], ym(ym_index(end) - 1))
                low = {m: c for m, c in ec.items() if c < spec["floor"]}
                below_full = {m: c for m, c in ec.items() if c < n}
                eligibility[f"{name} F={F}"] = {
                    "ranking_months": f"{FIRST_RANKING[F]} to {ym(ym_index(end) - 1)}",
                    "count": len(ec),
                    "min_eligible": min(ec.values()),
                    "months_below_full_set": below_full,
                    "months_below_floor": low,
                }
                if low:
                    stops.append(f"{name} F={F}: eligible count below {spec['floor']} at ranking months {low}")
        for t, spec in TRIALS.items():
            i1 = months_between(spec["first_holding"], I1_END)
            i2 = months_between(I2_START, end)
            windows[t] = {
                "I1": f"{spec['first_holding']} to {I1_END} ({i1})",
                "I2": f"{I2_START} to {end} ({i2})",
                "O": i1 + i2,
                "M": months_between(*M),
                "full": months_between(spec["first_holding"], end),
            }
            assert windows[t]["O"] + windows[t]["M"] == windows[t]["full"]

    stamp = now()
    result = {
        "run_at_utc": stamp,
        "parse_only": parse_only,
        "files": {
            n: {k: v for k, v in p.items() if k not in ("preamble_lines", "months", "has_value")} for n, p in files.items()
        },
        "last_common_month": end,
        "months_with_fewer_values_than_the_set": value_counts,
        "eligibility": eligibility,
        "window_months": windows,
        "stops": stops,
        "outcome": "STOP (§5.4): dated §16 amendment needed before any code runs on returns" if stops else "pass: no §5.4 stop rule met",
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "data_step.json").write_text(json.dumps(result, indent=2) + "\n")

    md = [
        "# Study 011 data step (§14 step 2): dates, column names, counts and missing-value markers only",
        "",
        f"Run {stamp}. Library page read {manifest['library_page']['read_at_utc']}; each file downloaded once "
        "(`data_manifest.json`: URL, time, SHA-256, bytes, header lines). Only the value-weighted monthly section was read, "
        "for dates and column names; each value field was compared as a stripped string with \"-99.99\", \"-999\" and empty, "
        "recording only whether it matched. No field was parsed as a number; no return value was written, printed or summarised; "
        "no other section was read.",
        "",
        "| File | Downloaded (UTC) | Industries | Rows | First month | Last month | Gaps | Duplicate / out of order |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for n, p in files.items():
        if "error" in p:
            md.append(f"| `{n}` | {manifest['files'][n]['downloaded_at_utc']} | error: {p['error']} | | | | | |")
            continue
        md.append(
            f"| `{n}` | {manifest['files'][n]['downloaded_at_utc']} | {len(p['column_header'])}: {', '.join(p['column_header'])} | "
            f"{p['rows']:,} | {p['first_month']} | {p['last_month']} | {len(p['month_gaps'])} | {len(p['duplicate_or_out_of_order'])} |"
        )
    md += ["", "Release lines (file headers, verbatim):", ""]
    for n in FILES:
        for ln in manifest["files"][n].get("preamble_lines", []):
            if "CRSP" in ln or re.search(r"\b20\d{4}\b", ln):
                md.append(f"- `{n}`: {ln}")
    md += ["", f"**Last common month: {end}.**", ""]
    if windows:
        md += ["| Trial | I1 | I2 | O | M | full |", "|---|---|---|---|---|---|"]
        for t, w in windows.items():
            md.append(f"| {t} | {w['I1']} | {w['I2']} | {w['O']:,} | {w['M']:,} | {w['full']:,} |")
        md += ["", "Eligibility at ranking months whose cohort is held (§5.4; marker flags only):", ""]
        for k, v in eligibility.items():
            md.append(
                f"- `{k}`: {v['count']:,} ranking months ({v['ranking_months']}); minimum eligible {v['min_eligible']}; "
                f"months below the full set {len(v['months_below_full_set'])}; below the floor {len(v['months_below_floor'])}"
            )
        md += ["", "Months with fewer industries holding a value than the set (to the last common month):", ""]
        for k, v in value_counts.items():
            md.append(f"- `{k}`: {len(v)} months" + (f" ({', '.join(f'{m}: {c}' for m, c in v.items())})" if v else ""))
    md += ["", f"**Outcome: {result['outcome']}.**"]
    md += [f"- {s}" for s in stops]
    md.append("")
    (OUT / "data_step.md").write_text("\n".join(md))
    print("\n".join(md))
    if stops:
        sys.exit(2)


if __name__ == "__main__":
    main()
