"""Power first for volatility-forecast accuracy at daily scoring (the reopener named 2026-10-27 00:2xZ).

Descriptive power calculation, written 2026-10-27 from 01:1xZ by the clock, before any question
is fixed. The 2026-10-27 00:2xZ addition to RESEARCH_AGENDA.md found no volatility-forecast
question powered at monthly scoring and named what reopens it: "daily scoring of one-day-ahead
forecasts ... with its power computed from Study 004's archived daily vendor files (git-ignored,
in the raw-file backup; seen data) before any question note". This script makes that statement.

Inputs: Study 004's archived Tiingo daily files (research/004-xasset-trend-voltarget/data/raw/,
git-ignored; each SHA-256 checked against results/data_manifest.json, refusing on a mismatch) and
the study's committed results (t1_periods_10assets_base.csv for the T1 book's weights and dates,
daily_index_10assets.csv for T1's daily net index). Nothing is fetched. Both windows were seen by
the author and read for this property at monthly scoring by the 2026-10-23 risk report and the
2026-10-27 00:2xZ power statement, so neither is a clean sample: only forward days are.

Per holding period (signal date t, weights w fixed at t, the period from the execution close to
the period end) and per trading day s after the execution day, two one-day-ahead variance
forecasts of the book, both from the 252 complete vendor rows of the held assets ending on the
trading day before s (so nothing from day s is used):
  ewma    w' S_ewma w, full covariance about zero, 42-day half-life (qune_research.risk);
  sample  w' S_sample w, equal-weighted 252-day covariance (ddof 1).
Realised: r_s, T1's daily net index return on day s, gross of the period's trading cost (Study
004's daily_index charges it on the first day after execution, so that day's return is divided
back by 1 - cost). The execution day's return belongs to the previous book and is not scored. The
index starts at 1.0 on the first execution date, so its first row's return is taken from that
base. Days on which the held assets have no vendor bar (exchange closures the index carries
forward on the cash leg: Good Fridays, 2007-01-02, 2012-10-29) are not scored, and their count is
printed. Holding periods with no position are not scored either, so a forward record of N months
scores fewer than 21 * N days; the share invested in each window is printed and applied.
The forecasts use the weights fixed at the signal date while the index lets them drift within
the period; the separate recomputation found this changes days to see by under 1%.
Same pair as R1 of tools/power_riskforecast.py; R2 (shrinkage) and R3 (diagonal) are not
repeated: R2 showed no detectable effect at monthly scoring with a median intensity of
0.04-0.10, and R3 is answered on seen data.

Loss, daily, with h the forecast variance and r_s^2 the proxy:
  QLIKE   L = ln h + r^2 / h. It differs from Patton's r^2/h - ln(r^2/h) - 1 only by a term that
          does not depend on h, so loss differentials are identical, and it stays finite on a
          zero return (Patton 2011, doi:10.1016/j.jeconom.2010.03.034);
  MSEvar  L = (r^2 - h)^2.
d_s = L(sample) - L(ewma); d > 0 favours EWMA. A forward test would be a Diebold-Mariano test,
mean(d) / its Newey-West standard error, at t >= 2.0. Lags: 21 (about one month of trading
days, Bartlett kernel; qune_research.stats.newey_west_mean) in the main table; because the
result depends on the lag, days to see s are also printed at 5, 42, 63 and 126 lags.

Power as in the other power tools, in units of the daily Sharpe of d: S_MDE = K * nw / sqrt(N),
K = 2.842, N scored days (60 months = 1,260 trading days when fully invested; 120 months = 2,520;
each also at the window's invested share). Days to see an observed daily Sharpe s: (K * nw / s)^2.
The loss differentials are heavy-tailed (the separate recomputation found the largest 1% of days
by |d| carry 50% (QLIKE) and 64% (MSE) of summed d in 2019-2026), so the normal approximation
behind K is fragile here and every figure below is an approximation, not a bound.

Run from the repository root: ``python tools/power_riskforecast_daily.py > tools/power_riskforecast_daily.txt``
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from qune_research import risk  # noqa: E402
from qune_research.stats import newey_west_mean  # noqa: E402

K = 2.842
STUDY = ROOT / "research" / "004-xasset-trend-voltarget"
RAW = STUDY / "data" / "raw"
RESULTS = STUDY / "results"
WINDOWS = {"in-sample 2004-2018": "insample", "2019-2026 (seen)": "oos"}
HALFLIFE_DAYS = 42
LOOKBACK_BARS = 252
MIN_BARS = 63
LAGS = 21
LAGS_ALT = (5, 63)
LAGS_SEE = (5, 21, 42, 63, 126)
FORWARD_DAYS = {"60 months": 1260, "120 months": 2520}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_prices(symbols: list[str]) -> pd.DataFrame:
    manifest = json.loads((RESULTS / "data_manifest.json").read_text(encoding="utf-8"))
    recorded = {k: v["sha256"] for k, v in manifest.items() if isinstance(v, dict) and "sha256" in v}
    cols = {}
    for s in symbols:
        f = RAW / f"tiingo_{s}_daily.csv"
        if recorded.get(f.name) != sha256(f):
            raise SystemExit(f"{f.name} is not the file the study's manifest records; refusing")
        df = pd.read_csv(f, parse_dates=["date"]).set_index("date").sort_index()
        cols[s] = df["adjClose"].astype(float)
    return pd.DataFrame(cols).sort_index()


def daily_rows(window: str, rets: pd.DataFrame, universe: list[str]) -> tuple[pd.DataFrame, dict[str, int]]:
    d = RESULTS / window
    periods = pd.read_csv(d / "t1_periods_10assets_base.csv",
                          parse_dates=["signal_date", "execution_date", "period_end"]).set_index("signal_date")
    index = pd.read_csv(d / "daily_index_10assets.csv", index_col=0, parse_dates=True)["T1"]
    first_exec = periods["execution_date"].min()
    if index.index[0] > first_exec:  # daily_index starts at level 1.0 on the first execution close
        index = pd.concat([pd.Series([1.0], index=[first_exec]), index])
    book_ret = index.pct_change()
    rows = []
    count = {"index_days": 0, "flat_days": 0, "closure_days": 0}
    for t, p in periods.iterrows():
        held = {a: float(p[f"w_{a}"]) for a in universe if float(p[f"w_{a}"]) != 0.0}
        days = book_ret.index[(book_ret.index > p["execution_date"]) & (book_ret.index <= p["period_end"])]
        count["index_days"] += len(days)
        if not held:
            count["flat_days"] += len(days)
            continue
        r = rets[list(held)]
        for i, s in enumerate(days):
            if s not in r.index or r.loc[s].isna().any():
                count["closure_days"] += 1
                continue
            hist = r.loc[r.index < s].dropna(how="any").iloc[-LOOKBACK_BARS:]
            if len(hist) < MIN_BARS:
                continue
            h_e = risk.portfolio_variance(held, risk.ewma_covariance(hist, HALFLIFE_DAYS, annualise=False))
            h_s = risk.portfolio_variance(held, risk.sample_covariance(hist, annualise=False))
            ret = float(book_ret.loc[s])
            if i == 0:  # the period's cost is charged on the first day after execution
                ret = (1.0 + ret) / (1.0 - float(p["cost"])) - 1.0
            rows.append({"day": s, "signal_date": t, "r": ret, "h_ewma": h_e, "h_sample": h_s})
    return pd.DataFrame(rows).set_index("day"), count


def qlike(r2: pd.Series, h: pd.Series) -> pd.Series:
    return np.log(h) + r2 / h


def mse_var(r2: pd.Series, h: pd.Series) -> pd.Series:
    return (r2 - h) ** 2


def describe(d: pd.Series, lags: int) -> dict[str, float]:
    n = len(d)
    sd = float(d.std(ddof=1))
    iid_se = sd / math.sqrt(n)
    nw = newey_west_mean(d, lags)
    return {"n": n, "mean": float(d.mean()), "sd": sd, "s": float(d.mean()) / sd, "t_iid": float(d.mean()) / iid_se,
            "t_nw": nw["t"], "nw": nw["se"] / iid_se, "wins": int((d > 0).sum())}


def main() -> None:
    checks = json.loads((RESULTS / "checks" / "data_checks.json").read_text(encoding="utf-8"))
    universe = list(checks["evaluation"]["universe"])
    rets = load_prices(universe).pct_change()
    print("Power first for volatility-forecast accuracy at daily scoring (tools/power_riskforecast_daily.py)")
    print(f"K = {K} (t >= 2.0 at 80% power); daily Sharpe of the loss differential d; Newey-West {LAGS} lags")
    print("inputs: Study 004's archived Tiingo daily files (hash-checked against results/data_manifest.json) and its")
    print("committed T1 periods and daily net index; nothing fetched; both windows seen, not clean")
    print("pair: R1, EWMA (42-day half-life) vs the 252-day sample covariance, one-day-ahead, d = L(sample) - L(ewma)")
    print()
    frames, shares = {}, {}
    for label, w in WINDOWS.items():
        df, c = daily_rows(w, rets, universe)
        frames[label] = df
        shares[label] = len(df) / c["index_days"]
        print(f"{label}: {len(df):,} scored days in {df['signal_date'].nunique()} holding periods "
              f"({df.index[0].date()} .. {df.index[-1].date()}); zero-return days {int((df['r'] == 0).sum())}; "
              f"median forecast vol (annualised) ewma {math.sqrt(df['h_ewma'].median() * risk.TRADING_DAYS):.4f}, "
              f"sample {math.sqrt(df['h_sample'].median() * risk.TRADING_DAYS):.4f}")
        print(f"  {c['index_days']:,} index days in the holding periods: {c['flat_days']:,} with no position, "
              f"{c['closure_days']} exchange closures (no vendor bar), so {shares[label]:.1%} scored")
    print()
    hdr = (f"  {'window':20} {'loss':6} {'n':>6} {'mean d':>10} {'sd d':>10} {'s/day':>7} {'t iid':>6} {'t NW':>6} "
           f"{'nw':>6} {'nw L5':>6} {'nw L63':>6} {'d>0':>12} {'days to see s':>14}")
    print(hdr)
    diffs, nws = {}, []
    for label, df in frames.items():
        r2 = df["r"] ** 2
        for lname, lf in (("QLIKE", qlike), ("MSEvar", mse_var)):
            d = (lf(r2, df["h_sample"]) - lf(r2, df["h_ewma"])).reset_index(drop=True)
            diffs[(label, lname)] = d
            res = describe(d, LAGS)
            alt = [describe(d, lag)["nw"] for lag in LAGS_ALT]
            need = f"{(K * res['nw'] / res['s']) ** 2:,.0f}" if res["s"] > 0 else "never (s <= 0)"
            print(f"  {label:20} {lname:6} {res['n']:>6,} {res['mean']:>10.3e} {res['sd']:>10.3e} {res['s']:>7.4f} "
                  f"{res['t_iid']:>6.2f} {res['t_nw']:>6.2f} {res['nw']:>6.3f} {alt[0]:>6.3f} {alt[1]:>6.3f} "
                  f"{res['wins']:>5,}/{res['n']:<6,} {need:>14}")
    print()
    print("Days to see each row's own s, by Newey-West lag (the result depends on the lag)")
    print(f"  {'window':20} {'loss':6} " + " ".join(f"{'L' + str(lag):>8}" for lag in LAGS_SEE))
    for (label, lname), d in diffs.items():
        cells = []
        for lag in LAGS_SEE:
            res = describe(d, lag)
            nws.append(res["nw"])
            cells.append(f"{(K * res['nw'] / res['s']) ** 2:>8,.0f}" if res["s"] > 0 else f"{'never':>8}")
        print(f"  {label:20} {lname:6} " + " ".join(cells))
    print()
    hi = max(nws)
    print("Forward record: detectable daily Sharpe of d, S_MDE = K * nw / sqrt(N scored days)")
    print(f"  nw bracket 1.00 / largest observed here over lags {LAGS_SEE[0]}-{LAGS_SEE[-1]} {hi:.3f} (not a bound)")
    for name, n in FORWARD_DAYS.items():
        print(f"  {name}, fully invested, {n:,} days: S_MDE = {K / math.sqrt(n):.4f} / {K * hi / math.sqrt(n):.4f}")
        for label, sh in shares.items():
            m = round(n * sh)
            print(f"  {name}, invested as in {label} ({sh:.1%}), {m:,} days: "
                  f"S_MDE = {K / math.sqrt(m):.4f} / {K * hi / math.sqrt(m):.4f}")
    print()
    print("Reading: compare each row's s/day with S_MDE. A daily forward record can see the comparison only if the")
    print("daily Sharpe of d out of sample is at least S_MDE. The in-sample s is an anchor, not a target; the")
    print("2019-2026 s shows whether that size held later. Both windows were seen, so only forward days are clean.")


if __name__ == "__main__":
    main()
