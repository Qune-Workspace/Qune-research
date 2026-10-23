"""Post-hoc risk report for Study 004's T1 book (library ``qune_research.risk``).

Built on 2026-10-23, after the study's results and its independent review,
so it carries no decision weight and changes nothing in ``results/``: it
reads the committed weights, volatilities and daily indices and the same
raw vendor files (hash-checked against ``results/data_manifest.json``), and
asks how well three ex-ante volatility forecasts described what followed,
where the book's risk sat, how the last book would have fared in four
historical windows, and what a linear drawdown rule would have done.

Forecasts at each signal date t, from the 252 vendor bars ending at t:
  diagonal  √(Σ w_i² σ_i²) with the study's own 63-day σ_i (the committed
            ``signal_vol`` file), the forecast the pre-registration made;
  ewma      full covariance, exponentially weighted, 42-day half-life;
  shrunk    the same, shrunk toward constant correlation with the
            Ledoit-Wolf intensity estimated on the window;
  sample    equal-weighted 252-day covariance.
Realised: the annualised standard deviation of T1's daily net index over
the holding period the forecast covered (execution close to period end).
Every number printed in README.md comes from ``report.json``.

Run from the study folder: ``python risk/risk_report.py``.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

STUDY_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STUDY_DIR.parent.parent))
from qune_research import risk  # noqa: E402

RAW_DIR = STUDY_DIR / "data" / "raw"
RESULTS_DIR = STUDY_DIR / "results"
OUT_DIR = STUDY_DIR / "risk"
HALFLIFE_DAYS = 42
LOOKBACK_BARS = 252
MIN_BARS = 63
MIN_PERIOD_DAYS = 10
VAR_LEVEL = 0.99
DRAWDOWN_LIMIT = 0.10
STRESS_WINDOWS = {"GFC 2008-09-01..2009-02-28": ("2008-09-01", "2009-02-28"),
                  "Taper 2013-05-21..2013-09-05": ("2013-05-21", "2013-09-05"),
                  "COVID 2020-02-19..2020-03-23": ("2020-02-19", "2020-03-23"),
                  "2022 2022-01-01..2022-10-31": ("2022-01-01", "2022-10-31")}
CASH_ETF = "BIL"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_vendor(symbols: list[str]) -> pd.DataFrame:
    manifest = json.loads((RESULTS_DIR / "data_manifest.json").read_text(encoding="utf-8"))
    recorded = {name: rec["sha256"] for name, rec in manifest.items() if isinstance(rec, dict) and "sha256" in rec}
    cols = {}
    hashes = {}
    for s in symbols:
        f = RAW_DIR / f"tiingo_{s}_daily.csv"
        h = sha256(f)
        if recorded.get(f.name) != h:
            raise SystemExit(f"{f.name} is not the file the study's manifest records; refusing")
        hashes[f.name] = {"sha256": h, "matches_manifest": True}
        df = pd.read_csv(f, parse_dates=["date"]).set_index("date").sort_index()
        cols[s] = df["adjClose"].astype(float)
    return pd.DataFrame(cols).sort_index(), hashes


def period_table(window: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    d = RESULTS_DIR / window
    periods = pd.read_csv(d / "t1_periods_10assets_base.csv", parse_dates=["signal_date", "execution_date", "period_end"]).set_index("signal_date")
    vol = pd.read_csv(d / "signal_vol_10assets.csv", index_col=0, parse_dates=True)
    daily = pd.read_csv(d / "daily_index_10assets.csv", index_col=0, parse_dates=True)["T1"]
    return periods, vol, daily


def forecasts_for_window(window: str, prices: pd.DataFrame, universe: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    periods, vol, daily = period_table(window)
    rets = prices[universe].pct_change()
    rows, rc_rows = [], []
    for t, row in periods.iterrows():
        w = {a: float(row[f"w_{a}"]) for a in universe}
        held = {a: v for a, v in w.items() if v != 0.0}
        if not held:
            rows.append({"signal_date": t, "gross_exposure": 0.0})
            continue
        hist = rets.loc[:t, list(held)].dropna(how="any").iloc[-LOOKBACK_BARS:]
        if len(hist) < MIN_BARS:
            rows.append({"signal_date": t, "gross_exposure": row["gross_exposure"], "note": "short history"})
            continue
        diag = float(np.sqrt(sum(w[a] ** 2 * float(vol.loc[t, a]) ** 2 for a in held)))
        ew = risk.ewma_covariance(hist, HALFLIFE_DAYS)
        sh, delta = risk.shrunk_ewma_covariance(hist, HALFLIFE_DAYS)
        sa = risk.sample_covariance(hist)
        seg = daily.loc[(daily.index > row["execution_date"]) & (daily.index <= row["period_end"])]
        seg = pd.concat([daily.loc[daily.index <= row["execution_date"]].iloc[-1:], seg])
        pr = seg.pct_change().dropna()
        realised = float(pr.std(ddof=1) * np.sqrt(risk.TRADING_DAYS)) if len(pr) >= MIN_PERIOD_DAYS else np.nan
        var_1d = risk.parametric_var_es(held, sh / risk.TRADING_DAYS, VAR_LEVEL, 1)["var"]
        rows.append({"signal_date": t, "gross_exposure": float(row["gross_exposure"]), "n_bars": int(len(hist)),
                     "vol_diagonal": diag, "vol_ewma": risk.portfolio_vol(held, ew),
                     "vol_shrunk": risk.portfolio_vol(held, sh), "vol_sample": risk.portfolio_vol(held, sa),
                     "lw_intensity": delta, "realised_period": realised, "period_days": int(len(pr)),
                     "var99_1d_shrunk": var_1d, "var99_exceedances": int((pr < -var_1d).sum())})
        rc = risk.risk_contributions(held, sh)
        rc_rows.append(pd.Series({**{a: float(rc.get(a, 0.0)) for a in universe}}, name=t))
    out = pd.DataFrame(rows).set_index("signal_date")
    rc_df = pd.DataFrame(rc_rows)
    return out, rc_df


def accuracy_block(table: pd.DataFrame) -> dict:
    have = table.dropna(subset=["realised_period"])
    out = {"months_with_forecast_and_realised": int(len(have))}
    for name in ("vol_diagonal", "vol_ewma", "vol_shrunk", "vol_sample"):
        if name in have:
            out[name] = risk.forecast_accuracy(have[name], have["realised_period"])
    if "var99_exceedances" in have:
        days = int(have["period_days"].sum())
        exc = int(have["var99_exceedances"].sum())
        out["var99_1d_backtest_shrunk"] = {"days": days, "exceedances": exc, "rate": exc / days if days else None,
                                           "expected_rate": 1.0 - VAR_LEVEL}
    if "lw_intensity" in have:
        out["lw_intensity_mean"] = float(have["lw_intensity"].mean())
    return out


def drawdown_block(window: str) -> dict:
    _, _, daily = period_table(window)
    dd = risk.drawdown_from_high(daily)
    m = risk.drawdown_multiplier(dd, DRAWDOWN_LIMIT)
    return {"limit": DRAWDOWN_LIMIT, "days": int(len(m)), "share_days_multiplier_below_one": float((m < 1.0).mean()),
            "min_multiplier": float(m.min()), "max_drawdown": float(dd.min()), "date_of_max_drawdown": str(dd.idxmin().date()),
            "note": "descriptive: what a linear rule with this limit would have applied to T1's realised path; never run as a rule"}


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=STUDY_DIR).stdout.strip()
    except Exception:
        return "unknown"


def main() -> None:
    checks = json.loads((RESULTS_DIR / "checks" / "data_checks.json").read_text(encoding="utf-8"))
    universe = list(checks["evaluation"]["universe"])
    prices, hashes = load_vendor(universe + [CASH_ETF])
    report = {"built": pd.Timestamp.now(tz="Europe/London").isoformat(timespec="minutes"), "commit_before_run": git_commit(),
              "universe": universe, "halflife_days": HALFLIFE_DAYS, "lookback_bars": LOOKBACK_BARS, "var_level": VAR_LEVEL,
              "files": hashes, "windows": {}}
    last_book = None
    for window in ("insample", "oos"):
        table, rc = forecasts_for_window(window, prices, universe)
        table.to_csv(OUT_DIR / f"forecasts_{window}.csv")
        rc.to_csv(OUT_DIR / f"risk_contributions_{window}.csv")
        blk = {"accuracy": accuracy_block(table), "drawdown_rule": drawdown_block(window),
               "risk_contributions_mean_over_months_held": {a: float(rc[a].mean()) for a in universe} if len(rc) else {},
               "months": int(len(table)), "months_in_cash": int((table["gross_exposure"] == 0).sum())}
        if window == "oos" and len(rc):
            t_last = rc.index[-1]
            periods, _, daily = period_table(window)
            last_book = {a: float(periods.loc[t_last, f"w_{a}"]) for a in universe if periods.loc[t_last, f"w_{a}"] != 0.0}
            blk["last_book"] = {"signal_date": str(t_last.date()), "weights": last_book,
                                "risk_contributions_shrunk": {a: float(rc.loc[t_last, a]) for a in universe},
                                "vol_forecasts": {k: float(table.loc[t_last, k]) for k in ("vol_diagonal", "vol_ewma", "vol_shrunk", "vol_sample")},
                                "var99_1d_parametric_shrunk": float(table.loc[t_last, "var99_1d_shrunk"])}
            pr = daily.pct_change().dropna()
            blk["historical_var_es_T1_daily_oos"] = risk.historical_var_es(pr, VAR_LEVEL)
            cash = prices[CASH_ETF]
            st = risk.stress_window_returns(prices[universe], last_book, STRESS_WINDOWS, cash)
            st.to_csv(OUT_DIR / "stress_last_book.csv")
            blk["stress_last_book"] = {k: {c: (None if pd.isna(v) else float(v)) for c, v in r.items()} for k, r in st.iterrows()}
        report["windows"][window] = blk
    (OUT_DIR / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({w: report["windows"][w]["accuracy"] for w in report["windows"]}, indent=1, default=str))
    print(json.dumps(report["windows"]["oos"].get("last_book"), indent=1))
    print(json.dumps(report["windows"]["oos"].get("stress_last_book"), indent=1))
    print(json.dumps({w: report["windows"][w]["drawdown_rule"] for w in report["windows"]}, indent=1))
    print(json.dumps({w: report["windows"][w]["risk_contributions_mean_over_months_held"] for w in report["windows"]}, indent=1))
    print(json.dumps(report["windows"]["oos"].get("historical_var_es_T1_daily_oos"), indent=1))


if __name__ == "__main__":
    main()
