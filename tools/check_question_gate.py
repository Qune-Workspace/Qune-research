"""The question gate: four statements a study must make before its question
is fixed, checked on the committed files.

Written on 2026-10-31 from the post-mortem of the programme's first eleven
studies (research/POST_MORTEMS.md): eight of the eleven verdicts could not
have seen an edge of the size that plausibly survives publication, three
studies re-ran one mined sample, two never reached a rule, and the files of
six were computed from data the repository may not publish. The lesson is
not "no edge": it is that most of the questions were not able to find one.

Rule, fixed before the first run. Every study folder research/NNN-* with
NNN >= 012 must hold a QUESTION.md with a section headed "## Question gate"
that contains these four labelled lines, each starting a line, in any order:

  Power ratio: <number>  the minimum detectable effect of the decision test
      at 80% power, divided by the source paper's published effect, in the
      same units (Sharpe of d, or % a year). At most 0.50 for the question
      to run as a test; between 0.50 and 1.00 it runs only as a labelled
      low-power check and the line must also contain the words
      "low-power check"; above 1.00 the question is not run and the folder
      must not exist. The line names the tools/power_*.txt file the number
      comes from.
  Persistence: <text>    why the edge should still exist in the decision
      sample after publication (a premium that must be paid, a constraint
      that persists, a bias with documented survival), and the mechanism by
      which the rule would fail against its exposure-matched benchmark.
      "The paper found it" is not a reason; the line must be at least 120
      characters.
  Data terms: <text>     the source's terms, read on a stated date, on
      publishing the derived series or the statistics; or which files will
      be withheld and how a reader regenerates them. Must contain "read on".
  Unmined: <text>        the months the decision test scores were read
      neither by the source paper nor by an earlier study of this programme
      on the same rule family; or the test is labelled a replication.

A PREREGISTRATION.md in such a folder without a passing QUESTION.md is a
failure: the gate comes before the pre-registration. Studies 001 to 011 were
fixed before the gate existed and are reported as exempt, not checked; the
post-mortem says which of the four each would have met.

The script never decides that a question is good, only that the four
statements are on the record before anything was computed. Exit 1 on any
failure. `--selftest` builds a passing and a failing folder in a temporary
directory and checks the verdicts; it reads nothing in the repository.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

GATE_FROM = 12  # first study number the gate applies to (Study 012)
TEST_RATIO = 0.50  # at most this: runs as a test
CHECK_RATIO = 1.00  # at most this: runs as a labelled low-power check
MIN_PERSISTENCE_CHARS = 120
LABELS = ("Power ratio", "Persistence", "Data terms", "Unmined")

FOLDER_RE = re.compile(r"^(\d{3})-")
NUMBER_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])")


def study_number(folder: Path) -> int | None:
    m = FOLDER_RE.match(folder.name)
    return int(m.group(1)) if m else None


def gate_section(text: str) -> str | None:
    """The text under '## Question gate' up to the next '## ' heading."""
    m = re.search(r"^## Question gate[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else None


def labelled_lines(section: str) -> dict[str, str]:
    """Each label's text, with wrapped continuation lines joined (a blank
    line, a new label or a new list item ends the statement)."""
    out: dict[str, str] = {}
    current: str | None = None
    for line in section.splitlines():
        stripped = line.strip()
        is_item = stripped.startswith(("-", "*"))
        body = stripped.lstrip("-* ").strip()
        label_here = next((lb for lb in LABELS if body.startswith(lb + ":")), None)
        if label_here is not None:
            current = label_here if label_here not in out else None
            if current is not None:
                out[current] = body[len(current) + 1 :].strip()
        elif not stripped or is_item:
            current = None
        elif current is not None:
            out[current] = (out[current] + " " + stripped).strip()
    return out


def check_folder(folder: Path) -> list[str]:
    """Return the list of failures for one study folder (empty = pass)."""
    failures: list[str] = []
    question = folder / "QUESTION.md"
    prereg = folder / "PREREGISTRATION.md"
    if not question.exists():
        failures.append("no QUESTION.md")
        if prereg.exists():
            failures.append("PREREGISTRATION.md exists without a QUESTION.md")
        return failures
    section = gate_section(question.read_text(encoding="utf-8"))
    if section is None:
        failures.append("QUESTION.md has no '## Question gate' section")
        return failures
    lines = labelled_lines(section)
    for label in LABELS:
        if label not in lines or not lines[label]:
            failures.append(f"'{label}:' line missing or empty")
    if failures:
        return failures

    power = lines["Power ratio"]
    nums = NUMBER_RE.findall(power)
    if not nums:
        failures.append("'Power ratio:' has no number")
    else:
        ratio = float(nums[0])
        if ratio > CHECK_RATIO:
            failures.append(f"power ratio {ratio} above {CHECK_RATIO}: the question is not run")
        elif ratio > TEST_RATIO and "low-power check" not in power:
            failures.append(
                f"power ratio {ratio} above {TEST_RATIO}: the line must say 'low-power check'"
            )
    if "tools/power_" not in power:
        failures.append("'Power ratio:' names no tools/power_*.txt file")

    if len(lines["Persistence"]) < MIN_PERSISTENCE_CHARS:
        failures.append(
            f"'Persistence:' is {len(lines['Persistence'])} characters; at least {MIN_PERSISTENCE_CHARS} needed"
        )
    if "read on" not in lines["Data terms"]:
        failures.append("'Data terms:' does not say when the terms were read ('read on <date>')")
    if "replication" not in lines["Unmined"] and len(lines["Unmined"]) < 40:
        failures.append("'Unmined:' names neither the unread months nor a replication label")
    return failures


def run(research_dir: Path) -> int:
    folders = sorted(p for p in research_dir.iterdir() if p.is_dir() and study_number(p) is not None)
    exit_code = 0
    print(f"question gate: {research_dir} ({len(folders)} study folders)")
    for folder in folders:
        n = study_number(folder)
        assert n is not None
        if n < GATE_FROM:
            print(f"  {folder.name}: exempt (fixed before the gate, 2026-10-31)")
            continue
        failures = check_folder(folder)
        if failures:
            exit_code = 1
            print(f"  {folder.name}: FAIL")
            for f in failures:
                print(f"    - {f}")
        else:
            print(f"  {folder.name}: pass")
    print("question gate: " + ("FAIL" if exit_code else "pass"))
    return exit_code


PASSING = """# Study 099: question note

## 1. The question

Text.

## Question gate

- Power ratio: 0.42 of the published Sharpe (MDE 0.21 against 0.50), from tools/power_example.txt.
- Persistence: the premium compensates a constraint on intermediaries that has not eased since
  publication (source read); the rule fails against its exposure-matched benchmark if the gain is
  only the average long position, which the benchmark holds.
- Data terms: the library's terms, read on 2026-10-31, allow redistribution with attribution.
- Unmined: 1927-07 to 1963-06, 432 months before the paper's sample, never used by this programme.

## 3. Next

Text.
"""

CHECK_ONLY = PASSING.replace(
    "Power ratio: 0.42 of the published Sharpe",
    "Power ratio: 0.77 of the published Sharpe, so a labelled low-power check",
)

FAILING = PASSING.replace("read on 2026-10-31", "read some time ago").replace(
    "Power ratio: 0.42", "Power ratio: 1.30"
)


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "research"
        cases = {
            "012-pass": PASSING,
            "013-check": CHECK_ONLY,
            "014-fail": FAILING,
            "015-nogate": "# Study 015\n\n## 1. Question\n\ntext\n",
            "011-exempt": "",
        }
        for name, text in cases.items():
            d = root / name
            d.mkdir(parents=True)
            (d / "QUESTION.md").write_text(text, encoding="utf-8")
        (root / "016-prereg-only").mkdir()
        (root / "016-prereg-only" / "PREREGISTRATION.md").write_text("# pre\n", encoding="utf-8")
        (root / "017-short-ratio").mkdir()
        (root / "017-short-ratio" / "QUESTION.md").write_text(
            PASSING.replace("so a labelled low-power check", "").replace("Power ratio: 0.42", "Power ratio: 0.80"),
            encoding="utf-8",
        )

        results = {
            "012-pass": check_folder(root / "012-pass"),
            "013-check": check_folder(root / "013-check"),
            "014-fail": check_folder(root / "014-fail"),
            "015-nogate": check_folder(root / "015-nogate"),
            "016-prereg-only": check_folder(root / "016-prereg-only"),
            "017-short-ratio": check_folder(root / "017-short-ratio"),
        }
        expect_pass = {"012-pass", "013-check"}
        ok = True
        for name, failures in results.items():
            should_pass = name in expect_pass
            if bool(failures) == should_pass:
                ok = False
                print(f"selftest: {name} unexpected: {failures or 'pass'}")
        if "above 1.0" not in " ".join(results["014-fail"]):
            ok = False
            print("selftest: 014-fail did not fail on the ratio")
        if "read on" not in " ".join(results["014-fail"]):
            ok = False
            print("selftest: 014-fail did not fail on the data terms")
        if "PREREGISTRATION.md exists" not in " ".join(results["016-prereg-only"]):
            ok = False
            print("selftest: 016 did not fail on the pre-registration without a question")
        if "low-power check" not in " ".join(results["017-short-ratio"]):
            ok = False
            print("selftest: 017 did not fail on the missing low-power label")
        if run(root) != 1:
            ok = False
            print("selftest: run() over the fixture did not exit 1")
        print("selftest: " + ("pass" if ok else "FAIL"))
        return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--research", default=str(Path(__file__).resolve().parent.parent / "research"))
    ap.add_argument("--selftest", action="store_true", help="check the rule on a built fixture, read nothing")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    return run(Path(args.research))


if __name__ == "__main__":
    sys.exit(main())
