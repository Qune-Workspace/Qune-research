"""Push order of the pre-registrations of Studies 006-011, read from GitHub's clock.

Why: ARCHITECTURE.md promised that each new pre-registration is pushed to the
public remote before any data are fetched, with the remote evidence recorded in
trials.md. Study 009 recorded GitHub's push-event time. Studies 006-008 did not
(ARCHITECTURE.md, dated addition of 2026-10-26: "Not done"), and neither did
Studies 010 and 011, which came after the promise. This script recovers, where
GitHub still lists it, the time at which GitHub received each pre-registration
commit, and compares it with the first data read recorded by the study itself.

Specification (committed before the events are fetched; not changed afterwards):

- Source: GitHub's public events API for this repository
  (https://api.github.com/repos/<owner>/<repo>/events, owner and repo read from
  `git remote get-url origin` at run time), no token, per_page=100, pages 1-3 (the API lists at most 300 events and at most 90
  days). Fetched once with --fetch; the raw pages are saved under
  tools/data/raw/push_order/ (git-ignored) with their SHA-256 in the output.
- A PushEvent "carries" a commit C if C is an ancestor of (or equal to) the
  event's payload.head and is not an ancestor of payload.before, by
  `git merge-base --is-ancestor` in this clone. The push time of C is the
  earliest created_at over the PushEvents that carry it (GitHub's clock).
- Reference time per study: the first data read the study records itself, on
  this machine's clock:
    006 results/data_step.json run_at_utc (02:21:01Z; trials.md also discloses
        that the header and first row of four input files were printed after
        the push and before the script was written, at a time not recorded);
    007 results/data_step.json run_at_utc;
    008 earliest downloaded_at_utc on 2026-10-25 in results/data_manifest.json
        (the CPI fetch);
    010 and 011 results/data_manifest.json read_at_utc (the library page read).
  009 has no data step; its recorded PushEvent time (2026-10-26T01:26:56Z) is
  the control: the method must reproduce it, else the whole check is void.
- Reading: "pushed before the first data read" if push time < reference time;
  "pushed after" otherwise; "not recoverable" if no listed PushEvent carries
  the commit (aged out of the 300-event window, or never pushed alone).
  The margin is reported in seconds. The two clocks are different machines;
  a margin under 60 s is reported as "within clock tolerance", not as a pass.
- Nothing about any return is read. The output is tools/push_order.txt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "tools" / "data" / "raw" / "push_order"
OUT = ROOT / "tools" / "push_order.txt"
API = "https://api.github.com/repos/{slug}/events?per_page=100&page={page}"

# study -> (pre-registration commit, reference label, reference time UTC or None)
STUDIES = {
    "006": ("a67ef8d", "data_step.json run_at_utc", None),
    "007": ("e4c21e5", "data_step.json run_at_utc", None),
    "008": ("ca2432a", "first 2026-10-25 downloaded_at_utc (CPI fetch)", None),
    "009": ("299b532", "control: recorded PushEvent 2026-10-26T01:26:56Z", "2026-10-26T01:26:56Z"),
    "010": ("d9648af", "data_manifest.json read_at_utc", None),
    "011": ("f534c99", "data_manifest.json read_at_utc", None),
}
FOLDERS = {
    "006": "006-term-spread-switch-long-history",
    "007": "007-bond-carry-tilt-long-history",
    "008": "008-bond-value-tilt-long-history",
    "010": "010-factor-momentum-french-us",
    "011": "011-industry-momentum-french-us",
}


def ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def reference_time(study: str) -> str:
    res = ROOT / "research" / FOLDERS[study] / "results"
    if study in ("006", "007"):
        return json.loads((res / "data_step.json").read_text())["run_at_utc"]
    man = json.loads((res / "data_manifest.json").read_text())
    if study == "008":
        times = []

        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == "downloaded_at_utc" and isinstance(v, str) and v.startswith("2026-10-25"):
                        times.append(v)
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(man)
        return min(times)
    return man["library_page"]["read_at_utc"]


def repo_slug() -> str:
    url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.strip()
    tail = url.split("github.com", 1)[1].lstrip(":/")
    return tail[:-4] if tail.endswith(".git") else tail


def fetch() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    slug = repo_slug()
    for page in (1, 2, 3):
        req = urllib.request.Request(API.format(slug=slug, page=page), headers={
            "Accept": "application/vnd.github+json", "User-Agent": "qune-research-push-order"})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
        (RAW / f"events_p{page}.json").write_bytes(body)
        if not json.loads(body):
            break


def is_ancestor(a: str, b: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=ROOT,
                          capture_output=True).returncode == 0


def known(c: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", c + "^{commit}"], cwd=ROOT,
                          capture_output=True).returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="fetch the events once (refused if saved)")
    a = ap.parse_args()
    if a.fetch:
        if RAW.exists() and any(RAW.iterdir()):
            sys.exit("events already fetched; refusing a second fetch")
        fetch()
    pages = sorted(RAW.glob("events_p*.json"))
    if not pages:
        sys.exit("no saved events; run with --fetch once")
    lines = ["# Push order of pre-registrations 006-011 (tools/push_order.py; spec in its docstring)", ""]
    events = []
    for p in pages:
        b = p.read_bytes()
        lines.append(f"{p.name}: sha256 {hashlib.sha256(b).hexdigest()}, {len(json.loads(b))} events")
        events += json.loads(b)
    pushes = [e for e in events if e.get("type") == "PushEvent"]
    created = sorted(e["created_at"] for e in events)
    lines.append(f"events listed: {len(events)}; PushEvents: {len(pushes)}; "
                 f"oldest listed {created[0] if created else 'none'}, newest {created[-1] if created else 'none'}")
    unknown = sum(1 for e in pushes if not known(e["payload"].get("head", "")))
    lines.append(f"PushEvent heads not in this clone: {unknown}")
    lines.append("")
    lines.append("| Study | Pre-registration commit | GitHub push time (earliest carrying PushEvent) | Reference | Reference time (machine) | Margin (s) | Reading |")
    lines.append("|---|---|---|---|---|---|---|")
    control_ok = None
    for study, (commit, label, fixed) in STUDIES.items():
        carrying = []
        for e in pushes:
            head, before = e["payload"].get("head"), e["payload"].get("before")
            if not head or not known(head) or not is_ancestor(commit, head):
                continue
            if before and known(before) and is_ancestor(commit, before):
                continue
            carrying.append(e["created_at"])
        push = min(carrying) if carrying else None
        ref = fixed or reference_time(study)
        if study == "009":
            control_ok = push == ref
            reading = "control reproduced" if control_ok else "CONTROL FAILED: check void"
            margin = "" if push is None else str(int((ts(ref) - ts(push)).total_seconds()))
        elif push is None:
            reading, margin = "not recoverable", ""
        else:
            m = int((ts(ref) - ts(push)).total_seconds())
            margin = str(m)
            reading = ("within clock tolerance" if abs(m) < 60 else
                       "pushed before the first data read" if m > 0 else "pushed after the first data read")
        lines.append(f"| {study} | `{commit}` | {push or 'none listed'} | {label} | {ref} | {margin} | {reading} |")
    lines.append("")
    lines.append("Control: " + ("reproduced, check valid." if control_ok else "NOT reproduced, the readings above are void."))
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if control_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
