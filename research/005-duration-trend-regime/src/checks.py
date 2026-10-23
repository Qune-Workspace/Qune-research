"""Data checks D0, D1, D3 (§5.3.1, §5.3.2, §5.3.4), one run, no rule applied.

* **D0, coverage** (dates only): the Tiingo IEF and SPY files on every NYSE
  trading day 2003-04-01 to 2018-12-31 with at most three consecutive
  missing days, IEF's first bar on or before 2002-07-31; the Alpaca SPY, IEF
  and BIL files the same on 2018-09-04 to 2026-09-30.  IEF failing is a halt
  ground; SPY failing makes the regime unavailable for that window.
* **D1, regime sign agreement across vendors** (descriptive, no gate): the
  63-day SPY–IEF correlation on every trading day 2016-01-04 to 2018-12-31
  from Tiingo and from Alpaca closes; share of days the signs agree, mean
  absolute difference, largest difference.  Below 95% the note must discuss
  it; T1 still runs.
* **D3, regime shares and the power statement**: for each in-sample signal
  date (2003-07 to 2018-11) the T1, T2 and T3 flags and their descriptives;
  the same for the 2019–2026 episode's dates, labelled; σ_d exactly from
  Study 003's committed in-sample file; the minimum detectable effect at the
  actual counts; whether §9.5's in-sample rows apply (n_pos ≥ 12).  **This
  computes correlations of instrument returns and reads a committed file; no
  return of any rule, benchmark or conditional statistic of this study.**

Every function takes series in; ``run`` wires the loaders of ``data.py`` and
writes ``results/checks/``.  Run only through ``reproduce.sh --check``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from qune_research import datacheck
from qune_research.nyse import nyse_trading_days

from . import data, regime
from .config import (ALPACA_COVERAGE, CASH_LEG, CHECKS_DIR, DURATION_LEG, EPISODE_FIRST_SIGNAL_MONTH,
                     EPISODE_LAST_SIGNAL_MONTH, IEF_FIRST_BAR_ON_OR_BEFORE, INSAMPLE_FIRST_SIGNAL_MONTH,
                     INSAMPLE_LAST_SIGNAL_MONTH, MAX_CONSECUTIVE_MISSING, MIN_POSITIVE_MONTHS, OVERLAP_LOW_AGREEMENT,
                     OVERLAP_WINDOW, PRIOR_POSITIVE_SHARE, PRIOR_SIGMA_D_PER_MONTH, REGIME_SYMBOL, REGIME_WINDOWS,
                     STUDY_003_INSAMPLE_MONTHLY, TIINGO_COVERAGE)
from .edge import minimum_detectable_effect, sigma_d_from_study_003
from .pipeline import window_bars, window_schedule


def _now() -> str:
    return pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


# --- D0 -------------------------------------------------------------------------------

def d0(tiingo: dict[str, pd.Series], alpaca: dict[str, pd.Series]) -> dict:
    """§5.3.1 on the bar indices only."""
    out = {"stage": "D0", "written_at_utc": _now(), "files": {}}
    for symbol, close in tiingo.items():
        cov = datacheck.coverage(close.index, *TIINGO_COVERAGE, MAX_CONSECUTIVE_MISSING)
        cov["first_bar"] = close.index[0].strftime("%Y-%m-%d")
        if symbol == DURATION_LEG:
            cov["first_bar_on_or_before_required"] = IEF_FIRST_BAR_ON_OR_BEFORE
            cov["pass"] = bool(cov["pass"] and close.index[0] <= pd.Timestamp(IEF_FIRST_BAR_ON_OR_BEFORE))
        out["files"][f"tiingo_{symbol}"] = cov
    for symbol, close in alpaca.items():
        cov = datacheck.coverage(close.index, *ALPACA_COVERAGE, MAX_CONSECUTIVE_MISSING)
        cov["first_bar"] = close.index[0].strftime("%Y-%m-%d")
        out["files"][f"alpaca_{symbol}"] = cov
    out["halt_ief"] = not out["files"][f"tiingo_{DURATION_LEG}"]["pass"] or not out["files"][f"alpaca_{DURATION_LEG}"]["pass"]
    out["regime_unavailable_insample"] = not out["files"][f"tiingo_{REGIME_SYMBOL}"]["pass"]
    out["regime_unavailable_episode"] = not out["files"][f"alpaca_{REGIME_SYMBOL}"]["pass"]
    out["pass"] = bool(all(f["pass"] for f in out["files"].values()))
    return out


# --- D1 -------------------------------------------------------------------------------

def d1(tiingo: dict[str, pd.Series], alpaca_overlap_spy: pd.Series, alpaca_ief: pd.Series,
       window: tuple[str, str] = OVERLAP_WINDOW, days: int = REGIME_WINDOWS["T1"]) -> dict:
    """§5.3.2: the 63-day correlation on every trading day of the overlap
    window from each vendor's closes; sign agreement, descriptive."""
    start, end = window
    trading = nyse_trading_days(start, end)
    rv = regime.common_returns(tiingo[REGIME_SYMBOL], tiingo[DURATION_LEG])
    rb = regime.common_returns(alpaca_overlap_spy, alpaca_ief)
    dates = pd.Series(trading, index=trading)
    rho_v = regime.trailing_correlation(rv, dates, days)
    rho_b = regime.trailing_correlation(rb, dates, days)
    both = pd.concat([rho_v.rename("vendor"), rho_b.rename("broker")], axis=1).dropna()
    diff = (both["vendor"] - both["broker"]).abs()
    agree = np.sign(both["vendor"]) == np.sign(both["broker"])
    return {"stage": "D1", "written_at_utc": _now(), "window": {"start": start, "end": end}, "correlation_days": days,
            "days_compared": int(len(both)), "days_undefined_vendor": int(rho_v.isna().sum()),
            "days_undefined_broker": int(rho_b.isna().sum()),
            "sign_agreement_share": float(agree.mean()) if len(both) else float("nan"),
            "days_signs_disagree": [d.strftime("%Y-%m-%d") for d in both.index[~agree]],
            "mean_abs_difference": float(diff.mean()) if len(both) else float("nan"),
            "max_abs_difference": float(diff.max()) if len(both) else float("nan"),
            "max_abs_difference_date": diff.idxmax().strftime("%Y-%m-%d") if len(both) else None,
            "share_days_vendor_positive": float((both["vendor"] > 0).mean()) if len(both) else float("nan"),
            "low_agreement_threshold_for_discussion": OVERLAP_LOW_AGREEMENT,
            "discuss_in_limitations": bool(len(both) and agree.mean() < OVERLAP_LOW_AGREEMENT),
            "gate": "none (§5.3.2; the level gap that excluded SPY from Study 004 does not bear on a sign)"}


# --- D3 -------------------------------------------------------------------------------

def regime_flags_for_window(close_spy: pd.Series, close_ief: pd.Series, cpi: pd.Series | None,
                            bars: pd.DatetimeIndex, first_month: str, last_month: str) -> pd.DataFrame:
    """T1, T2, T3 flags on the window's signal dates that start a holding
    period (every schedule row but the last).  Correlations of instrument
    returns only."""
    schedule, _ = window_schedule(bars, first_month, last_month)
    signal_dates = schedule["signal_date"].iloc[:-1]
    returns = regime.common_returns(close_spy, close_ief)
    frame = pd.DataFrame({"signal_date": signal_dates})
    for trial in ("T1", "T2"):
        reg = regime.correlation_regime(returns, signal_dates, trial)
        frame[f"rho_{trial}"] = reg["rho"].reindex(frame.index)
        frame[f"positive_{trial}"] = reg["positive"].reindex(frame.index)
    if cpi is not None:
        reg = regime.cpi_regime(cpi, signal_dates)
        frame["cpi_12m_change_T3"] = reg["cpi_12m_change"].reindex(frame.index)
        frame["positive_T3"] = reg["positive"].reindex(frame.index)
    return frame


def d3(insample_flags: pd.DataFrame, episode_flags: pd.DataFrame | None, sigma: dict) -> dict:
    """§5.3.4 and §9.6: shares, episodes, σ_d, MDE at the actual counts and
    whether the in-sample rows apply."""
    out = {"stage": "D3", "written_at_utc": _now(), "sigma_d": sigma,
           "sigma_d_at_registration": PRIOR_SIGMA_D_PER_MONTH, "prior_positive_share": list(PRIOR_POSITIVE_SHARE),
           "insample": {}, "episode_no_decision_weight": {}}
    for trial in ("T1", "T2", "T3"):
        col = f"positive_{trial}"
        if col not in insample_flags:
            out["insample"][trial] = {"status": "not run: series unavailable"}
            continue
        flags = insample_flags[col].dropna().astype(bool)
        desc = regime.regime_episodes(flags)
        desc["first_signal_month"], desc["last_signal_month"] = str(flags.index[0]), str(flags.index[-1])
        desc["undefined_months"] = int(insample_flags[col].isna().sum())
        n_pos, n_neg = desc["positive_months"], desc["months"] - desc["positive_months"]
        desc["mde"] = minimum_detectable_effect(sigma["sigma_d_per_month"], n_pos, n_neg)
        desc["insample_rows_apply"] = bool(n_pos >= MIN_POSITIVE_MONTHS)
        out["insample"][trial] = desc
    if episode_flags is not None:
        for trial in ("T1", "T2", "T3"):
            col = f"positive_{trial}"
            if col in episode_flags:
                flags = episode_flags[col].dropna().astype(bool)
                desc = regime.regime_episodes(flags)
                desc["first_signal_month"], desc["last_signal_month"] = str(flags.index[0]), str(flags.index[-1])
                out["episode_no_decision_weight"][trial] = desc
    out["min_positive_months_for_rows"] = MIN_POSITIVE_MONTHS
    out["insample_rows_apply_T1"] = out["insample"]["T1"].get("insample_rows_apply", False)
    return out


# --- Run --------------------------------------------------------------------------------

def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=lambda v: v.item() if hasattr(v, "item") else str(v)) + "\n",
                    encoding="utf-8")


def run(stage: str, out_dir: Path = CHECKS_DIR) -> None:
    tiingo = data.insample_closes()
    if stage == "d0":
        alpaca = data.episode_closes()
        result = d0(tiingo, {s: alpaca[s] for s in (REGIME_SYMBOL, DURATION_LEG, CASH_LEG)})
        _write(out_dir / "d0.json", result)
        print(f"D0 {'pass' if result['pass'] else 'FAIL'}; halt_ief={result['halt_ief']}; "
              f"regime unavailable in-sample={result['regime_unavailable_insample']} "
              f"episode={result['regime_unavailable_episode']}")
    elif stage == "d1":
        alpaca = data.episode_closes()
        result = d1(tiingo, data.alpaca_overlap_frame()["close"].astype(float).dropna(), alpaca[DURATION_LEG])
        _write(out_dir / "d1.json", result)
        print(f"D1 sign agreement {result['sign_agreement_share']:.4f} on {result['days_compared']} days; "
              f"mean |diff| {result['mean_abs_difference']:.4f}, max {result['max_abs_difference']:.4f}")
    elif stage == "d3":
        alpaca = data.episode_closes()
        cpi = data.cpi_series()
        from .pipeline import etf_indices, insample_indices
        ins_bars = window_bars(insample_indices(tiingo[DURATION_LEG], data.dtb3_series()), etf_cash=False)
        epi_bars = window_bars(etf_indices(alpaca), etf_cash=True)
        ins = regime_flags_for_window(tiingo[REGIME_SYMBOL], tiingo[DURATION_LEG], cpi, ins_bars,
                                      INSAMPLE_FIRST_SIGNAL_MONTH, INSAMPLE_LAST_SIGNAL_MONTH)
        epi = regime_flags_for_window(alpaca[REGIME_SYMBOL], alpaca[DURATION_LEG], cpi, epi_bars,
                                      EPISODE_FIRST_SIGNAL_MONTH, EPISODE_LAST_SIGNAL_MONTH)
        result = d3(ins, epi, sigma_d_from_study_003(STUDY_003_INSAMPLE_MONTHLY))
        out_dir.mkdir(parents=True, exist_ok=True)
        ins.to_csv(out_dir / "regime_flags_insample.csv")
        epi.to_csv(out_dir / "regime_flags_episode.csv")
        _write(out_dir / "d3.json", result)
        t1 = result["insample"]["T1"]
        print(f"D3 in-sample T1: {t1['positive_months']} of {t1['months']} positive ({t1['positive_share']:.3f}); "
              f"MDE {t1['mde']['per_year'] * 100:.2f}% a year; rows apply: {t1['insample_rows_apply']}")
    else:
        raise SystemExit(f"unknown stage {stage}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Study 005 data checks (§5.3). Invoke through reproduce.sh.")
    parser.add_argument("stage", choices=("d0", "d1", "d3"))
    args = parser.parse_args(argv)
    run(args.stage)


if __name__ == "__main__":
    main()
