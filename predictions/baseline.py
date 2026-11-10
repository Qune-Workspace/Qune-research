"""Market-anchored baseline probabilities for the desk's logged calls.

    python baseline.py --asof 2026-10-21 --ids V1-2026-10-23,V2-2026-10-23   # fetch, compute, append
    python baseline.py --asof 2026-10-21 --ids ... --dry-run                 # compute, write nothing
    python baseline.py --summary                                              # desk vs baseline so far

Why this exists.  A hit rate on a handful of calls says nothing: a call that the
forward curve already prices at 80% is not skill when it comes true.  So every
call gets a second probability, computed by a frozen method from public data as
of the day the call was made, and the ledger is judged on the *difference*
between the desk's Brier score and the baseline's.  Both are written before the
outcome.  The method is in this file; a reader can rerun it.

Rules, in code and not only in prose:
* ``baselines.csv`` is append-only.  One row per call id; a second attempt on an
  id is refused.  ``ledger.csv`` is never written here.
* Every number comes from observations on or before ``--asof`` (the date of the
  last market observation the desk view used when the call was made); later
  observations in the fetched files are dropped before anything is computed.
* The raw files used are hashed into the row.

Methods (the ``method`` column), chosen by the series and test of the call:
    bill_implied_hike       Policy-rate calls (``eq_on_due`` on DFEDTARU).  The 4-week
                            bill (DTB4WK) minus the effective funds rate (EFFR), scaled by
                            T / (T - t) where T is the bill's life in days and t the days
                            until the meeting (the day before ``due_on``), divided by the
                            hike step, clipped to [0, 1].  Attributes the whole spread to
                            policy; the bill-funds basis (usually a few basis points,
                            either sign) is ignored.  Not futures: FRED has none.
    forward_normal          Level calls on a yield or a yield spread (``between``,
                            ``below``, ``above`` on the due date).  Centre = the forward
                            level implied by the par curve under the zero-coupon
                            approximation f = (y_T * T - y_h * h) / (T - h), with y_h
                            the 3-month bill; scale = trailing 252-observation standard
                            deviation of daily changes times sqrt(h business days).
                            Normal distribution.  Realised, not implied, volatility
                            (FRED carries no option-implied series), so the width is a
                            proxy and is labelled as one in the row.
    forward_normal_barrier  ``within_every_day_until_due``: 200,000 seeded random-walk
                            paths with the same daily scale and the same drift to the
                            forward centre; the share that stays inside the band on every
                            step.  Breakevens use a zero drift (no forward is read).
    persistence_base_rate   Derived series with no market price (SBCORR63): the
                            historical share of days on which the series was on the same
                            side of the threshold h business days later, given today's
                            side.  Not market-implied; labelled as a base rate.

Horizon h counts weekdays from ``asof`` (exclusive) to ``due_on`` (inclusive);
holidays are not removed (a one- or two-day overstatement of h, disclosed).

Discipline after the V1 miss (2026-10-30, see POST_MORTEMS.md): for calls made on or
after 2026-10-30 the baseline row is computed before the confidence is written and
committed with the call; a confidence more than 0.20 from the baseline names the
baseline and what the market is missing in the basis.  ``max_policy_spread`` is the
check a front-end reading must pass before a bill spread is called expectations.
``desk-view/tests/test_ledger_discipline.py`` enforces the first two rules on the
committed files.

A baseline row is held against the call it prices (added 2026-11-10, POST_MORTEMS.md
"A result spelled another way was a miss"): the id is one ledger id and appears once;
``method`` is the frozen method for the call's series and test (``expected_method``);
``baseline_probability`` is in [0, 1] with four decimals; ``desk_confidence`` equals the
ledger's confidence (a confidence changed after the baseline was written is caught here);
``asof <= made_on`` and ``asof <= computed_on``; ``inputs`` is a JSON object carrying
``h_business_days``; the note is not empty; ``raw_sha256`` is one or more digests.
``baseline_row_violations`` is the list; ``read_baselines`` and ``append_baseline`` apply
it with the ledger.  ``skill_summary`` refuses a result outside ``score.RESULTS`` and a
probability outside [0, 1] instead of putting them in the Brier.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import score  # noqa: E402

from qune_research import data as qdata  # noqa: E402

BASELINES = HERE / "baselines.csv"
SKILL = HERE / "SKILL.md"
RAW_DIR = HERE / "raw"
MANIFEST = HERE / "manifest.json"
BASELINE_COLUMNS = ["id", "computed_on", "asof", "method", "baseline_probability", "desk_confidence",
                    "inputs", "note", "raw_sha256"]
METHODS = frozenset({"bill_implied_hike", "forward_normal", "forward_normal_barrier", "persistence_base_rate"})

TENOR_YEARS = {"DTB4WK": 28 / 365, "DGS3MO": 0.25, "DGS2": 2.0, "DGS10": 10.0, "DGS30": 30.0}
SHORT_LEG = "DGS3MO"          # the y_h used in the forward formula
LOOKBACK_OBS = 252            # observations for the realised daily scale
PATHS = 200_000
SEED = 2026
HIKE_STEP = 0.25
BILL_4W = "DTB4WK"
FUNDS = "EFFR"

# How each ledger series is turned into a baseline.  ``legs`` are FRED series with
# signs (a spread is long one, short another); ``forward`` says whether the centre
# is read off the curve (yields) or kept at the spot level (breakevens).
SERIES_SPEC: dict[str, dict] = {
    "DGS10": {"kind": "level", "legs": {"DGS10": 1.0}, "forward": True},
    "DGS2": {"kind": "level", "legs": {"DGS2": 1.0}, "forward": True},
    "DGS30": {"kind": "level", "legs": {"DGS30": 1.0}, "forward": True},
    "T10Y2Y": {"kind": "level", "legs": {"DGS10": 1.0, "DGS2": -1.0}, "forward": True},
    "T10YIE": {"kind": "level", "legs": {"T10YIE": 1.0}, "forward": False},
    "DFEDTARU": {"kind": "policy"},
    "SBCORR63": {"kind": "base_rate"},
}


# --- arithmetic ----------------------------------------------------------------------------

def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def business_days_between(asof: pd.Timestamp, due: pd.Timestamp) -> int:
    """Weekdays after ``asof`` up to and including ``due``."""
    if due <= asof:
        raise ValueError("due must be after asof")
    return len(pd.bdate_range(asof + pd.Timedelta(days=1), due))


def forward_yield(spot: float, tenor_years: float, short_yield: float, horizon_years: float) -> float:
    """Forward par-ish yield of a ``tenor_years`` instrument ``horizon_years`` ahead,
    zero-coupon approximation: f = (y_T * T - y_h * h) / (T - h)."""
    if not 0 < horizon_years < tenor_years:
        raise ValueError("horizon must be positive and shorter than the tenor")
    return (spot * tenor_years - short_yield * horizon_years) / (tenor_years - horizon_years)


def realised_daily_sd(level: pd.Series, lookback: int = LOOKBACK_OBS) -> float:
    changes = level.dropna().diff().dropna()
    if len(changes) < lookback:
        raise ValueError(f"need {lookback} daily changes, have {len(changes)}")
    return float(changes.iloc[-lookback:].std(ddof=1))


def probability_on_due(test: str, low: float, high: float, centre: float, scale: float) -> float:
    """Probability of a point test under N(centre, scale)."""
    if scale <= 0:
        raise ValueError("scale must be positive")
    z = lambda v: (v - centre) / scale  # noqa: E731
    if test == "between_on_due":
        return normal_cdf(z(high)) - normal_cdf(z(low))
    if test == "below_on_due":
        return normal_cdf(z(low))
    if test == "above_on_due":
        return 1.0 - normal_cdf(z(low))
    raise ValueError(f"no normal baseline for test {test}")


def barrier_probability(start: float, low: float, high: float, steps: int, daily_sd: float,
                        total_drift: float = 0.0, paths: int = PATHS, seed: int = SEED) -> float:
    """Share of seeded random-walk paths that stay inside [low, high] on every one of
    ``steps`` daily steps.  Drift is spread evenly over the steps."""
    if not low <= start <= high:
        return 0.0
    rng = np.random.default_rng(seed)
    increments = rng.normal(total_drift / steps, daily_sd, size=(paths, steps))
    levels = start + np.cumsum(increments, axis=1)
    inside = (levels >= low) & (levels <= high)
    return float(inside.all(axis=1).mean())


def bill_implied_hike_probability(bill: float, funds: float, bill_days: int, days_to_meeting: int,
                                  step: float = HIKE_STEP) -> float:
    """Expected hikes at the single meeting inside the bill's life, clipped to a probability."""
    if not 0 < days_to_meeting < bill_days:
        raise ValueError("the meeting must fall inside the bill's life")
    implied = (bill - funds) * bill_days / (bill_days - days_to_meeting) / step
    return float(min(1.0, max(0.0, implied)))


def max_policy_spread(bill_days: int, days_to_meetings: list[int], step: float = HIKE_STEP) -> float:
    """The largest bill-minus-funds spread (percentage points) that policy alone can
    explain: one full ``step`` at every meeting inside the bill's life, each weighted
    by the share of the bill's life that follows it.  Any spread above this figure is
    premium (term, supply, bill-funds basis), not expectations.

    Added 2026-10-30 after the V1 miss: on 2026-10-21 the 3-month bill sat 37 bp over
    funds with the 28 October and 9 December meetings inside its life; two full hikes
    would have produced at most 34.6 bp, so the desk's reading of the spread as 'one
    hike plus part of another' was arithmetically impossible as policy content."""
    if bill_days <= 0:
        raise ValueError("bill_days must be positive")
    inside = [t for t in days_to_meetings if 0 < t < bill_days]
    return float(sum(step * (bill_days - t) / bill_days for t in inside))


def persistence_base_rate(series: pd.Series, threshold: float, above_now: bool, horizon_obs: int) -> float:
    """Share of past observations on the same side of ``threshold`` as today whose
    value ``horizon_obs`` observations later was above the threshold."""
    values = series.dropna().to_numpy()
    if len(values) <= horizon_obs + 1:
        raise ValueError("series too short for the horizon")
    now_side = values[:-horizon_obs] > threshold
    later_above = values[horizon_obs:] > threshold
    mask = now_side == above_now
    if mask.sum() == 0:
        raise ValueError("no past observation on today's side of the threshold")
    return float(later_above[mask].mean())


# --- one call ------------------------------------------------------------------------------

def truncate(series: pd.Series, asof: pd.Timestamp) -> pd.Series:
    return series.loc[:asof]


def expected_method(series: str, test: str) -> str:
    """The one method ``compute_baseline`` returns for a call's series and test; a test
    holds the two in agreement.  Raises ValueError when no method covers the pair."""
    spec = SERIES_SPEC.get(series)
    if spec is None:
        raise ValueError(f"no baseline method for series {series}")
    if spec["kind"] == "policy":
        if test != "eq_on_due":
            raise ValueError("policy baseline covers eq_on_due only")
        return "bill_implied_hike"
    if spec["kind"] == "base_rate":
        if test not in {"above_on_due", "below_on_due"}:
            raise ValueError("base-rate baseline covers above/below on the due date only")
        return "persistence_base_rate"
    return "forward_normal_barrier" if test == "within_every_day_until_due" else "forward_normal"


def compute_baseline(row: pd.Series, load, asof: pd.Timestamp) -> dict:
    """``load(series_id) -> pd.Series`` (full FRED history).  Returns the row for
    baselines.csv except ``computed_on`` and ``raw_sha256``."""
    spec = SERIES_SPEC.get(row["series"])
    if spec is None:
        raise ValueError(f"no baseline method for series {row['series']}")
    due = pd.Timestamp(row["due_on"])
    test = row["test"]
    low = float(row["threshold_low"])
    high = float(row["threshold_high"]) if row["threshold_high"] != "" else float("nan")
    h = business_days_between(asof, due)
    inputs: dict[str, object] = {"h_business_days": h}

    if spec["kind"] == "policy":
        if test != "eq_on_due":
            raise ValueError("policy baseline covers eq_on_due only")
        bill_series = truncate(load(BILL_4W), asof).dropna()
        funds_series = truncate(load(FUNDS), asof).dropna()
        bill_date, bill = bill_series.index[-1], float(bill_series.iloc[-1])
        funds_date, funds = funds_series.index[-1], float(funds_series.iloc[-1])
        meeting = due - pd.Timedelta(days=1)
        days_to_meeting = (meeting - asof).days
        p = bill_implied_hike_probability(bill, funds, 28, days_to_meeting)
        inputs.update({BILL_4W: bill, f"{BILL_4W}_on": str(bill_date.date()), FUNDS: funds,
                       f"{FUNDS}_on": str(funds_date.date()), "meeting_on": str(meeting.date()),
                       "days_to_meeting": days_to_meeting, "bill_days": 28, "step": HIKE_STEP})
        note = ("4-week bill minus funds, scaled to the meeting day and divided by the step; "
                "bill-funds basis ignored; no futures on FRED")
        return {"method": "bill_implied_hike", "baseline_probability": p, "inputs": inputs, "note": note}

    if spec["kind"] == "base_rate":
        if test not in {"above_on_due", "below_on_due"}:
            raise ValueError("base-rate baseline covers above/below on the due date only")
        series = truncate(score.load_series(row["series"], load), asof).dropna()
        now = float(series.iloc[-1])
        above_now = now > low
        p_above = persistence_base_rate(series, low, above_now, h)
        p = p_above if test == "above_on_due" else 1.0 - p_above
        inputs.update({"now": now, "now_on": str(series.index[-1].date()), "threshold": low,
                       "history_from": str(series.index[0].date()), "observations": int(len(series))})
        note = "historical persistence of the series' side of the threshold over h observations; not market-implied"
        return {"method": "persistence_base_rate", "baseline_probability": p, "inputs": inputs, "note": note}

    # level: one or two yield legs
    legs = {sid: truncate(load(sid), asof).dropna() for sid in spec["legs"]}
    level = sum(sign * legs[sid] for sid, sign in spec["legs"].items()).dropna()
    spot_on = level.index[-1]
    spot = float(level.iloc[-1])
    daily_sd = realised_daily_sd(level)
    scale = daily_sd * math.sqrt(h)
    inputs.update({"spot": spot, "spot_on": str(spot_on.date()), "daily_sd": daily_sd, "scale": scale,
                   "lookback_obs": LOOKBACK_OBS})
    if spec["forward"]:
        short = truncate(load(SHORT_LEG), asof).dropna()
        short_yield = float(short.iloc[-1])
        horizon_years = h / 252
        centre = 0.0
        for sid, sign in spec["legs"].items():
            leg_spot = float(legs[sid].iloc[-1])
            centre += sign * forward_yield(leg_spot, TENOR_YEARS[sid], short_yield, horizon_years)
        inputs.update({"forward_centre": centre, f"{SHORT_LEG}": short_yield,
                       f"{SHORT_LEG}_on": str(short.index[-1].date()), "horizon_years": horizon_years})
        centre_note = "forward centre from the par curve (zero-coupon approximation)"
    else:
        centre = spot
        inputs["forward_centre"] = centre
        centre_note = "spot centre (no forward read for breakevens)"

    if test == "within_every_day_until_due":
        p = barrier_probability(spot, low, high, h, daily_sd, total_drift=centre - spot)
        inputs.update({"paths": PATHS, "seed": SEED})
        note = f"{centre_note}; realised daily sd over {LOOKBACK_OBS} obs; seeded random walk; realised, not implied, width"
        return {"method": "forward_normal_barrier", "baseline_probability": p, "inputs": inputs, "note": note}
    p = probability_on_due(test, low, high, centre, scale)
    note = f"{centre_note}; realised daily sd over {LOOKBACK_OBS} obs x sqrt(h); realised, not implied, width"
    return {"method": "forward_normal", "baseline_probability": p, "inputs": inputs, "note": note}


# --- files ---------------------------------------------------------------------------------

def _probability_text(text: str, row_id: str, col: str, decimals: int, closed: bool) -> list[str]:
    """A probability written with exactly ``decimals`` decimals; ``closed`` allows 0 and 1."""
    try:
        p = float(text)
    except (TypeError, ValueError):
        return [f"{row_id}: {col} {text!r} is not a number"]
    lo_ok = (0.0 <= p) if closed else (0.0 < p)
    hi_ok = (p <= 1.0) if closed else (p < 1.0)
    if not (lo_ok and hi_ok):
        return [f"{row_id}: {col} {text} is not a probability in {'[0, 1]' if closed else '(0, 1)'}"]
    if str(text) != f"{p:.{decimals}f}":
        return [f"{row_id}: {col} {text} is not written with {decimals} decimals"]
    return []


def baseline_row_violations(row: dict, call: dict | None) -> list[str]:
    """Every rule one baseline row must meet, each sentence naming the id and the column.
    ``call`` is the ledger row it prices (None when the id is not in the ledger, which is
    itself a violation).  The reader, the writer and the committed-file test apply this list."""
    row_id = str(row.get("id", "")).strip() or "<no id>"
    out: list[str] = []
    if not str(row.get("id", "")).strip():
        out.append(f"{row_id}: id is empty")
    elif call is None:
        out.append(f"{row_id}: id is not a call in the ledger")
    elif str(row.get("id")) != str(call.get("id")):
        out.append(f"{row_id}: id is not written as the ledger writes it ({call.get('id')!r})")
    method = row.get("method")
    if method not in METHODS:
        out.append(f"{row_id}: method {method!r} is not one of {', '.join(sorted(METHODS))}")
    elif call is not None:
        try:
            want = expected_method(str(call.get("series")), str(call.get("test")))
            if method != want:
                out.append(f"{row_id}: method {method} is not the frozen method {want} for {call.get('series')} {call.get('test')}")
        except ValueError as exc:
            out.append(f"{row_id}: method: {exc}")
    out += _probability_text(str(row.get("baseline_probability", "")), row_id, "baseline_probability", 4, closed=True)
    out += _probability_text(str(row.get("desk_confidence", "")), row_id, "desk_confidence", 2, closed=False)
    if call is not None and str(row.get("desk_confidence")) != str(call.get("confidence")):
        out.append(f"{row_id}: desk_confidence {row.get('desk_confidence')} is not the ledger's confidence "
                   f"{call.get('confidence')}; the call changed after its baseline was written")
    try:
        inputs = json.loads(str(row.get("inputs", "")))
        if not isinstance(inputs, dict) or "h_business_days" not in inputs:
            out.append(f"{row_id}: inputs is not a JSON object carrying h_business_days")
    except ValueError:
        out.append(f"{row_id}: inputs {str(row.get('inputs', ''))[:40]!r} is not JSON")
    if not str(row.get("note", "")).strip():
        out.append(f"{row_id}: note is empty")
    bad = score.hash_list_violation(row.get("raw_sha256", ""), row_id, "raw_sha256")
    if bad:
        out.append(bad)
    try:
        asof = score._day(row.get("asof", ""), row_id, "asof")
        computed = score._day(row.get("computed_on", ""), row_id, "computed_on")
        if computed < asof:
            out.append(f"{row_id}: computed_on {row['computed_on']} is before asof {row['asof']}")
        if call is not None and asof > score._day(call.get("made_on", ""), row_id, "made_on"):
            out.append(f"{row_id}: asof {row['asof']} is after the call was made ({call['made_on']}); "
                       "a baseline reads nothing the desk could not have seen")
    except ValueError as exc:
        out.append(str(exc))
    return out


def validate_baselines(baselines: pd.DataFrame, ledger: pd.DataFrame) -> None:
    missing = [c for c in BASELINE_COLUMNS if c not in baselines.columns]
    if missing:
        raise ValueError(f"baselines lack columns {missing}")
    dupes = sorted(set(baselines.loc[baselines["id"].duplicated(), "id"]))
    if dupes:
        raise ValueError(f"baseline ids must be unique; repeated id {dupes}")
    calls = score.ledger_rows_by_id(ledger)
    problems = [p for _, row in baselines.iterrows()
                for p in baseline_row_violations(row.to_dict(), calls.get(str(row["id"])))]
    if problems:
        raise ValueError("baseline rows refused: " + "; ".join(problems))


def read_baselines(ledger: pd.DataFrame, path: Path = BASELINES) -> pd.DataFrame:
    """The baselines on record, every row held against the ledger (``validate_baselines``)."""
    if not path.exists():
        return pd.DataFrame(columns=BASELINE_COLUMNS)
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    validate_baselines(frame, ledger)
    return frame


def append_baseline(path: Path, record: dict, ledger: pd.DataFrame) -> None:
    """Write one baseline row after holding it against its call and the rows already written."""
    text = {c: ("" if record.get(c) is None else str(record.get(c))) for c in BASELINE_COLUMNS}
    existing = read_baselines(ledger, path)
    if text["id"] in set(existing["id"]):
        raise ValueError(f"{text['id']} already has a baseline; refusing")
    problems = baseline_row_violations(text, score.ledger_rows_by_id(ledger).get(text["id"]))
    if problems:
        raise ValueError("baseline row refused: " + "; ".join(problems))
    exists = path.exists()
    with path.open("a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=BASELINE_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(text)


def format_record(call_id: str, computed_on: pd.Timestamp, asof: pd.Timestamp, desk_confidence: str,
                  result: dict, raw_sha256: str) -> dict:
    return {"id": call_id, "computed_on": str(computed_on.date()), "asof": str(asof.date()),
            "method": result["method"], "baseline_probability": f"{result['baseline_probability']:.4f}",
            "desk_confidence": desk_confidence,
            "inputs": json.dumps(result["inputs"], sort_keys=True, default=float),
            "note": result["note"], "raw_sha256": raw_sha256}


# --- skill summary -------------------------------------------------------------------------

def brier(probabilities: pd.Series, hits: pd.Series) -> float:
    return float(((probabilities - hits) ** 2).mean())


def _ids_match_the_ledger(name: str, frame: pd.DataFrame, ledger: pd.DataFrame) -> None:
    """A table built by merging on id drops a row whose id the ledger does not carry and
    doubles a call whose id a record repeats; both are refused here by name."""
    dupes = sorted(set(frame.loc[frame["id"].duplicated(), "id"]))
    if dupes:
        raise ValueError(f"{name}: repeated id {dupes}")
    strays = sorted(set(frame["id"]) - set(ledger["id"]))
    if strays:
        raise ValueError(f"{name}: id not in the ledger {strays}")


def skill_table(ledger: pd.DataFrame, baselines: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    """One row per call with a baseline: desk and baseline probabilities and, once
    scored, the outcome.  Calls without a baseline are listed with an empty method.
    Every baseline and outcome id must be a ledger id and appear once (2026-11-10)."""
    _ids_match_the_ledger("baselines", baselines, ledger)
    _ids_match_the_ledger("outcomes", outcomes, ledger)
    odd = outcomes[~outcomes["result"].isin(score.RESULTS)]
    if not odd.empty:  # after the merge an empty result and a missing row look the same ("not yet due")
        raise ValueError("outcomes: result not hit or miss: " + ", ".join(f"{r.id} {r.result!r}" for r in odd.itertuples()))
    table = ledger[["id", "made_on", "series", "test", "due_on", "confidence"]].merge(
        baselines[["id", "asof", "method", "baseline_probability"]], on="id", how="left")
    table = table.merge(outcomes[["id", "result", "observed_value"]], on="id", how="left")
    return table.fillna("")


def skill_summary(table: pd.DataFrame) -> dict:
    """Brier scores over the calls that are scored and have a baseline.  A result that
    is not ``hit`` or ``miss``, or a probability outside [0, 1], is refused by name
    (2026-11-10): before, any other word counted as a miss."""
    with_row = table[table["result"] != ""]
    odd = with_row[~with_row["result"].isin(score.RESULTS)]
    if not odd.empty:
        raise ValueError("outcome result not hit or miss: " + ", ".join(f"{r.id} {r.result!r}" for r in odd.itertuples()))
    scored = with_row[with_row["method"] != ""]
    if scored.empty:
        return {"scored_with_baseline": 0}
    hits = (scored["result"] == "hit").astype(float)
    desk = pd.to_numeric(scored["confidence"])
    base = pd.to_numeric(scored["baseline_probability"])
    for name, values in (("confidence", desk), ("baseline_probability", base)):
        bad = scored.loc[~values.between(0.0, 1.0), "id"]
        if not bad.empty:
            raise ValueError(f"{name} outside [0, 1] for {list(bad)}")
    return {"scored_with_baseline": int(len(scored)), "hits": int(hits.sum()),
            "brier_desk": brier(desk, hits), "brier_baseline": brier(base, hits),
            "skill_vs_baseline": brier(base, hits) - brier(desk, hits)}


def render_skill(table: pd.DataFrame, summary: dict, today: pd.Timestamp) -> str:
    lines = ["# Desk calls against the market-anchored baseline", "",
             f"Generated by `predictions/baseline.py --summary` on {today.date()} from `ledger.csv`, "
             "`baselines.csv` and `outcomes.csv`. The baseline probability is computed by the frozen method "
             "in `baseline.py` from public data as of the day the call was made (see that file's docstring). "
             "Skill is the baseline's Brier score minus the desk's: positive means the desk did better than "
             "the market-anchored baseline, negative means worse. A hit rate is not reported on its own.", "",
             "| id | series | test | due | desk p | baseline p | method | outcome |", "|---|---|---|---|---|---|---|---|"]
    for _, r in table.iterrows():
        outcome = r["result"] if r["result"] else "not yet due"
        lines.append(f"| {r['id']} | {r['series']} | {r['test']} | {r['due_on']} | {r['confidence']} | "
                     f"{r['baseline_probability'] or '—'} | {r['method'] or '—'} | {outcome} |")
    lines.append("")
    if summary["scored_with_baseline"] == 0:
        lines.append("Scored calls with a baseline: 0. Nothing can be said about skill yet.")
    else:
        lines += [f"Scored calls with a baseline: {summary['scored_with_baseline']} (hits {summary['hits']}).",
                  f"Brier, desk: {summary['brier_desk']:.4f}. Brier, baseline: {summary['brier_baseline']:.4f}. "
                  f"Skill (baseline minus desk): {summary['skill_vs_baseline']:+.4f}.",
                  "With fewer than about thirty scored calls this figure is descriptive, not evidence."]
    lines.append("")
    return "\n".join(lines)


# --- entry point ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asof", help="YYYY-MM-DD: last market observation the call could have used")
    parser.add_argument("--ids", help="comma-separated ledger ids to compute baselines for")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--summary", action="store_true", help="write SKILL.md from the committed files")
    parser.add_argument("--today", help="YYYY-MM-DD stamp for the summary and computed_on (default: machine clock)")
    args = parser.parse_args()
    today = pd.Timestamp(args.today) if args.today else pd.Timestamp(qdata.utc_now()[:10])
    ledger = score.read_ledger()
    if args.summary:
        table = skill_table(ledger, read_baselines(ledger), score.read_outcomes(ledger))
        text = render_skill(table, skill_summary(table), today)
        print(text)
        if not args.dry_run:
            SKILL.write_text(text, encoding="utf-8")
        return 0
    if not (args.asof and args.ids):
        parser.error("--asof and --ids are required unless --summary")
    asof = pd.Timestamp(args.asof)
    wanted = ledger[ledger["id"].isin(args.ids.split(","))]
    missing = set(args.ids.split(",")) - set(wanted["id"])
    if missing:
        raise SystemExit(f"not in the ledger: {sorted(missing)}")
    existing = set(read_baselines(ledger)["id"])
    for _, row in wanted.iterrows():
        if row["id"] in existing:
            raise SystemExit(f"{row['id']} already has a baseline; refusing")
        if pd.Timestamp(row["made_on"]) < asof:
            raise SystemExit(f"{row['id']}: asof {asof.date()} is after made_on {row['made_on']}")
        fetched: list[str] = []

        def load(sid: str, _fetched: list[str] = fetched) -> pd.Series:
            if sid not in _fetched:
                _fetched.append(sid)
            return qdata.fetch_fred(sid, RAW_DIR, MANIFEST)

        result = compute_baseline(row, load, asof)
        hashes = ";".join(qdata.sha256_of(qdata.fred_path(sid, RAW_DIR)) for sid in fetched)
        record = format_record(row["id"], today, asof, row["confidence"], result, hashes)
        print(record)
        if not args.dry_run:
            append_baseline(BASELINES, record, ledger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
