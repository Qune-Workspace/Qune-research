"""Study 006, before §14 step 3: is Study 002's src/ at the current commit the code of a2b713b?

For every module of Study 002's src/, compares the syntax tree at a2b713b (the commit the
pre-registration names) with the working tree, after removing import statements and treating
`timezone.utc` as `UTC` (the two mechanical changes of bddcf44). Reads code only, no data.

Usage: python src_provenance.py  (from this folder, inside the git checkout)
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

BASE = "a2b713b"
SRC = Path("research/002-slope-duration-switch-r/src")
UTC_OLD = "Attribute(value=Name(id='timezone', ctx=Load()), attr='utc', ctx=Load())"
UTC_NEW = "Name(id='UTC', ctx=Load())"


def normalised(source: str) -> str:
    tree = ast.parse(source)
    tree.body = [n for n in tree.body if not isinstance(n, ast.Import | ast.ImportFrom)]
    return ast.dump(tree).replace(UTC_OLD, UTC_NEW)


def main() -> None:
    root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
        ).stdout.strip()
    )
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    print(f"Study 002 src/: {BASE} against the working tree at {head} (imports removed, UTC alias normalised)")
    for path in sorted((root / SRC).glob("*.py")):
        old = subprocess.run(
            ["git", "show", f"{BASE}:{SRC / path.name}"], capture_output=True, text=True, check=True
        ).stdout
        same = normalised(old) == normalised(path.read_text())
        print(f"  {path.name:18s} {'identical' if same else 'DIFFERS'}")


if __name__ == "__main__":
    main()
