"""Prediction-market view: the pure functions behind the ledger, the quote and the score.

Why this folder exists (BACKLOG PM5, 2026-11-03): the rates desk view logs calls
against a market-anchored baseline that it has to construct from bills and
forwards.  On a prediction market the baseline is the market itself: the mid of
the best bid and ask on the YES token is a probability, read at the time of the
call.  So the discipline adopted after the V1 miss (predictions/POST_MORTEMS.md,
2026-10-30) becomes simpler and stricter here:

  - the market's probability is read and written down before the desk's;
  - a call is logged only when the desk's probability differs from the market
    mid by at least MIN_DEPARTURE, and its basis names the market's number and
    says in one testable sentence what the market is missing.  Nearer than
    that the desk has nothing to add and says so in the view instead;
  - every call is scored by Brier against the market mid at the time of the
    call, on the venue's own settlement, by the same outcome rule Study 013
    pre-registered (research/013-polymarket-calibration-forward, §6.5).

Eligibility mirrors Study 013's §6.3 (same floors, same order), so a market the
study would not count is not one the desk calls either: a binary market with an
order book, open and accepting orders, resolution not begun, scheduled end in
the future, a two-sided book with spread at most SPREAD_CAP, mid inside
[0.01, 0.99] and cumulative volume of at least VOLUME_FLOOR USDC.

Nothing here reads a file or the network; fetch.py and score.py do that and
pass the rows in.  The functions are tested on dicts built in memory.  One
exception, by design (2026-11-08): `record_calibration_line` reads a written
calibration file and appends its line to data/calibration_history.csv, so the
calibration scripts and readings.py record-calibration share one writer.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

MIN_DEPARTURE = 0.10  # |desk p - market mid| below this: no call
VOLUME_FLOOR = 10_000.0  # USDC, cumulative, as Study 013 §6.3
SPREAD_CAP = 0.10
RESOLUTION_BEGUN = ("proposed", "disputed", "resolved")

LEDGER_COLUMNS = (
    "id", "made_on", "venue", "market_id", "condition_id", "yes_token_id", "proposition", "settles_on",
    "due_on", "market_mid", "market_spread", "volume_usdc", "desk_p",
    "method", "method_p", "range_lo", "range_hi",  # added 2026-11-06: the method gate on the committed row
    "basis", "quote_sha256",
)
VENUE = "polymarket"  # the one venue a row may name (tools/pm_data_terms.md); one constant for both tools (2026-11-08)
MIN_SETTLES_ON_CHARS = 20  # the resolution rule restated: source and measure, not the title

# The methods a call may rest on, and where each one's calibration gate (rule R2:
# the method beats its dumb baseline on its own history, or it is no basis for a
# call) is written.  Added 2026-11-06 (predictions/POST_MORTEMS.md, "A call gate
# that knew one rule of three"): until then README rule 2 stated the R2 gate and
# the range rule, barrier.py and fomc_calibrate.py printed them as advice and
# never wrote a call, and the only check on the committed ledger was the 0.10
# departure plus `settles_on`, so a hand-written row could pass every test while
# breaking two of the three rules.  `stated` is the README's other path, a
# reason outside any method (a data release, written before the market moves on
# it); it carries no method reading and no gate beyond the departure, and the
# ledger shows that plainly.
METHODS = ("fomc_bills", "btc_touch", "stated")
METHOD_CALIBRATION = {  # method -> (calibration file under pm-view/, the R2 key in its "rules")
    "fomc_bills": ("data/fomc_calibration.json", "R2_basis_for_a_call"),
    "btc_touch": ("data/calibration.json", "R2_method_is_a_basis_for_a_call"),
}
BELOW_MARKET_NEVER = ("btc_touch",)  # a reading below the market is in the direction of the one-minute gap: never a call

# The gate's rule tags (2026-11-06 12:15Z, predictions/POST_MORTEMS.md "A rule in
# prose, a check elsewhere: the mechanical search").  Every reason the gate can
# give for refusing a call carries one of these tags, and README.md rule 2 carries
# the same tag beside the sentence that states the rule.  tests/test_rule_tags.py
# holds the three lists equal (prose, this tuple, the reasons the gate actually
# emits), so a rule written in prose without a check, or a check without its
# prose, fails a test instead of waiting for a reader; that is the class of defect
# found three times before this registry existed (the refusal fixed in the newest
# copy only, 31 Oct; the leak scan that read what it could never publish, 5 Nov;
# the ledger gate that knew one rule of three, 6 Nov; all in research/ and
# predictions/ POST_MORTEMS.md).
GATE_TAGS = (
    "probability",         # the desk's number is a probability strictly inside (0, 1)
    "departure",           # the desk's number departs from the market mid by at least MIN_DEPARTURE
    "basis-names-market",  # the basis names the market's probability and what it is missing
    "settles-on",          # the resolution rule restated with source and measure, not the title
    "method-named",        # a call names the method it rests on, one of METHODS
    "stated-bare",         # `stated` carries no method reading and no range
    "calibrated",          # the method's committed calibration says R2 true (missing: refused)
    "range-brackets",      # a method call carries its reading and a range that brackets it inside [0, 1]
    "range",               # the market mid lies outside the reading's range
    "touch-below",         # a touch reading at or below the market is never a call
    "method-departure",    # the method reading departs from the mid by at least MIN_DEPARTURE
    "desk-side",           # the desk's number sits on the reading's side of the market
    "made-on-quote-day",   # a call's made_on is the date of the quote it rests on (quote_day)
    # 2026-11-07 18:15Z: the row's own checks, applied at admission by ledger.py add (ledger_row_violations)
    "written-quote",       # the row's quote_sha256 is the book hash of a written manifest entry for its market and ids
    "mid-from-quote",      # the row's market_mid equals the written quote's, copied not retyped
    "eligible-at-quote",   # the market was eligible at the quote
    "rules-on-record",     # the quote recorded the hash of the market's own resolution text
    "one-per-day",         # one call per market and day
    # 2026-11-08 06:15Z: the calibration a call is admitted under, applied at admission only (admitted_utc given)
    "calibration-on-record",    # the committed calibration file is its method's latest line of the history
    "calibration-since-quote",  # no calibration of the method went into force between the quote and the call
    # 2026-11-08 12:15Z (predictions/POST_MORTEMS.md "Five columns the gate never read"): the rest of what the
    # tool copies from the quote or sets itself, held by the gate so the committed-file test holds them too
    "due-on-scheduled-end",     # due_on is the quote's scheduled end date (the day score.py treats the call as due)
    "book-from-quote",          # market_spread and volume_usdc are the written quote's, copied not retyped
    "id-rule",                  # the id is call_id(made_on, method, market_id) and the venue is VENUE
    # 2026-11-09 12:15Z (predictions/POST_MORTEMS.md "A calibration put after the quote by a space"): every
    # stamp the gate reads is parsed in UTC_STAMP_FORMAT before it is compared; another format refuses the row
    "utc-stamp",                # the quote's fetched_utc, the admission time and the history's in_force_utc parse
)
GATE_TAG_RE = re.compile(r"\[gate:([a-z-]+)\]")


def gate(tag: str, reason: str) -> str:
    """A refusal of the call gate with its rule tag in front, `[gate:<tag>] <reason>`."""
    if tag not in GATE_TAGS:
        raise ValueError(f"unknown gate tag {tag!r}; add it to GATE_TAGS and to README.md rule 2")
    return f"[gate:{tag}] {reason}"


def gate_tags(text: str) -> set[str]:
    """The gate tags written in a text (a README, a source file, a list of refusals joined)."""
    return set(GATE_TAG_RE.findall(text))


def quote_day(fetched_utc: object) -> str:
    """The UTC date `YYYY-MM-DD` of a quote's `fetched_utc` (`YYYY-MM-DDTHH:MM:SSZ`), the day a call or a
    reading resting on it is made; empty for no time or for a stamp in another format (stamp_violation
    names it).  Both gates compare dates through this one function, never a timestamp with a date as
    strings (2026-11-07 12:15Z, predictions/POST_MORTEMS.md "A timestamp compared with a date":
    `"2026-11-06T06:16:38Z" <= "2026-11-06"` is False).  Since 2026-11-09 12:15Z the stamp is parsed, not
    sliced: `"06/11/2026 06:20Z"[:10]` was `06/11/2026`, a day that is never `made_on`, refused with the
    reason "the quote's mid is stale"."""
    text = str(fetched_utc or "")
    if not text:
        return ""
    try:
        return parse_utc_stamp(text).date().isoformat()
    except ValueError:
        return ""


def stamp_violation(fetched_utc: object) -> str | None:
    """Why a quote's `fetched_utc` cannot be judged against, or None when it is a UTC stamp in
    UTC_STAMP_FORMAT: no time, or text in another format.  One sentence both gates print."""
    text = str(fetched_utc or "")
    if not text:
        return "the quote has no fetch time on record"
    try:
        parse_utc_stamp(text)
    except ValueError:
        return (f"the quote's fetched_utc {text!r} is not a UTC stamp YYYY-MM-DDTHH:MM:SSZ: fix data/manifest.json, "
                "nothing is compared as text")
    return None


def quote_timing_violations(made_on: str, fetched_utc: object) -> list[str]:
    """The call gate's rule on when a call is made: on its quote's day.  The row carries that quote's mid
    and the departure is measured against it, so a mid from an earlier day is stale and a quote from a
    later day was read after the call was made."""
    bad = stamp_violation(fetched_utc)
    if bad:
        return [gate("made-on-quote-day", f"made_on {made_on}: {bad}")]
    day = quote_day(fetched_utc)
    if day == made_on:
        return []
    why = "the quote was read after the call was made" if day > made_on else "the quote's mid is stale"
    return [gate("made-on-quote-day", f"made_on {made_on} is not the quote's day {day}: {why}; "
                                      "a call is made on the day of its quote")]


OUTCOME_COLUMNS = (
    "id", "scored_on", "kind", "y", "desk_p", "market_mid", "brier_desk", "brier_market",
    "gamma_sha256", "clob_sha256",
)

# --- The readings record (added 2026-11-06 18:15Z, predictions/POST_MORTEMS.md
# "A week of readings that no record could score") -------------------------------
#
# A call is rare by design (the gate above), so the ledger alone would take years
# to say whether a method's reading carries information against the market.  The
# readings record keeps, per view, each method reading beside the market mid it
# was read against, and score.py scores both on the venue's settlement by the
# same §6.5 rule as a call.  It is information, not a call: nothing in it is a
# position, and SKILL.md says so.  A row is admitted only on a quote that
# fetch.py wrote to data/manifest.json while the market was eligible, with the
# mid copied from that entry; a reading made on a dry-run quote has no hash and
# is not on the record.  That rule is what kept three of the week's five
# readings off this file on the day it was created, among them the one case
# that had already settled (the 80,000 touch market, read 0.607 against 0.805
# three hours before it resolved YES on 4 November): the quote behind it was
# a dry run.  The record starts where the written quotes start.
READING_COLUMNS = (
    "id", "made_on", "recorded_utc", "venue", "market_id", "condition_id", "yes_token_id", "proposition",
    "method", "method_p", "range_lo", "range_hi", "market_mid", "climatology_p", "due_on", "gate",
    "quote_fetched_utc", "quote_sha256", "source",
)
READING_OUTCOME_COLUMNS = (
    "id", "scored_on", "kind", "y", "method_p", "market_mid", "climatology_p",
    "brier_method", "brier_market", "brier_climatology", "gamma_sha256", "clob_sha256",
)
READING_METHODS = tuple(m for m in METHODS if m in METHOD_CALIBRATION)  # a reading comes from a method, never `stated`

# The readings gate's rule tags (2026-11-07 00:15Z, the second run of the mechanical
# search of 2026-11-06 12:15Z, extended to the second action this folder admits: a
# row to readings.csv).  Same shape as GATE_TAGS, a separate namespace so a rule
# about a reading and a rule about a call cannot be confused: every refusal
# reading_violations gives carries `[reading:<tag>]` from this tuple, README.md
# rule 5 carries the same tag beside the sentence that states the rule, and
# tests/test_rule_tags.py holds the prose, the declaration and the emitted set
# equal.  What the extension found on the day it was written: three checks the
# gate made that rule 5 never stated (the mid a probability, the climatology a
# probability, due_on the scheduled end) and one rule the prose stated whose
# check sat in readings.py, not in the gate (one reading per method, market and
# day); the sentences were added and the check moved here.
READING_TAGS = (
    "from-a-method",            # a reading comes from a method with a calibration file, never `stated`
    "range-brackets",           # the reading and its range are probabilities in [0, 1] with lo <= p <= hi
    "mid-probability",          # the market mid is a probability inside (0, 1)
    "climatology-probability",  # the climatological probability, when given, is in [0, 1]
    "written-quote",            # the quote is a written manifest entry (a --dry-run quote leaves none)
    "mid-from-quote",           # the mid equals the written quote's, copied not retyped
    "eligible-at-quote",        # the market was eligible at the quote (open, before any settlement)
    "made-on-quote-day",        # the reading is made on the day of its quote
    "due-on-scheduled-end",     # due_on is the quote's scheduled end date
    "one-per-day",              # one reading per method, market and view day
    "calibration-on-record",    # the method's calibration in force at recorded_utc is a line of data/calibration_history.csv
    "gate-column",              # the gate column is the call gate's tags under that calibration, not today's
    # 2026-11-09 00:15Z, predictions/POST_MORTEMS.md "A readings gate that never saw the row": the row's own columns
    "id-rule",                  # the id is R-<made_on>-<method>-<market_id> and the venue is VENUE
    "recorded-after-quote",     # recorded_utc is a UTC stamp YYYY-MM-DDTHH:MM:SSZ not before the quote's fetch
    # 2026-11-09 12:15Z (predictions/POST_MORTEMS.md "A calibration put after the quote by a space"): every
    # stamp the gate reads is parsed in UTC_STAMP_FORMAT before it is compared; another format refuses the row
    "utc-stamp",                # the quote's fetched_utc and the history's in_force_utc parse
)
UTC_STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"  # the one format of every UTC stamp this folder writes: fetched_utc, recorded_utc, in_force_utc
RECORDED_UTC_FORMAT = UTC_STAMP_FORMAT  # the readings gate's name for it (2026-11-09 00:15Z); parsed, never compared as text (12:15Z)


def parse_utc_stamp(stamp: object, what: str = "stamp") -> datetime:
    """The time of a UTC stamp in UTC_STAMP_FORMAT; ValueError naming `what` for any other text.

    2026-11-09 06:15Z, predictions/POST_MORTEMS.md "A call with no path to being due before its
    scheduled end": the path that makes a reading due on a later settlement quote compared the
    manifest's `fetched_utc` with the row's `quote_fetched_utc` as text, and nothing held the
    manifest's format, so a settlement quote stamped `06/11/2026 06:20Z` compared as earlier than
    every row's quote and was ignored.  Stamps on that path are parsed here, never compared as
    text; another format is a defect to fix, not a comparison to make."""
    text = str(stamp or "")
    try:
        return datetime.strptime(text, UTC_STAMP_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        raise ValueError(f"{what} {text!r} is not a UTC stamp YYYY-MM-DDTHH:MM:SSZ") from None


def settlement_quote_day(market_id: str, after_utc: object, entries: Iterable[dict[str, Any]]) -> date | None:
    """The UTC date of the earliest written quote of `market_id` in data/manifest.json that carries a
    `settlement` and was fetched after `after_utc` (the row's own quote; None or empty: any settlement
    quote of the market counts), or None when there is none.  Every stamp read is parsed with
    parse_utc_stamp; a manifest stamp in another format raises ValueError."""
    after = parse_utc_stamp(after_utc, "the row's quote_fetched_utc") if after_utc else None
    days: list[date] = []
    for e in entries:
        if str(e.get("market_id", "")) != str(market_id) or not e.get("settlement"):
            continue
        fetched = parse_utc_stamp(e.get("fetched_utc"), f"data/manifest.json fetched_utc of market {market_id}")
        if after is None or fetched > after:
            days.append(fetched.date())
    return min(days) if days else None


def earliest_scoring_day(due_on: str, market_id: str, after_utc: object, entries: Iterable[dict[str, Any]]) -> date:
    """The first UTC day a row of either record (a call on the ledger, a reading on the readings record)
    may be scored: its `due_on`, the market's scheduled end, or the day of an earlier written quote of
    the market carrying its settlement (a market can resolve before its scheduled end, as the 80,000 touch
    market did on 4 November).  One rule for both records: score.py and tools/check_due.py read it from
    here.  Until 2026-11-09 06:15Z a call had the first half only (predictions/POST_MORTEMS.md "A call
    with no path to being due before its scheduled end")."""
    day = date.fromisoformat(str(due_on))
    settled = settlement_quote_day(market_id, after_utc, entries)
    return min(day, settled) if settled is not None else day


def quote_fetched_for_call(call: dict[str, Any], entries: Iterable[dict[str, Any]]) -> str | None:
    """The fetch time of the written quote a ledger row rests on, found by its book hash (`quote_sha256`,
    the ledger's `written-quote` rule); None when no written quote carries that hash, in which case any
    settlement quote of the market counts towards the row's scoring day."""
    sha = str(call.get("quote_sha256", ""))
    if not sha:
        return None
    for e in entries:
        if e.get("book_sha256") == sha:
            return str(e.get("fetched_utc", ""))
    return None

# The calibration history (2026-11-07 06:15Z, predictions/POST_MORTEMS.md "A gate
# column judged against today's calibration").  A reading row's `gate` column is
# the call gate's refusals at admission, and one of them, `calibrated`, depends on
# R2 of the method's calibration file, which a re-run of calibrate.py or
# fomc_calibrate.py overwrites.  Until this date the committed-file test judged
# every row against the file as it stood that day, so a correct re-run that
# flipped R2 would have failed the test on rows that were right when written,
# leaving an edit to an append-only file or a weakened test as the only ways back
# to green; no rule said which calibration a row is judged under, and the row did
# not record it.  Now every calibration that has been in force is one append-only
# line of data/calibration_history.csv (method, the time it went on record, the
# file's SHA-256, its R2), a row is judged under the line in force at its own
# `recorded_utc`, and a reading is admitted only when the committed file is the
# latest line for its method.
CALIBRATION_HISTORY = "data/calibration_history.csv"
CALIBRATION_HISTORY_COLUMNS = ("method", "in_force_utc", "sha256", "r2", "source")


def calibration_in_force(history: Iterable[dict[str, Any]], method: str, at_utc: str) -> dict[str, Any] | None:
    """The calibration_history line for `method` in force at `at_utc`: the last line for the
    method, in file order, whose `in_force_utc` is at or before `at_utc`.  None when no line was
    yet on record.  Both stamps are parsed with parse_utc_stamp (UTC_STAMP_FORMAT); `at_utc` or a
    line of the method in another format raises ValueError naming it (2026-11-09 12:15Z,
    predictions/POST_MORTEMS.md "A calibration put after the quote by a space": until then the two
    were compared as text, and a quote stamped `2026-11-06 06:20:45 UTC` sorted before a line that
    went into force at `2026-11-06T05:00:00Z`, so the ledger gate judged a call under the superseded
    line and lost its `calibrated` refusal)."""
    at = parse_utc_stamp(at_utc, "the time the row is judged at")
    hit: dict[str, Any] | None = None
    for h in history:
        if h.get("method") != method:
            continue
        if parse_utc_stamp(h.get("in_force_utc"), f"{CALIBRATION_HISTORY} in_force_utc of {method}") <= at:
            hit = h
    return hit


def latest_calibration(history: Iterable[dict[str, Any]], method: str) -> dict[str, Any] | None:
    """The last calibration_history line for `method` in file order (the file is append-only and
    dated in order, which tests/test_readings.py holds), or None.  The question "is this file the
    method's latest line" reads no stamp; until 2026-11-09 12:15Z it was asked as
    calibration_in_force(…, "9999"), a sentinel that worked only because stamps were text."""
    hit: dict[str, Any] | None = None
    for h in history:
        if h.get("method") == method:
            hit = h
    return hit


def history_r2(line: dict[str, Any] | None) -> bool | None:
    """R2 of a calibration_history line (`true`/`false`); None for no line or any other value."""
    v = None if line is None else str(line.get("r2", "")).strip().lower()
    return {"true": True, "false": False}.get(v or "")


# Who writes the line (2026-11-08 00:15Z, predictions/POST_MORTEMS.md "A calibration
# that went into force before it was on record"): until this date calibrate.py and
# fomc_calibrate.py overwrote the committed calibration file and the line that puts
# it in force was appended by hand afterwards (readings.py record-calibration, a
# typed source, the time someone remembered), so between the two the printers read
# R2 from the file and the admission tools from the history.  Now the script that
# writes the file calls this function on the file it has just written; the readings
# tool calls it as the repair path for a file written by any other route.
def record_calibration_line(history_path: Path, method: str, calibration_path: Path, now: datetime,
                            source: str) -> tuple[str, dict[str, Any] | None]:
    """Put the written calibration file of `method` on record in `history_path`.
    The hash and R2 are read from the file's bytes as written (`method_gate`, the
    function the gates use), never from a caller's summary.  Returns ('recorded',
    the appended line); ('unchanged', the method's latest line) when the file's
    SHA-256 is already that line, appending nothing; ('refused', None) when the
    file is missing or carries no R2, appending nothing."""
    if method not in METHOD_CALIBRATION or not calibration_path.exists():
        return "refused", None
    body = calibration_path.read_bytes()
    try:
        cal = json.loads(body.decode("utf-8"))
    except ValueError:
        return "refused", None
    r2 = method_gate(method, cal)
    if r2 is None:
        return "refused", None
    sha = hashlib.sha256(body).hexdigest()
    history: list[dict[str, Any]] = []
    if history_path.exists():
        with history_path.open(encoding="utf-8", newline="") as fh:
            history = list(csv.DictReader(fh))
    latest = latest_calibration(history, method)
    if latest is not None and latest.get("sha256") == sha:
        return "unchanged", latest
    line = {"method": method, "in_force_utc": now.strftime(UTC_STAMP_FORMAT), "sha256": sha,
            "r2": "true" if r2 else "false", "source": source}
    new = not history_path.exists()
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(CALIBRATION_HISTORY_COLUMNS), lineterminator="\n")  # as committed
        if new:
            w.writeheader()
        w.writerow(line)
    return "recorded", line


def gate_column(method: str, method_p: float | None, range_lo: float | None, range_hi: float | None,
                market_mid: float | None, r2: bool | None) -> str:
    """The readings.csv `gate` column: the call gate's refusal tags for the numbers, sorted, or `open`."""
    if market_mid is None:
        return ""
    tags = gate_tags(" ".join(method_violations(method, method_p, range_lo, range_hi, market_mid, r2)))
    return ";".join(sorted(tags)) or "open"
READING_TAG_RE = re.compile(r"\[reading:([a-z-]+)\]")


def reading_gate(tag: str, reason: str) -> str:
    """A refusal of the readings gate with its rule tag in front, `[reading:<tag>] <reason>`."""
    if tag not in READING_TAGS:
        raise ValueError(f"unknown reading tag {tag!r}; add it to READING_TAGS and to README.md rule 5")
    return f"[reading:{tag}] {reason}"


def reading_tags(text: str) -> set[str]:
    """The reading tags written in a text (a README, a source file, a list of refusals joined)."""
    return set(READING_TAG_RE.findall(text))


def reading_id(made_on: str, method: str, market_id: str) -> str:
    """The readings.csv id: one per method, market and view day."""
    return f"R-{made_on}-{method}-{market_id}"


def reading_violations(method: str, method_p: float | None, range_lo: float | None, range_hi: float | None,
                       market_mid: float | None, climatology_p: float | None, quote: dict[str, Any] | None,
                       made_on: str, due_on: str, market_id: str = "",
                       existing_ids: Iterable[str] = (), gate_col: str | None = None,
                       calibration: dict[str, Any] | None = None,
                       calibration_sha256: str | None = None) -> list[str]:
    """What stops a reading row from being admitted to readings.csv; empty when it may be.
    Each reason carries its `[reading:<tag>]` (READING_TAGS; the same tag sits beside the
    rule in README.md rule 5).

    1. the method is one with a calibration file (READING_METHODS; `stated` has no reading);
    2. the reading and its range are probabilities in [0, 1] with lo <= p <= hi;
    3. the market mid is a probability inside (0, 1) and equals the quote's mid;
    4. the quote is a written manifest entry for this market, fetched on `made_on`,
       with the market eligible at the fetch (so the reading was made while the
       market was open, before any settlement);
    5. the climatological probability, when given, is a probability in [0, 1];
    6. `due_on` is the quote's scheduled end date (the day the row becomes due);
    7. one reading per method, market and view day: when `market_id` is given, the
       row's id is not among `existing_ids` (the ids already on the record);
    8. (2026-11-07 06:15Z) when the row's `gate` column is given (`gate_col`): `calibration`, the
       method's line of data/calibration_history.csv in force at the row's
       recorded_utc (calibration_in_force), exists, and at admission
       (`calibration_sha256`, the SHA-256 of the committed calibration file as
       read) it is that file; and the `gate` column is the call gate's tags under
       that line's R2, so a later re-run of the calibration leaves the row right."""
    out: list[str] = []
    if gate_col is not None:
        if calibration is None:
            out.append(reading_gate("calibration-on-record", f"no line for {method} in {CALIBRATION_HISTORY} in force "
                                    "when the row was recorded: the calibration script records its line when it "
                                    "writes the file; readings.py record-calibration is the repair path"))
        elif calibration_sha256 is not None and calibration_sha256 != calibration.get("sha256"):
            out.append(reading_gate("calibration-on-record", f"the committed calibration of {method} "
                                    f"(SHA-256 {calibration_sha256[:12]}…) is not its latest line in "
                                    f"{CALIBRATION_HISTORY}: the file was written by a route that did not record it; "
                                    "put it on record (readings.py record-calibration) before a reading is "
                                    "admitted under it"))
        want = gate_column(method, method_p, range_lo, range_hi, market_mid, history_r2(calibration))
        if want and gate_col != want:
            out.append(reading_gate("gate-column", f"gate column {gate_col!r} is not the call gate's {want!r} under the "
                                    "calibration in force when the row was recorded"))
    if method not in READING_METHODS:
        out.append(reading_gate("from-a-method",
                                f"method must be one of {', '.join(READING_METHODS)}: a reading comes from a method"))
    if method_p is None or range_lo is None or range_hi is None:
        out.append(reading_gate("range-brackets", "method_p, range_lo and range_hi are required"))
    elif not (0.0 <= range_lo <= method_p <= range_hi <= 1.0):
        out.append(reading_gate("range-brackets", f"the range [{range_lo:.3f}, {range_hi:.3f}] must bracket "
                                f"the reading {method_p:.3f} inside [0, 1]"))
    if market_mid is None or not (0.0 < market_mid < 1.0):
        out.append(reading_gate("mid-probability", "market_mid is not a probability inside (0, 1)"))
    if climatology_p is not None and not (0.0 <= climatology_p <= 1.0):
        out.append(reading_gate("climatology-probability", "climatology_p is not a probability"))
    if market_id and reading_id(made_on, method, market_id) in set(existing_ids):
        out.append(reading_gate("one-per-day", f"{reading_id(made_on, method, market_id)} is already on the record "
                                "(one reading per method, market and day)"))
    if quote is None:
        out.append(reading_gate("written-quote", "no written quote: the row's quote_sha256 is not a gamma_sha256 in "
                                "data/manifest.json (a --dry-run quote leaves no record; re-quote without it)"))
        return out
    qmid = as_float(quote.get("market_mid"))
    if market_mid is not None and (qmid is None or abs(qmid - market_mid) > 1e-9):
        out.append(reading_gate("mid-from-quote",
                                f"market_mid {market_mid} differs from the quote's {qmid}: copy the mid from the quote"))
    if quote.get("eligibility") != "eligible":
        out.append(reading_gate("eligible-at-quote", f"the market was not eligible at the quote "
                                f"({quote.get('eligibility')}): a reading on a market the record excludes is not "
                                "scored against its settlement"))
    bad_stamp = stamp_violation(quote.get("fetched_utc"))
    if bad_stamp:
        out.append(reading_gate("made-on-quote-day", f"made_on {made_on}: {bad_stamp}"))
    elif quote_day(quote.get("fetched_utc")) != made_on:
        out.append(reading_gate("made-on-quote-day", f"made_on {made_on} is not the quote's date "
                                f"{quote_day(quote.get('fetched_utc'))}: a reading is made on the day of its quote"))
    end = str(quote.get("end_date", ""))
    if end[:10] != due_on:
        out.append(reading_gate("due-on-scheduled-end",
                                f"due_on {due_on} is not the quote's scheduled end {end[:10]}"))
    return out


def reading_row_violations(row: dict[str, Any], quote: dict[str, Any] | None, history: Iterable[dict[str, Any]],
                           existing_ids: Iterable[str] = (), calibration_sha256: str | None = None) -> list[str]:
    """What stops a readings.csv row, as written, from being admitted; empty when it may be.
    `row` is the row (strings, or the values readings.py is about to write); `quote` the
    data/manifest.json entry its `quote_sha256` names (None: no written quote); `history`
    the lines of data/calibration_history.csv; `existing_ids` the ids already on the record;
    `calibration_sha256` the committed calibration file's hash as read, at admission only.

    The row's own columns first (2026-11-09 00:15Z, predictions/POST_MORTEMS.md "A readings
    gate that never saw the row"): until this date reading_violations judged the row's numbers
    and never saw the row, so of the twelve columns readings.py add copies from the quote or
    sets itself the gate held five, tests/test_readings.py held five more in assertions of its
    own (never at admission, no tag) and nothing held `venue` or `recorded_utc`, the stamp that
    names the calibration a row is judged under.  Now: the quote's record hash, market,
    condition and YES token ids and fetch time are the written quote's (`written-quote`); the
    id is reading_id of the row's own columns and the venue is VENUE (`id-rule`);
    `recorded_utc` is a UTC stamp in RECORDED_UTC_FORMAT not before the quote's fetch
    (`recorded-after-quote`), because calibration_in_force compares it with `in_force_utc` as
    text, which is right only while both carry one format.  Then reading_violations on the
    numbers, under the calibration line in force at the row's `recorded_utc`."""
    out: list[str] = []
    method, made_on, market_id = str(row.get("method", "")), str(row.get("made_on", "")), str(row.get("market_id", ""))
    want_id = reading_id(made_on, method, market_id)
    if str(row.get("id", "")) != want_id:
        out.append(reading_gate("id-rule", f"id {row.get('id')} is not {want_id} (R-<made_on>-<method>-<market_id>)"))
    if str(row.get("venue", "")) != VENUE:
        out.append(reading_gate("id-rule", f"venue {row.get('venue')!r} is not {VENUE!r}, the one venue the view quotes"))
    recorded = str(row.get("recorded_utc", ""))
    recorded_at: datetime | None
    try:
        recorded_at = parse_utc_stamp(recorded, "recorded_utc")
    except ValueError:
        recorded_at = None
        out.append(reading_gate("recorded-after-quote", f"recorded_utc {recorded!r} is not a UTC stamp "
                                "YYYY-MM-DDTHH:MM:SSZ: the row is judged under the calibration in force at this time"))
    if quote is not None:
        if str(quote.get("gamma_sha256", "")) != str(row.get("quote_sha256", "")):
            out.append(reading_gate("written-quote", "quote_sha256 is not the record hash (gamma_sha256) of the written "
                                    "quote: copy it from the quote"))
        for k in ("market_id", "condition_id", "yes_token_id"):
            if str(quote.get(k, "")) != str(row.get(k, "")):
                out.append(reading_gate("written-quote", f"{k} differs from the written quote's: copy it from the quote"))
        fetched = str(quote.get("fetched_utc", ""))
        if str(row.get("quote_fetched_utc", "")) != fetched:
            out.append(reading_gate("written-quote", f"quote_fetched_utc {row.get('quote_fetched_utc')} is not the "
                                    f"written quote's fetch time {fetched}: copy it from the quote"))
        # 2026-11-09 12:15Z: both stamps parsed before they are ordered; until then `recorded < fetched` as text,
        # and a quote stamped with a space for the T let a reading recorded before its quote pass
        bad_stamp = stamp_violation(fetched)
        if bad_stamp:
            out.append(reading_gate("utc-stamp", f"{bad_stamp}; the row cannot be judged against this quote"))
            return out
        if recorded_at is not None and recorded_at < parse_utc_stamp(fetched):
            out.append(reading_gate("recorded-after-quote", f"recorded_utc {recorded} is before the quote's fetch at "
                                    f"{fetched}: a reading is recorded after its quote"))
    clim_raw = row.get("climatology_p")
    climatology_p = None if clim_raw in (None, "") else as_float(clim_raw)
    try:
        calibration = calibration_in_force(history, method, recorded) if recorded_at is not None else None
    except ValueError as e:  # a history line of this method in another format
        out.append(reading_gate("utc-stamp", f"{e}: fix the line, nothing is compared as text"))
        return out
    out.extend(reading_violations(method, as_float(row.get("method_p")), as_float(row.get("range_lo")),
                                  as_float(row.get("range_hi")), as_float(row.get("market_mid")), climatology_p, quote,
                                  made_on, str(row.get("due_on", "")), market_id=market_id, existing_ids=existing_ids,
                                  gate_col=str(row.get("gate", "")), calibration=calibration,
                                  calibration_sha256=calibration_sha256))
    return out


def reading_file_violations(rows: list[dict[str, Any]], manifest: Iterable[dict[str, Any]],
                            history: Iterable[dict[str, Any]]) -> list[str]:
    """reading_row_violations over a whole readings record, row by row in file order (each row
    judged with the ids above it), each refusal prefixed with the row's id; the quote is found
    by the row's record hash (gamma_sha256)."""
    quotes = {e["gamma_sha256"]: e for e in manifest if e.get("gamma_sha256")}
    hist = list(history)
    ids: list[str] = []
    out: list[str] = []
    for r in rows:
        for v in reading_row_violations(r, quotes.get(str(r.get("quote_sha256", ""))), hist, ids):
            out.append(f"{r.get('id')}: {v}")
        ids.append(str(r.get("id", "")))
    return out


def reading_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per method: the count of scored readings (y present) and the mean Brier of
    the reading, the market mid and, over the rows that carry one, the
    climatological probability.  Information: with a handful of rows the figures
    describe the rows and nothing else."""
    out: dict[str, dict[str, Any]] = {}
    for method in READING_METHODS:
        scored = [r for r in rows if r.get("method") == method and r.get("y") not in (None, "")]
        n = len(scored)
        entry: dict[str, Any] = {"n": n, "brier_method": None, "brier_market": None, "brier_climatology": None,
                                 "n_climatology": 0}
        if n:
            entry["brier_method"] = sum(brier(float(r["method_p"]), int(r["y"])) for r in scored) / n
            entry["brier_market"] = sum(brier(float(r["market_mid"]), int(r["y"])) for r in scored) / n
            clim = [r for r in scored if r.get("climatology_p") not in (None, "")]
            entry["n_climatology"] = len(clim)
            if clim:
                entry["brier_climatology"] = sum(brier(float(r["climatology_p"]), int(r["y"])) for r in clim) / len(clim)
        out[method] = entry
    return out


def as_float(v: object) -> float | None:
    """A decimal number from a float, an int or a numeric string; None otherwise."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None


def decode_list(v: object) -> list | None:
    """A JSON-encoded list in a string (Gamma encodes `outcomes` and the token ids so), or a list as it is."""
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            out = json.loads(v)
        except ValueError:
            return None
        return out if isinstance(out, list) else None
    return None


def mid(bid: float, ask: float) -> float:
    return (bid + ask) / 2.0


def best_of_book(book: dict[str, Any]) -> tuple[float, float] | None:
    """Best bid and best ask of a CLOB `/book` body: the best price is the LAST
    entry of each array (observed 2026-11-01, ops/trading pm-data-sources; the
    arrays are sorted away from the touch).  Taken as max and min, not by
    position, so an unsorted body cannot mislead.  None when either side is empty."""
    bids = book.get("bids")
    asks = book.get("asks")
    if not isinstance(bids, list) or not isinstance(asks, list) or not bids or not asks:
        return None
    b = [as_float(x.get("price")) for x in bids if isinstance(x, dict)]
    a = [as_float(x.get("price")) for x in asks if isinstance(x, dict)]
    bb = [x for x in b if x is not None]
    aa = [x for x in a if x is not None]
    if not bb or not aa:
        return None
    return max(bb), min(aa)


def record_eligibility(row: dict[str, Any], at: datetime) -> str | None:
    """The reasons of `eligibility` that the Gamma record alone decides, in the
    same §6.3 order, before any book is read (added 2026-11-06: a settled
    market's book is gone (CLOB 404), and the quote had thrown the record away
    as a fetch failure, predictions/POST_MORTEMS.md).  None when the record
    leaves the market open to a call, so the book decides the rest."""
    outcomes = decode_list(row.get("outcomes"))
    tokens = decode_list(row.get("clobTokenIds"))
    if outcomes is None or tokens is None or len(outcomes) != 2 or len(tokens) != 2:
        return "not a binary market"
    if row.get("enableOrderBook") is not True:
        return "no order book"
    if row.get("active") is not True or row.get("closed") is not False or row.get("acceptingOrders") is not True:
        return "not open and accepting orders"
    uma = row.get("umaResolutionStatus")
    if isinstance(uma, str) and uma.lower() in RESOLUTION_BEGUN:
        return "resolution begun"
    end = row.get("endDate")
    if not isinstance(end, str) or not end:
        return "no scheduled end"
    try:
        end_at = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError:
        return "no scheduled end"
    if at >= end_at:
        return "past the scheduled end"
    return None


def settlement_state(row: dict[str, Any]) -> str:
    """What the Gamma record says about a market that is no longer open, in the
    record's own fields (closed, closedTime, umaResolutionStatus, outcomePrices),
    reported as information: the outcome rule that scores a call is Study 013
    §6.5 in score.py, not this line."""
    prices = decode_list(row.get("outcomePrices"))
    return (f"record says closed={row.get('closed')!r} closedTime={row.get('closedTime')!r} "
            f"umaResolutionStatus={row.get('umaResolutionStatus')!r} outcomePrices={prices!r}")


def eligibility(row: dict[str, Any], best: tuple[float, float] | None, at: datetime) -> str | None:
    """The first reason, in Study 013's §6.3 order, that excludes a market from a call; None when eligible.

    `row` is the Gamma market record; `best` the CLOB book's best bid and ask
    (None for a one-sided or empty book)."""
    reason = record_eligibility(row, at)
    if reason is not None:
        return reason
    if best is None:
        return "one-sided or empty book"
    bid, ask = best
    if not (0.0 < bid <= ask < 1.0):
        return "book not two-sided inside (0, 1)"
    if ask - bid > SPREAD_CAP:
        return f"spread above {SPREAD_CAP:.2f}"
    m = mid(bid, ask)
    if not (0.01 <= m <= 0.99):
        return "mid outside [0.01, 0.99]"
    vol = as_float(row.get("volumeNum"))
    if vol is None or vol < VOLUME_FLOOR:
        return f"volume below {VOLUME_FLOOR:,.0f} USDC"
    return None


def brier(p: float, y: int) -> float:
    return (p - y) ** 2


def departure(desk_p: float, market_mid: float) -> float:
    return abs(desk_p - market_mid)


def method_gate(method: str, calibration: dict[str, Any] | None) -> bool | None:
    """R2 of the method's calibration file (already loaded by the caller): True
    when the method beats its baselines on its own history, False when it does
    not, None when the file is missing or is not that method's calibration."""
    if method not in METHOD_CALIBRATION or calibration is None:
        return None
    key = METHOD_CALIBRATION[method][1]
    rules = calibration.get("rules") if isinstance(calibration, dict) else None
    v = rules.get(key) if isinstance(rules, dict) else None
    return v if isinstance(v, bool) else None


def method_violations(method: str, method_p: float | None, range_lo: float | None, range_hi: float | None,
                      market_mid: float, r2: bool | None, desk_p: float | None = None) -> list[str]:
    """The method gate of README rule 2, in the order the reasons are checked,
    on the numbers a ledger row carries; empty when the method may be a basis
    for a call.  The one copy of the rule: barrier.departure_verdict and
    fomc_calibrate.live_verdict print the same reasons and the tests hold them
    to this function.

    1. the method is one the desk has (METHODS);
    2. `stated` carries no method reading and no range (the gate is the
       departure alone, and the row says so);
    3. the method's calibration gate R2 is true (None: no calibration, refused);
    4. the reading and its range are probabilities with lo <= p <= hi (the
       range the ledger carries is the hull of the reading and its range under
       the method's own uncertainty: the historical basis for the bills, the
       primary-to-sensitivity window for the touch formula);
    5. the market mid lies outside the range (inside: covered, never a call);
    6. for BELOW_MARKET_NEVER methods the reading is above the market;
    7. the reading departs from the mid by at least MIN_DEPARTURE;
    8. the desk's probability sits on the same side of the market as the
       reading it rests on."""
    out: list[str] = []
    if method not in METHODS:
        return [gate("method-named", f"method must be one of {', '.join(METHODS)}")]
    if method == "stated":
        if any(v is not None for v in (method_p, range_lo, range_hi)):
            out.append(gate("stated-bare", "a stated reason carries no method reading or range: "
                                           "leave method_p, range_lo, range_hi empty"))
        return out
    if r2 is None:
        out.append(gate("calibrated", f"no calibration gate for {method}: run its calibration first "
                                      f"({METHOD_CALIBRATION[method][0]})"))
    elif not r2:
        out.append(gate("calibrated", f"{method} does not beat its baselines on its own history (R2): "
                                      "not a basis for a call"))
    if method_p is None or range_lo is None or range_hi is None:
        out.append(gate("range-brackets", "method_p, range_lo and range_hi are required for a method call"))
        return out
    if not (0.0 <= range_lo <= method_p <= range_hi <= 1.0):
        out.append(gate("range-brackets", f"the range [{range_lo:.3f}, {range_hi:.3f}] must bracket the method "
                                          f"reading {method_p:.3f} inside [0, 1]"))
        return out
    if range_lo <= market_mid <= range_hi:
        out.append(gate("range", f"the market mid {market_mid:.3f} lies inside the reading's range "
                                 f"[{range_lo:.3f}, {range_hi:.3f}]: no call"))
    if method in BELOW_MARKET_NEVER and method_p <= market_mid:
        out.append(gate("touch-below", f"{method}: the reading is at or below the market, the direction of the gap "
                                       "the method cannot see: never a call"))
    if departure(method_p, market_mid) < MIN_DEPARTURE:
        out.append(gate("method-departure", f"the method reading is within {MIN_DEPARTURE:.2f} of the market mid: no call"))
    if desk_p is not None and (desk_p - market_mid) * (method_p - market_mid) <= 0:
        out.append(gate("desk-side", "desk_p and the method reading sit on opposite sides of the market (or on it)"))
    return out


def call_violations(desk_p: float, market_mid: float, basis: str, settles_on: str = "",
                    proposition: str = "", method: str | None = None, method_p: float | None = None,
                    range_lo: float | None = None, range_hi: float | None = None,
                    r2: bool | None = None, made_on: str | None = None,
                    quote_fetched_utc: str | None = None) -> list[str]:
    """What stops a draft call from being logged; empty when it may be.

    `settles_on` (added 2026-11-04 after the first view described two touch
    markets as price-level markets from their titles, predictions/POST_MORTEMS.md)
    restates the market's resolution rule in the desk's words: the source and
    the measure that settle YES.  It must be present, long enough to say both,
    and not a copy of the proposition or of the title.

    `method` and the three numbers beside it (added 2026-11-06) carry the
    method gate: see method_violations.  A call with no method is refused.

    `made_on` and `quote_fetched_utc` (added 2026-11-07 12:15Z) carry the
    timing rule, quote_timing_violations: when `made_on` is given (a ledger
    row), it must be the quote's day.  The printers and the grid tests judge a
    candidate's numbers with no row yet and leave both out."""
    out: list[str] = []
    if not (0.0 < desk_p < 1.0):
        out.append(gate("probability", "desk_p is not a probability"))
    if departure(desk_p, market_mid) < MIN_DEPARTURE:
        out.append(gate("departure", f"desk_p is within {MIN_DEPARTURE:.2f} of the market mid: no call"))
    if "market" not in basis.lower():
        out.append(gate("basis-names-market", "basis must name the market's probability and what it is missing"))
    so = settles_on.strip()
    if len(so) < MIN_SETTLES_ON_CHARS or not any(c.isdigit() for c in so):
        out.append(gate("settles-on", "settles_on must restate the market's resolution rule with its source "
                                      "and the measured level or date"))
    elif so.lower() == proposition.strip().lower():
        out.append(gate("settles-on", "settles_on repeats the proposition; restate the rule, not the title"))
    if method is None:
        out.append(gate("method-named", f"method must be stated: one of {', '.join(METHODS)}"))
    else:
        out.extend(method_violations(method, method_p, range_lo, range_hi, market_mid, r2, desk_p))
    if made_on is not None:
        out.extend(quote_timing_violations(made_on, quote_fetched_utc))
    return out


def ledger_method_fields(call: dict[str, Any]) -> tuple[str | None, float | None, float | None, float | None]:
    """The four method columns of a ledger row as typed values; an empty cell is None."""
    def num(k: str) -> float | None:
        v = call.get(k, "")
        return as_float(v) if isinstance(v, str) and v.strip() else None
    m = call.get("method", "")
    return (m.strip() if isinstance(m, str) and m.strip() else None, num("method_p"), num("range_lo"), num("range_hi"))


# --- Admission of a call (2026-11-07 18:15Z, predictions/POST_MORTEMS.md "A gate
# that only a test applied") ------------------------------------------------------
#
# Until this date no tool wrote a call: a desk operator logging one would have
# hand-typed a CSV row, and call_violations ran only in tests/test_ledger_discipline.py
# on the committed file, after the row was written, while the row's own checks
# (the quote written, the mid copied, the market eligible, the rules fetched, the
# two-decimal desk number) lived in that test alone, outside the gate and its tags.
# ledger_row_violations is the one copy of everything a ledger row is held to;
# ledger.py add applies it where the row is admitted, the committed-file test
# applies it again row by row.

def call_id(made_on: str, method: str, market_id: str) -> str:
    """The ledger.csv id of a call, in the style of reading_id."""
    return f"C-{made_on}-{method}-{market_id}"


def ledger_row_violations(call: dict[str, Any], quote: dict[str, Any] | None,
                          history: Iterable[dict[str, Any]], earlier: Iterable[dict[str, Any]] = (),
                          admitted_utc: str | None = None, calibration_sha256: str | None = None) -> list[str]:
    """What stops a ledger row from being admitted; empty when it may be.  `call` is the
    row as written (strings, or the values ledger.py is about to write); `quote` the
    data/manifest.json entry it rests on (None: no written quote); `history` the lines of
    data/calibration_history.csv, R2 taken from the method's line in force at the quote's
    fetch (calibration_in_force); `earlier` the rows already on the ledger before this one.

    The row's own checks come first: desk_p a two-decimal probability, the quote written
    for the row's market and ids with its book hash in the row, the mid copied from it,
    the market eligible at it, its rules' hash on record, one call per market and day;
    then call_violations with the quote's day and fetch time.

    At admission (2026-11-08 06:15Z, predictions/POST_MORTEMS.md "A call admitted under a
    calibration already superseded"), when `admitted_utc` is given, for a method with a
    calibration: `calibration_sha256`, the SHA-256 of the method's committed calibration file
    as read (None: no file), is the method's line in force at `admitted_utc`, and that line is
    the one in force at the quote's fetch, so the call is judged under the calibration the
    organisation holds when it writes the call and the readings record, judged at
    `recorded_utc`, cannot disagree with it.  The committed ledger carries no admission time,
    so the committed-file test leaves both out and judges under the line at the quote.

    Every column the tool copies from the quote or sets itself is held to its source
    (2026-11-08 12:15Z, predictions/POST_MORTEMS.md "Five columns the gate never read"): until
    then a mechanical search over the eleven such columns found six held and five admitted at
    any value (`id`, `venue`, `due_on`, `market_spread`, `volume_usdc`), so a hand-typed row with
    a `due_on` a year late passed the committed-file test and would have kept a settled call off
    score.py, which reads nothing but `due_on` to decide when a call is due.  Now `due_on` is the
    quote's scheduled end, the spread and volume are the quote's, the id is call_id of the row's
    own columns and the venue is VENUE; tests/test_ledger.py runs the search on every column."""
    out: list[str] = []
    if any(e.get("market_id") == call.get("market_id") and e.get("made_on") == call.get("made_on") for e in earlier):
        out.append(gate("one-per-day", f"a call on market {call.get('market_id')} made on {call.get('made_on')} is "
                                       "already on the ledger (one call per market and day)"))
    raw_p = str(call.get("desk_p", "")).strip()
    desk_p = as_float(raw_p)
    if desk_p is None or raw_p != f"{desk_p:.2f}":
        out.append(gate("probability", f"desk_p {raw_p!r} is not written as a two-decimal probability"))
        return out
    if quote is None:
        out.append(gate("written-quote", "no written quote: a --dry-run quote leaves no entry in "
                                         "data/manifest.json; re-quote without --dry-run (the rest of the gate is "
                                         "measured against the quote's mid and is not run)"))
        return out
    book = quote.get("book_sha256")
    if not book or book != call.get("quote_sha256"):
        out.append(gate("written-quote", "quote_sha256 is not the book hash of the written quote "
                                         f"({'none: no book was read' if not book else str(book)[:12] + '…'})"))
    for k in ("market_id", "condition_id", "yes_token_id"):
        if str(quote.get(k, "")) != str(call.get(k, "")):
            out.append(gate("written-quote", f"{k} differs from the written quote's: copy it from the quote"))
    if quote.get("eligibility") != "eligible":
        out.append(gate("eligible-at-quote", f"the market was not eligible at the quote ({quote.get('eligibility')})"))
    if not quote.get("description_sha256"):
        out.append(gate("rules-on-record", "the quote did not record the hash of the market's resolution text: "
                                           "re-quote, read the rules, then write the call"))
    end = str(quote.get("end_date", ""))[:10]
    if str(call.get("due_on", "")) != end:
        out.append(gate("due-on-scheduled-end", f"due_on {call.get('due_on')} is not the quote's scheduled end "
                                                f"{end or 'unknown'}: score.py treats the call as due on this date"))
    for k in ("market_spread", "volume_usdc"):
        v_row, v_q = as_float(call.get(k)), as_float(quote.get(k))
        if v_row is None or v_q is None or abs(v_row - v_q) > 1e-9:
            out.append(gate("book-from-quote", f"{k} {call.get(k)} is not the written quote's {quote.get(k)}: "
                                               "copy it from the quote"))
    want_id = call_id(str(call.get("made_on", "")), str(call.get("method", "")).strip(), str(call.get("market_id", "")))
    if str(call.get("id", "")) != want_id:
        out.append(gate("id-rule", f"id {call.get('id')} is not {want_id} (C-<made_on>-<method>-<market_id>)"))
    if str(call.get("venue", "")) != VENUE:
        out.append(gate("id-rule", f"venue {call.get('venue')!r} is not {VENUE!r}, the one venue the view quotes"))
    mid_row, mid_q = as_float(call.get("market_mid")), as_float(quote.get("market_mid"))
    if mid_row is None or mid_q is None or abs(mid_row - mid_q) > 1e-9:
        out.append(gate("mid-from-quote", f"market_mid {call.get('market_mid')} is not the quote's {mid_q}: "
                                          "copy the mid from the quote"))
        return out
    fetched = str(quote.get("fetched_utc", ""))
    method, method_p, lo, hi = ledger_method_fields({k: ("" if v is None else str(v)) for k, v in call.items()})
    hist = list(history)
    # 2026-11-09 12:15Z (predictions/POST_MORTEMS.md "A calibration put after the quote by a space"): every stamp
    # on this path is parsed before anything is compared; a stamp in another format refuses the row here, so the
    # calibration checks below never run on text order
    bad_stamp = stamp_violation(fetched)
    if bad_stamp:
        out.append(gate("utc-stamp", f"{bad_stamp}; the row cannot be judged against this quote"))
        return out
    try:
        if admitted_utc is not None:
            parse_utc_stamp(admitted_utc, "the admission time")
        at_quote = calibration_in_force(hist, method or "", fetched)
        latest = (calibration_in_force(hist, method, admitted_utc)
                  if admitted_utc is not None and method in METHOD_CALIBRATION else None)
    except ValueError as e:
        out.append(gate("utc-stamp", f"{e}: fix the stamp, nothing is compared as text"))
        return out
    if admitted_utc is not None and method in METHOD_CALIBRATION:
        if calibration_sha256 is None or latest is None or calibration_sha256 != latest.get("sha256"):
            shown = "missing" if calibration_sha256 is None else f"SHA-256 {calibration_sha256[:12]}…"
            out.append(gate("calibration-on-record", f"the committed calibration of {method} ({shown}) is not its "
                                                     f"latest line in {CALIBRATION_HISTORY} at {admitted_utc}: the "
                                                     "printer read R2 from a file the ledger does not judge under; "
                                                     "put it on record (readings.py record-calibration) first"))
        elif latest is not at_quote:
            out.append(gate("calibration-since-quote", f"a calibration of {method} went into force at "
                                                       f"{latest.get('in_force_utc')}, after the quote at {fetched} "
                                                       f"(R2 {latest.get('r2')}): re-quote and re-read under it"))
    r2 = history_r2(at_quote)
    out.extend(call_violations(desk_p, mid_row, str(call.get("basis", "")), str(call.get("settles_on", "")),
                               str(call.get("proposition", "")), method, method_p, lo, hi, r2,
                               made_on=str(call.get("made_on", "")), quote_fetched_utc=fetched))
    return out


def ledger_file_violations(rows: list[dict[str, Any]], manifest: Iterable[dict[str, Any]],
                           history: Iterable[dict[str, Any]]) -> list[str]:
    """ledger_row_violations over a whole ledger, row by row in file order (each row judged
    against the rows above it), each refusal prefixed with the row's id; the quote is found
    by the row's book hash."""
    quotes = {e["book_sha256"]: e for e in manifest if e.get("book_sha256")}
    hist = list(history)
    out: list[str] = []
    for i, call in enumerate(rows):
        for v in ledger_row_violations(call, quotes.get(str(call.get("quote_sha256", ""))), hist, rows[:i]):
            out.append(f"{call.get('id')}: {v}")
    return out


def rules_excerpt(row: dict[str, Any], chars: int = 400) -> str:
    """The first `chars` characters of the market's own resolution text (Gamma
    `description`), one line, for the quote's printed output: the desk reads
    how YES settles before it writes a proposition or a probability.  Nothing
    of this is written to a committed file; the manifest carries its hash."""
    d = row.get("description")
    if not isinstance(d, str) or not d.strip():
        return "(no description on the record)"
    one = " ".join(d.split())
    return one if len(one) <= chars else one[:chars] + "..."


# --- Touch (first-passage) probability for the barrier markets -----------------
#
# Added 2026-11-04 with the post-mortem above: the monthly Bitcoin markets
# settle YES if ANY one-minute Binance BTC/USDT candle in the month has a High
# at or above the level (or a Low at or below it), so the desk's number is a
# first-passage probability, not the probability of ending above the level.
# Model: driftless geometric Brownian motion of the price with annualised
# volatility `sigma` over `days` calendar days (crypto trades every day, so the
# year is 365 days).  Reflection principle: P(max_{t<=T} S_t >= B) =
# 2 * Phi(-ln(B/S) / (sigma * sqrt(T))) for an upper barrier B > S, and the
# mirror for a lower barrier.  One-minute monitoring is treated as continuous
# (the Broadie-Glasserman-Kou correction at dt = 1 minute moves the barrier
# by exp(0.5826 * sigma * sqrt(dt)), under 0.1% at sigma = 0.6: inside the
# rounding of the view).  The drift is set to zero on purpose: any drift the
# desk believes in is a reason it must state in the basis, not a parameter.
# What the formula does NOT carry, and the view's basis sentence must say:
# a volatility estimated from Coinbase daily closes understates the intraday
# range Binance's one-minute extremes see, so the probability below is a
# lower reading of the touch chance, and the two venues' prices differ by a
# basis of their own (tools/pm_data_terms.md, "Price series for the Bitcoin
# barrier markets", condition 3).


def realised_vol(closes: list[float], days_per_year: int = 365) -> float:
    """Annualised close-to-close volatility: standard deviation (ddof = 1) of the
    log returns of consecutive daily closes, times sqrt(days_per_year).  Needs at
    least three closes; a non-positive close is refused."""
    if len(closes) < 3:
        raise ValueError("realised_vol needs at least three closes")
    if any(c <= 0 for c in closes):
        raise ValueError("realised_vol: a close is not positive")
    rets = [math.log(b / a) for a, b in zip(closes[:-1], closes[1:], strict=True)]
    n = len(rets)
    m = sum(rets) / n
    var = sum((r - m) ** 2 for r in rets) / (n - 1)
    return math.sqrt(var) * math.sqrt(days_per_year)


def touch_probability(spot: float, barrier: float, sigma: float, days: float, days_per_year: int = 365) -> float:
    """Probability that a driftless lognormal price with annualised volatility
    `sigma` touches `barrier` (above or below `spot`) within `days` calendar
    days.  1.0 when the barrier is already at or past the spot; 0.0 when no
    time or no volatility is left."""
    if spot <= 0 or barrier <= 0:
        raise ValueError("touch_probability: spot and barrier must be positive")
    if sigma < 0 or days < 0:
        raise ValueError("touch_probability: sigma and days must be non-negative")
    if barrier == spot:
        return 1.0
    if days == 0 or sigma == 0:
        return 0.0
    dist = abs(math.log(barrier / spot))
    return 2.0 * _phi(-dist / (sigma * math.sqrt(days / days_per_year)))


def _phi(x: float) -> float:
    """Standard normal CDF."""
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def skill_summary(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Brier for the desk and for the market mid over the scored calls (y present); skill = market minus desk."""
    scored = [o for o in outcomes if o.get("y") not in (None, "")]
    n = len(scored)
    if n == 0:
        return {"n": 0, "brier_desk": None, "brier_market": None, "skill": None}
    bd = sum(brier(float(o["desk_p"]), int(o["y"])) for o in scored) / n
    bm = sum(brier(float(o["market_mid"]), int(o["y"])) for o in scored) / n
    return {"n": n, "brier_desk": bd, "brier_market": bm, "skill": bm - bd}
