"""Independent recomputation for REVIEW.md (Study 004, cross-asset trend with
volatility targeting, ten liquid ETFs, long-only or flat).

Written by the reviewer (Tester, a separate agent session that did not write
the code).  It imports nothing from the study's ``src/`` or from the shared
library ``qune_research``: every number below is re-derived with numpy,
pandas and scipy only, from

  * the committed outputs under ``results/insample/`` and ``results/oos/``
    (``monthly_*.csv``, ``t1_periods_*.csv``, ``daily_index_*.csv``,
    ``signal_*.csv``, ``vol_forecast_vs_realised_*.csv``, ``metrics_*.csv``,
    ``summary.json``), and
  * the raw vendor files in ``data/raw/`` (git-ignored; present on disk at
    review time): Tiingo ``adjClose`` for the ten assets, SPY, IEF and BIL,
    the FRED DTB3 file, and the broker's bars for the overlap check.

With the raw files the reviewer rebuilds the whole monthly table (signals,
volatilities, weights, drift, costs, every strategy and benchmark) and the
daily indices with an engine of their own, then compares to the committed
files; every published statistic is recomputed from the committed monthly
files.  "Published" values are read from ``summary.json`` and the metrics CSVs
at full precision; numbers that exist only in README.md are typed in below,
marked README, and compared at the README's rounding.  Nothing is written to
disk.

Run from the study folder:  ../../.venv/bin/python review_recompute.py
Exit status is 1 if any row mismatches.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

STUDY = Path(__file__).resolve().parent
RES = STUDY / "results"
RAW = STUDY / "data" / "raw"
SQ12 = math.sqrt(12.0)
SQ252 = math.sqrt(252.0)
NW_LAGS = 6
BIL_EXPENSE = 0.001356                       # §5.2 (Study 001 §4)
SIGMA_A, W_CAP, VOL_WINDOW = 0.10, 0.25, 63  # §6.2
COST_BP = {"SPY": 2.0, "IWM": 2.0, "EFA": 2.5, "EEM": 3.0, "SHY": 2.0, "IEF": 2.0, "TLT": 2.0,
           "LQD": 2.5, "HYG": 3.0, "GLD": 2.0, "DBC": 3.5, "VNQ": 2.5}      # §9.2, one side
DSR_FLOOR = (0.05 / SQ12) ** 2                                               # §9.4
STRATS = ("B0", "B1", "B2", "B3", "B4", "T1", "T2", "T3", "T4")
TRIALS = ("T1", "T2", "T3", "T4")
LOOKBACKS = {"T1": (12,), "T2": (6,), "T3": (3,), "T4": (12, 6, 3)}
CRISIS = {"insample": {"GFC 2008-09-01..2009-02-28": ("2008-09-01", "2009-02-28")},
          "oos": {"COVID 2020-02-19..2020-03-23": ("2020-02-19", "2020-03-23"),
                  "COVID 2020-02-19..2020-08-31": ("2020-02-19", "2020-08-31"),
                  "2022 2022-01-01..2022-10-31": ("2022-01-01", "2022-10-31")}}
SUBPERIODS = {"2004-01..2008-12": ("2004-01", "2008-12"), "2009-01..2015-12": ("2009-01", "2015-12"),
              "2016-01..2018-12": ("2016-01", "2018-12")}

rows: list[tuple[str, str, str, str]] = []


def add(claim, published, recomputed, tol=0.0, fmt="{:.4f}", note=""):
    """Append one comparison row; match when |published - recomputed| <= tol."""
    suffix = f" ({note})" if note else ""
    if published is None:
        rows.append((claim, "n/a", fmt.format(recomputed) if isinstance(recomputed, (int, float, np.floating)) else str(recomputed),
                     "informational" + suffix))
        return
    if isinstance(published, (str, bool, np.bool_)) or isinstance(recomputed, (str, bool, np.bool_)):
        ok = str(published) == str(recomputed)
        rows.append((claim, str(published), str(recomputed), ("yes" if ok else "NO") + suffix))
        return
    p, r = float(published), float(recomputed)
    if math.isnan(p) and math.isnan(r):
        rows.append((claim, "nan", "nan", "yes" + suffix))
        return
    ok = abs(p - r) <= tol
    show = (lambda x: fmt.format(int(round(x)))) if "d}" in fmt else (lambda x: fmt.format(x))
    rows.append((claim, show(p), show(r), ("yes" if ok else "NO") + suffix))


def add_readme(claim, readme_value, recomputed, decimals, scale=1.0):
    """README value printed with ``decimals`` digits (after dividing by scale, e.g. 100 for %)."""
    add(claim + " [README]", readme_value, recomputed / scale, 0.5 * 10 ** (-decimals) + 1e-12, "{:." + str(decimals) + "f}")


# ----------------------------------------------------------------------------- statistics (reviewer's own)
def geo_annual(r):
    return float(np.prod(1.0 + r) ** (12.0 / len(r)) - 1.0)


def vol_annual(r):
    return float(np.std(r, ddof=1) * SQ12)


def sharpe_m(x):
    sd = np.std(x, ddof=1)
    return float(np.mean(x) / sd) if sd > 0 else float("nan")


def max_dd(levels):
    levels = np.asarray(levels, dtype=float)
    return float(np.min(levels / np.maximum.accumulate(levels) - 1.0))


def skew_kurt(x):
    z = (x - x.mean()) / x.std(ddof=0)
    return float((z ** 3).mean()), float((z ** 4).mean())


def nw_mean_t(x, lags=NW_LAGS):
    """Mean and HAC t (Bartlett kernel, ``lags`` lags, no small-sample factor), by hand."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    z = x - x.mean()
    s = float(z @ z) / n
    for j in range(1, lags + 1):
        s += 2.0 * (1.0 - j / (lags + 1.0)) * float(z[j:] @ z[:-j]) / n
    se = math.sqrt(s / n)
    return float(x.mean()), se, float(x.mean() / se)


def lw_point(ex1, ex2):
    """Ledoit-Wolf point estimate: Sharpe difference on population moments, annualised."""
    def sr(x):
        return x.mean() / math.sqrt((x ** 2).mean() - x.mean() ** 2)
    return float((sr(np.asarray(ex1)) - sr(np.asarray(ex2))) * SQ12)


def dsr(sr, n_obs, skew, kurt, n_trials, var_trials):
    g = 0.5772156649015329
    sr_star = math.sqrt(var_trials) * ((1 - g) * norm.ppf(1 - 1 / n_trials) + g * norm.ppf(1 - 1 / (n_trials * math.e)))
    den = math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr ** 2)
    psr = float(norm.cdf(sr * math.sqrt(n_obs - 1) / den))
    d = float(norm.cdf((sr - sr_star) * math.sqrt(n_obs - 1) / den))
    return sr_star, psr, d


# ----------------------------------------------------------------------------- reviewer's own engine (§6, §9.1)
def tiingo_tri(symbol):
    df = pd.read_csv(RAW / f"tiingo_{symbol}_daily.csv", parse_dates=["date"]).set_index("date").sort_index()
    c = df["adjClose"].astype(float).dropna()
    return (c / c.iloc[0]).rename(symbol)


def cash_index_dtb3():
    """§5.2 accrual: bey_s = 365 d/(360 - 91 d) at the previous valid observation, r = (bey - expense) days/365."""
    raw = pd.read_csv(RAW / "fred_DTB3.csv")
    raw.columns = ["date", "dtb3"]
    raw["date"] = pd.to_datetime(raw["date"])
    raw["dtb3"] = pd.to_numeric(raw["dtb3"], errors="coerce")
    v = raw.dropna().set_index("date")["dtb3"].astype(float) / 100.0
    d_prev = v.to_numpy()[:-1]
    bey = 365.0 * d_prev / (360.0 - 91.0 * d_prev)
    days = np.diff(v.index.to_numpy()).astype("timedelta64[D]").astype(float)
    r = (bey - BIL_EXPENSE) * days / 365.0
    return pd.Series(np.concatenate([[1.0], np.cumprod(1.0 + r)]), index=v.index, name="cash")


def month_ends(bars, start, end):
    s = pd.Series(bars, index=bars)
    last = pd.DatetimeIndex(s.groupby([bars.year, bars.month]).max().to_numpy())
    return last[(last >= pd.Timestamp(start)) & (last <= pd.Timestamp(end))]


def make_schedule(bars, sig, end_at_last_bar=False):
    pos = bars.searchsorted(sig.to_numpy(), side="right")
    exe = pd.DatetimeIndex([bars[p] if p < len(bars) else pd.NaT for p in pos])
    out = pd.DataFrame({"signal_date": sig, "execution_date": exe})
    out["period_end"] = out["execution_date"].shift(-1)
    if end_at_last_bar and pos[-1] >= len(bars):
        out.loc[out.index[-2], "period_end"] = bars[-1]
    return out


def lookback_bar(t, months, asset_bars):
    target = (pd.Timestamp(t).to_period("M") - months).to_timestamp(how="end").normalize()
    cand = asset_bars[asset_bars <= target]
    if len(cand) == 0 or cand[-1].to_period("M") != target.to_period("M"):
        return None
    return cand[-1]


def level(tri, dates):
    return tri.reindex(pd.DatetimeIndex(dates), method="ffill").to_numpy()


def signal_frames(prices, cash, universe, sig):
    """s12, s6, s3 (1/0, NaN before entry), vol (annualised 63-day std), present."""
    out = {k: pd.DataFrame(np.nan, index=sig, columns=universe) for k in ("s12", "s6", "s3", "vol")}
    for a in universe:
        tri = prices[a].dropna()
        ab = tri.index
        for t in sig:
            if t not in ab:
                continue
            t12 = lookback_bar(t, 12, ab)
            if t12 is None:
                continue
            hist = tri[ab <= t]
            if len(hist) < VOL_WINDOW + 1:
                continue
            r = hist.iloc[-(VOL_WINDOW + 1):].to_numpy()
            r = r[1:] / r[:-1] - 1.0
            out["vol"].at[t, a] = float(np.std(r, ddof=1) * SQ252)
            for key, L in (("s12", 12), ("s6", 6), ("s3", 3)):
                tl = lookback_bar(t, L, ab)
                c0, c1 = level(cash, [tl, t])
                mom = tri.loc[t] / tri.loc[tl] - c1 / c0
                out[key].at[t, a] = 1.0 if mom > 0 else 0.0
    out["present"] = out["s12"].notna()
    return out


def target_weights(sig_row, vol_row):
    present = [a for a in sig_row.index if not np.isnan(sig_row[a])]
    n = len(present)
    w = {a: float(sig_row[a]) * min(SIGMA_A / (n * vol_row[a]), W_CAP) for a in present}
    tot = sum(w.values())
    if tot > 1.0:
        w = {a: v / tot for a, v in w.items()}
    return w


def run_engine(prices, cash, sched, weights, costs):
    """§6.3-§6.4: drift inside the period, trade to target at the next execution close,
    cost = sum |target - drifted| x c_i on the pre-trade value.  Index values are
    taken as of the last observation on or before each date."""
    assets = list(prices.columns)
    full = pd.concat([prices, cash.rename("cash")], axis=1, sort=True).ffill()
    vals = {c: full[c].to_numpy() for c in full.columns}
    fidx = full.index

    def at(col, date):
        return vals[col][fidx.searchsorted(date, side="right") - 1]

    drifted = {a: 0.0 for a in assets}
    recs = []
    for _, row in sched.iloc[:-1].iterrows():
        t, e, e_next = row["signal_date"], row["execution_date"], row["period_end"]
        target = {a: float(weights.get(t, {}).get(a, 0.0)) for a in assets}
        turnover = sum(abs(target[a] - drifted[a]) for a in assets)
        cost = sum(abs(target[a] - drifted[a]) * costs[a] for a in assets)
        ar = {a: at(a, e_next) / at(a, e) - 1.0 for a in assets if target[a] != 0.0}
        cr = at("cash", e_next) / at("cash", e) - 1.0
        ge = sum(target.values())
        gross = sum(target[a] * ar[a] for a in ar) + (1.0 - ge) * cr
        net = (1.0 - cost) * (1.0 + gross) - 1.0
        drifted = {a: (target[a] * (1.0 + ar[a]) / (1.0 + gross) if a in ar else 0.0) for a in assets}
        rec = {"signal_date": t, "gross": gross, "cost": cost, "net": net, "gross_exposure": ge, "turnover": turnover}
        rec.update({f"w_{a}": target[a] for a in assets})
        recs.append(rec)
    return pd.DataFrame(recs).set_index("signal_date")


def daily_levels(result, sched, prices, cash):
    full = pd.concat([prices, cash.rename("cash")], axis=1, sort=True).ffill()
    assets = list(prices.columns)
    lvl, pieces = 1.0, []
    for _, row in sched.iloc[:-1].iterrows():
        t, e, e_next = row["signal_date"], row["execution_date"], row["period_end"]
        w = {a: result.at[t, f"w_{a}"] for a in assets}
        base = full.reindex([e], method="ffill").iloc[0]
        win = full.loc[e:e_next]
        rel = sum(w[a] * win[a] / base[a] for a in assets if w[a] != 0.0) + (1.0 - sum(w.values())) * win["cash"] / base["cash"]
        rel = rel.loc[rel.index > e]
        lvl *= 1.0 - result.at[t, "cost"]
        piece = lvl * rel
        pieces.append(piece)
        lvl = float(piece.iloc[-1])
    return pd.concat(pieces)


def period_asset_returns(prices, cash, sched):
    full = pd.concat([prices, cash.rename("cash")], axis=1, sort=True).ffill()
    out = {}
    for _, row in sched.iloc[:-1].iterrows():
        s = full.reindex([row["execution_date"]], method="ffill").iloc[0]
        e = full.reindex([row["period_end"]], method="ffill").iloc[0]
        out[row["signal_date"]] = e / s - 1.0
    return pd.DataFrame(out).T


def rebuild_window(window, universe, prices, cash, sched, k_frozen, multiple=1.0, table=None):
    """Every strategy for one window/universe/cost multiple from raw data: (results, signals, table, k)."""
    if table is None:
        table = signal_frames(prices, cash, universe, pd.DatetimeIndex(sched["signal_date"]))
    sigs = {}
    for t in TRIALS:
        s = sum(table[f"s{L}"] for L in LOOKBACKS[t]) / len(LOOKBACKS[t])
        sigs[t] = s.where(table["present"])
    ones = table["present"].astype(float).where(table["present"])
    assets = list(prices.columns)
    costs = {a: COST_BP[a] * 1e-4 * multiple for a in assets}
    weights = {t: {d: target_weights(sigs[t].loc[d], table["vol"].loc[d]) for d in sigs[t].index} for t in TRIALS}
    weights["B3"] = {d: target_weights(ones.loc[d], table["vol"].loc[d]) for d in ones.index}
    weights["B1"] = {d: ({a: 1.0 / int(table["present"].loc[d].sum()) for a in universe if table["present"].at[d, a]})
                     for d in table["present"].index}
    weights["B0"] = {d: {} for d in table["present"].index}
    weights["B2"] = {d: {"SPY": 0.6, "IEF": 0.4} for d in table["present"].index}
    results = {n: run_engine(prices, cash, sched, weights[n], costs) for n in ("B0", "B1", "B2", "B3", *TRIALS)}
    k = k_frozen
    if k is None:
        ratio = results["T1"]["gross_exposure"] / results["B3"]["gross_exposure"]
        k = float(ratio.replace([np.inf, -np.inf], np.nan).dropna().mean())
    weights["B4"] = {d: {a: v * k for a, v in w.items()} for d, w in weights["B3"].items()}
    results["B4"] = run_engine(prices, cash, sched, weights["B4"], costs)
    return results, sigs, table, k


# ----------------------------------------------------------------------------- committed files
def load(window, n):
    tag = f"{n}assets"
    monthly = pd.read_csv(RES / window / f"monthly_{tag}_base.csv", index_col=0, parse_dates=True)
    monthly["execution_date"] = pd.to_datetime(monthly["execution_date"])
    monthly["period_end"] = pd.to_datetime(monthly["period_end"])
    stress = pd.read_csv(RES / window / f"monthly_{tag}_stress.csv", index_col=0, parse_dates=True)
    met = pd.read_csv(RES / window / f"metrics_{tag}_base.csv", index_col=0)
    met_s = pd.read_csv(RES / window / f"metrics_{tag}_stress.csv", index_col=0)
    t1p = pd.read_csv(RES / window / f"t1_periods_{tag}_base.csv", index_col=0, parse_dates=True)
    daily = pd.read_csv(RES / window / f"daily_index_{tag}.csv", index_col=0, parse_dates=True)
    sig = {key: pd.read_csv(RES / window / f"signal_{key}_{tag}.csv", index_col=0, parse_dates=True) for key in ("s12", "s6", "s3", "vol")}
    vfr = pd.read_csv(RES / window / f"vol_forecast_vs_realised_T1_{tag}.csv", index_col=0, parse_dates=True)
    summ = json.loads((RES / window / "summary.json").read_text(encoding="utf-8"))
    run = summ["runs"]["ten" if n == 10 else "nine_without_IEF"]
    return dict(monthly=monthly, stress=stress, met=met, met_s=met_s, t1p=t1p, daily=daily, sig=sig, vfr=vfr, summ=summ, run=run)


def descriptive_block(label, monthly, met, base, n):
    """§9.3 items 1-4, 6, 11 for every strategy from the committed monthly file."""
    b0 = monthly["B0"].to_numpy()
    out = {}
    for s in STRATS:
        r = monthly[s].to_numpy()
        ex = r - b0
        d = base["descriptive"][s]
        add(f"{label} {s} ann. geometric return", met.at[s, "ann_geometric_return"], geo_annual(r), 1e-9, "{:.4%}")
        add(f"{label} {s} ann. volatility", met.at[s, "ann_volatility"], vol_annual(r), 1e-9, "{:.4%}")
        add(f"{label} {s} Sharpe (annual, excess over B0)", met.at[s, "sharpe_annual"], sharpe_m(ex) * SQ12, 1e-8)
        add(f"{label} {s} max drawdown (monthly)", met.at[s, "max_drawdown_monthly"], max_dd(np.cumprod(1 + r)), 1e-9, "{:.2%}")
        add(f"{label} {s} hit rate (excess > 0)", met.at[s, "hit_rate_positive_excess"], float((ex > 0).mean()), 1e-9)
        if s != "B0":
            sk, ku = skew_kurt(ex)
            add(f"{label} {s} skewness of excess", met.at[s, "skewness_excess"], sk, 1e-8, "{:.3f}")
            add(f"{label} {s} kurtosis of excess (non-excess)", met.at[s, "kurtosis_excess"], ku, 1e-8, "{:.3f}")
        add(f"{label} {s} summary.json descriptive equals metrics CSV (Sharpe)", d["sharpe_annual"], met.at[s, "sharpe_annual"], 1e-12, "{:.6f}")
        out[s] = {"ex": ex, "sr_m": sharpe_m(ex)}
    return out


def inference_block(label, monthly, base, srs, n):
    """§9.3 items 7 (Newey-West, 6 lags), 9 (Ledoit-Wolf point estimate) and §9.4 (PSR, DSR)."""
    b0 = monthly["B0"].to_numpy()
    for t in TRIALS:
        for bench in ("B3", "B4"):
            d = monthly[t].to_numpy() - monthly[bench].to_numpy()
            mean, se, tt = nw_mean_t(d)
            pub = base["inference"][t][f"vs_{bench}"]["newey_west"]
            add(f"{label} {t}-{bench} Newey-West lags published", 6, pub["lags"], 0, "{:d}")
            add(f"{label} mean({t}-{bench}) monthly", pub["mean"], mean, 1e-12, "{:+.6f}")
            add(f"{label} Newey-West t of {t}-{bench} (6 Bartlett lags, hand-coded)", pub["t"], tt, 5e-5)
            add(f"{label} Ledoit-Wolf Sharpe difference {t}-{bench}, annualised point estimate",
                base["inference"][t][f"vs_{bench}"]["ledoit_wolf"]["diff_annual"], lw_point(monthly[t] - b0, monthly[bench] - b0), 1e-8, "{:+.4f}")
    srs4 = [srs[t]["sr_m"] for t in TRIALS]
    var4 = float(np.var(srs4, ddof=0))
    floored = var4 < DSR_FLOOR
    v_used = DSR_FLOOR if floored else var4
    add(f"{label} variance of monthly Sharpe across T1-T4 (ddof=0; floor applied if below {DSR_FLOOR:.6f})",
        base["deflation_inputs"]["variance_across_trials"], v_used, 1e-12, "{:.8f}")
    add(f"{label} DSR floor applied", base["deflation_inputs"]["floor_applied"], bool(floored))
    for t in TRIALS:
        sk, ku = skew_kurt(srs[t]["ex"])
        for N in (4, 10):
            sr_star, psr, d = dsr(srs[t]["sr_m"], n, sk, ku, N, v_used)
            pub = base["deflated_sharpe"][t][f"N{N}"]
            add(f"{label} {t} SR* (monthly) N={N}", pub["sr_star_monthly"], sr_star, 1e-10, "{:.6f}")
            add(f"{label} {t} DSR N={N}", pub["dsr"], d, 1e-8)
        add(f"{label} {t} PSR", base["deflated_sharpe"][t]["N4"]["psr"], dsr(srs[t]["sr_m"], n, sk, ku, 4, v_used)[1], 1e-8)


def switches(sig_frame):
    return {a: int((sig_frame[a].dropna().diff().abs() > 1e-12).sum()) for a in sig_frame.columns}


# ----------------------------------------------------------------------------- main
def main() -> int:
    have_raw = all((RAW / f).exists() for f in ["fred_DTB3.csv"] + [f"tiingo_{s}_daily.csv" for s in
                   ("IWM", "EFA", "EEM", "SHY", "IEF", "TLT", "LQD", "HYG", "GLD", "VNQ", "SPY", "BIL")])
    universe10 = ["IWM", "EFA", "EEM", "SHY", "IEF", "TLT", "LQD", "HYG", "GLD", "VNQ"]
    universe9 = [a for a in universe10 if a != "IEF"]
    k_frozen = {}
    raw = {}
    if have_raw:
        prices = pd.concat([tiingo_tri(s) for s in universe10 + ["SPY"]], axis=1, sort=True)
        raw["prices"] = prices
        raw["cash_is"] = cash_index_dtb3()
        raw["cash_oos"] = tiingo_tri("BIL").rename("cash")
        bars = prices[universe10].dropna(how="all").index
        raw["sched_is"] = make_schedule(bars, month_ends(bars, "2003-12-31", pd.Period("2018-12", "M").to_timestamp(how="end").normalize()))
        last_bar = min(min(prices[c].last_valid_index() for c in universe10), raw["cash_oos"].last_valid_index())
        add("OOS common last bar of the ten assets and BIL (summary.json common_last_bar)",
            json.loads((RES / "oos" / "summary.json").read_text())["common_last_bar"], str(last_bar.date()))
        bars_o = bars[bars <= last_bar]
        raw["sched_oos"] = make_schedule(bars_o, month_ends(bars_o, pd.Period("2018-12", "M").to_timestamp(how="start"),
                                                            pd.Period("2026-09", "M").to_timestamp(how="end").normalize()), end_at_last_bar=True)
    else:
        rows.append(("Raw vendor files", "n/a", "absent", "not checked (data/raw/ missing)"))

    criteria = {}
    for window, wl in (("insample", "IS"), ("oos", "OOS")):
        for n, uni in ((10, universe10), (9, universe9)):
            label = f"{wl}{n}"
            f = load(window, n)
            monthly, met, run, t1p = f["monthly"], f["met"], f["run"], f["t1p"]
            base, stress = run["cost_cases"]["base"], run["cost_cases"]["stress"]
            periods = len(monthly)
            add(f"{label} holding periods", run["holding_periods"], periods, 0, "{:d}")
            add(f"{label} first execution date", run["first_execution_date"], str(monthly["execution_date"].iloc[0].date()))
            add(f"{label} last period end", run["last_period_end"], str(monthly["period_end"].iloc[-1].date()))
            add(f"{label} period_end equals next row's execution_date", True,
                bool((monthly["period_end"].iloc[:-1].to_numpy() == monthly["execution_date"].iloc[1:].to_numpy()).all()))
            years = periods / 12.0
            # descriptive and inference from the committed monthly file
            srs = descriptive_block(label, monthly, met, base, n)
            inference_block(label, monthly, base, srs, periods)
            # T1 period file: net = (1-cost)(1+gross)-1, exposure = sum w, turnover, mean cost
            wcols = [c for c in t1p.columns if c.startswith("w_")]
            add(f"{label} T1 net = (1-cost)(1+gross)-1 every period (max abs diff)", 0.0,
                float(np.abs((1 - t1p["cost"]) * (1 + t1p["gross"]) - 1 - t1p["net"]).max()), 1e-14, "{:.1e}")
            add(f"{label} T1 net in period file equals monthly file (max abs diff)", 0.0,
                float(np.abs(t1p["net"].to_numpy() - monthly["T1"].to_numpy()).max()), 1e-14, "{:.1e}")
            add(f"{label} T1 gross exposure equals sum of weights (max abs diff)", 0.0,
                float(np.abs(t1p[wcols].sum(axis=1) - t1p["gross_exposure"]).max()), 1e-12, "{:.1e}")
            add(f"{label} T1 weights never exceed the 25% cap or sum above one", True,
                bool((t1p[wcols].max(axis=1) <= 0.25 + 1e-12).all() and (t1p["gross_exposure"] <= 1 + 1e-12).all()))
            add(f"{label} T1 ann. one-way turnover", met.at["T1", "ann_one_way_turnover"], float(t1p["turnover"].sum() / years), 1e-10, "{:.4f}")
            add(f"{label} T1 mean gross exposure", met.at["T1", "mean_gross_exposure"], float(t1p["gross_exposure"].mean()), 1e-10)
            add(f"{label} T1 mean cost per month", met.at["T1", "mean_cost_monthly"], float(t1p["cost"].mean()), 1e-14, "{:.3e}")
            add(f"{label} T1 assets on per month (monthly file) equals count of positive weights", True,
                bool(((t1p[wcols] > 0).sum(axis=1).to_numpy() == monthly["T1_assets_on"].to_numpy()).all()))
            add(f"{label} T1 months fully in cash (no asset on)", None, int((monthly["T1_assets_on"] == 0).sum()), fmt="{:d}")
            # switches from the committed signal files (T4: any change of the 0, 1/3, 2/3, 1 level)
            for t in TRIALS:
                s = sum(f["sig"][f"s{L}"] for L in LOOKBACKS[t]) / len(LOOKBACKS[t])
                sw = switches(s)
                add(f"{label} {t} on/off switches (from signal CSVs)", base["descriptive"][t]["switches_total"], sum(sw.values()), 0, "{:d}")
            add(f"{label} power statement label", base["power_statement"]["label"],
                "as registered" if sum(switches(f["sig"]["s12"]).values()) >= 40 else "low-powered")
            # T1 weights reproduce from the committed signals and volatilities (§6.2)
            w_rec = pd.DataFrame({d: target_weights(f["sig"]["s12"].loc[d], f["sig"]["vol"].loc[d]) for d in t1p.index}).T.reindex(columns=uni).fillna(0.0)
            add(f"{label} T1 weights reproduce from signal_s12 and signal_vol by §6.2 (max abs diff)", 0.0,
                float(np.abs(w_rec.to_numpy() - t1p[[f"w_{a}" for a in uni]].to_numpy()).max()), 1e-12, "{:.1e}")
            # B3 exposure and k from the same files
            ones = f["sig"]["s12"].notna().astype(float).where(f["sig"]["s12"].notna())
            b3_ge = pd.Series({d: sum(target_weights(ones.loc[d], f["sig"]["vol"].loc[d]).values()) for d in t1p.index})
            k_rec = float((t1p["gross_exposure"] / b3_ge).mean())
            if window == "insample":
                k_frozen[n] = k_rec
                add(f"{label} k = mean(T1 gross exposure / B3 gross exposure) (summary k_exposure_ratio)", run["k_exposure_ratio"], k_rec, 1e-10)
                add(f"{label} B3 mean gross exposure", met.at["B3", "mean_gross_exposure"], float(b3_ge.mean()), 1e-10)
                add(f"{label} B4 mean gross exposure = k x B3's", met.at["B4", "mean_gross_exposure"], float(k_rec * b3_ge.mean()), 1e-10)
            else:
                add(f"{label} OOS k is the frozen in-sample k", run["k_frozen_from_insample"], k_frozen[n], 1e-12)
                add(f"{label} B4 mean gross exposure = frozen k x B3's", met.at["B4", "mean_gross_exposure"], float(k_frozen[n] * b3_ge.mean()), 1e-10)
            k = run["k_exposure_ratio"]
            # B4 = k x B3 with the remainder in cash: gross returns satisfy B4 = k B3 + (1-k) B0 exactly; costs scale almost exactly with k
            resid = monthly["B4"] - (k * monthly["B3"] + (1 - k) * monthly["B0"])
            add(f"{label} B4 - [k B3 + (1-k) B0] (net; max abs, should be of the order of the cost difference)", 0.0, float(resid.abs().max()), 2e-5, "{:.1e}")
            slope = float(np.polyfit((monthly["B3"] - monthly["B0"]).to_numpy(), (monthly["B4"] - monthly["B0"]).to_numpy(), 1)[0])
            add(f"{label} k recovered by regressing B4-B0 on B3-B0", k, slope, 1e-3)
            add(f"{label} Sharpe(B4) - Sharpe(B3) (identical by construction up to cost)", 0.0,
                float(met.at["B4", "sharpe_annual"] - met.at["B3", "sharpe_annual"]), 1e-4, "{:+.6f}")
            # daily drawdowns from the committed daily index
            for s in STRATS:
                add(f"{label} {s} max drawdown (daily index as published)", base["max_drawdown_daily"][s], max_dd(f["daily"][s].to_numpy()), 1e-12, "{:.2%}")
            add(f"{label} T1 daily drawdown with a 1.0 start prepended (reviewer's variant)", None,
                max_dd(np.concatenate([[1.0], f["daily"]["T1"].to_numpy()])), fmt="{:.2%}")
            # daily index at each period end reproduces the compounded monthly net return
            lv = f["daily"]["T1"].reindex(monthly["period_end"], method="ffill").to_numpy()
            add(f"{label} T1 daily index at period ends = compounded monthly net (max abs diff)", 0.0,
                float(np.abs(lv - np.cumprod(1 + monthly["T1"].to_numpy())).max()), 1e-10, "{:.1e}")
            # vol forecast vs realised from the committed series and from weights x vol
            vfr = f["vfr"]
            fc = np.sqrt(sum((t1p[f"w_{a}"] ** 2) * (f["sig"]["vol"][a].reindex(t1p.index).fillna(0.0) ** 2) for a in uni))
            real = monthly["T1"].rolling(12).std(ddof=1) * SQ12
            both = pd.DataFrame({"forecast": fc, "realised": real}).dropna()
            both = both[both["forecast"] > 0]
            ratio = both["realised"] / both["forecast"]
            v = base["vol_forecast_vs_realised"]["T1"]
            add(f"{label} T1 vol forecast months compared", v["months_compared"], len(both), 0, "{:d}")
            add(f"{label} T1 vol forecast series equals committed CSV (max abs diff, forecast and realised)", 0.0,
                float(max(np.abs(both["forecast"].to_numpy() - vfr["forecast"].to_numpy()).max(),
                          np.abs(both["realised"].to_numpy() - vfr["realised"].to_numpy()).max())), 1e-12, "{:.1e}")
            add(f"{label} T1 mean forecast / mean realised", v["mean_forecast"], float(both["forecast"].mean()), 1e-12, "{:.4%}")
            add(f"{label} T1 mean realised", v["mean_realised"], float(both["realised"].mean()), 1e-12, "{:.4%}")
            add(f"{label} T1 mean ratio realised/forecast", v["mean_ratio_realised_over_forecast"], float(ratio.mean()), 1e-10, "{:.3f}")
            add(f"{label} T1 share of months realised > 1.5x forecast", v["share_months_realised_over_1_5x_forecast"], float((ratio > 1.5).mean()), 1e-12, "{:.3f}")
            # stress file: C4 sign and stress Sharpe
            st = f["stress"]
            add(f"{label} stress mean(T1-B4) monthly", stress["inference"]["T1"]["vs_B4"]["newey_west"]["mean"], float((st["T1"] - st["B4"]).mean()), 1e-12, "{:+.6f}")
            for s in ("T1", "T2", "T3", "T4", "B3", "B4"):
                add(f"{label} {s} Sharpe at stress costs", f["met_s"].at[s, "sharpe_annual"], sharpe_m((st[s] - st["B0"]).to_numpy()) * SQ12, 1e-8)
            # criteria as §9.5 states, from the recomputed numbers
            sh = lambda s: sharpe_m(srs[s]["ex"]) * SQ12
            if window == "insample":
                c1 = sh("T1") >= sh("B4") + 0.10 and sh("T1") >= sh("B3") + 0.10
                c2 = nw_mean_t(monthly["T1"].to_numpy() - monthly["B4"].to_numpy())[2] >= 2.0
                sk, ku = skew_kurt(srs["T1"]["ex"])
                v_used = max(float(np.var([srs[t]["sr_m"] for t in TRIALS], ddof=0)), DSR_FLOOR) if float(np.var([srs[t]["sr_m"] for t in TRIALS], ddof=0)) < DSR_FLOOR else float(np.var([srs[t]["sr_m"] for t in TRIALS], ddof=0))
                c3 = dsr(srs["T1"]["sr_m"], periods, sk, ku, 4, v_used)[2] >= 0.95
                c4 = np.sign((monthly["T1"] - monthly["B4"]).mean()) == np.sign((st["T1"] - st["B4"]).mean())
                for name, val in (("C1", c1), ("C2", c2), ("C3", c3), ("C4", c4)):
                    add(f"{label} {name} (reviewer's application)", run["criteria"][name], bool(val))
                criteria[n] = {"C": [bool(c1), bool(c2), bool(c3), bool(c4)]}
                for t in ("T2", "T3", "T4"):
                    c1t = sh(t) >= sh("B4") + 0.10 and sh(t) >= sh("B3") + 0.10
                    c2t = nw_mean_t(monthly[t].to_numpy() - monthly["B4"].to_numpy())[2] >= 2.0
                    add(f"{label} {t} C1/C2", f"{run['criteria_T2_T4'][t]['C1']}/{run['criteria_T2_T4'][t]['C2']}", f"{bool(c1t)}/{bool(c2t)}")
                # sub-periods by holding-period start month
                em = monthly["execution_date"].dt.to_period("M")
                for name, (a, b) in SUBPERIODS.items():
                    m = (em >= pd.Period(a, "M")) & (em <= pd.Period(b, "M"))
                    seg = monthly[m]
                    pub = base["subperiods"][name]
                    add(f"{label} sub-period {name} months", pub["T1"]["periods"], int(m.sum()), 0, "{:d}")
                    for s in ("B1", "B3", "B4", "T1", "T2", "T3", "T4"):
                        r = seg[s].to_numpy()
                        add(f"{label} sub-period {name} {s} Sharpe", pub[s]["sharpe_annual"], sharpe_m(r - seg["B0"].to_numpy()) * SQ12, 1e-8, "{:.3f}")
                        add(f"{label} sub-period {name} {s} ann. return", pub[s]["ann_geometric_return"], geo_annual(r), 1e-9, "{:.2%}")
                        add(f"{label} sub-period {name} {s} max DD (monthly)", pub[s]["max_drawdown_monthly"], max_dd(np.cumprod(1 + r)), 1e-9, "{:.2%}")
                    add(f"{label} sub-period {name} T1 switches", pub["T1"]["switches_total"],
                        sum(switches(f["sig"]["s12"][f["sig"]["s12"].index.isin(seg.index)]).values()), 0, "{:d}")
            else:
                o1 = (monthly["T1"] - monthly["B4"]).mean() > 0
                o2 = sh("T1") > sh("B3")
                t_b4 = nw_mean_t(monthly["T1"].to_numpy() - monthly["B4"].to_numpy())[2]
                dd_clause = met.at["T1", "max_drawdown_monthly"] < met.at["B4", "max_drawdown_monthly"]
                add(f"{label} O1 (mean(T1-B4) > 0)", run["criteria"]["O1"], bool(o1))
                add(f"{label} O2 (Sharpe T1 > Sharpe B3)", run["criteria"]["O2"], bool(o2))
                add(f"{label} drawdown clause triggered (T1 monthly max DD worse than B4's)", False, bool(dd_clause))
                for t in ("T2", "T3", "T4"):
                    add(f"{label} {t} O1/O2", f"{run['criteria_T2_T4'][t]['O1']}/{run['criteria_T2_T4'][t]['O2']}",
                        f"{bool((monthly[t] - monthly['B4']).mean() > 0)}/{bool(sh(t) > sh('B3'))}")
                cs = criteria[n]["C"]
                if (not all(cs)) or ((not o1) and t_b4 <= -1.0) or dd_clause:
                    verdict = "not supported"
                elif o1 and o2:
                    verdict = "supported"
                else:
                    verdict = "inconclusive"
                add(f"{label} verdict for T1 by the §9.5 table (reviewer's application)", run["verdict_T1"], verdict)
                add(f"{label} 'not supported' follows from C1-C4 alone (precedence rule not needed)", True, bool(not all(cs)))
                add(f"{label} T1 DSR N=4 (descriptive)", None, base["deflated_sharpe"]["T1"]["N4"]["dsr"], fmt="{:.3f}")

            # ---------------- raw-data rebuild of the whole monthly table with the reviewer's engine
            if have_raw:
                prices_all = raw["prices"][uni + [s for s in ("IEF", "SPY") if s not in uni]]
                cash = raw["cash_is"] if window == "insample" else raw["cash_oos"]
                sched = raw["sched_is"] if window == "insample" else raw["sched_oos"]
                add(f"{label} schedule rebuilt from raw bars equals committed (signal, execution, period-end dates)", True,
                    bool((sched["signal_date"].iloc[:-1].to_numpy() == monthly.index.to_numpy()).all()
                         and (sched["execution_date"].iloc[:-1].to_numpy() == monthly["execution_date"].to_numpy()).all()
                         and (sched["period_end"].iloc[:-1].to_numpy() == monthly["period_end"].to_numpy()).all()))
                add(f"{label} signal date < execution date every period (no look-ahead in the schedule)", True,
                    bool((monthly.index < monthly["execution_date"]).all()))
                res, sigs, table, k_raw = rebuild_window(window, uni, prices_all, cash, sched, None if window == "insample" else k_frozen[n])
                for key in ("s12", "s6", "s3"):
                    pub = f["sig"][key].reindex(columns=uni)
                    same = (table[key].isna() == pub.isna()).all().all() and np.allclose(table[key].fillna(-1).to_numpy(), pub.fillna(-1).to_numpy())
                    add(f"{label} {key} signal recomputed from raw bars, all {len(pub)} signal dates x {len(uni)} assets", True, bool(same))
                add(f"{label} 63-day volatility recomputed from raw bars (max abs diff)", 0.0,
                    float(np.nanmax(np.abs(table["vol"].to_numpy() - f["sig"]["vol"].reindex(columns=uni).to_numpy()))), 1e-12, "{:.1e}")
                entry = {a: str(table["present"][a][table["present"][a]].index[0].date()) for a in uni}
                add(f"{label} entry signal dates from raw first bars", json.dumps(run["entry_signal_dates"], sort_keys=True), json.dumps(entry, sort_keys=True))
                if window == "insample":
                    add(f"{label} k from the rebuilt T1 and B3 exposures", run["k_exposure_ratio"], k_raw, 1e-10)
                for s in STRATS:
                    add(f"{label} {s} monthly net returns rebuilt from raw data (max abs diff vs committed)", 0.0,
                        float(np.abs(res[s]["net"].to_numpy() - monthly[s].to_numpy()).max()), 1e-12, "{:.1e}")
                dl = daily_levels(res["T1"], sched, prices_all, cash)
                add(f"{label} T1 daily index rebuilt from raw data (max abs diff vs committed)", 0.0,
                    float(np.abs(dl.reindex(f["daily"].index).to_numpy() - f["daily"]["T1"].to_numpy()).max()), 1e-10, "{:.1e}")
                # crisis table from the committed daily index and the raw SPY/IEF series
                for name, (a, b) in CRISIS[window].items():
                    pub = base["crisis_table"][name]
                    for s in ("T1", "B1", "B2", "B3", "B4"):
                        seg = f["daily"][s].loc[a:b]
                        add(f"{label} crisis {name} {s}", pub[s], float(seg.iloc[-1] / seg.iloc[0] - 1), 1e-12, "{:+.1%}")
                    for s in ("SPY", "IEF"):
                        seg = raw["prices"][s].dropna().loc[a:b]
                        add(f"{label} crisis {name} {s}", pub[s], float(seg.iloc[-1] / seg.iloc[0] - 1), 1e-12, "{:+.1%}")
                # correlations, attribution and per-asset Sharpe need the asset period returns
                ar = period_asset_returns(prices_all, cash, sched)
                for s in ("T1", "B3"):
                    ex = monthly[s] - monthly["B0"]
                    for ref in ("SPY", "IEF"):
                        add(f"{label} corr({s} excess, {ref} excess)", base["correlations"][s][ref],
                            float(ex.corr(ar[ref].reindex(ex.index) - ar["cash"].reindex(ex.index))), 1e-10, "{:.3f}")
                for s in ("T1", "B3"):
                    contrib = pd.DataFrame({a: res[s][f"w_{a}"] * ar[a].reindex(res[s].index).fillna(0.0) for a in uni})
                    port = contrib.sum(axis=1)
                    for a in uni:
                        pub = base["attribution"][s][a]
                        add(f"{label} attribution {s} {a} ann. return contribution", pub["ann_return_contribution"], float(contrib[a].mean() * 12), 1e-12, "{:+.2%}")
                        add(f"{label} attribution {s} {a} variance share", pub["variance_share"], float(contrib[a].cov(port) / port.var(ddof=1)), 1e-10, "{:.1%}")
                        add(f"{label} attribution {s} {a} asset-months on", pub["asset_months_on"], int((res[s][f"w_{a}"] > 0).sum()), 0, "{:d}")
                for a in uni:
                    present = res["B3"][f"w_{a}"] > 0
                    ex = ar[a].reindex(res["T1"].index) - ar["cash"].reindex(res["T1"].index)
                    pub = base["per_asset_sharpe"][a]
                    add(f"{label} {a} own long/flat Sharpe", pub["sharpe_long_flat"], sharpe_m((res["T1"][f"w_{a}"] * ex)[present].to_numpy()) * SQ12, 1e-8, "{:.2f}")
                    add(f"{label} {a} own always-on Sharpe", pub["sharpe_always_on"], sharpe_m((res["B3"][f"w_{a}"] * ex)[present].to_numpy()) * SQ12, 1e-8, "{:.2f}")
                # breakeven curve (k frozen): rerun T1 and B4 at each multiple
                curve = {}
                for mult in (0.0, 0.5, 1.0, 2.0, 3.0, 5.0):
                    r2, _, _, _ = rebuild_window(window, uni, prices_all, cash, sched, run["k_exposure_ratio"], mult, table)
                    c0 = r2["B0"]["net"]
                    curve[mult] = sharpe_m((r2["T1"]["net"] - c0).to_numpy()) * SQ12 - sharpe_m((r2["B4"]["net"] - c0).to_numpy()) * SQ12
                    add(f"{label} breakeven curve Sharpe(T1)-Sharpe(B4) at {mult}x base cost",
                        run["breakeven_curve"]["sharpe_T1_minus_B4_by_multiple"][str(mult)], curve[mult], 1e-8, "{:+.4f}")
                xs = sorted(curve)
                zc = None
                for lo, hi in zip(xs[:-1], xs[1:]):
                    if curve[lo] * curve[hi] < 0:
                        zc = lo + (hi - lo) * curve[lo] / (curve[lo] - curve[hi])
                        break
                pub_zc = run["breakeven_curve"]["zero_crossing_multiple"]
                if zc is None or pub_zc is None:
                    add(f"{label} breakeven zero crossing (linear interpolation)", "None" if pub_zc is None else f"{pub_zc:.4f}",
                        "None" if zc is None else f"{zc:.4f}")
                else:
                    add(f"{label} breakeven zero crossing (linear interpolation)", pub_zc, zc, 1e-8, "{:.4f}")

    # ---------------- D1 overlap statistics (§5.3.2) from the raw vendor and broker files
    if have_raw:
        d1 = json.loads((RES / "checks" / "d1.json").read_text(encoding="utf-8"))
        for sym, rec in d1["symbols"].items():
            v = pd.read_csv(RAW / f"tiingo_{sym}_daily.csv", parse_dates=["date"]).set_index("date")["adjClose"].sort_index()
            b = pd.read_csv(RAW / f"alpaca_{sym}_1Day_all.csv", parse_dates=["date"]).set_index("date")["close"].sort_index()
            rv, rb = v.pct_change().dropna(), b.pct_change().dropna()
            rv, rb = rv.loc["2016-01-04":"2018-12-31"], rb.loc["2016-01-04":"2018-12-31"]
            common = rv.index.intersection(rb.index)
            diff = rv.loc[common] - rb.loc[common]
            add(f"D1 {sym} common return days", rec["overlap"]["common_return_days"], len(common), 0, "{:d}")
            add(f"D1 {sym} annualised mean daily difference vendor-broker (x252)", rec["check"]["mean_diff_annual_vendor_minus_broker"], float(diff.mean() * 252), 1e-10, "{:+.4%}")
            add(f"D1 {sym} status by the ±0.20% gate", rec["status"], "excluded" if abs(float(diff.mean() * 252)) > 0.002 else "pass")

    # ---------------- README numbers (typed in; compared at the README's rounding)
    fi, fo = load("insample", 10), load("oos", 10)
    fi9, fo9 = load("insample", 9), load("oos", 9)
    mi, mo, mi9, mo9 = fi["met"], fo["met"], fi9["met"], fo9["met"]
    bi, bo, bi9, bo9 = fi["run"]["cost_cases"]["base"], fo["run"]["cost_cases"]["base"], fi9["run"]["cost_cases"]["base"], fo9["run"]["cost_cases"]["base"]
    readme_is = {  # ann return %, vol %, Sharpe, MDD monthly %, MDD daily %, hit, turnover, exposure, skew, kurt
        "B1": (6.65, 9.74, 0.594, -26.5, -30.2, 0.628, 0.44, 1.00, 0.12, 11.4), "B2": (6.82, 8.90, 0.657, -30.3, -32.2, 0.650, 0.29, 1.00, -0.48, 6.9),
        "B3": (4.96, 4.32, 0.880, -8.3, -9.8, 0.628, 0.87, 0.95, -0.54, 3.4), "B4": (4.21, 3.47, 0.880, -6.6, -7.8, 0.628, 0.70, 0.76, -0.54, 3.4),
        "T1": (4.60, 3.90, 0.886, -5.2, -6.8, 0.644, 2.07, 0.76, -0.44, 3.9), "T2": (3.71, 3.57, 0.723, -6.1, -6.5, 0.628, 2.68, 0.70, -0.49, 4.5),
        "T3": (3.87, 3.57, 0.767, -6.3, -7.1, 0.633, 3.61, 0.67, -0.54, 4.2), "T4": (4.14, 3.55, 0.843, -5.1, -6.0, 0.639, 2.45, 0.73, -0.55, 4.2)}
    readme_oos = {
        "B1": (6.61, 10.10, 0.426, -19.6, -22.4, 0.581, 0.41, 1.00, -0.50, 4.6), "B2": (10.62, 10.92, 0.742, -18.8, -21.2, 0.645, 0.36, 1.00, -0.45, 4.0),
        "B3": (3.75, 6.43, 0.200, -13.8, -15.5, 0.548, 1.01, 0.95, -0.62, 4.7), "B4": (3.57, 5.17, 0.200, -11.1, -12.4, 0.548, 0.81, 0.76, -0.62, 4.7),
        "T1": (3.95, 4.04, 0.336, -4.1, -11.4, 0.538, 2.16, 0.63, -0.76, 4.6), "T2": (3.74, 3.85, 0.294, -4.2, -11.1, 0.527, 3.20, 0.62, -0.33, 4.8),
        "T3": (3.33, 3.68, 0.197, -6.7, -7.2, 0.505, 4.39, 0.59, -0.40, 4.8), "T4": (3.80, 3.67, 0.322, -4.6, -10.1, 0.559, 2.81, 0.63, -0.40, 3.9)}
    for wl, met, base, tab in (("IS10", mi, bi, readme_is), ("OOS10", mo, bo, readme_oos)):
        for s, (ret, vol, shp, mdm, mdd, hit, to, ge, sk, ku) in tab.items():
            add_readme(f"{wl} {s} ann. return %", ret, met.at[s, "ann_geometric_return"], 2, 0.01)
            add_readme(f"{wl} {s} ann. vol %", vol, met.at[s, "ann_volatility"], 2, 0.01)
            add_readme(f"{wl} {s} Sharpe", shp, met.at[s, "sharpe_annual"], 3)
            add_readme(f"{wl} {s} max DD monthly %", mdm, met.at[s, "max_drawdown_monthly"], 1, 0.01)
            add_readme(f"{wl} {s} max DD daily %", mdd, base["max_drawdown_daily"][s], 1, 0.01)
            add_readme(f"{wl} {s} hit rate", hit, met.at[s, "hit_rate_positive_excess"], 3)
            add_readme(f"{wl} {s} turnover p.a.", to, met.at[s, "ann_one_way_turnover"], 2)
            add_readme(f"{wl} {s} mean gross exposure", ge, met.at[s, "mean_gross_exposure"], 2)
            add_readme(f"{wl} {s} skew", sk, met.at[s, "skewness_excess"], 2)
            add_readme(f"{wl} {s} kurtosis", ku, met.at[s, "kurtosis_excess"], 1)
    for s, (ret, vol, shp, mdm, to, ge) in {"B1": (6.87, 10.84, 0.563, -30.1, 0.46, 1.00), "B3": (5.09, 4.72, 0.838, -9.5, 0.89, 0.93),
                                            "B4": (4.22, 3.68, 0.838, -7.3, 0.69, 0.72), "T1": (4.70, 4.05, 0.879, -5.4, 1.86, 0.72)}.items():
        add_readme(f"IS9 {s} ann. return %", ret, mi9.at[s, "ann_geometric_return"], 2, 0.01)
        add_readme(f"IS9 {s} ann. vol %", vol, mi9.at[s, "ann_volatility"], 2, 0.01)
        add_readme(f"IS9 {s} Sharpe", shp, mi9.at[s, "sharpe_annual"], 3)
        add_readme(f"IS9 {s} max DD monthly %", mdm, mi9.at[s, "max_drawdown_monthly"], 1, 0.01)
        add_readme(f"IS9 {s} turnover", to, mi9.at[s, "ann_one_way_turnover"], 2)
        add_readme(f"IS9 {s} exposure", ge, mi9.at[s, "mean_gross_exposure"], 2)
    for s, (ret, vol, shp, mdm, to, ge) in {"T2": (4.11, 3.76, 0.793, -5.9, 2.30, 0.67), "T3": (3.90, 3.67, 0.756, -6.4, 3.19, 0.64), "T4": (4.30, 3.69, 0.858, -5.2, 2.20, 0.68)}.items():
        add_readme(f"IS9 {s} ann. return %", ret, mi9.at[s, "ann_geometric_return"], 2, 0.01)
        add_readme(f"IS9 {s} ann. vol %", vol, mi9.at[s, "ann_volatility"], 2, 0.01)
        add_readme(f"IS9 {s} Sharpe", shp, mi9.at[s, "sharpe_annual"], 3)
        add_readme(f"IS9 {s} max DD monthly %", mdm, mi9.at[s, "max_drawdown_monthly"], 1, 0.01)
        add_readme(f"IS9 {s} turnover", to, mi9.at[s, "ann_one_way_turnover"], 2)
        add_readme(f"IS9 {s} exposure", ge, mi9.at[s, "mean_gross_exposure"], 2)
    for s, (ret, vol, shp, mdm, mdd, ge) in {"B1": (7.26, 10.85, 0.461, -20.1, -23.0, 1.00), "B3": (4.36, 6.96, 0.273, -13.3, -16.8, 0.93),
                                             "B4": (4.02, 5.42, 0.273, -10.3, -13.0, 0.72), "T1": (4.09, 4.43, 0.340, -6.0, -13.3, 0.62),
                                             "T2": (3.84, 4.27, 0.291, -5.5, -12.9, 0.61), "T3": (3.55, 3.84, 0.245, -6.1, -8.0, 0.58), "T4": (3.95, 3.97, 0.339, -4.7, -11.4, 0.61)}.items():
        add_readme(f"OOS9 {s} ann. return %", ret, mo9.at[s, "ann_geometric_return"], 2, 0.01)
        add_readme(f"OOS9 {s} ann. vol %", vol, mo9.at[s, "ann_volatility"], 2, 0.01)
        add_readme(f"OOS9 {s} Sharpe", shp, mo9.at[s, "sharpe_annual"], 3)
        add_readme(f"OOS9 {s} max DD monthly %", mdm, mo9.at[s, "max_drawdown_monthly"], 1, 0.01)
        add_readme(f"OOS9 {s} max DD daily %", mdd, bo9["max_drawdown_daily"][s], 1, 0.01)
        add_readme(f"OOS9 {s} exposure", ge, mo9.at[s, "mean_gross_exposure"], 2)
    # inference tables
    inf_is = {"T1": (0.44, 1.37, -0.00030, -0.48, 0.005, 0.98, 0.00033, 0.65, 0.005, 0.98, 0.00031, 0.59),
              "T2": (0.24, 1.25, -0.00102, -1.68, -0.158, 0.49, -0.00040, -0.78, -0.158, 0.48, -0.00043, -0.85),
              "T3": (0.30, 1.28, -0.00090, -1.53, -0.114, 0.54, -0.00027, -0.56, -0.114, 0.54, -0.00032, -0.68),
              "T4": (0.37, 1.37, -0.00068, -1.27, -0.038, 0.85, -0.00005, -0.12, -0.038, 0.84, -0.00009, -0.20)}
    inf_oos = {"T1": (-0.19, 0.88, 0.00006, 0.06, 0.137, 0.45, 0.00027, 0.35, 0.137, 0.46),
               "T2": (-0.34, 0.85, -0.00012, -0.10, 0.095, 0.69, 0.00009, 0.10, 0.095, 0.69),
               "T3": (-0.56, 1.01, -0.00046, -0.36, -0.003, 0.99, -0.00025, -0.24, -0.003, 0.99),
               "T4": (-0.35, 0.91, -0.00008, -0.07, 0.124, 0.56, 0.00013, 0.16, 0.124, 0.57)}
    for wl, base, tab, stress in (("IS10", bi, inf_is, fi["run"]["cost_cases"]["stress"]), ("OOS10", bo, inf_oos, None)):
        for t, vals in tab.items():
            inf = base["inference"][t]
            add_readme(f"{wl} {t} Sharpe CI low", vals[0], inf["sharpe_ci"]["ci_low"], 2)
            add_readme(f"{wl} {t} Sharpe CI high", vals[1], inf["sharpe_ci"]["ci_high"], 2)
            add_readme(f"{wl} {t} vs B3 NW mean", vals[2], inf["vs_B3"]["newey_west"]["mean"], 5)
            add_readme(f"{wl} {t} vs B3 NW t", vals[3], inf["vs_B3"]["newey_west"]["t"], 2)
            add_readme(f"{wl} {t} vs B3 LW diff", vals[4], inf["vs_B3"]["ledoit_wolf"]["diff_annual"], 3)
            add_readme(f"{wl} {t} vs B3 LW p", vals[5], inf["vs_B3"]["ledoit_wolf"]["p_value"], 2)
            add_readme(f"{wl} {t} vs B4 NW mean", vals[6], inf["vs_B4"]["newey_west"]["mean"], 5)
            add_readme(f"{wl} {t} vs B4 NW t", vals[7], inf["vs_B4"]["newey_west"]["t"], 2)
            add_readme(f"{wl} {t} vs B4 LW diff", vals[8], inf["vs_B4"]["ledoit_wolf"]["diff_annual"], 3)
            add_readme(f"{wl} {t} vs B4 LW p", vals[9], inf["vs_B4"]["ledoit_wolf"]["p_value"], 2)
            if stress is not None:
                add_readme(f"{wl} {t} stress vs B4 NW mean", vals[10], stress["inference"][t]["vs_B4"]["newey_west"]["mean"], 5)
                add_readme(f"{wl} {t} stress vs B4 NW t", vals[11], stress["inference"][t]["vs_B4"]["newey_west"]["t"], 2)
    for t, (psr, d4, d10) in {"T1": (0.999, 0.998, 0.998), "T2": (None, 0.991, 0.988), "T3": (None, 0.994, 0.992), "T4": (None, 0.997, 0.996)}.items():
        if psr is not None:
            add_readme(f"IS10 {t} PSR", psr, bi["deflated_sharpe"][t]["N4"]["psr"], 3)
        add_readme(f"IS10 {t} DSR N=4", d4, bi["deflated_sharpe"][t]["N4"]["dsr"], 3)
        add_readme(f"IS10 {t} DSR N=10", d10, bi["deflated_sharpe"][t]["N10"]["dsr"], 3)
    add_readme("IS10 variance of the four monthly Sharpes", 0.000337, bi["deflation_inputs"]["variance_across_trials"], 6)
    add_readme("OOS10 T1 PSR", 0.81, bo["deflated_sharpe"]["T1"]["N4"]["psr"], 2)
    add_readme("OOS10 T1 DSR N=4", 0.77, bo["deflated_sharpe"]["T1"]["N4"]["dsr"], 2)
    add_readme("OOS10 T1 DSR N=10", 0.75, bo["deflated_sharpe"]["T1"]["N10"]["dsr"], 2)
    for s, v in {"T1": 0.873, "B3": 0.876, "B4": 0.876, "T2": 0.705, "T3": 0.744, "T4": 0.827}.items():
        add_readme(f"IS10 {s} stress Sharpe", v, fi["met_s"].at[s, "sharpe_annual"], 3)
    for s, v in {"T1": 0.323, "B3": 0.196, "B4": 0.196, "T2": 0.274, "T3": 0.169, "T4": 0.304}.items():
        add_readme(f"OOS10 {s} stress Sharpe", v, fo["met_s"].at[s, "sharpe_annual"], 3)
    add_readme("k ten assets", 0.8018, fi["summ"]["k_exposure_ratio_frozen"], 4)
    add_readme("k nine assets", 0.7764, fi["summ"]["k_exposure_ratio_frozen_nine_without_IEF"], 4)
    add_readme("IS10 switches", 167, bi["descriptive"]["T1"]["switches_total"], 0)
    add_readme("IS9 switches", 150, bi9["descriptive"]["T1"]["switches_total"], 0)
    add_readme("OOS10 switches", 122, bo["descriptive"]["T1"]["switches_total"], 0)
    add_readme("IS9 T1 vs B4 NW mean", 0.00040, bi9["inference"]["T1"]["vs_B4"]["newey_west"]["mean"], 5)
    add_readme("IS9 T1 vs B4 NW t", 0.74, bi9["inference"]["T1"]["vs_B4"]["newey_west"]["t"], 2)
    add_readme("IS9 T1 vs B4 LW diff", 0.041, bi9["inference"]["T1"]["vs_B4"]["ledoit_wolf"]["diff_annual"], 3)
    add_readme("IS9 T1 vs B4 LW p", 0.85, bi9["inference"]["T1"]["vs_B4"]["ledoit_wolf"]["p_value"], 2)
    add_readme("IS9 T1 DSR N=4", 0.998, bi9["deflated_sharpe"]["T1"]["N4"]["dsr"], 3)
    add("IS9 DSR floor applied [README: applied]", True, bi9["deflation_inputs"]["floor_applied"])
    add_readme("IS9 C1 bar B3+0.10", 0.938, mi9.at["B3", "sharpe_annual"] + 0.10, 3)
    add_readme("OOS9 T1 vs B4 NW mean", 0.00002, bo9["inference"]["T1"]["vs_B4"]["newey_west"]["mean"], 5)
    add_readme("OOS9 T1 vs B4 NW t", 0.03, bo9["inference"]["T1"]["vs_B4"]["newey_west"]["t"], 2)
    add_readme("OOS9 T1 vs B3 NW mean", -0.00033, bo9["inference"]["T1"]["vs_B3"]["newey_west"]["mean"], 5)
    add_readme("OOS9 T1 vs B3 NW t", -0.33, bo9["inference"]["T1"]["vs_B3"]["newey_west"]["t"], 2)
    # crisis tables
    for s, v in {"T1": 2.4, "B1": -20.7, "B2": -24.4, "B3": -5.3, "B4": -4.2, "SPY": -41.4, "IEF": 6.4}.items():
        add_readme(f"IS10 GFC {s} %", v, bi["crisis_table"]["GFC 2008-09-01..2009-02-28"][s], 1, 0.01)
    for s, v in {"T1": 1.9, "B3": -6.5, "B4": -5.1}.items():
        add_readme(f"IS9 GFC {s} %", v, bi9["crisis_table"]["GFC 2008-09-01..2009-02-28"][s], 1, 0.01)
    oos_crisis = {"COVID 2020-02-19..2020-03-23": {"T1": -8.5, "B1": -16.9, "B2": -18.7, "B3": -11.8, "B4": -9.5, "SPY": -33.7, "IEF": 6.4},
                  "COVID 2020-02-19..2020-08-31": {"T1": -3.8, "B1": 3.3, "B2": 7.0, "B3": -4.0, "B4": -3.2, "SPY": 4.3, "IEF": 7.8},
                  "2022 2022-01-01..2022-10-31": {"T1": -3.1, "B1": -19.3, "B2": -17.0, "B3": -13.4, "B4": -10.8, "SPY": -18.2, "IEF": -16.1}}
    for name, tab in oos_crisis.items():
        for s, v in tab.items():
            add_readme(f"OOS10 crisis {name} {s} %", v, bo["crisis_table"][name][s], 1, 0.01)
    # correlations, vol forecast, breakeven, power, attribution
    for wl, base, tab in (("IS10", bi, {"T1": (0.30, 0.43), "B3": (0.54, 0.42)}), ("OOS10", bo, {"T1": (0.53, 0.33), "B3": (0.72, 0.60)})):
        for s, (c_spy, c_ief) in tab.items():
            add_readme(f"{wl} corr {s}-SPY", c_spy, base["correlations"][s]["SPY"], 2)
            add_readme(f"{wl} corr {s}-IEF", c_ief, base["correlations"][s]["IEF"], 2)
    vi, vo = bi["vol_forecast_vs_realised"], bo["vol_forecast_vs_realised"]
    add_readme("IS10 T1 mean forecast %", 2.4, vi["T1"]["mean_forecast"], 1, 0.01)
    add_readme("IS10 T1 mean realised %", 3.7, vi["T1"]["mean_realised"], 1, 0.01)
    add_readme("IS10 T1 mean ratio", 1.58, vi["T1"]["mean_ratio_realised_over_forecast"], 2)
    add_readme("IS10 T1 share > 1.5x %", 53, vi["T1"]["share_months_realised_over_1_5x_forecast"], 0, 0.01)
    add_readme("IS10 months compared", 169, vi["T1"]["months_compared"], 0)
    add_readme("IS10 B3 mean forecast %", 2.6, vi["B3"]["mean_forecast"], 1, 0.01)
    add_readme("IS10 B3 mean realised %", 4.2, vi["B3"]["mean_realised"], 1, 0.01)
    add_readme("IS10 B3 mean ratio", 1.61, vi["B3"]["mean_ratio_realised_over_forecast"], 2)
    add_readme("IS10 B3 share > 1.5x %", 54, vi["B3"]["share_months_realised_over_1_5x_forecast"], 0, 0.01)
    add_readme("OOS10 T1 mean ratio", 1.82, vo["T1"]["mean_ratio_realised_over_forecast"], 2)
    add_readme("OOS10 T1 months compared", 74, vo["T1"]["months_compared"], 0)
    add_readme("OOS10 T1 share > 1.5x %", 69, vo["T1"]["share_months_realised_over_1_5x_forecast"], 0, 0.01)
    add_readme("OOS10 B3 mean ratio", 2.32, vo["B3"]["mean_ratio_realised_over_forecast"], 2)
    add_readme("OOS10 B3 share > 1.5x %", 91, vo["B3"]["share_months_realised_over_1_5x_forecast"], 0, 0.01)
    bc = fi["run"]["breakeven_curve"]["sharpe_T1_minus_B4_by_multiple"]
    for m, v in {"0.0": 0.013, "0.5": 0.009, "1.0": 0.005, "2.0": -0.002, "3.0": -0.010, "5.0": -0.025}.items():
        add_readme(f"IS10 breakeven at {m}x", v, bc[m], 3)
    add_readme("IS10 breakeven zero crossing", 1.70, fi["run"]["breakeven_curve"]["zero_crossing_multiple"], 2)
    bc9 = fi9["run"]["breakeven_curve"]["sharpe_T1_minus_B4_by_multiple"]
    add_readme("IS9 breakeven at 0x", 0.047, bc9["0.0"], 3)
    add_readme("IS9 breakeven at 5x", 0.016, bc9["5.0"], 3)
    add("IS9 breakeven never crosses [README]", "None", str(fi9["run"]["breakeven_curve"]["zero_crossing_multiple"]))
    add_readme("IS10 T1 Sharpe advantage over B3 [README 'What did not work': 0.006]", 0.006, mi.at["T1", "sharpe_annual"] - mi.at["B3", "sharpe_annual"], 3)
    add_readme("IS10 T1 Sharpe advantage over B4 [README breakeven paragraph: +0.005]", 0.005, mi.at["T1", "sharpe_annual"] - mi.at["B4", "sharpe_annual"], 3)
    att = bi["attribution"]["T1"]
    for a, (c, vs, on) in {"IWM": (0.45, 10, 139), "EFA": (0.53, 12, 123), "EEM": (0.48, 10, 122), "SHY": (0.28, 2, 124), "IEF": (0.46, 11, 123),
                           "TLT": (0.31, 12, 123), "LQD": (0.50, 15, 124), "HYG": (0.38, 8, 97), "GLD": (0.40, 8, 98), "VNQ": (0.41, 12, 119)}.items():
        add_readme(f"IS10 attribution {a} contribution %", c, att[a]["ann_return_contribution"], 2, 0.01)
        add_readme(f"IS10 attribution {a} variance share %", vs, att[a]["variance_share"], 0, 0.01)
        add_readme(f"IS10 attribution {a} months on", on, att[a]["asset_months_on"], 0)
    add_readme("IS10 ten legs sum to 4.2% a year", 4.2, sum(v["ann_return_contribution"] for v in att.values()), 1, 0.01)
    pas = bi["per_asset_sharpe"]
    for a, (lf, ao) in {"EFA": (0.56, 0.43), "EEM": (0.54, 0.46), "SHY": (0.89, 0.67), "HYG": (0.66, 0.41), "IEF": (0.38, 0.50),
                        "TLT": (0.25, 0.49), "LQD": (0.45, 0.52), "VNQ": (0.49, 0.53)}.items():
        add_readme(f"IS10 {a} long/flat Sharpe", lf, pas[a]["sharpe_long_flat"], 2)
        add_readme(f"IS10 {a} always-on Sharpe", ao, pas[a]["sharpe_always_on"], 2)
    atto = bo["attribution"]["T1"]
    for a, c in {"GLD": 0.79, "EEM": 0.54, "HYG": 0.43, "EFA": 0.34, "LQD": 0.29, "SHY": 0.27, "IEF": 0.23, "TLT": 0.12, "IWM": -0.08, "VNQ": -0.08}.items():
        add_readme(f"OOS10 attribution {a} contribution %", c, atto[a]["ann_return_contribution"], 2, 0.01)
    for a, vs in {"HYG": 20, "VNQ": 16, "LQD": 15}.items():
        add_readme(f"OOS10 attribution {a} variance share %", vs, atto[a]["variance_share"], 0, 0.01)
    paso = bo["per_asset_sharpe"]
    for a, (lf, ao) in {"SHY": (0.44, -0.45), "IEF": (0.13, -0.27), "TLT": (0.13, -0.29), "LQD": (0.13, -0.13), "EEM": (0.67, 0.39),
                        "IWM": (-0.24, 0.22), "VNQ": (-0.17, 0.18), "EFA": (0.27, 0.44), "GLD": (0.76, 0.93), "HYG": (0.03, 0.13)}.items():
        add_readme(f"OOS10 {a} long/flat Sharpe", lf, paso[a]["sharpe_long_flat"], 2)
        add_readme(f"OOS10 {a} always-on Sharpe", ao, paso[a]["sharpe_always_on"], 2)
    subs = bi["subperiods"]
    readme_sub = {"2004-01..2008-12": {"B1": (0.34, 6.4, -26.0), "B3": (0.62, 5.8, -8.3), "B4": (0.62, 5.2, -6.6), "T1": (1.01, 7.0, -4.1), "T2": (0.59, 5.0, -4.2), "T3": (0.69, 5.4, -4.0), "T4": (0.83, 5.9, -4.1)},
                  "2009-01..2015-12": {"B1": (0.82, 7.7, -8.5), "B3": (1.16, 4.9, -5.5), "B4": (1.16, 3.9, -4.4), "T1": (1.13, 4.2, -4.0), "T2": (0.94, 3.3, -6.1), "T3": (0.90, 3.3, -5.6), "T4": (1.06, 3.7, -5.1)},
                  "2016-01..2018-12": {"B1": (0.70, 4.7, -5.3), "B3": (0.68, 3.7, -4.6), "B4": (0.68, 3.1, -3.7), "T1": (0.17, 1.6, -5.2), "T2": (0.45, 2.6, -4.1), "T3": (0.54, 2.5, -3.2), "T4": (0.36, 2.2, -4.2)}}
    for name, tab in readme_sub.items():
        for s, (shp, ret, mdd) in tab.items():
            add_readme(f"IS10 sub-period {name} {s} Sharpe", shp, subs[name][s]["sharpe_annual"], 2)
            add_readme(f"IS10 sub-period {name} {s} return %", ret, subs[name][s]["ann_geometric_return"], 1, 0.01)
            add_readme(f"IS10 sub-period {name} {s} max DD %", mdd, subs[name][s]["max_drawdown_monthly"], 1, 0.01)
    add_readme("IS10 T1 switches per asset per year, min (SHY 0.6)", 0.6, min(bi["descriptive"]["T1"]["switches_per_asset_per_year"].values()), 1)
    add_readme("IS10 T1 switches per asset per year, max (1.7)", 1.7, max(bi["descriptive"]["T1"]["switches_per_asset_per_year"].values()), 1)
    add_readme("OOS10 T1 return over bills 1.3% a year", 1.3, mo.at["T1", "ann_geometric_return"] - mo.at["B0", "ann_geometric_return"], 1, 0.01)
    add_readme("IS10 B0 ann. return 1.15%", 1.15, mi.at["B0", "ann_geometric_return"], 2, 0.01)
    add_readme("OOS10 B0 ann. return 2.65%", 2.65, mo.at["B0", "ann_geometric_return"], 2, 0.01)
    add("OOS10 no degenerate resample (every CI)", 0, sum(bo["inference"][t]["sharpe_ci"]["resamples_dropped_degenerate"] for t in TRIALS), 0, "{:d}")
    add("IS10 no degenerate resample (every CI)", 0, sum(bi["inference"][t]["sharpe_ci"]["resamples_dropped_degenerate"] for t in TRIALS), 0, "{:d}")
    add("Seed recorded in both summaries = 20261021", "20261021/20261021", f"{fi['summ']['provenance']['seed']}/{fo['summ']['provenance']['seed']}")
    add("Provenance commits (in-sample bff736c, out-of-sample 1697e9d)", "bff736c/1697e9d",
        f"{fi['summ']['provenance']['git_commit'][:7]}/{fo['summ']['provenance']['git_commit'][:7]}")

    # ---------------- print
    print("| # | Claim | Published | Recomputed | Match |")
    print("|---|---|---|---|---|")
    for i, (c, p, r, m) in enumerate(rows, 1):
        print(f"| {i} | {c} | {p} | {r} | {m} |")
    n_yes = sum(1 for r in rows if r[3].startswith("yes"))
    n_no = sum(1 for r in rows if r[3].startswith("NO"))
    n_other = len(rows) - n_yes - n_no
    print(f"\nRows: {len(rows)}; match: {n_yes}; mismatch: {n_no}; informational/not checked: {n_other}")
    if n_no:
        print("Mismatches:")
        for c, p, r, m in rows:
            if m.startswith("NO"):
                print(f"  - {c}: published {p}, recomputed {r}")
    return 1 if n_no else 0


if __name__ == "__main__":
    sys.exit(main())
