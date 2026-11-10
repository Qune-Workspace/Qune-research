"""The forward record (PREREGISTRATION.md §11): decision record, monthly
shadow line, interim figures and the single scoring.  No paper order.

Decision record (§11.2).  ``python -m src.forward decide --signal-month m
[--fetch]`` fetches DGS10, DTB3 and DGS7 from FRED into ``paper-log/raw/``
(git-ignored, its own manifest, so the study's ``data/raw/`` hashes stay
frozen), finds the signal date t of month m by Study 001 §6.3 (the last FRED
business day of m on which DGS10 and DTB3 both exist), computes T1, T2 and T3
with the study's own ``signal`` functions on the observations dated on or
before t, and writes ``paper-log/decisions/<t>.json`` with every input, the
file hashes and the UTC time written.  Never rewritten.

When is t final?  FRED's CSV carries a row for every weekday (empty on
holidays).  t is final once every weekday of m after t has a row, or is an
NYSE holiday.  Until then, and until FRED holds t at all, the run logs a wait
line in ``paper-log/waits.csv`` and writes no record (§11.2: "the wait is
logged").

Execution date (§11.2, Study 001 §6.3 and §11.2): the first NYSE trading day
strictly after t whose 16:00 New York close is after the record is written;
a slip beyond the first such day is recorded in ``days_slipped``.  If no
record exists by the close of the third NYSE trading day after t, the record
is ``signal unavailable``: every trial holds its position, and the holding
period simply runs on (as ``calendar.build_schedule`` treats a month without
a signal).  A missed month is never filled later (§11.1).

Shadow line (§11.3).  ``python -m src.forward shadow --signal-month m
[--fetch]`` appends to ``paper-log/shadow.csv`` the line of the holding period
that ended at month m's execution date: IEF and BIL holding-period returns
from Alpaca ``adjustment='all'`` closes, T1–T3 and B1–B3 through the study's
own engine (``backtest.run_switching`` and ``backtest.run_static`` at base
costs, B3 at the weight frozen by the history run), and d = T1 − B3.  Earlier
periods' instrument returns are taken from the lines already written, so a
line is never recomputed.

Interim figures go to ``paper-log/interim.json`` under "Not yet scored".
Scoring (§11.4) runs once per block of 60 holding periods; the scoring date
is written in the decision record that ends the block, before any statistic.

Gates: no record for a month before ``FIRST_SIGNAL_MONTH``; none before
21:15 UTC on t (after the 16:15 ET H.15 release under EST or EDT).  A
refused run writes nothing and exits 1.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import backtest, stats
from .alpaca_bars import fetch_bars, load_bars, total_return_index
from .calendar import nyse_trading_days, signal_dates
from .config import CASH_LEG, COST_CASES, DURATION_LEG, PAPER_LOG_DIR, STUDY_DIR
from .config006 import HISTORY_DIR
from .fred import fetch_series, load_series, sha256_of
from .signal import t1, t2, t3, target_from_value

FIRST_SIGNAL_MONTH = "2026-10"   # §11.1: the first month-end after the note (3663b77, 2026-10-25)
STARTING_MONTH = "2026-09"       # its targets are the holdings before the first record
EARLIEST_UTC = (21, 15)          # H.15 for day t is posted 16:15 ET (Study 001 §6.3)
MAX_NYSE_DAYS_WAIT = 3           # §11.2, Study 001 §11.2
BLOCK_PERIODS = 60               # §11.3
LOW_POWERED_SWITCHES = 8         # §11.4
T_BAR = 2.0                      # §11.4
FORWARD_BARS_START = "2026-01-02"
NEW_YORK = ZoneInfo("America/New_York")

DECISIONS_DIR = PAPER_LOG_DIR / "decisions"
FROZEN_START = PAPER_LOG_DIR / "frozen_start.json"  # the holdings before the first record; written once, never re-estimated
FORWARD_RAW_DIR = PAPER_LOG_DIR / "raw"
FORWARD_MANIFEST = PAPER_LOG_DIR / "manifest.json"
SHADOW_CSV = PAPER_LOG_DIR / "shadow.csv"
WAITS_CSV = PAPER_LOG_DIR / "waits.csv"
INTERIM_JSON = PAPER_LOG_DIR / "interim.json"

LABEL = "forward record, no paper order (section 11); history verdict: inconclusive (fragile)"
NOT_YET_SCORED = "Not yet scored"
TRIALS = ("T1", "T2", "T3")
FRED_IDS = ("DGS10", "DTB3", "DGS7")
STRATEGIES = ("B1", "B2", "B3", "T1", "T2", "T3")
SHADOW_COLUMNS = (["signal_date", "execution_date", "period_end", "start_bar", "end_bar", "r_IEF", "r_BIL"]
                  + list(STRATEGIES) + ["d"] + [f"{t}_holding" for t in TRIALS] + [f"{t}_switched" for t in TRIALS]
                  + ["weight_b3", "cost_per_side", "run_at_utc"])

VERDICT_NOT_TESTABLE = "not testable"
VERDICT_SUPPORTED = "supported (forward)"
VERDICT_REFUTED = "refuted (forward)"
VERDICT_INCONCLUSIVE = "inconclusive (forward)"


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc(stamp) -> pd.Timestamp:
    ts = pd.Timestamp(stamp)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def close_utc(day) -> pd.Timestamp:
    """16:00 New York time on ``day``, in UTC (EST or EDT as it falls)."""
    d = pd.Timestamp(day)
    return pd.Timestamp(datetime(d.year, d.month, d.day, 16, 0, tzinfo=NEW_YORK)).tz_convert("UTC")


def frozen_weight(history_dir: Path = HISTORY_DIR) -> float:
    return float(json.loads((Path(history_dir) / "summary.json").read_text(encoding="utf-8"))["weight_b3"])


# --- Signal date and targets ------------------------------------------------------------------

def signal_status(fred: dict[str, pd.Series], month: str) -> tuple[str, pd.Timestamp | None, str]:
    """(``final`` | ``wait``, t, why).  ``final`` once FRED has t and a row
    (possibly empty) for every later weekday of the month that is not an
    NYSE holiday."""
    period = pd.Period(month, "M")
    t = signal_dates(fred["DGS10"], fred["DTB3"], month, month).iloc[0]
    if pd.isna(t):
        return "wait", None, f"FRED has no day in {month} with both DGS10 and DTB3"
    t = pd.Timestamp(t)
    for name in FRED_IDS:  # a row on t itself (possibly empty: an empty DGS7 then holds T3, §16 (c))
        if t not in fred[name].index:
            return "wait", t, f"{name} has no row yet for t = {t.date()}"
    later = pd.bdate_range(t + pd.Timedelta(days=1), period.to_timestamp(how="end").normalize())
    open_days = later.intersection(nyse_trading_days(later[0], later[-1])) if len(later) else later
    for name in ("DGS10", "DTB3"):
        missing = open_days.difference(fred[name].index)
        if len(missing):
            return "wait", t, (f"{name} has no row yet for {missing[0].date()}; t = {t.date()} is not final "
                               f"until every later weekday of {month} has a row")
    return "final", t, ""


def targets_at(fred: dict[str, pd.Series], t: pd.Timestamp) -> dict:
    """T1–T3 on t with the study's signal functions, from observations dated
    on or before t only.  A trial undefined on t (DGS7 missing) has target None."""
    cut = {name: s.loc[s.index <= t] for name, s in fred.items()}
    dates = pd.Series([t], index=pd.PeriodIndex([t.to_period("M")], freq="M"), name="signal_date")
    out = {}
    for trial, fn in (("T1", lambda: t1(cut["DGS10"], cut["DTB3"], dates)),
                      ("T2", lambda: t2(cut["DGS10"], cut["DTB3"], dates)),
                      ("T3", lambda: t3(cut["DGS10"], cut["DGS7"], cut["DTB3"], dates))):
        try:
            frame = fn()
        except ValueError as exc:
            out[trial] = {"value": None, "target": None, "note": str(exc)}
            continue
        out[trial] = {"value": float(frame["value"].iloc[0]), "target": str(frame["target"].iloc[0])}
    return out


def inputs_at(fred: dict[str, pd.Series], t: pd.Timestamp) -> dict:
    return {name: (None if pd.isna(fred[name].get(t, np.nan)) else float(fred[name].loc[t])) for name in FRED_IDS}


def execution_for(t: pd.Timestamp, now_utc) -> tuple[pd.Timestamp | None, int, pd.Timestamp]:
    """(execution date or None, NYSE days slipped, deadline).  The first NYSE
    day after t whose close is after ``now``; None past the third."""
    days = nyse_trading_days(t + pd.Timedelta(days=1), t + pd.Timedelta(days=15))[:MAX_NYSE_DAYS_WAIT]
    now = _utc(now_utc)
    for slipped, day in enumerate(days):
        if now < close_utc(day):
            return day, slipped, close_utc(days[-1])
    return None, MAX_NYSE_DAYS_WAIT, close_utc(days[-1])


# --- Decision record ---------------------------------------------------------------------------

STATUSES = ("ok", "signal unavailable")  # the closed set decision_record writes; nothing else is a record
STUDY = "006-term-spread-switch-long-history"


def _ymd(text) -> object:
    """A strict YYYY-MM-DD date, else None."""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def common_record_violations(record, path: Path, study: str) -> list[str]:
    """Sentences naming what in one committed decision record is not as this
    module's ``decision_record`` writes it: the shape every forward record of
    Studies 006-008 shares.  Empty means the record may be read.  Added
    2026-11-10 after a search showed no reader held any column (research/
    POST_MORTEMS.md): a holding spelled ``ief``, a status of ``OK``, a weight
    of 1.5 or a second file for the same month all became the next record's
    starting state."""
    name = Path(path).name
    if not isinstance(record, dict):
        return [f"{name}: the file does not hold a record (a JSON object)"]
    out: list[str] = []
    status = record.get("status")
    if status not in STATUSES:
        out.append(f"{name}: status {status!r} is not one of {list(STATUSES)}")
    if record.get("study") != study:
        out.append(f"{name}: study {record.get('study')!r} is not {study}")
    month = record.get("signal_month")
    try:
        datetime.strptime(month, "%Y-%m")
    except (TypeError, ValueError):
        out.append(f"{name}: signal_month {month!r} is not YYYY-MM")
        month = None
    signal = record.get("signal_date")
    signal_day = _ymd(signal)
    if signal is None:
        if status == "ok":
            out.append(f"{name}: an ok record has no signal_date")
        elif month and Path(path).stem != f"{month}-unavailable":
            out.append(f"{name}: a record without a signal date is named <signal_month>-unavailable.json")
    elif signal_day is None:
        out.append(f"{name}: signal_date {signal!r} is not YYYY-MM-DD")
    else:
        if month and signal[:7] != month:
            out.append(f"{name}: signal_date {signal} is not in signal_month {month}")
        if Path(path).stem != signal:
            out.append(f"{name}: the file is not named after its signal_date {signal}")
    execution = record.get("execution_date")
    if status == "ok":
        execution_day = _ymd(execution)
        if execution_day is None:
            out.append(f"{name}: an ok record's execution_date {execution!r} is not YYYY-MM-DD")
        elif signal_day is not None and execution_day < signal_day:
            out.append(f"{name}: execution_date {execution} is before signal_date {signal}")
    elif execution is not None:
        out.append(f"{name}: a record with status {status!r} carries an execution_date")
    try:
        datetime.strptime(record.get("run_at_utc"), "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        out.append(f"{name}: run_at_utc {record.get('run_at_utc')!r} is not a UTC stamp YYYY-MM-DDTHH:MM:SSZ")
    if record.get("paper_order") is not False or record.get("orders") != []:
        out.append(f"{name}: paper_order is not false or orders is not empty; none is placed (section 11)")
    return out


def _legs_violations(name: str, field: str, held) -> list[str]:
    if not isinstance(held, dict) or sorted(held) != sorted(TRIALS):
        return [f"{name}: {field} does not name exactly the trials {list(TRIALS)}"]
    return [f"{name}: {field}.{trial} is {leg!r}, neither {DURATION_LEG} nor {CASH_LEG}"
            for trial, leg in held.items() if leg not in (DURATION_LEG, CASH_LEG)]


def record_violations(record, path: Path) -> list[str]:
    """The common shape plus this study's: holdings before and after name
    exactly the trials and a leg each; an ok record's ``holding_after`` is the
    target its own ``targets`` entry names (the holding before it when the
    target is null), each target follows the sign of its value by the study's
    rule, and ``switch`` says whether the holding changed; an unavailable
    record holds every position."""
    out = common_record_violations(record, path, STUDY)
    if not isinstance(record, dict):
        return out
    name = Path(path).name
    before, after = record.get("holding_before"), record.get("holding_after")
    out += _legs_violations(name, "holding_before", before)
    out += _legs_violations(name, "holding_after", after)
    if out:
        return out
    status, targets, switch = record.get("status"), record.get("targets"), record.get("switch")
    if status == "signal unavailable":
        if after != before:
            out.append(f"{name}: an unavailable record's holding_after differs from its holding_before")
        if targets is not None:
            out.append(f"{name}: an unavailable record carries targets")
        return out
    if not isinstance(targets, dict) or sorted(targets) != sorted(TRIALS):
        return out + [f"{name}: targets does not name exactly the trials {list(TRIALS)}"]
    for trial in TRIALS:
        entry = targets[trial]
        target = entry.get("target") if isinstance(entry, dict) else "(not an entry)"
        value = entry.get("value") if isinstance(entry, dict) else None
        if target not in (None, DURATION_LEG, CASH_LEG):
            out.append(f"{name}: targets.{trial}.target is {target!r}, neither {DURATION_LEG}, {CASH_LEG} nor null")
            continue
        if target is not None:
            try:
                implied = str(target_from_value(pd.Series([float(value)])).iloc[0])
            except (TypeError, ValueError):
                implied = None
            if value is None or not np.isfinite(float(value)) or implied != target:
                out.append(f"{name}: targets.{trial} value {value!r} does not imply {target} by the study's rule")
        if after[trial] != (target or before[trial]):
            out.append(f"{name}: holding_after.{trial} {after[trial]} is not the target its own entry names "
                       f"({target or before[trial]})")
    if not isinstance(switch, dict) or sorted(switch) != sorted(TRIALS) or any(
            switch[trial] is not (after[trial] != before[trial]) for trial in TRIALS):
        out.append(f"{name}: switch does not say, trial by trial, whether holding_after differs from holding_before")
    return out


def load_records(directory: Path = DECISIONS_DIR, violations=None) -> list[dict]:
    """Every record in the folder, by signal month, each held against the
    shape its writer gives it (``violations``, this study's gate by default)
    and the folder held to one record per month and per file name; refuses
    the whole folder by name otherwise, so nothing downstream reads a record
    no writer wrote (2026-11-10)."""
    directory = Path(directory)
    if not directory.exists():
        return []
    check = violations or record_violations
    records: list[tuple[str, dict]] = []
    problems: list[str] = []
    for path in sorted(directory.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as bad:
            problems.append(f"{path.name}: not JSON ({bad})")
            continue
        found = check(record, path)
        problems += found
        if not found:
            records.append((path.stem, record))
    months = [r["signal_month"] for _, r in records]
    problems += [f"two records for {m}: never rewritten, never doubled (section 11.2)" for m in sorted(set(months))
                 if months.count(m) > 1]
    if problems:
        raise ValueError(f"{directory}: a decision record is not as its writer writes it; fix the record, never the "
                         "reader: " + "; ".join(problems))
    return [r for _, r in sorted(records, key=lambda item: item[1]["signal_month"])]


def freeze_starting_holdings(fred_frozen: dict[str, pd.Series], path: Path = FROZEN_START,
                             source_sha256: dict[str, str] | None = None, frozen_at_utc: str | None = None) -> Path:
    """Write, once, the holdings before the first record: the targets of the
    ``STARTING_MONTH`` signal from the study's frozen FRED files (no return
    involved), with the signal date, the inputs on it and the files' hashes.
    Refuses to overwrite: the starting state is frozen and never re-estimated
    (2026-10-31; until then it was recomputed from the git-ignored data/raw/
    at every run, so a fresh checkout could not write a record)."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"{path} exists; the starting state is frozen once and never rewritten")
    t = pd.Timestamp(signal_dates(fred_frozen["DGS10"], fred_frozen["DTB3"], STARTING_MONTH, STARTING_MONTH).iloc[0])
    targets = targets_at(fred_frozen, t)
    payload = {
        "what": (f"the holdings before the first forward record: the T1, T2 and T3 targets of the {STARTING_MONTH} "
                 "signal from the study's frozen FRED files (section 11.1); frozen once, never re-estimated"),
        "starting_month": STARTING_MONTH,
        "signal_date": str(t.date()),
        "frozen_at_utc": frozen_at_utc or utc_now(),
        "source_sha256": dict(source_sha256 or {}),
        "inputs": inputs_at(fred_frozen, t),
        "targets": targets,
        "holdings": {trial: targets[trial]["target"] for trial in TRIALS},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def starting_holdings(path: Path = FROZEN_START) -> dict:
    """The holdings before the first record, from the frozen starting-state
    file.  The file is checked against itself (review 2026-10-31): the month
    and signal date agree, each holding is the target its own ``targets``
    entry names and that target follows the sign of the entry's value by the
    study's rule (positive spread: the duration leg), so an edited holding or
    value is refused.  The values themselves need the history the file does
    not carry; their provenance is the source hashes."""
    frozen = json.loads(Path(path).read_text(encoding="utf-8"))
    name = Path(path).name
    if frozen["starting_month"] != STARTING_MONTH:
        raise ValueError(f"{name} was frozen for {frozen['starting_month']}, not {STARTING_MONTH}")
    if pd.Timestamp(frozen["signal_date"]).to_period("M") != pd.Period(STARTING_MONTH, "M"):
        raise ValueError(f"{name}: signal date {frozen['signal_date']} is not in {STARTING_MONTH}")
    held = {}
    for trial in TRIALS:
        entry = frozen["targets"][trial]
        leg = frozen["holdings"][trial]
        if leg not in (DURATION_LEG, CASH_LEG):
            raise ValueError(f"{name}: the {trial} holding is neither {DURATION_LEG} nor {CASH_LEG}: {leg}")
        if entry["target"] != leg:
            raise ValueError(f"{name}: the {trial} holding ({leg}) is not the target its own entry names "
                             f"({entry['target']}); the frozen starting state was edited")
        value = entry["value"]
        if value is None or not np.isfinite(float(value)):
            raise ValueError(f"{name}: the {trial} value is not a number; the frozen starting state was edited")
        implied = str(target_from_value(pd.Series([float(value)])).iloc[0])  # the study's own rule (§6.1)
        if implied != leg:
            raise ValueError(f"{name}: the {trial} value {value} implies {implied}, not {leg}; the frozen starting "
                             "state was edited")
        held[trial] = leg
    return held


def holdings_before(records: list[dict], start: dict) -> dict:
    """The holdings in force before the next record: the last record's
    ``holding_after``, with each record's ``holding_before`` held equal to the
    state in force before it (the frozen start for the first), so an edited
    link in the chain is refused rather than carried (2026-11-10)."""
    held = dict(start)
    for record in records:
        if record["holding_before"] != held:
            raise ValueError(f"the record for {record['signal_month']} says holding_before {record['holding_before']} "
                             f"but the state in force before it was {held}; fix the record, never the reader")
        held = dict(record["holding_after"])
    return held


def decision_record(fred: dict[str, pd.Series], month: str, held: dict, earlier_ok: int, now_utc: str,
                    input_sha256: dict | None = None) -> dict | None:
    """The record for ``month``, or None when the run must wait (nothing is
    written).  ``earlier_ok`` = number of earlier records with status ok."""
    base = {"study": STUDY, "label": LABEL, "signal_month": month,
            "run_at_utc": now_utc, "holding_before": dict(held), "input_sha256": dict(input_sha256 or {}),
            "paper_order": False, "orders": []}
    state, t, why = signal_status(fred, month)
    if state == "final":
        assert t is not None
        execution, slipped, deadline = execution_for(t, now_utc)
    else:
        if t is None:
            last = pd.Period(month, "M").to_timestamp(how="end").normalize()
            t_guess = pd.bdate_range(last - pd.Timedelta(days=6), last)[-1]
        else:
            t_guess = t
        execution, slipped, deadline = execution_for(t_guess, now_utc)
        if execution is not None:
            return None
    if execution is None:
        return {**base, "status": "signal unavailable", "signal_date": None if t is None else str(t.date()),
                "execution_date": None, "days_slipped": None, "targets": None, "holding_after": dict(held),
                "notes": (f"no record by the close of the third NYSE day after the signal date "
                          f"({deadline.strftime('%Y-%m-%dT%H:%M:%SZ')}); every trial holds its position and the "
                          f"holding period runs on (section 11.2, Study 001 section 11.2). {why}").strip()}
    assert t is not None
    targets = targets_at(fred, t)
    after = {trial: (targets[trial]["target"] or held.get(trial)) for trial in TRIALS}
    record = {**base, "status": "ok", "signal_date": str(t.date()), "execution_date": str(execution.date()),
              "days_slipped": int(slipped), "inputs_on_signal_date": inputs_at(fred, t),
              "spread": targets["T1"]["value"], "targets": targets, "holding_after": after,
              "switch": {trial: after[trial] != held.get(trial) for trial in TRIALS},
              "notes": "T1 on trial; T2 and T3 registered trials. A trial undefined on t holds its position. "
                       "No order is placed for any of them."}
    if earlier_ok and earlier_ok % BLOCK_PERIODS == 0:
        record["scoring"] = {"block": earlier_ok // BLOCK_PERIODS, "periods": BLOCK_PERIODS,
                             "scoring_date": str(execution.date()),
                             "rule": "scored once, after this record's execution date ends the block (section 11.3)"}
    return record


def _shown(path: Path) -> Path:
    """The path as printed: relative to the study when inside it, else as it is (a test's patched folder)."""
    try:
        return path.relative_to(STUDY_DIR)
    except ValueError:
        return path


def write_record(record: dict, directory: Path = DECISIONS_DIR, violations=None) -> Path:
    """One file per month, never rewritten; the record is held to its own
    writer's shape before it is written (``violations``, this study's gate by
    default), as every reader holds it afterwards (2026-11-10)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    name = record["signal_date"] or f"{record['signal_month']}-unavailable"
    path = directory / f"{name}.json"
    found = (violations or record_violations)(record, path)
    if found:
        raise ValueError("the record to be written is not as its writer writes it: " + "; ".join(found))
    if path.exists() or any(r["signal_month"] == record["signal_month"] for r in load_records(directory, violations)):
        raise FileExistsError(f"a record for {record['signal_month']} exists: never rewritten (section 11.2)")
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def log_wait(month: str, now_utc: str, why: str, path: Path = WAITS_CSV) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"signal_month": month, "checked_at_utc": now_utc, "why": why}]).to_csv(
        path, mode="a", header=not path.exists(), index=False)


# --- Shadow line --------------------------------------------------------------------------------

def read_shadow(path: Path = SHADOW_CSV) -> pd.DataFrame:
    path = Path(path)
    return pd.read_csv(path) if path.exists() else pd.DataFrame(columns=SHADOW_COLUMNS)


def _first_bar_on_or_after(bars: pd.DatetimeIndex, day: pd.Timestamp) -> pd.Timestamp | None:
    later = bars[bars >= day]
    return later[0] if len(later) else None


def shadow_line(indices: dict[str, pd.Series], ok_records: list[dict], shadow: pd.DataFrame, start: dict,
                weight_b3: float, cost: float = COST_CASES["base"], now_utc: str | None = None) -> dict:
    """The line of the period from ``ok_records[-2]``'s execution date to
    ``ok_records[-1]``'s, through the study's engine on every period so far."""
    if len(ok_records) < 2 or len(shadow) != len(ok_records) - 2:
        raise ValueError("a line needs the next ok record and every earlier line, in order")
    previous, current = ok_records[-2], ok_records[-1]
    common = indices[DURATION_LEG].index.intersection(indices[CASH_LEG].index).sort_values()
    s_day, e_day = pd.Timestamp(previous["execution_date"]), pd.Timestamp(current["execution_date"])
    s_bar, e_bar = _first_bar_on_or_after(common, s_day), _first_bar_on_or_after(common, e_day)
    if s_bar is None or e_bar is None:
        raise ValueError("no common IEF/BIL bar on or after an execution date; the line waits for the close")
    r_new = {leg: float(indices[leg].loc[e_bar] / indices[leg].loc[s_bar] - 1.0) for leg in (DURATION_LEG, CASH_LEG)}
    months = [r["signal_month"] for r in ok_records[:-1]]
    returns = pd.DataFrame({DURATION_LEG: list(shadow["r_IEF"].astype(float)) + [r_new[DURATION_LEG]],
                            CASH_LEG: list(shadow["r_BIL"].astype(float)) + [r_new[CASH_LEG]]},
                           index=pd.Index(months, name="month"))
    line = {"signal_date": previous["signal_date"], "execution_date": previous["execution_date"],
            "period_end": current["execution_date"], "start_bar": str(s_bar.date()), "end_bar": str(e_bar.date()),
            "r_IEF": r_new[DURATION_LEG], "r_BIL": r_new[CASH_LEG]}
    bench = backtest.benchmarks(returns, weight_b3, cost)
    for name in ("B1", "B2", "B3"):
        line[name] = float(bench[name]["r"].iloc[-1])
    for trial in TRIALS:
        targets = pd.Series([r["holding_after"][trial] for r in ok_records[:-1]], index=returns.index)
        result = backtest.run_switching(targets, returns, cost, initial_holding=start[trial])
        line[trial] = float(result["r"].iloc[-1])
        line[f"{trial}_holding"] = str(result["holding"].iloc[-1])
        line[f"{trial}_switched"] = bool(result["switched"].iloc[-1])
    line["d"] = line["T1"] - line["B3"]
    line.update(weight_b3=weight_b3, cost_per_side=cost, run_at_utc=now_utc or utc_now())
    return {c: line[c] for c in SHADOW_COLUMNS}


def append_shadow(line: dict, path: Path = SHADOW_CSV) -> Path:
    path = Path(path)
    existing = read_shadow(path)
    if len(existing) and (existing["execution_date"].astype(str) == line["execution_date"]).any():
        raise FileExistsError(f"shadow.csv already has the period starting {line['execution_date']}")
    if len(existing) and str(existing["period_end"].iloc[-1]) != line["execution_date"]:
        raise ValueError("the period does not follow the last recorded one")
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([line], columns=SHADOW_COLUMNS).to_csv(path, mode="a", header=not path.exists(), index=False)
    return path


# --- Interim and scoring --------------------------------------------------------------------------

def _flags(column: pd.Series) -> np.ndarray:
    return column.astype(str).str.lower().eq("true").to_numpy()


def interim(shadow: pd.DataFrame, now_utc: str | None = None) -> dict:
    """Counts and cumulative returns so far, under "Not yet scored"; no
    t-statistic and no verdict sentence before the block is complete."""
    n = int(len(shadow))
    out = {"heading": NOT_YET_SCORED, "label": LABEL, "holding_periods": n, "written_at_utc": now_utc or utc_now(),
           "scored_after": f"{BLOCK_PERIODS} holding periods", "periods_to_scoring": (-n) % BLOCK_PERIODS,
           "T1_switches": int(_flags(shadow["T1_switched"]).sum()) if n else 0, "cumulative": {}, "mean_d": None}
    if n:
        out["mean_d"] = float(shadow["d"].astype(float).mean())
        out["cumulative"] = {s: float(np.prod(1.0 + shadow[s].astype(float).to_numpy()) - 1.0) for s in STRATEGIES}
    return out


def forward_verdict(d: pd.Series, t1_holdings: pd.Series, t1_switches: int) -> dict:
    """§11.4 on one block of 60 periods."""
    if t1_holdings.nunique() == 1:
        row = VERDICT_NOT_TESTABLE
        nw = None
    else:
        nw = stats.newey_west_mean(d)
        if nw["mean"] > 0 and nw["t"] >= T_BAR:
            row = VERDICT_SUPPORTED
        elif nw["t"] <= -T_BAR:
            row = VERDICT_REFUTED
        else:
            row = VERDICT_INCONCLUSIVE
    labels = ["low-powered"] if t1_switches < LOW_POWERED_SWITCHES else []
    return {"verdict": row, "labels": labels, "newey_west": nw, "T1_switches": int(t1_switches)}


def score(shadow: pd.DataFrame, records: list[dict], block: int = 1) -> dict:
    """Score block ``block`` once.  Refuses unless the record that ends the
    block carries its scoring date (written before any statistic)."""
    end = block * BLOCK_PERIODS
    if len(shadow) < end:
        raise RuntimeError(f"{len(shadow)} periods; block {block} is scored after {end} (section 11.3)")
    ok = [r for r in records if r["status"] == "ok"]
    if len(ok) <= end or ok[end].get("scoring", {}).get("block") != block:
        raise RuntimeError("the decision record that ends the block carries no scoring date (section 11.3)")
    rows = shadow.iloc[end - BLOCK_PERIODS:end]
    out = forward_verdict(rows["d"].astype(float).reset_index(drop=True), rows["T1_holding"],
                          int(_flags(rows["T1_switched"]).sum()))
    out.update(block=block, periods=BLOCK_PERIODS, scoring_date=ok[end]["scoring"]["scoring_date"],
               history_verdict="inconclusive (fragile)")
    return out


# --- Inputs -----------------------------------------------------------------------------------------

def fetch_fred(raw_dir: Path = FORWARD_RAW_DIR, manifest: Path = FORWARD_MANIFEST) -> None:
    for name in FRED_IDS:
        fetch_series(name, raw_dir, manifest)


def fetch_alpaca(raw_dir: Path = FORWARD_RAW_DIR, manifest: Path = FORWARD_MANIFEST) -> None:
    for leg in (DURATION_LEG, CASH_LEG):
        fetch_bars(leg, FORWARD_BARS_START, None, raw_dir, manifest)


def load_fred(raw_dir: Path = FORWARD_RAW_DIR) -> dict[str, pd.Series]:
    return {name: load_series(name, raw_dir) for name in FRED_IDS}


def file_hashes(raw_dir: Path, prefix: str) -> dict:
    return {p.name: sha256_of(p) for p in sorted(Path(raw_dir).glob(f"{prefix}*"))}


# --- Entry point ------------------------------------------------------------------------------------

def refusal(month: str, now_utc: str, fred: dict | None = None) -> str | None:
    if pd.Period(month, "M") < pd.Period(FIRST_SIGNAL_MONTH, "M"):
        return f"{month} is before the first forward month {FIRST_SIGNAL_MONTH} (section 11.1); never backdated"
    period_end = pd.Period(month, "M").to_timestamp(how="end").normalize()
    last_weekday = pd.bdate_range(period_end - pd.Timedelta(days=6), period_end)[-1]
    earliest = last_weekday.tz_localize("UTC") + pd.Timedelta(hours=EARLIEST_UTC[0], minutes=EARLIEST_UTC[1])
    if _utc(now_utc) < earliest:
        return f"before {earliest.strftime('%Y-%m-%dT%H:%M:%SZ')}: the month's last H.15 release is not out"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Study 006 forward record (section 11). No paper order.")
    parser.add_argument("step", choices=("decide", "shadow", "interim"))
    parser.add_argument("--signal-month", help="YYYY-MM")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="print, write nothing")
    args = parser.parse_args(argv)
    now = utc_now()
    if args.step == "interim":
        payload = interim(read_shadow(SHADOW_CSV), now)
        print(json.dumps(payload, indent=2))
        if not args.dry_run:
            INTERIM_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return 0
    if not args.signal_month:
        parser.error("--signal-month is required")
    why = refusal(args.signal_month, now)
    if why:
        print(f"refused: {why}")
        return 1
    # Every path is passed by name so that a test can point the module's constants at an empty folder: a default
    # argument is bound at import and a patched module attribute never reaches it (found 2026-10-31: the
    # missing-input test passed locally only because the real paper-log/raw/ was read). The decide step was fixed
    # that day; the shadow and interim steps kept five bound defaults until tools/check_bound_defaults.py found
    # them on 2026-11-01 (research/POST_MORTEMS.md).
    records = load_records(DECISIONS_DIR)
    try:
        start = starting_holdings(FROZEN_START)
    except FileNotFoundError as missing:
        print(f"refused: the frozen starting state is not in paper-log/ ({Path(missing.filename).name}); it is "
              "written once by forward.freeze_starting_holdings from the study's data/raw/ and committed, never "
              "recomputed at run time")
        return 1
    except (KeyError, ValueError) as bad:  # an edited, truncated or malformed frozen file (review 2026-10-31)
        print(f"refused: the frozen starting state cannot be used ({type(bad).__name__}: {bad}); restore "
              f"{FROZEN_START.name} from git, never rewrite it")
        return 1
    if args.step == "decide":
        if any(r["signal_month"] == args.signal_month for r in records):
            print(f"refused: a record for {args.signal_month} exists")
            return 1
        if args.fetch and not args.dry_run:
            fetch_fred(FORWARD_RAW_DIR, FORWARD_MANIFEST)
        elif args.fetch:
            print("note: --dry-run does not fetch; paper-log/raw/ is read as it is")
        try:
            fred = load_fred(FORWARD_RAW_DIR)
        except FileNotFoundError as missing:
            print(f"refused: an input is not in paper-log/raw/ ({Path(missing.filename).name}); run with --fetch")
            return 1
        held = holdings_before(records, start)
        earlier_ok = sum(r["status"] == "ok" for r in records)
        record = decision_record(fred, args.signal_month, held, earlier_ok, now, file_hashes(FORWARD_RAW_DIR, "fred_"))
        if record is None:
            reason = signal_status(fred, args.signal_month)[2]
            print(f"wait: {reason}; re-check on the next run")
            if not args.dry_run:
                log_wait(args.signal_month, now, reason, WAITS_CSV)
            return 1
        print(json.dumps(record, indent=2, sort_keys=True))
        if not args.dry_run:
            print(f"written: {_shown(write_record(record, DECISIONS_DIR))}")
        return 0 if record["status"] == "ok" else 1
    ok = [r for r in records if r["status"] == "ok"]
    upto = [r for r in ok if r["signal_month"] <= args.signal_month]
    if not upto or upto[-1]["signal_month"] != args.signal_month or len(upto) < 2:
        print("refused: the line needs an ok record for this month and an earlier one (section 11.3)")
        return 1
    if args.fetch and not args.dry_run:
        fetch_alpaca(FORWARD_RAW_DIR, FORWARD_MANIFEST)
    indices = {leg: total_return_index(load_bars(leg, FORWARD_RAW_DIR)) for leg in (DURATION_LEG, CASH_LEG)}
    if _utc(now) < close_utc(upto[-1]["execution_date"]):
        print("refused: the line is written after the execution date's close")
        return 1
    line = shadow_line(indices, upto, read_shadow(SHADOW_CSV), start, frozen_weight(), now_utc=now)
    print(json.dumps(line, indent=2, default=str))
    if not args.dry_run:
        print(f"appended: {_shown(append_shadow(line, SHADOW_CSV))}")
        INTERIM_JSON.write_text(json.dumps(interim(read_shadow(SHADOW_CSV), now), indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
