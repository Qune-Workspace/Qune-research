"""The bill reading's fetch manifest is held to the repository's own history.

Written on 2026-11-16 (00:15Z run) after the chain built over 14 and 15 November
(row -> candidate -> kept folder -> manifest entry) was found to end at an entry
nothing held: on 5f46891, on a scratch copy of the kept 13 November folder, a
copy with its DTB3 prints moved by -0.60 and four manifest entries written by
hand to its bytes was read by default by `fomc_calibrate.py --live` (0.000 for
the hike where the recorded bytes read 1.000), its candidate was written, and
`--recompute` found the figures reproduced with rc 0 (predictions/POST_MORTEMS.md,
"A manifest held by nothing but the hand that wrote it").

Nothing on this host can hold the manifest against the host's own writer; what
can is the history outside the writer's reach, the pushed commits.  This check
makes that anchor explicit.  It reads every commit of
pm-view/data/fred_rates_manifest.json and the working tree, and refuses when:

- a folder-keyed entry (`<fetch folder>/<file>`) that was once committed is
  changed in a later commit or in the working tree, in any field, or removed:
  the manifest is append-only;
- an entry's folder name is not a UTC fetch time, or its `downloaded_at_utc` is
  not within ten minutes after that time: the entry does not describe the fetch
  it is filed under;
- the commit that first carries an entry's hash, under any key, is dated before
  the fetch it names (a fetch recorded before it happened) or more than 24 hours
  after it (a hash that arrived long after the fetch: by hand, or a run that
  broke the commit-before-long-fetches rule); an uncommitted entry is held to
  the clock the same way.  The hash, not the key, is what the history witnesses:
  the 13 November fetch was committed under file-name keys 14 minutes after it
  and re-keyed under its folder 36 hours later (6b7a0b4), and the 5 and 6
  November `bytes_kept: false` restorations carry hashes bec16ab and e074791
  committed within seven minutes of their fetches.  A `bytes_kept: false` entry
  must also carry a `note` saying where its hash came from;
- the manifest has no folder-keyed entry (an empty universe is a refusal, never
  a pass), or the clone is shallow and the history cannot be read.

What it cannot hold: an entry written by hand and committed within a day of a
folder named for that same day.  The check closes the gap between an entry and
the commit that carries it; the commit, once pushed, is the record.

Usage: python tools/check_manifest_history.py [--root PATH] [--manifest RELPATH] [--selftest]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "pm-view/data/fred_rates_manifest.json"
FOLDER_FORMAT = "%Y-%m-%dT%H%M%SZ"
STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
MAX_DELAY = timedelta(hours=24)
MAX_DOWNLOAD_SPAN = timedelta(minutes=10)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def _folder_keyed(manifest: dict) -> dict:
    return {k: v for k, v in manifest.items() if "/" in k}


def _changed_fields(a: dict, b: dict) -> list[str]:
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def _hours(delta: timedelta) -> str:
    return f"{delta.total_seconds() / 3600:.1f} h"


def manifest_history_violations(root: Path, rel: str = MANIFEST, now: datetime | None = None) -> tuple[list[str], str]:
    """Why the manifest at `root/rel` is not an honest, append-only record of its fetches, and a
    one-line summary of what was held when it is."""
    now = now or datetime.now(UTC)
    out: list[str] = []
    if _git(root, "rev-parse", "--is-shallow-repository").strip() == "true":
        return [f"{rel}: shallow clone, the history cannot be read (check out with fetch-depth 0)"], ""
    log = _git(root, "log", "--format=%H %cI", "--reverse", "--", rel).split("\n")
    commits = [(h, datetime.fromisoformat(d)) for h, _, d in (ln.partition(" ") for ln in log if ln)]
    states: list[tuple[str, datetime, dict]] = []
    for h, d in commits:
        states.append((h[:7], d, json.loads(_git(root, "show", f"{h}:{rel}"))))
    path = root / rel
    if path.exists():
        states.append(("working tree", now, json.loads(path.read_text(encoding="utf-8"))))
    if not states:
        return [f"{rel}: no manifest in the tree or the history"], ""
    # The hash is what the history witnesses: the first commit carrying an entry's sha256 under any key
    # (a fetch that returns the same bytes as an earlier one files an older hash, as the 6 November DFEDTARU
    # and EFFR entries do).  The key's own first commit holds the entry to not predating the fetch it names.
    hash_first_seen: dict[str, tuple[str, datetime]] = {}
    key_first_seen: dict[str, tuple[str, datetime]] = {}
    prev: dict = {}
    for label, d, full in states:
        cur = _folder_keyed(full)
        for key in prev:
            if key not in cur:
                out.append(f"{key}: removed in {label} ({d.isoformat()}); the manifest is append-only")
            elif cur[key] != prev[key]:
                out.append(f"{key}: rewritten in {label} ({d.isoformat()}): {', '.join(_changed_fields(prev[key], cur[key]))}; "
                           "the manifest is append-only")
        for key in cur:
            key_first_seen.setdefault(key, (label, d))
        for entry in full.values():
            if isinstance(entry, dict) and entry.get("sha256"):
                hash_first_seen.setdefault(str(entry["sha256"]), (label, d))
        prev = cur
    final = _folder_keyed(states[-1][2])
    if not final:
        out.append(f"{rel}: no folder-keyed entry (`<fetch folder>/<file>`): nothing to hold")
        return out, ""
    newest = ""
    for key, entry in sorted(final.items()):
        folder = key.split("/", 1)[0]
        try:
            fetched = datetime.strptime(folder, FOLDER_FORMAT).replace(tzinfo=UTC)
        except ValueError:
            out.append(f"{key}: the folder name is not a UTC fetch time ({FOLDER_FORMAT})")
            continue
        try:
            downloaded = datetime.strptime(str(entry.get("downloaded_at_utc", "")), STAMP_FORMAT).replace(tzinfo=UTC)
        except ValueError:
            out.append(f"{key}: downloaded_at_utc {entry.get('downloaded_at_utc')!r} is not a UTC stamp ({STAMP_FORMAT})")
            continue
        if not fetched <= downloaded <= fetched + MAX_DOWNLOAD_SPAN:
            out.append(f"{key}: downloaded_at_utc {entry['downloaded_at_utc']} is not within ten minutes after the "
                       f"folder's time {folder}")
        if entry.get("bytes_kept") is False and not str(entry.get("note", "")).strip():
            out.append(f"{key}: bytes_kept is false and no note says where the hash came from")
        if not entry.get("sha256"):
            out.append(f"{key}: no sha256: nothing for the history to witness")
            continue
        key_label, key_carried = key_first_seen[key]
        label, carried = hash_first_seen[str(entry["sha256"])]
        if key_carried < fetched:
            out.append(f"{key}: first carried by {key_label} at {key_carried.isoformat()}, before the fetch it names ({folder})")
        elif carried - fetched > MAX_DELAY:
            out.append(f"{key}: its hash was first carried by {label} at {carried.isoformat()}, {_hours(carried - fetched)} "
                       f"after the fetch it names ({folder}); the limit is {_hours(MAX_DELAY)}")
        else:
            newest = f"newest {folder}, filed by {key_label}, its hashes carried since {label} ({carried.isoformat()})"
    folders = {k.split('/', 1)[0] for k in final}
    summary = (f"{len(final)} entries over {len(folders)} fetch folders, {len(commits)} commits since "
               f"{commits[0][1].date().isoformat() if commits else 'none'}; {newest or 'no entry under the 24 h rule'}")
    return out, summary


# --- self-test -------------------------------------------------------------------------------------

_ENTRY = {"downloaded_at_utc": "2026-11-13T06:18:42Z", "first_bar": "2008-12-16", "last_bar": "2026-11-12",
          "rows": 6541, "series_id": "DFEDTARU", "sha256": "5306d0dd" * 8, "source": "FRED (fredgraph.csv)",
          "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFEDTARU"}


def _entry(folder: str, downloaded: str, **fields: object) -> dict:
    return dict(_ENTRY, downloaded_at_utc=downloaded, **fields)


def _repo(tmp: Path, name: str) -> Path:
    root = tmp / name
    root.mkdir()
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    for k, v in (("user.name", "selftest"), ("user.email", "selftest@example.invalid"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(root), "config", k, v], check=True)
    return root


def _commit(root: Path, manifest: dict, when: str) -> None:
    path = root / MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    subprocess.run(["git", "-C", str(root), "add", MANIFEST], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", f"manifest at {when}"], check=True, env=env)


def _write(root: Path, manifest: dict) -> None:
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


F1, F2 = "2026-11-13T061841Z", "2026-11-13T120000Z"
NOW = datetime(2026, 11, 16, 0, 30, tzinfo=UTC)
HONEST = {f"{F1}/fred_DFEDTARU.csv": _entry(F1, "2026-11-13T06:18:42Z")}
HONEST_2 = dict(HONEST, **{f"{F2}/fred_DFEDTARU.csv": _entry(F2, "2026-11-13T12:00:05Z", sha256="aaaa" * 16)})
RESTORED = {k: dict(v, bytes_kept=False, note="hash from git 1111111") for k, v in HONEST.items()}


def selftest() -> int:
    failed = 0
    cases: list[tuple[str, list[str]]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        def case(name: str, root: Path, expected: list[str], now: datetime = NOW) -> None:
            # `expected`: one substring per violation expected, in any order; [] = the check passes
            got, _ = manifest_history_violations(root, now=now)
            cases.append((name, expected))
            left = list(got)
            for e in expected:
                hit = next((g for g in left if e in g), None)
                if hit is not None:
                    left.remove(hit)
            if left or len(got) != len(expected):
                nonlocal failed
                failed += 1
                print(f"selftest FAIL: {name}: expected {expected}, got {got}")

        r = _repo(tmp, "honest")
        _commit(r, HONEST, "2026-11-13T06:30:00+00:00")
        _commit(r, HONEST_2, "2026-11-13T12:30:00+00:00")
        case("two fetches, each committed within the hour", r, [])
        shallow = tmp / "shallow"
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{r}", str(shallow)], check=True)
        case("a shallow clone", shallow, ["shallow clone"])

        r = _repo(tmp, "rewritten")
        _commit(r, HONEST, "2026-11-13T06:30:00+00:00")
        _commit(r, {k: dict(v, sha256="bbbb" * 16) for k, v in HONEST.items()}, "2026-11-13T12:30:00+00:00")
        case("an entry's hash rewritten in a later commit", r, ["): sha256; the manifest is append-only"])

        r = _repo(tmp, "removed")
        _commit(r, HONEST_2, "2026-11-13T12:30:00+00:00")
        _commit(r, HONEST, "2026-11-13T13:00:00+00:00")
        case("an entry removed in a later commit", r, ["removed in"])

        r = _repo(tmp, "before")
        _commit(r, HONEST, "2026-11-13T05:00:00+00:00")
        case("an entry carried by a commit dated before its fetch", r, ["before the fetch it names"])

        r = _repo(tmp, "late")
        _commit(r, HONEST, "2026-11-16T06:30:00+00:00")
        case("an entry committed three days after its fetch", r, ["72.2 h after the fetch it names"])

        r = _repo(tmp, "restored")
        _commit(r, {"fred_DFEDTARU.csv": _entry(F1, "2026-11-13T06:18:42Z")}, "2026-11-13T06:30:00+00:00")
        _commit(r, RESTORED, "2026-11-16T06:30:00+00:00")
        case("a restoration days later of a hash the history carried under the file's name on the day", r, [])
        r = _repo(tmp, "restored-mute")
        _commit(r, {"fred_DFEDTARU.csv": _entry(F1, "2026-11-13T06:18:42Z")}, "2026-11-13T06:30:00+00:00")
        _commit(r, {k: dict(v, note="") for k, v in RESTORED.items()}, "2026-11-16T06:30:00+00:00")
        case("a restoration with no note", r, ["no note"])
        r = _repo(tmp, "restored-new")
        _commit(r, RESTORED, "2026-11-16T06:30:00+00:00")
        case("a restoration of a hash no earlier commit carried", r, ["72.2 h after the fetch it names"])

        r = _repo(tmp, "span")
        _commit(r, {k: dict(v, downloaded_at_utc="2026-11-13T08:18:42Z") for k, v in HONEST.items()},
                "2026-11-13T08:30:00+00:00")
        case("downloaded_at_utc two hours after the folder's time", r, ["not within ten minutes"])
        r = _repo(tmp, "name")
        _commit(r, {"2026-11-13/fred_DFEDTARU.csv": _entry(F1, "2026-11-13T06:18:42Z")}, "2026-11-13T06:30:00+00:00")
        case("a folder name that is not a fetch time", r, ["not a UTC fetch time"])
        r = _repo(tmp, "no-hash")
        _commit(r, {k: {f: v for f, v in e.items() if f != "sha256"} for k, e in HONEST.items()}, "2026-11-13T06:30:00+00:00")
        case("an entry with no sha256", r, ["no sha256"])

        r = _repo(tmp, "tree-late")
        _commit(r, HONEST, "2026-11-13T06:30:00+00:00")
        _write(r, HONEST_2)
        case("an uncommitted entry whose fetch is two days old", r, ["after the fetch it names"])
        r = _repo(tmp, "tree-fresh")
        _commit(r, HONEST, "2026-11-13T06:30:00+00:00")
        _write(r, HONEST_2)
        case("an uncommitted entry fetched half an hour ago", r, [], now=datetime(2026, 11, 13, 12, 30, tzinfo=UTC))
        r = _repo(tmp, "tree-rewrite")
        _commit(r, HONEST, "2026-11-13T06:30:00+00:00")
        _write(r, {k: dict(v, rows=1) for k, v in HONEST.items()})
        case("a committed entry edited in the working tree", r, ["rewritten in working tree (2026-11-16T00:30:00+00:00): rows"])

        r = _repo(tmp, "empty")
        _commit(r, {"fred_DFEDTARU.csv": _entry(F1, "2026-11-13T06:18:42Z")}, "2026-11-13T06:30:00+00:00")
        case("a manifest with file-name keys only", r, ["nothing to hold"])
        r = _repo(tmp, "none")
        subprocess.run(["git", "-C", str(r), "commit", "-q", "--allow-empty", "-m", "nothing"], check=True)
        case("no manifest at all", r, ["no manifest"])
    if failed:
        print(f"selftest: FAIL ({failed} of {len(cases)} cases)")
        return 1
    print(f"selftest: pass ({len(cases)} cases)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="the repository to read (default: this one)")
    parser.add_argument("--manifest", default=MANIFEST, help=f"the manifest, relative to --root (default {MANIFEST})")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    violations, summary = manifest_history_violations(args.root.resolve(), args.manifest)
    if not violations:
        print(f"fetch manifest history: ok ({summary}; {args.manifest})")
        return 0
    print(f"fetch manifest history: FAIL ({args.manifest}; the manifest is append-only, fix the writer, never the record)")
    for line in violations:
        print(f"  {line}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
