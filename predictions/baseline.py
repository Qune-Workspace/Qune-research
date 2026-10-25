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

def read_baselines(path: Path = BASELINES) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=BASELINE_COLUMNS)
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if frame["id"].duplicated().any():
        raise ValueError("baselines ids must be unique")
    return frame


def append_baseline(path: Path, record: dict) -> None:
    existing = read_baselines(path)
    if record["id"] in set(existing["id"]):
        raise ValueError(f"{record['id']} already has a baseline; refusing")
    exists = path.exists()
    with path.open("a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=BASELINE_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(record)


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


def skill_table(ledger: pd.DataFrame, baselines: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    """One row per call with a baseline: desk and baseline probabilities and, once
    scored, the outcome.  Calls without a baseline are listed with an empty method."""
    table = ledger[["id", "made_on", "series", "test", "due_on", "confidence"]].merge(
        baselines[["id", "asof", "method", "baseline_probability"]], on="id", how="left")
    table = table.merge(outcomes[["id", "result", "observed_value"]], on="id", how="left")
    return table.fillna("")


def skill_summary(table: pd.DataFrame) -> dict:
    scored = table[(table["result"] != "") & (table["method"] != "")]
    if scored.empty:
        return {"scored_with_baseline": 0}
    hits = (scored["result"] == "hit").astype(float)
    desk = pd.to_numeric(scored["confidence"])
    base = pd.to_numeric(scored["baseline_probability"])
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
        table = skill_table(ledger, read_baselines(), score.read_outcomes())
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
    existing = set(read_baselines()["id"])
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
            append_baseline(BASELINES, record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
