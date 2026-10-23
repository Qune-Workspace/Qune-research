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
* "Due" means today is on or after ``due_on``; a value for the due date must
  exist (the last valid observation on or before ``due_on`` is used and named).

Test kinds (the ``test`` column):
    eq_on_due                value on due date equals threshold_low (to 1e-9)
    between_on_due           threshold_low <= value on due date <= threshold_high
    below_on_due             value on due date <  threshold_low
    above_on_due             value on due date >  threshold_low
    within_every_day_until_due   every valid observation from made_on (exclusive)
                             to due_on (inclusive) lies in [threshold_low, threshold_high]
"""
from __future__ import annotations

import argparse
import csv
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
TESTS = {"eq_on_due", "between_on_due", "below_on_due", "above_on_due", "within_every_day_until_due"}


def read_ledger(path: Path = LEDGER) -> pd.DataFrame:
    ledger = pd.read_csv(path, dtype=str, keep_default_na=False)
    validate_ledger(ledger)
    return ledger


def validate_ledger(ledger: pd.DataFrame) -> None:
    missing = [c for c in LEDGER_COLUMNS if c not in ledger.columns]
    if missing:
        raise ValueError(f"ledger lacks columns {missing}")
    if ledger["id"].duplicated().any():
        raise ValueError("ledger ids must be unique")
    bad = ledger[~ledger["test"].isin(TESTS)]
    if not bad.empty:
        raise ValueError(f"unknown test kinds: {sorted(bad['test'])}")
    made = pd.to_datetime(ledger["made_on"], format="%Y-%m-%d")
    due = pd.to_datetime(ledger["due_on"], format="%Y-%m-%d")
    if (due <= made).any():
        raise ValueError("every due_on must be after made_on")
    for col in ("threshold_low", "confidence"):
        pd.to_numeric(ledger[col], errors="raise")
    high = ledger.loc[ledger["threshold_high"] != "", "threshold_high"]
    pd.to_numeric(high, errors="raise")


def evaluate(row: pd.Series, series: pd.Series) -> dict:
    """Apply one row's test to a series.  Returns observed_on, observed_value,
    result ('hit' or 'miss') and a note."""
    due = pd.Timestamp(row["due_on"])
    made = pd.Timestamp(row["made_on"])
    low = float(row["threshold_low"])
    high = float(row["threshold_high"]) if row["threshold_high"] != "" else float("nan")
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
    elif kind == "above_on_due":
        hit = value > low
    else:
        raise ValueError(f"unknown test {kind}")
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


def read_outcomes(path: Path = OUTCOMES) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=OUTCOME_COLUMNS)
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def due_unscored(ledger: pd.DataFrame, outcomes: pd.DataFrame, today: pd.Timestamp) -> pd.DataFrame:
    scored = set(outcomes["id"])
    due = pd.to_datetime(ledger["due_on"]) <= today
    return ledger[due & ~ledger["id"].isin(scored)]


def append_outcome(path: Path, record: dict) -> None:
    exists = path.exists()
    with path.open("a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTCOME_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(record)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", required=True, help="YYYY-MM-DD; calls due on or before are scored")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    today = pd.Timestamp(args.today)
    ledger = read_ledger()
    outcomes = read_outcomes()
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
        result = evaluate(row, series)
        record = {"id": row["id"], "scored_on": str(today.date()), **result,
                  "raw_sha256": ";".join(qdata.sha256_of(qdata.fred_path(sid, RAW_DIR)) for sid in fetched)}
        print(record)
        if not args.dry_run:
            append_outcome(OUTCOMES, record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
