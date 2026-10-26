"""Study 011 history run (PREREGISTRATION.md §8, §9; §14 step 6), once.

Reads the snapshot through ``src.data.load_industries`` (SHA-256 checked
against the data step's manifest), runs M1, M1a and M1b from their first
holding months to the data step's last common month at base (c = 0.10) and
stress (c = 0.50) one-way costs, and writes ``results/history/``:

- ``monthly.csv``: per trial d_gross, turnover, d_base, d_stress, the legs,
  EW, empty legs and boundary ties;
- ``cohorts.json``: W(m), L(m) and boundary near-ties of every ranking month, per trial;
- ``industries_17.csv``, ``industries_30.csv``: the snapshot's value-weighted
  monthly returns (percent, as printed), so every figure can be recomputed;
- ``summary.json``: every §9.3-§9.6 figure, the criteria C1-C4, the window
  row, the verdicts of §9.5 with the return-unit label;
- ``verdict.md``: the verdict table in words.

The decision row O is I1 and I2 together; its Newey-West uses
``src.stats011.newey_west_stretches`` (§9.3), every other row the shared
library's ordinary estimator. Refusals: no ``APPROVED`` file;
``results/history/`` exists; no committed programme-wide count; no history-run
row in ``trials.md``. The bootstrap seed is the programme's 20261021, applied
once per cost case.
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

from .data import load_industries
from .rule import cohort_table, run
from .stats011 import newey_west_stretches

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qune_research import stats  # noqa: E402

SEED = 20261021
N_RESAMPLES = stats.BOOTSTRAP_RESAMPLES  # 10,000; the tests lower it
N_FAMILY = 3
DSR_ALSO_AT = 11
C1_SHARPE = 0.10
C2_T = 2.0
C3_DSR = 0.95
Z80 = 2.842
RETURN_UNIT_BAR = 2.0  # % a year
TRIALS = {
    "M1": {"set": 17, "F": 6, "n": 3, "first": "1927-06"},
    "M1a": {"set": 30, "F": 6, "n": 5, "first": "1927-06"},
    "M1b": {"set": 17, "F": 12, "n": 3, "first": "1927-12"},
}
I1_END = "1963-06"
M_WINDOW = ("1963-07", "1995-07")
I2_START = "1995-08"
PAPER_PCT_A_MONTH = 0.43
EPISODES = {"1929-09 to 1932-12": ("1929-09", "1932-12"), "2008-09 to 2009-12": ("2008-09", "2009-12")}
PRIMARY = "M1"
COMPANIONS = ("M1a", "M1b")
CASES = ("base", "stress")


def _slice(s: pd.Series, a: str, b: str) -> pd.Series:
    return s[(s.index >= pd.Period(a, "M")) & (s.index <= pd.Period(b, "M"))]


def stretches(s: pd.Series, first: str, end: str) -> tuple[pd.Series, pd.Series]:
    return _slice(s, first, I1_END), _slice(s, I2_START, end)


def diff_row(d: pd.Series) -> dict:
    """Mean (percent a month -> % a year), ordinary Newey-West t, Sharpe of a single-stretch series."""
    nw = stats.newey_west_mean(d)
    sd = float(d.std(ddof=1))
    return {
        "months": int(len(d)),
        "mean_pct_a_year": float(d.mean() * 12),
        "nw_t": nw["t"],
        "nw_se_pct_a_year": nw["se"] * 12,
        "sharpe_annual": float(d.mean() / sd * math.sqrt(12)) if sd > 0 else float("nan"),
    }


def o_row(i1: pd.Series, i2: pd.Series) -> dict:
    """The decision row O: two-stretch Newey-West (§9.3)."""
    d = pd.concat([i1, i2])
    nw = newey_west_stretches([i1, i2])
    sd = float(d.std(ddof=1))
    iid_se = sd / math.sqrt(len(d))
    sd_a = sd * math.sqrt(12)
    return {
        "months": int(len(d)),
        "months_I1": int(len(i1)),
        "months_I2": int(len(i2)),
        "mean_pct_a_year": float(d.mean() * 12),
        "nw_t": nw["t"],
        "nw_se_pct_a_year": nw["se"] * 12,
        "iid_t": float(d.mean() / iid_se) if sd > 0 else float("nan"),
        "sharpe_annual": float(d.mean() / sd * math.sqrt(12)) if sd > 0 else float("nan"),
        "power_realised": {
            "nw_over_iid_se": nw["se"] / iid_se,
            "sd_d_pct_a_year": sd_a,
            "mde_t2_pct_a_year": 2.0 * nw["se"] * 12,
            "mde_80_pct_a_year": Z80 * nw["se"] * 12,
            "mde_t2_sharpe_d": 2.0 * nw["se"] * 12 / sd_a,
            "mde_80_sharpe_d": Z80 * nw["se"] * 12 / sd_a,
        },
    }


def _o_brief(i1: pd.Series, i2: pd.Series) -> dict:
    r = o_row(i1, i2)
    return {k: r[k] for k in ("months", "mean_pct_a_year", "nw_t", "nw_se_pct_a_year", "sharpe_annual")}


def series_metrics(r: pd.Series, rng: np.random.Generator | None) -> dict:
    x = r / 100.0
    out = {
        "months": int(len(x)),
        "vol_pct_a_year": stats.annualised_volatility(x) * 100,
        "sharpe_annual": stats.sharpe_annual(x),
        "sharpe_monthly": stats.sharpe_monthly(x),
        "positive_month_share": float((x > 0).mean()),
        "skewness": stats.skewness(x),
        "kurtosis_non_excess": stats.kurtosis(x),
    }
    if rng is not None and x.std() > 0:
        out["sharpe_ci"] = stats.sharpe_ci_stationary_bootstrap(x, rng, n_resamples=N_RESAMPLES)
    return out


def criteria(o_base: dict, dsr_n3: float, o_stress_mean: float) -> dict:
    c = {
        "C1": bool(o_base["sharpe_annual"] >= C1_SHARPE),
        "C2": bool(o_base["nw_t"] >= C2_T),
        "C3": bool(dsr_n3 >= C3_DSR),
        "C4": bool(np.sign(o_stress_mean) == np.sign(o_base["mean_pct_a_year"])),
    }
    c["all"] = bool(c["C1"] and c["C2"] and c["C3"] and c["C4"])
    return c


def verdict(crit: dict, window_pass: bool, mde_80: float) -> dict:
    own = {k: ("meets C1–C4" if crit[k]["all"] else "not supported") for k in crit}
    if not crit[PRIMARY]["all"]:
        v = "not supported"
    elif not window_pass:
        v = "inconclusive (one side of the paper's sample only)"
    elif any(own[k] == "not supported" for k in COMPANIONS):
        v = "inconclusive (fragile)"
    else:
        v = "supported in history; forward record pending"
    bar_not_met = bool(mde_80 > RETURN_UNIT_BAR)
    suffix = " (Sharpe units; the 2%-a-year bar not met)"
    rows = {PRIMARY: v, **{k: own[k] for k in COMPANIONS}}
    return {
        **{k: r + (suffix if bar_not_met and r != "not supported" else "") for k, r in rows.items()},
        "return_unit_bar_not_met": bar_not_met,
        "mde_80_M1_pct_a_year": mde_80,
    }


def compute(ind: dict[int, pd.DataFrame], end: str, programme: dict) -> tuple[dict, dict, dict]:
    frames = {k: run(ind[t["set"]], t["F"], t["n"], pd.Period(t["first"], "M")) for k, t in TRIALS.items()}
    frames = {k: f[f.index <= pd.Period(end, "M")] for k, f in frames.items()}
    cohorts = {
        k: cohort_table(ind[t["set"]], t["F"], t["n"], pd.Period(t["first"], "M") - 6) for k, t in TRIALS.items()
    }
    summary: dict = {"end": end, "seed": SEED, "cost_cases": {}}
    for case in CASES:
        rng = np.random.default_rng(SEED)
        col = f"d_{case}"
        o_series = {k: pd.concat(stretches(f[col], TRIALS[k]["first"], end)) for k, f in frames.items()}
        var, floored = stats.trial_variance([stats.sharpe_monthly(o_series[k] / 100) for k in TRIALS])
        block: dict = {"variance_across_trials": var, "floor_applied": floored, "trials": {}}
        for k, f in frames.items():
            i1, i2 = stretches(f[col], TRIALS[k]["first"], end)
            x = o_series[k] / 100
            block["trials"][k] = {
                "O": o_row(i1, i2),
                "O_series": series_metrics(o_series[k], rng),
                "dsr": {
                    f"N{n}": stats.deflated_sharpe(stats.sharpe_monthly(x), len(x), stats.skewness(x),
                                                   stats.kurtosis(x), n, var)
                    for n in sorted({N_FAMILY, DSR_ALSO_AT, programme["public_trials_md"],
                                     programme["with_desk_registry"]})
                },
                "windows": {
                    "I1": diff_row(i1),
                    "I2": diff_row(i2),
                    "M": diff_row(_slice(f[col], *M_WINDOW)),
                    "full": diff_row(f[col]),
                },
                "turnover_per_year": float(f["turnover"].mean() * 12),
                "cost_pct_a_year_on_O": float((pd.concat(stretches(f["d_gross"], TRIALS[k]["first"], end))
                                               - o_series[k]).mean() * 12),
            }
        summary["cost_cases"][case] = block

    base, stress = summary["cost_cases"]["base"]["trials"], summary["cost_cases"]["stress"]["trials"]
    crit = {k: criteria(base[k]["O"], base[k]["dsr"][f"N{N_FAMILY}"]["dsr"], stress[k]["O"]["mean_pct_a_year"])
            for k in TRIALS}
    w1, w2 = base[PRIMARY]["windows"]["I1"], base[PRIMARY]["windows"]["I2"]
    win = {"I1_mean_pct_a_year": w1["mean_pct_a_year"], "I1_nw_t": w1["nw_t"],
           "I2_mean_pct_a_year": w2["mean_pct_a_year"], "I2_nw_t": w2["nw_t"],
           "rule": "mean(d^M1) > 0 over I1 and > 0 over I2, base costs",
           "pass": bool(w1["mean_pct_a_year"] > 0 and w2["mean_pct_a_year"] > 0)}
    summary["criteria"] = crit
    summary["window_row_M1"] = win
    summary["verdict"] = verdict(crit, win["pass"], base[PRIMARY]["O"]["power_realised"]["mde_80_pct_a_year"])

    f1 = frames[PRIMARY]
    d1 = f1["d_base"]
    decades = {f"{dec}s": diff_row(g) for dec, g in d1.groupby((d1.index.year // 10) * 10)}
    legs = {}
    i1w, i2w = stretches(f1["winners_leg"] - f1["ew"], TRIALS[PRIMARY]["first"], end)
    i1l, i2l = stretches(f1["losers_leg"] - f1["ew"], TRIALS[PRIMARY]["first"], end)
    i1e, i2e = stretches(f1["ew"], TRIALS[PRIMARY]["first"], end)
    legs["O"] = {"winners_minus_ew": _o_brief(i1w, i2w), "losers_minus_ew": _o_brief(i1l, i2l), "ew": _o_brief(i1e, i2e)}
    for name, (a, b) in {"I1": (TRIALS[PRIMARY]["first"], I1_END), "I2": (I2_START, end), "M": M_WINDOW,
                         "full": (TRIALS[PRIMARY]["first"], end)}.items():
        legs[name] = {"winners_minus_ew": diff_row(_slice(f1["winners_leg"] - f1["ew"], a, b)),
                      "losers_minus_ew": diff_row(_slice(f1["losers_leg"] - f1["ew"], a, b)),
                      "ew": diff_row(_slice(f1["ew"], a, b))}
    held = {m: v for m, v in cohorts[PRIMARY].items() if pd.Period(m, "M") < pd.Period(end, "M")}
    share = {c: {"W": sum(c in v[0] for v in held.values()) / len(held),
                 "L": sum(c in v[1] for v in held.values()) / len(held)} for c in ind[17].columns}
    worst = d1.nsmallest(12)
    summary["descriptive_M1"] = {
        "d_by_decade": decades,
        "legs": legs,
        "industry_share_in_W_and_L": share,
        "twelve_worst_months_d": [{"month": str(p), "d_pct": float(v)} for p, v in worst.items()],
        "episodes_d": {
            name: {"months": int(len(s)), "sum_pct": float(s.sum()), "mean_pct_a_year": float(s.mean() * 12)}
            for name, (a, b) in EPISODES.items() for s in [_slice(d1, a, b)]
        },
        "paper_comparison": {
            "paper_pct_a_month": PAPER_PCT_A_MONTH,
            "M1_gross_over_M_pct_a_month": float(_slice(f1["d_gross"], *M_WINDOW).mean()),
            "note": "the library's 17 four-digit-SIC industries, not the paper's 20; descriptive only (§9.6)",
        },
    }
    summary["data_events"] = {
        k: {"months_with_empty_legs": int((f["empty_legs"] > 0).sum()),
            "boundary_ties_over_held_ranking_months": int(sum(v[2] for m, v in cohorts[k].items()
                                                              if pd.Period(m, "M") < pd.Period(end, "M")))}
        for k, f in frames.items()
    }
    summary["programme_count"] = programme
    return summary, frames, cohorts


def monthly_csv(frames: dict) -> pd.DataFrame:
    cols = {}
    for k, f in frames.items():
        for c in f.columns:
            cols[f"{k}_{c}"] = f[c]
    frame = pd.DataFrame(cols)
    frame.index = frame.index.astype(str)
    frame.index.name = "month"
    return frame


def write_verdict(summary: dict, path: Path) -> None:
    b = summary["cost_cases"]["base"]["trials"]
    lines = [
        "# Study 011 history run: verdict (§9.5)",
        "",
        f"O = I1 and I2, to {summary['end']}. Base costs 10 bp one way; C4 at 50 bp. C3 at N = {N_FAMILY}. "
        "The rule is a variant of [MG99]'s on the library's industries.",
        "",
        "| Trial | months O | mean d (% a year) | NW t (two-stretch) | Sharpe of d | DSR N=3 | C1 | C2 | C3 | C4 | Row |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for k in TRIALS:
        o, c = b[k]["O"], summary["criteria"][k]
        lines.append(
            f"| {k} | {o['months']:,} | {o['mean_pct_a_year']:+.2f} | {o['nw_t']:.2f} | {o['sharpe_annual']:.3f} | "
            f"{b[k]['dsr'][f'N{N_FAMILY}']['dsr']:.3f} | " + " | ".join("pass" if c[x] else "fail" for x in ("C1", "C2", "C3", "C4"))
            + f" | {summary['verdict'][k]} |"
        )
    w = summary["window_row_M1"]
    lines += [
        "",
        f"Window row (M1): I1 mean d {w['I1_mean_pct_a_year']:+.2f}% a year (NW t {w['I1_nw_t']:.2f}); "
        f"I2 {w['I2_mean_pct_a_year']:+.2f}% a year (NW t {w['I2_nw_t']:.2f}); t reported, not tested: "
        f"**{'pass' if w['pass'] else 'fail'}**.",
        "",
        f"**Verdict (M1): {summary['verdict'][PRIMARY]}.**",
        "",
    ]
    path.write_text("\n".join(lines))


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


HISTORY_ROW = "| History run (§14 step 6), logged before it runs"


def check_programme_count(programme: dict) -> None:
    for key in ("public_trials_md", "with_desk_registry"):
        v = programme.get(key)
        if not isinstance(v, int) or isinstance(v, bool) or v < 2:
            raise SystemExit(f"refused: programme_count.json '{key}' must be an integer >= 2 (§9.4)")
    if not str(programme.get("method", "")).strip():
        raise SystemExit("refused: programme_count.json has no 'method' (§9.4: the method of the count)")


def main(argv: list[str] | None = None, here: Path = HERE) -> None:
    argparse.ArgumentParser(description="Study 011 history run (§8, §9), once.").parse_args(argv)
    if not (here / "APPROVED").is_file() or not (here / "APPROVED").read_text().strip():
        raise SystemExit("refused: no APPROVED file (§14 step 4)")
    out_dir = here / "results" / "history"
    tmp_dir = here / "results" / ".history_tmp"
    if out_dir.exists():
        raise SystemExit("refused: results/history/ exists; the history run is executed once (§14 step 6)")
    if tmp_dir.exists():
        raise SystemExit("refused: results/.history_tmp/ exists: an earlier run read the data and stopped; "
                         "a dated §16 amendment is needed before any re-run")
    count_path = here / "results" / "programme_count.json"
    if not count_path.exists():
        raise SystemExit("refused: results/programme_count.json missing; the re-count comes first (§9.4, §14 step 5)")
    programme = json.loads(count_path.read_text())
    check_programme_count(programme)
    if HISTORY_ROW not in (here / "trials.md").read_text():
        raise SystemExit("refused: trials.md has no history-run row; it is logged before the run (§14 step 5)")
    data_step = json.loads((here / "results" / "data_step.json").read_text())
    end = data_step["last_common_month"]
    # every check above runs before the first industry value is read; the marker below is written first,
    # so a run that stops after reading the data leaves results/.history_tmp/ behind and blocks a re-run
    tmp_dir.mkdir(parents=True)
    (tmp_dir / "STARTED").write_text(datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") + "\n")
    ind = load_industries(here / "data" / "raw", here / "results" / "data_manifest.json")
    summary, frames, cohorts = compute(ind, end, programme)
    summary["run_at_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary["eligibility_from_data_step"] = {
        k: {key: v[key] for key in ("ranking_months", "min_eligible")} | {"months_below_full_set": len(v["months_below_full_set"])}
        for k, v in data_step.get("eligibility", {}).items()
    }
    monthly_csv(frames).to_csv(tmp_dir / "monthly.csv", float_format="%.17g")
    (tmp_dir / "cohorts.json").write_text(json.dumps(cohorts, indent=1) + "\n")
    for n, f in ind.items():
        g = f.copy()
        g.index = g.index.astype(str)
        g.index.name = "month"
        g.to_csv(tmp_dir / f"industries_{n}.csv")
    (tmp_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=_json_default) + "\n")
    write_verdict(summary, tmp_dir / "verdict.md")
    tmp_dir.rename(out_dir)  # results/history/ appears only when every output is written
    print((out_dir / "verdict.md").read_text())


if __name__ == "__main__":
    main()
