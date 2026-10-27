"""Power first for value-at-risk coverage at daily scoring (the last risk-property candidate).

Descriptive power calculation, written 2026-10-27 from 02:2xZ by the clock, before any question
is fixed. The 2026-10-27 01:2xZ addition to RESEARCH_AGENDA.md closed the volatility-forecast
comparison and named what was still not assessed: "VaR coverage, a different risk property with
its own power statement". This script makes that statement.

Inputs, rows and timing are those of tools/power_riskforecast_daily.py (its file loader and
constants are imported; its row loop is re-implemented here with the same rules and gives the
same 3,775 / 1,756 scored days):
Study 004's archived Tiingo daily files (git-ignored, each SHA-256 checked against
results/data_manifest.json), its committed T1 periods and daily net index; nothing is fetched.
Per holding period and per trading day s after the execution day, with the weights w fixed at
the signal date and the 252 complete vendor rows of the held assets ending on the trading day
before s. Realised: T1's daily net index return on day s, gross of the period's trading cost on
the first day after execution; flat periods and exchange closures are not scored. The forecasts
cover the held risk assets only; the cash part of the book (BIL) is left out, as in the earlier
script. Both windows were seen by the author, and the 2026-10-23 risk report already read
normal-VaR coverage on them (monthly covariance, 2.1% and 2.6% exceedances at 99%), so neither
is a clean sample: only forward days are.

Four one-day VaR methods, fixed before the script first ran and not varied afterwards:
  normal-ewma    z * sqrt(w' S_ewma w), 42-day half-life, zero mean (qune_research.risk);
  normal-sample  the same from the equal-weighted 252-day covariance;
  hs             historical simulation: minus the (1 - level) quantile of the 252 hypothetical
                 book returns x_j = w' r_j over the window (numpy's default linear quantile);
  fhs            filtered historical simulation: x_j scaled by its own EWMA volatility (42-day
                 half-life, recursion seeded with the window's first 21 days' mean square and run
                 over the whole window; each sigma_j uses days before j except that the seed
                 includes the first 21 days themselves; every day is before s), then minus the
                 (1 - level) quantile of x_j / sigma_j times the one-day-ahead sigma for day s.
Levels: 99% and 95%. An exceedance is r_s < -VaR_s.

Tests a forward record would use, at 5%:
  Kupiec (1995) unconditional coverage, likelihood ratio against the nominal rate, chi2(1);
  Christoffersen (1998) independence of exceedances (first-order Markov), chi2(1), printed
  for the seen windows only (no power figure: it needs an alternative this script does not fix).
  It treats consecutive scored days as adjacent, also across the gaps left by closures (6
  in-sample) and all-cash periods (2 gaps in 2019-2026); the separate recomputation found the
  effect negligible.
Power for Kupiec is computed exactly from the binomial distribution, not from the chi2
approximation: for N scored days and nominal p0, the rejection region is every count whose LR
exceeds 3.841; power at a true rate p1 is the binomial probability of that region. The script
prints the smallest true rate above p0 (and the largest below) with power >= 80%, the power at
each method's seen rate, and the size of the test at p0 (exact, not 5%).
Forward lengths as in the earlier script: 60 months fully invested (1,260 days) and at the
2019-2026 invested share (1,137 days = round(1,260 x 0.902), the share printed by
tools/power_riskforecast_daily.txt); 120 months (2,520 days). The grid search prints the rate
above p0 rounded up and the rate below rounded down to 0.01 percentage points.
Days are treated as independent for power. Exceedances cluster (the independence rows show by
how much on seen data), which makes the effective sample smaller; every power figure below is an
approximation, not a bound.

Run from the repository root: ``python tools/power_varcoverage.py > tools/power_varcoverage.txt``
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import power_riskforecast_daily as prd  # noqa: E402

from qune_research import risk  # noqa: E402

LEVELS = (0.99, 0.95)
METHODS = ("normal-ewma", "normal-sample", "hs", "fhs")
CHI2_5 = float(sps.chi2.ppf(0.95, 1))
POWER = 0.80
SEED_DAYS = 21
FORWARD = {"60 months, fully invested": 1260, "60 months, invested as in 2019-2026 (90.2%)": 1137,
           "120 months, fully invested": 2520}


def fhs_quantile(x: np.ndarray, q: float, halflife: float) -> tuple[float, float]:
    """Quantile of x / sigma and the one-day-ahead sigma after the last row (EWMA about zero)."""
    lam = 0.5 ** (1.0 / halflife)
    var = float(np.mean(x[:SEED_DAYS] ** 2))
    z = np.empty(len(x))
    for j, xj in enumerate(x):
        z[j] = xj / math.sqrt(var)
        var = lam * var + (1.0 - lam) * xj * xj
    return float(np.quantile(z, q)), math.sqrt(var)


def var_rows(window: str, rets: pd.DataFrame, universe: list[str]) -> pd.DataFrame:
    d = prd.RESULTS / window
    periods = pd.read_csv(d / "t1_periods_10assets_base.csv",
                          parse_dates=["signal_date", "execution_date", "period_end"]).set_index("signal_date")
    index = pd.read_csv(d / "daily_index_10assets.csv", index_col=0, parse_dates=True)["T1"]
    first_exec = periods["execution_date"].min()
    if index.index[0] > first_exec:
        index = pd.concat([pd.Series([1.0], index=[first_exec]), index])
    book_ret = index.pct_change()
    rows = []
    for _, p in periods.iterrows():
        held = {a: float(p[f"w_{a}"]) for a in universe if float(p[f"w_{a}"]) != 0.0}
        if not held:
            continue
        days = book_ret.index[(book_ret.index > p["execution_date"]) & (book_ret.index <= p["period_end"])]
        r = rets[list(held)]
        wv = np.array([held[a] for a in r.columns])
        for i, s in enumerate(days):
            if s not in r.index or r.loc[s].isna().any():
                continue
            hist = r.loc[r.index < s].dropna(how="any").iloc[-prd.LOOKBACK_BARS:]
            if len(hist) < prd.MIN_BARS:
                continue
            sd_e = math.sqrt(risk.portfolio_variance(held, risk.ewma_covariance(hist, prd.HALFLIFE_DAYS,
                                                                                annualise=False)))
            sd_s = math.sqrt(risk.portfolio_variance(held, risk.sample_covariance(hist, annualise=False)))
            x = hist.to_numpy() @ wv
            ret = float(book_ret.loc[s])
            if i == 0:
                ret = (1.0 + ret) / (1.0 - float(p["cost"])) - 1.0
            row = {"day": s, "r": ret}
            for lv in LEVELS:
                z = float(sps.norm.ppf(lv))
                qz, sig = fhs_quantile(x, 1.0 - lv, prd.HALFLIFE_DAYS)
                row[f"normal-ewma_{lv}"] = z * sd_e
                row[f"normal-sample_{lv}"] = z * sd_s
                row[f"hs_{lv}"] = -float(np.quantile(x, 1.0 - lv))
                row[f"fhs_{lv}"] = -qz * sig
            rows.append(row)
    return pd.DataFrame(rows).set_index("day")


def lr_uc(n: int, k: int, p0: float) -> float:
    """Kupiec likelihood ratio for k exceedances in n days at nominal p0."""
    def ll(p: float) -> float:
        a = k * math.log(p) if k > 0 else 0.0
        b = (n - k) * math.log(1.0 - p) if n - k > 0 else 0.0
        return a + b
    phat = k / n
    return -2.0 * (ll(p0) - ll(phat))


def lr_ind(hit: np.ndarray) -> tuple[float, int]:
    """Christoffersen first-order independence likelihood ratio and the count of back-to-back hits."""
    a, b = hit[:-1], hit[1:]
    n00 = int(((a == 0) & (b == 0)).sum())
    n01 = int(((a == 0) & (b == 1)).sum())
    n10 = int(((a == 1) & (b == 0)).sum())
    n11 = int(((a == 1) & (b == 1)).sum())

    def term(c: int, p: float) -> float:
        return c * math.log(p) if c > 0 else 0.0
    p01 = n01 / (n00 + n01) if n00 + n01 else 0.0
    p11 = n11 / (n10 + n11) if n10 + n11 else 0.0
    p = (n01 + n11) / (n00 + n01 + n10 + n11)
    l1 = term(n00, 1 - p01) + term(n01, p01) + term(n10, 1 - p11) + term(n11, p11)
    l0 = term(n00 + n10, 1 - p) + term(n01 + n11, p)
    return -2.0 * (l0 - l1), n11


def reject_region(n: int, p0: float) -> np.ndarray:
    ks = np.arange(n + 1)
    return np.array([lr_uc(n, int(k), p0) > CHI2_5 for k in ks])


def power_at(n: int, region: np.ndarray, p1: float) -> float:
    return float(sps.binom.pmf(np.arange(n + 1), n, p1)[region].sum())


def mde_rates(n: int, p0: float, region: np.ndarray) -> tuple[float, float | None]:
    """Smallest true rate above p0 and largest below p0 with power >= 80% (grid of 0.0001)."""
    up = next(p for p in np.arange(p0, 0.5, 0.0001) if power_at(n, region, p) >= POWER)
    downs = [p for p in np.arange(0.0001, p0, 0.0001) if power_at(n, region, p) >= POWER]
    return float(up), (float(downs[-1]) if downs else None)


def main() -> None:
    checks = json.loads((prd.RESULTS / "checks" / "data_checks.json").read_text(encoding="utf-8"))
    universe = list(checks["evaluation"]["universe"])
    rets = prd.load_prices(universe).pct_change()
    print("Power first for value-at-risk coverage at daily scoring (tools/power_varcoverage.py)")
    print("inputs: Study 004's archived Tiingo daily files (hash-checked against results/data_manifest.json) and its")
    print("committed T1 periods and daily net index, rows as in tools/power_riskforecast_daily.py; nothing fetched;")
    print("both windows seen, and normal-VaR coverage already read on them by the 2026-10-23 risk report, so not clean")
    print(f"tests: Kupiec unconditional coverage and Christoffersen independence, LR > {CHI2_5:.3f} (chi2(1), 5%)")
    print()
    seen: dict[tuple[str, str, float], float] = {}
    print(f"  {'window':20} {'level':5} {'method':13} {'n':>6} {'hits':>5} {'rate':>7} {'LR uc':>7} {'p uc':>7} "
          f"{'LR ind':>7} {'p ind':>7} {'pairs':>5} {'median VaR':>10}")
    for label, w in prd.WINDOWS.items():
        df = var_rows(w, rets, universe)
        n = len(df)
        for lv in LEVELS:
            for m in METHODS:
                v = df[f"{m}_{lv}"]
                hit = (df["r"] < -v).to_numpy().astype(int)
                k = int(hit.sum())
                uc = lr_uc(n, k, 1.0 - lv)
                ind, n11 = lr_ind(hit)
                seen[(label, m, lv)] = k / n
                print(f"  {label:20} {lv:<5} {m:13} {n:>6,} {k:>5} {k / n:>7.2%} {uc:>7.2f} {sps.chi2.sf(uc, 1):>7.4f} "
                      f"{ind:>7.2f} {sps.chi2.sf(ind, 1):>7.4f} {n11:>5} {v.median():>10.4%}")
    print()
    print("Forward record: exact binomial power of the Kupiec test at 5% (days treated as independent)")
    print(f"  {'length':44} {'n':>5} {'level':5} {'size at p0':>10} {'80% power above':>16} {'80% power below':>16}")
    regions = {}
    for name, n in FORWARD.items():
        for lv in LEVELS:
            p0 = 1.0 - lv
            reg = reject_region(n, p0)
            regions[(n, lv)] = reg
            up, down = mde_rates(n, p0, reg)
            dn = f"{down:.2%}" if down is not None else "none"
            print(f"  {name:44} {n:>5,} {lv:<5} {power_at(n, reg, p0):>10.3f} {up:>16.2%} {dn:>16}")
    print()
    print("Power at each method's seen rate, 60 months at the 2019-2026 invested share (1,137 days)")
    n = FORWARD["60 months, invested as in 2019-2026 (90.2%)"]
    print(f"  {'level':5} {'method':13} " + " ".join(f"{lab + ' rate':>26} {'power':>6}" for lab in prd.WINDOWS))
    for lv in LEVELS:
        for m in METHODS:
            cells = []
            for lab in prd.WINDOWS:
                p1 = seen[(lab, m, lv)]
                cells.append(f"{p1:>26.2%} {power_at(n, regions[(n, lv)], p1):>6.3f}")
            print(f"  {lv:<5} {m:13} " + " ".join(cells))
    print()
    print("Reading: a seen rate with high power here is one a forward record would likely confirm if the rate held and")
    print("days were independent; a seen rate inside the 80% band is one it would not reliably tell from nominal")
    print("(power below 80%, not zero). Every Christoffersen row above rejects independence at 5%, so the")
    print("independence behind these power figures is rejected on the data the rates come from; with clustering the")
    print("effective sample is smaller and the power lower. Both windows were seen, so only forward days are clean.")


if __name__ == "__main__":
    main()
