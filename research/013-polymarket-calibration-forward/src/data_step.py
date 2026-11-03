"""Study 013 data step (PREREGISTRATION.md §5.2–§5.4, §6.1–§6.4, §9.6 power row; §14 step 6).

What it reads: the snapshot log and the snapshots' rows (§5.1), and
`status.jsonl` of the resolution fetch (§5.3). **It never opens the fetch's
other file**: this module does not know that file's name, no function here
takes its path, and a test runs the step with that file present behind a
guard that raises on any attempt to open it (§6.6, pitfall 14).

What it fixes, before any outcome is read: for each trial, the data-step
sample (every windowed market with a snapshot of record on which it is
eligible), every exclusion counted in the order of §6.3, the cluster of each
market (§6.4), the early flag (§9.6), the price distribution at the horizon
(Ê and the ten-bin histogram), the realised horizon, the number of clusters G
and the recomputed power row (§9.6); the gap days of the window by kind and the
stop and halt rules (§5.4); the price-field check of §6.2.

What it writes: `results/data_step.json` and `results/data_step.md` (keys in
the study's own words, never a venue field name: Polymarket's verdict is
`derived`), `results/sample.jsonl` (per-market rows, git-ignored) and
`results/data_manifest.json` (SHA-256 of the sample file and of the inputs).

Refusals (exit 1, nothing written): the resolution fetch has not completed
(`paper-log/resolution_fetch.csv` missing) or `status.jsonl` is missing; the
step has already run (`results/data_step.json` exists) and no `--amendment`
is named (§14 step 8: a re-run after a dated §16 gap amendment names it).
Exit 0 when the study proceeds, 4 when it stops for an amendment, 5 when it
halts permanently; the outputs are written in every one of the three cases,
because the counts are published whatever they show (§5.4).

Every path is passed by name (tools/check_bound_defaults.py).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from src import fit
from src.snapshots import Snapshot, as_float, decode_list, iter_rows, parse_time, read_snapshot_log

UTC = dt.UTC

# ---- the rules of the pre-registration, fixed on 2026-11-02 (§0); the data step may not move them (§15) ----
S = dt.date(2026, 11, 3)  # the first snapshot that can enter a sample (§0 item 6; S0 = 2026-11-02 never)
WINDOW_START = dt.datetime(2026, 11, 4, tzinfo=UTC)  # closedTime in [WINDOW_START, WINDOW_END) (§6.4)
WINDOW_MID = dt.datetime(2026, 12, 2, tzinfo=UTC)  # W1 = [start, mid), W2 = [mid, end): halves of 28 days (§8)
WINDOW_END = dt.datetime(2026, 12, 30, tzinfo=UTC)
LAST_SERVING_DAY = {24: dt.date(2026, 12, 28), 168: dt.date(2026, 12, 22)}  # §5.4
SERVING_DAYS = 56  # S to 2026-12-28 inclusive (§5.4)
STOP_MIN_SERVING_DAYS = 42  # §5.4: fewer present -> stop for a §16 amendment
STOP_GAP_RUN = 3  # §5.4: a run of three or more gap days -> stop
H_HOURS = 24  # C1, C1a (§6.1)
H_PRIME_HOURS = 168  # C1b (§6.1)
GAP_CAP_HOURS = 48  # T - t_s >= h + 48 h: no snapshot of record (§5.2)
VOLUME_FLOOR = 10_000.0  # USDC, cumulative at the snapshot (§6.3)
MAX_SPREAD = 0.10  # §6.3
P_MIN, P_MAX = 0.01, 0.99  # §6.3
EARLY_HOURS = 24  # closedTime more than 24 h before the scheduled end on the row: early (§9.6)
PRICE_CHECK_TOL = 0.02  # §6.2
PRICE_CHECK_MIN_SHARE = 0.99  # §6.2
HALT_MIN_CLUSTERS = 2_000  # §5.4
HALT_MIN_MARKETS = 5_000  # §5.4
SPORTS_LABEL = "sports"  # C1a: exact, case-insensitive match on the label (§6.4)
RESOLUTION_BEGUN = {"proposed", "disputed", "resolved"}  # §6.3

TRIALS: dict[str, dict] = {
    "C1": {"h": H_HOURS, "non_sports": False},
    "C1a": {"h": H_HOURS, "non_sports": True},
    "C1b": {"h": H_PRIME_HOURS, "non_sports": False},
}

# The §6.3 fields a gap-day snapshot can have null on every row (pitfall 12). Read from the rows only
# for this count; the names are the collector's whitelist, never written to a result file.
# `umaResolutionStatus` is not in the list (§16 note of 2026-11-03): null is its legitimate value on an open
# market whose resolution has not begun, so a correct snapshot can have it null on every row; the first
# version of this trigger, with the field in the list, flagged a correct synthetic snapshot as a gap day.
GAP_FIELDS = (
    "outcomes", "clobTokenIds", "enableOrderBook", "active", "closed", "acceptingOrders",
    "endDate", "bestBid", "bestAsk", "volumeNum",
)

# Exclusion reasons of §6.3, in the order written there (the first reason that excludes a market counts).
EXCLUSION_ORDER = (
    "not two outcomes or two tokens",
    "order book not enabled",
    "not active, closed, or not accepting orders",
    "resolution begun at the snapshot",
    "scheduled end missing or before the snapshot",
    "best bid or ask missing or not 0 < bid <= ask < 1",
    "spread above 0.10",
    "mid price outside [0.01, 0.99]",
    "volume below 10,000 USDC",
)
SPORTS_REASON = "Sports tag (C1a only)"
NO_SNAPSHOT_REASON = "no snapshot of record (none before T - h after S, or gap cap)"
NO_ROW_REASON = "market absent from its snapshot of record"


class Refusal(Exception):
    """A clean refusal with its reason (exit 1, nothing written)."""


@dataclass
class StatusRow:
    market_id: str
    closed_time: dt.datetime | None
    fetch_failed: bool


def read_status(status_jsonl: Path) -> dict[str, StatusRow]:
    """`status.jsonl` of the resolution fetch (§5.3): the fields the data step needs, by market id."""
    out: dict[str, StatusRow] = {}
    with open(status_jsonl, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            mid = str(r.get("id"))
            out[mid] = StatusRow(market_id=mid, closed_time=parse_time(r.get("closedTime")),
                                 fetch_failed=bool(r.get("fetch_failed", False)))
    return out


# ---- gap days (§5.4) ----


@dataclass
class GapReport:
    serving_days_present: int
    gap_days: dict[str, str]  # date -> kind
    longest_run: int
    usable_dates: list[dt.date]

    @property
    def stop(self) -> bool:
        return self.serving_days_present < STOP_MIN_SERVING_DAYS or self.longest_run >= STOP_GAP_RUN


def all_null_fields(snapshot_root: Path, snap: Snapshot) -> list[str]:
    """The §6.3 fields that are null on every row of the snapshot (empty when the snapshot has no row)."""
    seen = dict.fromkeys(GAP_FIELDS, False)
    rows = 0
    for row in iter_rows(snapshot_root, snap):
        rows += 1
        for k in GAP_FIELDS:
            if not seen[k] and row.get(k) is not None:
                seen[k] = True
        if all(seen.values()):
            return []
    if rows == 0:
        return list(GAP_FIELDS)
    return [k for k, v in seen.items() if not v]


def classify_gaps(snapshot_root: Path, snapshots: list[Snapshot], last_day: dt.date,
                  null_fields: dict[dt.date, list[str]] | None = None) -> GapReport:
    """Gap days from S to `last_day` inclusive, by kind: `missing`, `short listing` (distinct markets below half
    the median of the window's snapshots), `field null on every row` (§5.4). Snapshots dated before S are not
    looked at. `null_fields` may be given (tests); otherwise the rows are scanned."""
    by_date = {s.date: s for s in snapshots if S <= s.date <= last_day}
    counts = [s.distinct_markets for s in by_date.values()]
    median = statistics.median(counts) if counts else 0
    gaps: dict[str, str] = {}
    usable: list[dt.date] = []
    d = S
    while d <= last_day:
        snap = by_date.get(d)
        if snap is None:
            gaps[d.isoformat()] = "missing"
        elif snap.distinct_markets < 0.5 * median:
            gaps[d.isoformat()] = f"short listing ({snap.distinct_markets} distinct markets, median {median:g})"
        else:
            nulls = null_fields.get(d) if null_fields is not None else all_null_fields(snapshot_root, snap)
            if nulls:
                gaps[d.isoformat()] = f"field null on every row ({len(nulls)} field(s))"
            else:
                usable.append(d)
        d += dt.timedelta(days=1)
    longest = run = 0
    d = S
    while d <= last_day:
        run = run + 1 if d.isoformat() in gaps else 0
        longest = max(longest, run)
        d += dt.timedelta(days=1)
    return GapReport(serving_days_present=len(usable), gap_days=gaps, longest_run=longest, usable_dates=usable)


# ---- snapshot of record (§5.2) ----


def snapshot_of_record(t_close: dt.datetime, h_hours: int, usable: list[Snapshot]) -> Snapshot | None:
    """The usable snapshot dated on or after S with the latest t_s <= T - h; None when there is none or when
    T - t_s >= h + 48 h (the gap cap). `usable` holds the non-gap snapshots, any order."""
    limit = t_close - dt.timedelta(hours=h_hours)
    best: Snapshot | None = None
    for s in usable:
        if s.date < S or s.started > limit:
            continue
        if best is None or s.started > best.started:
            best = s
    if best is None:
        return None
    if t_close - best.started >= dt.timedelta(hours=h_hours + GAP_CAP_HOURS):
        return None
    return best


# ---- eligibility (§6.3) and the row's derived quantities ----


@dataclass
class RowFacts:
    p: float
    cluster: str
    cluster_unparsed: bool
    n_events: int
    first_label_yes: bool
    sports: bool
    tag_labels: list[str]
    listing_mid: float | None  # the listing's own mid for the first token (§6.2 check), from the row
    volume: float
    first_token: str  # the first listed outcome token's id on the snapshot-of-record row (§6.2; the scoring run's y)


def eligibility(row: dict, t_s: dt.datetime) -> tuple[str | None, RowFacts | None]:
    """§6.3 on one snapshot-of-record row: (None, facts) when eligible, else (the first failing reason, None)."""
    outcomes = decode_list(row.get("outcomes"))
    tokens = decode_list(row.get("clobTokenIds"))
    if outcomes is None or tokens is None or len(outcomes) != 2 or len(tokens) != 2:
        return EXCLUSION_ORDER[0], None
    if row.get("enableOrderBook") is not True:
        return EXCLUSION_ORDER[1], None
    if row.get("active") is not True or row.get("closed") is not False or row.get("acceptingOrders") is not True:
        return EXCLUSION_ORDER[2], None
    status = row.get("umaResolutionStatus")
    if isinstance(status, str) and status.lower() in RESOLUTION_BEGUN:
        return EXCLUSION_ORDER[3], None
    end = parse_time(row.get("endDate"))
    if end is None or t_s > end:
        return EXCLUSION_ORDER[4], None
    bid, ask = as_float(row.get("bestBid")), as_float(row.get("bestAsk"))
    if bid is None or ask is None or not (0.0 < bid <= ask < 1.0):
        return EXCLUSION_ORDER[5], None
    if ask - bid > MAX_SPREAD + 1e-12:
        return EXCLUSION_ORDER[6], None
    p = (bid + ask) / 2.0
    if not (P_MIN <= p <= P_MAX):
        return EXCLUSION_ORDER[7], None
    vol = as_float(row.get("volumeNum"))
    if vol is None or vol < VOLUME_FLOOR:
        return EXCLUSION_ORDER[8], None
    cluster, unparsed, n_events = cluster_of(row)
    labels = [str(x) for x in (row.get("tagLabels") or [])]
    sports = any(x.strip().lower() == SPORTS_LABEL for x in labels)
    mids = decode_list(row.get("outcomePrices"))
    listing_mid = as_float(mids[0]) if mids and len(mids) >= 1 else None
    first_yes = str(outcomes[0]).strip().lower() == "yes"
    return None, RowFacts(p=p, cluster=cluster, cluster_unparsed=unparsed, n_events=n_events,
                          first_label_yes=first_yes, sports=sports, tag_labels=labels, listing_mid=listing_mid,
                          volume=vol, first_token=str(tokens[0]))


def cluster_of(row: dict) -> tuple[str, bool, int]:
    """§6.4: the numerically smallest event id (ids parsed as integers); should any fail to parse, the ids are
    ordered as strings and the row is counted; a market with no event id is its own cluster (`market:<id>`)."""
    ids = [str(x) for x in (row.get("eventIds") or []) if x is not None and str(x) != ""]
    if not ids:
        return f"market:{row.get('id')}", False, 0
    try:
        return str(min(int(x) for x in ids)), False, len(ids)
    except ValueError:
        return min(ids), True, len(ids)


def early_flag(closed_time: dt.datetime, end_on_row: dt.datetime | None) -> bool:
    """§9.6: `closedTime` (from status) more than 24 hours before the scheduled end on the snapshot-of-record row."""
    return end_on_row is not None and (end_on_row - closed_time) > dt.timedelta(hours=EARLY_HOURS)


# ---- the step ----


@dataclass
class TrialSample:
    name: str
    h_hours: int
    excluded: Counter = field(default_factory=Counter)
    markets: list[dict] = field(default_factory=list)  # sample rows (study words only)

    def power(self) -> dict[str, float]:
        p = np.array([m["price"] for m in self.markets], dtype=np.float64)
        g = len({m["cluster"] for m in self.markets})
        if p.size == 0:
            return {"n": 0.0, "G": float(g), "E_hat": float("nan"), "se_h0": float("nan"),
                    "mde_programme": float("nan"), "mde_onesided": float("nan"), "ratio": float("nan"),
                    "low_power": 1.0}
        return fit.power_row(p, g)


def run_data_step(
    *,
    snapshot_root: Path,
    snapshot_log: Path,
    status_jsonl: Path,
    results_dir: Path,
    fetch_log_csv: Path,
    amendment: str | None = None,
    null_fields: dict[dt.date, list[str]] | None = None,
    now: dt.datetime | None = None,
) -> dict:
    """The data step. Writes the four outputs under `results_dir` and returns the report dict."""
    if not fetch_log_csv.exists():
        raise Refusal(f"the resolution fetch has not completed: {fetch_log_csv.name} is missing (§14 step 4 before step 6)")
    if not status_jsonl.exists():
        raise Refusal(f"{status_jsonl.name} is missing: nothing to window on")
    report_json = results_dir / "data_step.json"
    if report_json.exists() and not amendment:
        raise Refusal(f"{report_json} exists: the data step runs once; a re-run after a dated §16 gap amendment names it with --amendment")
    now = now or dt.datetime.now(UTC)

    snapshots = read_snapshot_log(snapshot_log)
    gaps = {h: classify_gaps(snapshot_root, snapshots, LAST_SERVING_DAY[h], null_fields) for h in (H_HOURS, H_PRIME_HOURS)}
    stop = gaps[H_HOURS].stop or gaps[H_PRIME_HOURS].stop
    usable_dates = set(gaps[H_HOURS].usable_dates) | set(gaps[H_PRIME_HOURS].usable_dates)
    usable = [s for s in snapshots if s.date in usable_dates]
    by_date = {s.date: s for s in snapshots}

    status = read_status(status_jsonl)
    # §6.4: the candidate set is every id in any snapshot from S to the last serving day
    candidates: set[str] = set()
    for snap in snapshots:
        if S <= snap.date <= LAST_SERVING_DAY[H_HOURS]:
            for row in iter_rows(snapshot_root, snap):
                candidates.add(str(row.get("id")))
    unfetched = sum(1 for c in candidates if c not in status or status[c].fetch_failed)
    no_close_time = sum(1 for c in candidates if c in status and not status[c].fetch_failed and status[c].closed_time is None)
    windowed: dict[str, dt.datetime] = {}
    for c in candidates:
        st = status.get(c)
        if st is None or st.fetch_failed or st.closed_time is None:
            continue
        if WINDOW_START <= st.closed_time < WINDOW_END:
            windowed[c] = st.closed_time

    # which snapshot each (market, horizon) reads: computed from the log alone, then one pass over each snapshot
    trials = {name: TrialSample(name=name, h_hours=spec["h"]) for name, spec in TRIALS.items()}
    need: dict[dt.date, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))  # date -> id -> trial names
    for mid, t_close in windowed.items():
        for name, spec in TRIALS.items():
            sor = snapshot_of_record(t_close, spec["h"], usable)
            if sor is None:
                trials[name].excluded[NO_SNAPSHOT_REASON] += 1
                continue
            need[sor.date][mid].append(name)

    price_check_rows = 0
    price_check_ok = 0
    multi_event = 0
    unparsed_clusters = 0
    labels_present: Counter = Counter()
    for date in sorted(need):
        snap = by_date[date]
        wanted = need[date]
        found: set[str] = set()
        for row in iter_rows(snapshot_root, snap):
            mid = str(row.get("id"))
            names = wanted.get(mid)
            if not names:
                continue
            found.add(mid)
            reason, facts = eligibility(row, snap.started)
            for name in names:
                tr = trials[name]
                if reason is not None or facts is None:
                    tr.excluded[reason or EXCLUSION_ORDER[0]] += 1
                    continue
                if TRIALS[name]["non_sports"] and facts.sports:
                    tr.excluded[SPORTS_REASON] += 1
                    continue
                t_close = windowed[mid]
                horizon_h = (t_close - snap.started).total_seconds() / 3600.0
                end_on_row = parse_time(row.get("endDate"))
                tr.markets.append({
                    "market": mid,
                    "cluster": facts.cluster,
                    "price": facts.p,
                    "snapshot": date.isoformat(),
                    "realised_horizon_hours": round(horizon_h, 4),
                    "early": early_flag(t_close, end_on_row),
                    "half": "W1" if t_close < WINDOW_MID else "W2",
                    "sports": facts.sports,
                    "first_label_yes": facts.first_label_yes,
                    "volume_at_horizon": facts.volume,
                    "tag_family": tag_family(facts.tag_labels),
                    "first_token": facts.first_token,
                })
                if name == "C1":
                    if facts.n_events > 1:
                        multi_event += 1
                    if facts.cluster_unparsed:
                        unparsed_clusters += 1
                    labels_present.update(set(facts.tag_labels))
                    if facts.listing_mid is not None:
                        price_check_rows += 1
                        if abs(facts.p - facts.listing_mid) <= PRICE_CHECK_TOL:
                            price_check_ok += 1
        for mid, names in wanted.items():
            if mid not in found:
                for name in names:
                    trials[name].excluded[NO_ROW_REASON] += 1

    c1 = trials["C1"]
    g_c1 = len({m["cluster"] for m in c1.markets})
    price_share = price_check_ok / price_check_rows if price_check_rows else float("nan")
    price_check_fail = price_check_rows == 0 or price_share < PRICE_CHECK_MIN_SHARE
    halt_reasons: list[str] = []
    if price_check_fail:
        halt_reasons.append(f"price-field check (§6.2): {price_check_ok} of {price_check_rows} rows within 0.02 of the listing's mid")
    if g_c1 < HALT_MIN_CLUSTERS:
        halt_reasons.append(f"C1 data-step sample has {g_c1} clusters, fewer than {HALT_MIN_CLUSTERS} (§5.4)")
    if len(c1.markets) < HALT_MIN_MARKETS:
        halt_reasons.append(f"C1 data-step sample has {len(c1.markets)} markets, fewer than {HALT_MIN_MARKETS} (§5.4)")
    halted = bool(halt_reasons)

    report: dict[str, Any] = {
        "study": "013-polymarket-calibration-forward",
        "step": "data step (§14 step 6)",
        "run_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "amendment": amendment,
        "no_outcome_read": True,
        "snapshots_logged": len(snapshots),
        "first_snapshot_in_sample": S.isoformat(),
        "gap_days": {
            "C1 and C1a (to 2026-12-28)": {
                "serving_days_present": gaps[H_HOURS].serving_days_present,
                "serving_days_in_window": SERVING_DAYS,
                "gap_days": gaps[H_HOURS].gap_days,
                "longest_run": gaps[H_HOURS].longest_run,
            },
            "C1b (to 2026-12-22)": {
                "serving_days_present": gaps[H_PRIME_HOURS].serving_days_present,
                "gap_days": gaps[H_PRIME_HOURS].gap_days,
                "longest_run": gaps[H_PRIME_HOURS].longest_run,
            },
        },
        "stopped_for_amendment": stop,
        "halted": halted,
        "halt_reasons": halt_reasons,
        "verdict_row": "inconclusive (halted at the data step)" if halted else None,
        "counts": {
            "candidates": len(candidates),
            "candidates_unfetched_or_failed": unfetched,
            "candidates_without_close_time": no_close_time,
            "windowed": len(windowed),
            "markets_in_more_than_one_event (C1 sample)": multi_event,
            "event_ids_ordered_as_strings (C1 sample)": unparsed_clusters,
        },
        "price_field_check": {
            "rows": price_check_rows,
            "within_0.02": price_check_ok,
            "share": price_share,
            "required_share": PRICE_CHECK_MIN_SHARE,
            "pass": not price_check_fail,
        },
        "tag_labels_in_C1_sample": dict(sorted(labels_present.items())),
        "trials": {},
    }
    for name, tr in trials.items():
        p = np.array([m["price"] for m in tr.markets], dtype=np.float64)
        horizons = np.array([m["realised_horizon_hours"] for m in tr.markets], dtype=np.float64)
        hist = np.histogram(p, bins=np.array(fit.BIN_EDGES))[0].tolist() if p.size else [0] * (len(fit.BIN_EDGES) - 1)
        excluded_in_order = {k: tr.excluded.get(k, 0) for k in (NO_SNAPSHOT_REASON, NO_ROW_REASON, *EXCLUSION_ORDER)}
        if TRIALS[name]["non_sports"]:
            excluded_in_order[SPORTS_REASON] = tr.excluded.get(SPORTS_REASON, 0)
        report["trials"][name] = {
            "horizon_hours": tr.h_hours,
            "n": len(tr.markets),
            "G": len({m["cluster"] for m in tr.markets}),
            "n_W1": sum(1 for m in tr.markets if m["half"] == "W1"),
            "n_W2": sum(1 for m in tr.markets if m["half"] == "W2"),
            "early_share": float(np.mean([m["early"] for m in tr.markets])) if tr.markets else float("nan"),
            "sports_share": float(np.mean([m["sports"] for m in tr.markets])) if tr.markets else float("nan"),
            "first_label_yes_share": float(np.mean([m["first_label_yes"] for m in tr.markets])) if tr.markets else float("nan"),
            "price_histogram_ten_bins": hist,
            "realised_horizon_hours": {
                "min": float(horizons.min()) if horizons.size else float("nan"),
                "median": float(np.median(horizons)) if horizons.size else float("nan"),
                "max": float(horizons.max()) if horizons.size else float("nan"),
                "share_above_h_plus_24": float(np.mean(horizons > tr.h_hours + 24)) if horizons.size else float("nan"),
            },
            "excluded": excluded_in_order,
            "power": tr.power(),
        }

    results_dir.mkdir(parents=True, exist_ok=True)
    sample_path = results_dir / "sample.jsonl"
    with open(sample_path, "w", encoding="utf-8") as f:
        for name, tr in trials.items():
            for m in tr.markets:
                f.write(json.dumps({"trial": name, **m}) + "\n")
    manifest = {
        "written_at_utc": report["run_at_utc"],
        "sample_jsonl_sha256": _sha256(sample_path),
        "status_jsonl_sha256": _sha256(status_jsonl),
        "snapshot_log_sha256": _sha256(snapshot_log),
        "snapshots_read": {s.date.isoformat(): s.records_sha256 for s in snapshots if s.date in need or s.date in usable_dates},
    }
    (results_dir / "data_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_json.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=True) + "\n", encoding="utf-8")
    (results_dir / "data_step.md").write_text(render_md(report), encoding="utf-8")
    return report


def tag_family(labels: list[str]) -> str:
    """§9.6: Sports > Politics > Crypto > other (exact, case-insensitive)."""
    low = {x.strip().lower() for x in labels}
    for fam in ("sports", "politics", "crypto"):
        if fam in low:
            return fam.capitalize()
    return "other"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def render_md(r: dict) -> str:
    """The data-step report in prose tables (aggregates only)."""
    lines = [
        "# Study 013 data step",
        "",
        f"Run at {r['run_at_utc']} (no outcome read). "
        + ("**Stopped for a dated §16 gap amendment.** " if r["stopped_for_amendment"] else "")
        + ("**Halted permanently: " + "; ".join(r["halt_reasons"]) + ".** " if r["halted"] else "")
        + (f"Re-run after amendment: {r['amendment']}. " if r.get("amendment") else ""),
        "",
        "| Count | Value |",
        "|---|---|",
    ]
    for k, v in r["counts"].items():
        lines.append(f"| {k} | {v} |")
    g = r["gap_days"]["C1 and C1a (to 2026-12-28)"]
    lines += [
        f"| serving days present (C1, C1a) | {g['serving_days_present']} of {g['serving_days_in_window']} |",
        f"| gap days (C1, C1a) | {len(g['gap_days'])}, longest run {g['longest_run']} |",
        f"| price-field check | {r['price_field_check']['within_0.02']} of {r['price_field_check']['rows']} within 0.02 ({'pass' if r['price_field_check']['pass'] else 'FAIL'}) |",
        "",
        "| Trial | h | n | G | W1 | W2 | early share | Sports share | Ê | SE under H0 | MDE (2.842) | ratio | low power |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, t in r["trials"].items():
        pw = t["power"]
        lines.append(
            f"| {name} | {t['horizon_hours']} | {t['n']} | {t['G']} | {t['n_W1']} | {t['n_W2']} | {t['early_share']:.3f} | "
            f"{t['sports_share']:.3f} | {pw['E_hat']:.4f} | {pw['se_h0']:.4f} | {pw['mde_programme']:.4f} | {pw['ratio']:.2f} | "
            f"{'yes' if pw['low_power'] else 'no'} |"
        )
    lines += ["", "## Exclusions, in the order of §6.3 (first reason counts)", ""]
    for name, t in r["trials"].items():
        lines += [f"### {name}", "", "| Reason | Markets |", "|---|---|"]
        for k, v in t["excluded"].items():
            lines.append(f"| {k} | {v} |")
        lines.append("")
    if r["gap_days"]["C1 and C1a (to 2026-12-28)"]["gap_days"]:
        lines += ["## Gap days (C1, C1a window)", "", "| Date | Kind |", "|---|---|"]
        for d, kind in sorted(g["gap_days"].items()):
            lines.append(f"| {d} | {kind} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--study-dir", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--amendment", default=None, help="the dated §16 gap amendment this re-run follows (§14 step 8)")
    a = ap.parse_args(argv)
    study = a.study_dir
    try:
        report = run_data_step(
            snapshot_root=study / "data" / "raw" / "snapshots",
            snapshot_log=study / "paper-log" / "snapshots.csv",
            status_jsonl=study / "data" / "raw" / "resolution" / "status.jsonl",
            results_dir=study / "results",
            fetch_log_csv=study / "paper-log" / "resolution_fetch.csv",
            amendment=a.amendment,
        )
    except Refusal as e:
        print(f"refused: {e}; nothing written")
        return 1
    c1 = report["trials"]["C1"]
    print(
        f"data step: candidates {report['counts']['candidates']}, windowed {report['counts']['windowed']}, "
        f"C1 n {c1['n']} G {c1['G']} ratio {c1['power']['ratio']:.2f}; "
        f"stop {report['stopped_for_amendment']}, halted {report['halted']}; written to results/"
    )
    if report["halted"]:
        return 5
    if report["stopped_for_amendment"]:
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
