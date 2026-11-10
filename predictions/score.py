"""Score the desk's logged calls against public FRED data, once each, when due.

    python score.py --today 2026-12-31            # fetch, score every due unscored call
    python score.py --today 2026-12-31 --dry-run  # show what would be scored, write nothing

Rules, in code and not only in prose:
* ``ledger.csv`` is append-only and this script never writes to it.  A call is
  one row, written before its outcome; its id, dates, thresholds and basis do
  not change afterwards.
* A call is scored once.  A second attempt on a scored id is refused.
* Scores go to ``outcomes.csv`` with the observed value, the date it was
  observed and the data file's hash; a miss is written like a hit.
* "Due" means today is on or after ``due_on``.  A due call is scored only once
  the fetched series reaches the due date: it must hold a row dated on or after
  ``due_on`` (FRED writes a row with an empty value on holidays).  Until then
  the call is reported as not yet published and left unscored, so a run made
  before the day's print cannot score yesterday's value as today's.  When the
  due date's own value is empty, the last valid observation before it is used
  and named.  (Added 2026-10-28, before any call was scored: the first version
  fell back to the last earlier observation even when the due date's row had
  not been published yet.)

Test kinds (the ``test`` column):
    eq_on_due                value on due date equals threshold_low (to 1e-9)
    between_on_due           threshold_low <= value on due date <= threshold_high
    below_on_due             value on due date <  threshold_low
    above_on_due             value on due date >  threshold_low
    within_every_day_until_due   every valid observation from made_on (exclusive)
                             to due_on (inclusive) lies in [threshold_low, threshold_high]

* A row's shape is held against its test kind before anything is scored (added
  2026-11-09, predictions/POST_MORTEMS.md "A band with one side scored as a result"):
  a two-sided test carries both thresholds with low < high, a one-sided test carries
  no threshold_high, the series is one the baseline can price (``SCORABLE_SERIES``,
  held equal to ``baseline.SERIES_SPEC`` by a test), statement and basis are not
  empty, and the confidence is a probability in (0, 1) written with two decimals.
  ``validate_ledger`` refuses the row naming its id and column; ``evaluate`` refuses
  a band it cannot read instead of scoring it.  Before this date an empty
  threshold_high on ``between_on_due`` scored a silent miss (``low <= v <= nan`` is
  False) and on ``within_every_day_until_due`` a silent hit (nothing exceeds nan).
* An outcome row is held against the call it scores (added 2026-11-10,
  predictions/POST_MORTEMS.md "A result spelled another way was a miss"): ``result`` is
  ``hit`` or ``miss`` and nothing else, the id is one ledger id and appears once,
  ``made_on <= observed_on <= due_on <= scored_on``, ``observed_value`` is a finite
  number, the note is not empty and ``raw_sha256`` is one or more SHA-256 digests
  joined by ``;``.  ``outcome_row_violations`` is the list; ``read_outcomes`` and
  ``append_outcome`` apply it with the ledger, and ``baseline.skill_summary`` refuses a
  result outside ``RESULTS`` instead of counting it.  Before this date any non-empty
  result that was not the word ``hit`` was counted as a scored miss, an empty one left
  the call "not yet due" for ever while ``due_unscored`` treated it as scored, an id not
  in the ledger was dropped from the table while the call was scored again, and a
  repeated id doubled the call in the Brier.
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qune_research import data as qdata  # noqa: E402

LEDGER = HERE / "ledger.csv"
OUTCOMES = HERE / "outcomes.csv"
RAW_DIR = HERE / "raw"
MANIFEST = HERE / "manifest.json"
LEDGER_COLUMNS = ["id", "made_on", "series", "statement", "test", "threshold_low", "threshold_high",
                  "due_on", "confidence", "basis"]
OUTCOME_COLUMNS = ["id", "scored_on", "observed_on", "observed_value", "result", "note", "raw_sha256"]
RESULTS = frozenset({"hit", "miss"})   # the only words an outcome row may carry as its result
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
TESTS ={"eq_on_due", "between_on_due", "below_on_due", "above_on_due", "within_every_day_until_due"}
TWO_SIDED = {"between_on_due", "within_every_day_until_due"}   # need threshold_low < threshold_high
ONE_SIDED = TESTS - TWO_SIDED                                   # threshold_high must be empty
# Series a call may name: those the baseline can price (baseline.SERIES_SPEC; a test holds the
# two sets equal, baseline.py imports this module so the set cannot be read from there).
SCORABLE_SERIES = frozenset({"DGS10", "DGS2", "DGS30", "T10Y2Y", "T10YIE", "DFEDTARU", "SBCORR63"})


class NotYetPublished(ValueError):
    """The series does not reach the due date yet; retry on a later day."""


def read_ledger(path: Path = LEDGER) -> pd.DataFrame:
    ledger = pd.read_csv(path, dtype=str, keep_default_na=False)
    validate_ledger(ledger)
    return ledger


def _day(text: str, call_id: str, col: str) -> pd.Timestamp:
    try:
        stamp = pd.Timestamp(pd.to_datetime(text, format="%Y-%m-%d"))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{call_id}: {col} {text!r} is not a date YYYY-MM-DD") from exc
    if pd.isna(stamp):  # pandas parses '' to NaT without raising
        raise ValueError(f"{call_id}: {col} {text!r} is not a date YYYY-MM-DD")
    return stamp


def _number(text: str, call_id: str, col: str) -> float:
    try:
        return float(text)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{call_id}: {col} {text!r} is not a number") from exc


def row_shape_violations(row: dict) -> list[str]:
    """Every rule one ledger row must meet on its own, each sentence naming the column.
    The reader (``validate_ledger``) and the committed-file test apply the same list."""
    call_id = str(row.get("id", "")) or "<no id>"
    out: list[str] = []
    if not str(row.get("id", "")).strip():
        out.append(f"{call_id}: id is empty")
    for col in ("statement", "basis"):
        if not str(row.get(col, "")).strip():
            out.append(f"{call_id}: {col} is empty")
    if row.get("series") not in SCORABLE_SERIES:
        out.append(f"{call_id}: series {row.get('series')!r} is not one the baseline can price "
                   f"({', '.join(sorted(SCORABLE_SERIES))})")
    kind = row.get("test")
    if kind not in TESTS:
        out.append(f"{call_id}: test {kind!r} is not a known kind ({', '.join(sorted(TESTS))})")
    try:
        made, due = _day(row.get("made_on", ""), call_id, "made_on"), _day(row.get("due_on", ""), call_id, "due_on")
        if due <= made:
            out.append(f"{call_id}: due_on {row['due_on']} is not after made_on {row['made_on']}")
    except ValueError as exc:
        out.append(str(exc))
    try:
        low = _number(row.get("threshold_low", ""), call_id, "threshold_low")
        high_text = str(row.get("threshold_high", "")).strip()
        if kind in TWO_SIDED:
            if high_text == "":
                out.append(f"{call_id}: threshold_high is empty on the two-sided test {kind}")
            elif not low < _number(high_text, call_id, "threshold_high"):
                out.append(f"{call_id}: threshold_low {low} is not below threshold_high {high_text}")
        elif kind in ONE_SIDED and high_text != "":
            out.append(f"{call_id}: threshold_high {high_text!r} is set on the one-sided test {kind}; leave it empty")
    except ValueError as exc:
        out.append(str(exc))
    conf = str(row.get("confidence", ""))
    try:
        p = _number(conf, call_id, "confidence")
        if not 0.0 < p < 1.0:
            out.append(f"{call_id}: confidence {conf} is not a probability in (0, 1)")
        elif conf != f"{p:.2f}":
            out.append(f"{call_id}: confidence {conf} is not written with two decimals")
    except ValueError as exc:
        out.append(str(exc))
    return out


def validate_ledger(ledger: pd.DataFrame) -> None:
    missing = [c for c in LEDGER_COLUMNS if c not in ledger.columns]
    if missing:
        raise ValueError(f"ledger lacks columns {missing}")
    dupes = sorted(set(ledger.loc[ledger["id"].duplicated(), "id"]))
    if dupes:
        raise ValueError(f"ledger ids must be unique; repeated id {dupes}")
    problems = [p for _, row in ledger.iterrows() for p in row_shape_violations(row.to_dict())]
    if problems:
        raise ValueError("ledger rows refused: " + "; ".join(problems))


def evaluate(row: pd.Series, series: pd.Series) -> dict:
    """Apply one row's test to a series.  Returns observed_on, observed_value,
    result ('hit' or 'miss') and a note."""
    due = pd.Timestamp(row["due_on"])
    made = pd.Timestamp(row["made_on"])
    low = float(row["threshold_low"])
    kind = row["test"]
    if kind not in TESTS:
        raise ValueError(f"{row['id']}: unknown test {kind}")
    if kind in TWO_SIDED:
        if str(row["threshold_high"]).strip() == "":
            raise ValueError(f"{row['id']}: {kind} needs threshold_high; an empty band is not scored")
        high = float(row["threshold_high"])
        if not low < high:
            raise ValueError(f"{row['id']}: threshold_low {low} is not below threshold_high {high}; not scored")
    else:
        if str(row["threshold_high"]).strip() != "":
            raise ValueError(f"{row['id']}: {kind} takes no threshold_high ({row['threshold_high']!r}); not scored")
        high = float("nan")
    if series.empty or series.index.max() < due:
        last = "no rows" if series.empty else f"last row {series.index.max().date()}"
        raise NotYetPublished(f"{row['id']}: series does not reach the due date {due.date()} yet ({last})")
    valid = series.dropna()
    if valid.loc[:due].empty:
        raise ValueError(f"{row['id']}: no observation on or before {due.date()}")
    kind = row["test"]
    if kind == "within_every_day_until_due":
        window = valid.loc[made + pd.Timedelta(days=1):due]
        if window.empty:
            raise ValueError(f"{row['id']}: no observations in the window")
        outside = window[(window < low) | (window > high)]
        hit = outside.empty
        observed_on = str(outside.index[0].date()) if not hit else str(window.index[-1].date())
        observed_value = float(outside.iloc[0]) if not hit else float(window.iloc[-1])
        note = (f"{len(window)} observations in [{low}, {high}]" if hit
                else f"first of {len(outside)} observations outside [{low}, {high}]")
        return {"observed_on": observed_on, "observed_value": observed_value,
                "result": "hit" if hit else "miss", "note": note}
    date = valid.loc[:due].index[-1]
    value = float(valid.loc[date])
    if kind == "eq_on_due":
        hit = abs(value - low) < 1e-9
    elif kind == "between_on_due":
        hit = low <= value <= high
    elif kind == "below_on_due":
        hit = value < low
    else:  # above_on_due; the kind was held to TESTS above
        hit = value > low
    note = "value on the due date" if date == due else f"last observation before the due date ({date.date()})"
    return {"observed_on": str(date.date()), "observed_value": value, "result": "hit" if hit else "miss", "note": note}


DERIVED = {
    # Series the ledger may name that are built from FRED series by the desk view's
    # own functions (desk-view/view_lib.py), so that a call on them is scored by the
    # same definition the note used.
    "SBCORR63": ("SP500", "DGS10"),  # 63-day stock-bond correlation proxy
}


def load_series(series_id: str, fetch) -> pd.Series:
    """``fetch(series_id) -> pd.Series`` for a FRED id; derived ids are built here."""
    if series_id not in DERIVED:
        return fetch(series_id)
    sys.path.insert(0, str(ROOT / "desk-view"))
    import view_lib  # noqa: E402

    if series_id == "SBCORR63":
        stock, yld = (fetch(sid) for sid in DERIVED[series_id])
        return view_lib.rolling_stock_bond_corr(stock, yld, window=63)
    raise ValueError(series_id)


def hash_list_violation(text: str, row_id: str, col: str) -> str | None:
    """``raw_sha256`` is one or more lowercase SHA-256 digests joined by ``;``."""
    parts = str(text).split(";")
    if not parts or any(not SHA256_HEX.match(p) for p in parts):
        return f"{row_id}: {col} {str(text)[:40]!r} is not one or more SHA-256 digests joined by ';'"
    return None


def ledger_rows_by_id(ledger: pd.DataFrame) -> dict[str, dict]:
    return {str(r["id"]): r.to_dict() for _, r in ledger.iterrows()}


def outcome_row_violations(row: dict, call: dict | None) -> list[str]:
    """Every rule one outcome row must meet, each sentence naming the id and the column.
    ``call`` is the ledger row it scores (None when the id is not in the ledger, which is
    itself a violation).  The reader, the writer and the committed-file test apply this list."""
    row_id = str(row.get("id", "")).strip() or "<no id>"
    out: list[str] = []
    if not str(row.get("id", "")).strip():
        out.append(f"{row_id}: id is empty")
    elif call is None:
        out.append(f"{row_id}: id is not a call in the ledger")
    elif str(row.get("id")) != str(call.get("id")):
        out.append(f"{row_id}: id is not written as the ledger writes it ({call.get('id')!r})")
    result = row.get("result")
    if result not in RESULTS:
        out.append(f"{row_id}: result {result!r} is not one of {', '.join(sorted(RESULTS))}")
    if not str(row.get("note", "")).strip():
        out.append(f"{row_id}: note is empty")
    try:
        v = _number(row.get("observed_value", ""), row_id, "observed_value")
        if not math.isfinite(v):
            out.append(f"{row_id}: observed_value {row.get('observed_value')!r} is not finite")
    except ValueError as exc:
        out.append(str(exc))
    bad = hash_list_violation(row.get("raw_sha256", ""), row_id, "raw_sha256")
    if bad:
        out.append(bad)
    try:
        observed = _day(row.get("observed_on", ""), row_id, "observed_on")
        scored = _day(row.get("scored_on", ""), row_id, "scored_on")
        if scored < observed:
            out.append(f"{row_id}: scored_on {row['scored_on']} is before observed_on {row['observed_on']}")
        if call is not None:
            made, due = _day(call.get("made_on", ""), row_id, "made_on"), _day(call.get("due_on", ""), row_id, "due_on")
            if observed < made:
                out.append(f"{row_id}: observed_on {row['observed_on']} is before the call was made ({call['made_on']})")
            if observed > due:
                out.append(f"{row_id}: observed_on {row['observed_on']} is after due_on {call['due_on']}")
            if scored < due:
                out.append(f"{row_id}: scored_on {row['scored_on']} is before due_on {call['due_on']}; a call is scored once due")
    except ValueError as exc:
        out.append(str(exc))
    return out


def validate_outcomes(outcomes: pd.DataFrame, ledger: pd.DataFrame) -> None:
    missing = [c for c in OUTCOME_COLUMNS if c not in outcomes.columns]
    if missing:
        raise ValueError(f"outcomes lack columns {missing}")
    dupes = sorted(set(outcomes.loc[outcomes["id"].duplicated(), "id"]))
    if dupes:
        raise ValueError(f"outcome ids must be unique; repeated id {dupes}")
    calls = ledger_rows_by_id(ledger)
    problems = [p for _, row in outcomes.iterrows()
                for p in outcome_row_violations(row.to_dict(), calls.get(str(row["id"])))]
    if problems:
        raise ValueError("outcome rows refused: " + "; ".join(problems))


def read_outcomes(ledger: pd.DataFrame, path: Path = OUTCOMES) -> pd.DataFrame:
    """The scored calls, every row held against the ledger (``validate_outcomes``)."""
    if not path.exists():
        return pd.DataFrame(columns=OUTCOME_COLUMNS)
    outcomes = pd.read_csv(path, dtype=str, keep_default_na=False)
    validate_outcomes(outcomes, ledger)
    return outcomes


def due_unscored(ledger: pd.DataFrame, outcomes: pd.DataFrame, today: pd.Timestamp) -> pd.DataFrame:
    scored = set(outcomes["id"])
    due = pd.to_datetime(ledger["due_on"]) <= today
    return ledger[due & ~ledger["id"].isin(scored)]


def append_outcome(path: Path, record: dict, ledger: pd.DataFrame) -> None:
    """Write one outcome row after holding it against its call and the rows already written."""
    text = {c: ("" if record.get(c) is None else str(record.get(c))) for c in OUTCOME_COLUMNS}
    existing = read_outcomes(ledger, path)
    if text["id"] in set(existing["id"]):
        raise ValueError(f"{text['id']} is already scored; refusing")
    problems = outcome_row_violations(text, ledger_rows_by_id(ledger).get(text["id"]))
    if problems:
        raise ValueError("outcome row refused: " + "; ".join(problems))
    exists = path.exists()
    with path.open("a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTCOME_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", required=True, help="YYYY-MM-DD; calls due on or before are scored")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    today = pd.Timestamp(args.today)
    ledger = read_ledger()
    outcomes = read_outcomes(ledger)
    todo = due_unscored(ledger, outcomes, today)
    if todo.empty:
        print("nothing due and unscored")
        return 0
    for _, row in todo.iterrows():
        if row["id"] in set(outcomes["id"]):
            raise SystemExit(f"{row['id']} is already scored; refusing")
        fetched: list[str] = []

        def fetch(sid: str, _fetched: list[str] = fetched) -> pd.Series:
            _fetched.append(sid)
            return qdata.fetch_fred(sid, RAW_DIR, MANIFEST)

        series = load_series(row["series"], fetch)
        try:
            result = evaluate(row, series)
        except NotYetPublished as exc:
            print(f"NOT SCORED: {exc}; retry on a later day")
            continue
        record = {"id": row["id"], "scored_on": str(today.date()), **result,
                  "raw_sha256": ";".join(qdata.sha256_of(qdata.fred_path(sid, RAW_DIR)) for sid in fetched)}
        print(record)
        if not args.dry_run:
            append_outcome(OUTCOMES, record, ledger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
