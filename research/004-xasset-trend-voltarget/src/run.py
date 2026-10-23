"""In-sample and out-of-sample runs (§8, §9): T1–T4 and B0–B4 on the universe
left by the data checks, base and stress costs, every §9.3 metric, the §9.5
criteria and every §9.6 descriptive, written to ``results/``.

``python -m src.run --insample`` writes ``results/insample/`` and freezes k
(§9.1 B4); ``python -m src.run --oos`` reads k, runs the held-back window once
on the same vendor series with actual BIL as cash and writes ``results/oos/``.
Both are invoked only through ``reproduce.sh`` after approval.

The engine, signals, sizing and statistics come from the shared library
``qune_research``; the metric, inference, deflation, criteria and verdict
functions follow Study 003's frozen ``report.py`` by attribution, generalised
from one instrument to a weight vector.  The universe is read from
``results/checks/data_checks.json`` (the §5.3.5 evaluation), never from this
module: an excluded symbol cannot be re-admitted here.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from qune_research import engine, stats
from qune_research.dates import month_end_signal_dates
from qune_research.dates import schedule as build_schedule
from qune_research.sizing import realised_vol, target_weights, trend_signal

from . import data
from .cash import cash_index
from .config import (
    B2_WEIGHTS,
    C1_SHARPE_MARGIN,
    C2_T_MIN,
    C3_DSR_MIN,
    CASH_ETF,
    CHECKS_DIR,
    COST_BP_BASE,
    COST_MULTIPLES_BREAKEVEN,
    COST_STRESS_MULTIPLE,
    CRISIS_WINDOWS,
    INSAMPLE_FIRST_SIGNAL_DATE,
    INSAMPLE_LAST_SIGNAL_MONTH,
    LOOKBACKS_MONTHS,
    MANIFEST_PATH,
    N_TRIALS_REGISTERED,
    N_TRIALS_SENSITIVITY,
    NOT_SUPPORTED_T_MAX,
    OOS_FIRST_SIGNAL_MONTH,
    OOS_LAST_SIGNAL_MONTH,
    POWER_MIN_SWITCHES,
    REFERENCE_SYMBOLS,
    RESULTS_DIR,
    SEED,
    SIGMA_TARGET,
    STUDY_DIR,
    SUBPERIODS,
    TRIAL_IDS,
    VOL_EXCEEDANCE_FACTOR,
    VOL_REALISED_WINDOW_MONTHS,
    VOL_WINDOW_DAYS,
    WEIGHT_CAP,
)

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (backend must be chosen first)

BENCHMARK_IDS = ("B0", "B1", "B2", "B3", "B4")
COST_CASES = {"base": 1.0, "stress": COST_STRESS_MULTIPLE}


# --- Inputs ------------------------------------------------------------------------------

def universe_from_checks(checks_dir: Path = CHECKS_DIR) -> list[str]:
    """The instruments left by §5.3.5, in the pre-registered order."""
    report = json.loads((checks_dir / "data_checks.json").read_text(encoding="utf-8"))
    ev = report["evaluation"]
    if ev["halt"]:
        raise SystemExit("the data checks halted the study (§5.3.5); no rule may run")
    return list(ev["universe"])


def vendor_tri(symbol: str) -> pd.Series:
    """The vendor's adjusted close rebased to 1.0 at its first bar (§5.1)."""
    close = data.vendor_frame(symbol)["adjClose"].astype(float).dropna()
    return (close / close.iloc[0]).rename(symbol)


def load_prices(symbols: list[str]) -> pd.DataFrame:
    return pd.concat([vendor_tri(s) for s in symbols], axis=1).sort_index()


def costs_for(symbols: list[str], multiple: float, cost_bp: dict[str, float] | None = None) -> dict[str, float]:
    """Per-asset one-way cost as a fraction (§9.2), ``multiple`` × base; the
    table is the pre-registered one unless a test supplies its own."""
    table = COST_BP_BASE if cost_bp is None else cost_bp
    return {s: table[s] * 1e-4 * multiple for s in symbols}


# --- Signals and weights (§6) ----------------------------------------------------------------

def signal_table(prices: pd.DataFrame, cash_tri: pd.Series, universe: list[str],
                 signal_dates: pd.DatetimeIndex) -> dict[str, pd.DataFrame]:
    """Per signal date and asset: the three raw signals, the volatility and
    presence (§8.1: a 12-month lookback bar and 63 days of returns).  Keys:
    ``s12``, ``s6``, ``s3``, ``vol``, ``present``.  Absent assets are NaN."""
    out = {k: pd.DataFrame(index=signal_dates, columns=universe, dtype=float) for k in ("s12", "s6", "s3", "vol")}
    for t in signal_dates:
        for a in universe:
            s12 = trend_signal(prices[a], cash_tri, t, 12)
            vol = realised_vol(prices[a], t, VOL_WINDOW_DAYS)
            if s12 is None or vol is None:
                continue                      # not entered (§8.1): absent, not flat
            out["s12"].at[t, a], out["vol"].at[t, a] = s12, vol
            out["s6"].at[t, a] = trend_signal(prices[a], cash_tri, t, 6)
            out["s3"].at[t, a] = trend_signal(prices[a], cash_tri, t, 3)
    out["present"] = out["s12"].notna()
    return out


def trial_signal(table: dict[str, pd.DataFrame], trial: str) -> pd.DataFrame:
    """The trial's s_i,t (§7): one lookback, or the mean of the three (T4)."""
    cols = [f"s{L}" for L in LOOKBACKS_MONTHS[trial]]
    s = sum(table[c] for c in cols) / len(cols)
    return s.where(table["present"])


def weights_from(signal: pd.DataFrame, vol: pd.DataFrame) -> dict[pd.Timestamp, dict[str, float]]:
    """§6.2 weights per signal date from a signal frame (NaN = absent)."""
    out = {}
    for t in signal.index:
        row, v = signal.loc[t], vol.loc[t]
        present = [a for a in signal.columns if not np.isnan(row[a])]
        out[t] = target_weights({a: float(row[a]) for a in present}, {a: float(v[a]) for a in present},
                                SIGMA_TARGET, WEIGHT_CAP)
    return out


def equal_weights(present: pd.DataFrame) -> dict[pd.Timestamp, dict[str, float]]:
    out = {}
    for t in present.index:
        assets = [a for a in present.columns if present.at[t, a]]
        out[t] = {a: 1.0 / len(assets) for a in assets} if assets else {}
    return out


def fixed_weights(signal_dates: pd.DatetimeIndex, w: dict[str, float]) -> dict[pd.Timestamp, dict[str, float]]:
    return {t: dict(w) for t in signal_dates}


def scaled(weights: dict[pd.Timestamp, dict[str, float]], k: float) -> dict[pd.Timestamp, dict[str, float]]:
    return {t: {a: v * k for a, v in w.items()} for t, w in weights.items()}


# --- Daily index and period returns ------------------------------------------------------

def period_asset_returns(prices: pd.DataFrame, cash_tri: pd.Series, sched: pd.DataFrame) -> pd.DataFrame:
    """Holding-period simple return of every column (and ``cash``) from the
    close of the execution date to the close of the period end; NaN before an
    asset's first bar."""
    periods = sched.iloc[:-1]
    rows = {}
    full = pd.concat([prices, cash_tri.rename("cash")], axis=1).sort_index().ffill()
    for _, row in periods.iterrows():
        start = full.reindex([row["execution_date"]], method="ffill").iloc[0]
        end = full.reindex([row["period_end"]], method="ffill").iloc[0]
        rows[row["signal_date"]] = end / start - 1.0
    return pd.DataFrame(rows).T


def daily_index(result: pd.DataFrame, sched: pd.DataFrame, prices: pd.DataFrame, cash_tri: pd.Series) -> pd.Series:
    """Daily total-return index of a weight-vector result (for the daily
    drawdown of §9.3 item 4): within each holding period the assets' daily
    relatives apply at the weights set at the open, the remainder in cash; the
    period's cost is charged at the execution-date close."""
    full = pd.concat([prices, cash_tri.rename("cash")], axis=1).sort_index().ffill()
    assets = list(prices.columns)
    level, pieces = 1.0, []
    for _, row in sched.iloc[:-1].iterrows():
        t, e, e_next = row["signal_date"], row["execution_date"], row["period_end"]
        w = {a: result.at[t, f"w_{a}"] for a in assets}
        base = full.reindex([e], method="ffill").iloc[0]
        window = full.loc[e:e_next]
        rel = sum(w[a] * window[a] / base[a] for a in assets if w[a] != 0.0) + \
            (1.0 - sum(w.values())) * window["cash"] / base["cash"]
        rel = rel.loc[rel.index > e]
        level *= 1.0 - result.at[t, "cost"]
        piece = level * rel
        pieces.append(piece)
        level = float(piece.iloc[-1])
    return pd.concat(pieces).rename("tri")


# --- Metrics (§9.3) ---------------------------------------------------------------------

def descriptive_metrics(frame: pd.DataFrame, r_cash: pd.Series, signal: pd.DataFrame | None,
                        universe: list[str]) -> dict[str, float]:
    """§9.3 items 1–6 and 11 for one result frame (``net`` per period)."""
    r = frame["net"]
    excess = r - r_cash.reindex(r.index)
    years = len(r) / stats.MONTHS_PER_YEAR
    wcols = [f"w_{a}" for a in universe if f"w_{a}" in frame]
    on = (frame[wcols] > 0)
    out = {"periods": int(len(r)), "first_period": str(r.index[0].date()), "last_period": str(r.index[-1].date()),
           "ann_geometric_return": stats.annualised_geometric_return(r),
           "ann_volatility": stats.annualised_volatility(r),
           "sharpe_annual": stats.sharpe_annual(excess), "sharpe_monthly": stats.sharpe_monthly(excess),
           "max_drawdown_monthly": stats.max_drawdown(stats.total_return_index(r)),
           "mean_excess_monthly": float(excess.mean()), "hit_rate_positive_excess": float((excess > 0).mean()),
           "skewness_excess": stats.skewness(excess), "kurtosis_excess": stats.kurtosis(excess),
           "ann_one_way_turnover": float(frame["turnover"].sum() / years),
           "mean_gross_exposure": float(frame["gross_exposure"].mean()),
           "mean_cost_monthly": float(frame["cost"].mean()),
           "fraction_asset_months_on": float(on.to_numpy().sum() / max(1, int(signal.notna().to_numpy().sum())))
           if signal is not None else float(on.to_numpy().mean())}
    if signal is not None:
        sw = switches_per_asset(signal)
        out["switches_total"] = int(sum(sw.values()))
        out["switches_per_asset_per_year"] = {a: float(n / years) for a, n in sw.items()}
    return out


def switches_per_asset(signal: pd.DataFrame) -> dict[str, int]:
    """On/off changes of each asset's signal between consecutive signal dates
    on which it is present (T4: any change of its 0, ⅓, ⅔, 1 level)."""
    out = {}
    for a in signal.columns:
        s = signal[a].dropna()
        out[a] = int((s.diff().abs() > 1e-12).sum())
    return out


def inference_metrics(trial: str, results: dict[str, pd.DataFrame], rng: np.random.Generator) -> dict:
    """§9.3 items 7–9 against B3 and B4."""
    r = results[trial]["net"]
    r_cash = results["B0"]["net"].reindex(r.index)
    out = {"sharpe_ci": stats.sharpe_ci_stationary_bootstrap(r - r_cash, rng)}
    for bench in ("B3", "B4"):
        rb = results[bench]["net"].reindex(r.index)
        out[f"vs_{bench}"] = {"newey_west": stats.newey_west_mean(r - rb),
                              "ledoit_wolf": stats.ledoit_wolf_sharpe_test(r - r_cash, rb - r_cash, rng)}
    return out


def deflation(desc: dict[str, dict]) -> tuple[dict[str, dict], dict]:
    sharpes = [desc[t]["sharpe_monthly"] for t in TRIAL_IDS]
    variance, floored = stats.trial_variance(sharpes)
    out = {t: {f"N{n}": stats.deflated_sharpe(desc[t]["sharpe_monthly"], desc[t]["periods"], desc[t]["skewness_excess"],
                                               desc[t]["kurtosis_excess"], n, variance)
               for n in (N_TRIALS_REGISTERED, N_TRIALS_SENSITIVITY)} for t in TRIAL_IDS}
    return out, {"variance_across_trials": variance, "floor_applied": floored}


# --- Decision criteria (§9.5) ------------------------------------------------------------

def insample_criteria(desc: dict, infer: dict, dsr: dict, infer_stress: dict, trial: str = "T1") -> dict[str, bool]:
    nw = infer[trial]["vs_B4"]["newey_west"]
    return {"C1": bool(desc[trial]["sharpe_annual"] >= desc["B4"]["sharpe_annual"] + C1_SHARPE_MARGIN
                       and desc[trial]["sharpe_annual"] >= desc["B3"]["sharpe_annual"] + C1_SHARPE_MARGIN),
            "C2": bool(nw["t"] >= C2_T_MIN),
            "C3": bool(dsr[trial][f"N{N_TRIALS_REGISTERED}"]["dsr"] >= C3_DSR_MIN),
            "C4": bool(np.sign(nw["mean"]) == np.sign(infer_stress[trial]["vs_B4"]["newey_west"]["mean"]))}


def oos_criteria(desc: dict, infer: dict, trial: str = "T1") -> dict[str, bool]:
    return {"O1": bool(infer[trial]["vs_B4"]["newey_west"]["mean"] > 0),
            "O2": bool(desc[trial]["sharpe_annual"] > desc["B3"]["sharpe_annual"])}


def verdict(c: dict[str, bool], o: dict[str, bool], oos_t_vs_b4: float, oos_mdd_t1: float, oos_mdd_b4: float) -> str:
    """§9.5 verdict table; "not supported" conditions first (precedence)."""
    if not all(c.values()) or (not o["O1"] and oos_t_vs_b4 <= NOT_SUPPORTED_T_MAX) or oos_mdd_t1 < oos_mdd_b4:
        return "not supported"
    if o["O1"] and o["O2"]:
        return "supported"
    return "inconclusive"


# --- §9.6 descriptives ---------------------------------------------------------------------

def attribution(result: pd.DataFrame, asset_r: pd.DataFrame, universe: list[str]) -> dict:
    """Each asset's contribution to the annualised arithmetic return and to the
    variance of the gross period return, and its asset-months on."""
    contrib = pd.DataFrame({a: result[f"w_{a}"] * asset_r[a].reindex(result.index).fillna(0.0) for a in universe})
    port = contrib.sum(axis=1)
    var = float(port.var(ddof=1))
    out = {}
    for a in universe:
        out[a] = {"ann_return_contribution": float(contrib[a].mean() * stats.MONTHS_PER_YEAR),
                  "variance_share": float(contrib[a].cov(port) / var) if var > 0 else float("nan"),
                  "asset_months_on": int((result[f"w_{a}"] > 0).sum()),
                  "mean_weight_when_on": float(result.loc[result[f"w_{a}"] > 0, f"w_{a}"].mean())
                  if (result[f"w_{a}"] > 0).any() else 0.0}
    return out


def per_asset_sharpe(t1: pd.DataFrame, b3: pd.DataFrame, asset_r: pd.DataFrame, universe: list[str]) -> dict:
    """Each asset's own long/flat position (T1's weight) against its own
    always-on vol-scaled position (B3's weight): annualised Sharpe of the
    weighted excess return over the months the asset is present."""
    out = {}
    for a in universe:
        present = b3[f"w_{a}"] > 0
        ex = asset_r[a].reindex(t1.index) - asset_r["cash"].reindex(t1.index)
        own = (t1[f"w_{a}"] * ex)[present]
        always = (b3[f"w_{a}"] * ex)[present]
        out[a] = {"months_present": int(present.sum()),
                  "sharpe_long_flat": stats.sharpe_annual(own) if present.sum() > 1 else float("nan"),
                  "sharpe_always_on": stats.sharpe_annual(always) if present.sum() > 1 else float("nan")}
    return out


def crisis_table(daily: dict[str, pd.Series], refs: pd.DataFrame, window_label: str) -> dict:
    out = {}
    for name, (start, end, w) in CRISIS_WINDOWS.items():
        if w != window_label:
            continue
        row = {}
        for k, idx in daily.items():
            seg = idx.loc[start:end]
            row[k] = float(seg.iloc[-1] / seg.iloc[0] - 1.0) if len(seg) > 1 else float("nan")
        for s in refs.columns:
            seg = refs[s].dropna().loc[start:end]
            row[s] = float(seg.iloc[-1] / seg.iloc[0] - 1.0) if len(seg) > 1 else float("nan")
        out[name] = row
    return out


def correlations(results: dict[str, pd.DataFrame], asset_r: pd.DataFrame) -> dict:
    cash = asset_r["cash"]
    out = {}
    for k in ("T1", "B3"):
        ex = results[k]["net"] - cash.reindex(results[k].index)
        out[k] = {s: float(ex.corr(asset_r[s].reindex(ex.index) - cash.reindex(ex.index))) for s in REFERENCE_SYMBOLS}
    return out


def vol_forecast_vs_realised(result: pd.DataFrame, vol: pd.DataFrame, universe: list[str]) -> dict:
    """Ex-ante diagonal forecast √(Σ w_i² σ_i²) per period against the realised
    rolling 12-month annualised volatility of the net return."""
    w2s2 = sum((result[f"w_{a}"] ** 2) * (vol[a].reindex(result.index).fillna(0.0) ** 2) for a in universe)
    forecast = np.sqrt(w2s2)
    realised = result["net"].rolling(VOL_REALISED_WINDOW_MONTHS).std(ddof=1) * np.sqrt(stats.MONTHS_PER_YEAR)
    both = pd.DataFrame({"forecast": forecast, "realised": realised}).dropna()
    both = both[both["forecast"] > 0]
    ratio = both["realised"] / both["forecast"]
    return {"months_compared": int(len(both)), "mean_forecast": float(both["forecast"].mean()),
            "mean_realised": float(both["realised"].mean()), "mean_ratio_realised_over_forecast": float(ratio.mean()),
            "share_months_realised_over_1_5x_forecast": float((ratio > VOL_EXCEEDANCE_FACTOR).mean()),
            "series": both.assign(ratio=ratio)}


def subperiod_metrics(results: dict[str, pd.DataFrame], sched: pd.DataFrame, signals: dict[str, pd.DataFrame],
                      universe: list[str]) -> dict:
    start_month = sched.set_index("signal_date")["execution_date"].dt.to_period("M")
    out = {}
    for name, (first, last) in SUBPERIODS.items():
        lo, hi = pd.Period(first, "M"), pd.Period(last, "M")
        months = start_month[(start_month >= lo) & (start_month <= hi)].index
        sliced = {k: f.loc[f.index.isin(months)] for k, f in results.items()}
        out[name] = {}
        for k, f in sliced.items():
            if len(f) <= 1:
                continue
            sig = signals[k].loc[signals[k].index.isin(months)] if k in signals else None
            out[name][k] = descriptive_metrics(f, sliced["B0"]["net"], sig, universe)
    return out


def power_statement(signal_t1: pd.DataFrame) -> dict:
    n = int(sum(switches_per_asset(signal_t1).values()))
    return {"switches_total": n, "min_switches_for_full_power": POWER_MIN_SWITCHES,
            "label": "low-powered" if n < POWER_MIN_SWITCHES else "as registered"}


# --- One window --------------------------------------------------------------------------

def run_strategies(prices: pd.DataFrame, cash_tri: pd.Series, sched: pd.DataFrame, table: dict[str, pd.DataFrame],
                   universe: list[str], k: float | None, multiple: float,
                   cost_bp: dict[str, float] | None = None) -> tuple[dict[str, pd.DataFrame], dict, float]:
    """T1–T4 and B0–B4 for one cost multiple; returns (results, signals, k)."""
    signals = {t: trial_signal(table, t) for t in TRIAL_IDS}
    ones = table["present"].astype(float).where(table["present"])
    weights = {t: weights_from(signals[t], table["vol"]) for t in TRIAL_IDS}
    weights["B3"] = weights_from(ones, table["vol"])
    weights["B1"] = equal_weights(table["present"])
    weights["B0"] = fixed_weights(table["present"].index, {})
    weights["B2"] = fixed_weights(table["present"].index, B2_WEIGHTS if cost_bp is None else {})
    costs = costs_for(list(prices.columns), multiple, cost_bp)
    results = {name: engine.run(prices, cash_tri, sched, weights[name], costs) for name in ("B0", "B1", "B2", "B3", *TRIAL_IDS)}
    if k is None:
        k = engine.exposure_ratio(results["T1"], results["B3"])
    weights["B4"] = scaled(weights["B3"], k)
    results["B4"] = engine.run(prices, cash_tri, sched, weights["B4"], costs)
    return results, signals, k


def run_window(label: str, window: str, prices: pd.DataFrame, cash_tri: pd.Series, sched: pd.DataFrame,
               universe: list[str], k_frozen: float | None, out_dir: Path, with_subperiods: bool) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    table = signal_table(prices, cash_tri, universe, pd.DatetimeIndex(sched["signal_date"]))
    asset_r = period_asset_returns(prices, cash_tri, sched)
    entry = {a: str(table["present"][a][table["present"][a]].index[0].date()) if table["present"][a].any() else None
             for a in universe}
    summary = {"label": label, "universe": universe, "n_assets": len(universe), "holding_periods": int(len(sched) - 1),
               "first_signal_date": str(sched["signal_date"].iloc[0].date()),
               "first_execution_date": str(sched["execution_date"].iloc[0].date()),
               "last_period_end": str(sched["period_end"].iloc[-2].date()), "entry_signal_dates": entry,
               "cost_cases": {}}
    k = k_frozen
    refs = prices[[s for s in REFERENCE_SYMBOLS if s in prices]]
    for case, multiple in COST_CASES.items():
        rng = np.random.default_rng(SEED)
        results, signals, k = run_strategies(prices, cash_tri, sched, table, universe, k, multiple)
        desc = {name: descriptive_metrics(f, results["B0"]["net"], signals.get(name), universe) for name, f in results.items()}
        infer = {t: inference_metrics(t, results, rng) for t in TRIAL_IDS}
        dsr, dsr_inputs = deflation(desc)
        daily = {name: daily_index(results[name], sched, prices, cash_tri) for name in results}
        vfr = vol_forecast_vs_realised(results["T1"], table["vol"], universe)
        vfr_b3 = vol_forecast_vs_realised(results["B3"], table["vol"], universe)
        case_summary = {"cost_multiple": multiple, "k_exposure_ratio": k, "descriptive": desc, "inference": infer,
                        "deflated_sharpe": dsr, "deflation_inputs": dsr_inputs,
                        "max_drawdown_daily": {name: stats.max_drawdown(idx) for name, idx in daily.items()},
                        "attribution": {"T1": attribution(results["T1"], asset_r, universe),
                                        "B3": attribution(results["B3"], asset_r, universe)},
                        "per_asset_sharpe": per_asset_sharpe(results["T1"], results["B3"], asset_r, universe),
                        "crisis_table": crisis_table({n: daily[n] for n in ("T1", "B1", "B2", "B3", "B4")}, refs, window),
                        "correlations": correlations(results, asset_r),
                        "vol_forecast_vs_realised": {"T1": {k_: v for k_, v in vfr.items() if k_ != "series"},
                                                     "B3": {k_: v for k_, v in vfr_b3.items() if k_ != "series"}},
                        "power_statement": power_statement(signals["T1"])}
        if with_subperiods:
            case_summary["subperiods"] = subperiod_metrics(results, sched, signals, universe)
        summary["cost_cases"][case] = case_summary
        tag = f"{len(universe)}assets_{case}"
        pd.DataFrame({n: {k_: v for k_, v in d.items() if not isinstance(v, dict)} for n, d in desc.items()}).T.to_csv(
            out_dir / f"metrics_{tag}.csv")
        monthly = pd.concat({name: f["net"] for name, f in results.items()}, axis=1)
        monthly.insert(0, "T1_gross_exposure", results["T1"]["gross_exposure"])
        monthly.insert(0, "T1_assets_on", (results["T1"][[f"w_{a}" for a in universe]] > 0).sum(axis=1))
        monthly.insert(0, "period_end", sched.set_index("signal_date")["period_end"].reindex(monthly.index).dt.date)
        monthly.insert(0, "execution_date", sched.set_index("signal_date")["execution_date"].reindex(monthly.index).dt.date)
        monthly.to_csv(out_dir / f"monthly_{tag}.csv")
        results["T1"].to_csv(out_dir / f"t1_periods_{tag}.csv")
        if case == "base":
            for key in ("s12", "s6", "s3", "vol"):
                table[key].to_csv(out_dir / f"signal_{key}_{len(universe)}assets.csv")
            vfr["series"].to_csv(out_dir / f"vol_forecast_vs_realised_T1_{len(universe)}assets.csv")
            pd.concat({n: d for n, d in daily.items()}, axis=1).to_csv(out_dir / f"daily_index_{len(universe)}assets.csv")
            plots(results, signals["T1"], daily, universe, out_dir, f"{label} ({len(universe)} assets)",
                  f"{len(universe)}assets")
    # breakeven curve (§9.6): Sharpe(T1) − Sharpe(B4) by cost multiple, k frozen
    curve = {}
    for m in COST_MULTIPLES_BREAKEVEN:
        res, _, _ = run_strategies(prices, cash_tri, sched, table, universe, k, m)
        cash_r = res["B0"]["net"]
        curve[m] = stats.sharpe_annual(res["T1"]["net"] - cash_r) - stats.sharpe_annual(res["B4"]["net"] - cash_r)
    summary["breakeven_curve"] = {"sharpe_T1_minus_B4_by_multiple": {str(m): v for m, v in curve.items()},
                                  "zero_crossing_multiple": zero_crossing(curve)}
    summary["k_exposure_ratio"] = k
    return summary


def zero_crossing(curve: dict[float, float]) -> float | None:
    xs = sorted(curve)
    for lo, hi in zip(xs[:-1], xs[1:]):
        a, b = curve[lo], curve[hi]
        if a == 0:
            return float(lo)
        if a * b < 0:
            return float(lo + (hi - lo) * a / (a - b))
    return None if curve[xs[0]] * curve[xs[-1]] > 0 else float(xs[-1])


def plots(results: dict[str, pd.DataFrame], signal_t1: pd.DataFrame, daily: dict[str, pd.Series],
          universe: list[str], out_dir: Path, title: str, tag: str) -> None:
    fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    t1 = results["T1"]
    ax[0].plot(t1.index, t1["gross_exposure"], color="black", lw=1.2, label="T1 gross exposure")
    ax[0].plot(results["B3"].index, results["B3"]["gross_exposure"], color="grey", lw=0.8, ls="--", label="B3 gross exposure")
    ax[0].set_ylabel("gross exposure"); ax[0].legend(loc="upper left", fontsize=8)
    ax2 = ax[0].twinx()
    ax2.step(t1.index, (t1[[f"w_{a}" for a in universe]] > 0).sum(axis=1), color="tab:blue", lw=0.8, where="post")
    ax2.set_ylabel("assets on", color="tab:blue")
    for name, c in (("T1", "black"), ("B3", "grey"), ("B4", "tab:red")):
        dd = daily[name] / daily[name].cummax() - 1.0
        ax[1].plot(dd.index, dd, color=c, lw=0.9, label=f"{name} drawdown (daily)")
    ax[1].set_ylabel("drawdown"); ax[1].legend(loc="lower left", fontsize=8)
    fig.suptitle(title); fig.tight_layout()
    fig.savefig(out_dir / f"exposure_drawdown_{tag}.png", dpi=110); plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 0.45 * len(universe) + 1))
    for i, a in enumerate(universe):
        s = signal_t1[a]
        on = s[s > 0].index
        ax.scatter(on, [i] * len(on), marker="|", s=60, color="black")
    ax.set_yticks(range(len(universe))); ax.set_yticklabels(universe); ax.set_title(f"T1 on/off strips, {title}")
    fig.tight_layout(); fig.savefig(out_dir / f"onoff_strips_{tag}.png", dpi=110); plt.close(fig)


# --- Provenance and entry points ---------------------------------------------------------------

def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=STUDY_DIR, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def provenance() -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
    return {"git_commit": git_commit(), "seed": SEED,
            "data": {k: {"sha256": v.get("sha256"), "downloaded_at_utc": v.get("downloaded_at_utc"),
                         "reused_from": v.get("reused_from")} for k, v in manifest.items()}}


def _json_default(value):
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, pd.Period)):
        return str(value)
    raise TypeError(f"not serialisable: {type(value)}")


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n", encoding="utf-8")


def insample_schedule(bars: pd.DatetimeIndex) -> pd.DataFrame:
    end = pd.Period(INSAMPLE_LAST_SIGNAL_MONTH, "M").to_timestamp(how="end").normalize()
    return build_schedule(bars, month_end_signal_dates(bars, INSAMPLE_FIRST_SIGNAL_DATE, end))


def common_last_bar(prices: pd.DataFrame, columns: list[str]) -> pd.Timestamp:
    """The last bar that every one of ``columns`` has (§16, 2026-10-22: the
    held-back window ends there for every instrument alike)."""
    return min(prices[c].last_valid_index() for c in columns)


def oos_schedule(bars: pd.DatetimeIndex) -> pd.DataFrame:
    """§8.2 signal dates on ``bars``; the last holding period ends at the last
    bar when the bars stop before the execution date that follows the last
    signal (§16 amendment of 2026-10-22, decided before the run)."""
    start = pd.Period(OOS_FIRST_SIGNAL_MONTH, "M").to_timestamp(how="start")
    end = pd.Period(OOS_LAST_SIGNAL_MONTH, "M").to_timestamp(how="end").normalize()
    return build_schedule(bars, month_end_signal_dates(bars, start, end), end_at_last_bar=True)


def run_insample(out_dir: Path = RESULTS_DIR / "insample") -> None:
    universe = universe_from_checks()
    prices = load_prices(sorted(set(universe) | set(REFERENCE_SYMBOLS), key=lambda s: (s not in universe, s)))
    cash_tri = cash_index(data.fred_series())
    bars = prices[universe].dropna(how="all").index
    sched = insample_schedule(bars)
    summary = {"window": "insample", "runs": {}}
    for tag, uni in (("ten", universe), ("nine_without_IEF", [a for a in universe if a != "IEF"])):
        s = run_window(f"in-sample, vendor history and the cash accrual, {tag}", "insample", prices, cash_tri, sched,
                       uni, None, out_dir, with_subperiods=True)
        base, stress = s["cost_cases"]["base"], s["cost_cases"]["stress"]
        s["criteria"] = insample_criteria(base["descriptive"], base["inference"], base["deflated_sharpe"], stress["inference"])
        s["criteria_T2_T4"] = {t: insample_criteria(base["descriptive"], base["inference"], base["deflated_sharpe"],
                                                    stress["inference"], t) for t in ("T2", "T3", "T4")}
        s["power_statement"] = base["power_statement"]
        summary["runs"][tag] = s
    summary["k_exposure_ratio_frozen"] = summary["runs"]["ten"]["k_exposure_ratio"]
    summary["k_exposure_ratio_frozen_nine_without_IEF"] = summary["runs"]["nine_without_IEF"]["k_exposure_ratio"]
    summary["criteria"] = summary["runs"]["ten"]["criteria"]
    summary["provenance"] = provenance()
    write_json(out_dir / "summary.json", summary)
    ten = summary["runs"]["ten"]
    print(f"in-sample written to {out_dir.relative_to(STUDY_DIR)}; k = {ten['k_exposure_ratio']:.4f}; "
          f"criteria {ten['criteria']}; power: {ten['power_statement']['label']} "
          f"({ten['power_statement']['switches_total']} switches)")


def run_oos(out_dir: Path = RESULTS_DIR / "oos") -> None:
    if out_dir.exists():
        raise SystemExit("results/oos/ exists: the out-of-sample run is executed exactly once (§8.2)")
    insample = json.loads((RESULTS_DIR / "insample" / "summary.json").read_text(encoding="utf-8"))
    universe = universe_from_checks()
    prices = load_prices(sorted(set(universe) | set(REFERENCE_SYMBOLS), key=lambda s: (s not in universe, s)))
    cash_tri = vendor_tri(CASH_ETF)
    # §16 (2026-10-22): the window ends at the last bar every instrument and the cash ETF have.
    # IEF and BIL were reused from earlier studies and reach beyond 2026-09-30; the ten fetched
    # files stop there.  Without this cut the engine would forward-fill nine assets one day short
    # of the last execution date while IEF and cash got the full period.
    last_bar = min(common_last_bar(prices, universe), cash_tri.last_valid_index())
    bars = prices[universe].dropna(how="all").index
    bars = bars[bars <= last_bar]
    sched = oos_schedule(bars)
    summary = {"window": "oos", "runs": {},
               "common_last_bar": str(last_bar.date()),
               "last_period_ends_at_last_bar": bool(pd.isna(sched["execution_date"].iloc[-1])),
               "note": "§16 amendment, 2026-10-22, decided before this run: the last holding period ends at the "
                       "common last bar instead of the first execution date of October 2026 (§8.2), which no "
                       "fetched file holds; one trading day short, identical for every instrument"}
    for tag, uni, kkey in (("ten", universe, "k_exposure_ratio_frozen"),
                           ("nine_without_IEF", [a for a in universe if a != "IEF"], "k_exposure_ratio_frozen_nine_without_IEF")):
        k = float(insample[kkey])
        s = run_window(f"out-of-sample, vendor history and actual BIL, {tag}", "oos", prices, cash_tri, sched, uni, k,
                       out_dir, with_subperiods=False)
        base = s["cost_cases"]["base"]
        o = oos_criteria(base["descriptive"], base["inference"])
        s["criteria"] = o
        s["verdict_T1"] = verdict(insample["runs"][tag]["criteria"], o, base["inference"]["T1"]["vs_B4"]["newey_west"]["t"],
                                  base["descriptive"]["T1"]["max_drawdown_monthly"], base["descriptive"]["B4"]["max_drawdown_monthly"])
        s["criteria_T2_T4"] = {t: oos_criteria(base["descriptive"], base["inference"], t) for t in ("T2", "T3", "T4")}
        s["k_frozen_from_insample"] = k
        summary["runs"][tag] = s
    summary["criteria"] = summary["runs"]["ten"]["criteria"]
    summary["verdict_T1"] = summary["runs"]["ten"]["verdict_T1"]
    summary["provenance"] = provenance()
    write_json(out_dir / "summary.json", summary)
    print(f"out-of-sample written to {out_dir.relative_to(STUDY_DIR)}; verdict for T1 (ten assets): {summary['verdict_T1']}; "
          f"nine without IEF: {summary['runs']['nine_without_IEF']['verdict_T1']}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Study 004 runs (§8, §9). Invoke through reproduce.sh.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--insample", action="store_true")
    group.add_argument("--oos", action="store_true")
    args = parser.parse_args(argv)
    run_insample() if args.insample else run_oos()


if __name__ == "__main__":
    main()
