"""Coverage of the events the view follows: every leg of a followed event is
read (a row in readings.csv), declined with a reason (a row in not_read.csv),
or counted as a coverage miss when it settles with neither.

Added 2026-11-13 12:15Z after the 70,000 touch market settled between two
weekly views with no quote while open (predictions/POST_MORTEMS.md "Ten of
eleven settled legs with nothing to score"): the view had followed the November
Bitcoin event since 3 November and quoted the legs it chose by hand, one or
two a week, so ten of the eleven legs that settled by 13 November left no
reading to score.  README rule 6 `[coverage:every-open-leg]`.

Subcommands (every path is passed by name; the defaults are this folder's files):

  fetch <event slug>       one Gamma /events?slug= call; raw body git-ignored under
                           data/raw/events/<fetched time>/, one entry appended to
                           data/events_manifest.json (slug, time, bytes, SHA-256, leg count)
  check [--at YYYY-MM-DD]  the legs of every event in events.csv against readings.csv and
                           not_read.csv, from the newest kept listing: read / declined /
                           open-unread / settled-unread, one line per leg and a summary
  record                   append every settled-unread leg not yet on coverage_misses.csv
                           (append-only; a leg is recorded once, by market id)
  decline <market id> --view <YYYY-MM-DD> --why "<reason>"
                           one row on not_read.csv for a leg the view saw and chose not to
                           read; the reason is required and must say something

Polymarket's verdict is `derived` (tools/pm_data_terms.md): the listing's raw body
stays git-ignored; the committed rows carry identifiers, the venue's question
title (as data/manifest.json already does), times, and counts.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

from pm_lib import rules_window

HERE = Path(__file__).resolve().parent
GAMMA_EVENTS = "https://gamma-api.polymarket.com/events?slug="
UTC_STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

EVENTS_COLUMNS = ("venue", "event_id", "event_slug", "method", "followed_from", "source")
MISSES_COLUMNS = ("event_slug", "market_id", "question", "listed_utc", "settled_utc", "outcome_prices",
                  "views_while_open", "noted_on", "listing_sha256")
NOT_READ_COLUMNS = ("event_slug", "market_id", "view_day", "why", "recorded_utc")

Fetcher = Callable[[str], bytes]


# --- parsing ------------------------------------------------------------------------------------

def parse_venue_time(value: object) -> datetime | None:
    """Gamma writes two shapes: '2026-11-01T05:07:10Z' and '2026-11-13 03:04:12.310502+00'.
    Both are parsed as datetimes (never sliced or compared as text); anything else is None."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip())  # both shapes parse whole on Python 3.11+; nothing is sliced
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


@dataclass(frozen=True)
class Leg:
    market_id: str
    question: str
    listed: datetime | None
    closed: bool
    closed_time: datetime | None
    uma_status: str | None
    outcome_prices: str | None
    volume: float | None
    rules_window: str = "unknown"  # 2026-11-14: how the leg's own rules open its window (pm_lib.rules_window)
    created: datetime | None = None

    @property
    def settled(self) -> bool:
        """The record says the market is no longer open: closed with a settlement time. The outcome
        rule that scores a row is Study 013 §6.5 in score.py; this flag only says there is nothing
        left to quote."""
        return bool(self.closed) and self.closed_time is not None

    def open_at(self, at: datetime) -> bool:
        """Listed at or before `at` and not yet settled at `at` (instants, never calendar days: the
        70,000 leg settled at 03:04Z on 13 November and that day's view read its quotes at 06:17Z)."""
        if self.listed is not None and self.listed > at:
            return False
        return self.closed_time is None or self.closed_time > at


def legs_of(event_body: bytes | str | list | dict) -> tuple[dict[str, Any], list[Leg]]:
    """The event (first element of the list Gamma returns for ?slug=) and its markets as legs."""
    data: Any = event_body
    if isinstance(data, (bytes, str)):
        data = json.loads(data)
    if isinstance(data, list):
        if not data:
            raise ValueError("event listing is an empty list (no event with that slug)")
        data = data[0]
    if not isinstance(data, dict):
        raise ValueError("event listing is not a JSON object")
    legs: list[Leg] = []
    for m in data.get("markets") or []:
        if not isinstance(m, dict) or m.get("id") is None:
            continue
        vol = m.get("volumeNum")
        try:
            volume = float(vol) if vol is not None else None
        except (TypeError, ValueError):
            volume = None
        legs.append(Leg(market_id=str(m["id"]), question=str(m.get("question") or ""),
                        listed=parse_venue_time(m.get("startDate")) or parse_venue_time(m.get("createdAt")),
                        closed=bool(m.get("closed")), closed_time=parse_venue_time(m.get("closedTime")),
                        uma_status=m.get("umaResolutionStatus"), outcome_prices=m.get("outcomePrices"),
                        volume=volume, rules_window=rules_window(m.get("description")),
                        created=parse_venue_time(m.get("createdAt"))))
    return data, legs


# --- files --------------------------------------------------------------------------------------

def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_row(path: Path, columns: tuple[str, ...], row: dict[str, Any]) -> None:
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(columns))
        if new:
            w.writeheader()
        w.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in columns})


def view_times(manifest_entries: list[dict[str, Any]]) -> dict[date, datetime]:
    """The view days and, for each, the first quote's time that day (data/manifest.json fetched_utc,
    parsed in the folder's one format, never sliced): the instant at which a leg had to be open to
    be read by that view."""
    times: dict[date, datetime] = {}
    for e in manifest_entries:
        try:
            at = datetime.strptime(str((e or {}).get("fetched_utc")), UTC_STAMP_FORMAT).replace(tzinfo=UTC)
        except (ValueError, TypeError, AttributeError):
            continue
        if at.date() not in times or at < times[at.date()]:
            times[at.date()] = at
    return times


def view_at_on(day: date, times: dict[date, datetime]) -> datetime:
    """The instant a check 'as of `day`' means: the day's first quote when a view was written that
    day, else the end of the day."""
    return times.get(day, datetime.combine(day, time(23, 59, 59), tzinfo=UTC))


def latest_listing(events_manifest: Path, slug: str) -> dict[str, Any] | None:
    """The newest kept listing of `slug` in data/events_manifest.json, by its fetched_utc parsed."""
    if not events_manifest.exists():
        return None
    try:
        entries = json.loads(events_manifest.read_text(encoding="utf-8"))
    except ValueError:
        return None
    best: tuple[datetime, dict[str, Any]] | None = None
    for e in entries if isinstance(entries, list) else []:
        if not isinstance(e, dict) or e.get("event_slug") != slug:
            continue
        try:
            at = datetime.strptime(str(e.get("fetched_utc")), UTC_STAMP_FORMAT).replace(tzinfo=UTC)
        except (ValueError, TypeError):
            continue
        if best is None or at > best[0]:
            best = (at, e)
    return best[1] if best else None


# --- the check ----------------------------------------------------------------------------------

@dataclass(frozen=True)
class LegStatus:
    leg: Leg
    status: str  # read | declined | open-unread | settled-unread | not-yet-listed
    detail: str


def coverage(legs: list[Leg], readings: list[dict[str, str]], not_read: list[dict[str, str]],
             view_at: datetime, event_slug: str) -> list[LegStatus]:
    """Each leg's standing as of `view_at`, the instant of the view being checked (its first quote).

    read: readings.csv carries a row for the market (any view; a settled leg that was read once has
          something to score).  declined: not_read.csv names the market for the view's day.
          open-unread: open at `view_at` with neither.  settled-unread: settled by `view_at` with no
          reading at all, the coverage miss.  not-yet-listed: listed after `view_at`."""
    read_ids = {r.get("market_id") for r in readings}
    declined = {(r.get("market_id"), r.get("view_day")) for r in not_read if r.get("event_slug") == event_slug}
    day = view_at.date().isoformat()
    out: list[LegStatus] = []
    for leg in legs:
        if leg.listed is not None and leg.listed > view_at:
            out.append(LegStatus(leg, "not-yet-listed", f"listed {leg.listed:%Y-%m-%d %H:%M}Z"))
        elif leg.market_id in read_ids:
            out.append(LegStatus(leg, "read", "readings.csv"))
        elif leg.open_at(view_at):
            if (leg.market_id, day) in declined:
                out.append(LegStatus(leg, "declined", f"not_read.csv {day}"))
            else:
                out.append(LegStatus(leg, "open-unread", f"open at {view_at:%Y-%m-%d %H:%M}Z, no reading, no not_read row"))
        else:
            out.append(LegStatus(leg, "settled-unread", f"settled {leg.closed_time:%Y-%m-%d %H:%M}Z, no reading"))
    return out


def views_while_open(leg: Leg, times: dict[date, datetime]) -> int:
    """How many views could have read the leg: the view instants at which it was open."""
    return sum(1 for t in times.values() if leg.open_at(t))


def summary(statuses: list[LegStatus]) -> dict[str, int]:
    counts = {k: 0 for k in ("read", "declined", "open-unread", "settled-unread", "not-yet-listed")}
    for s in statuses:
        counts[s.status] += 1
    return counts


# --- subcommands --------------------------------------------------------------------------------

def http_get(url: str) -> bytes:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "qune-research/0.1 (public research; event listing; "
                                                             "pm-view/event_coverage.py)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def fetch(slug: str, fetcher: Fetcher, raw_dir: Path, events_manifest: Path, now: datetime, root: Path) -> dict[str, Any]:
    """One listing: raw body under raw_dir/<time>/ (git-ignored), one manifest entry with its hash."""
    body = fetcher(GAMMA_EVENTS + slug)
    event, legs = legs_of(body)
    stamp = now.strftime(UTC_STAMP_FORMAT)
    folder = raw_dir / stamp.replace(":", "")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"event_{slug}.json"
    path.write_bytes(body)
    entry = {"event_slug": slug, "event_id": str(event.get("id")), "fetched_utc": stamp, "bytes": len(body),
             "sha256": hashlib.sha256(body).hexdigest(), "legs": len(legs),
             "legs_settled": sum(1 for g in legs if g.settled), "raw": str(path.resolve().relative_to(root.resolve())),
             # 2026-11-14: how many legs' rules open their window at the month's start, at the market's creation, or
             # in words the classifier does not know (a count per word, never the text)
             "rules_windows": {w: sum(1 for g in legs if g.rules_window == w) for w in ("month", "creation", "unknown")},
             "source": "Polymarket Gamma /events?slug=<slug>"}
    entries: list[dict[str, Any]] = []
    if events_manifest.exists():
        entries = json.loads(events_manifest.read_text(encoding="utf-8"))
    entries.append(entry)
    events_manifest.parent.mkdir(parents=True, exist_ok=True)
    events_manifest.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return entry


def listing_days(events_manifest: Path, slug: str) -> set[date]:
    """The days on which a listing of `slug` was fetched."""
    if not events_manifest.exists():
        return set()
    try:
        entries = json.loads(events_manifest.read_text(encoding="utf-8"))
    except ValueError:
        return set()
    days: set[date] = set()
    for e in entries if isinstance(entries, list) else []:
        if isinstance(e, dict) and e.get("event_slug") == slug:
            try:
                days.add(datetime.strptime(str(e.get("fetched_utc")), UTC_STAMP_FORMAT).date())
            except (ValueError, TypeError):
                continue
    return days


def load_legs(entry: dict[str, Any], root: Path) -> list[Leg] | None:
    """The legs of a kept listing; None when the raw body is not on this machine (git-ignored)."""
    path = root / str(entry.get("raw"))
    if not path.exists():
        return None
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != entry.get("sha256"):
        raise ValueError(f"{path} does not match the hash the manifest logged")
    return legs_of(body)[1]


def manifest_entries_of(manifest: Path) -> list[dict[str, Any]]:
    try:
        entries = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
    except ValueError:
        entries = []
    return entries if isinstance(entries, list) else []


def check(events: Path, events_manifest: Path, readings: Path, not_read: Path, manifest: Path, at: datetime,
          root: Path, out: Callable[[str], None] = print) -> tuple[int, dict[str, dict[str, int]]]:
    rows = read_csv(events)
    if not rows:
        out(f"coverage: no events followed ({events})")
        return 0, {}
    readings_rows = read_csv(readings)
    not_read_rows = read_csv(not_read)
    times = view_times(manifest_entries_of(manifest))
    rc = 0
    totals: dict[str, dict[str, int]] = {}
    for ev in rows:
        slug = ev["event_slug"]
        entry = latest_listing(events_manifest, slug)
        if entry is None:
            out(f"coverage {slug}: no listing kept (run `event_coverage.py fetch {slug}`)")
            rc = 1
            continue
        legs = load_legs(entry, root)
        if legs is None:
            out(f"coverage {slug}: listing {entry['fetched_utc']} kept but its raw body is not on this machine")
            continue
        statuses = coverage(legs, readings_rows, not_read_rows, at, slug)
        out(f"coverage {slug}: listing fetched {entry['fetched_utc']}, {len(legs)} legs, as of {at:%Y-%m-%dT%H:%M:%S}Z")
        for s in sorted(statuses, key=lambda s: (s.status, s.leg.question, s.leg.market_id)):
            extra = f", views while open {views_while_open(s.leg, times)}" if s.status == "settled-unread" else ""
            window = f", rules window {s.leg.rules_window}" + (
                f" from {s.leg.created:%Y-%m-%dT%H:%M:%SZ}" if s.leg.rules_window == "creation" and s.leg.created else "")
            out(f"  {s.status:14s} {s.leg.market_id} {s.leg.question} ({s.detail}{extra}{window})")
        counts = summary(statuses)
        totals[slug] = counts
        out("  summary: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
        if counts["open-unread"] or counts["settled-unread"]:
            rc = 1
    return rc, totals


def record(events: Path, events_manifest: Path, readings: Path, not_read: Path, manifest: Path, misses: Path,
           at: datetime, root: Path, dry_run: bool, out: Callable[[str], None] = print) -> int:
    """Append each settled-unread leg not yet on coverage_misses.csv; a leg is recorded once by market id."""
    existing = {r.get("market_id") for r in read_csv(misses)}
    readings_rows = read_csv(readings)
    not_read_rows = read_csv(not_read)
    times = view_times(manifest_entries_of(manifest))
    written = 0
    for ev in read_csv(events):
        slug = ev["event_slug"]
        entry = latest_listing(events_manifest, slug)
        if entry is None:
            out(f"record {slug}: no listing kept; nothing recorded")
            continue
        legs = load_legs(entry, root)
        if legs is None:
            out(f"record {slug}: raw listing not on this machine; nothing recorded")
            continue
        for s in coverage(legs, readings_rows, not_read_rows, at, slug):
            if s.status != "settled-unread" or s.leg.market_id in existing:
                continue
            row = {"event_slug": slug, "market_id": s.leg.market_id, "question": s.leg.question,
                   "listed_utc": s.leg.listed.strftime(UTC_STAMP_FORMAT) if s.leg.listed else "",
                   "settled_utc": s.leg.closed_time.strftime(UTC_STAMP_FORMAT) if s.leg.closed_time else "",
                   "outcome_prices": s.leg.outcome_prices or "", "views_while_open": views_while_open(s.leg, times),
                   "noted_on": at.date().isoformat(), "listing_sha256": entry["sha256"]}
            out(("would record " if dry_run else "recorded ") + f"{slug} {row['market_id']} {row['question']} "
                f"settled {row['settled_utc']} views while open {row['views_while_open']}")
            if not dry_run:
                append_row(misses, MISSES_COLUMNS, row)
                existing.add(s.leg.market_id)
            written += 1
    out(f"record: {written} coverage miss(es) {'would be ' if dry_run else ''}written to {misses.name}")
    return 0


def decline(events: Path, events_manifest: Path, root: Path, not_read: Path, market_id: str, view_day: date,
            why: str, now: datetime, out: Callable[[str], None] = print) -> int:
    """One not_read row for a leg the view saw and chose not to read. The leg must be in the newest
    kept listing of a followed event (so a typo cannot be declined), the reason must say something,
    and a leg already declined for that view day is not written twice."""
    if not why or len(why.strip()) < 12:
        out("decline: refused; --why must say why the leg was not read (at least twelve characters)")
        return 2
    if not market_id.strip().isdigit():
        out("decline: refused; the market id is the venue's numeric id")
        return 2
    slug = None
    for ev in read_csv(events):
        entry = latest_listing(events_manifest, ev["event_slug"])
        legs = load_legs(entry, root) if entry else None
        if legs and any(g.market_id == market_id for g in legs):
            slug = ev["event_slug"]
            break
    if slug is None:
        out(f"decline: refused; {market_id} is not a leg of any followed event's newest kept listing")
        return 2
    rows = read_csv(not_read)
    if any(r.get("market_id") == market_id and r.get("view_day") == view_day.isoformat() for r in rows):
        out(f"decline: {market_id} already declined for {view_day}; nothing written")
        return 0
    append_row(not_read, NOT_READ_COLUMNS, {"event_slug": slug, "market_id": market_id,
                                            "view_day": view_day.isoformat(), "why": why.strip(),
                                            "recorded_utc": now.strftime(UTC_STAMP_FORMAT)})
    out(f"declined {market_id} for {view_day}: {why.strip()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", type=Path, default=HERE / "events.csv")
    ap.add_argument("--events-manifest", type=Path, default=HERE / "data" / "events_manifest.json")
    ap.add_argument("--raw-dir", type=Path, default=HERE / "data" / "raw" / "events")
    ap.add_argument("--readings", type=Path, default=HERE / "readings.csv")
    ap.add_argument("--not-read", type=Path, default=HERE / "not_read.csv")
    ap.add_argument("--manifest", type=Path, default=HERE / "data" / "manifest.json")
    ap.add_argument("--misses", type=Path, default=HERE / "coverage_misses.csv")
    ap.add_argument("--root", type=Path, default=HERE, help="folder the manifest's raw paths are relative to")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("slug")
    c = sub.add_parser("check")
    c.add_argument("--at", type=date.fromisoformat, default=None,
                   help="as of that day's first quote (or its end when no view was written that day); default now")
    r = sub.add_parser("record")
    r.add_argument("--at", type=date.fromisoformat, default=None)
    r.add_argument("--dry-run", action="store_true")
    d = sub.add_parser("decline")
    d.add_argument("market_id")
    d.add_argument("--view", type=date.fromisoformat, required=True)
    d.add_argument("--why", required=True)
    a = ap.parse_args(argv)
    now = datetime.now(UTC)
    at = view_at_on(a.at, view_times(manifest_entries_of(a.manifest))) if getattr(a, "at", None) else now
    if a.cmd == "fetch":
        entry = fetch(a.slug, http_get, a.raw_dir, a.events_manifest, now, a.root)
        print(f"fetched {a.slug}: {entry['legs']} legs ({entry['legs_settled']} settled), {entry['bytes']} bytes, "
              f"sha256 {entry['sha256'][:12]}…, {entry['fetched_utc']}, raw {entry['raw']} (git-ignored)")
        return 0
    if a.cmd == "check":
        return check(a.events, a.events_manifest, a.readings, a.not_read, a.manifest, at, a.root)[0]
    if a.cmd == "record":
        return record(a.events, a.events_manifest, a.readings, a.not_read, a.manifest, a.misses, at, a.root, a.dry_run)
    if a.cmd == "decline":
        return decline(a.events, a.events_manifest, a.root, a.not_read, a.market_id, a.view, a.why, now)
    return 2


if __name__ == "__main__":
    sys.exit(main())
