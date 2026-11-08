"""Historical calibration of the touch-market method (barrier.py) on the FRED
series CBBTCUSD, against a climatological baseline, before the method is used
in a view.  Reads a kept download (git-ignored under data/raw/fred/), never
fetches, writes aggregates only.

Why (BUILD_LOG 2026-11-04 12:15Z; the V1 miss of predictions/POST_MORTEMS.md):
the first live run showed the 30- and 90-observation windows 0.10 apart in
probability, the whole call threshold, and the primary window had been fixed by
rule (the month's length), not by evidence.  A method that is to be a reason
for a call against a market must first be shown to beat the dumbest baseline
on the history it had, with the test written before the answer is known.

PRE-SPECIFIED 2026-11-05 12:2x UTC, committed before the first run on the series
(nothing below was chosen on a result):

* Sample: every Eastern-time calendar month that has at least SENSITIVITY + 1
  observations before its first in-month observation and whose end (00:00
  Eastern on the 1st of the next month) is at or before the spot time of the
  series' last observation.  The live month is never in the sample.
* Evaluation observation, PRIMARY: the first observation whose spot time
  (17:00 Pacific on its date, barrier.spot_time_utc) lies inside the month.
  SECONDARY, reported only: the first in-month observation dated the 5th or
  later, which mirrors a Friday view's position in the month.
* Barriers: log distances DISTANCES above and below the evaluation spot (the
  two live markets of November 2026 sit near +-0.03).  Nothing depends on a
  level, and no level or date-level pair is written.
* Prediction: pm_lib.touch_probability with pm_lib.realised_vol over the
  PRIMARY_WINDOW (30) and SENSITIVITY_WINDOW (90) observations ending at the
  evaluation observation; horizon from the spot time to the month's end; zero
  drift.  The same functions and constants as barrier.py.
* Outcome: 1 if any later observation inside the month closes at or beyond the
  barrier (barrier.already_touched's rule), else 0.  LIMIT, stated with every
  figure: this is the method's own outcome (a daily Coinbase close), so it
  measures the formula and the window on that outcome; the gap between a daily
  close and a Binance one-minute extreme, the method's known downward bias on
  the markets, is NOT measurable from this series and is not measured here.
* Baseline (climatology): for a month and a (distance, side), the touch
  frequency over all EARLIER sample months at the same (distance, side),
  expanding; a month is scored only when at least MIN_BASELINE_MONTHS (12)
  earlier months exist.  Never a later month (no look-ahead).
* Scores: Brier per model (30, 90, baseline), per (distance, side) and pooled
  over the scored rows; reliability table in bins of width 0.1 for the two
  windows (count, mean predicted, observed frequency); disagreement = share of
  rows with |p30 - p90| >= CALL_THRESHOLD.  Uncertainty: a block bootstrap
  over months (BOOT = 2000 draws, seed SEED) of the pooled Brier differences
  (30 - 90) and (primary - baseline), 2.5th and 97.5th percentiles.
* Decision rules, fixed now, applied in the view from the date of the run:
  R1  the primary window for the view becomes 90 only if the pooled Brier of
      the 90 window is lower than the 30's AND the bootstrap interval of
      (B30 - B90) lies above zero; otherwise 30 stays.
  R2  if the chosen primary's pooled Brier is not lower than the baseline's
      with the interval of (Bprimary - Bbase) below zero, the barrier method is
      not a basis for a call on its own: the view prints its reading beside
      the climatological rate and logs no call from the method.
  R3  the sign of (observed - mean predicted) in the bins 0.5-0.9, where the
      live readings sit, is reported as the method's direction of error on its
      own outcome; a positive sign (under-reading) adds to the known bias and
      a negative sign (over-reading) partly offsets it.

Usage (from this folder):
    python calibrate.py --from-file data/raw/fred/<stamp>/CBBTCUSD.csv [--out data/calibration.json]
Exit 0 when the report was written, 1 when the series is too short.

With --out the run also puts the file it wrote on record (2026-11-08 00:15Z,
predictions/POST_MORTEMS.md "A calibration that went into force before it was
on record"): one line of calibration_history.csv beside the file (for the
default, data/calibration_history.csv), its hash and R2 read back from the file
as written, its source built from what the run read (the input's name and
SHA-256, observations, last observation, R1/R2/R3), never typed; it prints
RECORDED, or UNCHANGED when the file is already the method's latest line.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import barrier as B
import pm_lib as L
from pm_lib import realised_vol, touch_probability

HERE = Path(__file__).resolve().parent
PRIMARY_WINDOW = B.PRIMARY_WINDOW
SENSITIVITY_WINDOW = B.SENSITIVITY_WINDOW
CALL_THRESHOLD = B.CALL_THRESHOLD
DISTANCES = (0.025, 0.05, 0.10, 0.15, 0.20)
SIDES = ("up", "down")
MIN_BASELINE_MONTHS = 12
SECONDARY_DAY = 5
BOOT = 2000
SEED = 20261105
BINS = [k / 10 for k in range(11)]


def months_in(obs: list[tuple[date, float]]) -> list[tuple[int, int]]:
    """Every (year, month) from the first observation's month to the last complete one."""
    first, last = obs[0][0], obs[-1][0]
    last_spot = B.spot_time_utc(last)
    out: list[tuple[int, int]] = []
    y, m = first.year, first.month
    while (y, m) <= (last.year, last.month):
        _, end = B.month_window_utc(y, m)
        if end <= last_spot:
            out.append((y, m))
        y, m = (y + (m == 12), m % 12 + 1)
    return out


def evaluation_index(obs: list[tuple[date, float]], y: int, m: int, min_day: int = 1) -> int | None:
    """Index of the first observation inside the month dated `min_day` or later, else None."""
    start, end = B.month_window_utc(y, m)
    for i, (d, _) in enumerate(obs):
        t = B.spot_time_utc(d)
        if start <= t < end and d.day >= min_day:
            return i
    return None


def touched_after(obs: list[tuple[date, float]], i: int, barrier: float, side: str, end: datetime) -> int:
    """1 if an observation after index i and before the month's end closes at or beyond the barrier."""
    for d, v in obs[i + 1:]:
        if B.spot_time_utc(d) >= end:
            break
        if (side == "up" and v >= barrier) or (side == "down" and v <= barrier):
            return 1
    return 0


def rows_for(obs: list[tuple[date, float]], min_day: int = 1,
             primary: int = PRIMARY_WINDOW, sensitivity: int = SENSITIVITY_WINDOW) -> list[dict[str, Any]]:
    """One row per (sample month, distance, side): the two predictions and the outcome.
    A month without an evaluation observation or without `sensitivity + 1`
    observations before it is skipped.  No level is kept in a row."""
    out: list[dict[str, Any]] = []
    for y, m in months_in(obs):
        i = evaluation_index(obs, y, m, min_day)
        if i is None or i < sensitivity:
            continue
        _, end = B.month_window_utc(y, m)
        spot_d, spot = obs[i]
        horizon = (end - B.spot_time_utc(spot_d)).total_seconds() / 86400.0
        closes = [v for _, v in obs[: i + 1]]
        s30 = realised_vol(closes[-(primary + 1):])
        s90 = realised_vol(closes[-(sensitivity + 1):])
        for dist in DISTANCES:
            for side in SIDES:
                level = spot * math.exp(dist if side == "up" else -dist)
                out.append({
                    "month": f"{y:04d}-{m:02d}", "distance": dist, "side": side, "horizon_days": horizon,
                    "p30": touch_probability(spot, level, s30, horizon),
                    "p90": touch_probability(spot, level, s90, horizon),
                    "y": touched_after(obs, i, level, side, end),
                })
    return out


def add_baseline(rows: list[dict[str, Any]], min_months: int = MIN_BASELINE_MONTHS) -> list[dict[str, Any]]:
    """Climatology: for each row, the touch frequency of the same (distance, side)
    over the earlier months; rows with fewer than `min_months` earlier months
    get no baseline and are not scored."""
    seen: dict[tuple[float, str], list[int]] = {}
    scored: list[dict[str, Any]] = []
    months = sorted({r["month"] for r in rows})
    by_month: dict[str, list[dict[str, Any]]] = {mo: [] for mo in months}
    for r in rows:
        by_month[r["month"]].append(r)
    for mo in months:
        for r in by_month[mo]:
            key = (r["distance"], r["side"])
            prior = seen.get(key, [])
            if len(prior) >= min_months:
                r["p_base"] = sum(prior) / len(prior)
                scored.append(r)
        for r in by_month[mo]:
            seen.setdefault((r["distance"], r["side"]), []).append(r["y"])
    return scored


def brier(ps: Iterable[float], ys: Iterable[int]) -> float:
    pairs = list(zip(ps, ys, strict=True))
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def reliability(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    table = []
    for lo, hi in zip(BINS[:-1], BINS[1:], strict=True):
        sel = [r for r in rows if lo <= r[key] < hi or (hi == 1.0 and r[key] == 1.0)]
        if not sel:
            table.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": 0, "mean_p": None, "observed": None})
            continue
        table.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(sel),
                      "mean_p": sum(r[key] for r in sel) / len(sel),
                      "observed": sum(r["y"] for r in sel) / len(sel)})
    return table


def bootstrap_diff(rows: list[dict[str, Any]], a: str, b: str, draws: int = BOOT, seed: int = SEED) -> dict[str, float]:
    """Pooled Brier(a) - Brier(b), with a month-block bootstrap interval."""
    months = sorted({r["month"] for r in rows})
    sums = {mo: 0.0 for mo in months}
    counts = {mo: 0 for mo in months}
    for r in rows:
        sums[r["month"]] += (r[a] - r["y"]) ** 2 - (r[b] - r["y"]) ** 2
        counts[r["month"]] += 1
    point = sum(sums.values()) / sum(counts.values())
    rng = random.Random(seed)
    draws_out = []
    for _ in range(draws):
        pick = [rng.choice(months) for _ in months]
        draws_out.append(sum(sums[mo] for mo in pick) / sum(counts[mo] for mo in pick))
    draws_out.sort()
    return {"point": point, "lo": draws_out[int(0.025 * draws)], "hi": draws_out[int(0.975 * draws) - 1]}


def summarise(rows: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> dict[str, Any]:
    """The aggregates: nothing in here is a level, a date-level pair or a row."""
    months = sorted({r["month"] for r in rows})
    per: list[dict[str, Any]] = []
    for dist in DISTANCES:
        for side in SIDES:
            sel = [r for r in rows if r["distance"] == dist and r["side"] == side]
            if not sel:
                continue
            per.append({"distance": dist, "side": side, "n": len(sel), "touch_rate": sum(r["y"] for r in sel) / len(sel),
                        "brier30": brier((r["p30"] for r in sel), (r["y"] for r in sel)),
                        "brier90": brier((r["p90"] for r in sel), (r["y"] for r in sel)),
                        "brier_base": brier((r["p_base"] for r in sel), (r["y"] for r in sel)),
                        "mean_p30": sum(r["p30"] for r in sel) / len(sel),
                        "mean_p90": sum(r["p90"] for r in sel) / len(sel)})
    pooled = {"n": len(rows), "months": len(months), "first_month": months[0], "last_month": months[-1],
              "brier30": brier((r["p30"] for r in rows), (r["y"] for r in rows)),
              "brier90": brier((r["p90"] for r in rows), (r["y"] for r in rows)),
              "brier_base": brier((r["p_base"] for r in rows), (r["y"] for r in rows)),
              "disagreement_share": sum(abs(r["p30"] - r["p90"]) >= CALL_THRESHOLD for r in rows) / len(rows),
              "departure_share_30_vs_base": sum(abs(r["p30"] - r["p_base"]) >= CALL_THRESHOLD for r in rows) / len(rows)}
    d30_90 = bootstrap_diff(rows, "p30", "p90")
    r1_primary = 90 if (pooled["brier90"] < pooled["brier30"] and d30_90["lo"] > 0) else 30
    pkey = "p90" if r1_primary == 90 else "p30"
    dprim_base = bootstrap_diff(rows, pkey, "p_base")
    r2_method_is_a_basis = (pooled[f"brier{r1_primary}"] < pooled["brier_base"]) and dprim_base["hi"] < 0
    rel30, rel90 = reliability(rows, "p30"), reliability(rows, "p90")
    mid = [t for t in reliability(rows, pkey) if t["n"] and t["bin"] in ("0.5-0.6", "0.6-0.7", "0.7-0.8", "0.8-0.9")]
    n_mid = sum(t["n"] for t in mid)
    r3 = None
    if n_mid:
        r3 = {"n": n_mid,
              "observed_minus_predicted": (sum(t["observed"] * t["n"] for t in mid) - sum(t["mean_p"] * t["n"] for t in mid)) / n_mid}
    sec = None
    if secondary:
        sec = {"n": len(secondary), "months": len({r["month"] for r in secondary}),
               "brier30": brier((r["p30"] for r in secondary), (r["y"] for r in secondary)),
               "brier90": brier((r["p90"] for r in secondary), (r["y"] for r in secondary)),
               "brier_base": brier((r["p_base"] for r in secondary), (r["y"] for r in secondary))}
    return {
        "series": B.SERIES, "citation": B.CITATION,
        "spec": {"distances": list(DISTANCES), "primary_window": PRIMARY_WINDOW, "sensitivity_window": SENSITIVITY_WINDOW,
                 "min_baseline_months": MIN_BASELINE_MONTHS, "secondary_day": SECONDARY_DAY, "bootstrap_draws": BOOT, "seed": SEED,
                 "outcome": "a later daily close inside the month at or beyond the barrier (the method's own outcome; "
                            "the daily-close vs one-minute-extreme gap is not measurable here)"},
        "pooled": pooled, "per_barrier": per, "reliability30": rel30, "reliability90": rel90,
        "boot_30_minus_90": d30_90, "boot_primary_minus_base": dprim_base,
        "rules": {"R1_primary_window": r1_primary, "R2_method_is_a_basis_for_a_call": r2_method_is_a_basis, "R3_mid_bins": r3},
        "secondary_day5": sec,
    }


def report(s: dict[str, Any]) -> list[str]:
    p = s["pooled"]
    out = [
        f"{s['series']} calibration of the touch method on daily closes: {p['months']} months {p['first_month']}..{p['last_month']}, "
        f"{p['n']} month-barrier rows (distances {s['spec']['distances']}, both sides), baseline needs {s['spec']['min_baseline_months']} earlier months",
        f"  pooled Brier: 30-obs window {p['brier30']:.4f}; 90-obs window {p['brier90']:.4f}; climatology {p['brier_base']:.4f}",
        f"  |p30 - p90| >= {CALL_THRESHOLD:.2f} in {p['disagreement_share']:.1%} of rows; |p30 - climatology| >= {CALL_THRESHOLD:.2f} in {p['departure_share_30_vs_base']:.1%}",
        f"  bootstrap over months ({s['spec']['bootstrap_draws']} draws): B30 - B90 = {s['boot_30_minus_90']['point']:+.4f} "
        f"[{s['boot_30_minus_90']['lo']:+.4f}, {s['boot_30_minus_90']['hi']:+.4f}]; "
        f"Bprimary - Bbase = {s['boot_primary_minus_base']['point']:+.4f} "
        f"[{s['boot_primary_minus_base']['lo']:+.4f}, {s['boot_primary_minus_base']['hi']:+.4f}]",
        f"  R1 primary window for the view: {s['rules']['R1_primary_window']} observations",
        f"  R2 the method {'beats' if s['rules']['R2_method_is_a_basis_for_a_call'] else 'does NOT beat'} the climatological baseline: "
        f"{'may be' if s['rules']['R2_method_is_a_basis_for_a_call'] else 'is not'} a basis for a call on its own",
    ]
    r3 = s["rules"]["R3_mid_bins"]
    if r3:
        out.append(f"  R3 bins 0.5-0.9 of the primary ({r3['n']} rows): observed - predicted = {r3['observed_minus_predicted']:+.3f} "
                   f"({'under-reads' if r3['observed_minus_predicted'] > 0 else 'over-reads'} on its own outcome)")
    out.append("  per barrier (distance side: n, touch rate, Brier 30 / 90 / base, mean p30 / p90):")
    for b in s["per_barrier"]:
        out.append(f"    {b['distance']:.3f} {b['side']:<4}: {b['n']:3d}, {b['touch_rate']:.3f}, {b['brier30']:.4f} / {b['brier90']:.4f} / "
                   f"{b['brier_base']:.4f}, {b['mean_p30']:.3f} / {b['mean_p90']:.3f}")
    for key, label in (("reliability30", "30"), ("reliability90", "90")):
        out.append(f"  reliability, {label}-obs window (bin: n, mean p, observed):")
        for t in s[key]:
            if t["n"]:
                out.append(f"    {t['bin']}: {t['n']:4d}, {t['mean_p']:.3f}, {t['observed']:.3f}")
    if s["secondary_day5"]:
        q = s["secondary_day5"]
        out.append(f"  secondary (evaluation on day {s['spec']['secondary_day']}+, reported only): {q['months']} months, "
                   f"Brier 30 {q['brier30']:.4f} / 90 {q['brier90']:.4f} / base {q['brier_base']:.4f}")
    out.append(f"  limit: outcome = a daily Coinbase close; the one-minute Binance extreme gap is not measured. source: {s['citation']}")
    return out


METHOD = "btc_touch"


def record(out: Path, input_name: str, input_sha256: str, now: datetime) -> int:
    """Put the file just written on record in the calibration history beside it,
    with a source built from the file as written and the input the run read."""
    written = json.loads(out.read_text(encoding="utf-8"))
    rules = written.get("rules") or {}
    r3 = rules.get("R3_mid_bins")
    r3_text = "n/a" if not r3 else f"{r3['observed_minus_predicted']:+.4f} on {r3['n']} rows"
    source = (f"calibrate.py: {input_name} sha256 {input_sha256[:12]}; {written.get('observations')} observations, "
              f"last {written.get('last_obs')}; R1 {rules.get('R1_primary_window')}, "
              f"R2 {str(L.method_gate(METHOD, written)).lower()}, R3 {r3_text}")
    history = out.parent / Path(L.CALIBRATION_HISTORY).name
    status, line = L.record_calibration_line(history, METHOD, out, now, source)
    if status == "refused" or line is None:
        print(f"  REFUSED {METHOD}: {out} carries no R2; not on record")
        return 1
    word = "RECORDED" if status == "recorded" else "UNCHANGED"
    print(f"  {word} {METHOD}: SHA-256 {line['sha256']} R2={line['r2']} in force from {line['in_force_utc']} ({history})")
    return 0


def run(from_file: Path, out: Path | None, now: datetime | None = None) -> int:
    raw = from_file.read_bytes()
    obs = B.parse_fred_csv(raw.decode("utf-8"))
    rows = add_baseline(rows_for(obs))
    if not rows:
        print(f"{B.SERIES}: FAILED the series is too short for a scored month")
        return 1
    secondary = add_baseline(rows_for(obs, min_day=SECONDARY_DAY))
    s = summarise(rows, secondary)
    s["read_from"] = from_file.name
    s["observations"] = len(obs)
    s["last_obs"] = obs[-1][0].isoformat()
    for ln in report(s):
        print(ln)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(s, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"  written: {out}")
        return record(out, from_file.name, hashlib.sha256(raw).hexdigest(), now or datetime.now(UTC))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-file", type=Path, required=True, help="a kept FRED download (git-ignored)")
    ap.add_argument("--out", type=Path, default=None, help="aggregates json (default: none written)")
    a = ap.parse_args(argv)
    return run(a.from_file, a.out)


if __name__ == "__main__":
    sys.exit(main())
