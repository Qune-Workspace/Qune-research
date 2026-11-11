"""The desk view's Brier line is held against the record it quotes.

Written on 2026-11-11 after the 6 November view was found to print "baseline
0.046" where the record says 0.045: the line was typed by hand from
predictions/SKILL.md's four-decimal figures (0.0455 rounded again), and nothing
read it back.  The README rule "Brier every week" (2026-10-30) said each view
reports the desk's and the baseline's Brier and the count of scored calls; no
tool or test held the sentence (predictions/POST_MORTEMS.md, "A Brier figure
rounded twice").

What it does: reads predictions/ledger.csv, baselines.csv and outcomes.csv
through their gates (the readers that write SKILL.md), recomputes the summary,
and holds the one line of desk-view/DESK_VIEW.md that carries the lead
"Brier against the market-anchored baseline" to it: the count, and each of the
three figures equal to the record's figure at the decimals the line prints.
`--print` renders the clause to paste into the next view, so the figures are
copied from the tool, never retyped.  Exit 1 with each violation on its own
line, and the clause to carry, when the line is not the record's.

Usage: python tools/check_view_brier.py [--view PATH] [--print] [--selftest]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "predictions"))
import baseline  # noqa: E402

VIEW = ROOT / "desk-view" / "DESK_VIEW.md"

# The record on 2026-11-11 (V1 scored a miss at 0.70 against a baseline of 0.2133).
_SUMMARY = {"scored_with_baseline": 1, "hits": 0, "brier_desk": 0.49,
            "brier_baseline": 0.04549689, "skill_vs_baseline": -0.44450311}
_PUBLISHED_6_NOV = ("Brier against the market-anchored baseline (SKILL.md): 1 scored call; desk 0.490, "
                    "baseline 0.046, skill −0.445; descriptive, not evidence.")
_CLEAN = _PUBLISHED_6_NOV.replace("baseline 0.046", "baseline 0.045")


def selftest() -> int:
    cases: list[tuple[str, str, dict, list[str]]] = [
        # name, text, summary, substrings each expected once among the violations ([] = none)
        ("the 6 November line as published", _PUBLISHED_6_NOV, _SUMMARY, ["baseline: the view prints 0.046"]),
        ("the record's line", _CLEAN, _SUMMARY, []),
        ("an ASCII hyphen for the minus sign", _CLEAN.replace("−", "-"), _SUMMARY, []),
        ("two decimals throughout", _CLEAN.replace("0.490", "0.49").replace("0.045", "0.05").replace("0.445", "0.44"),
         _SUMMARY, []),
        ("a count of two", _CLEAN.replace("1 scored call", "2 scored calls"), _SUMMARY, ["count: the view prints 2"]),
        ("a skill one digit off", _CLEAN.replace("0.445", "0.444"), _SUMMARY, ["skill: the view prints −0.444"]),
        ("mixed decimals", _CLEAN.replace("0.490", "0.49"), _SUMMARY, ["decimals: the three figures"]),
        ("no clause after the lead", "Brier against the market-anchored baseline: see SKILL.md.", _SUMMARY,
         ["does not carry"]),
        ("no line while a call is scored", "A view with no Brier line.", _SUMMARY, ["carries no line"]),
        ("two lines", _CLEAN + "\n" + _CLEAN, _SUMMARY, ["2 lines"]),
        ("figures while nothing is scored", _CLEAN, {"scored_with_baseline": 0}, ["record has no scored call"]),
        ("no line while nothing is scored", "A view with no Brier line.", {"scored_with_baseline": 0}, []),
    ]
    failed = 0
    for name, text, summary, expected in cases:
        got = baseline.view_brier_violations(text, summary)
        ok = len(got) == len(expected) and all(any(e in g for g in got) for e in expected)
        if not ok:
            failed += 1
            print(f"selftest FAIL: {name}: expected {expected}, got {got}")
    clause = baseline.view_brier_clause(_SUMMARY)
    if clause != "1 scored call; desk 0.490, baseline 0.045, skill −0.445":
        failed += 1
        print(f"selftest FAIL: clause rendered {clause!r}")
    if baseline.view_brier_clause({"scored_with_baseline": 0}) != "no scored call with a baseline yet":
        failed += 1
        print("selftest FAIL: the empty clause")
    if failed:
        print(f"selftest: FAIL ({failed} of {len(cases) + 2} cases)")
        return 1
    print(f"selftest: pass ({len(cases) + 2} cases)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--view", type=Path, default=VIEW, help="the view to hold (default desk-view/DESK_VIEW.md)")
    parser.add_argument("--print", action="store_true", dest="print_clause",
                        help="print the clause the view should carry, from the committed records, and exit")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    summary = baseline.record_summary()
    clause = baseline.view_brier_clause(summary)
    if args.print_clause:
        print(clause)
        return 0
    text = args.view.read_text(encoding="utf-8")
    violations = baseline.view_brier_violations(text, summary)
    if not violations:
        print(f"desk view Brier line: ok ({clause}; {args.view.relative_to(ROOT)})")
        return 0
    print(f"desk view Brier line: FAIL ({args.view.relative_to(ROOT)}; fix the page, never the record)")
    for sentence in violations:
        print(f"  {sentence}")
    print(f"  the clause to carry, from the committed records: {clause}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
