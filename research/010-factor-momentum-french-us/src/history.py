"""Study 010 history run (PREREGISTRATION.md §8, §9; §14 step 6), once.

Reads the snapshot through ``src.data.load_factors`` (SHA-256 checked against
the data step's manifest), runs T1, T1a and T1b on H (1927-07 to the data
step's H end) at base (c = 0.10) and stress (c = 0.50) timing costs, and
writes ``results/history/``:

- ``monthly_{base,stress}.csv``: the four factors (percent a month, as in the
  snapshot), and per trial T_gross, cost, T, B1, B3, d, K and the positions h;
- ``summary.json``: every §9.3–§9.6 figure, the criteria C1–C4, the window
  row, the verdicts of §9.5 with the return-unit label;
- ``verdict.md``: the verdict table in words.

Refusals: no ``APPROVED`` file; ``results/history/`` exists; no committed
programme-wide count (``results/programme_count.json``, §9.4, §14 step 5).
The shared library's statistics are used unchanged (§6.4); the bootstrap seed
is the programme's 20261021, applied once per cost case.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .data import load_factors
from .rule import COST_BASE, COST_STRESS, TRIALS, run, static_exposure, window

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qune_research import stats  # noqa: E402

SEED = 20261021
N_RESAMPLES = stats.BOOTSTRAP_RESAMPLES  # 10,000 (Study 001 §9.3 items 8-9); the tests lower it
COSTS = {"base": COST_BASE, "stress": COST_STRESS}
N_FAMILY = 3
DSR_ALSO_AT = 10
C1_MARGIN = 0.10
C2_T = 2.0
C3_DSR = 0.95
Z80 = 2.842  # t of 2.0 plus the 80%-power z of 0.842 (QUESTION.md §2.3)
RETURN_UNIT_BAR = 2.0  # % a year
PAPER_WINDOW = ("1964-07", "2015-12")
PAPER_FIGURES = {"tsfm_pct_a_year": 4.2, "tsfm_t": 7.04, "equal_weight_pct_a_year": 4.21, "equal_weight_t": 7.60}
EPISODES = {"1929-09 to 1932-12": ("1929-09", "1932-12"), "2008-09 to 2009-12": ("2008-09", "2009-12")}
PRIMARY = "T1"
COMPANIONS = ("T1a", "T1b")


def _slice(s: pd.Series, a: str, b: str) -> pd.Series:
    return s[(s.index >= pd.Period(a, "M")) & (s.index <= pd.Period(b, "M"))]


def diff_row(d: pd.Series) -> dict:
    """Mean of a monthly difference (percent a month) in % a year, its Newey–West t and its Sharpe."""
    nw = stats.newey_west_mean(d)
    sd = float(d.std(ddof=1))
    return {
        "months": int(len(d)),
        "mean_pct_a_year": float(d.mean() * 12),
        "nw_t": nw["t"],
        "nw_se_pct_a_year": nw["se"] * 12,
        "sharpe_annual": float(d.mean() / sd * math.sqrt(12)) if sd > 0 else float("nan"),
    }


def series_metrics(r: pd.Series, rng: np.random.Generator | None) -> dict:
    """Study 001 §9.3 items 1–3, 4, 6b, 9, 11 for one monthly series (percent a month; B0 is zero)."""
    x = r / 100.0
    out = {
        "months": int(len(x)),
        "mean_pct_a_year": float(r.mean() * 12),
        "geometric_pct_a_year": stats.annualised_geometric_return(x) * 100,
        "vol_pct_a_year": stats.annualised_volatility(x) * 100,
        "sharpe_annual": stats.sharpe_annual(x),
        "sharpe_monthly": stats.sharpe_monthly(x),
        "max_drawdown": stats.max_drawdown(stats.total_return_index(x)),
        "positive_month_share": float((x > 0).mean()),
        "skewness": stats.skewness(x),
        "kurtosis": stats.kurtosis(x),
    }
    if rng is not None and x.std() > 0:
        out["sharpe_ci"] = stats.sharpe_ci_stationary_bootstrap(x, rng, n_resamples=N_RESAMPLES)
    return out


def power_realised(d: pd.Series) -> dict:
    nw = stats.newey_west_mean(d)
    iid_se = float(d.std(ddof=1) / math.sqrt(len(d)))
    sd_a = float(d.std(ddof=1) * math.sqrt(12))
    mde_t2, mde_80 = 2.0 * nw["se"] * 12, Z80 * nw["se"] * 12
    return {
        "nw_over_iid_se": nw["se"] / iid_se,
        "sd_d_pct_a_year": sd_a,
        "mde_t2_pct_a_year": mde_t2,
        "mde_80_pct_a_year": mde_80,
        "mde_t2_sharpe_d": mde_t2 / sd_a,
        "mde_80_sharpe_d": mde_80 / sd_a,
    }


def per_factor(out: dict, f: pd.DataFrame) -> dict:
    h, hbar, K = out["h"], out["hbar"], out["frame"]["K"]
    fh = f.reindex(h.index)[h.columns]
    se = static_exposure(h, hbar)
    rows = {}
    for k in h:
        held = h[k].notna()
        flips = int((h[k].diff().abs() == 2).sum())
        contrib = ((h[k] - hbar[k]) * fh[k] / K).where(held, 0.0)  # gross of costs; (1/K_t)-weighted
        hit = (np.sign(h[k][held]) == np.sign(fh[k][held])) & (fh[k][held] != 0)
        rows[k] = {
            "hbar": float(hbar[k]),
            "months_held": int(held.sum()),
            "flips": flips,
            "flips_per_year": flips / held.sum() * 12,
            "ties": out["ties"][k],
            "long_share": float((h[k][held] > 0).mean()),
            "hit_rate": float(hit.mean()),
            "contribution_to_mean_d_pct_a_year": float(contrib.mean() * 12),
            "contribution_nw_t": stats.newey_west_mean(contrib)["t"],
            "static_exposure": float(se[k]),
        }
    return rows


def criteria(m: dict, stress_mean_d: float) -> dict:
    sT, s1, s3 = m["T"]["sharpe_annual"], m["B1"]["sharpe_annual"], m["B3"]["sharpe_annual"]
    b3_zero = m["B3_identically_zero"]
    c1_b3 = sT >= C1_MARGIN if b3_zero else sT >= s3 + C1_MARGIN
    c = {
        "C1": bool(sT >= s1 + C1_MARGIN and c1_b3),
        "C2": bool(m["d"]["nw_t"] >= C2_T),
        "C3": bool(m["dsr"][f"N{N_FAMILY}"]["dsr"] >= C3_DSR),
        "C4": bool(np.sign(stress_mean_d) == np.sign(m["d"]["mean_pct_a_year"])),
        "C1_B3_leg": "Sharpe(T) >= 0.10 (B3 identically zero)" if b3_zero else "Sharpe(T) >= Sharpe(B3) + 0.10",
    }
    c["all"] = bool(c["C1"] and c["C2"] and c["C3"] and c["C4"])
    return c


def verdict(crit: dict, window_pass: bool, mde_80: float) -> dict:
    own = {k: ("meets C1–C4" if crit[k]["all"] else "not supported") for k in crit}
    if not crit[PRIMARY]["all"]:
        v = "not supported"
    elif not window_pass:
        v = "inconclusive (paper's window only)"
    elif any(own[k] == "not supported" for k in COMPANIONS):
        v = "inconclusive (fragile)"
    else:
        v = "supported in history; forward record pending"
    label = v != "not supported" and mde_80 > RETURN_UNIT_BAR
    return {
        PRIMARY: v + (" (Sharpe units; the 2%-a-year bar not met)" if label else ""),
        **{k: own[k] + (" (Sharpe units; the 2%-a-year bar not met)" if own[k] != "not supported" and label else "")
           for k in COMPANIONS},
        "return_unit_label_applied": bool(label),
        "mde_80_T1_pct_a_year": mde_80,
    }


def compute(f: pd.DataFrame, h_end: str, programme: dict) -> tuple[dict, dict]:
    runs = {case: {k: run(f, t, h_end, c) for k, t in TRIALS.items()} for case, c in COSTS.items()}
    summary: dict = {"h_end": h_end, "seed": SEED, "cost_cases": {}}
    for case in COSTS:
        rng = np.random.default_rng(SEED)
        res = runs[case]
        sh_m = [stats.sharpe_monthly(res[k]["frame"]["T"] / 100) for k in TRIALS]
        var, floored = stats.trial_variance(sh_m)
        block: dict = {"variance_across_trials": var, "floor_applied": floored, "trials": {}}
        for k in TRIALS:
            fr = res[k]["frame"]
            b3_zero = bool((res[k]["hbar"] == 0).all())
            x = fr["T"] / 100
            m = {
                "T": series_metrics(fr["T"], rng),
                "T_gross": series_metrics(fr["T_gross"], None),
                "B1": series_metrics(fr["B1"], rng),
                "B3": series_metrics(fr["B3"], rng) if not b3_zero else None,
                "B3_identically_zero": b3_zero,
                "d": diff_row(fr["d"]),
                "T_minus_B1": diff_row(fr["T"] - fr["B1"]),
                "cost_pct_a_year": float(fr["cost"].mean() * 12),
                "sharpe_test_vs_B1": stats.ledoit_wolf_sharpe_test(fr["T"] / 100, fr["B1"] / 100, rng, n_resamples=N_RESAMPLES),
                "sharpe_test_vs_B3": (stats.ledoit_wolf_sharpe_test(fr["T"] / 100, fr["B3"] / 100, rng,
                                                                    n_resamples=N_RESAMPLES)
                                      if not b3_zero else None),
                "dsr": {
                    f"N{n}": stats.deflated_sharpe(stats.sharpe_monthly(x), len(x), stats.skewness(x),
                                                   stats.kurtosis(x), n, var)
                    for n in sorted({N_FAMILY, DSR_ALSO_AT, programme["public_trials_md"],
                                     programme["with_desk_registry"]})
                },
                "windows": {w: diff_row(window(fr, w)["d"]) for w in ("P1", "L", "P2", "P")},
                "per_factor": per_factor(res[k], f),
                "flips_total_per_year": float(sum((res[k]["h"][c].diff().abs() == 2).sum() for c in res[k]["h"])
                                              / len(fr) * 12),
                "power_realised": power_realised(fr["d"]),
            }
            if b3_zero:
                m["B3"] = {"sharpe_annual": float("nan")}
            block["trials"][k] = m
        summary["cost_cases"][case] = block

    base, stress = summary["cost_cases"]["base"]["trials"], summary["cost_cases"]["stress"]["trials"]
    crit = {k: criteria(base[k], stress[k]["d"]["mean_pct_a_year"]) for k in TRIALS}
    d1 = runs["base"][PRIMARY]["frame"]["d"]
    win = {**diff_row(window(runs["base"][PRIMARY]["frame"], "P")["d"]), "rule": "mean(d^T1) over P > 0, base costs"}
    win["pass"] = bool(win["mean_pct_a_year"] > 0)
    summary["criteria"] = crit
    summary["window_row_T1"] = win
    summary["verdict"] = verdict(crit, win["pass"], base[PRIMARY]["power_realised"]["mde_80_pct_a_year"])

    t1 = runs["base"][PRIMARY]["frame"]
    decades = {}
    for dec, grp in d1.groupby((d1.index.year // 10) * 10):
        decades[f"{dec}s"] = diff_row(grp)
    worst = d1.nsmallest(12)
    summary["descriptive_T1"] = {
        "d_by_decade": decades,
        "twelve_worst_months_d": [{"month": str(p), "d_pct": float(v)} for p, v in worst.items()],
        "episodes_d": {
            name: {"months": int(len(s)), "sum_pct": float(s.sum()), "mean_pct_a_year": float(s.mean() * 12)}
            for name, (a, b) in EPISODES.items()
            for s in [_slice(d1, a, b)]
        },
        "paper_comparison": {
            "paper": PAPER_FIGURES,
            "note": "different factor set and construction; descriptive only (§9.6)",
            **{
                label: {
                    "T1_gross": diff_row(_slice(t1["T_gross"], a, b)),
                    "T1_base": diff_row(_slice(t1["T"], a, b)),
                    "B1": diff_row(_slice(t1["B1"], a, b)),
                }
                for label, (a, b) in {"paper_strategy_months": PAPER_WINDOW, "H": ("1927-07", h_end)}.items()
            },
        },
    }
    summary["programme_count"] = programme
    return summary, runs


def monthly_csv(f: pd.DataFrame, runs_case: dict) -> pd.DataFrame:
    idx = runs_case[PRIMARY]["frame"].index
    cols = {f"f_{k}": f[k].reindex(idx) for k in ["SMB", "HML", "ST_Rev", "LT_Rev"]}
    for t, out in runs_case.items():
        for c in ["T_gross", "cost", "T", "B1", "B3", "d", "K"]:
            cols[f"{t}_{c}"] = out["frame"][c]
        for k in out["h"]:
            cols[f"{t}_h_{k}"] = out["h"][k]
    frame = pd.DataFrame(cols)
    frame.index = frame.index.astype(str)
    frame.index.name = "month"
    return frame


def write_verdict(summary: dict, path: Path) -> None:
    b = summary["cost_cases"]["base"]["trials"]
    lines = [
        "# Study 010 history run: verdict (§9.5)",
        "",
        f"H: 1927-07 to {summary['h_end']}. Base timing costs 10 bp; C4 at 50 bp. C3 at N = {N_FAMILY}.",
        "",
        "| Trial | Sharpe T | Sharpe B1 | Sharpe B3 | mean d (% a year) | NW t of d | DSR N=3 | C1 | C2 | C3 | C4 | Row |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for k in TRIALS:
        m, c = b[k], summary["criteria"][k]
        lines.append(
            f"| {k} | {m['T']['sharpe_annual']:.3f} | {m['B1']['sharpe_annual']:.3f} | {m['B3']['sharpe_annual']:.3f} | "
            f"{m['d']['mean_pct_a_year']:+.2f} | {m['d']['nw_t']:.2f} | {m['dsr'][f'N{N_FAMILY}']['dsr']:.3f} | "
            f"{'pass' if c['C1'] else 'fail'} | {'pass' if c['C2'] else 'fail'} | {'pass' if c['C3'] else 'fail'} | "
            f"{'pass' if c['C4'] else 'fail'} | {summary['verdict'][k]} |"
        )
    w = summary["window_row_T1"]
    lines += [
        "",
        f"Window row (T1, P = P1 and P2, {w['months']} months): mean d {w['mean_pct_a_year']:+.2f}% a year, "
        f"NW t {w['nw_t']:.2f} (reported, not tested): **{'pass' if w['pass'] else 'fail'}**.",
        "",
        f"**Verdict (T1): {summary['verdict'][PRIMARY]}.**",
        "",
    ]
    path.write_text("\n".join(lines))


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


def main(argv: list[str] | None = None, here: Path = HERE) -> None:
    argparse.ArgumentParser(description="Study 010 history run (§8, §9), once.").parse_args(argv)
    if not (here / "APPROVED").is_file() or not (here / "APPROVED").read_text().strip():
        raise SystemExit("refused: no APPROVED file (§14 step 4)")
    out_dir = here / "results" / "history"
    if out_dir.exists():
        raise SystemExit("refused: results/history/ exists; the history run is executed once (§14 step 6)")
    count_path = here / "results" / "programme_count.json"
    if not count_path.exists():
        raise SystemExit("refused: results/programme_count.json missing; the re-count comes first (§9.4, §14 step 5)")
    programme = json.loads(count_path.read_text())
    h_end = json.loads((here / "results" / "data_step.json").read_text())["h_end"]
    f = load_factors(here / "data" / "raw", here / "results" / "data_manifest.json")
    summary, runs = compute(f, h_end, programme)
    summary["run_at_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_dir.mkdir(parents=True)
    for case in COSTS:
        monthly_csv(f, runs[case]).to_csv(out_dir / f"monthly_{case}.csv", float_format="%.17g")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=_json_default) + "\n")
    write_verdict(summary, out_dir / "verdict.md")
    print((out_dir / "verdict.md").read_text())


if __name__ == "__main__":
    main()
