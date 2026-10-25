"""Study 008 forward record (PREREGISTRATION.md §11): decision record, monthly
shadow line, interim figures and the single scoring.  No paper order.

Study 007's ``forward007.py`` (copied unchanged) supplies the finality rule
(``signal_status``: t final once every later NYSE weekday of m has a row in
DGS10, DTB3 and DGS7 and both ETFs have a bar on or after t) and the hold
engine (``run_with_holds``); Study 006's ``forward.py`` supplies the clock
gates, the execution-date rule, the wait log and the record writer.  This
module adds what §11.2 changes: a real yield from the CPI instead of a carry,
three trials, no trend.

Decision record (§11.2).  ``python -m src.forward008 decide --signal-month m
[--fetch]`` fetches DGS10, DTB3, DGS7, CPIAUCNS and CPILFENS from FRED and
Alpaca ``adjustment='all'`` daily bars of IEF and BIL into ``paper-log/raw/``
(git-ignored, own manifest; ``data/raw/`` stays frozen).  On t, for each CPI
series, from the file fetched on t (§11.2: "the index is used only if its row
is in the fetched file on t"):

- CPI(m - 1) after the file's last non-empty row: **not yet in the fetched
  file**; §6.1's availability rule sets k to the latest month the file holds;
- CPI(m - 1) an empty row before the last non-empty one: **never published**
  (§16 (b)); r is undefined and the trials on that series hold;
- otherwise k = m - 1.  The same test on k - 12: an empty row there (the
  October 2025 index) makes r undefined, so signal month 2026-11 holds
  (k - 12 = 2025-10), as §11's own text and §16 (b) say.

Each record writes k, k - 12 and their status for both series, π and r at
full precision, n (defined real yields in the rank history) and w for T1, T1a
and T1b to four decimals.  Month m's own index is published in month m + 1,
after the deadline of the third NYSE day after t, so no later CPI can enter.

Rank history (§6.2, "continues to expand (T1b's to trail), no
re-estimation"): the real yields of 1969-07 to 2026-09 exactly as the episode
computed them (``gate008.weight_paths`` on the frozen files and
``results/cpi_availability.csv``), then one per forward month.  A forward
month's real yield is the one its own decision record wrote; only a month
without an ok record is computed from the current fetch (with its own
signal date's DGS10 and the rule above, and said so in the record).

Starting weights (§11.2): the three trials' weights at the 2026-09 signal
date from ``results/episode/summary.json``.  Shadow line (§11.3), interim and
scoring (§11.4) as Study 007's, for T1, T1a and T1b; d = T1 - B3^T1.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import backtest, stats
from .alpaca_bars import fetch_bars, load_bars, total_return_index
from .calendar import build_schedule, signal_dates
from .config import CASH_LEG, COST_CASES, DURATION_LEG, PAPER_LOG_DIR, RAW_DIR, STUDY_DIR
from .config008 import (
    CPI_AVAILABILITY_PATH,
    CPI_SERIES,
    EPISODE_DIR,
    EPISODE_LAST_SIGNAL_MONTH,
    HISTORY_DIR,
    LOW_POWERED_TURNOVER_008,
    PRIMARY,
    RANK_KIND,
    RANK_N,
    REAL_YIELD_FIRST_SIGNAL_MONTH,
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
from .forward007 import _cut, run_with_holds, signal_status
from .fred import fetch_series, load_series, sha256_of
from .gate008 import weight_paths
from .real_yield import monthly, rank_defined

assert FIRST_SIGNAL_MONTH == "2026-10"  # §11.1: the note (a90f048) was committed on 2026-10-25, before 2026-10-30
STARTING_MONTH = EPISODE_LAST_SIGNAL_MONTH  # "2026-09"
FORWARD_BARS_START = "2026-09-01"  # no trend here: the bars serve finality and the shadow line only
DECIMALS = 4  # §11.2
CPI_IDS = tuple(sorted(set(CPI_SERIES.values())))  # ("CPIAUCNS", "CPILFENS")

DECISIONS_DIR = PAPER_LOG_DIR / "decisions"
FORWARD_RAW_DIR = PAPER_LOG_DIR / "raw"
FORWARD_MANIFEST = PAPER_LOG_DIR / "manifest.json"
SHADOW_CSV = PAPER_LOG_DIR / "shadow.csv"
WAITS_CSV = PAPER_LOG_DIR / "waits.csv"
INTERIM_JSON = PAPER_LOG_DIR / "interim.json"

STUDY = "008-bond-value-tilt-long-history"
HISTORY_VERDICT = "not supported"  # results/history/summary.json, T1 (README.md); a test reads it
LABEL = f"forward record, no paper order (section 11); history verdict: {HISTORY_VERDICT}"
NOT_YET_SCORED = "Not yet scored"
SHADOW_COLUMNS = (["signal_date", "execution_date", "period_end", "start_bar", "end_bar", "r_IEF", "r_BIL", "B1", "B2"]
                  + [f"B3_{k}" for k in TRIAL_IDS] + list(TRIAL_IDS) + ["d"]
                  + [f"w_{k}" for k in TRIAL_IDS] + [f"traded_{k}" for k in TRIAL_IDS]
                  + ["cost_per_side", "run_at_utc"])

IN_FILE = "in the fetched file"
NOT_YET = "not yet in the fetched file"
NEVER = "never published"

VERDICT_NOT_TESTABLE = "not testable"
VERDICT_SUPPORTED = "supported (forward)"
VERDICT_REFUTED = "refuted (forward)"
VERDICT_INCONCLUSIVE = "inconclusive (forward)"


def frozen_weights(history_dir: Path = HISTORY_DIR) -> dict[str, float]:
    w = json.loads((Path(history_dir) / "summary.json").read_text(encoding="utf-8"))["weight_b3"]
    return {k: float(w[k]) for k in TRIAL_IDS}


def starting_weights(episode_dir: Path = EPISODE_DIR) -> dict[str, float | None]:
    """§11.2: the weights at the 2026-09 signal date, as the episode wrote them."""
    s = json.loads((Path(episode_dir) / "summary.json").read_text(encoding="utf-8"))
    start = s["weights_at_last_signal_month_for_forward_record"]
    if start["signal_month"] != STARTING_MONTH:
        raise ValueError(f"episode starting weights are for {start['signal_month']}, not {STARTING_MONTH}")
    return {k: (None if start[k] is None else float(start[k])) for k in TRIAL_IDS}


# --- Real yields: the episode's path, then the forward months ----------------------------------------

def episode_real_yields(frozen: dict[str, pd.Series], frozen_cpi: dict[str, pd.Series],
                        availability: pd.DataFrame) -> pd.DataFrame:
    """r for each CPI series on every signal month 1969-07 to 2026-09 (NaN
    where undefined), from the frozen files exactly as the episode built them."""
    schedule = build_schedule(frozen["DGS10"], frozen["DTB3"], REAL_YIELD_FIRST_SIGNAL_MONTH, STARTING_MONTH)
    paths = weight_paths(frozen["DGS10"], frozen_cpi, availability, schedule)
    return paths[[f"r_{s}" for s in CPI_IDS]].rename(columns=lambda c: c[2:])


def _status(cpi_m: pd.Series, month: pd.Period, last: pd.Period) -> str:
    if month > last:
        return NOT_YET
    return NEVER if pd.isna(cpi_m.get(month, np.nan)) else IN_FILE


def cpi_reading(cpi: pd.Series, month: str) -> dict:
    """k, k - 12, their status and π for signal month ``month`` from one CPI
    file as fetched on t (§11.2, §6.1, §16 (b)).  π is None when undefined."""
    cpi_m = monthly(cpi)
    m = pd.Period(month, "M")
    published = cpi_m.dropna()
    if published.empty:
        raise ValueError(f"{cpi.name}: the fetched file holds no index")
    last = published.index.max()
    s_m1 = _status(cpi_m, m - 1, last)
    k = last if s_m1 == NOT_YET else m - 1
    s_k = _status(cpi_m, k, last)
    s_k12 = _status(cpi_m, k - 12, last)
    out = {"k": str(k), "k_minus_12": str(k - 12), "status_m_minus_1": s_m1, "status_k": s_k,
           "status_k_minus_12": s_k12, "last_month_in_file": str(last),
           "cpi_k": None if pd.isna(cpi_m.get(k, np.nan)) else float(cpi_m[k]),
           "cpi_k_minus_12": None if pd.isna(cpi_m.get(k - 12, np.nan)) else float(cpi_m[k - 12]), "pi": None}
    if s_m1 != NEVER and s_k == IN_FILE and s_k12 == IN_FILE:
        out["pi"] = float(cpi_m[k] / cpi_m[k - 12] - 1.0)
    return out


def forward_month_reading(fred: dict[str, pd.Series], cpi: dict[str, pd.Series], t: pd.Timestamp, month: str) -> dict:
    """DGS10 on t, and per CPI series the reading and r (None where undefined)."""
    y = fred["DGS10"].get(t, np.nan)
    out: dict = {"signal_date": str(t.date()), "DGS10": None if pd.isna(y) else float(y), "cpi": {}, "real_yield": {}}
    for s in CPI_IDS:
        reading = cpi_reading(cpi[s], month)
        out["cpi"][s] = reading
        out["real_yield"][s] = (None if reading["pi"] is None or out["DGS10"] is None
                                else float(out["DGS10"] / 100.0 - reading["pi"]))
    return out


def weights_at(episode_r: pd.DataFrame, fred: dict[str, pd.Series], cpi: dict[str, pd.Series],
               t: pd.Timestamp, month: str, earlier: list[dict] | None = None) -> dict:
    """The reading on t, n per series and the three weights (four decimals;
    None where r is undefined on t), from observations dated on or before t.
    ``earlier``: the earlier decision records (their real yields are reused)."""
    if pd.Period(month, "M") <= pd.Period(STARTING_MONTH, "M"):
        raise ValueError(f"{month} is not a forward month")
    fred = _cut(fred, t)
    first_new = (pd.Period(STARTING_MONTH, "M") + 1).strftime("%Y-%m")
    dates = signal_dates(fred["DGS10"], fred["DTB3"], first_new, month).dropna()
    if not len(dates) or dates.index[-1] != pd.Period(month, "M") or pd.Timestamp(dates.iloc[-1]) != t:
        raise ValueError(f"the last signal date is not t = {t.date()}")
    recorded = {r["signal_month"]: r for r in (earlier or []) if r.get("status") == "ok" and "real_yield" in r}
    notes: list[str] = []
    recomputed: dict[str, dict] = {}
    forward_r = {s: {} for s in CPI_IDS}
    for period, t_i in dates.iloc[:-1].items():
        key = str(period)
        if key in recorded:
            values = recorded[key]["real_yield"]
        else:
            recomputed[key] = forward_month_reading(fred, cpi, pd.Timestamp(t_i), key)
            values = recomputed[key]["real_yield"]
            notes.append(f"{key}: no ok record; its real yields computed from this fetch at its signal date "
                         f"{pd.Timestamp(t_i).date()}")
        for s in CPI_IDS:
            forward_r[s][key] = values[s]
    now = forward_month_reading(fred, cpi, t, month)
    for s in CPI_IDS:
        forward_r[s][month] = now["real_yield"][s]
    out = {**now, "n": {}, "weights": {k: None for k in TRIAL_IDS}, "rank_unrounded": {k: None for k in TRIAL_IDS},
           "forward_real_yields": {s: dict(v) for s, v in forward_r.items()},
           "recomputed_months": recomputed, "notes": notes}
    for s in CPI_IDS:
        extra = pd.Series([np.nan if v is None else v for v in forward_r[s].values()],
                          index=pd.PeriodIndex(list(forward_r[s]), freq="M"), dtype=float)
        history = pd.concat([episode_r[s].astype(float), extra])
        out["n"][s] = int(history.notna().sum())
        out[f"_history_{s}"] = history
        earlier_gaps = [m for m, v in list(forward_r[s].items())[:-1] if v is None]
        if earlier_gaps:
            notes.append(f"{s}: real yield undefined in {earlier_gaps}: left out of the rank history "
                         "(n counts defined real yields only)")
    for k in TRIAL_IDS:
        s = CPI_SERIES[k]
        if now["real_yield"][s] is None:
            notes.append(f"{k}: real yield undefined on t ({s} k = {now['cpi'][s]['k']} "
                         f"[{now['cpi'][s]['status_k']}], k - 12 = {now['cpi'][s]['k_minus_12']} "
                         f"[{now['cpi'][s]['status_k_minus_12']}]): holds its position (sections 6.1, 6.4, 16 (b))")
            continue
        w = rank_defined(out[f"_history_{s}"], RANK_KIND[k], RANK_N[k]).iloc[-1]
        if not pd.isna(w):
            out["rank_unrounded"][k] = float(w)
            out["weights"][k] = round(float(w), DECIMALS)
    for s in CPI_IDS:
        del out[f"_history_{s}"]
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


def decision_record(episode_r: pd.DataFrame, fred: dict[str, pd.Series], cpi: dict[str, pd.Series],
                    bars: dict[str, pd.Series], month: str, held: dict, start: dict, earlier: list[dict],
                    now_utc: str, input_sha256: dict | None = None, cpi_fetched_at: dict | None = None) -> dict | None:
    """The record for ``month``, or None when the run must wait (nothing is
    written).  ``earlier`` = the earlier records, in order."""
    earlier_ok = sum(r["status"] == "ok" for r in earlier)
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
    w = weights_at(episode_r, fred, cpi, t, month, earlier)
    late = sorted(s for s, at in (cpi_fetched_at or {}).items() if at and _utc(at).tz_localize(None).normalize() > t.normalize())
    if late:
        w["notes"].append(f"{late} fetched after the day of t (see cpi_fetched_at_utc): an index first released "
                          "between t and the fetch would be in the file; check the BLS release date of k")
    record = {**base, "status": "ok", "signal_date": str(t.date()), "execution_date": str(execution.date()),
              "days_slipped": int(slipped), "inputs_on_signal_date": inputs_at(fred, t),
              "cpi": w["cpi"], "real_yield": w["real_yield"], "rank_history_n": w["n"],
              "weights_after": dict(w["weights"]), "rank_unrounded": w["rank_unrounded"],
              "forward_real_yields_used": w["forward_real_yields"], "recomputed_months": w["recomputed_months"],
              "cpi_fetched_at_utc": dict(cpi_fetched_at or {}),
              "notes": " ".join(["T1 on trial (headline CPI, expanding rank); T1a (core CPI) and T1b (trailing "
                                 "120-month rank) its fragility companions. A weight of null means the trial "
                                 "holds its position (no trade). No order is placed for any of them."] + w["notes"])}
    if earlier_ok and earlier_ok % BLOCK_PERIODS == 0:
        record["scoring"] = {"block": earlier_ok // BLOCK_PERIODS, "periods": BLOCK_PERIODS,
                             "scoring_date": str(execution.date()),
                             "rule": "scored once, after this record's execution date ends the block (section 11.3)"}
    return record


# --- Shadow line --------------------------------------------------------------------------------------

def read_shadow(path: Path = SHADOW_CSV) -> pd.DataFrame:
    path = Path(path)
    return pd.read_csv(path) if path.exists() else pd.DataFrame(columns=SHADOW_COLUMNS)


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
           "scored_after": f"{BLOCK_PERIODS} holding periods", "periods_to_scoring": (-n) % BLOCK_PERIODS,
           "T1_turnover": float(shadow[f"traded_{PRIMARY}"].astype(float).sum()) if n else 0.0,
           "cumulative": {}, "mean_d": None}
    if n:
        out["mean_d"] = float(shadow["d"].astype(float).mean())
        out["cumulative"] = {s: float(np.prod(1.0 + shadow[s].astype(float).to_numpy()) - 1.0) for s in STRATEGIES}
    return out


def forward_verdict(d: pd.Series, t1_weights: pd.Series, t1_turnover: float) -> dict:
    """§11.4 (Study 007's rows) on one block of 60 periods.  ``t1_weights``:
    T1's targets as written in the records (holds left out), so a block in
    which the rule never set a varying weight is "not testable"."""
    w = t1_weights.dropna().astype(float).to_numpy()
    if len(w) == 0 or float(np.std(w)) == 0.0:
        row, nw = VERDICT_NOT_TESTABLE, None
    else:
        nw = stats.newey_west_mean(d)
        if nw["mean"] > 0 and nw["t"] >= T_BAR:
            row = VERDICT_SUPPORTED
        elif nw["t"] <= -T_BAR:
            row = VERDICT_REFUTED
        else:
            row = VERDICT_INCONCLUSIVE
    labels = ["low-powered"] if t1_turnover < LOW_POWERED_TURNOVER_008 else []
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
    targets = pd.Series([r["weights_after"][PRIMARY] for r in ok[end - BLOCK_PERIODS:end]], dtype=float)
    out = forward_verdict(rows["d"].astype(float).reset_index(drop=True), targets,
                          float(rows[f"traded_{PRIMARY}"].astype(float).sum()))
    out.update(block=block, periods=BLOCK_PERIODS, scoring_date=ok[end]["scoring"]["scoring_date"],
               history_verdict=HISTORY_VERDICT)
    return out


# --- Inputs ---------------------------------------------------------------------------------------------

def fetch_inputs(raw_dir: Path = FORWARD_RAW_DIR, manifest: Path = FORWARD_MANIFEST) -> None:
    for name in (*FRED_IDS, *CPI_IDS):
        fetch_series(name, raw_dir, manifest)
    for leg in (DURATION_LEG, CASH_LEG):
        fetch_bars(leg, FORWARD_BARS_START, None, raw_dir, manifest)


def load_inputs(raw_dir: Path = FORWARD_RAW_DIR) -> tuple[dict, dict, dict]:
    fred = {name: load_series(name, raw_dir) for name in FRED_IDS}
    cpi = {name: load_series(name, raw_dir).rename(name) for name in CPI_IDS}
    bars = {leg: load_bars(leg, raw_dir)["close"].astype(float) for leg in (DURATION_LEG, CASH_LEG)}
    return fred, cpi, bars


def load_episode_real_yields(raw_dir: Path = RAW_DIR, availability_path: Path = CPI_AVAILABILITY_PATH) -> pd.DataFrame:
    frozen = {name: load_series(name, raw_dir) for name in FRED_IDS}
    frozen_cpi = {name: load_series(name, raw_dir) for name in CPI_IDS}
    availability = pd.read_csv(availability_path, dtype=str, keep_default_na=False)
    return episode_real_yields(frozen, frozen_cpi, availability)


# --- Entry point ------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Study 008 forward record (section 11). No paper order.")
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
    records = load_records(DECISIONS_DIR)
    start = starting_weights()
    if args.step == "decide":
        if any(r["signal_month"] == args.signal_month for r in records):
            print(f"refused: a record for {args.signal_month} exists")
            return 1
        if args.fetch and not args.dry_run:
            fetch_inputs(FORWARD_RAW_DIR, FORWARD_MANIFEST)
        elif args.fetch:
            print("note: --dry-run does not fetch; paper-log/raw/ is read as it is")
        try:
            fred, cpi, bars = load_inputs(FORWARD_RAW_DIR)
        except FileNotFoundError as missing:
            print(f"refused: an input is not in paper-log/raw/ ({Path(missing.filename).name}); run with --fetch")
            return 1
        manifest = json.loads(FORWARD_MANIFEST.read_text(encoding="utf-8")) if FORWARD_MANIFEST.exists() else {}
        fetched_at = {s: manifest.get(f"fred_{s}.csv", {}).get("downloaded_at_utc") for s in CPI_IDS}
        episode_r = load_episode_real_yields()
        held = weights_before(records, start)
        hashes = {**file_hashes(FORWARD_RAW_DIR, "fred_"), **file_hashes(FORWARD_RAW_DIR, "alpaca_"),
                  **{f"frozen/{k}": v for k, v in file_hashes(RAW_DIR, "fred_").items()},
                  "frozen/results/cpi_availability.csv": sha256_of(CPI_AVAILABILITY_PATH),
                  "frozen/results/episode/summary.json": sha256_of(EPISODE_DIR / "summary.json")}
        record = decision_record(episode_r, fred, cpi, bars, args.signal_month, held, start, records, now, hashes,
                                 fetched_at)
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
        fetch_inputs(FORWARD_RAW_DIR, FORWARD_MANIFEST)
    indices = {leg: total_return_index(load_bars(leg, FORWARD_RAW_DIR)) for leg in (DURATION_LEG, CASH_LEG)}
    line = shadow_line(indices, upto, read_shadow(SHADOW_CSV), start, frozen_weights(), now_utc=now)
    print(json.dumps(line, indent=2, default=str))
    if not args.dry_run:
        print(f"appended: {append_shadow(line, SHADOW_CSV).relative_to(STUDY_DIR)}")
        INTERIM_JSON.write_text(json.dumps(interim(read_shadow(SHADOW_CSV), now), indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
