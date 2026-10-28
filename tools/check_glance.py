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
    for study, folder, row in rows:
        files = tracked_files(folder)
        corpus = "\n".join(normalise(p.read_text(encoding="utf-8", errors="replace")) for p in files)
        tokens = numbers_in(row)
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
        f"rows {len(rows)}; decisive numbers {total_dec}, not found {failures}; integers {total_int}",
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
