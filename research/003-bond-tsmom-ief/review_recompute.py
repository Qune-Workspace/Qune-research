"""Independent recomputation for REVIEW.md (Study 003, time-series momentum IEF vs BIL).

Written by the reviewer (Tester, a separate agent session that did not write the
code).  It uses none of the study's ``src/`` functions: every statistic below is
re-derived with numpy/pandas/scipy from

  * the committed monthly holding-period returns ``results/insample/monthly_base.csv``
    and ``results/oos/monthly_base.csv`` (columns month, execution_date, period_end,
    mom_at_signal, T1_holding, B0..B3, T1..T3), and
  * the raw daily files in ``data/raw/`` (git-ignored, must be present on disk):
    ``tiingo_IEF_daily.csv`` (adjClose), ``fred_DTB3.csv``, ``alpaca_IEF_1Day_all.csv``
    and ``alpaca_BIL_1Day_all.csv`` (close, adjustment='all').

It prints a comparison table (claim | published | recomputed | match) that
REVIEW.md reports.  "Published" values are read from ``results/*/metrics_base.csv``
and ``summary.json`` at full precision; numbers that exist only in README.md are
typed in below and marked README.  Nothing is written to disk.

Run from the study folder:  ../../.venv/bin/python review_recompute.py
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
COST = 2e-4                 # base cost per side (Study 001 §9.2)
BIL_EXPENSE = 0.001356      # §5.2
SQ12 = math.sqrt(12.0)
NW_LAGS = 6
STRATS = ("T1", "T2", "T3", "B1", "B2", "B3")

rows: list[tuple[str, str, str, str]] = []   # (claim, published, recomputed, match)


def add(claim: str, published, recomputed, tol: float | None = None, fmt: str = "{:.4f}", note: str = "") -> None:
    """Append a comparison row.  ``match`` is yes when |pub - rec| <= tol."""
    if published is None or (isinstance(published, float) and math.isnan(published)):
        rows.append((claim, "n/a", fmt.format(recomputed), "not checked" + (f" ({note})" if note else "")))
        return
    if isinstance(published, (str, bool, np.bool_)) or isinstance(recomputed, (str, bool, np.bool_)):
        ok = str(published) == str(recomputed)
        rows.append((claim, str(published), str(recomputed), "yes" if ok else "NO"))
        return
    ok = abs(float(published) - float(recomputed)) <= (tol if tol is not None else 0.0)
    rows.append((claim, fmt.format(published), fmt.format(recomputed), ("yes" if ok else "NO") + (f" ({note})" if note else "")))


# ----------------------------------------------------------------------------- helpers

def geo_annual(r: np.ndarray) -> float:
    return float(np.prod(1.0 + r) ** (12.0 / len(r)) - 1.0)


def vol_annual(r: np.ndarray) -> float:
    return float(np.std(r, ddof=1) * SQ12)


def sharpe_monthly(x: np.ndarray) -> float:
    return float(np.mean(x) / np.std(x, ddof=1))


def max_dd(levels: np.ndarray) -> float:
    peak = np.maximum.accumulate(levels)
    return float(np.min(levels / peak - 1.0))


def nw_mean_t(x: np.ndarray, lags: int = NW_LAGS) -> tuple[float, float, float]:
    """Mean, HAC (Bartlett kernel, ``lags`` lags) standard error and t, written
    out by hand (no statsmodels): S = g0 + 2 sum_j (1 - j/(L+1)) g_j, se = sqrt(S/n)."""
    n = len(x)
    z = x - x.mean()
    s = float(np.dot(z, z)) / n
    for j in range(1, lags + 1):
        s += 2.0 * (1.0 - j / (lags + 1.0)) * float(np.dot(z[j:], z[:-j])) / n
    se = math.sqrt(s / n)
    return float(x.mean()), se, float(x.mean() / se)


def dsr(sr: float, n_obs: int, skew: float, kurt: float, n_trials: int, var_trials: float) -> tuple[float, float, float]:
    """Study 001 §9.4 (Bailey and Lopez de Prado, 2014), monthly units, non-excess kurtosis."""
    g = 0.5772156649015329
    sr_star = math.sqrt(var_trials) * ((1 - g) * norm.ppf(1 - 1 / n_trials) + g * norm.ppf(1 - 1 / (n_trials * math.e)))
    den = math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr ** 2)
    psr = float(norm.cdf(sr * math.sqrt(n_obs - 1) / den))
    d = float(norm.cdf((sr - sr_star) * math.sqrt(n_obs - 1) / den))
    return sr_star, psr, d


def infer_holdings(df: pd.DataFrame, col: str) -> tuple[pd.Series, pd.Series]:
    """Recover the instrument held each month and whether a switch was charged,
    from the strategy return alone: r = f*(1+gross)-1 with gross = B1 (IEF, no
    cost) or B0 (BIL, no cost) and f = 1 (no trade) or (1-c)^2 (a switch)."""
    f_switch = (1.0 - COST) ** 2
    held, switched = [], []
    for _, row in df.iterrows():
        found = None
        for name, gross in (("IEF", row["B1"]), ("BIL", row["B0"])):
            f = (1.0 + row[col]) / (1.0 + gross)
            if abs(f - 1.0) < 1e-12:
                found = (name, False)
            elif abs(f - f_switch) < 1e-12:
                found = (name, True)
            if found:
                break
        if found is None:
            raise ValueError(f"{col} return in {row.name} is neither IEF nor BIL with or without a switch cost")
        held.append(found[0])
        switched.append(found[1])
    return pd.Series(held, index=df.index), pd.Series(switched, index=df.index)


def episodes(flags: pd.Series) -> list[tuple[str, str, int]]:
    out, start, prev = [], None, None
    for m, f in flags.items():
        if f and start is None:
            start = m
        if not f and start is not None:
            out.append((start, prev, len(flags.loc[start:prev])))
            start = None
        prev = m
    if start is not None:
        out.append((start, prev, len(flags.loc[start:prev])))
    return out


def cash_index_from_dtb3(path: Path) -> pd.Series:
    """§5.2 accrual, reviewer's own implementation: bey_s = 365 d/(360 - 91 d) at the
    previous valid observation s, r_t = (bey_s - expense) * days(s,t)/365."""
    raw = pd.read_csv(path)
    raw.columns = ["date", "dtb3"]
    raw["date"] = pd.to_datetime(raw["date"])
    raw["dtb3"] = pd.to_numeric(raw["dtb3"], errors="coerce")
    v = raw.dropna().set_index("date")["dtb3"] / 100.0
    d_prev = v.values[:-1]
    bey = 365.0 * d_prev / (360.0 - 91.0 * d_prev)
    days = np.diff(v.index.values).astype("timedelta64[D]").astype(float)
    r = (bey - BIL_EXPENSE) * days / 365.0
    tri = np.concatenate([[1.0], np.cumprod(1.0 + r)])
    return pd.Series(tri, index=v.index, name="cash")


def month_end_bars(idx: pd.DatetimeIndex) -> pd.Series:
    s = pd.Series(idx, index=idx)
    return s.groupby(idx.to_period("M")).last()


def level_at(tri: pd.Series, dates) -> np.ndarray:
    """Index level as of each date (last observation on or before it)."""
    return tri.reindex(pd.DatetimeIndex(dates), method="ffill").to_numpy()


def daily_strategy_levels(df: pd.DataFrame, holding: pd.Series, switched: pd.Series,
                          tri: dict[str, pd.Series]) -> pd.Series:
    """Daily total-return index of a switching strategy inside its holding periods:
    the held instrument's daily path from execution_date to period_end, the switch
    cost (1-c)^2 charged at the execution-date close."""
    pieces, level = [], 1.0
    for m, row in df.iterrows():
        held = tri[holding[m]]
        base = held.reindex([row["execution_date"]], method="ffill").iloc[0]
        path = held.loc[row["execution_date"]:row["period_end"]] / base
        if switched[m]:
            level *= (1.0 - COST) ** 2
        seg = level * path
        pieces.append(seg)
        level = float(seg.iloc[-1])
    out = pd.concat(pieces)
    return out[~out.index.duplicated(keep="last")]


# ----------------------------------------------------------------------------- load
def load(window: str):
    df = pd.read_csv(RES / window / "monthly_base.csv", index_col=0,
                     parse_dates=["execution_date", "period_end"])
    met = pd.read_csv(RES / window / "metrics_base.csv", index_col=0)
    summ = json.loads((RES / window / "summary.json").read_text(encoding="utf-8"))
    return df, met, summ


def recompute_window(window: str, label: str) -> dict:
    df, met, summ = load(window)
    base = summ["cost_cases"]["base"]
    n = len(df)
    add(f"{label}: holding periods", summ["holding_periods"], n, 0, "{:d}")
    out = {"n": n}
    b0 = df["B0"].to_numpy()
    srs = {}
    for s in STRATS:
        r = df[s].to_numpy()
        ex = r - b0
        geo, vol, sm = geo_annual(r), vol_annual(r), sharpe_monthly(ex)
        mdd = max_dd(np.cumprod(1.0 + r))
        add(f"{label} {s} ann. geometric return", met.at[s, "ann_geometric_return"], geo, 5e-7, "{:.4%}")
        add(f"{label} {s} ann. volatility", met.at[s, "ann_volatility"], vol, 5e-7, "{:.4%}")
        add(f"{label} {s} Sharpe (annual, excess over B0)", met.at[s, "sharpe_annual"], sm * SQ12, 5e-5, "{:.4f}")
        add(f"{label} {s} max drawdown (monthly)", met.at[s, "max_drawdown_monthly"], mdd, 5e-6, "{:.2%}")
        srs[s] = sm
        if s.startswith("T"):
            held, sw = infer_holdings(df, s)
            add(f"{label} {s} switches (inferred from returns, incl. initial BIL->target)", met.at[s, "switches"], int(sw.sum()), 0, "{:d}")
            add(f"{label} {s} fraction of months in IEF", met.at[s, "fraction_in_ief"], float((held == "IEF").mean()), 5e-7, "{:.4f}")
            add(f"{label} {s} hit rate (excess > 0)", met.at[s, "hit_rate_positive_excess"], float((ex > 0).mean()), 5e-7, "{:.4f}")
            out[s] = {"held": held, "switched": sw, "excess": ex}
    # T1 holding column vs inferred holding and vs sign of the signal
    t1h = df["T1_holding"]
    add(f"{label} T1_holding column equals holding inferred from T1 return (all months)", True, bool((t1h == out["T1"]["held"]).all()))
    add(f"{label} T1_holding == IEF iff mom_at_signal > 0 (all months)", True, bool(((df["mom_at_signal"] > 0) == (t1h == "IEF")).all()))
    add(f"{label} T1 switches counted as changes of T1_holding only (no initial trade)", None, int((t1h != t1h.shift()).sum() - 1), fmt="{:d}", note="informational")
    # timing differences
    for bench in ("B3", "B1"):
        d = df["T1"].to_numpy() - df[bench].to_numpy()
        mean, se, t = nw_mean_t(d)
        pub = base["inference"]["T1"][f"vs_{bench}"]["newey_west"]
        add(f"{label} mean(T1-{bench}) annualised (x12)", pub["mean"] * 12, mean * 12, 5e-7, "{:+.4%}")
        add(f"{label} Newey-West t (6 lags) of T1-{bench}", pub["t"], t, 5e-5, "{:.4f}")
    # Ledoit-Wolf point estimate (population-moment Sharpe difference, monthly), no bootstrap
    def sr_pop(x):
        return float(x.mean() / x.std(ddof=0))
    for bench in ("B3", "B1"):
        pub = base["inference"]["T1"][f"vs_{bench}"]["ledoit_wolf"]["diff_annual"]
        rec = (sr_pop(df["T1"] - df["B0"]) - sr_pop(df[bench] - df["B0"])) * SQ12
        add(f"{label} Ledoit-Wolf Sharpe difference T1-{bench}, annualised point estimate", pub, rec, 5e-5, "{:+.4f}")
    # deflated Sharpe at N = 3 and 10 from the three recomputed monthly Sharpes
    tri_sr = [srs["T1"], srs["T2"], srs["T3"]]
    var3 = float(np.var(tri_sr, ddof=0))
    ex1 = out["T1"]["excess"]
    z = (ex1 - ex1.mean()) / ex1.std(ddof=0)
    skew, kurt = float((z ** 3).mean()), float((z ** 4).mean())
    pubd = base["deflated_sharpe"]["T1"]
    add(f"{label} variance of monthly Sharpe across T1-T3 (ddof=0)", pubd["N3"]["variance_across_trials"], var3, 5e-9, "{:.6f}")
    add(f"{label} T1 excess kurtosis (non-excess gamma4)", met.at["T1", "kurtosis_excess"], kurt, 5e-4, "{:.3f}")
    for N in (3, 10):
        sr_star, psr, d = dsr(srs["T1"], n, skew, kurt, N, var3)
        add(f"{label} T1 expected max Sharpe SR* (monthly), N={N}", pubd[f"N{N}"]["sr_star_monthly"], sr_star, 5e-6, "{:.5f}")
        add(f"{label} T1 DSR, N={N}", pubd[f"N{N}"]["dsr"], d, 5e-5, "{:.4f}")
    add(f"{label} T1 PSR", pubd["N3"]["psr"], dsr(srs["T1"], n, skew, kurt, 3, var3)[1], 5e-5, "{:.4f}")
    out["df"], out["met"], out["summ"], out["srs"] = df, met, summ, srs
    return out


# ----------------------------------------------------------------------------- main
def main() -> int:
    ins = recompute_window("insample", "IS")
    oos = recompute_window("oos", "OOS")
    dfi, dfo = ins["df"], oos["df"]

    # B3 weight: in-sample fraction of months T1 held IEF, frozen for OOS
    w = float((dfi["T1_holding"] == "IEF").mean())
    add("B3 weight = in-sample fraction of months T1 held IEF", ins["summ"]["weight_b3"], w, 5e-7, "{:.4f}")
    add("B3 weight used out-of-sample equals the in-sample weight", oos["summ"]["weight_b3_frozen_from_insample"], w, 5e-7, "{:.4f}")
    add("IS months T1 held IEF (README: 128 of 185)", 128, int((dfi["T1_holding"] == "IEF").sum()), 0, "{:d}")
    # B3 return reproduces from w, B1 and B0 with rebalancing cost (sanity on the benchmark construction)
    r_ief, r_bil = dfi["B1"].to_numpy(), dfi["B0"].to_numpy()
    gross = w * r_ief + (1 - w) * r_bil
    drift = np.empty_like(gross); drift[0] = w; drift[1:] = w * (1 + r_ief[:-1]) / (1 + gross[:-1])
    b3_rec = (1 - COST * np.abs(drift - w)) ** 2 * (1 + gross) - 1
    add("IS B3 monthly returns reproduce from w, B1, B0 and the rebalancing cost (max abs diff)", 0.0, float(np.max(np.abs(b3_rec - dfi["B3"].to_numpy()))), 1e-12, "{:.1e}")

    # OOS months with T1 - B0 exactly zero
    add("OOS months with T1 - B0 exactly zero (README/§16: 50 of 93)", 50, int((dfo["T1"].to_numpy() - dfo["B0"].to_numpy() == 0).sum()), 0, "{:d}")

    # Criteria as Study 001 §9.5 states (reviewer's application)
    mi, mo = ins["met"], oos["met"]
    s = lambda m, k: float(m.at[k, "sharpe_annual"])
    c1 = s(mi, "T1") >= s(mi, "B1") + 0.10 and s(mi, "T1") >= s(mi, "B3") + 0.10
    t_b3 = nw_mean_t(dfi["T1"].to_numpy() - dfi["B3"].to_numpy())[2]
    c2 = t_b3 >= 2.0
    c3 = ins["summ"]["cost_cases"]["base"]["deflated_sharpe"]["T1"]["N3"]["dsr"] >= 0.95
    stress = pd.read_csv(RES / "insample" / "monthly_stress.csv", index_col=0)
    c4 = np.sign((dfi["T1"] - dfi["B3"]).mean()) == np.sign((stress["T1"] - stress["B3"]).mean())
    o1 = (dfo["T1"] - dfo["B3"]).mean() > 0
    o2 = s(mo, "T1") > s(mo, "B1")
    dd_clause = oos["summ"]["cost_cases"]["base"]["max_drawdown_daily"]["T1"] < oos["summ"]["cost_cases"]["base"]["max_drawdown_daily"]["B1"]
    add("C1 (Sharpe margin 0.10 over B1 and B3)", ins["summ"]["criteria"]["C1"], bool(c1))
    add("C2 (NW t of T1-B3 >= 2.0)", ins["summ"]["criteria"]["C2"], bool(c2))
    add("C3 (DSR N=3 >= 0.95)", ins["summ"]["criteria"]["C3"], bool(c3))
    add("C4 (sign of mean(T1-B3) unchanged at 4 bp)", ins["summ"]["criteria"]["C4"], bool(c4))
    add("IS mean(T1-B3) at stress costs, annualised (README +0.18% p.a.)", 0.0018, float((stress["T1"] - stress["B3"]).mean() * 12), 5e-5, "{:+.4%}")
    add("O1 (mean(T1-B3) > 0 OOS)", oos["summ"]["criteria"]["O1"], bool(o1))
    add("O2 (Sharpe T1 > Sharpe B1 OOS)", oos["summ"]["criteria"]["O2"], bool(o2))
    add("OOS drawdown clause triggered (T1 daily max DD worse than B1)", False, bool(dd_clause))
    t_oos_b3 = nw_mean_t(dfo["T1"].to_numpy() - dfo["B3"].to_numpy())[2]
    insample_ok = c1 and c2 and c3 and c4
    if (not insample_ok) or ((not o1) and t_oos_b3 <= -1.0) or dd_clause:
        verdict = "not supported"                       # §9.5 row 2; precedence: not supported wins
    elif insample_ok and o1 and o2:
        verdict = "supported"
    else:
        verdict = "inconclusive"
    add("Verdict for T1 by the §9.5 table", oos["summ"]["verdict_T1"], verdict)
    # Descriptive only (reviewer's note, not a criterion): T1 against a mix with T1's own OOS exposure
    w_oos = float((dfo["T1_holding"] == "IEF").mean())
    mix = w_oos * dfo["B1"] + (1 - w_oos) * dfo["B0"]
    add(f"OOS mean(T1 - mix at T1's own OOS exposure {w_oos:.3f}), annualised, no cost (reviewer's note)", None,
        float((dfo["T1"] - mix).mean() * 12), fmt="{:+.4%}", note="descriptive, not pre-registered")

    # README descriptive claims from the monthly files
    t1_cash = dfi["T1_holding"] == "BIL"
    eps = episodes(t1_cash)
    add("IS T1 cash months (README 57)", 57, int(t1_cash.sum()), 0, "{:d}")
    add("IS T1 cash episodes (README 9)", 9, len(eps), 0, "{:d}")
    add("IS mean IEF return in cash months (README 0.38%/month)", 0.0038, float(dfi.loc[t1_cash, "B1"].mean()), 5e-5, "{:.4%}")
    add("IS mean cash return in cash months (README 0.16%/month)", 0.0016, float(dfi.loc[t1_cash, "B0"].mean()), 5e-5, "{:.4%}")
    add("IS share of cash months in which cash beat IEF (README 42%)", 0.42, float((dfi.loc[t1_cash, "B0"] > dfi.loc[t1_cash, "B1"]).mean()), 5e-3, "{:.3f}")
    readme_eps = {"2005-09": -0.0012, "2013-05": 0.0011, "2017-01": 0.0204, "2018-01": 0.0221, "2004-04": 0.0120}
    for start, end, length in eps:
        if start in readme_eps:
            seg = dfi.loc[start:end]
            diff = float(np.prod(1 + seg["B1"]) - np.prod(1 + seg["B0"]))
            add(f"IS cash episode {start}..{end} ({length} m) IEF - cash (README)", readme_eps[start], diff, 5e-4, "{:+.2%}")
    worst_t1 = dfi["T1"].nsmallest(3)
    worst_b1 = dfi["B1"].nsmallest(3)
    add("IS T1 three worst months (README 2016-10, 2004-03, 2009-11)", "2016-10,2004-03,2009-11", ",".join(worst_t1.index))
    add("IS T1 worst months are IEF's worst months", True, bool(set(worst_t1.index) == set(worst_b1.index)))
    years = len(dfi) / 12.0
    add("IS T1 switching cost p.a. (README about 5 bp)", 0.0005, float(ins["T1"]["switched"].sum() * (1 - (1 - COST) ** 2) / years), 1e-4, "{:.2%}")
    # sub-periods by execution month
    exec_month = dfi["execution_date"].dt.to_period("M")
    subs = {"2003-08..2008-12": ("2003-08", "2008-12", 0.575, 0.653, 0.652, 9, 65),
            "2009-01..2015-12": ("2009-01", "2015-12", 0.553, 0.621, 0.621, 6, 84),
            "2016-01..2018-12": ("2016-01", "2018-12", -0.208, 0.122, 0.122, 3, 36)}
    for name, (a, b, st1, sb1, sb3, nsw, cnt) in subs.items():
        m = (exec_month >= pd.Period(a, "M")) & (exec_month <= pd.Period(b, "M"))
        seg = dfi[m]
        add(f"IS sub-period {name} months (README {cnt})", cnt, int(m.sum()), 0, "{:d}")
        for strat, pub in (("T1", st1), ("B1", sb1), ("B3", sb3)):
            add(f"IS sub-period {name} {strat} Sharpe (README)", pub, sharpe_monthly((seg[strat] - seg["B0"]).to_numpy()) * SQ12, 5e-4, "{:.3f}")
        add(f"IS sub-period {name} T1 switches (README)", nsw, int(ins["T1"]["switched"][m].sum()), 0, "{:d}")
    # OOS descriptives
    o_cash = dfo["T1_holding"] == "BIL"
    o_eps = episodes(o_cash)
    add("OOS T1 cash months (README 55)", 55, int(o_cash.sum()), 0, "{:d}")
    add("OOS T1 cash episodes (README 6)", 6, len(o_eps), 0, "{:d}")
    add("OOS share of months in cash (README 59%)", 0.59, float(o_cash.mean()), 5e-3, "{:.3f}")
    big = [e for e in o_eps if e[0] == "2021-02"]
    if big:
        a, b, length = big[0]
        seg = dfo.loc[a:b]
        add("OOS long cash episode 2021-02..2024-07 length (README 42)", 42, length, 0, "{:d}")
        add("OOS 2021-02..2024-07 IEF - cash (README -19.0%)", -0.190, float(np.prod(1 + seg["B1"]) - np.prod(1 + seg["B0"])), 5e-4, "{:+.2%}")
        add("OOS 2021-02..2024-07 T1 return (README +10.1%)", 0.101, float(np.prod(1 + seg["T1"]) - 1), 5e-4, "{:+.2%}")
    for strat, pub in (("T1", 0.277), ("B0", 0.225), ("B3", 0.095), ("B1", 0.035)):
        add(f"OOS cumulative {strat} (README)", pub, float(np.prod(1 + dfo[strat]) - 1), 5e-4, "{:+.2%}")
    add("OOS terminal T1 signal, September 2026 month-end (README -7.4%)", -0.074, oos["summ"]["terminal_signal_value"]["T1"], 5e-4, "{:+.3%}", note="from summary.json; not recomputed, no 2026-09 row in monthly file")

    # ---------------------------------------------------------------- raw daily data: signal integrity and daily drawdowns
    have_raw = all((RAW / f).exists() for f in ("tiingo_IEF_daily.csv", "fred_DTB3.csv", "alpaca_IEF_1Day_all.csv", "alpaca_BIL_1Day_all.csv"))
    if not have_raw:
        rows.append(("Raw daily files", "n/a", "absent", "not checked (data/raw/ missing)"))
    else:
        tii = pd.read_csv(RAW / "tiingo_IEF_daily.csv", parse_dates=["date"]).set_index("date").sort_index()
        ief_is = (tii["adjClose"] / tii["adjClose"].iloc[0]).rename("IEF")
        cash_is = cash_index_from_dtb3(RAW / "fred_DTB3.csv")
        alp = {s: pd.read_csv(RAW / f"alpaca_{s}_1Day_all.csv", parse_dates=["date"]).set_index("date").sort_index()["close"] for s in ("IEF", "BIL")}
        ief_oos = (alp["IEF"] / alp["IEF"].iloc[0]).rename("IEF")
        bil_oos = (alp["BIL"] / alp["BIL"].iloc[0]).rename("BIL")

        def check_signal(df: pd.DataFrame, ief: pd.Series, cash: pd.Series, label: str) -> None:
            me = month_end_bars(ief.index)             # last IEF bar of every calendar month
            months = pd.PeriodIndex(df.index, freq="M")
            t = me.reindex(months).to_numpy()
            t12 = me.reindex(months - 12).to_numpy()
            assert not pd.isna(t).any() and not pd.isna(t12).any()
            mom = level_at(ief, t) / level_at(ief, t12) - level_at(cash, t) / level_at(cash, t12)
            diff = np.abs(mom - df["mom_at_signal"].to_numpy())
            add(f"{label} mom_at_signal recomputed from month-end bars, all {len(df)} months (max abs diff)", 0.0, float(diff.max()), 1e-9, "{:.1e}")
            # look-ahead: signal date t (last bar of the signal month) is strictly before execution_date,
            # and execution_date is the first bar strictly after t
            bars = ief.index
            next_bar = bars[np.searchsorted(bars.values, t, side="right")]
            add(f"{label} signal date < execution_date for every month", True, bool((pd.DatetimeIndex(t) < df["execution_date"]).all()))
            add(f"{label} execution_date is the first bar strictly after the signal date, every month", True,
                bool((pd.DatetimeIndex(next_bar) == pd.DatetimeIndex(df["execution_date"])).all()))
            add(f"{label} period_end equals the next row's execution_date", True,
                bool((df["period_end"].iloc[:-1].to_numpy() == df["execution_date"].iloc[1:].to_numpy()).all()))
            # the holding-period returns of B1 and B0 reproduce from the daily indices
            e, pe = df["execution_date"], df["period_end"]
            b1 = level_at(ief, pe) / level_at(ief, e) - 1
            b0 = level_at(cash, pe) / level_at(cash, e) - 1
            add(f"{label} B1 holding-period returns reproduce from daily IEF index (max abs diff)", 0.0, float(np.abs(b1 - df["B1"].to_numpy()).max()), 1e-12, "{:.1e}")
            add(f"{label} B0 holding-period returns reproduce from daily cash index (max abs diff)", 0.0, float(np.abs(b0 - df["B0"].to_numpy()).max()), 1e-12, "{:.1e}")

        check_signal(dfi, ief_is, cash_is, "IS")
        check_signal(dfo, ief_oos, bil_oos, "OOS")

        # daily maximum drawdowns inside the holding periods
        for label, df, tri, res in (("IS", dfi, {"IEF": ief_is, "BIL": cash_is}, ins), ("OOS", dfo, {"IEF": ief_oos, "BIL": bil_oos}, oos)):
            pub = res["summ"]["cost_cases"]["base"]["max_drawdown_daily"]
            for strat in ("T1", "T2", "T3"):
                lv = daily_strategy_levels(df, res[strat]["held"], res[strat]["switched"], tri)
                add(f"{label} {strat} max drawdown (daily)", pub[strat], max_dd(lv.to_numpy()), 5e-4, "{:.2%}")
            window = tri["IEF"].loc[df["execution_date"].iloc[0]:df["period_end"].iloc[-1]]
            add(f"{label} B1 max drawdown (daily)", pub["B1"], max_dd(window.to_numpy()), 5e-4, "{:.2%}")

    # ---------------------------------------------------------------- print
    print("| # | Claim | Published | Recomputed | Match |")
    print("|---|---|---|---|---|")
    for i, (c, p, r, m) in enumerate(rows, 1):
        print(f"| {i} | {c} | {p} | {r} | {m} |")
    n_yes = sum(1 for r in rows if r[3].startswith("yes"))
    n_no = sum(1 for r in rows if r[3].startswith("NO"))
    n_nc = len(rows) - n_yes - n_no
    print(f"\nRows: {len(rows)}; match: {n_yes}; mismatch: {n_no}; informational/not checked: {n_nc}")
    return 1 if n_no else 0


if __name__ == "__main__":
    sys.exit(main())
