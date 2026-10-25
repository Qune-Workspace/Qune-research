"""Study 006 gate (PREREGISTRATION.md §5.3): the error that the synthetic
series puts into the monthly timing differential, on the 192 overlap periods.

Computes the signal path h_t (FRED yields only), the duration leg's return over
cash x_t on the synthetic and the ETF side (instrument returns only), their gap
g_t and e_t = (h_t - w_o) * g_t.  It never forms a rule or benchmark return:
nothing here multiplies a holding by a return, and the module cannot import the
backtest (tests/test_gate.py checks the import graph).

    python -m src.gate        # §14 step 5; writes results/gate/ once
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .alpaca_bars import load_bars
from .calendar import build_schedule, holding_periods
from .config import DURATION_LEG, STUDY_DIR
from .config006 import (
    BIL_VENDORS,
    G1_MAX,
    G2_MAX,
    GATE_DIR,
    IEF_VENDORS,
    OVERLAP_FIRST_SIGNAL_MONTH,
    OVERLAP_LAST_SIGNAL_MONTH,
    OVERLAP_PERIODS,
    OVERLAP_SPLIT_YEAR,
)
from .fred import load_series
from .signal import t1, t2, t3
from .synthetic import synthetic_indices
from .tiingo_bars import load_prices


def period_returns(tri: pd.Series, starts: pd.Series, ends: pd.Series) -> np.ndarray:
    """Close-to-close return of an index between paired dates, with the
    engine's convention (the last index value on or before each date)."""
    start = tri.reindex(pd.DatetimeIndex(starts), method="ffill").to_numpy()
    end = tri.reindex(pd.DatetimeIndex(ends), method="ffill").to_numpy()
    if np.isnan(start).any() or np.isnan(end).any():
        raise ValueError("index does not cover the periods")
    return end / start - 1.0


def etf_indices() -> dict[tuple[str, str], pd.Series]:
    """Adjusted-close indices keyed by (symbol, vendor), on bar dates only."""
    out = {}
    for symbol in ("IEF", "BIL"):
        out[(symbol, "alpaca")] = load_bars(symbol)["close"].astype(float).dropna()
        out[(symbol, "tiingo")] = load_prices(symbol)["adjClose"].astype(float).dropna()
    return out


def choose_vendor(
    starts: pd.Series, ends: pd.Series, bar_dates: dict[str, pd.DatetimeIndex], preference: tuple[str, ...]
) -> list[str | None]:
    """§5.3.2: the first vendor in ``preference`` with a bar on both dates of
    the period; None if no vendor has both."""
    chosen: list[str | None] = []
    for a, b in zip(pd.DatetimeIndex(starts), pd.DatetimeIndex(ends), strict=True):
        pick = None
        for vendor in preference:
            dates = bar_dates[vendor]
            if a in dates and b in dates:
                pick = vendor
                break
        chosen.append(pick)
    return chosen


def etf_leg_returns(
    index: dict[str, pd.Series], vendors: list[str | None], starts: pd.Series, ends: pd.Series
) -> np.ndarray:
    """Period returns from each period's own vendor (both ends from it); NaN
    where no vendor covers the period."""
    out = np.full(len(vendors), np.nan)
    s, e = pd.DatetimeIndex(starts), pd.DatetimeIndex(ends)
    for vendor in {v for v in vendors if v is not None}:
        mask = np.array([v == vendor for v in vendors])
        tri = index[vendor]
        out[mask] = tri.loc[e[mask]].to_numpy() / tri.loc[s[mask]].to_numpy() - 1.0
    return out


def gate_statistics(h: np.ndarray, x_syn: np.ndarray, x_etf: np.ndarray) -> dict:
    """G1 and G2 (§5.3.3) and the quantities behind them.  ``h`` is 0/1."""
    h = np.asarray(h, dtype=float)
    g = np.asarray(x_syn, dtype=float) - np.asarray(x_etf, dtype=float)
    w_o = float(h.mean())
    e = (h - w_o) * g
    g1 = abs(float(e.mean())) * 12.0
    g2 = float(np.std(g, ddof=1) / np.std(x_etf, ddof=1))
    return {
        "periods": int(len(h)),
        "w_o": w_o,
        "G1_bias_annual": g1,
        "G1_pass": bool(g1 <= G1_MAX),
        "G2_noise_ratio": g2,
        "G2_pass": bool(g2 <= G2_MAX),
        "mean_e_annual_signed": float(e.mean()) * 12.0,
        "mean_g_annual": float(g.mean()) * 12.0,
        "corr_g_x_etf": float(np.corrcoef(g, x_etf)[0, 1]),
        "switches": int(np.abs(np.diff(h)).sum()),
    }


def holdings(targets: pd.DataFrame, months: pd.Index) -> np.ndarray:
    """h_t = 1 where the trial's target is the duration leg (signal only)."""
    target = targets["target"].reindex(months)
    if target.isna().any():
        raise ValueError("signal missing on an overlap month")
    return (target == DURATION_LEG).to_numpy(dtype=float)


def compute() -> dict:
    dgs10, dtb3, dgs7 = load_series("DGS10"), load_series("DTB3"), load_series("DGS7")
    schedule = build_schedule(dgs10, dtb3, OVERLAP_FIRST_SIGNAL_MONTH, OVERLAP_LAST_SIGNAL_MONTH)
    periods = holding_periods(schedule)
    if len(periods) != OVERLAP_PERIODS:
        raise ValueError(f"{len(periods)} overlap periods, expected {OVERLAP_PERIODS}")
    starts, ends = periods["execution_date"], periods["period_end"]

    synthetic = synthetic_indices(dgs10, dtb3, dgs7)
    d_syn = period_returns(synthetic["IEF"], starts, ends)
    c_syn = period_returns(synthetic["BIL"], starts, ends)
    x_syn = d_syn - c_syn

    etf = etf_indices()
    dates = {(s, v): idx.index for (s, v), idx in etf.items()}
    ief_vendor = choose_vendor(starts, ends, {v: dates[("IEF", v)] for v in IEF_VENDORS}, IEF_VENDORS)
    bil_vendor = choose_vendor(starts, ends, {v: dates[("BIL", v)] for v in BIL_VENDORS}, BIL_VENDORS)
    if any(v is None for v in ief_vendor):
        raise ValueError("an overlap period has no IEF bar at both ends (§5.3.2)")
    first_bil = next(i for i, v in enumerate(bil_vendor) if v is not None)
    if any(v is None for v in bil_vendor[first_bil:]):
        raise ValueError("BIL missing after its first covered period (§5.3.2)")
    ief = etf_leg_returns({v: etf[("IEF", v)] for v in IEF_VENDORS}, ief_vendor, starts, ends)
    bil = etf_leg_returns({v: etf[("BIL", v)] for v in BIL_VENDORS}, bil_vendor, starts, ends)
    bil = np.where(np.isnan(bil), c_syn, bil)  # synthetic cash on both sides before BIL (§5.3.1)
    x_etf = ief - bil

    signal_dates = schedule["signal_date"]
    months = periods.index
    h = {
        "T1": holdings(t1(dgs10, dtb3, signal_dates), months),
        "T2": holdings(t2(dgs10, dtb3, signal_dates), months),
        "T3": holdings(t3(dgs10, dgs7, dtb3, signal_dates), months),
    }
    gate = gate_statistics(h["T1"], x_syn, x_etf)
    passed = gate["G1_pass"] and gate["G2_pass"]

    years = pd.DatetimeIndex(starts).year.to_numpy()
    early, late = years < OVERLAP_SPLIT_YEAR, years >= OVERLAP_SPLIT_YEAR
    descriptive = {
        "split_2003_2007": gate_statistics(h["T1"][early], x_syn[early], x_etf[early]),
        "split_2008_2018": gate_statistics(h["T1"][late], x_syn[late], x_etf[late]),
        "T2": gate_statistics(h["T2"], x_syn, x_etf),
        "T3": gate_statistics(h["T3"], x_syn, x_etf),
    }
    return {
        "study": "006",
        "section": "PREREGISTRATION.md §5.3",
        "outcome": "PASS" if passed else "FAIL: study halts as inconclusive (§5.3.6)",
        "bounds": {"G1_max_annual": G1_MAX, "G2_max": G2_MAX},
        "gate_T1": gate,
        "descriptive_no_decision_weight": descriptive,
        "descriptive_note": "Splits and T2/T3 use their own w (each computed as the gate would be on that subset or signal).",
        "overlap": {
            "first_execution": str(pd.Timestamp(starts.iloc[0]).date()),
            "last_period_end": str(pd.Timestamp(ends.iloc[-1]).date()),
            "ief_vendor_counts": pd.Series(ief_vendor).value_counts().to_dict(),
            "bil_vendor_counts": pd.Series([v or "synthetic cash" for v in bil_vendor]).value_counts().to_dict(),
            "first_bil_execution": str(pd.Timestamp(starts.iloc[first_bil]).date()),
        },
        "periods": pd.DataFrame(
            {
                "month": [str(m) for m in months],
                "execution_date": pd.DatetimeIndex(starts).strftime("%Y-%m-%d"),
                "period_end": pd.DatetimeIndex(ends).strftime("%Y-%m-%d"),
                "h_T1": h["T1"].astype(int),
                "ief_vendor": ief_vendor,
                "bil_vendor": [v or "synthetic cash" for v in bil_vendor],
                "g": x_syn - x_etf,
                "e_T1": (h["T1"] - gate["w_o"]) * (x_syn - x_etf),
            }
        ),
    }


def _commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=STUDY_DIR
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def write(result: dict, out_dir: Path = GATE_DIR) -> None:
    if out_dir.exists():
        raise SystemExit(f"refused: {out_dir.name}/ exists; the gate runs once (§5.3.6)")
    out_dir.mkdir(parents=True)
    periods = result.pop("periods")
    periods.to_csv(out_dir / "periods.csv", index=False)
    result["run_at_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    result["code_commit"] = _commit()
    (out_dir / "gate.json").write_text(json.dumps(result, indent=2) + "\n")
    g = result["gate_T1"]

    def pct(v: float) -> str:
        return f"{v * 100:.3f}%"

    lines = [
        "# Study 006 gate (§5.3), run once",
        "",
        f"**{result['outcome']}**",
        "",
        "| Check | Value | Bound | Pass |",
        "|---|---|---|---|",
        f"| G1, \\|mean(e)\\| × 12 | {pct(g['G1_bias_annual'])} a year | ≤ {pct(G1_MAX)} | {g['G1_pass']} |",
        f"| G2, sd(g) / sd(x_ETF) | {g['G2_noise_ratio']:.3f} | ≤ {G2_MAX:.2f} | {g['G2_pass']} |",
        "",
        f"{g['periods']} periods; w_o {g['w_o']:.3f}; switches {g['switches']}; signed mean(e) × 12 "
        f"{pct(g['mean_e_annual_signed'])}; level gap mean(g) × 12 {pct(g['mean_g_annual'])} (cancels in e); "
        f"corr(g, x_ETF) {g['corr_g_x_etf']:.3f}.",
        "",
        "Descriptive, no decision weight (§5.3.4):",
        "",
        "| Subset | Periods | w | G1 | G2 |",
        "|---|---|---|---|---|",
    ]
    for name, s in result["descriptive_no_decision_weight"].items():
        lines.append(
            f"| {name} | {s['periods']} | {s['w_o']:.3f} | {pct(s['G1_bias_annual'])} | {s['G2_noise_ratio']:.3f} |"
        )
    lines += [
        "",
        f"Run {result['run_at_utc']}, code {result['code_commit'][:7]}. No rule or benchmark return computed.",
        "",
    ]
    (out_dir / "gate.md").write_text("\n".join(lines))
    print("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Study 006 gate (§5.3), run once.").parse_args(argv)
    result = compute()
    write(result)
    return 0 if result["outcome"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
