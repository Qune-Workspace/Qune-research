#!/usr/bin/env python3
"""Check every DOI cited in a Markdown file against Crossref.

Usage: python3 tools/check_citations.py RESEARCH_AGENDA.md [--out tools/citations_check.txt]

Reads citation lines of the form

    - [KEY] Family, ... (YEAR). Title. Journal. doi:10.xxxx/yyyy

from the file, asks Crossref for each DOI (no key needed; standard library only)
and reports, per DOI: resolved or not, the registered first author's family
name, the registered year and title, and whether the year and first author in
the Markdown match the registry. Exit status 1 if any DOI fails to resolve or
any year/author mismatches, so the check can run in CI.

Crossref titles are compared loosely (case-insensitive prefix of 25 chars) and
reported in full; years are allowed to differ by one (print vs online issue).
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request

UA = "qune-research citation check (public research repository; standard-library client)"
LINE = re.compile(r"^\s*-\s*\[(?P<key>[^\]]+)\]\s*(?P<authors>[^(]+?)\s*\((?P<year>\d{4})[a-z]?\)\.\s*(?P<title>.+?)\.\s.*?doi:(?P<doi>10\.\S+?)\s*$")


def crossref(doi):
    req = urllib.request.Request("https://api.crossref.org/works/" + doi, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)["message"]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = None
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    if not args:
        print(__doc__)
        return 2
    rows, bad = [], 0
    for line in open(args[0], encoding="utf-8"):
        m = LINE.match(line)
        if not m:
            continue
        key, doi = m["key"], m["doi"].rstrip(".,)")
        first = re.split(r"[,&]| and ", m["authors"])[0].strip().split()[-1]
        msg = crossref(doi)
        if msg is None:
            rows.append((key, doi, "NOT RESOLVED", "", "", ""))
            bad += 1
            continue
        reg_year = (msg.get("issued", {}).get("date-parts") or [[None]])[0][0]
        reg_first = (msg.get("author") or [{}])[0].get("family", "")
        reg_title = re.sub(r"\s+", " ", (msg.get("title") or [""])[0]).strip()
        venue = (msg.get("container-title") or [""])[0]
        ok_year = reg_year is not None and abs(int(m["year"]) - int(reg_year)) <= 1
        ok_auth = reg_first.lower() == first.lower()
        ok_title = reg_title[:25].lower() == m["title"][:25].lower()
        status = "ok" if (ok_year and ok_auth) else "MISMATCH"
        if not ok_title:
            status += " (title differs: see registered title)"
        if status.startswith("MISMATCH"):
            bad += 1
        rows.append((key, doi, status, f"{reg_first} ({reg_year})", reg_title, venue))
    lines = [f"Citation check of {args[0]}: {len(rows)} DOIs, {len(rows) - bad} ok, {bad} problems. Checked {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}", ""]
    for key, doi, status, reg, title, venue in rows:
        lines.append(f"[{key}] doi:{doi} -> {status} | registered: {reg} | {title} | {venue}")
    text = "\n".join(lines) + "\n"
    print(text)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
