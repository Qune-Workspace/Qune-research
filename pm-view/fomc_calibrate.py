"""Historical calibration of the bill-implied FOMC reading (the method of the
2026-11-03 view, predictions/baseline.py::max_policy_spread) on the scheduled
meetings since 2016, against two dumb baselines, before the reading may be a
basis for a call on the December 2026 FOMC markets.  Fetches four FRED series
once (raw git-ignored under data/raw/, hashed into data/fred_rates_manifest.json,
never a value), or reads a kept download; writes aggregates only.

Why (BUILD_LOG 2026-11-05 12:15Z; the V1 miss of predictions/POST_MORTEMS.md):
the touch method was scored against climatology on its own history on 5
November and failed; the view's other method, the bill reading of the FOMC
event, had never been scored at all, and the 2026-11-03 view already said its
range under the basis assumption alone (0.22 to 0.79) was "the weak joint V1
broke on".  The same rule applies to every method the view uses: a method is a
reason against a market only once it beats the dumbest baseline on the history
it had, under rules written before the answer is known.

PRE-SPECIFIED 2026-11-05 18:2x UTC, committed before the first run on the series
(nothing below was chosen on a result):

* Meetings: the scheduled decision dates of tools/fomc_statement_dates_2016_2026-09.txt
  (85 dates read from the Fed's pages on 2026-10-27, BUILD_LOG), plus 2026-10-28
  (held; the 2026-10-30 desk view) as a sample meeting and 2026-12-09 as a
  future date that only enters the policy-content arithmetic.  No other date.
* Reading date R, PRIMARY: the last observation of each series on or before the
  meeting date D minus PRIMARY_LAG_DAYS (35 calendar days, a Friday view's
  position five weeks before the 9 December meeting; the 2026-11-03 view read a
  print 40 days out).  A reading needs every series observed within
  MAX_STALE_DAYS (7) of R, and no scheduled meeting between R and D.
* The reading, exactly as the view computed it on 2026-11-03: the 3-month bill
  (DTB3) minus the effective funds rate (EFFR) is the raw spread; the 4-week
  bill (DTB4WK) minus EFFR is the bill-funds basis, readable only because the
  4-week bill matures before the meeting (R + 28 < D); the spread net of basis
  is DTB3 minus DTB4WK.  The policy content a full step at D can add to the
  3-month bill's average rate is STEP x (BILL_DAYS - t) / BILL_DAYS with
  BILL_DAYS 91 and t the days from the DTB3 print to D
  (predictions/baseline.py::max_policy_spread, one meeting).  The implied
  expected change at D in steps is x = spread / that content, clipped to
  [-1, 1]; later meetings inside the bill's life are ignored (the whole spread
  is attributed to the first meeting, the view's reading).  NET (x from the
  net spread) is the PRIMARY model and RAW (x from the raw spread) the
  SENSITIVITY, the pair the view printed as 0.58 and 0.79.
* Forecast at D, three classes: p_hike = max(x, 0), p_cut = max(-x, 0),
  p_none = 1 - |x|.
* Outcome at D: the change in the target range's upper bound (DFEDTARU) from
  its last observation on or before D - 1 to its last observation on or before
  D + OUTCOME_LAG_DAYS (7), class hike when the change is at least
  MOVE_THRESHOLD (0.125), cut when at most minus that, else none.  A meeting
  whose D + 1 is after the series' last observation has no outcome and is not
  in the sample.  LIMIT, stated with every figure: the reading's scale is one
  step, so a 50 or 75 bp move scores as a hike or cut of one step and x is
  clipped; a move between scheduled meetings (March 2020) counts at the next
  scheduled meeting only through the level it left behind.
* Baselines, each from earlier sample meetings only, never a later one:
  CLIMATOLOGY, the class frequencies over all earlier sample meetings
  (expanding); PERSISTENCE, probability 1 on the class of the previous sample
  meeting.  A meeting is scored only when at least MIN_BASELINE_MEETINGS (12)
  earlier sample meetings exist.
* Scores: the three-class Brier score, sum over classes of (p - y)^2 (0 to 2),
  per meeting; pooled mean per model (NET, RAW, climatology, persistence);
  reliability of p_hike in bins of width 0.1 for NET and RAW (count, mean
  predicted, observed hike frequency); the share of scored meetings where NET
  and RAW differ in p_hike by at least CALL_THRESHOLD (0.10).  Uncertainty: a
  block bootstrap over calendar years of the meeting (BOOT 2000 draws, seed
  SEED) of the pooled differences (NET - RAW), (primary - climatology),
  (primary - persistence), 2.5th and 97.5th percentiles.
* SECONDARY, reported only: the same at SECONDARY_LAG_DAYS (7); the 4-week
  bill then spans the meeting, so only RAW exists there.
* Decision rules, fixed now, applied in the view from the date of the run:
  R1  the primary becomes RAW only if its pooled Brier is lower than NET's AND
      the interval of (NET - RAW) lies above zero; otherwise NET stays.
  R2  the bill reading is a basis for a call on its own only if the primary's
      pooled Brier is lower than BOTH baselines' with BOTH intervals below
      zero; otherwise the view prints the reading beside the market and the
      two baselines and logs no call from the reading.
  R3  the sign of (observed hike frequency - mean p_hike) over the scored
      meetings whose primary p_hike lies in [LIVE_BIN_LOW, LIVE_BIN_HIGH) =
      [0.4, 0.8), where the live reading of 0.58 sits, is the reading's
      direction of error where it is being used.

Usage (from this folder):
    python fomc_calibrate.py --fetch [--out data/fomc_calibration.json]
    python fomc_calibrate.py --from-dir data/raw/fred_rates [--out ...]
Exit 0 when the report was written, 1 when the sample is too short (fewer than
MIN_SCORED (24) scored meetings).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qune_research import data as qdata  # noqa: E402

SERIES = ("DTB3", "DTB4WK", "EFFR", "DFEDTARU")
DATES_FILE = ROOT / "tools" / "fomc_statement_dates_2016_2026-09.txt"
EXTRA_MEETINGS = (date(2026, 10, 28), date(2026, 12, 9))
PRIMARY_LAG_DAYS = 35
SECONDARY_LAG_DAYS = 7
MAX_STALE_DAYS = 7
BILL_DAYS = 91
BASIS_BILL_DAYS = 28
STEP = 0.25
MOVE_THRESHOLD = 0.125
OUTCOME_LAG_DAYS = 7
MIN_BASELINE_MEETINGS = 12
MIN_SCORED = 24
CALL_THRESHOLD = 0.10
LIVE_BIN_LOW, LIVE_BIN_HIGH = 0.4, 0.8
BOOT = 2000
SEED = 20261105
CLASSES = ("hike", "none", "cut")
MODELS = ("net", "raw", "climatology", "persistence")
CITATION = ("Board of Governors of the Federal Reserve System (US), DTB3, DTB4WK, DFEDTARU; Federal Reserve "
            "Bank of New York, EFFR; all retrieved from FRED, Federal Reserve Bank of St. Louis")

Series = dict[str, pd.Series]


# --- inputs ----------------------------------------------------------------------------------

def meeting_dates(path: Path = DATES_FILE, extra: Iterable[date] = EXTRA_MEETINGS) -> list[date]:
    """Scheduled decision dates, sorted and unique: the committed list plus the
    two dates named in the pre-specification."""
    out: set[date] = set()
    for token in path.read_text(encoding="utf-8").split():
        token = token.strip().strip(",")
        if len(token) == 8 and token.isdigit():
            out.add(date(int(token[:4]), int(token[4:6]), int(token[6:])))
    out.update(extra)
    return sorted(out)


def last_on_or_before(series: pd.Series, d: date) -> tuple[date, float] | None:
    s = series.dropna()
    s = s.loc[: pd.Timestamp(d)]
    if s.empty:
        return None
    return s.index[-1].date(), float(s.iloc[-1])


def policy_content(days_to_meeting: int, bill_days: int = BILL_DAYS, step: float = STEP) -> float:
    """The most a full step at the meeting can add to the bill's average rate:
    predictions/baseline.py::max_policy_spread for one meeting."""
    if not 0 < days_to_meeting < bill_days:
        raise ValueError("the meeting must fall inside the bill's life")
    return step * (bill_days - days_to_meeting) / bill_days


def implied_steps(spread_pct: float, content_pct: float) -> float:
    return max(-1.0, min(1.0, spread_pct / content_pct))


def forecast(x: float) -> dict[str, float]:
    return {"hike": max(x, 0.0), "cut": max(-x, 0.0), "none": 1.0 - abs(x)}


def reading(s: Series, meetings: list[date], d: date, lag_days: int) -> dict[str, Any] | None:
    """The bill reading for meeting ``d`` taken ``lag_days`` before it, or None
    when a series is stale, another meeting lies between the reading and ``d``,
    or ``d`` is not inside the bill's life.  ``net`` is None when the 4-week
    bill would span the meeting."""
    r = d - timedelta(days=lag_days)
    if any(r < m < d for m in meetings):
        return None
    obs = {k: last_on_or_before(s[k], r) for k in ("DTB3", "DTB4WK", "EFFR")}
    if any(v is None for v in obs.values()):
        return None
    if any((r - v[0]).days > MAX_STALE_DAYS for v in obs.values() if v is not None):
        return None
    dtb3_on, dtb3 = obs["DTB3"]  # type: ignore[misc]
    dtb4wk_on, dtb4wk = obs["DTB4WK"]  # type: ignore[misc]
    _, effr = obs["EFFR"]  # type: ignore[misc]
    t = (d - dtb3_on).days
    if not 0 < t < BILL_DAYS:
        return None
    content = policy_content(t)
    raw = implied_steps(dtb3 - effr, content)
    net = implied_steps(dtb3 - dtb4wk, content) if dtb4wk_on + timedelta(days=BASIS_BILL_DAYS) < d else None
    return {"read_on": dtb3_on, "days_to_meeting": t, "content_pct": content, "x_raw": raw, "x_net": net,
            "raw": forecast(raw), "net": forecast(net) if net is not None else None}


def outcome(dfedtaru: pd.Series, d: date) -> str | None:
    before = last_on_or_before(dfedtaru, d - timedelta(days=1))
    after = last_on_or_before(dfedtaru, d + timedelta(days=OUTCOME_LAG_DAYS))
    if before is None or after is None or after[0] < d + timedelta(days=1):
        return None
    change = after[1] - before[1]
    if change >= MOVE_THRESHOLD:
        return "hike"
    if change <= -MOVE_THRESHOLD:
        return "cut"
    return "none"


def rows_for(s: Series, meetings: list[date], lag_days: int) -> list[dict[str, Any]]:
    rows = []
    for d in meetings:
        y = outcome(s["DFEDTARU"], d)
        if y is None:
            continue
        rd = reading(s, meetings, d, lag_days)
        if rd is None:
            continue
        rows.append({"meeting": d, "year": d.year, "y": y, **rd})
    return rows


# --- baselines and scores ------------------------------------------------------------------

def add_baselines(rows: list[dict[str, Any]], min_meetings: int = MIN_BASELINE_MEETINGS) -> list[dict[str, Any]]:
    """Climatology and persistence from earlier rows only; a row is kept only
    when both exist.  ``rows`` must be in meeting order."""
    out = []
    for i, r in enumerate(rows):
        earlier = rows[:i]
        if len(earlier) < min_meetings:
            continue
        counts = {c: sum(1 for e in earlier if e["y"] == c) for c in CLASSES}
        n = len(earlier)
        clim = {c: counts[c] / n for c in CLASSES}
        pers = {c: 1.0 if earlier[-1]["y"] == c else 0.0 for c in CLASSES}
        out.append({**r, "climatology": clim, "persistence": pers, "n_earlier": n})
    return out


def brier3(p: dict[str, float], y: str) -> float:
    return sum((p[c] - (1.0 if c == y else 0.0)) ** 2 for c in CLASSES)


def pooled(rows: list[dict[str, Any]], model: str) -> float | None:
    vals = [brier3(r[model], r["y"]) for r in rows if r.get(model) is not None]
    return sum(vals) / len(vals) if vals else None


def reliability(rows: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
    table = []
    for k in range(10):
        lo, hi = k / 10, (k + 1) / 10
        inb = [r for r in rows if r.get(model) is not None and lo <= r[model]["hike"] < hi + (1e-12 if k == 9 else 0)]
        if not inb:
            continue
        table.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(inb),
                      "mean_p_hike": sum(r[model]["hike"] for r in inb) / len(inb),
                      "observed_hike": sum(1 for r in inb if r["y"] == "hike") / len(inb)})
    return table


def live_bin_error(rows: list[dict[str, Any]], model: str) -> dict[str, Any]:
    inb = [r for r in rows if r.get(model) is not None and LIVE_BIN_LOW <= r[model]["hike"] < LIVE_BIN_HIGH]
    if not inb:
        return {"n": 0, "observed_minus_predicted": None}
    pred = sum(r[model]["hike"] for r in inb) / len(inb)
    obs = sum(1 for r in inb if r["y"] == "hike") / len(inb)
    return {"n": len(inb), "mean_p_hike": pred, "observed_hike": obs, "observed_minus_predicted": obs - pred}


def bootstrap_diff(rows: list[dict[str, Any]], a: str, b: str, draws: int = BOOT, seed: int = SEED) -> dict[str, Any]:
    """Block bootstrap over calendar years of the pooled Brier difference (a - b)
    on the rows where both models exist."""
    both = [r for r in rows if r.get(a) is not None and r.get(b) is not None]
    years = sorted({r["year"] for r in both})
    by_year = {y: [r for r in both if r["year"] == y] for y in years}
    point = pooled(both, a) - pooled(both, b)  # type: ignore[operator]
    rng = random.Random(seed)
    diffs = []
    for _ in range(draws):
        sample: list[dict[str, Any]] = []
        for _ in years:
            sample.extend(by_year[rng.choice(years)])
        diffs.append(pooled(sample, a) - pooled(sample, b))  # type: ignore[operator]
    diffs.sort()
    return {"point": point, "lo": diffs[int(0.025 * draws)], "hi": diffs[int(0.975 * draws) - 1],
            "n_rows": len(both), "n_blocks": len(years)}


def disagreement(rows: list[dict[str, Any]]) -> float | None:
    both = [r for r in rows if r.get("net") is not None and r.get("raw") is not None]
    if not both:
        return None
    return sum(1 for r in both if abs(r["net"]["hike"] - r["raw"]["hike"]) >= CALL_THRESHOLD) / len(both)


def apply_rules(s: dict[str, Any]) -> dict[str, Any]:
    b = s["pooled_brier"]
    d = s["bootstrap"]
    raw_better = b["raw"] is not None and b["net"] is not None and b["raw"] < b["net"] and d["net_minus_raw"]["lo"] > 0
    primary = "raw" if raw_better else "net"
    pc, pp = d[f"{primary}_minus_climatology"], d[f"{primary}_minus_persistence"]
    beats = (b[primary] < b["climatology"] and pc["hi"] < 0 and b[primary] < b["persistence"] and pp["hi"] < 0)
    err = s["live_bin"][primary]["observed_minus_predicted"]
    return {"R1_primary": primary,
            "R2_basis_for_a_call": bool(beats),
            "R3_live_bin_sign": None if err is None else ("under-reads" if err > 0 else "over-reads" if err < 0 else "none"),
            "R3_observed_minus_predicted": err}


def summarise(rows: list[dict[str, Any]], secondary: list[dict[str, Any]], manifest: dict[str, Any] | None) -> dict[str, Any]:
    s: dict[str, Any] = {
        "spec": {"primary_lag_days": PRIMARY_LAG_DAYS, "secondary_lag_days": SECONDARY_LAG_DAYS, "bill_days": BILL_DAYS,
                 "basis_bill_days": BASIS_BILL_DAYS, "step": STEP, "move_threshold": MOVE_THRESHOLD,
                 "outcome_lag_days": OUTCOME_LAG_DAYS, "min_baseline_meetings": MIN_BASELINE_MEETINGS,
                 "call_threshold": CALL_THRESHOLD, "live_bin": [LIVE_BIN_LOW, LIVE_BIN_HIGH],
                 "bootstrap_draws": BOOT, "seed": SEED, "series": list(SERIES), "citation": CITATION,
                 "prespecified": "2026-11-05 18:2x UTC, committed before the first run"},
        "sample": {"scored_meetings": len(rows),
                   "first_meeting": str(rows[0]["meeting"]) if rows else None,
                   "last_meeting": str(rows[-1]["meeting"]) if rows else None,
                   "outcomes": {c: sum(1 for r in rows if r["y"] == c) for c in CLASSES},
                   "years": len({r["year"] for r in rows})},
        "pooled_brier": {m: pooled(rows, m) for m in MODELS},
        "bootstrap": {"net_minus_raw": bootstrap_diff(rows, "net", "raw"),
                      "net_minus_climatology": bootstrap_diff(rows, "net", "climatology"),
                      "net_minus_persistence": bootstrap_diff(rows, "net", "persistence"),
                      "raw_minus_climatology": bootstrap_diff(rows, "raw", "climatology"),
                      "raw_minus_persistence": bootstrap_diff(rows, "raw", "persistence")},
        "disagreement_share": disagreement(rows),
        "reliability": {"net": reliability(rows, "net"), "raw": reliability(rows, "raw")},
        "live_bin": {"net": live_bin_error(rows, "net"), "raw": live_bin_error(rows, "raw")},
        "secondary_lag": {"scored_meetings": len(secondary), "pooled_brier": {m: pooled(secondary, m) for m in MODELS},
                          "live_bin_raw": live_bin_error(secondary, "raw")},
        "limits": ["outcome = change in DFEDTARU within 7 days of the scheduled date; the reading's scale is one step, "
                   "so larger moves score as one step and x is clipped",
                   "the whole spread is attributed to the first meeting inside the bill's life, as the view did",
                   "a move between scheduled meetings enters only through the level it left behind",
                   "sample = scheduled meetings 2016-2026 with twelve earlier sample meetings; no earlier history"],
        "inputs_manifest": manifest,
    }
    s["rules"] = apply_rules(s)
    return s


def report(s: dict[str, Any]) -> list[str]:
    b, r, d = s["pooled_brier"], s["rules"], s["bootstrap"]
    f = lambda v: "n/a" if v is None else f"{v:.4f}"  # noqa: E731
    out = [f"FOMC bill reading, calibration on {s['sample']['scored_meetings']} scored meetings "
           f"{s['sample']['first_meeting']}..{s['sample']['last_meeting']} ({s['sample']['years']} years); "
           f"outcomes {s['sample']['outcomes']}",
           f"pooled three-class Brier: net {f(b['net'])}, raw {f(b['raw'])}, climatology {f(b['climatology'])}, "
           f"persistence {f(b['persistence'])}"]
    for k, v in d.items():
        out.append(f"  {k}: {v['point']:+.4f} [{v['lo']:+.4f}, {v['hi']:+.4f}] over {v['n_rows']} rows, {v['n_blocks']} year blocks")
    out.append(f"net and raw differ by >= {CALL_THRESHOLD} in p_hike on {f(s['disagreement_share'])} of rows")
    for m in ("net", "raw"):
        lb = s["live_bin"][m]
        out.append(f"live bin [{LIVE_BIN_LOW}, {LIVE_BIN_HIGH}) {m}: n {lb['n']}, observed - predicted "
                   f"{f(lb.get('observed_minus_predicted'))}")
    sec = s["secondary_lag"]
    out.append(f"secondary lag {SECONDARY_LAG_DAYS} d (raw only): {sec['scored_meetings']} meetings, raw {f(sec['pooled_brier']['raw'])}, "
               f"climatology {f(sec['pooled_brier']['climatology'])}, persistence {f(sec['pooled_brier']['persistence'])}")
    out.append(f"R1 primary: {r['R1_primary']}; R2 basis for a call: {r['R2_basis_for_a_call']}; "
               f"R3 in the live bin the primary {r['R3_live_bin_sign']} ({f(r['R3_observed_minus_predicted'])})")
    out.append("limit: " + "; ".join(s["limits"]))
    return out


# --- entry point ---------------------------------------------------------------------------

def load_dir(raw_dir: Path) -> Series:
    return {k: qdata.load_fred(k, raw_dir) for k in SERIES}


def run(raw_dir: Path, manifest: Path, out: Path | None, fetch: bool) -> int:
    if fetch:
        for k in SERIES:
            qdata.fetch_fred(k, raw_dir, manifest)
    s = load_dir(raw_dir)
    meetings = meeting_dates()
    rows = add_baselines(rows_for(s, meetings, PRIMARY_LAG_DAYS))
    secondary = add_baselines(rows_for(s, meetings, SECONDARY_LAG_DAYS))
    if len(rows) < MIN_SCORED:
        print(f"sample too short: {len(rows)} scored meetings, need {MIN_SCORED}")
        return 1
    man = qdata.read_manifest(manifest) if manifest.exists() else None
    summary = summarise(rows, secondary, man)
    for line in report(summary):
        print(line)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        print(f"written {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fetch", action="store_true", help="download the four series into --raw-dir first")
    ap.add_argument("--from-dir", type=Path, default=None, help="kept download folder (default data/raw/fred_rates)")
    ap.add_argument("--manifest", type=Path, default=HERE / "data" / "fred_rates_manifest.json")
    ap.add_argument("--out", type=Path, default=HERE / "data" / "fomc_calibration.json")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    raw_dir = a.from_dir if a.from_dir is not None else HERE / "data" / "raw" / "fred_rates"
    return run(raw_dir, a.manifest, None if a.no_write else a.out, a.fetch)


if __name__ == "__main__":
    raise SystemExit(main())
