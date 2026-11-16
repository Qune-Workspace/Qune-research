"""The desk's fetch manifests are held to the repository's own history.

Written on 2026-11-16 (00:15Z run) after the chain built over 14 and 15 November
(row -> candidate -> kept folder -> manifest entry) was found to end at an entry
nothing held: on 5f46891, on a scratch copy of the kept 13 November folder, a
copy with its DTB3 prints moved by -0.60 and four manifest entries written by
hand to its bytes was read by default by `fomc_calibrate.py --live` (0.000 for
the hike where the recorded bytes read 1.000), its candidate was written, and
`--recompute` found the figures reproduced with rc 0 (predictions/POST_MORTEMS.md,
"A manifest held by nothing but the hand that wrote it").

Extended on 2026-11-16 (06:15Z run) to the three sibling manifests the 00:15Z run
named as the next class: until then `--manifest` offered them by name and the
check died on each with a traceback (`'list' object has no attribute 'items'`),
because it read one shape, the folder-keyed object of the bill reading, and the
siblings are JSON lists of entries stamped `fetched_utc` (predictions/
POST_MORTEMS.md, "A check that offered what it could not read").

Nothing on this host can hold a manifest against the host's own writer; what
can is the history outside the writer's reach, the pushed commits.  This check
makes that anchor explicit.  It reads every commit of each manifest in
MANIFESTS and the working tree, and refuses when:

- an entry once committed is changed in a later commit or in the working tree,
  in any field, or removed: every manifest is append-only.  An entry is a
  folder-keyed one (`<fetch folder>/<file>`) in an object manifest, or in a list
  manifest the entry named by its `series`, `event_slug` or `market_id` at its
  `fetched_utc`; an entry no field names, or one listed twice under the same
  name and time, is a refusal, because append-only cannot be judged for it;
- an entry's folder name is not a UTC fetch time, or its `downloaded_at_utc` is
  not within ten minutes after that time (object manifests); or its
  `fetched_utc` is not a UTC stamp (list manifests): the entry does not
  describe the fetch it is filed under;
- the commit that first carries one of an entry's hashes (every field ending in
  `sha256`, under any entry) is dated more than 24 hours after the fetch it
  names (a hash that arrived long after the fetch: by hand, or a run that broke
  the commit-before-long-fetches rule), or the entry itself was first committed
  before the fetch it names (a fetch recorded before it happened); an
  uncommitted entry is held to the clock the same way.  The hash, not the key,
  is what the history witnesses: the 13 November bill-reading fetch was
  committed under file-name keys 14 minutes after it and re-keyed under its
  folder 36 hours later (6b7a0b4); the 5 and 6 November `bytes_kept: false`
  restorations carry hashes bec16ab and e074791 committed within seven minutes
  of their fetches; a quote whose order book bytes equal an earlier quote's
  files a hash the history already carries, and passes.  A `bytes_kept: false`
  entry must also carry a `note` saying where its hash came from;
- a manifest has no entry (an empty universe is a refusal, never a pass), is
  neither a JSON object nor a list, or the clone is shallow and the history
  cannot be read.

What it cannot hold: an entry written by hand and committed within a day of
the fetch time it names.  The check closes the gap between an entry and the
commit that carries it; the commit, once pushed, is the record.

Usage: python tools/check_manifest_history.py [--root PATH] [--manifest RELPATH ...] [--selftest]
With no --manifest every manifest in MANIFESTS is read; the exit status is 1 if any refuses.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "pm-view/data/fred_rates_manifest.json"
MANIFESTS = (
    MANIFEST,                             # the bill reading's four FRED series, folder-keyed object (fomc_calibrate.py)
    "pm-view/data/manifest.json",         # one entry per written quote, list (fetch.py)
    "pm-view/data/fred_manifest.json",    # one entry per fetch of CBBTCUSD, list (barrier.py)
    "pm-view/data/events_manifest.json",  # one entry per fetched event listing, list (event_coverage.py)
)
NAME_FIELDS = ("series", "event_slug", "market_id")
FOLDER_FORMAT = "%Y-%m-%dT%H%M%SZ"
STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
MAX_DELAY = timedelta(hours=24)
MAX_DOWNLOAD_SPAN = timedelta(minutes=10)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def _folder_keyed(manifest: dict) -> dict:
    return {k: v for k, v in manifest.items() if "/" in k}


def _identity(entry: dict) -> str | None:
    """A list entry's name for the append-only rule: `<series|event_slug|market_id>@<fetched_utc>`."""
    name = next((str(entry[f]) for f in NAME_FIELDS if entry.get(f) not in (None, "")), None)
    return None if name is None else f"{name}@{entry.get('fetched_utc')}"


def _entries(full: Any) -> tuple[dict[str, dict], list[str]]:
    """The held entries of one manifest state keyed for the append-only rule, and the lines for the entries
    that cannot be keyed (reported for the state a reader reads: the last one)."""
    if isinstance(full, dict):
        return _folder_keyed(full), []
    if not isinstance(full, list):
        return {}, [f"the manifest is neither a JSON object nor a list ({type(full).__name__}); nothing to hold"]
    out: dict[str, dict] = {}
    problems: list[str] = []
    for i, entry in enumerate(full):
        if not isinstance(entry, dict):
            problems.append(f"entry {i}: not a JSON object; nothing to hold")
            continue
        key = _identity(entry)
        if key is None:
            problems.append(f"entry {i} (fetched_utc {entry.get('fetched_utc')!r}): no name field among "
                            f"{', '.join(NAME_FIELDS)}; append-only cannot be judged for an entry nothing names")
        elif key in out:
            problems.append(f"{key}: listed twice; append-only cannot be judged for a repeated name and time")
        else:
            out[key] = entry
    return out, problems


def _all_entries(full: Any) -> list[dict]:
    values = full.values() if isinstance(full, dict) else full if isinstance(full, list) else []
    return [e for e in values if isinstance(e, dict)]


def _hashes(entry: dict) -> list[tuple[str, str]]:
    return [(k, str(v)) for k, v in sorted(entry.items()) if k.endswith("sha256") and v]


def _changed_fields(a: dict, b: dict) -> list[str]:
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def _hours(delta: timedelta) -> str:
    return f"{delta.total_seconds() / 3600:.1f} h"


def _fetch_time(key: str, entry: dict, shape: str) -> tuple[datetime | None, list[str]]:
    """When the fetch an entry names happened, read from the entry's own stamps, and the lines when it cannot."""
    if shape == "object":
        folder = key.split("/", 1)[0]
        try:
            fetched = datetime.strptime(folder, FOLDER_FORMAT).replace(tzinfo=UTC)
        except ValueError:
            return None, [f"{key}: the folder name is not a UTC fetch time ({FOLDER_FORMAT})"]
        try:
            downloaded = datetime.strptime(str(entry.get("downloaded_at_utc", "")), STAMP_FORMAT).replace(tzinfo=UTC)
        except ValueError:
            return None, [f"{key}: downloaded_at_utc {entry.get('downloaded_at_utc')!r} is not a UTC stamp ({STAMP_FORMAT})"]
        if not fetched <= downloaded <= fetched + MAX_DOWNLOAD_SPAN:
            return fetched, [f"{key}: downloaded_at_utc {entry['downloaded_at_utc']} is not within ten minutes after the "
                             f"folder's time {folder}"]
        return fetched, []
    try:
        return datetime.strptime(str(entry.get("fetched_utc", "")), STAMP_FORMAT).replace(tzinfo=UTC), []
    except ValueError:
        return None, [f"{key}: fetched_utc {entry.get('fetched_utc')!r} is not a UTC stamp ({STAMP_FORMAT})"]


def manifest_history_violations(root: Path, rel: str = MANIFEST, now: datetime | None = None) -> tuple[list[str], str]:
    """Why the manifest at `root/rel` is not an honest, append-only record of its fetches, and a
    one-line summary of what was held when it is."""
    now = now or datetime.now(UTC)
    out: list[str] = []
    if _git(root, "rev-parse", "--is-shallow-repository").strip() == "true":
        return [f"{rel}: shallow clone, the history cannot be read (check out with fetch-depth 0)"], ""
    log = _git(root, "log", "--format=%H %cI", "--reverse", "--", rel).split("\n")
    commits = [(h, datetime.fromisoformat(d)) for h, _, d in (ln.partition(" ") for ln in log if ln)]
    states: list[tuple[str, datetime, Any]] = []
    for h, d in commits:
        states.append((h[:7], d, json.loads(_git(root, "show", f"{h}:{rel}"))))
    path = root / rel
    if path.exists():
        states.append(("working tree", now, json.loads(path.read_text(encoding="utf-8"))))
    if not states:
        return [f"{rel}: no manifest in the tree or the history"], ""
    shape = "object" if isinstance(states[-1][2], dict) else "list"
    # The hash is what the history witnesses: the first commit carrying a hash under any entry (a fetch that
    # returns the same bytes as an earlier one files an older hash, as the 6 November DFEDTARU and EFFR
    # entries do).  The entry's own first commit holds it to not predating the fetch it names.
    hash_first_seen: dict[str, tuple[str, datetime]] = {}
    key_first_seen: dict[str, tuple[str, datetime]] = {}
    prev: dict[str, dict] = {}
    problems: list[str] = []
    for label, d, full in states:
        cur, problems = _entries(full)
        for key in prev:
            if key not in cur:
                out.append(f"{key}: removed in {label} ({d.isoformat()}); the manifest is append-only")
            elif cur[key] != prev[key]:
                out.append(f"{key}: rewritten in {label} ({d.isoformat()}): {', '.join(_changed_fields(prev[key], cur[key]))}; "
                           "the manifest is append-only")
        for key in cur:
            key_first_seen.setdefault(key, (label, d))
        for entry in _all_entries(full):
            for _, digest in _hashes(entry):
                hash_first_seen.setdefault(digest, (label, d))
        prev = cur
    out.extend(f"{rel}: {p}" for p in problems)
    final = prev
    if not final:
        unit = "folder-keyed entry (`<fetch folder>/<file>`)" if shape == "object" else "entry"
        out.append(f"{rel}: no {unit}: nothing to hold")
        return out, ""
    passing: list[tuple[datetime, str, str, str, datetime]] = []
    fetches: set[datetime] = set()
    for key, entry in sorted(final.items()):
        fetched, lines = _fetch_time(key, entry, shape)
        out.extend(lines)
        if fetched is None:
            continue
        fetches.add(fetched)
        if entry.get("bytes_kept") is False and not str(entry.get("note", "")).strip():
            out.append(f"{key}: bytes_kept is false and no note says where the hash came from")
        hashes = _hashes(entry)
        if not hashes:
            out.append(f"{key}: no sha256: nothing for the history to witness")
            continue
        key_label, key_carried = key_first_seen[key]
        if key_carried < fetched:
            out.append(f"{key}: first carried by {key_label} at {key_carried.isoformat()}, before the fetch it names "
                       f"({fetched.strftime(STAMP_FORMAT)})")
            continue
        late = False
        latest_label, latest_carried = key_label, datetime.min.replace(tzinfo=UTC)
        for field, digest in hashes:
            label, carried = hash_first_seen[digest]
            if carried - fetched > MAX_DELAY:
                late = True
                out.append(f"{key}: its {field} was first carried by {label} at {carried.isoformat()}, "
                           f"{_hours(carried - fetched)} after the fetch it names ({fetched.strftime(STAMP_FORMAT)}); "
                           f"the limit is {_hours(MAX_DELAY)}")
            elif carried > latest_carried:
                latest_label, latest_carried = label, carried
        if not late:
            passing.append((fetched, key, key_label, latest_label, latest_carried))
    newest = ""
    if passing:
        fetched, key, key_label, label, carried = max(passing)
        newest = (f"newest {fetched.strftime(STAMP_FORMAT)} ({key}), filed by {key_label}, its hashes carried since "
                  f"{label} ({carried.isoformat()})")
    summary = (f"{len(final)} entries over {len(fetches)} fetch times, {len(commits)} commits since "
               f"{commits[0][1].date().isoformat() if commits else 'none'}; {newest or 'no entry under the 24 h rule'}")
    return out, summary


# --- self-test -------------------------------------------------------------------------------------

_ENTRY = {"downloaded_at_utc": "2026-11-13T06:18:42Z", "first_bar": "2008-12-16", "last_bar": "2026-11-12",
          "rows": 6541, "series_id": "DFEDTARU", "sha256": "5306d0dd" * 8, "source": "FRED (fredgraph.csv)",
          "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFEDTARU"}
_QUOTE = {"best_ask": 0.74, "best_bid": 0.73, "book_sha256": "832f5e4c" * 8, "end_date": "2026-12-09T23:59:00Z",
          "fetched_utc": "2026-11-13T06:24:40Z", "gamma_sha256": "5c18bd13" * 8, "market_id": "3215008",
          "market_mid": 0.735, "source": "Polymarket Gamma /markets/<id> and CLOB /book?token_id=<yes token>"}
LIST_MANIFEST = "pm-view/data/manifest.json"


def _entry(folder: str, downloaded: str, **fields: object) -> dict:
    return dict(_ENTRY, downloaded_at_utc=downloaded, **fields)


def _quote(fetched: str, market_id: str = "3215008", **fields: object) -> dict:
    return dict(_QUOTE, fetched_utc=fetched, market_id=market_id, **fields)


def _repo(tmp: Path, name: str) -> Path:
    root = tmp / name
    root.mkdir()
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    for k, v in (("user.name", "selftest"), ("user.email", "selftest@example.invalid"), ("commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(root), "config", k, v], check=True)
    return root


def _commit(root: Path, manifest: Any, when: str, rel: str = MANIFEST) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    subprocess.run(["git", "-C", str(root), "add", rel], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", f"manifest at {when}"], check=True, env=env)


def _write(root: Path, manifest: Any, rel: str = MANIFEST) -> None:
    (root / rel).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


F1, F2 = "2026-11-13T061841Z", "2026-11-13T120000Z"
NOW = datetime(2026, 11, 16, 0, 30, tzinfo=UTC)
HONEST = {f"{F1}/fred_DFEDTARU.csv": _entry(F1, "2026-11-13T06:18:42Z")}
HONEST_2 = dict(HONEST, **{f"{F2}/fred_DFEDTARU.csv": _entry(F2, "2026-11-13T12:00:05Z", sha256="aaaa" * 16)})
RESTORED = {k: dict(v, bytes_kept=False, note="hash from git 1111111") for k, v in HONEST.items()}
Q1, Q2 = "2026-11-06T06:17:29Z", "2026-11-13T06:24:40Z"
QUOTES = [_quote(Q1, book_sha256="1111" * 16, gamma_sha256="2222" * 16)]
QUOTES_2 = QUOTES + [_quote(Q2)]


def selftest() -> int:
    failed = 0
    cases: list[tuple[str, list[str]]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        def case(name: str, root: Path, expected: list[str], now: datetime = NOW, rel: str = MANIFEST) -> None:
            # `expected`: one substring per violation expected, in any order; [] = the check passes
            got, _ = manifest_history_violations(root, rel, now=now)
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

        # --- list manifests (quotes, price-series fetches, event listings), added 2026-11-16 06:15Z ---
        L = LIST_MANIFEST
        r = _repo(tmp, "list-honest")
        _commit(r, QUOTES, "2026-11-06T06:26:00+00:00", L)
        _commit(r, QUOTES_2, "2026-11-13T06:32:00+00:00", L)
        case("list: two quotes, each committed within the hour", r, [], rel=L)
        r = _repo(tmp, "list-rewritten")
        _commit(r, QUOTES, "2026-11-06T06:26:00+00:00", L)
        _commit(r, [dict(QUOTES[0], market_mid=0.5)], "2026-11-13T06:32:00+00:00", L)
        case("list: a quote's mid rewritten in a later commit", r, ["): market_mid; the manifest is append-only"], rel=L)
        r = _repo(tmp, "list-removed")
        _commit(r, QUOTES, "2026-11-06T06:26:00+00:00", L)
        _commit(r, QUOTES_2, "2026-11-13T06:32:00+00:00", L)
        _commit(r, QUOTES, "2026-11-13T07:00:00+00:00", L)
        case("list: a quote removed in a later commit", r, ["removed in"], rel=L)
        r = _repo(tmp, "list-before")
        _commit(r, QUOTES, "2026-11-06T05:00:00+00:00", L)
        case("list: a quote carried by a commit dated before its fetch", r, ["before the fetch it names"], rel=L)
        r = _repo(tmp, "list-late")
        _commit(r, QUOTES, "2026-11-09T06:26:00+00:00", L)
        case("list: a quote committed three days after its fetch, both hashes named", r,
             ["its book_sha256 was first carried", "its gamma_sha256 was first carried"], rel=L)
        r = _repo(tmp, "list-same-book")
        _commit(r, QUOTES, "2026-11-06T06:26:00+00:00", L)
        _commit(r, QUOTES + [_quote(Q2, book_sha256="1111" * 16)], "2026-11-13T06:32:00+00:00", L)
        case("list: a later quote whose book bytes equal an earlier one's", r, [], rel=L)
        r = _repo(tmp, "list-twice")
        _commit(r, QUOTES + QUOTES, "2026-11-06T06:26:00+00:00", L)
        case("list: the same market and time listed twice", r, ["listed twice"], rel=L)
        r = _repo(tmp, "list-unnamed")
        _commit(r, [{k: v for k, v in QUOTES[0].items() if k != "market_id"}], "2026-11-06T06:26:00+00:00", L)
        case("list: an entry no name field names", r, ["no name field", "nothing to hold"], rel=L)
        r = _repo(tmp, "list-no-hash")
        _commit(r, [{k: v for k, v in QUOTES[0].items() if not k.endswith("sha256")}], "2026-11-06T06:26:00+00:00", L)
        case("list: an entry with no hash field", r, ["no sha256"], rel=L)
        r = _repo(tmp, "list-stamp")
        _commit(r, [dict(QUOTES[0], fetched_utc="2026-11-06")], "2026-11-06T06:26:00+00:00", L)
        case("list: a fetched_utc that is a date, not a stamp", r, ["not a UTC stamp"], rel=L)
        r = _repo(tmp, "list-empty")
        _commit(r, [], "2026-11-06T06:26:00+00:00", L)
        case("list: an empty list", r, ["nothing to hold"], rel=L)
        r = _repo(tmp, "list-tree-fresh")
        _commit(r, QUOTES, "2026-11-06T06:26:00+00:00", L)
        _write(r, QUOTES_2, L)
        case("list: an uncommitted quote fetched half an hour ago", r, [], now=datetime(2026, 11, 13, 6, 55, tzinfo=UTC), rel=L)
        r = _repo(tmp, "list-tree-late")
        _commit(r, QUOTES, "2026-11-06T06:26:00+00:00", L)
        _write(r, QUOTES_2, L)
        case("list: an uncommitted quote whose fetch is two days old", r,
             ["its book_sha256 was first carried", "its gamma_sha256 was first carried"], now=NOW, rel=L)
        r = _repo(tmp, "list-series")
        _commit(r, [{"series": "CBBTCUSD", "fetched_utc": Q1, "sha256": "3333" * 16}], "2026-11-06T06:26:00+00:00", L)
        case("list: a price-series entry named by `series`", r, [], rel=L)
        r = _repo(tmp, "list-slug")
        _commit(r, [{"event_slug": "fed-decision", "fetched_utc": Q1, "sha256": "4444" * 16}], "2026-11-06T06:26:00+00:00", L)
        case("list: an event listing named by `event_slug`", r, [], rel=L)
        r = _repo(tmp, "scalar")
        _commit(r, "not a manifest", "2026-11-06T06:26:00+00:00", L)
        case("a manifest that is neither object nor list", r, ["neither a JSON object nor a list", "nothing to hold"], rel=L)
    if failed:
        print(f"selftest: FAIL ({failed} of {len(cases)} cases)")
        return 1
    print(f"selftest: pass ({len(cases)} cases)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="the repository to read (default: this one)")
    parser.add_argument("--manifest", action="append", default=None,
                        help=f"a manifest, relative to --root; repeatable (default: all of {', '.join(MANIFESTS)})")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    rc = 0
    for rel in args.manifest or MANIFESTS:
        violations, summary = manifest_history_violations(args.root.resolve(), rel)
        if not violations:
            print(f"fetch manifest history: ok ({summary}; {rel})")
            continue
        rc = 1
        print(f"fetch manifest history: FAIL ({rel}; the manifest is append-only, fix the writer, never the record)")
        for line in violations:
            print(f"  {line}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
