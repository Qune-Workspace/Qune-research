"""The forward record (§11): the month-end decision record, the monthly
shadow line, the interim figures, the stopping rule and the verdict table.

No paper order is placed by anything in this module (§11, §12).  SPY is a
regime input and is never held.

Decision record (§11.1).  On the last NYSE trading day of a month, after the
close, ``python -m src.forward decide --signal-date t [--fetch]`` fetches
Alpaca ``adjustment='all'`` daily bars for SPY, IEF and BIL and CPIAUCNS
from FRED into ``paper-log/raw/`` (git-ignored; its own manifest, so the
study's ``data/raw/`` hashes stay frozen), confirms the bar for ``t`` is
present for all three, and computes with the study's own functions (the
ones the backtest called): ``mom_t`` through ``trend_signal.excess_momentum``
on the ETF total-return indices, ρ63 and ρ252 through
``regime.trailing_correlation`` on the common daily returns, the CPI flag
through ``regime.cpi_regime``, the unconditional target (B2) and the
conditional targets (T1, and T2, T3 as descriptives).  One JSON file per
signal date with every input value, the input hashes and the UTC time
written; never rewritten.  Only observations on or before ``t`` are used.

Shadow line (§11.2).  ``python -m src.forward shadow --signal-date t``
appends to ``paper-log/shadow.csv`` the holding-period return of B1 (hold
IEF), B2 and T1 (and T2, T3) over the period that *ended* at ``t``'s
execution date, from the same closes, with the period's regime flags and
``d_t``; the period's targets and switch flags are read from the previous
decision record (the one whose execution date started the period).  A line
is appended once per period, in order.

Interim figures (§11.2) go to ``paper-log/interim.json`` under the heading
"Not yet scored".  Scoring (§11.3–11.4) runs once, when ``stopping_month``
fires, through ``edge.conditional_edge`` with the pre-registered seed and
``forward_verdict``; the refuted row is tested first so that a result
meeting both the supported and the refuted conditions is reported as
refuted and the conflict named by the caller.

Gates: no record before ``FORWARD_FIRST_SIGNAL_DATE`` (the first month-end
after the note's publication), none before 21:15 UTC on the signal date
(after the New York close under EDT or EST), none on a date that is not the
last NYSE trading day of its month, none without the three bars for ``t``.
A refused run writes nothing and exits 1.
"""
from __future__ import annotations

import argparse
import json
import math
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from qune_research import data as lib

from . import regime
from .config import (CASH_LEG, COST_CASES, CPI_SERIES, DURATION_LEG, FORWARD_BARS_START, FORWARD_DECISIONS_DIR,
                     FORWARD_EARLIEST_UTC, FORWARD_FIRST_SIGNAL_DATE, FORWARD_INTERIM_JSON, FORWARD_LABEL,
                     FORWARD_MANIFEST, FORWARD_RAW_DIR, FORWARD_SHADOW_CSV, FORWARD_STOP_POSITIVE_MONTHS,
                     FORWARD_STOP_TOTAL_MONTHS, FORWARD_T_MIN, MIN_EDGE_PER_MONTH, MOMENTUM_LOOKBACK_MONTHS,
                     REGIME_SYMBOL, REGIME_WINDOWS, RESULTS_DIR, SEED, STUDY_DIR)
from .pipeline import etf_indices, window_bars
from .schedule import execution_dates, month_end_bars, nyse_trading_days
from .trend_signal import excess_momentum, month_end_levels

VERDICT_SUPPORTED = "supported (forward)"
VERDICT_REFUTED = "refuted (forward)"
VERDICT_INCONCLUSIVE = "inconclusive (forward)"
NOT_YET_SCORED = "Not yet scored"

STRATEGY_IDS = ("B2", "T1", "T2", "T3")          # B2 = the unconditional trend rule; T1 on trial; T2, T3 descriptive
FORWARD_SYMBOLS = (DURATION_LEG, CASH_LEG, REGIME_SYMBOL)
SHADOW_COLUMNS = ["signal_date", "execution_date", "period_start_bar", "period_end", "period_end_bar",
                  "days_slipped_start", "days_slipped_end", "r_IEF", "r_BIL", "B1", "B2", "T1", "T2", "T3", "d",
                  "B2_holding", "T1_holding", "T2_holding", "T3_holding",
                  "B2_switched", "T1_switched", "T2_switched", "T3_switched",
                  "positive_T1", "positive_T2", "positive_T3", "rho_T1", "rho_T2", "cpi_12m_change_T3",
                  "cost_per_side", "run_at_utc"]


# --- Stopping rule and verdict (§11.3–11.4; written at §14 step 2, unchanged) ----------------

def stopping_month(positive_flags: Iterable[bool], stop_positive: int = FORWARD_STOP_POSITIVE_MONTHS,
                   stop_total: int = FORWARD_STOP_TOTAL_MONTHS) -> int | None:
    """1-based count of holding periods at which the rule first fires, or
    None if it has not fired on the flags seen so far (§11.3)."""
    n_pos = 0
    for n, flag in enumerate(positive_flags, start=1):
        n_pos += int(bool(flag))
        if n_pos >= stop_positive or n >= stop_total:
            return n
    return None


def forward_verdict(edge: dict, t_min: float = FORWARD_T_MIN, min_edge: float = MIN_EDGE_PER_MONTH) -> str:
    """§11.4 on the forward edge (base costs)."""
    nw, boot = edge.get("newey_west"), edge.get("bootstrap")
    if nw is None or boot is None:
        return VERDICT_INCONCLUSIVE
    t, upper = nw["t"], boot["delta"]["ci_high"]
    if upper < min_edge or t <= -t_min:
        return VERDICT_REFUTED
    if edge["delta"] > 0 and t >= t_min and edge["mean_positive"] > 0 and edge["mean_negative"] < 0:
        return VERDICT_SUPPORTED
    return VERDICT_INCONCLUSIVE


# --- Gates ----------------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def earliest_run_utc(signal_date) -> pd.Timestamp:
    """21:15 UTC on the signal date (after the 16:00 New York close under
    EDT or EST)."""
    hour, minute = FORWARD_EARLIEST_UTC
    return pd.Timestamp(signal_date).normalize().tz_localize("UTC") + pd.Timedelta(hours=hour, minutes=minute)


def refusal(signal_date, run_at_utc: str, first_signal_date: str = FORWARD_FIRST_SIGNAL_DATE) -> str | None:
    """Why a run must not write anything, or None if it may."""
    t = pd.Timestamp(signal_date).normalize()
    if t < pd.Timestamp(first_signal_date):
        return (f"{t.date()} is before the first forward signal date {first_signal_date} (section 14 step 11); "
                f"the history is spent and no earlier month may be recorded")
    now = pd.Timestamp(run_at_utc)
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    if now < earliest_run_utc(t):
        return (f"it is {now.strftime('%Y-%m-%dT%H:%M:%SZ')}, before {earliest_run_utc(t).strftime('%H:%M')} UTC on the "
                f"signal date; a daily bar fetched during the session is the partial day (section 16)")
    return None


# --- Decision record (§11.1) -------------------------------------------------------------------

def _month_end_refusal(t: pd.Timestamp, trading_days: pd.DatetimeIndex) -> str | None:
    month_last_day = t.to_period("M").to_timestamp(how="end").normalize()
    later = trading_days[(trading_days > t) & (trading_days <= month_last_day)]
    if len(later):
        return (f"{t.date()} is not the last NYSE trading day of its month ({later[-1].date()} is); "
                f"no signal on other days (section 6.3)")
    return None


def decision_record(closes: dict[str, pd.Series], cpi: pd.Series | None, signal_date, holding_before: dict,
                    run_at_utc: str | None = None, trading_days: pd.DatetimeIndex | None = None,
                    input_sha256: dict[str, str] | None = None) -> dict:
    """The §11.1 record for ``signal_date`` from the three close series
    (``adjustment='all'``) and the CPI series (monthly, PeriodIndex).  Only
    observations on or before the signal date are used; later ones in the
    inputs are ignored."""
    t = pd.Timestamp(signal_date).normalize()
    month = t.to_period("M")
    if trading_days is None:
        trading_days = nyse_trading_days(t, t + pd.Timedelta(days=45))
    base = {"study": "005-duration-trend-regime", "label": FORWARD_LABEL, "signal_date": str(t.date()),
            "run_at_utc": run_at_utc or utc_now(), "holding_before": dict(holding_before),
            "input_sha256": dict(input_sha256 or {}), "orders": [], "paper_order": False,
            "regime_symbol_held": False}
    unavailable = {**base, "status": "signal unavailable", "execution_date": None, "targets": None, "switch": None}
    why = _month_end_refusal(t, trading_days)
    if why:
        return {**unavailable, "notes": why}
    cut = {}
    for name in FORWARD_SYMBOLS:
        series = closes[name].astype(float).dropna().sort_index()
        series = series.loc[series.index <= t]
        if series.empty or series.index[-1] != t:
            last = str(series.index[-1].date()) if not series.empty else None
            return {**unavailable, "notes": f"no {name} bar for the signal date (last bar {last}); "
                                            f"re-check on the next run, never fill (section 11.5)"}
        cut[name] = series
    indices = etf_indices({DURATION_LEG: cut[DURATION_LEG], CASH_LEG: cut[CASH_LEG]})
    bars = window_bars(indices, etf_cash=True)
    month_ends = month_end_bars(bars)
    mom = excess_momentum(indices[DURATION_LEG], indices[CASH_LEG], month_ends)
    if month not in mom.index:
        return {**unavailable, "notes": f"the {MOMENTUM_LOOKBACK_MONTHS}-month lookback is not covered by the bars"}
    value = float(mom.loc[month])
    target_b2 = DURATION_LEG if value > 0 else CASH_LEG
    levels = {name: month_end_levels(indices[name], month_ends) for name in (DURATION_LEG, CASH_LEG)}
    t12 = month - MOMENTUM_LOOKBACK_MONTHS
    dates = pd.Series([t], index=pd.PeriodIndex([month], freq="M"), name="signal_date")
    returns = regime.common_returns(cut[REGIME_SYMBOL], cut[DURATION_LEG])
    regimes: dict[str, dict] = {}
    for trial in ("T1", "T2"):
        window = REGIME_WINDOWS[trial]
        rho = float(regime.trailing_correlation(returns, dates, window).iloc[0])
        if math.isnan(rho):
            return {**unavailable, "notes": f"{trial}: fewer than {window} common SPY-IEF return days on or before "
                                            f"the signal date"}
        tail = returns.loc[:t].iloc[-window:]
        regimes[trial] = {"variable": f"sign of the {window}-day SPY-IEF correlation", "window_days": window,
                          "first_return_day": str(tail.index[0].date()), "rho": rho, "positive": bool(rho > 0.0)}
    cpi_variable = "CPIAUCNS twelve-month change (m-2) > 3%"
    if cpi is None:
        regimes["T3"] = {"variable": cpi_variable, "status": "not available: no CPI series"}
    else:
        visible = cpi.loc[cpi.index <= month] if isinstance(cpi.index, pd.PeriodIndex) else cpi
        frame = regime.cpi_regime(visible, dates)
        if frame.empty:
            regimes["T3"] = {"variable": cpi_variable, "status": "not available: no defined lagged change"}
        else:
            row = frame.iloc[0]
            regimes["T3"] = {"variable": cpi_variable, "cpi_month": str(row["cpi_month"]),
                             "cpi_month_filled": bool(row["cpi_month_filled"]),
                             "cpi_12m_change": float(row["cpi_12m_change"]), "positive": bool(row["positive"])}
    targets = {"B2": target_b2}
    for trial in ("T1", "T2", "T3"):
        flag = regimes[trial].get("positive")
        targets[trial] = None if flag is None else (target_b2 if flag else DURATION_LEG)
    switch = {name: (None if targets[name] is None or holding_before.get(name) is None
                     else targets[name] != holding_before[name]) for name in STRATEGY_IDS}
    execution = execution_dates(dates, trading_days).iloc[0]
    return {**base, "status": "ok", "execution_date": str(execution.date()),
            "trend": {"rule": "IEF if mom > 0 else BIL (Study 003 T1, section 6.2)", "mom": value,
                      "tri_ief_t": float(levels[DURATION_LEG].loc[month]),
                      "tri_ief_t12": float(levels[DURATION_LEG].loc[t12]),
                      "tri_bil_t": float(levels[CASH_LEG].loc[month]), "tri_bil_t12": float(levels[CASH_LEG].loc[t12]),
                      "t12_date": str(month_ends.loc[t12].date()),
                      "close_t": {name: float(cut[name].iloc[-1]) for name in FORWARD_SYMBOLS}},
            "regimes": regimes, "targets": targets, "switch": switch,
            "notes": "B2 = unconditional trend rule; T1 = B2's target in a positive regime, IEF otherwise (on trial); "
                     "T2, T3 descriptive. No order is placed for any of them."}


def load_records(decisions_dir: Path = FORWARD_DECISIONS_DIR, before=None) -> list[dict]:
    directory = Path(decisions_dir)
    if not directory.exists():
        return []
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))]
    if before is not None:
        limit = str(pd.Timestamp(before).date())
        records = [r for r in records if r["signal_date"] < limit]
    return records


def previous_targets(decisions_dir: Path = FORWARD_DECISIONS_DIR,
                     episode_summary: Path = RESULTS_DIR / "episode" / "summary.json",
                     before=None) -> tuple[dict, str]:
    """The holdings before a signal date: the targets of the latest earlier
    ``status: ok`` record, else the episode's terminal targets (the
    2026-09-30 signal, whose holding period the forward record starts after)."""
    ok = [r for r in load_records(decisions_dir, before=before) if r["status"] == "ok"]
    if ok:
        last = max(ok, key=lambda r: r["signal_date"])
        return dict(last["targets"]), f"decision record {last['signal_date']}"
    summary = json.loads(Path(episode_summary).read_text(encoding="utf-8"))
    trend = summary["terminal_trend_target"]
    out = {"B2": trend}
    for trial in ("T1", "T2", "T3"):
        terminal = summary["terminal_regime"].get(trial)
        out[trial] = None if terminal is None else (trend if terminal["positive"] else DURATION_LEG)
    return out, f"episode terminal targets (signal date {summary['terminal_regime']['T1']['signal_date']})"


def write_record(record: dict, directory: Path = FORWARD_DECISIONS_DIR) -> Path:
    """One file per signal date; refuses to overwrite (a record is never
    rewritten; a correction is a later record with a note)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record['signal_date']}.json"
    if path.exists():
        raise FileExistsError(f"{path} exists: decision records are never overwritten (section 11.1)")
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


# --- Shadow line (§11.2) ---------------------------------------------------------------------

def _first_bar_on_or_after(bars: pd.DatetimeIndex, day: pd.Timestamp) -> pd.Timestamp | None:
    later = bars[bars >= day]
    return later[0] if len(later) else None


def shadow_line(closes: dict[str, pd.Series], previous: dict, current: dict,
                cost_per_side: float = COST_CASES["base"], run_at_utc: str | None = None) -> dict:
    """The §11.2 line for the holding period from ``previous``'s execution
    date to ``current``'s, in Study 003's engine conventions: the period
    runs between the first common IEF/BIL bar on or after each execution
    date (slippage recorded), a switch pays ``cost_per_side`` on the sale and
    on the purchase of the whole position, hold-IEF pays nothing."""
    if previous["status"] != "ok" or current["status"] != "ok":
        raise ValueError("both decision records must have status ok")
    legs = {name: closes[name].astype(float).dropna().sort_index() for name in (DURATION_LEG, CASH_LEG)}
    common = legs[DURATION_LEG].index.intersection(legs[CASH_LEG].index).sort_values()
    start, end = pd.Timestamp(previous["execution_date"]), pd.Timestamp(current["execution_date"])
    if end <= start:
        raise ValueError("the current record's execution date must follow the previous record's")
    start_bar, end_bar = _first_bar_on_or_after(common, start), _first_bar_on_or_after(common, end)
    if start_bar is None or end_bar is None:
        missing = start.date() if start_bar is None else end.date()
        raise ValueError(f"no common IEF/BIL bar on or after {missing}; the line is written after the execution "
                         f"date's close, never before")
    r = {name: float(legs[name].loc[end_bar] / legs[name].loc[start_bar] - 1.0) for name in legs}
    factor_switch = (1.0 - cost_per_side) ** 2
    line = {"signal_date": previous["signal_date"], "execution_date": previous["execution_date"],
            "period_start_bar": str(start_bar.date()), "period_end": current["execution_date"],
            "period_end_bar": str(end_bar.date()),
            "days_slipped_start": int(len(common[(common >= start) & (common < start_bar)])),
            "days_slipped_end": int(len(common[(common >= end) & (common < end_bar)])),
            "r_IEF": r[DURATION_LEG], "r_BIL": r[CASH_LEG], "B1": r[DURATION_LEG]}
    for name in STRATEGY_IDS:
        holding = previous["targets"].get(name)
        if holding is None:
            line[name], line[f"{name}_holding"], line[f"{name}_switched"] = float("nan"), None, None
            continue
        switched = bool(previous["switch"].get(name))
        factor = factor_switch if switched else 1.0
        line[name] = factor * (1.0 + r[holding]) - 1.0
        line[f"{name}_holding"], line[f"{name}_switched"] = holding, switched
    line["d"] = line["B2"] - line["B1"]
    for trial in ("T1", "T2", "T3"):
        line[f"positive_{trial}"] = previous["regimes"][trial].get("positive")
    line["rho_T1"], line["rho_T2"] = previous["regimes"]["T1"]["rho"], previous["regimes"]["T2"]["rho"]
    line["cpi_12m_change_T3"] = previous["regimes"]["T3"].get("cpi_12m_change")
    line["cost_per_side"], line["run_at_utc"] = cost_per_side, run_at_utc or utc_now()
    return {column: line[column] for column in SHADOW_COLUMNS}


def read_shadow(path: Path = FORWARD_SHADOW_CSV) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=SHADOW_COLUMNS)
    return pd.read_csv(path)


def append_shadow(line: dict, path: Path = FORWARD_SHADOW_CSV) -> Path:
    """Append one line; refuses a second line for the same period and a
    period that does not follow the last one (a period is recorded once and
    a missed month is logged, never skipped silently; §11.5)."""
    path = Path(path)
    existing = read_shadow(path)
    if len(existing) and (existing["execution_date"].astype(str) == line["execution_date"]).any():
        raise FileExistsError(f"shadow.csv already has the period starting {line['execution_date']}")
    if len(existing) and str(existing["period_end"].iloc[-1]) != line["execution_date"]:
        raise ValueError(f"the period starting {line['execution_date']} does not follow the last recorded period "
                         f"(ends {existing['period_end'].iloc[-1]})")
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([line], columns=SHADOW_COLUMNS).to_csv(path, mode="a", header=not path.exists(), index=False)
    return path


# --- Interim figures and the single scoring (§11.2–11.4) ---------------------------------------

def _positive_flags(shadow: pd.DataFrame) -> np.ndarray:
    return shadow["positive_T1"].astype(str).str.lower().eq("true").to_numpy()


def interim(shadow: pd.DataFrame, run_at_utc: str | None = None) -> dict:
    """What is published every month under "Not yet scored": counts, the
    conditional means so far, whether the stopping rule has fired.  No
    verdict sentence before the rule fires."""
    n = int(len(shadow))
    out = {"heading": NOT_YET_SCORED, "label": FORWARD_LABEL, "holding_periods": n,
           "written_at_utc": run_at_utc or utc_now(),
           "stopping_rule": f"first month-end with {FORWARD_STOP_POSITIVE_MONTHS} positive-regime months (T1) or "
                            f"{FORWARD_STOP_TOTAL_MONTHS} holding periods",
           "stopping_month": None, "n_pos_T1": 0, "n_neg_T1": 0, "mean_d_positive": None, "mean_d_negative": None,
           "delta_so_far": None, "cumulative": {}}
    if n == 0:
        return out
    pos, d = _positive_flags(shadow), shadow["d"].to_numpy(dtype=float)
    out["stopping_month"] = stopping_month(pos)
    out["n_pos_T1"], out["n_neg_T1"] = int(pos.sum()), int((~pos).sum())
    if pos.any():
        out["mean_d_positive"] = float(d[pos].mean())
    if (~pos).any():
        out["mean_d_negative"] = float(d[~pos].mean())
    if pos.any() and (~pos).any():
        out["delta_so_far"] = out["mean_d_positive"] - out["mean_d_negative"]
    for name in ("B1", "B2", "T1", "T2", "T3"):
        values = shadow[name].to_numpy(dtype=float)
        defined = values[~np.isnan(values)]
        out["cumulative"][name] = float(np.prod(1.0 + defined) - 1.0) if len(defined) else None
    return out


def score(shadow: pd.DataFrame) -> dict:
    """§11.3–11.4, run once when the stopping rule has fired: the edge
    statistics of §9.3 on the forward ``d_t`` with the pre-registered seed
    and the verdict row.  Raises if the rule has not fired."""
    from .edge import conditional_edge
    pos = _positive_flags(shadow)
    fired = stopping_month(pos)
    if fired is None:
        raise RuntimeError("the stopping rule has not fired; the record is scored once, when it does (section 11.3)")
    scored = shadow.iloc[:fired]
    index = pd.RangeIndex(fired)
    d = pd.Series(scored["d"].to_numpy(dtype=float), index=index, name="d")
    edge = conditional_edge(d, pd.Series(pos[:fired], index=index), np.random.default_rng(SEED))
    verdict = forward_verdict(edge)
    both = (edge.get("newey_west") is not None and edge.get("bootstrap") is not None
            and edge["delta"] > 0 and edge["newey_west"]["t"] >= FORWARD_T_MIN
            and edge["mean_positive"] > 0 and edge["mean_negative"] < 0
            and edge["bootstrap"]["delta"]["ci_high"] < MIN_EDGE_PER_MONTH)
    return {"scored_periods": fired, "scoring_period_end": str(scored["period_end"].iloc[-1]), "edge": edge,
            "verdict": verdict, "in_sample_row": "refuted in-sample",
            "conflict": ("meets both the supported and the refuted condition; refuted tested first (section 16 note 2)"
                         if both else None)}


# --- Inputs: fetch and load (paper-log/raw/, own manifest) -----------------------------------------

def fetch_inputs(raw_dir: Path = FORWARD_RAW_DIR, manifest_path: Path = FORWARD_MANIFEST, session=None) -> None:
    """Fresh bars for the three symbols from ``FORWARD_BARS_START`` to now
    and the CPI series; credentials from the environment only."""
    for symbol in FORWARD_SYMBOLS:
        lib.fetch_alpaca(symbol, FORWARD_BARS_START, None, raw_dir, manifest_path, session)
    lib.fetch_fred(CPI_SERIES, raw_dir, manifest_path, session)


def monthly_cpi(series: pd.Series) -> pd.Series:
    """A FRED CPIAUCNS series (dated the first of the month) as a monthly
    PeriodIndex series without the missing prints."""
    out = series.dropna().copy()
    out.index = pd.PeriodIndex(out.index, freq="M")
    return out


def load_inputs(raw_dir: Path = FORWARD_RAW_DIR, manifest_path: Path = FORWARD_MANIFEST) -> tuple[dict, pd.Series | None, dict]:
    closes = {s: lib.load_alpaca(s, raw_dir)["close"].astype(float).dropna() for s in FORWARD_SYMBOLS}
    cpi_path = lib.fred_path(CPI_SERIES, raw_dir)
    cpi = monthly_cpi(lib.load_fred(CPI_SERIES, raw_dir)) if cpi_path.exists() else None
    manifest = lib.read_manifest(manifest_path)
    hashes = {name: entry["sha256"] for name, entry in manifest.items() if "sha256" in entry}
    return closes, cpi, hashes


# --- Entry point ----------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Study 005 forward record (section 11). No paper order.")
    parser.add_argument("step", choices=("decide", "shadow", "interim"))
    parser.add_argument("--signal-date", help="YYYY-MM-DD, the last NYSE trading day of the month")
    parser.add_argument("--fetch", action="store_true", help="fetch fresh bars and CPI into paper-log/raw/ first")
    parser.add_argument("--dry-run", action="store_true", help="print, write nothing")
    parser.add_argument("--check-only-historical", action="store_true",
                        help="CHECK ONLY: compute a record for a date before the first forward signal date from the "
                             "study's frozen data/raw files, print it, write nothing (used once at step 11 against "
                             "the episode's terminal values)")
    args = parser.parse_args(argv)
    now = utc_now()
    if args.step == "interim":
        payload = interim(read_shadow(), now)
        print(json.dumps(payload, indent=2))
        if not args.dry_run:
            FORWARD_INTERIM_JSON.parent.mkdir(parents=True, exist_ok=True)
            FORWARD_INTERIM_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            print(f"written: {FORWARD_INTERIM_JSON.relative_to(STUDY_DIR)}")
        return 0
    if not args.signal_date:
        parser.error("--signal-date is required for decide and shadow")
    if args.check_only_historical:
        from .config import MANIFEST_PATH, RAW_DIR
        from .data import cpi_series, episode_closes
        print("CHECK ONLY: not a forward record; nothing is written (section 14 step 11 check against the episode)")
        record = decision_record(episode_closes(RAW_DIR, MANIFEST_PATH), monthly_cpi(cpi_series(RAW_DIR, MANIFEST_PATH)),
                                 args.signal_date, {}, now)
        record["label"] = "CHECK ONLY, not a forward record, not written"
        print(json.dumps(record, indent=2, sort_keys=True))
        return 0 if record["status"] == "ok" else 1
    why = refusal(args.signal_date, now)
    if why:
        print(f"refused: {why}")
        return 1
    if args.fetch and not args.dry_run:
        fetch_inputs()
    closes, cpi, hashes = load_inputs()
    if args.step == "decide":
        holding_before, source = previous_targets(before=args.signal_date)
        record = decision_record(closes, cpi, args.signal_date, holding_before, now, input_sha256=hashes)
        record["holding_before_source"] = source
        print(json.dumps(record, indent=2, sort_keys=True))
        if not args.dry_run:
            print(f"written: {write_record(record).relative_to(STUDY_DIR)}")
        return 0 if record["status"] == "ok" else 1
    records = {r["signal_date"]: r for r in load_records()}
    current = records.get(str(pd.Timestamp(args.signal_date).date()))
    if current is None or current["status"] != "ok":
        print(f"refused: no ok decision record for {args.signal_date}; run decide first")
        return 1
    earlier = [r for r in records.values() if r["status"] == "ok" and r["signal_date"] < current["signal_date"]]
    if not earlier:
        print("refused: no earlier decision record; the first forward period starts at the first record's execution "
              "date and its line is written after the second record (section 11.2)")
        return 1
    previous = max(earlier, key=lambda r: r["signal_date"])
    line = shadow_line(closes, previous, current, run_at_utc=now)
    print(json.dumps(line, indent=2, default=str))
    if not args.dry_run:
        print(f"appended: {append_shadow(line).relative_to(STUDY_DIR)}")
        payload = interim(read_shadow(), now)
        FORWARD_INTERIM_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"written: {FORWARD_INTERIM_JSON.relative_to(STUDY_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
