"""Check every relative link in the repository's tracked Markdown files.

A reader clones the repository, so a link counts as working only if its
target is a tracked file or a directory holding tracked files. A link with
an anchor (``file.md#section``) also needs a heading in the target that
GitHub renders with that anchor. External links (http, https, mailto) are
not fetched; they are counted and listed separately.

Usage: python3 tools/check_links.py [--out tools/check_links.txt]
Exit status 1 if any relative link or anchor is broken.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent

# Inline links and images: [text](target) or ![alt](target "title").
LINK_RE = re.compile(r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
HTML_ANCHOR_RE = re.compile(r"<a\s+(?:name|id)=\"([^\"]+)\"", re.IGNORECASE)


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line]


def github_slug(text: str) -> str:
    """GitHub's heading anchor: strip markup, lowercase, drop punctuation, spaces to '-'."""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors_of(path: Path) -> set[str]:
    anchors: set[str] = set()
    seen: Counter[str] = Counter()
    in_fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        anchors.update(a.lower() for a in HTML_ANCHOR_RE.findall(line))
        m = HEADING_RE.match(line)
        if not m:
            continue
        slug = github_slug(m.group(2))
        n = seen[slug]
        seen[slug] += 1
        anchors.add(slug if n == 0 else f"{slug}-{n}")
    return anchors


def links_of(path: Path) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    in_fence = False
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        stripped = re.sub(r"`[^`]*`", "", line)
        found.extend((lineno, m.group(1)) for m in LINK_RE.finditer(stripped))
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    files = tracked_files()
    tracked = set(files)
    dirs = {str(p) for f in files for p in PurePosixPath(f).parents if str(p) != "."}
    md_files = sorted(f for f in files if f.lower().endswith(".md"))
    anchor_cache: dict[str, set[str]] = {}

    relative = external = 0
    broken: list[str] = []
    for md in md_files:
        for lineno, target in links_of(ROOT / md):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
                external += 1
                continue
            relative += 1
            target_path, _, anchor = target.partition("#")
            if target_path:
                resolved = PurePosixPath(md).parent / unquote(target_path)
                parts: list[str] = []
                for part in resolved.parts:
                    if part == "..":
                        if parts:
                            parts.pop()
                        else:
                            parts.append(part)
                    elif part != ".":
                        parts.append(part)
                norm = "/".join(parts).rstrip("/")
            else:
                norm = md
            if norm not in tracked and norm not in dirs:
                broken.append(f"{md}:{lineno}: missing target {target}")
                continue
            if anchor and norm.lower().endswith(".md") and norm in tracked:
                if norm not in anchor_cache:
                    anchor_cache[norm] = anchors_of(ROOT / norm)
                if unquote(anchor).lower() not in anchor_cache[norm]:
                    broken.append(f"{md}:{lineno}: missing anchor #{anchor} in {norm}")

    lines = [
        "Relative-link check of tracked Markdown files (tools/check_links.py)",
        f"Markdown files: {len(md_files)}",
        f"Relative links and anchors checked: {relative}",
        f"External links (not fetched): {external}",
        f"Broken: {len(broken)}",
        *broken,
    ]
    report = "\n".join(lines) + "\n"
    sys.stdout.write(report)
    if args.out:
        (ROOT / args.out).write_text(report, encoding="utf-8")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
