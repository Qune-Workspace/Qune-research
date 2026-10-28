"""Check that every number in the front page's "Results at a glance" table
appears in its own study's folder.

A reader who sees a figure on the front page should find the same figure,
written the same way, in the study's committed files. For each table row the
script takes the study folder from the row's link, extracts every number in
the row's cells (minus signs normalised, thousands separators kept), and
searches the git-tracked notes and result files of that folder (.md, .txt,
.json) for the same token, bounded so that 0.45 does not match 0.455. Data
tables (.csv) and code are left out: on the first run they let a planted
0.93 pass on a monthly return in Study 011's industry file (BUILD_LOG,
2026-10-28).

Rule fixed before the first run: a row passes when every number with a
decimal point, a thousands separator or a % sign is found. Bare integers
(years, month counts, trial counts) are searched and reported but do not
decide the result, because a short integer matches almost any folder.
A number not found is a reader-path fault until a person shows where it
comes from; the script never decides that a figure is right, only that the
front page and the study folder say the same thing.

Extension, 2026-10-28 12:2xZ (rule fixed before its first run): the same
test now also covers the front page's prose result sections, every "## Latest
result" and "## Previous result" section. Such a section is about one study;
its folder is taken from the first `research/NNN-...` link in the section, and
every number in the whole section (heading included, link targets stripped) is
searched in that folder exactly as for a table row, with the same decisive
rule. A section with no study link is a failure. "What the desk knows" is not
covered: it cites many studies at once, so no single folder can be searched.

Extension, 2026-10-28 13:2xZ (rule fixed before its first run): "What the
desk knows" is now covered point by point. Each numbered point (and the
closing paragraph, as one more unit) is searched in the union of (a) the
folders of every study it names by its three-digit id ("Study 011",
"Studies 003 and 004"; a range "006–008" names every id in it; an id with no
folder, such as the planned 012, adds nothing) and (b) every tracked file or
folder it links to (in-page #anchors add nothing). Study ids themselves are
not counted as numbers. Same decisive rule; a unit with a decisive number and
an empty corpus fails. Limit, stated: the union is wider than one folder, so a
figure attributed to the wrong study inside the same point still passes.

Usage: python3 tools/check_glance.py [--readme README.md] [--out tools/check_glance.txt]
Exit status 1 if any decisive number is not found.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT_SUFFIXES = {".md", ".txt", ".json"}
ROW_LINK_RE = re.compile(r"^\|\s*\[(\d{3})\]\((research/[^/)]+)/")
# A number: optional sign, digits with optional thousands groups, optional decimals, optional %.
NUM_RE = re.compile(r"(?<![\w.])[+\-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|(?<![\w.,])[+\-]?\d+(?:\.\d+)?%?")
MINUS = "−"


def normalise(text: str) -> str:
    return text.replace(MINUS, "-").replace("–", " - ")


def tracked_files(folder: str) -> list[Path]:
    out = subprocess.run(["git", "ls-files", "--", folder], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    return [ROOT / line for line in out.splitlines() if Path(line).suffix in TEXT_SUFFIXES]


def glance_rows(readme: str) -> list[tuple[str, str, str]]:
    """(study id, folder, row text) for every row of the 'Results at a glance' table."""
    rows: list[tuple[str, str, str]] = []
    in_section = False
    for line in readme.splitlines():
        if line.startswith("## "):
            in_section = line.strip() == "## Results at a glance"
            continue
        if in_section:
            m = ROW_LINK_RE.match(line)
            if m:
                rows.append((m.group(1), m.group(2), line))
    return rows


SECTION_PREFIXES = ("## Latest result", "## Previous result")
SECTION_LINK_RE = re.compile(r"\]\((research/\d{3}-[^/)#]+)")


def result_sections(readme: str) -> list[tuple[str, str | None, str]]:
    """(label, folder or None, section text) for every Latest/Previous result section."""
    sections: list[tuple[str, str | None, str]] = []
    current: list[str] | None = None
    for line in readme.splitlines() + ["## end"]:
        if line.startswith("## "):
            if current is not None:
                text = "\n".join(current)
                m = SECTION_LINK_RE.search(text)
                folder = m.group(1) if m else None
                label = current[0][3:].split(":")[0].strip() + (f" ({folder.split('/')[1][:3]})" if folder else "")
                sections.append((label, folder, text))
            current = [line] if line.startswith(SECTION_PREFIXES) else None
            continue
        if current is not None:
            current.append(line)
    return sections


DESK_HEADING = "## What the desk knows"
STUDY_ID_RE = re.compile(r"(?<![\w.,/])(0\d{2})(?:\s*[–-]\s*(0\d{2}))?(?![\w.%]|,\d)")
FILE_LINK_RE = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def desk_units(readme: str) -> list[tuple[str, str]]:
    """(label, text) for each numbered point of 'What the desk knows' plus its closing paragraph."""
    units: list[tuple[str, list[str]]] = []
    in_section = False
    prev_blank = False
    for line in readme.splitlines():
        if line.startswith("## "):
            in_section = line.startswith(DESK_HEADING)
            continue
        if not in_section:
            continue
        m = re.match(r"^(\d+)\. ", line)
        if m:
            units.append((f"desk point {m.group(1)}", [line]))
        elif line.strip() and prev_blank and units and not line.startswith(" "):
            units.append(("desk closing", [line]))
        elif units and line.strip():
            units[-1][1].append(line)
        prev_blank = not line.strip()
    return [(label, "\n".join(text)) for label, text in units]


def desk_sources(text: str, folders: dict[str, str]) -> list[str]:
    ids: set[str] = set()
    for m in STUDY_ID_RE.finditer(text):
        lo = int(m.group(1))
        hi = int(m.group(2)) if m.group(2) else lo
        ids.update(f"{i:03d}" for i in range(lo, hi + 1))
    sources = [folders[i] for i in sorted(ids) if i in folders]
    sources += [t for t in FILE_LINK_RE.findall(text) if not t.startswith(("http://", "https://"))]
    return sources


def strip_study_ids(text: str) -> str:
    return STUDY_ID_RE.sub(" ", text)


def numbers_in_text(text: str) -> list[str]:
    body = re.sub(r"\]\([^)]*\)", "]", text)
    return [m.group(0) for m in NUM_RE.finditer(normalise(body))]


def numbers_in(row: str) -> list[str]:
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    # Drop the study id cell (its link would match itself) and strip link targets.
    body = " | ".join(re.sub(r"\]\([^)]*\)", "]", c) for c in cells[1:])
    return [m.group(0) for m in NUM_RE.finditer(normalise(body))]


def decisive(token: str) -> bool:
    return "." in token or "," in token or token.endswith("%")


def found(token: str, corpus: str) -> bool:
    core = token.lstrip("+")
    # The bare value with the same bounds; a leading sign in the corpus is allowed.
    pattern = r"(?<![\d.,])" + re.escape(core.lstrip("-")) + r"(?![\d]|\.\d|,\d{3})"
    if core.startswith("-"):
        pattern = r"-\s?" + pattern
    return re.search(pattern, corpus) is not None


def check(readme_path: Path) -> tuple[list[str], int]:
    lines: list[str] = []
    failures = 0
    rows = glance_rows(readme_path.read_text(encoding="utf-8"))
    if not rows:
        return ["no 'Results at a glance' rows found"], 1
    total_dec = total_int = 0
    units: list[tuple[str, str | None, list[str]]] = [(study, folder, numbers_in(row)) for study, folder, row in rows]
    sections = result_sections(readme_path.read_text(encoding="utf-8"))
    units += [(label, folder, numbers_in_text(text)) for label, folder, text in sections]
    folders = {p.name[:3]: f"research/{p.name}" for p in (ROOT / "research").iterdir() if p.is_dir()}
    desk = desk_units(readme_path.read_text(encoding="utf-8"))
    if not desk:
        return ["no 'What the desk knows' points found"], 1
    desk_corpus: dict[str, list[str]] = {}
    for label, text in desk:
        desk_corpus[label] = desk_sources(text, folders)
        units.append((label, " + ".join(desk_corpus[label]) or None, numbers_in_text(strip_study_ids(text))))
    for study, folder, tokens in units:
        if folder is None:
            if study.startswith("desk") and not any(decisive(t) for t in tokens):
                lines.append(f"{study} pass: no decisive numbers, no sources named")
                continue
            failures += 1
            lines.append(f"{study} FAIL: no research/NNN-... link in the section")
            continue
        files = [f for src in (desk_corpus[study] if study in desk_corpus else [folder]) for f in tracked_files(src)]
        corpus = "\n".join(normalise(p.read_text(encoding="utf-8", errors="replace")) for p in files)
        missing_dec = [t for t in tokens if decisive(t) and not found(t, corpus)]
        missing_int = [t for t in tokens if not decisive(t) and not found(t, corpus)]
        n_dec = sum(decisive(t) for t in tokens)
        n_int = len(tokens) - n_dec
        total_dec += n_dec
        total_int += n_int
        failures += len(missing_dec)
        status = "pass" if not missing_dec else "FAIL"
        lines.append(
            f"{study} {status}: {n_dec - len(missing_dec)}/{n_dec} decisive numbers found, "
            f"{n_int - len(missing_int)}/{n_int} integers found, {len(files)} files in {folder}"
        )
        if missing_dec:
            lines.append(f"    not found (decisive): {', '.join(missing_dec)}")
        if missing_int:
            lines.append(f"    not found (integer, reported only): {', '.join(missing_int)}")
    lines.insert(
        0,
        f"rows {len(rows)}, prose result sections {len(sections)}, desk units {len(desk)}; decisive numbers {total_dec}, not found {failures}; integers {total_int}",
    )
    return lines, failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--readme", default=str(ROOT / "README.md"))
    ap.add_argument("--out")
    args = ap.parse_args()
    lines, failures = check(Path(args.readme))
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
