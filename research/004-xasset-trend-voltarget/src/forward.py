"""The forward shadow record (§11): the month-end decision record and the
monthly shadow line.  No paper order is placed by anything here (§11, §12).

Decision record (§11.1).  On the last NYSE trading day of a month, after the
close, ``python -m src.forward decide --signal-date t [--fetch]`` fetches
Alpaca ``adjustment='all'`` daily bars for the ten universe instruments
(the universe left by §5.3.5, read from ``results/checks/``, never from
here), the cash ETF and SPY (reference only, never held) into
``paper-log/raw/`` (git-ignored; its own manifest, so the study's
``data/raw/`` hashes stay frozen), confirms the bar for ``t`` is present,
and computes with the library functions the backtest called: the 12-month
excess momentum (``sizing.excess_momentum``), the long/flat signal, the
63-day volatility (``sizing.realised_vol``) and the capped
inverse-volatility weights (``sizing.target_weights``) of T1; B3's
always-on weights from the same volatilities; B4 = B3 × k with k frozen
from the in-sample run.  One JSON file per signal date with every input
value, the input hashes and the UTC time written; never rewritten.  Only
observations on or before ``t`` are used.  An instrument without a bar at
``t`` is logged as "signal unavailable" and its previous weight is carried
(§11.1); the record's status says so.

Shadow line (§11.2).  ``python -m src.forward shadow --signal-date t``
appends to ``paper-log/shadow.csv`` the holding period that *ended* at
``t``'s execution date: the net return, cost and turnover of the T1, B3
and B4 books in the engine's conventions (``period_step`` mirrors one
period of ``qune_research.engine.run`` and is tested against it), the
three book values (each a notional 10,000 USD book that starts all cash
at the first execution date, the initial purchase charged like any trade),
and the period returns of SPY, IEF and the cash ETF from the same closes.
The books' drifted weights are written to ``paper-log/books/<period_end>.json``
so that the next line charges the cost of the trade from the drifted
weights, as the engine does.  A line is appended once per period, in
order; a period whose end bar is not yet on disk is refused.

Gates: no record before ``FORWARD_FIRST_SIGNAL_DATE`` (the first month-end
after the note's publication), none before 21:15 UTC on the signal date
(after the New York close under EDT or EST), none on a date that is not
the last NYSE trading day of its month, none without the cash ETF's bar
for ``t``.  A refused run writes nothing and exits 1.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from qune_research import data as lib
from qune_research.nyse import nyse_trading_days
from qune_research.sizing import excess_momentum, realised_vol, target_weights

from .config import (
    CASH_ETF,
    COST_BP_BASE,
    FORWARD_BOOK_USD,
    FORWARD_BOOKS_DIR,
    FORWARD_DECISIONS_DIR,
    FORWARD_EARLIEST_UTC,
    FORWARD_FIRST_SIGNAL_DATE,
    FORWARD_LABEL,
    FORWARD_MANIFEST,
    FORWARD_RAW_DIR,
    FORWARD_SHADOW_CSV,
    LOOKBACKS_MONTHS,
    RESULTS_DIR,
    SIGMA_TARGET,
    STUDY_DIR,
    VOL_WINDOW_DAYS,
    WEIGHT_CAP,
)
from .run import universe_from_checks

STRATEGY_IDS = ("T1", "B3", "B4")                # T1 on record; B3 always-on vol-scaled; B4 = B3 × k (§9.1)
REFERENCE_SYMBOL = "SPY"                         # §9.6 reference; never held (excluded under branch X, §16)
LOOKBACK = LOOKBACKS_MONTHS["T1"][0]
SHADOW_COLUMNS = ["signal_date", "execution_date", "period_start_bar", "period_end", "period_end_bar",
                  "days_slipped_start", "days_slipped_end",
                  "T1_net", "B3_net", "B4_net", "T1_cost", "B3_cost", "B4_cost",
                  "T1_turnover", "B3_turnover", "B4_turnover", "T1_gross_exposure", "B3_gross_exposure",
                  "B4_gross_exposure", "T1_assets_on", "T1_book", "B3_book", "B4_book",
                  "r_SPY", "r_IEF", "r_BIL", "cost_multiple", "run_at_utc"]


# --- Gates ----------------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def earliest_run_utc(signal_date) -> pd.Timestamp:
    """21:15 UTC on the signal date (after the 16:00 New York close under
    EDT or EST)."""
    hour, minute = FORWARD_EARLIEST_UTC
    return pd.Timestamp(signal_date).normalize().tz_localize("UTC") + pd.Timedelta(hours=hour, minutes=minute)


def refusal(signal_date, run_at_utc: str, first_signal_date: str = FORWARD_FIRST_SIGNAL_DATE) -> str | None:
    """Why a run must not write anything, or None if it may."""
    t = pd.Timestamp(signal_date).normalize()
    if t < pd.Timestamp(first_signal_date):
        return (f"{t.date()} is before the first forward signal date {first_signal_date} (section 11); "
                f"the history is spent and no earlier month may be recorded")
    now = pd.Timestamp(run_at_utc)
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    if now < earliest_run_utc(t):
        return (f"it is {now.strftime('%Y-%m-%dT%H:%M:%SZ')}, before {earliest_run_utc(t).strftime('%H:%M')} UTC on the "
                f"signal date; a daily bar fetched during the session is the partial day (section 16)")
    return None


def _month_end_refusal(t: pd.Timestamp, trading_days: pd.DatetimeIndex) -> str | None:
    month_last_day = t.to_period("M").to_timestamp(how="end").normalize()
    later = trading_days[(trading_days > t) & (trading_days <= month_last_day)]
    if len(later):
        return (f"{t.date()} is not the last NYSE trading day of its month ({later[-1].date()} is); "
                f"no signal on other days (section 6.3)")
    return None


def _execution_date(t: pd.Timestamp, trading_days: pd.DatetimeIndex) -> pd.Timestamp:
    later = trading_days[trading_days > t]
    if not len(later):
        raise ValueError("no NYSE trading day after the signal date in the calendar window")
    return later[0]


# --- Decision record (§11.1) -------------------------------------------------------------------

def frozen_k(insample_summary: Path = RESULTS_DIR / "insample" / "summary.json") -> float:
    """k for B4, frozen by the in-sample run (§9.1); read, never recomputed."""
    return float(json.loads(Path(insample_summary).read_text(encoding="utf-8"))["k_exposure_ratio_frozen"])


def decision_record(closes: dict[str, pd.Series], signal_date, universe: list[str], k: float, holding_before: dict,
                    run_at_utc: str | None = None, trading_days: pd.DatetimeIndex | None = None,
                    input_sha256: dict[str, str] | None = None) -> dict:
    """The §11.1 record for ``signal_date`` from the close series
    (``adjustment='all'``; a ratio-only input, so the scale of each series
    does not matter).  Only observations on or before the signal date are
    used; later ones in the inputs are ignored.  ``holding_before`` maps
    each strategy to its previous target weights (carried for an instrument
    whose bar is missing)."""
    t = pd.Timestamp(signal_date).normalize()
    if trading_days is None:
        trading_days = nyse_trading_days(t - pd.Timedelta(days=5), t + pd.Timedelta(days=45))
    base = {"study": "004-xasset-trend-voltarget", "label": FORWARD_LABEL, "signal_date": str(t.date()),
            "run_at_utc": run_at_utc or utc_now(), "universe": list(universe), "k_exposure_ratio_frozen": k,
            "holding_before": {name: dict(holding_before.get(name) or {}) for name in STRATEGY_IDS},
            "input_sha256": dict(input_sha256 or {}), "orders": [], "paper_order": False,
            "reference_symbol_held": False}
    unavailable = {**base, "status": "signal unavailable", "execution_date": None, "targets": None}
    why = _month_end_refusal(t, trading_days)
    if why:
        return {**unavailable, "notes": why}
    cash = closes[CASH_ETF].astype(float).dropna().sort_index()
    cash = cash.loc[cash.index <= t]
    if cash.empty or cash.index[-1] != t:
        last = str(cash.index[-1].date()) if not cash.empty else None
        return {**unavailable, "notes": f"no {CASH_ETF} bar for the signal date (last bar {last}); every signal needs "
                                        f"the cash index at t (section 6.1); re-check on the next run, never fill"}
    assets: dict[str, dict] = {}
    signals: dict[str, float] = {}
    vols: dict[str, float] = {}
    carried: list[str] = []
    for a in universe:
        series = closes[a].astype(float).dropna().sort_index()
        series = series.loc[series.index <= t]
        row: dict = {"status": "ok"}
        if series.empty or series.index[-1] != t:
            row = {"status": "signal unavailable",
                   "notes": f"no bar for the signal date (last bar {str(series.index[-1].date()) if not series.empty else None}); "
                            f"previous weight carried (section 11.1)"}
        else:
            mom = excess_momentum(series, cash, t, LOOKBACK)
            vol = realised_vol(series, t, VOL_WINDOW_DAYS)
            if mom is None or vol is None:
                row = {"status": "signal unavailable",
                       "notes": f"the {LOOKBACK}-month lookback bar or the {VOL_WINDOW_DAYS} return days are not covered by "
                                f"the bars; previous weight carried (section 11.1)"}
            else:
                t_l = series.index[series.index <= (t.to_period("M") - LOOKBACK).to_timestamp(how="end").normalize()][-1]
                row.update({"close_t": float(series.iloc[-1]), "close_t12": float(series.loc[t_l]),
                            "t12_date": str(t_l.date()), "cash_t": float(cash.iloc[-1]),
                            "cash_t12": float(cash.reindex([t_l], method="ffill").iloc[0]),
                            "mom12": mom, "s12": 1.0 if mom > 0 else 0.0, "vol63_annualised": vol})
                signals[a], vols[a] = row["s12"], vol
        if row["status"] != "ok":
            carried.append(a)
        assets[a] = row
    targets = {"T1": target_weights(signals, vols, SIGMA_TARGET, WEIGHT_CAP),
               "B3": target_weights({a: 1.0 for a in signals}, vols, SIGMA_TARGET, WEIGHT_CAP)}
    targets["B4"] = {a: w * k for a, w in targets["B3"].items()}
    for name in STRATEGY_IDS:
        for a in carried:
            targets[name][a] = float((holding_before.get(name) or {}).get(a, 0.0))
        total = sum(targets[name].values())
        if total > 1.0:                                  # §6.2 scale-down applies to the carried book as well
            targets[name] = {a: w / total for a, w in targets[name].items()}
        targets[name] = {a: float(targets[name].get(a, 0.0)) for a in universe}
    exposure = {name: float(sum(targets[name].values())) for name in STRATEGY_IDS}
    turnover = {name: (float(sum(abs(targets[name][a] - float(holding_before[name].get(a, 0.0))) for a in universe))
                       if holding_before.get(name) else None) for name in STRATEGY_IDS}
    execution = _execution_date(t, trading_days)
    status = "ok" if not carried else "ok, weights carried for: " + ", ".join(carried)
    return {**base, "status": status, "execution_date": str(execution.date()), "assets": assets,
            "n_assets_signalled": len(signals), "carried": carried, "targets": targets,
            "gross_exposure": exposure, "cash_weight": {name: 1.0 - exposure[name] for name in STRATEGY_IDS},
            "assets_on_T1": sorted(a for a, w in targets["T1"].items() if w > 0),
            "turnover_vs_holding_before": turnover,
            "notes": "T1 = long/flat 12-month excess momentum with capped inverse-volatility sizing (section 6); "
                     "B3 = the same sizing always on; B4 = B3 scaled by the frozen k. No order is placed for any of them. "
                     "The weights take effect at the execution date's close and are marked by the shadow line."}


def load_records(decisions_dir: Path = FORWARD_DECISIONS_DIR, before=None) -> list[dict]:
    directory = Path(decisions_dir)
    if not directory.exists():
        return []
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))]
    if before is not None:
        limit = str(pd.Timestamp(before).date())
        records = [r for r in records if r["signal_date"] < limit]
    return records


def _ok(record: dict) -> bool:
    return str(record["status"]).startswith("ok")


def terminal_targets(universe: list[str], k: float, oos_dir: Path = RESULTS_DIR / "oos") -> dict:
    """The held-back window's terminal position: the weights the 2026-09-30
    signal set, from the committed signal and volatility files (§16 end-bar
    amendment: computed and published, starts no period)."""
    n = len(universe)
    s12 = pd.read_csv(oos_dir / f"signal_s12_{n}assets.csv", index_col=0).iloc[-1]
    vol = pd.read_csv(oos_dir / f"signal_vol_{n}assets.csv", index_col=0).iloc[-1]
    signals = {a: float(s12[a]) for a in universe}
    vols = {a: float(vol[a]) for a in universe}
    t1 = target_weights(signals, vols, SIGMA_TARGET, WEIGHT_CAP)
    b3 = target_weights({a: 1.0 for a in universe}, vols, SIGMA_TARGET, WEIGHT_CAP)
    out = {"T1": {a: float(t1.get(a, 0.0)) for a in universe}, "B3": {a: float(b3.get(a, 0.0)) for a in universe}}
    out["B4"] = {a: w * k for a, w in out["B3"].items()}
    return out, f"terminal position of the held-back window (signal date {s12.name})"


def previous_targets(universe: list[str], k: float, decisions_dir: Path = FORWARD_DECISIONS_DIR,
                     oos_dir: Path = RESULTS_DIR / "oos", before=None) -> tuple[dict, str]:
    """The holdings before a signal date: the targets of the latest earlier
    ok record, else the held-back window's terminal position."""
    ok = [r for r in load_records(decisions_dir, before=before) if _ok(r)]
    if ok:
        last = max(ok, key=lambda r: r["signal_date"])
        return {name: dict(last["targets"][name]) for name in STRATEGY_IDS}, f"decision record {last['signal_date']}"
    return terminal_targets(universe, k, oos_dir)


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

def period_step(target: dict[str, float], drifted: dict[str, float], asset_r: dict[str, float], cash_r: float,
                costs: dict[str, float]) -> dict:
    """One holding period in ``qune_research.engine.run``'s arithmetic: the
    trade from the drifted weights to the targets at the period's first
    close (cost Σ|Δw|·c on the pre-trade value), the gross return at the
    targets with the remainder in cash, the net return, and the weights
    drifted to the period's last close."""
    assets = list(target)
    turnover = sum(abs(target[a] - drifted.get(a, 0.0)) for a in assets)
    cost = sum(abs(target[a] - drifted.get(a, 0.0)) * costs[a] for a in assets)
    gross_exposure = sum(target.values())
    if gross_exposure > 1.0 + 1e-12:
        raise ValueError("weights sum to more than one (no leverage, section 6.2)")
    gross = sum(target[a] * asset_r[a] for a in assets if target[a] != 0.0) + (1.0 - gross_exposure) * cash_r
    net = (1.0 - cost) * (1.0 + gross) - 1.0
    new_drifted = {a: (target[a] * (1.0 + asset_r[a]) / (1.0 + gross) if target[a] != 0.0 else 0.0) for a in assets}
    return {"gross": gross, "cost": cost, "net": net, "gross_exposure": gross_exposure, "turnover": turnover,
            "drifted": new_drifted}


def _first_bar_on_or_after(bars: pd.DatetimeIndex, day: pd.Timestamp) -> pd.Timestamp | None:
    later = bars[bars >= day]
    return later[0] if len(later) else None


def initial_books(universe: list[str], book_usd: float = FORWARD_BOOK_USD) -> dict:
    """All three books start all cash at the first execution date (§11.1)."""
    return {"period_end": None, "books": {name: {"value": book_usd, "drifted_weights": {a: 0.0 for a in universe}}
                                          for name in STRATEGY_IDS}}


def shadow_line(closes: dict[str, pd.Series], previous: dict, current: dict, books_before: dict,
                cost_multiple: float = 1.0, run_at_utc: str | None = None,
                cost_bp: dict[str, float] | None = None) -> tuple[dict, dict]:
    """The §11.2 line for the holding period from ``previous``'s execution
    date to ``current``'s, and the books after it.  The period runs between
    the first bar on or after each execution date that every instrument and
    the cash ETF have (a missing execution bar moves the trade to the next
    bar, slippage recorded; §6.4)."""
    if not (_ok(previous) and _ok(current)):
        raise ValueError("both decision records must have an ok status")
    universe = list(previous["universe"])
    if books_before["period_end"] is not None and books_before["period_end"] != previous["execution_date"]:
        raise ValueError(f"the books on disk end at {books_before['period_end']}, not at the period's start "
                         f"{previous['execution_date']}; periods are recorded in order")
    series = {name: closes[name].astype(float).dropna().sort_index() for name in (*universe, CASH_ETF, REFERENCE_SYMBOL)}
    common = series[universe[0]].index
    for name in (*universe[1:], CASH_ETF):
        common = common.intersection(series[name].index)
    common = common.sort_values()
    start, end = pd.Timestamp(previous["execution_date"]), pd.Timestamp(current["execution_date"])
    if end <= start:
        raise ValueError("the current record's execution date must follow the previous record's")
    start_bar, end_bar = _first_bar_on_or_after(common, start), _first_bar_on_or_after(common, end)
    if start_bar is None or end_bar is None:
        missing = start.date() if start_bar is None else end.date()
        raise ValueError(f"no common bar on or after {missing}; the line is written after the execution date's "
                         f"close, never before")
    if end_bar <= start_bar:
        raise ValueError("the period's end bar does not follow its start bar")
    r = {name: float(series[name].loc[end_bar] / series[name].loc[start_bar] - 1.0) for name in series
         if start_bar in series[name].index and end_bar in series[name].index}
    table = COST_BP_BASE if cost_bp is None else cost_bp          # the pre-registered table unless a test supplies its own
    costs = {a: table[a] * 1e-4 * cost_multiple for a in universe}
    line = {"signal_date": previous["signal_date"], "execution_date": previous["execution_date"],
            "period_start_bar": str(start_bar.date()), "period_end": current["execution_date"],
            "period_end_bar": str(end_bar.date()),
            "days_slipped_start": int(len(common[(common >= start) & (common < start_bar)])),
            "days_slipped_end": int(len(common[(common >= end) & (common < end_bar)]))}
    books_after = {"period_end": current["execution_date"], "period_end_bar": str(end_bar.date()), "books": {}}
    for name in STRATEGY_IDS:
        target = {a: float(previous["targets"][name].get(a, 0.0)) for a in universe}
        before = books_before["books"][name]
        step = period_step(target, before["drifted_weights"], {a: r[a] for a in universe}, r[CASH_ETF], costs)
        value = float(before["value"]) * (1.0 + step["net"])
        line[f"{name}_net"], line[f"{name}_cost"], line[f"{name}_turnover"] = step["net"], step["cost"], step["turnover"]
        line[f"{name}_gross_exposure"], line[f"{name}_book"] = step["gross_exposure"], value
        books_after["books"][name] = {"value": value, "drifted_weights": step["drifted"], "target_weights": target,
                                      "net": step["net"], "cost": step["cost"]}
    line["T1_assets_on"] = int(sum(1 for a in universe if float(previous["targets"]["T1"].get(a, 0.0)) > 0))
    line["r_SPY"] = r.get(REFERENCE_SYMBOL, float("nan"))
    line["r_IEF"], line["r_BIL"] = r.get("IEF", float("nan")), r[CASH_ETF]
    line["cost_multiple"], line["run_at_utc"] = cost_multiple, run_at_utc or utc_now()
    return {column: line[column] for column in SHADOW_COLUMNS}, books_after


def read_shadow(path: Path = FORWARD_SHADOW_CSV) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=SHADOW_COLUMNS)
    return pd.read_csv(path)


def append_shadow(line: dict, path: Path = FORWARD_SHADOW_CSV) -> Path:
    """Append one line; refuses a second line for the same period and a
    period that does not follow the last one (a period is recorded once and
    a missed month is logged, never skipped silently)."""
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


def latest_books(universe: list[str], books_dir: Path = FORWARD_BOOKS_DIR) -> dict:
    directory = Path(books_dir)
    files = sorted(directory.glob("*.json")) if directory.exists() else []
    if not files:
        return initial_books(universe)
    return json.loads(files[-1].read_text(encoding="utf-8"))


def write_books(books: dict, books_dir: Path = FORWARD_BOOKS_DIR) -> Path:
    directory = Path(books_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{books['period_end']}.json"
    if path.exists():
        raise FileExistsError(f"{path} exists: the books of a period are written once")
    path.write_text(json.dumps(books, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


# --- Inputs: fetch and load (paper-log/raw/, own manifest) -----------------------------------------

def forward_symbols(universe: list[str]) -> tuple[str, ...]:
    return (*universe, CASH_ETF, REFERENCE_SYMBOL)


def fetch_inputs(universe: list[str], raw_dir: Path = FORWARD_RAW_DIR, manifest_path: Path = FORWARD_MANIFEST,
                 session=None) -> None:
    """Fresh ``adjustment='all'`` bars for the universe, the cash ETF and
    SPY from ``FORWARD_BARS_START`` to now; credentials from the environment."""
    from .config import FORWARD_BARS_START
    for symbol in forward_symbols(universe):
        lib.fetch_alpaca(symbol, FORWARD_BARS_START, None, raw_dir, manifest_path, session)


def load_inputs(universe: list[str], raw_dir: Path = FORWARD_RAW_DIR,
                manifest_path: Path = FORWARD_MANIFEST) -> tuple[dict, dict]:
    closes = {s: lib.load_alpaca(s, raw_dir)["close"].astype(float).dropna() for s in forward_symbols(universe)}
    manifest = lib.read_manifest(manifest_path)
    hashes = {name: entry["sha256"] for name, entry in manifest.items() if "sha256" in entry}
    return closes, hashes


# --- Entry point ----------------------------------------------------------------------------------

def _check_only_historical(signal_date: str) -> int:
    """CHECK ONLY: a record for a signal date inside the held-back window from
    the study's frozen vendor files, printed next to the committed weights of
    that signal date; nothing written."""
    from .run import load_prices, vendor_tri
    print("CHECK ONLY: not a forward record; nothing is written (section 14 step 11 check against the committed files)")
    universe = universe_from_checks()
    prices = load_prices(universe)
    closes = {a: prices[a] for a in universe}
    closes[CASH_ETF] = vendor_tri(CASH_ETF)
    closes[REFERENCE_SYMBOL] = vendor_tri(REFERENCE_SYMBOL)
    k = frozen_k()
    record = decision_record(closes, signal_date, universe, k, {}, utc_now())
    record["label"] = "CHECK ONLY, not a forward record, not written"
    print(json.dumps(record, indent=2, sort_keys=True))
    if not _ok(record):
        return 1
    periods = pd.read_csv(RESULTS_DIR / "oos" / f"t1_periods_{len(universe)}assets_base.csv", index_col=0)
    s12 = pd.read_csv(RESULTS_DIR / "oos" / f"signal_s12_{len(universe)}assets.csv", index_col=0)
    vol = pd.read_csv(RESULTS_DIR / "oos" / f"signal_vol_{len(universe)}assets.csv", index_col=0)
    day = record["signal_date"]
    worst = 0.0
    for a in universe:
        worst = max(worst, abs(record["assets"][a]["s12"] - float(s12.loc[day, a])),
                    abs(record["assets"][a]["vol63_annualised"] - float(vol.loc[day, a])))
        if day in periods.index:
            worst = max(worst, abs(record["targets"]["T1"][a] - float(periods.loc[day, f"w_{a}"])))
    print(f"largest absolute difference against the committed signal, volatility and T1 weight files for {day}: {worst:.3e}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Study 004 forward shadow record (section 11). No paper order.")
    parser.add_argument("step", choices=("decide", "shadow"))
    parser.add_argument("--signal-date", required=True, help="YYYY-MM-DD, the last NYSE trading day of the month")
    parser.add_argument("--fetch", action="store_true", help="fetch fresh bars into paper-log/raw/ first")
    parser.add_argument("--dry-run", action="store_true", help="print, write nothing")
    parser.add_argument("--check-only-historical", action="store_true",
                        help="CHECK ONLY: compute a record for a date inside the held-back window from the study's "
                             "frozen data/raw files, print it next to the committed weights, write nothing")
    args = parser.parse_args(argv)
    now = utc_now()
    if args.check_only_historical:
        return _check_only_historical(args.signal_date)
    why = refusal(args.signal_date, now)
    if why:
        print(f"refused: {why}")
        return 1
    universe = universe_from_checks()
    k = frozen_k()
    if args.fetch and not args.dry_run:
        fetch_inputs(universe)
    closes, hashes = load_inputs(universe)
    if args.step == "decide":
        holding_before, source = previous_targets(universe, k, before=args.signal_date)
        record = decision_record(closes, args.signal_date, universe, k, holding_before, now, input_sha256=hashes)
        record["holding_before_source"] = source
        print(json.dumps(record, indent=2, sort_keys=True))
        if not args.dry_run:
            print(f"written: {write_record(record).relative_to(STUDY_DIR)}")
        return 0 if _ok(record) else 1
    records = {r["signal_date"]: r for r in load_records()}
    current = records.get(str(pd.Timestamp(args.signal_date).date()))
    if current is None or not _ok(current):
        print(f"refused: no ok decision record for {args.signal_date}; run decide first")
        return 1
    earlier = [r for r in records.values() if _ok(r) and r["signal_date"] < current["signal_date"]]
    if not earlier:
        print("refused: no earlier decision record; the first forward period starts at the first record's execution "
              "date and its line is written after the second record (section 11.2)")
        return 1
    previous = max(earlier, key=lambda r: r["signal_date"])
    line, books = shadow_line(closes, previous, current, latest_books(universe), run_at_utc=now)
    print(json.dumps(line, indent=2, default=str))
    if not args.dry_run:
        print(f"appended: {append_shadow(line).relative_to(STUDY_DIR)}")
        print(f"written: {write_books(books).relative_to(STUDY_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
