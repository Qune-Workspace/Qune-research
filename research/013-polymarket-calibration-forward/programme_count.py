"""Study 013 programme-wide trial re-count (PREREGISTRATION.md §9.4, §14 step 7).

Counts every row of the registered-trials table (the table whose header starts
"| ID |") in each ``research/*/trials.md``, and every row of the desk's private
registry (JSON lines) when its path is given. Writes
``results/programme_count.json``. The count has no decision weight: C3 is
decided at N = 3 (a Bonferroni bar, t_cl >= 2.128). No price and no outcome is
read. Adapted from Study 011's programme_count.py.

    python programme_count.py --desk-registry /path/to/trials.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
FAMILY_PATTERN = r"polymarket|kalshi|prediction|calibrat|favou?rite|longshot|brier"


def registered_rows(trials_md: Path) -> list[str]:
    """Trial IDs in the first table whose header row starts with '| ID |'."""
    ids: list[str] = []
    in_table = False
    for line in trials_md.read_text(encoding="utf-8").splitlines():
        if line.startswith("| ID |"):
            if in_table or ids:
                raise SystemExit(f"{trials_md}: more than one '| ID |' table")
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                in_table = False
                continue
            cell = line.split("|")[1].strip()
            if set(cell) <= set("-: "):
                continue  # separator row
            ids.append(cell)
    if not ids:
        raise SystemExit(f"{trials_md}: no registered-trials table found")
    return ids


def count_public(research: Path = RESEARCH) -> dict[str, list[str]]:
    return {p.parent.name: registered_rows(p) for p in sorted(research.glob("*/trials.md"))}


def count_desk(path: Path) -> dict:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    corrections = sum(1 for r in rows if r.get("corrects") not in (None, "", "None"))
    pat = re.compile(FAMILY_PATTERN, re.I)
    hits = sum(1 for r in rows if pat.search(json.dumps(r)))
    return {"rows": len(rows), "correction_rows": corrections, "family_keyword_hits": hits}


def build(public: dict[str, list[str]], desk: dict) -> dict:
    n_public = sum(len(v) for v in public.values())
    return {
        "counted_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "public_trials_md": n_public,
        "with_desk_registry": n_public + desk["rows"],
        "public_by_study": {k: len(v) for k, v in public.items()},
        "public_ids_by_study": public,
        "desk_registry": desk,
        "family_keyword_pattern": FAMILY_PATTERN,
        "method": (
            "Every row of the registered-trials table (header '| ID |') in each research/*/trials.md, "
            "counted as written: rows never run and rows carried over from another study are all counted, so the "
            "figure is an upper bound on distinct rules. with_desk_registry adds every row of the desk's private "
            "registry (JSON lines), declaration and correction rows included, also an upper bound; that part cannot "
            "be checked by a reader. A case-insensitive search of every desk row for the family pattern finds "
            "whether any desk trial touched prediction markets or calibration. No decision weight: C3 is decided at N = 3 (§9.4)."
        ),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--desk-registry", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=HERE / "results" / "programme_count.json")
    args = ap.parse_args(argv)
    out = build(count_public(), count_desk(args.desk_registry))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("public_trials_md", "with_desk_registry", "public_by_study", "desk_registry")}, indent=2))


if __name__ == "__main__":
    main()
