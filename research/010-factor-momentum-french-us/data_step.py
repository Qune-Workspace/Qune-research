"""Study 010, §14 step 2: the data step (dates and missing-value markers only).

1. Reads the Kenneth French Data Library's page once and takes the download
   links of the three §5.1 files from it (the expected file names are matched
   against the page's links; a different name stops the step).
2. Downloads each file **once** into ``data/raw/`` (git-ignored) and writes
   ``results/data_manifest.json``: URL, UTC download time, SHA-256 and byte
   size of the zip and of the CSV inside it, and the text lines above the
   monthly column header (they name the CRSP release; they hold no value).
   If the manifest already exists the step refuses to download again
   (§5.2: no second download before the history run); ``--parse-only``
   re-checks the stored files' hashes against the manifest and re-parses.
3. Parses the **monthly section only** (rows whose first field is a six-digit
   YYYYMM) for dates, and compares each value field with the library's
   missing-value codes −99.99 and −999 (and with an empty field), recording
   only whether it matched. No factor value is written, printed or
   summarised; the annual section is not parsed.
4. Applies the §5.4 stop rules and writes ``results/data_step.{json,md}``:
   first and last month, row count, month gaps and marker dates per file and
   column; H's end (last month common to the three files); the month counts
   of H, P1, L, P2 and P; each trial's first holding month per factor
   (fixed by PREREGISTRATION.md §6.2, checked here only for formation
   coverage).

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

import requests

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"
OUT = HERE / "results"
MANIFEST = OUT / "data_manifest.json"

LIBRARY_PAGE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"
UA = {"User-Agent": "qune-research study 010 data step (one download per file)"}

# file name -> (columns used by the study, monthly start stated in QUESTION.md §1)
FILES = {
    "F-F_Research_Data_Factors_CSV.zip": {"used": ["SMB", "HML"], "start": "1926-07"},
    "F-F_ST_Reversal_Factor_CSV.zip": {"used": ["ST_Rev"], "start": "1926-02"},
    "F-F_LT_Reversal_Factor_CSV.zip": {"used": ["LT_Rev"], "start": "1931-01"},
}
# first month a trial uses (formation included), PREREGISTRATION.md §5.4
FIRST_USED = {"SMB": "1926-07", "HML": "1926-07", "ST_Rev": "1926-07", "LT_Rev": "1931-01"}
H_START = "1927-07"
H_END_MIN = "2026-06"
P1 = ("1927-07", "1963-06")
L = ("1963-07", "2015-12")
P2_START = "2016-01"
# PREREGISTRATION.md §6.2: first holding month per factor and formation length
TRIALS = {
    "T1": {"L": 12, "entry": {"SMB": "1927-07", "HML": "1927-07", "ST_Rev": "1927-07", "LT_Rev": "1932-01"}},
    "T1a": {"L": 12, "entry": {"SMB": "1927-07", "HML": "1927-07"}},
    "T1b": {"L": 6, "entry": {"SMB": "1927-07", "HML": "1927-07", "ST_Rev": "1927-07", "LT_Rev": "1931-07"}},
}
MARKERS = (-99.99, -999.0)


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def ym_index(ym: str) -> int:
    y, m = int(ym[:4]), int(ym[5:7])
    return y * 12 + m - 1


def ym(i: int) -> str:
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def months_between(a: str, b: str) -> int:
    """Inclusive count of months from a to b."""
    return ym_index(b) - ym_index(a) + 1


def find_links(html: str) -> dict[str, str]:
    hrefs = re.findall(r'href\s*=\s*"([^"]+)"', html, flags=re.I)
    links = {}
    for name in FILES:
        hits = sorted({h for h in hrefs if h.rsplit("/", 1)[-1] == name})
        if len(hits) != 1:
            raise SystemExit(f"STOP: {len(hits)} links named {name} on the library page; expected exactly one (§5.1)")
        links[name] = requests.compat.urljoin(LIBRARY_PAGE, hits[0])
    return links


def download() -> dict:
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


def parse_monthly(text: str) -> dict:
    """Dates, header text and marker flags of the monthly section. No value leaves this function."""
    lines = text.splitlines()
    first = next(i for i, ln in enumerate(lines) if ln.split(",")[0].strip() and is_month(ln.split(",")[0]))
    header_line = lines[first - 1]
    columns = [c.strip() for c in header_line.split(",")[1:]]
    preamble = [ln.strip() for ln in lines[: first - 1] if ln.strip()]
    months: list[str] = []
    markers: dict[str, list[str]] = {c: [] for c in columns}
    width_problems: list[str] = []
    for ln in lines[first:]:
        fields = ln.split(",")
        if not is_month(fields[0]):
            break
        m = f"{fields[0].strip()[:4]}-{fields[0].strip()[4:]}"
        months.append(m)
        vals = fields[1:]
        if len(vals) != len(columns):
            width_problems.append(m)
            continue
        for c, v in zip(columns, vals):
            s = v.strip()
            try:
                hit = s == "" or float(s) in MARKERS
            except ValueError:
                hit = True  # not a number: treated as missing, its text is not recorded
            if hit:
                markers[c].append(m)
    idx = [ym_index(m) for m in months]
    gaps = [f"{ym(a)}..{ym(b)}" for a, b in zip(idx, idx[1:]) if b != a + 1]
    return {
        "preamble_lines": preamble,
        "column_header": [c for c in columns],
        "first_month": months[0],
        "last_month": months[-1],
        "rows": len(months),
        "month_gaps": gaps,
        "rows_with_wrong_field_count": width_problems,
        "marker_months_by_column": markers,
    }


def main() -> None:
    parse_only = "--parse-only" in sys.argv[1:]
    manifest = json.loads(MANIFEST.read_text()) if parse_only else download()
    blobs = load_verified(manifest)
    stops: list[str] = []
    files: dict[str, dict] = {}
    for name, spec in FILES.items():
        member, text, raw = csv_text(blobs[name])
        manifest["files"][name].update({"csv_member": member, "csv_sha256": sha256(raw), "csv_bytes": len(raw)})
        p = parse_monthly(text)
        manifest["files"][name]["preamble_lines"] = p["preamble_lines"]
        files[name] = p
        for c in spec["used"]:
            if c not in p["column_header"]:
                stops.append(f"{name}: column {c} not in the monthly header {p['column_header']}")
        if p["first_month"] != spec["start"]:
            stops.append(f"{name}: monthly section starts {p['first_month']}, QUESTION.md §1 states {spec['start']}")
        if p["rows_with_wrong_field_count"]:
            stops.append(f"{name}: rows with a wrong field count: {p['rows_with_wrong_field_count']}")
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    h_end = min(p["last_month"] for p in files.values())
    if ym_index(h_end) < ym_index(H_END_MIN):
        stops.append(f"H's end {h_end} is before {H_END_MIN}")
    in_use: dict[str, dict] = {}
    for name, spec in FILES.items():
        p = files[name]
        for c in spec["used"]:
            lo, hi = ym_index(FIRST_USED[c]), ym_index(h_end)
            mk = [m for m in p["marker_months_by_column"].get(c, []) if lo <= ym_index(m) <= hi]
            gp = [g for g in p["month_gaps"] if ym_index(g[:7]) < hi and ym_index(g[9:]) > lo]
            in_use[c] = {"file": name, "months_used": f"{FIRST_USED[c]} to {h_end}", "markers_in_use": mk, "gaps_in_use": gp}
            if mk:
                stops.append(f"{c}: missing-value markers in months used: {mk}")
            if gp:
                stops.append(f"{c}: month gaps in months used: {gp}")

    trials = {}
    for t, spec in TRIALS.items():
        rows = {}
        for c, entry in spec["entry"].items():
            form_start = ym(ym_index(entry) - spec["L"])
            name = next(n for n, s in FILES.items() if c in s["used"])
            covered = ym_index(form_start) >= ym_index(files[name]["first_month"])
            if not covered:
                stops.append(f"{t} {c}: formation for {entry} starts {form_start}, before the file's first month")
            rows[c] = {"first_holding_month": entry, "first_formation_month": form_start, "holding_months_in_H": months_between(entry, h_end)}
        trials[t] = {"formation_months": spec["L"], "factors": rows}

    counts = {
        "H": {"from": H_START, "to": h_end, "months": months_between(H_START, h_end)},
        "P1": {"from": P1[0], "to": P1[1], "months": months_between(*P1)},
        "L": {"from": L[0], "to": L[1], "months": months_between(*L)},
        "P2": {"from": P2_START, "to": h_end, "months": months_between(P2_START, h_end)},
    }
    counts["P"] = {"from": "P1 and P2", "months": counts["P1"]["months"] + counts["P2"]["months"]}
    assert counts["P1"]["months"] + counts["L"]["months"] + counts["P2"]["months"] == counts["H"]["months"]

    stamp = now()
    result = {
        "run_at_utc": stamp,
        "parse_only": parse_only,
        "files": {n: {k: v for k, v in p.items() if k != "preamble_lines"} for n, p in files.items()},
        "last_month_by_file": {n: p["last_month"] for n, p in files.items()},
        "h_end": h_end,
        "window_months": counts,
        "used_columns": in_use,
        "trials": trials,
        "stops": stops,
        "outcome": "STOP (§5.4): dated §16 amendment needed before any code runs on returns" if stops else "pass: no §5.4 stop rule met",
    }
    (OUT / "data_step.json").write_text(json.dumps(result, indent=2) + "\n")

    md = [
        "# Study 010 data step (§14 step 2): dates and missing-value markers only",
        "",
        f"Run {stamp}. Library page read {manifest['library_page']['read_at_utc']}; each file downloaded once "
        "(`data_manifest.json`: URL, time, SHA-256, bytes, header lines). Only dates were read from the monthly "
        "sections, and each value field was compared with −99.99, −999 and empty, recording only whether it matched. "
        "No factor value was written, printed or summarised; the annual sections were not parsed.",
        "",
        "| File | Downloaded (UTC) | Columns | Rows | First month | Last month | Gaps | Marker months (all columns) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for n, p in files.items():
        mk = sum(len(v) for v in p["marker_months_by_column"].values())
        md.append(
            f"| `{n}` | {manifest['files'][n]['downloaded_at_utc']} | {', '.join(p['column_header'])} | {p['rows']:,} | "
            f"{p['first_month']} | {p['last_month']} | {len(p['month_gaps'])} | {mk} |"
        )
    md += ["", "Release lines (file headers, verbatim):", ""]
    for n in FILES:
        for ln in manifest["files"][n]["preamble_lines"]:
            if "CRSP" in ln or re.search(r"\b20\d{4}\b", ln):
                md.append(f"- `{n}`: {ln}")
    md += [
        "",
        f"**H's end (last month common to the three files): {h_end}.**",
        "",
        "| Row | Months | Count |",
        "|---|---|---|",
    ]
    for k, v in counts.items():
        md.append(f"| {k} | {v['from']}{' to ' + v['to'] if 'to' in v else ''} | {v['months']:,} |")
    md += ["", "| Trial | Factor | First formation month | First holding month | Holding months in H |", "|---|---|---|---|---|"]
    for t, v in trials.items():
        for c, r in v["factors"].items():
            md.append(f"| {t} | {c} | {r['first_formation_month']} | {r['first_holding_month']} | {r['holding_months_in_H']:,} |")
    md += ["", "Columns used, months the trials use: markers and gaps", ""]
    for c, v in in_use.items():
        md.append(f"- {c} ({v['months_used']}): markers {v['markers_in_use'] or 'none'}; gaps {v['gaps_in_use'] or 'none'}")
    md += ["", f"**Outcome: {result['outcome']}.**"]
    md += [f"- {s}" for s in stops]
    md.append("")
    (OUT / "data_step.md").write_text("\n".join(md))
    print("\n".join(md))
    if stops:
        sys.exit(2)


if __name__ == "__main__":
    main()
