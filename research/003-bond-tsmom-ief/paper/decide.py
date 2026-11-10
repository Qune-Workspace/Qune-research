"""Month-end decision record for the paper sleeve (PREREGISTRATION.md §11.2, §11.5).

On the last NYSE trading day of the month, after the close, the paper path
fetches Alpaca daily bars (``adjustment='all'``) for IEF and BIL into the
paper log's own raw directory (never the study's ``data/raw/``, whose hashes
are frozen in ``results/data_manifest.json``), confirms the bar for the
signal date ``t`` is present, computes

    mom_t = TRI_IEF(t) / TRI_IEF(t_12) - TRI_BIL(t) / TRI_BIL(t_12)

with the study's own ``signal.excess_momentum`` (the same function the
backtest called), sets ``target = IEF if mom_t > 0 else BIL``, and writes one
JSON record.  The order leg reads that record on the next NYSE trading day;
this module places no order and holds no credential beyond the environment
variables ``src.alpaca_bars`` reads.

A record is written whatever the outcome: a missing or stale month-end bar
produces ``status = "signal unavailable"`` with ``target = None`` (§11.2:
hold, re-check for up to three NYSE days, then alert).  The record carries
``run_at_utc`` so the commit history shows it was written after the signal
date, never before and never backdated.  Since 2026-10-24 (before the first
record) ``write_record`` also refuses to write before 17:00 New York time on
the signal date (§11.2), so a record cannot be made from a session that has
not closed; a refused write leaves nothing on disk.

Since 2026-11-10 (research/POST_MORTEMS.md "A holding passed by hand"): the
holding before a signal date is read from the records already written, as a
chain from the pre-registered starting position (BIL, ``paper/README.md``):
each record's ``holding_before`` must be the state in force before it, and an
ok record's ``target`` becomes the state in force after it.  ``--holding`` is
optional and, when given, is held against that chain; a disagreement is a
refusal naming both and nothing is fetched or written.  Every record is read
back only through ``record_violations``, the gate that also judges a record
before it is written.

Usage (from the study folder, after the close on the signal date):

    python -m paper.decide --signal-date 2026-10-30 [--holding BIL] [--fetch]
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from src.alpaca_bars import fetch_bars, load_bars, total_return_index
from src.calendar import execution_dates, month_end_bars, nyse_trading_days
from src.config import CASH_LEG, DURATION_LEG, MOMENTUM_LOOKBACK_MONTHS, PAPER_LOG_DIR, SYMBOLS
from src.signal import excess_momentum, month_end_levels

PAPER_RAW_DIR = PAPER_LOG_DIR / "raw"             # git-ignored, separate from the study's data/raw/
PAPER_MANIFEST = PAPER_LOG_DIR / "manifest.json"  # provenance of every paper fetch (hashes, not data)
DECISIONS_DIR = PAPER_LOG_DIR / "decisions"
STRATEGY_ID = "study003-tsmom-ief-bil"
STRATEGY_VERSION = "1"
# Bars are fetched from this date so that the 12-month lookback and the T3
# comparison always have more history than they need.
PAPER_BARS_START = "2024-01-02"
# §11.2: the decision is made after 17:00 New York time on the signal date.
# ``write_record`` refuses an earlier write whatever the host's clock says.
DECISION_TIME_NY = "17:00"
NEW_YORK = "America/New_York"
# The sleeve's position before the first record: "Starting position: BIL" in
# paper/README.md (§11.1 as inherited).  The chain of records is walked from it.
STARTING_HOLDING = CASH_LEG
# What ``decision_record`` writes as a status; a reader admits nothing else.
RECORD_STATUSES = ("ok", "signal unavailable")
MOM_TOLERANCE = 1e-9


def decision_record(ief_bars: pd.DataFrame, bil_bars: pd.DataFrame, signal_date: str,
                    holding_before: str, trading_days: pd.DatetimeIndex | None = None,
                    run_at_utc: str | None = None) -> dict:
    """The §11.5 record for signal date ``signal_date`` from the two bar
    frames.  Only bars on or before ``signal_date`` are used (§6.3); the
    frames may contain later bars and they are ignored."""
    if holding_before not in SYMBOLS:
        raise ValueError(f"holding_before must be one of {SYMBOLS}, got {holding_before!r}")
    t = pd.Timestamp(signal_date).normalize()
    month_last_day = t.to_period("M").to_timestamp(how="end").normalize()
    if trading_days is None:
        trading_days = nyse_trading_days(t, month_last_day + pd.Timedelta(days=10))
    later_in_month = trading_days[(trading_days > t) & (trading_days <= month_last_day)]
    ief = ief_bars.loc[ief_bars.index <= t]
    bil = bil_bars.loc[bil_bars.index <= t]
    base = {
        "strategy_id": STRATEGY_ID, "strategy_version": STRATEGY_VERSION,
        "signal_date": t.strftime("%Y-%m-%d"), "holding_before": holding_before,
        "run_at_utc": run_at_utc or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "orders": [], "equity_close": None, "peak_equity": None, "drawdown": None, "notes": "",
    }
    if len(later_in_month):
        return {**base, "status": "signal unavailable", "target": None, "execution_date": None,
                "notes": f"{t.date()} is not the last NYSE trading day of its month "
                         f"({later_in_month[-1].date()} is); no signal on other days (§11.2)"}
    for name, frame in ((DURATION_LEG, ief), (CASH_LEG, bil)):
        if frame.empty or frame.index[-1] != t:
            last = frame.index[-1].strftime("%Y-%m-%d") if not frame.empty else None
            return {**base, "status": "signal unavailable", "target": None, "execution_date": None,
                    "notes": f"no {name} bar for the signal date (last bar {last}); hold and re-check (§11.2)"}
    month_ends = month_end_bars(ief.index)
    tri_ief, tri_bil = total_return_index(ief), total_return_index(bil)
    mom = excess_momentum(tri_ief, tri_bil, month_ends, lookback=MOMENTUM_LOOKBACK_MONTHS)
    month = t.to_period("M")
    if month not in mom.index:
        return {**base, "status": "signal unavailable", "target": None, "execution_date": None,
                "notes": f"lookback of {MOMENTUM_LOOKBACK_MONTHS} months not covered by the fetched bars"}
    value = float(mom.loc[month])
    lv_ief, lv_bil = month_end_levels(tri_ief, month_ends), month_end_levels(tri_bil, month_ends)
    t12 = month - MOMENTUM_LOOKBACK_MONTHS
    execution = execution_dates(pd.Series([t], index=[month]), trading_days).iloc[0]
    target = DURATION_LEG if value > 0 else CASH_LEG
    return {
        **base, "status": "ok", "execution_date": execution.strftime("%Y-%m-%d"),
        "tri_ief_t": float(lv_ief.loc[month]), "tri_ief_t12": float(lv_ief.loc[t12]),
        "tri_cash_t": float(lv_bil.loc[month]), "tri_cash_t12": float(lv_bil.loc[t12]),
        "t12_date": month_ends.loc[t12].strftime("%Y-%m-%d"),
        "mom": value, "target": target, "switch": target != holding_before,
    }


def earliest_write_utc(signal_date: str) -> pd.Timestamp:
    """§11.2: the decision is made after 17:00 New York time on the signal
    date, i.e. after the 16:00 close under EDT or EST.  Returned in UTC
    (21:00Z under EDT, 22:00Z under EST).  Added 2026-10-24, before the first
    record: until then only the schedule, not the code, kept a record from
    being written during the session."""
    local = pd.Timestamp(f"{pd.Timestamp(signal_date).date()} {DECISION_TIME_NY}", tz=NEW_YORK)
    return local.tz_convert("UTC")


def _ymd(text):
    """A strict YYYY-MM-DD date, else None."""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def record_violations(record, path: Path) -> list[str]:
    """Every way a decision record is not as ``decision_record`` writes it: a
    list of sentences naming the file and the column, empty for a well-formed
    record.  Added 2026-11-10 after a search showed that no reader held any
    column of the committed record and that the holding before a record was
    taken from a hand-typed argument (research/POST_MORTEMS.md).  Shape and
    internal consistency only: the bars behind ``mom`` are not re-fetched."""
    name = Path(path).name
    if not isinstance(record, dict):
        return [f"{name}: the file does not hold a record (a JSON object)"]
    out: list[str] = []
    status = record.get("status")
    ok = status == "ok"
    if status not in RECORD_STATUSES:
        out.append(f"{name}: status {status!r} is not one its writer writes {RECORD_STATUSES}")
    if record.get("strategy_id") != STRATEGY_ID:
        out.append(f"{name}: strategy_id {record.get('strategy_id')!r} is not {STRATEGY_ID}")
    if record.get("strategy_version") != STRATEGY_VERSION:
        out.append(f"{name}: strategy_version {record.get('strategy_version')!r} is not {STRATEGY_VERSION}")
    signal = record.get("signal_date")
    signal_day = _ymd(signal)
    if signal_day is None:
        out.append(f"{name}: signal_date {signal!r} is not YYYY-MM-DD")
    elif Path(path).stem != signal:
        out.append(f"{name}: the file is not named after its signal_date {signal}")
    holding = record.get("holding_before")
    if holding not in SYMBOLS:
        out.append(f"{name}: holding_before {holding!r} is not one of {SYMBOLS}")
    try:
        run_at = datetime.strptime(record.get("run_at_utc"), "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        out.append(f"{name}: run_at_utc {record.get('run_at_utc')!r} is not a UTC stamp YYYY-MM-DDTHH:MM:SSZ")
    else:
        if signal_day is not None and pd.Timestamp(run_at, tz="UTC") < earliest_write_utc(signal):
            out.append(f"{name}: run_at_utc {record.get('run_at_utc')} is before {DECISION_TIME_NY} New York on the "
                       f"signal date {signal}; a record is never written before the close (section 11.2)")
    if record.get("orders") != []:
        out.append(f"{name}: orders is not empty; the decision record places no order (section 11.2)")
    for key in ("equity_close", "peak_equity", "drawdown"):
        if record.get(key) is not None:
            out.append(f"{name}: {key} {record.get(key)!r} is not null; the decision record carries no equity mark")
    if not isinstance(record.get("notes"), str):
        out.append(f"{name}: notes {record.get('notes')!r} is not text")
    target, execution, switch, mom = record.get("target"), record.get("execution_date"), record.get("switch"), record.get("mom")
    if ok:
        execution_day = _ymd(execution)
        if execution_day is None:
            out.append(f"{name}: an ok record's execution_date {execution!r} is not YYYY-MM-DD")
        elif signal_day is not None and execution_day <= signal_day:
            out.append(f"{name}: execution_date {execution} is not after signal_date {signal} (section 11.2)")
        if target not in SYMBOLS:
            out.append(f"{name}: an ok record's target {target!r} is not one of {SYMBOLS}")
        if not _finite(mom):
            out.append(f"{name}: mom {mom!r} is not a finite number")
        elif target in SYMBOLS and target != (DURATION_LEG if mom > 0 else CASH_LEG):
            out.append(f"{name}: target {target} does not follow from mom {mom} (IEF if mom > 0 else BIL, section 6.1)")
        if holding in SYMBOLS and target in SYMBOLS and switch != (target != holding):
            out.append(f"{name}: switch {switch!r} is not whether target {target} differs from holding_before {holding}")
        levels = {k: record.get(k) for k in ("tri_ief_t", "tri_ief_t12", "tri_cash_t", "tri_cash_t12")}
        bad = [k for k, v in levels.items() if not _finite(v) or v <= 0]
        if bad:
            out.append(f"{name}: {', '.join(bad)} not finite positive index levels")
        elif _finite(mom):
            implied = levels["tri_ief_t"] / levels["tri_ief_t12"] - levels["tri_cash_t"] / levels["tri_cash_t12"]
            if abs(implied - mom) > MOM_TOLERANCE:
                out.append(f"{name}: mom {mom} is not the excess momentum of its own index levels ({implied})")
        t12_day = _ymd(record.get("t12_date"))
        if t12_day is None:
            out.append(f"{name}: t12_date {record.get('t12_date')!r} is not YYYY-MM-DD")
        elif signal_day is not None and t12_day >= signal_day:
            out.append(f"{name}: t12_date {record.get('t12_date')} is not before signal_date {signal}")
    elif status in RECORD_STATUSES:
        for key, value in (("target", target), ("execution_date", execution)):
            if value is not None:
                out.append(f"{name}: a record with status {status!r} carries {key} {value!r}")
        if not record.get("notes"):
            out.append(f"{name}: a record with status {status!r} has no notes saying why (section 11.2)")
    return out


def load_records(directory: Path = DECISIONS_DIR) -> list[dict]:
    """Every decision record in the folder, each through ``record_violations``,
    one per signal date and one per month, sorted by signal date.  Refuses the
    whole folder by name otherwise: a record is fixed where it is wrong, never
    read around (2026-11-10)."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    records: list[dict] = []
    problems: list[str] = []
    for path in sorted(directory.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as bad:
            problems.append(f"{path.name}: not JSON ({bad})")
            continue
        found = record_violations(record, path)
        problems += found
        if not found:
            records.append(record)
    dates = [r["signal_date"] for r in records]
    months = [d[:7] for d in dates]
    problems += [f"two records for {d}: never rewritten, never doubled (section 11.2)" for d in sorted(set(dates))
                 if dates.count(d) > 1]
    problems += [f"two records in {m}: one record per signal month (section 11.2)" for m in sorted(set(months))
                 if months.count(m) > 1 and not any(dates.count(d) > 1 for d in dates if d[:7] == m)]
    if problems:
        raise ValueError(f"{directory}: a decision record is not as its writer writes it; fix the record, never the "
                         "reader: " + "; ".join(problems))
    return sorted(records, key=lambda r: r["signal_date"])


def holding_in_force(signal_date: str, directory: Path = DECISIONS_DIR,
                     start: str = STARTING_HOLDING) -> tuple[str, str]:
    """The sleeve's holding before ``signal_date``, read as a chain from the
    pre-registered starting position through every earlier record: each
    record's ``holding_before`` must be the state in force before it (an
    edited link is refused, never carried), and an ok record's ``target`` is
    the state in force after it; a ``signal unavailable`` record carries the
    holding (section 11.2: hold).  Returns the holding and where it came
    from.  Replaces the hand-typed ``--holding`` as the source (2026-11-10)."""
    if start not in SYMBOLS:
        raise ValueError(f"starting holding {start!r} is not one of {SYMBOLS}")
    if _ymd(signal_date) is None:
        raise ValueError(f"signal date {signal_date!r} is not YYYY-MM-DD")
    held, source = start, "the pre-registered starting position (paper/README.md)"
    for record in load_records(directory):
        if record["signal_date"] >= signal_date:
            continue
        if record["holding_before"] != held:
            raise ValueError(f"the record for {record['signal_date']} says holding_before {record['holding_before']} "
                             f"but the state in force before it was {held} ({source}); fix the record, never the reader")
        if record["status"] == "ok":
            held, source = record["target"], f"decision record {record['signal_date']} (target)"
        else:
            source = f"decision record {record['signal_date']} ({record['status']}: {held} held)"
    return held, source


def write_record(record: dict, directory: Path = DECISIONS_DIR,
                 now_utc: pd.Timestamp | str | None = None, start: str = STARTING_HOLDING) -> Path:
    """One file per signal date; refuses a record that is not as
    ``decision_record`` writes it or whose ``holding_before`` is not the state
    in force before it (2026-11-10), refuses to overwrite (a record is never
    rewritten; a correction is a new, later record with a note) and refuses
    to write before 17:00 New York time on the signal date (§11.2).  A
    refused write leaves nothing on disk."""
    directory = Path(directory)
    path = directory / f"{record.get('signal_date')}.json"
    found = record_violations(record, path)   # the writer's own record is held as every reader holds it
    if found:
        raise ValueError("the record to be written is not as decision_record writes it: " + "; ".join(found))
    held, source = holding_in_force(record["signal_date"], directory, start)
    if record["holding_before"] != held:
        raise ValueError(f"the record for {record['signal_date']} says holding_before {record['holding_before']} but "
                         f"the state in force before it is {held} ({source}); nothing written")
    later = [r["signal_date"] for r in load_records(directory) if r["signal_date"] > record["signal_date"]]
    if later:
        raise ValueError(f"a record for {record['signal_date']} would be written after the record for {later[0]}: "
                         "records are written in signal-date order, never backdated; nothing written")
    now = pd.Timestamp.now(tz="UTC") if now_utc is None else pd.Timestamp(now_utc)
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    earliest = earliest_write_utc(record["signal_date"])
    if now < earliest:
        raise RuntimeError(f"too early: a record for {record['signal_date']} is written after "
                           f"{DECISION_TIME_NY} New York time ({earliest.strftime('%Y-%m-%dT%H:%MZ')}); "
                           f"now {now.strftime('%Y-%m-%dT%H:%MZ')} (§11.2)")
    directory.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"{path} exists: decision records are never overwritten")
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return path


def main(argv: list[str] | None = None, decisions_dir: Path = DECISIONS_DIR, raw_dir: Path = PAPER_RAW_DIR,
         manifest_path: Path = PAPER_MANIFEST, start: str = STARTING_HOLDING) -> int:
    """Paths are passed by name from here on, never reached through a default
    (tools/check_bound_defaults.py, research/POST_MORTEMS.md 2026-11-01)."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--signal-date", required=True, help="YYYY-MM-DD, the last NYSE trading day of the month")
    parser.add_argument("--holding", choices=SYMBOLS, default=None,
                        help="the sleeve's holding before the signal date; read from paper-log/decisions/ and the "
                             "starting position when omitted, and held against them when given")
    parser.add_argument("--fetch", action="store_true", help="fetch fresh Alpaca bars into paper-log/raw/ first")
    parser.add_argument("--dry-run", action="store_true", help="print the record, write nothing")
    args = parser.parse_args(argv)
    try:
        held, source = holding_in_force(args.signal_date, decisions_dir, start)
    except ValueError as exc:                # a record on disk is not as its writer writes it: nothing fetched
        print(f"refused: {exc}")
        return 1
    if args.holding is not None and args.holding != held:
        print(f"refused: --holding {args.holding} disagrees with the record: the holding in force before "
              f"{args.signal_date} is {held} ({source}); nothing fetched, nothing written")
        return 1
    print(f"holding before {args.signal_date}: {held} ({source})")
    if args.fetch:
        for symbol in SYMBOLS:
            fetch_bars(symbol, start=PAPER_BARS_START, raw_dir=raw_dir, manifest_path=manifest_path)
    record = decision_record(load_bars(DURATION_LEG, raw_dir), load_bars(CASH_LEG, raw_dir), args.signal_date, held)
    print(json.dumps(record, indent=2, sort_keys=True))
    if not args.dry_run:
        try:
            print(f"written: {write_record(record, decisions_dir, start=start)}")
        except (RuntimeError, ValueError, FileExistsError) as exc:   # too early, not as written, or a recorded window
            print(f"refused: {exc}")
            return 1
    return 0 if record["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
