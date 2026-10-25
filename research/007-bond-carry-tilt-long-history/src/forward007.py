"""Study 007 forward record (PREREGISTRATION.md §11): decision record, monthly
shadow line, interim figures and the single scoring.  No paper order.

Study 006's ``forward.py`` (copied unchanged) supplies the clock gates, the
execution-date rule, the wait log and the record writer; this module adds what
§11.2-§11.4 change for a fractional weight.

Decision record (§11.2).  ``python -m src.forward007 decide --signal-month m
[--fetch]`` fetches DGS10, DTB3 and DGS7 from FRED and Alpaca
``adjustment='all'`` daily bars of IEF and BIL from 2025-01-02 into
``paper-log/raw/`` (git-ignored, own manifest; ``data/raw/`` stays frozen).
The signal date t of month m is Study 001 §6.3's (last FRED day with DGS10
and DTB3).  t is final once every later weekday of m that is an NYSE day has
a row in all three FRED series (the H.15 release carries the three together)
and both ETFs have a bar on or after t; until then a wait line and no record.
On t, from observations dated on or before t only:

- c_t by ``carry_rank.carry_at_signal_dates`` (§6.1);
- the rank history (§6.2, "continues to expand, no re-estimation"): the
  carries of 1969-07 to 2026-09 from the study's frozen FRED files (exactly
  the episode's 687), then one carry per forward month from the fetched files;
  w_t for T1, T1a and T1b by ``carry_rank.expanding_rank`` with m = 60, 36, 120;
- h_t by ``carry_rank.trend_signal`` on the ETF total-return indices read at
  the last bar on or before each of the thirteen signal dates t-12 .. t
  (§6.3: "in the episode and the forward record the ETF closes are used");
  signal dates up to 2026-09 are the frozen schedule's;
- T2 = ½ w_t(T1) + ½ h_t, T3 = h_t.

Weights are written to four decimals (§11.2) and the shadow line uses the
written values.  A trial whose weight is undefined on t holds its position:
no trade, its weight drifts with the two legs over the period.

Starting weights (§11.2): the five trials' weights at the 2026-09 signal date
from ``results/episode/summary.json``; they are written in the first record.

Shadow line (§11.3).  ``python -m src.forward007 shadow --signal-month m
[--fetch]`` appends the line of the period that ended at month m's execution
date: IEF and BIL returns from the Alpaca closes, the five trials through
``tilt.run_tilt`` (from the starting weights, drift convention of §6.4, base
cost), B1 and B2 and each trial's B3 at its frozen w̄ through
``backtest.benchmarks``, and d = T1 − B3^T1.  Earlier lines' instrument
returns are reused, never recomputed.  Scoring (§11.4) runs once per block of
60 periods; the scoring date is in the record that ends the block.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import backtest, stats, tilt
from .alpaca_bars import fetch_bars, load_bars, total_return_index
from .calendar import build_schedule, nyse_trading_days, signal_dates
from .carry_rank import blend, carry_at_signal_dates, expanding_rank, trend_signal
from .config import CASH_LEG, COST_CASES, DURATION_LEG, PAPER_LOG_DIR, RAW_DIR, STUDY_DIR
from .config007 import (
    CARRY_FIRST_SIGNAL_MONTH,
    EPISODE_DIR,
    EPISODE_LAST_SIGNAL_MONTH,
    HISTORY_DIR,
    LOW_POWERED_TURNOVER,
    MIN_HISTORY,
    PRIMARY,
    TREND_LAG_ROWS,
    TRIAL_IDS,
)
from .forward import (
    BLOCK_PERIODS,
    FIRST_SIGNAL_MONTH,
    FRED_IDS,
    T_BAR,
    _first_bar_on_or_after,
    _utc,
    close_utc,
    execution_for,
    file_hashes,
    load_records,
    log_wait,
    refusal,
    utc_now,
    write_record,
)
from .fred import fetch_series, load_series

assert FIRST_SIGNAL_MONTH == "2026-10"  # §11.1: the note (6cbfa6c) was committed on 2026-10-25, before 2026-10-30
STARTING_MONTH = EPISODE_LAST_SIGNAL_MONTH  # "2026-09"
FORWARD_BARS_START = "2025-01-02"  # the trend needs the close twelve signal dates before 2026-10
DECIMALS = 4  # §11.2

DECISIONS_DIR = PAPER_LOG_DIR / "decisions"
FORWARD_RAW_DIR = PAPER_LOG_DIR / "raw"
FORWARD_MANIFEST = PAPER_LOG_DIR / "manifest.json"
SHADOW_CSV = PAPER_LOG_DIR / "shadow.csv"
WAITS_CSV = PAPER_LOG_DIR / "waits.csv"
INTERIM_JSON = PAPER_LOG_DIR / "interim.json"

STUDY = "007-bond-carry-tilt-long-history"
HISTORY_VERDICT = "inconclusive (fragile)"
LABEL = f"forward record, no paper order (section 11); history verdict: {HISTORY_VERDICT}"
NOT_YET_SCORED = "Not yet scored"
SHADOW_COLUMNS = (["signal_date", "execution_date", "period_end", "start_bar", "end_bar", "r_IEF", "r_BIL", "B1", "B2"]
                  + [f"B3_{k}" for k in TRIAL_IDS] + list(TRIAL_IDS) + ["d"]
                  + [f"w_{k}" for k in TRIAL_IDS] + [f"traded_{k}" for k in TRIAL_IDS]
                  + ["cost_per_side", "run_at_utc"])

VERDICT_NOT_TESTABLE = "not testable"
VERDICT_SUPPORTED = "supported (forward)"
VERDICT_REFUTED = "refuted (forward)"
VERDICT_INCONCLUSIVE = "inconclusive (forward)"


def frozen_weights(history_dir: Path = HISTORY_DIR) -> dict[str, float]:
    w = json.loads((Path(history_dir) / "summary.json").read_text(encoding="utf-8"))["weight_b3"]
    return {k: float(w[k]) for k in TRIAL_IDS}


def starting_weights(episode_dir: Path = EPISODE_DIR) -> dict[str, float]:
    """§11.2: the weights at the 2026-09 signal date, as the episode wrote them."""
    s = json.loads((Path(episode_dir) / "summary.json").read_text(encoding="utf-8"))
    start = s["weights_at_last_signal_month_for_forward_record"]
    if start["signal_month"] != STARTING_MONTH:
        raise ValueError(f"episode starting weights are for {start['signal_month']}, not {STARTING_MONTH}")
    return {k: float(start[k]) for k in TRIAL_IDS}


# --- Signal date, finality and weights ------------------------------------------------------------

def _cut(series: dict[str, pd.Series], t: pd.Timestamp) -> dict[str, pd.Series]:
    return {name: s.loc[s.index <= t] for name, s in series.items()}


def signal_status(fred: dict[str, pd.Series], bars: dict[str, pd.Series], month: str) -> tuple[str, pd.Timestamp | None, str]:
    """(``final`` | ``wait``, t, why).  Study 006's rule on all three FRED
    series, plus a bar of each ETF on or after t (the close of t is known)."""
    period = pd.Period(month, "M")
    t = signal_dates(fred["DGS10"], fred["DTB3"], month, month).iloc[0]
    if pd.isna(t):
        return "wait", None, f"FRED has no day in {month} with both DGS10 and DTB3"
    t = pd.Timestamp(t)
    later = pd.bdate_range(t + pd.Timedelta(days=1), period.to_timestamp(how="end").normalize())
    open_days = later.intersection(nyse_trading_days(later[0], later[-1])) if len(later) else later
    for name in FRED_IDS:
        missing = open_days.difference(fred[name].index)
        if len(missing):
            return "wait", t, (f"{name} has no row yet for {missing[0].date()}; t = {t.date()} is not final "
                               f"until every later weekday of {month} has a row")
    for leg in (DURATION_LEG, CASH_LEG):
        if bars[leg].index.max() < t:
            return "wait", t, f"no {leg} bar on or after t = {t.date()} yet (last {bars[leg].index.max().date()})"
    return "final", t, ""


def forward_signal_dates(frozen: dict[str, pd.Series], fred: dict[str, pd.Series], month: str) -> pd.Series:
    """Signal dates from 1969-07 to ``month``: the frozen schedule's up to
    2026-09, the fetched files' after it (months without a date dropped, as
    ``calendar.build_schedule`` does)."""
    old = build_schedule(frozen["DGS10"], frozen["DTB3"], CARRY_FIRST_SIGNAL_MONTH, STARTING_MONTH)["signal_date"]
    first_new = (pd.Period(STARTING_MONTH, "M") + 1).strftime("%Y-%m")
    if pd.Period(month, "M") <= pd.Period(STARTING_MONTH, "M"):
        raise ValueError(f"{month} is not a forward month")
    new = signal_dates(fred["DGS10"], fred["DTB3"], first_new, month).dropna()
    return pd.concat([old, new]).rename("signal_date")


def weights_at(frozen: dict[str, pd.Series], fred: dict[str, pd.Series], bars: dict[str, pd.Series],
               t: pd.Timestamp, month: str) -> dict:
    """c_t, n_t, the five weights (four decimals; None where undefined) and
    h_t on t, from observations dated on or before t only."""
    fred, bars = _cut(fred, t), _cut(bars, t)
    dates = forward_signal_dates(frozen, fred, month)
    if dates.index[-1] != pd.Period(month, "M") or pd.Timestamp(dates.iloc[-1]) != t:
        raise ValueError(f"the last signal date is not t = {t.date()}")
    n_old = int((dates.index <= pd.Period(STARTING_MONTH, "M")).sum())
    old_carry = carry_at_signal_dates(frozen["DGS10"], frozen["DGS7"], frozen["DTB3"], dates.iloc[:n_old])
    new_carry = pd.Series(np.nan, index=dates.index[n_old:], name="carry")
    for month_i in new_carry.index:  # ``signal.t3`` raises where DGS7 is missing on a signal date
        try:
            new_carry[month_i] = float(carry_at_signal_dates(fred["DGS10"], fred["DGS7"], fred["DTB3"],
                                                             dates.loc[[month_i]]).iloc[0])
        except ValueError:
            pass
    carry = pd.concat([old_carry, new_carry])
    out: dict = {"carry": None, "n": None, "trend": None,
                 "weights": {k: None for k in TRIAL_IDS}, "notes": []}
    if new_carry.isna().any():
        missing = [str(m) for m in new_carry.index[new_carry.isna()]]
        out["notes"].append(f"carry undefined in {missing} (DGS7 missing): T1, T1a, T1b and T2 hold their positions")
    else:
        out["carry"] = float(carry.iloc[-1])
        out["n"] = int(len(carry))
        for k, m in MIN_HISTORY.items():
            out["weights"][k] = round(float(expanding_rank(carry, m).iloc[-1]), DECIMALS)
    last = dates.iloc[-(TREND_LAG_ROWS + 1):]
    tri = {leg: total_return_index(pd.DataFrame({"close": bars[leg]})) for leg in (DURATION_LEG, CASH_LEG)}
    read = {leg: tri[leg].sort_index().reindex(pd.DatetimeIndex(last.values), method="ffill") for leg in tri}
    if any(r.isna().any() for r in read.values()):
        out["notes"].append("an ETF index is undefined on one of the thirteen signal dates: T2 and T3 hold")
    else:
        h = trend_signal(pd.Series(read[DURATION_LEG].to_numpy(), index=read[DURATION_LEG].index),
                         pd.Series(read[CASH_LEG].to_numpy(), index=read[CASH_LEG].index), last)
        out["trend"] = int(h.iloc[-1])
        out["weights"]["T3"] = float(out["trend"])
        if out["weights"][PRIMARY] is not None:
            out["weights"]["T2"] = round(float(blend(pd.Series([out["weights"][PRIMARY]]),
                                                     pd.Series([float(out["trend"])])).iloc[0]), DECIMALS)
    return out


def inputs_at(fred: dict[str, pd.Series], t: pd.Timestamp) -> dict:
    return {name: (None if pd.isna(fred[name].get(t, np.nan)) else float(fred[name].loc[t])) for name in FRED_IDS}


# --- Decision record ----------------------------------------------------------------------------------

def weights_before(records: list[dict], start: dict) -> dict:
    """The targets in force before the next record (None = holding, drifting)."""
    held = dict(start)
    for record in records:
        held = dict(record["weights_after"])
    return held


def decision_record(frozen: dict[str, pd.Series], fred: dict[str, pd.Series], bars: dict[str, pd.Series],
                    month: str, held: dict, start: dict, earlier_ok: int, now_utc: str,
                    input_sha256: dict | None = None) -> dict | None:
    """The record for ``month``, or None when the run must wait (nothing is
    written).  ``earlier_ok`` = number of earlier records with status ok."""
    base = {"study": STUDY, "label": LABEL, "signal_month": month, "run_at_utc": now_utc,
            "weights_before": dict(held), "input_sha256": dict(input_sha256 or {}),
            "paper_order": False, "orders": []}
    if earlier_ok == 0:
        base["starting_weights"] = {"signal_month": STARTING_MONTH, **start,
                                    "source": "results/episode/summary.json (section 11.2)"}
    state, t, why = signal_status(fred, bars, month)
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
                "execution_date": None, "days_slipped": None, "weights_after": dict(held),
                "notes": (f"no record by the close of the third NYSE day after the signal date "
                          f"({deadline.strftime('%Y-%m-%dT%H:%M:%SZ')}); every trial holds its position and the "
                          f"holding period runs on (section 11.2, Study 001 section 11.2). {why}").strip()}
    assert t is not None
    w = weights_at(frozen, fred, bars, t, month)
    after = {k: w["weights"][k] for k in TRIAL_IDS}
    record = {**base, "status": "ok", "signal_date": str(t.date()), "execution_date": str(execution.date()),
              "days_slipped": int(slipped), "inputs_on_signal_date": inputs_at(fred, t),
              "carry": w["carry"], "rank_history_n": w["n"], "trend": w["trend"], "weights_after": after,
              "notes": " ".join(["T1 on trial; T1a and T1b its fragility companions; T2 and T3 registered "
                                 "secondary trials. A weight of null means the trial holds its position (no "
                                 "trade). No order is placed for any of them."] + w["notes"])}
    if earlier_ok and earlier_ok % BLOCK_PERIODS == 0:
        record["scoring"] = {"block": earlier_ok // BLOCK_PERIODS, "periods": BLOCK_PERIODS,
                             "scoring_date": str(execution.date()),
                             "rule": "scored once, after this record's execution date ends the block (section 11.3)"}
    return record


# --- Shadow line --------------------------------------------------------------------------------------

def read_shadow(path: Path = SHADOW_CSV) -> pd.DataFrame:
    path = Path(path)
    return pd.read_csv(path) if path.exists() else pd.DataFrame(columns=SHADOW_COLUMNS)


def run_with_holds(targets: list, returns: pd.DataFrame, cost: float, initial_weight: float) -> pd.DataFrame:
    """``tilt.run_tilt`` where a None target means hold: the weight is the
    previous one after drift, so the traded fraction is zero."""
    w: list[float] = []
    for i, target in enumerate(targets):
        if target is None:
            if i == 0:
                w.append(float(initial_weight))
            else:
                prev = tilt.run_tilt(pd.Series(w, index=returns.index[:i]), returns.iloc[:i], cost, initial_weight)
                r = prev.iloc[-1]
                w.append(float(r["weight"] * (1.0 + returns[DURATION_LEG].iloc[i - 1]) / (1.0 + r["r_gross"])))
        else:
            w.append(float(target))
    return tilt.run_tilt(pd.Series(w, index=returns.index), returns, cost, initial_weight)


def shadow_line(indices: dict[str, pd.Series], ok_records: list[dict], shadow: pd.DataFrame, start: dict,
                frozen: dict[str, float], cost: float = COST_CASES["base"], now_utc: str | None = None) -> dict:
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
    for k in TRIAL_IDS:
        bench = backtest.benchmarks(returns, frozen[k], cost)
        if k == PRIMARY:
            line["B1"], line["B2"] = float(bench["B1"]["r"].iloc[-1]), float(bench["B2"]["r"].iloc[-1])
        line[f"B3_{k}"] = float(bench["B3"]["r"].iloc[-1])
        result = run_with_holds([r["weights_after"][k] for r in ok_records[:-1]], returns, cost, start[k])
        line[k] = float(result["r"].iloc[-1])
        line[f"w_{k}"] = float(result["weight"].iloc[-1])
        line[f"traded_{k}"] = float(result["traded_fraction"].iloc[-1])
    line["d"] = line[PRIMARY] - line[f"B3_{PRIMARY}"]
    line.update(cost_per_side=cost, run_at_utc=now_utc or utc_now())
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


# --- Interim and scoring ----------------------------------------------------------------------------------

STRATEGIES = ("B1", "B2", *(f"B3_{k}" for k in TRIAL_IDS), *TRIAL_IDS)


def interim(shadow: pd.DataFrame, now_utc: str | None = None) -> dict:
    """Counts and cumulative returns so far, under "Not yet scored"; no
    t-statistic and no verdict sentence before the block is complete."""
    n = int(len(shadow))
    out = {"heading": NOT_YET_SCORED, "label": LABEL, "holding_periods": n, "written_at_utc": now_utc or utc_now(),
           "scored_after": f"{BLOCK_PERIODS} holding periods", "periods_to_scoring": BLOCK_PERIODS - n % BLOCK_PERIODS,
           "T1_turnover": float(shadow[f"traded_{PRIMARY}"].astype(float).sum()) if n else 0.0,
           "cumulative": {}, "mean_d": None}
    if n:
        out["mean_d"] = float(shadow["d"].astype(float).mean())
        out["cumulative"] = {s: float(np.prod(1.0 + shadow[s].astype(float).to_numpy()) - 1.0) for s in STRATEGIES}
    return out


def forward_verdict(d: pd.Series, t1_weights: pd.Series, t1_turnover: float) -> dict:
    """§11.4 on one block of 60 periods."""
    if float(np.std(t1_weights.astype(float).to_numpy())) == 0.0:
        row, nw = VERDICT_NOT_TESTABLE, None
    else:
        nw = stats.newey_west_mean(d)
        if nw["mean"] > 0 and nw["t"] >= T_BAR:
            row = VERDICT_SUPPORTED
        elif nw["t"] <= -T_BAR:
            row = VERDICT_REFUTED
        else:
            row = VERDICT_INCONCLUSIVE
    labels = ["low-powered"] if t1_turnover < LOW_POWERED_TURNOVER else []
    return {"verdict": row, "labels": labels, "newey_west": nw, "T1_turnover": float(t1_turnover)}


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
    out = forward_verdict(rows["d"].astype(float).reset_index(drop=True), rows[f"w_{PRIMARY}"],
                          float(rows[f"traded_{PRIMARY}"].astype(float).sum()))
    out.update(block=block, periods=BLOCK_PERIODS, scoring_date=ok[end]["scoring"]["scoring_date"],
               history_verdict=HISTORY_VERDICT)
    return out


# --- Inputs ---------------------------------------------------------------------------------------------

def fetch_inputs(raw_dir: Path = FORWARD_RAW_DIR, manifest: Path = FORWARD_MANIFEST) -> None:
    for name in FRED_IDS:
        fetch_series(name, raw_dir, manifest)
    for leg in (DURATION_LEG, CASH_LEG):
        fetch_bars(leg, FORWARD_BARS_START, None, raw_dir, manifest)


def load_inputs(raw_dir: Path = FORWARD_RAW_DIR) -> tuple[dict, dict]:
    fred = {name: load_series(name, raw_dir) for name in FRED_IDS}
    bars = {leg: load_bars(leg, raw_dir)["close"].astype(float) for leg in (DURATION_LEG, CASH_LEG)}
    return fred, bars


# --- Entry point ------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Study 007 forward record (section 11). No paper order.")
    parser.add_argument("step", choices=("decide", "shadow", "interim"))
    parser.add_argument("--signal-month", help="YYYY-MM")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="print, write nothing")
    args = parser.parse_args(argv)
    now = utc_now()
    if args.step == "interim":
        payload = interim(read_shadow(), now)
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
    records = load_records(DECISIONS_DIR)
    start = starting_weights()
    if args.step == "decide":
        if any(r["signal_month"] == args.signal_month for r in records):
            print(f"refused: a record for {args.signal_month} exists")
            return 1
        if args.fetch and not args.dry_run:
            fetch_inputs()
        fred, bars = load_inputs()
        frozen = {name: load_series(name, RAW_DIR) for name in FRED_IDS}
        held = weights_before(records, start)
        earlier_ok = sum(r["status"] == "ok" for r in records)
        hashes = {**file_hashes(FORWARD_RAW_DIR, "fred_"), **file_hashes(FORWARD_RAW_DIR, "alpaca_")}
        record = decision_record(frozen, fred, bars, args.signal_month, held, start, earlier_ok, now, hashes)
        if record is None:
            reason = signal_status(fred, bars, args.signal_month)[2]
            print(f"wait: {reason}; re-check on the next run")
            if not args.dry_run:
                log_wait(args.signal_month, now, reason, WAITS_CSV)
            return 1
        print(json.dumps(record, indent=2, sort_keys=True))
        if not args.dry_run:
            print(f"written: {write_record(record, DECISIONS_DIR).relative_to(STUDY_DIR)}")
        return 0 if record["status"] == "ok" else 1
    ok = [r for r in records if r["status"] == "ok"]
    upto = [r for r in ok if r["signal_month"] <= args.signal_month]
    if not upto or upto[-1]["signal_month"] != args.signal_month or len(upto) < 2:
        print("refused: the line needs an ok record for this month and an earlier one (section 11.3)")
        return 1
    if _utc(now) < close_utc(upto[-1]["execution_date"]):
        print("refused: the line is written after the execution date's close")
        return 1
    if args.fetch and not args.dry_run:
        fetch_inputs()
    indices = {leg: total_return_index(load_bars(leg, FORWARD_RAW_DIR)) for leg in (DURATION_LEG, CASH_LEG)}
    line = shadow_line(indices, upto, read_shadow(), start, frozen_weights(), now_utc=now)
    print(json.dumps(line, indent=2, default=str))
    if not args.dry_run:
        print(f"appended: {append_shadow(line).relative_to(STUDY_DIR)}")
        INTERIM_JSON.write_text(json.dumps(interim(read_shadow(), now), indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
