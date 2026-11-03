"""Study 013 resolution fetch (PREREGISTRATION.md §5.1, §5.3, §11; §14 step 4).

Once, on or after the scoring deadline 2027-01-20 00:00Z, for every candidate
market (§6.4: every id in any snapshot from S to 2026-12-28): Gamma
`GET /markets/<id>` and CLOB `GET /markets/<conditionId>`, public, no key,
inside the documented rate limits. Each response body is hashed (SHA-256, byte
count, fetch time) into `manifest.jsonl` and **not kept**; the two files of
§5.3 are the only record, under `data/raw/resolution/` (git-ignored):

  - `status.jsonl`: id, conditionId, closedTime, closed, umaResolutionStatus,
    endDate, volumeNum, event ids, tag labels, the two outcome labels, fetch
    time, body hashes (what the data step may read);
  - `outcome.jsonl`: id, outcomePrices, the CLOB tokens with their winner
    flags, fetch time, body hashes (what only the scoring run may read).

A market whose two requests have not both succeeded after three attempts is
written to `status.jsonl` with `fetch_failed` true and no field of either
body, and counted (§6.5, the fourth kind). **The fetch prints no outcome
field**: progress lines carry counts only.

Resumable (pitfall 11: hundreds of thousands of markets, two requests each, at
most 300 requests per 10 s): a run skips every id already present in
`status.jsonl` (it reads that file's ids only, never the outcome file's
content) and appends. The provenance line in `paper-log/resolution_fetch.csv`
is written once, when every candidate has a line; after it exists the fetch
refuses (exit 2). Before the deadline it refuses (exit 1). A shape failure on
every one of the first twenty markets (a body without the identifiers or the
token list the code expects) aborts the run so that the reading is fixed
before the venue's rate budget is spent; nothing is counted for them.

Field names follow the collector's observed listing rows (2026-11-02) and the
CLOB documentation's market record (`tokens[]` with `token_id`, `outcome`,
`winner`); the separate-session code review checks the reading before the
first real call (§14 step 3). Every path is passed by name
(tools/check_bound_defaults.py).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from src.snapshots import candidate_set, read_snapshot_log

UTC = dt.UTC
DEADLINE = dt.datetime(2027, 1, 20, tzinfo=UTC)  # §11
FIRST_DAY = dt.date(2026, 11, 3)  # S (§0 item 6)
LAST_DAY = dt.date(2026, 12, 28)  # §6.4, §5.4
GAMMA_MARKET = "https://gamma-api.polymarket.com/markets/"
CLOB_MARKET = "https://clob.polymarket.com/markets/"
UA = "qune-research/0.1 (public research; resolution fetch once after the scoring deadline; research/013/src/resolution.py)"
ATTEMPTS = 3  # §6.5
PAUSE_S = 0.07  # two requests a market; well inside 300 requests per 10 s
SHAPE_ABORT_AFTER = 20

STATUS_FIELDS = ("conditionId", "closedTime", "closed", "umaResolutionStatus", "endDate", "volumeNum")
LOG_COLUMNS = ("started_utc", "finished_utc", "candidates", "fetched", "failed", "status_sha256", "outcome_sha256", "manifest_sha256")

# A body fetcher returns the raw bytes; it raises on a failure the caller should retry.
Fetcher = Callable[[str], bytes]


class ShapeError(Exception):
    """The body does not carry the identifiers or lists the reading expects."""


def http_fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def gamma_fetcher(url_base: str = GAMMA_MARKET) -> Fetcher:
    return lambda market_id: http_fetch(url_base + market_id)


def clob_fetcher(url_base: str = CLOB_MARKET) -> Fetcher:
    return lambda condition_id: http_fetch(url_base + condition_id)


def stamp(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def split_gamma(body: bytes, market_id: str) -> tuple[dict, dict]:
    """The status part and the outcome part of a Gamma market body (§5.3)."""
    m = json.loads(body)
    if not isinstance(m, dict) or str(m.get("id")) != str(market_id):
        raise ShapeError("gamma body is not the market object asked for")
    status = {k: m.get(k) for k in STATUS_FIELDS}
    status["eventIds"] = sorted(str(e.get("id")) for e in (m.get("events") or []) if isinstance(e, dict) and e.get("id") is not None)
    status["tagLabels"] = sorted(str(t.get("label")) for t in (m.get("tags") or []) if isinstance(t, dict) and t.get("label"))
    status["outcomeLabels"] = m.get("outcomes")
    status["clobTokenIds"] = m.get("clobTokenIds")
    outcome = {"outcomePrices": m.get("outcomePrices")}
    return status, outcome


def split_clob(body: bytes) -> dict:
    """The tokens of a CLOB market body with their winner flags (§6.5)."""
    m = json.loads(body)
    tokens = m.get("tokens") if isinstance(m, dict) else None
    if not isinstance(tokens, list):
        raise ShapeError("clob body has no token list")
    return {"tokens": [{"token_id": str(t.get("token_id")), "winner": t.get("winner")} for t in tokens if isinstance(t, dict)]}


def _retrying(fetch: Fetcher, key: str, manifest, api: str, market_id: str, attempts: int, now: Callable[[], dt.datetime]) -> bytes | None:
    delay = 1.0
    for attempt in range(1, attempts + 1):
        try:
            body = fetch(key)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            manifest.write(json.dumps({"id": market_id, "api": api, "attempt": attempt, "ok": False,
                                       "error": type(e).__name__, "fetched_utc": stamp(now())}) + "\n")
            if attempt < attempts:
                time.sleep(delay)
                delay *= 2
            continue
        manifest.write(json.dumps({"id": market_id, "api": api, "attempt": attempt, "ok": True,
                                   "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
                                   "fetched_utc": stamp(now())}) + "\n")
        return body
    return None


def done_ids(status_jsonl: Path) -> set[str]:
    """Ids already written to status.jsonl (the id field only)."""
    if not status_jsonl.exists():
        return set()
    out: set[str] = set()
    with open(status_jsonl, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.add(str(json.loads(line).get("id")))
    return out


def fetch_resolution(
    *,
    candidates: dict[str, str],
    out_dir: Path,
    log_csv: Path,
    gamma: Fetcher,
    clob: Fetcher,
    now: Callable[[], dt.datetime],
    attempts: int = ATTEMPTS,
    pause_s: float = PAUSE_S,
    progress_every: int = 1000,
    limit: int = 0,
    log=sys.stdout,
) -> dict[str, str]:
    """Fetch every candidate not yet in status.jsonl; write the provenance line when all are done.

    Raises Refusal-like ValueError before the deadline or after completion; ShapeError when the first
    SHAPE_ABORT_AFTER markets all fail on shape."""
    started = now()
    if started < DEADLINE:
        raise ValueError(f"before the scoring deadline {stamp(DEADLINE)} (§11): the resolution fetch runs on or after it")
    if log_csv.exists():
        raise ValueError(f"{log_csv.name} exists: the resolution fetch ran once already (§11)")
    out_dir.mkdir(parents=True, exist_ok=True)
    status_path = out_dir / "status.jsonl"
    outcome_path = out_dir / "outcome.jsonl"
    manifest_path = out_dir / "manifest.jsonl"
    already = done_ids(status_path)
    todo = [(m, c) for m, c in sorted(candidates.items()) if m not in already]
    if limit:
        todo = todo[:limit]
    fetched = failed = 0
    # The first SHAPE_ABORT_AFTER markets are buffered: if every one of them fails on shape the run aborts and
    # none of them gets a line (nothing counted); otherwise the buffer is flushed and the rest streams.
    buffer: list[tuple[str, str | None, str]] = []  # (status line, outcome line or None, manifest line)
    shape_in_buffer = 0
    buffering = True
    with (
        open(status_path, "a", encoding="utf-8") as st,
        open(outcome_path, "a", encoding="utf-8") as oc,
        open(manifest_path, "a", encoding="utf-8") as man,
    ):

        def emit(status_line: str, outcome_line: str | None, shape_note: str | None) -> None:
            nonlocal shape_in_buffer
            if buffering:
                buffer.append((status_line, outcome_line, shape_note or ""))
                shape_in_buffer += 1 if shape_note else 0
                return
            st.write(status_line)
            if outcome_line:
                oc.write(outcome_line)
            if shape_note:
                man.write(shape_note)

        def flush_buffer() -> None:
            nonlocal buffering
            buffering = False
            for s_line, o_line, note in buffer:
                st.write(s_line)
                if o_line:
                    oc.write(o_line)
                if note:
                    man.write(note)
            buffer.clear()

        for k, (mid, cid) in enumerate(todo, 1):
            t = stamp(now())
            g_body = _retrying(gamma, mid, man, "gamma", mid, attempts, now)
            c_body = _retrying(clob, cid, man, "clob", mid, attempts, now) if cid else None
            shape_note: str | None = None
            try:
                if g_body is None or c_body is None:
                    raise ValueError("a request failed after every attempt")
                status, outcome = split_gamma(g_body, mid)
                outcome.update(split_clob(c_body))
            except ShapeError as e:
                failed += 1
                shape_note = json.dumps({"id": mid, "api": "shape", "ok": False, "error": str(e), "fetched_utc": stamp(now())}) + "\n"
                emit(json.dumps({"id": mid, "conditionId": cid, "fetch_failed": True, "reason": "shape", "fetched_utc": t}) + "\n", None, shape_note)
            except (ValueError, json.JSONDecodeError):
                failed += 1
                emit(json.dumps({"id": mid, "conditionId": cid, "fetch_failed": True, "reason": "request", "fetched_utc": t}) + "\n", None, None)
            else:
                hashes = {"gamma_sha256": hashlib.sha256(g_body).hexdigest(), "clob_sha256": hashlib.sha256(c_body).hexdigest()}
                emit(json.dumps({"id": mid, **status, "fetch_failed": False, "fetched_utc": t, **hashes}) + "\n",
                     json.dumps({"id": mid, **outcome, "fetched_utc": t, **hashes}) + "\n", None)
                fetched += 1
            if buffering and len(buffer) == SHAPE_ABORT_AFTER:
                if shape_in_buffer == SHAPE_ABORT_AFTER:
                    raise ShapeError(f"the first {SHAPE_ABORT_AFTER} markets all failed on shape: fix the reading before spending the budget; no line written for them")
                flush_buffer()
            if progress_every and k % progress_every == 0:
                print(f"resolution fetch: {k} of {len(todo)} this run ({fetched} fetched, {failed} failed)", file=log, flush=True)
            if pause_s:
                time.sleep(pause_s)
        if buffering and todo and shape_in_buffer == len(buffer) == len(todo):
            raise ShapeError(f"every market this run ({len(todo)}) failed on shape: fix the reading; no line written for them")
        if buffering:
            flush_buffer()
    remaining = set(candidates) - done_ids(status_path)
    if remaining:
        print(f"resolution fetch: {len(remaining)} candidate(s) without a line; run again", file=log, flush=True)
        return {"complete": "no", "fetched": str(fetched), "failed": str(failed), "remaining": str(len(remaining))}
    finished = now()
    all_lines = _count_lines(status_path)
    all_failed = _count_failed(status_path)
    row = {
        "started_utc": stamp(started),
        "finished_utc": stamp(finished),
        "candidates": str(len(candidates)),
        "fetched": str(all_lines - all_failed),
        "failed": str(all_failed),
        "status_sha256": _sha256(status_path),
        "outcome_sha256": _sha256(outcome_path),
        "manifest_sha256": _sha256(manifest_path),
    }
    log_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(log_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerow(row)
    return {"complete": "yes", **row}


def _count_lines(path: Path) -> int:
    with open(path, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def _count_failed(path: Path) -> int:
    n = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip() and json.loads(line).get("fetch_failed"):
                n += 1
    return n


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--study-dir", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--limit", type=int, default=0, help="fetch at most this many candidates this run (0 = all)")
    a = ap.parse_args(argv)
    study = a.study_dir
    snapshots = read_snapshot_log(study / "paper-log" / "snapshots.csv")
    candidates = candidate_set(study / "data" / "raw" / "snapshots", snapshots, FIRST_DAY, LAST_DAY)
    try:
        row = fetch_resolution(
            candidates=candidates,
            out_dir=study / "data" / "raw" / "resolution",
            log_csv=study / "paper-log" / "resolution_fetch.csv",
            gamma=gamma_fetcher(),
            clob=clob_fetcher(),
            now=lambda: dt.datetime.now(UTC),
            limit=a.limit,
        )
    except ValueError as e:
        print(f"refused: {e}; nothing written")
        return 2 if "exists" in str(e) else 1
    except ShapeError as e:
        print(f"aborted: {e}", file=sys.stderr)
        return 3
    print(f"resolution fetch: complete {row['complete']}; " + ", ".join(f"{k} {v}" for k, v in row.items() if k != "complete"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
