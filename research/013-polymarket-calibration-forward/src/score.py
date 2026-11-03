"""Study 013 scoring run (PREREGISTRATION.md §9; §14 step 9), once, after `APPROVED`.

The only step that opens the resolution fetch's outcome file. It reads the
data step's sample (`results/sample.jsonl`, git-ignored, SHA-256 checked against
`results/data_manifest.json`), the fetch's `status.jsonl` and `outcome.jsonl`
(both checked against the fetch's provenance line in
`paper-log/resolution_fetch.csv`), applies the outcome rule of §6.5 to every
sampled market (`src/outcome.py`), and fits the test object of §9.1 with the
estimator of `src/fit.py`:

- per trial (C1, C1a, C1b) on W, W1 and W2: n, G, b-hat, a-hat, SE_cl,
  SE_ordinary, the clustered bootstrap interval (W only), t_cl, the
  log-likelihood of the fit and of the calibrated model (§9.6);
- C1-C4 and the verdict table of §9.5 with its precedence; the low-power label
  read from the data step's recomputed ratio for C1; the Bonferroni bars of
  §9.4 at N = 3 (decides), N = 12 and the programme-wide count (no weight);
- the ten-bin reliability table, Brier, log-loss and Brier skill (§9.6);
- the descriptive splits listed in §9.6 before any outcome was read: early
  closes against the rest, tag families (fewer than 500 markets pooled into
  "other"), liquidity terciles of the volume at the horizon, realised-horizon
  halves; each with b-hat and a clustered Wald interval, no decision weight;
- every exclusion at scoring by the kind of §6.5, in the order written.

What it writes, under `results/score/` (aggregates only, never a per-market
row): `summary.json`, `verdict.md`, `slopes.csv` (one row per fitted subset)
and `reliability.csv`. The outcome rule's inputs leave no trace beyond the
counts.

Refusals (exit 1, nothing written), in this order: no non-empty `APPROVED`
(§14 step 5); `results/score/` exists (the run is executed once, §14 step 9);
no data-step report (§14 step 6 first); the data step halted (the study ended
there with its verdict row, §5.4) or stopped for a gap amendment that has not
been followed by a re-run; no `results/programme_count.json` or a malformed one
(§9.4, §14 step 7); no scoring-run row in `trials.md` (logged before the run,
§14 step 7); a sample, status or outcome file whose SHA-256 differs from the
one recorded when it was written.

Every path is passed by name (tools/check_bound_defaults.py). The bootstrap's
resample count is a parameter only so that the tests can lower it; the command
line never changes it.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np

from src import fit, outcome
from src.data_step import TRIALS, Refusal

UTC = dt.UTC

SCORING_ROW = "| Scoring run logged (§14 step 7)"  # the first cell of the trials.md row written before the run
MIN_FAMILY = 500  # §9.6: a tag family with fewer markets is pooled into "other"
N_FAMILY = 3  # §9.4: C3 decides here
N_STUDIES = 12  # §9.4: one per study to date, reported beside, no weight
WALD_Z = 1.96  # the clustered interval of the descriptive splits (§9.6)
WINDOW_TEXT = "W: closedTime in [2026-11-04, 2026-12-30)"
LOW_POWER_LABEL = "(low-power check: the published effect could not have been seen at 80 percent power)"
PUBLISHED_B_WA26 = 1.112  # [WA26], descriptive comparison only (§9.6)
FLOOR_TEXT = "floor 10,000 USDC and spread <= 0.10 at the horizon"
SLOPE_COLUMNS = (
    "trial", "row", "n", "G", "a", "b", "se_cl", "se_ordinary", "t_cl", "wald_low", "wald_high",
    "boot_low", "boot_high", "boot_dropped", "boot_available", "converged", "separated", "loglik", "loglik_calibrated",
)
RELIABILITY_COLUMNS = ("trial", "bin_low", "bin_high", "n", "clusters", "mean_p", "outcome_share", "diff_pp", "ci_low_pp", "ci_high_pp")


def bonferroni_bar(n: int) -> float:
    """One-sided 0.05 / n on the standard normal (§9.4): 2.128 at N = 3, 2.638 at N = 12."""
    return float(NormalDist().inv_cdf(1.0 - 0.05 / n))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl_by_id(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                out[str(r.get("id"))] = r
    return out


def read_sample(path: Path) -> dict[str, list[dict]]:
    by_trial: dict[str, list[dict]] = {name: [] for name in TRIALS}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                by_trial.setdefault(str(r["trial"]), []).append(r)
    return by_trial


def check_programme_count(d: dict) -> None:
    for key in ("public_trials_md", "with_desk_registry"):
        v = d.get(key)
        if not isinstance(v, int) or isinstance(v, bool) or v < 2:
            raise Refusal(f"programme_count.json '{key}' must be an integer >= 2 (§9.4)")
    if not isinstance(d.get("method"), str) or not d["method"].strip():
        raise Refusal("programme_count.json has no 'method' (§9.4: the method of the count)")


def _nan_row(n: int = 0) -> dict[str, Any]:
    return {"n": n, "G": 0, "a": float("nan"), "b": float("nan"), "converged": False, "separated": False,
            "fitted": False, "se_cl": float("nan"), "se_ordinary": float("nan"), "t_cl": float("nan"),
            "wald_low": float("nan"), "wald_high": float("nan"), "loglik": float("nan"), "loglik_calibrated": float("nan"),
            "iterations": 0}


def fit_subset(rows: list[dict], resamples: int = 0) -> dict[str, Any]:
    """The §9.6 figures for one set of scored rows; the bootstrap only when `resamples` > 0 (the W rows)."""
    n = len(rows)
    if n == 0:
        return _nan_row(0)
    p = np.array([r["price"] for r in rows], dtype=np.float64)
    y = np.array([r["y"] for r in rows], dtype=np.float64)
    g = np.array([r["cluster"] for r in rows])
    out = _nan_row(n)
    out["G"] = int(np.unique(g).size)
    if y.min() == y.max():
        out["one_outcome_only"] = True
        return out
    x = fit.logit(p)
    f = fit.fit_logistic(x, y)
    se_cl, g_count = fit.se_clustered_b(f, x, y, g)
    t_cl = (f.b - 1.0) / se_cl if np.isfinite(se_cl) and se_cl > 0 else float("nan")
    out.update({
        "G": g_count, "a": f.a, "b": f.b, "converged": f.converged, "separated": f.separated, "fitted": f.converged,
        "se_cl": se_cl, "se_ordinary": f.se_ordinary_b, "t_cl": float(t_cl),
        "wald_low": f.b - WALD_Z * se_cl if np.isfinite(se_cl) else float("nan"),
        "wald_high": f.b + WALD_Z * se_cl if np.isfinite(se_cl) else float("nan"),
        "loglik": f.loglik, "loglik_calibrated": f.loglik_calibrated, "iterations": f.iterations,
    })
    if resamples > 0:
        bs = fit.cluster_bootstrap(x, y, g, resamples=resamples)
        out["bootstrap"] = {"low": bs.low, "high": bs.high, "resamples": bs.resamples, "dropped": bs.dropped,
                            "available": bs.available}
    return out


def tag_family_groups(rows: list[dict]) -> dict[str, list[dict]]:
    """§9.6: families with fewer than MIN_FAMILY markets pooled into "other"; "other" is listed last."""
    counts = Counter(r["tag_family"] for r in rows)
    groups: dict[str, list[dict]] = {}
    for r in rows:
        fam = r["tag_family"] if counts[r["tag_family"]] >= MIN_FAMILY and r["tag_family"] != "other" else "other"
        groups.setdefault(fam, []).append(r)
    ordered = {k: groups[k] for k in sorted(groups) if k != "other"}
    if "other" in groups:
        ordered["other"] = groups["other"]
    return ordered


def score_trial(name: str, rows: list[dict], status: dict[str, dict], outcomes: dict[str, dict], resamples: int) -> dict[str, Any]:
    """One trial: the outcome rule on every sampled market, then every §9.6 figure on the scored rows."""
    kinds: Counter = Counter()
    scored: list[dict] = []
    for r in rows:
        mid = str(r["market"])
        kind = outcome.classify(status.get(mid), outcomes.get(mid), str(r["first_token"]))
        y = outcome.y_of(kind)
        if y is None:
            kinds[kind] += 1
            continue
        scored.append({**r, "y": y})
    rows_w = fit_subset(scored, resamples=resamples)
    rows_w1 = fit_subset([r for r in scored if r["half"] == "W1"])
    rows_w2 = fit_subset([r for r in scored if r["half"] == "W2"])
    crit = fit.criteria(rows_w["b"], rows_w["se_cl"], rows_w1["b"], rows_w2["b"], rows_w["converged"])
    p = np.array([r["price"] for r in scored], dtype=np.float64)
    y = np.array([r["y"] for r in scored], dtype=np.float64)
    g = np.array([r["cluster"] for r in scored])
    reliability = fit.reliability_table(p, y, g) if scored else []
    sc = fit.scores(p, y) if scored and y.min() != y.max() else {}
    early = [r for r in scored if r["early"]]
    not_early = [r for r in scored if not r["early"]]
    splits: dict[str, dict[str, Any]] = {"early": fit_subset(early), "not early": fit_subset(not_early)}
    for fam, members in tag_family_groups(scored).items():
        splits[f"tag:{fam}"] = fit_subset(members)
    if scored:
        vol = np.array([r["volume_at_horizon"] for r in scored], dtype=np.float64)
        q1, q2 = (float(v) for v in np.quantile(vol, [1.0 / 3.0, 2.0 / 3.0]))
        splits["liquidity:low tercile"] = fit_subset([r for r in scored if r["volume_at_horizon"] < q1])
        splits["liquidity:middle tercile"] = fit_subset([r for r in scored if q1 <= r["volume_at_horizon"] < q2])
        splits["liquidity:high tercile"] = fit_subset([r for r in scored if r["volume_at_horizon"] >= q2])
        hz = np.array([r["realised_horizon_hours"] for r in scored], dtype=np.float64)
        med = float(np.median(hz))
        splits["horizon:below median"] = fit_subset([r for r in scored if r["realised_horizon_hours"] < med])
        splits["horizon:at or above median"] = fit_subset([r for r in scored if r["realised_horizon_hours"] >= med])
        split_cuts = {"liquidity_tercile_cuts_usdc": [q1, q2], "realised_horizon_median_hours": med}
    else:
        split_cuts = {}
    return {
        "horizon_hours": TRIALS[name]["h"],
        "sampled": len(rows),
        "scored": len(scored),
        "excluded_at_scoring": {k: kinds.get(k, 0) for k in outcome.KINDS},
        "sports_share": float(np.mean([r["sports"] for r in scored])) if scored else float("nan"),
        "first_label_yes_share": float(np.mean([r["first_label_yes"] for r in scored])) if scored else float("nan"),
        "early_share": float(np.mean([r["early"] for r in scored])) if scored else float("nan"),
        "rows": {"W": rows_w, "W1": rows_w1, "W2": rows_w2},
        "criteria": crit,
        "reliability": reliability,
        "scores": sc,
        "splits": splits,
        "split_cuts": split_cuts,
    }


def verdict_sentence(core: str, trial: dict, low_power: bool) -> str:
    """§9.5: every verdict states the horizon, the floor and the Sports share; the window dates for 'supported'."""
    s = f"{core} ({WINDOW_TEXT})" if core.startswith("supported") else core
    s += (f"; h = {trial['horizon_hours']} h; {FLOOR_TEXT}; Sports share {trial['sports_share']:.3f} of the scored sample; "
          f"n = {trial['scored']}, G = {trial['rows']['W']['G']}")
    if low_power:
        s += " " + LOW_POWER_LABEL
    return s


def companion_row(trial: dict) -> str:
    w = trial["rows"]["W"]
    if not w["converged"]:
        return "not supported (no fit)"
    return "meets C1–C4" if trial["criteria"]["all"] else "not supported"


def run_score(
    *,
    approved: Path,
    trials_md: Path,
    data_step_json: Path,
    data_manifest_json: Path,
    sample_jsonl: Path,
    programme_count_json: Path,
    status_jsonl: Path,
    outcome_jsonl: Path,
    fetch_log_csv: Path,
    out_dir: Path,
    now: dt.datetime | None = None,
    resamples: int = fit.BOOTSTRAP_RESAMPLES,
) -> dict[str, Any]:
    """The scoring run. Writes the four outputs under `out_dir` and returns the summary dict."""
    if not approved.is_file() or not approved.read_text(encoding="utf-8").strip():
        raise Refusal("no APPROVED file (§14 step 5)")
    if out_dir.exists():
        raise Refusal(f"{out_dir} exists: the scoring run is executed once (§14 step 9)")
    if not data_step_json.is_file():
        raise Refusal("the data step has not run (results/data_step.json missing; §14 step 6 before step 9)")
    ds = json.loads(data_step_json.read_text(encoding="utf-8"))
    if ds.get("halted"):
        raise Refusal("the data step halted the study (§5.4); its verdict row stands and no slope is fitted (§14 step 8)")
    if ds.get("stopped_for_amendment") and not ds.get("amendment"):
        raise Refusal("the data step stopped for a dated §16 gap amendment and has not been re-run after it (§14 step 8)")
    if not programme_count_json.is_file():
        raise Refusal("results/programme_count.json missing; the programme-wide re-count comes first (§9.4, §14 step 7)")
    programme = json.loads(programme_count_json.read_text(encoding="utf-8"))
    check_programme_count(programme)
    if SCORING_ROW not in trials_md.read_text(encoding="utf-8"):
        raise Refusal("trials.md has no scoring-run row; it is logged before the run (§14 step 7)")
    for p in (sample_jsonl, status_jsonl, outcome_jsonl, data_manifest_json, fetch_log_csv):
        if not p.is_file():
            raise Refusal(f"{p.name} is missing")
    manifest = json.loads(data_manifest_json.read_text(encoding="utf-8"))
    hashes = {"sample_jsonl": _sha256(sample_jsonl), "status_jsonl": _sha256(status_jsonl), "outcome_jsonl": _sha256(outcome_jsonl)}
    if hashes["sample_jsonl"] != manifest.get("sample_jsonl_sha256"):
        raise Refusal("results/sample.jsonl does not match the SHA-256 the data step recorded in data_manifest.json")
    if hashes["status_jsonl"] != manifest.get("status_jsonl_sha256"):
        raise Refusal("status.jsonl does not match the SHA-256 the data step recorded in data_manifest.json")
    with open(fetch_log_csv, encoding="utf-8", newline="") as f:
        fetch_rows = list(csv.DictReader(f))
    if len(fetch_rows) != 1:
        raise Refusal("paper-log/resolution_fetch.csv must hold exactly one provenance line (§5.3)")
    if hashes["outcome_jsonl"] != fetch_rows[0].get("outcome_sha256"):
        raise Refusal("outcome.jsonl does not match the SHA-256 the resolution fetch recorded in resolution_fetch.csv")
    if hashes["status_jsonl"] != fetch_rows[0].get("status_sha256"):
        raise Refusal("status.jsonl does not match the SHA-256 the resolution fetch recorded in resolution_fetch.csv")

    now = now or dt.datetime.now(UTC)
    sample = read_sample(sample_jsonl)
    status = read_jsonl_by_id(status_jsonl)
    outcomes = read_jsonl_by_id(outcome_jsonl)
    trials = {name: score_trial(name, sample.get(name, []), status, outcomes, resamples) for name in TRIALS}

    ratio_c1 = float(ds["trials"]["C1"]["power"]["ratio"])
    low_power = bool(np.isfinite(ratio_c1) and ratio_c1 > fit.LOW_POWER_RATIO)
    c1, c1a, c1b = trials["C1"], trials["C1a"], trials["C1b"]
    c1a_not_supported = (not c1a["rows"]["W"]["converged"]) or (not c1a["criteria"]["all"])
    core = fit.headline_verdict(c1["criteria"]["all"], c1["rows"]["W"]["converged"], c1a_not_supported, halted=False)
    b_h, b_hp = c1["rows"]["W"]["b"], c1b["rows"]["W"]["b"]
    direction = "yes" if np.isfinite(b_h) and np.isfinite(b_hp) and b_hp > b_h else "no"
    verdicts = {
        "C1": verdict_sentence(core, c1, low_power),
        "C1a": verdict_sentence(companion_row(c1a), c1a, low_power),
        "C1b": verdict_sentence(companion_row(c1b), c1b, low_power) + f"; b-hat(168 h) > b-hat(24 h): {direction} (descriptive, [WA26]'s direction)",
    }
    bars = {"N=3 (decides C3)": bonferroni_bar(N_FAMILY), "N=12 (one per study)": bonferroni_bar(N_STUDIES),
            f"N={programme['public_trials_md']} (public trials.md rows)": bonferroni_bar(programme["public_trials_md"]),
            f"N={programme['with_desk_registry']} (with the desk registry)": bonferroni_bar(programme["with_desk_registry"])}
    multiplicity = {name: {bar: {"z": z, "t_cl": trials[name]["rows"]["W"]["t_cl"],
                                 "meets": bool(np.isfinite(trials[name]["rows"]["W"]["t_cl"]) and trials[name]["rows"]["W"]["t_cl"] >= z)}
                           for bar, z in bars.items()} for name in TRIALS}
    summary: dict[str, Any] = {
        "study": "013-polymarket-calibration-forward",
        "step": "scoring run (§14 step 9), once",
        "run_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "code_commit": _git_head(approved.parent),
        "approval_line": approved.read_text(encoding="utf-8").splitlines()[0].strip(),
        "inputs_sha256": {**hashes, "data_step_json": _sha256(data_step_json), "programme_count_json": _sha256(programme_count_json)},
        "data_step_run_at_utc": ds.get("run_at_utc"),
        "low_power_label": low_power,
        "data_step_ratio_C1": ratio_c1,
        "headline_verdict": core,
        "verdicts": verdicts,
        "bootstrap_resamples": resamples,
        "multiplicity_bars": multiplicity,
        "programme_count": {k: programme.get(k) for k in ("counted_at_utc", "public_trials_md", "with_desk_registry", "method")},
        "published_comparison": {
            "WA26_b": PUBLISHED_B_WA26,
            "C1_b_minus_WA26_b": float(b_h - PUBLISHED_B_WA26) if np.isfinite(b_h) else float("nan"),
            "note": "descriptive only: different sample, horizon and weights (§9.6); [CR26]'s interior-bin errors are compared in the note",
        },
        "trials": trials,
    }
    _write_outputs(summary, out_dir)
    return summary


def _git_head(study_dir: Path) -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=study_dir, capture_output=True, text=True, check=True,
                              timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _fmt(v: Any, nd: int = 4) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return "n/a" if not np.isfinite(v) else f"{v:.{nd}f}"
    return str(v)


def _write_outputs(summary: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=True) + "\n", encoding="utf-8")
    with open(out_dir / "slopes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SLOPE_COLUMNS, lineterminator="\n")
        w.writeheader()
        for name, t in summary["trials"].items():
            for row_name, r in list(t["rows"].items()) + list(t["splits"].items()):
                bs = r.get("bootstrap", {})
                w.writerow({
                    "trial": name, "row": row_name, "n": r["n"], "G": r["G"], "a": _fmt(r["a"], 6), "b": _fmt(r["b"], 6),
                    "se_cl": _fmt(r["se_cl"], 6), "se_ordinary": _fmt(r["se_ordinary"], 6), "t_cl": _fmt(r["t_cl"], 4),
                    "wald_low": _fmt(r["wald_low"], 6), "wald_high": _fmt(r["wald_high"], 6),
                    "boot_low": _fmt(bs.get("low", float("nan")), 6), "boot_high": _fmt(bs.get("high", float("nan")), 6),
                    "boot_dropped": bs.get("dropped", ""), "boot_available": _fmt(bs["available"]) if bs else "",
                    "converged": _fmt(r["converged"]), "separated": _fmt(r["separated"]),
                    "loglik": _fmt(r["loglik"], 4), "loglik_calibrated": _fmt(r["loglik_calibrated"], 4),
                })
    with open(out_dir / "reliability.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RELIABILITY_COLUMNS, lineterminator="\n")
        w.writeheader()
        for name, t in summary["trials"].items():
            for b in t["reliability"]:
                w.writerow({"trial": name, **{k: (_fmt(b[k], 6) if isinstance(b[k], float) else b[k]) for k in RELIABILITY_COLUMNS[1:]}})
    (out_dir / "verdict.md").write_text(render_verdict(summary), encoding="utf-8")


def render_verdict(s: dict[str, Any]) -> str:
    lines = [
        "# Study 013 scoring run: verdict table (§9.5)",
        "",
        f"Run once at {s['run_at_utc']} (code {s['code_commit'][:7]}), after `APPROVED` ({s['approval_line']}). "
        "Aggregates only; the note (README) carries the §2.4 disclosure first and compares with [CR26] and [WA26]. "
        f"Low-power label: {'on' if s['low_power_label'] else 'off'} (data-step ratio for C1: {s['data_step_ratio_C1']:.2f}; label above 0.50).",
        "",
        f"**Headline (C1): {s['headline_verdict']}.**",
        "",
        "| Trial | Verdict |",
        "|---|---|",
    ]
    for name, v in s["verdicts"].items():
        lines.append(f"| {name} | {v} |")
    lines += ["", "| Trial | Row | n | G | b-hat | a-hat | SE_cl | SE_ord | t_cl | bootstrap 95% | C1 | C2 | C3 | C4 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, t in s["trials"].items():
        c = t["criteria"]
        for row_name in ("W", "W1", "W2"):
            r = t["rows"][row_name]
            bs = r.get("bootstrap")
            boot = (f"[{_fmt(bs['low'])}, {_fmt(bs['high'])}]" + ("" if bs["available"] else " (not available: dropped resamples)")) if bs else ""
            crit = (_fmt(c["C1"]), _fmt(c["C2"]), _fmt(c["C3"]), _fmt(c["C4"])) if row_name == "W" else ("", "", "", "")
            lines.append(f"| {name} | {row_name} | {r['n']} | {r['G']} | {_fmt(r['b'])} | {_fmt(r['a'])} | {_fmt(r['se_cl'])} | "
                         f"{_fmt(r['se_ordinary'])} | {_fmt(r['t_cl'], 2)} | {boot} | {' | '.join(crit)} |")
    lines += ["", "## Multiplicity bars (§9.4; only N = 3 decides)", "", "| Trial | Bar | z | t_cl | meets |", "|---|---|---|---|---|"]
    for name, bars in s["multiplicity_bars"].items():
        for bar, r in bars.items():
            lines.append(f"| {name} | {bar} | {r['z']:.3f} | {_fmt(r['t_cl'], 2)} | {_fmt(r['meets'])} |")
    lines += ["", "## Excluded at scoring, by the kind of §6.5 in order", "", "| Trial | sampled | scored | " + " | ".join(outcome.KINDS) + " |",
              "|---|---|---|" + "---|" * len(outcome.KINDS)]
    for name, t in s["trials"].items():
        lines.append(f"| {name} | {t['sampled']} | {t['scored']} | " + " | ".join(str(t["excluded_at_scoring"][k]) for k in outcome.KINDS) + " |")
    lines += ["", "## Scores and shares (§9.6, descriptive)", "", "| Trial | Brier | log-loss | base rate | Brier skill | Sports share | first label Yes | early share |", "|---|---|---|---|---|---|---|---|"]
    for name, t in s["trials"].items():
        sc = t["scores"]
        lines.append(f"| {name} | {_fmt(sc.get('brier', float('nan')))} | {_fmt(sc.get('log_loss', float('nan')))} | "
                     f"{_fmt(sc.get('base_rate', float('nan')))} | {_fmt(sc.get('brier_skill', float('nan')))} | "
                     f"{_fmt(t['sports_share'], 3)} | {_fmt(t['first_label_yes_share'], 3)} | {_fmt(t['early_share'], 3)} |")
    lines += ["", "## Descriptive splits (§9.6; b-hat with a clustered Wald 95% interval; no decision weight)", "",
              "| Trial | Split | n | G | b-hat | interval |", "|---|---|---|---|---|---|"]
    for name, t in s["trials"].items():
        for split, r in t["splits"].items():
            lines.append(f"| {name} | {split} | {r['n']} | {r['G']} | {_fmt(r['b'])} | [{_fmt(r['wald_low'])}, {_fmt(r['wald_high'])}] |")
    lines += ["", "## Reliability table, C1 (§9.6)", "", "| bin | n | clusters | mean p | outcome share | diff (pp) | 95% interval (pp) |", "|---|---|---|---|---|---|---|"]
    for b in s["trials"]["C1"]["reliability"]:
        lines.append(f"| [{b['bin_low']:.2f}, {b['bin_high']:.2f}{']' if b['bin_high'] == 0.99 else ')'} | {int(b['n'])} | {int(b['clusters'])} | "
                     f"{_fmt(b['mean_p'], 3)} | {_fmt(b['outcome_share'], 3)} | {_fmt(b['diff_pp'], 2)} | [{_fmt(b['ci_low_pp'], 2)}, {_fmt(b['ci_high_pp'], 2)}] |")
    lines += ["", f"Comparison with [WA26]: b = {PUBLISHED_B_WA26}; C1 b-hat minus it: {_fmt(s['published_comparison']['C1_b_minus_WA26_b'])} "
              "(descriptive only: different sample, horizon and weights).", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--study-dir", type=Path, default=Path(__file__).resolve().parents[1])
    a = ap.parse_args(argv)
    study = a.study_dir
    try:
        s = run_score(
            approved=study / "APPROVED",
            trials_md=study / "trials.md",
            data_step_json=study / "results" / "data_step.json",
            data_manifest_json=study / "results" / "data_manifest.json",
            sample_jsonl=study / "results" / "sample.jsonl",
            programme_count_json=study / "results" / "programme_count.json",
            status_jsonl=study / "data" / "raw" / "resolution" / "status.jsonl",
            outcome_jsonl=study / "data" / "raw" / "resolution" / "outcome.jsonl",
            fetch_log_csv=study / "paper-log" / "resolution_fetch.csv",
            out_dir=study / "results" / "score",
        )
    except Refusal as e:
        print(f"refused: {e}; nothing written")
        return 1
    c1 = s["trials"]["C1"]["rows"]["W"]
    print(f"scoring run: C1 n {c1['n']} G {c1['G']} b-hat {_fmt(c1['b'])} t_cl {_fmt(c1['t_cl'], 2)}; "
          f"headline: {s['headline_verdict']}; written to results/score/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
