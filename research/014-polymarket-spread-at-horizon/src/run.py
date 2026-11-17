"""Study 014 analysis run (PREREGISTRATION.md §9, §14 step 6), once, after `APPROVED`.

It reads Study 013's sample rows and data-step report, the snapshot-of-record
row of every sampled market (eight fields, hash-checked, `src/reader.py`),
excludes the followed events (§6.3), computes the §6.2 variables, assigns the
bins and fits the test object of §9.1 with `src/analysis.py` for M1, M1a and
M1b on W, W1 and W2, with the descriptive sub-analyses of §9.6.

What it writes, under `results/run/` (aggregates only, never a per-market row):
`summary.json`, `verdict.md`, `deltas.csv` (one row per fitted subset),
`deciles.csv`; under `results/`: `input_manifest.json` (the SHA-256 of every
input read and of the git-ignored `results/rows.jsonl`, the per-market rows the
figures are computed from: trial, id, mid, s, tick, bin, cluster).

Refusals (exit 1, nothing written), in this order: no non-empty `APPROVED`
(§14 step 4); `results/run/` exists (the run is executed once); Study 013's
data-step report or manifest missing (§14 step 3); Study 013's data step stopped
for a gap amendment and has not been re-run (§5.4: this study waits); no
analysis-run row in `trials.md` naming the programme count (§9.4, §14 step 5);
Study 013's sample file off its manifest hash; a snapshot off its logged hash.

Halts (§5.4; the verdict is written, no Delta is estimated, exit 5): Study 013's
price-field check failed; "row not as recorded" above 1 percent of the M1 rows;
fewer than 100 clusters or 200 markets in either M1 decision bin.

Every path is passed by name from `main`. The bootstrap's resample count is a
parameter only so that the tests can lower it; the command line never changes it.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from src import analysis as an
from src import reader
from src.reader import Refusal

UTC = dt.UTC
TRIALS = {"M1": "C1", "M1a": "C1a", "M1b": "C1b"}  # this study's trial -> Study 013's rows (§6.3, §7)
HORIZON_HOURS = {"M1": 24, "M1a": 24, "M1b": 168}
S_013 = dt.date(2026, 11, 3)  # the first snapshot that can be a snapshot of record (Study 013 §0 item 6)
D_THIS = dt.date(2026, 11, 17)  # §9.6: the date of the pre-registration (before-D / after-D split)
RUN_ROW = "| Analysis run logged (§14 step 5)"  # the first cell of the trials.md row written before the run
RUN_ROW_COUNT = re.compile(r"N_programme\s*=\s*(\d+)")
MIN_CLUSTERS, MIN_MARKETS = 100, 200  # §5.4
MAX_NOT_RECORDED_SHARE = 0.01  # §5.4
N_FAMILY, N_STUDIES = 3, 13  # §9.4
FLOOR_TEXT = "Study 013's floor 10,000 USDC and spread <= 0.10 at the horizon"
DELTA_COLUMNS = ("trial", "row", "n", "n_longshot", "n_central", "G", "fitted", "no_fit_reason", "alpha", "delta",
                 "se_cl", "se_ordinary", "t_cl", "wald_low", "wald_high", "boot_low", "boot_high", "boot_dropped",
                 "boot_available", "floored_share_longshot", "floored_share_central")
DECILE_COLUMNS = ("decile_low", "decile_high", "n", "G", "median_s", "median_half_points", "floored_share",
                  "median_liquidity", "fees_enabled_share", "suppressed")


def bonferroni_bar(n: int) -> float:
    from statistics import NormalDist

    return float(NormalDist().inv_cdf(1.0 - 0.05 / n))


def read_run_row(trials_md: Path) -> int:
    """The programme count of §9.4 from the analysis-run row logged before the run (§14 step 5)."""
    if not trials_md.exists():
        raise Refusal("trials.md is missing")
    for line in trials_md.read_text(encoding="utf-8").splitlines():
        if line.startswith(RUN_ROW):
            m = RUN_ROW_COUNT.search(line)
            if not m or int(m.group(1)) < 3:
                raise Refusal("the analysis-run row in trials.md names no programme count 'N_programme = <int>' >= 3 (§9.4)")
            return int(m.group(1))
    raise Refusal("trials.md has no analysis-run row; it is logged before the run (§14 step 5)")


def check_preconditions(study: Path, study_013: Path) -> dict:
    if not (study / "APPROVED").exists() or not (study / "APPROVED").read_text(encoding="utf-8").strip():
        raise Refusal("no non-empty APPROVED file (§14 step 4)")
    if (study / "results" / "run").exists():
        raise Refusal("results/run exists; the analysis run is executed once (§14 step 6)")
    step = reader.read_data_step(study_013 / "results" / "data_step.json")
    if not (study_013 / "results" / "data_manifest.json").exists():
        raise Refusal("Study 013's data_manifest.json is missing: its data step has not fixed the sample (§14 step 3)")
    if step["stopped_for_amendment"]:
        raise Refusal("Study 013's data step stopped for a gap amendment and has not been re-run; this study waits (§5.4)")
    return step


def _event_ids(row: dict) -> list[str]:
    ids = reader.decode_list(row.get("eventIds"))
    return [str(e) for e in ids] if ids else []


def classify_rows(sample: list[dict], records: dict[tuple[str, str], dict], fixed: set[str], later: set[str],
                  null_tick: float = an.NULL_TICK) -> tuple[list[dict], dict[str, Counter]]:
    """§5.4 and §6.3 on every sample row, by this study's trial; returns the kept rows with their §6.2 variables
    and the exclusion counts per trial, in the order of §9.6."""
    kept: list[dict] = []
    counts: dict[str, Counter] = {t: Counter() for t in TRIALS}
    later_ids: dict[str, set[str]] = {t: set() for t in TRIALS}
    for r in sample:
        trial = next((t for t, c in TRIALS.items() if c == r["trial"]), None)
        if trial is None:
            continue
        c = counts[trial]
        c["sample_rows"] += 1
        rec = records.get((str(r["snapshot"]), str(r["market"])))
        if rec is None:
            c["not_as_recorded"] += 1
            c["not_as_recorded_missing_row"] += 1
            continue
        evs = _event_ids(rec)
        if any(e in fixed for e in evs):
            c["followed_fixed"] += 1
            continue
        hit = [e for e in evs if e in later]
        if hit:
            c["followed_later"] += 1
            later_ids[trial].update(hit)
            continue
        c["after_followed_exclusion"] += 1
        bid, ask = reader.as_float(rec.get("bestBid")), reader.as_float(rec.get("bestAsk"))
        if not an.row_as_recorded(bid, ask, r["price"]):
            c["not_as_recorded"] += 1
            continue
        tick_raw = reader.as_float(rec.get("orderPriceMinTickSize"))
        qv = an.quote_variables(bid, ask, tick_raw, null_tick=null_tick)  # type: ignore[arg-type]
        b = an.assign_bin(qv.mid)
        if qv.tick_null:
            c["null_tick"] += 1
        if qv.tick_below:
            c["tick_below_0.001"] += 1
        if qv.locked:
            c["locked_book"] += 1
        if b not in an.DECISION_BINS:
            c["outside_decision_bins"] += 1
        c[f"bin_{b or 'none'}_{r['half']}"] += 1
        kept.append({
            "trial": trial, "id": str(r["market"]), "cluster": r["cluster"], "half": r["half"], "early": bool(r["early"]),
            "sports": bool(r["sports"]), "snapshot": str(r["snapshot"]), "horizon_h": r["realised_horizon_hours"],
            "price": r["price"], "mid": qv.mid, "q": qv.q, "tick": qv.tick, "tick_null": qv.tick_null,
            "tick_below": qv.tick_below, "locked": qv.locked, "floored": qv.floored, "s": qv.s, "ln_s": qv.ln_s,
            "half_points": qv.half_points, "bin": b, "decile": an.decile(qv.mid),
            "liquidity": reader.as_float(rec.get("liquidityNum")), "fees": rec.get("feesEnabled") is True,
            "end_date": rec.get("endDate"),
        })
    for t in TRIALS:
        counts[t]["followed_later_ids"] = sorted(later_ids[t])  # type: ignore[assignment]
    return kept, counts


def decision_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["bin"] in an.DECISION_BINS]


def fit_rows(rows: list[dict], resamples: int = 0) -> dict[str, Any]:
    """§9.6 figures for one set of rows (the two decision bins only); the bootstrap only when `resamples` > 0."""
    d = decision_rows(rows)
    y = np.array([r["ln_s"] for r in d], dtype=np.float64)
    L = np.array([1.0 if r["bin"] == an.LONGSHOT else 0.0 for r in d], dtype=np.float64)
    g = np.array([str(r["cluster"]) for r in d])
    f = an.fit_delta(y, L, g)
    out = f.as_dict()
    lo, hi = an.wald(f)
    out.update({"wald_low": lo, "wald_high": hi, "boot_low": float("nan"), "boot_high": float("nan"),
                "boot_dropped": 0, "boot_available": False})
    for b in an.DECISION_BINS:
        inb = [r for r in d if r["bin"] == b]
        out[f"floored_share_{b}"] = float(np.mean([r["floored"] for r in inb])) if inb else float("nan")
    if resamples > 0 and f.fitted:
        bs = an.cluster_bootstrap(y, L, g, resamples=resamples)
        out.update({"boot_low": bs.low, "boot_high": bs.high, "boot_dropped": bs.dropped, "boot_available": bs.available})
    out["power"] = an.power(f.se_cl) if f.fitted else None
    return out


def own_halts(m1_counts: Counter, m1_rows: list[dict]) -> list[str]:
    """§5.4: this study's permanent halts on the M1 rows."""
    reasons: list[str] = []
    # §5.4: the M1 rows after the followed-event exclusion, before the bin assignment; a row whose record is missing
    # could not be tested for a followed event, so it is counted in the base as well as under "not as recorded"
    base = m1_counts["after_followed_exclusion"] + m1_counts["not_as_recorded_missing_row"]
    if base and m1_counts["not_as_recorded"] > MAX_NOT_RECORDED_SHARE * base:
        reasons.append(f"rows not as Study 013 recorded them: {m1_counts['not_as_recorded']} of {base} (above 1 percent)")
    d = decision_rows(m1_rows)
    g = len({str(r["cluster"]) for r in d})
    n_by_bin = Counter(r["bin"] for r in d)
    if g < MIN_CLUSTERS:
        reasons.append(f"{g} clusters in the M1 decision sample (fewer than {MIN_CLUSTERS})")
    for b in an.DECISION_BINS:
        if n_by_bin[b] < MIN_MARKETS:
            reasons.append(f"{n_by_bin[b]} markets in the M1 {b} bin (fewer than {MIN_MARKETS})")
    return reasons


def _cell(rows: list[dict]) -> dict[str, Any]:
    n = len(rows)
    g = len({str(r["cluster"]) for r in rows})
    if n < an.MIN_CELL:
        return {"n": n, "G": g, "suppressed": True, "median_s": float("nan"), "median_half_points": float("nan"),
                "floored_share": float("nan"), "median_liquidity": float("nan"), "fees_enabled_share": float("nan")}
    liq = [r["liquidity"] for r in rows if r["liquidity"] is not None]
    return {"n": n, "G": g, "suppressed": False,
            "median_s": an.median_or_nan([r["s"] for r in rows]),
            "median_half_points": an.median_or_nan([r["half_points"] for r in rows]),
            "floored_share": float(np.mean([r["floored"] for r in rows])),
            "median_liquidity": an.median_or_nan(liq), "fees_enabled_share": float(np.mean([r["fees"] for r in rows]))}


def decile_table(rows: list[dict]) -> list[dict[str, Any]]:
    out = []
    for k in range(10):
        cell = _cell([r for r in rows if r["decile"] == k])
        out.append({"decile_low": an.DECILE_EDGES[k], "decile_high": an.DECILE_EDGES[k + 1], **cell})
    return out


def secondary_reading(rows: list[dict]) -> dict[str, Any]:
    """§9.6: median half-spread in points by bin beside [WA26]'s compression at the bin's median mid and [CR26]'s range."""
    out: dict[str, Any] = {}
    for b in (an.LONGSHOT, an.CENTRAL, an.HIGH):
        inb = [r for r in rows if r["bin"] == b]
        if len(inb) < an.MIN_CELL:
            out[b] = {"n": len(inb), "suppressed": True}
            continue
        half = an.median_or_nan([r["half_points"] for r in inb])
        mid = an.median_or_nan([r["mid"] for r in inb])
        wa = an.wa26_compression_points(mid)
        out[b] = {"n": len(inb), "suppressed": False, "median_mid": mid, "median_half_points": half,
                  "wa26_compression_points": wa, "wa26_clears_half_spread": wa > half,
                  # the two figures the pre-registration names, for the reader (the slope's compression is 0 at 0.50)
                  "wa26_at_named_prices": {"0.05": an.wa26_compression_points(0.05), "0.60": an.wa26_compression_points(0.60)},
                  "cr26_compression_points": list(an.CR26_COMPRESSION_POINTS),
                  "cr26_clears_half_spread": an.CR26_COMPRESSION_POINTS[0] > half}
    return out


def high_bin_difference(rows: list[dict]) -> dict[str, Any]:
    """§9.6: mean ln s of the high-probability bin, its difference from the central bin with a clustered Wald interval."""
    sub = [r for r in rows if r["bin"] in (an.HIGH, an.CENTRAL)]
    y = np.array([r["ln_s"] for r in sub], dtype=np.float64)
    L = np.array([1.0 if r["bin"] == an.HIGH else 0.0 for r in sub], dtype=np.float64)
    g = np.array([str(r["cluster"]) for r in sub])
    f = an.fit_delta(y, L, g)
    lo, hi = an.wald(f)
    high = [r["ln_s"] for r in sub if r["bin"] == an.HIGH]
    return {"n_high": len(high), "mean_ln_s_high": float(np.mean(high)) if high else float("nan"),
            "difference_from_central": f.delta, "se_cl": f.se_cl, "wald_low": lo, "wald_high": hi, "fitted": f.fitted}


def moved_end_count(rows: list[dict], first_ends: dict[str, object]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for b in (an.LONGSHOT, an.CENTRAL, an.HIGH, None):
        inb = [r for r in rows if r["bin"] == b]
        known = [r for r in inb if r["id"] in first_ends]
        moved = sum(1 for r in known if str(r["end_date"]) != str(first_ends[r["id"]]))
        out[b or "none"] = {"n": len(inb), "with_first_listing": len(known), "moved": moved}
    return out


def run_analysis(*, study: Path, study_013: Path, events_csv: Path, run_date: dt.date, resamples: int = an.BOOTSTRAP_RESAMPLES,
                 moved_end: bool = True) -> dict[str, Any]:
    step = check_preconditions(study, study_013)
    n_programme = read_run_row(study / "trials.md")
    results = study / "results"
    run_dir = results / "run"
    sample_path = study_013 / "results" / "sample.jsonl"
    manifest_path = study_013 / "results" / "data_manifest.json"
    sample, sample_sha = reader.read_sample(sample_path, manifest_path)
    manifest: dict[str, Any] = {
        "run_utc": dt.datetime.now(UTC).isoformat(timespec="seconds"),
        "study_013_sample_jsonl_sha256": sample_sha,
        "study_013_data_manifest_sha256": reader.sha256_file(manifest_path),
        "study_013_data_step_sha256": reader.sha256_file(study_013 / "results" / "data_step.json"),
        "snapshots_read": {}, "earlier_snapshots_read": {},
    }
    summary: dict[str, Any] = {"programme_count": n_programme, "bars": {"N_3": an.C3_T, "N_13": bonferroni_bar(N_STUDIES),
                                                                        "N_programme": bonferroni_bar(n_programme)},
                               "inherited_data_step": step, "halted": False, "halt_reasons": [], "run_date": run_date.isoformat()}
    if not step["price_field_pass"]:
        summary.update({"halted": True, "halt_reasons": ["Study 013's §6.2 price-field check failed"],
                        "verdict": {"M1": "inconclusive (halted: the quote fields do not mean what both documents say)"}})
        _write(run_dir, results, summary, [], [], manifest, rows=None)
        return summary
    fixed, later = reader.read_followed_events(events_csv, run_date)
    log = reader.read_snapshot_log(study_013 / "paper-log" / "snapshots.csv")
    wanted: dict[dt.date, set[str]] = {}
    for r in sample:
        if r["trial"] in TRIALS.values():
            wanted.setdefault(dt.date.fromisoformat(str(r["snapshot"])), set()).add(str(r["market"]))
    records, hashes = reader.read_record_rows(study_013 / "data" / "raw" / "snapshots", log, wanted)
    manifest["snapshots_read"] = hashes
    kept, counts = classify_rows(sample, records, fixed, later)
    summary["followed_events"] = {"fixed": sorted(fixed), "later": sorted(later)}
    summary["exclusions"] = {t: dict(c) for t, c in counts.items()}
    m1_rows = [r for r in kept if r["trial"] == "M1"]
    halts = own_halts(counts["M1"], m1_rows)
    if halts:
        summary.update({"halted": True, "halt_reasons": halts, "verdict": {"M1": "inconclusive (halted at the analysis run)"}})
        _write(run_dir, results, summary, [], [], manifest, rows=kept)
        return summary
    # fits per trial on W, W1, W2
    fits: dict[str, dict[str, dict]] = {}
    deltas: list[dict] = []
    for t in TRIALS:
        rows_t = [r for r in kept if r["trial"] == t]
        fits[t] = {"W": fit_rows(rows_t, resamples=resamples),
                   "W1": fit_rows([r for r in rows_t if r["half"] == "W1"]),
                   "W2": fit_rows([r for r in rows_t if r["half"] == "W2"])}
        for name, f in fits[t].items():
            deltas.append({"trial": t, "row": name, **{k: f.get(k) for k in DELTA_COLUMNS if k not in ("trial", "row")}})
    crit = {t: an.criteria(_fit(fits[t]["W"]), _fit(fits[t]["W1"]), _fit(fits[t]["W2"])) for t in TRIALS}
    m1_power = fits["M1"]["W"]["power"]
    low_power = bool(m1_power and m1_power["ratio"] > an.LOW_POWER_RATIO)
    rows_txt = {t: an.companion_row(_fit(fits[t]["W"]), crit[t]) for t in TRIALS}
    verdict = {"M1": an.headline(_fit(fits["M1"]["W"]), crit["M1"], rows_txt["M1a"], low_power),
               "M1a": rows_txt["M1a"] + (f" {an.LOW_POWER_LABEL}" if low_power else ""),
               "M1b": rows_txt["M1b"] + (f" {an.LOW_POWER_LABEL}" if low_power else "")}
    d_h, d_hp = fits["M1"]["W"]["delta"], fits["M1b"]["W"]["delta"]
    summary.update({
        "fits": fits, "criteria": crit, "verdict": verdict, "low_power": low_power,
        "m1b_delta_exceeds_m1": bool(np.isfinite(d_h) and np.isfinite(d_hp) and d_hp > d_h),
        "sports_share": {t: float(np.mean([r["sports"] for r in kept if r["trial"] == t])) if any(r["trial"] == t for r in kept) else float("nan") for t in TRIALS},
        "deciles_M1": decile_table(m1_rows), "secondary_reading_M1": secondary_reading(m1_rows),
        "high_bin_M1": high_bin_difference(m1_rows),
        "early_split_M1": {"early": fit_rows([r for r in m1_rows if r["early"]]), "not_early": fit_rows([r for r in m1_rows if not r["early"]]),
                           "early_share": float(np.mean([r["early"] for r in m1_rows])) if m1_rows else float("nan")},
        "before_after_D_M1": {"before_D": fit_rows([r for r in m1_rows if dt.date.fromisoformat(r["snapshot"]) < D_THIS]),
                              "after_D": fit_rows([r for r in m1_rows if dt.date.fromisoformat(r["snapshot"]) >= D_THIS])},
    })
    alt_rows, _ = classify_rows(sample, records, fixed, later, null_tick=an.ALT_NULL_TICK)
    summary["null_tick_0.01_M1"] = fit_rows([r for r in alt_rows if r["trial"] == "M1"])
    if moved_end:
        last_day = max(wanted) if wanted else S_013
        first_ends, earlier = reader.first_end_dates(study_013 / "data" / "raw" / "snapshots", log, {r["id"] for r in m1_rows}, S_013, last_day)
        manifest["earlier_snapshots_read"] = earlier
        summary["moved_end_M1"] = moved_end_count(m1_rows, first_ends)
    _write(run_dir, results, summary, deltas, decile_table(m1_rows), manifest, rows=kept)
    return summary


def _fit(d: dict) -> an.Fit:
    return an.Fit(**{k: d[k] for k in an.Fit.__dataclass_fields__})


def _write(run_dir: Path, results: Path, summary: dict, deltas: list[dict], deciles: list[dict], manifest: dict,
           rows: list[dict] | None) -> None:
    run_dir.mkdir(parents=True, exist_ok=False)
    if rows is not None:
        rows_path = results / "rows.jsonl"
        with open(rows_path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps({k: r[k] for k in ("trial", "id", "mid", "s", "tick", "bin", "cluster")}) + "\n")
        manifest["rows_jsonl_sha256"] = reader.sha256_file(rows_path)
    (results / "input_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=True, default=str) + "\n", encoding="utf-8")
    with open(run_dir / "deltas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DELTA_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(deltas)
    with open(run_dir / "deciles.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DECILE_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(deciles)
    (run_dir / "verdict.md").write_text(verdict_text(summary), encoding="utf-8")


def verdict_text(s: dict) -> str:
    lines = ["# Study 014 verdict (PREREGISTRATION.md §9.5)", ""]
    if s["halted"]:
        lines += [f"**{s['verdict']['M1']}.** " + "; ".join(s["halt_reasons"]) + ".", ""]
        return "\n".join(lines) + "\n"
    for t in TRIALS:
        f = s["fits"][t]["W"]
        lines.append(
            f"- **{t}** (h = {HORIZON_HOURS[t]} h; {FLOOR_TEXT}): {s['verdict'][t]}. "
            f"n = {f['n']} (longshot {f['n_longshot']}, central {f['n_central']}), G = {f['G']}, "
            f"Δ̂ = {f['delta']:.3f}, SE_cl = {f['se_cl']:.3f}, t_cl = {f['t_cl']:.2f}; "
            f"tick-floored share longshot {f['floored_share_longshot']:.3f}, central {f['floored_share_central']:.3f}; "
            f"Sports share {s['sports_share'][t]:.3f}."
        )
    lines += ["", f"M1b's Δ̂(h′) exceeds M1's Δ̂(h): {s['m1b_delta_exceeds_m1']}.",
              f"Bars: t_cl ≥ {an.C3_T} at N = 3 (decides); z ≥ {s['bars']['N_13']:.3f} at N = 13; "
              f"z ≥ {s['bars']['N_programme']:.3f} at the programme count {s['programme_count']} (no weight)."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    here = Path(__file__).resolve().parents[1]
    ap.add_argument("--study-dir", type=Path, default=here)
    ap.add_argument("--study-013-dir", type=Path, default=here.parent / "013-polymarket-calibration-forward")
    ap.add_argument("--events-csv", type=Path, default=here.parents[1] / "pm-view" / "events.csv")
    a = ap.parse_args(argv)
    try:
        s = run_analysis(study=a.study_dir, study_013=a.study_013_dir, events_csv=a.events_csv, run_date=dt.datetime.now(UTC).date())
    except Refusal as e:
        print(f"refused: {e}; nothing written")
        return 1
    print(f"analysis run: verdict M1 {s['verdict']['M1']}; written to results/run/")
    return 5 if s["halted"] else 0


if __name__ == "__main__":
    sys.exit(main())
