"""Data checks D0 and D1 (§5.3.1, §5.3.2), one run, no rule applied.

* **D0, fetch and coverage** (``stage d0``): for each of the twelve ETFs and
  the cash ETF, the vendor file is reused by hash or fetched; from its first
  bar to 2026-09-30 it must have a bar on every NYSE trading day with at most
  three consecutive missing days anywhere.  A fetch that fails, or a file that
  fails coverage, is retried once; a second failure **excludes the symbol**
  (branch X) before any return of any rule is computed.  The first bar sets
  the asset's entry date (§8.1), computed here from dates only and compared
  with the §4 expectation.  Output ``results/checks/d0.json``; the manifest
  is committed before D1 runs (§5.3.1).
* **D1, per-symbol second-vendor overlap** (``stage d1``): for every symbol
  D0 kept, vendor-minus-broker annualised mean daily return difference on
  the common return days 2016-01-04 to 2018-12-31; **within ±0.20% p.a.
  passes**, outside is branch X.  Broker bars unavailable after two attempts:
  the check is skipped and the symbol stays, labelled single-vendor,
  unchecked.  Correlation, tracking error and the largest gap are reported,
  not thresholds.  Output ``results/checks/d1.json``.
* **Halt rule** (§5.3.5): more than three exclusions, or any class left with
  fewer than two instruments, halts the study permanently before any rule is
  tested.  ``data_checks.json`` and ``data_checks.md`` carry every statistic
  whatever the outcome.

Only returns inside the overlap window are read, for the overlap check; D0
reads dates only.  Run only through ``reproduce.sh --check``; the ``get_*``
arguments exist for the tests.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from qune_research import datacheck
from qune_research.dates import month_end_signal_dates, months_before

from . import data
from .config import (
    CASH_ETF,
    CHECKS_DIR,
    CLASS_OF,
    COVERAGE_END,
    EXPECTED_ENTRY_SIGNAL_DATE,
    EXPECTED_INCEPTION,
    FETCH_ATTEMPTS,
    HALT_MAX_EXCLUSIONS,
    HALT_MIN_PER_CLASS,
    INSAMPLE_FIRST_SIGNAL_DATE,
    MAX_CONSECUTIVE_MISSING,
    MIN_RETURN_DAYS_FOR_ENTRY,
    OVERLAP_END,
    OVERLAP_EXANTE_ABS_MAX,
    OVERLAP_MEAN_DIFF_ABS_MAX,
    OVERLAP_START,
    SYMBOLS,
    UNIVERSE,
    VENDOR_FETCH_START,
)

GetFrame = Callable[..., pd.DataFrame]


def _now() -> str:
    return pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


# --- D0 -------------------------------------------------------------------------------

def entry_signal_date(bars: pd.DatetimeIndex, first_signal: str = INSAMPLE_FIRST_SIGNAL_DATE,
                      end: str = COVERAGE_END, lookback_months: int = 12,
                      min_return_days: int = MIN_RETURN_DAYS_FOR_ENTRY) -> str | None:
    """§8.1: the first month-end signal date t, not before ``first_signal``,
    at which the bars reach the month-end bar twelve months earlier and
    ``min_return_days`` returns (that many bars plus one) end at t.  Dates only."""
    idx = pd.DatetimeIndex(bars).sort_values()
    for t in month_end_signal_dates(idx, first_signal, end):
        if months_before(t, lookback_months, idx) is None:
            continue
        if int((idx <= t).sum()) >= min_return_days + 1:
            return t.strftime("%Y-%m-%d")
    return None


def d0_symbol(symbol: str, get_vendor: GetFrame, attempts: int = FETCH_ATTEMPTS) -> dict:
    """Fetch-or-reuse and coverage for one symbol with the single retry of §5.3.1."""
    record: dict = {"symbol": symbol, "class": CLASS_OF.get(symbol, "cash"), "attempts": []}
    frame = None
    for attempt in range(1, attempts + 1):
        try:
            frame = get_vendor(symbol, refetch=attempt > 1)
        except Exception as err:  # noqa: BLE001  (the adapters redact credentials from their messages)
            record["attempts"].append({"attempt": attempt, "outcome": "fetch failed", "error": str(err)[:300]})
            frame = None
            continue
        cov = datacheck.coverage(frame.index, frame.index[0], COVERAGE_END, MAX_CONSECUTIVE_MISSING)
        record["attempts"].append({"attempt": attempt, "outcome": "coverage pass" if cov["pass"] else "coverage fail"})
        record["coverage"] = cov
        if cov["pass"]:
            break
        frame = None
    if frame is None:
        record["status"] = "excluded"
        record["reason"] = f"branch X: {record['attempts'][-1]['outcome']} after {attempts} attempts"
        return record
    first, last = frame.index[0], frame.index[-1]
    record.update({"status": "pass", "rows": int(len(frame)), "first_bar": first.strftime("%Y-%m-%d"),
                   "last_bar": last.strftime("%Y-%m-%d")})
    if symbol in EXPECTED_INCEPTION:
        expected = EXPECTED_INCEPTION[symbol]
        bounded = expected < VENDOR_FETCH_START[:7]
        record["inception"] = {"expected": expected, "first_bar_month": first.strftime("%Y-%m"),
                               "verdict": ("file starts at the fetch start, inception earlier (not testable here)" if bounded
                                           else "confirmed" if first.strftime("%Y-%m") == expected
                                           else f"corrected to {first.strftime('%Y-%m')}")}
        actual = entry_signal_date(frame.index)
        record["entry"] = {"expected_signal_date": EXPECTED_ENTRY_SIGNAL_DATE[symbol], "signal_date": actual,
                           "as_expected": actual == EXPECTED_ENTRY_SIGNAL_DATE[symbol]}
    return record


def run_d0(get_vendor: GetFrame, symbols: tuple[str, ...] = SYMBOLS + (CASH_ETF,)) -> dict:
    return {"run_at_utc": _now(), "coverage_end": COVERAGE_END, "max_consecutive_missing": MAX_CONSECUTIVE_MISSING,
            "symbols": {s: d0_symbol(s, get_vendor) for s in symbols}}


# --- D1 -------------------------------------------------------------------------------

def d1_symbol(symbol: str, vendor_close: pd.Series, get_broker: GetFrame, attempts: int = FETCH_ATTEMPTS) -> dict:
    record: dict = {"symbol": symbol, "class": CLASS_OF.get(symbol, "cash"), "attempts": []}
    broker = None
    for attempt in range(1, attempts + 1):
        try:
            broker = get_broker(symbol)
            break
        except Exception as err:  # noqa: BLE001
            record["attempts"].append({"attempt": attempt, "outcome": "broker bars unavailable", "error": str(err)[:300]})
    if broker is None:
        record.update({"status": "unchecked", "label": "single-vendor, unchecked",
                       "reason": f"broker bars unavailable after {attempts} attempts; the check is skipped (§5.3.2)"})
        return record
    stats = datacheck.overlap_statistics(vendor_close, broker["close"].astype(float), OVERLAP_START, OVERLAP_END)
    value = stats["mean_diff_annual_vendor_minus_broker"]
    passed = bool(abs(value) <= OVERLAP_MEAN_DIFF_ABS_MAX)
    record.update({"overlap": stats,
                   "check": {"mean_diff_annual_vendor_minus_broker": value, "threshold": f"within +/-{OVERLAP_MEAN_DIFF_ABS_MAX}",
                             "pass": passed, "within_exante_expectation": bool(abs(value) <= OVERLAP_EXANTE_ABS_MAX)},
                   "status": "pass" if passed else "excluded",
                   "reason": "mean difference within the gate" if passed else "branch X: mean difference outside +/-0.20% p.a."})
    return record


def run_d1(d0: dict, get_vendor_close: Callable[[str], pd.Series], get_broker: GetFrame) -> dict:
    kept = [s for s in SYMBOLS if d0["symbols"][s]["status"] == "pass"]
    return {"run_at_utc": _now(), "window": {"start": OVERLAP_START, "end": OVERLAP_END},
            "threshold_abs_max": OVERLAP_MEAN_DIFF_ABS_MAX, "exante_abs_max": OVERLAP_EXANTE_ABS_MAX,
            "symbols": {s: d1_symbol(s, get_vendor_close(s), get_broker) for s in kept}}


# --- Evaluation (§5.3.5) ----------------------------------------------------------------

def evaluate(d0: dict, d1: dict) -> dict:
    excluded = {s: d0["symbols"][s]["reason"] for s in SYMBOLS if d0["symbols"][s]["status"] == "excluded"}
    excluded.update({s: r["reason"] for s, r in d1["symbols"].items() if r["status"] == "excluded"})
    universe = [s for s in SYMBOLS if s not in excluded]
    unchecked = [s for s, r in d1["symbols"].items() if r["status"] == "unchecked"]
    per_class = {c: [s for s in group if s in universe] for c, group in UNIVERSE.items()}
    reasons = []
    if len(excluded) > HALT_MAX_EXCLUSIONS:
        reasons.append(f"{len(excluded)} symbols excluded, more than {HALT_MAX_EXCLUSIONS}")
    for c, members in per_class.items():
        if len(members) < HALT_MIN_PER_CLASS:
            reasons.append(f"class {c} left with {len(members)} instrument(s), fewer than {HALT_MIN_PER_CLASS}")
    return {"excluded": excluded, "universe": universe, "universe_size": len(universe), "per_class": per_class,
            "single_vendor_unchecked": unchecked, "halt": bool(reasons), "halt_reasons": reasons,
            "outcome": ("HALT: " + "; ".join(reasons)) if reasons else
                       f"proceed with {len(universe)} instruments" + (f" ({len(unchecked)} single-vendor, unchecked)" if unchecked else "")}


# --- Output ----------------------------------------------------------------------------

def write_report(report: dict, out_dir: Path) -> str:
    d0, d1, ev = report["D0"], report["D1"], report["evaluation"]
    lines = ["# Data checks D0 and D1 (§5.3.1, §5.3.2), single run", "",
             f"D0 run at {d0['run_at_utc']}, D1 run at {d1['run_at_utc']} (UTC). Instrument data only; no rule applied; "
             "D0 reads dates only; D1 reads daily returns inside the overlap window only.", "",
             f"**Outcome: {ev['outcome']}.**", "",
             "## D0: fetch and coverage (from each file's first bar to " + d0["coverage_end"] + ")", "",
             "| Symbol | Class | Rows | First bar | Last bar | Trading days / bars | Longest missing run | Inception (§4) | Entry signal date (§8.1) | Status |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for s, r in d0["symbols"].items():
        if r["status"] != "pass":
            lines.append(f"| {s} | {r['class']} | — | — | — | — | — | — | — | **{r['status']}**: {r['reason']} |")
            continue
        cov, inc, ent = r["coverage"], r.get("inception", {}), r.get("entry", {})
        lines.append(f"| {s} | {r['class']} | {r['rows']} | {r['first_bar']} | {r['last_bar']} | "
                     f"{cov['nyse_trading_days']} / {cov['bars_present']} | {cov['max_consecutive_missing_days']} | "
                     f"{inc.get('expected', '—')}: {inc.get('verdict', 'cash leg')} | "
                     f"{ent.get('signal_date', '—')} (expected {ent.get('expected_signal_date', '—')}) | pass |")
    missing = {s: r["coverage"]["missing_days"] for s, r in d0["symbols"].items() if r.get("coverage", {}).get("missing_days")}
    extra = {s: r["coverage"]["extra_bars_on_rule_calendar_closures"] for s, r in d0["symbols"].items()
             if r.get("coverage", {}).get("extra_bars_on_rule_calendar_closures")}
    if missing:
        lines += ["", "Missing NYSE trading days (descriptive): " + "; ".join(f"{s}: {', '.join(d)}" for s, d in missing.items()) + "."]
    if extra:
        lines += ["", "Bars on days the rule calendar lists as closed (calendar finding, reported only): "
                  + "; ".join(f"{s}: {', '.join(d)}" for s, d in extra.items()) + "."]
    lines += ["", f"## D1: vendor against broker, {d1['window']['start']} to {d1['window']['end']}", "",
              f"Gate: annualised mean daily return difference, vendor − broker, within ±{d1['threshold_abs_max'] * 100:.2f}% p.a. "
              f"Ex-ante expectation (§5.3.2, written before the run): every symbol under {d1['exante_abs_max'] * 100:.2f}% in absolute value.", "",
              "| Symbol | Common days | Mean diff (% p.a.) | Within ex-ante | Correlation | Tracking error (% p.a.) | Max daily gap (bp) | Days > 10 bp | Only vendor / only broker | Status |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for s, r in d1["symbols"].items():
        if r["status"] == "unchecked":
            lines.append(f"| {s} | — | — | — | — | — | — | — | — | **single-vendor, unchecked** |")
            continue
        o, c = r["overlap"], r["check"]
        lines.append(f"| {s} | {o['common_return_days']} | {c['mean_diff_annual_vendor_minus_broker'] * 100:+.4f} | "
                     f"{'yes' if c['within_exante_expectation'] else 'NO'} | {o['correlation_descriptive']:.6f} | "
                     f"{o['tracking_error_annual_descriptive'] * 100:.4f} | {o['max_abs_daily_diff'] * 1e4:.2f} | "
                     f"{o['days_abs_diff_over_large']} | {len(o['days_only_in_vendor'])} / {len(o['days_only_in_broker'])} | "
                     f"{'pass' if c['pass'] else '**excluded (branch X)**'} |")
    outside = [s for s, r in d1["symbols"].items() if r["status"] != "unchecked" and not r["check"]["within_exante_expectation"]]
    lines += ["", "Symbols outside the ex-ante expectation: " + (", ".join(outside) if outside else "none") + ".", "",
              "## Evaluation (§5.3.5)", "",
              f"Excluded: {', '.join(f'{s} ({r})' for s, r in ev['excluded'].items()) or 'none'}. "
              f"Universe: {ev['universe_size']} instruments ({', '.join(ev['universe'])}). "
              "Per class: " + ", ".join(f"{c} {len(m)}" for c, m in ev["per_class"].items()) + ". "
              f"Single-vendor, unchecked: {', '.join(ev['single_vendor_unchecked']) or 'none'}.", "",
              f"**Result: {ev['outcome']}.**"]
    text = "\n".join(lines) + "\n"
    (out_dir / "data_checks.md").write_text(text, encoding="utf-8")
    return text


# --- Stages ----------------------------------------------------------------------------

def stage_d0(out_dir: Path = CHECKS_DIR, get_vendor: GetFrame | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    d0 = run_d0(get_vendor or data.vendor_frame)
    (out_dir / "d0.json").write_text(json.dumps(d0, indent=2) + "\n", encoding="utf-8")
    return d0


def stage_d1(out_dir: Path = CHECKS_DIR, get_vendor_close: Callable[[str], pd.Series] | None = None,
             get_broker: GetFrame | None = None) -> dict:
    d0_path = out_dir / "d0.json"
    if not d0_path.exists():
        raise FileNotFoundError("d0.json missing: stage d0 must run and its manifest be committed before d1 (§5.3.1)")
    d0 = json.loads(d0_path.read_text(encoding="utf-8"))
    if get_vendor_close is None:
        def get_vendor_close(symbol: str) -> pd.Series:
            return data.vendor_frame(symbol)["adjClose"].astype(float)
    d1 = run_d1(d0, get_vendor_close, get_broker or data.broker_frame)
    (out_dir / "d1.json").write_text(json.dumps(d1, indent=2) + "\n", encoding="utf-8")
    report = {"D0": d0, "D1": d1, "evaluation": evaluate(d0, d1)}
    (out_dir / "data_checks.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(write_report(report, out_dir))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="§5.3 data checks D0 and D1, one run.")
    parser.add_argument("stage", choices=["d0", "d1"])
    args = parser.parse_args(argv)
    if args.stage == "d0":
        d0 = stage_d0()
        for s, r in d0["symbols"].items():
            print(f"{s}: {r['status']}" + (f", {r['rows']} rows, {r['first_bar']} to {r['last_bar']}, "
                                            f"entry {r.get('entry', {}).get('signal_date', 'cash')}" if r["status"] == "pass"
                                            else f" ({r['reason']})"))
        return 0
    report = stage_d1()
    return 1 if report["evaluation"]["halt"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
